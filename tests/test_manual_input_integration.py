"""Layer 1.7-D — tests for ``macro_pipeline.manual_input.integration``.

Spec ref: Strategic L1.7-D inline spec (post-L1.7-C 2026-05-15) §6.
Pipeline integration: 5 surface helpers + forecast-time confidence
cap defense-in-depth + Gate 29 NEW.

Surface mapping (per integration module docstring):
  S1  fit_return_forecast_task_b1     — manual_inputs kwarg added
  S2  derive_forecast_sigma_v2        — manual_inputs kwarg added
  S3  apply_dms_adjustment            — manual_inputs kwarg added
  S4  compute_regime_conditional_oos_validation
       — NO signature change; helper-only via load_classifier_from_manual_inputs
  S5  Recession-P composite
       — NO discrete composite-computation callee in codebase;
         helper-only via apply_recession_p_override_for_horizon

Test inventory (NEG ratio >= 50% per AP-AUTH-53):
   1. POS-inv  test_surface1_no_manual_inputs_preserves_existing_behavior
   2. POS      test_surface1_scenario_override_applied
   3. POS-inv  test_surface2_no_manual_inputs_preserves_existing_behavior
   4. POS      test_surface2_scenario_override_applied
   5. POS-inv  test_surface3_no_manual_inputs_preserves_existing_behavior
   6. POS      test_surface3_dms_override_applied
   7. NEG-inv  test_surface3_sensitivity_band_NOT_overridable
   8. POS      test_surface4_classifier_override_loaded_from_path
   9. NEG      test_surface4_classifier_override_missing_path_raises
  10. NEG      test_surface4_classifier_override_missing_callable_raises
  11. POS      test_surface5_recession_p_override_applied
  12. NEG      test_forecast_time_cap_10y_non_stratified_violation
  13. NEG      test_forecast_time_cap_10y_regime_stratified_violation
  14. POS      test_forecast_time_cap_below_threshold_passes
  15. POS      test_gate29_passes_clean_schedule
  16. NEG      test_gate29_fails_when_schema_field_missing
  17. NEG      test_precedence_manual_only_missing_value_raises_scenario
  18. NEG      test_load_classifier_non_py_path_raises
  19. NEG      test_precedence_manual_only_missing_value_raises_dms
  20. NEG      test_precedence_manual_only_missing_value_raises_recession_p

NEG count: 7, 9, 10, 12, 13, 16, 17, 18, 19, 20 = 10 NEG.
POS count: 1, 2, 3, 4, 5, 6, 8, 11, 14, 15 = 10 POS (POS-inv counted as POS-flavor).
NEG floor: 10/20 = 50% >= 50% required (AP-AUTH-53).
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from macro_pipeline.manual_input import (
    ConfidenceCapViolation,
    ManualInputField,
    ManualInputSchedule,
    SCHEMA_VERSION_CURRENT,
    apply_dms_override_for_horizon,
    apply_recession_p_override_for_horizon,
    apply_scenario_inputs_to_kwargs,
    enforce_forecast_time_confidence_cap,
    load_classifier_from_manual_inputs,
)
from macro_pipeline.models.dms_adjustment import (
    DMS_BPS_CENTRAL,
    DMS_BPS_SENSITIVITY,
    apply_dms_adjustment,
)
from macro_pipeline.models.return_forecast import fit_return_forecast_task_b1
from macro_pipeline.analysis.forecast_sigma import derive_forecast_sigma_v2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scenario_field(
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


def _make_dms_field(
    horizon: str,
    value: float | None,
    precedence: str = "manual_or_auto",
) -> ManualInputField:
    return ManualInputField(
        field_id=f"dms_bps_{horizon}",
        value=value,
        precedence=precedence,  # type: ignore[arg-type]
        label=f"DMS {horizon}",
        description=f"DMS adjustment for {horizon}",
        help_text="DMS bps central override",
        category="dms",
        range_min=-500.0,
        range_max=0.0,
    )


def _make_recession_field(
    horizon: str,
    value: float | None,
    precedence: str = "manual_or_auto",
) -> ManualInputField:
    return ManualInputField(
        field_id=f"recession_p_{horizon}",
        value=value,
        precedence=precedence,  # type: ignore[arg-type]
        label=f"recession_p {horizon}",
        description=f"recession probability {horizon}",
        help_text="recession_p override",
        category="recession",
        range_min=0.0,
        range_max=1.0,
    )


def _make_schedule(
    recession_p=None,
    dms_override=None,
    scenario_inputs=None,
    regime_classifier_override=None,
) -> ManualInputSchedule:
    return ManualInputSchedule(
        schema_version=SCHEMA_VERSION_CURRENT,
        created_at="2026-05-15T12:00:00Z",
        author="V",
        description="L1.7-D integration test",
        recession_p=recession_p or [],
        dms_override=dms_override or [],
        scenario_inputs=scenario_inputs or {},
        regime_classifier_override=regime_classifier_override,
    )


# ===========================================================================
# Test 1 — POS-inv — Surface 1 backward compat (signature + default None)
# ===========================================================================


def test_surface1_no_manual_inputs_preserves_existing_behavior() -> None:
    """POS-inv: fit_return_forecast_task_b1 has manual_inputs kwarg
    defaulting to None; original signature otherwise unchanged."""
    sig = inspect.signature(fit_return_forecast_task_b1)
    assert "manual_inputs" in sig.parameters
    param = sig.parameters["manual_inputs"]
    assert param.default is None
    assert param.kind == inspect.Parameter.KEYWORD_ONLY


# ===========================================================================
# Test 2 — POS — Surface 1 override applied (lambda_grid collapse)
# ===========================================================================


def test_surface1_scenario_override_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POS: when manual_inputs.scenario_inputs has 'ridge_lambda',
    lambda_grid is collapsed to a 1-tuple BEFORE _validate_b1_input_schema.

    We monkey-patch _validate_b1_input_schema to capture lambda_grid.
    """
    captured: dict = {}

    def fake_validate(crps, cdrs, macro, lambda_grid):
        captured["lambda_grid"] = lambda_grid
        # Raise to short-circuit further execution (we only need to
        # observe lambda_grid arriving at the validator).
        raise RuntimeError("short-circuit after capture")

    monkeypatch.setattr(
        "macro_pipeline.models.return_forecast._validate_b1_input_schema",
        fake_validate,
    )

    schedule = _make_schedule(
        scenario_inputs={
            "ridge_lambda": _make_scenario_field("ridge_lambda", value=0.5),
        }
    )

    with pytest.raises(RuntimeError, match="short-circuit"):
        fit_return_forecast_task_b1(
            schedule=None,  # type: ignore[arg-type]  short-circuited before use
            crps_calibrated_panel=None,  # type: ignore[arg-type]
            cdrs_calibrated_panel=None,  # type: ignore[arg-type]
            macro_features=None,  # type: ignore[arg-type]
            forward_returns=None,  # type: ignore[arg-type]
            manual_inputs=schedule,
        )

    assert captured["lambda_grid"] == (0.5,)


