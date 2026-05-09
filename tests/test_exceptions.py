"""Tests for the typed IndicatorLoadError hierarchy (Layer 1.5D.1).

Each subclass has at least one trigger test using mocked failures so the
suite can run offline.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from macro_pipeline.exceptions import (
    IndicatorAuthError,
    IndicatorLoadError,
    IndicatorNetworkError,
    IndicatorNotFoundError,
    IndicatorParseError,
    IndicatorRateLimitError,
    from_request_exception,
)


# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------
def test_all_subclasses_inherit_from_base():
    for cls in (
        IndicatorAuthError,
        IndicatorNotFoundError,
        IndicatorRateLimitError,
        IndicatorParseError,
        IndicatorNetworkError,
    ):
        assert issubclass(cls, IndicatorLoadError)


def test_recoverable_flag_per_subclass():
    """Auth / NotFound / Parse are NOT recoverable; RateLimit / Network are."""
    assert IndicatorAuthError(indicator_id="X", source="S").recoverable is False
    assert IndicatorNotFoundError(indicator_id="X", source="S").recoverable is False
    assert IndicatorParseError(indicator_id="X", source="S").recoverable is False
    assert IndicatorRateLimitError(indicator_id="X", source="S").recoverable is True
    assert IndicatorNetworkError(indicator_id="X", source="S").recoverable is True


def test_base_carries_indicator_id_source_context():
    err = IndicatorLoadError(
        indicator_id="PAYEMS", source="FRED_API",
        reason="something", context={"http_status": 500},
    )
    assert err.indicator_id == "PAYEMS"
    assert err.source == "FRED_API"
    assert err.context == {"http_status": 500}
    assert "PAYEMS" in str(err)
    assert "FRED_API" in str(err)


# ---------------------------------------------------------------------------
# from_request_exception conversions
# ---------------------------------------------------------------------------
def _http_error(status: int) -> requests.HTTPError:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    return requests.HTTPError(response=resp)


def test_from_request_exception_401_yields_auth():
    err = from_request_exception(
        _http_error(401), indicator_id="X", source="FRED_API",
    )
    assert isinstance(err, IndicatorAuthError)
    assert err.context["http_status"] == 401


def test_from_request_exception_404_yields_not_found():
    err = from_request_exception(
        _http_error(404), indicator_id="X", source="FRED_API",
    )
    assert isinstance(err, IndicatorNotFoundError)


def test_from_request_exception_429_yields_rate_limit():
    err = from_request_exception(
        _http_error(429), indicator_id="X", source="YAHOO",
    )
    assert isinstance(err, IndicatorRateLimitError)
    assert err.recoverable is True


def test_from_request_exception_500_yields_network():
    err = from_request_exception(
        _http_error(500), indicator_id="X", source="EBP",
    )
    assert isinstance(err, IndicatorNetworkError)


def test_from_request_exception_connection_yields_network():
    err = from_request_exception(
        ConnectionError("dns fail"), indicator_id="X", source="FRED_API",
    )
    assert isinstance(err, IndicatorNetworkError)
    assert err.recoverable is True


# ---------------------------------------------------------------------------
# Loader retrofits — each subclass has at least one trigger test
# ---------------------------------------------------------------------------
def test_yahoo_raises_indicator_network_error_on_fetch_failure():
    """yahoo_loader retrofit (D.1)."""
    from macro_pipeline.loaders.yahoo_loader import load_yahoo_series
    with patch(
        "macro_pipeline.loaders.yahoo_loader._fetch_yahoo_one",
        side_effect=ConnectionError("simulated"),
    ), pytest.raises(IndicatorNetworkError) as exc_info:
        load_yahoo_series("SPX_TR", force_refresh=True)
    err = exc_info.value
    assert err.source == "YAHOO_FINANCE"
    assert err.indicator_id == "SPX_TR"
    assert err.recoverable is True
    assert isinstance(err.original_exception, ConnectionError)


def test_ebp_raises_indicator_network_error_when_url_unreachable(tmp_path, monkeypatch):
    """ebp loader retrofit (D.1)."""
    from macro_pipeline.loaders import ebp as ebp_mod

    monkeypatch.setattr(ebp_mod, "EBP_LOCAL_PATH", tmp_path / "no_ebp.csv")

    def _broken(*a, **kw):
        raise requests.ConnectionError("simulated")

    monkeypatch.setattr(ebp_mod.requests, "get", _broken)

    with pytest.raises(IndicatorNetworkError) as exc_info:
        ebp_mod.fetch_ebp_csv(force_refresh=True)
    assert exc_info.value.indicator_id == "EBP"


def test_ntfs_raises_indicator_network_error_when_gsw_unreachable(tmp_path, monkeypatch):
    """ntfs loader retrofit (D.1)."""
    from macro_pipeline.loaders import ntfs as ntfs_mod

    monkeypatch.setattr(ntfs_mod, "GSW_LOCAL_PATH", tmp_path / "no_gsw.csv")

    def _broken(*a, **kw):
        raise requests.Timeout("simulated")

    monkeypatch.setattr(ntfs_mod.requests, "get", _broken)

    with pytest.raises(IndicatorNetworkError) as exc_info:
        ntfs_mod.fetch_gsw_csv(force_refresh=True)
    assert exc_info.value.recoverable is True


def test_fred_raises_indicator_not_found_when_no_data():
    """fred_loader retrofit (D.1)."""
    from macro_pipeline.loaders import fred_loader as fred_mod

    fake = MagicMock()
    fake.get_series.return_value = pd.Series([], dtype=float)

    with (
        patch.object(fred_mod, "Fred", return_value=fake),
        pytest.raises(IndicatorNotFoundError) as exc_info,
    ):
        fred_mod.load_fred_series("T10Y2Y", force_refresh=True)
    assert exc_info.value.source == "FRED_API"
    assert exc_info.value.indicator_id == "T10Y2Y"


def test_atlanta_wage_raises_parse_error_on_missing_column(tmp_path, monkeypatch):
    """atlanta_wage retrofit (D.1) — schema drift surfaces as ParseError."""
    from macro_pipeline.loaders import atlanta_wage as aw_mod

    bogus_xlsx = tmp_path / "wagegrowthdata.xlsx"
    pd.DataFrame({"date": ["2024-01-01"], "WrongHeader": [3.0]}).to_excel(
        bogus_xlsx, sheet_name=aw_mod.WAGE_SHEET, index=False,
    )
    monkeypatch.setattr(aw_mod, "WAGE_PATH", bogus_xlsx)

    with pytest.raises(IndicatorParseError) as exc_info:
        aw_mod._read_atlanta_wage_raw()
    assert "Overall" in exc_info.value.context["expected_column"]


def test_atlanta_wage_raises_not_found_when_file_missing(tmp_path, monkeypatch):
    from macro_pipeline.loaders import atlanta_wage as aw_mod
    monkeypatch.setattr(aw_mod, "WAGE_PATH", tmp_path / "no_such.xlsx")
    with pytest.raises(IndicatorNotFoundError):
        aw_mod._read_atlanta_wage_raw()


def test_indicator_auth_error_carries_correct_context():
    err = IndicatorAuthError(
        indicator_id="X", source="FRED_API",
        original_exception=ValueError("missing api_key"),
    )
    assert err.recoverable is False
    assert "Authentication" in err.reason


def test_indicator_parse_error_carries_correct_context():
    err = IndicatorParseError(
        indicator_id="HLW_RSTAR", source="NYFED_HLW_CURRENT_XLSX",
        reason="column 14 out of range (file has 12 columns)",
        context={"file_columns": 12},
    )
    assert err.context["file_columns"] == 12
    assert err.recoverable is False
