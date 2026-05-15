"""MANUAL_INPUT validation layer (L1.7-B).

Per Strategic L1.7-B inline spec (post-L1.7-A 2026-05-15): implements
8 V-rules for ``ManualInputSchedule`` instances beyond the L1.7-A
dataclass invariants. Critical layer for Standing Order #9 (confidence
cap) enforcement post-override.

V-rules
-------
V1  recession_p[i].value in [0, 1] when not None.
V2  recession_p non-decreasing in horizon (cumulative recession prob).
V3  dms_override[i].value <= 0 when not None (negative-only adjustment).
V4  dms_override[i].value in [-500, 0] when not None.
V5  Confidence cap at 10Y (Standing Order #9 + Vision v2.0 §4).
    Raises ConfidenceCapViolation; does NOT accumulate in report.
V6  field_id uniqueness across all override categories.
V7  regime_classifier_override path validity (existence + .py).
V8  author + description non-empty (post-strip).

Public API
----------
``ValidationViolation``      Single rule violation (frozen dataclass).
``ValidationReport``         Result of validate_schedule (frozen).
``validate_schedule(...)``   Entry point; returns ValidationReport.
``ConfidenceCapViolation``   Hard-fail exception (V5 only).

Out-of-scope (per Strategic L1.7-B §2)
--------------------------------------
- YAML migration shims for schema_version != 1 (L1.7-C)
- Pipeline integration with L2/L3/L5 (L1.7-D)
- Forecast-time confidence computation (L1.7-D; V5 here checks override
  values only, not actual forecast outputs)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from macro_pipeline.manual_input.schema import ManualInputSchedule

# Confidence cap thresholds per Standing Order #9 + Vision v2.0 §4
# (institutional discipline boundary; not user-tunable).
CONFIDENCE_CAP_10Y_NON_STRATIFIED = 0.70
CONFIDENCE_CAP_10Y_REGIME_STRATIFIED = 0.55

# DMS bps adjustment range (negative-only; lower bound deep enough to
# accommodate sensitivity-band exploration around the -175 bps central).
DMS_BPS_LOWER_BOUND = -500.0
DMS_BPS_UPPER_BOUND = 0.0

# Recession probability bounds.
RECESSION_P_LOWER = 0.0
RECESSION_P_UPPER = 1.0

# Horizon suffix extractor: matches "_1y", "_3y", "_5y", "_10y", etc.
_HORIZON_SUFFIX_RE = re.compile(r"_(\d+)y$", re.IGNORECASE)


class ConfidenceCapViolation(ValueError):
    """Standing Order #9 confidence cap breach at validation time.

    Raised by ``validate_schedule()`` when an override value exceeds
    the institutional confidence cap at 10Y horizon. Fail-closed (not
    collected in ValidationReport) because cap enforcement is a hard
    institutional discipline boundary per Vision v2.0 §4. Callers
    should catch ``ConfidenceCapViolation`` specifically (NOT broad
    ``except ValueError``) per L1.7-B §10 risk #4.
    """


@dataclass(frozen=True)
class ValidationViolation:
    """Single validation-rule violation.

    Fields:
        rule_id   The V-rule that fired (e.g. "V1", "V3").
        field_ref Human-readable pointer to the offending field
                  (e.g. "recession_p[0] (field_id='recession_p_10y')").
        message   Description of the violation.
    """

    rule_id: str
    field_ref: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    """Result of ``validate_schedule()``.

    Use ``.is_valid`` for the boolean summary and ``.violations`` for
    detail. V5 (confidence cap) never appears here — it raises.
    """

    violations: tuple[ValidationViolation, ...]

    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0

    def by_rule(self, rule_id: str) -> tuple[ValidationViolation, ...]:
        """Filter violations to a single V-rule (e.g. ``"V1"``)."""
        return tuple(v for v in self.violations if v.rule_id == rule_id)


def validate_schedule(
    schedule: ManualInputSchedule,
    horizon_for_confidence_check: Optional[int] = None,
    regime_stratified: bool = False,
) -> ValidationReport:
    """Validate a ``ManualInputSchedule`` against the 8 V-rules.

    Parameters
    ----------
    schedule
        The ManualInputSchedule to validate.
    horizon_for_confidence_check
        If 10, enforce V5 confidence cap. Otherwise V5 is skipped
        (cap applies at forecast time for non-10Y horizons; L1.7-B
        enforces the 10Y institutional discipline boundary only).
    regime_stratified
        If True, use the regime-stratified 10Y cap (0.55); else use
        the non-stratified 10Y cap (0.70). Standing Order #9 +
        Vision v2.0 §4.

    Returns
    -------
    ValidationReport
        Accumulated V1-V4, V6-V8 violations. ``is_valid`` is True iff
        empty.

    Raises
    ------
    ConfidenceCapViolation
        If V5 trips (10Y horizon + recession_p_10y override > cap).
        Hard institutional discipline boundary; fail-closed per
        Standing Order #9.
    """
    violations: List[ValidationViolation] = []

    # V5 first — fail-closed if breached.
    _check_confidence_cap(
        schedule,
        horizon_for_confidence_check,
        regime_stratified,
    )

    _check_recession_p_bounds(schedule, violations)  # V1
    _check_recession_p_monotonicity(schedule, violations)  # V2
    _check_dms_sign_and_bounds(schedule, violations)  # V3 + V4
    _check_field_id_uniqueness(schedule, violations)  # V6
    _check_regime_classifier_path(schedule, violations)  # V7
    _check_metadata(schedule, violations)  # V8

    return ValidationReport(violations=tuple(violations))


# ---------------------------------------------------------------------------
# V1: recession_p bounds
# ---------------------------------------------------------------------------
def _check_recession_p_bounds(
    schedule: ManualInputSchedule,
    violations: List[ValidationViolation],
) -> None:
    """V1: each recession_p[i].value in [0, 1] when not None."""
    for idx, f in enumerate(schedule.recession_p):
        if f.value is None:
            continue
        if not (RECESSION_P_LOWER <= f.value <= RECESSION_P_UPPER):
            violations.append(
                ValidationViolation(
                    rule_id="V1",
                    field_ref=f"recession_p[{idx}] (field_id={f.field_id!r})",
                    message=(
                        f"recession_p value {f.value} outside "
                        f"[{RECESSION_P_LOWER}, {RECESSION_P_UPPER}]"
                    ),
                )
            )


# ---------------------------------------------------------------------------
# V2: recession_p monotonicity in horizon
# ---------------------------------------------------------------------------
def _check_recession_p_monotonicity(
    schedule: ManualInputSchedule,
    violations: List[ValidationViolation],
) -> None:
    """V2: recession_p non-decreasing in horizon (cumulative prob).

    Skips fields with value=None (no information). Skips fields whose
    field_id doesn't match the ``*_Ny`` pattern (non-standard horizon
    naming).
    """
    horizon_value_pairs: List[tuple[int, float, str]] = []
    for f in schedule.recession_p:
        if f.value is None:
            continue
        m = _HORIZON_SUFFIX_RE.search(f.field_id)
        if m is None:
            continue
        horizon_value_pairs.append((int(m.group(1)), f.value, f.field_id))

    horizon_value_pairs.sort(key=lambda x: x[0])

    for i in range(1, len(horizon_value_pairs)):
        prev_h, prev_v, prev_id = horizon_value_pairs[i - 1]
        curr_h, curr_v, curr_id = horizon_value_pairs[i]
        if curr_v < prev_v:
            violations.append(
                ValidationViolation(
                    rule_id="V2",
                    field_ref=f"recession_p ({prev_id} -> {curr_id})",
                    message=(
                        f"non-monotone in horizon: {prev_id}={prev_v} > "
                        f"{curr_id}={curr_v} (cumulative recession prob "
                        f"must be non-decreasing in horizon)"
                    ),
                )
            )


# ---------------------------------------------------------------------------
# V3 + V4: dms_override sign + range bounds
# ---------------------------------------------------------------------------
def _check_dms_sign_and_bounds(
    schedule: ManualInputSchedule,
    violations: List[ValidationViolation],
) -> None:
    """V3 + V4: dms_override.value <= 0 AND in [-500, 0]."""
    for idx, f in enumerate(schedule.dms_override):
        if f.value is None:
            continue
        if f.value > DMS_BPS_UPPER_BOUND:
            violations.append(
                ValidationViolation(
                    rule_id="V3",
                    field_ref=f"dms_override[{idx}] (field_id={f.field_id!r})",
                    message=(
                        f"dms_override value {f.value} > "
                        f"{DMS_BPS_UPPER_BOUND} (DMS adjustment must be "
                        f"<= 0; survivorship subtracts return)"
                    ),
                )
            )
        if f.value < DMS_BPS_LOWER_BOUND:
            violations.append(
                ValidationViolation(
                    rule_id="V4",
                    field_ref=f"dms_override[{idx}] (field_id={f.field_id!r})",
                    message=(
                        f"dms_override value {f.value} below lower bound "
                        f"{DMS_BPS_LOWER_BOUND} bps"
                    ),
                )
            )


# ---------------------------------------------------------------------------
# V5: confidence cap (Standing Order #9 + Vision v2.0 §4)
# ---------------------------------------------------------------------------
def _check_confidence_cap(
    schedule: ManualInputSchedule,
    horizon: Optional[int],
    regime_stratified: bool,
) -> None:
    """V5: enforce Standing Order #9 confidence cap at 10Y horizon.

    Cap:
      - 10Y non-stratified:    0.70
      - 10Y regime-stratified: 0.55
      - Other horizons: no L1.7-B cap (caps applied at forecast time
        by the pipeline; L1.7-B only enforces the institutional
        discipline boundary at 10Y).

    L1.7-B does NOT compute actual forecast confidence — that requires
    pipeline integration (L1.7-D). Instead, L1.7-B enforces that the
    OVERRIDE VALUES themselves don't reach the cap: if any
    recession_p_10y override > cap, the user is asserting confidence
    in an outcome that exceeds Vision-allowed confidence at 10Y.
    """
    if horizon != 10:
        return
    cap = (
        CONFIDENCE_CAP_10Y_REGIME_STRATIFIED
        if regime_stratified
        else CONFIDENCE_CAP_10Y_NON_STRATIFIED
    )
    for f in schedule.recession_p:
        if not f.field_id.endswith("_10y"):
            continue
        if f.value is None:
            continue
        if f.value > cap:
            label = (
                "regime-stratified" if regime_stratified else "non-stratified"
            )
            raise ConfidenceCapViolation(
                f"recession_p_10y override value {f.value} exceeds "
                f"{label} 10Y cap of {cap}. Per Standing Order #9 + "
                f"Vision v2.0 §4."
            )


# ---------------------------------------------------------------------------
# V6: field_id uniqueness
# ---------------------------------------------------------------------------
def _check_field_id_uniqueness(
    schedule: ManualInputSchedule,
    violations: List[ValidationViolation],
) -> None:
    """V6: assert no duplicate field_id across categories."""
    field_ids: List[str] = []
    field_ids.extend(f.field_id for f in schedule.recession_p)
    field_ids.extend(f.field_id for f in schedule.dms_override)
    field_ids.extend(f.field_id for f in schedule.scenario_inputs.values())

    seen: set[str] = set()
    duplicates: set[str] = set()
    for fid in field_ids:
        if fid in seen:
            duplicates.add(fid)
        seen.add(fid)

    for dup in sorted(duplicates):
        violations.append(
            ValidationViolation(
                rule_id="V6",
                field_ref=f"field_id={dup!r}",
                message="duplicate field_id across override categories",
            )
        )


# ---------------------------------------------------------------------------
# V7: regime_classifier_override path validity
# ---------------------------------------------------------------------------
def _check_regime_classifier_path(
    schedule: ManualInputSchedule,
    violations: List[ValidationViolation],
) -> None:
    """V7: if regime_classifier_override is non-None, path must exist + .py.

    Note: full import validation (does the module load? does it
    export a Callable[[pd.Timestamp], str]?) is L1.7-D integration
    scope. L1.7-B only checks file existence + .py extension.
    """
    path_str = schedule.regime_classifier_override
    if path_str is None:
        return
    if not path_str.endswith(".py"):
        violations.append(
            ValidationViolation(
                rule_id="V7",
                field_ref="regime_classifier_override",
                message=(
                    f"path {path_str!r} does not end in .py (expected "
                    f"Python module file)"
                ),
            )
        )
        return
    if not Path(path_str).is_file():
        violations.append(
            ValidationViolation(
                rule_id="V7",
                field_ref="regime_classifier_override",
                message=f"path {path_str!r} does not exist or is not a file",
            )
        )


# ---------------------------------------------------------------------------
# V8: metadata completeness
# ---------------------------------------------------------------------------
def _check_metadata(
    schedule: ManualInputSchedule,
    violations: List[ValidationViolation],
) -> None:
    """V8: author + description non-empty (post-strip).

    L1.7-A __post_init__ already enforces created_at non-empty + ISO 8601.
    V8 covers the remaining metadata fields.
    """
    if not schedule.author.strip():
        violations.append(
            ValidationViolation(
                rule_id="V8",
                field_ref="author",
                message="author must be non-empty string (post-strip)",
            )
        )
    if not schedule.description.strip():
        violations.append(
            ValidationViolation(
                rule_id="V8",
                field_ref="description",
                message="description must be non-empty string (post-strip)",
            )
        )
