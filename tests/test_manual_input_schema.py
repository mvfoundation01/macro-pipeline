"""Layer 1.7-A — tests for ``macro_pipeline.manual_input.schema``.

Spec ref: Strategic L1.7 inline spec (post-L5b-H session resume
2026-05-15) §3 Step 6. Schema definition sub-phase establishing
``ManualInputField`` + ``ManualInputSchedule`` frozen dataclasses plus
YAML load/save stubs. Validation logic beyond dataclass invariants
deferred to L1.7-B; full persistence deferred to L1.7-C; integration
deferred to L1.7-D.

Test inventory (NEG ratio ≥50% per AP-AUTH-53 discipline):
  1.  POS      test_manual_input_field_basic_construction
  2.  NEG      test_manual_input_field_rejects_empty_field_id
  3.  NEG      test_manual_input_field_rejects_invalid_category
  4.  NEG      test_manual_input_field_rejects_range_inversion
  5.  POS      test_manual_input_schedule_basic_construction
  6.  NEG      test_manual_input_schedule_rejects_invalid_schema_version
  7.  NEG      test_manual_input_schedule_rejects_malformed_created_at
  8.  POS-inv  test_yaml_round_trip_preserves_all_fields

NEG count: 2, 3, 4, 6, 7 = 5 NEG.
POS count: 1, 5, 8 (round-trip counted as positive flavor) = 3 POS.
NEG floor: 5/8 = 62.5% ≥ 50% required (AP-AUTH-53).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from macro_pipeline.manual_input import (
    CATEGORY_VALID,
    SCHEMA_VERSION_CURRENT,
    ManualInputField,
    ManualInputSchedule,
    load_manual_inputs,
    save_manual_inputs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_recession_field() -> ManualInputField:
    """A valid 10Y recession probability override field."""
    return ManualInputField(
        field_id="recession_p_10y",
        value=0.45,
        precedence="manual_or_auto",
        label="10Y Recession Probability",
        description="Probability of recession occurring within 10-year horizon",
        help_text="Default uses Sahm Rule + NY Fed + LEI 3D-rule composite",
        category="recession",
        range_min=0.0,
        range_max=1.0,
        requires_confidence_cap_check=True,
    )


@pytest.fixture
def valid_dms_field() -> ManualInputField:
    """A valid 10Y DMS bps adjustment override field."""
    return ManualInputField(
        field_id="dms_bps_10y",
        value=-200.0,
        precedence="manual_or_auto",
        label="10Y DMS Adjustment (bps)",
        description="Annualized DMS survivorship adjustment for 10Y horizon",
        help_text="Auto-load: -175 bps central + +/-50 sensitivity band",
        category="dms",
        range_min=-500.0,
        range_max=0.0,
        requires_confidence_cap_check=False,
    )


@pytest.fixture
def valid_scenario_field() -> ManualInputField:
    """A valid scenario_inputs free-form ridge lambda field."""
    return ManualInputField(
        field_id="scenario_ridge_lambda",
        value=0.5,
        precedence="manual_or_auto",
        label="Ridge regression lambda",
        description="L2 regularization strength for return forecast Ridge fit",
        help_text="Auto-load: cross-validated lambda from training fold",
        category="scenario",
    )


@pytest.fixture
def valid_schedule(
    valid_recession_field: ManualInputField,
    valid_dms_field: ManualInputField,
    valid_scenario_field: ManualInputField,
) -> ManualInputSchedule:
    """A valid ManualInputSchedule with one field of each kind."""
    return ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author="V",
        description="L1.7-A round-trip test scenario",
        recession_p=[valid_recession_field],
        dms_override=[valid_dms_field],
        scenario_inputs={"ridge_lambda": valid_scenario_field},
        regime_classifier_override=None,
    )


# ---------------------------------------------------------------------------
# Test 1 — POS — ManualInputField basic construction
# ---------------------------------------------------------------------------


def test_manual_input_field_basic_construction(
    valid_recession_field: ManualInputField,
) -> None:
    """POS: construct a valid ManualInputField; all fields preserved."""
    f = valid_recession_field
    assert f.field_id == "recession_p_10y"
    assert f.value == 0.45
    assert f.precedence == "manual_or_auto"
    assert f.label == "10Y Recession Probability"
    assert f.category == "recession"
    assert f.range_min == 0.0
    assert f.range_max == 1.0
    assert f.requires_confidence_cap_check is True
    # Frozen invariant: re-assignment must fail.
    with pytest.raises(Exception):
        f.value = 0.99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 2 — NEG — empty field_id raises ValueError
# ---------------------------------------------------------------------------


def test_manual_input_field_rejects_empty_field_id() -> None:
    """NEG: empty field_id raises ValueError per __post_init__ invariant."""
    with pytest.raises(ValueError, match="field_id must be non-empty"):
        ManualInputField(
            field_id="",
            value=0.5,
            precedence="manual_or_auto",
            label="bad",
            description="bad",
            help_text="bad",
            category="recession",
        )


# ---------------------------------------------------------------------------
# Test 3 — NEG — invalid category raises ValueError
# ---------------------------------------------------------------------------


def test_manual_input_field_rejects_invalid_category() -> None:
    """NEG: category outside CATEGORY_VALID raises ValueError."""
    assert "not_a_category" not in CATEGORY_VALID
    with pytest.raises(ValueError, match="category must be one of"):
        ManualInputField(
            field_id="bad_cat",
            value=0.0,
            precedence="manual_or_auto",
            label="bad",
            description="bad",
            help_text="bad",
            category="not_a_category",
        )


# ---------------------------------------------------------------------------
# Test 4 — NEG — range_min > range_max raises ValueError
# ---------------------------------------------------------------------------


def test_manual_input_field_rejects_range_inversion() -> None:
    """NEG: range_min greater than range_max raises ValueError."""
    with pytest.raises(ValueError, match="range_min .* > range_max"):
        ManualInputField(
            field_id="inverted_range",
            value=0.0,
            precedence="manual_or_auto",
            label="bad",
            description="bad",
            help_text="bad",
            category="scenario",
            range_min=1.0,
            range_max=0.0,
        )


# ---------------------------------------------------------------------------
# Test 5 — POS — ManualInputSchedule basic construction
# ---------------------------------------------------------------------------


def test_manual_input_schedule_basic_construction(
    valid_schedule: ManualInputSchedule,
    valid_recession_field: ManualInputField,
    valid_dms_field: ManualInputField,
) -> None:
    """POS: construct a valid schedule; container fields preserved."""
    s = valid_schedule
    assert s.schema_version == SCHEMA_VERSION_CURRENT
    assert s.created_at == "2026-05-15T12:00:00Z"
    assert s.author == "V"
    assert s.description == "L1.7-A round-trip test scenario"
    assert s.recession_p == [valid_recession_field]
    assert s.dms_override == [valid_dms_field]
    assert set(s.scenario_inputs.keys()) == {"ridge_lambda"}
    assert s.regime_classifier_override is None


# ---------------------------------------------------------------------------
# Test 6 — NEG — schema_version != current raises ValueError
# ---------------------------------------------------------------------------


def test_manual_input_schedule_rejects_invalid_schema_version(
    valid_recession_field: ManualInputField,
    valid_dms_field: ManualInputField,
    valid_scenario_field: ManualInputField,
) -> None:
    """NEG: schema_version=2 (forward) blocked at L1.7-A.

    Forward-compat with migration shim is L1.7-C scope; at L1.7-A any
    version not equal to ``SCHEMA_VERSION_CURRENT`` raises ValueError.
    """
    with pytest.raises(ValueError, match="schema_version must be 1"):
        ManualInputSchedule(
            schema_version=2,
            created_at="2026-05-15T12:00:00Z",
            author="V",
            description="bad version",
            recession_p=[valid_recession_field],
            dms_override=[valid_dms_field],
            scenario_inputs={"ridge_lambda": valid_scenario_field},
        )


# ---------------------------------------------------------------------------
# Test 7 — NEG — malformed ISO 8601 created_at raises ValueError
# ---------------------------------------------------------------------------


def test_manual_input_schedule_rejects_malformed_created_at(
    valid_recession_field: ManualInputField,
    valid_dms_field: ManualInputField,
    valid_scenario_field: ManualInputField,
) -> None:
    """NEG: malformed ISO 8601 created_at raises ValueError."""
    with pytest.raises(ValueError, match="created_at must be valid ISO 8601"):
        ManualInputSchedule(
            schema_version=SCHEMA_VERSION_CURRENT,
            created_at="not-a-date",
            author="V",
            description="bad date",
            recession_p=[valid_recession_field],
            dms_override=[valid_dms_field],
            scenario_inputs={"ridge_lambda": valid_scenario_field},
        )


# ---------------------------------------------------------------------------
# Test 8 — POS-inv — YAML save + load round-trip preserves all fields
# ---------------------------------------------------------------------------


def test_yaml_round_trip_preserves_all_fields(
    valid_schedule: ManualInputSchedule,
    tmp_path: Path,
) -> None:
    """POS-inv: save_manual_inputs + load_manual_inputs preserves equality."""
    yaml_path = tmp_path / "manual_inputs.yaml"
    save_manual_inputs(valid_schedule, str(yaml_path))
    assert yaml_path.exists(), "YAML file was not written"
    loaded = load_manual_inputs(str(yaml_path))
    assert loaded == valid_schedule, (
        f"round-trip mismatch:\n  saved   = {valid_schedule!r}\n  "
        f"loaded  = {loaded!r}"
    )
    # Container types preserved
    assert isinstance(loaded.recession_p, list)
    assert isinstance(loaded.scenario_inputs, dict)
    assert isinstance(loaded.recession_p[0], ManualInputField)
    assert isinstance(loaded.scenario_inputs["ridge_lambda"], ManualInputField)
