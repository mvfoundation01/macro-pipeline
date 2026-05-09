"""Excess Bond Premium loader (Layer 1.5C.2).

Source: Gilchrist & Zakrajšek (2012, AER 102(4)) — the EBP isolates the
component of corporate bond spreads in excess of expected default risk.
Federal Reserve maintains an updated monthly version as a companion file
to a 2016 FEDS Notes piece (the URL has stayed stable since publication).

Schema of ``ebp_csv.csv``:
    date         monthly, MS-aligned
    gz_spread    GZ credit spread
    ebp          EBP itself (the residual)
    est_prob     12-month-ahead recession probability from Fed model

We expose the ``ebp`` column as the indicator. The other two columns are
informative but the build guide does not register them as separate
indicators (yet).

ChatGPT review note: EBP is a Tier 1A academic-gold-standard indicator,
distinct from the regular Y10-Y3M slope and from HY OAS regime. Adding
it closes a gap flagged in the AGGREGATED_REVIEW_FINDINGS doc (D3).
"""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from macro_pipeline.cache import read_cache_validated, write_cache_atomic
from macro_pipeline.config import DATA_CACHE, DATA_RAW
from macro_pipeline.loaders.base import IndicatorMetadata, Loader
from macro_pipeline.preprocessing import run_universal_pipeline

log = logging.getLogger(__name__)

EBP_URL = (
    "https://www.federalreserve.gov/econresdata/notes/feds-notes/2016/files/"
    "ebp_csv.csv"
)
EBP_LOCAL_PATH = DATA_RAW / "official" / "ebp_csv.csv"


def fetch_ebp_csv(*, force_refresh: bool = False, timeout: float = 30.0) -> Path:
    """Ensure the EBP CSV is on disk under ``data/raw/official/``."""
    EBP_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if EBP_LOCAL_PATH.exists() and not force_refresh:
        return EBP_LOCAL_PATH
    log.info("Downloading EBP CSV from %s", EBP_URL)
    try:
        resp = requests.get(EBP_URL, timeout=timeout)
        resp.raise_for_status()
    except (requests.RequestException, ConnectionError, TimeoutError) as exc:
        from macro_pipeline.exceptions import from_request_exception
        raise from_request_exception(
            exc, indicator_id="EBP", source="FED_BOARD_FEDS_NOTES",
            extra_context={"url": EBP_URL},
        ) from exc
    EBP_LOCAL_PATH.write_bytes(resp.content)
    return EBP_LOCAL_PATH


def load_ebp(
    *, force_refresh: bool = False,
) -> tuple[pd.Series, IndicatorMetadata]:
    """Return the monthly EBP series + metadata."""
    stem = "fed_EBP"
    parquet_path = DATA_CACHE / f"{stem}.parquet"
    if parquet_path.exists() and not force_refresh:
        cached = read_cache_validated(stem, DATA_CACHE)
        if cached is not None:
            df, cmeta = cached
            s = df.iloc[:, 0]
            s.name = "EBP"
            return s, _meta_from_cache(cmeta)

    path = fetch_ebp_csv(force_refresh=force_refresh)
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    if "ebp" not in df.columns:
        raise ValueError(
            f"EBP CSV at {path} missing 'ebp' column; saw {list(df.columns)}"
        )
    raw = df["ebp"].astype(float).dropna()

    result = run_universal_pipeline(
        raw, indicator_id="EBP", unit="pct",
        native_freq="M",
        expected_min=-3.0, expected_max=10.0,
    )
    series = result.series
    series.name = "EBP"

    extra = {
        "reference": "Gilchrist & Zakrajsek (2012) AER 102(4)",
        "academic_standard": True,
        "source_url": EBP_URL,
        "n_obs": int(series.notna().sum()),
        "n_outliers_iqr5": result.n_outliers,
    }
    meta = IndicatorMetadata(
        indicator_id="EBP",
        source="FED_BOARD_FEDS_NOTES",
        frequency="M",
        first_obs=result.raw_first_obs,
        last_obs=result.raw_last_obs,
        last_update=pd.Timestamp(datetime.now(UTC).replace(tzinfo=None)),
        needs_vintage=False,
        unit="pct",
        # FEDS Notes publishes the file with about a one-month lag —
        # last_obs is typically the prior month-end on a current pull.
        release_lag_days=30,
        description=(
            "Excess Bond Premium (Gilchrist-Zakrajsek 2012); the credit "
            "spread component in excess of expected default risk. Updated "
            "monthly by the Federal Reserve Board in FEDS Notes companion "
            "file."
        ),
        expected_min=-3.0,
        expected_max=10.0,
        extra=extra,
    )

    write_cache_atomic(
        stem, series.to_frame("EBP"), meta.to_dict(),
        DATA_CACHE, pipeline_processed=True,
    )
    return series, meta


def _meta_from_cache(cmeta: dict) -> IndicatorMetadata:
    return IndicatorMetadata(
        indicator_id="EBP",
        source=cmeta.get("source", "FED_BOARD_FEDS_NOTES"),
        frequency=cmeta.get("frequency", "M"),
        first_obs=pd.Timestamp(cmeta["first_obs"]) if cmeta.get("first_obs") else pd.NaT,
        last_obs=pd.Timestamp(cmeta["last_obs"]) if cmeta.get("last_obs") else pd.NaT,
        last_update=pd.Timestamp(cmeta["last_update"]) if cmeta.get("last_update") else pd.NaT,
        needs_vintage=bool(cmeta.get("needs_vintage", False)),
        unit=cmeta.get("unit", "pct"),
        release_lag_days=int(cmeta.get("release_lag_days", 30)),
        description=cmeta.get("description", ""),
        expected_min=cmeta.get("expected_min"),
        expected_max=cmeta.get("expected_max"),
        extra={k: v for k, v in cmeta.items() if k not in {
            "indicator_id", "source", "frequency", "first_obs", "last_obs",
            "last_update", "needs_vintage", "unit", "release_lag_days",
            "description", "expected_min", "expected_max",
            "data_quality_suspect_periods",
        }},
    )


class EbpLoader(Loader):
    def load(self):
        s, m = load_ebp()
        return s.to_frame("EBP"), {m.indicator_id: m}


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    s, m = load_ebp(force_refresh=True)
    print(f"EBP: {len(s)} obs, {s.index.min().date()} -> {s.index.max().date()}, "
          f"latest={s.iloc[-1]:.3f}%")
    print(f"Mean: {s.mean():.3f}, std: {s.std():.3f}")
