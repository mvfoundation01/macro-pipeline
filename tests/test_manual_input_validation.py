"""Layer 1.7-B — tests for ``macro_pipeline.manual_input.validation``.

Spec ref: Strategic L1.7-B inline spec (post-L1.7-A 2026-05-15) §5.
Validation layer for ManualInputSchedule beyond L1.7-A dataclass
invariants. 8 V-rules; V5 (confidence cap) is fail-closed; others
accumulate in ValidationReport.

Test inventory (NEG ratio >= 50% per AP-AUTH-53 discipline):
   1. POS      test_validate_clean_schedule_passes
   2. NEG      test_v1_recession_p_out_of_bounds
   3. NEG      test_v2_recession_p_non_monotonic
   4. POS-inv  test_v2_skips_none_values
   5. NEG      test_v3_dms_positive_value_violation
   6. NEG      test_v4_dms_below_lower_bound
   7. NEG      test_v5_confidence_cap_10y_non_stratified
   8. NEG      test_v5_confidence_cap_10y_regime_stratified
   9. POS      test_v5_cap_passes_below_threshold
  10. NEG      test_v6_duplicate_field_ids
  11. NEG      test_v7_regime_classifier_path_missing
  12. NEG      test_v8_empty_author_or_description
  13. POS-inv  test_multiple_violations_collected
  14. POS      test_clean_horizon_specific_validation

NEG count: 2, 3, 5, 6, 7, 8, 10, 11, 12 = 9 NEG.
POS count: 1, 4, 9, 13, 14 = 5 POS (POS-inv counted as POS-flavor).
NEG floor: 9/14 = 64.3% >= 50% required (AP-AUTH-53).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from macro_pipeline.manual_input import (
    ConfidenceCapViolation,
    ManualInputField,
    ManualInputSchedule,
    SCHEMA_VERSION_CURRENT,
    ValidationReport,
    ValidationViolation,
    validate_schedule,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_recession_field(
    horizon: str,
    value: float | None,
    field_id: str | None = None,
) -> ManualInputField:
    """Build a recession_p ManualInputField for a horizon like '1y'."""
    return ManualInputField(
        field_id=field_id or f"recession_p_{horizon}",
        value=value,
        precedence="manual_or_auto",
        label=f"{horizon.upper()} Recession Probability",
        description=f"Probability of recession within {horizon} horizon",
        help_text="Default uses Sahm + NY Fed + LEI 3D-rule composite",
        category="recession",
        range_min=0.0,
        range_max=1.0,
        requires_confidence_cap_check=True,
    )


def _make_dms_field(
    horizon: str,
    value: float | None,
    field_id: str | None = None,
) -> ManualInputField:
    """Build a dms_override ManualInputField for a horizon like '10y'."""
    return ManualInputField(
        field_id=field_id or f"dms_bps_{horizon}",
        value=value,
        precedence="manual_or_auto",
        label=f"{horizon.upper()} DMS Adjustment (bps)",
        description=f"DMS survivorship adjustment for {horizon} horizon",
        help_text="Auto-load: -175 bps central +/- 50 bps sensitivity",
        category="dms",
        range_min=-500.0,
        range_max=0.0,
    )


def _make_schedule(
    recession_p: list[ManualInputField] | None = None,
    dms_override: list[ManualInputField] | None = None,
    scenario_inputs: dict[str, ManualInputField] | None = None,
    regime_classifier_override: str | None = None,
    author: str = "V",
    description: str = "L1.7-B validation test scenario",
) -> ManualInputSchedule:
    """Build a ManualInputSchedule with sensible defaults."""
    return ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author=author,
        description=description,
        recession_p=recession_p or [],
        dms_override=dms_override or [],
        scenario_inputs=scenario_inputs or {},
        regime_classifier_override=regime_classifier_override,
    )


# ---------------------------------------------------------------------------
# Test 1 — POS — clean schedule passes
# ---------------------------------------------------------------------------


def test_validate_clean_schedule_passes() -> None:
    """POS: a clean schedule yields ValidationReport(is_valid=True)."""
    schedule = _make_schedule(
        recession_p=[
            _make_recession_field("1y", 0.10),
            _make_recession_field("3y", 0.25),
            _make_recession_field("5y", 0.35),
            _make_recession_field("10y", 0.50),
        ],
        dms_override=[_make_dms_field("10y", -200.0)],
    )
    report = validate_schedule(schedule)
    assert isinstance(report, ValidationReport)
    assert report.is_valid is True
    assert report.violations == ()


# ---------------------------------------------------------------------------
# Test 2 — NEG — V1 recession_p out of bounds
# ---------------------------------------------------------------------------


def test_v1_recession_p_out_of_bounds() -> None:
    """NEG: recession_p value=1.5 (out of [0, 1]) triggers V1."""
    schedule = _make_schedule(
        recession_p=[_make_recession_field("5y", 1.5)],
    )
    # horizon=None: V5 skipped; V1 fires
    report = validate_schedule(schedule)
    assert report.is_valid is False
    v1 = report.by_rule("V1")
    assert len(v1) == 1
    assert "1.5" in v1[0].message
    assert "recession_p_5y" in v1[0].field_ref


# ---------------------------------------------------------------------------
# Test 3 — NEG — V2 recession_p non-monotonic
# ---------------------------------------------------------------------------


def test_v2_recession_p_non_monotonic() -> None:
    """NEG: 1Y=0.3, 10Y=0.1 violates monotonicity in horizon."""
    schedule = _make_schedule(
        recession_p=[
            _make_recession_field("1y", 0.3),
            _make_recession_field("10y", 0.1),
        ],
    )
    report = validate_schedule(schedule)
    v2 = report.by_rule("V2")
    assert len(v2) >= 1
    assert "non-monotone" in v2[0].message
    assert "recession_p_1y" in v2[0].field_ref
    assert "recession_p_10y" in v2[0].field_ref


# ---------------------------------------------------------------------------
# Test 4 — POS-inv — V2 skips None values
# ---------------------------------------------------------------------------


def test_v2_skips_none_values() -> None:
    """POS-inv: V2 skips fields with value=None; doesn't trip."""
    schedule = _make_schedule(
        recession_p=[
            _make_recession_field("1y", 0.20),
            _make_recession_field("3y", None),  # skipped by V2
            _make_recession_field("5y", 0.30),
            _make_recession_field("10y", None),  # skipped by V2
        ],
    )
    report = validate_schedule(schedule)
    assert report.by_rule("V2") == ()
    # And report is otherwise clean
    assert report.is_valid is True


