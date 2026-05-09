"""Phase 4C official-source loader tests.

Covers AAII sentiment, Atlanta Fed wage growth, and CFTC TFF Treasury
positioning (via OFR HFM file). All read local files.
"""
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

from macro_pipeline.loaders.aaii import load_aaii
from macro_pipeline.loaders.atlanta_wage import load_atlanta_wage
from macro_pipeline.loaders.cftc_tff_treasury import load_cftc_tff_treasury
from macro_pipeline.validation import validate_gate4c


# ---------------------------------------------------------------------------
# AAII Sentiment
# ---------------------------------------------------------------------------
def test_aaii_returns_four_series():
    series, meta = load_aaii()
    expected = {
        "AAII_BULLISH", "AAII_BEARISH",
        "AAII_BULL_BEAR_SPREAD", "AAII_BULL_8WMA",
    }
    assert set(series.keys()) == expected
    assert set(meta.keys()) == expected


def test_aaii_history_starts_after_filter():
    """Pre-survey rows (NaN bullish/neutral/bearish) must be filtered."""
    _, meta = load_aaii()
    assert meta["AAII_BULLISH"].first_obs >= pd.Timestamp("1987-07-01")
    assert meta["AAII_BULLISH"].first_obs <= pd.Timestamp("1988-01-01")


def test_aaii_bullish_in_pct_scale():
    """Source stores 0-1 share; loader multiplies by 100 for pct convention."""
    series, meta = load_aaii()
    s = series["AAII_BULLISH"].dropna()
    assert s.min() >= 0 and s.max() <= 100
    # If we forgot to multiply by 100, max would be < 1.
    assert s.max() > 5, "AAII_BULLISH appears not to have been rescaled to pct"
    assert meta["AAII_BULLISH"].unit == "pct"


def test_aaii_bullish_plus_bearish_below_100():
    """Bullish + Bearish must be <= 100% (Neutral makes up the difference)."""
    series, _ = load_aaii()
    bullish = series["AAII_BULLISH"].dropna()
    bearish = series["AAII_BEARISH"].dropna()
    common = bullish.index.intersection(bearish.index)
    sum_ = bullish.loc[common] + bearish.loc[common]
    assert sum_.max() <= 100.5  # allow tiny rounding


def test_aaii_bull_bear_spread_signed():
    """Spread can be positive (bullish > bearish) or negative.

    Historical extremes: late-1980s/early-2000s euphoria pushed the spread
    to ~+63pp; 2008/2022/2023 pessimism pushed it to ~-54pp. Bound at
    [-65, +70] to allow these without being trivially loose.
    """
    series, _ = load_aaii()
    s = series["AAII_BULL_BEAR_SPREAD"].dropna()
    assert s.min() < 0
    assert s.max() > 0
    assert s.min() >= -65 and s.max() <= 70


def test_aaii_8wma_in_range():
    series, _ = load_aaii()
    s = series["AAII_BULL_8WMA"].dropna()
    assert s.min() >= 10 and s.max() <= 70


def test_aaii_metadata_storage_convention():
    """Metadata must record that source is decimal share x100."""
    _, meta = load_aaii()
    assert meta["AAII_BULLISH"].extra.get("source_storage_convention") == "decimal_share_x100"


# ---------------------------------------------------------------------------
# Atlanta Fed Wage Growth
# ---------------------------------------------------------------------------
def test_atlanta_wage_loads_returns_series():
    s, meta = load_atlanta_wage()
    assert meta.indicator_id == "ATLANTA_WAGE_OVERALL"
    assert meta.source == "ATLANTA_FED_WAGE_XLSX"
    assert meta.unit == "pct"
    assert meta.frequency == "M"
    assert not s.dropna().empty


def test_atlanta_wage_history_starts_1997():
    _, meta = load_atlanta_wage()
    assert pd.Timestamp("1997-01-01") <= meta.first_obs <= pd.Timestamp("1997-12-31")


def test_atlanta_wage_in_plausible_range():
    s, _ = load_atlanta_wage()
    obs = s.dropna()
    # Typical range; 2022-23 hot market peaked ~6.7%.
    assert 0.5 <= obs.min() <= obs.max() <= 8.0


def test_atlanta_wage_full_history_revisable_tagged():
    """Critical caveat: Atlanta revises full series with each release."""
    _, meta = load_atlanta_wage()
    assert meta.extra.get("full_history_revisable") is True
    assert "Atlanta Fed revises" in (meta.extra.get("vintage_caveat") or "")


# ---------------------------------------------------------------------------
# CFTC TFF Treasury (OFR HFM file)
# ---------------------------------------------------------------------------
def test_cftc_tr_returns_three_series():
    series, meta = load_cftc_tff_treasury()
    expected = {"CFTC_TR_10Y_LV_NET", "CFTC_TR_10Y_AM_NET", "CFTC_TR_10Y_DEALER_NET"}
    assert set(series.keys()) == expected


def test_cftc_tr_history_starts_2013():
    _, meta = load_cftc_tff_treasury()
    for sid in ("CFTC_TR_10Y_LV_NET", "CFTC_TR_10Y_AM_NET", "CFTC_TR_10Y_DEALER_NET"):
        assert meta[sid].first_obs >= pd.Timestamp("2013-01-01")
        assert meta[sid].first_obs <= pd.Timestamp("2013-12-31")


