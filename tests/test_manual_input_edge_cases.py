"""Layer 1.7-E — edge case tests for the MANUAL_INPUT layer.

Spec ref: Strategic L1.7-E inline spec (post-L1.7-D 2026-05-15) §3
Task T1. Covers integration boundary edge cases across L1.7-A/B/C/D:
partial overrides, empty schedule semantics, precedence dispatch,
YAML edge cases, and cross-layer confidence cap defense-in-depth.

Test inventory (NEG ratio >= 50% per AP-AUTH-53 discipline):
   1. POS-inv     test_partial_overrides_some_none_some_set
   2. POS-inv     test_empty_schedule_equivalent_to_none
   3. POS         test_precedence_manual_only_with_value
   4. POS         test_precedence_manual_or_auto_falls_back_when_none
   5. POS-inv     test_yaml_minimal_schema_only_loads_empty_schedule
   6. NEG         test_yaml_empty_file_load_raises
   7. NEG         test_yaml_root_is_list_not_dict_raises
   8. NEG         test_load_classifier_py_syntax_error_raises
   9. NEG         test_load_classifier_module_attr_not_callable_raises
  10. NEG strict  test_cross_layer_cap_defense_in_depth

NEG count: 6, 7, 8, 9, 10 = 5 NEG.
POS count: 1, 2, 3, 4, 5 = 5 POS (POS-inv counted as POS-flavor).
NEG floor: 5/10 = 50% >= 50% required (AP-AUTH-53).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from macro_pipeline.manual_input import (
    ConfidenceCapViolation,
    ManualInputField,
    ManualInputLoadError,
    ManualInputSchedule,
    SCHEMA_VERSION_CURRENT,
    apply_dms_override_for_horizon,
    apply_recession_p_override_for_horizon,
    apply_scenario_inputs_to_kwargs,
    enforce_forecast_time_confidence_cap,
    load_classifier_from_manual_inputs,
    load_manual_inputs_robust,
    save_manual_inputs_atomic,
    validate_schedule,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scenario_field(
    field_id: str,
    value: float | None,
    precedence: str = "manual_or_auto",
) -> ManualInputField:
    return ManualInputField(
        field_id=field_id,
        value=value,
        precedence=precedence,  # type: ignore[arg-type]
        label=field_id,
        description=field_id,
        help_text=field_id,
        category="scenario",
    )


def _empty_schedule() -> ManualInputSchedule:
    return ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author="V",
        description="L1.7-E edge case schedule",
        recession_p=[],
        dms_override=[],
        scenario_inputs={},
        regime_classifier_override=None,
    )


# ===========================================================================
# Test 1 — POS-inv — partial overrides (some None, some set)
# ===========================================================================


def test_partial_overrides_some_none_some_set() -> None:
    """POS-inv: schedule has some fields set + some value=None; helpers
    return manual override for set, auto for None.

    Validates that the precedence-driven fallback logic correctly
    distinguishes a field-with-value (use override) from a field-with-
    None-value (use auto).
    """
    schedule = ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author="V",
        description="partial",
        recession_p=[],
        dms_override=[],
        scenario_inputs={
            "ridge_lambda": _scenario_field("ridge_lambda", value=0.5),
            "bootstrap_n": _scenario_field("bootstrap_n", value=None),
        },
    )
    resolved = apply_scenario_inputs_to_kwargs(
        schedule,
        keys=("ridge_lambda", "bootstrap_n"),
        auto_kwargs={"ridge_lambda": 0.1, "bootstrap_n": 1000},
    )
    assert resolved["ridge_lambda"] == 0.5  # override used
    assert resolved["bootstrap_n"] == 1000  # auto used (manual is None)


# ===========================================================================
# Test 2 — POS-inv — empty schedule equivalent to None
# ===========================================================================


def test_empty_schedule_equivalent_to_none() -> None:
    """POS-inv: empty ManualInputSchedule yields same helper outputs as
    passing manual_inputs=None.

    Empty lists/dicts have nothing to iterate; helpers must return
    auto values identically to the None case.
    """
    empty = _empty_schedule()
    auto_kwargs = {"ridge_lambda": 0.1, "bootstrap_n": 1000}

    none_result = apply_scenario_inputs_to_kwargs(
        None, keys=("ridge_lambda", "bootstrap_n"), auto_kwargs=auto_kwargs
    )
    empty_result = apply_scenario_inputs_to_kwargs(
        empty, keys=("ridge_lambda", "bootstrap_n"), auto_kwargs=auto_kwargs
    )
    assert none_result == empty_result

    # DMS helper: same equivalence
    assert apply_dms_override_for_horizon(None, 10, -175.0) == pytest.approx(
        apply_dms_override_for_horizon(empty, 10, -175.0)
    )
    # Recession-p helper: same equivalence
    assert apply_recession_p_override_for_horizon(None, 10, 0.30) == pytest.approx(
        apply_recession_p_override_for_horizon(empty, 10, 0.30)
    )


# ===========================================================================
# Test 3 — POS — precedence=manual_only with value uses manual
# ===========================================================================


def test_precedence_manual_only_with_value() -> None:
    """POS: precedence='manual_only' + value=0.5 -> override used."""
    schedule = ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author="V",
        description="manual_only with value",
        recession_p=[],
        dms_override=[],
        scenario_inputs={
            "ridge_lambda": _scenario_field(
                "ridge_lambda", value=0.5, precedence="manual_only"
            ),
        },
    )
    resolved = apply_scenario_inputs_to_kwargs(
        schedule, keys=("ridge_lambda",), auto_kwargs={"ridge_lambda": 0.1}
    )
    assert resolved["ridge_lambda"] == 0.5


# ===========================================================================
# Test 4 — POS — precedence=manual_or_auto with value=None falls back
# ===========================================================================


def test_precedence_manual_or_auto_falls_back_when_none() -> None:
    """POS: precedence='manual_or_auto' + value=None -> auto used."""
    schedule = ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author="V",
        description="manual_or_auto with None",
        recession_p=[],
        dms_override=[],
        scenario_inputs={
            "ridge_lambda": _scenario_field(
                "ridge_lambda", value=None, precedence="manual_or_auto"
            ),
        },
    )
    resolved = apply_scenario_inputs_to_kwargs(
        schedule, keys=("ridge_lambda",), auto_kwargs={"ridge_lambda": 0.1}
    )
    assert resolved["ridge_lambda"] == 0.1


# ===========================================================================
# Test 5 — POS-inv — YAML with only schema_version loads empty schedule
# ===========================================================================


def test_yaml_minimal_schema_only_loads_empty_schedule(tmp_path: Path) -> None:
    """POS-inv: YAML with schema_version + minimal metadata + empty
    fields loads to a valid ManualInputSchedule (recession_p empty,
    dms_override empty, scenario_inputs empty).
    """
    # First write a valid schedule with empty fields, then verify load
    empty = _empty_schedule()
    yaml_path = tmp_path / "minimal.yaml"
    save_manual_inputs_atomic(empty, str(yaml_path))
    loaded = load_manual_inputs_robust(str(yaml_path))
    assert loaded.schedule.recession_p == []
    assert loaded.schedule.dms_override == []
    assert loaded.schedule.scenario_inputs == {}
    assert loaded.schedule.regime_classifier_override is None


# ===========================================================================
# Test 6 — NEG — empty YAML file rejected
# ===========================================================================


def test_yaml_empty_file_load_raises(tmp_path: Path) -> None:
    """NEG: completely empty YAML file -> ManualInputLoadError.

    yaml.safe_load returns None for empty files; load_robust checks
    isinstance(raw, dict) and rejects None root.
    """
    empty_yaml = tmp_path / "empty.yaml"
    empty_yaml.write_text("", encoding="utf-8")
    with pytest.raises(ManualInputLoadError, match="not a mapping"):
        load_manual_inputs_robust(str(empty_yaml))


# ===========================================================================
# Test 7 — NEG — YAML root is a list, not a dict
# ===========================================================================


def test_yaml_root_is_list_not_dict_raises(tmp_path: Path) -> None:
    """NEG: YAML root that parses to a list (not mapping) raises."""
    list_yaml = tmp_path / "list_root.yaml"
    list_yaml.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ManualInputLoadError, match="not a mapping"):
        load_manual_inputs_robust(str(list_yaml))


# ===========================================================================
# Test 8 — NEG — user .py classifier with syntax error
# ===========================================================================


def test_load_classifier_py_syntax_error_raises(tmp_path: Path) -> None:
    """NEG: user .py module with Python syntax error -> SyntaxError
    (propagates from spec.loader.exec_module)."""
    bad_py = tmp_path / "broken.py"
    bad_py.write_text(
        "def regime_classifier(date)\n    # missing colon -> SyntaxError\n"
        "    return 'expansion'\n",
        encoding="utf-8",
    )
    schedule = ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author="V",
        description="bad classifier",
        recession_p=[],
        dms_override=[],
        scenario_inputs={},
        regime_classifier_override=str(bad_py),
    )
    with pytest.raises(SyntaxError):
        load_classifier_from_manual_inputs(schedule)


# ===========================================================================
# Test 9 — NEG — user .py classifier exists but is not callable
# ===========================================================================


def test_load_classifier_module_attr_not_callable_raises(
    tmp_path: Path,
) -> None:
    """NEG: user .py exports 'regime_classifier' as a non-callable
    (e.g., a string) -> ValueError per L1.7-D integration helper guard.

    Different code path from L1.7-D Test 10 which tested ABSENT
    attribute; this tests PRESENT-but-non-callable attribute.
    """
    non_callable_py = tmp_path / "not_callable.py"
    non_callable_py.write_text(
        "regime_classifier = 'this is a string, not a function'\n",
        encoding="utf-8",
    )
    schedule = ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author="V",
        description="non-callable classifier",
        recession_p=[],
        dms_override=[],
        scenario_inputs={},
        regime_classifier_override=str(non_callable_py),
    )
    with pytest.raises(ValueError, match="must be callable"):
        load_classifier_from_manual_inputs(schedule)


# ===========================================================================
# Test 10 — NEG strict — cross-layer cap defense-in-depth
# ===========================================================================


def test_cross_layer_cap_defense_in_depth() -> None:
    """NEG strict: schedule passes L1.7-B value-level V5 cap (override
    BELOW cap) BUT a propagated forecast confidence exceeds cap at
    L1.7-D forecast-time -> defense-in-depth caught at forecast layer.

    Architecture:
      - Schedule: recession_p_10y = 0.50 (below 0.55 regime-strat cap)
      - L1.7-B validate_schedule(horizon=10, regime_stratified=True)
        PASSES — V5 doesn't raise; override value is below cap.
      - L1.7-D enforce_forecast_time_confidence_cap(0.65, horizon=10,
        regime_stratified=True) RAISES — propagated forecast (e.g.,
        post-DMS-shift) exceeds cap.

    This pattern validates that the two cap layers are positioned at
    distinct points in the pipeline:
      L1.7-B catches dangerous OVERRIDE VALUES at construction;
      L1.7-D catches dangerous PROPAGATED FORECAST values regardless of
      whether any specific override was itself out of bounds.
    """
    schedule = ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author="V",
        description="cross-layer cap scenario",
        recession_p=[
            ManualInputField(
                field_id="recession_p_10y",
                value=0.50,  # below 0.55 regime-strat cap -> V5 passes
                precedence="manual_or_auto",
                label="recession_p_10y",
                description="below cap",
                help_text="below cap",
                category="recession",
                range_min=0.0,
                range_max=1.0,
                requires_confidence_cap_check=True,
            ),
        ],
        dms_override=[],
        scenario_inputs={},
    )

    # Layer 1 (L1.7-B value-level): validate_schedule does NOT raise.
    report = validate_schedule(
        schedule,
        horizon_for_confidence_check=10,
        regime_stratified=True,
    )
    assert report.is_valid is True  # V5 PASSES — override below cap

    # Layer 2 (L1.7-D forecast-time): a propagated forecast confidence
    # of 0.65 at 10Y regime-stratified exceeds the 0.55 cap -> raises.
    with pytest.raises(ConfidenceCapViolation, match="regime-stratified"):
        enforce_forecast_time_confidence_cap(
            forecast_confidence=0.65,
            horizon=10,
            regime_stratified=True,
        )
