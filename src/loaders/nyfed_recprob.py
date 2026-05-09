"""NY Fed Recession Probability + NBER recession label loader.

File: ``data/raw/official/allmonth.xls``
Sheet: ``rec_prob``

Two outputs:
  * ``NYFED_REC_PROB`` - 12-month-ahead recession probability (share, 0-1)
  * ``NBER_REC_LABEL`` - binary NBER recession indicator (training label
    for walk-forward backtest). Tagged with ``role="backtest_label"``.

The label is the AUTHORITATIVE training target for the recession side
of CRPS. It's derived directly from NBER's published peak/trough dates,
so vintage-aware backtest code must look it up at the appropriate
historical vintage rather than using the latest revision.

Tier: 2B (build guide Section 21.1 designation).
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

NYFED_PATH = DATA_RAW / "official" / "allmonth.xls"
NYFED_SHEET = "rec_prob"

REC_PROB_COL = "Rec_prob"
NBER_COL = "NBER_Rec"


def _read_nyfed_raw() -> pd.DataFrame:
    df = pd.read_excel(NYFED_PATH, sheet_name=NYFED_SHEET)
    if "Date" not in df.columns:
        raise ValueError(f"NY Fed: missing 'Date' column, got {list(df.columns)}")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    df = df[~df["Date"].duplicated(keep="last")]
    df = df.set_index("Date")
    return df


def load_nyfed_recprob(
    *, force_refresh: bool = False, apply_pipeline: bool = True
) -> tuple[dict[str, pd.Series], dict[str, IndicatorMetadata]]:
    raw = _read_nyfed_raw()

    rec_prob_raw = raw[REC_PROB_COL].astype(float)
    rec_prob_raw.name = "NYFED_REC_PROB"

    nber_raw = raw[NBER_COL].astype(float)
    nber_raw.name = "NBER_REC_LABEL"
    # Source label is non-null up to NBER's latest determination; trailing
    # NaNs reflect "not yet declared" rather than "no recession". Capture
    # the boundary so we can mask the post-alignment ffill back to NaN.
    nber_last_known = nber_raw.dropna().index.max()

    series_out: dict[str, pd.Series] = {}
    meta_out: dict[str, IndicatorMetadata] = {}

    # ---- NYFED_REC_PROB ----
    if apply_pipeline:
        rp_result = run_universal_pipeline(
            rec_prob_raw,
            indicator_id="NYFED_REC_PROB",
            unit="share",
            native_freq="M",
            expected_min=0.0, expected_max=1.01,
        )
        rp_series = rp_result.series
        rp_first, rp_last = rp_result.raw_first_obs, rp_result.raw_last_obs
        rp_n_out = rp_result.n_outliers
    else:
        rp_series, rp_first, rp_last, rp_n_out = (
            rec_prob_raw, rec_prob_raw.index.min(),
            rec_prob_raw.index.max(), 0,
        )

    rp_meta = IndicatorMetadata(
        indicator_id="NYFED_REC_PROB",
        source="NYFED_ALLMONTH_XLS",
        frequency="M",
        first_obs=rp_first, last_obs=rp_last,
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=False,
        unit="share",
        release_lag_days=10,
        description=(
            "NY Fed yield-curve-based 12-month-ahead recession probability "
            "(Estrella & Mishkin model)."
        ),
        expected_min=0.0, expected_max=1.01,
        extra={
            "tier": "2B",
            "source_file": NYFED_PATH.name,
            "source_sheet": NYFED_SHEET,
            "n_outliers_iqr5": rp_n_out,
            "n_obs": int(rp_series.notna().sum()),
        },
    )
    series_out["NYFED_REC_PROB"] = rp_series
    meta_out["NYFED_REC_PROB"] = rp_meta

    if apply_pipeline:
        cache_series_to_parquet(
            rp_series, cache_dir=DATA_CACHE,
            file_stem="official_NYFED_REC_PROB",
            column_name="NYFED_REC_PROB",
            metadata=rp_meta.to_dict(),
        )

    # ---- NBER_REC_LABEL ----
    if apply_pipeline:
        nb_result = run_universal_pipeline(
            nber_raw,
            indicator_id="NBER_REC_LABEL",
            unit="binary",
            native_freq="M",
            expected_min=0, expected_max=1,
        )
        nb_series = nb_result.series.copy()
        # Mask post-NBER-determination dates back to NaN so downstream code
        # doesn't treat ffilled "0"/"1" as a confirmed label.
        nb_series.loc[nb_series.index > nber_last_known] = pd.NA
        nb_first, nb_last = nb_result.raw_first_obs, nb_result.raw_last_obs
        nb_n_out = nb_result.n_outliers
    else:
        nb_series = nber_raw
        nb_first, nb_last = nber_raw.index.min(), nber_raw.index.max()
        nb_n_out = 0

    nb_meta = IndicatorMetadata(
        indicator_id="NBER_REC_LABEL",
        source="NYFED_ALLMONTH_XLS",
        frequency="M",
        first_obs=nb_first, last_obs=nb_last,
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=False,
        unit="binary",
        release_lag_days=180,  # NBER typically declares 6-18 months after the fact
        description=(
            "NBER recession indicator (1 = peak-to-trough). THIS IS THE "
            "TRAINING LABEL for the walk-forward CRPS backtest. Trailing "
            "values past the last NBER determination are masked NaN."
        ),
        expected_min=0, expected_max=1,
        extra={
            "tier": "2B",
            "role": "backtest_label",
            "source_file": NYFED_PATH.name,
            "source_sheet": NYFED_SHEET,
            "last_known_label_date": nber_last_known.isoformat(),
            "n_outliers_iqr5": nb_n_out,
            "n_obs": int(nb_series.notna().sum()),
        },
    )
    series_out["NBER_REC_LABEL"] = nb_series
    meta_out["NBER_REC_LABEL"] = nb_meta

    if apply_pipeline:
        cache_series_to_parquet(
            nb_series, cache_dir=DATA_CACHE,
            file_stem="official_NBER_REC_LABEL",
            column_name="NBER_REC_LABEL",
            metadata=nb_meta.to_dict(),
        )

    return series_out, meta_out


class NyfedRecProbLoader(Loader):
    def load(self):
        series_dict, meta_dict = load_nyfed_recprob()
        return pd.concat(series_dict, axis=1), meta_dict


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    series, meta = load_nyfed_recprob()
    rp = series["NYFED_REC_PROB"].dropna()
    nb = series["NBER_REC_LABEL"].dropna()
    n_recessions = int((nb.diff() == 1).sum())
    print(f"NYFED_REC_PROB: {len(rp):,} non-null obs, last={rp.iloc[-1]:.4f}")
    print(f"NBER_REC_LABEL: {len(nb):,} non-null obs, "
          f"last_known={meta['NBER_REC_LABEL'].extra['last_known_label_date']}, "
          f"recessions(0->1 transitions)={n_recessions}")
