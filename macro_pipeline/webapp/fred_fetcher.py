"""L12 v2 D7 — FRED API auto-fetcher with graceful no-key fallback.

V's L12 v2 form replaces 3 of the 8 manual fields (UNRATE, PAYEMS MoM,
FEDFUNDS) with auto-fetched values from FRED. The fetcher MUST:

* read ``FRED_API_KEY`` from the environment (loaded via python-dotenv at
  ``macro_pipeline.config`` import time);
* degrade gracefully when the key is missing — the form then renders the
  three fields as manual inputs;
* cache the most recent observation per series (1-hour TTL) so a typical
  V session of "load form / fill manual / submit" hits the FRED API at
  most 3 times per hour;
* never raise — every failure path returns ``(None, None)`` so the route
  layer can render the manual-entry fallback without exception handling.

Public API
----------
``FetchResult``    Frozen ``(value, as_of)`` pair (both ``None`` on failure).
``FREDFetcher``    Reads the env key, caches per-series, handles failures.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchResult:
    """Outcome of a single FRED call."""

    value: float | None
    as_of: str | None  # YYYY-MM-DD or None

    @classmethod
    def empty(cls) -> FetchResult:
        return cls(value=None, as_of=None)

    @property
    def ok(self) -> bool:
        return self.value is not None


# 1-hour cache TTL: FRED publishes monthly series; refreshing more often
# wastes API quota without any data-quality benefit. Daily series (FEDFUNDS)
# still benefit from caching within a single V session.
_CACHE_TTL_SECONDS: float = 3600.0


class FREDFetcher:
    """Fetches the latest observation of selected FRED series.

    Series IDs used (Vision §3 anchored):
      * UNRATE    — civilian unemployment rate, %
      * PAYEMS    — total nonfarm employment, thousands (we compute MoM Δ)
      * FEDFUNDS  — effective federal funds rate, %

    Construction is cheap; instantiate per-request and let the cache hand-off
    work via the module-level ``_LATEST_CACHE`` dict.
    """

    SERIES_UNRATE = "UNRATE"
    SERIES_PAYEMS = "PAYEMS"
    SERIES_FEDFUNDS = "FEDFUNDS"

    def __init__(self, api_key: str | None = None) -> None:
        """``api_key`` overrides the ``FRED_API_KEY`` env var (mainly for tests)."""
        self._api_key = api_key if api_key is not None else os.environ.get("FRED_API_KEY")
        self._fred: Any | None = None  # lazily imported; fredapi pulls in pandas
        if self._api_key:
            try:
                from fredapi import Fred
                self._fred = Fred(api_key=self._api_key)
            except Exception:
                log.exception("FRED client construction failed")
                self._fred = None

    @property
    def available(self) -> bool:
        """True iff we have a key + a working client (caller renders auto UI)."""
        return self._fred is not None

    # ------------------------------------------------------------------
    # Public fetchers (one per series consumed by the L12 v2 form)
    # ------------------------------------------------------------------
    def fetch_unrate(self) -> FetchResult:
        return self._fetch_latest(self.SERIES_UNRATE)

    def fetch_fed_funds(self) -> FetchResult:
        return self._fetch_latest(self.SERIES_FEDFUNDS)

    def fetch_payrolls_mom(self) -> FetchResult:
        """Latest PAYEMS month-over-month CHANGE in thousands (matches V's
        form semantics: ``payrolls_mom`` = headline NFP print)."""
        if not self.available:
            return FetchResult.empty()
        cache_key = (self.SERIES_PAYEMS, "mom")
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            series = self._fred.get_series(self.SERIES_PAYEMS)
            if series is None or len(series) < 2:
                return _cache_set(cache_key, FetchResult.empty())
            mom = float(series.iloc[-1] - series.iloc[-2])
            as_of = series.index[-1].strftime("%Y-%m-%d")
            return _cache_set(cache_key, FetchResult(value=mom, as_of=as_of))
        except Exception:
            log.exception("fetch_payrolls_mom failed")
            return _cache_set(cache_key, FetchResult.empty())

    def fetch_all_form_fields(self) -> dict[str, FetchResult]:
        """Convenience: fetch every series the L12 v2 form auto-fills.

        Keys line up with the form ``name`` attributes so the template can
        ``{{ auto_fetched.unemployment_rate.value }}`` directly.
        """
        return {
            "unemployment_rate": self.fetch_unrate(),
            "payrolls_mom": self.fetch_payrolls_mom(),
            "fed_funds_rate": self.fetch_fed_funds(),
        }

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _fetch_latest(self, series_id: str) -> FetchResult:
        """Latest single observation of ``series_id``. Cached + failure-safe."""
        if not self.available:
            return FetchResult.empty()
        cache_key = (series_id, "latest")
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            series = self._fred.get_series(series_id)
            if series is None or len(series) == 0:
                return _cache_set(cache_key, FetchResult.empty())
            value = float(series.iloc[-1])
            as_of = series.index[-1].strftime("%Y-%m-%d")
            return _cache_set(cache_key, FetchResult(value=value, as_of=as_of))
        except Exception:
            log.exception("_fetch_latest(%s) failed", series_id)
            return _cache_set(cache_key, FetchResult.empty())


# ---------------------------------------------------------------------------
# Module-level TTL cache (per-process). Threadsafe enough for Flask's default
# threaded server — concurrent reads/writes can produce a duplicate fetch in
# the rare race window, which is harmless.
# ---------------------------------------------------------------------------
_LATEST_CACHE: dict[tuple[str, str], tuple[float, FetchResult]] = {}


def _cache_get(key: tuple[str, str]) -> FetchResult | None:
    entry = _LATEST_CACHE.get(key)
    if entry is None:
        return None
    stored_at, value = entry
    if (time.time() - stored_at) > _CACHE_TTL_SECONDS:
        _LATEST_CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: tuple[str, str], value: FetchResult) -> FetchResult:
    _LATEST_CACHE[key] = (time.time(), value)
    return value


def _cache_clear() -> None:
    """Test helper: nuke the cache so a subsequent fetch goes through."""
    _LATEST_CACHE.clear()
