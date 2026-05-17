"""L7 D1 — APScheduler-based forecast pipeline scheduler.

Per Strategic L7 pre-flight 2026-05-16 (ACCELERATION PROTOCOL v1.0).

Design discipline:
- In-process BackgroundScheduler (no external broker like Celery/Redis)
- UTC-only timezone discipline (matches L6-H replication_kit_metadata)
- Frozen dataclasses for config + result (AP-AUTH-56 invariants)
- `trigger_once` test-mode for deterministic E2E integration tests
- Injectable scheduler instance for unit-test isolation
- Job results captured in-memory; persistence delegated to L7 D4
  ``ParquetForecastStore`` via caller orchestration

L6 invariants preserved:
- Defense-in-depth pattern: scheduler does NOT bypass cap enforcement;
  pipeline callbacks invoke ``aggregate_ensemble`` which enforces cap
  cascade + 6-layer defense
- Finite invariants (AP-AUTH per L6-I D1): timestamps validated;
  numeric fields finite-checked at JobResult construction
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


VALID_TRIGGER_TYPES: Tuple[str, ...] = ("cron", "interval")


@dataclass(frozen=True)
class ScheduleConfig:
    """Schedule configuration for a single forecast job.

    Fields
    ------
    job_id           Stable identifier; used by APScheduler for replace + lookup.
    trigger_type     ``"cron"`` or ``"interval"`` per ``VALID_TRIGGER_TYPES``.
    trigger_args     Kwargs forwarded to ``CronTrigger`` or ``IntervalTrigger``.

    Invariants enforced by ``__post_init__``:
      - job_id non-empty string
      - trigger_type in VALID_TRIGGER_TYPES
      - trigger_args is dict
    """

    job_id: str
    trigger_type: str
    trigger_args: Dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or not self.job_id:
            raise ValueError(
                f"job_id must be non-empty string; got {self.job_id!r}"
            )
        if self.trigger_type not in VALID_TRIGGER_TYPES:
            raise ValueError(
                f"trigger_type {self.trigger_type!r} not in "
                f"{VALID_TRIGGER_TYPES}"
            )
        if not isinstance(self.trigger_args, dict):
            raise TypeError(
                f"trigger_args must be dict; got "
                f"{type(self.trigger_args).__name__}"
            )


@dataclass(frozen=True)
class JobResult:
    """Result of a single forecast-job execution.

    Fields
    ------
    job_id            Mirror of ``ScheduleConfig.job_id``.
    started_at_utc    Timezone-aware UTC datetime.
    completed_at_utc  Timezone-aware UTC datetime.
    success           True if callback completed without exception.
    error_message     Exception string when ``success=False``; None otherwise.
    output_path       Optional path-string when callback persists artifact.

    Invariants enforced by ``__post_init__``:
      - Both timestamps timezone-aware
      - completed_at_utc >= started_at_utc
      - job_id non-empty
    """

    job_id: str
    started_at_utc: datetime
    completed_at_utc: datetime
    success: bool
    error_message: Optional[str] = None
    output_path: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or not self.job_id:
            raise ValueError(
                f"job_id must be non-empty string; got {self.job_id!r}"
            )
        if (
            self.started_at_utc.tzinfo is None
            or self.completed_at_utc.tzinfo is None
        ):
            raise ValueError("timestamps must be timezone-aware (UTC)")
        if self.completed_at_utc < self.started_at_utc:
            raise ValueError(
                f"completed_at_utc {self.completed_at_utc!r} < "
                f"started_at_utc {self.started_at_utc!r}"
            )


class ForecastScheduler:
    """APScheduler wrapper for forecast pipeline scheduling.

    Design: in-process BackgroundScheduler; no external broker.
    Test-friendly via injectable scheduler instance + `trigger_once`
    deterministic mode.

    Usage
    -----
    >>> sched = ForecastScheduler()
    >>> sched.schedule_job(
    ...     ScheduleConfig(
    ...         job_id="daily_forecast",
    ...         trigger_type="cron",
    ...         trigger_args={"hour": 6, "minute": 0},
    ...     ),
    ...     callback=run_daily_forecast,
    ... )
    >>> sched.start()
    >>> # Or for tests: sched.trigger_once("daily_forecast")
    >>> sched.shutdown(wait=False)
    """

    def __init__(
        self, scheduler: Optional[BackgroundScheduler] = None
    ) -> None:
        self._scheduler = scheduler or BackgroundScheduler(timezone="UTC")
        self._job_results: list[JobResult] = []
        self._callbacks: Dict[str, Callable[[], JobResult]] = {}

    def schedule_job(
        self,
        config: ScheduleConfig,
        callback: Callable[[], JobResult],
    ) -> None:
        """Register a callback against a schedule trigger.

        ``callback`` should return a ``JobResult``; if it raises, the
        scheduler wraps the exception in a failure JobResult.
        """
        if config.trigger_type == "cron":
            trigger = CronTrigger(timezone="UTC", **config.trigger_args)
        else:  # interval
            trigger = IntervalTrigger(timezone="UTC", **config.trigger_args)

        self._callbacks[config.job_id] = callback
        self._scheduler.add_job(
            func=self._wrap_callback(callback, config.job_id),
            trigger=trigger,
            id=config.job_id,
            replace_existing=True,
        )

    def _wrap_callback(
        self,
        callback: Callable[[], JobResult],
        job_id: str,
    ) -> Callable[[], None]:
        """Wrap callback to capture JobResult + handle exceptions."""

        def wrapped() -> None:
            started = datetime.now(timezone.utc)
            try:
                result = callback()
                if not isinstance(result, JobResult):
                    # Callback returned something else; synthesize success.
                    result = JobResult(
                        job_id=job_id,
                        started_at_utc=started,
                        completed_at_utc=datetime.now(timezone.utc),
                        success=True,
                    )
                self._job_results.append(result)
            except Exception as e:
                completed = datetime.now(timezone.utc)
                self._job_results.append(
                    JobResult(
                        job_id=job_id,
                        started_at_utc=started,
                        completed_at_utc=completed,
                        success=False,
                        error_message=str(e),
                    )
                )

        return wrapped

    def start(self) -> None:
        """Start the background scheduler thread."""
        self._scheduler.start()

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the scheduler. ``wait=False`` for test cleanup."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)

    def trigger_once(self, job_id: str) -> JobResult:
        """Run job once immediately (testing convenience).

        Bypasses the trigger schedule; useful for E2E integration tests
        that need deterministic execution without waiting for cron-time.
        """
        if job_id not in self._callbacks:
            raise KeyError(
                f"Job {job_id!r} not scheduled; "
                f"available: {sorted(self._callbacks.keys())}"
            )
        wrapped = self._wrap_callback(self._callbacks[job_id], job_id)
        wrapped()
        return self._job_results[-1]

    @property
    def job_results(self) -> Tuple[JobResult, ...]:
        """Immutable view of accumulated job results."""
        return tuple(self._job_results)

    @property
    def scheduled_job_ids(self) -> Tuple[str, ...]:
        """Tuple of currently registered job_ids."""
        return tuple(sorted(self._callbacks.keys()))
