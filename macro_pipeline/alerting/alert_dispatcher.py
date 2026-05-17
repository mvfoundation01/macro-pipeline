"""L7 D2 — Alert dataclass + dispatcher with pluggable-adapter pattern.

Per Strategic L7 pre-flight 2026-05-16. AlertDispatcher routes alerts
to a list of adapters (email, Slack, webhook); per-adapter failure
isolated (one adapter raising does NOT block others).

Design discipline:
- Frozen ``Alert`` dataclass (immutable; AP-AUTH-56 invariant pattern)
- ``AlertSeverity`` enum (info / warning / critical) — controlled vocabulary
- Adapter Protocol (duck-typed; any object with ``send(alert) -> bool``)
- Per-adapter exception handling (no global pipeline disruption from
  one transport failure)
- Dispatch log preserved for audit (Vision §14 replication discipline)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Protocol, Tuple


class AlertSeverity(Enum):
    """Vision §X severity tiers for forecast alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Alert:
    """Forecast alert payload for dispatch.

    Fields
    ------
    alert_id        Unique identifier (caller-generated; e.g., uuid + ts).
    severity        AlertSeverity enum member.
    title           Short headline (subject line for email; title for Slack).
    message         Body text.
    timestamp_utc   Timezone-aware UTC datetime.
    metadata        Free-form dict (horizon, forecast_id, metric_outputs subset).

    Invariants enforced by ``__post_init__``:
      - alert_id non-empty string
      - severity is AlertSeverity instance
      - timestamp_utc timezone-aware
    """

    alert_id: str
    severity: AlertSeverity
    title: str
    message: str
    timestamp_utc: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.alert_id, str) or not self.alert_id:
            raise ValueError(
                f"alert_id must be non-empty string; got {self.alert_id!r}"
            )
        if not isinstance(self.severity, AlertSeverity):
            raise TypeError(
                f"severity must be AlertSeverity enum; got "
                f"{type(self.severity).__name__}"
            )
        if self.timestamp_utc.tzinfo is None:
            raise ValueError("timestamp_utc must be timezone-aware")


class AlertAdapter(Protocol):
    """Protocol for alert dispatch adapters.

    Implementations: ``EmailAdapter``, ``SlackAdapter``, ``WebhookAdapter``
    (in ``macro_pipeline.alerting.adapters``). Custom adapters need only
    implement ``send(alert) -> bool``.
    """

    def send(self, alert: Alert) -> bool:
        """Send alert; return True on success, False on failure.

        Implementations MUST NOT raise on transient failure (e.g.,
        network timeout); catch and return False instead. Raising is
        reserved for genuine programming errors.
        """
        ...


class AlertDispatcher:
    """Dispatches alerts to configured adapters; per-adapter failure isolated.

    Usage
    -----
    >>> dispatcher = AlertDispatcher([EmailAdapter(...), SlackAdapter(...)])
    >>> results = dispatcher.dispatch(alert)
    >>> # {"EmailAdapter": True, "SlackAdapter": False}
    """

    def __init__(self, adapters: List[AlertAdapter]) -> None:
        if not adapters:
            raise ValueError("at least one adapter required")
        self._adapters = list(adapters)
        self._dispatch_log: List[Tuple[Alert, str, bool]] = []

    def dispatch(self, alert: Alert) -> Dict[str, bool]:
        """Dispatch alert to all adapters.

        Returns dict mapping adapter class name to success bool. Per-
        adapter exceptions are caught + logged as False (not raised).
        """
        results: Dict[str, bool] = {}
        for adapter in self._adapters:
            adapter_name = type(adapter).__name__
            try:
                success = adapter.send(alert)
                if not isinstance(success, bool):
                    success = False  # adapter returned non-bool; treat as fail
            except Exception:
                success = False
            self._dispatch_log.append((alert, adapter_name, success))
            results[adapter_name] = success
        return results

    @property
    def dispatch_log(self) -> Tuple[Tuple[Alert, str, bool], ...]:
        """Immutable view of dispatch history."""
        return tuple(self._dispatch_log)

    @property
    def adapter_count(self) -> int:
        return len(self._adapters)