# ===========================================================================
# Test 3 — POS-inv — Surface 2 backward compat
# ===========================================================================


def test_surface2_no_manual_inputs_preserves_existing_behavior() -> None:
    """POS-inv: derive_forecast_sigma_v2 has manual_inputs kwarg
    defaulting to None."""
    sig = inspect.signature(derive_forecast_sigma_v2)
    assert "manual_inputs" in sig.parameters
    param = sig.parameters["manual_inputs"]
    assert param.default is None
    assert param.kind == inspect.Parameter.KEYWORD_ONLY


# ===========================================================================
# Test 4 — POS — Surface 2 override applied
# ===========================================================================


def test_surface2_scenario_override_applied() -> None:
    """POS: when scenario_inputs overrides historical_return_sigma,
    the v2 computation uses the override (observable via result).

    We invoke derive_forecast_sigma_v2 twice with same scalars but
    differing historical_return_sigma (auto-call vs manual override)
    and confirm the historical_return_sigma field in the result reflects
    the override.
    """
    # Auto call: historical_return_sigma=0.10 passed directly
    auto_result = derive_forecast_sigma_v2(
        ridge_residual_se_hac=0.02,
        isotonic_bootstrap_se=0.01,
        historical_return_sigma=0.10,
        analog_period_dispersion_sigma=0.05,
        calibrated_probability=0.4,
        horizon="5Y",
        joint_bootstrap_covariance=0.0,
        empirical_coverage_95=0.95,
    )
    # Manual override: pass 0.10 but override to 0.25 via manual_inputs
    schedule = _make_schedule(
        scenario_inputs={
            "historical_return_sigma": _make_scenario_field(
                "historical_return_sigma", value=0.25
            ),
        }
    )
    manual_result = derive_forecast_sigma_v2(
        ridge_residual_se_hac=0.02,
        isotonic_bootstrap_se=0.01,
        historical_return_sigma=0.10,  # would be 0.10 auto, overridden to 0.25
        analog_period_dispersion_sigma=0.05,
        calibrated_probability=0.4,
        horizon="5Y",
        joint_bootstrap_covariance=0.0,
        empirical_coverage_95=0.95,
        manual_inputs=schedule,
    )
    # The override changes historical_return_sigma; downstream the v1
    # callee writes the input to result.return_sigma (passthrough).
    # Auto vs manual results differ on return_sigma reflecting override.
    assert auto_result.return_sigma == pytest.approx(0.10)
    assert manual_result.return_sigma == pytest.approx(0.25)


