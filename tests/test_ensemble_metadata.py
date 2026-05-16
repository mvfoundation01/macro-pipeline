"""Layer 6-A — tests for ``macro_pipeline.ensemble.metadata`` + ``.registry``.

Spec ref: Strategic L6-A inline spec (post-L6-PREP 2026-05-15) §3 Step 7.
MetricMetadata frozen dataclass invariants + YAML registry I/O round-trip
+ Vision §3 90-measurement catalogue institutional fidelity.

Test inventory (NEG ratio >= 50% per AP-AUTH-53 discipline):
   1. POS      test_metric_metadata_basic_construction
   2. NEG      test_metric_metadata_invalid_metric_id_chars
   3. NEG      test_metric_metadata_subcategory_index_out_of_range
   4. NEG      test_metric_metadata_range_inversion
   5. NEG      test_metric_metadata_empty_description_l1
   6. POS      test_load_metrics_registry_full_90
   7. POS-inv  test_load_metrics_registry_subcategory_counts_match_vision_s3
   8. POS-inv  test_registry_round_trip_yaml
   9. NEG      test_load_registry_missing_file
  10. NEG      test_load_registry_duplicate_metric_id
  11. POS      test_registry_metric_id_uniqueness
  12. NEG      test_metric_metadata_invalid_layer_origin

NEG count: 2, 3, 4, 5, 9, 10, 12 = 7 NEG.
POS count: 1, 6, 7, 8, 11 = 5 POS (POS-inv counted as POS-flavor).
NEG floor: 7/12 = 58.3% >= 50% required (AP-AUTH-53).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
import yaml

from macro_pipeline.ensemble import (
    DEFAULT_REGISTRY_PATH,
    SUBCATEGORY_VALID,
    MetricMetadata,
    load_metrics_registry,
    save_metrics_registry,
)

# Vision §3 expected subcategory counts (per Vision §3 §3.1 through §3.12).
VISION_S3_EXPECTED_COUNTS: dict[str, int] = {
    "probability": 8,
    "uncertainty": 7,
    "confidence_conviction": 6,
    "goodness_fit_calibration": 10,
    "statistical_significance": 9,
    "bias_correction": 7,
    "risk_measures": 9,
    "time_series_quality": 6,
    "information_theory": 4,
    "bayesian": 7,
    "macro_specific": 8,
    "regime_conditional": 9,
}
VISION_S3_TOTAL = sum(VISION_S3_EXPECTED_COUNTS.values())  # 90


def _make_valid_metadata(**overrides) -> MetricMetadata:
    """Build a valid MetricMetadata instance; pass overrides as kwargs."""
    defaults = {
        "metric_id": "test_metric",
        "name": "Test Metric",
        "subcategory": "probability",
        "subcategory_index": 1,
        "layer_origin": "L6",
        "unit": "ratio",
        "update_frequency": "on_request",
        "description_l1": "Plain English description.",
        "description_l2": "Sophisticated peer-level description.",
        "description_l3": "Academic precise description with citation.",
    }
    defaults.update(overrides)
    return MetricMetadata(**defaults)


# ===========================================================================
# Test 1 — POS — basic construction
# ===========================================================================


def test_metric_metadata_basic_construction() -> None:
    """POS: valid MetricMetadata constructs cleanly; fields preserved."""
    m = _make_valid_metadata(
        metric_id="cape_percentile",
        name="CAPE percentile",
        subcategory="macro_specific",
        subcategory_index=11,
        layer_origin="L1",
        unit="percentile",
        update_frequency="monthly",
        range_min=0.0,
        range_max=100.0,
        typical_range=(0.0, 100.0),
        invert_for_signal=True,
        citations=("Campbell-Shiller (1988)", "Shiller (2000)"),
    )
    assert m.metric_id == "cape_percentile"
    assert m.subcategory == "macro_specific"
    assert m.subcategory_index == 11
    assert m.layer_origin == "L1"
    assert m.range_min == 0.0
    assert m.range_max == 100.0
    assert m.typical_range == (0.0, 100.0)
    assert m.invert_for_signal is True
    assert m.citations == ("Campbell-Shiller (1988)", "Shiller (2000)")
    # Frozen invariant
    with pytest.raises(Exception):
        m.metric_id = "changed"  # type: ignore[misc]


# ===========================================================================
# Test 2 — NEG — invalid metric_id characters
# ===========================================================================


def test_metric_metadata_invalid_metric_id_chars() -> None:
    """NEG: metric_id with hyphen, space, uppercase, or punctuation raises."""
    for bad_id in ("hyphen-id", "with space", "UpperCase", "with.dot"):
        with pytest.raises(ValueError):
            _make_valid_metadata(metric_id=bad_id)


# ===========================================================================
# Test 3 — NEG — subcategory_index out of range
# ===========================================================================


def test_metric_metadata_subcategory_index_out_of_range() -> None:
    """NEG: subcategory_index outside [1, 12] raises."""
    with pytest.raises(ValueError, match="subcategory_index"):
        _make_valid_metadata(subcategory_index=13)
    with pytest.raises(ValueError, match="subcategory_index"):
        _make_valid_metadata(subcategory_index=0)


# ===========================================================================
# Test 4 — NEG — range_min > range_max
# ===========================================================================


def test_metric_metadata_range_inversion() -> None:
    """NEG: range_min > range_max raises."""
    with pytest.raises(ValueError, match="range_min"):
        _make_valid_metadata(range_min=1.0, range_max=0.0)
    # typical_range inversion too
    with pytest.raises(ValueError, match="typical_range"):
        _make_valid_metadata(typical_range=(1.0, 0.0))


# ===========================================================================
# Test 5 — NEG — empty description_l1
# ===========================================================================


def test_metric_metadata_empty_description_l1() -> None:
    """NEG: empty / whitespace-only description_l1 raises."""
    with pytest.raises(ValueError, match="description_l1"):
        _make_valid_metadata(description_l1="")
    with pytest.raises(ValueError, match="description_l1"):
        _make_valid_metadata(description_l1="   ")
    # description_l2 + description_l3 also required (sanity)
    with pytest.raises(ValueError, match="description_l2"):
        _make_valid_metadata(description_l2="")
    with pytest.raises(ValueError, match="description_l3"):
        _make_valid_metadata(description_l3="")


# ===========================================================================
# Test 6 — POS — load full 90 from default registry
# ===========================================================================


def test_load_metrics_registry_full_90() -> None:
    """POS: default registry loads exactly 90 metrics."""
    registry = load_metrics_registry()
    assert len(registry) == VISION_S3_TOTAL == 90
    # All entries are MetricMetadata instances
    for metric_id, metadata in registry.items():
        assert isinstance(metadata, MetricMetadata)
        assert metadata.metric_id == metric_id  # key matches field


# ===========================================================================
# Test 7 — POS-inv — subcategory counts match Vision §3 distribution
# ===========================================================================


def test_load_metrics_registry_subcategory_counts_match_vision_s3() -> None:
    """POS-inv: each subcategory has the Vision §3-spec'd count."""
    registry = load_metrics_registry()
    counts = Counter(m.subcategory for m in registry.values())
    for subcat, expected in VISION_S3_EXPECTED_COUNTS.items():
        assert counts[subcat] == expected, (
            f"Subcategory {subcat!r}: expected {expected} metrics per "
            f"Vision §3; got {counts[subcat]}"
        )
    # All subcategories covered (no extras)
    assert set(counts.keys()) == SUBCATEGORY_VALID


