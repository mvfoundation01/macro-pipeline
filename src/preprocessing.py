"""Universal preprocessing pipeline (Preprocessing guide Part 1, Stages 1.1-1.7).

Every loader pipes raw output through ``run_universal_pipeline`` before
returning. Outliers are *flagged*, not removed (Stage 1.3) — macro data
legitimately contains 1973/1987/2008/2020-style outliers.

Forward-fill only — never backfill — to preserve point-in-time correctness.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass

import pandas as pd

from src.config import MASTER_INDEX_START, UNIT_EXPECTED_RANGES

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage 1.0 - Point-in-time visibility shift (Layer 1.5A.1)
# ---------------------------------------------------------------------------
def to_visibility_index(s: pd.Series, release_lag_days: int) -> pd.Series:
    """Shift index from observation_date to visibility_date.

    Used for PIT-safe alignment in ``access.PitSeriesReader``: a row whose
    underlying observation is dated 2008-08-01 but is published with a
    7-day lag was not visible until 2008-08-08, so we shift its index by
    ``release_lag_days`` before truncating at ``as_of``.

    For non-vintage series only. Vintage series carry their own
    ``realtime_start`` per row and bypass this helper.
    """
    if release_lag_days == 0:
        return s
    out = s.copy()
    out.index = out.index + pd.Timedelta(days=release_lag_days)
    return out


# ---------------------------------------------------------------------------
# Stage 1.1 - Ingestion validation
# ---------------------------------------------------------------------------
class IngestionError(Exception):
    """Hard ingestion failure - empty series, all-NaN, unsorted index, dupes."""


def validate_ingest(
    s: pd.Series,
    indicator_id: str,
    expected_freq: str | None = None,
    expected_min: float | None = None,
    expected_max: float | None = None,
) -> pd.Series:
    """Hard checks abort; range/freq mismatches warn."""
    if s.empty:
        raise IngestionError(f"{indicator_id}: empty series")
    if s.isna().all():
        raise IngestionError(f"{indicator_id}: all NaN")
    if not s.index.is_monotonic_increasing:
        s = s.sort_index()
    if not s.index.is_unique:
        # Keep last for duplicates (latest revision wins).
        s = s[~s.index.duplicated(keep="last")]

    obs = s.dropna()
    if expected_min is not None and float(obs.min()) < expected_min:
        log.warning(
            "%s: min %.4g below expected %.4g",
            indicator_id, obs.min(), expected_min,
        )
    if expected_max is not None and float(obs.max()) > expected_max:
        log.warning(
            "%s: max %.4g above expected %.4g",
            indicator_id, obs.max(), expected_max,
        )

    if expected_freq:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            inferred = pd.infer_freq(obs.index[:30]) if len(obs) >= 3 else None
        if inferred and not inferred[0].upper().startswith(expected_freq[0].upper()):
            log.info(
                "%s: inferred freq %s != expected %s (mixed publication cadence)",
                indicator_id, inferred, expected_freq,
            )
    return s


# ---------------------------------------------------------------------------
# Stage 1.2 - Timezone normalization
# ---------------------------------------------------------------------------
def normalize_tz(s: pd.Series) -> pd.Series:
    if isinstance(s.index, pd.DatetimeIndex) and s.index.tz is not None:
        s.index = s.index.tz_convert("UTC").tz_localize(None)
    if isinstance(s.index, pd.DatetimeIndex):
        s.index = s.index.normalize()
    return s


# ---------------------------------------------------------------------------
# Stage 1.3 - Outlier *flagging* (do not remove)
# ---------------------------------------------------------------------------
def flag_outliers_iqr(s: pd.Series, k: float = 5.0) -> pd.Series:
    obs = s.dropna()
    if len(obs) < 4:
        return pd.Series(False, index=s.index)
    q1, q3 = obs.quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr == 0:
        return pd.Series(False, index=s.index)
    lower, upper = q1 - k * iqr, q3 + k * iqr
    flags = (s < lower) | (s > upper)
    return flags.fillna(False)


# ---------------------------------------------------------------------------
# Stage 1.4 - Missing data handling
# ---------------------------------------------------------------------------
def handle_missing(s: pd.Series, max_interp_days: int = 5) -> pd.Series:
    """ffill weekend/holiday gaps; linear-interp short mid-series gaps; leave end gaps NaN.

    Note: this is the pre-alignment step. It leaves ``s`` on its native index;
    ``align_to_business_days`` ffills onwards from there.
    """
    if s.empty:
        return s
    last_valid = s.last_valid_index()
    if last_valid is None:
        return s

    is_missing = s.isna()
    # Run-length encode missing chunks; only fill chunks <= max_interp_days
    # whose end is at or before ``last_valid`` (i.e. internal, not trailing).
    if not is_missing.any():
        return s

    out = s.copy()
    # Identify groups of consecutive NaNs.
    grp = (~is_missing).cumsum()
    chunk_lens = is_missing.groupby(grp).transform("sum")
    short_internal = is_missing & (chunk_lens <= max_interp_days) & (s.index <= last_valid)
    if short_internal.any():
        interpolated = out.interpolate(method="linear", limit_area="inside")
        out.loc[short_internal] = interpolated.loc[short_internal]
    return out


# ---------------------------------------------------------------------------
# Stage 1.5 - Frequency alignment to a business-day master index
# ---------------------------------------------------------------------------
def build_master_index(start: str | None = None, end: pd.Timestamp | None = None) -> pd.DatetimeIndex:
    start = start or MASTER_INDEX_START
    end = end or pd.Timestamp.today().normalize()
    return pd.bdate_range(start, end)


def align_to_business_days(
    s: pd.Series,
    native_freq: str,
    master_index: pd.DatetimeIndex | None = None,
    *,
    end: pd.Timestamp | None = None,
) -> pd.Series:
    """Reindex to business-day master index using forward-fill only.

    The build guide is explicit: never backfill, to preserve point-in-time
    semantics for backtest. ffill is correct because the value remained
    'in force' from publication until the next release.

    The auto-built master index extends back to ``min(MASTER_INDEX_START,
    s.index.min())`` so series with deeper history (e.g. Shiller from 1871)
    don't have their pre-1959 portion silently dropped.

    ``end`` caps the master index (use ``vintage_date`` for PIT queries so
    the index does not get padded forward to today).
    """
    if s.empty:
        return s
    if master_index is None:
        upper = end if end is not None else pd.Timestamp.today().normalize()
        upper = max(s.index.max(), upper)
        # Extend backwards if the source predates MASTER_INDEX_START.
        default_start = pd.Timestamp(MASTER_INDEX_START)
        lower = min(s.index.min(), default_start)
        master_index = build_master_index(
            start=lower.strftime("%Y-%m-%d"), end=upper,
        )
    freq = (native_freq or "D").upper()[0]
    if freq not in {"D", "W", "M", "Q", "B", "A", "Y"}:
        raise ValueError(f"Unknown native frequency: {native_freq}")
    return s.reindex(master_index, method="ffill")


# ---------------------------------------------------------------------------
# Stage 1.6 - Unit normalization / sanity range check
# ---------------------------------------------------------------------------
class UnitError(Exception):
    pass


def assert_unit(s: pd.Series, unit: str, indicator_id: str = "?") -> None:
    obs = s.dropna()
    if obs.empty:
        return
    if unit not in UNIT_EXPECTED_RANGES:
        log.debug("%s: unit %s has no sanity range registered", indicator_id, unit)
        return
    lo, hi = UNIT_EXPECTED_RANGES[unit]
    actual_min, actual_max = float(obs.min()), float(obs.max())
    if not (lo <= actual_min and actual_max <= hi):
        raise UnitError(
            f"{indicator_id}: range [{actual_min:.4g}, {actual_max:.4g}] "
            f"inconsistent with unit '{unit}' expected [{lo:g}, {hi:g}]"
        )


# ---------------------------------------------------------------------------
# Data-quality suspect-period helper
# ---------------------------------------------------------------------------
def is_quality_suspect(meta_or_periods, date) -> bool:
    """Return True if ``date`` falls within any suspect period.

    ``meta_or_periods`` accepts:
    - an ``IndicatorMetadata`` instance,
    - a serialized metadata dict (e.g. from a meta.json sidecar),
    - or the bare list of period dicts.

    Each period is ``{"start_date", "end_date", "reason"}``. Boundaries are
    inclusive. Returns False if no periods are configured.
    """
    if hasattr(meta_or_periods, "data_quality_suspect_periods"):
        periods = meta_or_periods.data_quality_suspect_periods
    elif isinstance(meta_or_periods, dict):
        periods = meta_or_periods.get("data_quality_suspect_periods", []) or []
    else:
        periods = list(meta_or_periods or [])
    if not periods:
        return False
    d = pd.Timestamp(date).normalize()
    for p in periods:
        start = pd.Timestamp(p["start_date"]).normalize()
        end = pd.Timestamp(p["end_date"]).normalize()
        if start <= d <= end:
            return True
    return False


# ---------------------------------------------------------------------------
# Stage 1.7 - Persist to parquet cache
# ---------------------------------------------------------------------------
def cache_series_to_parquet(
    s: pd.Series,
    *,
    cache_dir,
    file_stem: str,
    column_name: str | None = None,
    metadata: dict | None = None,
    pipeline_processed: bool = True,
) -> None:
    """Persist a series + sidecar metadata atomically (Layer 1.5A.5).

    ``file_stem`` is the filename (no extension) used for path discrimination
    across loaders, e.g. ``"fred_PAYEMS"`` or ``"tv_VIX"``.
    ``column_name`` is what the column is named *inside* the parquet — keep
    this as the bare indicator_id (no loader prefix) so Layer 3 derived
    series can join cleanly across sources.

    Routes through ``cache.write_cache_atomic`` so the parquet is written
    to a tmp file first, fsynced, then atomically renamed; the metadata is
    enriched with ``data_sha256`` / ``schema_version`` / ``row_count`` /
    ``cache_written_at`` and ``pipeline_processed`` so that
    ``read_cache_validated`` can detect crash-corrupted or schema-stale
    caches and ``run_universal_pipeline`` can short-circuit on cache hits
    (Layer 1.5A.6).
    """
    column_name = column_name or file_stem
    df = s.to_frame(column_name)

    # Local import avoids a circular dependency: src.cache imports nothing
    # else from src.preprocessing, but importing it at module load could
    # invert the order during test collection.
    from src.cache import write_cache_atomic

    write_cache_atomic(
        file_stem,
        df,
        metadata or {},
        cache_dir,
        pipeline_processed=pipeline_processed,
    )


# ---------------------------------------------------------------------------
# Combined pipeline
# ---------------------------------------------------------------------------
@dataclass
class PreprocessResult:
    series: pd.Series
    outlier_flags: pd.Series
    n_outliers: int
    raw_first_obs: pd.Timestamp
    raw_last_obs: pd.Timestamp


def run_universal_pipeline(
    raw: pd.Series,
    *,
    indicator_id: str,
    unit: str,
    native_freq: str,
    expected_min: float | None = None,
    expected_max: float | None = None,
    align_to_master: bool = True,
    enforce_unit: bool = True,
    fail_on_unit_error: bool = True,
    master_end: pd.Timestamp | None = None,
    _processed: bool = False,
) -> PreprocessResult:
    """Stages 1.1 -> 1.6 wired together. Caller decides whether to persist.

    ``master_end`` caps the post-alignment master index (set this to the
    vintage date for PIT queries to prevent forward-padding into the future).

    ``fail_on_unit_error`` (Layer 1.5A.3, Codex review HIGH #3): when True
    (production default), an out-of-range unit assertion re-raises
    ``UnitError`` so the pipeline cannot silently emit data with the wrong
    units. Set to False only for inspection workflows where you want a
    warning instead of an abort.

    ``_processed`` (Layer 1.5A.6, Codex review #5): when True the series is
    treated as already-pipeline-processed (e.g. read from a cache marked
    ``pipeline_processed=true``) and stages 1.1-1.6 are skipped. The caller
    still gets back a ``PreprocessResult`` so call sites stay uniform.
    """
    if _processed:
        log.debug("%s: cache hit, skip pipeline (already processed)", indicator_id)
        s = raw.copy()
        s.name = indicator_id
        non_na = s.dropna()
        first = non_na.index.min() if not non_na.empty else pd.NaT
        last = non_na.index.max() if not non_na.empty else pd.NaT
        return PreprocessResult(
            series=s,
            outlier_flags=pd.Series(False, index=s.index),
            n_outliers=0,
            raw_first_obs=first,
            raw_last_obs=last,
        )

    s = raw.copy()
    s.name = indicator_id

    s = validate_ingest(
        s, indicator_id,
        expected_freq=native_freq,
        expected_min=expected_min,
        expected_max=expected_max,
    )
    s = normalize_tz(s)
    raw_first, raw_last = s.index.min(), s.index.max()

    flags = flag_outliers_iqr(s, k=5.0)
    s = handle_missing(s, max_interp_days=5)

    if align_to_master:
        s = align_to_business_days(s, native_freq=native_freq, end=master_end)

    if enforce_unit:
        try:
            assert_unit(s, unit, indicator_id)
        except UnitError as exc:
            if fail_on_unit_error:
                raise
            log.warning("%s", exc)

    return PreprocessResult(
        series=s,
        outlier_flags=flags.reindex(s.index, fill_value=False),
        n_outliers=int(flags.sum()),
        raw_first_obs=raw_first,
        raw_last_obs=raw_last,
    )
