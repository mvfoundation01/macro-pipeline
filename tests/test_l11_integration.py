"""L11 D12 — Integration tests (full POST /forecast/run + provenance plumbing).

Counts: 5 tests (3 NEG / 2 POS) = 60% NEG.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from macro_pipeline.webapp.app import create_app
from macro_pipeline.webapp.data_ingestion import ForecastInputsBuilder
from macro_pipeline.webapp.snapshot_loader import SnapshotNotFoundError

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = REPO_ROOT / "macro_pipeline" / "data_snapshot"


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "UPLOAD_DIR": tmp_path / "uploads",
            "FORECAST_STORE_DIR": tmp_path / "forecasts",
            "WEBAPP_RENDER_DIR": tmp_path / "renders",
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


def _good_form() -> dict[str, str]:
    return {
        "pmi_manufacturing": "51.0",
        "pmi_services": "53.0",
        "cape_ratio": "30.0",
        "sp500_current": "5800.0",
        "payrolls_mom": "200",
        "unemployment_rate": "4.1",
        "core_cpi_yoy": "2.9",
        "fed_funds_rate": "4.25",
    }


# ----------------------------------------------------------------------
# POS — happy paths (2 tests)
# ----------------------------------------------------------------------
def test_post_forecast_run_writes_provenance_json(client, app) -> None:
    if not (DEFAULT_SNAPSHOT / "MANIFEST.json").exists():
        pytest.skip("snapshot not built")
    resp = client.post("/forecast/run", data=_good_form(), follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers.get("Location", "")
    assert "/results/" in location
    # PROVENANCE.json must be written into the report dir.
    render_dir = Path(app.config["WEBAPP_RENDER_DIR"])
    prov_files = list(render_dir.rglob("PROVENANCE.json"))
    assert len(prov_files) == 1
    payload = json.loads(prov_files[0].read_text(encoding="utf-8"))
    assert payload["mode"] == "producer_derived"
    assert payload["snapshot_date"] != "unknown"
    assert len(payload["producers_run"]) == 6


def test_results_page_renders_provenance_section(client) -> None:
    if not (DEFAULT_SNAPSHOT / "MANIFEST.json").exists():
        pytest.skip("snapshot not built")
    client.post("/forecast/run", data=_good_form(), follow_redirects=False)
    resp = client.get("/results/latest", follow_redirects=True)
    body = resp.data.decode("utf-8")
    assert "DATA PROVENANCE" in body
    assert "producer_derived" in body
    assert "Ngày build snapshot" in body
    # At least one of the producer-run names should be rendered as a code block.
    assert "point_estimates" in body


# ----------------------------------------------------------------------
# NEG — fallback / regression guards (3 tests)
# ----------------------------------------------------------------------
def test_builder_falls_back_to_heuristic_when_adapter_raises(client) -> None:
    """Inject a broken adapter; build() must return a valid ForecastInputs via heuristic."""

    class _BrokenAdapter:
        def derive_forecast_inputs(self, *_a, **_kw):
            raise SnapshotNotFoundError("test injection")

    builder = ForecastInputsBuilder(producer_adapter=_BrokenAdapter())
    fi = builder.build(
        uploaded_data=None,
        numerical_inputs={
            "pmi_manufacturing": 51.0,
            "pmi_services": 53.0,
            "cape_ratio": 30.0,
            "sp500_current": 5800.0,
            "payrolls_mom": 200.0,
            "unemployment_rate": 4.1,
            "core_cpi_yoy": 2.9,
            "fed_funds_rate": 4.25,
        },
    )
    assert builder.last_provenance["mode"] == "heuristic_fallback"
    assert "test injection" in builder.last_provenance["fallback_reason"]
    # ForecastInputs must still be valid.
    assert set(fi.point_estimates.keys()) == {1, 3, 5, 10}


def test_builder_falls_back_when_adapter_raises_generic_exception() -> None:
    """Non-Snapshot exception from adapter must also fall back gracefully."""

    class _BrokenAdapter:
        def derive_forecast_inputs(self, *_a, **_kw):
            raise RuntimeError("upstream weirdness")

    builder = ForecastInputsBuilder(producer_adapter=_BrokenAdapter())
    fi = builder.build(
        uploaded_data=None,
        numerical_inputs={
            "pmi_manufacturing": 50.0,
            "pmi_services": 52.0,
            "cape_ratio": 32.0,
            "sp500_current": 5800.0,
            "payrolls_mom": 200.0,
            "unemployment_rate": 4.0,
            "core_cpi_yoy": 3.0,
            "fed_funds_rate": 4.5,
        },
    )
    assert builder.last_provenance["mode"] == "heuristic_fallback"
    assert "RuntimeError" in builder.last_provenance["fallback_reason"]
    assert set(fi.point_estimates.keys()) == {1, 3, 5, 10}


def test_l10_public_api_signature_preserved() -> None:
    """Gate 8 BINDING: ForecastInputsBuilder.build() signature unchanged."""
    import inspect

    sig = inspect.signature(ForecastInputsBuilder.build)
    param_names = list(sig.parameters.keys())
    # self + the three L10 parameters in the same order.
    assert param_names == ["self", "uploaded_data", "numerical_inputs", "horizons"]
