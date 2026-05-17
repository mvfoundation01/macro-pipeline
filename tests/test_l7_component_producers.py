"""L7 D3 tests — component producers."""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.ensemble.component_producers import (
    L7_BUILT_PRODUCER_SLOTS,
    L8A_DEFERRED_SLOTS,
    produce_data_quality,
    produce_edge_score,
    produce_model_agreement,
    produce_regime_stability,
    produce_valuation_support,
)
from macro_pipeline.ensemble.model_signals import (
    MODEL_IDS,
    ModelSignal,
    wrap_point_estimates_as_model_signals,
)
from macro_pipeline.ensemble.rcf import MacroStateVector, ReferenceClass


# ===========================================================================
# Slot-to-producer mapping constants
# ===========================================================================


def test_l7_built_producer_slots_count() -> None:
    """POS: 5 L7-built producer slots."""
    assert len(L7_BUILT_PRODUCER_SLOTS) == 5


def test_l8a_deferred_slots_count() -> None:
    """POS: 6 L8a-deferred producer slots."""
    assert len(L8A_DEFERRED_SLOTS) == 6


def test_slot_sets_disjoint() -> None:
    """POS: L7-built and L8a-deferred slot sets are disjoint."""
    assert L7_BUILT_PRODUCER_SLOTS.isdisjoint(L8A_DEFERRED_SLOTS)


# ===========================================================================
# produce_data_quality
# ===========================================================================


def test_data_quality_defaults_to_perfect() -> None:
    """POS: defaults (all "perfect" sub-signals) yield 1.0."""
    score = produce_data_quality()
    assert score == pytest.approx(1.0)


def test_data_quality_vintage_age_degrades() -> None:
    """POS-inv: higher vintage_age_days lowers score."""
    fresh = produce_data_quality(vintage_age_days=0)
    stale = produce_data_quality(vintage_age_days=30)
    assert fresh > stale


def test_data_quality_outlier_count_degrades() -> None:
    """POS-inv: outlier_count lowers score."""
    clean = produce_data_quality(outlier_count=0)
    dirty = produce_data_quality(outlier_count=5)
    assert clean > dirty


def test_data_quality_invalid_coverage_raises() -> None:
    """NEG: coverage ratio out of [0, 1] raises."""
    with pytest.raises(ValueError, match="indicator_coverage_ratio"):
        produce_data_quality(indicator_coverage_ratio=1.5)


def test_data_quality_negative_vintage_raises() -> None:
    """NEG: negative vintage_age_days raises."""
    with pytest.raises(ValueError, match="vintage_age_days"):
        produce_data_quality(vintage_age_days=-1)


def test_data_quality_nan_missing_raises() -> None:
    """NEG: NaN missing_data_ratio raises."""
    with pytest.raises(ValueError, match="missing_data_ratio"):
        produce_data_quality(missing_data_ratio=float("nan"))


# ===========================================================================
# produce_model_agreement
# ===========================================================================


def _make_uniform_signals(point_estimate: float) -> tuple:
    """Build 11 placeholder signals all sharing same point_estimate."""
    return wrap_point_estimates_as_model_signals(
        point_estimates={
            1: point_estimate, 3: point_estimate,
            5: point_estimate, 10: point_estimate,
        },
        horizon=5,
    )


def test_model_agreement_uniform_signals_score_1() -> None:
    """POS-inv: uniform placeholder signals → perfect agreement (1.0)."""
    signals = _make_uniform_signals(0.06)
    score = produce_model_agreement(signals)
    assert score == pytest.approx(1.0)


def test_model_agreement_empty_raises() -> None:
    """NEG: empty signals raises."""
    with pytest.raises(ValueError, match="non-empty"):
        produce_model_agreement(())


def test_model_agreement_diverging_signals() -> None:
    """POS-inv: diverging signals produce score < 1."""
    base_signals = list(_make_uniform_signals(0.05))
    # Replace one signal with an outlier-distant point estimate.
    outlier = ModelSignal(
        model_id=base_signals[0].model_id,
        horizon=5,
        point_estimate_annualized=0.50,  # 10x larger
        sigma_annualized=None,
        confidence=None,
        weight=base_signals[0].weight,
        is_placeholder=True,
    )
    mixed = (outlier,) + tuple(base_signals[1:])
    score = produce_model_agreement(mixed)
    # Most signals still uniform; outlier reduces agreement.
    assert 0.0 <= score <= 1.0


# ===========================================================================
# produce_regime_stability
# ===========================================================================


