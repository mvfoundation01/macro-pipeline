"""Layer 1.7-C — tests for ``macro_pipeline.manual_input.persistence``.

Spec ref: Strategic L1.7-C inline spec (post-L1.7-B 2026-05-15) §5.
Robust YAML persistence + schema versioning + migration shims +
replication-kit metadata.

Test inventory (NEG ratio >= 50% per AP-AUTH-53 discipline):
   1. POS      test_load_manual_inputs_robust_clean_v1
   2. NEG      test_load_robust_file_not_found
   3. NEG      test_load_robust_malformed_yaml
   4. NEG      test_load_robust_missing_schema_version
   5. NEG      test_load_robust_non_int_schema_version
   6. POS-inv  test_save_atomic_round_trip
   7. NEG-inv  test_save_atomic_cleans_temp_on_failure
   8. POS      test_migrate_v1_to_v1_no_op
   9. POS-inv  test_migrate_v2_to_v1_forward_compat
  10. NEG      test_migrate_v0_to_v1_not_implemented
  11. NEG      test_migrate_unknown_version
  12. POS      test_replication_kit_metadata_populated
  13. NEG-inv  test_load_result_is_frozen
  14. POS      test_load_with_validation_report_clean
  15. NEG-inv  test_atomic_write_preserves_existing_file_on_failure
  16. NEG      test_load_robust_schedule_construction_fails

NEG count: 2, 3, 4, 5, 7, 10, 11, 13, 15, 16 = 10 NEG.
POS count: 1, 6, 8, 9, 12, 14 = 6 POS (POS-inv counted as POS-flavor).
NEG floor: 10/16 = 62.5% >= 50% required (AP-AUTH-53).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from macro_pipeline.manual_input import (
    LoadResult,
    ManualInputField,
    ManualInputLoadError,
    ManualInputMigrationError,
    ManualInputSchedule,
    SCHEMA_VERSION_CURRENT,
    load_manual_inputs_robust,
    migrate_manual_inputs,
    save_manual_inputs_atomic,
    validate_schedule,
)
from macro_pipeline.manual_input import persistence as persistence_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_recession_field() -> ManualInputField:
    return ManualInputField(
        field_id="recession_p_10y",
        value=0.40,
        precedence="manual_or_auto",
        label="10Y Recession Probability",
        description="Probability of recession within 10Y",
        help_text="Default uses Sahm + NY Fed + LEI 3D composite",
        category="recession",
        range_min=0.0,
        range_max=1.0,
        requires_confidence_cap_check=True,
    )


@pytest.fixture
def sample_dms_field() -> ManualInputField:
    return ManualInputField(
        field_id="dms_bps_10y",
        value=-200.0,
        precedence="manual_or_auto",
        label="10Y DMS Adjustment (bps)",
        description="DMS survivorship adjustment for 10Y horizon",
        help_text="Auto-load: -175 bps central +/- 50 bps band",
        category="dms",
        range_min=-500.0,
        range_max=0.0,
    )


@pytest.fixture
def sample_schedule(
    sample_recession_field: ManualInputField,
    sample_dms_field: ManualInputField,
) -> ManualInputSchedule:
    return ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author="V",
        description="L1.7-C persistence test scenario",
        recession_p=[sample_recession_field],
        dms_override=[sample_dms_field],
        scenario_inputs={},
        regime_classifier_override=None,
    )


# ---------------------------------------------------------------------------
# Test 1 — POS — load_robust clean v1
# ---------------------------------------------------------------------------


def test_load_manual_inputs_robust_clean_v1(
    sample_schedule: ManualInputSchedule, tmp_path: Path
) -> None:
    """POS: load a clean v1 YAML returns a populated LoadResult."""
    yaml_path = tmp_path / "manual_inputs.yaml"
    save_manual_inputs_atomic(sample_schedule, str(yaml_path))
    result = load_manual_inputs_robust(str(yaml_path))
    assert isinstance(result, LoadResult)
    assert result.schedule == sample_schedule
    assert result.source_path == str(yaml_path)
    assert result.schema_version_detected == SCHEMA_VERSION_CURRENT
    assert result.migration_applied is False
    assert result.warnings == ()
    assert isinstance(result.replication_kit_metadata, tuple)


# ---------------------------------------------------------------------------
# Test 2 — NEG — file not found
# ---------------------------------------------------------------------------


def test_load_robust_file_not_found(tmp_path: Path) -> None:
    """NEG: missing file raises ManualInputLoadError."""
    missing = tmp_path / "does_not_exist.yaml"
    assert not missing.exists()
    with pytest.raises(ManualInputLoadError, match="not found"):
        load_manual_inputs_robust(str(missing))


# ---------------------------------------------------------------------------
# Test 3 — NEG — malformed YAML
# ---------------------------------------------------------------------------


def test_load_robust_malformed_yaml(tmp_path: Path) -> None:
    """NEG: invalid YAML syntax raises ManualInputLoadError."""
    bad = tmp_path / "bad.yaml"
    # Unbalanced brackets + tab-then-space indentation issue.
    bad.write_text("schema_version: 1\nrecession_p: [unclosed", encoding="utf-8")
    with pytest.raises(ManualInputLoadError, match="Malformed YAML"):
        load_manual_inputs_robust(str(bad))


# ---------------------------------------------------------------------------
# Test 4 — NEG — missing schema_version
# ---------------------------------------------------------------------------


def test_load_robust_missing_schema_version(tmp_path: Path) -> None:
    """NEG: YAML without schema_version key raises ManualInputLoadError."""
    no_version = tmp_path / "no_version.yaml"
    no_version.write_text("author: V\ndescription: x\n", encoding="utf-8")
    with pytest.raises(ManualInputLoadError, match="Missing schema_version"):
        load_manual_inputs_robust(str(no_version))


# ---------------------------------------------------------------------------
# Test 5 — NEG — non-int schema_version
# ---------------------------------------------------------------------------


def test_load_robust_non_int_schema_version(tmp_path: Path) -> None:
    """NEG: schema_version as string raises ManualInputLoadError."""
    bad_version = tmp_path / "bad_version.yaml"
    bad_version.write_text(
        'schema_version: "1"\nauthor: V\ndescription: x\n',
        encoding="utf-8",
    )
    with pytest.raises(ManualInputLoadError, match="must be int"):
        load_manual_inputs_robust(str(bad_version))


# ---------------------------------------------------------------------------
# Test 6 — POS-inv — save_atomic round trip
# ---------------------------------------------------------------------------


def test_save_atomic_round_trip(
    sample_schedule: ManualInputSchedule, tmp_path: Path
) -> None:
    """POS-inv: save_atomic + load_robust preserves equality."""
    yaml_path = tmp_path / "round_trip.yaml"
    save_manual_inputs_atomic(sample_schedule, str(yaml_path))
    assert yaml_path.exists()
    result = load_manual_inputs_robust(str(yaml_path))
    assert result.schedule == sample_schedule


# ---------------------------------------------------------------------------
# Test 7 — NEG-inv — save_atomic cleans temp on failure
# ---------------------------------------------------------------------------


def test_save_atomic_cleans_temp_on_failure(
    sample_schedule: ManualInputSchedule,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NEG-inv: if yaml.safe_dump raises, tmp file is cleaned up.

    Verifies the sibling-tmp + os.replace pattern (mirrors cache.py).
    """
    yaml_path = tmp_path / "wont_finish.yaml"

    def boom(*args, **kwargs):
        raise RuntimeError("simulated mid-write failure")

    monkeypatch.setattr(persistence_module.yaml, "safe_dump", boom)

    with pytest.raises(RuntimeError, match="simulated mid-write failure"):
        save_manual_inputs_atomic(sample_schedule, str(yaml_path))

    assert not yaml_path.exists(), "target file should not exist on write failure"
    leftover = list(tmp_path.glob(f".{yaml_path.name}.*.tmp"))
    assert leftover == [], f"tmp file(s) not cleaned up: {leftover}"


