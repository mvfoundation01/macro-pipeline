"""L8 D2-D7 tests — template rendering verification via BeautifulSoup."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from macro_pipeline.persistence import ForecastRecord, ParquetForecastStore
from macro_pipeline.ui.renderer import ForecastUIRenderer, UIConfig


REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_DIR = REPO_ROOT / "macro_pipeline" / "ui" / "templates"
STATIC_DIR = REPO_ROOT / "macro_pipeline" / "ui" / "static"


def _make_record(**overrides) -> ForecastRecord:
    base = dict(
        forecast_id="t-001",
        timestamp_utc=datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc),
        horizon=1,
        point_estimate_annualized=0.07,
        sigma_annualized=0.15,
        confidence=0.7,
        conviction=5.5,
        code_sha="abc123def456",
        metadata_json="{}",
    )
    base.update(overrides)
    return ForecastRecord(**base)


@pytest.fixture
def rendered_report(tmp_path: Path) -> Path:
    """Fixture: render a full report with 4 horizons + return output dir."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    fixed_ts = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)
    records = [_make_record(horizon=h, timestamp_utc=fixed_ts) for h in (1, 3, 5, 10)]
    store.append(records)
    cfg = UIConfig(
        template_dir=TEMPLATE_DIR,
        static_dir=STATIC_DIR,
        output_dir=tmp_path / "out",
        persistence_store=store,
    )
    renderer = ForecastUIRenderer(cfg)
    return renderer.render_full_report("2026-05")


# ===========================================================================
# Template structure verification (parse via BS4)
# ===========================================================================


def test_index_html_has_navigation(rendered_report: Path) -> None:
    """POS: index.html has terminal-nav with all 8 page links."""
    html = (rendered_report / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.find("nav", class_="terminal-nav")
    assert nav is not None
    links = [a.get("href") for a in nav.find_all("a")]
    expected_pages = [
        "forecast_results.html",
        "macro_snapshot.html",
        "scenarios.html",
        "drawdown_risk.html",
        "analogs.html",
        "sector_factor.html",
        "academic/index.html",
        "educational/index.html",
    ]
    for page in expected_pages:
        assert page in links


def test_forecast_results_renders_all_horizons(rendered_report: Path) -> None:
    """POS-inv: forecast_results.html renders rows for all 4 horizons."""
    html = (rendered_report / "forecast_results.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    # First table is the main horizon-results table.
    main_table = soup.find("table", class_="terminal-table")
    assert main_table is not None
    rows = main_table.find("tbody").find_all("tr")
    assert len(rows) == 4  # 4 horizons


def test_forecast_results_has_conviction_bar(rendered_report: Path) -> None:
    """POS: conviction visualization bar rendered."""
    html = (rendered_report / "forecast_results.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    bars = soup.find_all("span", class_="conviction-bar")
    assert len(bars) >= 4  # one per horizon


def test_macro_snapshot_has_lucas_block(rendered_report: Path) -> None:
    """POS: macro_snapshot.html includes Lucas critique block."""
    html = (rendered_report / "macro_snapshot.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    titles = [
        tag.get_text() for tag in soup.find_all(class_="data-block-title")
    ]
    has_lucas = any("LUCAS" in t.upper() for t in titles)
    assert has_lucas


def test_scenarios_has_5_bucket_columns(rendered_report: Path) -> None:
    """POS: scenarios.html table has bull/base/bear/tail/OOD columns."""
    html = (rendered_report / "scenarios.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    headers = soup.find_all("th")
    header_texts = [h.get_text().upper() for h in headers]
    assert any("BULL" in t for t in header_texts)
    assert any("BASE" in t for t in header_texts)
    assert any("BEAR" in t for t in header_texts)
    assert any("TAIL" in t for t in header_texts)
    assert any("OOD" in t for t in header_texts)


def test_drawdown_risk_has_dd_columns(rendered_report: Path) -> None:
    """POS: drawdown_risk.html includes drawdown percentage columns."""
    html = (rendered_report / "drawdown_risk.html").read_text(encoding="utf-8")
    assert "DD &gt; 10%" in html or "P(DD" in html
    assert "VAR" in html.upper()


def test_analogs_has_rcf_metrics(rendered_report: Path) -> None:
    """POS: analogs.html surfaces RCF top-k metrics."""
    html = (rendered_report / "analogs.html").read_text(encoding="utf-8")
    assert "RCF MEAN SIM" in html.upper() or "TOP-K" in html.upper()


def test_sector_factor_has_placeholder_status(rendered_report: Path) -> None:
    """POS: sector_factor.html shows placeholder status (pre-staged surface)."""
    html = (rendered_report / "sector_factor.html").read_text(encoding="utf-8")
    assert "PLACEHOLDER" in html.upper() or "PRE-STAGED" in html.upper()


def test_academic_has_replication_kit_button(rendered_report: Path) -> None:
    """POS: academic/index.html has download button."""
    html = (rendered_report / "academic" / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    download = soup.find(class_="download-button")
    assert download is not None


def test_academic_has_lineage_summary(rendered_report: Path) -> None:
    """POS: academic page has lineage summary with 90 total."""
    html = (rendered_report / "academic" / "index.html").read_text(encoding="utf-8")
    assert "Vision &sect;3 BINDING" in html or "90-measurement" in html


def test_educational_has_progressive_disclosure_toggles(rendered_report: Path) -> None:
    """POS: educational/index.html has explanation-toggle spans."""
    html = (rendered_report / "educational" / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    toggles = soup.find_all(class_="explanation-toggle")
    assert len(toggles) >= 4  # multiple metric blocks have toggles


def test_educational_has_explanation_blocks(rendered_report: Path) -> None:
    """POS: educational page has explanation-block divs."""
    html = (rendered_report / "educational" / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.find_all(class_="explanation-block")
    assert len(blocks) >= 5  # multiple metrics covered


def test_all_pages_link_to_css(rendered_report: Path) -> None:
    """POS: all rendered pages include link to terminal.css."""
    pages = [
        "index.html",
        "forecast_results.html",
        "macro_snapshot.html",
        "scenarios.html",
        "drawdown_risk.html",
        "analogs.html",
        "sector_factor.html",
        "academic/index.html",
        "educational/index.html",
    ]
    for page in pages:
        html = (rendered_report / page).read_text(encoding="utf-8")
        assert "terminal.css" in html, f"page {page} missing CSS link"
