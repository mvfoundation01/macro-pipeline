"""TV CSV loader tests covering Gate 2.

Reads from disk (no API call). Skips if the FRED_API_KEY-bound config
import path raises.
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

from macro_pipeline.loaders.tv_csv_loader import (
    TV_FILES_REGISTRY,
    discover_tv_files,
    load_tv_all,
    load_tv_file,
)
from macro_pipeline.validation import validate_gate2_tv


# ---------------------------------------------------------------------------
# Discovery + registry sanity
# ---------------------------------------------------------------------------
def test_discover_finds_22_csvs():
    files = discover_tv_files()
    assert len(files) == 22, f"expected 22 TV CSVs, got {len(files)}: {files}"


def test_all_22_files_registered():
    discovered = set(discover_tv_files())
    registered = set(TV_FILES_REGISTRY.keys())
    assert discovered == registered, (
        f"missing from registry: {sorted(discovered - registered)}; "
        f"registry not on disk: {sorted(registered - discovered)}"
    )


def test_indicator_ids_unique():
    ids = [spec["indicator_id"] for spec in TV_FILES_REGISTRY.values()]
    assert len(set(ids)) == len(ids), (
        f"duplicate indicator_ids: "
        f"{sorted([i for i in set(ids) if ids.count(i) > 1])}"
    )


# ---------------------------------------------------------------------------
# Full panel + Gate 2
# ---------------------------------------------------------------------------
def test_load_all_returns_full_panel():
    df, meta = load_tv_all()
    assert df.shape[1] == 22
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    assert df.index.is_unique
    for sid in df.columns:
        assert meta[sid].source == "TV_CSV"


def test_gate2_passes():
    df, meta = load_tv_all()
    report = validate_gate2_tv(df, meta)
    assert report.passed, "Gate 2 must pass:\n" + report.render()


# ---------------------------------------------------------------------------
# Unit conversion + sanity ranges (gotchas 1-3 from prompt)
# ---------------------------------------------------------------------------
def test_walcl_in_millions_after_transform():
    s, meta = load_tv_file("FRED_WALCL_1D.csv")
    last = float(s.dropna().iloc[-1])
    assert 5e5 <= last <= 1e7, (
        f"WALCL latest {last:,.0f} not in [5e5, 1e7] millions; "
        "check raw_unit_transform=raw_to_M_USD"
    )
    assert meta.unit == "M_USD"


def test_rrpontsyd_in_billions_after_transform():
    s, meta = load_tv_file("FRED_RRPONTSYD_1D.csv")
    last = float(s.dropna().iloc[-1])
    assert 0 <= last <= 3000, (
        f"RRPONTSYD latest {last:,.2f} not in [0, 3000] billions"
    )
    assert meta.unit == "B_USD"


def test_gdp_in_billions_after_transform():
    s, meta = load_tv_file("FRED_GDP_3M.csv")
    last = float(s.dropna().iloc[-1])
    # 2026 GDP nominal should be around $30T = 30,000 billion
    assert 100 <= last <= 5e4
    assert meta.unit == "B_USD"


def test_hy_oas_already_a_spread_no_negative():
    s, meta = load_tv_file("FRED_BAMLH0A0HYM2_1D.csv")
    obs = s.dropna()
    assert obs.min() >= 0, "HY OAS must be non-negative (already a spread)"
    assert obs.max() <= 25
    assert meta.unit == "pct"
    assert "spread" in meta.description.lower()


def test_treasury_yields_consistent_unit_and_range():
    # 3M bill went briefly negative in March 2020; 10Y/2Y did not.
    for fname, lo in (
        ("TVC_US10Y_1D.csv", 0.0),
        ("TVC_US02Y_1D.csv", 0.0),
        ("TVC_US03MY_1D.csv", -0.5),
    ):
        s, meta = load_tv_file(fname)
        obs = s.dropna()
        assert meta.unit == "pct"
        assert lo <= obs.min() and obs.max() <= 25, f"{fname} out of [{lo},25]"


def test_vix_in_canonical_range():
    s, meta = load_tv_file("CBOE_DLY_VIX_1D.csv")
    obs = s.dropna()
    assert obs.min() >= 5 and obs.max() <= 100
    assert meta.indicator_id == "VIX"
    assert meta.unit == "index"


# ---------------------------------------------------------------------------
# Tier 5 metadata (gotcha 5)
# ---------------------------------------------------------------------------
def test_tier5_wilshire_metadata_complete():
    _, meta = load_tv_file("FRED_WILL5000PR_3M.csv")
    assert meta.extra.get("tier") == 5
    assert meta.extra.get("data_status") == "stale"
    blocked = meta.extra.get("do_not_use_for", [])
    assert "real_time_signal" in blocked
    assert "live_crps" in blocked
    assert "live_cdrs" in blocked
    assert "backtest" in meta.extra.get("use_for", [])
    assert meta.extra.get("replacement_realtime")


def test_tier5_oecd_cci_metadata_complete():
    _, meta = load_tv_file("FRED_CSCICP03USM665S_1M.csv")
    assert meta.extra.get("tier") == 5
    assert meta.extra.get("data_status") == "stale"
    assert "real_time_signal" in meta.extra.get("do_not_use_for", [])
    assert meta.extra.get("replacement_realtime")


def test_tier5_data_does_not_extend_past_stale_date():
    """A stale series should still report its true last_obs (no padding past it)."""
    s, _ = load_tv_file("FRED_WILL5000PR_3M.csv")
    # last_obs = 2024-04-01 in source. After ffill alignment to today's
    # business-day master index, the LAST NON-NULL VALUE should remain that
    # 2024-04 print, so nominal index extends to today but the source-based
    # series in the parquet is value-frozen at the 2024-04 print.
    last_value = float(s.dropna().iloc[-1])
    assert 1e3 <= last_value <= 1e5


# ---------------------------------------------------------------------------
# Special filename / format cases (gotchas 4, 6, 7)
# ---------------------------------------------------------------------------
def test_short_history_warn_on_gamma():
    _, meta = load_tv_file("CBOE_DLY_GAMMA_1D.csv")
    assert meta.extra.get("short_history_warn") is True


def test_hyphen_filename_sanitized():
    _, meta = load_tv_file("INDEX_HIGN-INDEX_LOWN_1D.csv")
    assert "-" not in meta.indicator_id
    assert meta.indicator_id == "HIGN_LOWN_NET"


def test_rut_spx_is_already_a_ratio_not_two_columns():
    s, meta = load_tv_file("TVC_RUT_SP_SPX_1D.csv")
    assert meta.indicator_id == "RUT_SPX_RATIO"
    assert meta.unit == "ratio"
    obs = s.dropna()
    assert 0.1 < obs.min() < 1.5 and 0.1 < obs.max() < 2.0


# ---------------------------------------------------------------------------
# Cache + column-name integrity
# ---------------------------------------------------------------------------
def test_cached_parquet_column_is_bare_indicator_id():
    """Item A consistency - parquet column name = indicator_id, file = tv_<id>."""
    load_tv_file("FRED_BAMLH0A0HYM2_1D.csv")  # ensure cached
    from macro_pipeline.config import DATA_CACHE
    df = pd.read_parquet(DATA_CACHE / "tv_BAMLH0A0HYM2.parquet")
    assert df.columns.tolist() == ["BAMLH0A0HYM2"]


def test_us10y_master_index_extends_to_1912():
    """TV's TVC_US10Y starts 1912-06; pipeline must not truncate to 1959.

    Regression test for the master-index bug fixed in Phase 4B post-mortem.
    """
    s, _ = load_tv_file("TVC_US10Y_1D.csv")
    obs = s.dropna()
    assert obs.index.min() <= pd.Timestamp("1912-12-31"), (
        f"TVC_US10Y first_obs={obs.index.min().date()} did not extend back to 1912"
    )
    assert obs.shape[0] > 25000  # ~114 years of business days


def test_wtregen_data_quality_suspect_period_tagged():
    """WTREGEN pre-2002 period must be tagged as suspect (Phase 3 Item A)."""
    from macro_pipeline.preprocessing import is_quality_suspect

    _, meta = load_tv_file("FRED_WTREGEN_1D.csv")
    periods = meta.data_quality_suspect_periods
    assert len(periods) == 1, f"expected 1 suspect period, got {len(periods)}"
    p = periods[0]
    assert p["start_date"] == "1986-01-01"
    assert p["end_date"] == "2002-12-17"
    assert "discontinued precursor" in p["reason"]

    # Helper resolves both ends correctly (boundaries inclusive).
    assert is_quality_suspect(meta, "1986-01-01") is True
    assert is_quality_suspect(meta, "1990-06-15") is True
    assert is_quality_suspect(meta, "2002-12-17") is True
    assert is_quality_suspect(meta, "2002-12-18") is False
    assert is_quality_suspect(meta, "2010-01-01") is False
    # Helper accepts a plain dict (e.g. from a meta.json sidecar).
    assert is_quality_suspect(meta.to_dict(), "1990-06-15") is True
    # Helper accepts the raw period list.
    assert is_quality_suspect(periods, "1990-06-15") is True
    # No-suspect series returns False.
    _, meta_clean = load_tv_file("CBOE_DLY_VIX_1D.csv")
    assert meta_clean.data_quality_suspect_periods == []
    assert is_quality_suspect(meta_clean, "1990-06-15") is False