# ---------------------------------------------------------------------------
# Test 5 — NEG — V3 DMS positive value violation
# ---------------------------------------------------------------------------


def test_v3_dms_positive_value_violation() -> None:
    """NEG: dms_override value=+50 (positive) violates V3 (sign)."""
    schedule = _make_schedule(
        dms_override=[_make_dms_field("10y", 50.0)],
    )
    report = validate_schedule(schedule)
    v3 = report.by_rule("V3")
    assert len(v3) == 1
    assert "50" in v3[0].message
    assert "dms_bps_10y" in v3[0].field_ref


# ---------------------------------------------------------------------------
# Test 6 — NEG — V4 DMS below lower bound
# ---------------------------------------------------------------------------


def test_v4_dms_below_lower_bound() -> None:
    """NEG: dms_override value=-600 (below -500) violates V4."""
    schedule = _make_schedule(
        dms_override=[_make_dms_field("10y", -600.0)],
    )
    report = validate_schedule(schedule)
    v4 = report.by_rule("V4")
    assert len(v4) == 1
    assert "-600" in v4[0].message
    assert "below lower bound" in v4[0].message


# ---------------------------------------------------------------------------
# Test 7 — NEG strict — V5 confidence cap 10Y non-stratified
# ---------------------------------------------------------------------------


def test_v5_confidence_cap_10y_non_stratified() -> None:
    """NEG strict: recession_p_10y=0.75, horizon=10, non-stratified.

    0.75 > 0.70 cap -> ConfidenceCapViolation raised (fail-closed).
    """
    schedule = _make_schedule(
        recession_p=[_make_recession_field("10y", 0.75)],
    )
    with pytest.raises(ConfidenceCapViolation, match="0.75"):
        validate_schedule(
            schedule,
            horizon_for_confidence_check=10,
            regime_stratified=False,
        )


# ---------------------------------------------------------------------------
# Test 8 — NEG strict — V5 confidence cap 10Y regime-stratified
# ---------------------------------------------------------------------------


def test_v5_confidence_cap_10y_regime_stratified() -> None:
    """NEG strict: recession_p_10y=0.60, horizon=10, regime_stratified.

    0.60 > 0.55 cap -> ConfidenceCapViolation raised (fail-closed).
    """
    schedule = _make_schedule(
        recession_p=[_make_recession_field("10y", 0.60)],
    )
    with pytest.raises(ConfidenceCapViolation, match="regime-stratified"):
        validate_schedule(
            schedule,
            horizon_for_confidence_check=10,
            regime_stratified=True,
        )


# ---------------------------------------------------------------------------
# Test 9 — POS — V5 cap passes below threshold
# ---------------------------------------------------------------------------


def test_v5_cap_passes_below_threshold() -> None:
    """POS: recession_p_10y=0.50, regime_stratified -> no raise.

    0.50 < 0.55 cap. ConfidenceCapViolation NOT raised; other rules
    apply.
    """
    schedule = _make_schedule(
        recession_p=[_make_recession_field("10y", 0.50)],
    )
    report = validate_schedule(
        schedule,
        horizon_for_confidence_check=10,
        regime_stratified=True,
    )
    assert report.is_valid is True


