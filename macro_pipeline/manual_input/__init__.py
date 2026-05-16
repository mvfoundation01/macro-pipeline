"""MANUAL_INPUT layer — user-overridable macro forecast inputs (L1.7).

Per Strategic L1.7 inline spec (post-L5b-H session resume 2026-05-15):
enables V (and future users) to override specific macro forecast inputs
for nowcasting scenarios, custom assumptions, replication kits, and
academic exploration. Vision v2.0 5-pillar discipline preserved (no
confidence cap bypass; replication-kit-compatible; UX-ready metadata;
auditable).

Sub-phase ledger
----------------
L1.7-A  schema definition          (COMPLETE — l1.7-a-accept @ 296cee5)
L1.7-B  validation logic           (COMPLETE — l1.7-b-accept @ 92385e9)
L1.7-C  persistence + versioning   (COMPLETE — l1.7-c-accept @ 2b000ec)
L1.7-D  pipeline integration + Gate 29 (THIS SUB-PHASE)
L1.7-E  edge cases + retrospective

Public API
----------
Schema (L1.7-A):
  ``ManualInputField``           Single overridable input with UX metadata.
  ``ManualInputSchedule``        Full set of manual inputs (loaded from YAML).
  ``load_manual_inputs(path)``   YAML -> ManualInputSchedule (stub; prefer
                                 ``load_manual_inputs_robust`` for new code).
  ``save_manual_inputs(...)``    ManualInputSchedule -> YAML (stub; prefer
                                 ``save_manual_inputs_atomic`` for new code).
  ``SCHEMA_VERSION_CURRENT``     Current schema version (int).
  ``CATEGORY_VALID``             Valid category names (frozenset).

Validation (L1.7-B):
  ``validate_schedule(...)``     Entry point; returns ValidationReport.
  ``ValidationReport``           Result of validate_schedule (frozen).
  ``ValidationViolation``        Single V-rule violation (frozen).
  ``ConfidenceCapViolation``     Hard-fail exception for V5 (Standing
                                 Order #9 confidence cap breach).

Persistence + versioning (L1.7-C):
  ``LoadResult``                 Frozen wrapper for loaded schedule +
                                 replication-kit metadata (Vision §14).
  ``load_manual_inputs_robust``  Existence + parse + version + migration.
  ``save_manual_inputs_atomic``  Atomic YAML write (sibling tmp + os.replace).
  ``migrate_manual_inputs``      Version-dispatch migration shim.
  ``ManualInputLoadError``       Load failure (ValueError subclass).
  ``ManualInputMigrationError``  Migration failure (ValueError subclass).

Pipeline integration (L1.7-D):
  ``apply_scenario_inputs_to_kwargs``     Surface 1 + 2 kwargs override.
  ``apply_dms_override_for_horizon``      Surface 3 central-bps override.
  ``apply_recession_p_override_for_horizon`` Surface 5 helper.
  ``load_classifier_from_manual_inputs``  Surface 4 dynamic-import helper.
  ``enforce_forecast_time_confidence_cap`` Defense-in-depth cap helper.
"""
from __future__ import annotations

from macro_pipeline.manual_input.integration import (
    apply_dms_override_for_horizon,
    apply_recession_p_override_for_horizon,
    apply_scenario_inputs_to_kwargs,
    enforce_forecast_time_confidence_cap,
    load_classifier_from_manual_inputs,
)
from macro_pipeline.manual_input.persistence import (
    LoadResult,
    ManualInputLoadError,
    ManualInputMigrationError,
    load_manual_inputs_robust,
    migrate_manual_inputs,
    save_manual_inputs_atomic,
)
from macro_pipeline.manual_input.schema import (
    CATEGORY_VALID,
    SCHEMA_VERSION_CURRENT,
    ManualInputField,
    ManualInputSchedule,
    PrecedenceLevel,
    load_manual_inputs,
    save_manual_inputs,
)
from macro_pipeline.manual_input.validation import (
    ConfidenceCapViolation,
    ValidationReport,
    ValidationViolation,
    validate_schedule,
)

__all__ = [
    # L1.7-A schema
    "CATEGORY_VALID",
    "ManualInputField",
    "ManualInputSchedule",
    "PrecedenceLevel",
    "SCHEMA_VERSION_CURRENT",
    "load_manual_inputs",
    "save_manual_inputs",
    # L1.7-B validation
    "ConfidenceCapViolation",
    "ValidationReport",
    "ValidationViolation",
    "validate_schedule",
    # L1.7-C persistence + versioning
    "LoadResult",
    "ManualInputLoadError",
    "ManualInputMigrationError",
    "load_manual_inputs_robust",
    "migrate_manual_inputs",
    "save_manual_inputs_atomic",
    # L1.7-D pipeline integration
    "apply_dms_override_for_horizon",
    "apply_recession_p_override_for_horizon",
    "apply_scenario_inputs_to_kwargs",
    "enforce_forecast_time_confidence_cap",
    "load_classifier_from_manual_inputs",
]
