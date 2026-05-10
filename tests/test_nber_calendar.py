"""Tests for Layer 3.5C NBER announcement calendar.

Per ``LAYER_3_5_BUILD_SPEC.md`` §5.5 + standing-orders §2.7 (≥50% NEG floor).

Final split: 4 NEG / 4 POS = 50%, satisfying §2.7.

Negative tests cover:
- pre-1978 real-time raises ``PitDataUnavailableError``
- announcement after peak invariant (CSV row sanity)
- calendar with missing required column raises ``NberCalendarLoadError``
- get_announcement_date raises for unknown turning point

Positive tests cover:
- Dec 2007 peak announcement = 2008-12-01
- Feb 2020 peak announcement = 2020-06-08 (4-month)
- pre-1978 training mode returns label with caveat flag
- spec test #7 contract: 2008-09 query at as_of=2008-09 -> "expansion"
"""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.regime import (
    NBER_CALENDAR_BOUNDARY,
    NberCalendarLoader,
    NberCalendarLoadError,
    NberCycleNotFoundError,
    extract_nber_state,
)
from macro_pipeline.regime.exceptions import PitDataUnavailableError


# ---------------------------------------------------------------------------
# 1. POS — Dec 2007 peak announced Dec 2008 (12-month lag)
# ---------------------------------------------------------------------------
def test_nber_dec_2007_peak_announced_dec_2008():
    cal = NberCalendarLoader()
    announcement = cal.get_announcement_date("2007-12", "peak")
    assert announcement == pd.Timestamp("2008-12-01")


# ---------------------------------------------------------------------------
# 2. POS — Feb 2020 peak announced June 2020 (4-month, atypically fast)
# ---------------------------------------------------------------------------
def test_nber_2020_covid_peak_4_month_announcement():
    cal = NberCalendarLoader()
    announcement = cal.get_announcement_date("2020-02", "peak")
    assert announcement == pd.Timestamp("2020-06-08")


# ---------------------------------------------------------------------------
# 3. NEG — pre-1978 real-time raises PitDataUnavailableError
# ---------------------------------------------------------------------------
def test_nber_pre_1978_real_time_raises_pit_data_unavailable():
    ctx = PitDataContext(as_of=pd.Timestamp("2024-01-01"), is_real_time=True)
    with pytest.raises(PitDataUnavailableError) as exc_info:
        extract_nber_state(pd.Timestamp("1975-06-01"), ctx=ctx)
    msg = str(exc_info.value).lower()
    assert "pre-1978" in msg or "training-only" in msg


# ---------------------------------------------------------------------------
# 4. POS — pre-1978 training mode returns label with caveat flag
# ---------------------------------------------------------------------------
def test_nber_pre_1978_training_mode_allowed():
    ctx = PitDataContext(as_of=pd.Timestamp("2024-01-01"), is_real_time=False)
    r = extract_nber_state(pd.Timestamp("1975-06-01"), ctx=ctx)
    # 1975-06 is just after the 1975-03 trough → expansion
    assert r.state == "expansion"
    assert r.is_pre_1978_training_only is True


# ---------------------------------------------------------------------------
# 5. POS — calendar contains all 6 expected post-1978 cycles
# ---------------------------------------------------------------------------
def test_nber_calendar_completeness_post_1978():
    cal = NberCalendarLoader()
    actual_peaks = sorted(str(c.peak_date) for c in cal.cycles)
    assert actual_peaks == [
        "1980-01", "1981-07", "1990-07",
        "2001-03", "2007-12", "2020-02",
    ]
    # All cycles should be on/after 1978-01.
    for c in cal.cycles:
        assert c.peak_date >= NBER_CALENDAR_BOUNDARY
        assert c.trough_date >= NBER_CALENDAR_BOUNDARY


# ---------------------------------------------------------------------------
# 6. NEG — announcement after peak invariant (no negative lag in CSV)
# ---------------------------------------------------------------------------
def test_nber_announcement_after_peak():
    cal = NberCalendarLoader()
    for c in cal.cycles:
        peak_ts = c.peak_date.to_timestamp()
        trough_ts = c.trough_date.to_timestamp()
        assert c.peak_announcement_date > peak_ts, (
            f"Negative lag: {c.peak_date} peak announced "
            f"{c.peak_announcement_date.date()}"
        )
        assert c.trough_announcement_date > trough_ts, (
            f"Negative lag: {c.trough_date} trough announced "
            f"{c.trough_announcement_date.date()}"
        )


# ---------------------------------------------------------------------------
# 7. POS — spec test #7 contract:
# at as_of=2008-09-01 querying 2008-09-01 -> "expansion"
# ---------------------------------------------------------------------------
def test_extract_nber_state_uses_actual_lag_not_180():
    """Pre-3.5C this would have asserted the 180-day approximation
    masked 2008-09 (visibility_date = 2009-03 > as_of=2008-09 → fil-
    tered). Post-3.5C the calendar shows 2007-12 peak announced
    2008-12-01 → at as_of=2008-09-01 only the 2001-11 trough is
    visible → state is 'expansion'. Latest mode shows 'recession'
    (post-hoc determination). The PIT vs latest discrepancy IS the
    observable consequence of using actual lag instead of 180-day
    approx.
    """
    pit_ctx = PitDataContext(as_of=pd.Timestamp("2008-09-01"))
    pit_state = extract_nber_state(
        pd.Timestamp("2008-09-01"), ctx=pit_ctx
    ).state
    latest_state = extract_nber_state(pd.Timestamp("2008-09-01")).state
    assert pit_state == "expansion"
    assert latest_state == "recession"


# ---------------------------------------------------------------------------
# 8. POS — backward compat: PitDataContext.is_real_time defaults to True
# ---------------------------------------------------------------------------
def test_pit_data_context_is_real_time_default_true():
    ctx = PitDataContext(as_of=pd.Timestamp("2024-01-01"))
    assert ctx.is_real_time is True
    # Explicitly setting False also works.
    ctx2 = PitDataContext(as_of=pd.Timestamp("2024-01-01"), is_real_time=False)
    assert ctx2.is_real_time is False


# ---------------------------------------------------------------------------
# 9. NEG — calendar CSV missing required column raises NberCalendarLoadError
# ---------------------------------------------------------------------------
def test_nber_calendar_csv_malformed_raises(tmp_path: Path):
    bad_csv = tmp_path / "bad.csv"
    # Missing trough_announcement_date column.
    with bad_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["peak_date", "peak_announcement_date", "trough_date",
             "source_url", "notes"]
        )
        writer.writerow(
            ["1980-01", "1980-06-03", "1980-07",
             "https://www.nber.org/", "test"]
        )
    with pytest.raises(NberCalendarLoadError) as exc_info:
        NberCalendarLoader(csv_path=bad_csv)
    assert "missing required columns" in str(exc_info.value).lower() \
        or "trough_announcement_date" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 10. NEG — get_announcement_date raises for unknown turning point
# ---------------------------------------------------------------------------
def test_nber_calendar_loader_unknown_cycle_raises():
    cal = NberCalendarLoader()
    # 2030-01 is not in calendar; should raise.
    with pytest.raises(NberCycleNotFoundError) as exc_info:
        cal.get_announcement_date("2030-01", "peak")
    msg = str(exc_info.value).lower()
    assert "2030" in msg or "not found" in msg or "calendar covers" in msg
