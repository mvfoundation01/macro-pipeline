"""CFTC TFF Treasury positioning loader (Build guide Phase 4C).

File: ``data/raw/official/tff.xlsx`` (the OFR Hedge Fund Monitor compilation)
Sheet: ``tff``

Header layout: rows 0-2 are descriptive (Source / Description / Last
Update); row 3 holds the column codes; data starts row 4.

Source structure notes (verified against the file):

1. The AI/DI/OR trader categories are reported as **aggregate Treasury**
   (TFF-AI_TREAS_*, TFF-DI_TREAS_*, TFF-OR_TREAS_*) - per-contract
   breakdowns are NOT in this file. Only the LF (Leveraged Funds)
   category exposes per-contract columns including TFF-LF_TY_* (10-year
   futures).

2. ALL "_POSITION" columns are in NOTIONAL US DOLLARS, not contract
   counts (e.g. LF_TY_LONG_POSITION = $27.7B notional, not 27.7B
   contracts). For 10-year T-Note futures the contract face is $100k,
   so contracts = USD_notional / 1e5; we keep values in $B notional
   for cross-trader comparability.

So we deliver (all in billions USD notional, weekly):
  * CFTC_TR_10Y_LV_NET     - true LF 10-year futures net (TFF-LF_TY_*)
  * CFTC_TR_10Y_AM_NET     - AM aggregate Treasury net, 10Y-equivalent
  * CFTC_TR_10Y_DEALER_NET - DI aggregate Treasury net, 10Y-equivalent

Open interest is NOT in this file (the OFR HFM compilation only stores
position columns). For true OI we'd need a Socrata API call to
``publicreporting.cftc.gov`` filtering by CFTC contract code 043602
(10-Year US Treasury Notes); that's deferred to a later phase if needed.

Frequency: weekly (Tuesday positions, Friday release). Tier: 2A.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import pandas as pd

from src.config import DATA_CACHE, DATA_RAW
from src.loaders.base import IndicatorMetadata, Loader

log = logging.getLogger(__name__)

TFF_PATH = DATA_RAW / "official" / "tff.xlsx"
TFF_SHEET = "tff"

# (indicator_id, long_col, short_col, scope, lo, hi, description)
# All values rescaled to billions USD notional (raw / 1e9).
TFF_TR_SERIES_SPEC: list[tuple] = [
    ("CFTC_TR_10Y_LV_NET",
     "TFF-LF_TY_LONG_POSITION", "TFF-LF_TY_SHORT_POSITION",
     "true_10y_notional", -1000.0, 1000.0,
     "Leveraged Funds net 10-year Treasury futures position "
     "(billions USD notional; TFF-LF_TY_*)"),
    ("CFTC_TR_10Y_AM_NET",
     "TFF-AI_TREAS_LONG_POS10YREQV", "TFF-AI_TREAS_SHORT_POS10YREQV",
     "agg_treasury_10yreqv", -5000.0, 5000.0,
     "Asset Manager aggregate Treasury net "
     "(billions USD, 10Y-equivalent notional; cross-tenor)"),
    ("CFTC_TR_10Y_DEALER_NET",
     "TFF-DI_TREAS_LONG_POS10YREQV", "TFF-DI_TREAS_SHORT_POS10YREQV",
     "agg_treasury_10yreqv", -5000.0, 5000.0,
     "Dealer aggregate Treasury net "
     "(billions USD, 10Y-equivalent notional; cross-tenor)"),
]


def _read_tff_raw() -> pd.DataFrame:
    """Read tff.xlsx with column codes from row 3 and data from row 4."""
    raw = pd.read_excel(TFF_PATH, sheet_name=TFF_SHEET, header=None)
    if raw.shape[0] < 5:
        raise ValueError(f"tff.xlsx: only {raw.shape[0]} rows, expected >=5")
    codes = [str(c) for c in raw.iloc[3].values]
    data = raw.iloc[4:].copy()
    data.columns = codes
    # Column 0 is the date.
    date_col = codes[0]  # = 'date'
    data[date_col] = pd.to_datetime(data[date_col], errors="coerce")
    data = data.dropna(subset=[date_col]).sort_values(date_col)
    data = data.set_index(date_col)
    data = data[~data.index.duplicated(keep="last")]
    return data


def load_cftc_tff_treasury(
    *, force_refresh: bool = False
) -> tuple[dict[str, pd.Series], dict[str, IndicatorMetadata]]:
    raw = _read_tff_raw()

    series_out: dict[str, pd.Series] = {}
    meta_out: dict[str, IndicatorMetadata] = {}

    for (indicator_id, long_col, short_col, scope, lo, hi,
         description) in TFF_TR_SERIES_SPEC:
        for col in (long_col, short_col):
            if col not in raw.columns:
                raise ValueError(
                    f"tff.xlsx: missing column {col!r} for {indicator_id}"
                )
        # Rescale raw USD notional to billions for cross-trader readability.
        long_s = pd.to_numeric(raw[long_col], errors="coerce") / 1e9
        short_s = pd.to_numeric(raw[short_col], errors="coerce") / 1e9
        net = (long_s - short_s).dropna()
        net.name = indicator_id

        # Don't run the universal pipeline here - this is structured
        # weekly data that should NOT be ffilled to daily (per Phase 3
        # Treasury TFF convention).

        first_obs = net.index.min()
        last_obs = net.index.max()

        meta = IndicatorMetadata(
            indicator_id=indicator_id,
            source="OFR_TFF_XLSX",
            frequency="W",
            first_obs=first_obs, last_obs=last_obs,
            last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
            needs_vintage=False,
            unit="B_USD_signed",
            release_lag_days=3,
            description=description,
            expected_min=lo, expected_max=hi,
            extra={
                "tier": "2A",
                "source_file": TFF_PATH.name,
                "source_sheet": TFF_SHEET,
                "long_column": long_col,
                "short_column": short_col,
                "scope": scope,
                "release_schedule": "Friday 3:30pm ET (Tuesday positions)",
                "conviction_score": 5,
                "n_obs": int(net.notna().sum()),
            },
        )
        series_out[indicator_id] = net
        meta_out[indicator_id] = meta

        # Cache as a single-column parquet (consistent with other loaders).
        DATA_CACHE.mkdir(parents=True, exist_ok=True)
        parquet = DATA_CACHE / f"official_{indicator_id}.parquet"
        sidecar = DATA_CACHE / f"official_{indicator_id}.meta.json"
        net.to_frame(indicator_id).to_parquet(parquet)
        sidecar.write_text(json.dumps(meta.to_dict(), default=str, indent=2))

    return series_out, meta_out


class CftcTffTreasuryLoader(Loader):
    def load(self):
        series_dict, meta_dict = load_cftc_tff_treasury()
        return pd.concat(series_dict, axis=1), meta_dict


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    series, meta = load_cftc_tff_treasury()
    for sid, s in series.items():
        obs = s.dropna()
        print(f"{sid}: n_obs={len(obs):,}  first={meta[sid].first_obs.date()}  "
              f"last={meta[sid].last_obs.date()}  unit={meta[sid].unit}  "
              f"current={obs.iloc[-1]:,.0f}")