# ---------------------------------------------------------------------------
# Test 8 — POS — migrate v1 -> v1 no-op
# ---------------------------------------------------------------------------


def test_migrate_v1_to_v1_no_op() -> None:
    """POS: detected=1, target=1 -> (raw unchanged, applied=False, [])."""
    raw = {"schema_version": 1, "author": "V"}
    migrated, applied, warnings = migrate_manual_inputs(raw, target_version=1)
    assert migrated is raw  # same object — no copy
    assert applied is False
    assert warnings == []


# ---------------------------------------------------------------------------
# Test 9 — POS-inv — migrate v2 -> v1 forward-compat
# ---------------------------------------------------------------------------


def test_migrate_v2_to_v1_forward_compat() -> None:
    """POS-inv: detected=2, target=1 -> warning + schema_version coerced to 1."""
    raw = {"schema_version": 2, "author": "V"}
    migrated, applied, warnings = migrate_manual_inputs(raw, target_version=1)
    assert migrated["schema_version"] == 1
    assert applied is True
    assert len(warnings) == 1
    assert "v2-specific" in warnings[0]


# ---------------------------------------------------------------------------
# Test 10 — NEG — migrate v0 -> v1 not implemented
# ---------------------------------------------------------------------------


def test_migrate_v0_to_v1_not_implemented() -> None:
    """NEG: detected=0 raises ManualInputMigrationError."""
    raw = {"schema_version": 0, "author": "V"}
    with pytest.raises(ManualInputMigrationError, match="NOT IMPLEMENTED"):
        migrate_manual_inputs(raw, target_version=1)


# ---------------------------------------------------------------------------
# Test 11 — NEG — migrate unknown version
# ---------------------------------------------------------------------------