def test_cftc_tr_unit_is_signed_billions():
    _, meta = load_cftc_tff_treasury()
    for sid in meta:
        assert meta[sid].unit == "B_USD_signed"


def test_cftc_tr_bond_basis_structure():
    """Asset Managers structurally LONG, Leveraged Funds structurally SHORT
    (the bond basis trade). Magnitudes vary - LV positioning ramped up
    post-2018, so the FULL-history median is smaller than recent levels.
    """
    series, _ = load_cftc_tff_treasury()
    am_med = float(series["CFTC_TR_10Y_AM_NET"].median())
    lv_med = float(series["CFTC_TR_10Y_LV_NET"].median())
    assert am_med > 0, f"AM median {am_med:.0f}B not net long"
    assert lv_med < 0, f"LV median {lv_med:.0f}B not net short"
    # AM is large since 2013; LV ramped up post-2018 so median can be modest.
    assert abs(am_med) > 100
    # Recent (post-2020) LV positions are -100B to -250B; verify the trend
    # is meaningful by checking recent median rather than full-history.
    lv_recent = float(series["CFTC_TR_10Y_LV_NET"].loc["2020-01-01":].median())
    assert lv_recent < -50, f"LV recent median {lv_recent:.0f}B not strongly net short"


def test_cftc_tr_lv_position_uses_true_10y_columns():
    """LV_NET should come from TFF-LF_TY_* (true 10-year futures), per
    the loader's documented spec (the only category with per-contract data)."""
    _, meta = load_cftc_tff_treasury()
    m = meta["CFTC_TR_10Y_LV_NET"]
    assert "_TY_" in m.extra.get("long_column", "")
    assert "_TY_" in m.extra.get("short_column", "")
    assert m.extra.get("scope") == "true_10y_notional"


def test_cftc_tr_am_dealer_use_aggregate_treasury_columns():
    """AM/DI in this OFR file are reported as aggregate Treasury, NOT per-contract."""
    _, meta = load_cftc_tff_treasury()
    for sid in ("CFTC_TR_10Y_AM_NET", "CFTC_TR_10Y_DEALER_NET"):
        m = meta[sid]
        assert "_TREAS_" in m.extra.get("long_column", "")
        assert "_TREAS_" in m.extra.get("short_column", "")
        assert m.extra.get("scope") == "agg_treasury_10yreqv"


def test_cftc_tr_conviction_score_documented():
    _, meta = load_cftc_tff_treasury()
    for sid in meta:
        assert meta[sid].extra.get("conviction_score") == 5


# ---------------------------------------------------------------------------
# Cache + Gate 4C
# ---------------------------------------------------------------------------
def test_phase4c_cache_files_use_official_prefix():
    from macro_pipeline.config import DATA_CACHE
    load_aaii()
    load_atlanta_wage()
    load_cftc_tff_treasury()
    expected = [
        "official_AAII_BULLISH", "official_AAII_BEARISH",
        "official_AAII_BULL_BEAR_SPREAD", "official_AAII_BULL_8WMA",
        "official_ATLANTA_WAGE_OVERALL",
        "official_CFTC_TR_10Y_LV_NET", "official_CFTC_TR_10Y_AM_NET",
        "official_CFTC_TR_10Y_DEALER_NET",
    ]
    for stem in expected:
        assert (DATA_CACHE / f"{stem}.parquet").exists(), f"missing {stem}.parquet"


def test_gate4c_passes():
    _, aaii_meta = load_aaii()
    _, atlanta_meta = load_atlanta_wage()
    _, tr_meta = load_cftc_tff_treasury()
    report = validate_gate4c(aaii_meta, atlanta_meta, tr_meta)
    assert report.passed, "Gate 4C must pass:\n" + report.render()


# ---------------------------------------------------------------------------
# Item B: regression-config constants
# ---------------------------------------------------------------------------
def test_regression_config_constants():
    from macro_pipeline.models.regression_config import (
        CROSS_VALIDATION_TARGET,
        FORWARD_HORIZONS_MONTHS,
        PRIMARY_REGRESSION_TARGET,
        REGRESSION_TARGET_USE_FOR_TAGS,
        TARGET_TYPE,
        is_primary_regression_target,
    )
    assert PRIMARY_REGRESSION_TARGET == "SHILLER_TR_PRICE"
    assert TARGET_TYPE == "real_total_return"
    assert CROSS_VALIDATION_TARGET == "SP500TR"
    assert FORWARD_HORIZONS_MONTHS == (12, 36, 60, 120)
    assert "forward_return_calc" in REGRESSION_TARGET_USE_FOR_TAGS
    # is_primary_regression_target works with metadata + dict + bare string-id
    from macro_pipeline.loaders.shiller import load_shiller
    _, meta = load_shiller()
    assert is_primary_regression_target(meta["SHILLER_TR_PRICE"]) is True
    assert is_primary_regression_target(meta["SHILLER_PRICE"]) is False
    assert is_primary_regression_target({"indicator_id": "SHILLER_TR_PRICE"}) is True
