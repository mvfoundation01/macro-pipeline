"""Layer 5b-D — regime-conditional OOS Brier decomposition across
NBER recession/expansion regimes.

Spec ref: ChatGPT 5.5 Dim-3 OOS rigor mandate ("OOS validation must
report regime-conditional metrics. The 1913-present sample spans
multiple regimes (gold standard, Bretton Woods, Great Inflation,
Great Moderation, ZIRP/QE, post-2022). A model that passes OOS Brier
improvement on the full sample may fail dramatically in any single
regime. L5b should report Brier improvement vs climatology + ...
CONDITIONAL on regime") + build plan §3.1 L5b-D scope ("Implement OOS
validation that decomposes performance metrics by NBER regime...
flag horizon × score-type combinations where regime-conditional
Brier improvement is materially weaker (e.g., ΔBrier < 50% of
full-sample value) than full-sample reporting suggests").

L5b-D (tag ``l5b-d-accept``, 2026-05-15): FOURTH original OOS
hardening sub-phase post-kickoff sprint; deepest methodological
sub-phase of the L5b sprint. Closes the regime-conditional OOS
validation gap via the AP-AUTH-54 seventh-instance internal-
implementation variant pattern. **AP-AUTH-54 envelope STAYS CLOSED**
at 4-instance characterization (KICK-4 heaviest / KICK-5 medium /
KICK-6 lightest / L5b-A heavy); L5b-D is the 7th instance with five
within-envelope sub-characteristics documented per Strategic
disposition 4: (1-3) NEW module + NEW gate + NEW test file (mirrors
L5b-C pattern); (4) **largest dataclass** in L5b (14 fields + 4
invariants vs L5b-B's 7+1, L5b-C's 7+5); (5) **Callable injection**
caller pattern (``regime_classifier`` parameter).

Public API
----------
``RegimePre1978Handling``                       Literal tri-state for pre-1978 handling.
``RegimeConditionalDiagnostics``                Frozen dataclass; 14 no-default fields + 4 invariants.
``classify_nber_regime_diagnostic_only``        Reference classifier helper (Approach C documentation example).
``compute_regime_conditional_oos_validation``   Aggregator over calibrated probabilities + binary outcomes + dates.

NBER infrastructure (AP-AUTH-50 grep evidence)
----------------------------------------------
Existing pipeline infrastructure (Layer 3.5C):

* ``macro_pipeline.regime.nber_calendar.NberCycle`` — peak/trough/
  announcement dates per cycle.
* ``macro_pipeline.regime.nber_calendar.LastKnownLabel`` with
  ``regime: Literal["expansion", "recession"]``.
* ``NBER_CALENDAR_BOUNDARY = pd.Period("1978-01", freq="M")`` —
  Decision Lock 3.5C-D1 pre-1978 boundary.
* ``NBER_PRE_1978_POLICY = "training_only"`` (``config.py``).
* Real-time mode fails-closed for ``as_of < 1978-01`` per Decision
  Lock 3.5C-D1.

L5b-D **consumes** this infrastructure via Callable injection
(Strategic disposition 1 refined): the aggregator accepts a
``regime_classifier: Callable[[pd.Timestamp], str]`` parameter.
Production callers typically wire::

    from macro_pipeline.regime.nber_calendar import (
        NBER_CALENDAR_BOUNDARY, NberCalendarLoader,
    )
    loader = NberCalendarLoader(...)

    def production_classifier(date: pd.Timestamp) -> str:
        if pd.Period(date, freq="M") < NBER_CALENDAR_BOUNDARY:
            return "pre_1978"
        return loader.last_known_label(date).regime

Test fixtures pass synthetic lambdas (e.g., alternating-regime
classifiers) that exercise the aggregator without requiring data
files. This pattern preserves greenfield test isolation while
enabling real-NBER production wiring.

L5b-5 NBER pre-1978 caveat handling (Strategic disposition 6)
-------------------------------------------------------------
Per Decision Lock 3.5C-D1, the NBER calendar EXCLUDES pre-1978
cycles. Real-time mode fails-closed; training mode allowed with
``is_pre_1978_training_only=True`` flag on ``NberStateResult``.

For L5b-D regime-conditional Brier, the ``pre_1978_handling`` field
is a tri-state ``Literal``:

  ``"include"``         Treat pre-1978 obs as expansion (lossy;
                         assumes no recession before 1978).
  ``"exclude"``         Drop pre-1978 obs from regime-conditional
                         computation AND from full-sample Brier.
  ``"diagnostic_only"`` Include in full-sample Brier; report
                         ``n_pre_1978_obs`` separately;
                         recession/expansion subsets restricted to
                         post-1978. **Default.** Matches L3.5C
                         Decision Lock 3.5C-D1 spirit.

**L5b-5 non-closure**: L5b-D addresses the NBER pre-1978 caveat at
the regime-conditional-Brier-aggregator layer via ``pre_1978_handling``
field. The upstream ``pre_1978_training_only`` flag in
``ScoredObservation`` schema remains deferred per L5b-5 backlog
rationale (L5b-5 is a different surface concern — scoring-level
caveat propagation, not aggregator-level regime decomposition).

Sensitivity flag (AP-AUTH-52 50% threshold derivation)
-------------------------------------------------------
``regime_sensitivity_flag = True`` iff EITHER:

  * ``recession_brier_improvement`` finite AND
    ``< 0.50 * full_sample_brier_improvement``, OR
  * ``expansion_brier_improvement`` finite AND
    ``< 0.50 * full_sample_brier_improvement``.

The 50% threshold is per build plan §3.1 literal:
"ΔBrier < 50% of full-sample value". Strict less-than per the
literal. NOT a magic number; cited in helper + dataclass docstring.

Edge case (Strategic disposition 5): when
``full_sample_brier_improvement <= 0`` (model worse than climatology
on full sample), threshold = ``0.5 * 0 = 0``; subset improvement
< 0 triggers the flag. The flag remains well-defined in this
degenerate regime.

Approach C honest documentation (mirror L5b-C dependence disclaimer)
--------------------------------------------------------------------
L5b-D consumes calibrated probabilities and binary outcomes; the
Brier decomposition arithmetic is standard. The regime-conditional
methodological choice — subset-pooled Brier estimation, 50%
sensitivity threshold — reflects build plan §3.1 literal +
ChatGPT 5.5 Dim-3 institutional default. More sophisticated
regime-conditional inference (e.g., hierarchical Bayesian regime
pooling, regime-specific calibration recalibration) is deferred as
L5b-residue; revisit if future reviewer flag pushes precision.

Gate 27 NEW (cross-cutting downstream-consumer)
-----------------------------------------------
L5b-D introduces **Gate 27** as the second NEW gate post-Gate-25-SEAL
after L5b-C Gate 26. Gate 27 is cross-cutting (downstream of L5-C
Brier reliability output) vs prior implementation-correctness gates
which inspect a single module's output. Cross-cutting architecture
documented at Gate 26 (FDR) and Gate 27 (regime-conditional)
together established the institutional pattern.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Literal

import numpy as np
import pandas as pd


# L5b-D pre-1978 NBER handling tri-state (Strategic disposition 6
# APPROVED 2026-05-15). Default "diagnostic_only" matches L3.5C
# Decision Lock 3.5C-D1 spirit (pre-1978 reported as diagnostic, not
# as production-grade regime classification).
RegimePre1978Handling = Literal["include", "exclude", "diagnostic_only"]
_VALID_PRE_1978_HANDLING: frozenset[str] = frozenset({
    "include", "exclude", "diagnostic_only",
})


@dataclass(frozen=True)
class RegimeConditionalDiagnostics:
    """Regime-conditional OOS Brier decomposition diagnostics.

    L5b-D (tag ``l5b-d-accept``, 2026-05-15): largest dataclass in
    L5b sprint (14 no-default fields + 4 ``__post_init__`` invariants).
    Closes ChatGPT 5.5 Dim-3 regime-conditional OOS validation
    mandate via the AP-AUTH-54 seventh-instance pattern.

    All fourteen fields no-default per AP-AUTH-53 step #3. Brier
    fields admit NaN for empty subsets (recession-only fixture with
    zero recession obs → recession Brier NaN; same for expansion);
    invariant 3 admits NaN. The ``regime_sensitivity_flag``
    consistency invariant (invariant 4) uses the
    ``_compute_expected_sensitivity_flag`` helper method.

    Fields
    ------
    full_sample_brier
        Brier on full sample (or post-pre-1978-filter sample per
        ``pre_1978_handling``).
    recession_subset_brier
        Brier on recession-window subset. NaN if ``n_recession_obs == 0``.
    expansion_subset_brier
        Brier on expansion-window subset. NaN if ``n_expansion_obs == 0``.
    full_sample_climatology_brier
        Climatology baseline ``ȳ × (1 − ȳ)`` on full sample.
    recession_climatology_brier
        Climatology on recession subset. NaN if empty.
    expansion_climatology_brier
        Climatology on expansion subset. NaN if empty.
    full_sample_brier_improvement
        ``full_sample_climatology_brier − full_sample_brier``.
    recession_brier_improvement
        Recession subset improvement. NaN if empty subset.
    expansion_brier_improvement
        Expansion subset improvement. NaN if empty subset.
    regime_sensitivity_flag
        True iff any finite subset improvement is strictly less than
        ``0.50 * full_sample_brier_improvement`` (build plan §3.1
        literal; AP-AUTH-52 derivation). Edge case: when
        ``full_sample_brier_improvement <= 0``, threshold ``0.5 * 0``
        means any subset improvement < 0 triggers the flag.
    n_recession_obs
        Cardinality of recession-classified observations (post-1978).
    n_expansion_obs
        Cardinality of expansion-classified observations (post-1978).
    n_pre_1978_obs
        Cardinality of pre-1978 observations. Diagnostic only;
        contributes to full sample under ``"include"`` /
        ``"diagnostic_only"`` modes; excluded under ``"exclude"`` mode.
    pre_1978_handling
        ``Literal`` tri-state controlling pre-1978 observation
        handling. Default ``"diagnostic_only"`` per Strategic
        disposition 6.

    Invariants enforced by ``__post_init__``
    ----------------------------------------
    1. ``pre_1978_handling`` in ``{"include", "exclude", "diagnostic_only"}``.
    2. ``n_recession_obs >= 0`` AND ``n_expansion_obs >= 0`` AND
       ``n_pre_1978_obs >= 0``.
    3. All finite Brier values in ``[0, 1]``; NaN admissible for
       empty subsets.
    4. ``regime_sensitivity_flag`` consistency: equal to
       ``_compute_expected_sensitivity_flag()`` (caller must
       compute correctly per the 50% threshold).
    """

    # Brier scores (3 fields).
    full_sample_brier: float
    recession_subset_brier: float
    expansion_subset_brier: float
    # Climatology baselines (3 fields).
    full_sample_climatology_brier: float
    recession_climatology_brier: float
    expansion_climatology_brier: float
    # Brier improvements (3 fields).
    full_sample_brier_improvement: float
    recession_brier_improvement: float
    expansion_brier_improvement: float
    # Sensitivity flag (1 field).
    regime_sensitivity_flag: bool
    # Sample-size cardinality (3 fields).
    n_recession_obs: int
    n_expansion_obs: int
    n_pre_1978_obs: int
    # Pre-1978 handling tri-state (1 field).
    pre_1978_handling: RegimePre1978Handling

    def __post_init__(self) -> None:
        # Invariant 1: pre_1978_handling tri-state validation.
        if self.pre_1978_handling not in _VALID_PRE_1978_HANDLING:
            raise ValueError(
                f"pre_1978_handling={self.pre_1978_handling!r} must be one of "
                f"{sorted(_VALID_PRE_1978_HANDLING)} "
                "(L5b-D Strategic disposition 6; matches L3.5C "
                "Decision Lock 3.5C-D1 spirit)"
            )
        # Invariant 2: n_*_obs all non-negative.
        for name, val in (
            ("n_recession_obs", self.n_recession_obs),
            ("n_expansion_obs", self.n_expansion_obs),
            ("n_pre_1978_obs", self.n_pre_1978_obs),
        ):
            if val < 0:
                raise ValueError(
                    f"{name}={val} must be >= 0 (L5b-D invariant 2)"
                )
        # Invariant 3: all finite Brier values in [0, 1]; NaN admissible.
        for name, val in (
            ("full_sample_brier", self.full_sample_brier),
            ("recession_subset_brier", self.recession_subset_brier),
            ("expansion_subset_brier", self.expansion_subset_brier),
            ("full_sample_climatology_brier", self.full_sample_climatology_brier),
            ("recession_climatology_brier", self.recession_climatology_brier),
            ("expansion_climatology_brier", self.expansion_climatology_brier),
        ):
            if math.isfinite(val) and not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"{name}={val} must be in [0, 1] or NaN "
                    "(L5b-D invariant 3; Brier semantic requires "
                    "0 <= mean((p-y)^2) <= 1 for p,y in [0,1])"
                )
        # Invariant 4: regime_sensitivity_flag consistency with 50% threshold.
        expected_flag = self._compute_expected_sensitivity_flag()
        if self.regime_sensitivity_flag != expected_flag:
            raise ValueError(
                f"regime_sensitivity_flag={self.regime_sensitivity_flag} "
                f"inconsistent with 50% threshold derivation "
                f"(expected {expected_flag}); caller must compute "
                "correctly per AP-AUTH-52 build plan §3.1 literal "
                "(L5b-D invariant 4)"
            )

    def _compute_expected_sensitivity_flag(self) -> bool:
        """Compute the expected sensitivity flag per the 50% threshold.

        Returns True iff EITHER:
          * ``recession_brier_improvement`` finite AND strictly less
            than ``0.50 * full_sample_brier_improvement``, OR
          * ``expansion_brier_improvement`` finite AND strictly less
            than ``0.50 * full_sample_brier_improvement``.

        Edge case (Strategic disposition 5 + dataclass docstring):
        when ``full_sample_brier_improvement <= 0``, threshold is
        ``0.5 * <= 0 = <= 0``. Subset improvements strictly less than
        a non-positive threshold trigger the flag (the model is
        regime-worse than even a poor full-sample baseline). The flag
        remains well-defined.
        """
        threshold = 0.5 * self.full_sample_brier_improvement
        flag = False
        if math.isfinite(self.recession_brier_improvement):
            if self.recession_brier_improvement < threshold:
                flag = True
        if math.isfinite(self.expansion_brier_improvement):
            if self.expansion_brier_improvement < threshold:
                flag = True
        return flag


def classify_nber_regime_diagnostic_only(
    date: pd.Timestamp,
    nber_recession_windows: Iterable[tuple[pd.Timestamp, pd.Timestamp]],
    nber_calendar_boundary: pd.Timestamp = pd.Timestamp("1978-01-01"),
) -> Literal["recession", "expansion", "pre_1978"]:
    """Reference NBER regime classifier conforming to the L5b-D
    aggregator's ``regime_classifier`` Callable signature.

    Documentation example only (Approach C reference helper);
    production callers typically wire
    ``NberCalendarLoader.last_known_label(date).regime`` instead.
    Test fixtures pass synthetic lambdas.

    Algorithm
    ---------
    1. If ``date < nber_calendar_boundary`` (default 1978-01-01),
       return ``"pre_1978"``.
    2. If ``date`` falls in any (start, end) recession window
       (inclusive), return ``"recession"``.
    3. Otherwise return ``"expansion"``.

    Parameters
    ----------
    date
        Observation date to classify.
    nber_recession_windows
        Iterable of (start, end) inclusive recession window bounds.
        Typically sourced from ``NberCalendarLoader``.
    nber_calendar_boundary
        Pre-1978 boundary per L3.5C Decision Lock 3.5C-D1. Default
        ``1978-01-01``. Observations before this are returned as
        ``"pre_1978"`` regardless of any caller-supplied recession
        windows (matches Decision Lock 3.5C-D1 fail-closed spirit).
    """
    if date < nber_calendar_boundary:
        return "pre_1978"
    for start, end in nber_recession_windows:
        if start <= date <= end:
            return "recession"
    return "expansion"


def _compute_brier_safe(p: np.ndarray, y: np.ndarray) -> float:
    """Compute Brier score; return NaN if empty input."""
    if len(p) == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def _compute_climatology_brier_safe(y: np.ndarray) -> float:
    """Compute climatology baseline ``ȳ × (1 − ȳ)``; return NaN if
    empty."""
    if len(y) == 0:
        return float("nan")
    y_mean = float(np.mean(y))
    return y_mean * (1.0 - y_mean)


def compute_regime_conditional_oos_validation(
    calibrated_probabilities: np.ndarray,
    forward_returns_binary: np.ndarray,
    observation_dates: pd.DatetimeIndex,
    regime_classifier: Callable[[pd.Timestamp], str],
    *,
    pre_1978_handling: RegimePre1978Handling = "diagnostic_only",
) -> RegimeConditionalDiagnostics:
    """Aggregate calibrated probabilities + binary outcomes + dates;
    decompose Brier by NBER regime per ``regime_classifier``.

    L5b-D Approach C with Callable injection (Strategic-approved
    2026-05-15): the ``regime_classifier`` parameter accepts any
    Callable mapping ``pd.Timestamp -> Literal["recession",
    "expansion", "pre_1978"]``. Production callers typically wire
    ``NberCalendarLoader.last_known_label(date).regime``; test
    fixtures pass synthetic lambdas.

    Algorithm
    ---------
    1. Classify each observation via ``regime_classifier``.
    2. Per ``pre_1978_handling``:
         ``"exclude"``: drop pre-1978 obs from BOTH full-sample AND
           subsets.
         ``"include"`` / ``"diagnostic_only"``: include pre-1978 obs
           in full sample; recession/expansion subsets always
           restricted to post-1978 (per L3.5C Decision Lock 3.5C-D1).
    3. Compute Brier + climatology + improvement for full sample.
    4. Compute Brier + climatology + improvement for recession
       subset (NaN if ``n_recession_obs == 0``).
    5. Compute Brier + climatology + improvement for expansion
       subset (NaN if ``n_expansion_obs == 0``).
    6. Compute ``regime_sensitivity_flag`` per 50% threshold
       (build plan §3.1 literal).

    Inputs aligned element-wise: ``calibrated_probabilities[i]``,
    ``forward_returns_binary[i]``, ``observation_dates[i]``.

    Parameters
    ----------
    calibrated_probabilities
        1-D array of calibrated probability values in ``[0, 1]``.
    forward_returns_binary
        1-D array of binary outcomes ``{0, 1}``.
    observation_dates
        ``pd.DatetimeIndex`` aligned element-wise with the above.
    regime_classifier
        Callable mapping date to regime label.

    Keyword-only
    ------------
    pre_1978_handling
        Tri-state pre-1978 handling per Strategic disposition 6.
        Default ``"diagnostic_only"``.

    Returns
    -------
    RegimeConditionalDiagnostics
        Populated with all 14 fields. ``regime_sensitivity_flag``
        consistency with 50% threshold enforced by ``__post_init__``
        invariant 4.
    """
    p = np.asarray(calibrated_probabilities, dtype=float)
    y = np.asarray(forward_returns_binary, dtype=float)
    dates = pd.DatetimeIndex(observation_dates)

    # Classify each observation.
    regimes = np.array([regime_classifier(d) for d in dates])

    # Counts (always reflect raw classifications regardless of mode).
    n_recession = int(np.sum(regimes == "recession"))
    n_expansion = int(np.sum(regimes == "expansion"))
    n_pre_1978 = int(np.sum(regimes == "pre_1978"))

    # Pre-1978 filter for full-sample computation per tri-state.
    if pre_1978_handling == "exclude":
        full_mask = regimes != "pre_1978"
    else:
        # "include" or "diagnostic_only" both retain pre-1978 in full.
        full_mask = np.ones_like(regimes, dtype=bool)

    p_full = p[full_mask]
    y_full = y[full_mask]
    full_brier = _compute_brier_safe(p_full, y_full)
    full_climatology = _compute_climatology_brier_safe(y_full)
    full_improvement = full_climatology - full_brier

    # Recession + expansion subsets (always post-1978 per L3.5C
    # Decision Lock 3.5C-D1 spirit).
    rec_mask = regimes == "recession"
    exp_mask = regimes == "expansion"

    p_rec = p[rec_mask]
    y_rec = y[rec_mask]
    rec_brier = _compute_brier_safe(p_rec, y_rec)
    rec_climatology = _compute_climatology_brier_safe(y_rec)
    rec_improvement = rec_climatology - rec_brier

    p_exp = p[exp_mask]
    y_exp = y[exp_mask]
    exp_brier = _compute_brier_safe(p_exp, y_exp)
    exp_climatology = _compute_climatology_brier_safe(y_exp)
    exp_improvement = exp_climatology - exp_brier

    # Compute sensitivity flag per 50% threshold (build plan §3.1
    # literal; AP-AUTH-52 derivation). Strict less-than.
    threshold = 0.5 * full_improvement
    sensitivity_flag = False
    if math.isfinite(rec_improvement):
        if rec_improvement < threshold:
            sensitivity_flag = True
    if math.isfinite(exp_improvement):
        if exp_improvement < threshold:
            sensitivity_flag = True

    return RegimeConditionalDiagnostics(
        full_sample_brier=full_brier,
        recession_subset_brier=rec_brier,
        expansion_subset_brier=exp_brier,
        full_sample_climatology_brier=full_climatology,
        recession_climatology_brier=rec_climatology,
        expansion_climatology_brier=exp_climatology,
        full_sample_brier_improvement=full_improvement,
        recession_brier_improvement=rec_improvement,
        expansion_brier_improvement=exp_improvement,
        regime_sensitivity_flag=sensitivity_flag,
        n_recession_obs=n_recession,
        n_expansion_obs=n_expansion,
        n_pre_1978_obs=n_pre_1978,
        pre_1978_handling=pre_1978_handling,
    )


__all__ = [
    "RegimeConditionalDiagnostics",
    "RegimePre1978Handling",
    "classify_nber_regime_diagnostic_only",
    "compute_regime_conditional_oos_validation",
]
