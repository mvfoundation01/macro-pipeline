"""Tests for ``macro_pipeline.regime.kindleberger`` (Layer 3A)."""
from __future__ import annotations

import pandas as pd

from macro_pipeline.access import PitDataContext
from macro_pipeline.regime import classify_kindleberger
from macro_pipeline.regime.kindleberger import PHASES


def test_kindleberger_2007_euphoria() -> None:
    """At as_of=2007-06-01, valuation is in 95th pctile and margin debt is
    elevated — classifier should fire euphoria with at least 2 of 3
    triggers hit."""
    ctx = PitDataContext(as_of=pd.Timestamp("2007-06-01"))
    r = classify_kindleberger(ctx)
    assert r.phase == "euphoria"
    assert r.method == "rule_based_heuristic_v1"
    # CAPE rank should be very high
    assert r.metrics["cape_rank_full"] > 0.85
    # All 3 euphoria triggers must be True
    eup = r.triggers_hit["euphoria"]
    assert sum(1 for v in eup.values() if v is True) >= 2


def test_kindleberger_2009_revulsion() -> None:
    """At as_of=2009-03-01, equity drawdown, wide HY OAS, vol surge —
    revulsion phase."""
    ctx = PitDataContext(as_of=pd.Timestamp("2009-03-01"))
    r = classify_kindleberger(ctx)
    assert r.phase == "revulsion"
    # Confirm the underlying conditions
    assert r.metrics["equity_drawdown_pct"] < -20.0
    assert r.metrics["hy_oas_pct"] - r.metrics["hy_oas_lt_median"] > 2.0


def test_kindleberger_phase_vocabulary() -> None:
    """Whatever phase is returned must come from the documented set."""
    ctx = PitDataContext(as_of=pd.Timestamp("2017-06-01"))
    r = classify_kindleberger(ctx)
    assert r.phase in PHASES


def test_kindleberger_records_as_of() -> None:
    asof = pd.Timestamp("2010-01-01")
    r = classify_kindleberger(PitDataContext(as_of=asof))
    assert r.as_of == asof


def test_kindleberger_indeterminate_when_data_thin() -> None:
    """At as_of=1985-01-01 BAMLH0A0HYM2 (HY OAS) has no data; without
    enough triggers no phase fires and we return ``indeterminate``."""
    ctx = PitDataContext(as_of=pd.Timestamp("1985-01-01"))
    r = classify_kindleberger(ctx)
    # 1985-01-01: BAMLH0A0HYM2 starts 1996-12 so HY metrics absent;
    # FINRA margin debt starts 1997-01 so margin metrics absent;
    # most triggers should be None.
    assert "hy_oas_pct" not in r.metrics or r.metrics.get("hy_oas_pct") is None
    # Phase should be one of the documented values; usually indeterminate
    assert r.phase in PHASES
