"""Tests for src.loaders.fred_vintage_panel (Layer 1.5A.4).

These tests use the materialized panel cached under
``data/cache/vintage_panels/`` (created via the ``materialize_one`` /
``materialize_all_vintage_panels`` driver). They do not hit the FRED
network — the panel is loaded from disk.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.loaders.fred_vintage_panel import (
    VINTAGE_PANEL_DIR,
    VINTAGE_REQUIRED_SERIES,
    get_pit_series,
    get_pit_value,
    load_panel,
    panel_path,
)


def _has_panel(series_id: str) -> bool:
    return panel_path(series_id).exists()


@pytest.fixture(scope="module")
def payems_panel() -> pd.DataFrame:
    if not _has_panel("PAYEMS"):
        pytest.skip("PAYEMS vintage panel not materialized yet")
    return load_panel("PAYEMS")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
def test_panel_columns(payems_panel):
    assert list(payems_panel.columns) == [
        "obs_date", "value", "realtime_start", "realtime_end",
    ]


def test_panel_is_sorted(payems_panel):
    # Sorted by (obs_date, realtime_start) as required for determinism.
    sorted_ref = payems_panel.sort_values(
        ["obs_date", "realtime_start"], kind="mergesort"
    ).reset_index(drop=True)
    pd.testing.assert_frame_equal(payems_panel, sorted_ref)


def test_realtime_end_is_next_realtime_start_within_obs_date(payems_panel):
    """For each obs_date, all but the last vintage must have realtime_end
    set, and that value must equal the next vintage's realtime_start."""
    for obs_date, rows in payems_panel.groupby("obs_date"):
        if len(rows) <= 1:
            assert rows.iloc[0]["realtime_end"] is pd.NaT or pd.isna(
                rows.iloc[0]["realtime_end"]
            )
            continue
        starts = rows["realtime_start"].tolist()
        ends = rows["realtime_end"].tolist()
        # All but the last
        for i in range(len(rows) - 1):
            assert ends[i] == starts[i + 1]
        # The last must be NaT (current vintage)
        assert pd.isna(ends[-1])


# ---------------------------------------------------------------------------
# PIT lookups
# ---------------------------------------------------------------------------
def test_pit_lookup_returns_none_before_publication(payems_panel):
    """PAYEMS Aug 2008 was first published Sept 5 2008. Asking on Sept 4
    must return None (not yet visible)."""
    val = get_pit_value(
        payems_panel,
        observation_date=pd.Timestamp("2008-08-01"),
        asof_date=pd.Timestamp("2008-09-04"),
    )
    assert val is None


def test_pit_lookup_post_lehman_initial_estimate(payems_panel):
    """As of Sept 12 2008, the Aug 2008 initial estimate must be visible."""
    val = get_pit_value(
        payems_panel,
        observation_date=pd.Timestamp("2008-08-01"),
        asof_date=pd.Timestamp("2008-09-12"),
    )
    assert val is not None
    assert val > 130_000  # PAYEMS in thousands; 137M jobs in Aug 2008


def test_pit_uses_revised_value_after_revision(payems_panel):
    """Aug 2008 PAYEMS was revised in subsequent prints; PIT must
    reflect the *latest* revision visible on asof_date."""
    initial = get_pit_value(
        payems_panel, pd.Timestamp("2008-08-01"), pd.Timestamp("2008-09-12"),
    )
    revised = get_pit_value(
        payems_panel, pd.Timestamp("2008-08-01"), pd.Timestamp("2009-01-15"),
    )
    assert initial is not None and revised is not None
    assert initial != revised


def test_get_pit_series_excludes_unpublished_observations(payems_panel):
    """As of 2008-09-04, August 2008 must NOT appear in the series."""
    s = get_pit_series(payems_panel, asof_date=pd.Timestamp("2008-09-04"))
    assert pd.Timestamp("2008-08-01") not in s.index


def test_get_pit_series_includes_published_observations(payems_panel):
    """As of 2008-09-12, August 2008 IS in the series."""
    s = get_pit_series(payems_panel, asof_date=pd.Timestamp("2008-09-12"))
    assert pd.Timestamp("2008-08-01") in s.index


# ---------------------------------------------------------------------------
# Materialization
# ---------------------------------------------------------------------------
def test_all_required_series_have_panels():
    """Every entry in VINTAGE_REQUIRED_SERIES must have a parquet file
    under data/cache/vintage_panels/. (Spec gate for Sub-phase 1.5A.)"""
    missing = [sid for sid in VINTAGE_REQUIRED_SERIES if not _has_panel(sid)]
    if missing:
        pytest.skip(
            f"Vintage panels not yet materialized: {missing}. "
            f"Run materialize_all_vintage_panels() first."
        )
    assert sorted(p.stem.replace("_vintage", "")
                  for p in VINTAGE_PANEL_DIR.glob("*_vintage.parquet")) \
           == sorted(VINTAGE_REQUIRED_SERIES)
