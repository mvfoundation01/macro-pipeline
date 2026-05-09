"""Tests for ``macro_pipeline.regime.dalio_cycle`` (Layer 3A)."""
from __future__ import annotations

import pandas as pd

from macro_pipeline.access import PitDataContext
from macro_pipeline.regime import classify_dalio
from macro_pipeline.regime.dalio_cycle import PHASES


def test_dalio_2025_late_phase() -> None:
    """At as_of=2025-06-01, debt/GDP is in the top decile and
    interest/revenue exceeds 8% — classifier should fire ``late``."""
    ctx = PitDataContext(as_of=pd.Timestamp("2025-06-01"))
    r = classify_dalio(ctx)
    assert r.phase == "late"
    # Confirm underlying conditions
    assert r.metrics["debt_gdp_rank_full"] > 0.70
    assert r.metrics["interest_pct_revenue"] > 8.0


def test_dalio_metrics_populated_at_modern_as_of() -> None:
    """All 5 expected metrics should be present for a modern as_of."""
    r = classify_dalio(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    expected = {"debt_gdp_pct", "debt_gdp_rank_full", "interest_pct_revenue",
                "r_star_pct", "real_rate_pct"}
    assert expected.issubset(r.metrics.keys())


def test_dalio_pre_vintage_indeterminate() -> None:
    """At as_of=2008-09-15 the FRED ALFRED + HLW vintage panels both
    have nothing visible (panels start ~2011 / 2015Q4 respectively).
    Classifier must degrade to ``indeterminate`` rather than raise."""
    ctx = PitDataContext(as_of=pd.Timestamp("2008-09-15"))
    r = classify_dalio(ctx)
    assert r.phase == "indeterminate"
    # Notes should record the missing data
    notes_str = " ".join(r.notes).lower()
    assert "debt" in notes_str or "hlw" in notes_str


def test_dalio_method_recorded() -> None:
    r = classify_dalio(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    assert r.method == "rule_based_heuristic_v1"


def test_dalio_phase_vocabulary() -> None:
    r = classify_dalio(PitDataContext(as_of=pd.Timestamp("2020-12-01")))
    assert r.phase in PHASES
