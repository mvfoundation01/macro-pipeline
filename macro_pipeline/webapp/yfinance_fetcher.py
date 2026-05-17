"""L12 v2 D8 — Yahoo Finance auto-fetcher for ^GSPC.

V's L12 v2 form replaces the manual ``sp500_current`` field with the latest
close from ``yfinance``. Same contract as ``FREDFetcher``: graceful
degradation, never raises, returns ``FetchResult.empty()`` on any failure.

Cache TTL is 15 minutes — equity prices change continuously during market
hours, but a 15-minute snapshot is plenty for a form-render context.

Public API
----------
``YahooFetcher``   Fetches latest ^GSPC close, cached.
"""
from __future__ import annotations

import logging
import time

from macro_pipeline.webapp.fred_fetcher import FetchResult

log = logging.getLogger(__name__)

_CACHE_TTL_SECONDS: float = 900.0  # 15 minutes
_CACHE: dict[str, tuple[float, FetchResult]] = {}


class YahooFetcher:
    """Fetches latest spot close for a Yahoo ticker (default ``^GSPC``)."""

    DEFAULT_TICKER = "^GSPC"

    def __init__(self, ticker: str | None = None) -> None:
        self.ticker = ticker or self.DEFAULT_TICKER

    def fetch_sp500(self) -> FetchResult:
        return self._fetch_ticker(self.ticker)

    def fetch_all_form_fields(self) -> dict[str, FetchResult]:
        """Convenience pair to ``FREDFetcher.fetch_all_form_fields()``."""
        return {"sp500_current": self.fetch_sp500()}

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _fetch_ticker(self, ticker: str) -> FetchResult:
        cached = _cache_get(ticker)
        if cached is not None:
            return cached
        try:
            import yfinance as yf  # lazy import: heavy + network-aware

            t = yf.Ticker(ticker)
            # ``history`` returns a DataFrame; ``period="5d"`` covers the
            # weekend-then-Monday gap so we always get at least one close.
            hist = t.history(period="5d")
            if hist is None or len(hist) == 0 or "Close" not in hist.columns:
                return _cache_set(ticker, FetchResult.empty())
            close = float(hist["Close"].iloc[-1])
            as_of = hist.index[-1].strftime("%Y-%m-%d")
            return _cache_set(ticker, FetchResult(value=close, as_of=as_of))
        except Exception:
            log.exception("YahooFetcher fetch failed for %s", ticker)
            return _cache_set(ticker, FetchResult.empty())


# ---------------------------------------------------------------------------
# Module-level TTL cache
# ---------------------------------------------------------------------------
def _cache_get(key: str) -> FetchResult | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    stored_at, value = entry
    if (time.time() - stored_at) > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: FetchResult) -> FetchResult:
    _CACHE[key] = (time.time(), value)
    return value


def _cache_clear() -> None:
    """Test helper."""
    _CACHE.clear()
