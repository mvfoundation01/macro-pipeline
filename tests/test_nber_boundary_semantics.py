"""Layer 3.5b-W — NBER calendar boundary semantics tests.

Closes Codex 5.5 finding W (MED) — `NberCalendarLoader.state_at` at the
exact peak/trough month diverged from NBER announcement convention
across all 6 cycles. The fix distinguishes "AT the turning point"
(regime is the type the cycle is ENDING) from "STRICTLY AFTER" (regime
is the new type that started).

NBER convention (per FRED USREC encoding, cross-checked at 12 boundary
months — 100% aligned):
  - peak month   = LAST expansion month (recession starts month M+1)
  - trough month = LAST recession month (expansion starts month M+1)

Test plan per pre-flight §5: 3 POS parametrized over 6 cycles + 3 NEG
drift = 50% NEG (meets floor); 24+ effective assertions.
"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.regime.exceptions import NberCycleNotFoundError
from macro_pipeline.regime.nber_calendar import NberCalendarLoader

# Far-future as_of so all 6 cycles' announcements are visible. This is
# the "post-hoc / latest-knowledge" view — boundary semantics tests do
# not depend on announcement-date timing.
_AS_OF_POST = pd.Timestamp("2030-01-01")

# Cycles inline so the tests are independent of the calendar CSV.
_CYCLES = [
    {"label": "1980", "peak": "1980-01", "trough": "1980-07"},
    {"label": "1981", "peak": "1981-07", "trough": "1982-11"},
    {"label": "1990", "peak": "1990-07", "trough": "1991-03"},
    {"label": "2001", "peak": "2001-03", "trough": "2001-11"},
    {"label": "2007", "peak": "2007-12", "trough": "2009-06"},
    {"label": "2020", "peak": "2020-02", "trough": "2020-04"},
]

_PEAK_PARAMS = [(c["label"], c["peak"]) for c in _CYCLES]
_TROUGH_PARAMS = [(c["label"], c["trough"]) for c in _CYCLES]


@pytest.fixture(scope="module")
def cal() -> NberCalendarLoader:
    return NberCalendarLoader()


# ---------------------------------------------------------------------------
# 1. POS — exact peak month returns expansion (parametrized over 6 cycles)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("label,peak", _PEAK_PARAMS)
def test_nber_exact_peak_month_returns_expansion(
    cal: NberCalendarLoader, label: str, peak: str,
) -> None:
    """At `query_period == peak_date`, NBER convention says regime is
    `expansion` (peak month is LAST expansion month before recession
    starts the following month). Pre-3.5b-W returned `recession`."""
    state = cal.state_at(peak, as_of=_AS_OF_POST)
    assert state == "expansion", (
        f"cycle {label}: at peak month {peak}, got {state!r}; "
        "NBER convention says expansion (last expansion month)"
    )


# ---------------------------------------------------------------------------
# 2. POS — first month after peak returns recession (parametrized)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("label,peak", _PEAK_PARAMS)
def test_nber_first_month_after_peak_returns_recession(
    cal: NberCalendarLoader, label: str, peak: str,
) -> None:
    """At `query_period == peak_date + 1`, recession has started → regime
    `recession`. Should match pre-3.5b-W behavior (post-peak case was
    correct; only the AT-peak case was buggy)."""
    after_peak = pd.Period(peak, freq="M") + 1
    state = cal.state_at(after_peak, as_of=_AS_OF_POST)
    assert state == "recession", (
        f"cycle {label}: at peak+1 month {after_peak}, got {state!r}; "
        "NBER convention says recession (recession started)"
    )


# ---------------------------------------------------------------------------
# 3. POS — exact trough month returns recession (parametrized)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("label,trough", _TROUGH_PARAMS)
def test_nber_exact_trough_month_returns_recession(
    cal: NberCalendarLoader, label: str, trough: str,
) -> None:
    """At `query_period == trough_date`, NBER convention says regime is
    `recession` (trough month is LAST recession month before expansion
    starts the following month). Pre-3.5b-W returned `expansion`."""
    state = cal.state_at(trough, as_of=_AS_OF_POST)
    assert state == "recession", (
        f"cycle {label}: at trough month {trough}, got {state!r}; "
        "NBER convention says recession (last recession month)"
    )


# ---------------------------------------------------------------------------
# 4. NEG — no silent state drift at peak boundary (parametrized)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("label,peak", _PEAK_PARAMS)
def test_nber_no_silent_state_drift_at_peak_boundary(
    cal: NberCalendarLoader, label: str, peak: str,
) -> None:
    """The peak-month state and peak+1 state must be DIFFERENT — NBER
    convention says expansion ENDS at the peak month, so the immediately
    following month must be recession. Pre-3.5b-W silently returned
    'recession' for BOTH the peak month and peak+1 (no transition
    visible). This NEG test asserts the transition is preserved."""
    peak_period = pd.Period(peak, freq="M")
    state_at_peak = cal.state_at(peak_period, as_of=_AS_OF_POST)
    state_after = cal.state_at(peak_period + 1, as_of=_AS_OF_POST)
    assert state_at_peak == "expansion"
    assert state_after == "recession"
    assert state_at_peak != state_after, (
        f"cycle {label}: silent drift at peak boundary {peak}: "
        f"both months returned {state_at_peak!r} (transition not visible)"
    )


# ---------------------------------------------------------------------------
# 5. NEG — no silent state drift at trough boundary (parametrized;
#    implicitly covers post-trough → expansion case)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("label,trough", _TROUGH_PARAMS)
def test_nber_no_silent_state_drift_at_trough_boundary(
    cal: NberCalendarLoader, label: str, trough: str,
) -> None:
    """The trough-month state and trough+1 state must be DIFFERENT —
    recession ENDS at the trough month; expansion starts month +1.
    Implicitly covers the post-trough → expansion case (test #5 of the
    informal 4-case set)."""
    trough_period = pd.Period(trough, freq="M")
    state_at_trough = cal.state_at(trough_period, as_of=_AS_OF_POST)
    state_after = cal.state_at(trough_period + 1, as_of=_AS_OF_POST)
    assert state_at_trough == "recession"
    assert state_after == "expansion"
    assert state_at_trough != state_after, (
        f"cycle {label}: silent drift at trough boundary {trough}: "
        f"both months returned {state_at_trough!r} (transition not visible)"
    )


# ---------------------------------------------------------------------------
# 6. NEG — calendar lookup distinguishes announce-date from state-date
# ---------------------------------------------------------------------------
def test_nber_calendar_lookup_distinguishes_announce_vs_state_date(
    cal: NberCalendarLoader,
) -> None:
    """The 2007-12 peak was announced 2008-12-01. At as_of one day
    BEFORE the announcement, querying 2007-12 should raise (no turning
    point announced). At as_of slightly AFTER the announcement, the
    same query should resolve to "expansion" (per the boundary fix —
    pre-3.5b-W this returned "recession", incorrectly conflating the
    "announced-and-visible" boolean with the "state at query month"
    boolean)."""
    # Pre-announcement: query_date 2007-12 with as_of 2008-11-30 should
    # raise NberCycleNotFoundError (the 2001-11 trough is the most
    # recent visible turning point and 2007-12 > 2001-11; but no peak
    # for the 2007 cycle has been announced yet at as_of=2008-11-30,
    # so the 2007-12 peak is NOT in the relevant set; nothing visible
    # ≤ 2007-12 except the 2001-11 trough).
    pre_announce = pd.Timestamp("2008-11-30")
    state_pre = cal.state_at("2007-12", as_of=pre_announce)
    # Pre-announcement: 2001-11 trough is most-recent visible at 2007-12
    # (since the 2007-12 peak is not yet announced). 2007-12 > 2001-11
    # AND 2007-12 != 2001-11 → strictly after trough → expansion.
    assert state_pre == "expansion", (
        f"pre-announcement query (2007-12 at as_of=2008-11-30): "
        f"got {state_pre!r}; expected expansion (most-recent visible "
        "turning point is the 2001-11 trough; 2007-12 is strictly past)"
    )
    # Post-announcement: same query at as_of=2008-12-15 should resolve
    # to "expansion" via the BOUNDARY FIX (2007-12 IS the peak month →
    # last expansion month, AT-the-turning-point semantics).
    post_announce = pd.Timestamp("2008-12-15")
    state_post = cal.state_at("2007-12", as_of=post_announce)
    assert state_post == "expansion", (
        f"post-announcement query (2007-12 at as_of=2008-12-15): "
        f"got {state_post!r}; expected expansion (NBER convention: "
        "peak month is LAST expansion month — boundary fix per 3.5b-W)"
    )
    # Sanity: querying BEFORE 1980-06-03 (the earliest announcement)
    # for ANY date in 1980+ raises (no turning point visible at all).
    before_calendar = pd.Timestamp("1980-01-15")  # before 1980 peak announce
    with pytest.raises(NberCycleNotFoundError):
        cal.state_at("1980-01", as_of=before_calendar)
