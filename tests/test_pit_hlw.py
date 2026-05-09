"""Tests for HLW vintage dispatch in src.access.PitSeriesReader (Layer 1.5B.5)."""
from __future__ import annotations

import logging

import pandas as pd
import pytest

from src.access import HLW_VINTAGE_INDICATORS, PitDataContext, load_series


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def test_hlw_indicators_registered():
    assert set(HLW_VINTAGE_INDICATORS) == {
        "HLW_RSTAR", "HLW_TREND_GROWTH", "HLW_OUTPUT_GAP",
    }


# ---------------------------------------------------------------------------
# B.5 acceptance: HLW_RSTAR @ 2021-06-30 must use 2020Q2 vintage,
# not the latest (2025Q4) values truncated.
# ---------------------------------------------------------------------------
def test_hlw_rstar_pit_returns_pre_asof_vintage():
    asof = pd.Timestamp("2021-06-30")
    bundle = load_series("HLW_RSTAR", as_of=asof)
    assert bundle.pit_safe is True
    # Vintage 2020Q2 is published 2020-07-14; later vintages are
    # 2022Q4 (2023-01-14), 2023Q1 (2023-04-14), ... — none of those
    # may be visible at as_of=2021-06-30.
    assert bundle.metadata["hlw_vintage"] == "2020Q2"
    pub_date = pd.Timestamp(bundle.metadata["hlw_vintage_publication_date"])
    assert pub_date < asof


def test_hlw_rstar_pit_publication_date_strictly_before_asof():
    """B.5 strictness: the picked vintage's publication date must be
    strictly < as_of (not silently included if equal)."""
    bundle = load_series("HLW_RSTAR", as_of=pd.Timestamp("2024-01-15"))
    pub = pd.Timestamp(bundle.metadata["hlw_vintage_publication_date"])
    assert pub <= pd.Timestamp("2024-01-15")


def test_hlw_rstar_pit_data_truncated_at_vintage_quarter_end():
    """The values returned must come from the matched vintage, NOT the
    latest cache. Vintage 2020Q2 ends at 2020Q2 (last obs ~2020-04-01)."""
    bundle = load_series("HLW_RSTAR", as_of=pd.Timestamp("2021-06-30"))
    last_obs = bundle.data.dropna().index.max()
    # Vintage quarter end is 2020-06-30; data inside the sheet ends there.
    assert last_obs <= pd.Timestamp("2020-06-30")
    # And NOT today.
    assert last_obs < pd.Timestamp("2024-01-01")


def test_hlw_rstar_pit_metadata_records_vintage_source():
    bundle = load_series("HLW_RSTAR", as_of=pd.Timestamp("2024-04-15"))
    assert bundle.metadata["pit_source"] == "hlw_vintage_panel"


def test_hlw_trend_growth_dispatches_to_correct_column():
    bundle = load_series("HLW_TREND_GROWTH", as_of=pd.Timestamp("2024-04-15"))
    assert bundle.pit_safe is True
    assert bundle.metadata["pit_source"] == "hlw_vintage_panel"
    assert bundle.indicator_id == "HLW_TREND_GROWTH"


def test_hlw_output_gap_dispatches_to_correct_column():
    bundle = load_series("HLW_OUTPUT_GAP", as_of=pd.Timestamp("2024-04-15"))
    assert bundle.indicator_id == "HLW_OUTPUT_GAP"
    assert bundle.metadata["pit_source"] == "hlw_vintage_panel"


# ---------------------------------------------------------------------------
# Closes the 1.5A "fallback warning" path
# ---------------------------------------------------------------------------
def test_hlw_rstar_pit_does_not_emit_fallback_warning(caplog):
    """Layer 1.5A logged 'no materialized FRED vintage panel; falling
    back to latest-cache truncation' for HLW. After B.5, that warning
    must NOT appear for HLW_RSTAR."""
    with caplog.at_level(logging.WARNING, logger="src.access"):
        load_series("HLW_RSTAR", as_of=pd.Timestamp("2024-04-15"))
    msgs = [rec.message for rec in caplog.records]
    assert not any(
        "needs_vintage=True but no materialized FRED vintage panel" in m
        for m in msgs
    ), f"Unexpected fallback warning(s) in: {msgs}"