# ===========================================================================
# Test 8 — POS-inv — YAML save + load round-trip
# ===========================================================================


def test_registry_round_trip_yaml(tmp_path: Path) -> None:
    """POS-inv: save + load preserves the entire registry."""
    original = load_metrics_registry()
    rt_path = tmp_path / "rt_registry.yaml"
    save_metrics_registry(original, rt_path)
    assert rt_path.exists()
    reloaded = load_metrics_registry(rt_path)
    assert len(reloaded) == len(original)
    for metric_id, original_metadata in original.items():
        assert metric_id in reloaded
        assert reloaded[metric_id] == original_metadata


# ===========================================================================
# Test 9 — NEG — missing registry file
# ===========================================================================


def test_load_registry_missing_file(tmp_path: Path) -> None:
    """NEG: missing path raises FileNotFoundError."""
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError, match="not found"):
        load_metrics_registry(missing)


# ===========================================================================
# Test 10 — NEG — duplicate metric_id in registry YAML
# ===========================================================================


def test_load_registry_duplicate_metric_id(tmp_path: Path) -> None:
    """NEG: YAML with duplicate metric_id raises ValueError."""
    dup_yaml = tmp_path / "duplicates.yaml"
    base_entry = {
        "metric_id": "duplicate_id",
        "name": "Duplicate",
        "subcategory": "probability",
        "subcategory_index": 1,
        "layer_origin": "L6",
        "unit": "ratio",
        "update_frequency": "on_request",
        "description_l1": "L1.",
        "description_l2": "L2.",
        "description_l3": "L3.",
    }
    raw = {
        "registry_version": 1,
        "n_metrics": 2,
        "metrics": [base_entry, dict(base_entry)],
    }
    with open(dup_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f)
    with pytest.raises(ValueError, match="Duplicate metric_id"):
        load_metrics_registry(dup_yaml)


# ===========================================================================
# Test 11 — POS — all metric_ids unique in default registry
# ===========================================================================


def test_registry_metric_id_uniqueness() -> None:
    """POS: all 90 metric_ids unique in default registry."""
    registry = load_metrics_registry()
    ids = [m.metric_id for m in registry.values()]
    assert len(ids) == len(set(ids)), (
        f"Duplicate metric_ids in default registry: "
        f"{[i for i in ids if ids.count(i) > 1]}"
    )


# ===========================================================================
# Test 12 — NEG — invalid layer_origin rejected
# ===========================================================================


def test_metric_metadata_invalid_layer_origin() -> None:
    """NEG: layer_origin outside LAYER_ORIGIN_VALID raises."""
    with pytest.raises(ValueError, match="layer_origin"):
        _make_valid_metadata(layer_origin="L99")
    with pytest.raises(ValueError, match="layer_origin"):
        _make_valid_metadata(layer_origin="invalid")
