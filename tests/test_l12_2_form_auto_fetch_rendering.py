"""L12 v2 D9+D11 — Tests for the 4-manual + 4-auto form layout.

Counts: 6 tests (2 NEG / 4 POS) = 33% NEG. The validation-heavy NEG
ratio sits in the fetcher + exception files.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from macro_pipeline.webapp.app import create_app
from macro_pipeline.webapp.fred_fetcher import FetchResult

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_HTML = REPO_ROOT / "macro_pipeline" / "webapp" / "templates" / "input.html"


@pytest.fixture
def client(tmp_path):
    app = create_app(
        {
            "UPLOAD_DIR": tmp_path / "uploads",
            "FORECAST_STORE_DIR": tmp_path / "forecasts",
            "WEBAPP_RENDER_DIR": tmp_path / "renders",
        }
    )
    return app.test_client()


# ----------------------------------------------------------------------
# POS — layout + auto-fetch UI states (4 tests)
# ----------------------------------------------------------------------
def test_input_html_has_two_distinct_sections() -> None:
    """L12 v2 D9: form must show 4 manual (2A) AND 4 auto-fetch (2B)."""
    text = INPUT_HTML.read_text(encoding="utf-8")
    assert "2A. CHỈ SỐ MANUAL" in text
    assert "2B. CHỈ SỐ AUTO-FETCH" in text
    # Manual section before auto section.
    assert text.index("2A. CHỈ SỐ MANUAL") < text.index("2B. CHỈ SỐ AUTO-FETCH")


def test_home_renders_auto_fetched_badges_when_values_present(client) -> None:
    """L12 v2 D11: when auto-fetch succeeded, each auto field shows
    "Auto-fetched · cập nhật YYYY-MM-DD" badge instead of the manual fallback."""

    def fake_fred(self):
        return {
            "unemployment_rate": FetchResult(value=4.2, as_of="2026-04-30"),
            "payrolls_mom": FetchResult(value=180.0, as_of="2026-04-01"),
            "fed_funds_rate": FetchResult(value=4.33, as_of="2026-05-01"),
        }

    def fake_yahoo(self):
        return {"sp500_current": FetchResult(value=5800.42, as_of="2026-05-05")}

    with patch(
        "macro_pipeline.webapp.fred_fetcher.FREDFetcher.fetch_all_form_fields",
        fake_fred,
    ), patch(
        "macro_pipeline.webapp.yfinance_fetcher.YahooFetcher.fetch_all_form_fields",
        fake_yahoo,
    ), patch(
        "macro_pipeline.webapp.fred_fetcher.FREDFetcher.available",
        new_callable=lambda: property(lambda self: True),
    ):
        resp = client.get("/")
    body = resp.data.decode("utf-8")
    assert "Auto-fetched · cập nhật 2026-05-05" in body
    assert "FRED · cập nhật 2026-04-30" in body
    assert "FRED PAYEMS Δ · cập nhật 2026-04-01" in body
    assert "5800.42" in body  # SPX value pre-populated as input default


def test_home_renders_manual_fallback_when_fred_key_missing(client) -> None:
    """L12 v2 D11: no FRED key → "FRED không khả dụng · nhập manual" badge
    + the empty-state warning callout."""

    def fake_fred_empty(self):
        return {
            "unemployment_rate": FetchResult.empty(),
            "payrolls_mom": FetchResult.empty(),
            "fed_funds_rate": FetchResult.empty(),
        }

    with patch(
        "macro_pipeline.webapp.fred_fetcher.FREDFetcher.fetch_all_form_fields",
        fake_fred_empty,
    ), patch(
        "macro_pipeline.webapp.yfinance_fetcher.YahooFetcher.fetch_all_form_fields",
        lambda self: {"sp500_current": FetchResult.empty()},
    ), patch(
        "macro_pipeline.webapp.fred_fetcher.FREDFetcher.available",
        new_callable=lambda: property(lambda self: False),
    ):
        resp = client.get("/")
    body = resp.data.decode("utf-8")
    assert "FRED_API_KEY chưa được set" in body
    assert "FRED không khả dụng · nhập manual" in body


def test_post_with_4_manual_and_4_blank_uses_auto_fetch_fallback(client) -> None:
    """L12 v2 D9 backend: a POST with 4 manual fields populated + 4 auto
    fields blank must trigger the auto-fetch fallback inside
    ``_fill_auto_fetch_defaults`` and successfully build a ForecastInputs."""

    def fake_fred(self):
        return {
            "unemployment_rate": FetchResult(value=4.2, as_of="2026-04-30"),
            "payrolls_mom": FetchResult(value=180.0, as_of="2026-04-01"),
            "fed_funds_rate": FetchResult(value=4.33, as_of="2026-05-01"),
        }

    with patch(
        "macro_pipeline.webapp.fred_fetcher.FREDFetcher.fetch_all_form_fields",
        fake_fred,
    ), patch(
        "macro_pipeline.webapp.yfinance_fetcher.YahooFetcher.fetch_all_form_fields",
        lambda self: {"sp500_current": FetchResult(value=5800.0, as_of="2026-05-05")},
    ), patch(
        "macro_pipeline.webapp.fred_fetcher.FREDFetcher.available",
        new_callable=lambda: property(lambda self: True),
    ):
        data = {
            "pmi_manufacturing": "51.0",
            "pmi_services": "53.0",
            "cape_ratio": "30.0",
            "core_cpi_yoy": "2.9",
            "sp500_current": "",   # ← auto-fetch must fill
            "payrolls_mom": "",    # ← auto-fetch must fill
            "unemployment_rate": "",
            "fed_funds_rate": "",
        }
        resp = client.post("/forecast/run", data=data, follow_redirects=False)
    # 302 to /results/ means the auto-fetched defaults satisfied validation.
    assert resp.status_code == 302
    assert "/results/" in resp.headers.get("Location", "")


# ----------------------------------------------------------------------
# NEG (2 tests)
# ----------------------------------------------------------------------
def test_post_with_blank_auto_fields_and_no_fred_falls_through_to_validation_error(
    client,
) -> None:
    """When auto-fetch can't fill (no key + no Yahoo), validation rejects
    the blank required fields and we redirect home — NOT crash."""
    with patch(
        "macro_pipeline.webapp.fred_fetcher.FREDFetcher.fetch_all_form_fields",
        lambda self: {k: FetchResult.empty() for k in
                      ("unemployment_rate", "payrolls_mom", "fed_funds_rate")},
    ), patch(
        "macro_pipeline.webapp.yfinance_fetcher.YahooFetcher.fetch_all_form_fields",
        lambda self: {"sp500_current": FetchResult.empty()},
    ):
        data = {
            "pmi_manufacturing": "51.0", "pmi_services": "53.0",
            "cape_ratio": "30.0", "core_cpi_yoy": "2.9",
            "sp500_current": "", "payrolls_mom": "",
            "unemployment_rate": "", "fed_funds_rate": "",
        }
        resp = client.post("/forecast/run", data=data, follow_redirects=False)
    assert resp.status_code == 302  # flash + redirect home, not 500
    assert resp.headers.get("Location", "").endswith("/")


def test_input_html_warns_when_fred_key_missing_with_setup_link(client) -> None:
    """The "set FRED_API_KEY" callout must include the FRED registration link
    so V knows how to fix the empty state."""
    with patch(
        "macro_pipeline.webapp.fred_fetcher.FREDFetcher.available",
        new_callable=lambda: property(lambda self: False),
    ), patch(
        "macro_pipeline.webapp.fred_fetcher.FREDFetcher.fetch_all_form_fields",
        lambda self: {k: FetchResult.empty() for k in
                      ("unemployment_rate", "payrolls_mom", "fed_funds_rate")},
    ), patch(
        "macro_pipeline.webapp.yfinance_fetcher.YahooFetcher.fetch_all_form_fields",
        lambda self: {"sp500_current": FetchResult.empty()},
    ):
        resp = client.get("/")
    body = resp.data.decode("utf-8")
    assert "fred.stlouisfed.org/docs/api/api_key.html" in body
    assert ".env" in body
