"""FINRA Customer Margin Balances loader (Build guide Phase 4A).

File: ``data/raw/official/marginstatistics.xlsx``
Sheet: ``Customer Margin Balances``

CRITICAL: source has NEWEST-FIRST ordering. We reverse during parse so
the cached series runs oldest -> newest.

Headline output: ``FINRA_MARGIN_DEBT`` (Debit Balances column),
monthly, in millions USD.

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

FINRA_PATH = DATA_RAW / "official" / "marginstatistics.xlsx"
FINRA_SHEET = "Customer Margin Balances"
DEBIT_COL = "Debit Balances in Customers' Securities Margin Accounts"
INDICATOR_ID = "FINRA_MARGIN_DEBT"


def _read_finra_raw() -> pd.Series:
    df = pd.read_excel(FINRA_PATH, sheet_name=FINRA_SHEET)
    if "Year-Month" not in df.columns or DEBIT_COL not in df.columns:
        raise ValueError(
            f"FINRA: expected 'Year-Month' and '{DEBIT_COL}', "
            f"got {list(df.columns)}"
        )

    # Year-Month is typically e.g. "2026-03" or "Mar-26".
    raw = df["Year-Month"].astype(str).str.strip()
    parsed = pd.to_datetime(raw + "-01", errors="coerce", format="%Y-%m-%d")
    if parsed.isna().sum() > 0.5 * len(parsed):
        # Fall back to abbreviated-month parsing.
        parsed = pd.to_datetime(raw, errors="coerce")

    df = df.assign(date=parsed).dropna(subset=["date"])
    # Source is NEWEST FIRST - sort_values flips to oldest-first regardless.
    df = df.sort_values("date")
    df = df[~df["date"].duplicated(keep="last")]
    # Move dates to month-end for consistency with monthly FRED series.
    s = df.set_index("date")[DEBIT_COL].astype(float)
    s.index = s.index + pd.offsets.MonthEnd(0)
    s.name = INDICATOR_ID
    return s


def load_finra_margin(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[pd.Series, IndicatorMetadata]:
    raw = _read_finra_raw()

    if apply_pipeline:
        result = run_universal_pipeline(
            raw,
            indicator_id=INDICATOR_ID,
            unit="M_USD",
            native_freq="M",
            expected_min=1e3, expected_max=2e6,
        )
        series = result.series
        first_obs, last_obs = result.raw_first_obs, result.raw_last_obs
        n_outliers = result.n_outliers
    else:
        series = raw
        first_obs, last_obs = raw.index.min(), raw.index.max()
        n_outliers = 0

    meta = IndicatorMetadata(
        indicator_id=INDICATOR_ID,
        source="FINRA_XLSX",
        frequency="M",
        first_obs=first_obs,
        last_obs=last_obs,
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=False,
        unit="M_USD",
        release_lag_days=21,  # ~3rd week of the following month
        description=(
            "FINRA aggregate customer margin debit balances (millions USD, "
            "monthly). Source `marginstatistics.xlsx` is published newest-first "
            "and reversed during parse."
        ),
        expected_min=1e3, expected_max=2e6,
        extra={
            "tier": "2A",
            "source_file": FINRA_PATH.name,
            "source_sheet": FINRA_SHEET,
            "source_order": "newest_first_reversed_on_load",
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


class FinraMarginLoader(Loader):
    def load(self):
        s, m = load_finra_margin()
        return s.to_frame(), {m.indicator_id: m}


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    s, meta = load_finra_margin()
    print(f"FINRA_MARGIN_DEBT: {len(s.dropna()):,} non-null obs, "
          f"first={meta.first_obs.date()}  last={meta.last_obs.date()}  "
          f"current=${s.dropna().iloc[-1]:,.0f}M")
