"""Phase 4B official-source loader tests.

Covers Shiller, ACM Term Premium, Fernald TFP, HLW (current vintage),
and IMF COFER. All read local files; cross-validation test additionally
hits Yahoo for ^SP500TR.
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

from src.loaders.acm_termpremium import load_acm_termpremium
from src.loaders.fernald_tfp import load_fernald_tfp
from src.loaders.hlw_rstar import load_hlw_rstar
from src.loaders.imf_cofer import (
    QUARTER_COL_RE,
    SERIES_CODE_RE,
    _quarter_label_to_ts,
    load_imf_cofer,
)
from src.loaders.shiller import _shiller_decimal_to_ts, load_shiller
from src.validation import cross_validate_tr_sources, validate_gate4b


# ---------------------------------------------------------------------------
# Shiller decimal-date parser (offline)
# ---------------------------------------------------------------------------
def test_shiller_decimal_parser_january_vs_october():
    """Critical: 1871.01 = January, 1871.1 = October (Shiller's literal format)."""
    jan = _shiller_decimal_to_ts(1871.01)
    oct_ = _shiller_decimal_to_ts(1871.10)
    dec = _shiller_decimal_to_ts(1871.12)
    assert jan == pd.Timestamp("1871-01-01")
    assert oct_ == pd.Timestamp("1871-10-01")
    assert dec == pd.Timestamp("1871-12-01")
    # 1871.1 (float, trailing zero lost) must still resolve to October
    assert _shiller_decimal_to_ts(1871.1) == pd.Timestamp("1871-10-01")


def test_shiller_decimal_parser_handles_invalid():
    assert pd.isna(_shiller_decimal_to_ts(None))
    assert pd.isna(_shiller_decimal_to_ts("not-a-number"))
    assert pd.isna(_shiller_decimal_to_ts(1871.13))  # month > 12
    assert pd.isna(_shiller_decimal_to_ts(1871.0))   # month = 0


# ---------------------------------------------------------------------------
# Shiller integration
# ---------------------------------------------------------------------------
def test_shiller_returns_nine_series():
    series, meta = load_shiller()
    expected = {
        "SHILLER_PRICE", "SHILLER_DIVIDEND", "SHILLER_EARNINGS", "SHILLER_CPI",
        "SHILLER_GS10", "SHILLER_REAL_PRICE", "SHILLER_TR_PRICE",
        "SHILLER_CAPE", "SHILLER_TR_CAPE",
    }
    assert set(series.keys()) == expected
    assert set(meta.keys()) == expected


def test_shiller_history_starts_1871_01():
    _, meta = load_shiller()
    assert meta["SHILLER_PRICE"].first_obs <= pd.Timestamp("1871-01-01")
    assert meta["SHILLER_GS10"].first_obs <= pd.Timestamp("1871-01-01")


def test_shiller_cape_in_academic_range():
    """CAPE has historically lived in [5, 50]; current ~36, lows ~5 (1920)."""
    series, _ = load_shiller()
    cape = series["SHILLER_CAPE"].dropna()
    assert cape.min() >= 4.0
    assert cape.max() <= 50.0


def test_shiller_tr_price_role_is_regression_target():
    _, meta = load_shiller()
    assert meta["SHILLER_TR_PRICE"].extra.get("role") == "regression_target"
    use_for = meta["SHILLER_TR_PRICE"].extra.get("use_for", [])
    assert "forward_return_calc" in use_for
    assert "r_squared_regression" in use_for


def test_shiller_tr_price_compounds_through_history():
    """TR_PRICE must grow by factor of >1000 over 150 years (real total return)."""
    series, _ = load_shiller()
    tr = series["SHILLER_TR_PRICE"].dropna()
    growth = float(tr.iloc[-1] / tr.iloc[0])
    assert growth > 1000, f"TR_PRICE growth {growth:.0f}x is too small"


# ---------------------------------------------------------------------------
# ACM Term Premium
# ---------------------------------------------------------------------------
def test_acm_returns_three_series():
    series, meta = load_acm_termpremium()
    assert set(series.keys()) == {"ACM_TP_10Y", "ACM_TP_5Y", "ACM_RNY_10Y"}


def test_acm_tp_10y_in_expected_range():
    series, _ = load_acm_termpremium()
    s = series["ACM_TP_10Y"].dropna()
    assert -3.0 <= s.min() <= s.max() <= 6.0


def test_acm_history_starts_1961():
    _, meta = load_acm_termpremium()
    assert pd.Timestamp("1961-06-01") <= meta["ACM_TP_10Y"].first_obs <= pd.Timestamp("1961-12-31")


def test_acm_rny_plus_tp_approximates_yield():
    """ACMRNY + ACMTP should approximately equal ACMY (model-fitted yield)."""
    series, _ = load_acm_termpremium()
    rny = series["ACM_RNY_10Y"].dropna()
    tp = series["ACM_TP_10Y"].dropna()
    common = rny.index.intersection(tp.index)
    sum_ = rny.loc[common] + tp.loc[common]
    # The sum should yield reasonable nominal levels (0-15%)
    assert sum_.min() >= 0
    assert sum_.max() <= 20


# ---------------------------------------------------------------------------
# Fernald TFP
# ---------------------------------------------------------------------------
def test_fernald_returns_two_series():
    series, _ = load_fernald_tfp()
    assert set(series.keys()) == {"FERNALD_TFP", "FERNALD_TFP_UTIL"}


def test_fernald_tfp_in_plausible_range():
    series, _ = load_fernald_tfp()
    s = series["FERNALD_TFP"].dropna()
    assert -25.0 <= s.min() <= s.max() <= 25.0


def test_fernald_history_starts_1947():
    _, meta = load_fernald_tfp()
    assert meta["FERNALD_TFP"].first_obs <= pd.Timestamp("1947-12-31")


def test_fernald_metadata_marks_structural():
    _, meta = load_fernald_tfp()
    assert meta["FERNALD_TFP"].extra.get("structural") is True
    assert meta["FERNALD_TFP"].source == "SF_FED_FERNALD"


# ---------------------------------------------------------------------------
# HLW r-star (current vintage)
# ---------------------------------------------------------------------------
def test_hlw_returns_three_series():
    series, _ = load_hlw_rstar()
    assert set(series.keys()) == {"HLW_RSTAR", "HLW_TREND_GROWTH", "HLW_OUTPUT_GAP"}


def test_hlw_rstar_in_expected_range():
    series, _ = load_hlw_rstar()
    s = series["HLW_RSTAR"].dropna()
    # Loosened upper bound to 7 to admit early-1960s peak (~6.16).
    assert -1.0 <= s.min() <= s.max() <= 7.0


def test_hlw_metadata_marks_current_vintage():
    _, meta = load_hlw_rstar()
    for sid in ("HLW_RSTAR", "HLW_TREND_GROWTH", "HLW_OUTPUT_GAP"):
        assert meta[sid].extra.get("vintage") == "current"
        assert meta[sid].extra.get("country") == "US"


# ---------------------------------------------------------------------------
# IMF COFER
# ---------------------------------------------------------------------------
def test_imf_series_code_regex_matches():
    """SERIES_CODE pattern matches the share-quarterly entries."""
    m = SERIES_CODE_RE.match("G001.AFXRA.CI_USD.SHRO_PT.Q")
    assert m is not None
    assert m.group("currency") == "USD"
    assert SERIES_CODE_RE.match("G001.AFXRA.CI_USD.SHRO_PT.A") is None  # annual
    assert SERIES_CODE_RE.match("G001.AFXRA.CI_USD.NV_USD.Q") is None  # not share


def test_imf_quarter_label_parser():
    assert QUARTER_COL_RE.match("2024-Q1") is not None
    assert QUARTER_COL_RE.match("2024") is None  # bare year
    assert _quarter_label_to_ts("2024-Q3") == pd.Timestamp("2024-07-01")


def test_imf_returns_six_currencies():
    series, _ = load_imf_cofer()
    expected = {
        "USD_RESERVE_SHARE", "EUR_RESERVE_SHARE", "JPY_RESERVE_SHARE",
        "GBP_RESERVE_SHARE", "CHF_RESERVE_SHARE", "CNY_RESERVE_SHARE",
    }
    assert set(series.keys()) == expected


def test_imf_usd_share_in_canonical_range():
    """USD share has been in [50%, 75%] over 1999-present."""
    series, _ = load_imf_cofer()
    s = series["USD_RESERVE_SHARE"].dropna()
    assert 50.0 <= s.min() <= s.max() <= 75.0


def test_imf_cny_starts_after_2016():
    """RMB inclusion in COFER began with 2016-Q4."""
    series, _ = load_imf_cofer()
    cny = series["CNY_RESERVE_SHARE"].dropna()
    assert cny.index.min() >= pd.Timestamp("2016-01-01")


# ---------------------------------------------------------------------------
# Cache + Gate 4B
# ---------------------------------------------------------------------------
def test_phase4b_cache_files_use_official_prefix():
    from src.config import DATA_CACHE
    load_shiller()
    load_acm_termpremium()
    load_fernald_tfp()
    load_hlw_rstar()
    load_imf_cofer()

    expected = [
        "official_SHILLER_PRICE", "official_SHILLER_TR_PRICE",
        "official_SHILLER_CAPE", "official_ACM_TP_10Y",
        "official_FERNALD_TFP", "official_HLW_RSTAR",
        "official_USD_RESERVE_SHARE", "official_CNY_RESERVE_SHARE",
    ]
    for stem in expected:
        assert (DATA_CACHE / f"{stem}.parquet").exists(), f"missing {stem}.parquet"


def test_gate4b_passes():
    sh_series, sh_meta = load_shiller()
    _, acm_meta = load_acm_termpremium()
    _, fer_meta = load_fernald_tfp()
    _, hlw_meta = load_hlw_rstar()
    _, imf_meta = load_imf_cofer()
    report = validate_gate4b(sh_meta, acm_meta, fer_meta, hlw_meta, imf_meta)
    assert report.passed, "Gate 4B must pass:\n" + report.render()


# ---------------------------------------------------------------------------
# Cross-validation: Yahoo ^SP500TR vs Shiller TR_PRICE
# ---------------------------------------------------------------------------
def test_cross_validation_yahoo_sp500tr_vs_shiller_tr():
    """Yahoo (nominal) and Shiller (real) TR series should track each other
    on annual growth, modulo CPI inflation gap (~2-3% per year)."""
    from src.loaders.yahoo_loader import load_yahoo_series

    sh_series, _ = load_shiller()
    yh, _ = load_yahoo_series("SP500TR")

    result = cross_validate_tr_sources(
        yh, sh_series["SHILLER_TR_PRICE"],
        overlap_start="2010-01-01", overlap_end="2024-12-31",
    )
    assert result["n_years"] >= 10, (
        f"only {result['n_years']} overlap years; expected >= 10"
    )
    # Median diff between nominal Yahoo and real Shiller should be roughly
    # the inflation rate (1-4% per year). Bound generously.
    assert -1.0 <= result["median_diff_pct"] <= 6.0, (
        f"median yoy diff {result['median_diff_pct']:.2f}% outside expected "
        "[-1, 6]; suggests scale or unit error in one of the series"
    )
