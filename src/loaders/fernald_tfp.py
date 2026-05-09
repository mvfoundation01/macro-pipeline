"""Fernald TFP loader (SF Fed productivity series, Build guide Phase 4B).

File: ``data/raw/official/Copy_of_data_quarterly_2025_02_12.xlsx``
Sheet: ``quarterly``

Header is on row 1 (row 0 is a free-form note). Date column is
``date`` with values like ``"1947:Q1"``.

Outputs (quarterly, from 1947-Q2 - 1947-Q1 has all-NaN):
  * FERNALD_TFP       (column ``dtfp``, growth rate %)
  * FERNALD_TFP_UTIL  (column ``dtfp_util``, utilization-adjusted)

Tier: 2A. Tagged ``structural=True`` to flag downstream as a slowly-
moving structural metric (not a cyclical signal).
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone

import pandas as pd

from src.config import DATA_CACHE, DATA_RAW
from src.loaders.base import IndicatorMetadata, Loader
from src.preprocessing import cache_series_to_parquet, run_universal_pipeline

log = logging.getLogger(__name__)

FERNALD_PATH = DATA_RAW / "official" / "Copy_of_data_quarterly_2025_02_12.xlsx"
FERNALD_SHEET = "quarterly"

FERNALD_SERIES_SPEC: list[tuple[str, str, float, float, str]] = [
    ("FERNALD_TFP", "dtfp", -25.0, 25.0,
     "Total Factor Productivity growth (Fernald, % annualized)"),
    ("FERNALD_TFP_UTIL", "dtfp_util", -25.0, 25.0,
     "Utilization-adjusted TFP growth (Fernald, % annualized)"),
]


def _quarter_to_ts(s: str) -> pd.Timestamp:
    """Parse ``"1947:Q1"`` -> 1947-01-01 (quarter-start)."""
    if not isinstance(s, str):
        return pd.NaT
    m = re.match(r"^\s*(\d{4})\s*:\s*Q([1-4])\s*$", s)
    if not m:
        return pd.NaT
    year = int(m.group(1))
    q = int(m.group(2))
    month = (q - 1) * 3 + 1
    return pd.Timestamp(year=year, month=month, day=1)


def _read_fernald_raw() -> pd.DataFrame:
    raw = pd.read_excel(FERNALD_PATH, sheet_name=FERNALD_SHEET, header=1)
    if "date" not in raw.columns:
        raise ValueError(
            f"Fernald: missing 'date' column, got {list(raw.columns)}"
        )
    raw["__date"] = raw["date"].apply(_quarter_to_ts)
    raw = raw.dropna(subset=["__date"]).set_index("__date")
    raw.index.name = "date"
    raw = raw[~raw.index.duplicated(keep="last")]
    return raw


def load_fernald_tfp(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[dict[str, pd.Series], dict[str, IndicatorMetadata]]:
    raw = _read_fernald_raw()
    series_out: dict[str, pd.Series] = {}
    meta_out: dict[str, IndicatorMetadata] = {}

    for indicator_id, source_col, lo, hi, description in FERNALD_SERIES_SPEC:
        if source_col not in raw.columns:
            raise ValueError(
                f"Fernald: column {source_col} missing for {indicator_id}"
            )
        s_raw = pd.to_numeric(raw[source_col], errors="coerce").dropna()
        s_raw.name = indicator_id

        if apply_pipeline:
            result = run_universal_pipeline(
                s_raw,
                indicator_id=indicator_id,
                unit="pct",
                native_freq="Q",
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
            source="SF_FED_FERNALD",
            frequency="Q",
            first_obs=first_obs, last_obs=last_obs,
            last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
            needs_vintage=False,
            unit="pct",
            release_lag_days=60,
            description=description,
            expected_min=lo, expected_max=hi,
            extra={
                "tier": "2A",
                "structural": True,
                "source_file": FERNALD_PATH.name,
                "source_sheet": FERNALD_SHEET,
                "source_column": source_col,
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


class FernaldTfpLoader(Loader):
    def load(self):
        series_dict, meta_dict = load_fernald_tfp()
        return pd.concat(series_dict, axis=1), meta_dict


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    series, meta = load_fernald_tfp()
    for sid, s in series.items():
        obs = s.dropna()
        print(f"{sid}: n_obs={len(obs):,}  first={meta[sid].first_obs.date()}  "
              f"last={meta[sid].last_obs.date()}  current={obs.iloc[-1]:.4f}")
