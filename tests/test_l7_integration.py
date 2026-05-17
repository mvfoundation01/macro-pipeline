"""L7 D5 — end-to-end integration tests.

Wires scheduler (D1) → component producers (D3) → persistence (D4) →
alerting (D2) → alert rules (D6) into a full pipeline trigger cycle.
Verifies the L7 surfaces interact correctly without making real
network/external calls.

Uses ``unittest.mock`` for all external dependencies (smtplib/requests).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from macro_pipeline.alerting import (
    Alert,
    AlertDispatcher,
    AlertSeverity,
    evaluate_rule_against_payload,
    load_alert_rules,
)
from macro_pipeline.persistence import ForecastRecord, ParquetForecastStore
from macro_pipeline.scheduler import (
    ForecastScheduler,
    JobResult,
    ScheduleConfig,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def test_end_to_end_scheduler_persistence_alert(tmp_path: Path) -> None:
    """E2E: scheduler triggers → persistence appends → alert dispatched."""
    store = ParquetForecastStore(tmp_path / "forecasts")
    mock_adapter = MagicMock()
    mock_adapter.send.return_value = True
    dispatcher = AlertDispatcher(adapters=[mock_adapter])

    captured: dict = {}

    def pipeline_callback() -> JobResult:
        started = _utcnow()
        record = ForecastRecord(
            forecast_id="e2e-001",
            timestamp_utc=started,
            horizon=1,
            point_estimate_annualized=0.08,
            sigma_annualized=0.15,
            confidence=0.85,  # high → triggers rule
            conviction=6.5,
            code_sha="abc123",
            metadata_json="{}",
        )
        output_path = store.append([record])
        captured["record"] = record

        # Dispatch alert when confidence > 0.80.
        if record.confidence > 0.80:
            alert = Alert(
                alert_id=f"alert-{record.forecast_id}",
                severity=AlertSeverity.CRITICAL,
                title="High confidence forecast",
                message=(
                    f"1Y forecast: {record.point_estimate_annualized:.2%} "
                    f"(confidence {record.confidence:.2f})"
                ),
                timestamp_utc=_utcnow(),
                metadata={"horizon": 1, "forecast_id": record.forecast_id},
            )
            dispatcher.dispatch(alert)
        completed = _utcnow()
        return JobResult(
            job_id="e2e-job",
            started_at_utc=started,
            completed_at_utc=completed,
            success=True,
            output_path=str(output_path),
        )

    scheduler = ForecastScheduler()
    cfg = ScheduleConfig(
        job_id="e2e-job",
        trigger_type="interval",
        trigger_args={"seconds": 3600},
    )
    scheduler.schedule_job(cfg, pipeline_callback)

    # Trigger immediately via deterministic test mode.
    result = scheduler.trigger_once("e2e-job")

    assert result.success is True
    assert mock_adapter.send.call_count == 1
    # Verify persistence.
    partition = captured["record"].timestamp_utc.strftime("%Y-%m")
    records = store.read(partition)
    assert len(records) == 1
    assert records[0].forecast_id == "e2e-001"


def test_end_to_end_rule_loader_against_payload(tmp_path: Path) -> None:
    """E2E: load real config/alert_rules.yaml + evaluate against synthetic payload."""
    repo_root = Path(__file__).parent.parent
    rules_path = repo_root / "config" / "alert_rules.yaml"
    if not rules_path.exists():
        pytest.skip("config/alert_rules.yaml not present")

    rules = load_alert_rules(rules_path)
    payload = {
        "confidence": 0.85,
        "reference_class_ood": False,
        "lucas_critique_flag": True,
        "sqrt_t_scaling_warning": False,
        "layer_disagreement_flag": False,
        "ood_reserve_fraction": 0.05,
    }
    # At horizon=1: high_confidence_1y_breach should fire.
    fired_rules = [
        rule.rule_id
        for rule in rules
        if evaluate_rule_against_payload(rule, payload, horizon=1)
    ]
    assert "high_confidence_1y_breach" in fired_rules
    # lucas_critique_flag should fire (horizon-agnostic).
    assert "lucas_critique_flag" in fired_rules


def test_end_to_end_alert_dispatch_failure_isolation() -> None:
    """E2E: one adapter failing doesn't block other adapters."""
    adapter_ok = MagicMock()
    adapter_ok.send.return_value = True
    adapter_fail = MagicMock()
    adapter_fail.send.side_effect = ConnectionError("network down")

    dispatcher = AlertDispatcher(adapters=[adapter_fail, adapter_ok])
    alert = Alert(
        alert_id="x",
        severity=AlertSeverity.WARNING,
        title="t",
        message="m",
        timestamp_utc=_utcnow(),
    )
    results = dispatcher.dispatch(alert)
    # adapter_ok still called despite adapter_fail exception.
    assert adapter_ok.send.call_count == 1
    # 1 success + 1 failure recorded.
    assert sum(results.values()) == 1


def test_end_to_end_persistence_multi_horizon_round_trip(tmp_path: Path) -> None:
    """E2E: persist forecasts for all 4 horizons; round-trip stable."""
    store = ParquetForecastStore(tmp_path)
    now = _utcnow()
    records = []
    for h, pe in [(1, 0.07), (3, 0.065), (5, 0.06), (10, 0.055)]:
        records.append(
            ForecastRecord(
                forecast_id=f"f-h{h}",
                timestamp_utc=now,
                horizon=h,
                point_estimate_annualized=pe,
                sigma_annualized=0.15 + 0.01 * h,
                confidence=0.6,
                conviction=5.0,
                code_sha="test",
                metadata_json="{}",
            )
        )
    store.append(records)
    partition = now.strftime("%Y-%m")
    read_back = store.read(partition)
    assert len(read_back) == 4
    assert {r.horizon for r in read_back} == {1, 3, 5, 10}


def test_end_to_end_scheduler_callback_failure_recorded() -> None:
    """E2E: scheduler captures callback exception as failure JobResult."""
    scheduler = ForecastScheduler()

    def failing_callback() -> JobResult:
        raise RuntimeError("simulated pipeline failure")

    cfg = ScheduleConfig(
        job_id="failing-job",
        trigger_type="interval",
        trigger_args={"seconds": 60},
    )
    scheduler.schedule_job(cfg, failing_callback)
    result = scheduler.trigger_once("failing-job")
    assert result.success is False
    assert "simulated pipeline failure" in (result.error_message or "")
