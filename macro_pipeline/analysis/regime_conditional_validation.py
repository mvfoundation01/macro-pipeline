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
from typing import TYPE_CHECKING, Callable, Iterable, Literal, Optional

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    # L5b-F Phase 4 — Lucas critique field type (forward ref to avoid
    # runtime circular import via macro_pipeline.models.return_forecast).
    from macro_pipeline.models.return_forecast import StructuralBreakDiagnostics


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
    # L5b-F Phase 2 — sample-size + confidence cap fields (5 fields;
    # closes Codex 5.5 + ChatGPT 5.5 R6 finding F-H2 on regime-stratified
    # confidence caps + Standing Order #10 10Y hard cap).
    horizon: int                    # Forecast horizon in YEARS (1, 3, 5, 10)
    n_eff_recession: int            # Effective non-overlapping sample (= n_recession_obs // (horizon * 12))
    n_eff_expansion: int            # Effective non-overlapping sample (= n_expansion_obs // (horizon * 12))
    max_confidence_cap: float       # 0.55 for 10Y regime-stratified per Standing Order #10; 0.85 otherwise
    diagnostic_only: bool           # True iff min(n_eff_recession, n_eff_expansion) < 5
    # L5b-F Phase 4 — Murphy 1973 decomposition by stratum (8 fields;
    # closes R6 finding F-M5 on regime-conditional Brier decomposition).
    # Murphy identity: Brier = reliability - resolution + uncertainty
    # per stratum. NaN admissible for empty subsets.
    reliability_recession: float
    resolution_recession: float
    uncertainty_recession: float
    reliability_expansion: float
    resolution_expansion: float
    uncertainty_expansion: float
    murphy_ci_recession: tuple[float, float]    # (lower, upper) bootstrap CI on recession Brier
    murphy_ci_expansion: tuple[float, float]    # (lower, upper) bootstrap CI on expansion Brier
    # L5b-F Phase 4 — OOD reserve (F-M2 fail-closed; Vision v2.0 §7).
    ood_reserve_fraction: Optional[float]       # 0.05-0.15 per Vision §7; None admissible for dataclass-direct testing
    # L5b-F Phase 4 — Lucas critique surface (F-M3).
    lucas_flag: bool                            # True iff regime shift detected within Lucas lookback window
    regime_shift_test: Optional["StructuralBreakDiagnostics"]  # Optional; populated when Lucas check requested
    pre_post_metric_delta: Optional[float]      # Optional; Brier delta pre vs post detected shift
    lucas_warning_text: Optional[str]           # Optional; human-readable Lucas warning when flag fires

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
        # L5b-F Phase 2 invariants (5-9) — sample-size + confidence cap.
        # Invariant 5: horizon must be a positive integer (years).
        if self.horizon <= 0:
            raise ValueError(
                f"horizon={self.horizon} must be > 0 (L5b-F Phase 2 "
                "invariant 5; horizon is forecast horizon in years)"
            )
        # Invariant 6: n_eff_recession + n_eff_expansion must be
        # non-negative (effective non-overlapping sample sizes).
        for name, val in (
            ("n_eff_recession", self.n_eff_recession),
            ("n_eff_expansion", self.n_eff_expansion),
        ):
            if val < 0:
                raise ValueError(
                    f"{name}={val} must be >= 0 "
                    "(L5b-F Phase 2 invariant 6)"
                )
        # Invariant 7: max_confidence_cap must be in [0, 1].
        if not (0.0 <= self.max_confidence_cap <= 1.0):
            raise ValueError(
                f"max_confidence_cap={self.max_confidence_cap} must be "
                "in [0, 1] (L5b-F Phase 2 invariant 7)"
            )
        # Invariant 8: max_confidence_cap consistency with horizon per
        # Standing Order #10 (10Y regime-stratified hard cap 0.55) +
        # Vision v2.0 §10 (other horizons cap 0.85).
        expected_cap = 0.55 if self.horizon == 10 else 0.85
        if not math.isclose(self.max_confidence_cap, expected_cap, abs_tol=1e-9):
            raise ValueError(
                f"max_confidence_cap={self.max_confidence_cap} "
                f"inconsistent with horizon={self.horizon}: expected "
                f"{expected_cap} (L5b-F Phase 2 invariant 8 — Standing "
                "Order #10: 10Y regime-stratified cap = 0.55; other "
                "horizons cap = 0.85 per Vision v2.0 §10)"
            )
        # Invariant 9: diagnostic_only consistency with n_eff threshold
        # (True iff min(n_eff_recession, n_eff_expansion) < 5).
        expected_diag = min(self.n_eff_recession, self.n_eff_expansion) < 5
        if self.diagnostic_only != expected_diag:
            raise ValueError(
                f"diagnostic_only={self.diagnostic_only} inconsistent "
                f"with min(n_eff_recession={self.n_eff_recession}, "
                f"n_eff_expansion={self.n_eff_expansion})="
                f"{min(self.n_eff_recession, self.n_eff_expansion)} "
                f"(expected {expected_diag} per L5b-F Phase 2 invariant "
                "9: True iff min(n_eff_*) < 5)"
            )
        # L5b-F Phase 4 invariants (10-13) — Murphy + OOD + Lucas.
        # Invariant 10: Murphy decomposition consistency per stratum
        # (Brier = reliability - resolution + uncertainty within 1e-6).
        # Skip check when ANY component is NaN (empty subset case).
        for stratum, brier, rel, res, unc in (
            ("recession", self.recession_subset_brier,
             self.reliability_recession, self.resolution_recession,
             self.uncertainty_recession),
            ("expansion", self.expansion_subset_brier,
             self.reliability_expansion, self.resolution_expansion,
             self.uncertainty_expansion),
        ):
            if (math.isfinite(brier) and math.isfinite(rel)
                    and math.isfinite(res) and math.isfinite(unc)):
                identity = rel - res + unc
                if not math.isclose(identity, brier, abs_tol=1e-6):
                    raise ValueError(
                        f"L5b-F Phase 4 invariant 10 violation: "
                        f"{stratum} Murphy identity reliability "
                        f"({rel}) - resolution ({res}) + uncertainty "
                        f"({unc}) = {identity} != brier ({brier}) "
                        "within 1e-6"
                    )
        # Invariant 11: Murphy CI bounds (lower <= upper) per stratum.
        for stratum, ci in (
            ("recession", self.murphy_ci_recession),
            ("expansion", self.murphy_ci_expansion),
        ):
            if not isinstance(ci, tuple) or len(ci) != 2:
                raise ValueError(
                    f"L5b-F Phase 4 invariant 11 violation: "
                    f"murphy_ci_{stratum}={ci} must be a 2-tuple of floats"
                )
            lo, hi = ci
            if math.isfinite(lo) and math.isfinite(hi):
                if lo > hi:
                    raise ValueError(
                        f"L5b-F Phase 4 invariant 11 violation: "
                        f"murphy_ci_{stratum} lower {lo} > upper {hi}"
                    )
        # Invariant 12: OOD reserve fraction bounds per Vision §7
        # (5-15% range). None admissible for dataclass-direct construction.
        if self.ood_reserve_fraction is not None:
            if not (0.05 <= self.ood_reserve_fraction <= 0.15):
                raise ValueError(
                    f"ood_reserve_fraction={self.ood_reserve_fraction} "
                    "must be in [0.05, 0.15] per Vision v2.0 §7 OOD "
                    "reserve discipline (L5b-F Phase 4 invariant 12); "
                    "pass None at dataclass-direct construction time"
                )
        # Invariant 13: Lucas consistency — if lucas_flag True, then
        # regime_shift_test must be non-None AND lucas_warning_text
        # must be non-None (caller must populate the surface when flag
        # fires). If lucas_flag False, fields may be None.
        if self.lucas_flag:
            if self.regime_shift_test is None:
                raise ValueError(
                    "L5b-F Phase 4 invariant 13 violation: lucas_flag=True "
                    "requires regime_shift_test to be non-None"
                )
            if self.lucas_warning_text is None:
                raise ValueError(
                    "L5b-F Phase 4 invariant 13 violation: lucas_flag=True "
                    "requires lucas_warning_text to be non-None"
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


def _murphy_decomposition(
    p: np.ndarray, y: np.ndarray, n_bins: int = 10,
) -> tuple[float, float, float]:
    """Murphy (1973) reliability + resolution + uncertainty decomposition.

    Closes Codex 5.5 + ChatGPT 5.5 R6 finding F-M5 on regime-conditional
    Brier decomposition.

    Identity: ``Brier = reliability - resolution + uncertainty`` where
    each term is computed over equal-width probability bins (10 default,
    matching the L5-C Brier reliability decomposition convention).

    Returns
    -------
    (reliability, resolution, uncertainty) : tuple of float
        NaN for all three if ``p`` is empty (empty subset case).
    """
    if len(p) == 0:
        return float("nan"), float("nan"), float("nan")
    n = len(p)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(p, bin_edges) - 1, 0, n_bins - 1)
    y_mean = float(np.mean(y))
    uncertainty = y_mean * (1.0 - y_mean)
    reliability = 0.0
    resolution = 0.0
    for k in range(n_bins):
        mask = bin_idx == k
        n_k = int(mask.sum())
        if n_k == 0:
            continue
        p_k_mean = float(np.mean(p[mask]))
        y_k_mean = float(np.mean(y[mask]))
        reliability += (n_k / n) * (p_k_mean - y_k_mean) ** 2
        resolution += (n_k / n) * (y_k_mean - y_mean) ** 2
    return float(reliability), float(resolution), float(uncertainty)


