"""L8 D9 — L1/L2/L3 progressive disclosure explanation stack.

Per Strategic L8 single comprehensive pre-flight 2026-05-16
(ACCELERATION PROTOCOL v2.0). Vision §11 BINDING for all outputs.

Three explanation levels per metric:
  - L1 (beginner): one-sentence plain English, no jargon
  - L2 (intermediate): paragraph using finance terminology
  - L3 (advanced): technical formula + Vision section reference

Loaded from ``macro_pipeline/ui/data/explanations.yaml``. Top 20-30
commonly-referenced metrics covered at L8; full 90-metric coverage
deferred to post-deployment polish sub-phase per L8 §11 risk #2
pragmatic scoping (Strategic L8 §3 D9 +20 metric floor).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


class ExplanationLevel(Enum):
    """Vision §11 BINDING progressive disclosure levels."""

    L1 = "beginner"
    L2 = "intermediate"
    L3 = "advanced"


@dataclass(frozen=True)
class Explanation:
    """A single explanation at a specific level for a single metric.

    Fields
    ------
    metric_id        Registry metric ID (e.g., "confidence_score").
    level            ExplanationLevel enum (L1 / L2 / L3).
    text             The explanation text.
    vision_section   Optional Vision section reference (e.g., "§4").
    """

    metric_id: str
    level: ExplanationLevel
    text: str
    vision_section: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.metric_id, str) or not self.metric_id:
            raise ValueError(
                f"metric_id must be non-empty string; got {self.metric_id!r}"
            )
        if not isinstance(self.level, ExplanationLevel):
            raise TypeError(
                f"level must be ExplanationLevel; got "
                f"{type(self.level).__name__}"
            )
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError(
                f"explanation text required (non-empty) for "
                f"{self.metric_id!r} at {self.level}"
            )


class ExplanationStack:
    """L1/L2/L3 explanation lookup for Vision §3 metric registry."""

    def __init__(self, explanations_yaml_path: Union[str, Path]) -> None:
        path = Path(explanations_yaml_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"Explanations YAML not found: {path}"
            )
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, dict):
            raise ValueError(
                f"Explanations YAML root must be mapping; got "
                f"{type(raw).__name__}"
            )
        if "explanations" not in raw:
            raise ValueError("Explanations YAML missing 'explanations' key")
        entries = raw["explanations"]
        if not isinstance(entries, list):
            raise ValueError("explanations must be list")

        self._index: Dict[tuple, Explanation] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Each explanation entry must be mapping; got "
                    f"{type(entry).__name__}"
                )
            metric_id = entry.get("metric_id", "")
            vision_section = entry.get("vision_section")
            for level_name in ("L1", "L2", "L3"):
                if level_name in entry:
                    level = ExplanationLevel[level_name]
                    self._index[(metric_id, level)] = Explanation(
                        metric_id=metric_id,
                        level=level,
                        text=entry[level_name],
                        vision_section=vision_section,
                    )

    def get(
        self, metric_id: str, level: ExplanationLevel
    ) -> Optional[Explanation]:
        """Get explanation for a single metric + level. None if missing."""
        return self._index.get((metric_id, level))

    def get_all_levels(
        self, metric_id: str
    ) -> Dict[ExplanationLevel, Explanation]:
        """Get all available explanation levels for a metric."""
        return {
            lvl: self._index[(metric_id, lvl)]
            for lvl in ExplanationLevel
            if (metric_id, lvl) in self._index
        }

    def metric_ids(self) -> List[str]:
        """All distinct metric IDs with at least one explanation."""
        return sorted({mid for (mid, _) in self._index.keys()})

    def coverage(self) -> Dict[str, int]:
        """Per-level coverage counts."""
        counts: Dict[str, int] = {"L1": 0, "L2": 0, "L3": 0}
        for (_mid, lvl) in self._index.keys():
            counts[lvl.name] += 1
        return counts
