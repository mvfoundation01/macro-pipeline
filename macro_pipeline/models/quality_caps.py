"""Confidence-cap aggregation for series sources, vintages, and Tier 5
auxiliary indicators (Layer 1.5C.5 + E.1/E.2/E.3).

Final confidence per indicator is the minimum of:
  1. ``source_cap``: a static cap derived from the source category (FRED
     API → 1.00, OCR-image → 0.60, etc. — see
     ``scoring_config.SOURCE_QUALITY_CAPS``).
  2. ``vintage_confidence_cap``: a per-indicator override set by the
     loader when the dataset is full-history-revisable (E.1: Atlanta
     Wage Tracker → 0.60).
  3. ``vintage_staleness_cap``: dynamic, applies when a PIT load picks
     a vintage that is more than 2 quarters old at as_of (E.2: HLW
     staleness during 2020Q3-2022Q3 publication gap → 0.80).
  4. ``tier5_realtime_cap``: 0.0 (block) when a Tier 5 indicator is
     used for real-time scoring within ``horizon_months`` of its
     ``last_valid_date`` (E.3).

Why min, not multiplicative
---------------------------
Per the user spec: "pick min for honesty". A multiplicative formula
(0.9 × 0.8 × 0.6 = 0.432) compounds caps that already reflect different
risk dimensions. Min is conservative and easier to reason about: the
weakest link sets the ceiling.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from macro_pipeline.models.scoring_config import SOURCE_QUALITY_CAPS

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source category mapping
# ---------------------------------------------------------------------------
def _is_tier5(meta: dict) -> bool:
    """Tier may be int (5) or string ('5', '2A', etc.) — only true 5 counts."""
    t = meta.get("tier")
    if t is None:
        return False
    return str(t).strip() == "5"


def categorize_source(meta: dict) -> str:
    """Map an indicator's metadata to one of the SOURCE_QUALITY_CAPS keys."""
    src = (meta.get("source") or "").upper()

    # Tier 5 stale local files take precedence over their nominal source.
    if _is_tier5(meta) or meta.get("data_status") == "stale":
        return "stale_local_file"

    if "FRED_API" in src or "FRED_ALFRED" in src or "CFTC_TFF_SOCRATA" in src:
        return "free_api"
    if "FED_BOARD_GSW" in src or "FED_BOARD_FEDS_NOTES" in src:
        return "free_api"
    if src.startswith("YAHOO"):
        # ^MOVE / similar are unofficial; everything else is treated as
        # a free public API for cap purposes.
        if meta.get("unofficial_yahoo"):
            return "yahoo_unofficial"
        return "free_api"
    if src.startswith("TV_") or "TRADINGVIEW" in src:
        return "tradingview_csv"
    if "DAMODARAN" in src or meta.get("source_origin") == "image":
        return "manual_image_csv"
    if "XLSX" in src or "XLS" in src or "CSV" in src:
        return "free_download"
    return "free_download"


def source_cap_for_meta(meta: dict) -> float:
    """Return the SOURCE_QUALITY_CAPS entry for this metadata's category."""
    cat = categorize_source(meta)
    return SOURCE_QUALITY_CAPS.get(cat, 1.0)


# ---------------------------------------------------------------------------
# E.2 — vintage staleness
# ---------------------------------------------------------------------------
_STALE_QUARTER_THRESHOLD = 2          # > 2 quarters stale triggers the cap
_STALE_VINTAGE_CAP = 0.80


def stale_quarters_since_release(
    publication_date: pd.Timestamp | str | None,
    as_of: pd.Timestamp | str,
) -> int:
    """Number of completed calendar quarters between ``publication_date``
    and ``as_of``. Returns 0 if either is missing or as_of <= publication.
    """
    if publication_date is None:
        return 0
    pub = pd.Timestamp(publication_date)
    asof = pd.Timestamp(as_of)
    if pd.isna(pub) or pd.isna(asof) or asof <= pub:
        return 0
    delta_q = (asof.year - pub.year) * 4 + (asof.quarter - pub.quarter)
    return max(0, int(delta_q))


def vintage_staleness_cap(stale_quarters: int) -> float | None:
    """Cap dynamics: > 2 quarters stale → 0.80. Otherwise no cap added."""
    if stale_quarters > _STALE_QUARTER_THRESHOLD:
        return _STALE_VINTAGE_CAP
    return None


# ---------------------------------------------------------------------------
# E.3 — Tier 5 forward-horizon cutoff
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Tier5BlockResult:
    blocked: bool
    reason: str = ""
    last_valid_date: pd.Timestamp | None = None
    as_of: pd.Timestamp | None = None
    horizon_months: int | None = None


