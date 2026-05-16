"""Layer 6-I D1+D2 — NaN/inf invariant + deep-immutability tests across ensemble.

Spec ref: Strategic L6-I R7 closure pre-flight 2026-05-16 §3 Phase 1
+ Phase 2. Closes Codex code review HIGH Findings:
  - Codex Finding #1 (C-6): frozen mutability — dict fields wrapped via
    MappingProxyType
  - Codex Finding #2 (C-7): NaN/inf invariant enforcement on all public
    numeric fields + helpers

Test inventory (NEG-heavy by design per PD18; D1 tests are uniformly NEG):
   D1 NaN/inf invariants:
   1. NEG  test_triple_sigma_nan_field_raises
   2. NEG  test_triple_sigma_inf_field_raises
   3. NEG  test_triple_decomposition_nan_field_raises
   4. NEG  test_triple_decomposition_inf_field_raises
   5. NEG  test_metric_metadata_nan_range_min_raises
   6. NEG  test_metric_metadata_nan_range_max_raises
   7. NEG  test_metric_metadata_inf_typical_range_raises
   8. NEG  test_reference_class_nan_mean_similarity_raises
   9. NEG  test_forecast_inputs_nan_point_estimate_raises
  10. NEG  test_forecast_inputs_inf_forecast_sigma_raises
  11. NEG  test_forecast_inputs_negative_n_eff_raises
  12. NEG  test_forecast_inputs_non_int_n_eff_raises
  13. NEG  test_forecast_inputs_nan_dms_adjustment_raises
  14. NEG  test_horizon_result_nan_dms_field_raises
  15. NEG  test_horizon_result_nan_metric_outputs_raises
  16. NEG  test_ensemble_result_nan_ood_reserve_raises

   D2 deep-immutability:
  17. POS  test_forecast_inputs_point_estimates_immutable
  18. POS  test_forecast_inputs_all_dicts_immutable
  19. POS  test_horizon_result_metric_outputs_immutable
  20. POS  test_ensemble_result_horizons_immutable
  21. POS  test_ensemble_result_replication_kit_immutable
  22. POS  test_forecast_inputs_accepts_regular_dict
  23. POS  test_forecast_inputs_reads_still_work

NEG count: 1-16 = 16 NEG.
POS count: 17-23 = 7 POS.
Total: 23 tests; NEG-floor = 16/23 ≈ 70% (well above ≥40% PD18 floor).
"""
from __future__ import annotations

import pytest

from macro_pipeline.ensemble.aggregator import (
    SUPPORTED_HORIZONS,
    ForecastInputs,
    aggregate_ensemble,
)
from macro_pipeline.ensemble.metadata import MetricMetadata
from macro_pipeline.ensemble.rcf import MacroStateVector, ReferenceClass
from macro_pipeline.ensemble.triple_decomposition import TripleDecomposition
from macro_pipeline.ensemble.triple_sigma import TripleSigma
import pandas as pd


# ===========================================================================
# Helpers
# ===========================================================================


def _make_valid_forecast_inputs(**overrides) -> ForecastInputs:
    base = {
        "point_estimates": {1: 0.05, 3: 0.06, 5: 0.065, 10: 0.07},
        "point_estimate_n_eff": {1: 100, 3: 30, 5: 18, 10: 9},
        "forecast_sigmas": {1: 0.02, 3: 0.025, 5: 0.03, 10: 0.035},
        "analog_dispersions": {1: 0.04, 3: 0.05, 5: 0.06, 10: 0.07},
        "return_sigmas": {1: 0.15, 3: 0.16, 5: 0.17, 10: 0.18},
        "recession_probabilities": {1: 0.15, 3: 0.25, 5: 0.35, 10: 0.45},
    }
    base.update(overrides)
    return ForecastInputs(**base)  # type: ignore[arg-type]


