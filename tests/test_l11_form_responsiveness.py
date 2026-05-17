"""L11 D12 — Form responsiveness invariants (D7 PASS criteria).

Counts: 4 tests (1 NEG / 3 POS) = 25% NEG. NEG anchor is met aggregate via
the producer_adapter + integration test files.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from macro_pipeline.webapp.producer_adapter import ProducerAdapter

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = REPO_ROOT / "macro_pipeline" / "data_snapshot"


def _baseline() -> dict[str, float]:
    return dict(
        pmi_manufacturing=50.0,
        pmi_services=52.0,
        cape_ratio=32.0,
        sp500_current=5800.0,
        payrolls_mom=200.0,
        unemployment_rate=4.0,
        core_cpi_yoy=3.0,
        fed_funds_rate=4.5,
    )


def _snapshot_available() -> bool:
    return (DEFAULT_SNAPSHOT / "MANIFEST.json").exists()


# ----------------------------------------------------------------------
# POS — sensitivity invariants (3 tests)
# ----------------------------------------------------------------------
def test_pmi_one_unit_change_moves_1y_forecast_at_least_0_3pp() -> None:
    """L11-REV D7 BINDING: ±1 PMI unit → 1Y forecast Δ ≥ 0.3pp."""
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    low = _baseline()
    low["pmi_manufacturing"] = 49.0
    high = _baseline()
    high["pmi_manufacturing"] = 51.0
    r_low = ProducerAdapter().derive_forecast_inputs(low, {})
    r_high = ProducerAdapter().derive_forecast_inputs(high, {})
    # Range is 2 PMI units; per-unit delta = 0.5 of the total.
    delta_per_unit = (
        r_high.inputs.point_estimates[1] - r_low.inputs.point_estimates[1]
    ) / 2.0
    assert delta_per_unit >= 0.003, (
        f"sensitivity {delta_per_unit*100:.3f}pp/unit < 0.3pp; "
        "calibration regressed (D7 invariant)"
    )


def test_yield_curve_inversion_visibly_lifts_recession_p_at_3y() -> None:
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    base = ProducerAdapter().derive_forecast_inputs(
        _baseline(), {"yield_curve": {"inverted": False}}
    )
    inv = ProducerAdapter().derive_forecast_inputs(
        _baseline(), {"yield_curve": {"inverted": True}}
    )
    delta = (
        inv.inputs.recession_probabilities[3]
        - base.inputs.recession_probabilities[3]
    )
    assert delta >= 0.05, f"yc-inversion bump too small at 3Y: {delta:.4f}"


def test_unemployment_shock_lifts_recession_p() -> None:
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    calm = _baseline()
    shock = _baseline()
    shock["unemployment_rate"] = 7.0  # high
    r_calm = ProducerAdapter().derive_forecast_inputs(calm, {})
    r_shock = ProducerAdapter().derive_forecast_inputs(shock, {})
    assert (
        r_shock.inputs.recession_probabilities[1]
        > r_calm.inputs.recession_probabilities[1]
    )


# ----------------------------------------------------------------------
# NEG — sensitivity-overflow guard (1 test)
# ----------------------------------------------------------------------
def test_extreme_pmi_response_stays_inside_aggregator_invariants() -> None:
    """Sensitivity must not produce ForecastInputs outside L6-H accepted ranges
    (would raise inside ``ForecastInputs.__post_init__`` and break the pipeline)."""
    if not _snapshot_available():
        pytest.skip("snapshot not built")
    from macro_pipeline.ensemble.aggregator import aggregate_ensemble

    extreme_low = _baseline()
    extreme_low["pmi_manufacturing"] = 20.0
    extreme_low["pmi_services"] = 20.0
    extreme_low["unemployment_rate"] = 12.0
    result = ProducerAdapter().derive_forecast_inputs(extreme_low, {})
    # ForecastInputs.__post_init__ validates; aggregate_ensemble validates further.
    ensemble = aggregate_ensemble(result.inputs)
    for h in (1, 3, 5, 10):
        hr = ensemble.horizons[h]
        assert 0.0 <= hr.triple_decomposition.confidence <= 1.0
