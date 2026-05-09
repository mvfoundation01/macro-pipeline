"""FRED API loader (Build guide Section 5.2).

Pulls every series listed in ``config.FRED_SERIES_API`` through the
universal preprocessing pipeline (Preprocessing guide Stages 1.1-1.7),
caches as parquet, and supports ALFRED point-in-time vintage queries
for backtest.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

import pandas as pd
from fredapi import Fred
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import (
    CACHE_TTL_DAYS,
    DATA_CACHE,
    FRED_API_KEY,
    FRED_SERIES_API,
)
from src.loaders.base import IndicatorMetadata, Loader
from src.preprocessing import cache_series_to_parquet, run_universal_pipeline

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal: a single FRED client with retry on transient errors
# ---------------------------------------------------------------------------
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, ValueError)),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def _fetch_latest(fred: Fred, series_id: str) -> pd.Series:
    s = fred.get_series(series_id)
    if s is None or len(s) == 0:
        raise ValueError(f"FRED returned no data for {series_id}")
    return s


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, ValueError)),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def _fetch_vintage(fred: Fred, series_id: str) -> pd.DataFrame:
    """ALFRED full release history. Columns: date, realtime_start, value."""
    df = fred.get_series_all_releases(series_id)
    if df is None or len(df) == 0:
        raise ValueError(f"FRED returned no vintage rows for {series_id}")
    return df


# ---------------------------------------------------------------------------
# Caching helpers
# ---------------------------------------------------------------------------
def _cache_paths(series_id: str) -> tuple:
    parquet = DATA_CACHE / f"fred_{series_id}.parquet"
    sidecar = DATA_CACHE / f"fred_{series_id}.meta.json"
    return parquet, sidecar


def _is_cache_fresh(parquet_path, freq: str) -> bool:
    if not parquet_path.exists():
        return False
    ttl = CACHE_TTL_DAYS.get(freq.upper()[0], 1)
    age_days = (time.time() - parquet_path.stat().st_mtime) / 86400.0
    return age_days < ttl


def _read_cache(series_id: str) -> tuple[pd.Series, dict]:
    parquet, sidecar = _cache_paths(series_id)
    df = pd.read_parquet(parquet)
    s = df.iloc[:, 0]
    s.name = series_id
    meta = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    return s, meta


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_fred_series(
    series_id: str,
    *,
    vintage_date: str | pd.Timestamp | None = None,
    force_refresh: bool = False,
    apply_pipeline: bool = True,
) -> tuple[pd.Series, IndicatorMetadata]:
    """Load a single FRED series, cached.

    Parameters
    ----------
    series_id
        FRED ID (e.g. ``"T10Y2Y"``). Must be registered in ``FRED_SERIES_API``.
    vintage_date
        If set, return the value of the series as known on that date
        (point-in-time). Vintage queries bypass cache.
    force_refresh
        If True, ignore cache and re-fetch from API.
    apply_pipeline
        If True (default), pipe through ``run_universal_pipeline``
        (validation, outlier flagging, missing-data handling, frequency
        alignment, unit assertion).
    """
    if series_id not in FRED_SERIES_API:
        raise KeyError(
            f"{series_id}: not registered in FRED_SERIES_API. "
            f"Add it to src/config.py before requesting."
        )
    spec = FRED_SERIES_API[series_id]
    # Layer 1.5C.3: spec may carry an ``indicator_id`` alias when the FRED
    # series id is a misnomer (e.g. USSLIND -> PHILLY_LEI_PROXY). The cache
    # file name still uses the FRED id (so the on-disk artefact is stable
    # across renames) but the IndicatorMetadata.indicator_id and the
    # parquet column name use the alias.
    indicator_id = spec.get("indicator_id", series_id)
    fred = Fred(api_key=FRED_API_KEY)

    parquet, _sidecar = _cache_paths(series_id)
    use_cache = (
        vintage_date is None
        and not force_refresh
        and _is_cache_fresh(parquet, spec["freq"])
    )

    cache_already_processed = False
    if use_cache:
        log.debug("FRED %s: cache hit (%s)", series_id, parquet.name)
        raw_series, cached_meta = _read_cache(series_id)
        cache_already_processed = bool(cached_meta.get("pipeline_processed", False))
    elif vintage_date is not None and spec.get("vintage", False):
        # Codex review HIGH #4: groupby("date").last() must be made
        # deterministic by sorting by (date, realtime_start) first so the
        # last vintage row known on or before vintage_date wins
        # reproducibly across pandas / fredapi versions.
        vintage_ts = pd.Timestamp(vintage_date)
        df = _fetch_vintage(fred, series_id)
        df = df[df["realtime_start"] <= vintage_ts]
        if df.empty:
            raise ValueError(
                f"{series_id}: no observations were known on or before {vintage_ts.date()}"
            )
        df = df.sort_values(["date", "realtime_start"], kind="mergesort")
        raw_series = df.groupby("date").last()["value"].sort_index()
        raw_series.name = series_id
    else:
        raw_series = _fetch_latest(fred, series_id)
        raw_series.name = series_id

    if apply_pipeline:
        master_end = pd.Timestamp(vintage_date) if vintage_date else None
        result = run_universal_pipeline(
            raw_series,
            indicator_id=indicator_id,
            unit=spec["unit"],
            native_freq=spec["freq"],
            expected_min=spec.get("expected_min"),
            expected_max=spec.get("expected_max"),
            master_end=master_end,
            _processed=cache_already_processed,
        )
        series = result.series
        first_obs, last_obs = result.raw_first_obs, result.raw_last_obs
        n_outliers = result.n_outliers
    else:
        series = raw_series
        first_obs, last_obs = raw_series.index.min(), raw_series.index.max()
        n_outliers = 0

    # Pass through the spec-level enrichment fields so consumers (Sahm
    # use-context guard, PHILLY_LEI_PROXY double-counting checker, etc.)
    # can read them directly off IndicatorMetadata.extra.
    extra = {
        "fred_series_id": series_id,
        "vintage_date": str(vintage_date) if vintage_date else None,
        "n_outliers_iqr5": n_outliers,
        "n_obs": int(series.notna().sum()),
    }
    for key in (
        "signal_type", "valid_uses", "INVALID_uses",
        "double_counting_risk", "overlap_components",
    ):
        if key in spec:
            extra[key] = spec[key]

    meta = IndicatorMetadata(
        indicator_id=indicator_id,
        source="FRED_ALFRED" if vintage_date else "FRED_API",
        frequency=spec["freq"],
        first_obs=first_obs,
        last_obs=last_obs,
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=spec.get("vintage", False),
        unit=spec["unit"],
        release_lag_days=spec.get("release_lag_days", 0),
        description=spec.get("description", ""),
        expected_min=spec.get("expected_min"),
        expected_max=spec.get("expected_max"),
        data_quality_suspect_periods=spec.get("data_quality_suspect_periods", []),
        extra=extra,
    )

    # Cache only the live (non-vintage) series. Cache file naming uses
    # the FRED series id for stability across indicator-id renames; the
    # parquet column is named by the (possibly aliased) indicator_id so
    # cross-source joins in Layer 3 align cleanly.
    if vintage_date is None and not use_cache and apply_pipeline:
        cache_series_to_parquet(
            series,
            cache_dir=DATA_CACHE,
            file_stem=f"fred_{series_id}",
            column_name=indicator_id,
            metadata=meta.to_dict(),
        )

    return series, meta


def load_fred_all(
    *,
    vintage_date: str | pd.Timestamp | None = None,
    force_refresh: bool = False,
    only: list[str] | None = None,
    skip_on_error: bool = True,
) -> tuple[pd.DataFrame, dict[str, IndicatorMetadata]]:
    """Fetch every series in ``FRED_SERIES_API`` (or just ``only``).

    Returns
    -------
    df
        DataFrame on the business-day master index, columns = series IDs.
    metadata
        Dict[series_id -> IndicatorMetadata].
    """
    targets = only or list(FRED_SERIES_API.keys())
    results: dict[str, pd.Series] = {}
    metadata: dict[str, IndicatorMetadata] = {}
    failures: dict[str, str] = {}

    for sid in targets:
        try:
            s, meta = load_fred_series(
                sid, vintage_date=vintage_date, force_refresh=force_refresh
            )
            # Key by indicator_id so aliased entries (e.g. USSLIND ->
            # PHILLY_LEI_PROXY) appear under their canonical name.
            results[meta.indicator_id] = s
            metadata[meta.indicator_id] = meta
        except (RetryError, ValueError, ConnectionError) as exc:
            failures[sid] = str(exc)
            log.error("FRED %s: failed - %s", sid, exc)
            if not skip_on_error:
                raise

    if failures:
        log.warning("FRED loader: %d/%d series failed: %s",
                    len(failures), len(targets), list(failures.keys()))

    df = pd.concat(results, axis=1) if results else pd.DataFrame()
    df.index.name = "date"
    return df, metadata


class FredLoader(Loader):
    """Thin wrapper for compatibility with the ``Loader`` ABC."""

    def __init__(
        self,
        *,
        vintage_date: str | pd.Timestamp | None = None,
        force_refresh: bool = False,
        only: list[str] | None = None,
    ):
        self.vintage_date = vintage_date
        self.force_refresh = force_refresh
        self.only = only

    def load(self) -> tuple[pd.DataFrame, dict[str, IndicatorMetadata]]:
        return load_fred_all(
            vintage_date=self.vintage_date,
            force_refresh=self.force_refresh,
            only=self.only,
        )


# ---------------------------------------------------------------------------
# CLI entry: `python -m src.loaders.fred_loader`
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    df, meta = load_fred_all()
    print(f"Loaded {df.shape[1]} series, {df.shape[0]} business days "
          f"({df.index.min().date()} -> {df.index.max().date()})")
    print(df.tail(3))