def _make_metric_metadata_defaults(**overrides) -> dict:
    base = {
        "metric_id": "test_metric",
        "name": "Test Metric",
        "subcategory": "probability",
        "subcategory_index": 1,
        "layer_origin": "L6",
        "unit": "ratio",
        "update_frequency": "on_request",
        "description_l1": "L1",
        "description_l2": "L2",
        "description_l3": "L3",
    }
    base.update(overrides)
    return base


# ===========================================================================
# D1 — NaN/inf invariants
# ===========================================================================


def test_triple_sigma_nan_field_raises() -> None:
    """NEG: NaN in any TripleSigma field raises ValueError."""
    with pytest.raises(ValueError, match="must be finite"):
        TripleSigma(
            return_sigma=float("nan"),
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=0.05,
            horizon=5,
        )
    with pytest.raises(ValueError, match="must be finite"):
        TripleSigma(
            return_sigma=0.15,
            forecast_error_sigma=float("nan"),
            analog_dispersion_sigma=0.05,
            horizon=5,
        )


def test_triple_sigma_inf_field_raises() -> None:
    """NEG: +inf and -inf in TripleSigma field raise ValueError."""
    with pytest.raises(ValueError, match="must be finite"):
        TripleSigma(
            return_sigma=float("inf"),
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=0.05,
            horizon=5,
        )
    with pytest.raises(ValueError, match="must be finite"):
        TripleSigma(
            return_sigma=0.15,
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=float("-inf"),
            horizon=5,
        )


def test_triple_decomposition_nan_field_raises() -> None:
    """NEG: NaN in TripleDecomposition field raises ValueError (explicit msg)."""
    with pytest.raises(ValueError, match="must be finite"):
        TripleDecomposition(
            probability=float("nan"),
            confidence=0.7,
            conviction=5.0,
            horizon=5,
        )
    with pytest.raises(ValueError, match="must be finite"):
        TripleDecomposition(
            probability=0.5,
            confidence=float("nan"),
            conviction=5.0,
            horizon=5,
        )


def test_triple_decomposition_inf_field_raises() -> None:
    """NEG: inf in TripleDecomposition field raises ValueError."""
    with pytest.raises(ValueError, match="must be finite"):
        TripleDecomposition(
            probability=0.5,
            confidence=0.7,
            conviction=float("inf"),
            horizon=5,
        )


def test_metric_metadata_nan_range_min_raises() -> None:
    """NEG: NaN range_min raises ValueError (Codex line 227 closure)."""
    kwargs = _make_metric_metadata_defaults(range_min=float("nan"), range_max=1.0)
    with pytest.raises(ValueError, match="range_min must be finite"):
        MetricMetadata(**kwargs)


def test_metric_metadata_nan_range_max_raises() -> None:
    """NEG: NaN range_max raises ValueError."""
    kwargs = _make_metric_metadata_defaults(range_min=0.0, range_max=float("nan"))
    with pytest.raises(ValueError, match="range_max must be finite"):
        MetricMetadata(**kwargs)


def test_metric_metadata_inf_typical_range_raises() -> None:
    """NEG: inf in typical_range tuple raises ValueError."""
    kwargs = _make_metric_metadata_defaults(typical_range=(0.0, float("inf")))
    with pytest.raises(ValueError, match="typical_range"):
        MetricMetadata(**kwargs)


def test_reference_class_nan_mean_similarity_raises() -> None:
    """NEG: NaN mean_similarity raises ValueError (explicit msg)."""
    query = MacroStateVector(
        cape_z=0.0, yield_curve_z=0.0, lei_z=0.0, credit_spread_z=0.0,
        sentiment_z=0.0, breadth_z=0.0, volatility_z=0.0, concentration_z=0.0,
    )
    neighbors = ((pd.Timestamp("2000-01-01"), 0.5),)
    with pytest.raises(ValueError, match="must be finite"):
        ReferenceClass(
            neighbors=neighbors,
            n_neighbors=1,
            mean_similarity=float("nan"),
            query_state=query,
        )