# ---------------------------------------------------------------------------
# Test 10 — NEG — V6 duplicate field IDs
# ---------------------------------------------------------------------------


def test_v6_duplicate_field_ids() -> None:
    """NEG: two fields with same field_id (across categories) violate V6.

    Uses a scenario-input duplicating a recession_p field_id.
    """
    duplicated_id = "recession_p_10y"
    schedule = _make_schedule(
        recession_p=[_make_recession_field("10y", 0.40)],
        scenario_inputs={
            "dup": ManualInputField(
                field_id=duplicated_id,
                value=0.0,
                precedence="manual_or_auto",
                label="dup",
                description="dup",
                help_text="dup",
                category="scenario",
            ),
        },
    )
    report = validate_schedule(schedule)
    v6 = report.by_rule("V6")
    assert len(v6) == 1
    assert duplicated_id in v6[0].field_ref


# ---------------------------------------------------------------------------
# Test 11 — NEG — V7 regime classifier path missing
# ---------------------------------------------------------------------------


def test_v7_regime_classifier_path_missing(tmp_path: Path) -> None:
    """NEG: regime_classifier_override points to a non-existent .py file.

    File extension is correct (.py) but file doesn't exist on disk.
    """
    nonexistent = tmp_path / "definitely_not_here.py"
    assert not nonexistent.exists()
    schedule = _make_schedule(regime_classifier_override=str(nonexistent))
    report = validate_schedule(schedule)
    v7 = report.by_rule("V7")
    assert len(v7) == 1
    assert "does not exist" in v7[0].message


# ---------------------------------------------------------------------------
# Test 12 — NEG — V8 empty author or description
# ---------------------------------------------------------------------------


def test_v8_empty_author_or_description() -> None:
    """NEG: author='' AND description='   ' both violate V8."""
    schedule = _make_schedule(author="", description="   ")
    report = validate_schedule(schedule)
    v8 = report.by_rule("V8")
    assert len(v8) == 2
    field_refs = {v.field_ref for v in v8}
    assert field_refs == {"author", "description"}


# ---------------------------------------------------------------------------
# Test 13 — POS-inv — multiple violations collected (not V5)
# ---------------------------------------------------------------------------


def test_multiple_violations_collected() -> None:
    """POS-inv: schedule with V1 + V3 + V8 -> 3+ violations in report.

    Uses horizon_for_confidence_check=None so V5 doesn't raise; rest
    accumulate.
    """
    schedule = _make_schedule(
        recession_p=[_make_recession_field("5y", 1.2)],  # V1 out of bounds
        dms_override=[_make_dms_field("10y", 100.0)],  # V3 positive value
        author="",  # V8 empty author
    )
    report = validate_schedule(schedule)
    assert report.is_valid is False
    assert len(report.by_rule("V1")) == 1
    assert len(report.by_rule("V3")) == 1
    assert len(report.by_rule("V8")) >= 1
    rule_ids = {v.rule_id for v in report.violations}
    assert {"V1", "V3", "V8"}.issubset(rule_ids)


# ---------------------------------------------------------------------------
# Test 14 — POS — horizon-specific (non-10Y) skips V5
# ---------------------------------------------------------------------------


def test_clean_horizon_specific_validation() -> None:
    """POS: horizon=1 skips V5 even with values that would exceed 10Y cap.

    A recession_p_10y of 0.99 would exceed BOTH caps, but because the
    caller specified horizon=1 (1Y check), V5 is skipped entirely.
    Other rules still apply.
    """
    schedule = _make_schedule(
        recession_p=[
            _make_recession_field("1y", 0.10),
            _make_recession_field("10y", 0.99),
        ],
    )
    report = validate_schedule(
        schedule,
        horizon_for_confidence_check=1,  # skips V5
        regime_stratified=False,
    )
    # V5 didn't fire; report returned; V1+V2 etc still apply
    assert isinstance(report, ValidationReport)
    # 0.10 then 0.99 is monotone non-decreasing -> no V2; bounds OK -> no V1
    assert report.is_valid is True


# ---------------------------------------------------------------------------
# Sanity: ValidationViolation + ValidationReport are frozen dataclasses
# ---------------------------------------------------------------------------


def test_validation_dataclasses_are_frozen() -> None:
    """POS (sanity): ValidationViolation + ValidationReport immutable."""
    v = ValidationViolation(rule_id="V1", field_ref="x", message="y")
    with pytest.raises(Exception):
        v.message = "changed"  # type: ignore[misc]
    r = ValidationReport(violations=(v,))
    with pytest.raises(Exception):
        r.violations = ()  # type: ignore[misc]
    # by_rule helper works
    assert r.by_rule("V1") == (v,)
    assert r.by_rule("V99") == ()
