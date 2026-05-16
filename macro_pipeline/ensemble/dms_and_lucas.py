"""L6-H DMS dynamic selector + Lucas critique runtime diagnostics.

Per Strategic L6-H R7 closure pre-flight 2026-05-16. Closes ChatGPT
methodology Finding #9 (C-11): DMS adjustment must propagate INTO the
L6 forecast output (not just surface as a side metric), and Lucas
critique runtime flag + reason codes must be exposed in the aggregator
output for downstream consumers.

Sub-module scope
----------------
This module exposes two L6-H surfaces:

  ``select_dms_adjustment_bps``       Risk-count-driven tier table that
                                      maps (horizon, risk flags) -> bps +
                                      selection reason. Applied to 5Y/10Y
                                      only per Vision §8 (1Y/3Y get 0 bps
                                      since cyclical noise dominates).
  ``LucasCritiqueDiagnostics``        Frozen dataclass carrying the Lucas
                                      flag + reason codes + structural-
                                      break evidence dict per Vision §9.
  ``compute_lucas_diagnostics``       Helper that derives the flag + reason
                                      codes from a structural-break
                                      evidence dict (≥2 evidence values
                                      above threshold → flag fires).

The existing L5-F module ``macro_pipeline.models.dms_adjustment`` ships
the Q6-locked midpoint constants (-125 5Y, -175 10Y) for *raw* forecast
adjustment. This L6-H selector layers a risk-count-driven tier above
the midpoint anchor to surface the Vision §8 "lower end / higher end"
range distinction at the ensemble aggregator output, with reason codes
for audit. The two layers are complementary:

  L5-F ``apply_dms_adjustment``         Q6-locked midpoint; spec §5.F.1
                                        constant-arithmetic surface.
  L6-H ``select_dms_adjustment_bps``    Dynamic tier table for the
                                        aggregator HorizonResult.

DMS selector tier table (L6-H per Strategic D5 spec)
----------------------------------------------------
For ``horizon ∈ {5, 10}`` (1Y/3Y return 0 bps):

  risk_count    bps         selection_reason
  0             -100        "structural_edge_persists"
  1             -150        "single_risk_factor"
  2+            -200        "multiple_risk_factors"

``risk_count`` is the sum of four bool risk flags:
``valuation_extreme``, ``concentration_extreme``,
``fiscal_risks_elevated``, ``reserve_currency_risk``.

Note re Vision §8 ranges: §8 specifies horizon-conditional ranges
(5Y: -100/-150; 10Y: -150/-200). The L6-H selector uses a UNIFIED
tier table across 5Y/10Y per Strategic spec. The 10Y "structural
edge persists" tier (-100 bps) deviates from §8's 10Y lower bound
(-150 bps); this is acknowledged as a simplified L6-H operationalisation
of the Vision §8 RANGE narrative, with the L5-F midpoint anchor
(-175 10Y central) retained as the spec §5.F.4 Q6-locked source-of-
truth. Future refinement may bring the L6-H selector into full
alignment with §8 per-horizon ranges.

Lucas critique diagnostics (L6-H per Strategic D5 spec)
-------------------------------------------------------
Vision §9 enumerates 7 structural-break trigger categories. The L6-H
``compute_lucas_diagnostics`` accepts a dict mapping reason codes
(subset of: ``fed_reaction_shift``, ``fiscal_dominance``,
``balance_sheet_dominance``, ``nbfi_transmission``,
``ai_productivity_shift``, ``inflation_target_credibility``,
``treasury_issuance_structure``) to a numeric evidence value in
[0, 1]. The flag fires when ≥2 evidence values exceed
``LUCAS_THRESHOLD_DEFAULT`` (0.5). Reason codes are returned for
the breached subset.

Upstream sourcing is OUT OF SCOPE for L6-H per mandate §11 risk #4
(deferred to L6-J if needed). The aggregator accepts the evidence
dict as an OPTIONAL input; callers without diagnostics pass ``None``
which yields a default ``LucasCritiqueDiagnostics(flag=False,
reason_codes=(), structural_break_evidence={})``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# Vision §8 horizon eligibility for DMS adjustment.
DMS_ELIGIBLE_HORIZONS = (5, 10)
DMS_ZERO_HORIZONS = (1, 3)

# L6-H Strategic D5 unified tier table (applied to 5Y + 10Y per mandate).
# Negative bps = downward survivorship adjustment.
DMS_TIER_0_BPS = -100.0  # structural_edge_persists
DMS_TIER_1_BPS = -150.0  # single_risk_factor
DMS_TIER_2_BPS = -200.0  # multiple_risk_factors

DMS_REASON_TIER_0 = "structural_edge_persists"
DMS_REASON_TIER_1 = "single_risk_factor"
DMS_REASON_TIER_2 = "multiple_risk_factors"
DMS_REASON_HORIZON_NOT_ELIGIBLE = "horizon_not_eligible"

# Lucas critique threshold (Vision §9 default; per-call override possible).
LUCAS_THRESHOLD_DEFAULT = 0.5
LUCAS_MIN_BREACHES_FOR_FLAG = 2

# Vision §9 enumerated reason codes (sorted; canonical order).
LUCAS_VALID_REASON_CODES = frozenset({
    "fed_reaction_shift",
    "fiscal_dominance",
    "balance_sheet_dominance",
    "nbfi_transmission",
    "ai_productivity_shift",
    "inflation_target_credibility",
    "treasury_issuance_structure",
})


# =============================================================================
# DMS dynamic selector (L6-H D5)
# =============================================================================


def select_dms_adjustment_bps(
    horizon: int,
    *,
    valuation_extreme: bool = False,
    concentration_extreme: bool = False,
    fiscal_risks_elevated: bool = False,
    reserve_currency_risk: bool = False,
) -> Tuple[float, str]:
    """Select DMS bps + reason code per L6-H Strategic tier table.

    For ``horizon in {5, 10}``:
      - ``risk_count >= 2`` → ``(-200.0, "multiple_risk_factors")``
      - ``risk_count == 1`` → ``(-150.0, "single_risk_factor")``
      - ``risk_count == 0`` → ``(-100.0, "structural_edge_persists")``

    For ``horizon in {1, 3}``: ``(0.0, "horizon_not_eligible")`` per
    Vision §8 (cyclical noise dominates at short horizons; no
    survivorship adjustment).

    Parameters
    ----------
    horizon
        Forecast horizon in years.
    valuation_extreme, concentration_extreme,
    fiscal_risks_elevated, reserve_currency_risk
        Risk flags. All keyword-only + bool. Each ``True`` increments
        ``risk_count``.

    Returns
    -------
    tuple[float, str]
        ``(bps, selection_reason)``.

    Raises
    ------
    ValueError
        If ``horizon`` not in ``{1, 3, 5, 10}``, or any risk flag is
        not ``bool``.
    """
    if horizon not in (1, 3, 5, 10):
        raise ValueError(
            f"horizon {horizon} not in {{1, 3, 5, 10}}; DMS selector "
            f"supports the Vision §1 Pillar 4 horizon set only"
        )

    risk_flags = {
        "valuation_extreme": valuation_extreme,
        "concentration_extreme": concentration_extreme,
        "fiscal_risks_elevated": fiscal_risks_elevated,
        "reserve_currency_risk": reserve_currency_risk,
    }
    for name, val in risk_flags.items():
        if not isinstance(val, bool):
            raise ValueError(
                f"risk flag {name!r} must be bool; got "
                f"{type(val).__name__}"
            )

    if horizon in DMS_ZERO_HORIZONS:
        return (0.0, DMS_REASON_HORIZON_NOT_ELIGIBLE)

    # Eligible horizon (5Y or 10Y).
    risk_count = sum(risk_flags.values())
    if risk_count >= 2:
        return (DMS_TIER_2_BPS, DMS_REASON_TIER_2)
    if risk_count == 1:
        return (DMS_TIER_1_BPS, DMS_REASON_TIER_1)
    return (DMS_TIER_0_BPS, DMS_REASON_TIER_0)


def apply_dms_bps_to_return(
    point_estimate_return: float,
    dms_bps: float,
) -> float:
    """Apply DMS bps adjustment to a return-fraction point estimate.

    ``adjusted_return = point_estimate_return + (dms_bps / 10000)``.
    Negative bps (per Vision §8) lowers the return. 1 bps = 0.0001
    return fraction; 100 bps = 1% = 0.01 return fraction.

    Parameters
    ----------
    point_estimate_return
        Forecast point estimate in return-fraction units (e.g.,
        0.065 for 6.5%).
    dms_bps
        DMS adjustment in basis points (e.g., -150.0 for -1.5%).

    Returns
    -------
    float
        Adjusted return-fraction point estimate.

    Raises
    ------
    ValueError
        If either input is NaN/inf.
    """
    if not math.isfinite(point_estimate_return):
        raise ValueError(
            f"point_estimate_return must be finite; got "
            f"{point_estimate_return!r}"
        )
    if not math.isfinite(dms_bps):
        raise ValueError(f"dms_bps must be finite; got {dms_bps!r}")
    return point_estimate_return + (dms_bps / 10000.0)


# =============================================================================
# Lucas critique diagnostics (L6-H D5)
# =============================================================================


@dataclass(frozen=True)
class LucasCritiqueDiagnostics:
    """L6-H runtime Lucas critique flag + reason codes + evidence.

    Vision §9 enumerates structural-break trigger categories. The
    diagnostics carry:

      flag                  True when ≥2 evidence values exceed threshold
                            per ``compute_lucas_diagnostics``.
      reason_codes          tuple of breached reason codes (sorted; subset
                            of ``LUCAS_VALID_REASON_CODES``); empty when
                            flag is False.
      structural_break_evidence  Per-reason-code numeric evidence in
                            [0, 1]; immutable view of the source dict.

    Invariants (``__post_init__``):
      - ``reason_codes`` is a tuple of strings, all sorted ascending +
        all in ``LUCAS_VALID_REASON_CODES``.
      - ``flag`` agrees with ``len(reason_codes) >= 2``.
      - ``structural_break_evidence`` keys all in
        ``LUCAS_VALID_REASON_CODES``; values finite in [0, 1].
    """

    flag: bool
    reason_codes: Tuple[str, ...]
    structural_break_evidence: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # reason_codes invariants.
        if not isinstance(self.reason_codes, tuple):
            raise TypeError(
                f"reason_codes must be tuple; got "
                f"{type(self.reason_codes).__name__}"
            )
        for rc in self.reason_codes:
            if not isinstance(rc, str):
                raise TypeError(
                    f"reason_codes entries must be str; got "
                    f"{type(rc).__name__}"
                )
            if rc not in LUCAS_VALID_REASON_CODES:
                raise ValueError(
                    f"reason_code {rc!r} not in valid set "
                    f"{sorted(LUCAS_VALID_REASON_CODES)}"
                )
        # Sort invariant (deterministic ordering).
        if list(self.reason_codes) != sorted(self.reason_codes):
            raise ValueError(
                f"reason_codes must be sorted ascending; got "
                f"{self.reason_codes}"
            )
        # flag agreement with reason_codes.
        expected_flag = len(self.reason_codes) >= LUCAS_MIN_BREACHES_FOR_FLAG
        if self.flag != expected_flag:
            raise ValueError(
                f"flag {self.flag} disagrees with reason_codes count "
                f"{len(self.reason_codes)} (expected flag = "
                f"{expected_flag} when count >= "
                f"{LUCAS_MIN_BREACHES_FOR_FLAG})"
            )
        # structural_break_evidence invariants.
        if not isinstance(self.structural_break_evidence, dict):
            raise TypeError(
                f"structural_break_evidence must be dict; got "
                f"{type(self.structural_break_evidence).__name__}"
            )
        for key, val in self.structural_break_evidence.items():
            if key not in LUCAS_VALID_REASON_CODES:
                raise ValueError(
                    f"structural_break_evidence key {key!r} not in valid set"
                )
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise ValueError(
                    f"structural_break_evidence[{key!r}] must be real "
                    f"number; got {type(val).__name__}"
                )
            if not math.isfinite(float(val)):
                raise ValueError(
                    f"structural_break_evidence[{key!r}] must be finite; "
                    f"got {val!r}"
                )
            if not (0.0 <= float(val) <= 1.0):
                raise ValueError(
                    f"structural_break_evidence[{key!r}] must be in "
                    f"[0, 1]; got {val}"
                )


def compute_lucas_diagnostics(
    structural_break_evidence: Optional[Dict[str, float]] = None,
    threshold: float = LUCAS_THRESHOLD_DEFAULT,
) -> LucasCritiqueDiagnostics:
    """Compute Lucas flag + reason codes from structural-break evidence.

    Flag fires when ≥``LUCAS_MIN_BREACHES_FOR_FLAG`` (2) evidence
    values strictly exceed ``threshold``. Reason codes are the
    breached subset, sorted alphabetically.

    Parameters
    ----------
    structural_break_evidence
        Optional dict mapping Vision §9 reason codes (subset of
        ``LUCAS_VALID_REASON_CODES``) to numeric evidence in [0, 1].
        ``None`` (default) returns the no-evidence diagnostics
        ``LucasCritiqueDiagnostics(flag=False, reason_codes=(),
        structural_break_evidence={})``.
    threshold
        Evidence threshold for considering a reason-code "breached";
        default ``LUCAS_THRESHOLD_DEFAULT`` (0.5).

    Returns
    -------
    LucasCritiqueDiagnostics
        Frozen dataclass; ``__post_init__`` validates invariants.

    Raises
    ------
    ValueError
        If ``threshold`` is non-finite or out of [0, 1]; or any
        evidence key not in ``LUCAS_VALID_REASON_CODES`` (raised via
        dataclass ``__post_init__``).
    """
    if not math.isfinite(threshold) or not (0.0 <= threshold <= 1.0):
        raise ValueError(
            f"threshold must be finite + in [0, 1]; got {threshold!r}"
        )

    if structural_break_evidence is None:
        return LucasCritiqueDiagnostics(
            flag=False,
            reason_codes=(),
            structural_break_evidence={},
        )

    # Validate evidence dict via dataclass construction (single source of truth
    # for invariants).
    breached = tuple(
        sorted(
            k for k, v in structural_break_evidence.items()
            if isinstance(v, (int, float))
            and not isinstance(v, bool)
            and math.isfinite(float(v))
            and float(v) > threshold
        )
    )
    flag = len(breached) >= LUCAS_MIN_BREACHES_FOR_FLAG
    # Per dataclass docstring: reason_codes empty when flag is False.
    reason_codes = breached if flag else ()
    return LucasCritiqueDiagnostics(
        flag=flag,
        reason_codes=reason_codes,
        structural_break_evidence=dict(structural_break_evidence),
    )
