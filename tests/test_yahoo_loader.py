"""Yahoo Finance loader tests (Phase 3, Gate 3 partial).

These tests hit Yahoo's API. If you're offline they will fail loudly.
The ^MOVE fallback test mocks the API to avoid network dependence on
that path specifically.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pandas as pd
import pytest
from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("FRED_API_KEY"):
    pytest.skip(
        "FRED_API_KEY not set (required for src.config import)",
        allow_module_level=True,
    )

from src.loaders.yahoo_loader import (
    YAHOO_REGISTRY,
    load_yahoo_all,
    load_yahoo_series,
    squeeze_close_from_yfinance,
)


# ---------------------------------------------------------------------------
# Registry sanity (offline)
# ---------------------------------------------------------------------------
def test_yahoo_registry_has_26_series():
    """22 unique tickers + 3 dual PRICE + ^SP500TR = 26 indicator ids."""
    assert len(YAHOO_REGISTRY) == 26


def test_yahoo_indicator_ids_are_unique():
    ids = list(YAHOO_REGISTRY.keys())
    assert len(set(ids)) == len(ids)


def test_yahoo_naming_convention_yahoo_suffix_on_collision():
    """When an indicator name collides with another loader source, suffix _YAHOO.
    Otherwise use the bare name.
    """
    # ^VIX collides with TV's VIX -> must be VIX_YAHOO (not VIX_YH or bare VIX)
    assert "VIX_YAHOO" in YAHOO_REGISTRY
    assert YAHOO_REGISTRY["VIX_YAHOO"]["yahoo_ticker"] == "^VIX"
    assert "VIX_YH" not in YAHOO_REGISTRY  # old name retired
    # Non-colliding tickers keep clean names
    for clean in ("DXY", "GOLD", "RSP", "SKEW", "MOVE", "VVIX", "VIX3M"):
        assert clean in YAHOO_REGISTRY
    # Sector ETFs already collision-free
    for sector in ("XLK", "XLF", "XLV", "XLY", "XLP", "XLE",
                    "XLI", "XLB", "XLU", "XLRE", "XLC"):
        assert sector in YAHOO_REGISTRY


def test_yahoo_dual_series_spx_ndx_rut():
    """SPX, NDX, RUT each expose both _PRICE and _TR variants."""
    for base in ("SPX", "NDX", "RUT"):
        price_id = f"{base}_PRICE"
        tr_id = f"{base}_TR"
        assert price_id in YAHOO_REGISTRY
        assert tr_id in YAHOO_REGISTRY
        # Same underlying ticker, different auto_adjust mode
        assert (
            YAHOO_REGISTRY[price_id]["yahoo_ticker"]
            == YAHOO_REGISTRY[tr_id]["yahoo_ticker"]
        )
        assert YAHOO_REGISTRY[price_id]["auto_adjust"] is False
        assert YAHOO_REGISTRY[tr_id]["auto_adjust"] is True
        # use_for tags differentiate appropriate downstream contexts
        price_use = set(YAHOO_REGISTRY[price_id]["use_for"])
        tr_use = set(YAHOO_REGISTRY[tr_id]["use_for"])
        assert "drawdown" in price_use
        assert "threshold_check" in price_use
        assert "total_return" in tr_use
        assert "r_squared_regression" in tr_use
        # The two contexts should be disjoint on the load-bearing tags
        assert "drawdown" not in tr_use
        assert "total_return" not in price_use


def test_squeeze_close_from_multi_ticker_close_first():
    """yfinance bulk download: ('Close', '<ticker>') columns."""
    idx = pd.date_range("2024-01-02", periods=3, freq="B")
    cols = pd.MultiIndex.from_tuples(
        [("Close", "^GSPC"), ("Close", "^NDX"), ("Volume", "^GSPC")]
    )
    df = pd.DataFrame(
        [[4700, 16500, 1e9], [4750, 16600, 1.1e9], [4800, 16700, 1.2e9]],
        index=idx, columns=cols,
    )
    s = squeeze_close_from_yfinance(df, "^GSPC")
    assert s.tolist() == [4700.0, 4750.0, 4800.0]
    assert s.name == "^GSPC"


def test_squeeze_close_from_single_ticker_flat():
    """yfinance single-ticker download: flat OHLCV columns."""
    idx = pd.date_range("2024-01-02", periods=3, freq="B")
    df = pd.DataFrame(
        {"Open": [1, 2, 3], "Close": [10, 20, 30], "Volume": [100, 200, 300]},
        index=idx,
    )
    s = squeeze_close_from_yfinance(df, "^GSPC")
    assert s.tolist() == [10.0, 20.0, 30.0]


# ---------------------------------------------------------------------------
# Live Yahoo fetches (cached after first run)
# ---------------------------------------------------------------------------
def test_load_spx_tr_returns_series():
    s, meta = load_yahoo_series("SPX_TR")
    assert isinstance(s, pd.Series)
    assert meta.indicator_id == "SPX_TR"
    assert meta.source == "YAHOO_FINANCE"
    assert meta.extra.get("auto_adjust") is True
    assert not s.dropna().empty


def test_load_spx_price_and_tr_both_load_with_distinct_metadata():
    """SPX_PRICE and SPX_TR both load with the right metadata flags.

    yfinance's auto_adjust applies dividend back-adjustment, which is a
    no-op for ^GSPC because it's a price-only index (no embedded
    dividends). The two series therefore carry IDENTICAL numerical data
    but distinct ``use_for`` tags so downstream code can label its
    intent. For true S&P 500 total return use Shiller's TR_CAPE (Phase 4
    official loader), not Yahoo.
    """
    s_tr, m_tr = load_yahoo_series("SPX_TR")
    s_px, m_px = load_yahoo_series("SPX_PRICE")

    assert m_tr.indicator_id == "SPX_TR"
    assert m_px.indicator_id == "SPX_PRICE"
    assert m_tr.extra.get("auto_adjust") is True
    assert m_px.extra.get("auto_adjust") is False
    assert m_tr.extra.get("yahoo_ticker") == m_px.extra.get("yahoo_ticker") == "^GSPC"

    # Distinct use-case tags
    assert "drawdown" in m_px.extra.get("use_for", [])
    assert "threshold_check" in m_px.extra.get("use_for", [])
    assert "total_return" in m_tr.extra.get("use_for", [])
    assert "r_squared_regression" in m_tr.extra.get("use_for", [])

    # Both load and end at the same latest value (same ticker).
    assert not s_tr.dropna().empty
    assert not s_px.dropna().empty
    assert s_tr.dropna().iloc[-1] == s_px.dropna().iloc[-1]


def test_load_all_returns_26_columns():
    df, meta = load_yahoo_all()
    assert df.shape[1] == 26, f"expected 26 columns, got {df.shape[1]}"
    for sid, m in meta.items():
        assert m.source == "YAHOO_FINANCE"
        assert m.extra.get("tier") == 3


def test_sp500tr_loads_and_diverges_from_gspc():
    """Official S&P 500 Total Return must grow much faster than ^GSPC over
    decades because it compounds reinvested dividends. Recent ^SP500TR is
    >2x ^GSPC level on the same date.
    """
    s_tr, m_tr = load_yahoo_series("SP500TR")
    s_px, _ = load_yahoo_series("SPX_PRICE")

    assert m_tr.indicator_id == "SP500TR"
    assert m_tr.extra.get("yahoo_ticker") == "^SP500TR"
    assert m_tr.extra.get("category") == "equity_index_tr"
    assert "r_squared_regression" in m_tr.extra.get("use_for", [])

    # ^SP500TR history starts ~1988
    first_tr = s_tr.dropna().index.min()
    assert pd.Timestamp("1987-12-01") <= first_tr <= pd.Timestamp("1988-12-31"), (
        f"^SP500TR first_obs={first_tr.date()} outside 1988 launch window"
    )

    # On the most recent shared business day, SP500TR should be substantially
    # above SPX_PRICE because of ~37 years of compounded dividends.
    latest = sorted(set(s_tr.dropna().index) & set(s_px.dropna().index))[-1]
    tr_val = float(s_tr.loc[latest])
    px_val = float(s_px.loc[latest])
    assert tr_val > 2.0 * px_val, (
        f"on {latest.date()}: SP500TR={tr_val:.1f}, SPX_PRICE={px_val:.1f}; "
        "TR should be at least ~2x PRICE after ~37 years of dividends"
    )


def test_yahoo_metadata_tier_is_3():
    """All Yahoo series tagged tier=3 (unofficial)."""
    _, meta = load_yahoo_series("SPX_TR")
    assert meta.extra.get("tier") == 3


def test_yahoo_spx_tr_in_plausible_range():
    s, _ = load_yahoo_series("SPX_TR")
    obs = s.dropna()
    # auto_adjust=True back-adjusts pre-dividend prices, so 1959-era min ~4.
    assert obs.min() >= 3
    assert obs.max() <= 1e5
    assert obs.iloc[-1] > 1000  # post-2010 SPX always > 1000


def test_yahoo_vix_in_plausible_range():
    s, meta = load_yahoo_series("VIX_YAHOO")
    obs = s.dropna()
    assert 5 <= obs.min() <= obs.max() <= 100
    assert meta.indicator_id == "VIX_YAHOO"
    assert meta.unit == "index"


def test_yahoo_no_negative_close_prices():
    """auto_adjust must not produce negative prices on any equity series."""
    df, _ = load_yahoo_all()
    equity_like = [
        "SPX_PRICE", "SPX_TR", "NDX_PRICE", "NDX_TR", "RUT_PRICE", "RUT_TR",
        "RSP", "DXY", "GOLD",
        "XLK", "XLF", "XLV", "XLY", "XLP", "XLE",
        "XLI", "XLB", "XLU", "XLRE", "XLC",
    ]
    for sid in equity_like:
        if sid in df.columns:
            assert df[sid].dropna().min() > 0, f"{sid} has non-positive prices"


def test_yahoo_xlre_first_obs_after_2015():
    s, _ = load_yahoo_series("XLRE")
    first = s.dropna().index.min()
    assert first >= pd.Timestamp("2015-10-01"), (
        f"XLRE first obs {first.date()} earlier than expected (~2015-10-08)"
    )


def test_yahoo_xlc_first_obs_after_2018():
    s, _ = load_yahoo_series("XLC")
    first = s.dropna().index.min()
    assert first >= pd.Timestamp("2018-06-01"), (
        f"XLC first obs {first.date()} earlier than expected (~2018-06-19)"
    )


def test_yahoo_older_sectors_start_around_1998():
    """XLK launched 1998-12-22; should have data deep into history."""
    s, _ = load_yahoo_series("XLK")
    first = s.dropna().index.min()
    assert first <= pd.Timestamp("1999-01-31"), (
        f"XLK first obs {first.date()} later than expected (~1998-12-22)"
    )


def test_yahoo_skew_always_above_100():
    """Cboe SKEW is bounded below by 100 by construction."""
    s, _ = load_yahoo_series("SKEW")
    obs = s.dropna()
    assert obs.min() >= 99.0


# ---------------------------------------------------------------------------
# ^MOVE fallback (mocked failure path)
# ---------------------------------------------------------------------------
def test_move_fallback_uses_stale_cache_on_failure():
    """If yfinance raises for ^MOVE, loader falls back to cached parquet."""
    _, meta_first = load_yahoo_series("MOVE")
    assert meta_first.indicator_id == "MOVE"

    with patch(
        "src.loaders.yahoo_loader._fetch_yahoo_one",
        side_effect=ConnectionError("simulated yfinance failure"),
    ):
        s, meta = load_yahoo_series("MOVE", force_refresh=True)
    assert not s.dropna().empty, "fallback should serve cached data"
    assert meta.extra.get("fetch_status") == "fallback_to_stale_cache"
    assert meta.extra.get("unofficial_yahoo") is True


def test_non_unofficial_ticker_does_not_silently_fall_back():
    """A regular ticker (not ^MOVE) must propagate the failure."""
    with patch(
        "src.loaders.yahoo_loader._fetch_yahoo_one",
        side_effect=ConnectionError("simulated"),
    ):
        with pytest.raises(ConnectionError):
            load_yahoo_series("SPX_TR", force_refresh=True)


# ---------------------------------------------------------------------------
# Cache + column naming
# ---------------------------------------------------------------------------
def test_yahoo_cached_parquet_column_is_bare_indicator_id():
    load_yahoo_series("SPX_TR")
    from src.config import DATA_CACHE
    df = pd.read_parquet(DATA_CACHE / "yahoo_SPX_TR.parquet")
    assert df.columns.tolist() == ["SPX_TR"]