# ===========================================================================
# Test 5 — POS-inv — Surface 3 backward compat
# ===========================================================================


def test_surface3_no_manual_inputs_preserves_existing_behavior() -> None:
    """POS-inv: apply_dms_adjustment without manual_inputs returns the
    auto DMS_BPS_CENTRAL value (e.g., -175 at 10Y)."""
    central, lower, upper = apply_dms_adjustment(1000.0, "10Y")
    # Expected: 1000 + (-175) = 825 central; +/- 50 sensitivity band.
    assert central == pytest.approx(1000.0 + DMS_BPS_CENTRAL["10Y"])
    assert lower == pytest.approx(central - DMS_BPS_SENSITIVITY)
    assert upper == pytest.approx(central + DMS_BPS_SENSITIVITY)
    # Also check signature
    sig = inspect.signature(apply_dms_adjustment)
    assert "manual_inputs" in sig.parameters
    assert sig.parameters["manual_inputs"].default is None


# ===========================================================================
# Test 6 — POS — Surface 3 DMS override applied
# ===========================================================================


def test_surface3_dms_override_applied() -> None:
    """POS: manual dms_override central -300 bps is applied at 10Y."""
    schedule = _make_schedule(
        dms_override=[_make_dms_field("10y", value=-300.0)],
    )
    central, lower, upper = apply_dms_adjustment(
        1000.0, "10Y", manual_inputs=schedule
    )
    # Expected: 1000 + (-300) = 700; +/- 50 sensitivity band.
    assert central == pytest.approx(700.0)
    assert lower == pytest.approx(650.0)
    assert upper == pytest.approx(750.0)


# ===========================================================================
# Test 7 — NEG-inv — Surface 3 sensitivity band NOT overridable
# ===========================================================================


def test_surface3_sensitivity_band_NOT_overridable() -> None:
    """NEG-inv: even with manual central override, sensitivity band
    is fixed at +/- DMS_BPS_SENSITIVITY (Q6-locked per L5b-F F-M4(b)).

    Asserts that lower/upper offsets from central remain
    DMS_BPS_SENSITIVITY regardless of override value.
    """
    schedule = _make_schedule(
        dms_override=[_make_dms_field("10y", value=-300.0)],
    )
    central, lower, upper = apply_dms_adjustment(
        1000.0, "10Y", manual_inputs=schedule
    )
    # Symmetric ±DMS_BPS_SENSITIVITY around override central.
    assert central - lower == pytest.approx(DMS_BPS_SENSITIVITY)
    assert upper - central == pytest.approx(DMS_BPS_SENSITIVITY)


# ===========================================================================
# Test 8 — POS — Surface 4 classifier loaded from .py
# ===========================================================================


def test_surface4_classifier_override_loaded_from_path(
    tmp_path: Path,
) -> None:
    """POS: load_classifier_from_manual_inputs dynamically imports a
    user .py module and returns the regime_classifier callable."""
    classifier_py = tmp_path / "user_classifier.py"
    classifier_py.write_text(
        "def regime_classifier(date):\n"
        "    return 'expansion'\n",
        encoding="utf-8",
    )
    schedule = _make_schedule(
        regime_classifier_override=str(classifier_py),
    )
    clf = load_classifier_from_manual_inputs(schedule)
    assert callable(clf)
    assert clf(None) == "expansion"  # type: ignore[misc]


