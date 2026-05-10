"""Central configuration. Every magic string and threshold lives here.

Conforms to:
- Build guide v1.1 Section 4.3
- Preprocessing guide Stage 1.6 (UNIT_REGISTRY)
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_CACHE = ROOT / "data" / "cache"
DATA_DERIVED = ROOT / "data" / "derived"
DATA_OUTPUT = ROOT / "data" / "output"

for _d in (DATA_CACHE, DATA_DERIVED, DATA_OUTPUT):
    _d.mkdir(parents=True, exist_ok=True)

FRED_API_KEY = os.environ.get("FRED_API_KEY")
if not FRED_API_KEY:
    raise RuntimeError(
        "FRED_API_KEY is not set. Add it to .env at project root or export it."
    )

# Master business-day index start (preprocessing guide Stage 1.5).
MASTER_INDEX_START = "1959-01-01"

# Cache TTL (build guide pitfall #3): max staleness before re-fetch.
CACHE_TTL_DAYS = {
    "D": 1,
    "W": 7,
    "M": 30,
    "Q": 30,
}

# ---------------------------------------------------------------------------
# FRED series metadata
# ---------------------------------------------------------------------------
# `unit` matches the preprocessing guide UNIT_REGISTRY taxonomy:
#   pct          -> stored as 4.43 means 4.43%
#   pct_change   -> already YoY/MoM percent change
#   M_USD        -> millions of USD
#   B_USD        -> billions of USD
#   index        -> dimensionless level (PMI, NFCI, INDPRO ...)
#   count_k      -> count in thousands (PAYEMS, claims)
#   binary       -> 0/1 indicator
#   ratio        -> dimensionless ratio (e.g. debt/GDP already as percent)
#
# `expected_min`/`expected_max` are wide sanity bounds used by Stage 1.1
# ingestion validation. They warn but do not abort.
#
# `release_lag_days` is the typical observation -> publication lag.

FRED_SERIES_API: dict[str, dict] = {
    # --- Yield curve / rates ---
    "T10Y2Y": {
        "freq": "D", "vintage": False, "unit": "pct",
        "expected_min": -5.0, "expected_max": 5.0, "release_lag_days": 1,
        "description": "10-Year minus 2-Year Treasury yield spread",
    },
    # Layer 3B: added retroactively for CRPS yield-curve component.
    # T10Y3M is the canonical recession yield-curve signal in the
    # Estrella/Mishkin tradition (NY Fed recession-probability model
    # and Bauer-Mertens), preferred over T10Y2Y for the 12M leading
    # signal. Daily, no vintage. FRED publishes BC_10YEAR − BC_3MONTH.
    "T10Y3M": {
        "freq": "D", "vintage": False, "unit": "pct",
        "expected_min": -6.0, "expected_max": 6.0, "release_lag_days": 1,
        "description": (
            "10-Year minus 3-Month Treasury yield spread — canonical "
            "recession yield-curve signal (NY Fed Estrella-Mishkin "
            "model, Bauer-Mertens 2018)."
        ),
    },
    "DFII10": {
        "freq": "D", "vintage": False, "unit": "pct",
        "expected_min": -2.0, "expected_max": 6.0, "release_lag_days": 1,
        "description": "10-Year TIPS (real yield)",
    },
    "THREEFYTP10": {
        "freq": "D", "vintage": False, "unit": "pct",
        "expected_min": -3.0, "expected_max": 6.0, "release_lag_days": 7,
        "description": "ACM 10-Year nominal Treasury term premium",
    },
    "SOFR": {
        "freq": "D", "vintage": False, "unit": "pct",
        "expected_min": 0.0, "expected_max": 10.0, "release_lag_days": 1,
        "description": "Secured Overnight Financing Rate",
    },
    "IORB": {
        "freq": "D", "vintage": False, "unit": "pct",
        "expected_min": 0.0, "expected_max": 10.0, "release_lag_days": 1,
        "description": "Interest on Reserve Balances rate",
    },
    # --- Short rates needed by NTFS (Layer 1.5C.1) ---
    "TB3MS": {
        "freq": "M", "vintage": False, "unit": "pct",
        "expected_min": 0.0, "expected_max": 25.0, "release_lag_days": 1,
        "description": (
            "3-Month Treasury Bill secondary market rate, monthly average. "
            "Used by NTFS_OFFICIAL_REPL as the spot 3-month yield."
        ),
    },
    "DTB3": {
        "freq": "D", "vintage": False, "unit": "pct",
        "expected_min": 0.0, "expected_max": 25.0, "release_lag_days": 1,
        "description": (
            "3-Month Treasury Bill secondary market rate, daily. "
            "Used by NTFS_DAILY_DASHBOARD as the spot 3-month yield."
        ),
    },
    # --- Sahm rule / labor market ---
    "SAHMREALTIME": {
        "freq": "M", "vintage": True, "unit": "pct",
        "expected_min": -1.0, "expected_max": 10.0, "release_lag_days": 7,
        # Layer 1.5C.4 re-classification (ChatGPT review):
        # Sahm is COINCIDENT, not 12M-leading. CRPS/CDRS builders that
        # ask for a 12M_leading_composite must reject this indicator.
        "signal_type": "coincident",
        "valid_uses": [
            "recession_start_detection",
            "real_time_recession_indicator",
        ],
        "INVALID_uses": [
            "12M_recession_probability_composite",
            "12M_leading_indicator",
        ],
        # Layer 3.5B Option Z (per LAYER_3_5_BUILD_SPEC.md §4.3-2; D21):
        # FRED's SAHMREALTIME series is constructed from only the
        # unemployment data available at each point in time per the Sahm
        # Rule definition (Atlanta Fed methodology). Since the
        # construction itself is real-time, we treat the latest cache as
        # PIT-safe by construction — but cap downstream confidence at
        # 0.70 to defend against (a) seasonal-factor revisions to recent
        # values (BLS routinely revises the seasonally-adjusted UNRATE
        # back ~5 years each annual benchmark) and (b) the residual
        # methodology-vs-vintage gap. The cap propagates through
        # ``compute_final_confidence_cap`` into CRPS/CDRS aggregates.
        # Removing this flag (in-memory mutation in tests) deterministically
        # fails Gate 13.
        "pit_safe_by_construction": True,
        "pit_construction_rationale": (
            "FRED publishes SAHMREALTIME as a real-time series constructed "
            "using only the unemployment data available at each point in "
            "time per the Sahm Rule definition (Atlanta Fed methodology). "
            "Caveat: seasonal factor revisions can affect recent values "
            "after annual BLS benchmark refreshes. See scoring/README.md §D20 "
            "for the full Option Z rationale."
        ),
        "derived_confidence_cap": 0.70,
        "description": (
            "Sahm Rule real-time recession indicator. COINCIDENT signal "
            "(detects recession start, not 12M ahead). Use for "
            "recession_start_detection only — see 1.5C.4. PIT-safe by "
            "construction per Layer 3.5B Option Z; downstream confidence "
            "capped at 0.70."
        ),
    },
    # --- Philly Fed STATE Leading Index (NOT Conference Board LEI) ---
    # Layer 1.5C.3 (ChatGPT review): the FRED series id is USSLIND but the
    # build guide called it CB_LEI. USSLIND is Philly Fed's STATE leading
    # index aggregate; its inputs already include T10Y3M and ISM data, so
    # combining USSLIND + T10Y3M + ISM in CRPS double-counts the same
    # signal. We expose it as PHILLY_LEI_PROXY with a double-counting flag
    # so any composite builder that uses it next to T10Y3M/ISM can warn.
    "USSLIND": {
        "freq": "M", "vintage": False, "unit": "pct",
        "expected_min": -10.0, "expected_max": 10.0, "release_lag_days": 30,
        "indicator_id": "PHILLY_LEI_PROXY",
        "double_counting_risk": True,
        "overlap_components": ["T10Y3M", "ISM_NEW_ORDERS", "IC4WSA"],
        "description": (
            "Philly Fed STATE leading index aggregate (FRED id USSLIND). "
            "Mislabeled as Conference Board LEI in earlier builds. "
            "Double-counts T10Y3M and ISM data — see 1.5C.3."
        ),
    },
    "PAYEMS": {
        "freq": "M", "vintage": True, "unit": "count_k",
        "expected_min": 29000, "expected_max": 200000, "release_lag_days": 5,
        "description": "All Employees, Total Nonfarm (thousands of persons)",
    },
    "JTSQUR": {
        "freq": "M", "vintage": True, "unit": "pct",
        "expected_min": 0.5, "expected_max": 8.0, "release_lag_days": 35,
        "description": "Job openings rate (JOLTS)",
    },
    "IC4WSA": {
        "freq": "W", "vintage": False, "unit": "count",
        "expected_min": 1.5e5, "expected_max": 7e6, "release_lag_days": 7,
        "description": "Initial Claims, 4-week MA (raw count)",
    },
    "CCSA": {
        "freq": "W", "vintage": False, "unit": "count",
        "expected_min": 9e5, "expected_max": 3e7, "release_lag_days": 14,
        "description": "Continued Claims, SA (raw count)",
    },
    # --- Activity composites ---
    "INDPRO": {
        # FRED returns INDPRO from 1919-01-01; range check sees pre-1959 lows.
        "freq": "M", "vintage": True, "unit": "index",
        "expected_min": 3.0, "expected_max": 200.0, "release_lag_days": 17,
        "description": "Industrial Production Index (2017=100)",
    },
    "RSAFS": {
        "freq": "M", "vintage": True, "unit": "M_USD",
        "expected_min": 1e4, "expected_max": 1e6, "release_lag_days": 17,
        "description": "Advance Retail Sales (millions USD)",
    },
    "RRSFS": {
        "freq": "M", "vintage": True, "unit": "M_USD",
        "expected_min": 1e4, "expected_max": 1e6, "release_lag_days": 17,
        "description": "Real Retail Sales (millions chained USD)",
    },
    "CFNAIMA3": {
        "freq": "M", "vintage": True, "unit": "index",
        "expected_min": -8.0, "expected_max": 5.0, "release_lag_days": 21,
        "description": "Chicago Fed National Activity Index, 3-month MA",
    },
    "GDPNOW": {
        "freq": "W", "vintage": False, "unit": "pct",
        "expected_min": -40.0, "expected_max": 40.0, "release_lag_days": 1,
        "description": "Atlanta Fed GDPNow nowcast (annualized %)",
    },
    # --- Financial conditions / stress composites ---
    "NFCI": {
        "freq": "W", "vintage": False, "unit": "index",
        "expected_min": -3.0, "expected_max": 6.0, "release_lag_days": 1,
        "description": "Chicago Fed National Financial Conditions Index",
    },
    "ANFCI": {
        "freq": "W", "vintage": False, "unit": "index",
        "expected_min": -3.0, "expected_max": 6.0, "release_lag_days": 1,
        "description": "Adjusted NFCI (controlling for economic conditions)",
    },
    "KCFSI": {
        "freq": "M", "vintage": False, "unit": "index",
        "expected_min": -3.0, "expected_max": 7.0, "release_lag_days": 30,
        "description": "Kansas City Fed Financial Stress Index",
    },
    "STLFSI4": {
        "freq": "W", "vintage": False, "unit": "index",
        "expected_min": -3.0, "expected_max": 10.0, "release_lag_days": 1,
        "description": "St Louis Fed Financial Stress Index, version 4",
    },
    # --- Senior Loan Officer Survey ---
    "DRTSCILM": {
        "freq": "Q", "vintage": False, "unit": "pct",
        "expected_min": -100.0, "expected_max": 100.0, "release_lag_days": 30,
        "description": "Net % banks tightening C&I large/mid firms",
    },
    "DRTSCLCC": {
        "freq": "Q", "vintage": False, "unit": "pct",
        "expected_min": -100.0, "expected_max": 100.0, "release_lag_days": 30,
        "description": "Net % banks tightening credit cards",
    },
    # --- Inflation ---
    "PCEPILFE": {
        "freq": "M", "vintage": True, "unit": "index",
        "expected_min": 10.0, "expected_max": 250.0, "release_lag_days": 30,
        "description": "Core PCE price index level",
    },
    "CORESTICKM159SFRBATL": {
        "freq": "M", "vintage": False, "unit": "pct",
        "expected_min": -2.0, "expected_max": 16.0, "release_lag_days": 14,
        "description": "Atlanta Fed Sticky Core CPI YoY %",
    },
    "MEDCPIM158SFRBCLE": {
        "freq": "M", "vintage": False, "unit": "pct",
        "expected_min": -2.0, "expected_max": 15.0, "release_lag_days": 14,
        "description": "Cleveland Fed Median CPI YoY %",
    },
    # --- Fiscal ---
    "GFDEGDQ188S": {
        "freq": "Q", "vintage": True, "unit": "pct",
        "expected_min": 30.0, "expected_max": 200.0, "release_lag_days": 90,
        "description": "Federal debt held by public, % of GDP",
    },
    "A091RC1Q027SBEA": {
        "freq": "Q", "vintage": True, "unit": "B_USD",
        "expected_min": 0.0, "expected_max": 5000.0, "release_lag_days": 30,
        "description": "Federal government interest payments (annualized $B)",
    },
    "FGRECPT": {
        "freq": "Q", "vintage": True, "unit": "B_USD",
        "expected_min": 0.0, "expected_max": 10000.0, "release_lag_days": 30,
        "description": "Federal government current receipts (annualized $B)",
    },
    # --- NBER labels (for backtest only, not real-time signal) ---
    "USREC": {
        "freq": "M", "vintage": False, "unit": "binary",
        "expected_min": 0, "expected_max": 1, "release_lag_days": 60,
        "description": "NBER recession indicator (1 = peak-to-trough)",
    },
}

# Sanity-check ranges by unit (preprocessing guide Stage 1.6).
# These are *coarse* unit-level bounds; per-series `expected_min`/`expected_max`
# in FRED_SERIES_API are tighter and authoritative for ingestion validation.
UNIT_EXPECTED_RANGES: dict[str, tuple[float, float]] = {
    # `pct` covers yields, spreads, share-of-GDP (debt/GDP can exceed 100),
    # Buffett-style market-cap/GDP ratios (~200), and YoY inflation prints.
    "pct": (-200.0, 500.0),
    "pct_change": (-200.0, 500.0),
    "M_USD": (1.0, 1e10),       # widened: some early series start below $100M
    "B_USD": (0.0, 5e7),
    "B_USD_signed": (-1e7, 1e7),  # signed billions USD (CFTC net positions)
    "index": (-10.0, 1e10),     # widened: cumulative TR indices compound
    "count": (0.0, 1e9),         # raw count (jobless claims, etc.)
    "count_k": (0.0, 5e6),       # count in thousands (PAYEMS, etc.)
    "count_signed": (-1e7, 1e7), # signed difference of counts (NH-NL net, CFTC nets)
    "count_10yreqv": (-1e13, 1e13),  # 10Y duration-weighted Treasury position notional
    "binary": (0.0, 1.0),
    "ratio": (0.0, 1e3),
    "share": (0.0, 1.01),
    "pct_exposure": (-200.0, 200.0),
}

# ---------------------------------------------------------------------------
# Yahoo tickers (used by yahoo_loader, not by FRED loader)
# ---------------------------------------------------------------------------
YAHOO_TICKERS: list[str] = [
    "^GSPC", "^NDX", "^RUT", "RSP",
    "^VIX", "^VIX3M", "^VVIX", "^SKEW", "^MOVE",
    "DX-Y.NYB", "GC=F",
    "XLK", "XLF", "XLV", "XLY", "XLP",
    "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC",
]

# ---------------------------------------------------------------------------
# Composite-score weights (build guide Section 12)
# ---------------------------------------------------------------------------
CRPS_WEIGHTS: dict[str, float] = {
    "yield_curve_nyfed":  0.30,
    "sahm_rule":          0.20,
    "lei_3d_rule":        0.20,
    "ism_pmi_neworders":  0.10,
    "nfci_kcfsi":         0.10,
    "hy_oas_regime":      0.10,
}

CDRS_BUCKET_WEIGHTS: dict[str, float] = {
    "valuation": 0.30,
    "sentiment": 0.20,
    "credit":    0.25,
    "vol_tech":  0.25,
}

FORWARD_HORIZONS_MONTHS: list[int] = [12, 36, 60, 120]


# ---------------------------------------------------------------------------
# Layer 3.5B — PIT-safe-by-construction (Option Z) validation.
# Runs at module import time. Surfaces config bugs (e.g. flag set without
# a non-empty rationale, cap out of (0, 1]) immediately rather than at
# inference time. Spec: LAYER_3_5_BUILD_SPEC.md §4.3-1 + §4.4-D3.
# ---------------------------------------------------------------------------
def _validate_pit_construction_consistency() -> None:
    """Validate every series flagged ``pit_safe_by_construction=True`` has
    a non-empty rationale and a cap in ``(0, 1]``.

    Raises ``ValueError`` (NOT a typed loader exception, since this is
    a *config* bug surfaced before any loader runs).
    """
    for sid, spec in FRED_SERIES_API.items():
        if not spec.get("pit_safe_by_construction", False):
            continue
        rationale = spec.get("pit_construction_rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(
                f"Config bug: {sid} has pit_safe_by_construction=True "
                "but missing/empty pit_construction_rationale. "
                "Per spec §4.4-D3 the rationale field is mandatory."
            )
        cap = spec.get("derived_confidence_cap")
        if cap is None:
            raise ValueError(
                f"Config bug: {sid} has pit_safe_by_construction=True "
                "but missing derived_confidence_cap. Spec mandates a "
                "numeric cap in (0, 1]."
            )
        try:
            cap_f = float(cap)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Config bug: {sid} derived_confidence_cap={cap!r} is "
                "not numeric."
            ) from exc
        if not (0.0 < cap_f <= 1.0):
            raise ValueError(
                f"Config bug: {sid} derived_confidence_cap={cap_f} must "
                "be in (0, 1]."
            )


_validate_pit_construction_consistency()
