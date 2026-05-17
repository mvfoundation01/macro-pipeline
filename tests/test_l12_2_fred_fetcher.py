"""L12 v2 D7 — Tests for ``macro_pipeline.webapp.fred_fetcher``.

Counts: 7 tests (4 NEG / 3 POS) = 57% NEG (validation-heavy).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from macro_pipeline.webapp import fred_fetcher as ff_module
from macro_pipeline.webapp.fred_fetcher import FetchResult, FREDFetcher


@pytest.fixture(autouse=True)
def _clear_fred_cache():
    """Wipe the per-test process cache so tests are independent."""
    ff_module._cache_clear()
    yield
    ff_module._cache_clear()


# ----------------------------------------------------------------------
# POS — happy paths (3 tests)
# ----------------------------------------------------------------------
def test_fetcher_with_mocked_client_returns_value_and_date() -> None:
    """When the FRED client returns data, the fetcher exposes both fields."""
    fetcher = FREDFetcher(api_key="dummy")  # construction won't raise even on fake key
    # Skip the dummy-key path by patching the underlying client directly.
    fake_client = MagicMock()
    fake_client.get_series.return_value = pd.Series(
        [4.2], index=pd.to_datetime(["2026-04-30"])
    )
    fetcher._fred = fake_client
    result = fetcher.fetch_unrate()
    assert result.ok is True
    assert result.value == pytest.approx(4.2)
    assert result.as_of == "2026-04-30"


def test_payrolls_mom_computes_difference_of_last_two_observations() -> None:
    fetcher = FREDFetcher(api_key="dummy")
    fake_client = MagicMock()
    # 200k jobs added between the two latest months.
    fake_client.get_series.return_value = pd.Series(
        [158_500.0, 158_700.0],
        index=pd.to_datetime(["2026-03-01", "2026-04-01"]),
    )
    fetcher._fred = fake_client
    result = fetcher.fetch_payrolls_mom()
    assert result.value == pytest.approx(200.0)
    assert result.as_of == "2026-04-01"


def test_fetch_all_form_fields_returns_three_keyed_results() -> None:
    """``fetch_all_form_fields`` is what the home route calls.

    NB: ``macro_pipeline.config`` calls ``dotenv.load_dotenv()`` at import
    time which may have populated ``FRED_API_KEY`` from V's local ``.env``.
    Clear the env explicitly here so we test the no-key path deterministically
    regardless of whether the dev machine has a real key.
    """
    with patch.dict("os.environ", {}, clear=True):
        fetcher = FREDFetcher()  # no api_key arg, no env → unavailable
    out = fetcher.fetch_all_form_fields()
    assert set(out.keys()) == {"unemployment_rate", "payrolls_mom", "fed_funds_rate"}
    assert all(r.ok is False for r in out.values())


# ----------------------------------------------------------------------
# NEG — failure-mode contracts (4 tests)
# ----------------------------------------------------------------------
def test_fetcher_without_key_reports_unavailable_and_returns_empty() -> None:
    """No env var, no constructor arg → ``available`` False, fetches return empty."""
    with patch.dict("os.environ", {}, clear=True):
        fetcher = FREDFetcher()
    assert fetcher.available is False
    assert fetcher.fetch_unrate() == FetchResult.empty()
    assert fetcher.fetch_fed_funds() == FetchResult.empty()
    assert fetcher.fetch_payrolls_mom() == FetchResult.empty()


def test_fetcher_swallows_underlying_api_error() -> None:
    """A raised exception from the FRED client must not propagate."""
    fetcher = FREDFetcher(api_key="dummy")
    fake_client = MagicMock()
    fake_client.get_series.side_effect = RuntimeError("network glitch")
    fetcher._fred = fake_client
    result = fetcher.fetch_unrate()
    assert result == FetchResult.empty()


def test_fetcher_handles_empty_series_gracefully() -> None:
    """Empty pandas series → empty result (not IndexError)."""
    fetcher = FREDFetcher(api_key="dummy")
    fake_client = MagicMock()
    fake_client.get_series.return_value = pd.Series(dtype=float)
    fetcher._fred = fake_client
    assert fetcher.fetch_unrate() == FetchResult.empty()


def test_payrolls_mom_returns_empty_when_only_one_observation() -> None:
    """MoM Δ needs ≥2 obs; one obs must yield empty, not crash on iloc[-2]."""
    fetcher = FREDFetcher(api_key="dummy")
    fake_client = MagicMock()
    fake_client.get_series.return_value = pd.Series(
        [158_500.0], index=pd.to_datetime(["2026-04-01"])
    )
    fetcher._fred = fake_client
    assert fetcher.fetch_payrolls_mom() == FetchResult.empty()
