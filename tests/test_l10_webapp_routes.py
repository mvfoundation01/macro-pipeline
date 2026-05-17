"""L10 D12 — Tests for Flask blueprints (home / forecast / results / help).

PD18 strict ≥40% NEG on validation paths.
Counts: 14 tests (7 NEG / 7 POS) = 50% NEG.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from macro_pipeline.webapp.app import create_app


@pytest.fixture
def app(tmp_path):
    """Return a Flask app with isolated tmp dirs (no /data side-effects)."""
    return create_app(
        {
            "UPLOAD_DIR": tmp_path / "uploads",
            "FORECAST_STORE_DIR": tmp_path / "forecasts",
            "WEBAPP_RENDER_DIR": tmp_path / "renders",
            "TESTING": True,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


# ----------------------------------------------------------------------
# POS — happy paths (7 tests)
# ----------------------------------------------------------------------
def test_app_factory_returns_flask_instance() -> None:
    app = create_app()
    from flask import Flask

    assert isinstance(app, Flask)


def test_app_registers_all_four_blueprints() -> None:
    app = create_app()
    assert set(app.blueprints.keys()) == {"home", "forecast", "results", "help"}


def test_get_home_returns_input_form(client) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "CHẠY FORECAST" in body
    assert "pmi_manufacturing" in body


def test_get_help_renders_vietnamese_guide(client) -> None:
    resp = client.get("/help/")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "HƯỚNG DẪN" in body


def test_get_template_yield_curve_serves_xlsx(client) -> None:
    """Excel templates must be pre-generated (CI: generate_excel_templates.py)."""
    repo_root = Path(__file__).parent.parent
    template_path = (
        repo_root
        / "macro_pipeline"
        / "webapp"
        / "static"
        / "templates"
        / "yield-curve.xlsx"
    )
    if not template_path.exists():
        pytest.skip("Excel templates not generated; run scripts/generate_excel_templates.py")
    resp = client.get("/forecast/template/yield-curve")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"].startswith(
        "application/vnd.openxmlformats"
    ) or resp.headers["Content-Type"].startswith("application/octet-stream")


def test_results_latest_redirects_to_home_when_empty(client) -> None:
    resp = client.get("/results/latest", follow_redirects=False)
    assert resp.status_code == 302
    assert "/" in resp.headers.get("Location", "")


def test_base_template_has_vietnamese_navigation(client) -> None:
    resp = client.get("/")
    body = resp.data.decode("utf-8")
    assert "Trang chủ" in body
    assert "Hướng dẫn" in body
    assert "Kết quả mới nhất" in body


# ----------------------------------------------------------------------
# NEG — validation rejections (7 tests)
# ----------------------------------------------------------------------
def test_post_forecast_run_missing_field_redirects_with_flash(client) -> None:
    # Missing all 8 numerical fields → first field check fails → redirect.
    resp = client.post("/forecast/run", data={}, follow_redirects=False)
    assert resp.status_code == 302


def test_post_forecast_run_non_numeric_value_redirects(client) -> None:
    data = {
        "pmi_manufacturing": "not-a-number",
        "pmi_services": "52",
        "cape_ratio": "30",
        "sp500_current": "5800",
        "payrolls_mom": "200",
        "unemployment_rate": "4",
        "core_cpi_yoy": "3",
        "fed_funds_rate": "4.5",
    }
    resp = client.post("/forecast/run", data=data, follow_redirects=False)
    assert resp.status_code == 302  # flash + redirect


def test_get_unknown_template_returns_404(client) -> None:
    resp = client.get("/forecast/template/does-not-exist")
    assert resp.status_code == 404


def test_get_results_bad_partition_returns_404(client) -> None:
    resp = client.get("/results/bad-partition-name")
    assert resp.status_code == 404


def test_get_results_partition_path_traversal_blocked(client) -> None:
    """Path-traversal must be rejected by partition regex."""
    resp = client.get("/results/..%2F..%2Fetc")
    assert resp.status_code == 404


def test_get_results_missing_partition_returns_404(client) -> None:
    resp = client.get("/results/2099-01")
    assert resp.status_code == 404


def test_get_results_asset_for_missing_partition_returns_404(client) -> None:
    resp = client.get("/results/2099-01/index.html")
    assert resp.status_code == 404
