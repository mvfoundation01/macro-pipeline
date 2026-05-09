"""Holston-Laubach-Williams natural rate (r*) loader, current-vintage only.

File: ``data/raw/official/Holston_Laubach_Williams_current_estimates.xlsx``
Sheet: ``HLW Estimates``

Header layout (verified):
  rows 0-3: free-form narrative
  row 4: section banners (Trend Growth | Other Determinants z |
                          Natural Rate r* | Output Gap)
  row 5: country sub-headers (US | Canada | Euro Area), repeated per section
  row 6+: data; Date column = real datetime

We extract US-only series via positional column index (the sub-header
text is fragile across releases).

Outputs (quarterly, from 1961-Q1):
  * HLW_RSTAR        - col 10  (US natural rate of interest, %)
  * HLW_TREND_GROWTH - col 2   (US annualized trend growth, %)
  * HLW_OUTPUT_GAP   - col 14  (US output gap, %)

Tier: 2A. Tagged ``vintage="current"`` - the 33-sheet
``..._real_time_estimates.xlsx`` will get its own vintage-aware loader
in Phase 4D.
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

HLW_PATH = DATA_RAW / "official" / "Holston_Laubach_Williams_current_estimates.xlsx"
HLW_SHEET = "HLW Estimates"

# (indicator_id, US column index, lo, hi, description)
HLW_SERIES_SPEC: list[tuple[str, int, float, float, str]] = [
    # Early-1960s r* estimate peaked just above 6%; allow 7 as ceiling.
    ("HLW_RSTAR", 10, -2.0, 7.0,
     "HLW US natural rate of interest r* (annualized %)"),
    ("HLW_TREND_GROWTH", 2, -2.0, 8.0,
     "HLW US trend growth g (annualized %)"),
    ("HLW_OUTPUT_GAP", 14, -15.0, 10.0,
     "HLW US output gap (% of potential)"),
]


def _read_hlw_raw() -> pd.DataFrame:
    """Skip header rows 0-5; data starts row 6."""
    raw = pd.read_excel(HLW_PATH, sheet_name=HLW_SHEET, header=None, skiprows=6)
    raw = raw.dropna(subset=[0])  # column 0 is Date
    raw[0] = pd.to_datetime(raw[0], errors="coerce")
    raw = raw.dropna(subset=[0]).set_index(0)
    raw.index.name = "date"
    raw = raw[~raw.index.duplicated(keep="last")]
    return raw


def load_hlw_rstar(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[dict[str, pd.Series], dict[str, IndicatorMetadata]]:
    raw = _read_hlw_raw()
    series_out: dict[str, pd.Series] = {}
    meta_out: dict[str, IndicatorMetadata] = {}

    for indicator_id, col_idx, lo, hi, description in HLW_SERIES_SPEC:
        if col_idx >= raw.shape[1]:
            raise ValueError(
                f"HLW: column index {col_idx} out of range "
                f"(file has {raw.shape[1]} columns)"
            )
        s_raw = pd.to_numeric(raw.iloc[:, col_idx], errors="coerce").dropna()
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
            source="NYFED_HLW_CURRENT_XLSX",
            frequency="Q",
            first_obs=first_obs, last_obs=last_obs,
            last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
            needs_vintage=False,  # vintage version comes in Phase 4D
            unit="pct",
            release_lag_days=120,  # NY Fed publishes after each quarter close
            description=description,
            expected_min=lo, expected_max=hi,
            extra={
                "tier": "2A",
                "vintage": "current",
                "country": "US",
                "source_file": HLW_PATH.name,
                "source_sheet": HLW_SHEET,
                "source_column_index": col_idx,
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


class HlwRstarLoader(Loader):
    def load(self):
        series_dict, meta_dict = load_hlw_rstar()
        return pd.concat(series_dict, axis=1), meta_dict


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    series, meta = load_hlw_rstar()
    for sid, s in series.items():
        obs = s.dropna()
        print(f"{sid}: n_obs={len(obs):,}  first={meta[sid].first_obs.date()}  "
              f"last={meta[sid].last_obs.date()}  current={obs.iloc[-1]:.4f}")
