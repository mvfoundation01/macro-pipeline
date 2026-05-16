"""MANUAL_INPUT pipeline integration helpers (L1.7-D).

Per Strategic L1.7-D inline spec (post-L1.7-C 2026-05-15): exposes
helpers that wire user-supplied ``ManualInputSchedule`` into the
forecast pipeline at the 5 designated integration surfaces, plus
forecast-time confidence cap enforcement (defense-in-depth with the
L1.7-B value-level V5 check).

Surface mapping
---------------
Surface 1 ``fit_return_forecast_task_b1`` (models/return_forecast.py)
    Adds ``manual_inputs`` keyword parameter. Body calls
    ``apply_scenario_inputs_to_kwargs`` to fold ``ridge_lambda`` +
    ``bootstrap_n`` scenario overrides into the function's
    ``lambda_grid`` + ``bootstrap_iterations`` parameters.
Surface 2 ``derive_forecast_sigma_v2`` (analysis/forecast_sigma.py)
    Adds ``manual_inputs`` keyword parameter. Body calls
    ``apply_scenario_inputs_to_kwargs`` to override the four sigma
    inputs (``historical_return_sigma``, ``analog_period_dispersion_sigma``,
    ``joint_bootstrap_covariance``, ``empirical_coverage_95``).
Surface 3 ``apply_dms_adjustment`` (models/dms_adjustment.py)
    Adds ``manual_inputs`` keyword parameter. Body calls
    ``apply_dms_override_for_horizon`` to override the central bps
    only; sensitivity band stays auto-load per L5b-F F-M4(b) Q6-locked
    discipline.
Surface 4 ``compute_regime_conditional_oos_validation``
    (analysis/regime_conditional_validation.py)
    NO function signature change. The existing ``regime_classifier``
    Callable parameter IS the injection point. Callers resolve a
    classifier via ``load_classifier_from_manual_inputs(manual_inputs)``
    and pass the resulting Callable in.
Surface 5 Recession-P composite ingestion
    NO discrete composite-computation function exists in the codebase
    (verified via Step 2 grep — ``12M_recession_probability_composite``
    is a string identifier referenced by validators/guards/CRPS context,
    not a callable that returns per-horizon recession probabilities).
    Helper ``apply_recession_p_override_for_horizon`` is exposed for
    future consumers to call when recession-P composite computation
    materializes as a discrete callable. Per V's standing-pace
    instruction, L1.7-D ships the helper without wiring to a non-
    existent function; L1.7-E or follow-up sprint wires the helper to
    the eventual composite when it exists.

Defense-in-depth confidence cap (Standing Order #9 + Vision v2.0 §4)
--------------------------------------------------------------------
``enforce_forecast_time_confidence_cap`` raises ``ConfidenceCapViolation``
if a post-override forecast confidence at 10Y exceeds the cap
(0.70 non-stratified; 0.55 regime-stratified). Companion to L1.7-B
``validate_schedule`` V5 which catches override VALUES at construction.
L1.7-B catches the override; L1.7-D catches the propagated forecast.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable, Optional

from macro_pipeline.manual_input.schema import ManualInputSchedule
from macro_pipeline.manual_input.validation import ConfidenceCapViolation

# Confidence cap thresholds — mirror manual_input.validation constants
# (kept duplicated to keep integration module self-contained at import).
CONFIDENCE_CAP_10Y_NON_STRATIFIED = 0.70
CONFIDENCE_CAP_10Y_REGIME_STRATIFIED = 0.55


def apply_scenario_inputs_to_kwargs(
    manual_inputs: Optional[ManualInputSchedule],
    keys: tuple[str, ...],
    auto_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Apply ``scenario_inputs`` overrides to a kwargs dict.

    Precedence handling per L1.7-A schema:
      ``manual_only``     use manual; raise ValueError if value is None.
      ``manual_or_auto``  use manual if value is not None; else auto.
      ``auto_only``       always use auto (manual ignored).

    Keys not present in ``manual_inputs.scenario_inputs`` are passed
    through from ``auto_kwargs`` unchanged.
    """
    if manual_inputs is None:
        return dict(auto_kwargs)

    result = dict(auto_kwargs)
    for key in keys:
        if key not in manual_inputs.scenario_inputs:
            continue
        field = manual_inputs.scenario_inputs[key]
        if field.precedence == "manual_only":
            if field.value is None:
                raise ValueError(
                    f"scenario_inputs[{key!r}].precedence='manual_only' "
                    f"but value is None — must supply explicit value"
                )
            result[key] = field.value
        elif field.precedence == "manual_or_auto":
            if field.value is not None:
                result[key] = field.value
            # else: keep auto value
        elif field.precedence == "auto_only":
            pass  # keep auto value
    return result