def _stationary_bootstrap_brier_ci(
    p: np.ndarray, y: np.ndarray,
    *,
    n_bootstrap: int = 200,
    mean_block_length: int = 12,
    seed: int = 42,
) -> tuple[float, float]:
    """Politis-Romano (1994) stationary block bootstrap CI on Brier.

    Reuses the L5b-A geometric block-length sampler from
    ``macro_pipeline.models.return_forecast._sample_stationary_block_lengths``
    for serial-dependence-robust CI estimation per ChatGPT 5.5 R6
    finding F-M5.

    Test-mode bootstrap N defaults to 200 per pre-flight §11 risk #3
    mitigation (keeps test runtime bounded; production callers can
    raise N at call site).

    Returns
    -------
    (lower, upper) : tuple of float
        (2.5th, 97.5th) percentiles of the bootstrap Brier distribution.
        NaN for both if ``p`` is empty.
    """
    if len(p) == 0:
        return float("nan"), float("nan")
    # Lazy import to avoid circular dependency at module load time.
    from macro_pipeline.models.return_forecast import (
        _sample_stationary_block_lengths,
    )
    n = len(p)
    rng = np.random.default_rng(seed)
    brier_samples = np.empty(n_bootstrap, dtype=float)
    for b in range(n_bootstrap):
        # Draw block lengths via L5b-A helper (Politis-Romano geometric).
        block_lengths = _sample_stationary_block_lengths(
            n_obs=n, mean_block_length=mean_block_length, rng=rng,
        )
        # Draw uniform start indices per block.
        start_indices = rng.integers(0, n, size=len(block_lengths))
        # Assemble indices via cyclic wrap; truncate to n.
        idx_list: list[int] = []
        for s, bl in zip(start_indices, block_lengths):
            for j in range(int(bl)):
                idx_list.append(int((s + j) % n))
                if len(idx_list) >= n:
                    break
            if len(idx_list) >= n:
                break
        idx = np.array(idx_list[:n])
        p_b = p[idx]
        y_b = y[idx]
        brier_samples[b] = float(np.mean((p_b - y_b) ** 2))
    lower = float(np.percentile(brier_samples, 2.5))
    upper = float(np.percentile(brier_samples, 97.5))
    return lower, upper


