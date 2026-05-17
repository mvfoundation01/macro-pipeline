"""L8 D1 tests — UI renderer + config + filters."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from macro_pipeline.persistence import ForecastRecord, ParquetForecastStore
from macro_pipeline.ui.renderer import (
    ForecastUIRenderer,
    UIConfig,
    _bps_filter,
    _num_filter,
    _pct_filter,
    _signed_class_filter,
)


REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_DIR = REPO_ROOT / "macro_pipeline" / "ui" / "templates"
STATIC_DIR = REPO_ROOT / "macro_pipeline" / "ui" / "static"


def _make_record(**overrides) -> ForecastRecord:
    base = dict(
        forecast_id="f-001",
        timestamp_utc=datetime.now(timezone.utc),
        horizon=1,
        point_estimate_annualized=0.07,
        sigma_annualized=0.15,
        confidence=0.7,
        conviction=5.5,
        code_sha="abc123def456",
        metadata_json='{"foo": 1.0}',
    )
    base.update(overrides)
    return ForecastRecord(**base)


# ===========================================================================
# Filters
# ===========================================================================


def test_pct_filter_basic() -> None:
    """POS: format positive return as percent."""
    assert _pct_filter(0.07) == "+7.00%"


def test_pct_filter_negative() -> None:
    """POS: format negative return."""
    assert _pct_filter(-0.05) == "-5.00%"


def test_pct_filter_nan_returns_na() -> None:
    """POS: NaN returns 'N/A' (safe)."""
    assert _pct_filter(float("nan")) == "N/A"


def test_pct_filter_none_returns_na() -> None:
    """POS: None returns 'N/A' (safe)."""
    assert _pct_filter(None) == "N/A"


def test_bps_filter_basic() -> None:
    """POS: format bps with sign."""
    assert _bps_filter(-150.0) == "-150 bps"


def test_bps_filter_nan_returns_na() -> None:
    """POS: NaN returns 'N/A'."""
    assert _bps_filter(float("inf")) == "N/A"


def test_num_filter_default_digits() -> None:
    """POS: format number with default 2 digits."""
    assert _num_filter(5.5) == "5.50"


def test_num_filter_custom_digits() -> None:
    """POS: format with custom digit count."""
    assert _num_filter(5.12345, 3) == "5.123"


def test_num_filter_thousands_separator() -> None:
    """POS: format includes comma thousands separator."""
    assert _num_filter(1234.5) == "1,234.50"


def test_num_filter_none_returns_na() -> None:
    """POS: None returns 'N/A'."""
    assert _num_filter(None) == "N/A"


def test_signed_class_filter_positive() -> None:
    """POS: positive → 'bullish'."""
    assert _signed_class_filter(0.05) == "bullish"


def test_signed_class_filter_negative() -> None:
    """POS: negative → 'bearish'."""
    assert _signed_class_filter(-0.03) == "bearish"


def test_signed_class_filter_zero() -> None:
    """POS: zero → 'neutral'."""
    assert _signed_class_filter(0.0) == "neutral"


def test_signed_class_filter_nan() -> None:
    """POS: NaN → 'neutral'."""
    assert _signed_class_filter(float("nan")) == "neutral"


# ===========================================================================
# UIConfig
# ===========================================================================


def test_ui_config_valid(tmp_path: Path) -> None:
    """POS: valid UIConfig."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    cfg = UIConfig(
        template_dir=TEMPLATE_DIR,
        static_dir=STATIC_DIR,
        output_dir=tmp_path / "out",
        persistence_store=store,
    )
    assert cfg.template_dir == TEMPLATE_DIR


def test_ui_config_missing_template_dir_raises(tmp_path: Path) -> None:
    """NEG: missing template_dir raises."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    with pytest.raises(ValueError, match="template_dir"):
        UIConfig(
            template_dir=Path("/nonexistent"),
            static_dir=STATIC_DIR,
            output_dir=tmp_path / "out",
            persistence_store=store,
        )


def test_ui_config_non_path_template_dir_raises(tmp_path: Path) -> None:
    """NEG: non-Path template_dir raises TypeError."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    with pytest.raises(TypeError, match="template_dir"):
        UIConfig(
            template_dir="/tmp",  # type: ignore[arg-type]
            static_dir=STATIC_DIR,
            output_dir=tmp_path / "out",
            persistence_store=store,
        )


def test_ui_config_non_store_persistence_raises(tmp_path: Path) -> None:
    """NEG: non-ParquetForecastStore raises."""
    with pytest.raises(TypeError, match="persistence_store"):
        UIConfig(
            template_dir=TEMPLATE_DIR,
            static_dir=STATIC_DIR,
            output_dir=tmp_path / "out",
            persistence_store="not a store",  # type: ignore[arg-type]
        )


# ===========================================================================
# Renderer
# ===========================================================================


def test_renderer_initializes(tmp_path: Path) -> None:
    """POS: renderer initializes."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    cfg = UIConfig(
        template_dir=TEMPLATE_DIR,
        static_dir=STATIC_DIR,
        output_dir=tmp_path / "out",
        persistence_store=store,
    )
    renderer = ForecastUIRenderer(cfg)
    assert renderer.config == cfg


def test_renderer_render_full_report_empty_raises(tmp_path: Path) -> None:
    """NEG: render with no records raises ValueError."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    cfg = UIConfig(
        template_dir=TEMPLATE_DIR,
        static_dir=STATIC_DIR,
        output_dir=tmp_path / "out",
        persistence_store=store,
    )
    renderer = ForecastUIRenderer(cfg)
    with pytest.raises(ValueError, match="No records"):
        renderer.render_full_report("2099-12")


def test_renderer_render_full_report_creates_files(tmp_path: Path) -> None:
    """POS-inv: render creates all expected files."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    # Use a fixed timestamp so partition is deterministic.
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
    output_path = renderer.render_full_report("2026-05")
    assert output_path.exists()
    expected_pages = [
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
    for page in expected_pages:
        assert (output_path / page).exists(), f"missing page {page}"
    # Static assets copied.
    assert (output_path / "static" / "css" / "terminal.css").exists()
    assert (output_path / "static" / "js" / "progressive_disclosure.js").exists()


def test_renderer_html_contains_horizons(tmp_path: Path) -> None:
    """POS-inv: forecast_results.html includes all rendered horizons."""
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
    output_path = renderer.render_full_report("2026-05")
    html = (output_path / "forecast_results.html").read_text(encoding="utf-8")
    for h in (1, 3, 5, 10):
        assert f"{h}Y" in html, f"horizon {h}Y missing from forecast_results.html"


def test_renderer_html_valid_xss_safe(tmp_path: Path) -> None:
    """POS-inv: autoescape protects against XSS in forecast_id."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    fixed_ts = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)
    malicious = _make_record(
        forecast_id="<script>alert('xss')</script>",
        timestamp_utc=fixed_ts,
    )
    store.append([malicious])
    cfg = UIConfig(
        template_dir=TEMPLATE_DIR,
        static_dir=STATIC_DIR,
        output_dir=tmp_path / "out",
        persistence_store=store,
    )
    renderer = ForecastUIRenderer(cfg)
    output_path = renderer.render_full_report("2026-05")
    # Index page (and any page that surfaces records) should escape.
    for page in ("index.html", "forecast_results.html"):
        html = (output_path / page).read_text(encoding="utf-8")
        # Raw <script> tag from forecast_id must NOT appear literally.
        assert "<script>alert" not in html