def apply_dms_override_for_horizon(
    manual_inputs: Optional[ManualInputSchedule],
    horizon: int,
    auto_dms_bps: float,
) -> float:
    """Apply manual DMS override for a specific horizon.

    Returns the manual override if present (and precedence allows);
    else returns the auto value. Sensitivity band is NOT overridable
    (L5b-F F-M4(b) Q6-locked discipline; only central bps is exposed
    via this helper).

    field_id convention: ``dms_bps_<horizon>y`` (lowercase; e.g.,
    ``dms_bps_10y``). Matching is exact.
    """
    if manual_inputs is None:
        return auto_dms_bps

    field_id = f"dms_bps_{horizon}y"
    for field in manual_inputs.dms_override:
        if field.field_id != field_id:
            continue
        if field.precedence == "auto_only":
            return auto_dms_bps
        if field.value is None:
            if field.precedence == "manual_only":
                raise ValueError(
                    f"dms_override field_id={field_id!r} precedence="
                    f"'manual_only' but value is None"
                )
            return auto_dms_bps
        return float(field.value)
    return auto_dms_bps


def apply_recession_p_override_for_horizon(
    manual_inputs: Optional[ManualInputSchedule],
    horizon: int,
    auto_recession_p: float,
) -> float:
    """Apply manual recession_p override for a specific horizon.

    Returns the manual override if present (and precedence allows);
    else returns the auto value. Consumer-side helper — see Surface 5
    note in module docstring re: no discrete composite-computation
    callee at L1.7-D.

    field_id convention: ``recession_p_<horizon>y`` (lowercase; e.g.,
    ``recession_p_10y``).
    """
    if manual_inputs is None:
        return auto_recession_p

    field_id = f"recession_p_{horizon}y"
    for field in manual_inputs.recession_p:
        if field.field_id != field_id:
            continue
        if field.precedence == "auto_only":
            return auto_recession_p
        if field.value is None:
            if field.precedence == "manual_only":
                raise ValueError(
                    f"recession_p field_id={field_id!r} precedence="
                    f"'manual_only' but value is None"
                )
            return auto_recession_p
        return float(field.value)
    return auto_recession_p


def load_classifier_from_manual_inputs(
    manual_inputs: Optional[ManualInputSchedule],
) -> Optional[Callable]:
    """Dynamically import a user-provided ``regime_classifier`` Callable.

    User module convention:
      The ``regime_classifier_override`` field of the schedule must be
      a path to a ``.py`` file that exports a callable named
      ``regime_classifier`` with signature
      ``(date: pd.Timestamp) -> str`` (one of the regime labels expected
      by Surface 4: "recession", "expansion", "pre_1978").

    Returns ``None`` if ``manual_inputs is None`` or
    ``regime_classifier_override is None``. The caller is then
    expected to use the pipeline default classifier.

    Side-effect note:
      The dynamic import uses a synthesized module name
      (``_manual_input_classifier_<stem>``); the user-supplied module
      is expected to be side-effect-free at import time.
    """
    if manual_inputs is None:
        return None
    if manual_inputs.regime_classifier_override is None:
        return None

    path = Path(manual_inputs.regime_classifier_override)
    if not path.is_file():
        raise ValueError(
            f"regime_classifier_override path does not exist: {path}"
        )
    if path.suffix != ".py":
        raise ValueError(
            f"regime_classifier_override must be a .py file: {path}"
        )

    module_name = f"_manual_input_classifier_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ValueError(f"Failed to load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "regime_classifier"):
        raise ValueError(
            f"User module at {path} must export 'regime_classifier' callable"
        )
    classifier = getattr(module, "regime_classifier")
    if not callable(classifier):
        raise ValueError(
            f"'regime_classifier' in {path} must be callable; got "
            f"{type(classifier).__name__}"
        )
    return classifier


def enforce_forecast_time_confidence_cap(
    forecast_confidence: float,
    horizon: int,
    regime_stratified: bool = False,
) -> None:
    """Forecast-time confidence cap enforcement (defense-in-depth).

    Companion to L1.7-B ``validate_schedule`` V5 (which catches
    override VALUES at construction). This helper catches the
    PROPAGATED forecast confidence after the pipeline applies overrides
    — i.e., if a manual override caused the final forecast confidence
    to exceed the institutional cap, this raises even though the
    override value itself may have been below the cap.

    Cap (Standing Order #9 + Vision v2.0 §4):
      10Y non-stratified:    0.70
      10Y regime-stratified: 0.55
      Other horizons: no L1.7-D enforcement at forecast time

    Raises
    ------
    ConfidenceCapViolation
        If ``forecast_confidence > cap`` at ``horizon == 10``.
    """
    if horizon != 10:
        return
    cap = (
        CONFIDENCE_CAP_10Y_REGIME_STRATIFIED
        if regime_stratified
        else CONFIDENCE_CAP_10Y_NON_STRATIFIED
    )
    if forecast_confidence > cap:
        label = "regime-stratified" if regime_stratified else "non-stratified"
        raise ConfidenceCapViolation(
            f"Forecast confidence {forecast_confidence:.4f} exceeds "
            f"{label} 10Y cap of {cap}. Manual override may have caused "
            f"implicit cap violation at the propagated-forecast stage. "
            f"Per Standing Order #9 + Vision v2.0 §4."
        )
