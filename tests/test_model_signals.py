"""Layer 6-I D3+D4+D5 — tests for ``macro_pipeline.ensemble.model_signals``.

Spec ref: Strategic L6-I R7 closure pre-flight 2026-05-16 §3 Phase 3 +
Phase 4. Closes ChatGPT methodology Finding #5 (C-5): 11-model
ensemble schema + weight validation + layer-disagreement output.

Per V Decision #2 Option B: schema + minimal wrapper producers
(``wrap_point_estimates_as_model_signals``); full 11-distinct-model
implementation deferred to L7.

Test inventory (POS:NEG ratio ≥40% per Strategic PD18 floor):
   1. POS         test_model_ids_count_is_eleven
   2. POS         test_weights_schema_sums_to_one_per_horizon
   3. POS         test_weights_schema_contains_all_model_ids_per_horizon
   4. POS         test_module_init_validation_runs_successfully
   5. POS-inv     test_dominant_models_per_horizon
   6. POS-inv     test_weights_frozen_view_immutable
   7. POS         test_model_signal_construction
   8. POS-inv     test_wrap_point_estimates_returns_11_signals
   9. POS-inv     test_aggregate_model_signals_reconstructs_point_estimate
  10. POS-inv     test_detect_layer_disagreement_consensus_default
  11. POS-inv     test_detect_layer_disagreement_mixed_signs_flag
  12. POS         test_detect_layer_disagreement_empty_signals
  13. NEG         test_model_signal_unknown_model_id_raises
  14. NEG         test_model_signal_unknown_horizon_raises
  15. NEG         test_model_signal_nan_point_estimate_raises
  16. NEG         test_model_signal_inf_weight_raises
  17. NEG         test_model_signal_weight_out_of_range_raises
  18. NEG         test_model_signal_confidence_out_of_range_raises
  19. NEG         test_wrap_unknown_horizon_raises
  20. NEG         test_wrap_missing_horizon_in_dict_raises
  21. NEG         test_wrap_nan_point_estimate_raises
  22. NEG         test_aggregate_empty_signals_raises
  23. NEG         test_aggregate_mixed_horizons_raises
  24. NEG         test_aggregate_weights_not_summing_to_one_raises

NEG count: 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24 = 12 NEG.
POS / POS-inv: 1-12 = 12.
NEG floor: 12/24 = 50% — meets ≥40% PD18 floor with margin.
"""
from __future__ import annotations

import math
from types import MappingProxyType

import pytest

from macro_pipeline.ensemble.model_signals import (
    LAYER_DISAGREEMENT_LABELS,
    MODEL_IDS,
    MODEL_IDS_VALID,
    MODEL_WEIGHTS_BY_HORIZON,
    MODEL_WEIGHTS_BY_HORIZON_FROZEN,
    SUPPORTED_HORIZONS,
    WEIGHT_SUM_TOLERANCE,
    ModelSignal,
    _validate_model_weights,
    aggregate_model_signals,
    detect_layer_disagreement,
    wrap_point_estimates_as_model_signals,
)


# ============================================================================
# Schema invariants
# ============================================================================


def test_model_ids_count_is_eleven() -> None:
    """POS: exactly 11 model_ids per ChatGPT C-5 spec."""
    assert len(MODEL_IDS) == 11
    assert len(MODEL_IDS_VALID) == 11


def test_weights_schema_sums_to_one_per_horizon() -> None:
    """POS: each horizon's weights sum to 1.0 within tolerance (D4 invariant)."""
    for horizon in SUPPORTED_HORIZONS:
        weights = MODEL_WEIGHTS_BY_HORIZON[horizon]
        total = sum(weights.values())
        assert abs(total - 1.0) < WEIGHT_SUM_TOLERANCE, (
            f"horizon {horizon} weights sum to {total!r}; "
            f"expected 1.0 within {WEIGHT_SUM_TOLERANCE}"
        )


def test_weights_schema_contains_all_model_ids_per_horizon() -> None:
    """POS: each horizon weights dict has all 11 model_ids as keys."""
    for horizon in SUPPORTED_HORIZONS:
        weights = MODEL_WEIGHTS_BY_HORIZON[horizon]
        assert frozenset(weights.keys()) == MODEL_IDS_VALID


def test_module_init_validation_runs_successfully() -> None:
    """POS: re-invoking _validate_model_weights() doesn't raise."""
    _validate_model_weights()  # idempotent; raises if schema broken


