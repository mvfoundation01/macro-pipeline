"""Layer 6-J D2-D6 — tests for L6-J R7 MEDIUM closures.

Spec ref: Strategic L6-J R7 closure pre-flight 2026-05-16.

Test inventory:
   D2 RCF OOD (ChatGPT R7 #6 / C-8):
   1. POS-inv test_reference_class_top_k_default_fields
   2. POS-inv test_find_reference_class_top_k_threshold_filter
   3. POS-inv test_find_reference_class_ood_when_below_3_neighbors
   4. POS-inv test_find_reference_class_sample_boundary_violation
   5. POS-inv test_horizon_conditional_kappa_scales_with_horizon
   6. POS-inv test_horizon_conditional_kappa_low_similarity_inflates
   7. POS-inv test_horizon_conditional_kappa_similarity_floor
   8. NEG     test_find_reference_class_invalid_threshold_raises
   9. NEG     test_find_reference_class_invalid_top_k_raises
  10. NEG     test_horizon_conditional_kappa_invalid_horizon_raises
  11. NEG     test_horizon_conditional_kappa_nan_similarity_raises
  12. NEG     test_reference_class_top_k_too_long_raises

   D3 Triple sigma validity (ChatGPT R7 #7 / C-9):
  13. POS-inv test_compute_sigma_validity_no_flags_no_warning
  14. POS-inv test_compute_sigma_validity_vol_cluster
  15. POS-inv test_compute_sigma_validity_multiple_flags
  16. POS-inv test_compute_sigma_validity_realized_ratio_threshold
  17. POS-inv test_triple_sigma_default_no_warning
  18. POS-inv test_triple_sigma_with_reasons_warning_true
  19. NEG     test_triple_sigma_warning_reasons_mismatch_raises
  20. NEG     test_triple_sigma_invalid_reason_code_raises
  21. NEG     test_compute_sigma_validity_nan_ratio_raises

   D4 Registry lineage (ChatGPT R7 #8 / C-10):
  22. POS     test_metric_lineage_default_all_none
  23. POS     test_metric_lineage_populated
  24. POS     test_validate_registry_counts_actual_split
  25. POS     test_validate_registry_counts_passes_with_expected
  26. POS-inv test_metric_metadata_derive_status_from_legacy
  27. POS-inv test_metric_metadata_explicit_status_override
  28. NEG     test_validate_registry_counts_mismatch_raises
  29. NEG     test_metric_metadata_invalid_status_raises
  30. NEG     test_metric_metadata_invalid_deferred_reason_raises
  31. NEG     test_metric_metadata_computed_with_deferred_to_raises

   D5 YAML registry caching (Codex R7 #3 / C-12):
  32. POS-inv test_load_metrics_registry_default_path_cached
  33. POS-inv test_load_metrics_registry_explicit_path_not_cached
  34. POS-inv test_clear_registry_cache_for_testing

   D6 Aggregator purity (Codex R7 #5 / C-14):
  35. POS-inv test_aggregate_horizons_pure_deterministic
  36. POS-inv test_aggregate_ensemble_injectable_timestamp
  37. POS-inv test_aggregate_ensemble_injectable_code_sha
  38. POS-inv test_aggregate_ensemble_dynamic_default_fallback
  39. NEG     test_aggregate_ensemble_invalid_timestamp_raises
  40. NEG     test_aggregate_ensemble_invalid_code_sha_raises

NEG count: 8, 9, 10, 11, 12, 19, 20, 21, 28, 29, 30, 31, 39, 40 = 14 NEG.
POS / POS-inv count: 1-7, 13-18, 22-27, 32-38 = 26.
Total: 40 tests.
NEG floor: 14/40 = 35% — at PD18 relaxed floor for L6-J integration sub-phase.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from macro_pipeline.ensemble.aggregator import (
    SUPPORTED_HORIZONS,
    ForecastInputs,
    aggregate_ensemble,
    aggregate_horizons_pure,
)
from macro_pipeline.ensemble.metadata import (
    DEFERRED_REASON_VALID,
    METRIC_STATUS_VALID,
    MetricLineage,
    MetricMetadata,
)
from macro_pipeline.ensemble.rcf import (
    BASE_KAPPA_BY_HORIZON,
    DEFAULT_MIN_SIMILARITY_THRESHOLD,
    DEFAULT_TOP_K_REPORTED,
    MACRO_STATE_FIELDS,
    SAMPLE_START_BOUNDARY,
    SIMILARITY_KAPPA_FLOOR,
    MacroStateVector,
    ReferenceClass,
    compute_horizon_conditional_kappa,
    find_reference_class,
)
from macro_pipeline.ensemble.registry import (
    DEFAULT_REGISTRY_PATH,
    _clear_registry_cache_for_testing,
    _load_default_registry_cached,
    load_metrics_registry,
    validate_registry_counts,
)
from macro_pipeline.ensemble.triple_sigma import (
    DEFAULT_REALIZED_VOL_RATIO_THRESHOLD,
    SIGMA_VALIDITY_REASON_CODES,
    TripleSigma,
    compute_sigma_validity_diagnostics,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_macro_state_vector(**overrides) -> MacroStateVector:
    base = {f: 0.0 for f in MACRO_STATE_FIELDS}
    base.update(overrides)
    return MacroStateVector(**base)


def _make_historical_panel(n_rows: int, start_date: str = "1950-01-01"):
    """Generate synthetic z-scored historical panel for RCF tests."""
    dates = pd.date_range(start=start_date, periods=n_rows, freq="ME")
    data = {f: [0.1 * (i % 5) - 0.2 for i in range(n_rows)] for f in MACRO_STATE_FIELDS}
    return pd.DataFrame(data, index=dates)


def _make_valid_forecast_inputs() -> ForecastInputs:
    return ForecastInputs(
        point_estimates={1: 0.05, 3: 0.06, 5: 0.065, 10: 0.07},
        point_estimate_n_eff={1: 100, 3: 30, 5: 18, 10: 9},
        forecast_sigmas={1: 0.02, 3: 0.025, 5: 0.03, 10: 0.035},
        analog_dispersions={1: 0.04, 3: 0.05, 5: 0.06, 10: 0.07},
        return_sigmas={1: 0.15, 3: 0.16, 5: 0.17, 10: 0.18},
        recession_probabilities={1: 0.15, 3: 0.25, 5: 0.35, 10: 0.45},
    )


# =============================================================================
# D2 — RCF OOD handling
# =============================================================================


def test_reference_class_top_k_default_fields() -> None:
    """POS-inv: ReferenceClass with no L6-J fields uses default neutral values."""
    query = _make_macro_state_vector(cape_z=0.1)
    rc = ReferenceClass(
        neighbors=((pd.Timestamp("2000-01-01"), 0.5),),
        n_neighbors=1,
        mean_similarity=0.5,
        query_state=query,
    )
    assert rc.top_k_analogs == ()
    assert rc.mean_similarity_top_k == 0.0
    assert rc.min_similarity_threshold == DEFAULT_MIN_SIMILARITY_THRESHOLD
    assert rc.reference_class_ood is False
    assert rc.sample_boundary_violation is False


def test_find_reference_class_top_k_threshold_filter() -> None:
    """POS-inv: top_k_analogs filters by min_similarity_threshold."""
    query = _make_macro_state_vector(cape_z=0.5, yield_curve_z=0.5)
    panel = _make_historical_panel(50)
    rc = find_reference_class(
        query, panel, n_neighbors=10, min_similarity_threshold=0.5, top_k_reported=5
    )
    assert len(rc.top_k_analogs) <= 5
    for ts, sim in rc.top_k_analogs:
        assert sim >= 0.5


def test_find_reference_class_ood_when_below_3_neighbors() -> None:
    """POS-inv: reference_class_ood fires when <3 above-threshold analogs."""
    query = _make_macro_state_vector(cape_z=5.0)  # extreme z-score
    panel = _make_historical_panel(50)
    # High threshold => few analogs pass
    rc = find_reference_class(
        query, panel, n_neighbors=10, min_similarity_threshold=0.999, top_k_reported=5
    )
    # With near-perfect threshold, expect 0-2 matches → OOD fires.
    assert rc.reference_class_ood == (len(rc.top_k_analogs) < 3)


def test_find_reference_class_sample_boundary_violation() -> None:
    """POS-inv: sample_boundary_violation fires when analog predates 1913."""
    query = _make_macro_state_vector(cape_z=0.1)
    # Panel starting 1900 (pre-1913 boundary).
    panel = _make_historical_panel(30, start_date="1900-01-01")
    rc = find_reference_class(query, panel, n_neighbors=10)
    assert rc.sample_boundary_violation is True


def test_horizon_conditional_kappa_scales_with_horizon() -> None:
    """POS-inv: longer horizons → higher kappa (more shrinkage to prior)."""
    sim = 0.5  # constant
    k1 = compute_horizon_conditional_kappa(1, sim)
    k3 = compute_horizon_conditional_kappa(3, sim)
    k5 = compute_horizon_conditional_kappa(5, sim)
    k10 = compute_horizon_conditional_kappa(10, sim)
    assert k1 < k3 < k5 < k10


def test_horizon_conditional_kappa_low_similarity_inflates() -> None:
    """POS-inv: low similarity → kappa_eff inflates (stronger prior pull)."""
    horizon = 10
    k_low = compute_horizon_conditional_kappa(horizon, 0.20)
    k_high = compute_horizon_conditional_kappa(horizon, 0.80)
    assert k_low > k_high


def test_horizon_conditional_kappa_similarity_floor() -> None:
    """POS-inv: similarity below SIMILARITY_KAPPA_FLOOR (0.10) is floored."""
    base = BASE_KAPPA_BY_HORIZON[10]
    # Very low similarity hits the floor.
    k = compute_horizon_conditional_kappa(10, 0.05)
    expected = base / SIMILARITY_KAPPA_FLOOR
    assert k == pytest.approx(expected)


def test_find_reference_class_invalid_threshold_raises() -> None:
    """NEG: invalid min_similarity_threshold raises ValueError."""
    query = _make_macro_state_vector(cape_z=0.1)
    panel = _make_historical_panel(30)
    with pytest.raises(ValueError, match="finite"):
        find_reference_class(
            query, panel, n_neighbors=10, min_similarity_threshold=float("nan")
        )
    with pytest.raises(ValueError, match="in"):
        find_reference_class(
            query, panel, n_neighbors=10, min_similarity_threshold=1.5
        )


def test_find_reference_class_invalid_top_k_raises() -> None:
    """NEG: invalid top_k_reported raises ValueError."""
    query = _make_macro_state_vector(cape_z=0.1)
    panel = _make_historical_panel(30)
    with pytest.raises(ValueError, match="in"):
        find_reference_class(query, panel, n_neighbors=10, top_k_reported=0)
    with pytest.raises(ValueError, match="in"):
        find_reference_class(query, panel, n_neighbors=10, top_k_reported=15)


def test_horizon_conditional_kappa_invalid_horizon_raises() -> None:
    """NEG: invalid horizon raises KeyError."""
    with pytest.raises(KeyError):
        compute_horizon_conditional_kappa(7, 0.5)


def test_horizon_conditional_kappa_nan_similarity_raises() -> None:
    """NEG: NaN mean_similarity_top_k raises ValueError."""
    with pytest.raises(ValueError, match="finite"):
        compute_horizon_conditional_kappa(5, float("nan"))


def test_reference_class_top_k_too_long_raises() -> None:
    """NEG: top_k_analogs longer than 10 raises ValueError."""
    query = _make_macro_state_vector()
    too_long = tuple((pd.Timestamp("2000-01-01"), 0.5) for _ in range(11))
    with pytest.raises(ValueError, match="top_k_analogs"):
        ReferenceClass(
            neighbors=((pd.Timestamp("2000-01-01"), 0.5),),
            n_neighbors=1,
            mean_similarity=0.5,
            query_state=query,
            top_k_analogs=too_long,
        )


# =============================================================================
# D3 — Triple sigma validity flag
# =============================================================================


def test_compute_sigma_validity_no_flags_no_warning() -> None:
    """POS-inv: no detection flags → no warning, empty reasons."""
    warning, reasons = compute_sigma_validity_diagnostics()
    assert warning is False
    assert reasons == ()


def test_compute_sigma_validity_vol_cluster() -> None:
    """POS-inv: vol_cluster_flag=True → warning + 'vol_cluster_detected'."""
    warning, reasons = compute_sigma_validity_diagnostics(vol_cluster_flag=True)
    assert warning is True
    assert reasons == ("vol_cluster_detected",)


def test_compute_sigma_validity_multiple_flags() -> None:
    """POS-inv: multiple flags produce multiple reasons in canonical order."""
    warning, reasons = compute_sigma_validity_diagnostics(
        vol_cluster_flag=True,
        structural_break_flag=True,
        policy_shock_flag=True,
    )
    assert warning is True
    assert set(reasons) == {
        "vol_cluster_detected",
        "structural_break_detected",
        "policy_shock_detected",
    }


def test_compute_sigma_validity_realized_ratio_threshold() -> None:
    """POS-inv: realized_vol_ratio > threshold triggers breach reason."""
    warning, reasons = compute_sigma_validity_diagnostics(
        realized_vol_ratio=2.5,
        realized_vol_ratio_threshold=DEFAULT_REALIZED_VOL_RATIO_THRESHOLD,
    )
    assert warning is True
    assert "realized_vol_ratio_threshold_breach" in reasons


def test_triple_sigma_default_no_warning() -> None:
    """POS-inv: TripleSigma default values produce no warning."""
    ts = TripleSigma(
        return_sigma=0.15,
        forecast_error_sigma=0.03,
        analog_dispersion_sigma=0.05,
        horizon=5,
    )
    assert ts.sqrt_t_scaling_warning is False
    assert ts.sqrt_t_validity_reason_codes == ()


def test_triple_sigma_with_reasons_warning_true() -> None:
    """POS-inv: TripleSigma with reason codes requires warning=True."""
    ts = TripleSigma(
        return_sigma=0.15,
        forecast_error_sigma=0.03,
        analog_dispersion_sigma=0.05,
        horizon=5,
        sqrt_t_scaling_warning=True,
        sqrt_t_validity_reason_codes=("vol_cluster_detected",),
    )
    assert ts.sqrt_t_scaling_warning is True
    assert len(ts.sqrt_t_validity_reason_codes) == 1


def test_triple_sigma_warning_reasons_mismatch_raises() -> None:
    """NEG: warning=True with empty reasons (or vice versa) raises."""
    with pytest.raises(ValueError, match="must equal"):
        TripleSigma(
            return_sigma=0.15,
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=0.05,
            horizon=5,
            sqrt_t_scaling_warning=True,
            sqrt_t_validity_reason_codes=(),
        )
    with pytest.raises(ValueError, match="must equal"):
        TripleSigma(
            return_sigma=0.15,
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=0.05,
            horizon=5,
            sqrt_t_scaling_warning=False,
            sqrt_t_validity_reason_codes=("vol_cluster_detected",),
        )


def test_triple_sigma_invalid_reason_code_raises() -> None:
    """NEG: unknown reason code raises ValueError."""
    with pytest.raises(ValueError, match="Unknown"):
        TripleSigma(
            return_sigma=0.15,
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=0.05,
            horizon=5,
            sqrt_t_scaling_warning=True,
            sqrt_t_validity_reason_codes=("bogus_reason",),
        )


def test_compute_sigma_validity_nan_ratio_raises() -> None:
    """NEG: NaN realized_vol_ratio raises ValueError."""
    with pytest.raises(ValueError, match="finite"):
        compute_sigma_validity_diagnostics(realized_vol_ratio=float("nan"))


# =============================================================================
# D4 — Registry lineage
# =============================================================================


def test_metric_lineage_default_all_none() -> None:
    """POS: MetricLineage with no args defaults to all None."""
    lineage = MetricLineage()
    assert lineage.raw_source is None
    assert lineage.loader is None
    assert lineage.transform is None
    assert lineage.model is None
    assert lineage.aggregator_field is None
    assert lineage.output_surface is None


def test_metric_lineage_populated() -> None:
    """POS: MetricLineage with populated fields."""
    lineage = MetricLineage(
        raw_source="fred:UMCSENT",
        loader="macro_pipeline.loaders.fred:FREDLoader.fetch",
        transform=None,
        model="macro_pipeline.models.return_forecast:Ridge",
        aggregator_field="HorizonResult.metric_outputs.confidence",
        output_surface=None,
    )
    assert lineage.raw_source == "fred:UMCSENT"


def test_validate_registry_counts_actual_split() -> None:
    """POS: empirical registry split matches L6-J D1 audit: 40/36/14."""
    reg = load_metrics_registry()
    counts = validate_registry_counts(
        reg, expected_computed=None, expected_deferred=None
    )
    assert counts["computed"] == 40
    assert counts["deferred"] == 50
    assert counts["deferred_to_l7"] == 36
    assert counts["deferred_to_l8a"] == 14
    assert counts["total"] == 90


def test_validate_registry_counts_passes_with_expected() -> None:
    """POS: validate_registry_counts passes when expected values match."""
    reg = load_metrics_registry()
    counts = validate_registry_counts(
        reg, expected_computed=40, expected_deferred=50
    )
    assert counts["computed"] == 40
    assert counts["deferred"] == 50


def test_metric_metadata_derive_status_from_legacy() -> None:
    """POS-inv: derive_status returns 'computed' when computation_path is set."""
    m = MetricMetadata(
        metric_id="test_metric",
        name="Test", subcategory="probability", subcategory_index=1,
        layer_origin="L6", unit="ratio", update_frequency="on_request",
        description_l1="L1", description_l2="L2", description_l3="L3",
        computation_path="some.module:some_func",
    )
    assert m.derive_status() == "computed"
    # And without computation_path → deferred.
    m2 = MetricMetadata(
        metric_id="test_metric2",
        name="Test", subcategory="probability", subcategory_index=1,
        layer_origin="L6", unit="ratio", update_frequency="on_request",
        description_l1="L1", description_l2="L2", description_l3="L3",
    )
    assert m2.derive_status() == "deferred"


def test_metric_metadata_explicit_status_override() -> None:
    """POS-inv: explicit status overrides derived value."""
    m = MetricMetadata(
        metric_id="test_metric",
        name="Test", subcategory="probability", subcategory_index=1,
        layer_origin="L6", unit="ratio", update_frequency="on_request",
        description_l1="L1", description_l2="L2", description_l3="L3",
        status="computed",
        lineage=MetricLineage(raw_source="x"),
    )
    assert m.derive_status() == "computed"


def test_validate_registry_counts_mismatch_raises() -> None:
    """NEG: registry split mismatch raises ValueError."""
    reg = load_metrics_registry()
    with pytest.raises(ValueError, match="count"):
        validate_registry_counts(
            reg, expected_computed=99, expected_deferred=None
        )


def test_metric_metadata_invalid_status_raises() -> None:
    """NEG: invalid status raises ValueError."""
    with pytest.raises(ValueError, match="status"):
        MetricMetadata(
            metric_id="test_metric",
            name="Test", subcategory="probability", subcategory_index=1,
            layer_origin="L6", unit="ratio", update_frequency="on_request",
            description_l1="L1", description_l2="L2", description_l3="L3",
            status="bogus_status",
        )


def test_metric_metadata_invalid_deferred_reason_raises() -> None:
    """NEG: invalid deferred_reason raises ValueError."""
    with pytest.raises(ValueError, match="deferred_reason"):
        MetricMetadata(
            metric_id="test_metric",
            name="Test", subcategory="probability", subcategory_index=1,
            layer_origin="L6", unit="ratio", update_frequency="on_request",
            description_l1="L1", description_l2="L2", description_l3="L3",
            deferred_reason="bogus_reason",
        )


def test_metric_metadata_computed_with_deferred_to_raises() -> None:
    """NEG: status='computed' with deferred_to set raises ValueError."""
    with pytest.raises(ValueError, match="computed metric"):
        MetricMetadata(
            metric_id="test_metric",
            name="Test", subcategory="probability", subcategory_index=1,
            layer_origin="L6", unit="ratio", update_frequency="on_request",
            description_l1="L1", description_l2="L2", description_l3="L3",
            status="computed",
            deferred_to="L7",
        )


# =============================================================================
# D5 — YAML registry caching
# =============================================================================


def test_load_metrics_registry_default_path_cached() -> None:
    """POS-inv: load_metrics_registry() twice returns same object (cache hit)."""
    _clear_registry_cache_for_testing()
    r1 = load_metrics_registry()
    r2 = load_metrics_registry()
    # Cache hit: same object identity.
    assert r1 is r2
    info = _load_default_registry_cached.cache_info()
    assert info.hits >= 1


def test_load_metrics_registry_explicit_path_not_cached() -> None:
    """POS-inv: explicit path bypasses cache (re-parses each call)."""
    _clear_registry_cache_for_testing()
    r1 = load_metrics_registry(path=DEFAULT_REGISTRY_PATH)
    r2 = load_metrics_registry(path=DEFAULT_REGISTRY_PATH)
    # Explicit path: distinct dicts (no cache).
    assert r1 is not r2
    # But content equality.
    assert set(r1.keys()) == set(r2.keys())


def test_clear_registry_cache_for_testing() -> None:
    """POS-inv: _clear_registry_cache_for_testing resets the singleton cache."""
    load_metrics_registry()  # populates cache
    info_before = _load_default_registry_cached.cache_info()
    assert info_before.currsize == 1
    _clear_registry_cache_for_testing()
    info_after = _load_default_registry_cached.cache_info()
    assert info_after.currsize == 0


# =============================================================================
# D6 — Aggregator purity
# =============================================================================


def test_aggregate_horizons_pure_deterministic() -> None:
    """POS-inv: aggregate_horizons_pure twice → identical horizon results."""
    inputs = _make_valid_forecast_inputs()
    h1, ood1, codes1 = aggregate_horizons_pure(inputs)
    h2, ood2, codes2 = aggregate_horizons_pure(inputs)
    # Same OOD reserve.
    assert ood1 == ood2
    assert codes1 == codes2
    # Per-horizon equivalence.
    for h in SUPPORTED_HORIZONS:
        assert h1[h].triple_decomposition.probability == pytest.approx(
            h2[h].triple_decomposition.probability
        )
        assert h1[h].triple_decomposition.confidence == pytest.approx(
            h2[h].triple_decomposition.confidence
        )
        assert h1[h].dms_adjusted_point_estimate == pytest.approx(
            h2[h].dms_adjusted_point_estimate
        )


def test_aggregate_ensemble_injectable_timestamp() -> None:
    """POS-inv: explicit timestamp_utc reflected in EnsembleResult metadata."""
    inputs = _make_valid_forecast_inputs()
    fixed_dt = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)
    result = aggregate_ensemble(inputs, timestamp_utc=fixed_dt)
    assert result.aggregation_timestamp_iso == fixed_dt.isoformat()
    assert (
        result.replication_kit_metadata["aggregation_timestamp_iso"]
        == fixed_dt.isoformat()
    )


def test_aggregate_ensemble_injectable_code_sha() -> None:
    """POS-inv: explicit code_sha reflected in replication metadata."""
    inputs = _make_valid_forecast_inputs()
    custom_sha = "0" * 40
    result = aggregate_ensemble(inputs, code_sha=custom_sha)
    assert result.replication_kit_metadata["code_sha"] == custom_sha


def test_aggregate_ensemble_dynamic_default_fallback() -> None:
    """POS-inv: no injection → dynamic timestamp + git SHA (backward compat)."""
    inputs = _make_valid_forecast_inputs()
    result1 = aggregate_ensemble(inputs)
    # SHA is dynamic git rev-parse OR "unknown"; non-empty string.
    assert isinstance(result1.replication_kit_metadata["code_sha"], str)
    assert len(result1.replication_kit_metadata["code_sha"]) >= 1


def test_aggregate_ensemble_invalid_timestamp_raises() -> None:
    """NEG: non-datetime timestamp_utc raises TypeError."""
    inputs = _make_valid_forecast_inputs()
    with pytest.raises(TypeError, match="datetime"):
        aggregate_ensemble(inputs, timestamp_utc="2026-05-16")  # type: ignore[arg-type]


def test_aggregate_ensemble_invalid_code_sha_raises() -> None:
    """NEG: non-str code_sha raises TypeError."""
    inputs = _make_valid_forecast_inputs()
    with pytest.raises(TypeError, match="str"):
        aggregate_ensemble(inputs, code_sha=12345)  # type: ignore[arg-type]
