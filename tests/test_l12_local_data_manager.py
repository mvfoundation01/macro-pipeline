"""L12 D10 — Tests for ``macro_pipeline.webapp.local_data_manager``.

Counts: 6 tests (3 NEG / 3 POS) = 50% NEG.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from macro_pipeline.webapp.local_data_manager import (
    FILENAME_PATTERNS,
    KNOWN_SUBSERIES,
    LocalDataManager,
    classify_filename,
)


def _write_csv(path: Path, rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)


def _seed_v_files(root: Path) -> None:
    """Drop small CSVs that mimic V's actual filenames + TradingView format."""
    (root).mkdir(parents=True, exist_ok=True)
    _write_csv(root / "TVC_US02Y_1D.csv", [
        ["time", "close"],
        ["2026-01-01", "4.20"], ["2026-02-01", "4.10"], ["2026-03-01", "3.95"],
    ])
    _write_csv(root / "TVC_US10Y_1D.csv", [
        ["time", "close"],
        ["2026-01-01", "4.40"], ["2026-02-01", "4.35"], ["2026-03-01", "4.42"],
    ])
    _write_csv(root / "FRED_BAMLC0A0CM_1D.csv", [
        ["time", "close"],
        ["2026-01-01", "0.85"], ["2026-02-01", "0.82"], ["2026-03-01", "0.80"],
    ])
    _write_csv(root / "FRED_UMCSENT_1M.csv", [
        ["time", "close"],
        ["2026-01-01", "65.0"], ["2026-02-01", "66.0"], ["2026-03-01", "53.3"],
    ])


# ----------------------------------------------------------------------
# POS (3 tests)
# ----------------------------------------------------------------------
def test_filename_patterns_classify_v_actual_filenames() -> None:
    """All 22 of V's TradingView CSVs in `data/raw/tradingview/` must classify
    to a (category, subseries) pair under the registered patterns."""
    expected = {
        "CBOE_DLY_GAMMA_1D.csv": ("sentiment", "dealer_gamma"),
        "CBOE_DLY_VIX_1D.csv": ("sentiment", "vix"),
        "FRED_BAMLC0A0CM_1D.csv": ("credit_spreads", "ig_oas"),
        "FRED_BAMLH0A0HYM2_1D.csv": ("credit_spreads", "hy_oas"),
        "FRED_BAMLH0A1HYBB_1D.csv": ("credit_spreads", "bb_oas"),
        "FRED_BAMLH0A3HYC_1D.csv": ("credit_spreads", "ccc_oas"),
        "FRED_UMCSENT_1M.csv": ("sentiment", "umich"),
        "FRED_CSCICP03USM665S_1M.csv": ("sentiment", "consumer_confidence"),
        "TVC_US02Y_1D.csv": ("yield_curve", "2y"),
        "TVC_US10Y_1D.csv": ("yield_curve", "10y"),
        "TVC_US03MY_1D.csv": ("yield_curve", "3m"),
        "INDEX_S5FI_1D.csv": ("sentiment", "spx_above_50dma"),
        "INDEX_S5TH_1D.csv": ("sentiment", "spx_above_200dma"),
        "USI_PCCE_1D.csv": ("sentiment", "put_call_equity"),
    }
    for name, want in expected.items():
        got = classify_filename(name)
        assert got == want, f"{name}: expected {want}, got {got}"


def test_scan_categorizes_seeded_files(tmp_path: Path) -> None:
    _seed_v_files(tmp_path)
    mgr = LocalDataManager(search_paths=(tmp_path,))
    detected = mgr.scan()
    assert len(detected["yield_curve"]) == 2
    assert len(detected["credit_spreads"]) == 1
    assert len(detected["sentiment"]) == 1
    assert len(detected["unclassified"]) == 0
    # subseries names line up with downstream consumers.
    yc_subs = {f.subseries for f in detected["yield_curve"]}
    assert yc_subs == {"2y", "10y"}


def test_build_uploaded_data_produces_l10_shape(tmp_path: Path) -> None:
    _seed_v_files(tmp_path)
    mgr = LocalDataManager(search_paths=(tmp_path,))
    uploaded = mgr.build_uploaded_data()
    # yield_curve dict matches ExcelDataIngester.parse_yield_curve output keys.
    yc = uploaded["yield_curve"]
    assert set(yc.keys()) >= {"rows", "latest", "inverted", "source", "files"}
    assert yc["source"] == "local_files"
    assert yc["latest"]["2y"] == pytest.approx(3.95)
    assert yc["latest"]["10y"] == pytest.approx(4.42)
    assert yc["inverted"] is False  # 3.95 < 4.42
    # credit_spreads dict has L10 fields + bps conversion (0.80% → 80 bps).
    cs = uploaded["credit_spreads"]
    assert cs["latest"]["ig_oas"] == pytest.approx(80.0)
    assert cs["elevated"] is False
    # sentiment dict in long format.
    se = uploaded["sentiment"]
    assert "by_indicator" in se
    assert se["by_indicator"]["umich"] == pytest.approx(53.3)


# ----------------------------------------------------------------------
# NEG (3 tests)
# ----------------------------------------------------------------------
def test_aggregate_yield_curve_returns_none_when_10y_missing(
    tmp_path: Path,
) -> None:
    """Yield curve needs BOTH 2y and 10y; with only 2y present, must return
    None so caller falls back to manual upload."""
    (tmp_path).mkdir(parents=True, exist_ok=True)
    _write_csv(tmp_path / "TVC_US02Y_1D.csv", [
        ["time", "close"], ["2026-01-01", "4.0"],
    ])
    mgr = LocalDataManager(search_paths=(tmp_path,))
    uploaded = mgr.build_uploaded_data()
    assert "yield_curve" not in uploaded


def test_scan_silently_skips_missing_directories(tmp_path: Path) -> None:
    """A missing search_path must not raise — common on fresh checkout."""
    mgr = LocalDataManager(search_paths=(tmp_path / "does_not_exist",))
    detected = mgr.scan()
    assert detected == {
        "yield_curve": [], "credit_spreads": [], "sentiment": [], "unclassified": [],
    }


def test_unknown_filenames_land_in_unclassified_bucket(tmp_path: Path) -> None:
    p = tmp_path / "ACMTermPremium.xls"
    p.write_bytes(b"not a real xls")
    # Also a CSV with an unrecognized name.
    _write_csv(tmp_path / "totally_random_name.csv", [
        ["time", "close"], ["2026-01-01", "1.0"],
    ])
    mgr = LocalDataManager(search_paths=(tmp_path,))
    detected = mgr.scan()
    # The .xls is filtered (not in SUPPORTED_EXTENSIONS).
    # The randomly-named CSV lands in unclassified.
    names = [f.path.name for f in detected["unclassified"]]
    assert "totally_random_name.csv" in names
    # KNOWN_SUBSERIES sanity check (covers FILENAME_PATTERNS introspection).
    assert "2y" in KNOWN_SUBSERIES
    assert "ig_oas" in KNOWN_SUBSERIES
    assert len(FILENAME_PATTERNS) >= 20  # at least V's known files
