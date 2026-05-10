"""Typed indicator-load exceptions (Layer 1.5D.1).

Codex review MEDIUM: error handling is currently untyped — every loader
catches ``ValueError`` / ``ConnectionError`` / ``Exception`` blanket and
hides the failure mode under a generic message. That's fine for ad-hoc
runs but makes Layer 5 retry logic and Layer 6 incident reporting
guess-work.

Hierarchy
---------
    IndicatorLoadError              base, never raised directly
        IndicatorAuthError          401/403, missing FRED_API_KEY, expired token
        IndicatorNotFoundError      404, missing series, missing local file
        IndicatorRateLimitError     429, FRED throttle, Yahoo throttle
        IndicatorParseError         XLS/CSV/JSON schema mismatch, header drift
        IndicatorNetworkError       timeout, connection refused, DNS fail

Every subclass carries:
    indicator_id        the bare indicator id (or FRED series id at the
                        boundary if the alias hasn't been resolved yet)
    source              the source string from IndicatorMetadata
                        (e.g. ``"FRED_API"``, ``"YAHOO_FINANCE"``)
    original_exception  the underlying exception (requests.HTTPError,
                        json.JSONDecodeError, etc.) so callers that want
                        to inspect it can
    context             open dict for arbitrary extra fields
                        (e.g. ``{"http_status": 429, "url": "..."}``)
    recoverable         True when the failure is transient and a retry
                        could plausibly succeed (rate limit / network)

Catch ``IndicatorLoadError`` to handle every flavor uniformly; catch a
specific subclass when the call site has a specific recovery strategy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndicatorLoadError(Exception):
    """Base class for typed loader failures."""

    indicator_id: str
    source: str
    reason: str = ""
    recoverable: bool = False
    original_exception: BaseException | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Initialise the Exception base with a useful str() so plain
        # ``raise`` / ``logging.exception`` produce readable output.
        super().__init__(str(self))

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        parts = [f"[{self.source}/{self.indicator_id}]"]
        if self.reason:
            parts.append(self.reason)
        if self.context:
            parts.append(f"context={self.context}")
        if self.original_exception is not None:
            parts.append(f"caused by {type(self.original_exception).__name__}: "
                         f"{self.original_exception}")
        return " ".join(parts)


@dataclass
class IndicatorAuthError(IndicatorLoadError):
    """401/403 — bad credentials or missing API key. NOT recoverable."""
    reason: str = "Authentication failed"
    recoverable: bool = False


@dataclass
class IndicatorNotFoundError(IndicatorLoadError):
    """404 — series/file does not exist. NOT recoverable."""
    reason: str = "Series or file not found"
    recoverable: bool = False


@dataclass
class IndicatorRateLimitError(IndicatorLoadError):
    """429 — rate limited. Recoverable with backoff."""
    reason: str = "Rate limited"
    recoverable: bool = True


@dataclass
class IndicatorParseError(IndicatorLoadError):
    """XLS / CSV / JSON schema mismatch or header drift. NOT recoverable."""
    reason: str = "Parse / schema mismatch"
    recoverable: bool = False


@dataclass
class IndicatorNetworkError(IndicatorLoadError):
    """Timeout / connection refused / DNS failure. Recoverable with retry."""
    reason: str = "Network failure"
    recoverable: bool = True


def from_request_exception(
    exc: BaseException, *, indicator_id: str, source: str,
    extra_context: dict | None = None,
) -> IndicatorLoadError:
    """Convert an HTTP / network exception into the right typed subclass.

    Handles ``requests.HTTPError`` by status code (401/403 -> Auth,
    404 -> NotFound, 429 -> RateLimit, other -> Network) and any other
    transport-level exception as Network. Anything unrecognized becomes
    a plain ``IndicatorLoadError`` so the caller can still catch the
    base type.
    """
    # Local import: requests is already a dependency, but keeping the
    # import inside the function makes the exceptions module importable
    # in environments that don't have requests installed (e.g. minimal
    # test runs).
    import requests

    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        ctx: dict[str, Any] = {"http_status": status}
        if extra_context:
            ctx.update(extra_context)
        if status in (401, 403):
            return IndicatorAuthError(
                indicator_id=indicator_id, source=source,
                original_exception=exc, context=ctx,
            )
        if status == 404:
            return IndicatorNotFoundError(
                indicator_id=indicator_id, source=source,
                original_exception=exc, context=ctx,
            )
        if status == 429:
            return IndicatorRateLimitError(
                indicator_id=indicator_id, source=source,
                original_exception=exc, context=ctx,
            )
        return IndicatorNetworkError(
            indicator_id=indicator_id, source=source,
            original_exception=exc, context=ctx,
        )

    if isinstance(exc, (ConnectionError, TimeoutError,
                         requests.ConnectionError, requests.Timeout,
                         requests.RequestException)):
        return IndicatorNetworkError(
            indicator_id=indicator_id, source=source,
            original_exception=exc,
            context=extra_context or {},
        )

    return IndicatorLoadError(
        indicator_id=indicator_id, source=source,
        reason=str(exc), original_exception=exc,
        context=extra_context or {},
    )


# ---------------------------------------------------------------------------
# Layer 3.5B — PIT contract enforcement (cross-cutting, not regime-scoped).
# ---------------------------------------------------------------------------
@dataclass
class PitContractViolationError(Exception):
    """Raised when a series with ``vintage=True`` (or its successor flag)
    is requested in PIT mode but is neither (a) materialised in
    ``VINTAGE_REQUIRED_SERIES`` nor (b) flagged
    ``pit_safe_by_construction=True`` in ``FRED_SERIES_API``.

    Layer 3.5B closes the prior silent fallback path that returned a
    latest-cache slice with ``pit_safe=True``. After 3.5B every series
    that can reach the PIT reader has an explicit disposition; an
    unflagged vintage series is a configuration bug and must fail closed.

    Per Codex finding B + ChatGPT Dim 1 + cross-reviewer aggregation
    finding #2 (look-ahead bias in walk-forward CV).
    """

    indicator_id: str
    reason: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(str(self))

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        parts = [f"[PIT/{self.indicator_id}]"]
        if self.reason:
            parts.append(self.reason)
        if self.context:
            parts.append(f"context={self.context}")
        return " ".join(parts)


__all__ = [
    "IndicatorAuthError",
    "IndicatorLoadError",
    "IndicatorNetworkError",
    "IndicatorNotFoundError",
    "IndicatorParseError",
    "IndicatorRateLimitError",
    "PitContractViolationError",
    "from_request_exception",
]
