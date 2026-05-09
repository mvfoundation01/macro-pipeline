"""Layer 5 (CRPS / CDRS) scoring conventions.

This file documents constraints that must be honored by composite-score
implementations. It does not yet build any scorer - it just establishes
the contract so when we get to Layer 5 there's no ambiguity.

Key constraint: positioning indicators have inconsistent units across
sources. CFTC TFF SPX (Phase 3, Socrata API) is in CONTRACTS. CFTC TFF
Treasury (Phase 4C, OFR HFM file) is in NOTIONAL USD (B_USD_signed).
FINRA Margin Debt (Phase 4A) is in MILLIONS USD. NAAIM Number is in
percent-exposure. NO absolute threshold can be applied uniformly.

Therefore: every positioning indicator MUST be transformed to a rolling
z-score (3-year or 5-year window) before being fed into the composite.
Z-score is unit-invariant by construction.
"""
from __future__ import annotations

POSITIONING_INDICATORS_REQUIRING_ZSCORE: list[str] = [
    # CFTC TFF S&P 500 E-Mini (Phase 3) - column names within the
    # CFTC_TFF_SPX_13874A multi-column DataFrame.
    "asset_mgr_net",        # AKA CFTC_SPX_AM_NET in downstream renaming
    "lev_money_net",        # AKA CFTC_SPX_LV_NET
    "dealer_net",           # AKA CFTC_SPX_DEALER_NET
    # CFTC TFF Treasury (Phase 4C, OFR file)
    "CFTC_TR_10Y_AM_NET",
    "CFTC_TR_10Y_LV_NET",
    "CFTC_TR_10Y_DEALER_NET",
    # Other positioning / sentiment levels
    "FINRA_MARGIN_DEBT",
    "NAAIM_NUMBER",
]

# Default rolling-window length for the z-score normalization.
ZSCORE_WINDOW_DEFAULT_YEARS: int = 3
# Alternative for slower-moving regimes.
ZSCORE_WINDOW_LONG_YEARS: int = 5

# CRPS/CDRS alert thresholds (Build guide Section 12).
CRPS_ALERT_THRESHOLDS: dict[str, float] = {
    "high":     0.60,
    "moderate": 0.40,
    "low":      0.0,
}
CDRS_ALERT_THRESHOLDS: dict[str, float] = {
    "high":     0.70,
    "moderate": 0.50,
    "low":      0.0,
}


def requires_zscore(indicator_id: str) -> bool:
    """Returns True if this series must be z-score-normalized before scoring."""
    return indicator_id in set(POSITIONING_INDICATORS_REQUIRING_ZSCORE)


# ---------------------------------------------------------------------------
# Source-quality confidence caps (Layer 1.5C.5)
# ---------------------------------------------------------------------------
# Maximum confidence the system may report for an indicator depending on
# the trustworthiness of its source pipeline. ChatGPT 2026-05-09 D7
# requested explicit caps for OCR / stale / unofficial data.
#
# These are proportions in [0, 1]; multiply by 100 to get a percentage cap.
# The "free_api" cap of 1.00 means no source-quality discount applies (the
# data is fetched from a maintained authoritative API).
SOURCE_QUALITY_CAPS: dict[str, float] = {
    "manual_image_csv": 0.60,   # OCR-transcribed (e.g. Damodaran ERP image)
    "stale_local_file": 0.50,   # Tier 5 frozen file
    "tradingview_csv":  0.75,   # TradingView-exported CSV (re-export, no API contract)
    "yahoo_unofficial": 0.80,   # Yahoo data on a ticker without an official endpoint
    "free_download":    0.90,   # Free CSV/XLS download from a primary source
    "free_api":         1.00,   # FRED / CFTC Socrata / other versioned APIs
}
