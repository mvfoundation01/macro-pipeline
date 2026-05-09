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

def test_nber_pit_raises_when_label_unannounced() -> None:
    """At as_of=2008-12-01, NBER had not yet announced the 2007-12 peak.

    Our visibility-shifted view (release_lag_days=180 on NBER_REC_LABEL)
    has labels only up to ~2008-06-04, so any query past that date
    must raise PitDataUnavailableError.
    """
    ctx = PitDataContext(as_of=pd.Timestamp("2008-12-01"))
    with pytest.raises(PitDataUnavailableError) as exc_info:
        extract_nber_state(pd.Timestamp("2008-09-01"), ctx=ctx)
    msg = str(exc_info.value).lower()
    assert "last_known_label_date" in msg
    assert "2008" in msg


def test_last_known_label_date_pit_mode() -> None:
    """PIT view at 2008-12-01 has labels strictly before the 6-month buffer."""
    ctx = PitDataContext(as_of=pd.Timestamp("2008-12-01"))
    boundary = last_known_label_date(ctx=ctx)
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