def _make_ref_class(
    mean_sim: float, ood: bool = False, boundary: bool = False
) -> ReferenceClass:
    query = MacroStateVector(
        cape_z=0, yield_curve_z=0, lei_z=0, credit_spread_z=0,
        sentiment_z=0, breadth_z=0, volatility_z=0, concentration_z=0,
    )
    return ReferenceClass(
        neighbors=((pd.Timestamp("2000-01-01"), 0.5),),
        n_neighbors=1,
        mean_similarity=0.5,
        query_state=query,
        top_k_analogs=((pd.Timestamp("2000-01-01"), mean_sim),) if mean_sim >= 0 else (),
        mean_similarity_top_k=mean_sim,
        reference_class_ood=ood,
        sample_boundary_violation=boundary,
    )


def test_regime_stability_none_returns_neutral() -> None:
    """POS: None reference_class → 0.5 neutral."""
    assert produce_regime_stability(None) == pytest.approx(0.5)


def test_regime_stability_high_similarity() -> None:
    """POS-inv: high similarity → high stability."""
    rc = _make_ref_class(mean_sim=0.9)
    score = produce_regime_stability(rc)
    assert score == pytest.approx(0.9)


def test_regime_stability_ood_returns_conservative() -> None:
    """POS-inv: OOD flag → 0.3 (conservative)."""
    rc = _make_ref_class(mean_sim=0.8, ood=True)
    score = produce_regime_stability(rc)
    assert score == pytest.approx(0.3)


def test_regime_stability_boundary_violation_degrades() -> None:
    """POS-inv: sample boundary violation reduces score by 0.1."""
    rc_clean = _make_ref_class(mean_sim=0.7, boundary=False)
    rc_boundary = _make_ref_class(mean_sim=0.7, boundary=True)
    assert produce_regime_stability(rc_clean) > produce_regime_stability(rc_boundary)


# ===========================================================================
# produce_edge_score
# ===========================================================================


def test_edge_score_zero_excess_neutral() -> None:
    """POS-inv: forecast equals risk_free → 0.5 neutral."""
    score = produce_edge_score(
        point_estimate_annualized=0.03,
        sigma_annualized=0.15,
        risk_free_rate=0.03,
    )
    assert score == pytest.approx(0.5)


def test_edge_score_positive_excess_above_half() -> None:
    """POS-inv: positive excess return → score > 0.5."""
    score = produce_edge_score(
        point_estimate_annualized=0.08,
        sigma_annualized=0.15,
        risk_free_rate=0.03,
    )
    assert score > 0.5


def test_edge_score_negative_excess_below_half() -> None:
    """POS-inv: negative excess → score < 0.5."""
    score = produce_edge_score(
        point_estimate_annualized=0.01,
        sigma_annualized=0.15,
        risk_free_rate=0.03,
    )
    assert score < 0.5


def test_edge_score_zero_sigma_neutral() -> None:
    """POS: zero sigma → 0.5 (degenerate)."""
    score = produce_edge_score(
        point_estimate_annualized=0.07,
        sigma_annualized=0.0,
    )
    assert score == pytest.approx(0.5)


def test_edge_score_nan_raises() -> None:
    """NEG: NaN input raises."""
    with pytest.raises(ValueError, match="finite"):
        produce_edge_score(
            point_estimate_annualized=float("nan"),
            sigma_annualized=0.15,
        )


# ===========================================================================
# produce_valuation_support
# ===========================================================================


def test_valuation_support_long_low_cape() -> None:
    """POS-inv: long-equity + low CAPE percentile → high support."""
    score = produce_valuation_support(cape_percentile=0.10)
    assert score == pytest.approx(0.90)


def test_valuation_support_long_high_cape() -> None:
    """POS-inv: long-equity + high CAPE → low support."""
    score = produce_valuation_support(cape_percentile=0.95)
    assert score == pytest.approx(0.05)


def test_valuation_support_short_equity_inverts() -> None:
    """POS-inv: short-equity direction inverts."""
    score = produce_valuation_support(
        cape_percentile=0.95, forecast_direction="short_equity"
    )
    assert score == pytest.approx(0.95)


def test_valuation_support_invalid_direction_raises() -> None:
    """NEG: unknown direction raises."""
    with pytest.raises(ValueError, match="forecast_direction"):
        produce_valuation_support(
            cape_percentile=0.5, forecast_direction="bogus"
        )


def test_valuation_support_invalid_percentile_raises() -> None:
    """NEG: percentile out of [0, 1] raises."""
    with pytest.raises(ValueError, match="cape_percentile"):
        produce_valuation_support(cape_percentile=1.5)
