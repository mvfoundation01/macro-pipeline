"""pytest fixtures (Layer 1.5D.2).

Provides ``mock_fred`` / ``mock_yahoo`` / ``mock_requests`` fixtures so
the suite can be run offline. The fixtures are opt-in (no autouse) — most
existing tests fall through their loader's cache-hit path when the
``data/cache/`` directory is populated, so they stay offline by
construction. New tests for loader internals can take any of these
fixtures and exercise the unhappy paths without needing a live network.

CLI flag
--------
``pytest --live-api ...`` is parsed here so future tests can branch on
``request.config.getoption("--live-api")`` to decide whether to skip the
mocks. The current implementation does not auto-disable mocks based on
this flag — opt-in fixtures are the contract.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# CLI option
# ---------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live-api",
        action="store_true",
        default=False,
        help="Allow live network calls (FRED / Yahoo / GSW / EBP). "
             "Default: rely on populated data/cache/ instead. Set this "
             "to bypass cache and exercise live endpoints (slow, "
             "non-hermetic).",
    )


# ---------------------------------------------------------------------------
# Fixture data accessors
# ---------------------------------------------------------------------------
@pytest.fixture
def fixtures_dir() -> Path:
    """Path to ``tests/fixtures/`` for tests that need on-disk samples."""
    return FIXTURE_DIR


def _sample_payems_series() -> pd.Series:
    """Inline tiny PAYEMS sample (5 monthly observations)."""
    idx = pd.date_range("2024-01-01", periods=5, freq="MS")
    return pd.Series(
        [157000.0, 157200.0, 157400.0, 157600.0, 157800.0],
        index=idx, name="PAYEMS",
    )


def _sample_alfred_payems() -> pd.DataFrame:
    """Inline tiny ALFRED-style vintage panel (1 obs date, 2 vintages)."""
    return pd.DataFrame(
        {
            "date": [pd.Timestamp("2008-08-01"), pd.Timestamp("2008-08-01")],
            "realtime_start": [pd.Timestamp("2008-09-05"),
                                pd.Timestamp("2009-01-15")],
            "value": [137473.0, 137423.0],   # initial / revised
        }
    )


def _sample_yahoo_close() -> pd.Series:
    """Inline tiny ^GSPC close sample."""
    idx = pd.date_range("2024-01-02", periods=5, freq="B")
    return pd.Series(
        [4742.83, 4704.81, 4688.68, 4697.24, 4783.45],
        index=idx, name="^GSPC",
    )


# ---------------------------------------------------------------------------
# Loader-level mocks
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_fred(monkeypatch: pytest.MonkeyPatch):
    """Patch ``fredapi.Fred`` so loader paths fall through deterministic
    sample data instead of hitting the live endpoint."""
    from macro_pipeline.loaders import fred_loader

    fake = MagicMock()
    fake.get_series.side_effect = (
        lambda series_id: _sample_payems_series().rename(series_id)
    )
    fake.get_series_all_releases.side_effect = (
        lambda series_id: _sample_alfred_payems()
    )
    monkeypatch.setattr(fred_loader, "Fred", lambda *a, **kw: fake)
    yield fake


@pytest.fixture
def mock_yahoo(monkeypatch: pytest.MonkeyPatch):
    """Patch ``yahoo_loader._fetch_yahoo_one`` to return a sample close
    series rather than calling yfinance."""
    from macro_pipeline.loaders import yahoo_loader

    def _fake_fetch(yahoo_ticker: str, *, auto_adjust: bool = True) -> pd.Series:
        s = _sample_yahoo_close()
        s.name = yahoo_ticker
        return s

    monkeypatch.setattr(yahoo_loader, "_fetch_yahoo_one", _fake_fetch)
    yield _fake_fetch


@pytest.fixture
def mock_requests(monkeypatch: pytest.MonkeyPatch):
    """Patch ``requests.get`` for EBP and GSW URL fetches with tiny CSVs."""
    from macro_pipeline.loaders import ebp as ebp_mod
    from macro_pipeline.loaders import ntfs as ntfs_mod

    ebp_csv = b"date,gz_spread,ebp,est_prob\n2024-01-01,1.0,0.5,0.1\n"
    gsw_csv = (
        b"Note: This is not an official Federal Reserve statistical release.\n"
        b"\n"
        b"Series,Compounding Convention,Mnemonic(s)\n"
        b"Zero-coupon yield,Continuously Compounded,SVENYXX\n"
        b"Par yield,Coupon-Equivalent,SVENPYXX\n"
        b"Instantaneous forward rate,Continuously Compounded,SVENFXX\n"
        b"One-year forward rate,Coupon-Equivalent,SVEN1FXX\n"
        b"Parameters,N/A,BETA0 to TAU2\n"
        b"\n"
        b"Date,BETA0,BETA1,BETA2,BETA3,TAU1,TAU2\n"
        b"2024-01-02,4.0,-0.5,0.2,0.0,1.5,5.0\n"
    )

    captured: dict[str, str] = {}

    def _fake_get(url, *args, **kwargs):
        captured["url"] = url
        resp = MagicMock(spec=__import__("requests").Response)
        if "ebp_csv" in url:
            resp.content = ebp_csv
        elif "feds200628" in url:
            resp.content = gsw_csv
        else:
            resp.content = b""
        resp.status_code = 200
        resp.raise_for_status = lambda: None
        return resp

    monkeypatch.setattr(ebp_mod.requests, "get", _fake_get)
    monkeypatch.setattr(ntfs_mod.requests, "get", _fake_get)
    yield captured


# ---------------------------------------------------------------------------
# A tiny on-disk fixtures store, written lazily so test runs that don't
# touch them don't even materialize the files.
# ---------------------------------------------------------------------------
def _ensure_fixtures_dir() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def write_fred_payems_fixture(tmp_path: Path) -> Path:
    _ensure_fixtures_dir()
    fp = FIXTURE_DIR / "fred_payems_sample.json"
    if not fp.exists():
        s = _sample_payems_series()
        fp.write_text(json.dumps({
            "indicator_id": "PAYEMS",
            "frequency": "M",
            "data": {ts.isoformat(): float(v) for ts, v in s.items()},
        }, indent=2))
    return fp


@pytest.fixture
def write_yahoo_gspc_fixture() -> Path:
    _ensure_fixtures_dir()
    fp = FIXTURE_DIR / "yahoo_gspc_sample.csv"
    if not fp.exists():
        _sample_yahoo_close().to_csv(fp, header=["close"])
    return fp
