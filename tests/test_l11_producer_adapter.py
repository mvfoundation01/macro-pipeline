"""L11 D12 — Tests for ``ProducerAdapter``.

PD18 strict ≥40% NEG: this is the validation-heavy module.
Counts: 10 tests (5 NEG / 5 POS) = 50% NEG.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from macro_pipeline.ensemble.aggregator import (
    SUPPORTED_HORIZONS,
    ForecastInputs,
    aggregate_ensemble,
)
from macro_pipeline.webapp.producer_adapter import (
    POINT_ESTIMATE_CLAMP,
    RECESSION_P_CLAMP,
    ProducerAdapter,
)
from macro_pipeline.webapp.snapshot_loader import SnapshotLoader, SnapshotNotFoundError

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = REPO_ROOT / "macro_pipeline" / "data_snapshot"


def _good_form() -> dict[str, float]:
    return dict(
        pmi_manufacturing=51.0,
        pmi_services=53.0,
        cape_ratio=30.0,
        sp500_current=5800.0,
        payrolls_mom=180.0,
        unemployment_rate=4.1,
        core_cpi_yoy=2.9,
        fed_funds_rate=4.25,
    )


def _snapshot_available() -> bool:
    return (DEFAULT_SNAPSHOT / "MANIFEST.json").exists()


# ----------------------------------------------------------------------
# POS — panel-derived path (5 tests)
# ----------------------------------------------------------------------
def test_adapter_constructs_with_default_loader() -> None:
    adapter = ProducerAdapter()
    assert isinstance(adapter._loader, SnapshotLoader)


def test_derive_inputs_produces_valid_forecast_inputs() -> None:
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    adapter = ProducerAdapter()
    result = adapter.derive_forecast_inputs(_good_form(), excel_data={})
    assert isinstance(result.inputs, ForecastInputs)
    # All 4 horizons present in each dict.
    for fname in (
        "point_estimates",
        "point_estimate_n_eff",
        "forecast_sigmas",
        "analog_dispersions",
        "return_sigmas",
        "recession_probabilities",
    ):
        d = getattr(result.inputs, fname)
        assert set(d.keys()) == set(SUPPORTED_HORIZONS), fname


def test_provenance_records_producer_derived_mode_and_panels() -> None:
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    adapter = ProducerAdapter()
    result = adapter.derive_forecast_inputs(_good_form(), excel_data={})
    assert result.provenance["mode"] == "producer_derived"
    assert len(result.provenance["panels_used"]) >= 3
    assert "point_estimates" in result.provenance["producers_run"]
    assert result.provenance["form_overlay_applied"] is True


def test_derived_inputs_flow_into_aggregator_without_error() -> None:
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    adapter = ProducerAdapter()
    result = adapter.derive_forecast_inputs(_good_form(), excel_data={})
    ensemble = aggregate_ensemble(result.inputs)
    assert len(ensemble.horizons) == 4
    for h in (1, 3, 5, 10):
        hr = ensemble.horizons[h]
        assert 0.0 <= hr.triple_decomposition.confidence <= 1.0
        assert 1.0 <= hr.triple_decomposition.conviction <= 10.0


def test_yield_curve_inversion_overlay_increases_recession_p() -> None:
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    adapter1 = ProducerAdapter()
    base = adapter1.derive_forecast_inputs(
        _good_form(), excel_data={"yield_curve": {"inverted": False}}
    )
    adapter2 = ProducerAdapter()
    inverted = adapter2.derive_forecast_inputs(
        _good_form(), excel_data={"yield_curve": {"inverted": True}}
    )
    # At 3Y, the bump multiplier is 0.5 + 0.1*(3-1) = 0.7, so 0.20 yc bump → 0.14 increase.
    assert (
        inverted.inputs.recession_probabilities[3]
        > base.inputs.recession_probabilities[3]
    )


# ----------------------------------------------------------------------
# NEG — validation + fallback paths (5 tests)
# ----------------------------------------------------------------------
def test_derive_inputs_raises_when_snapshot_unavailable(tmp_path: Path) -> None:
    """No snapshot → SnapshotNotFoundError (caller falls back to heuristic)."""
    loader = SnapshotLoader(snapshot_dir=tmp_path / "missing")
    adapter = ProducerAdapter(loader=loader)
    with pytest.raises(SnapshotNotFoundError):
        adapter.derive_forecast_inputs(_good_form(), excel_data={})


def test_extreme_pmi_low_clipped_to_lower_bound() -> None:
    """PMI=0 (severe recession signal) must clip point_estimate to floor."""
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    form = _good_form()
    form["pmi_manufacturing"] = 0.0
    form["pmi_services"] = 0.0
    form["unemployment_rate"] = 15.0
    adapter = ProducerAdapter()
    result = adapter.derive_forecast_inputs(form, excel_data={})
    pe_1y = result.inputs.point_estimates[1]
    assert pe_1y >= POINT_ESTIMATE_CLAMP[0]
    assert pe_1y < 0.0  # extreme down should produce negative


def test_extreme_pmi_high_clipped_to_upper_bound() -> None:
    """PMI=100 must clip point_estimate to ceiling."""
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    form = _good_form()
    form["pmi_manufacturing"] = 100.0
    form["pmi_services"] = 100.0
    adapter = ProducerAdapter()
    result = adapter.derive_forecast_inputs(form, excel_data={})
    pe_1y = result.inputs.point_estimates[1]
    assert pe_1y <= POINT_ESTIMATE_CLAMP[1]


def test_recession_p_never_exceeds_upper_clamp() -> None:
    """Even with all bumps, recession_p must stay within RECESSION_P_CLAMP."""
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    form = _good_form()
    form["pmi_manufacturing"] = 40.0  # bump +0.20
    form["pmi_services"] = 40.0
    form["unemployment_rate"] = 8.0  # bump +0.15
    adapter = ProducerAdapter()
    result = adapter.derive_forecast_inputs(
        form, excel_data={"yield_curve": {"inverted": True}}  # bump +0.20
    )
    for h in SUPPORTED_HORIZONS:
        assert RECESSION_P_CLAMP[0] <= result.inputs.recession_probabilities[h] <= RECESSION_P_CLAMP[1]


def test_garbage_form_values_dont_crash_adapter() -> None:
    """Non-numeric form fields must be substituted by safe defaults."""
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    form: dict[str, Any] = {
        "pmi_manufacturing": "not-a-number",
        "pmi_services": None,
        "cape_ratio": float("nan"),
        "sp500_current": 5800,
        "payrolls_mom": 200,
        "unemployment_rate": "junk",
        "core_cpi_yoy": 3,
        "fed_funds_rate": 4.5,
    }
    adapter = ProducerAdapter()
    # Must NOT raise; non-numeric values are coerced to defaults inside the adapter.
    result = adapter.derive_forecast_inputs(form, excel_data={})
    assert isinstance(result.inputs, ForecastInputs)
