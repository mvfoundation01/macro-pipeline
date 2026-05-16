"""OOD reserve helper + standalone confidence cap enforcement (L6-D).

Per Strategic L6-D inline spec (Batch 1 of L6 sprint, 2026-05-15).
Implements Pipeline Guide §8.4 (OOD reserve) + §8.5 (confidence cap
enforcement) + Vision §7 (OOD Reserve discipline) + Vision §10 (Sample
Size Honesty / confidence caps).

Defense-in-depth confidence cap — SECOND LAYER
-----------------------------------------------
The pipeline carries two cap-enforcement layers per Standing Order #9
+ Vision §10 + L5b-F F-H2:

  Layer 1  ``TripleDecomposition.__post_init__``  (L6-B)
           Construction-time check; the dataclass refuses to instantiate
           if the input confidence exceeds the horizon-specific cap.

  Layer 2  ``enforce_confidence_caps()`` (THIS MODULE)
           Forecast-time / aggregator-time check; usable on any float
           confidence value at any point in the pipeline, independent
           of TripleDecomposition construction.

Both layers raise ``ConfidenceCapViolation`` (reused from L1.7-B
``macro_pipeline.manual_input.validation``); unified exception class
enables callers to catch cap violations uniformly across pipeline
boundaries.

This is the SECOND INSTANCE of the defense-in-depth two-layer pattern
in the codebase. The FIRST INSTANCE was L1.7-B value-level
(``validate_schedule`` V5) plus L1.7-D forecast-time
(``enforce_forecast_time_confidence_cap``). The L6-B + L6-D pair is
structurally identical: construction-time validator class invariant
plus standalone forecast-time helper.

Per AP-AUTH-46 gratuitous-codification guard, the pattern reaches the
second-instance trigger threshold at L6-D. Codification scheduled at
L6-H sprint retrospective (candidate AP-AUTH-56).

OOD reserve (Vision §7)
-----------------------
``compute_ood_reserve(conditions)`` returns the mandatory 5-15% OOD
reserve fraction based on eight condition triggers per Vision §7:

  - valuation_extreme            (CAPE/Buffett >95th percentile)
  - policy_regime_unprecedented  (novel Fed framework)
  - geopolitical_risk_elevated   (active war / sanctions regime)
  - volatility_artificially_suppressed  (vol-control unwind risk)
  - financial_leverage_opaque    (NBFI, private credit)
  - market_concentration_historical_extreme  (top-5/10 weight extreme)
  - macro_variables_contradictory  (late-cycle ambiguity)
  - fiscal_dominance_risk        (Treasury issuance + debt/GDP)

Floor 5% with no conditions True. Each True condition adds an equal
share of (15% - 5%) / 8 = 1.25 percentage points toward the 15% ceiling.
All eight True saturates at 15%.
"""
from __future__ import annotations

from typing import TypedDict

from macro_pipeline.manual_input.validation import ConfidenceCapViolation

# OOD reserve bounds per Vision §7.
OOD_RESERVE_FLOOR = 0.05
OOD_RESERVE_CEILING = 0.15
OOD_N_CONDITIONS = 8
OOD_INCREMENT_PER_CONDITION = (
    OOD_RESERVE_CEILING - OOD_RESERVE_FLOOR
) / OOD_N_CONDITIONS

# Confidence cap thresholds per Standing Order #9 + Vision §10 + L5b-F F-H2.
# Mirror constants live in L1.7-B/D and L6-B; the duplicate keeps this
# module self-contained at import time.
CONFIDENCE_CAP_10Y_NON_STRATIFIED = 0.70
CONFIDENCE_CAP_10Y_REGIME_STRATIFIED = 0.55

# Confidence range bounds per Vision §4 (defensive lower-bound check
# below; the upper bound is the horizon-specific cap).
CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 1.0


