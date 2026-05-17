"""L7 D1 tests — scheduler module."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from macro_pipeline.scheduler import (
    VALID_TRIGGER_TYPES,
    ForecastScheduler,
    JobResult,
    ScheduleConfig,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ===========================================================================
# ScheduleConfig
# ===========================================================================


def test_schedule_config_valid_cron() -> None:
    """POS: valid cron config."""
    cfg = ScheduleConfig(
        job_id="daily",
        trigger_type="cron",
        trigger_args={"hour": 6, "minute": 0},
    )
    assert cfg.job_id == "daily"
    assert cfg.trigger_type == "cron"


def test_schedule_config_valid_interval() -> None:
    """POS: valid interval config."""
    cfg = ScheduleConfig(
        job_id="hourly",
        trigger_type="interval",
        trigger_args={"hours": 1},
    )
    assert cfg.trigger_type == "interval"


def test_schedule_config_invalid_trigger_type_raises() -> None:
    """NEG: unknown trigger_type raises ValueError."""
    with pytest.raises(ValueError, match="trigger_type"):
        ScheduleConfig(
            job_id="x", trigger_type="event", trigger_args={}
        )


def test_schedule_config_empty_job_id_raises() -> None:
    """NEG: empty job_id raises ValueError."""
    with pytest.raises(ValueError, match="job_id"):
        ScheduleConfig(job_id="", trigger_type="cron", trigger_args={})


def test_schedule_config_non_dict_trigger_args_raises() -> None:
    """NEG: non-dict trigger_args raises TypeError."""
    with pytest.raises(TypeError, match="trigger_args"):
        ScheduleConfig(
            job_id="x", trigger_type="cron", trigger_args="not_a_dict"  # type: ignore[arg-type]
        )


# ===========================================================================
# JobResult
# ===========================================================================


def test_job_result_valid_construction() -> None:
    """POS: valid JobResult."""
    start = _utcnow()
    end = start + timedelta(seconds=5)
    r = JobResult(
        job_id="x",
        started_at_utc=start,
        completed_at_utc=end,
        success=True,
    )
    assert r.success is True


def test_job_result_naive_datetime_raises() -> None:
    """NEG: naive datetime raises ValueError."""
    naive = datetime(2026, 5, 16, 12, 0, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        JobResult(
            job_id="x",
            started_at_utc=naive,
            completed_at_utc=naive,
            success=True,
        )


def test_job_result_completed_before_started_raises() -> None:
    """NEG: completed_at < started_at raises ValueError."""
    start = _utcnow()
    earlier = start - timedelta(seconds=1)
    with pytest.raises(ValueError, match="completed_at_utc"):
        JobResult(
            job_id="x",
            started_at_utc=start,
            completed_at_utc=earlier,
            success=True,
        )


def test_job_result_empty_job_id_raises() -> None:
    """NEG: empty job_id raises ValueError."""
    now = _utcnow()
    with pytest.raises(ValueError, match="job_id"):
        JobResult(
            job_id="",
            started_at_utc=now,
            completed_at_utc=now,
            success=True,
        )


# ===========================================================================
# ForecastScheduler
# ===========================================================================


def test_scheduler_trigger_once_captures_success() -> None:
    """POS-inv: trigger_once captures successful JobResult."""
    sched = ForecastScheduler()

    def callback() -> JobResult:
        now = _utcnow()
        return JobResult(
            job_id="test",
            started_at_utc=now,
            completed_at_utc=now,
            success=True,
            output_path="/tmp/test.parquet",
        )

    cfg = ScheduleConfig(
        job_id="test",
        trigger_type="interval",
        trigger_args={"seconds": 3600},
    )
    sched.schedule_job(cfg, callback)
    result = sched.trigger_once("test")
    assert result.success is True
    assert result.output_path == "/tmp/test.parquet"


def test_scheduler_trigger_once_captures_exception() -> None:
    """POS-inv: callback exception captured as failure JobResult."""
    sched = ForecastScheduler()

    def failing_callback() -> JobResult:
        raise RuntimeError("simulated failure")

    cfg = ScheduleConfig(
        job_id="failing",
        trigger_type="interval",
        trigger_args={"seconds": 60},
    )
    sched.schedule_job(cfg, failing_callback)
    result = sched.trigger_once("failing")
    assert result.success is False
    assert "simulated failure" in (result.error_message or "")


def test_scheduler_trigger_once_unknown_job_raises() -> None:
    """NEG: trigger_once on unknown job_id raises KeyError."""
    sched = ForecastScheduler()
    with pytest.raises(KeyError, match="not scheduled"):
        sched.trigger_once("missing")


def test_scheduler_scheduled_job_ids_property() -> None:
    """POS: scheduled_job_ids reflects registered jobs."""
    sched = ForecastScheduler()

    def cb() -> JobResult:
        now = _utcnow()
        return JobResult(
            job_id="x", started_at_utc=now, completed_at_utc=now,
            success=True,
        )

    sched.schedule_job(
        ScheduleConfig(job_id="x", trigger_type="interval", trigger_args={"seconds": 60}),
        cb,
    )
    sched.schedule_job(
        ScheduleConfig(job_id="y", trigger_type="interval", trigger_args={"seconds": 120}),
        cb,
    )
    assert sched.scheduled_job_ids == ("x", "y")


def test_scheduler_valid_trigger_types_constant() -> None:
    """POS: VALID_TRIGGER_TYPES is the expected tuple."""
    assert VALID_TRIGGER_TYPES == ("cron", "interval")


def test_scheduler_callback_returns_non_jobresult_synthesizes() -> None:
    """POS-inv: callback returning non-JobResult synthesizes success result."""
    sched = ForecastScheduler()

    def bad_callback():
        return "not a JobResult"

    cfg = ScheduleConfig(
        job_id="weird",
        trigger_type="interval",
        trigger_args={"seconds": 60},
    )
    sched.schedule_job(cfg, bad_callback)  # type: ignore[arg-type]
    result = sched.trigger_once("weird")
    # Per implementation: non-JobResult returns synthesizes success.
    assert result.success is True
    assert result.job_id == "weird"


def test_scheduler_shutdown_idempotent() -> None:
    """POS: shutdown when not running is no-op (no exception)."""
    sched = ForecastScheduler()
    # No start() call; shutdown should still be safe.
    sched.shutdown(wait=False)
