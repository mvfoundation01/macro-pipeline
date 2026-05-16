"""OOD reserve helper + confidence cap enforcement (L6-D base + L6-H refinement).

Per Strategic L6-D inline spec (Batch 1 of L6 sprint, 2026-05-15) +
L6-H R7 closure pre-flight 2026-05-16.

Implements Pipeline Guide §8.4 (OOD reserve) + §8.5 (confidence cap
enforcement) + Vision v2.1 §7 (OOD Reserve discipline; severity-tier
table) + Vision v2.1 §10 (Sample Size Honesty; horizon caps) + Vision
v2.1 §4 (cap modifier cascade — signal conflict / OOD vs analogs).

L6-H refinement summary
-----------------------
L6-D ships an *equal-weighted increment* OOD reserve (each True
condition adds ``(0.15 - 0.05) / 8 = 0.0125`` toward the ceiling) plus
a 10Y-only ``enforce_confidence_caps`` raise-helper.

L6-H replaces the equal-increment with the **Vision §7 severity-tier
bucket arithmetic** (each condition has a low/high bucket; reserve
equals the *upper* bound of the *largest* active bucket when ≥2
conditions are active, the *lower* bound otherwise; reserve floor is
5% per Vision §7). The bucket table is sourced directly from
Vision v2.1 §7 with one explicit extension: ``fiscal_dominance_risk``
(Vision §9 Lucas critique discipline) is included with the
(0.10, 0.12) bucket on the same scale as other policy-regime risks.

L6-H also adds **cap cascade** semantics (Vision v2.1 §4 + §7 + §10):
the cap at any horizon equals ``min(horizon_cap, signal_conflict_cap_if_active,
ood_cap_if_active)``. The new helper ``apply_confidence_cap_cascade``
returns the *capped* confidence value; it does NOT raise on cap
violation (caller decides to clamp or escalate).

The legacy ``enforce_confidence_caps`` raise-helper is PRESERVED
UNCHANGED for institutional discipline (Standing Order #9 +
defense-in-depth Test 12 + the 3rd-instance pattern at the aggregator).
The two helpers serve complementary roles:

  ``apply_confidence_cap_cascade``  → pipeline-time cap computation;
                                      returns capped value; never raises
                                      on cap violation; used by aggregator
                                      to compute the final per-horizon cap.
  ``enforce_confidence_caps``       → defensive raise-helper; raises
                                      ``ConfidenceCapViolation`` when the
                                      *propagated* confidence exceeds the
                                      10Y cap. Used as the 2nd defense-in-
                                      depth layer at construction-time +
                                      forecast-time boundaries.

Defense-in-depth confidence cap — SECOND LAYER (UNCHANGED at L6-H)
-------------------------------------------------------------------
The pipeline carries two cap-enforcement layers per Standing Order #9
+ Vision §10 + L5b-F F-H2:

  Layer 1  ``TripleDecomposition.__post_init__``  (L6-B)
           Construction-time check; the dataclass refuses to instantiate
           if the input confidence exceeds the horizon-specific cap.

  Layer 2  ``enforce_confidence_caps()`` (THIS MODULE; unchanged at L6-H)
           Forecast-time / aggregator-time check; usable on any float
           confidence value at any point in the pipeline, independent
           of TripleDecomposition construction.

Both layers raise ``ConfidenceCapViolation`` (reused from L1.7-B
``macro_pipeline.manual_input.validation``); unified exception class
enables callers to catch cap violations uniformly across pipeline
boundaries.

OOD reserve bucket table (Vision v2.1 §7 + §9 extension)
---------------------------------------------------------
Each Vision §7 trigger has a (low, high) bucket; ``compute_ood_reserve``
returns the *upper* bound of the *largest* active bucket when 2 or
more conditions are active, else the *lower* bound of that bucket.
A non-trigger baseline ``conditions`` returns the §7 floor 0.05 (5%).

  valuation_extreme                          (0.08, 0.10)  Vision §7
  policy_regime_unprecedented                (0.10, 0.12)  Vision §7
  geopolitical_risk_elevated                 (0.10, 0.12)  Vision §7
  volatility_artificially_suppressed         (0.10, 0.12)  Vision §7
  financial_leverage_opaque                  (0.10, 0.12)  Vision §7
  market_concentration_historical_extreme    (0.12, 0.15)  Vision §7
  macro_variables_contradictory              (0.12, 0.15)  Vision §7
  fiscal_dominance_risk                      (0.10, 0.12)  Vision §9 ext

L6-H input validation (Codex Finding #4 concurrent closure)
-----------------------------------------------------------
``compute_ood_reserve`` now rejects unknown condition keys, non-bool
values, and NaN/inf inputs with explicit exception types
(``ValueError`` / ``TypeError``) per Codex R7 finding C-13.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple, TypedDict

from macro_pipeline.manual_input.validation import ConfidenceCapViolation

# -----------------------------------------------------------------------------
# Vision §7 OOD-reserve bounds + severity-tier bucket table (L6-H refinement)
# -----------------------------------------------------------------------------

# Vision §7 floor + ceiling (anchors the bucket-table outputs).
OOD_RESERVE_FLOOR = 0.05
OOD_RESERVE_CEILING = 0.15

# Vision §7 + §9 severity-tier buckets (low, high) per condition.
# Each True condition contributes ITS bucket to the active set.
# Selection rule:
#   - 0 active conditions  → reserve = OOD_RESERVE_FLOOR (5%)
#   - 1 active condition   → reserve = LOW bound of that bucket
#   - ≥2 active conditions → reserve = HIGH bound of the *largest* bucket
# Reason codes returned alongside the reserve for audit.
OOD_BUCKET_TABLE: dict[str, Tuple[float, float]] = {
    "valuation_extreme": (0.08, 0.10),
    "policy_regime_unprecedented": (0.10, 0.12),
    "geopolitical_risk_elevated": (0.10, 0.12),
    "volatility_artificially_suppressed": (0.10, 0.12),
    "financial_leverage_opaque": (0.10, 0.12),
    "market_concentration_historical_extreme": (0.12, 0.15),
    "macro_variables_contradictory": (0.12, 0.15),
    # Vision §9 extension (Lucas-critique fiscal-dominance risk surfaces
    # explicitly in §9 as a structural-break trigger; included here for
    # OOD-reserve symmetry with the §7 policy-regime cohort).
    "fiscal_dominance_risk": (0.10, 0.12),
}

# Set of valid bucket-table keys for input validation.
OOD_VALID_KEYS = frozenset(OOD_BUCKET_TABLE.keys())

# -----------------------------------------------------------------------------
# Vision §10 horizon caps + §4 modifier cascade (L6-H refinement)
# -----------------------------------------------------------------------------

# Vision v2.1 §10 (canonical source; §4 mirrors §10) horizon-conditional caps.
# Non-stratified column applied when regime_stratified=False; stratified
# column when regime_stratified=True. 10Y stratified halves to 0.55 per
# Standing Order #9 (regime stratification halves effective N).
HORIZON_CAPS_NON_STRATIFIED: dict[int, float] = {
    1: 0.85,
    3: 0.80,
    5: 0.80,
    10: 0.70,
}
HORIZON_CAPS_REGIME_STRATIFIED: dict[int, float] = {
    1: 0.85,
    3: 0.80,
    5: 0.80,
    10: 0.55,
}

# Vision §4 cap modifiers (overlay horizon caps via min(...)).
SIGNAL_CONFLICT_CAP = 0.75
OOD_ELEVATED_CAP = 0.70

# OOD threshold for "elevated" classification (Vision §7 derivation:
# anything above 10% reserve indicates ≥1 policy-regime-tier condition
# active; this is the operational threshold for cap cascade triggering).
OOD_ELEVATED_THRESHOLD = 0.10

# -----------------------------------------------------------------------------
# Legacy L6-D constants (UNCHANGED — preserved for Test 12 + Layer-2 raise)
# -----------------------------------------------------------------------------

# Confidence cap thresholds per Standing Order #9 + Vision §10 + L5b-F F-H2.
# Mirror constants live in L1.7-B/D and L6-B; the duplicate keeps this
# module self-contained at import time.
CONFIDENCE_CAP_10Y_NON_STRATIFIED = 0.70
CONFIDENCE_CAP_10Y_REGIME_STRATIFIED = 0.55

# Confidence range bounds per Vision §4 (defensive lower-bound check
# below; the upper bound is the horizon-specific cap).
CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 1.0

# Supported horizons (mirror aggregator + L6-B).
SUPPORTED_HORIZONS = (1, 3, 5, 10)


class OODConditions(TypedDict, total=False):
    """Vision §7 + §9 OOD-escalation condition flags.

    All keys optional (``total=False``); missing keys treated as False.
    Each ``True`` value contributes its severity-tier bucket per
    ``OOD_BUCKET_TABLE``. The largest active bucket wins; the *upper*
    bound is used when ≥2 conditions are active.
    """

    valuation_extreme: bool
    policy_regime_unprecedented: bool
    geopolitical_risk_elevated: bool
    volatility_artificially_suppressed: bool
    financial_leverage_opaque: bool
    market_concentration_historical_extreme: bool
    macro_variables_contradictory: bool
    fiscal_dominance_risk: bool


# =============================================================================
# D1 — OOD reserve bucket arithmetic (L6-H per Vision §7 severity table)
# =============================================================================


def compute_ood_reserve(
    conditions: OODConditions,
) -> Tuple[float, Tuple[str, ...]]:
    """Compute OOD reserve fraction per Vision §7 severity-tier bucket table.

    Each Vision §7 trigger has a (low, high) bucket. With 0 conditions
    active, reserve = ``OOD_RESERVE_FLOOR`` (5% per Vision §7 baseline).
    With 1 condition active, reserve = LOW bound of that condition's
    bucket. With ≥2 conditions active, reserve = HIGH bound of the
    *largest* (highest-high) active bucket. Tie-break (when multiple
    buckets share the same high) selects the bucket whose LOW is also
    highest; further ties resolved alphabetically by condition key for
    deterministic behaviour.

    Parameters
    ----------
    conditions
        ``OODConditions`` TypedDict (or any dict-like). Missing keys
        treated as False. Keys must be members of ``OOD_VALID_KEYS``;
        values must be ``bool``.

    Returns
    -------
    tuple[float, tuple[str, ...]]
        ``(reserve, reason_codes)``. ``reserve`` always in
        [0.05, 0.15]. ``reason_codes`` is a tuple of the active
        condition keys (sorted alphabetically); empty tuple when no
        condition is active.

    Raises
    ------
    TypeError
        If ``conditions`` is not a dict-like, or any value is not a
        ``bool``.
    ValueError
        If any key is not in ``OOD_VALID_KEYS``, or any value is a NaN
        / inf float (defensive guard — values must be ``bool``;
        floats with ``isnan``/``isinf`` rejected explicitly even when
        bool-coercible).
    """
    if not isinstance(conditions, dict):
        raise TypeError(
            f"conditions must be dict-like; got {type(conditions).__name__}"
        )

    # Input validation per Codex R7 Finding #4 (C-13).
    for key, val in conditions.items():
        if key not in OOD_VALID_KEYS:
            raise ValueError(
                f"OOD condition key {key!r} not in Vision §7 + §9 valid set "
                f"{sorted(OOD_VALID_KEYS)}"
            )
        # Reject floats explicitly (catches NaN/inf even though bool is int).
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                raise ValueError(
                    f"OOD condition {key!r} value is NaN/inf; must be bool"
                )
            raise TypeError(
                f"OOD condition {key!r} value type {type(val).__name__}; "
                f"must be bool (got float {val!r})"
            )
        if not isinstance(val, bool):
            raise TypeError(
                f"OOD condition {key!r} value type "
                f"{type(val).__name__}; must be bool"
            )

    # Active condition set (True values only).
    active = sorted(k for k, v in conditions.items() if v is True)

    if not active:
        return (OOD_RESERVE_FLOOR, ())

    # Lookup buckets for active conditions.
    active_buckets = [(k, OOD_BUCKET_TABLE[k]) for k in active]

    if len(active) == 1:
        # 1 condition active → LOW bound of that bucket.
        _, (low, _high) = active_buckets[0]
        return (low, tuple(active))

    # ≥2 conditions active → HIGH bound of the largest (highest-high) bucket.
    # Tie-break: secondary by LOW (desc), tertiary alphabetical (already
    # sorted ascending by ``active``; for HIGH/LOW ties keep
    # deterministic behaviour by selecting the first alphabetical).
    max_high = max(b[1] for _, b in active_buckets)
    candidates = [(k, b) for k, b in active_buckets if b[1] == max_high]
    # Tie-break on LOW (descending); then alphabetical (already in input order).
    candidates.sort(key=lambda kb: (-kb[1][0], kb[0]))
    _winning_key, (_low, winning_high) = candidates[0]
    return (winning_high, tuple(active))


# =============================================================================
# D2 — Cap cascade across all horizons (L6-H per Vision §4 + §7 + §10)
# =============================================================================


def apply_confidence_cap_cascade(
    confidence: float,
    horizon: int,
    regime_stratified: bool = False,
    signal_conflict: bool = False,
    ood_elevated: bool = False,
    ood_reserve_fraction: Optional[float] = None,
) -> float:
    """Apply Vision §4 + §7 + §10 cap cascade and return CAPPED confidence.

    Cap cascade:
      1. Start from horizon cap (``HORIZON_CAPS_REGIME_STRATIFIED`` if
         ``regime_stratified=True`` else ``HORIZON_CAPS_NON_STRATIFIED``).
      2. If ``signal_conflict=True``: ``cap = min(cap, 0.75)`` (Vision §4).
      3. If OOD elevated (``ood_elevated=True`` OR
         ``ood_reserve_fraction >= 0.10``): ``cap = min(cap, 0.70)``
         (Vision §4 + §7).
      4. Return ``min(confidence, effective_cap)``.

    This helper returns the capped value; it does NOT raise on cap
    violation. The defensive raise-helper ``enforce_confidence_caps``
    (below; unchanged at L6-H) remains the institutional discipline
    surface for cap violation reporting.

    Parameters
    ----------
    confidence
        Pre-cap confidence value (typically the raw Vision §4 additive
        score from ``compute_bayesian_confidence``).
    horizon
        Forecast horizon; must be in ``SUPPORTED_HORIZONS``.
    regime_stratified
        If True, uses ``HORIZON_CAPS_REGIME_STRATIFIED``; else the
        non-stratified table.
    signal_conflict
        If True, overlays Vision §4 signal-conflict cap 0.75.
    ood_elevated
        If True (or implied via ``ood_reserve_fraction >=
        OOD_ELEVATED_THRESHOLD``), overlays Vision §4 + §7 OOD cap 0.70.
    ood_reserve_fraction
        Optional reserve fraction (from ``compute_ood_reserve``);
        ``>= OOD_ELEVATED_THRESHOLD`` (0.10) implies elevated OOD.

    Returns
    -------
    float
        Capped confidence ``min(confidence, effective_cap)``.

    Raises
    ------
    ValueError
        If ``confidence`` is non-finite (NaN/inf).
    KeyError
        If ``horizon`` not in ``SUPPORTED_HORIZONS``.
    """
    if not math.isfinite(confidence):
        raise ValueError(
            f"confidence must be finite; got {confidence!r}"
        )

    base_caps = (
        HORIZON_CAPS_REGIME_STRATIFIED
        if regime_stratified
        else HORIZON_CAPS_NON_STRATIFIED
    )
    if horizon not in base_caps:
        raise KeyError(
            f"horizon {horizon} not in {sorted(base_caps.keys())}"
        )

    cap = base_caps[horizon]

    if signal_conflict:
        cap = min(cap, SIGNAL_CONFLICT_CAP)

    # OOD elevated: explicit flag OR reserve >= 10% threshold.
    ood_active = ood_elevated or (
        ood_reserve_fraction is not None
        and ood_reserve_fraction >= OOD_ELEVATED_THRESHOLD
    )
    if ood_active:
        cap = min(cap, OOD_ELEVATED_CAP)

    return min(confidence, cap)


# =============================================================================
# L6-D legacy — enforce_confidence_caps (UNCHANGED at L6-H per PD20 + Test 12)
# =============================================================================


def enforce_confidence_caps(
    confidence: float,
    horizon: int,
    regime_stratified: bool = False,
) -> None:
    """Forecast-time confidence cap enforcement (defense-in-depth 2nd layer).

    UNCHANGED at L6-H per PD20 (Test 12 institutional invariant
    preservation). The new L6-H cap cascade is exposed via
    ``apply_confidence_cap_cascade`` above; this raise-helper
    remains the institutional discipline surface for cap violation
    reporting at the 10Y boundary.

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
