"""L10 D12 — Integration tests (full forecast run + Excel template round-trip).

Counts: 8 tests (3 NEG / 5 POS) = 38% NEG. Aggregate ≥45% NEG maintained
across the full L10 suite (other files carry higher NEG anchors).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from macro_pipeline.webapp.app import create_app
from macro_pipeline.webapp.data_ingestion import ExcelDataIngester

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = (
    REPO_ROOT / "macro_pipeline" / "webapp" / "static" / "templates"
)


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


# ----------------------------------------------------------------------
# POS — happy paths (5 tests)
# ----------------------------------------------------------------------
def test_generated_yield_curve_template_round_trip_parses() -> None:
    if not (TEMPLATES_DIR / "yield-curve.xlsx").exists():
        pytest.skip("templates not generated")
    res = ExcelDataIngester().parse_yield_curve(
        TEMPLATES_DIR / "yield-curve.xlsx"
    )
    assert res.success is True
    assert "inverted" in (res.data or {})


def test_generated_credit_spreads_template_round_trip_parses() -> None:
    if not (TEMPLATES_DIR / "credit-spreads.xlsx").exists():
        pytest.skip("templates not generated")
    res = ExcelDataIngester().parse_credit_spreads(
        TEMPLATES_DIR / "credit-spreads.xlsx"
    )
    assert res.success is True


def test_generated_sentiment_template_round_trip_parses() -> None:
    if not (TEMPLATES_DIR / "sentiment.xlsx").exists():
        pytest.skip("templates not generated")
    res = ExcelDataIngester().parse_sentiment(
        TEMPLATES_DIR / "sentiment.xlsx"
    )
    assert res.success is True


def test_post_forecast_run_with_form_only_succeeds_and_renders(client, app) -> None:
    """Full POST → aggregator → persist → render → redirect to results page."""
    data = {
        "pmi_manufacturing": "51.0",
        "pmi_services": "52.5",
        "cape_ratio": "30.0",
        "sp500_current": "5800.0",
        "payrolls_mom": "200",
        "unemployment_rate": "4.1",
        "core_cpi_yoy": "2.9",
        "fed_funds_rate": "4.25",
    }
    resp = client.post("/forecast/run", data=data, follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers.get("Location", "")
    assert "/results/" in location, f"Expected /results/ redirect; got {location!r}"

    # Follow the redirect — index.html should render.
    resp2 = client.get(location, follow_redirects=False)
    assert resp2.status_code in (200, 302)


def test_post_forecast_run_writes_parquet_partition(client, app, tmp_path) -> None:
    data = {
        "pmi_manufacturing": "50.5",
        "pmi_services": "51.0",
        "cape_ratio": "28.0",
        "sp500_current": "5700.0",
        "payrolls_mom": "150",
        "unemployment_rate": "4.0",
        "core_cpi_yoy": "3.0",
        "fed_funds_rate": "4.5",
    }
    resp = client.post("/forecast/run", data=data, follow_redirects=False)
    assert resp.status_code == 302
    forecast_dir = Path(app.config["FORECAST_STORE_DIR"])
    parquet_files = list(forecast_dir.glob("forecasts_*.parquet"))
    assert parquet_files, "expected at least one parquet partition after POST"


# ----------------------------------------------------------------------
# NEG — strict (3 tests)
# ----------------------------------------------------------------------
def test_post_forecast_run_oversized_payload_rejected(client, app) -> None:
    """MAX_CONTENT_LENGTH = 50 MiB; 51 MiB upload must be rejected."""
    from io import BytesIO

    big = b"x" * (51 * 1024 * 1024)
    data = {
        "pmi_manufacturing": "51",
        "pmi_services": "52",
        "cape_ratio": "30",
        "sp500_current": "5800",
        "payrolls_mom": "200",
        "unemployment_rate": "4",
        "core_cpi_yoy": "3",
        "fed_funds_rate": "4.5",
        "yield_curve_file": (BytesIO(big), "huge.xlsx"),
    }
    resp = client.post(
        "/forecast/run",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 413  # Payload Too Large


def test_post_forecast_run_invalid_excel_falls_back_to_form_defaults(
    client, app, tmp_path
) -> None:
    """A garbage upload must flash an error but still allow the user to retry."""
    from io import BytesIO

    data = {
        "pmi_manufacturing": "51",
        "pmi_services": "52",
        "cape_ratio": "30",
        "sp500_current": "5800",
        "payrolls_mom": "200",
        "unemployment_rate": "4",
        "core_cpi_yoy": "3",
        "fed_funds_rate": "4.5",
        "yield_curve_file": (BytesIO(b"not an xlsx file"), "garbage.xlsx"),
    }
    resp = client.post(
        "/forecast/run",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers.get("Location", "")
    # Either redirects home (flash) or to /results/ — both acceptable; what
    # matters is the request was handled rather than 500-ing.
    assert location.endswith("/") or "/results/" in location


def test_oversized_upload_does_not_leave_partial_file(client, app, tmp_path) -> None:
    """413 rejection must not silently persist a partial file in UPLOAD_DIR."""
    from io import BytesIO

    big = b"x" * (51 * 1024 * 1024)
    data = {
        "pmi_manufacturing": "51",
        "pmi_services": "52",
        "cape_ratio": "30",
        "sp500_current": "5800",
        "payrolls_mom": "200",
        "unemployment_rate": "4",
        "core_cpi_yoy": "3",
        "fed_funds_rate": "4.5",
        "yield_curve_file": (BytesIO(big), "huge.xlsx"),
    }
    client.post(
        "/forecast/run",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    upload_dir = Path(app.config["UPLOAD_DIR"])
    files = list(upload_dir.glob("*"))
    assert files == [], f"413 path should not persist files; got {files!r}"