def tier5_realtime_check(
    meta: dict,
    *,
    as_of: pd.Timestamp | str,
    horizon_months: int,
) -> Tier5BlockResult:
    """Block real-time scoring when a Tier-5 stale indicator is used at
    an ``as_of`` whose ``horizon_months``-ahead target exceeds the
    indicator's ``last_valid_date``.

    Returns a ``Tier5BlockResult``. ``blocked=True`` means the caller
    must drop this indicator from the real-time composite. Tier 1-4
    indicators always pass through (``blocked=False``).
    """
    if not _is_tier5(meta):
        return Tier5BlockResult(blocked=False)

    asof_ts = pd.Timestamp(as_of)
    last_valid = meta.get("last_valid_date") or meta.get("last_obs")
    if last_valid is None:
        return Tier5BlockResult(
            blocked=True,
            reason="Tier 5 indicator has no last_valid_date in metadata",
            as_of=asof_ts, horizon_months=horizon_months,
        )
    last_valid_ts = pd.Timestamp(last_valid)

    cutoff = last_valid_ts - pd.DateOffset(months=horizon_months)
    if asof_ts > cutoff:
        return Tier5BlockResult(
            blocked=True,
            reason=(
                f"Tier 5 indicator: as_of={asof_ts.date()} is within "
                f"{horizon_months}M of last_valid_date={last_valid_ts.date()} "
                f"(cutoff={cutoff.date()}). Forward target would peek past "
                f"the data's last valid observation — drop from real-time "
                f"composite."
            ),
            last_valid_date=last_valid_ts,
            as_of=asof_ts, horizon_months=horizon_months,
        )
    return Tier5BlockResult(
        blocked=False, last_valid_date=last_valid_ts,
        as_of=asof_ts, horizon_months=horizon_months,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
@dataclass
class AppliedCaps:
    """Audit-trail dataclass for the final cap aggregation."""
    source_cap: float = 1.0
    vintage_confidence_cap: float | None = None
    vintage_staleness_cap: float | None = None
    tier5_block: bool = False
    tier5_reason: str = ""
    final_cap: float = 1.0
    detail: dict[str, Any] = field(default_factory=dict)


def aggregate_caps(*caps: float | None) -> float:
    """Take the min of all non-None caps; return 1.0 if all are None."""
    valid = [c for c in caps if c is not None and not math.isnan(c)]
    return min(valid) if valid else 1.0


def compute_final_confidence_cap(
    meta: dict,
    *,
    as_of: pd.Timestamp | str | None = None,
    horizon_months: int | None = None,
) -> AppliedCaps:
    """Bundle source / vintage / staleness / Tier-5 caps into one result.

    Caller can read ``result.final_cap`` and clamp the headline confidence
    score by ``min(score, final_cap * 100)``. ``result.tier5_block``
    indicates whether the indicator should be excluded entirely from
    real-time scoring at this as_of.
    """
    out = AppliedCaps()

    out.source_cap = source_cap_for_meta(meta)

    vcc = meta.get("vintage_confidence_cap")
    if vcc is not None:
        out.vintage_confidence_cap = float(vcc)

    if as_of is not None:
        pub_date = meta.get("hlw_vintage_publication_date") \
            or meta.get("vintage_publication_date")
        if pub_date is not None:
            stale_q = stale_quarters_since_release(pub_date, as_of)
            out.detail["stale_quarters_since_release"] = stale_q
            cap = vintage_staleness_cap(stale_q)
            if cap is not None:
                out.vintage_staleness_cap = cap

    if horizon_months is not None and as_of is not None:
        t5 = tier5_realtime_check(meta, as_of=as_of, horizon_months=horizon_months)
        out.tier5_block = t5.blocked
        out.tier5_reason = t5.reason
        out.detail["tier5"] = {
            "last_valid_date": str(t5.last_valid_date) if t5.last_valid_date else None,
            "horizon_months": t5.horizon_months,
        }

    out.final_cap = aggregate_caps(
        out.source_cap, out.vintage_confidence_cap, out.vintage_staleness_cap,
    )
    return out


__all__ = [
    "SOURCE_QUALITY_CAPS",
    "AppliedCaps",
    "Tier5BlockResult",
    "aggregate_caps",
    "categorize_source",
    "compute_final_confidence_cap",
    "source_cap_for_meta",
    "stale_quarters_since_release",
    "tier5_realtime_check",
    "vintage_staleness_cap",
]