def test_dominant_models_per_horizon() -> None:
    """POS-inv: dominant model per horizon per Strategic L6-I spec.

    Vision §6 + R7 ChatGPT C-5 expectation:
      1Y    macro_regime         (highest weight at 1Y)
      3Y    earnings_growth      (highest weight at 3Y)
      5Y    structural_secular   (highest weight at 5Y)
      10Y   structural_secular   (highest weight at 10Y)
    """
    expected_dominant = {
        1: "macro_regime",
        3: "earnings_growth",
        5: "structural_secular",
        10: "structural_secular",
    }
    for horizon, expected_model in expected_dominant.items():
        weights = MODEL_WEIGHTS_BY_HORIZON[horizon]
        max_model = max(weights.items(), key=lambda kv: kv[1])[0]
        assert max_model == expected_model, (
            f"horizon {horizon} dominant model expected {expected_model}, "
            f"got {max_model}"
        )


def test_weights_frozen_view_immutable() -> None:
    """POS-inv: MODEL_WEIGHTS_BY_HORIZON_FROZEN is read-only."""
    assert isinstance(MODEL_WEIGHTS_BY_HORIZON_FROZEN, MappingProxyType)
    for inner in MODEL_WEIGHTS_BY_HORIZON_FROZEN.values():
        assert isinstance(inner, MappingProxyType)
    # Mutation attempts raise TypeError.
    with pytest.raises(TypeError):
        MODEL_WEIGHTS_BY_HORIZON_FROZEN[1] = {}  # type: ignore[index]


# ============================================================================
# ModelSignal dataclass
# ============================================================================


def test_model_signal_construction() -> None:
    """POS: valid ModelSignal constructs successfully."""
    s = ModelSignal(
        model_id="valuation",
        horizon=5,
        point_estimate_annualized=0.06,
        sigma_annualized=0.03,
        confidence=0.7,
        weight=0.15,
        is_placeholder=True,
    )
    assert s.model_id == "valuation"
    assert s.horizon == 5
    assert s.weight == 0.15


def test_model_signal_unknown_model_id_raises() -> None:
    """NEG: unknown model_id raises ValueError."""
    with pytest.raises(ValueError, match="Unknown model_id"):
        ModelSignal(
            model_id="bogus_model",
            horizon=5,
            point_estimate_annualized=0.05,
            sigma_annualized=None,
            confidence=None,
            weight=0.10,
            is_placeholder=True,
        )


def test_model_signal_unknown_horizon_raises() -> None:
    """NEG: unknown horizon raises ValueError."""
    with pytest.raises(ValueError, match="Unknown horizon"):
        ModelSignal(
            model_id="valuation",
            horizon=7,
            point_estimate_annualized=0.05,
            sigma_annualized=None,
            confidence=None,
            weight=0.10,
            is_placeholder=True,
        )


def test_model_signal_nan_point_estimate_raises() -> None:
    """NEG: NaN point_estimate_annualized raises ValueError."""
    with pytest.raises(ValueError, match="point_estimate_annualized must be finite"):
        ModelSignal(
            model_id="valuation",
            horizon=5,
            point_estimate_annualized=float("nan"),
            sigma_annualized=None,
            confidence=None,
            weight=0.10,
            is_placeholder=True,
        )


def test_model_signal_inf_weight_raises() -> None:
    """NEG: inf weight raises ValueError."""
    with pytest.raises(ValueError, match="weight must be finite"):
        ModelSignal(
            model_id="valuation",
            horizon=5,
            point_estimate_annualized=0.05,
            sigma_annualized=None,
            confidence=None,
            weight=float("inf"),
            is_placeholder=True,
        )


def test_model_signal_weight_out_of_range_raises() -> None:
    """NEG: weight outside [0, 1] raises ValueError."""
    with pytest.raises(ValueError, match="weight must be in"):
        ModelSignal(
            model_id="valuation",
            horizon=5,
            point_estimate_annualized=0.05,
            sigma_annualized=None,
            confidence=None,
            weight=1.5,
            is_placeholder=True,
        )


def test_model_signal_confidence_out_of_range_raises() -> None:
    """NEG: confidence outside [0, 1] when non-None raises ValueError."""
    with pytest.raises(ValueError, match="confidence must be in"):
        ModelSignal(
            model_id="valuation",
            horizon=5,
            point_estimate_annualized=0.05,
            sigma_annualized=None,
            confidence=1.2,
            weight=0.10,
            is_placeholder=True,
        )


# ============================================================================
# wrap_point_estimates_as_model_signals
# ============================================================================


def test_wrap_point_estimates_returns_11_signals() -> None:
    """POS-inv: wrapper returns 11 ModelSignals at the requested horizon."""
    point_estimates = {1: 0.07, 3: 0.065, 5: 0.06, 10: 0.055}
    signals = wrap_point_estimates_as_model_signals(point_estimates, horizon=5)
    assert len(signals) == 11
    assert all(s.horizon == 5 for s in signals)
    assert all(s.is_placeholder is True for s in signals)
    assert all(s.point_estimate_annualized == 0.06 for s in signals)
    # Each signal has a distinct model_id matching MODEL_IDS.
    assert {s.model_id for s in signals} == MODEL_IDS_VALID
    # Weights match the schema.
    for s in signals:
        assert s.weight == MODEL_WEIGHTS_BY_HORIZON[5][s.model_id]


