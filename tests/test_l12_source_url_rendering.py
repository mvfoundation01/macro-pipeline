"""L12 D10 — Tests for input.html source URL annotations + detected-files panel.

Counts: 4 tests (1 NEG / 3 POS) = 25% NEG. Aggregate L12 NEG ratio stays ≥45%
via the parser + manager files.
"""
from __future__ import annotations

from pathlib import Path

from macro_pipeline.webapp.app import create_app

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_HTML = REPO_ROOT / "macro_pipeline" / "webapp" / "templates" / "input.html"


# ----------------------------------------------------------------------
# POS (3 tests)
# ----------------------------------------------------------------------
def test_input_html_includes_all_8_primary_source_urls() -> None:
    """L12 D8: every numerical field must link to its government / primary
    data source so V can re-fetch the current value with one click."""
    text = INPUT_HTML.read_text(encoding="utf-8")
    required_urls = [
        # PMI Manufacturing
        "ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/pmi/",
        # PMI Services
        "ismworld.org/supply-management-news-and-reports/reports/ism-report-on-business/services/",
        # CAPE Ratio
        "multpl.com/shiller-pe",
        # S&P 500 current
        "finance.yahoo.com/quote/%5EGSPC/",
        # Nonfarm Payrolls MoM
        "fred.stlouisfed.org/series/PAYEMS",
        # Unemployment Rate
        "fred.stlouisfed.org/series/UNRATE",
        # Core CPI YoY
        "fred.stlouisfed.org/series/CPILFESL",
        # Fed Funds Rate
        "fred.stlouisfed.org/series/FEDFUNDS",
    ]
    missing = [u for u in required_urls if u not in text]
    assert not missing, f"input.html missing source URLs: {missing}"


def test_input_html_external_links_have_target_blank_and_noopener() -> None:
    """Source links must open in a new tab AND set rel=noopener (security).

    Counted by ``target="_blank"`` attribute (protocol-agnostic): some primary
    sources are http-only (e.g. the Shiller Yale dataset page), so a strict
    https:// count would under-report.
    """
    text = INPUT_HTML.read_text(encoding="utf-8")
    external_anchor_count = text.count('href="http://') + text.count('href="https://')
    target_blank_count = text.count('target="_blank"')
    noopener_count = text.count('rel="noopener"')
    # 2 sources x 8 fields = 16 external anchors expected.
    assert external_anchor_count >= 16, (
        f"expected >=16 external http(s):// links (2 sources x 8 fields); "
        f"got {external_anchor_count}"
    )
    assert target_blank_count >= 16
    assert noopener_count >= 16


def test_home_route_passes_detected_files_to_template(tmp_path: Path) -> None:
    """L12 D7: home GET / must inject ``detected_files`` + ``local_categories``
    into the template context so V sees what's auto-detected."""
    app = create_app(
        {
            "UPLOAD_DIR": tmp_path / "uploads",
            "FORECAST_STORE_DIR": tmp_path / "forecasts",
            "WEBAPP_RENDER_DIR": tmp_path / "renders",
        }
    )
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    # Detected files panel renders (either with table or empty-state).
    assert "DỮ LIỆU CỤC BỘ" in body
    assert (
        "data/raw/tradingview/" in body
        or "data/raw/official/" in body
    ), "expected raw-data path hint to appear in the panel"


# ----------------------------------------------------------------------
# NEG (1 test)
# ----------------------------------------------------------------------
def test_home_route_does_not_crash_when_raw_dirs_missing(
    tmp_path: Path, monkeypatch
) -> None:
    """If `data/raw/{official,tradingview}` don't exist on V's machine, the
    home page must still render — the scan must silently produce an empty
    classification, not raise."""
    # Patch LocalDataManager to point at nonexistent dirs.
    from macro_pipeline.webapp import local_data_manager

    fake = tmp_path / "no_such_path"
    monkeypatch.setattr(
        local_data_manager.LocalDataManager,
        "DEFAULT_PATHS",
        (fake,),
    )
    app = create_app(
        {
            "UPLOAD_DIR": tmp_path / "uploads",
            "FORECAST_STORE_DIR": tmp_path / "forecasts",
            "WEBAPP_RENDER_DIR": tmp_path / "renders",
        }
    )
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    # The empty-state Vietnamese message must appear.
    assert "Chưa tìm thấy file nào" in body
