"""L12 v2 D8 — Tests for ``macro_pipeline.webapp.yfinance_fetcher``.

Counts: 4 tests (2 NEG / 2 POS) = 50% NEG.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from macro_pipeline.webapp import yfinance_fetcher as yf_module
from macro_pipeline.webapp.fred_fetcher import FetchResult
from macro_pipeline.webapp.yfinance_fetcher import YahooFetcher


@pytest.fixture(autouse=True)
def _clear_yf_cache():
    yf_module._cache_clear()
    yield
    yf_module._cache_clear()


# ----------------------------------------------------------------------
# POS (2 tests)
# ----------------------------------------------------------------------
def test_fetch_sp500_with_mocked_yfinance_returns_close_and_date() -> None:
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = pd.DataFrame(
        {"Close": [5783.5, 5800.1]},
        index=pd.to_datetime(["2026-05-02", "2026-05-05"]),
    )
    fake_module = MagicMock()
    fake_module.Ticker.return_value = fake_ticker
    with patch.dict("sys.modules", {"yfinance": fake_module}):
        result = YahooFetcher().fetch_sp500()
    assert result.ok is True
    assert result.value == pytest.approx(5800.1)
    assert result.as_of == "2026-05-05"


def test_fetch_all_form_fields_returns_sp500_key() -> None:
    """API parallel to FREDFetcher.fetch_all_form_fields — single-entry dict."""
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = pd.DataFrame(
        {"Close": [5800.0]}, index=pd.to_datetime(["2026-05-05"])
    )
    fake_module = MagicMock()
    fake_module.Ticker.return_value = fake_ticker
    with patch.dict("sys.modules", {"yfinance": fake_module}):
        out = YahooFetcher().fetch_all_form_fields()
    assert set(out.keys()) == {"sp500_current"}
    assert out["sp500_current"].ok is True


# ----------------------------------------------------------------------
# NEG (2 tests)
# ----------------------------------------------------------------------
def test_yfinance_exception_returns_empty() -> None:
    """Any exception from yfinance must produce ``FetchResult.empty()``."""
    fake_module = MagicMock()
    fake_module.Ticker.side_effect = RuntimeError("Yahoo API rejected request")
    with patch.dict("sys.modules", {"yfinance": fake_module}):
        result = YahooFetcher().fetch_sp500()
    assert result == FetchResult.empty()


def test_empty_history_returns_empty() -> None:
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = pd.DataFrame()  # empty frame
    fake_module = MagicMock()
    fake_module.Ticker.return_value = fake_ticker
    with patch.dict("sys.modules", {"yfinance": fake_module}):
        result = YahooFetcher().fetch_sp500()
    assert result == FetchResult.empty()
