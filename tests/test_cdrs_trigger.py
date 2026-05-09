"""Tests for ``macro_pipeline.scoring.cdrs_trigger`` (Layer 3C)."""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.scoring import (
    T_COMPONENTS,
    TriggerResult,
    compute_trigger,
)
from macro_pipeline.scoring.scored_observation import CompositeBuildError

# --- §6.7 anchor tests (Path B thresholds per Strategic Claude) -----------

def test_cdrs_trigger_2008_september():
    """At as_of=2008-09-15 (Lehman week), T should fire moderately.
    Spec wanted T > 0.85; Strategic Claude D9 path B threshold T > 0.55
    (smoke saw 0.66)."""
    t = compute_trigger(PitDataContext(as_of=pd.Timestamp("2008-09-15")))
    assert isinstance(t, TriggerResult)
    assert t.score > 0.55
    # HY OAS should be widening sharply
    assert t.components_normalized["T1_hy_oas_30d_roc"] > 0.7
    # VIX percentile should be at or near top of 12M trailing window
    assert t.components_normalized["T2_vix_12m_pctile"] > 0.9


def test_cdrs_trigger_2017_calm():
    """Mid-cycle 2017-06: low VIX, narrow OAS, breadth strong. T < 0.20."""
    t = compute_trigger(PitDataContext(as_of=pd.Timestamp("2017-06-01")))
    assert t.score < 0.20


# --- D9 graceful-degradation pre-2022 (T3 dropped, weights renormalized) --

def test_t3_inactive_pre_2022_d9():
    """At as_of=2017-06-01, CBOE_GAMMA has no PIT-safe data (starts
    2022-12-12). T3 must drop and the remaining 4 components must each
    weight 0.25."""
    t = compute_trigger(PitDataContext(as_of=pd.Timestamp("2017-06-01")))
    assert "T3_gamma_sign" in t.inactive_components
    assert len(t.active_components) == 4
    for w in t.weights.values():
        assert abs(w - 0.25) < 1e-9


def test_t3_active_post_2022():
    """At as_of=2025-06-01, T3 is in active set; all 5 components
    weight 0.20 each."""
    t = compute_trigger(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    assert "T3_gamma_sign" in t.active_components
    assert len(t.active_components) == 5
    for w in t.weights.values():
        assert abs(w - 0.20) < 1e-9


def test_t_raises_when_no_components_active():
    """Pre-1990 has no T inputs — must raise CompositeBuildError per
    the trigger contract (cannot aggregate over empty active set)."""
    with pytest.raises(CompositeBuildError, match="no active components"):
        compute_trigger(PitDataContext(as_of=pd.Timestamp("1929-08-01")))


# --- Output contract -------------------------------------------------------

def test_trigger_score_in_unit_interval():
    t = compute_trigger(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    assert 0.0 <= t.score <= 1.0


def test_trigger_components_constant_matches_module_keys():
    t = compute_trigger(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    union = set(t.active_components) | set(t.inactive_components)
    assert union == set(T_COMPONENTS)


def test_trigger_method_recorded():
    t = compute_trigger(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    assert t.method == "trigger_v1"


def test_trigger_pit_safe():
    asof = pd.Timestamp("2008-09-15")
    t = compute_trigger(PitDataContext(as_of=asof))
    assert t.as_of == asof