def test_wrap_unknown_horizon_raises() -> None:
    """NEG: unknown horizon raises KeyError."""
    with pytest.raises(KeyError, match="Unknown horizon"):
        wrap_point_estimates_as_model_signals({1: 0.07}, horizon=7)


def test_wrap_missing_horizon_in_dict_raises() -> None:
    """NEG: horizon key absent from point_estimates dict raises KeyError."""
    with pytest.raises(KeyError, match="missing horizon"):
        wrap_point_estimates_as_model_signals({1: 0.07}, horizon=5)


def test_wrap_nan_point_estimate_raises() -> None:
    """NEG: NaN in point_estimates raises ValueError."""
    with pytest.raises(ValueError, match="must be finite"):
        wrap_point_estimates_as_model_signals(
            {1: 0.07, 5: float("nan")}, horizon=5
        )


# ============================================================================
# aggregate_model_signals
# ============================================================================


def test_aggregate_model_signals_reconstructs_point_estimate() -> None:
    """POS-inv: weighted-mean of placeholder signals = original point estimate.

    All placeholder signals share the same point_estimate; weighted-mean
    = point_estimate × sum(weights) = point_estimate × 1.0 = point_estimate.
    """
    signals = wrap_point_estimates_as_model_signals(
        {1: 0.05, 3: 0.06, 5: 0.07, 10: 0.075}, horizon=5
    )
    aggregated = aggregate_model_signals(signals)
    assert aggregated == pytest.approx(0.07)


def test_aggregate_empty_signals_raises() -> None:
    """NEG: empty signals tuple raises ValueError."""
    with pytest.raises(ValueError, match="non-empty"):
        aggregate_model_signals(())


def test_aggregate_mixed_horizons_raises() -> None:
    """NEG: signals from different horizons raise ValueError."""
    sigs_5y = wrap_point_estimates_as_model_signals({1: 0, 3: 0, 5: 0.06, 10: 0}, 5)
    sigs_10y = wrap_point_estimates_as_model_signals({1: 0, 3: 0, 5: 0, 10: 0.05}, 10)
    mixed = sigs_5y + sigs_10y
    with pytest.raises(ValueError, match="share one horizon"):
        aggregate_model_signals(mixed)


def test_aggregate_weights_not_summing_to_one_raises() -> None:
    """NEG: signals whose weights don't sum to 1.0 raise ValueError."""
    # Manually construct signals with non-conforming weights.
    bad_sigs = (
        ModelSignal(
            model_id="valuation", horizon=5,
            point_estimate_annualized=0.06,
            sigma_annualized=None, confidence=None,
            weight=0.3, is_placeholder=True,
        ),
        ModelSignal(
            model_id="earnings_growth", horizon=5,
            point_estimate_annualized=0.06,
            sigma_annualized=None, confidence=None,
            weight=0.3, is_placeholder=True,
        ),
    )  # weights sum to 0.6, not 1.0
    with pytest.raises(ValueError, match="weights sum"):
        aggregate_model_signals(bad_sigs)


# ============================================================================
# detect_layer_disagreement
# ============================================================================


def test_detect_layer_disagreement_consensus_default() -> None:
    """POS-inv: all positive point estimates → consensus (no disagreement)."""
    signals = wrap_point_estimates_as_model_signals(
        {1: 0.05, 3: 0.06, 5: 0.07, 10: 0.075}, horizon=5
    )
    flag, label = detect_layer_disagreement(signals)
    assert flag is False
    assert label == "consensus"


def test_detect_layer_disagreement_mixed_signs_flag() -> None:
    """POS-inv: mixed-sign point estimates → mixed_signal_undefined.

    Construct a mixed-sign signal set manually (placeholder wrapper
    only produces same-sign signals by construction).
    """
    signals = (
        ModelSignal(
            model_id="valuation", horizon=5,
            point_estimate_annualized=0.05,
            sigma_annualized=None, confidence=None,
            weight=0.15, is_placeholder=False,
        ),
        ModelSignal(
            model_id="credit_recession", horizon=5,
            point_estimate_annualized=-0.03,
            sigma_annualized=None, confidence=None,
            weight=0.075, is_placeholder=False,
        ),
    )
    flag, label = detect_layer_disagreement(signals)
    assert flag is True
    assert label == "mixed_signal_undefined"
    assert label in LAYER_DISAGREEMENT_LABELS


def test_detect_layer_disagreement_empty_signals() -> None:
    """POS: empty signals → consensus (no disagreement)."""
    flag, label = detect_layer_disagreement(())
    assert flag is False
    assert label == "consensus"
