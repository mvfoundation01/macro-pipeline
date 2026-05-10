"""Tests for ``macro_pipeline.regime.nber_extract`` (Layer 3A)."""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.regime import (
    NBER_FALLBACK_INDICATOR,
    NBER_PRIMARY_INDICATOR,
    extract_nber_state,
    last_known_label_date,
)
from macro_pipeline.regime.exceptions import PitDataUnavailableError

# --- Latest-knowledge sanity (post-hoc inspection mode) -------------------

@pytest.mark.parametrize(
    "query_date",
    ["1973-12-01", "2008-09-01", "2020-04-01"],
)
def test_nber_known_recession_latest_mode(query_date: str) -> None:
    """Cached NBER labels confirm the canonical recession dates."""
    r = extract_nber_state(query_date)
    assert r.state == "recession"
    assert r.source == NBER_PRIMARY_INDICATOR
    assert r.as_of is None  # latest mode


@pytest.mark.parametrize(
    "query_date",
    ["1995-06-01", "2017-06-01", "2025-06-01"],
)
def test_nber_known_expansion_latest_mode(query_date: str) -> None:
    r = extract_nber_state(query_date)
    assert r.state == "expansion"


# --- PIT discipline -------------------------------------------------------

def test_nber_pit_returns_pre_announcement_state_at_2008_11_30() -> None:
    """Layer 3.5C semantic update (D22): the original test asserted
    that a PIT query of 2008-09 at as_of=2008-12-01 raises (because
    the 180-day visibility shift filtered 2008-09 obs out). After
    3.5C the calendar shows the 2007-12 peak was announced 2008-12-01,
    so at as_of=2008-12-01 the lookup resolves to "recession" cleanly.

    The new contract: at as_of=2008-11-30 (one day BEFORE the peak
    announcement) querying 2008-09 returns "expansion" (the most
    recent visible turning point was the 2001-11 trough). This
    exercises the same look-ahead-bias defense as before but uses the
    calendar-aware mechanism.

    See LAYER_3_5_DEVIATIONS.md D22.
    """
    ctx = PitDataContext(as_of=pd.Timestamp("2008-11-30"))
    r = extract_nber_state(pd.Timestamp("2008-09-01"), ctx=ctx)
    assert r.state == "expansion"
    assert r.source == "calendar"
    # Latest mode would have returned "recession" — divergence is the
    # discriminating evidence of PIT discipline.
    latest = extract_nber_state(pd.Timestamp("2008-09-01"))
    assert latest.state == "recession"


def test_last_known_label_date_pit_mode() -> None:
    """PIT view at 2008-12-01 reports the most recent announced
    turning point: the 2007-12 peak (announced 2008-12-01)."""
    ctx = PitDataContext(as_of=pd.Timestamp("2008-12-01"))
    boundary = last_known_label_date(ctx=ctx)
    # Most recent firm-determined turning point at as_of=2008-12-01
    # is the 2007-12 peak (announced same day).
    assert boundary <= pd.Timestamp("2008-06-30")
    assert boundary >= pd.Timestamp("2007-12-01")


def test_last_known_label_date_latest_is_modern() -> None:
    """Latest-knowledge view should reach roughly today."""
    boundary = last_known_label_date()
    assert boundary >= pd.Timestamp("2024-01-01")


def test_nber_pit_safe_query_within_visible_window() -> None:
    """Asking about a date far enough in the past should succeed in PIT mode."""
    ctx = PitDataContext(as_of=pd.Timestamp("2010-06-01"))
    r = extract_nber_state(pd.Timestamp("2008-09-01"), ctx=ctx)
    assert r.state == "recession"
    assert r.as_of == pd.Timestamp("2010-06-01")
    assert r.last_known_label_date <= pd.Timestamp("2010-06-01")


def test_nber_query_before_earliest_label_raises() -> None:
    """A pre-1959 query has no label visible at any as_of."""
    with pytest.raises(PitDataUnavailableError):
        extract_nber_state(pd.Timestamp("1850-01-01"))


def test_nber_fallback_to_usrec() -> None:
    """USREC source is selectable (coarser PIT, but accessible)."""
    r = extract_nber_state(
        pd.Timestamp("2008-09-01"),
        indicator_id=NBER_FALLBACK_INDICATOR,
    )
    assert r.source == NBER_FALLBACK_INDICATOR
    assert r.state == "recession"