def test_migrate_unknown_version() -> None:
    """NEG: detected=99 raises ManualInputMigrationError."""
    raw = {"schema_version": 99, "author": "V"}
    with pytest.raises(ManualInputMigrationError, match="No migration path"):
        migrate_manual_inputs(raw, target_version=1)


# ---------------------------------------------------------------------------
# Test 12 — POS — replication kit metadata populated
# ---------------------------------------------------------------------------


def test_replication_kit_metadata_populated(
    sample_schedule: ManualInputSchedule, tmp_path: Path
) -> None:
    """POS: LoadResult.replication_kit_metadata has 4 required keys."""
    yaml_path = tmp_path / "meta.yaml"
    save_manual_inputs_atomic(sample_schedule, str(yaml_path))
    result = load_manual_inputs_robust(str(yaml_path))
    meta_dict = dict(result.replication_kit_metadata)
    assert "code_sha" in meta_dict
    assert "load_timestamp_iso" in meta_dict
    assert "schema_version_detected" in meta_dict
    assert "migration_applied" in meta_dict
    assert meta_dict["schema_version_detected"] == str(SCHEMA_VERSION_CURRENT)
    assert meta_dict["migration_applied"] == "False"
    # code_sha is either a 40-char hex string or "unknown"
    code_sha = meta_dict["code_sha"]
    assert code_sha == "unknown" or (
        len(code_sha) == 40 and all(c in "0123456789abcdef" for c in code_sha)
    )


# ---------------------------------------------------------------------------
# Test 13 — NEG-inv — LoadResult is frozen
# ---------------------------------------------------------------------------


def test_load_result_is_frozen(
    sample_schedule: ManualInputSchedule, tmp_path: Path
) -> None:
    """NEG-inv: mutating LoadResult fields raises."""
    yaml_path = tmp_path / "frozen.yaml"
    save_manual_inputs_atomic(sample_schedule, str(yaml_path))
    result = load_manual_inputs_robust(str(yaml_path))
    with pytest.raises(Exception):  # FrozenInstanceError subclass of AttributeError
        result.migration_applied = True  # type: ignore[misc]
    with pytest.raises(Exception):
        result.warnings = ("hacked",)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 14 — POS — load_robust integrates with validate_schedule
# ---------------------------------------------------------------------------


def test_load_with_validation_report_clean(
    sample_schedule: ManualInputSchedule, tmp_path: Path
) -> None:
    """POS: load_robust + validate_schedule yields clean ValidationReport.

    Exercises L1.7-B + L1.7-C integration. Sample schedule is clean.
    """
    yaml_path = tmp_path / "validated.yaml"
    save_manual_inputs_atomic(sample_schedule, str(yaml_path))
    result = load_manual_inputs_robust(str(yaml_path))
    report = validate_schedule(result.schedule)
    assert report.is_valid is True


# ---------------------------------------------------------------------------
# Test 15 — NEG-inv — atomic write preserves existing file on failure
# ---------------------------------------------------------------------------


def test_atomic_write_preserves_existing_file_on_failure(
    sample_schedule: ManualInputSchedule,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NEG-inv: pre-existing target file is NOT touched on write failure.

    The temp-file-then-replace pattern guarantees that a write failure
    leaves the original file intact (no partial overwrite).
    """
    yaml_path = tmp_path / "preexisting.yaml"
    original_content = "schema_version: 999\noriginal: untouched\n"
    yaml_path.write_text(original_content, encoding="utf-8")

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(persistence_module.yaml, "safe_dump", boom)

    with pytest.raises(RuntimeError, match="simulated failure"):
        save_manual_inputs_atomic(sample_schedule, str(yaml_path))

    assert yaml_path.read_text(encoding="utf-8") == original_content


# ---------------------------------------------------------------------------
# Test 16 — NEG — load_robust: post-migration construction fails
# ---------------------------------------------------------------------------


def test_load_robust_schedule_construction_fails(tmp_path: Path) -> None:
    """NEG: valid YAML + valid schema_version but post-migration dict
    yields an invalid ManualInputField (bad category) -> ManualInputLoadError.
    """
    bad_yaml = tmp_path / "bad_field.yaml"
    raw = {
        "schema_version": 1,
        "created_at": "2026-05-15T12:00:00Z",
        "author": "V",
        "description": "construction will fail",
        "recession_p": [
            {
                "field_id": "x",
                "value": 0.5,
                "precedence": "manual_or_auto",
                "label": "x",
                "description": "x",
                "help_text": "x",
                "category": "INVALID_CATEGORY",  # triggers ManualInputField.__post_init__ ValueError
            }
        ],
        "dms_override": [],
        "scenario_inputs": {},
        "regime_classifier_override": None,
    }
    with open(bad_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f)

    with pytest.raises(ManualInputLoadError, match="Failed to construct"):
        load_manual_inputs_robust(str(bad_yaml))
