"""L8 UI module — HTML dark financial terminal renderer.

Per Strategic L8 single comprehensive pre-flight 2026-05-16
(ACCELERATION PROTOCOL v2.0). Single sub-phase covers 8a Core + 8b
Academic + 8c Educational features.

Public API
----------
``ForecastUIRenderer``       Jinja2-based HTML report renderer.
``UIConfig``                 Frozen renderer config dataclass.
``ExplanationStack``         L1/L2/L3 explanation lookup.
``ExplanationLevel``         Enum (L1/L2/L3).
``ReplicationKitBuilder``    Academic peer-review kit zip builder.
``ReplicationKitConfig``     Frozen kit builder config.
"""
from __future__ import annotations

from .explanation_stack import (
    Explanation,
    ExplanationLevel,
    ExplanationStack,
)
from .renderer import ForecastUIRenderer, UIConfig
from .replication_kit import ReplicationKitBuilder, ReplicationKitConfig

__all__ = [
    "Explanation",
    "ExplanationLevel",
    "ExplanationStack",
    "ForecastUIRenderer",
    "ReplicationKitBuilder",
    "ReplicationKitConfig",
    "UIConfig",
]
