"""L7 D2 + D6 tests — alerting module + rule loader."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from macro_pipeline.alerting import (
    Alert,
    AlertDispatcher,
    AlertRule,
    AlertRuleTrigger,
    AlertSeverity,
    EmailAdapter,
    SlackAdapter,
    VALID_ADAPTER_NAMES,
    VALID_OPERATORS,
    WebhookAdapter,
    evaluate_rule_against_payload,
    load_alert_rules,
)


# ===========================================================================
# Alert dataclass
# ===========================================================================


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def test_alert_construction_valid() -> None:
    """POS: valid Alert constructs."""
    a = Alert(
        alert_id="x1",
        severity=AlertSeverity.INFO,
        title="Title",
        message="Body",
        timestamp_utc=_utcnow(),
        metadata={"horizon": 1},
    )
    assert a.alert_id == "x1"
    assert a.severity == AlertSeverity.INFO


def test_alert_empty_id_raises() -> None:
    """NEG: empty alert_id raises ValueError."""
    with pytest.raises(ValueError, match="alert_id"):
        Alert(
            alert_id="",
            severity=AlertSeverity.INFO,
            title="t", message="m",
            timestamp_utc=_utcnow(),
        )


def test_alert_naive_datetime_raises() -> None:
    """NEG: naive datetime raises ValueError."""
    with pytest.raises(ValueError, match="timezone-aware"):
        Alert(
            alert_id="x",
            severity=AlertSeverity.INFO,
            title="t", message="m",
            timestamp_utc=datetime(2026, 5, 16),
        )


def test_alert_invalid_severity_type_raises() -> None:
    """NEG: severity must be AlertSeverity enum."""
    with pytest.raises(TypeError, match="severity"):
        Alert(
            alert_id="x",
            severity="info",  # type: ignore[arg-type]
            title="t", message="m",
            timestamp_utc=_utcnow(),
        )


# ===========================================================================
# AlertDispatcher
# ===========================================================================


def test_dispatcher_routes_to_all_adapters() -> None:
    """POS-inv: dispatcher routes to all adapters; returns per-adapter results."""
    adapter1 = MagicMock()
    adapter1.send.return_value = True
    adapter1.__class__.__name__ = "Adapter1"
    adapter2 = MagicMock()
    adapter2.send.return_value = False
    adapter2.__class__.__name__ = "Adapter2"

    dispatcher = AlertDispatcher([adapter1, adapter2])
    alert = Alert(
        alert_id="x", severity=AlertSeverity.WARNING,
        title="t", message="m", timestamp_utc=_utcnow(),
    )
    results = dispatcher.dispatch(alert)
    assert len(results) == 2
    assert adapter1.send.call_count == 1
    assert adapter2.send.call_count == 1


def test_dispatcher_adapter_exception_isolated() -> None:
    """POS-inv: adapter exception doesn't block other adapters."""
    adapter1 = MagicMock()
    adapter1.send.side_effect = RuntimeError("network down")
    adapter2 = MagicMock()
    adapter2.send.return_value = True

    dispatcher = AlertDispatcher([adapter1, adapter2])
    alert = Alert(
        alert_id="x", severity=AlertSeverity.INFO,
        title="t", message="m", timestamp_utc=_utcnow(),
    )
    results = dispatcher.dispatch(alert)
    # adapter2 still called despite adapter1 failure.
    assert adapter2.send.call_count == 1
    # 1 success + 1 failure recorded.
    assert sum(results.values()) == 1


def test_dispatcher_empty_adapters_raises() -> None:
    """NEG: empty adapters list raises ValueError."""
    with pytest.raises(ValueError, match="at least one adapter"):
        AlertDispatcher([])


def test_dispatcher_log_captures_history() -> None:
    """POS: dispatch_log accumulates per-call records."""
    adapter = MagicMock()
    adapter.send.return_value = True
    dispatcher = AlertDispatcher([adapter])
    alert = Alert(
        alert_id="x", severity=AlertSeverity.INFO,
        title="t", message="m", timestamp_utc=_utcnow(),
    )
    dispatcher.dispatch(alert)
    dispatcher.dispatch(alert)
    assert len(dispatcher.dispatch_log) == 2


