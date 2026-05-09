"""Tests for src.models.confidence (Layer 1.5B.2)."""
from __future__ import annotations

import math

import pytest

from macro_pipeline.models.confidence import (
    CONFIDENCE_CAPS,
    N_TARGET_RECESSION_EVENTS,
    N_TARGET_REGRESSION_LONG_HORIZON,
    confidence_score_v2,
    sample_adequacy_ratio,
)


# ---------------------------------------------------------------------------
# sample_adequacy_ratio
# ---------------------------------------------------------------------------
def test_sample_adequacy_caps_at_1():
    assert sample_adequacy_ratio(n_eff=200, n_target=20) == 1.0


def test_sample_adequacy_below_target_uses_sqrt():
    """sqrt(11/30) ≈ 0.6055."""
    r = sample_adequacy_ratio(n_eff=11, n_target=30)
    assert abs(r - math.sqrt(11 / 30)) < 1e-9


def test_n_target_constants():
    """ChatGPT 2026-05-09: production targets are 20 events / 30 long-horizon."""
    assert N_TARGET_RECESSION_EVENTS == 20
    assert N_TARGET_REGRESSION_LONG_HORIZON == 30


# ---------------------------------------------------------------------------
# Horizon caps
# ---------------------------------------------------------------------------
def test_confidence_caps_match_chatgpt_revision():
    """1Y=85, 3Y=75, 5Y=70, 10Y=65 (NOT 85 — N_eff ≈ 11)."""
    assert CONFIDENCE_CAPS["1Y"] == 0.85
    assert CONFIDENCE_CAPS["3Y"] == 0.75
    assert CONFIDENCE_CAPS["5Y"] == 0.70
    assert CONFIDENCE_CAPS["10Y"] == 0.65


# ---------------------------------------------------------------------------
# confidence_score_v2
# ---------------------------------------------------------------------------
def test_confidence_yield_curve_10y_capped_at_65():
    """B.2 acceptance scenario from CONFIRM 2:
        data_quality=0.95, track_record=0.85, regime_stability=0.6,
        theory=0.9, sample_adequacy=sqrt(11/30), ood_penalty=0.05,
        horizon=10Y → score capped at 65.
    """
    sa = math.sqrt(11 / 30)
    score = confidence_score_v2(
        data_quality=0.95,
        track_record=0.85,
        regime_stability=0.6,
        theoretical_foundation=0.9,
        sample_adequacy=sa,
        ood_penalty=0.05,
        horizon="10Y",
    )
    assert abs(score - 65.0) < 1e-9


def test_confidence_low_inputs_score_low():
    score = confidence_score_v2(
        data_quality=0.1,
        track_record=0.1,
        regime_stability=0.1,
        theoretical_foundation=0.1,
        sample_adequacy=0.1,
        horizon="1Y",
    )
    # 0.1 * 0.95 * 100 = 9.5
    assert abs(score - 9.5) < 1e-9


def test_confidence_max_inputs_capped_at_horizon():
    """All inputs at 1.0, no penalty → raw 95, capped at the horizon limit."""
    for horizon, cap in CONFIDENCE_CAPS.items():
        score = confidence_score_v2(
            data_quality=1.0, track_record=1.0, regime_stability=1.0,
            theoretical_foundation=1.0, sample_adequacy=1.0, horizon=horizon,
        )
        assert abs(score - cap * 100) < 1e-9


def test_confidence_score_floors_at_zero():
    """Penalties cannot drive the score below 0."""
    score = confidence_score_v2(
        data_quality=0.0, track_record=0.0, regime_stability=0.0,
        theoretical_foundation=0.0, sample_adequacy=0.0,
        ood_penalty=1.0, revision_penalty=1.0, horizon="1Y",
    )
    assert score == 0.0


def test_confidence_rejects_unknown_horizon():
    with pytest.raises(KeyError):
        confidence_score_v2(
            data_quality=1.0, track_record=1.0, regime_stability=1.0,
            theoretical_foundation=1.0, sample_adequacy=1.0,
            horizon="20Y",
        )


def test_confidence_rejects_out_of_range_inputs():
    with pytest.raises(ValueError):
        confidence_score_v2(
            data_quality=1.5, track_record=0.5, regime_stability=0.5,
            theoretical_foundation=0.5, sample_adequacy=0.5, horizon="1Y",
        )