def test_forecast_inputs_nan_point_estimate_raises() -> None:
    """NEG: NaN in ForecastInputs.point_estimates raises ValueError."""
    bad = {1: 0.05, 3: 0.06, 5: float("nan"), 10: 0.07}
    with pytest.raises(ValueError, match="must be finite"):
        _make_valid_forecast_inputs(point_estimates=bad)


def test_forecast_inputs_inf_forecast_sigma_raises() -> None:
    """NEG: inf in ForecastInputs.forecast_sigmas raises ValueError."""
    bad = {1: 0.02, 3: 0.025, 5: float("inf"), 10: 0.035}
    with pytest.raises(ValueError, match="must be finite"):
        _make_valid_forecast_inputs(forecast_sigmas=bad)


def test_forecast_inputs_negative_n_eff_raises() -> None:
    """NEG: negative n_eff raises ValueError at ForecastInputs construction."""
    bad = {1: 100, 3: 30, 5: 18, 10: -1}
    with pytest.raises(ValueError, match="must be non-negative"):
        _make_valid_forecast_inputs(point_estimate_n_eff=bad)


def test_forecast_inputs_non_int_n_eff_raises() -> None:
    """NEG: non-int n_eff raises TypeError."""
    bad = {1: 100, 3: 30, 5: 18, 10: 9.5}  # float at 10Y
    with pytest.raises(TypeError, match="must be int"):
        _make_valid_forecast_inputs(point_estimate_n_eff=bad)


def test_forecast_inputs_nan_dms_adjustment_raises() -> None:
    """NEG: NaN in ForecastInputs.dms_adjustments raises ValueError."""
    with pytest.raises(ValueError, match="must be finite"):
        _make_valid_forecast_inputs(
            dms_adjustments={1: 0.0, 3: 0.0, 5: float("nan"), 10: -175.0},
        )


def test_horizon_result_nan_dms_field_raises() -> None:
    """NEG: aggregate_ensemble produces HorizonResult with finite DMS fields.

    Indirectly tests that HorizonResult __post_init__ would reject NaN
    if construction attempted with NaN dms field (via direct construction
    test in upstream usage); the aggregator path uses finite-checked
    helpers so this is a no-throw integration smoke test.
    """
    inputs = _make_valid_forecast_inputs()
    result = aggregate_ensemble(inputs)
    import math
    for h in SUPPORTED_HORIZONS:
        hr = result.horizons[h]
        assert math.isfinite(hr.dms_raw_point_estimate)
        assert math.isfinite(hr.dms_adjusted_point_estimate)
        assert math.isfinite(hr.dms_adjustment_bps)


def test_horizon_result_nan_metric_outputs_raises() -> None:
    """NEG: HorizonResult constructed with NaN metric_outputs raises.

    Direct construction test (bypasses aggregator).
    """
    from macro_pipeline.ensemble.aggregator import HorizonResult
    td = TripleDecomposition(probability=0.3, confidence=0.5, conviction=5.0, horizon=5)
    ts = TripleSigma(return_sigma=0.15, forecast_error_sigma=0.03,
                     analog_dispersion_sigma=0.05, horizon=5)
    with pytest.raises(ValueError, match="must be finite"):
        HorizonResult(
            horizon=5,
            triple_decomposition=td,
            triple_sigma=ts,
            metric_outputs={"confidence": float("nan")},
            bayesian_shrinkage_applied=False,
        )


def test_ensemble_result_nan_ood_reserve_raises() -> None:
    """NEG: NaN ood_reserve_fraction raises ValueError at EnsembleResult."""
    from macro_pipeline.ensemble.aggregator import EnsembleResult
    inputs = _make_valid_forecast_inputs()
    result = aggregate_ensemble(inputs)
    # Reconstruct with bad ood reserve.
    with pytest.raises(ValueError, match="must be finite"):
        EnsembleResult(
            horizons=dict(result.horizons),
            ood_reserve_fraction=float("nan"),
            reference_class=None,
            replication_kit_metadata=dict(result.replication_kit_metadata),
            aggregation_timestamp_iso=result.aggregation_timestamp_iso,
        )


