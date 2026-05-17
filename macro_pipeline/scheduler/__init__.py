"""L7 scheduler module — APScheduler-based forecast pipeline scheduler.

Per Strategic L7 single-sub-phase pre-flight 2026-05-16
(ACCELERATION PROTOCOL v1.0). L6-K D7 stub replaced with full
implementation at L7 D1.

Public API
----------
``ForecastScheduler``    APScheduler wrapper for in-process scheduling.
``ScheduleConfig``       Frozen config dataclass (job_id + trigger).
``JobResult``            Frozen result dataclass (timestamps + success).
``VALID_TRIGGER_TYPES``  ``("cron", "interval")``.
"""
from __future__ import annotations

from .scheduler import (
    VALID_TRIGGER_TYPES,
    ForecastScheduler,
    JobResult,
    ScheduleConfig,
)

__all__ = [
    "VALID_TRIGGER_TYPES",
    "ForecastScheduler",
    "JobResult",
    "ScheduleConfig",
]