# ===========================================================================
# Adapters (mocked transport)
# ===========================================================================


def test_email_adapter_construction_validates() -> None:
    """NEG: invalid construction args raise."""
    with pytest.raises(ValueError, match="smtp_host"):
        EmailAdapter(smtp_host="", smtp_port=587, sender="a@b", recipients=["c@d"])
    with pytest.raises(ValueError, match="smtp_port"):
        EmailAdapter(smtp_host="x", smtp_port=99999, sender="a@b", recipients=["c@d"])
    with pytest.raises(ValueError, match="recipients"):
        EmailAdapter(smtp_host="x", smtp_port=587, sender="a@b", recipients=[])


def test_email_adapter_send_success_mocked() -> None:
    """POS: send returns True on mocked SMTP success."""
    adapter = EmailAdapter(
        smtp_host="smtp.example.com", smtp_port=587,
        sender="a@b.com", recipients=["c@d.com"],
    )
    alert = Alert(
        alert_id="x", severity=AlertSeverity.INFO,
        title="t", message="m", timestamp_utc=_utcnow(),
    )
    with patch("macro_pipeline.alerting.adapters.smtplib.SMTP") as mock_smtp:
        ctx = MagicMock()
        mock_smtp.return_value.__enter__.return_value = ctx
        assert adapter.send(alert) is True


def test_email_adapter_send_failure_mocked() -> None:
    """POS: send returns False on mocked exception."""
    adapter = EmailAdapter(
        smtp_host="smtp.example.com", smtp_port=587,
        sender="a@b.com", recipients=["c@d.com"],
    )
    alert = Alert(
        alert_id="x", severity=AlertSeverity.INFO,
        title="t", message="m", timestamp_utc=_utcnow(),
    )
    with patch(
        "macro_pipeline.alerting.adapters.smtplib.SMTP",
        side_effect=ConnectionError("blocked"),
    ):
        assert adapter.send(alert) is False


def test_slack_adapter_send_success_mocked() -> None:
    """POS: SlackAdapter returns True on mocked 200 response."""
    adapter = SlackAdapter(webhook_url="https://hooks.slack.com/X")
    alert = Alert(
        alert_id="x", severity=AlertSeverity.CRITICAL,
        title="t", message="m", timestamp_utc=_utcnow(),
    )
    with patch(
        "macro_pipeline.alerting.adapters.requests.post"
    ) as mock_post:
        mock_post.return_value.status_code = 200
        assert adapter.send(alert) is True


def test_slack_adapter_send_failure_mocked() -> None:
    """POS: SlackAdapter returns False on mocked 500 response."""
    adapter = SlackAdapter(webhook_url="https://hooks.slack.com/X")
    alert = Alert(
        alert_id="x", severity=AlertSeverity.WARNING,
        title="t", message="m", timestamp_utc=_utcnow(),
    )
    with patch(
        "macro_pipeline.alerting.adapters.requests.post"
    ) as mock_post:
        mock_post.return_value.status_code = 500
        assert adapter.send(alert) is False


def test_webhook_adapter_send_success_mocked() -> None:
    """POS: WebhookAdapter returns True on 2xx response."""
    adapter = WebhookAdapter(url="https://example.com/hook")
    alert = Alert(
        alert_id="x", severity=AlertSeverity.INFO,
        title="t", message="m", timestamp_utc=_utcnow(),
        metadata={"k": "v"},
    )
    with patch(
        "macro_pipeline.alerting.adapters.requests.post"
    ) as mock_post:
        mock_post.return_value.status_code = 201
        assert adapter.send(alert) is True


# ===========================================================================
# D6 — AlertRule + loader + evaluator
# ===========================================================================


def test_alert_rule_construction_valid() -> None:
    """POS: valid AlertRule constructs."""
    trigger = AlertRuleTrigger(
        field="confidence", operator=">", threshold=0.8, horizon=1
    )
    rule = AlertRule(
        rule_id="r1", description="d",
        trigger=trigger,
        severity=AlertSeverity.CRITICAL,
        adapters=["email"],
    )
    assert rule.rule_id == "r1"


