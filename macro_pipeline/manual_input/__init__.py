"""MANUAL_INPUT layer — user-overridable macro forecast inputs (L1.7).

Per Strategic L1.7 inline spec (post-L5b-H session resume 2026-05-15):
enables V (and future users) to override specific macro forecast inputs
for nowcasting scenarios, custom assumptions, replication kits, and
academic exploration. Vision v2.0 5-pillar discipline preserved (no
confidence cap bypass; replication-kit-compatible; UX-ready metadata;
auditable).

Sub-phase ledger
----------------
L1.7-A  schema definition (THIS SUB-PHASE)
L1.7-B  validation logic
L1.7-C  full persistence (versioning + migration)
L1.7-D  integration with L2/L3/L5 + Gate 29 NEW
L1.7-E  edge cases + retrospective

Public API
----------
``ManualInputField``           Single overridable input with UX metadata.
``ManualInputSchedule``        Full set of manual inputs (loaded from YAML).
``load_manual_inputs(path)``   YAML -> ManualInputSchedule (stub).
``save_manual_inputs(...)``    ManualInputSchedule -> YAML (stub).
``SCHEMA_VERSION_CURRENT``     Current schema version (int).
``CATEGORY_VALID``             Valid category names (frozenset).
"""
from __future__ import annotations

from macro_pipeline.manual_input.schema import (
    CATEGORY_VALID,
    SCHEMA_VERSION_CURRENT,
    ManualInputField,
    ManualInputSchedule,
    PrecedenceLevel,
    load_manual_inputs,
    save_manual_inputs,
)

__all__ = [
    "CATEGORY_VALID",
    "ManualInputField",
    "ManualInputSchedule",
    "PrecedenceLevel",
    "SCHEMA_VERSION_CURRENT",
    "load_manual_inputs",
    "save_manual_inputs",
]
