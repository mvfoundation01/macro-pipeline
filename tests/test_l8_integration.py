"""L8 D10 — end-to-end integration tests.

Wires L7 persistence + L8 UI rendering + L8 replication kit into a
full pipeline E2E test. Verifies the L8 surfaces interact correctly
with L7 outputs.
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from macro_pipeline.persistence import ForecastRecord, ParquetForecastStore
from macro_pipeline.ui import (
    ExplanationLevel,
    ExplanationStack,
    ForecastUIRenderer,
    ReplicationKitBuilder,
    ReplicationKitConfig,
    UIConfig,
)


REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_DIR = REPO_ROOT / "macro_pipeline" / "ui" / "templates"
STATIC_DIR = REPO_ROOT / "macro_pipeline" / "ui" / "static"
EXPLANATIONS_YAML = (
    REPO_ROOT / "macro_pipeline" / "ui" / "data" / "explanations.yaml"
)


def _make_record(**overrides) -> ForecastRecord:
    base = dict(
        forecast_id="e2e-001",
        timestamp_utc=datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc),
        horizon=1,
        point_estimate_annualized=0.07,
        sigma_annualized=0.15,
        confidence=0.7,
        conviction=5.5,
        code_sha="abc123",
        metadata_json='{"foo": 1.0}',
    )
    base.update(overrides)
    return ForecastRecord(**base)


def test_e2e_persistence_to_ui_rendering(tmp_path: Path) -> None:
    """E2E: write records to parquet, render full HTML report, verify outputs."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    fixed_ts = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)
    records = [_make_record(horizon=h, timestamp_utc=fixed_ts) for h in (1, 3, 5, 10)]
    store.append(records)

    cfg = UIConfig(
        template_dir=TEMPLATE_DIR,
        static_dir=STATIC_DIR,
        output_dir=tmp_path / "reports",
        persistence_store=store,
    )
    renderer = ForecastUIRenderer(cfg)
    output_path = renderer.render_full_report("2026-05")
    assert (output_path / "index.html").exists()
    assert (output_path / "forecast_results.html").exists()


def test_e2e_replication_kit_from_persisted_records(tmp_path: Path) -> None:
    """E2E: persist records, then generate replication kit from them."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    fixed_ts = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)
    records = [_make_record(horizon=h, timestamp_utc=fixed_ts) for h in (1, 3, 5, 10)]
    store.append(records)
    read_back = store.read("2026-05")
    assert len(read_back) == 4

    builder = ReplicationKitBuilder()
    cfg = ReplicationKitConfig(output_dir=tmp_path / "kits")
    zip_path = builder.build(read_back, cfg)
    assert zip_path.exists()

    # Verify zip contents.
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("forecast_records.json") as f:
            data = json.loads(f.read())
    assert len(data) == 4


def test_e2e_explanation_stack_loads_all_layers(tmp_path: Path) -> None:
    """E2E: explanation stack loads from repo yaml + queries successfully."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    # Key metric coverage spot-check.
    for metric_id in (
        "confidence_score",
        "conviction_score",
        "reference_class_ood",
        "lucas_critique_flag",
    ):
        for lvl in ExplanationLevel:
            exp = stack.get(metric_id, lvl)
            assert exp is not None, f"missing {metric_id} {lvl}"


def test_e2e_rendered_html_renders_explanation_stack(tmp_path: Path) -> None:
    """E2E: rendered educational page contains explanation-toggle elements."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    fixed_ts = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)
    records = [_make_record(horizon=h, timestamp_utc=fixed_ts) for h in (1, 3, 5, 10)]
    store.append(records)
    cfg = UIConfig(
        template_dir=TEMPLATE_DIR,
        static_dir=STATIC_DIR,
        output_dir=tmp_path / "reports",
        persistence_store=store,
    )
    renderer = ForecastUIRenderer(cfg)
    output_path = renderer.render_full_report("2026-05")
    html = (output_path / "educational" / "index.html").read_text(encoding="utf-8")
    assert "explanation-toggle" in html
    assert "progressive_disclosure.js" in html


def test_e2e_static_assets_present(tmp_path: Path) -> None:
    """E2E: rendered report includes copied static CSS + JS."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    fixed_ts = datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)
    store.append([_make_record(timestamp_utc=fixed_ts)])
    cfg = UIConfig(
        template_dir=TEMPLATE_DIR,
        static_dir=STATIC_DIR,
        output_dir=tmp_path / "reports",
        persistence_store=store,
    )
    renderer = ForecastUIRenderer(cfg)
    output_path = renderer.render_full_report("2026-05")
    assert (output_path / "static" / "css" / "terminal.css").exists()
    assert (output_path / "static" / "js" / "progressive_disclosure.js").exists()


def test_e2e_missing_partition_raises_helpful_error(tmp_path: Path) -> None:
    """NEG E2E: requesting unrendered partition raises ValueError."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    cfg = UIConfig(
        template_dir=TEMPLATE_DIR,
        static_dir=STATIC_DIR,
        output_dir=tmp_path / "reports",
        persistence_store=store,
    )
    renderer = ForecastUIRenderer(cfg)
    with pytest.raises(ValueError, match="No records"):
        renderer.render_full_report("2099-12")