class OODConditions(TypedDict, total=False):
    """Vision §7 OOD-escalation condition flags.

    All keys optional (``total=False``); missing keys treated as False.
    Each ``True`` value adds one increment toward the 15% ceiling.
    """

    valuation_extreme: bool
    policy_regime_unprecedented: bool
    geopolitical_risk_elevated: bool
    volatility_artificially_suppressed: bool
    financial_leverage_opaque: bool
    market_concentration_historical_extreme: bool
    macro_variables_contradictory: bool
    fiscal_dominance_risk: bool


def compute_ood_reserve(conditions: OODConditions) -> float:
    """Compute OOD reserve fraction in [0.05, 0.15] per Vision §7.

    Floor of 0.05 (5%) applies whenever ``conditions`` is empty or all
    entries are ``False``. Each ``True`` condition adds an equal share
    of (0.15 - 0.05) / 8 = 0.0125 toward the ceiling 0.15. All eight
    True saturates at 0.15 (15%).

    Parameters
    ----------
    conditions
        ``OODConditions`` TypedDict (or any dict-like). Missing keys
        treated as False; non-True values (e.g., None, 0) treated as
        False.

    Returns
    -------
    float
        OOD reserve fraction; always in [0.05, 0.15].
    """
    n_true = sum(1 for v in conditions.values() if v is True)
    raw = OOD_RESERVE_FLOOR + n_true * OOD_INCREMENT_PER_CONDITION
    return min(raw, OOD_RESERVE_CEILING)


def enforce_confidence_caps(
    confidence: float,
    horizon: int,
    regime_stratified: bool = False,
) -> None:
    """Forecast-time confidence cap enforcement (defense-in-depth 2nd layer).

    Companion to ``TripleDecomposition.__post_init__`` (1st layer, L6-B).
    Use this helper anywhere in the pipeline where a confidence value
    is produced or propagated independently of TripleDecomposition
    construction — e.g., aggregator output, OOD-adjusted confidence,
    post-override forecast confidence.

    Lower-bound check
    -----------------
    A negative ``confidence`` raises ``ValueError`` (NOT
    ``ConfidenceCapViolation``). Cap violations are an institutional
    discipline concern (Standing Order #9); negative confidence is a
    range invariant violation (Vision §4 ``confidence in [0, 1]``).
    The two failure modes are distinct exception types.

    Parameters
    ----------
    confidence
        Confidence value in [0, 1].
    horizon
        Forecast horizon in years. Only ``horizon == 10`` triggers a
        cap check at L6-D; 1Y/3Y/5Y horizons skip silently per
        Standing Order #9 + L5b-F F-H2.
    regime_stratified
        If True applies the 0.55 regime-stratified 10Y cap; else the
        0.70 non-stratified 10Y cap.

    Raises
    ------
    ValueError
        If ``confidence`` is negative or above 1.0 (range invariant;
        Vision §4).
    ConfidenceCapViolation
        If ``horizon == 10`` and ``confidence > cap`` (institutional
        discipline; Standing Order #9). Reused from L1.7-B
        ``macro_pipeline.manual_input.validation`` per defense-in-depth
        single-exception-class convention.
    """
    # Lower-bound range invariant (Vision §4).
    if confidence < CONFIDENCE_MIN:
        raise ValueError(
            f"confidence {confidence} below {CONFIDENCE_MIN} (Vision §4 "
            f"range invariant)"
        )
    if confidence > CONFIDENCE_MAX:
        raise ValueError(
            f"confidence {confidence} above {CONFIDENCE_MAX} (Vision §4 "
            f"range invariant)"
        )
    # 10Y cap check — institutional discipline (Standing Order #9).
    if horizon != 10:
        return
    cap = (
        CONFIDENCE_CAP_10Y_REGIME_STRATIFIED
        if regime_stratified
        else CONFIDENCE_CAP_10Y_NON_STRATIFIED
    )
    if confidence > cap:
        label = "regime-stratified" if regime_stratified else "non-stratified"
        raise ConfidenceCapViolation(
            f"Forecast confidence {confidence:.4f} exceeds {label} 10Y "
            f"cap of {cap}. Per Standing Order #9 + Vision §10 + L5b-F "
            f"F-H2 + L6-D (defense-in-depth forecast-time layer)."
        )