# ===========================================================================
# Test 9 — NEG — Surface 4 missing path raises
# ===========================================================================


def test_surface4_classifier_override_missing_path_raises(
    tmp_path: Path,
) -> None:
    """NEG: regime_classifier_override path doesn't exist -> ValueError."""
    missing = tmp_path / "does_not_exist.py"
    schedule = _make_schedule(regime_classifier_override=str(missing))
    with pytest.raises(ValueError, match="does not exist"):
        load_classifier_from_manual_inputs(schedule)


# ===========================================================================
# Test 10 — NEG — Surface 4 missing callable in module raises
# ===========================================================================


def test_surface4_classifier_override_missing_callable_raises(
    tmp_path: Path,
) -> None:
    """NEG: user .py module without regime_classifier attribute -> ValueError."""
    bad_module = tmp_path / "bad_module.py"
    bad_module.write_text("WRONG_NAME = 42\n", encoding="utf-8")
    schedule = _make_schedule(regime_classifier_override=str(bad_module))
    with pytest.raises(ValueError, match="must export 'regime_classifier'"):
        load_classifier_from_manual_inputs(schedule)


# ===========================================================================
# Test 11 — POS — Surface 5 recession_p override via helper
# ===========================================================================


def test_surface5_recession_p_override_applied() -> None:
    """POS: apply_recession_p_override_for_horizon returns manual
    override when present, auto value otherwise."""
    schedule = _make_schedule(
        recession_p=[_make_recession_field("10y", value=0.45)],
    )
    # 10Y override present
    override = apply_recession_p_override_for_horizon(
        schedule, horizon=10, auto_recession_p=0.30
    )
    assert override == pytest.approx(0.45)
    # 5Y has no override -> auto value
    auto = apply_recession_p_override_for_horizon(
        schedule, horizon=5, auto_recession_p=0.20
    )
    assert auto == pytest.approx(0.20)
    # None manual_inputs -> auto value
    none_case = apply_recession_p_override_for_horizon(
        None, horizon=10, auto_recession_p=0.30
    )
    assert none_case == pytest.approx(0.30)


# ===========================================================================
# Test 12 — NEG — Forecast-time cap 10Y non-stratified violation
# ===========================================================================


def test_forecast_time_cap_10y_non_stratified_violation() -> None:
    """NEG: forecast confidence 0.75 at 10Y non-stratified > 0.70 cap
    -> ConfidenceCapViolation raised."""
    with pytest.raises(ConfidenceCapViolation, match="0.7500"):
        enforce_forecast_time_confidence_cap(
            forecast_confidence=0.75,
            horizon=10,
            regime_stratified=False,
        )


# ===========================================================================
# Test 13 — NEG — Forecast-time cap 10Y regime-stratified violation
# ===========================================================================


def test_forecast_time_cap_10y_regime_stratified_violation() -> None:
    """NEG: forecast confidence 0.60 at 10Y regime-stratified > 0.55 cap
    -> ConfidenceCapViolation raised."""
    with pytest.raises(ConfidenceCapViolation, match="regime-stratified"):
        enforce_forecast_time_confidence_cap(
            forecast_confidence=0.60,
            horizon=10,
            regime_stratified=True,
        )


# ===========================================================================
# Test 14 — POS — Forecast-time cap below threshold passes
# ===========================================================================


def test_forecast_time_cap_below_threshold_passes() -> None:
    """POS: forecast confidence below cap and non-10Y horizons skip cap."""
    # 0.50 < 0.55 regime-strat cap at 10Y -> no raise
    enforce_forecast_time_confidence_cap(0.50, horizon=10, regime_stratified=True)
    # 0.65 < 0.70 non-strat cap at 10Y -> no raise
    enforce_forecast_time_confidence_cap(0.65, horizon=10, regime_stratified=False)
    # Non-10Y horizons skip cap entirely (1Y/3Y/5Y)
    enforce_forecast_time_confidence_cap(0.99, horizon=5, regime_stratified=False)
    enforce_forecast_time_confidence_cap(0.99, horizon=1, regime_stratified=True)


# ===========================================================================
# Test 15 — POS — Gate 29 PASSES on clean repo state
# ===========================================================================


