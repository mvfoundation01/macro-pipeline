"""Tests that exercise the offline mock fixtures (Layer 1.5D.2).

These prove the conftest fixtures work end-to-end: a loader call routed
through the fixture returns deterministic data without making any network
calls. CI (which has no data/cache populated) relies on this path.
"""
from __future__ import annotations

import pandas as pd
import pytest


def test_mock_fred_get_series_returns_sample(mock_fred):
    """``mock_fred`` patches the ``Fred`` symbol *inside* fred_loader so
    a load through the loader returns the inline sample. Direct
    ``fredapi.Fred(...)`` calls bypass the patch and hit the live API,
    which is the intended boundary."""
    from macro_pipeline.loaders import fred_loader as fred_mod
    fake_fred = fred_mod.Fred(api_key="x")    # this is the patched factory
    s = fake_fred.get_series("ANYTHING")
    assert isinstance(s, pd.Series)
    assert len(s) == 5
    assert s.name == "ANYTHING"
    assert mock_fred.get_series.called


def test_mock_fred_alfred_returns_two_vintages(mock_fred):
    from macro_pipeline.loaders import fred_loader as fred_mod
    fake_fred = fred_mod.Fred(api_key="x")
    df = fake_fred.get_series_all_releases("PAYEMS")
    assert set(df.columns) == {"date", "realtime_start", "value"}
    assert len(df) == 2
    # Initial vs revised — Aug 2008 PAYEMS revised down from 137473 to 137423.
    assert sorted(df["value"].tolist()) == [137423.0, 137473.0]


def test_mock_yahoo_returns_sample_series(mock_yahoo):
    """``mock_yahoo`` patches _fetch_yahoo_one to return inline close data."""
    from macro_pipeline.loaders.yahoo_loader import _fetch_yahoo_one
    s = _fetch_yahoo_one("^GSPC")
    assert isinstance(s, pd.Series)
    assert len(s) == 5
    assert s.name == "^GSPC"


def test_mock_requests_intercepts_ebp_url(mock_requests, tmp_path, monkeypatch):
    """fetch_ebp_csv goes through the mocked requests.get and writes the
    tiny inline CSV without hitting the network."""
    from macro_pipeline.loaders import ebp as ebp_mod

    monkeypatch.setattr(ebp_mod, "EBP_LOCAL_PATH", tmp_path / "ebp.csv")
    path = ebp_mod.fetch_ebp_csv(force_refresh=True)
    assert path.exists()
    assert "ebp_csv" in mock_requests["url"]
    body = path.read_text()
    assert "ebp" in body and "2024-01-01" in body


def test_mock_requests_intercepts_gsw_url(mock_requests, tmp_path, monkeypatch):
    """fetch_gsw_csv goes through the mocked requests.get."""
    from macro_pipeline.loaders import ntfs as ntfs_mod

    monkeypatch.setattr(ntfs_mod, "GSW_LOCAL_PATH", tmp_path / "gsw.csv")
    path = ntfs_mod.fetch_gsw_csv(force_refresh=True)
    assert path.exists()
    assert "feds200628" in mock_requests["url"]


def test_live_api_flag_is_registered(pytestconfig):
    """The --live-api option is parsed by conftest.py."""
    assert pytestconfig.getoption("--live-api") is False  # default


def test_fixtures_dir_resolves_correctly(fixtures_dir):
    assert fixtures_dir.name == "fixtures"
    # Resolves underneath the tests/ directory itself.
    assert fixtures_dir.parent.name == "tests"


def test_write_fred_payems_fixture_creates_file(write_fred_payems_fixture):
    """The lazy fixture writes the JSON sample on first access."""
    assert write_fred_payems_fixture.exists()
    import json
    payload = json.loads(write_fred_payems_fixture.read_text())
    assert payload["indicator_id"] == "PAYEMS"
    assert payload["frequency"] == "M"
    assert len(payload["data"]) == 5


def test_write_yahoo_gspc_fixture_creates_file(write_yahoo_gspc_fixture):
    assert write_yahoo_gspc_fixture.exists()
    df = pd.read_csv(write_yahoo_gspc_fixture, index_col=0)
    assert "close" in df.columns
    assert len(df) == 5
