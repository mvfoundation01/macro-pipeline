"""FRED loader smoke + Gate 1 tests.

Hits the FRED API once (or uses cache when fresh). Skips entirely if no
FRED_API_KEY is set or the live fetch fails.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest
from dotenv import load_dotenv

# Load project .env so FRED_API_KEY is visible regardless of pytest cwd.
load_dotenv()

if not os.environ.get("FRED_API_KEY"):
    # config.py raises at import time without the key; skip the whole module.
    pytest.skip("FRED_API_KEY not set", allow_module_level=True)

from src.config import FRED_SERIES_API
from src.loaders.fred_loader import load_fred_all, load_fred_series
from src.preprocessing import (
    UnitError,
    align_to_business_days,
    flag_outliers_iqr,
    validate_ingest,
)
from src.validation import validate_gate1_fred


# ---------------------------------------------------------------------------
# Universal preprocessing primitives
# ---------------------------------------------------------------------------
def test_validate_ingest_rejects_empty():
    from src.preprocessing import IngestionError
    with pytest.raises(IngestionError):
        validate_ingest(pd.Series(dtype=float), "TEST")


def test_validate_ingest_rejects_all_nan():
    from src.preprocessing import IngestionError
    s = pd.Series([float("nan")] * 5,
                  index=pd.date_range("2020-01-01", periods=5, freq="D"))
    with pytest.raises(IngestionError):
        validate_ingest(s, "TEST")


def test_flag_outliers_iqr5_marks_extremes():
    s = pd.Series(
        [1.0, 1.1, 0.9, 1.05, 1.0, 0.95, 100.0],
        index=pd.date_range("2020-01-01", periods=7, freq="D"),
    )
    flags = flag_outliers_iqr(s, k=5.0)
    assert flags.iloc[-1], "should flag 100.0 as outlier"
    assert not flags.iloc[:-1].any(), "core values should not be flagged"


def test_align_to_business_days_forward_fills_only():
    s = pd.Series(
        [1.0, 2.0, 3.0],
        index=pd.to_datetime(["2024-01-02", "2024-01-09", "2024-01-16"]),
    )
    aligned = align_to_business_days(s, native_freq="W")
    # ffill: between 2024-01-02 and 2024-01-09, value should remain 1.0
    assert aligned.loc["2024-01-05"] == 1.0
    # No backfill: before 2024-01-02 should remain NaN
    pre = aligned.loc[: "2024-01-01"]
    assert pre.isna().all()


# ---------------------------------------------------------------------------
# FRED loader (live or cached)
# ---------------------------------------------------------------------------
def test_load_single_series_t10y2y():
    s, meta = load_fred_series("T10Y2Y")
    assert isinstance(s, pd.Series)
    assert isinstance(s.index, pd.DatetimeIndex)
    assert s.index.tz is None, "index must be tz-naive"
    assert not s.dropna().empty
    assert meta.indicator_id == "T10Y2Y"
    assert meta.unit == "pct"
    assert meta.source in {"FRED_API", "FRED_ALFRED"}


def test_load_all_returns_full_panel():
    df, meta = load_fred_all()
    assert df.shape[1] == len(FRED_SERIES_API), "all configured series present"
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    assert df.index.is_unique
    # Master index runs through today (within 1 business day)
    today = pd.Timestamp.today().normalize()
    assert (today - df.index.max()).days <= 3
    # No fully-empty columns
    n_obs = df.notna().sum()
    assert (n_obs > 0).all(), f"empty columns: {list(n_obs[n_obs == 0].index)}"


def test_gate1_passes():
    df, meta = load_fred_all()
    report = validate_gate1_fred(df, meta)
    assert report.passed, "Gate 1 must pass:\n" + report.render()


# ---------------------------------------------------------------------------
# Per-series unit sanity (after universal pipeline)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("series_id", list(FRED_SERIES_API.keys()))
def test_each_series_within_unit_range(series_id):
    s, meta = load_fred_series(series_id)
    obs = s.dropna()
    if obs.empty:
        pytest.fail(f"{series_id}: no observations")
    from src.config import UNIT_EXPECTED_RANGES
    lo, hi = UNIT_EXPECTED_RANGES[meta.unit]
    assert lo <= obs.min() <= obs.max() <= hi, (
        f"{series_id} range [{obs.min()}, {obs.max()}] "
        f"outside unit '{meta.unit}' range [{lo}, {hi}]"
    )


# ---------------------------------------------------------------------------
# ALFRED vintage path (one spot check on PAYEMS)
# ---------------------------------------------------------------------------
def test_indpro_master_index_extends_to_1919():
    """INDPRO source data starts 1919-01; pipeline must NOT truncate to 1959.

    Regression test for the master-index bug fixed in Phase 4B post-mortem:
    align_to_business_days used to start at MASTER_INDEX_START (1959-01-01)
    unconditionally, silently dropping ~40 years of INDPRO history.
    """
    s, _ = load_fred_series("INDPRO")
    obs = s.dropna()
    assert obs.index.min() <= pd.Timestamp("1919-12-31"), (
        f"INDPRO first_obs={obs.index.min().date()} did not extend back to 1919"
    )
    # Sanity: should have ~25k+ business days of history (1919 -> today).
    assert obs.shape[0] > 20000


def test_payems_vintage_pre_lehman():
    # PAYEMS as known on 2008-09-12 (Friday before Lehman) should NOT include
    # the post-Lehman shock observations.
    s, meta = load_fred_series("PAYEMS", vintage_date="2008-09-12")
    assert meta.source == "FRED_ALFRED"
    assert meta.extra["vintage_date"] == "2008-09-12"
    assert s.index.max() <= pd.Timestamp("2008-09-12")
    # The August 2008 print should be there (released early September 2008).
    assert s.dropna().shape[0] > 600, "expected long historical PAYEMS series"
