"""Tests for src.access PIT-safe / latest dispatch (Layer 1.5A.1)."""
from __future__ import annotations

import pandas as pd
import pytest

from src.access import (
    IndicatorBundle,
    LatestSeriesReader,
    PitDataContext,
    PitSeriesReader,
    load_series,
)
from src.loaders.fred_vintage_panel import panel_path
from src.preprocessing import to_visibility_index


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def test_load_series_no_asof_returns_latest():
    bundle = load_series("PAYEMS")
    assert isinstance(bundle, IndicatorBundle)
    assert bundle.pit_safe is False
    assert bundle.as_of is None
    assert bundle.indicator_id == "PAYEMS"
    assert bundle.data.notna().sum() > 0


def test_load_series_with_asof_returns_pit_safe_bundle():
    if not panel_path("PAYEMS").exists():
        pytest.skip("PAYEMS vintage panel not materialized")
    bundle = load_series("PAYEMS", as_of=pd.Timestamp("2008-09-12"))
    assert bundle.pit_safe is True
    assert bundle.as_of == pd.Timestamp("2008-09-12")


def test_load_series_pit_view_includes_aug_2008_after_publication():
    """Codex HIGH #1 acceptance: PAYEMS Aug 2008 (published Sep 5)
    is visible in the PIT view as of Sep 12 2008."""
    if not panel_path("PAYEMS").exists():
        pytest.skip("PAYEMS vintage panel not materialized")
    bundle = load_series("PAYEMS", as_of=pd.Timestamp("2008-09-12"))
    assert pd.Timestamp("2008-08-01") in bundle.data.index


def test_load_series_pit_view_excludes_sep_2008_before_publication():
    """PAYEMS Sep 2008 was published Oct 3 2008 — it MUST NOT appear in
    the PIT view as of Sep 12 2008."""
    if not panel_path("PAYEMS").exists():
        pytest.skip("PAYEMS vintage panel not materialized")
    bundle = load_series("PAYEMS", as_of=pd.Timestamp("2008-09-12"))
    assert pd.Timestamp("2008-09-01") not in bundle.data.index


# ---------------------------------------------------------------------------
# PitDataContext (backtest contract)
# ---------------------------------------------------------------------------
def test_pit_context_rejects_none_asof():
    with pytest.raises(ValueError):
        PitDataContext(as_of=None)


def test_pit_context_propagates_asof():
    if not panel_path("PAYEMS").exists():
        pytest.skip("PAYEMS vintage panel not materialized")
    ctx = PitDataContext(as_of=pd.Timestamp("2008-09-12"))
    bundle = ctx.load("PAYEMS")
    assert bundle.pit_safe is True
    assert bundle.as_of == pd.Timestamp("2008-09-12")


def test_pit_context_string_asof_is_normalized():
    ctx = PitDataContext(as_of="2024-01-15")
    assert ctx.as_of == pd.Timestamp("2024-01-15")


# ---------------------------------------------------------------------------
# Visibility shift on non-vintage series
# ---------------------------------------------------------------------------
def test_release_lag_shift_preserves_data_length():
    s = pd.Series([1.0, 2.0, 3.0],
                  index=pd.date_range("2024-01-01", periods=3, freq="ME"))
    shifted = to_visibility_index(s, release_lag_days=10)
    assert len(shifted) == 3
    # The first index entry was Jan 31 2024 (month-end) → shifted by 10 days.
    assert shifted.index[0] == pd.Timestamp("2024-02-10")


def test_release_lag_shift_zero_is_passthrough():
    s = pd.Series([1.0, 2.0], index=pd.date_range("2024-01-01", periods=2))
    out = to_visibility_index(s, release_lag_days=0)
    pd.testing.assert_series_equal(out, s)


def test_pit_view_truncates_at_asof_for_non_vintage():
    """T10Y2Y has release_lag_days=1 and no vintage panel; the PIT view
    must drop rows whose visibility_date > as_of."""
    bundle = load_series("T10Y2Y", as_of=pd.Timestamp("2024-06-30"))
    assert bundle.pit_safe is True
    # With lag=1 the latest visible obs_date as of 2024-06-30 is at most 2024-06-29.
    assert bundle.data.dropna().index.max() <= pd.Timestamp("2024-06-30")


# ---------------------------------------------------------------------------
# Latest reader
# ---------------------------------------------------------------------------
def test_latest_reader_pit_safe_false():
    bundle = LatestSeriesReader().load("PAYEMS")
    assert bundle.pit_safe is False
    assert bundle.as_of is None


def test_pit_reader_returns_pit_safe_bundle():
    if not panel_path("PAYEMS").exists():
        pytest.skip("PAYEMS vintage panel not materialized")
    bundle = PitSeriesReader().load(
        "PAYEMS", as_of=pd.Timestamp("2008-09-12"),
    )
    assert bundle.pit_safe is True
