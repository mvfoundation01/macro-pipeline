"""IMF COFER (Composition of Foreign Exchange Reserves) loader.

File: ``data/raw/official/imf_cofer_2026_05_06.csv``

The CSV is wide (140 rows x 196 cols): metadata columns followed by
time columns (annual ``YYYY`` and quarterly ``YYYY-Qn``). We filter to
the World aggregate (SERIES_CODE prefix ``G001`` per this snapshot)
and the share-of-allocated-reserves quarterly pattern, then melt the
quarterly time columns into long format.

Outputs (quarterly, share 0-100%, from 1995-Q1 to 2025-Q4):
  * USD_RESERVE_SHARE
  * EUR_RESERVE_SHARE
  * JPY_RESERVE_SHARE
  * GBP_RESERVE_SHARE
  * CHF_RESERVE_SHARE
  * CNY_RESERVE_SHARE  (post-2016)

Tier: 2A.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime

import pandas as pd

from macro_pipeline.config import DATA_CACHE, DATA_RAW
from macro_pipeline.loaders.base import IndicatorMetadata, Loader
from macro_pipeline.preprocessing import cache_series_to_parquet, run_universal_pipeline

log = logging.getLogger(__name__)

IMF_PATH = DATA_RAW / "official" / "imf_cofer_2026_05_06.csv"

# (indicator_id, currency_code_in_series, description)
COFER_CURRENCIES: list[tuple[str, str, str]] = [
    ("USD_RESERVE_SHARE", "USD", "USD share of allocated foreign-exchange reserves (%)"),
    ("EUR_RESERVE_SHARE", "EUR", "EUR share of allocated FX reserves (%)"),
    ("JPY_RESERVE_SHARE", "JPY", "JPY share of allocated FX reserves (%)"),
    ("GBP_RESERVE_SHARE", "GBP", "GBP share of allocated FX reserves (%)"),
    ("CHF_RESERVE_SHARE", "CHF", "CHF share of allocated FX reserves (%)"),
    ("CNY_RESERVE_SHARE", "CNY", "CNY share of allocated FX reserves (%)"),
]

# Match e.g. ``G001.AFXRA.CI_USD.SHRO_PT.Q``
SERIES_CODE_RE = re.compile(
    r"^G\d{3}\.AFXRA\.CI_(?P<currency>[A-Z]{3,4})\.SHRO_PT\.Q$"
)
# Match quarterly columns like "2024-Q1" (skip bare "2024").
QUARTER_COL_RE = re.compile(r"^(?P<year>\d{4})-Q(?P<q>[1-4])$")


def _quarter_label_to_ts(label: str) -> pd.Timestamp:
    m = QUARTER_COL_RE.match(label)
    if not m:
        return pd.NaT
    year = int(m.group("year"))
    q = int(m.group("q"))
    month = (q - 1) * 3 + 1
    return pd.Timestamp(year=year, month=month, day=1)


def _read_imf_raw() -> pd.DataFrame:
    df = pd.read_csv(IMF_PATH)
    required = {"COUNTRY", "SERIES_CODE", "FXR_CURRENCY"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"IMF COFER: missing required columns {missing}")
    return df


def _world_share_quarterly_subset(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to World rows whose series_code matches share-quarterly pattern."""
    world = df[df["COUNTRY"] == "World"].copy()
    matches = world["SERIES_CODE"].astype(str).map(
        lambda s: SERIES_CODE_RE.match(s)
    )
    world["_currency"] = matches.map(
        lambda m: m.group("currency") if m else None
    )
    return world.dropna(subset=["_currency"])


def _melt_quarterly_columns(world: pd.DataFrame) -> pd.DataFrame:
    """Reshape: rows = (currency, date), value = share."""
    quarter_cols = [c for c in world.columns if QUARTER_COL_RE.match(str(c))]
    if not quarter_cols:
        raise ValueError("IMF COFER: no quarterly time columns found")
    long = world.melt(
        id_vars=["_currency"],
        value_vars=quarter_cols,
        var_name="quarter_label",
        value_name="share",
    )
    long["date"] = long["quarter_label"].apply(_quarter_label_to_ts)
    long = long.dropna(subset=["date"])
    long["share"] = pd.to_numeric(long["share"], errors="coerce")
    long = long.sort_values(["_currency", "date"])
    return long


def load_imf_cofer(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[dict[str, pd.Series], dict[str, IndicatorMetadata]]:
    raw = _read_imf_raw()
    world = _world_share_quarterly_subset(raw)
    long = _melt_quarterly_columns(world)

    series_out: dict[str, pd.Series] = {}
    meta_out: dict[str, IndicatorMetadata] = {}

    for indicator_id, currency, description in COFER_CURRENCIES:
        sub = long[long["_currency"] == currency]
        if sub.empty:
            log.warning("IMF COFER: no rows for currency %s", currency)
            continue
        s_raw = sub.set_index("date")["share"].astype(float).dropna()
        s_raw = s_raw[~s_raw.index.duplicated(keep="last")]
        s_raw.name = indicator_id

        if apply_pipeline:
            result = run_universal_pipeline(
                s_raw,
                indicator_id=indicator_id,
                unit="pct",
                native_freq="Q",
                expected_min=0.0, expected_max=100.0,
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
            source="IMF_COFER_CSV",
            frequency="Q",
            first_obs=first_obs, last_obs=last_obs,
            last_update=pd.Timestamp(datetime.now(UTC).replace(tzinfo=None)),
            needs_vintage=False,
            unit="pct",
            release_lag_days=90,
            description=description,
            expected_min=0.0, expected_max=100.0,
            extra={
                "tier": "2A",
                "currency": currency,
                "source_file": IMF_PATH.name,
                "country_aggregate": "World",
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


class ImfCoferLoader(Loader):
    def load(self):
        series_dict, meta_dict = load_imf_cofer()
        return pd.concat(series_dict, axis=1), meta_dict


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    series, meta = load_imf_cofer()
    for sid, s in series.items():
        obs = s.dropna()
        if obs.empty:
            print(f"{sid}: EMPTY")
            continue
        print(f"{sid}: n_obs={len(obs):,}  first={meta[sid].first_obs.date()}  "
              f"last={meta[sid].last_obs.date()}  current={obs.iloc[-1]:.4f}")
