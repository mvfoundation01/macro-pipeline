"""Shiller ie_data.xls loader (Build guide Phase 4B).

File: ``data/raw/official/ie_data.xls``
Sheet: ``Data``

The header spans rows 5-7; data starts row 8. The date column uses a
decimal ``YYYY.MM`` format where January = ``.01``, October = ``.10``,
December = ``.12`` (NOT ``pd.to_datetime``-compatible).

Outputs (all monthly, from 1871-01):
  * SHILLER_PRICE      (col 1, S&P composite)
  * SHILLER_DIVIDEND   (col 2)
  * SHILLER_EARNINGS   (col 3)
  * SHILLER_CPI        (col 4)
  * SHILLER_GS10       (col 6, 10-Year Treasury yield)
  * SHILLER_REAL_PRICE (col 7, CPI-adjusted price)
  * SHILLER_TR_PRICE   (col 9, real total return cumulative)  <- regression target
  * SHILLER_CAPE       (col 12, P/E10 valuation)              <- key signal
  * SHILLER_TR_CAPE    (col 14, total-return CAPE)

We use POSITIONAL column access (``iloc[:, N]``) because Shiller adds
new columns over time. Layout verified for the 2024+ release.

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

SHILLER_PATH = DATA_RAW / "official" / "ie_data.xls"
SHILLER_SHEET = "Data"

# (indicator_id, source_col_index, unit, lo, hi, role, use_for, description)
SHILLER_SERIES_SPEC: list[tuple] = [
    ("SHILLER_PRICE",      1,  "index", 1.0,    1e5,  None, [],
     "S&P Composite price (nominal)"),
    ("SHILLER_DIVIDEND",   2,  "index", 0.0,    500,  None, [],
     "S&P Composite dividend per share (nominal)"),
    ("SHILLER_EARNINGS",   3,  "index", 0.0,    1000, None, [],
     "S&P Composite earnings per share (nominal)"),
    ("SHILLER_CPI",        4,  "index", 5.0,    1000, None, [],
     "Consumer Price Index"),
    ("SHILLER_GS10",       6,  "pct",   0.0,    20.0, None, [],
     "10-Year US Treasury yield (Long Interest Rate)"),
    ("SHILLER_REAL_PRICE", 7,  "index", 50.0,   1e5,  None, [],
     "Real (CPI-adjusted) S&P Composite price"),
    ("SHILLER_TR_PRICE",   9,  "index", 50.0,   1e8,  "regression_target",
     ["forward_return_calc", "r_squared_regression"],
     "Real total return cumulative price (dividends reinvested, CPI-adjusted)"),
    ("SHILLER_CAPE",       12, "ratio", 3.0,    60.0, None, [],
     "Cyclically Adjusted P/E (Shiller CAPE / P/E10)"),
    ("SHILLER_TR_CAPE",    14, "ratio", 3.0,    100.0, None, [],
     "Total return CAPE"),
]


def _shiller_decimal_to_ts(x) -> pd.Timestamp:
    """Parse Shiller's ``YYYY.MM`` decimal where Jan=.01, Oct=.10, Dec=.12.

    Pandas reads the column as float, which loses the trailing zero on
    ``2024.10``. We format with two decimals to recover the literal month.
    """
    if pd.isna(x):
        return pd.NaT
    try:
        s = f"{float(x):.2f}"
    except (TypeError, ValueError):
        return pd.NaT
    if "." not in s:
        return pd.NaT
    year_str, month_str = s.split(".")
    try:
        year = int(year_str)
        month = int(month_str)
    except ValueError:
        return pd.NaT
    if not (1 <= month <= 12):
        return pd.NaT
    return pd.Timestamp(year=year, month=month, day=1)


def _read_shiller_raw() -> pd.DataFrame:
    raw = pd.read_excel(SHILLER_PATH, sheet_name=SHILLER_SHEET, header=7)
    # Date is in column 0 - reparse defensively.
    raw["__date"] = raw.iloc[:, 0].apply(_shiller_decimal_to_ts)
    raw = raw.dropna(subset=["__date"])
    raw = raw.set_index("__date")
    raw.index.name = "date"
    raw = raw[~raw.index.duplicated(keep="last")]
    return raw


def load_shiller(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[dict[str, pd.Series], dict[str, IndicatorMetadata]]:
    raw = _read_shiller_raw()
    series_out: dict[str, pd.Series] = {}
    meta_out: dict[str, IndicatorMetadata] = {}

    for indicator_id, col_idx, unit, lo, hi, role, use_for, description in SHILLER_SERIES_SPEC:
        if col_idx >= raw.shape[1]:
            raise ValueError(
                f"Shiller: column index {col_idx} out of range "
                f"(file has {raw.shape[1]} columns); layout may have shifted"
            )
        s_raw = pd.to_numeric(raw.iloc[:, col_idx], errors="coerce")
        s_raw = s_raw.dropna()
        s_raw.name = indicator_id

        if apply_pipeline:
            result = run_universal_pipeline(
                s_raw,
                indicator_id=indicator_id,
                unit=unit,
                native_freq="M",
                expected_min=lo, expected_max=hi,
            )
            series = result.series
            first_obs = result.raw_first_obs
            last_obs = result.raw_last_obs
            n_outliers = result.n_outliers
        else:
            series = s_raw
            first_obs, last_obs = s_raw.index.min(), s_raw.index.max()
            n_outliers = 0

        extra = {
            "tier": "2A",
            "source_file": SHILLER_PATH.name,
            "source_sheet": SHILLER_SHEET,
            "source_column_index": col_idx,
            "n_outliers_iqr5": n_outliers,
            "n_obs": int(series.notna().sum()),
        }
        if role:
            extra["role"] = role
        if use_for:
            extra["use_for"] = list(use_for)

        meta = IndicatorMetadata(
            indicator_id=indicator_id,
            source="SHILLER_XLS",
            frequency="M",
            first_obs=first_obs, last_obs=last_obs,
            last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
            needs_vintage=False,
            unit=unit,
            release_lag_days=30,
            description=description,
            expected_min=lo, expected_max=hi,
            extra=extra,
        )
        series_out[indicator_id] = series
        meta_out[indicator_id] = meta

        if apply_pipeline:
            cache_series_to_parquet(
                series, cache_dir=DATA_CACHE,
                file_stem=f"official_{indicator_id}",
                column_name=indicator_id,
                metadata=meta.to_dict(),
            )

    return series_out, meta_out


class ShillerLoader(Loader):
    def load(self):
        series_dict, meta_dict = load_shiller()
        return pd.concat(series_dict, axis=1), meta_dict


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    series, meta = load_shiller()
    for sid, s in series.items():
        s_obs = s.dropna()
        print(f"{sid}: n_obs={len(s_obs):,}  "
              f"first={meta[sid].first_obs.date()}  "
              f"last={meta[sid].last_obs.date()}  "
              f"current={s_obs.iloc[-1]:.4f}")
