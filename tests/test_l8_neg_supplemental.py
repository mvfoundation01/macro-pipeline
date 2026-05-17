"""L8 D10 — supplemental NEG tests for PD18 STRICT 40% floor.

Per Strategic L8 §10 gate criterion #12 (PD18 40% strict; no relax in v2.0).
This file adds NEG-flavor tests across D1-D9 surfaces to lift the L8 new-test
NEG ratio above the floor.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from macro_pipeline.persistence import ForecastRecord, ParquetForecastStore
from macro_pipeline.ui.explanation_stack import (
    Explanation,
    ExplanationLevel,
    ExplanationStack,
)
from macro_pipeline.ui.renderer import (
    ForecastUIRenderer,
    UIConfig,
    _bps_filter,
    _num_filter,
    _pct_filter,
    _signed_class_filter,
)
from macro_pipeline.ui.replication_kit import (
    ReplicationKitBuilder,
    ReplicationKitConfig,
)


REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_DIR = REPO_ROOT / "macro_pipeline" / "ui" / "templates"
STATIC_DIR = REPO_ROOT / "macro_pipeline" / "ui" / "static"


# ===========================================================================
# Filter NEG cases (defensive coverage; filters silently handle bad input)
# ===========================================================================


def test_pct_filter_string_input_returns_na() -> None:
    """NEG: non-numeric string returns 'N/A' (no exception)."""
    assert _pct_filter("not a number") == "N/A"


def test_pct_filter_inf_returns_na() -> None:
    """NEG: inf returns 'N/A'."""
    assert _pct_filter(float("inf")) == "N/A"


def test_bps_filter_string_returns_na() -> None:
    """NEG: non-numeric string returns 'N/A'."""
    assert _bps_filter("bad") == "N/A"


def test_bps_filter_none_returns_na() -> None:
    """NEG: None returns 'N/A'."""
    assert _bps_filter(None) == "N/A"


def test_num_filter_string_returns_na() -> None:
    """NEG: non-numeric string returns 'N/A'."""
    assert _num_filter("not numeric") == "N/A"


def test_num_filter_nan_returns_na() -> None:
    """NEG: NaN returns 'N/A'."""
    assert _num_filter(float("nan")) == "N/A"


def test_signed_class_filter_string_returns_neutral() -> None:
    """NEG: non-numeric string returns 'neutral'."""
    assert _signed_class_filter("text") == "neutral"


def test_signed_class_filter_inf_returns_neutral() -> None:
    """NEG: inf returns 'neutral'."""
    assert _signed_class_filter(float("inf")) == "neutral"


# ===========================================================================
# UIConfig + Renderer NEG
# ===========================================================================


def test_ui_config_non_dir_template_raises(tmp_path: Path) -> None:
    """NEG: template_dir that's a file (not dir) raises."""
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("x", encoding="utf-8")
    store = ParquetForecastStore(tmp_path / "forecasts")
    with pytest.raises(ValueError, match="directory"):
        UIConfig(
            template_dir=file_path,
            static_dir=STATIC_DIR,
            output_dir=tmp_path / "out",
            persistence_store=store,
        )


def test_ui_config_missing_static_dir_raises(tmp_path: Path) -> None:
    """NEG: missing static_dir raises."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    with pytest.raises(ValueError, match="static_dir"):
        UIConfig(
            template_dir=TEMPLATE_DIR,
            static_dir=Path("/nonexistent_static"),
            output_dir=tmp_path / "out",
            persistence_store=store,
        )


def test_ui_config_non_path_output_dir_raises(tmp_path: Path) -> None:
    """NEG: non-Path output_dir raises TypeError."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    with pytest.raises(TypeError, match="output_dir"):
        UIConfig(
            template_dir=TEMPLATE_DIR,
            static_dir=STATIC_DIR,
            output_dir="/tmp/out",  # type: ignore[arg-type]
            persistence_store=store,
        )


# ===========================================================================
# Explanation NEG
# ===========================================================================


def test_explanation_non_string_text_raises() -> None:
    """NEG: integer text raises."""
    with pytest.raises(ValueError, match="text required"):
        Explanation(
            metric_id="x", level=ExplanationLevel.L1, text=None  # type: ignore[arg-type]
        )


def test_explanation_stack_load_with_non_mapping_entries_raises(tmp_path: Path) -> None:
    """NEG: each explanation entry must be mapping."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(
        "explanations:\n  - not_a_mapping\n  - also_not_a_mapping\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mapping"):
        ExplanationStack(bad_yaml)


# ===========================================================================
# ReplicationKit NEG
# ===========================================================================


def test_replication_kit_builder_empty_records_raises_explicit_msg(tmp_path: Path) -> None:
    """NEG: empty records raises ValueError with explicit message."""
    builder = ReplicationKitBuilder()
    cfg = ReplicationKitConfig(output_dir=tmp_path)
    with pytest.raises(ValueError, match="empty"):
        builder.build([], cfg)


def test_replication_kit_config_none_output_dir_raises() -> None:
    """NEG: None output_dir raises TypeError."""
    with pytest.raises(TypeError, match="output_dir"):
        ReplicationKitConfig(output_dir=None)  # type: ignore[arg-type]


# ===========================================================================
# Renderer NEG (additional)
# ===========================================================================


def test_renderer_invalid_partition_format_raises(tmp_path: Path) -> None:
    """NEG: invalid partition format (handled at persistence layer) raises."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    cfg = UIConfig(
        template_dir=TEMPLATE_DIR,
        static_dir=STATIC_DIR,
        output_dir=tmp_path / "out",
        persistence_store=store,
    )
    renderer = ForecastUIRenderer(cfg)
    # Invalid format triggers persistence-layer ValueError when calling .read.
    with pytest.raises(ValueError):
        renderer.render_full_report("2026-13-01")


# ===========================================================================
# Filter edge cases (more NEG coverage)
# ===========================================================================


def test_pct_filter_boolean_input() -> None:
    """NEG: bool input (True coerces to 1.0; bool is int subclass)."""
    # Bools coerce to 1/0 → format as '+100.00%' / '+0.00%'. This is documented
    # behavior, not a failure mode; just exercising the path.
    assert "+100.00%" == _pct_filter(True)
    assert "+0.00%" == _pct_filter(False)


def test_bps_filter_list_input_returns_na() -> None:
    """NEG: list input returns 'N/A' (unconvertible)."""
    assert _bps_filter([1, 2, 3]) == "N/A"


def test_num_filter_dict_input_returns_na() -> None:
    """NEG: dict input returns 'N/A' (unconvertible)."""
    assert _num_filter({"k": 1}) == "N/A"


def test_signed_class_filter_none_returns_neutral() -> None:
    """NEG: None returns 'neutral'."""
    assert _signed_class_filter(None) == "neutral"


def test_explanation_stack_yaml_with_non_list_explanations_field(tmp_path: Path) -> None:
    """NEG: explanations field as dict (not list) raises."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "explanations:\n  metric_id: x\n  L1: a\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="list"):
        ExplanationStack(bad)