def test_alert_rule_trigger_unknown_operator_raises() -> None:
    """NEG: unknown operator raises ValueError."""
    with pytest.raises(ValueError, match="trigger.operator"):
        AlertRuleTrigger(field="x", operator="LIKE", threshold=0.5)


def test_alert_rule_invalid_adapter_raises() -> None:
    """NEG: unknown adapter name raises ValueError."""
    trigger = AlertRuleTrigger(field="x", operator="==", value=True)
    with pytest.raises(ValueError, match="adapter"):
        AlertRule(
            rule_id="r", description="d",
            trigger=trigger,
            severity=AlertSeverity.INFO,
            adapters=["bogus_adapter"],
        )


def test_load_alert_rules_actual_file() -> None:
    """POS: load the in-repo config/alert_rules.yaml."""
    repo_root = Path(__file__).parent.parent
    rules_path = repo_root / "config" / "alert_rules.yaml"
    if not rules_path.exists():
        pytest.skip("config/alert_rules.yaml not present in this clone")
    rules = load_alert_rules(rules_path)
    assert len(rules) >= 1
    for r in rules:
        assert isinstance(r, AlertRule)


def test_load_alert_rules_missing_file_raises() -> None:
    """NEG: missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_alert_rules(Path("/nonexistent/alert_rules.yaml"))


def test_evaluate_rule_threshold_breach() -> None:
    """POS-inv: rule fires when payload value exceeds threshold."""
    trigger = AlertRuleTrigger(
        field="confidence", operator=">", threshold=0.8, horizon=1
    )
    rule = AlertRule(
        rule_id="r1", description="d", trigger=trigger,
        severity=AlertSeverity.CRITICAL, adapters=["email"],
    )
    assert evaluate_rule_against_payload(
        rule, {"confidence": 0.85}, horizon=1
    ) is True
    assert evaluate_rule_against_payload(
        rule, {"confidence": 0.75}, horizon=1
    ) is False


def test_evaluate_rule_horizon_mismatch_skips() -> None:
    """POS-inv: rule with horizon=1 doesn't fire when evaluating horizon=5."""
    trigger = AlertRuleTrigger(
        field="confidence", operator=">", threshold=0.8, horizon=1
    )
    rule = AlertRule(
        rule_id="r1", description="d", trigger=trigger,
        severity=AlertSeverity.CRITICAL, adapters=["email"],
    )
    assert evaluate_rule_against_payload(
        rule, {"confidence": 0.95}, horizon=5
    ) is False


def test_evaluate_rule_equality_value() -> None:
    """POS-inv: equality rule with value field."""
    trigger = AlertRuleTrigger(
        field="reference_class_ood", operator="==", value=True
    )
    rule = AlertRule(
        rule_id="r2", description="d", trigger=trigger,
        severity=AlertSeverity.WARNING, adapters=["slack"],
    )
    assert evaluate_rule_against_payload(
        rule, {"reference_class_ood": True}
    ) is True
    assert evaluate_rule_against_payload(
        rule, {"reference_class_ood": False}
    ) is False


def test_evaluate_rule_field_missing_returns_false() -> None:
    """POS-inv: missing field in payload → rule doesn't fire."""
    trigger = AlertRuleTrigger(
        field="missing_field", operator=">", threshold=0.5
    )
    rule = AlertRule(
        rule_id="r3", description="d", trigger=trigger,
        severity=AlertSeverity.INFO, adapters=["webhook"],
    )
    assert evaluate_rule_against_payload(rule, {}) is False


def test_valid_operators_constant() -> None:
    """POS: VALID_OPERATORS contains expected operators."""
    assert ">" in VALID_OPERATORS
    assert "==" in VALID_OPERATORS
    assert len(VALID_OPERATORS) == 6


def test_valid_adapter_names_constant() -> None:
    """POS: VALID_ADAPTER_NAMES contains the 3 default adapters."""
    assert VALID_ADAPTER_NAMES == frozenset({"email", "slack", "webhook"})
