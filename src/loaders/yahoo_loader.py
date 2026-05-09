"""Yahoo Finance loader (Build guide Phase 3).

Pulls 25 series via yfinance. The 3 broad-market indices (SPX, NDX, RUT)
are loaded TWICE - once each as ``_PRICE`` (``auto_adjust=False``, suitable
for drawdown / threshold / above-MA tests) and ``_TR`` (``auto_adjust=True``,
suitable for total-return regression and forward-return calculation).

CAVEAT - auto_adjust on price indices: yfinance's ``auto_adjust=True``
applies split- and dividend-based back-adjustment to the ``Close`` column.
For PRICE INDICES (^GSPC, ^NDX, ^RUT) the dividend stream is not embedded
in the ticker, so the adjustment factor is 1 - ``_PRICE`` and ``_TR``
return numerically IDENTICAL data. The dual-series structure exists for
semantic labelling (``use_for`` metadata) so downstream code can
self-document its intent. For true S&P 500 total return, use Shiller's
TR_CAPE from ``ie_data.xls`` (Phase 4 official loader).

For dividend-paying ETFs (sector ETFs, RSP) auto_adjust does meaningfully
back-adjust historical prices.

Naming convention: when a series name collides with another loader source
(e.g. TV CSV's ``VIX``), the Yahoo entry is suffixed ``_YAHOO``. Otherwise
the bare indicator id is used.

Tier: 3 (unofficial; Yahoo is not authoritative). ``^MOVE`` is unofficial
even within Yahoo - on fetch failure we fall back to the most recent cached
snapshot rather than crashing.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import DATA_CACHE
from src.loaders.base import IndicatorMetadata, Loader
from src.preprocessing import cache_series_to_parquet, run_universal_pipeline

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registry: indicator_id -> spec
# ---------------------------------------------------------------------------
# Each entry maps a final indicator_id (the parquet column name) to the
# underlying yahoo_ticker plus auto_adjust mode. ``use_for`` lists
# downstream contexts where the series is appropriate.
YAHOO_REGISTRY: dict[str, dict] = {
    # === Equity indices: dual price-and-TR ===
    "SPX_PRICE": {
        "yahoo_ticker": "^GSPC",
        "auto_adjust": False,
        "freq": "D", "unit": "index",
        "expected_min": 50, "expected_max": 1e5,
        "category": "equity_index",
        "use_for": ["drawdown", "threshold_check", "above_below_MA"],
        "description": "S&P 500 price index (Yahoo, auto_adjust=False)",
    },
    "SPX_TR": {
        "yahoo_ticker": "^GSPC",
        "auto_adjust": True,
        "freq": "D", "unit": "index",
        # Back-adjusted prices compress 1959-era levels to ~$4.
        "expected_min": 3, "expected_max": 1e5,
        "category": "equity_index",
        "use_for": ["total_return", "r_squared_regression", "forward_return_calc"],
        "description": "S&P 500 total return (Yahoo, auto_adjust=True)",
    },
    "NDX_PRICE": {
        "yahoo_ticker": "^NDX",
        "auto_adjust": False,
        "freq": "D", "unit": "index",
        "expected_min": 50, "expected_max": 1e5,
        "category": "equity_index",
        "use_for": ["drawdown", "threshold_check", "above_below_MA"],
        "description": "Nasdaq 100 price index (auto_adjust=False)",
    },
    "NDX_TR": {
        "yahoo_ticker": "^NDX",
        "auto_adjust": True,
        "freq": "D", "unit": "index",
        "expected_min": 5, "expected_max": 1e5,
        "category": "equity_index",
        "use_for": ["total_return", "r_squared_regression", "forward_return_calc"],
        "description": "Nasdaq 100 total return (auto_adjust=True)",
    },
    "RUT_PRICE": {
        "yahoo_ticker": "^RUT",
        "auto_adjust": False,
        "freq": "D", "unit": "index",
        "expected_min": 50, "expected_max": 1e4,
        "category": "equity_index",
        "use_for": ["drawdown", "threshold_check", "above_below_MA"],
        "description": "Russell 2000 price index (auto_adjust=False)",
    },
    "RUT_TR": {
        "yahoo_ticker": "^RUT",
        "auto_adjust": True,
        "freq": "D", "unit": "index",
        "expected_min": 5, "expected_max": 1e4,
        "category": "equity_index",
        "use_for": ["total_return", "r_squared_regression", "forward_return_calc"],
        "description": "Russell 2000 total return (auto_adjust=True)",
    },

    # === Official S&P 500 Total Return (dividends compounded into level) ===
    "SP500TR": {
        "yahoo_ticker": "^SP500TR",
        "auto_adjust": True,  # already TR; auto_adjust is a no-op
        "freq": "D", "unit": "index",
        # Index started 1988-01-04 around 200; today >16,000 with dividends
        # reinvested. Wide upper bound to allow decades of compounding.
        "expected_min": 100, "expected_max": 1e6,
        "category": "equity_index_tr",
        "expected_first_obs": "1988-01-04",
        "use_for": ["total_return", "r_squared_regression",
                     "forward_return_calc", "daily_tr_benchmark"],
        "description": (
            "S&P 500 Total Return Index (Yahoo). Official TR series with "
            "dividends compounded into the level. Shorter history than "
            "^GSPC (starts 1988); use Shiller TR_PRICE for pre-1988 history."
        ),
    },

    # === Equity ETF (RSP) - single TR series ===
    "RSP": {
        "yahoo_ticker": "RSP",
        "auto_adjust": True,
        "freq": "D", "unit": "index",
        "expected_min": 5, "expected_max": 1000,
        "category": "equity_etf",
        "use_for": ["total_return", "drawdown", "above_below_MA"],
        "description": "Invesco S&P 500 Equal Weight ETF (auto-adjusted)",
    },

    # === Volatility composites ===
    "VIX_YAHOO": {
        # Suffix because TV CSV exposes the same data as bare `VIX`.
        "yahoo_ticker": "^VIX",
        "auto_adjust": True,  # VIX has no dividends, auto_adjust is a no-op
        "freq": "D", "unit": "index",
        "expected_min": 5, "expected_max": 100,
        "category": "volatility",
        "use_for": ["volatility_regime", "vol_term_structure"],
        "description": "Cboe VIX (Yahoo). TV CSV mirror is `VIX`.",
    },
    "VIX3M": {
        "yahoo_ticker": "^VIX3M",
        "auto_adjust": True,
        "freq": "D", "unit": "index",
        "expected_min": 5, "expected_max": 100,
        "category": "volatility",
        "use_for": ["vol_term_structure"],
        "description": "Cboe 3-Month VIX",
    },
    "VVIX": {
        "yahoo_ticker": "^VVIX",
        "auto_adjust": True,
        "freq": "D", "unit": "index",
        "expected_min": 30, "expected_max": 300,
        "category": "volatility",
        "use_for": ["volatility_regime"],
        "description": "Cboe Volatility of VIX",
    },
    "SKEW": {
        "yahoo_ticker": "^SKEW",
        "auto_adjust": True,
        "freq": "D", "unit": "index",
        "expected_min": 100, "expected_max": 200,
        "category": "volatility",
        "use_for": ["tail_risk"],
        "description": "Cboe SKEW (>= 100 by construction)",
    },
    "MOVE": {
        "yahoo_ticker": "^MOVE",
        "auto_adjust": True,
        "freq": "D", "unit": "index",
        "expected_min": 30, "expected_max": 350,
        "category": "volatility",
        "unofficial_yahoo": True,
        "use_for": ["rate_volatility"],
        "description": "ICE BofA MOVE Treasury Volatility (Yahoo unofficial)",
    },

    # === Macro markets ===
    "DXY": {
        "yahoo_ticker": "DX-Y.NYB",
        "auto_adjust": True,
        "freq": "D", "unit": "index",
        "expected_min": 70, "expected_max": 170,
        "category": "fx",
        "use_for": ["dollar_strength"],
        "description": "US Dollar Index (DXY)",
    },
    "GOLD": {
        "yahoo_ticker": "GC=F",
        "auto_adjust": True,
        "freq": "D", "unit": "index",
        "expected_min": 200, "expected_max": 6000,
        "category": "commodity",
        "use_for": ["safe_haven", "real_assets"],
        "description": "Gold continuous futures (CME)",
    },

    # === Sector ETFs (auto-adjusted total return) ===
    "XLK":  {"yahoo_ticker": "XLK",  "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 4, "expected_max": 500, "category": "sector_etf",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Technology Select Sector"},
    "XLF":  {"yahoo_ticker": "XLF",  "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 1, "expected_max": 200, "category": "sector_etf",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Financial Select Sector"},
    "XLV":  {"yahoo_ticker": "XLV",  "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 5, "expected_max": 300, "category": "sector_etf",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Health Care Select Sector"},
    "XLY":  {"yahoo_ticker": "XLY",  "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 5, "expected_max": 300, "category": "sector_etf",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Consumer Discretionary Select Sector"},
    "XLP":  {"yahoo_ticker": "XLP",  "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 5, "expected_max": 200, "category": "sector_etf",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Consumer Staples Select Sector"},
    "XLE":  {"yahoo_ticker": "XLE",  "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 5, "expected_max": 200, "category": "sector_etf",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Energy Select Sector"},
    "XLI":  {"yahoo_ticker": "XLI",  "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 5, "expected_max": 300, "category": "sector_etf",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Industrial Select Sector"},
    "XLB":  {"yahoo_ticker": "XLB",  "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 4, "expected_max": 200, "category": "sector_etf",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Materials Select Sector"},
    "XLU":  {"yahoo_ticker": "XLU",  "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 3, "expected_max": 200, "category": "sector_etf",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Utilities Select Sector"},
    "XLRE": {"yahoo_ticker": "XLRE", "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 5, "expected_max": 200, "category": "sector_etf",
             "expected_first_obs": "2015-10-08",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Real Estate Select Sector (launched 2015-10)"},
    "XLC":  {"yahoo_ticker": "XLC",  "auto_adjust": True, "freq": "D", "unit": "index",
             "expected_min": 5, "expected_max": 200, "category": "sector_etf",
             "expected_first_obs": "2018-06-19",
             "use_for": ["sector_relative_strength"],
             "description": "SPDR Communication Services Select Sector (launched 2018-06)"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cache_paths(indicator_id: str) -> tuple[Path, Path]:
    parquet = DATA_CACHE / f"yahoo_{indicator_id}.parquet"
    sidecar = DATA_CACHE / f"yahoo_{indicator_id}.meta.json"
    return parquet, sidecar


def _is_cache_fresh(parquet: Path, ttl_days: float = 1.0) -> bool:
    if not parquet.exists():
        return False
    age_days = (time.time() - parquet.stat().st_mtime) / 86400
    return age_days < ttl_days


def _read_cache(indicator_id: str) -> pd.Series:
    parquet, _ = _cache_paths(indicator_id)
    df = pd.read_parquet(parquet)
    s = df.iloc[:, 0]
    s.name = indicator_id
    return s


def squeeze_close_from_yfinance(data, ticker: str) -> pd.Series:
    """Extract a ticker's close column from a yfinance frame.

    Handles both bulk-download MultiIndex (``('Close', '^GSPC')`` or
    ``('^GSPC', 'Close')``) and single-ticker flat columns. For
    ``auto_adjust=False`` downloads, ``Close`` is the unadjusted close;
    for ``auto_adjust=True``, it's the adjusted close.
    """
    if data is None or data.empty:
        raise ValueError(f"{ticker}: empty yfinance frame")
    if isinstance(data.columns, pd.MultiIndex):
        if ("Close", ticker) in data.columns:
            s = data[("Close", ticker)]
        elif (ticker, "Close") in data.columns:
            s = data[(ticker, "Close")]
        else:
            raise KeyError(f"{ticker}: not found in MultiIndex columns")
    else:
        if "Close" not in data.columns:
            raise KeyError(f"{ticker}: no Close column")
        s = data["Close"]
    s = s.dropna().astype(float)
    if isinstance(s.index, pd.DatetimeIndex) and s.index.tz is not None:
        s.index = s.index.tz_convert("UTC").tz_localize(None)
    s.name = ticker
    return s


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=15),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, ValueError, KeyError)),
    reraise=True,
)
def _fetch_yahoo_one(yahoo_ticker: str, *, auto_adjust: bool = True) -> pd.Series:
    obj = yf.Ticker(yahoo_ticker)
    df = obj.history(period="max", auto_adjust=auto_adjust)
    return squeeze_close_from_yfinance(df, yahoo_ticker)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_yahoo_series(
    indicator_id: str,
    *,
    force_refresh: bool = False,
    apply_pipeline: bool = True,
) -> tuple[pd.Series, IndicatorMetadata]:
    """Load a single Yahoo series by indicator_id (e.g. ``"SPX_TR"``)."""
    if indicator_id not in YAHOO_REGISTRY:
        raise KeyError(
            f"{indicator_id}: not registered in YAHOO_REGISTRY"
        )
    spec = YAHOO_REGISTRY[indicator_id]
    yahoo_ticker = spec["yahoo_ticker"]
    auto_adjust = spec.get("auto_adjust", True)
    parquet, _ = _cache_paths(indicator_id)

    ttl = 7.0 if spec.get("unofficial_yahoo") else 1.0
    use_cache = not force_refresh and _is_cache_fresh(parquet, ttl_days=ttl)
    fallback_used = False

    if use_cache:
        log.debug("Yahoo %s: cache hit", indicator_id)
        series = _read_cache(indicator_id)
        non_na = series.dropna()
        first_obs = non_na.index.min() if not non_na.empty else pd.NaT
        last_obs = non_na.index.max() if not non_na.empty else pd.NaT
        n_outliers = 0
    else:
        try:
            raw = _fetch_yahoo_one(yahoo_ticker, auto_adjust=auto_adjust)
            raw.name = indicator_id
        except Exception as exc:
            if spec.get("unofficial_yahoo") and parquet.exists():
                log.warning(
                    "Yahoo %s (%s): live fetch failed (%s); using stale cache",
                    indicator_id, yahoo_ticker, exc,
                )
                series = _read_cache(indicator_id)
                non_na = series.dropna()
                first_obs = non_na.index.min() if not non_na.empty else pd.NaT
                last_obs = non_na.index.max() if not non_na.empty else pd.NaT
                fallback_used = True
                n_outliers = 0
                apply_pipeline = False
            else:
                raise

        if apply_pipeline:
            result = run_universal_pipeline(
                raw,
                indicator_id=indicator_id,
                unit=spec["unit"],
                native_freq=spec["freq"],
                expected_min=spec.get("expected_min"),
                expected_max=spec.get("expected_max"),
            )
            series = result.series
            first_obs = result.raw_first_obs
            last_obs = result.raw_last_obs
            n_outliers = result.n_outliers
        elif not fallback_used:
            series = raw
            first_obs = raw.index.min()
            last_obs = raw.index.max()
            n_outliers = 0

    extra: dict = {
        "yahoo_ticker": yahoo_ticker,
        "auto_adjust": auto_adjust,
        "tier": 3,
        "category": spec.get("category"),
        "use_for": spec.get("use_for", []),
        "n_outliers_iqr5": n_outliers,
        "n_obs": int(series.notna().sum()),
    }
    if spec.get("unofficial_yahoo"):
        extra["unofficial_yahoo"] = True
    if spec.get("expected_first_obs"):
        extra["expected_first_obs"] = spec["expected_first_obs"]
    if fallback_used:
        extra["fetch_status"] = "fallback_to_stale_cache"

    meta = IndicatorMetadata(
        indicator_id=indicator_id,
        source="YAHOO_FINANCE",
        frequency=spec["freq"],
        first_obs=first_obs,
        last_obs=last_obs,
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=False,
        unit=spec["unit"],
        release_lag_days=0,
        description=spec["description"],
        expected_min=spec.get("expected_min"),
        expected_max=spec.get("expected_max"),
        extra=extra,
    )

    if not use_cache and not fallback_used and apply_pipeline:
        cache_series_to_parquet(
            series,
            cache_dir=DATA_CACHE,
            file_stem=f"yahoo_{indicator_id}",
            column_name=indicator_id,
            metadata=meta.to_dict(),
        )

    return series, meta


# Back-compat alias - the old name was accepted by load_yahoo_ticker(ticker).
# The test suite has been updated to use load_yahoo_series(indicator_id).
def load_yahoo_ticker(*args, **kwargs):  # pragma: no cover - thin shim
    raise NotImplementedError(
        "load_yahoo_ticker has been replaced by load_yahoo_series(indicator_id). "
        "The registry is now keyed by indicator_id; pass e.g. 'SPX_TR' or "
        "'VIX_YAHOO'."
    )


def load_yahoo_all(
    *,
    force_refresh: bool = False,
    only: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, IndicatorMetadata]]:
    targets = only or list(YAHOO_REGISTRY.keys())
    results: dict[str, pd.Series] = {}
    metadata: dict[str, IndicatorMetadata] = {}
    failures: dict[str, str] = {}
    for sid in targets:
        try:
            s, meta = load_yahoo_series(sid, force_refresh=force_refresh)
            results[meta.indicator_id] = s
            metadata[meta.indicator_id] = meta
        except Exception as exc:  # noqa: BLE001
            failures[sid] = str(exc)
            log.error("Yahoo %s: %s", sid, exc)
    if failures:
        log.warning("Yahoo loader: %d/%d failed: %s",
                    len(failures), len(targets), list(failures.keys()))
    df = pd.concat(results, axis=1) if results else pd.DataFrame()
    df.index.name = "date"
    return df, metadata


class YahooLoader(Loader):
    def __init__(self, *, force_refresh: bool = False, only: list[str] | None = None):
        self.force_refresh = force_refresh
        self.only = only

    def load(self):
        return load_yahoo_all(force_refresh=self.force_refresh, only=self.only)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    df, meta = load_yahoo_all()
    print(f"Loaded {df.shape[1]} Yahoo series, {df.shape[0]} rows "
          f"({df.index.min().date() if not df.empty else 'empty'} -> "
          f"{df.index.max().date() if not df.empty else 'empty'})")
    if not df.empty:
        print(df.tail(2))
