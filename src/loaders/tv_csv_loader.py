"""TradingView CSV loader (Build guide Section 5.3).

Pulls every ``data/raw/tradingview/*.csv`` through the universal
preprocessing pipeline (Preprocessing guide Stages 1.1-1.7), caches as
``data/cache/tv_<indicator_id>.parquet``, and tags Tier 5 auxiliary series
(Wilshire 5000, OECD CCI) with ``do_not_use_for=[real_time_signal,...]``
per Build guide Section 23.

Where a TV file shares an ID with a series exposed via FRED API
(BAMLH0A0HYM2, WALCL, ...) the canonical convention is: prefer the FRED
API path for production scoring (vintage support, no re-export drift);
the TV CSV serves as backup/historical. Today we only have the TV CSV
for these series, so they are loaded as primary.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import CACHE_TTL_DAYS, DATA_CACHE, DATA_RAW
from src.loaders.base import IndicatorMetadata, Loader
from src.preprocessing import cache_series_to_parquet, run_universal_pipeline

log = logging.getLogger(__name__)

TV_RAW_DIR = DATA_RAW / "tradingview"


# ---------------------------------------------------------------------------
# Registry: filename -> spec
# ---------------------------------------------------------------------------
# `indicator_id` is the bare canonical name used inside parquet columns and
# downstream joins. `raw_unit_transform` rescales the TV-exported raw USD
# magnitudes into the project-wide unit convention (M_USD, B_USD).
TV_FILES_REGISTRY: dict[str, dict] = {
    # === Treasury yields ===
    "TVC_US10Y_1D.csv": {
        "indicator_id": "US10Y",
        "freq": "D", "unit": "pct",
        "expected_min": 0.0, "expected_max": 20.0, "tier": 1,
        "description": "10-Year US Treasury yield (TVC bond-equivalent basis)",
    },
    "TVC_US02Y_1D.csv": {
        "indicator_id": "US02Y",
        "freq": "D", "unit": "pct",
        "expected_min": 0.0, "expected_max": 20.0, "tier": 1,
        "description": "2-Year US Treasury yield",
    },
    "TVC_US03MY_1D.csv": {
        "indicator_id": "US03MY",
        "freq": "D", "unit": "pct",
        # 3M T-bill went briefly negative in March 2020 (premium to par).
        "expected_min": -0.5, "expected_max": 20.0, "tier": 1,
        "description": "3-Month US Treasury yield (BEB)",
    },

    # === Credit OAS (already spreads in pct - do NOT subtract Treasury) ===
    "FRED_BAMLH0A0HYM2_1D.csv": {
        "indicator_id": "BAMLH0A0HYM2",
        "freq": "D", "unit": "pct",
        "expected_min": 0.0, "expected_max": 25.0, "tier": 1,
        "description": "ICE BofA US High Yield OAS (already a spread)",
    },
    "FRED_BAMLC0A0CM_1D.csv": {
        "indicator_id": "BAMLC0A0CM",
        "freq": "D", "unit": "pct",
        "expected_min": 0.0, "expected_max": 15.0, "tier": 1,
        "description": "ICE BofA US Investment Grade Corporate OAS",
    },
    "FRED_BAMLH0A3HYC_1D.csv": {
        "indicator_id": "BAMLH0A3HYC",
        "freq": "D", "unit": "pct",
        "expected_min": 0.0, "expected_max": 50.0, "tier": 1,
        "description": "ICE BofA US HY CCC & Below OAS",
    },
    "FRED_BAMLH0A1HYBB_1D.csv": {
        "indicator_id": "BAMLH0A1HYBB",
        "freq": "D", "unit": "pct",
        "expected_min": 0.0, "expected_max": 25.0, "tier": 1,
        "description": "ICE BofA US HY BB OAS",
    },

    # === Fed BS / TGA / RRP / GDP - raw USD on disk, normalized in loader ===
    "FRED_WALCL_1D.csv": {
        "indicator_id": "WALCL",
        "freq": "D", "unit": "M_USD",
        "expected_min": 5e5, "expected_max": 1e7, "tier": 1,
        "raw_unit_transform": "raw_to_M_USD",
        "description": "Fed Reserve Balance Sheet Total Assets (millions USD)",
    },
    "FRED_WTREGEN_1D.csv": {
        "indicator_id": "WTREGEN",
        "freq": "D", "unit": "M_USD",
        # Pre-2002 TV data may use a different scale than the 2002+ FRED-aligned
        # series (FRED's WTREGEN is NaN before 2002). Lower bound permissive.
        "expected_min": 1.0, "expected_max": 2e6, "tier": 1,
        "raw_unit_transform": "raw_to_M_USD",
        "description": "Treasury General Account (millions USD; pre-2002 may differ from FRED)",
        "data_quality_suspect_periods": [
            {
                "start_date": "1986-01-01",
                "end_date": "2002-12-17",
                "reason": (
                    "TV CSV pre-2002 from discontinued precursor series; "
                    "values ~1000x scale-mismatched vs current WTREGEN "
                    "definition; FRED API returns NaN for this period."
                ),
            }
        ],
    },
    "FRED_RRPONTSYD_1D.csv": {
        "indicator_id": "RRPONTSYD",
        "freq": "D", "unit": "B_USD",
        "expected_min": 0, "expected_max": 3000, "tier": 1,
        "raw_unit_transform": "raw_to_B_USD",
        "description": "Overnight Reverse Repo balances (billions USD)",
    },
    "FRED_GDP_3M.csv": {
        "indicator_id": "GDP",
        "freq": "Q", "unit": "B_USD",
        "expected_min": 100, "expected_max": 5e4, "tier": 1,
        "raw_unit_transform": "raw_to_B_USD",
        "description": "Nominal GDP (billions USD, quarterly)",
    },

    # === Equity breadth / relative strength ===
    "INDEX_S5TH_1D.csv": {
        "indicator_id": "S5TH",
        "freq": "D", "unit": "pct",
        "expected_min": 0, "expected_max": 100, "tier": 1,
        "description": "Percent of S&P 500 stocks above 200-day MA",
    },
    "INDEX_S5FI_1D.csv": {
        "indicator_id": "S5FI",
        "freq": "D", "unit": "pct",
        "expected_min": 0, "expected_max": 100, "tier": 1,
        "description": "Percent of S&P 500 stocks above 50-day MA",
    },
    "INDEX_HIGN-INDEX_LOWN_1D.csv": {
        # Hyphen sanitized -> HIGN_LOWN_NET. Already differenced (NH-NL).
        "indicator_id": "HIGN_LOWN_NET",
        "freq": "D", "unit": "count_signed",
        "expected_min": -2000, "expected_max": 2000, "tier": 1,
        "description": "NYSE 52-week new highs minus new lows (NH-NL net)",
    },
    "USI_ISSU_1D.csv": {
        # Note: TV's USI_ISSU values are O(1), interpretable as A/D ratio
        # (advances divided by declines), not raw issue counts.
        "indicator_id": "NYSE_ADV_DECL_RATIO",
        "freq": "D", "unit": "ratio",
        "expected_min": 0, "expected_max": 100, "tier": 1,
        "description": "NYSE Advances / Declines daily ratio (TV USI_ISSU)",
    },
    "TVC_RUT_SP_SPX_1D.csv": {
        "indicator_id": "RUT_SPX_RATIO",
        "freq": "D", "unit": "ratio",
        "expected_min": 0.2, "expected_max": 1.5, "tier": 1,
        "description": "Russell 2000 / S&P 500 ratio (TV-computed)",
    },

    # === Volatility / options ===
    "CBOE_DLY_VIX_1D.csv": {
        "indicator_id": "VIX",
        "freq": "D", "unit": "index",
        "expected_min": 5, "expected_max": 100, "tier": 1,
        "description": "Cboe Volatility Index",
    },
    "CBOE_DLY_GAMMA_1D.csv": {
        "indicator_id": "CBOE_GAMMA",
        "freq": "D", "unit": "index",
        "expected_min": 0, "expected_max": 1000, "tier": 1,
        "short_history_warn": True,
        "description": "Cboe GAMMA index (history starts 2022-12, ~852 obs)",
    },
    "USI_PCCE_1D.csv": {
        "indicator_id": "PCCE",
        "freq": "D", "unit": "ratio",
        "expected_min": 0, "expected_max": 5, "tier": 1,
        "description": "Cboe Equity Put/Call ratio (TV USI_PCCE)",
    },

    # === Coincident sentiment ===
    "FRED_UMCSENT_1M.csv": {
        "indicator_id": "UMCSENT",
        "freq": "M", "unit": "index",
        "expected_min": 30, "expected_max": 130, "tier": 1,
        "description": "University of Michigan Consumer Sentiment Index",
    },

    # === Tier 5 auxiliary (stale-but-valid, backtest only) ===
    "FRED_WILL5000PR_3M.csv": {
        "indicator_id": "WILL5000PR",
        "freq": "Q", "unit": "index",
        "expected_min": 100, "expected_max": 1e5, "tier": 5,
        "data_status": "stale",
        # last_valid_date is the last DATE for which the underlying source
        # had real data; downstream `align_to_business_days` ffills past
        # that to today, so `last_obs` is misleading for E.3 cutoff logic.
        "last_valid_date": "2024-04-01",
        "stale_reason": "Wilshire revoked FRED license 2024-06-03; series stops 2024-04-01",
        "use_for": ["backtest", "regression", "historical_derived"],
        "do_not_use_for": ["real_time_signal", "current_alert", "live_crps", "live_cdrs"],
        "replacement_realtime": "Russell 3000 (^RUA via Yahoo) with calibration factor",
        "description": "Wilshire 5000 Total Market Index (TIER 5 stale 2024-04)",
    },
    "FRED_CSCICP03USM665S_1M.csv": {
        "indicator_id": "CSCICP03USM665S",
        "freq": "M", "unit": "index",
        "expected_min": 80, "expected_max": 110, "tier": 5,
        "data_status": "stale",
        "last_valid_date": "2024-01-01",
        "stale_reason": "OECD methodology change; FRED stops updating 2024-01-01",
        "use_for": ["backtest", "regression", "historical_derived"],
        "do_not_use_for": ["real_time_signal", "current_alert", "live_crps", "live_cdrs"],
        "replacement_realtime": "FRED USACSCICP02STSAM (OECD successor)",
        "description": "OECD US Consumer Confidence Index (TIER 5 stale 2024-01)",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _unit_transform(s: pd.Series, transform: str | None) -> pd.Series:
    if transform is None:
        return s
    if transform == "raw_to_M_USD":
        return s / 1e6
    if transform == "raw_to_B_USD":
        return s / 1e9
    raise ValueError(f"Unknown raw_unit_transform: {transform}")


def _read_tv_csv(path: Path) -> pd.Series:
    """Read TV CSV - returns close column as float Series indexed by date."""
    df = pd.read_csv(path)
    if "time" not in df.columns:
        raise ValueError(f"{path.name}: missing 'time' column")
    if "close" not in df.columns:
        raise ValueError(f"{path.name}: missing 'close' column "
                         f"(have: {list(df.columns)})")
    df["time"] = pd.to_datetime(df["time"], errors="raise")
    df = df.dropna(subset=["time"]).sort_values("time").set_index("time")
    df = df[~df.index.duplicated(keep="last")]
    return df["close"].astype(float)


def _cache_paths(indicator_id: str) -> tuple[Path, Path]:
    parquet = DATA_CACHE / f"tv_{indicator_id}.parquet"
    sidecar = DATA_CACHE / f"tv_{indicator_id}.meta.json"
    return parquet, sidecar


def _is_cache_fresh(parquet: Path, freq: str) -> bool:
    if not parquet.exists():
        return False
    ttl = CACHE_TTL_DAYS.get(freq.upper()[0], 1)
    age_days = (time.time() - parquet.stat().st_mtime) / 86400
    return age_days < ttl


def _read_cache(indicator_id: str) -> pd.Series:
    parquet, _ = _cache_paths(indicator_id)
    df = pd.read_parquet(parquet)
    s = df.iloc[:, 0]
    s.name = indicator_id
    return s


def discover_tv_files() -> list[str]:
    """Sorted list of *.csv basenames in data/raw/tradingview/."""
    if not TV_RAW_DIR.exists():
        return []
    return sorted([p.name for p in TV_RAW_DIR.glob("*.csv")])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_tv_file(
    filename: str,
    *,
    force_refresh: bool = False,
    apply_pipeline: bool = True,
) -> tuple[pd.Series, IndicatorMetadata]:
    if filename not in TV_FILES_REGISTRY:
        raise KeyError(
            f"{filename}: not registered in TV_FILES_REGISTRY. "
            "Add it to src/loaders/tv_csv_loader.py before requesting."
        )
    spec = TV_FILES_REGISTRY[filename]
    indicator_id = spec["indicator_id"]
    parquet, _ = _cache_paths(indicator_id)

    use_cache = not force_refresh and _is_cache_fresh(parquet, spec["freq"])

    if use_cache:
        log.debug("TV %s: cache hit", indicator_id)
        series = _read_cache(indicator_id)
        non_na = series.dropna()
        first_obs = non_na.index.min() if not non_na.empty else pd.NaT
        last_obs = non_na.index.max() if not non_na.empty else pd.NaT
        n_outliers = 0
    else:
        path = TV_RAW_DIR / filename
        if not path.exists():
            raise FileNotFoundError(str(path))
        raw = _read_tv_csv(path)
        raw.name = indicator_id
        raw = _unit_transform(raw, spec.get("raw_unit_transform"))

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
            first_obs, last_obs = result.raw_first_obs, result.raw_last_obs
            n_outliers = result.n_outliers
        else:
            series = raw
            first_obs, last_obs = raw.index.min(), raw.index.max()
            n_outliers = 0

    extra: dict = {
        "tv_filename": filename,
        "n_outliers_iqr5": n_outliers,
        "n_obs": int(series.notna().sum()),
    }
    if spec.get("tier") == 5:
        extra.update({
            "tier": 5,
            "data_status": spec.get("data_status"),
            "last_valid_date": spec.get("last_valid_date"),
            "stale_reason": spec.get("stale_reason"),
            "use_for": spec.get("use_for"),
            "do_not_use_for": spec.get("do_not_use_for"),
            "replacement_realtime": spec.get("replacement_realtime"),
        })
    else:
        extra["tier"] = spec.get("tier", 1)
    if spec.get("short_history_warn"):
        extra["short_history_warn"] = True
    if spec.get("raw_unit_transform"):
        extra["raw_unit_transform"] = spec["raw_unit_transform"]

    meta = IndicatorMetadata(
        indicator_id=indicator_id,
        source="TV_CSV",
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
        data_quality_suspect_periods=spec.get("data_quality_suspect_periods", []),
        extra=extra,
    )

    if not use_cache and apply_pipeline:
        cache_series_to_parquet(
            series,
            cache_dir=DATA_CACHE,
            file_stem=f"tv_{indicator_id}",
            column_name=indicator_id,
            metadata=meta.to_dict(),
        )

    return series, meta


def load_tv_all(
    *,
    force_refresh: bool = False,
    only: list[str] | None = None,
    skip_unregistered: bool = True,
) -> tuple[pd.DataFrame, dict[str, IndicatorMetadata]]:
    discovered = discover_tv_files()
    targets = only or discovered

    unregistered = [f for f in targets if f not in TV_FILES_REGISTRY]
    if unregistered:
        if skip_unregistered:
            log.warning("Skipping unregistered TV files: %s", unregistered)
            targets = [f for f in targets if f in TV_FILES_REGISTRY]
        else:
            raise KeyError(f"Unregistered TV files: {unregistered}")

    missing = [f for f in TV_FILES_REGISTRY if f not in discovered]
    if missing:
        log.warning("Registered TV files not on disk: %s", missing)

    results: dict[str, pd.Series] = {}
    metadata: dict[str, IndicatorMetadata] = {}
    failures: dict[str, str] = {}

    for fname in targets:
        try:
            s, meta = load_tv_file(fname, force_refresh=force_refresh)
            results[meta.indicator_id] = s
            metadata[meta.indicator_id] = meta
        except (ValueError, FileNotFoundError, KeyError) as exc:
            failures[fname] = str(exc)
            log.error("TV %s: failed - %s", fname, exc)

    if failures:
        log.warning("TV loader: %d/%d files failed: %s",
                    len(failures), len(targets), list(failures.keys()))

    df = pd.concat(results, axis=1) if results else pd.DataFrame()
    df.index.name = "date"
    return df, metadata


class TvCsvLoader(Loader):
    def __init__(self, *, force_refresh: bool = False, only: list[str] | None = None):
        self.force_refresh = force_refresh
        self.only = only

    def load(self):
        return load_tv_all(force_refresh=self.force_refresh, only=self.only)


# ---------------------------------------------------------------------------
# CLI: `python -m src.loaders.tv_csv_loader`
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    df, meta = load_tv_all()
    print(f"Loaded {df.shape[1]} TV series, {df.shape[0]} business days "
          f"({df.index.min().date()} -> {df.index.max().date()})")
    print(df.tail(2))
