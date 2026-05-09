"""CFTC Traders in Financial Futures (TFF) S&P 500 loader.

Build guide Section 22. Pulls weekly trader-category positioning for the
E-Mini S&P 500 future (CFTC contract code ``13874A``) from the CFTC
Socrata public reporting API. Coverage: 2006-06-13 to current.

Release schedule: each Tuesday's positions are released the following
Friday at 3:30pm ET. We cache for 7 days.

Tier: 2C (official, public API).
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import DATA_CACHE
from src.loaders.base import IndicatorMetadata, Loader

log = logging.getLogger(__name__)

ENDPOINT = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
HEADERS = {"User-Agent": "Mozilla/5.0 macro-pipeline/1.0"}
TTL_DAYS = 7  # weekly release cadence

# Map canonical -> Socrata field. Some categories use the `_all` suffix.
CFTC_FIELD_MAP: dict[str, str] = {
    "asset_mgr_long":   "asset_mgr_positions_long",
    "asset_mgr_short":  "asset_mgr_positions_short",
    "lev_money_long":   "lev_money_positions_long",
    "lev_money_short":  "lev_money_positions_short",
    "dealer_long":      "dealer_positions_long_all",
    "dealer_short":     "dealer_positions_short_all",
    "other_rept_long":  "other_rept_positions_long",
    "other_rept_short": "other_rept_positions_short",
    "open_interest":    "open_interest_all",
}

NET_CATEGORIES = ("asset_mgr", "lev_money", "dealer", "other_rept")


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception_type(
        (requests.RequestException, TimeoutError, ValueError)
    ),
    reraise=True,
)
def _fetch(contract_code: str) -> list[dict]:
    """Single bulk Socrata query - up to 50000 rows fits full SPX history."""
    params = {
        "$where": f"cftc_contract_market_code='{contract_code}'",
        "$order": "report_date_as_yyyy_mm_dd ASC",
        "$limit": 50000,
    }
    r = requests.get(ENDPOINT, params=params, headers=HEADERS, timeout=120)
    r.raise_for_status()
    js = r.json()
    if not isinstance(js, list):
        raise ValueError(f"Unexpected CFTC response type: {type(js)}")
    if not js:
        raise ValueError(f"Empty CFTC response for contract {contract_code}")
    return js


def _build_dataframe(records: list[dict]) -> pd.DataFrame:
    raw = pd.DataFrame(records)
    if "report_date_as_yyyy_mm_dd" not in raw.columns:
        raise ValueError("CFTC response missing report_date_as_yyyy_mm_dd")
    raw["report_date"] = pd.to_datetime(
        raw["report_date_as_yyyy_mm_dd"], errors="coerce"
    )
    raw = raw.dropna(subset=["report_date"])

    out = pd.DataFrame(index=raw["report_date"].rename("report_date"))
    for canon, src in CFTC_FIELD_MAP.items():
        if src in raw.columns:
            out[canon] = pd.to_numeric(raw[src].values, errors="coerce")
        else:
            log.warning("CFTC: source field %s missing in response", src)
            out[canon] = pd.NA
    for cat in NET_CATEGORIES:
        out[f"{cat}_net"] = out[f"{cat}_long"] - out[f"{cat}_short"]
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
def _cache_paths(contract_code: str) -> tuple[Path, Path]:
    parquet = DATA_CACHE / f"cftc_tff_spx_{contract_code}.parquet"
    sidecar = DATA_CACHE / f"cftc_tff_spx_{contract_code}.meta.json"
    return parquet, sidecar


def _is_cache_fresh(parquet: Path) -> bool:
    if not parquet.exists():
        return False
    age_days = (time.time() - parquet.stat().st_mtime) / 86400
    return age_days < TTL_DAYS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_cftc_tff_spx(
    contract_code: str = "13874A",
    *,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, IndicatorMetadata]:
    parquet, sidecar = _cache_paths(contract_code)
    use_cache = not force_refresh and _is_cache_fresh(parquet)

    if use_cache:
        log.debug("CFTC TFF %s: cache hit", contract_code)
        df = pd.read_parquet(parquet)
    else:
        log.info("CFTC TFF %s: fetching from %s", contract_code, ENDPOINT)
        records = _fetch(contract_code)
        df = _build_dataframe(records)

    first_obs = df.index.min()
    last_obs = df.index.max()
    indicator_id = f"CFTC_TFF_SPX_{contract_code}"
    meta = IndicatorMetadata(
        indicator_id=indicator_id,
        source="CFTC_TFF_SOCRATA",
        frequency="W",
        first_obs=first_obs,
        last_obs=last_obs,
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=False,
        unit="count",
        release_lag_days=3,  # Tue positions released Fri
        description=(
            f"CFTC TFF E-Mini S&P 500 (CME contract {contract_code}) - "
            "weekly trader positioning. Tuesday positions, Friday 3:30pm ET release."
        ),
        expected_min=0,
        expected_max=1e7,
        extra={
            "tier": "2C",
            "endpoint": ENDPOINT,
            "contract_code": contract_code,
            "schema_columns": list(df.columns),
            "release_schedule": "Friday 3:30pm ET (Tuesday positions)",
            "n_obs": int(df.shape[0]),
        },
    )

    if not use_cache:
        df.to_parquet(parquet)
        sidecar.write_text(json.dumps(meta.to_dict(), default=str, indent=2))

    return df, meta


class CftcTffSpxLoader(Loader):
    def __init__(self, *, contract_code: str = "13874A", force_refresh: bool = False):
        self.contract_code = contract_code
        self.force_refresh = force_refresh

    def load(self):
        df, meta = load_cftc_tff_spx(
            contract_code=self.contract_code,
            force_refresh=self.force_refresh,
        )
        return df, {meta.indicator_id: meta}


# ---------------------------------------------------------------------------
# CLI: `python -m src.loaders.cftc_tff_spx`
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    df, meta = load_cftc_tff_spx()
    print(f"Loaded CFTC TFF SPX: {len(df)} weekly rows, "
          f"{df.index.min().date()} -> {df.index.max().date()}")
    print(df.tail(3))
