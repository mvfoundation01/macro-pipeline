"""NY Fed ACM Term Premium loader (Build guide Phase 4B).

File: ``data/raw/official/ACMTermPremium.xls``
Sheet: ``ACM Daily``  (the ``ACM Monthly`` sheet is ignored.)

ACM = Adrian, Crump, Moench (NY Fed). The file has 31 columns:
Date + ACMY01-10 (model-fitted yields) + ACMTP01-10 (term premiums)
+ ACMRNY01-10 (risk-neutral yields).

Outputs:
  * ACM_TP_10Y  - 10Y term premium (%)  -- the headline series
  * ACM_TP_5Y   - 5Y term premium  (comparison reference)
  * ACM_RNY_10Y - 10Y risk-neutral yield (= GS10 - TP10Y)

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

ACM_PATH = DATA_RAW / "official" / "ACMTermPremium.xls"
ACM_SHEET = "ACM Daily"

# (indicator_id, source_col_name, lo, hi, description)
ACM_SERIES_SPEC: list[tuple[str, str, float, float, str]] = [
    ("ACM_TP_10Y", "ACMTP10",  -3.0, 6.0,
     "ACM 10-Year nominal Treasury term premium (%)"),
    ("ACM_TP_5Y", "ACMTP05",   -3.0, 6.0,
     "ACM 5-Year nominal Treasury term premium (%)"),
    ("ACM_RNY_10Y", "ACMRNY10", 0.0, 15.0,
     "ACM 10-Year risk-neutral yield (= GS10 - TP10Y, %)"),
]


def _read_acm_raw() -> pd.DataFrame:
    df = pd.read_excel(ACM_PATH, sheet_name=ACM_SHEET)
    if "DATE" not in df.columns:
        raise ValueError(f"ACM: missing DATE column, got {list(df.columns)}")
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df = df.dropna(subset=["DATE"]).sort_values("DATE")
    df = df.set_index("DATE")
    df = df[~df.index.duplicated(keep="last")]
    return df


def load_acm_termpremium(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[dict[str, pd.Series], dict[str, IndicatorMetadata]]:
    raw = _read_acm_raw()
    series_out: dict[str, pd.Series] = {}
    meta_out: dict[str, IndicatorMetadata] = {}

    for indicator_id, source_col, lo, hi, description in ACM_SERIES_SPEC:
        if source_col not in raw.columns:
            raise ValueError(
                f"ACM: column {source_col} missing for {indicator_id}"
            )
        s_raw = pd.to_numeric(raw[source_col], errors="coerce")
        s_raw.name = indicator_id

        if apply_pipeline:
            result = run_universal_pipeline(
                s_raw,
                indicator_id=indicator_id,
                unit="pct",
                native_freq="D",
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
            source="NYFED_ACM_XLS",
            frequency="D",
            first_obs=first_obs, last_obs=last_obs,
            last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
            needs_vintage=False,
            unit="pct",
            release_lag_days=7,
            description=description,
            expected_min=lo, expected_max=hi,
            extra={
                "tier": "2A",
                "source_file": ACM_PATH.name,
                "source_sheet": ACM_SHEET,
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


class AcmTermPremiumLoader(Loader):
    def load(self):
        series_dict, meta_dict = load_acm_termpremium()
        return pd.concat(series_dict, axis=1), meta_dict


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    series, meta = load_acm_termpremium()
    for sid, s in series.items():
        obs = s.dropna()
        print(f"{sid}: n_obs={len(obs):,}  first={meta[sid].first_obs.date()}  "
              f"last={meta[sid].last_obs.date()}  current={obs.iloc[-1]:.4f}")
