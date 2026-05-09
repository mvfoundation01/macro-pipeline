"""NAAIM Exposure Index loader (Build guide Phase 4A).

File: ``data/raw/official/USE_Data_since_Inception_2026_04_29.xlsx``
Sheet: ``USE_Data since Inception_2026``

Headline series is ``NAAIM Number`` (active manager equity exposure %).
Source has NEWEST-FIRST ordering and weekly Wednesday cadence; we
reverse to ascending and pipe through the universal preprocessing
pipeline before caching as ``data/cache/official_NAAIM_NUMBER.parquet``.

Tier: 2A (official survey data).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import DATA_CACHE, DATA_RAW
from src.loaders.base import IndicatorMetadata, Loader
from src.preprocessing import cache_series_to_parquet, run_universal_pipeline

log = logging.getLogger(__name__)

NAAIM_PATH = DATA_RAW / "official" / "USE_Data_since_Inception_2026_04_29.xlsx"
NAAIM_SHEET = "USE_Data since Inception_2026"
INDICATOR_ID = "NAAIM_NUMBER"


def _read_naaim_raw() -> pd.Series:
    df = pd.read_excel(NAAIM_PATH, sheet_name=NAAIM_SHEET)
    if "Date" not in df.columns or "NAAIM Number" not in df.columns:
        raise ValueError(
            f"NAAIM: expected columns 'Date' and 'NAAIM Number', "
            f"got {list(df.columns)}"
        )
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    df = df[~df["Date"].duplicated(keep="last")]
    s = df.set_index("Date")["NAAIM Number"].astype(float)
    s.name = INDICATOR_ID
    return s


def load_naaim(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[pd.Series, IndicatorMetadata]:
    raw = _read_naaim_raw()

    if apply_pipeline:
        result = run_universal_pipeline(
            raw,
            indicator_id=INDICATOR_ID,
            unit="pct_exposure",
            native_freq="W",
            expected_min=-200, expected_max=250,
        )
        series = result.series
        first_obs = result.raw_first_obs
        last_obs = result.raw_last_obs
        n_outliers = result.n_outliers
    else:
        series = raw
        first_obs, last_obs = raw.index.min(), raw.index.max()
        n_outliers = 0

    meta = IndicatorMetadata(
        indicator_id=INDICATOR_ID,
        source="NAAIM_XLSX",
        frequency="W",
        first_obs=first_obs,
        last_obs=last_obs,
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=False,
        unit="pct_exposure",
        release_lag_days=2,  # weekly survey, reported next day
        description=(
            "NAAIM Active Manager Equity Exposure Index (weekly Wednesday). "
            "100 = fully long; 0 = neutral; -100 = fully short; values up to "
            "200 indicate leveraged long, down to -200 leveraged short."
        ),
        expected_min=-200, expected_max=250,
        extra={
            "tier": "2A",
            "source_file": NAAIM_PATH.name,
            "source_sheet": NAAIM_SHEET,
            "release_schedule": "Wednesday",
            "n_outliers_iqr5": n_outliers,
            "n_obs": int(series.notna().sum()),
        },
    )

    if apply_pipeline:
        cache_series_to_parquet(
            series,
            cache_dir=DATA_CACHE,
            file_stem=f"official_{INDICATOR_ID}",
            column_name=INDICATOR_ID,
            metadata=meta.to_dict(),
        )
    return series, meta


class NaaimLoader(Loader):
    def load(self):
        s, m = load_naaim()
        return s.to_frame(), {m.indicator_id: m}


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    s, meta = load_naaim()
    print(f"NAAIM_NUMBER: {len(s.dropna()):,} non-null obs, "
          f"first={meta.first_obs.date()}  last={meta.last_obs.date()}  "
          f"current={s.dropna().iloc[-1]:.2f}")
