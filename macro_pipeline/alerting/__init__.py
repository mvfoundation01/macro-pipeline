"""L7 alerting module — pluggable adapter pattern for forecast alerts.

Per Strategic L7 single-sub-phase pre-flight 2026-05-16
(ACCELERATION PROTOCOL v1.0). L6-K D7 stub replaced with full
implementation at L7 D2.

Public API
----------
``Alert``               Frozen alert payload dataclass.
``AlertSeverity``       Enum (info / warning / critical).
``AlertAdapter``        Protocol for dispatch adapters.
``AlertDispatcher``     Routes alerts to adapter list; per-adapter failure isolated.
``EmailAdapter``        smtplib-based email dispatch.
``SlackAdapter``        Slack Incoming Webhook via ``requests``.
``WebhookAdapter``      Generic HTTP webhook for custom integrations.
"""
from __future__ import annotations

from .adapters import EmailAdapter, SlackAdapter, WebhookAdapter
from .alert_dispatcher import (
    Alert,
    AlertAdapter,
    AlertDispatcher,
    AlertSeverity,
)
from .rule_loader import (
    EQUALITY_OPERATORS,
    NUMERIC_OPERATORS,
    VALID_ADAPTER_NAMES,
    VALID_OPERATORS,
    AlertRule,
    AlertRuleTrigger,
    evaluate_rule_against_payload,
    load_alert_rules,
)

__all__ = [
    "Alert",
    "AlertAdapter",
    "AlertDispatcher",
    "AlertRule",
    "AlertRuleTrigger",
    "AlertSeverity",
    "EQUALITY_OPERATORS",
    "EmailAdapter",
    "NUMERIC_OPERATORS",
    "SlackAdapter",
    "VALID_ADAPTER_NAMES",
    "VALID_OPERATORS",
    "WebhookAdapter",
    "evaluate_rule_against_payload",
    "load_alert_rules",
]
