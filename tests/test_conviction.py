"""Tests for src.models.conviction (Layer 1.5B.3)."""
from __future__ import annotations

import math

import pytest

from src.models.conviction import (
    ConvictionProfile,
    compute_operational_reliability,
    compute_portfolio_actionability,
    compute_statistical_reliability,
)


# ---------------------------------------------------------------------------
# ConvictionProfile core
# ---------------------------------------------------------------------------
def test_conviction_profile_three_fields_separated():
    """The whole point of B.3: never collapse the three dimensions."""
    cv = ConvictionProfile(
        statistical_reliability=8.0,
        operational_reliability=9.0,
        portfolio_actionability=7.0,
    )
    assert cv.statistical_reliability == 8.0
    assert cv.operational_reliability == 9.0
    assert cv.portfolio_actionability == 7.0


def test_conviction_profile_rejects_out_of_range():
    with pytest.raises(ValueError):
        ConvictionProfile(11.0, 5.0, 5.0)
    with pytest.raises(ValueError):
        ConvictionProfile(-1.0, 5.0, 5.0)


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------
def test_aggregate_conservative_returns_min():
    cv = ConvictionProfile(8.0, 9.0, 7.0)
    assert cv.aggregate_conservative() == 7.0


def test_aggregate_geomean_unweighted():
    """Unweighted geomean of (8, 9, 7)."""
    cv = ConvictionProfile(8.0, 9.0, 7.0)
    expected = (8 * 9 * 7) ** (1 / 3)
    assert abs(cv.aggregate_geomean() - expected) < 1e-9


def test_aggregate_geomean_weighted():
    """Weighted geomean: weight statistical 2x, others 1x."""
    cv = ConvictionProfile(8.0, 9.0, 7.0)
    g = cv.aggregate_geomean(weights=(2.0, 1.0, 1.0))
    # exp((2/4)*ln(8) + (1/4)*ln(9) + (1/4)*ln(7))
    expected = math.exp(0.5 * math.log(8) + 0.25 * math.log(9) + 0.25 * math.log(7))
    assert abs(g - expected) < 1e-9


def test_aggregate_geomean_zero_field_drives_to_zero():
    """Geomean property: any 0-field zeroes the aggregate (weakest-link)."""
    cv = ConvictionProfile(10.0, 10.0, 0.0)
    assert cv.aggregate_geomean() == 0.0


def test_aggregate_handles_all_low():
    cv = ConvictionProfile(1.0, 1.0, 1.0)
    assert cv.aggregate_conservative() == 1.0
    assert abs(cv.aggregate_geomean() - 1.0) < 1e-9


def test_aggregate_handles_mixed():
    cv = ConvictionProfile(9.0, 5.0, 3.0)
    assert cv.aggregate_conservative() == 3.0
    expected_geo = (9 * 5 * 3) ** (1 / 3)
    assert abs(cv.aggregate_geomean() - expected_geo) < 1e-9


# ---------------------------------------------------------------------------
# Component helpers
# ---------------------------------------------------------------------------
def test_compute_statistical_reliability_full_marks():
    s = compute_statistical_reliability(
        oos_auc=1.0, oos_brier=0.0, coefficient_stability=1.0,
    )
    assert s == 10.0


def test_compute_operational_reliability_zero_lag_full_quality():
    s = compute_operational_reliability(
        latency_days=0, revision_risk=0.0, source_quality=1.0,
    )
    assert s == 10.0


def test_compute_operational_reliability_long_lag_caps_low():
    """30+ days latency → latency_score=0; remainder is 0.6 max → 6.0."""
    s = compute_operational_reliability(
        latency_days=60, revision_risk=0.0, source_quality=1.0,
    )
    assert abs(s - 6.0) < 1e-9


def test_compute_portfolio_actionability_full_marks():
    s = compute_portfolio_actionability(
        payoff_asymmetry=1.0, implementation_cost=0.0, signal_horizon_match=1.0,
    )
    assert s == 10.0
