"""L7 D2 — Alert dispatch adapters (email, Slack, webhook).

Each adapter implements the ``AlertAdapter`` protocol (``send(alert) -> bool``).
All return False on transient failure; never raise on network errors.

Test discipline:
- Tests MUST mock ``smtplib.SMTP`` and ``requests.post`` via
  ``unittest.mock``. No real network calls in test suite.
- Credential handling: env vars (recommended) or constructor args.
  No credentials checked into repo or test fixtures.
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from typing import Dict, List, Optional

import requests

from macro_pipeline.alerting.alert_dispatcher import Alert


class EmailAdapter:
    """SMTP-based email adapter.

    Constructor params
    ------------------
    smtp_host       SMTP server hostname.
    smtp_port       SMTP server port (typically 587 for STARTTLS).
    sender          From-address email.
    recipients      List of to-address emails.
    username        Optional SMTP auth username.
    password        Optional SMTP auth password.
    use_starttls    Default True; only honored when username+password set.
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        sender: str,
        recipients: List[str],
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_starttls: bool = True,
    ) -> None:
        if not smtp_host:
            raise ValueError("smtp_host required")
        if not (0 < smtp_port < 65536):
            raise ValueError(f"smtp_port out of range: {smtp_port}")
        if not sender:
            raise ValueError("sender required")
        if not recipients:
            raise ValueError("recipients list cannot be empty")
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender = sender
        self.recipients = list(recipients)
        self.username = username
        self.password = password
        self.use_starttls = use_starttls

    def send(self, alert: Alert) -> bool:
        """Send alert via SMTP. Returns False on any transport error."""
        try:
            msg = MIMEText(
                f"{alert.message}\n\nMetadata: {alert.metadata}\n"
                f"Timestamp (UTC): {alert.timestamp_utc.isoformat()}\n"
                f"Alert ID: {alert.alert_id}"
            )
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.recipients)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.username and self.password:
                    if self.use_starttls:
                        server.starttls()
                    server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception:
            return False


# Slack severity → color mapping per Slack attachment convention.
_SLACK_COLOR_BY_SEVERITY: Dict[str, str] = {
    "info": "good",       # green
    "warning": "warning", # yellow
    "critical": "danger", # red
}


class SlackAdapter:
    """Slack Incoming Webhook adapter (uses ``requests``, no slack_sdk).

    Constructor params
    ------------------
    webhook_url     Slack Incoming Webhook URL (sensitive; from env var).
    timeout         HTTP timeout seconds; default 10.
    """

    def __init__(self, webhook_url: str, timeout: float = 10.0) -> None:
        if not webhook_url:
            raise ValueError("webhook_url required")
        if timeout <= 0:
            raise ValueError(f"timeout must be positive; got {timeout}")
        self.webhook_url = webhook_url
        self.timeout = timeout

    def send(self, alert: Alert) -> bool:
        """Post alert to Slack via webhook. Returns False on non-200 response."""
        try:
            color = _SLACK_COLOR_BY_SEVERITY.get(
                alert.severity.value, "good"
            )
            payload = {
                "text": f"*[{alert.severity.value.upper()}]* {alert.title}",
                "attachments": [
                    {
                        "text": alert.message,
                        "color": color,
                        "ts": int(alert.timestamp_utc.timestamp()),
                        "fields": [
                            {
                                "title": str(k),
                                "value": str(v),
                                "short": True,
                            }
                            for k, v in alert.metadata.items()
                        ],
                    }
                ],
            }
            response = requests.post(
                self.webhook_url, json=payload, timeout=self.timeout
            )
            return response.status_code == 200
        except Exception:
            return False


class WebhookAdapter:
    """Generic HTTP webhook adapter for custom integrations.

    Constructor params
    ------------------
    url         Webhook target URL.
    headers     Optional HTTP headers dict (e.g., {"Authorization": "Bearer xxx"}).
    timeout     HTTP timeout seconds; default 10.
    """

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> None:
        if not url:
            raise ValueError("url required")
        if timeout <= 0:
            raise ValueError(f"timeout must be positive; got {timeout}")
        self.url = url
        self.headers = dict(headers) if headers else {}
        self.timeout = timeout

    def send(self, alert: Alert) -> bool:
        """POST JSON payload to webhook. Returns True on 2xx response."""
        try:
            payload = {
                "alert_id": alert.alert_id,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "timestamp_utc": alert.timestamp_utc.isoformat(),
                "metadata": alert.metadata,
            }
            response = requests.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout,
            )
            return 200 <= response.status_code < 300
        except Exception:
            return False