def test_gate29_passes_clean_schedule() -> None:
    """POS: validate_gate29_manual_input_integration() returns PASS
    in current repo state (L1.7-D wiring complete)."""
    from macro_pipeline.validation import (
        validate_gate29_manual_input_integration,
    )
    report = validate_gate29_manual_input_integration()
    assert report.passed is True
    assert not any(f.startswith("FAIL") for f in report.findings)
    # All six criteria should appear in findings as PASS
    for crit_num in ("29.1", "29.2", "29.3", "29.4", "29.5", "29.6"):
        assert any(
            f"Criterion {crit_num} PASS" in f for f in report.findings
        ), f"Missing PASS finding for Criterion {crit_num}"


# ===========================================================================
# Test 16 — NEG — Gate 29 FAILS if expected schema field removed
# ===========================================================================


def test_gate29_fails_when_schema_field_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NEG: monkey-patch fields() to return an incomplete field set;
    Gate 29.1 should FAIL with missing-fields finding."""
    import dataclasses

    real_fields = dataclasses.fields

    def fake_fields(cls):
        all_fields = real_fields(cls)
        # Drop 'schema_version' if present
        return tuple(f for f in all_fields if f.name != "schema_version")

    # Patch the dataclasses.fields imported into validation module
    import macro_pipeline.validation as val_module

    # The validator does `from dataclasses import fields` inside the func.
    # Patch at the dataclasses module level so the local-import sees fake_fields.
    monkeypatch.setattr(dataclasses, "fields", fake_fields)

    report = val_module.validate_gate29_manual_input_integration()
    assert report.passed is False
    assert any("FAIL: Criterion 29.1" in f for f in report.findings)
    assert any("schema_version" in f for f in report.findings)


# ===========================================================================
# Test 17 — NEG — scenario_inputs precedence=manual_only + value=None raises
# ===========================================================================


def test_precedence_manual_only_missing_value_raises_scenario() -> None:
    """NEG: apply_scenario_inputs_to_kwargs raises ValueError when
    precedence='manual_only' but value is None."""
    schedule = _make_schedule(
        scenario_inputs={
            "ridge_lambda": _make_scenario_field(
                "ridge_lambda", value=None, precedence="manual_only"
            ),
        }
    )
    with pytest.raises(ValueError, match="manual_only.*value is None"):
        apply_scenario_inputs_to_kwargs(
            schedule,
            keys=("ridge_lambda",),
            auto_kwargs={"ridge_lambda": 0.1},
        )


# ===========================================================================
# Test 18 — NEG — Surface 4 classifier path non-.py extension raises
# ===========================================================================


def test_load_classifier_non_py_path_raises(tmp_path: Path) -> None:
    """NEG: regime_classifier_override pointing to a .txt file raises."""
    txt = tmp_path / "not_python.txt"
    txt.write_text("not python code", encoding="utf-8")
    schedule = _make_schedule(regime_classifier_override=str(txt))
    with pytest.raises(ValueError, match=r"must be a \.py file"):
        load_classifier_from_manual_inputs(schedule)


# ===========================================================================
# Test 19 — NEG — dms_override precedence=manual_only + value=None raises
# ===========================================================================


def test_precedence_manual_only_missing_value_raises_dms() -> None:
    """NEG: apply_dms_override_for_horizon raises ValueError when
    precedence='manual_only' but value is None."""
    schedule = _make_schedule(
        dms_override=[
            _make_dms_field("10y", value=None, precedence="manual_only"),
        ]
    )
    with pytest.raises(ValueError, match="manual_only.*value is None"):
        apply_dms_override_for_horizon(
            schedule, horizon=10, auto_dms_bps=-175.0
        )


# ===========================================================================
# Test 20 — NEG — recession_p precedence=manual_only + value=None raises
# ===========================================================================


def test_precedence_manual_only_missing_value_raises_recession_p() -> None:
    """NEG: apply_recession_p_override_for_horizon raises ValueError when
    precedence='manual_only' but value is None."""
    schedule = _make_schedule(
        recession_p=[
            _make_recession_field("10y", value=None, precedence="manual_only"),
        ]
    )
    with pytest.raises(ValueError, match="manual_only.*value is None"):
        apply_recession_p_override_for_horizon(
            schedule, horizon=10, auto_recession_p=0.30
        )