def compute_regime_conditional_oos_validation(
    calibrated_probabilities: np.ndarray,
    forward_returns_binary: np.ndarray,
    observation_dates: pd.DatetimeIndex,
    regime_classifier: Callable[[pd.Timestamp], str],
    *,
    horizon: int,
    ood_reserve_fraction: float,
    pre_1978_handling: RegimePre1978Handling = "diagnostic_only",
    compute_murphy_decomposition: bool = False,
    regime_shift_test: Optional["StructuralBreakDiagnostics"] = None,
    lucas_lookback_months: int = 24,
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

    # L5b-F Phase 3 (F-H4) — fail-closed classifier output validation
    # (closes R6 finding F-H4 on silent classifier misbehavior). Reject
    # any regime label outside the canonical tri-state taxonomy with a
    # ValueError citing the offending label(s); guarantees that the
    # downstream count/mask logic operates on a known-clean label set.
    _valid_regime_labels = {"recession", "expansion", "pre_1978"}
    _unique_labels = set(regimes.tolist())
    _invalid_labels = _unique_labels - _valid_regime_labels
    if _invalid_labels:
        raise ValueError(
            f"regime_classifier returned invalid regime label(s) "
            f"{sorted(_invalid_labels)}; must be subset of "
            f"{sorted(_valid_regime_labels)} per L5b-D tri-state "
            "taxonomy (L5b-F F-H4 fail-closed classifier validation)"
        )

    # Raw classification counts (defensive cardinality check
    # post-validation — these MUST sum to len(dates) by construction
    # once labels are validated above; explicit assertion guards
    # against future regressions in the classifier path).
    n_recession_raw = int(np.sum(regimes == "recession"))
    n_expansion_raw = int(np.sum(regimes == "expansion"))
    n_pre_1978_raw = int(np.sum(regimes == "pre_1978"))
    if n_recession_raw + n_expansion_raw + n_pre_1978_raw != len(dates):
        raise ValueError(
            f"L5b-F F-H4 cardinality violation: n_recession_raw="
            f"{n_recession_raw} + n_expansion_raw={n_expansion_raw} "
            f"+ n_pre_1978_raw={n_pre_1978_raw} = "
            f"{n_recession_raw + n_expansion_raw + n_pre_1978_raw} "
            f"!= len(dates)={len(dates)}; classifier output bucket "
            "split inconsistent (defense-in-depth post-validation)"
        )

    # L5b-F Phase 3 (F-H3) — mode-conditional count aggregation.
    # Per docstring §"include" semantics ("treat pre-1978 obs as
    # expansion; lossy"), the "include" mode aggregates pre-1978
    # cardinality INTO the expansion bucket for n_expansion_obs
    # reporting + downstream Brier computation. Other modes report
    # raw classifier counts. n_pre_1978_obs always reflects raw
    # classifier count for diagnostic visibility (independent of mode).
    n_recession = n_recession_raw
    n_pre_1978 = n_pre_1978_raw  # always raw (diagnostic)
    if pre_1978_handling == "include":
        n_expansion = n_expansion_raw + n_pre_1978_raw  # absorb pre_1978
    else:
        n_expansion = n_expansion_raw

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

    # Recession + expansion subsets per L3.5C Decision Lock 3.5C-D1.
    # L5b-F Phase 3 (F-H3): "include" mode aggregates pre-1978 obs
    # into the expansion subset (matches docstring §"include" semantic
    # "treat pre-1978 obs as expansion (lossy; assumes no recession
    # before 1978)"). Other modes restrict expansion to post-1978
    # per the original L3.5C policy.
    rec_mask = regimes == "recession"
    if pre_1978_handling == "include":
        exp_mask = (regimes == "expansion") | (regimes == "pre_1978")
    else:
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

    # L5b-F Phase 2 (F-H2) — sample-size + confidence cap fields.
    # n_eff = n_obs // (horizon * 12)  (effective non-overlapping
    # sample at monthly observation frequency; mirrors L5b-A's
    # n_eff_nonoverlap pattern from analysis/effective_sample_size.py).
    horizon_months = horizon * 12
    n_eff_rec = n_recession // horizon_months
    n_eff_exp = n_expansion // horizon_months
    # max_confidence_cap per Standing Order #10 (10Y regime-stratified
    # hard cap 0.55) + Vision v2.0 §10 (other horizons 0.85).
    cap = 0.55 if horizon == 10 else 0.85
    # diagnostic_only when either stratum has <5 effective non-
    # overlapping observations (Vision v2.0 §10 sample-size honesty).
    diagnostic = min(n_eff_rec, n_eff_exp) < 5

    # L5b-F Phase 4 (F-M2) — fail-closed OOD reserve validation per
    # Vision v2.0 §7 (5-15% reserve mass mandatory). Reject None at
    # aggregator entry (caller must explicitly supply); dataclass
    # admits None for direct-construction testing only.
    if ood_reserve_fraction is None:
        raise ValueError(
            "ood_reserve_fraction is required at "
            "compute_regime_conditional_oos_validation entry per "
            "Vision v2.0 §7 OOD reserve discipline (L5b-F F-M2 "
            "fail-closed). L5b-D produces stratified Brier "
            "diagnostics, NOT scenario-complete probabilities; "
            "caller must supply a 5-15% OOD reserve mass explicitly."
        )
    if not (0.05 <= ood_reserve_fraction <= 0.15):
        raise ValueError(
            f"ood_reserve_fraction={ood_reserve_fraction} must be in "
            "[0.05, 0.15] per Vision v2.0 §7 (L5b-F F-M2)"
        )

    # L5b-F Phase 4 (F-M5) — Murphy 1973 decomposition by stratum.
    # Computed via opt-in flag (default False yields NaN tuples per
    # documented degenerate semantics).
    if compute_murphy_decomposition:
        rel_rec, res_rec, unc_rec = _murphy_decomposition(p_rec, y_rec)
        rel_exp, res_exp, unc_exp = _murphy_decomposition(p_exp, y_exp)
        ci_rec = _stationary_bootstrap_brier_ci(p_rec, y_rec)
        ci_exp = _stationary_bootstrap_brier_ci(p_exp, y_exp)
        # Re-derive subset Brier values from Murphy identity to enforce
        # invariant 10 (Brier == reliability - resolution + uncertainty)
        # at machine precision. Empty subsets stay NaN.
        if (math.isfinite(rel_rec) and math.isfinite(res_rec)
                and math.isfinite(unc_rec)):
            rec_brier = rel_rec - res_rec + unc_rec
        if (math.isfinite(rel_exp) and math.isfinite(res_exp)
                and math.isfinite(unc_exp)):
            exp_brier = rel_exp - res_exp + unc_exp
    else:
        rel_rec = res_rec = unc_rec = float("nan")
        rel_exp = res_exp = unc_exp = float("nan")
        ci_rec = (float("nan"), float("nan"))
        ci_exp = (float("nan"), float("nan"))

    # L5b-F Phase 4 (F-M3) — Lucas critique detection.
    lucas_flag = False
    pre_post_metric_delta: Optional[float] = None
    lucas_warning_text: Optional[str] = None
    if regime_shift_test is not None:
        # Check break date within Lucas lookback window from most-recent
        # observation. Reuses L5b-B `StructuralBreakDiagnostics.break_dates_detected`.
        break_dates = getattr(regime_shift_test, "break_dates_detected", ())
        if break_dates and len(dates) > 0:
            most_recent = dates.max()
            lookback_start = most_recent - pd.DateOffset(
                months=lucas_lookback_months,
            )
            recent_breaks = [
                bd for bd in break_dates
                if pd.Timestamp(bd) >= lookback_start
            ]
            if recent_breaks:
                lucas_flag = True
                # Compute Brier pre vs post most-recent break (simple
                # split; documented as approximate per pre-flight).
                latest_break = max(pd.Timestamp(bd) for bd in recent_breaks)
                pre_mask = dates < latest_break
                post_mask = dates >= latest_break
                if pre_mask.any() and post_mask.any():
                    brier_pre = _compute_brier_safe(p[pre_mask], y[pre_mask])
                    brier_post = _compute_brier_safe(p[post_mask], y[post_mask])
                    if math.isfinite(brier_pre) and math.isfinite(brier_post):
                        pre_post_metric_delta = float(brier_post - brier_pre)
                lucas_warning_text = (
                    f"Lucas critique flag: structural break detected at "
                    f"{latest_break.date()} within {lucas_lookback_months}M "
                    "lookback window; historical relationships may not "
                    "extrapolate forward. Review regime-conditional Brier "
                    "trajectory pre vs post detected shift."
                )

    # Recompute sensitivity flag if Murphy recomputed Brier values
    # (rare but possible drift at 1e-15 scale).
    threshold_post = 0.5 * full_improvement
    sensitivity_flag_final = False
    rec_improvement_final = (
        rec_climatology - rec_brier if math.isfinite(rec_brier) else float("nan")
    )
    exp_improvement_final = (
        exp_climatology - exp_brier if math.isfinite(exp_brier) else float("nan")
    )
    if math.isfinite(rec_improvement_final):
        if rec_improvement_final < threshold_post:
            sensitivity_flag_final = True
    if math.isfinite(exp_improvement_final):
        if exp_improvement_final < threshold_post:
            sensitivity_flag_final = True

    return RegimeConditionalDiagnostics(
        full_sample_brier=full_brier,
        recession_subset_brier=rec_brier,
        expansion_subset_brier=exp_brier,
        full_sample_climatology_brier=full_climatology,
        recession_climatology_brier=rec_climatology,
        expansion_climatology_brier=exp_climatology,
        full_sample_brier_improvement=full_improvement,
        recession_brier_improvement=rec_improvement_final,
        expansion_brier_improvement=exp_improvement_final,
        regime_sensitivity_flag=sensitivity_flag_final,
        n_recession_obs=n_recession,
        n_expansion_obs=n_expansion,
        n_pre_1978_obs=n_pre_1978,
        pre_1978_handling=pre_1978_handling,
        horizon=horizon,
        n_eff_recession=n_eff_rec,
        n_eff_expansion=n_eff_exp,
        max_confidence_cap=cap,
        diagnostic_only=diagnostic,
        reliability_recession=rel_rec,
        resolution_recession=res_rec,
        uncertainty_recession=unc_rec,
        reliability_expansion=rel_exp,
        resolution_expansion=res_exp,
        uncertainty_expansion=unc_exp,
        murphy_ci_recession=ci_rec,
        murphy_ci_expansion=ci_exp,
        ood_reserve_fraction=ood_reserve_fraction,
        lucas_flag=lucas_flag,
        regime_shift_test=regime_shift_test,
        pre_post_metric_delta=pre_post_metric_delta,
        lucas_warning_text=lucas_warning_text,
    )


__all__ = [
    "RegimeConditionalDiagnostics",
    "RegimePre1978Handling",
    "classify_nber_regime_diagnostic_only",
    "compute_regime_conditional_oos_validation",
]