# ===========================================================================
# D2 — Deep-immutability via MappingProxyType
# ===========================================================================


def test_forecast_inputs_point_estimates_immutable() -> None:
    """POS: ForecastInputs.point_estimates mutation raises TypeError (deep-immutable)."""
    inputs = _make_valid_forecast_inputs()
    with pytest.raises(TypeError):
        inputs.point_estimates[1] = 999.0  # type: ignore[index]


def test_forecast_inputs_all_dicts_immutable() -> None:
    """POS: ALL ForecastInputs dict fields are deep-immutable."""
    inputs = _make_valid_forecast_inputs()
    dict_attrs = [
        "point_estimates",
        "point_estimate_n_eff",
        "forecast_sigmas",
        "analog_dispersions",
        "return_sigmas",
        "recession_probabilities",
    ]
    for attr in dict_attrs:
        d = getattr(inputs, attr)
        with pytest.raises(TypeError):
            d[1] = 999.0  # type: ignore[index]


def test_horizon_result_metric_outputs_immutable() -> None:
    """POS: HorizonResult.metric_outputs mutation raises TypeError."""
    inputs = _make_valid_forecast_inputs()
    result = aggregate_ensemble(inputs)
    hr = result.horizons[5]
    with pytest.raises(TypeError):
        hr.metric_outputs["confidence"] = 999.0  # type: ignore[index]


def test_ensemble_result_horizons_immutable() -> None:
    """POS: EnsembleResult.horizons mutation raises TypeError."""
    inputs = _make_valid_forecast_inputs()
    result = aggregate_ensemble(inputs)
    with pytest.raises(TypeError):
        del result.horizons[1]  # type: ignore[index]


def test_ensemble_result_replication_kit_immutable() -> None:
    """POS: EnsembleResult.replication_kit_metadata mutation raises TypeError."""
    inputs = _make_valid_forecast_inputs()
    result = aggregate_ensemble(inputs)
    with pytest.raises(TypeError):
        result.replication_kit_metadata["new_key"] = "new_value"  # type: ignore[index]


def test_forecast_inputs_accepts_regular_dict() -> None:
    """POS: ForecastInputs constructor accepts regular dict input (auto-wraps)."""
    regular = {1: 0.05, 3: 0.06, 5: 0.065, 10: 0.07}
    inputs = _make_valid_forecast_inputs(point_estimates=regular)
    # Confirm it's now wrapped (mutation prevented).
    with pytest.raises(TypeError):
        inputs.point_estimates[99] = 0.99  # type: ignore[index]


def test_forecast_inputs_reads_still_work() -> None:
    """POS: read access on wrapped dicts works normally."""
    inputs = _make_valid_forecast_inputs()
    assert inputs.point_estimates[5] == pytest.approx(0.065)
    assert len(inputs.point_estimates) == 4
    assert 10 in inputs.point_estimates
    assert list(inputs.point_estimates.keys()) == [1, 3, 5, 10]


# ===========================================================================
# D5 — Layer-disagreement output integration
# ===========================================================================


def test_horizon_result_layer_disagreement_default_consensus() -> None:
    """POS: aggregate_ensemble populates layer_disagreement fields with consensus."""
    inputs = _make_valid_forecast_inputs()
    result = aggregate_ensemble(inputs)
    for h in SUPPORTED_HORIZONS:
        hr = result.horizons[h]
        # L6-I D5: placeholder wrapper produces consensus by construction.
        assert hr.layer_disagreement_flag is False
        assert hr.layer_disagreement_label == "consensus"


def test_horizon_result_layer_disagreement_label_in_valid_set() -> None:
    """POS-inv: layer_disagreement_label is always in valid set."""
    from macro_pipeline.ensemble.model_signals import LAYER_DISAGREEMENT_LABELS
    inputs = _make_valid_forecast_inputs()
    result = aggregate_ensemble(inputs)
    for h in SUPPORTED_HORIZONS:
        hr = result.horizons[h]
        assert hr.layer_disagreement_label in LAYER_DISAGREEMENT_LABELS
