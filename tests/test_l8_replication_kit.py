"""L8 D8 tests — replication kit builder."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from macro_pipeline.persistence import ForecastRecord
from macro_pipeline.ui.replication_kit import (
    METHODOLOGY_CITATIONS,
    ReplicationKitBuilder,
    ReplicationKitConfig,
)


def _make_record(**overrides) -> ForecastRecord:
    base = dict(
        forecast_id="rk-001",
        timestamp_utc=datetime.now(timezone.utc),
        horizon=1,
        point_estimate_annualized=0.07,
        sigma_annualized=0.15,
        confidence=0.7,
        conviction=5.5,
        code_sha="abc123",
        metadata_json='{"k": "v"}',
    )
    base.update(overrides)
    return ForecastRecord(**base)


# ===========================================================================
# ReplicationKitConfig
# ===========================================================================


def test_replication_kit_config_valid(tmp_path: Path) -> None:
    """POS: valid config."""
    cfg = ReplicationKitConfig(output_dir=tmp_path)
    assert cfg.include_data_caches is False  # default


def test_replication_kit_config_non_path_raises() -> None:
    """NEG: non-Path output_dir raises TypeError."""
    with pytest.raises(TypeError, match="output_dir"):
        ReplicationKitConfig(output_dir="not a Path")  # type: ignore[arg-type]


def test_replication_kit_config_non_bool_caches_raises(tmp_path: Path) -> None:
    """NEG: non-bool include_data_caches raises."""
    with pytest.raises(TypeError, match="include_data_caches"):
        ReplicationKitConfig(
            output_dir=tmp_path, include_data_caches="yes"  # type: ignore[arg-type]
        )


# ===========================================================================
# ReplicationKitBuilder
# ===========================================================================


def test_builder_creates_zip(tmp_path: Path) -> None:
    """POS-inv: build creates zip file at output_dir."""
    builder = ReplicationKitBuilder()
    cfg = ReplicationKitConfig(output_dir=tmp_path)
    records = [_make_record()]
    zip_path = builder.build(records, cfg)
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"


def test_builder_zip_contains_required_files(tmp_path: Path) -> None:
    """POS-inv: zip contains 4 required files."""
    builder = ReplicationKitBuilder()
    cfg = ReplicationKitConfig(output_dir=tmp_path)
    records = [_make_record()]
    zip_path = builder.build(records, cfg)
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
    assert "forecast_records.json" in names
    assert "methodology_citations.json" in names
    assert "data_lineage.json" in names
    assert "README.md" in names


def test_builder_forecast_records_json_round_trip(tmp_path: Path) -> None:
    """POS-inv: forecast_records.json round-trips."""
    builder = ReplicationKitBuilder()
    cfg = ReplicationKitConfig(output_dir=tmp_path)
    records = [_make_record(forecast_id="abc", horizon=5)]
    zip_path = builder.build(records, cfg)
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("forecast_records.json") as f:
            data = json.loads(f.read())
    assert len(data) == 1
    assert data[0]["forecast_id"] == "abc"
    assert data[0]["horizon"] == 5


def test_builder_lineage_includes_counts(tmp_path: Path) -> None:
    """POS-inv: data_lineage.json includes computed/deferred counts."""
    builder = ReplicationKitBuilder()
    cfg = ReplicationKitConfig(output_dir=tmp_path)
    records = [_make_record()]
    zip_path = builder.build(records, cfg)
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("data_lineage.json") as f:
            lineage = json.loads(f.read())
    assert "n_computed" in lineage
    assert "n_deferred" in lineage
    assert "n_deferred_l7" in lineage
    assert "n_deferred_l8a" in lineage
    assert lineage["total"] == 90  # Vision section 3 BINDING 90-measurement count


def test_builder_lineage_l7_l8a_split_correct(tmp_path: Path) -> None:
    """POS-inv: lineage split matches L6-J D1 audit (40 computed + 36 L7 + 14 L8a)."""
    builder = ReplicationKitBuilder()
    cfg = ReplicationKitConfig(output_dir=tmp_path)
    records = [_make_record()]
    zip_path = builder.build(records, cfg)
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("data_lineage.json") as f:
            lineage = json.loads(f.read())
    assert lineage["n_computed"] == 40
    assert lineage["n_deferred_l7"] == 36
    assert lineage["n_deferred_l8a"] == 14


def test_builder_citations_match_module_constant(tmp_path: Path) -> None:
    """POS: methodology_citations.json matches METHODOLOGY_CITATIONS constant."""
    builder = ReplicationKitBuilder()
    cfg = ReplicationKitConfig(output_dir=tmp_path)
    records = [_make_record()]
    zip_path = builder.build(records, cfg)
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("methodology_citations.json") as f:
            citations = json.loads(f.read())
    assert citations == METHODOLOGY_CITATIONS


def test_builder_readme_includes_code_sha(tmp_path: Path) -> None:
    """POS: README includes the code SHA from records for replication."""
    builder = ReplicationKitBuilder()
    cfg = ReplicationKitConfig(output_dir=tmp_path)
    records = [_make_record(code_sha="deadbeef12345")]
    zip_path = builder.build(records, cfg)
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("README.md") as f:
            readme = f.read().decode("utf-8")
    assert "deadbeef12345" in readme


def test_builder_empty_records_raises(tmp_path: Path) -> None:
    """NEG: empty records list raises ValueError."""
    builder = ReplicationKitBuilder()
    cfg = ReplicationKitConfig(output_dir=tmp_path)
    with pytest.raises(ValueError, match="records"):
        builder.build([], cfg)


def test_builder_methodology_citations_constant_keys() -> None:
    """POS: METHODOLOGY_CITATIONS has expected section keys."""
    expected_keys = {
        "valuation_methodology",
        "ensemble_methodology",
        "reference_class_forecasting",
        "dms_survivorship_adjustment",
        "lucas_critique",
        "minsky_kindleberger",
        "bayesian_shrinkage",
        "triple_sigma_reporting",
    }
    assert set(METHODOLOGY_CITATIONS.keys()) == expected_keys


def test_builder_each_citation_section_has_section_field() -> None:
    """POS-inv: each METHODOLOGY_CITATIONS entry has section + citations fields."""
    for section_key, entry in METHODOLOGY_CITATIONS.items():
        assert "section" in entry
        assert "citations" in entry
        assert isinstance(entry["citations"], list)
        assert len(entry["citations"]) >= 1
