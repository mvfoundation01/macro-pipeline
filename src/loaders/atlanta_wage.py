"""Atlanta Fed Wage Growth Tracker (Build guide Phase 4C).

File: ``data/raw/official/wagegrowthdata.xlsx``
Sheet: ``data_overall`` (the main aggregate; 19 other sheets are
demographic breakdowns, ignored here.)

Header row 1, data starts row 2. Cell value ``"."`` represents missing
(coerced to NaN). Date column is unnamed; column 1 is "Overall".

Output: ``ATLANTA_WAGE_OVERALL`` - 12-month moving average of median
hourly wage growth, monthly, in % YoY (typically 3-5% in normal periods,
>6% in 2022-23 hot labour market, ~4% currently).

CRITICAL VINTAGE NOTE: the Atlanta Fed REVISES THE FULL HISTORY each
release (their methodology updates retroactively). This is different
from BLS-style point-in-time revisions. Backtests using the latest
file as if it were observable in real time will have ~1-3% optimistic
bias from the modern methodology being applied to historical periods.

Tier: 2A.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import pandas as pd

from src.config import DATA_CACHE, DATA_RAW
from src.loaders.base import IndicatorMetadata, Loader
from src.preprocessing import cache_series_to_parquet, run_universal_pipeline

log = logging.getLogger(__name__)

WAGE_PATH = DATA_RAW / "official" / "wagegrowthdata.xlsx"
WAGE_SHEET = "data_overall"
INDICATOR_ID = "ATLANTA_WAGE_OVERALL"
SOURCE_COL = "Overall"


def _read_atlanta_wage_raw() -> pd.Series:
    raw = pd.read_excel(WAGE_PATH, sheet_name=WAGE_SHEET, header=1)
    # First column is the date (no header in source).
    raw = raw.rename(columns={raw.columns[0]: "date"})
    if SOURCE_COL not in raw.columns:
        raise ValueError(
            f"Atlanta wage: '{SOURCE_COL}' column missing, have {list(raw.columns)}"
        )
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw = raw.dropna(subset=["date"])
    # '.' means missing - coerce to NaN
    raw[SOURCE_COL] = pd.to_numeric(raw[SOURCE_COL], errors="coerce")
    raw = raw.dropna(subset=[SOURCE_COL])
    raw = raw.sort_values("date").set_index("date")
    raw = raw[~raw.index.duplicated(keep="last")]
    s = raw[SOURCE_COL].astype(float)
    s.name = INDICATOR_ID
    return s


def load_atlanta_wage(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[pd.Series, IndicatorMetadata]:
    raw = _read_atlanta_wage_raw()

    if apply_pipeline:
        result = run_universal_pipeline(
            raw,
            indicator_id=INDICATOR_ID,
            unit="pct",
            native_freq="M",
            expected_min=0.0, expected_max=10.0,
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
        source="ATLANTA_FED_WAGE_XLSX",
        frequency="M",
        first_obs=first_obs, last_obs=last_obs,
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=False,
        unit="pct",
        release_lag_days=21,  # mid-following-month release
        description=(
            "Atlanta Fed Wage Growth Tracker (12-month moving average of "
            "median hourly wage growth, % YoY). Aggregate / overall."
        ),
        expected_min=0.0, expected_max=10.0,
        extra={
            "tier": "2A",
            "source_file": WAGE_PATH.name,
            "source_sheet": WAGE_SHEET,
            "source_column": SOURCE_COL,
            "full_history_revisable": True,
            "vintage_caveat": (
                "Atlanta Fed revises entire series with each monthly release; "
                "backtest may have ~1-3% optimistic bias from latest "
                "methodology being applied to historical values."
            ),
            "n_outliers_iqr5": n_outliers,
            "n_obs": int(series.notna().sum()),
        },
    )

    if apply_pipeline:
        cache_series_to_parquet(
            series, cache_dir=DATA_CACHE,
            file_stem=f"official_{INDICATOR_ID}",
            column_name=INDICATOR_ID,
            metadata=meta.to_dict(),
        )
    return series, meta


class AtlantaWageLoader(Loader):
    def load(self):
        s, m = load_atlanta_wage()
        return s.to_frame(), {m.indicator_id: m}


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    s, meta = load_atlanta_wage()
    obs = s.dropna()
    print(f"{INDICATOR_ID}: n_obs={len(obs):,}  first={meta.first_obs.date()}  "
          f"last={meta.last_obs.date()}  current={obs.iloc[-1]:.3f}%")
