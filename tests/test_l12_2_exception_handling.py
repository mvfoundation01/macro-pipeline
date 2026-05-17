"""L12 v2 D3 — Tests for /forecast/run exception handling + error.html.

Counts: 5 tests (3 NEG / 2 POS) = 60% NEG.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from macro_pipeline.webapp.app import create_app


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
        "core_cpi_yoy": "2.9",
        "sp500_current": "5800.0",
        "unemployment_rate": "4.1",
        "payrolls_mom": "200",
        "fed_funds_rate": "4.25",
    }


# ----------------------------------------------------------------------
# POS (2 tests)
# ----------------------------------------------------------------------
def test_error_html_template_exists_at_expected_path() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    template = repo_root / "macro_pipeline" / "webapp" / "templates" / "error.html"
    assert template.exists(), "error.html missing — L12 v2 D3 not shipped"
    text = template.read_text(encoding="utf-8")
    # Vietnamese error display + recovery link.
    assert "QUAY LẠI FORM" in text
    assert "{% extends" in text  # uses base.html


def test_internal_error_renders_error_html_with_500(client) -> None:
    """When the aggregator raises, the outer try/except renders error.html
    (status 500) instead of letting Flask emit a tracebacks page."""
    # NB: aggregate_ensemble failures are caught INSIDE _run_impl with a
    # flash+redirect (L10 behavior; gives V a chance to retry the form).
    # The OUTER try/except wrapping _run_impl handles ALL OTHER failure
    # surfaces — e.g. the persistence layer. Patch one of those.
    with patch(
        "macro_pipeline.persistence.ParquetForecastStore.append",
        side_effect=RuntimeError("test injected store failure"),
    ):
        resp = client.post(
            "/forecast/run", data=_good_form(), follow_redirects=False
        )
    assert resp.status_code == 500
    body = resp.data.decode("utf-8")
    assert "QUAY LẠI FORM" in body  # error.html template rendered
    assert "Internal Error" in body
    assert "test injected store failure" in body
    assert "RuntimeError" in body


# ----------------------------------------------------------------------
# NEG (3 tests)
# ----------------------------------------------------------------------
def test_validation_error_still_redirects_to_home_with_flash(client) -> None:
    """Pre-existing validation errors (missing/non-numeric form field) must
    still redirect to /, NOT fall through to error.html (so V can fix the
    input without leaving the form context)."""
    data = _good_form()
    data["pmi_manufacturing"] = "not-a-number"
    resp = client.post("/forecast/run", data=data, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers.get("Location", "").endswith("/")


def test_arbitrary_unhandled_exception_lands_at_error_page(client) -> None:
    """ANY unhandled exception (not just aggregator) must hit error.html.
    Patch ParquetForecastStore.append — a downstream step."""
    with patch(
        "macro_pipeline.persistence.ParquetForecastStore.append",
        side_effect=OSError("disk full"),
    ):
        resp = client.post(
            "/forecast/run", data=_good_form(), follow_redirects=False
        )
    assert resp.status_code == 500
    body = resp.data.decode("utf-8")
    assert "disk full" in body
    assert "OSError" in body


def test_error_page_response_has_html_content_type(client) -> None:
    """Error response MUST be HTML — a plaintext 500 would break V's browser
    UX (Flask default 500 is text/html anyway; this regression-guards that)."""
    with patch(
        "macro_pipeline.persistence.ParquetForecastStore.append",
        side_effect=ValueError("test"),
    ):
        resp = client.post(
            "/forecast/run", data=_good_form(), follow_redirects=False
        )
    assert resp.status_code == 500
    assert "text/html" in resp.headers.get("Content-Type", "")
