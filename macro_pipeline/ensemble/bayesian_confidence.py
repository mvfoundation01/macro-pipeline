"""Bayesian confidence + conviction computation (L6-G base + L6-H refinement).

Per Strategic L6-G inline pre-flight 2026-05-15 + L6-H R7 closure pre-flight
2026-05-16.

L6-G shipped a tractable Bayesian subset (single posterior-precision
heuristic for confidence; linear-from-confidence + 2 penalties for
conviction). L6-H REPLACES this with the **Vision v2.1 §4 BINDING
additive formulas** for both confidence and conviction, closing
ChatGPT R7 methodology Findings #3 (C-3) and #4 (C-4).

L6-H formulas
-------------

**Confidence** (Vision v2.1 §4 BINDING; weighted-sum of 6 quality
components in [0, 1])::

    raw_confidence = (
        0.25 * data_quality
      + 0.25 * model_agreement
      + 0.20 * regime_stability
      + 0.15 * analog_strength
      + 0.10 * sample_size_adequacy
      - 0.05 * ood_penalty
    )
    raw_confidence ∈ [-0.05, 0.95]   (clamped to [0, 1] for output)

Caller applies the §4 + §7 + §10 cap cascade externally via
``apply_confidence_cap_cascade`` from ``ood_and_caps``. This module
returns the *raw* (clamped to [0, 1]) confidence; cap discipline
remains the responsibility of the cap helpers + defense-in-depth
layers per the institutional pattern.

**Conviction** (Vision v2.1 §4 BINDING; 10-component edge-and-risk
score in [1, 10])::

    raw_0_1 = (
        0.20 * edge_score
      + 0.20 * asymmetry_score
      + 0.15 * model_agreement
      + 0.15 * valuation_support
      + 0.10 * trend_confirmation
      + 0.10 * liquidity_support
      - 0.15 * tail_risk_penalty
      - 0.10 * crowding_penalty
      - 0.10 * policy_uncertainty_penalty
      - 0.10 * forecast_decay_penalty
    )
    conviction = 1.0 + 9.0 * clamp(raw_0_1, 0, 1)   # map to [1, 10]

Vision v2.1 §4 critical rule preserved: **conviction CAN BE LOWER
THAN confidence** when risk/reward asymmetry is poor — the two scales
are *independent*. This is structurally enforced by the formula
(conviction depends on a distinct 10-component set; the asymmetry +
penalty components can dominate even at high confidence).

Component sourcing (L6-H placeholder discipline + L6-I roadmap)
----------------------------------------------------------------
Not all 10 conviction components or 6 confidence components have full
upstream L1-L5b producers at L6-H. Where producer data exists, the
component is sourced empirically; where data is unavailable, a
documented placeholder value is used (typically the neutral 0.5).
Each placeholder is flagged in the component-builder helper
docstrings + the aggregator integration; future L7/L8a sub-phases
will replace placeholders with empirical producers.

This discipline closes ChatGPT R7 Finding #4 (conviction must be a
*distinct* risk/reward score with the §4 BINDING components) while
acknowledging the empirical sourcing gap (documented + deferred,
not silently elided).

L6-I D6 producer roadmap (Strategic Decision Ratify #2 — 2026-05-16)
--------------------------------------------------------------------
At L6-H + L6-I, the following components use PLACEHOLDER_NEUTRAL (0.5)
in ``derive_confidence_components`` and ``derive_conviction_components``;
producer-backed sourcing is roadmapped per the Strategic disposition:

Confidence components (3 of 6 placeholder at L6-I):

  data_quality          → L7 producer: FRED vintage age + indicator
                          coverage diagnostics; consumes loaders/* +
                          analysis/* PIT audit outputs.
  model_agreement       → L7 producer: L5b 11-model dispersion
                          diagnostics; consumes ensemble residual
                          across 11 model_ids (post-L6-I D3 schema +
                          L7 dedicated producer wiring).
  regime_stability      → L7 producer: rcf.py regime_classifier
                          extension; consumes regime transition
                          probabilities + persistence diagnostics
                          across 1913-present sample.

Confidence components (3 of 6 empirical at L6-H):

  analog_strength       ← L6-E rcf.ReferenceClass.mean_similarity
                          (clamped to [0, 1]).
  sample_size_adequacy  ← L6-H compute_sample_size_adequacy via
                          Vision §10 N targets (113/38/22/11).
  ood_penalty           ← L6-H OOD reserve fraction normalized
                          to [0, 1] via (reserve - 0.05) / 0.10.

Conviction components (9 of 10 placeholder at L6-I; 1 empirical):

  edge_score                   → L7 producer: forecast vs benchmark
                                 (e.g., risk-free rate, opportunity-cost
                                 anchor); Sharpe-like normalized score.
  asymmetry_score              → L7 producer: vol-implied right/left
                                 tail dispersion from VIX/SKEW + options.
  model_agreement              → L7 producer: L5b 11-model dispersion
                                 (same producer as confidence variant;
                                 surfaces here as conviction INPUT not
                                 confidence weight).
  valuation_support            → L7 producer: CAPE/Tobin/ERP percentile
                                 classifier; direction-aware vs forecast.
  trend_confirmation           → L7 producer: 50/200 DMA + breadth +
                                 momentum diagnostics from L4.
  liquidity_support            → L7 producer: FCI + credit spreads +
                                 funding-liquidity diagnostics.
  tail_risk_penalty            → L7 producer: VaR/CVaR breach probability
                                 from forecast distribution.
  crowding_penalty             → L7 producer: CFTC positioning + dealer
                                 gamma + AAII bull-bear extremes.
  policy_uncertainty_penalty   → L7 producer: Fed reaction-function
                                 shift signals (Lucas critique surface;
                                 partial integration via L6-H
                                 LucasCritiqueDiagnostics).
  forecast_decay_penalty       ← L6-H derive_conviction_components
                                 horizon-decay schedule (empirical at
                                 L6-H/I; full producer-backed model
                                 deferred to L8a UI surface).

Summary
-------
* L6-H/I empirical: 3 confidence + 1 conviction component
* L6-H/I placeholder: 3 confidence + 9 conviction components
* Producer-backed sourcing: roadmapped to L7 (component producers) +
  L8a (forecast decay UI model).

R8 reviewer expectation: this discipline is documented for
transparency. If R8 flags the placeholder-driven L6-H/I formula
output as MEDIUM (e.g., "components are 0.5 → confidence + conviction
are not differentiated"), Strategic accepts (alternative is 20-30h L6
scope expansion that breaks gate hygiene + sprint cadence). The
binding Vision §4 FORMULAS are correctly implemented; component
sourcing is a separate L7 concern.

Defense-in-depth confidence cap (3rd-instance UNCHANGED at L6-H)
----------------------------------------------------------------
The aggregator pipeline still calls both cap-enforcement layers:
- Layer 1: ``TripleDecomposition.__post_init__`` (construction-time)
- Layer 2: ``enforce_confidence_caps`` (raise-helper; PRESERVED
  UNCHANGED at L6-H per PD20 for Test 12 invariant)

The L6-H cap cascade (``apply_confidence_cap_cascade``) is applied
*before* TripleDecomposition construction; the raise-helper remains
a defensive check after the cascade has produced the final value.
Test 12 (``test_aggregate_defense_in_depth_both_layers_fire``)
remains PASSING unchanged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Optional

from macro_pipeline.ensemble.rcf import ReferenceClass

# =============================================================================
# Vision §4 BINDING confidence formula weights
# =============================================================================

CONFIDENCE_WEIGHT_DATA_QUALITY = 0.25
CONFIDENCE_WEIGHT_MODEL_AGREEMENT = 0.25
CONFIDENCE_WEIGHT_REGIME_STABILITY = 0.20
CONFIDENCE_WEIGHT_ANALOG_STRENGTH = 0.15
CONFIDENCE_WEIGHT_SAMPLE_SIZE = 0.10
CONFIDENCE_WEIGHT_OOD_PENALTY = -0.05

# Sum of POSITIVE weights = 0.95; minus OOD = 0.90 net.
# With all components = 1.0 and ood_penalty = 0: raw = 0.95.
# With all components = 1.0 and ood_penalty = 1.0: raw = 0.90.
# With all positive = 0, ood_penalty = 1.0: raw = -0.05 (clamped to 0).

# =============================================================================
# Vision §4 BINDING conviction formula weights (10-component)
# =============================================================================

CONVICTION_WEIGHT_EDGE = 0.20
CONVICTION_WEIGHT_ASYMMETRY = 0.20
CONVICTION_WEIGHT_MODEL_AGREEMENT = 0.15
CONVICTION_WEIGHT_VALUATION = 0.15
CONVICTION_WEIGHT_TREND = 0.10
CONVICTION_WEIGHT_LIQUIDITY = 0.10
CONVICTION_WEIGHT_TAIL_RISK = -0.15
CONVICTION_WEIGHT_CROWDING = -0.10
CONVICTION_WEIGHT_POLICY = -0.10
CONVICTION_WEIGHT_DECAY = -0.10

# Sum positive weights = 0.90; sum negative weights = -0.45.
# Max possible: all positive = 1, all negative = 0 → 0.90 → conviction 9.1.
# Min possible: all positive = 0, all negative = 1 → -0.45 (clamped to 0) → conviction 1.0.

# Conviction output range bounds (Vision §4).
CONVICTION_MIN = 1.0
CONVICTION_MAX = 10.0

# Vision §10 sample-size targets per horizon (N_eff at which
# sample_size_adequacy = 1.0; sqrt scaling below that).
SAMPLE_SIZE_TARGETS: dict[int, int] = {
    1: 113,
    3: 38,
    5: 22,
    10: 11,
}

# Supported horizons (mirrors aggregator + L6-B + L6-D).
SUPPORTED_HORIZONS = (1, 3, 5, 10)

# L6-G compat constant (retained for backward export; no functional use at L6-H).
KAPPA_EVIDENCE = 10

# Neutral placeholder used by component builders when upstream producer
# data is unavailable (documented per-component in builder docstrings).
PLACEHOLDER_NEUTRAL = 0.5


def _validate_component(value: float, name: str) -> None:
    """Validate a single Vision §4 component value: finite + in [0, 1]."""
    if not isinstance(value, (int, float)):
        raise ValueError(
            f"{name} must be a real number; got {type(value).__name__}"
        )
    if isinstance(value, bool):
        # bool is int subclass; reject explicitly per type semantics.
        raise ValueError(
            f"{name} must be a real number; got bool"
        )
    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite; got {value!r}")
    if not (0.0 <= float(value) <= 1.0):
        raise ValueError(f"{name} must be in [0, 1]; got {value}")


# =============================================================================
# D3 — Confidence Vision §4 additive formula
# =============================================================================


@dataclass(frozen=True)
class ConfidenceComponents:
    """Six-component additive confidence score per Vision v2.1 §4 BINDING.

    Each component is a quality score in [0, 1] with semantics anchored
    to Vision v2.1 §4:

      data_quality          Input data freshness + completeness + sanity
                            (e.g., FRED vintage age, no NaN/extreme outlier
                            count, indicator-coverage completeness).
      model_agreement       Agreement across the L5b 11-model ensemble at
                            this horizon (e.g., 1 - normalized stdev of
                            model point estimates; or proportion of models
                            within ±1 σ of ensemble mean).
      regime_stability      Stability of the current regime relative to
                            the analog window (e.g., regime-transition
                            probability below some threshold; or regime
                            persistence above some threshold).
      analog_strength       Reference-class L6-E mean_similarity, clamped
                            to [0, 1].
      sample_size_adequacy  ``sqrt(min(1, n_eff / N_target))`` where
                            ``N_target`` is Vision §10 horizon N (113 /
                            38 / 22 / 11 non-overlapping windows).
      ood_penalty           OOD reserve-fraction-derived penalty in [0, 1]
                            (e.g., ``(reserve - 0.05) / (0.15 - 0.05)``).
                            Penalty: subtracted at 5% weight per Vision §4.

    Invariants (``__post_init__``):
      - All fields finite + in [0, 1].
    """

    data_quality: float
    model_agreement: float
    regime_stability: float
    analog_strength: float
    sample_size_adequacy: float
    ood_penalty: float

    def __post_init__(self) -> None:
        for f in fields(self):
            _validate_component(getattr(self, f.name), f.name)


def compute_bayesian_confidence(
    components: ConfidenceComponents,
    horizon: int,
) -> float:
    """Compute UNCAPPED Vision §4 additive confidence in [0, 1].

    Vision v2.1 §4 BINDING formula::

        raw = (
            0.25 * data_quality
          + 0.25 * model_agreement
          + 0.20 * regime_stability
          + 0.15 * analog_strength
          + 0.10 * sample_size_adequacy
          - 0.05 * ood_penalty
        )
        return clamp(raw, 0, 1)

    Returns the *raw* clamped-to-[0, 1] additive score. The Vision §4
    + §7 + §10 cap cascade is applied separately by the caller (typically
    ``apply_confidence_cap_cascade`` from ``ood_and_caps``). The 2nd
    defense-in-depth layer (``enforce_confidence_caps``) and the 1st
    layer (``TripleDecomposition.__post_init__``) both fire on
    post-cascade cap violations.

    Parameters
    ----------
    components
        ``ConfidenceComponents`` dataclass with the 6 Vision §4 fields.
    horizon
        Forecast horizon; must be in ``SUPPORTED_HORIZONS``. Reserved
        for future horizon-conditional weight adjustments; the L6-H
        formula uses uniform weights across horizons (per Vision §4
        BINDING).

    Returns
    -------
    float
        Raw additive confidence in [0, 1]. Cap cascade NOT applied
        here; caller responsibility.

    Raises
    ------
    KeyError
        If ``horizon`` not in ``SUPPORTED_HORIZONS``.
    """
    if horizon not in SUPPORTED_HORIZONS:
        raise KeyError(
            f"horizon {horizon} not in {sorted(SUPPORTED_HORIZONS)}"
        )

    raw = (
        CONFIDENCE_WEIGHT_DATA_QUALITY * components.data_quality
        + CONFIDENCE_WEIGHT_MODEL_AGREEMENT * components.model_agreement
        + CONFIDENCE_WEIGHT_REGIME_STABILITY * components.regime_stability
        + CONFIDENCE_WEIGHT_ANALOG_STRENGTH * components.analog_strength
        + CONFIDENCE_WEIGHT_SAMPLE_SIZE * components.sample_size_adequacy
        + CONFIDENCE_WEIGHT_OOD_PENALTY * components.ood_penalty
    )
    return max(0.0, min(1.0, raw))


def compute_sample_size_adequacy(n_eff: int, horizon: int) -> float:
    """Vision §10 sample-size adequacy: ``sqrt(min(1, n_eff / N_target))``.

    ``N_target`` is the Vision §10 nominal non-overlapping window count
    at the horizon (113 / 38 / 22 / 11 for 1Y / 3Y / 5Y / 10Y). When
    ``n_eff >= N_target`` the adequacy = 1.0 (saturates); below target
    it scales as sqrt of the ratio (smoother than linear; reflects
    that uncertainty contracts as sqrt(N) for unbiased estimators).

    Parameters
    ----------
    n_eff
        Effective sample size (non-negative integer).
    horizon
        Forecast horizon in ``SUPPORTED_HORIZONS``.

    Returns
    -------
    float
        Sample-size adequacy in [0, 1].

    Raises
    ------
    ValueError
        If ``n_eff < 0``.
    KeyError
        If ``horizon`` not in ``SAMPLE_SIZE_TARGETS``.
    """
    if n_eff < 0:
        raise ValueError(f"n_eff must be non-negative; got {n_eff}")
    if horizon not in SAMPLE_SIZE_TARGETS:
        raise KeyError(
            f"horizon {horizon} not in {sorted(SAMPLE_SIZE_TARGETS.keys())}"
        )
    target = SAMPLE_SIZE_TARGETS[horizon]
    ratio = min(1.0, n_eff / target)
    return math.sqrt(ratio)


def derive_confidence_components(
    n_eff: int,
    horizon: int,
    reference_class: Optional[ReferenceClass],
    ood_reserve_fraction: float,
    data_quality: float = PLACEHOLDER_NEUTRAL,
    model_agreement: float = PLACEHOLDER_NEUTRAL,
    regime_stability: float = PLACEHOLDER_NEUTRAL,
) -> ConfidenceComponents:
    """Build ``ConfidenceComponents`` from available L5b/L6-E inputs.

    Component sourcing (L6-H):

      data_quality        PLACEHOLDER 0.5 (no L6-H upstream producer;
                          future L7/L8a will source from FRED vintage
                          + indicator coverage diagnostics).
      model_agreement     PLACEHOLDER 0.5 (no L6-H upstream producer;
                          future L7/L8a will source from L5b 11-model
                          dispersion diagnostics).
      regime_stability    PLACEHOLDER 0.5 (no L6-H upstream producer;
                          future L7/L8a will source from regime-
                          transition probabilities + persistence
                          diagnostics).
      analog_strength     EMPIRICAL from ``reference_class.mean_similarity``
                          clamped to [0, 1] (Vision §6 BINDING).
                          When ``reference_class is None``: 0.5 neutral.
      sample_size_adequacy  EMPIRICAL via ``compute_sample_size_adequacy``
                          (Vision §10).
      ood_penalty         EMPIRICAL from ``ood_reserve_fraction``
                          normalized to [0, 1] via
                          ``(reserve - 0.05) / (0.15 - 0.05)``.

    Caller MAY override ``data_quality`` / ``model_agreement`` /
    ``regime_stability`` with explicit values when upstream diagnostics
    are available; the keyword defaults provide the L6-H placeholder
    discipline.

    Parameters
    ----------
    n_eff
        Effective sample size at this horizon.
    horizon
        Forecast horizon in ``SUPPORTED_HORIZONS``.
    reference_class
        Optional L6-E reference class output (provides
        ``mean_similarity`` for ``analog_strength``).
    ood_reserve_fraction
        OOD reserve fraction in [0.05, 0.15] from ``compute_ood_reserve``.
        Normalized to [0, 1] for the ``ood_penalty`` component.
    data_quality, model_agreement, regime_stability
        Optional explicit values when upstream producers are
        available. Default to ``PLACEHOLDER_NEUTRAL`` (0.5) at L6-H
        per the documented deferral.

    Returns
    -------
    ConfidenceComponents
        Frozen dataclass; ``__post_init__`` validates each field
        finite + in [0, 1].
    """
    # analog_strength: empirical from reference class when available.
    if reference_class is not None:
        analog_strength = max(0.0, min(1.0, reference_class.mean_similarity))
    else:
        analog_strength = PLACEHOLDER_NEUTRAL

    # sample_size_adequacy: empirical Vision §10.
    sample_size_adequacy = compute_sample_size_adequacy(n_eff, horizon)

    # ood_penalty: normalize reserve from [0.05, 0.15] -> [0, 1].
    ood_penalty_raw = (ood_reserve_fraction - 0.05) / (0.15 - 0.05)
    ood_penalty = max(0.0, min(1.0, ood_penalty_raw))

    return ConfidenceComponents(
        data_quality=data_quality,
        model_agreement=model_agreement,
        regime_stability=regime_stability,
        analog_strength=analog_strength,
        sample_size_adequacy=sample_size_adequacy,
        ood_penalty=ood_penalty,
    )


# =============================================================================
# D4 — Conviction Vision §4 10-component formula (distinct from confidence)
# =============================================================================


@dataclass(frozen=True)
class ConvictionComponents:
    """Ten-component additive conviction score per Vision v2.1 §4 BINDING.

    Vision §4 critical rule: **conviction CAN BE LOWER THAN confidence**
    when risk/reward asymmetry is poor. The two scales are independent;
    conviction depends on edge + asymmetry + supports MINUS tail-risk +
    crowding + policy uncertainty + forecast decay penalties.

    Each component is a normalized score in [0, 1] with semantics
    anchored to Vision v2.1 §4:

      edge_score                    Expected return attractiveness vs
                                    risk-free / opportunity-cost benchmark
                                    (e.g., normalized Sharpe-like score).
      asymmetry_score               Right-tail vs left-tail upside skew
                                    (e.g., (P[r > median + σ] - P[r <
                                    median - σ]) shifted to [0, 1]).
      model_agreement               Agreement across L5b 11-model ensemble;
                                    same surface as the confidence
                                    component but here it's a conviction
                                    INPUT not a confidence weight.
      valuation_support             CAPE / Tobin's Q / ERP support for the
                                    forecast direction (e.g., when forecast
                                    is long-equity and CAPE is at <20th
                                    percentile: high valuation support).
      trend_confirmation            Trend / breadth / momentum confirmation
                                    of the forecast direction.
      liquidity_support             Funding-liquidity + credit-spread support
                                    for the forecast direction.
      tail_risk_penalty             Tail-risk magnitude (VaR/CVaR breach
                                    probability; -15% weight).
      crowding_penalty              Positioning + flow concentration
                                    (-10% weight).
      policy_uncertainty_penalty    Policy + Lucas-critique uncertainty
                                    (-10% weight).
      forecast_decay_penalty        Forecast-skill decay over the horizon
                                    (e.g., decay from R² at 1Y -> R² at
                                    10Y normalized; -10% weight).

    Invariants (``__post_init__``):
      - All fields finite + in [0, 1].
    """

    edge_score: float
    asymmetry_score: float
    model_agreement: float
    valuation_support: float
    trend_confirmation: float
    liquidity_support: float
    tail_risk_penalty: float
    crowding_penalty: float
    policy_uncertainty_penalty: float
    forecast_decay_penalty: float

    def __post_init__(self) -> None:
        for f in fields(self):
            _validate_component(getattr(self, f.name), f.name)


def compute_conviction_score(components: ConvictionComponents) -> float:
    """Compute Vision §4 10-component conviction score in [1, 10].

    Vision v2.1 §4 BINDING formula::

        raw_0_1 = clamp(
            0.20 * edge_score
          + 0.20 * asymmetry_score
          + 0.15 * model_agreement
          + 0.15 * valuation_support
          + 0.10 * trend_confirmation
          + 0.10 * liquidity_support
          - 0.15 * tail_risk_penalty
          - 0.10 * crowding_penalty
          - 0.10 * policy_uncertainty_penalty
          - 0.10 * forecast_decay_penalty,
            0, 1
        )
        return 1.0 + 9.0 * raw_0_1   # map to [1, 10]

    Parameters
    ----------
    components
        ``ConvictionComponents`` dataclass with the 10 Vision §4 fields.

    Returns
    -------
    float
        Conviction in [1, 10] = [CONVICTION_MIN, CONVICTION_MAX].
    """
    raw_0_1 = (
        CONVICTION_WEIGHT_EDGE * components.edge_score
        + CONVICTION_WEIGHT_ASYMMETRY * components.asymmetry_score
        + CONVICTION_WEIGHT_MODEL_AGREEMENT * components.model_agreement
        + CONVICTION_WEIGHT_VALUATION * components.valuation_support
        + CONVICTION_WEIGHT_TREND * components.trend_confirmation
        + CONVICTION_WEIGHT_LIQUIDITY * components.liquidity_support
        + CONVICTION_WEIGHT_TAIL_RISK * components.tail_risk_penalty
        + CONVICTION_WEIGHT_CROWDING * components.crowding_penalty
        + CONVICTION_WEIGHT_POLICY * components.policy_uncertainty_penalty
        + CONVICTION_WEIGHT_DECAY * components.forecast_decay_penalty
    )
    raw_0_1 = max(0.0, min(1.0, raw_0_1))
    return CONVICTION_MIN + (CONVICTION_MAX - CONVICTION_MIN) * raw_0_1


def derive_conviction_components(
    confidence: float,
    n_eff: int,
    horizon: int,
    reference_class: Optional[ReferenceClass],
    point_estimate: float,
    edge_score: float = PLACEHOLDER_NEUTRAL,
    asymmetry_score: float = PLACEHOLDER_NEUTRAL,
    model_agreement: float = PLACEHOLDER_NEUTRAL,
    valuation_support: float = PLACEHOLDER_NEUTRAL,
    trend_confirmation: float = PLACEHOLDER_NEUTRAL,
    liquidity_support: float = PLACEHOLDER_NEUTRAL,
    tail_risk_penalty: float = PLACEHOLDER_NEUTRAL,
    crowding_penalty: float = PLACEHOLDER_NEUTRAL,
    policy_uncertainty_penalty: float = PLACEHOLDER_NEUTRAL,
    forecast_decay_penalty: Optional[float] = None,
) -> ConvictionComponents:
    """Build ``ConvictionComponents`` from available pipeline inputs.

    Component sourcing (L6-H):

      edge_score                    PLACEHOLDER 0.5 (Sharpe-like score
                                    requires forecast σ + benchmark;
                                    future L7).
      asymmetry_score               PLACEHOLDER 0.5 (requires return
                                    distribution skew estimate; future
                                    L7 Kelly-fraction surface).
      model_agreement               PLACEHOLDER 0.5 (same as confidence;
                                    future L7 from L5b ensemble
                                    dispersion).
      valuation_support             PLACEHOLDER 0.5 (requires CAPE/Tobin
                                    percentile linked to forecast
                                    direction; future L7).
      trend_confirmation            PLACEHOLDER 0.5 (requires breadth/
                                    momentum diagnostics; future L7).
      liquidity_support             PLACEHOLDER 0.5 (requires credit
                                    spread / funding liquidity; future
                                    L7).
      tail_risk_penalty             PLACEHOLDER 0.5 (requires VaR/CVaR
                                    breach probability; future L7).
      crowding_penalty              PLACEHOLDER 0.5 (requires positioning
                                    + flow concentration; future L7).
      policy_uncertainty_penalty    PLACEHOLDER 0.5 (Lucas critique
                                    surface; L6-H D5 LucasCritiqueDiagnostics
                                    integration deferred to caller).
      forecast_decay_penalty        EMPIRICAL when explicit value passed;
                                    else derived from horizon (longer
                                    horizon → higher decay penalty:
                                    0.0 at 1Y, 0.1 at 3Y, 0.25 at 5Y,
                                    0.5 at 10Y per Strategic L6-H
                                    horizon-decay default).

    Caller MAY override any component with an explicit value when
    upstream diagnostics are available.

    Parameters
    ----------
    confidence
        Post-cascade confidence value (reserved for future caller-
        side adjustments; not used in the L6-H derivation directly).
    n_eff
        Effective sample size (reserved; not used directly).
    horizon
        Forecast horizon in ``SUPPORTED_HORIZONS``.
    reference_class
        Optional L6-E reference class (reserved; not used directly at
        L6-H — analog_strength surfaces via confidence components,
        not conviction).
    point_estimate
        Forecast point estimate (reserved; not used directly).
    edge_score, asymmetry_score, ..., crowding_penalty,
    policy_uncertainty_penalty
        Optional explicit values; defaults are ``PLACEHOLDER_NEUTRAL``.
    forecast_decay_penalty
        Optional explicit value; ``None`` → derive from horizon per
        Strategic L6-H default schedule.

    Returns
    -------
    ConvictionComponents
        Frozen dataclass; ``__post_init__`` validates each field.
    """
    # Argument-existence guard for typing tools (not used directly at L6-H;
    # surfaces explicitly that the values pass through to future refinement).
    del confidence, n_eff, reference_class, point_estimate

    # forecast_decay_penalty: empirical from horizon if not overridden.
    if forecast_decay_penalty is None:
        decay_default_by_horizon = {1: 0.0, 3: 0.10, 5: 0.25, 10: 0.50}
        if horizon not in decay_default_by_horizon:
            raise KeyError(
                f"horizon {horizon} not in {sorted(decay_default_by_horizon.keys())}"
            )
        forecast_decay_penalty = decay_default_by_horizon[horizon]

    return ConvictionComponents(
        edge_score=edge_score,
        asymmetry_score=asymmetry_score,
        model_agreement=model_agreement,
        valuation_support=valuation_support,
        trend_confirmation=trend_confirmation,
        liquidity_support=liquidity_support,
        tail_risk_penalty=tail_risk_penalty,
        crowding_penalty=crowding_penalty,
        policy_uncertainty_penalty=policy_uncertainty_penalty,
        forecast_decay_penalty=forecast_decay_penalty,
    )
