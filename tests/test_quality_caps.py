"""Tests for source quality caps + E.1/E.2/E.3 (Layer 1.5C.5)."""
from __future__ import annotations

import pandas as pd

from src.models.quality_caps import (
    SOURCE_QUALITY_CAPS,
    aggregate_caps,
    categorize_source,
    compute_final_confidence_cap,
    source_cap_for_meta,
    stale_quarters_since_release,
    tier5_realtime_check,
    vintage_staleness_cap,
)


# ---------------------------------------------------------------------------
# SOURCE_QUALITY_CAPS dict
# ---------------------------------------------------------------------------
def test_source_quality_caps_match_spec():
    """User CONFIRM 2 spec values."""
    assert SOURCE_QUALITY_CAPS["manual_image_csv"] == 0.60
    assert SOURCE_QUALITY_CAPS["stale_local_file"] == 0.50
    assert SOURCE_QUALITY_CAPS["tradingview_csv"] == 0.75
    assert SOURCE_QUALITY_CAPS["yahoo_unofficial"] == 0.80
    assert SOURCE_QUALITY_CAPS["free_download"] == 0.90
    assert SOURCE_QUALITY_CAPS["free_api"] == 1.00


# ---------------------------------------------------------------------------
# Source categorization
# ---------------------------------------------------------------------------
def test_categorize_fred_api_as_free_api():
    assert categorize_source({"source": "FRED_API"}) == "free_api"


def test_categorize_yahoo_unofficial():
    assert categorize_source({
        "source": "YAHOO_FINANCE", "unofficial_yahoo": True,
    }) == "yahoo_unofficial"


def test_categorize_yahoo_official_as_free_api():
    """Most Yahoo tickers (no unofficial flag) are treated as a free API."""
    assert categorize_source({"source": "YAHOO_FINANCE"}) == "free_api"


def test_categorize_tier5_overrides_source():
    """Tier 5 takes precedence — any source maps to stale_local_file."""
    assert categorize_source({"source": "TV_CSV", "tier": 5}) == "stale_local_file"


def test_categorize_damodaran_as_manual_image():
    assert categorize_source({"source": "DAMODARAN_CSV"}) == "manual_image_csv"


def test_source_cap_for_damodaran_is_60():
    assert source_cap_for_meta({"source": "DAMODARAN_CSV"}) == 0.60


def test_source_cap_for_fred_api_is_100():
    assert source_cap_for_meta({"source": "FRED_API"}) == 1.00


# ---------------------------------------------------------------------------
# E.2 vintage staleness
# ---------------------------------------------------------------------------
def test_stale_quarters_zero_when_pub_after_asof():
    n = stale_quarters_since_release("2024-04-15", "2024-01-01")
    assert n == 0


def test_stale_quarters_six_for_hlw_2020q2_at_2022_01_15():
    """2020-07-14 publication, as_of 2022-01-15 -> 6 quarters."""
    n = stale_quarters_since_release("2020-07-14", "2022-01-15")
    assert n == 6


def test_vintage_staleness_cap_applies_above_threshold():
    assert vintage_staleness_cap(3) == 0.80
    assert vintage_staleness_cap(6) == 0.80


def test_vintage_staleness_cap_none_at_or_below_threshold():
    assert vintage_staleness_cap(0) is None
    assert vintage_staleness_cap(2) is None


# ---------------------------------------------------------------------------
# E.3 Tier 5 forward-horizon cutoff
# ---------------------------------------------------------------------------
def _wilshire_meta() -> dict:
    return {
        "source": "TV_CSV", "tier": 5, "data_status": "stale",
        "last_valid_date": "2024-04-01",
    }


def test_tier5_block_within_horizon_window():
    """as_of=2024-12 within 12M of last_valid 2024-04 -> blocked."""
    res = tier5_realtime_check(
        _wilshire_meta(), as_of=pd.Timestamp("2024-12-01"), horizon_months=12,
    )
    assert res.blocked is True


def test_tier5_block_at_user_example_2023_09():
    """as_of=2023-09-01 within 12M of 2024-04-01 -> blocked (cutoff
    is 2023-04-01)."""
    res = tier5_realtime_check(
        _wilshire_meta(), as_of=pd.Timestamp("2023-09-01"), horizon_months=12,
    )
    assert res.blocked is True


def test_tier5_pass_well_before_cutoff():
    res = tier5_realtime_check(
        _wilshire_meta(), as_of=pd.Timestamp("2022-01-01"), horizon_months=12,
    )
    assert res.blocked is False


def test_tier5_check_passes_through_for_non_tier5():
    res = tier5_realtime_check(
        {"source": "FRED_API", "tier": 1, "last_valid_date": "2026-05-01"},
        as_of=pd.Timestamp("2025-12-01"), horizon_months=12,
    )
    assert res.blocked is False


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def test_aggregate_caps_min():
    assert aggregate_caps(0.95, 0.6, 0.8) == 0.6
    assert aggregate_caps(0.95, None, 0.8) == 0.8
    assert aggregate_caps(None, None, None) == 1.0


def test_compute_final_cap_picks_lowest():
    """An indicator with source_cap=0.9 and vintage_confidence_cap=0.6
    must end up with final_cap=0.6."""
    meta = {
        "source": "ATLANTA_FED_WAGE_XLSX",
        "vintage_confidence_cap": 0.60,
    }
    out = compute_final_confidence_cap(meta)
    assert out.source_cap == 0.90
    assert out.vintage_confidence_cap == 0.60
    assert out.final_cap == 0.60


def test_compute_final_cap_includes_staleness():
    """E.2: a 6-quarter-stale HLW load triggers vintage_staleness_cap=0.80;
    combined with source_cap=0.9 -> final 0.80."""
    meta = {
        "source": "NYFED_HLW_CURRENT_XLSX",
        "hlw_vintage_publication_date": "2020-07-14",
    }
    out = compute_final_confidence_cap(meta, as_of=pd.Timestamp("2022-01-15"))
    assert out.vintage_staleness_cap == 0.80
    assert out.detail["stale_quarters_since_release"] == 6
    assert out.final_cap == 0.80
