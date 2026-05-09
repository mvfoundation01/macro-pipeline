"""CFTC TFF SPX loader tests (Phase 3, Gate 3 partial)."""
from __future__ import annotations

import os

import pandas as pd
import pytest
from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("FRED_API_KEY"):
    pytest.skip(
        "FRED_API_KEY not set (required for src.config import)",
        allow_module_level=True,
    )

from src.loaders.cftc_tff_spx import (
    CFTC_FIELD_MAP,
    NET_CATEGORIES,
    load_cftc_tff_spx,
)


# ---------------------------------------------------------------------------
# Schema sanity (offline)
# ---------------------------------------------------------------------------
def test_cftc_field_map_covers_all_categories():
    expected = {"asset_mgr", "lev_money", "dealer", "other_rept"}
    for prefix in expected:
        assert any(k.startswith(prefix) for k in CFTC_FIELD_MAP)


def test_net_categories_match_field_map():
    for cat in NET_CATEGORIES:
        assert f"{cat}_long" in CFTC_FIELD_MAP
        assert f"{cat}_short" in CFTC_FIELD_MAP


# ---------------------------------------------------------------------------
# Live API tests
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def cftc_payload():
    return load_cftc_tff_spx()


def test_cftc_loads_e_mini_spx(cftc_payload):
    df, meta = cftc_payload
    assert not df.empty
    assert meta.indicator_id == "CFTC_TFF_SPX_13874A"
    assert meta.source == "CFTC_TFF_SOCRATA"


def test_cftc_schema_has_all_expected_columns(cftc_payload):
    df, _ = cftc_payload
    expected = (
        list(CFTC_FIELD_MAP.keys())
        + [f"{c}_net" for c in NET_CATEGORIES]
    )
    for col in expected:
        assert col in df.columns, f"missing column: {col}"


def test_cftc_dates_are_monotonic_and_unique(cftc_payload):
    df, _ = cftc_payload
    assert df.index.is_monotonic_increasing
    assert df.index.is_unique


def test_cftc_dates_are_tuesdays(cftc_payload):
    """CFTC reports cover Tuesday positions; the report_date column = Tuesday.
    Allow up to ~1% tolerance for federal-holiday shifts.
    """
    df, _ = cftc_payload
    weekday = df.index.dayofweek  # Mon=0, Tue=1
    fraction_tuesday = float((weekday == 1).mean())
    assert fraction_tuesday >= 0.95, (
        f"only {fraction_tuesday:.1%} of report dates are Tuesdays"
    )


def test_cftc_first_obs_around_2006_06(cftc_payload):
    df, _ = cftc_payload
    first = df.index.min()
    assert pd.Timestamp("2006-06-01") <= first <= pd.Timestamp("2006-12-31"), (
        f"first obs {first.date()} not in expected range"
    )


def test_cftc_open_interest_above_100k(cftc_payload):
    df, _ = cftc_payload
    oi = df["open_interest"].dropna()
    assert oi.min() >= 100_000, f"min OI = {oi.min():,.0f} below 100k threshold"


def test_cftc_dealer_typically_net_short(cftc_payload):
    """Dealers (market makers) historically net short the E-Mini SPX."""
    df, _ = cftc_payload
    median_dealer_net = float(df["dealer_net"].dropna().median())
    assert median_dealer_net < 0, (
        f"median dealer_net = {median_dealer_net:,.0f} unexpectedly positive"
    )


def test_cftc_metadata_tier_is_2c(cftc_payload):
    _, meta = cftc_payload
    assert meta.extra.get("tier") == "2C"
    assert meta.unit == "count"
    assert meta.frequency == "W"
    assert meta.extra.get("contract_code") == "13874A"


def test_cftc_cache_file_exists_after_load(cftc_payload):
    from src.config import DATA_CACHE
    assert (DATA_CACHE / "cftc_tff_spx_13874A.parquet").exists()
    assert (DATA_CACHE / "cftc_tff_spx_13874A.meta.json").exists()
