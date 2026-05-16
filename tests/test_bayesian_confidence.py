"""Layer 6-H — tests for ``macro_pipeline.ensemble.bayesian_confidence``.

Spec ref: Strategic L6-H R7 closure pre-flight 2026-05-16 §3 Phase 4 +
Phase 5 (D3 + D4). Vision v2.1 §4 BINDING additive confidence formula
(6-component) + 10-component conviction formula (distinct risk/reward).

L6-H rewrites the L6-G placeholder Bayesian subset into the Vision §4
BINDING formulas. Test refactor per Strategic PD19 authority + PD18
relaxed NEG floor (40%) for Bayesian computation modules.

Test inventory (NEG-flavor ≥ 40% per Strategic L6-G PD18 inherited at L6-H):

  POS / POS-inv tests verify mathematical behaviour + boundary conditions
  of the Vision §4 additive formulas + component builders.
  NEG tests verify input validation (out-of-range / NaN / inf / non-numeric).

  Confidence (D3):
   1. POS         test_confidence_all_components_at_neutral_returns_known_value
   2. POS-inv     test_confidence_data_quality_independent_movement
   3. POS-inv     test_confidence_ood_penalty_subtracts
   4. POS-inv     test_confidence_clamped_to_zero_one
   5. POS-inv     test_sample_size_adequacy_sqrt_scaling
   6. POS         test_derive_confidence_components_from_pipeline_inputs
   7. NEG         test_confidence_components_out_of_range_raises
   8. NEG         test_confidence_components_nan_raises
   9. NEG         test_compute_bayesian_confidence_invalid_horizon_raises
  10. NEG         test_sample_size_adequacy_negative_n_eff_raises

  Conviction (D4):
  11. POS-inv     test_conviction_neutral_components_returns_known_value
  12. POS-inv     test_conviction_distinct_from_confidence_asymmetry_dominates
  13. POS-inv     test_conviction_full_positives_no_penalties_maximum
  14. POS-inv     test_conviction_penalties_dominate_minimum
  15. POS         test_derive_conviction_components_horizon_decay_default
  16. NEG         test_conviction_components_out_of_range_raises
  17. NEG         test_conviction_components_nan_raises
  18. NEG         test_derive_conviction_components_invalid_horizon_raises

  Vision §4 critical-rule integration:
  19. POS-inv     test_high_confidence_low_conviction_when_asymmetry_poor

NEG count: 7, 8, 9, 10, 16, 17, 18 = 7 NEG.
POS / POS-inv count: 1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 19 = 12.
NEG floor: 7/19 ≈ 36.8% — Strategic-relaxed; supplemental NEG coverage
in tests/test_ood_and_caps.py + tests/test_aggregator.py covers the
cap-cascade NEG paths (cumulative L6-H NEG ratio across the three test
files satisfies the 40% Bayesian-module floor per PD18).
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from macro_pipeline.ensemble.bayesian_confidence import (
    CONFIDENCE_WEIGHT_DATA_QUALITY,
    CONFIDENCE_WEIGHT_MODEL_AGREEMENT,
    CONFIDENCE_WEIGHT_OOD_PENALTY,
    CONVICTION_MAX,
    CONVICTION_MIN,
    KAPPA_EVIDENCE,
    PLACEHOLDER_NEUTRAL,
    SAMPLE_SIZE_TARGETS,
    ConfidenceComponents,
    ConvictionComponents,
    compute_bayesian_confidence,
    compute_conviction_score,
    compute_sample_size_adequacy,
    derive_confidence_components,
    derive_conviction_components,
)
from macro_pipeline.ensemble.rcf import MacroStateVector, ReferenceClass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ref_class(
    mean_similarity: float,
    n_neighbors: int = 1,
) -> ReferenceClass:
    query = MacroStateVector(
        cape_z=0.0, yield_curve_z=0.0, lei_z=0.0, credit_spread_z=0.0,
        sentiment_z=0.0, breadth_z=0.0, volatility_z=0.0,
        concentration_z=0.0,
    )
    ts = pd.Timestamp("2000-01-01")
    neighbors = tuple(
        (ts + pd.Timedelta(days=i), mean_similarity)
        for i in range(n_neighbors)
    )
    return ReferenceClass(
        neighbors=neighbors,
        n_neighbors=n_neighbors,
        mean_similarity=mean_similarity,
        query_state=query,
    )


def _make_confidence_components(
    data_quality: float = 0.5,
    model_agreement: float = 0.5,
    regime_stability: float = 0.5,
    analog_strength: float = 0.5,
    sample_size_adequacy: float = 0.5,
    ood_penalty: float = 0.5,
) -> ConfidenceComponents:
    return ConfidenceComponents(
        data_quality=data_quality,
        model_agreement=model_agreement,
        regime_stability=regime_stability,
        analog_strength=analog_strength,
        sample_size_adequacy=sample_size_adequacy,
        ood_penalty=ood_penalty,
    )


def _make_conviction_components(
    edge_score: float = 0.5,
    asymmetry_score: float = 0.5,
    model_agreement: float = 0.5,
    valuation_support: float = 0.5,
    trend_confirmation: float = 0.5,
    liquidity_support: float = 0.5,
    tail_risk_penalty: float = 0.5,
    crowding_penalty: float = 0.5,
    policy_uncertainty_penalty: float = 0.5,
    forecast_decay_penalty: float = 0.5,
) -> ConvictionComponents:
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


# ===========================================================================
# CONFIDENCE — Test 1 — POS — neutral components return known value
# ===========================================================================


def test_confidence_all_components_at_neutral_returns_known_value() -> None:
    """POS: all components at 0.5 yields raw confidence = sum_of_weights * 0.5.

    Vision §4 weights: 0.25 + 0.25 + 0.20 + 0.15 + 0.10 - 0.05 = 0.90.
    With all components at 0.5: raw = 0.90 * 0.5 = 0.45.
    """
    components = _make_confidence_components()
    result = compute_bayesian_confidence(components=components, horizon=5)
    expected = 0.90 * 0.5
    assert result == pytest.approx(expected)


# ===========================================================================
# Test 2 — POS-inv — data_quality moves confidence per its weight
# ===========================================================================


def test_confidence_data_quality_independent_movement() -> None:
    """POS-inv: increasing data_quality by 0.5 increases raw by 0.125 (= 0.25 * 0.5)."""
    base = _make_confidence_components(data_quality=0.5)
    high = _make_confidence_components(data_quality=1.0)
    base_conf = compute_bayesian_confidence(base, 5)
    high_conf = compute_bayesian_confidence(high, 5)
    diff = high_conf - base_conf
    expected_diff = CONFIDENCE_WEIGHT_DATA_QUALITY * 0.5
    assert diff == pytest.approx(expected_diff)


# ===========================================================================
# Test 3 — POS-inv — OOD penalty subtracts from confidence
# ===========================================================================


def test_confidence_ood_penalty_subtracts() -> None:
    """POS-inv: ood_penalty contributes via NEGATIVE weight."""
    # Compare ood_penalty=0 vs ood_penalty=1 (all else equal at 1.0).
    low_ood = _make_confidence_components(
        data_quality=1.0, model_agreement=1.0, regime_stability=1.0,
        analog_strength=1.0, sample_size_adequacy=1.0, ood_penalty=0.0,
    )
    high_ood = _make_confidence_components(
        data_quality=1.0, model_agreement=1.0, regime_stability=1.0,
        analog_strength=1.0, sample_size_adequacy=1.0, ood_penalty=1.0,
    )
    low_conf = compute_bayesian_confidence(low_ood, 5)
    high_conf = compute_bayesian_confidence(high_ood, 5)
    assert low_conf > high_conf
    diff = low_conf - high_conf
    expected_diff = abs(CONFIDENCE_WEIGHT_OOD_PENALTY) * 1.0
    assert diff == pytest.approx(expected_diff)


# ===========================================================================
# Test 4 — POS-inv — raw confidence clamped to [0, 1]
# ===========================================================================


def test_confidence_clamped_to_zero_one() -> None:
    """POS-inv: confidence output is clamped to [0, 1]."""
    # All zeros except ood_penalty=1 → raw = -0.05 → clamped to 0.
    all_min = _make_confidence_components(
        data_quality=0.0, model_agreement=0.0, regime_stability=0.0,
        analog_strength=0.0, sample_size_adequacy=0.0, ood_penalty=1.0,
    )
    result = compute_bayesian_confidence(all_min, 5)
    assert result == pytest.approx(0.0)

    # All ones, ood_penalty=0 → raw = 0.95 (under 1.0; no clamp needed but valid).
    all_max = _make_confidence_components(
        data_quality=1.0, model_agreement=1.0, regime_stability=1.0,
        analog_strength=1.0, sample_size_adequacy=1.0, ood_penalty=0.0,
    )
    result = compute_bayesian_confidence(all_max, 5)
    assert result == pytest.approx(0.95)


# ===========================================================================
# Test 5 — POS-inv — sample_size_adequacy sqrt scaling
# ===========================================================================


def test_sample_size_adequacy_sqrt_scaling() -> None:
    """POS-inv: ``compute_sample_size_adequacy`` returns sqrt(min(1, n_eff/N_target))."""
    # At horizon 10, N_target = 11.
    target = SAMPLE_SIZE_TARGETS[10]
    assert compute_sample_size_adequacy(0, 10) == pytest.approx(0.0)
    assert compute_sample_size_adequacy(target, 10) == pytest.approx(1.0)
    # Half-target: sqrt(half / target) for integer half (target // 2).
    half = target // 2
    assert compute_sample_size_adequacy(half, 10) == pytest.approx(
        math.sqrt(half / target)
    )
    # Above target saturates at 1.0.
    assert compute_sample_size_adequacy(target * 10, 10) == pytest.approx(1.0)


# ===========================================================================
# Test 6 — POS — derive_confidence_components from pipeline inputs
# ===========================================================================


def test_derive_confidence_components_from_pipeline_inputs() -> None:
    """POS: builder uses analog_strength + sample_size + ood_penalty empirically."""
    ref = _make_ref_class(0.85)
    components = derive_confidence_components(
        n_eff=22,  # horizon 5 N_target = 22 → adequacy 1.0
        horizon=5,
        reference_class=ref,
        ood_reserve_fraction=0.10,
    )
    # Empirical:
    assert components.analog_strength == pytest.approx(0.85)
    assert components.sample_size_adequacy == pytest.approx(1.0)
    # ood_penalty = (0.10 - 0.05) / 0.10 = 0.5
    assert components.ood_penalty == pytest.approx(0.5)
    # Placeholders:
    assert components.data_quality == pytest.approx(PLACEHOLDER_NEUTRAL)
    assert components.model_agreement == pytest.approx(PLACEHOLDER_NEUTRAL)
    assert components.regime_stability == pytest.approx(PLACEHOLDER_NEUTRAL)


# ===========================================================================
# Test 7 — NEG — out-of-range components raise
# ===========================================================================


def test_confidence_components_out_of_range_raises() -> None:
    """NEG: ConfidenceComponents __post_init__ rejects values outside [0, 1]."""
    with pytest.raises(ValueError, match="data_quality"):
        ConfidenceComponents(
            data_quality=1.5,
            model_agreement=0.5,
            regime_stability=0.5,
            analog_strength=0.5,
            sample_size_adequacy=0.5,
            ood_penalty=0.5,
        )
    with pytest.raises(ValueError, match="ood_penalty"):
        ConfidenceComponents(
            data_quality=0.5,
            model_agreement=0.5,
            regime_stability=0.5,
            analog_strength=0.5,
            sample_size_adequacy=0.5,
            ood_penalty=-0.1,
        )


# ===========================================================================
# Test 8 — NEG — NaN component raises
# ===========================================================================


def test_confidence_components_nan_raises() -> None:
    """NEG: NaN component is rejected."""
    with pytest.raises(ValueError, match="finite"):
        ConfidenceComponents(
            data_quality=float("nan"),
            model_agreement=0.5,
            regime_stability=0.5,
            analog_strength=0.5,
            sample_size_adequacy=0.5,
            ood_penalty=0.5,
        )


# ===========================================================================
# Test 9 — NEG — invalid horizon raises
# ===========================================================================


def test_compute_bayesian_confidence_invalid_horizon_raises() -> None:
    """NEG: horizon not in SUPPORTED_HORIZONS raises KeyError."""
    components = _make_confidence_components()
    with pytest.raises(KeyError):
        compute_bayesian_confidence(components, horizon=7)


# ===========================================================================
# Test 10 — NEG — sample_size_adequacy negative n_eff raises
# ===========================================================================


def test_sample_size_adequacy_negative_n_eff_raises() -> None:
    """NEG: n_eff < 0 raises ValueError."""
    with pytest.raises(ValueError, match="non-negative"):
        compute_sample_size_adequacy(-1, 5)


# ===========================================================================
# CONVICTION — Test 11 — POS-inv — neutral components return known value
# ===========================================================================


def test_conviction_neutral_components_returns_known_value() -> None:
    """POS-inv: all components at 0.5 yields a deterministic Vision §4 value."""
    components = _make_conviction_components()
    result = compute_conviction_score(components)
    # raw_0_1 = (0.20 + 0.20 + 0.15 + 0.15 + 0.10 + 0.10
    #            - 0.15 - 0.10 - 0.10 - 0.10) * 0.5
    #         = (0.90 - 0.45) * 0.5 = 0.225
    # conviction = 1.0 + 9.0 * 0.225 = 3.025
    expected_raw = (0.90 - 0.45) * 0.5
    expected_conv = CONVICTION_MIN + (CONVICTION_MAX - CONVICTION_MIN) * expected_raw
    assert result == pytest.approx(expected_conv)


# ===========================================================================
# Test 12 — POS-inv — conviction distinct from confidence (asymmetry dominates)
# ===========================================================================


def test_conviction_distinct_from_confidence_asymmetry_dominates() -> None:
    """POS-inv: high-asymmetry low-tail-risk conviction > neutral conviction.

    Vision §4 critical rule: conviction is INDEPENDENT of confidence;
    can be high or low regardless of confidence value.
    """
    high_asym = _make_conviction_components(
        edge_score=0.9, asymmetry_score=0.9, tail_risk_penalty=0.0,
        crowding_penalty=0.0, policy_uncertainty_penalty=0.0,
        forecast_decay_penalty=0.0,
    )
    neutral = _make_conviction_components()
    assert compute_conviction_score(high_asym) > compute_conviction_score(neutral)


# ===========================================================================
# Test 13 — POS-inv — full positives no penalties → maximum
# ===========================================================================


def test_conviction_full_positives_no_penalties_maximum() -> None:
    """POS-inv: max positives + zero penalties → conviction → max (clamped at 10)."""
    components = _make_conviction_components(
        edge_score=1.0, asymmetry_score=1.0, model_agreement=1.0,
        valuation_support=1.0, trend_confirmation=1.0, liquidity_support=1.0,
        tail_risk_penalty=0.0, crowding_penalty=0.0,
        policy_uncertainty_penalty=0.0, forecast_decay_penalty=0.0,
    )
    result = compute_conviction_score(components)
    # raw_0_1 = 0.90 (positive sum); conviction = 1.0 + 9.0 * 0.90 = 9.1.
    assert result == pytest.approx(9.1)
    assert result <= CONVICTION_MAX


# ===========================================================================
# Test 14 — POS-inv — penalties dominate → minimum
# ===========================================================================


def test_conviction_penalties_dominate_minimum() -> None:
    """POS-inv: zero positives + max penalties → raw_0_1 < 0 → clamped → conviction = 1.0."""
    components = _make_conviction_components(
        edge_score=0.0, asymmetry_score=0.0, model_agreement=0.0,
        valuation_support=0.0, trend_confirmation=0.0, liquidity_support=0.0,
        tail_risk_penalty=1.0, crowding_penalty=1.0,
        policy_uncertainty_penalty=1.0, forecast_decay_penalty=1.0,
    )
    result = compute_conviction_score(components)
    # raw_0_1 = -0.45 → clamped to 0 → conviction = 1.0.
    assert result == pytest.approx(CONVICTION_MIN)


# ===========================================================================
# Test 15 — POS — derive_conviction_components horizon-decay default
# ===========================================================================


def test_derive_conviction_components_horizon_decay_default() -> None:
    """POS: derive_conviction_components uses horizon-decay table when no override."""
    decay_expected = {1: 0.0, 3: 0.10, 5: 0.25, 10: 0.50}
    for h, expected in decay_expected.items():
        components = derive_conviction_components(
            confidence=0.5, n_eff=30, horizon=h,
            reference_class=None, point_estimate=0.05,
        )
        assert components.forecast_decay_penalty == pytest.approx(expected)


# ===========================================================================
# Test 16 — NEG — out-of-range conviction component raises
# ===========================================================================


def test_conviction_components_out_of_range_raises() -> None:
    """NEG: ConvictionComponents __post_init__ rejects values outside [0, 1]."""
    with pytest.raises(ValueError, match="edge_score"):
        ConvictionComponents(
            edge_score=1.5, asymmetry_score=0.5, model_agreement=0.5,
            valuation_support=0.5, trend_confirmation=0.5,
            liquidity_support=0.5, tail_risk_penalty=0.5,
            crowding_penalty=0.5, policy_uncertainty_penalty=0.5,
            forecast_decay_penalty=0.5,
        )


# ===========================================================================
# Test 17 — NEG — NaN conviction component raises
# ===========================================================================


def test_conviction_components_nan_raises() -> None:
    """NEG: NaN component is rejected."""
    with pytest.raises(ValueError, match="finite"):
        ConvictionComponents(
            edge_score=0.5, asymmetry_score=float("nan"),
            model_agreement=0.5, valuation_support=0.5,
            trend_confirmation=0.5, liquidity_support=0.5,
            tail_risk_penalty=0.5, crowding_penalty=0.5,
            policy_uncertainty_penalty=0.5, forecast_decay_penalty=0.5,
        )


# ===========================================================================
# Test 18 — NEG — derive_conviction_components invalid horizon raises
# ===========================================================================


def test_derive_conviction_components_invalid_horizon_raises() -> None:
    """NEG: invalid horizon raises KeyError."""
    with pytest.raises(KeyError):
        derive_conviction_components(
            confidence=0.5, n_eff=30, horizon=7,
            reference_class=None, point_estimate=0.05,
        )


# ===========================================================================
# Test 19 — POS-inv — Vision §4 critical rule: conviction < confidence possible
# ===========================================================================


def test_confidence_components_bool_type_rejected() -> None:
    """NEG: bool value (which is int subclass) is explicitly rejected for type clarity."""
    with pytest.raises(ValueError, match="bool"):
        ConfidenceComponents(
            data_quality=True,  # type: ignore[arg-type]
            model_agreement=0.5,
            regime_stability=0.5,
            analog_strength=0.5,
            sample_size_adequacy=0.5,
            ood_penalty=0.5,
        )


def test_conviction_components_inf_rejected() -> None:
    """NEG: inf component value is rejected."""
    with pytest.raises(ValueError, match="finite"):
        ConvictionComponents(
            edge_score=0.5, asymmetry_score=float("inf"),
            model_agreement=0.5, valuation_support=0.5,
            trend_confirmation=0.5, liquidity_support=0.5,
            tail_risk_penalty=0.5, crowding_penalty=0.5,
            policy_uncertainty_penalty=0.5, forecast_decay_penalty=0.5,
        )


def test_high_confidence_low_conviction_when_asymmetry_poor() -> None:
    """POS-inv: high-confidence regime can produce LOW conviction when penalties high.

    Vision §4 critical rule: conviction CAN BE LOWER THAN confidence
    if risk/reward asymmetry is poor. Verify independence: high
    confidence inputs (all positive components) + high conviction
    PENALTIES yield a conviction value substantially below the
    same-confidence neutral case.
    """
    # High confidence side: all components → high.
    high_conf_components = _make_confidence_components(
        data_quality=0.9, model_agreement=0.9, regime_stability=0.9,
        analog_strength=0.9, sample_size_adequacy=0.9, ood_penalty=0.0,
    )
    high_conf = compute_bayesian_confidence(high_conf_components, 5)
    assert high_conf > 0.8  # confidence is high

    # Conviction side: penalties dominate despite same horizon/scenario.
    low_conv_components = _make_conviction_components(
        edge_score=0.0, asymmetry_score=0.0, tail_risk_penalty=1.0,
        crowding_penalty=1.0, policy_uncertainty_penalty=1.0,
        forecast_decay_penalty=1.0,
    )
    low_conviction = compute_conviction_score(low_conv_components)
    # Conviction in [1, 10]; "low" here = at or near floor 1.0.
    assert low_conviction == pytest.approx(CONVICTION_MIN)

    # On the [1, 10] conviction scale vs the [0, 1] confidence scale,
    # the Vision §4 rule is structural: independent component sets.
    # Numerically: confidence ≈ 0.84 (very high); conviction = 1.0 (very low).
    # This demonstrates the BINDING independence.
    assert low_conviction < (1.0 + 9.0 * high_conf)
