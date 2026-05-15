"""MANUAL_INPUT schema definitions (L1.7-A).

Per Strategic L1.7 inline spec (post-L5b-H session resume 2026-05-15):
defines ``ManualInputField`` + ``ManualInputSchedule`` frozen dataclasses
plus YAML load/save stubs. Full persistence implementation deferred to
L1.7-C; validation logic beyond dataclass invariants deferred to L1.7-B;
pipeline integration deferred to L1.7-D.

Public API
----------
``ManualInputField``        Single user-overridable input with UX metadata.
``ManualInputSchedule``     Full set of manual inputs (loaded from YAML).
``load_manual_inputs(path)``  YAML -> ManualInputSchedule (stub for L1.7-A).
``save_manual_inputs(schedule, path)``  ManualInputSchedule -> YAML (stub).

Categories (per Strategic disposition #2)
-----------------------------------------
``recession``  recession-P override per horizon (1Y / 3Y / 5Y / 10Y)
``regime``     regime classifier injection (string path; Callable loaded
               at runtime by L1.7-D integration layer)
``dms``        DMS adjustment override per horizon (bps; central only;
               sensitivity band stays auto-load per Strategic Q6)
``scenario``   free-form forecast assumption overrides
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Literal, Optional

PrecedenceLevel = Literal["manual_only", "manual_or_auto", "auto_only"]

CATEGORY_VALID = frozenset({"recession", "regime", "dms", "scenario"})

SCHEMA_VERSION_CURRENT = 1


@dataclass(frozen=True)
class ManualInputField:
    """Single user-overridable input with UX metadata.

    Per Strategic L1.7 spec §2 disposition #2 + #6. Validation beyond
    these dataclass invariants is deferred to L1.7-B.
    """

    field_id: str
    value: Optional[float]
    precedence: PrecedenceLevel
    label: str
    description: str
    help_text: str
    category: str
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    requires_confidence_cap_check: bool = False

    def __post_init__(self) -> None:
        if not self.field_id:
            raise ValueError("field_id must be non-empty")
        if self.category not in CATEGORY_VALID:
            raise ValueError(
                f"category must be one of {sorted(CATEGORY_VALID)}; "
                f"got {self.category!r}"
            )
        if self.range_min is not None and self.range_max is not None:
            if self.range_min > self.range_max:
                raise ValueError(
                    f"range_min ({self.range_min}) > range_max "
                    f"({self.range_max}) for field_id={self.field_id!r}"
                )


@dataclass(frozen=True)
class ManualInputSchedule:
    """Full set of manual inputs (loaded from YAML).

    Per Strategic L1.7 spec §2. ``regime_classifier_override`` is a
    string path to a user Python module; the runtime Callable resolution
    happens in the L1.7-D integration layer (not at schema load time).
    """

    schema_version: int
    created_at: str
    author: str
    description: str
    recession_p: List[ManualInputField]
    dms_override: List[ManualInputField]
    scenario_inputs: Dict[str, ManualInputField]
    regime_classifier_override: Optional[str] = None

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION_CURRENT:
            raise ValueError(
                f"schema_version must be {SCHEMA_VERSION_CURRENT} (current); "
                f"got {self.schema_version}"
            )
        if not self.created_at:
            raise ValueError("created_at must be non-empty ISO 8601 string")
        try:
            datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"created_at must be valid ISO 8601; got "
                f"{self.created_at!r}: {exc}"
            ) from exc


def load_manual_inputs(path: str) -> ManualInputSchedule:
    """Load ``ManualInputSchedule`` from YAML.

    Stub for L1.7-A; full persistence (with versioning + migration) is
    L1.7-C scope.
    """
    import yaml

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _from_dict(raw)


def save_manual_inputs(schedule: ManualInputSchedule, path: str) -> None:
    """Save ``ManualInputSchedule`` to YAML.

    Stub for L1.7-A; full persistence (with versioning + migration) is
    L1.7-C scope.
    """
    import yaml

    raw = _to_dict(schedule)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, default_flow_style=False, sort_keys=False)


def _from_dict(raw: dict) -> ManualInputSchedule:
    """Dict (parsed YAML) -> ManualInputSchedule. Minimal stub."""
    recession_p = [ManualInputField(**f) for f in raw.get("recession_p", [])]
    dms_override = [ManualInputField(**f) for f in raw.get("dms_override", [])]
    scenario_inputs = {
        k: ManualInputField(**v) for k, v in raw.get("scenario_inputs", {}).items()
    }
    return ManualInputSchedule(
        schema_version=raw["schema_version"],
        created_at=raw["created_at"],
        author=raw["author"],
        description=raw["description"],
        recession_p=recession_p,
        dms_override=dms_override,
        scenario_inputs=scenario_inputs,
        regime_classifier_override=raw.get("regime_classifier_override"),
    )


def _to_dict(schedule: ManualInputSchedule) -> dict:
    """ManualInputSchedule -> dict (for YAML safe_dump). Minimal stub."""
    return asdict(schedule)
