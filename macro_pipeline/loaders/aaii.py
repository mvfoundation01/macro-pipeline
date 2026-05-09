"""AAII Investor Sentiment loader (Build guide Phase 4C).

File: ``data/raw/official/sentiment.xls``
Sheet: ``SENTIMENT``

Header row 3, data starts row 5. Pre-1987-07-24 rows have NaN for the
Bullish/Neutral/Bearish columns (only the long-run averages are
populated) - we filter those rows out.

Source storage convention: the Bullish/Neutral/Bearish/Spread columns
are stored as DECIMAL SHARE in Excel (0.36 = 36% bullish). We multiply
by 100 to publish percent-formatted series to match the rest of the
project's ``pct`` unit convention.

Outputs (weekly Wednesday cadence, from 1987-07-24):
  * AAII_BULLISH         - % bullish responses (0-100)
  * AAII_BEARISH         - % bearish responses
  * AAII_BULL_BEAR_SPREAD - bullish - bearish (in pp, signed)
  * AAII_BULL_8WMA       - 8-week moving avg of bullish %

Tier: 2A.
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import pandas as pd

from macro_pipeline.config import DATA_CACHE, DATA_RAW
from macro_pipeline.loaders.base import IndicatorMetadata, Loader
from macro_pipeline.preprocessing import cache_series_to_parquet, run_universal_pipeline

log = logging.getLogger(__name__)

AAII_PATH = DATA_RAW / "official" / "sentiment.xls"
AAII_SHEET = "SENTIMENT"

# (indicator_id, source_col_name, lo, hi, derived, description)
AAII_SERIES_SPEC: list[tuple[str, str, float, float, bool, str]] = [
    ("AAII_BULLISH", "Bullish",  0.0, 100.0, False,
     "AAII Investor Sentiment Survey - % bullish responses (weekly Wed)"),
    ("AAII_BEARISH", "Bearish",  0.0, 100.0, False,
     "AAII Investor Sentiment Survey - % bearish responses"),
    # Source columns under header=3: "Spread" and "Mov Avg" (the multi-row
    # banner labels collapse to row 3's terse header names).
    ("AAII_BULL_BEAR_SPREAD", "Spread", -100.0, 100.0, False,
     "AAII Bullish - Bearish (percentage points, signed)"),
    ("AAII_BULL_8WMA", "Mov Avg", 0.0, 100.0, False,
     "AAII 8-week moving average of bullish %"),
]


def _read_aaii_raw() -> pd.DataFrame:
    """Read sheet with header=3 and parse the dated weekly rows."""
    raw = pd.read_excel(AAII_PATH, sheet_name=AAII_SHEET, header=3)
    # Column 0 is the date (header was "Date" or NaN sometimes).
    raw = raw.rename(columns={raw.columns[0]: "Date"})
    raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
    raw = raw.dropna(subset=["Date"]).sort_values("Date")
    raw = raw[~raw["Date"].duplicated(keep="last")]
    return raw.set_index("Date")


def load_aaii(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[dict[str, pd.Series], dict[str, IndicatorMetadata]]:
    raw = _read_aaii_raw()

    # Filter pre-1990 rows where Bullish/Neutral/Bearish are NaN (the
    # long-run-average columns persist further back, but the survey
    # itself only starts 1987-07-24).
    survey_cols = ["Bullish", "Neutral", "Bearish"]
    available = [c for c in survey_cols if c in raw.columns]
    if not available:
        raise ValueError(
            f"AAII: none of {survey_cols} present, got {list(raw.columns)}"
        )
    raw = raw.dropna(subset=available, how="all")

    series_out: dict[str, pd.Series] = {}
    meta_out: dict[str, IndicatorMetadata] = {}

    for indicator_id, source_col, lo, hi, _, description in AAII_SERIES_SPEC:
        if source_col not in raw.columns:
            raise ValueError(
                f"AAII: column '{source_col}' missing for {indicator_id} "
                f"(have: {list(raw.columns)})"
            )
        # Source is decimal share -> multiply by 100 for pct convention.
        s_raw = pd.to_numeric(raw[source_col], errors="coerce") * 100.0
        s_raw = s_raw.dropna()
        s_raw.name = indicator_id

        if apply_pipeline:
            result = run_universal_pipeline(
                s_raw,
                indicator_id=indicator_id,
                unit="pct",
                native_freq="W",
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
            source="AAII_XLS",
            frequency="W",
            first_obs=first_obs, last_obs=last_obs,
            last_update=pd.Timestamp(datetime.now(UTC).replace(tzinfo=None)),
            needs_vintage=False,
            unit="pct",
            release_lag_days=2,
            description=description,
            expected_min=lo, expected_max=hi,
            extra={
                "tier": "2A",
                "source_file": AAII_PATH.name,
                "source_sheet": AAII_SHEET,
                "source_column": source_col,
                "source_storage_convention": "decimal_share_x100",
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


class AaiiLoader(Loader):
    def load(self):
        series_dict, meta_dict = load_aaii()
        return pd.concat(series_dict, axis=1), meta_dict


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    series, meta = load_aaii()
    for sid, s in series.items():
        obs = s.dropna()
        print(f"{sid}: n_obs={len(obs):,}  first={meta[sid].first_obs.date()}  "
              f"last={meta[sid].last_obs.date()}  current={obs.iloc[-1]:.2f}")
