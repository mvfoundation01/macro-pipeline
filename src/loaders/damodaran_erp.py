"""Damodaran Implied ERP loader (Build guide Phase 4A).

File: ``data/raw/official/damodaran_implied_erp_1960_2025.csv``
This is the transcribed CSV (NOT the stale ``histimpl.xls``).

Outputs four annual series:
  * ``DAMODARAN_ERP``    - Implied_ERP_FCFE (primary signal)
  * ``DAMODARAN_EY``     - Earnings_Yield
  * ``DAMODARAN_DY``     - Dividend_Yield
  * ``DAMODARAN_TBOND``  - 10Y Treasury Rate (used in ERP decomposition)

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

DAMODARAN_PATH = DATA_RAW / "official" / "damodaran_implied_erp_1960_2025.csv"

# (indicator_id, source_column, description, expected_min, expected_max)
DAMODARAN_SERIES_SPEC: list[tuple[str, str, str, float, float]] = [
    ("DAMODARAN_ERP", "Implied_ERP_FCFE",
     "Damodaran implied equity risk premium (FCFE-based)", 0.0, 15.0),
    ("DAMODARAN_EY", "Earnings_Yield",
     "Damodaran trailing earnings yield (S&P 500)", 0.0, 20.0),
    ("DAMODARAN_DY", "Dividend_Yield",
     "Damodaran trailing dividend yield (S&P 500)", 0.0, 8.0),
    ("DAMODARAN_TBOND", "TBond_Rate",
     "Damodaran year-end 10-Year US Treasury rate", 0.0, 20.0),
]


def _read_damodaran_raw() -> pd.DataFrame:
    df = pd.read_csv(DAMODARAN_PATH)
    if "Date" not in df.columns:
        raise ValueError(
            f"Damodaran: missing 'Date' column, got {list(df.columns)}"
        )
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    df = df[~df["Date"].duplicated(keep="last")]
    return df.set_index("Date")


def load_damodaran_erp(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[dict[str, pd.Series], dict[str, IndicatorMetadata]]:
    raw = _read_damodaran_raw()
    last_year = int(raw.index.max().year)
    series_out: dict[str, pd.Series] = {}
    meta_out: dict[str, IndicatorMetadata] = {}

    for indicator_id, source_col, description, lo, hi in DAMODARAN_SERIES_SPEC:
        if source_col not in raw.columns:
            raise ValueError(
                f"Damodaran: source column '{source_col}' missing for {indicator_id}"
            )
        s_raw = raw[source_col].astype(float)
        s_raw.name = indicator_id

        if apply_pipeline:
            result = run_universal_pipeline(
                s_raw,
                indicator_id=indicator_id,
                unit="pct",
                native_freq="A",
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

        meta = IndicatorMetadata(
            indicator_id=indicator_id,
            source="DAMODARAN_CSV",
            frequency="A",
            first_obs=first_obs, last_obs=last_obs,
            last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
            needs_vintage=False,
            unit="pct",
            release_lag_days=30,
            description=description,
            expected_min=lo, expected_max=hi,
            extra={
                "tier": "2A",
                "source_file": DAMODARAN_PATH.name,
                "source_column": source_col,
                "last_year_in_data": last_year,
                "n_outliers_iqr5": n_outliers,
                "n_obs": int(series.notna().sum()),
            },
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


class DamodaranErpLoader(Loader):
    def load(self):
        series_dict, meta_dict = load_damodaran_erp()
        return pd.concat(series_dict, axis=1), meta_dict


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    series, meta = load_damodaran_erp()
    for sid, s in series.items():
        print(f"{sid}: n_obs={int(s.notna().sum())}  "
              f"first={meta[sid].first_obs.date()}  "
              f"last={meta[sid].last_obs.date()}  "
              f"current={s.dropna().iloc[-1]:.3f}")
