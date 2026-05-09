"""Tests for src.models.signal_probability (Layer 1.5B.1)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_pipeline.models.signal_probability import (
    PriorStrength,
    SignalProbabilityProfile,
    beta_prior_params,
    compute_signal_profile,
    wilson_95_ci,
)


# ---------------------------------------------------------------------------
# PriorStrength + beta_prior_params
# ---------------------------------------------------------------------------
def test_prior_strength_hard_cap_is_5():
    assert int(PriorStrength.EXCEPTIONAL) == 5
    # Aliases
    assert PriorStrength.S2 == PriorStrength.UNINFORMATIVE
    assert PriorStrength.S5 == PriorStrength.EXCEPTIONAL


def test_beta_prior_uniform_for_S2():
    """S=2 collapses to Beta(1,1) regardless of mean."""
    a, b = beta_prior_params(prior_mean=0.5, prior_strength=PriorStrength.UNINFORMATIVE)
    assert a == 1.0 and b == 1.0
    a, b = beta_prior_params(prior_mean=0.9, prior_strength=PriorStrength.UNINFORMATIVE)
    assert a == 1.0 and b == 1.0


def test_beta_prior_S4_with_uninformative_mean():
    """S=4, m=0.5: α = 1 + 0.5*(4-2) = 2; β = 1 + 0.5*(4-2) = 2 → Beta(2,2)."""
    a, b = beta_prior_params(0.5, PriorStrength.STRONG_ACADEMIC)
    assert a == 2.0 and b == 2.0


def test_beta_prior_S4_with_pinned_mean():
    """S=4, m=0.8: α = 1+0.8*2 = 2.6; β = 1+0.2*2 = 1.4."""
    a, b = beta_prior_params(0.8, PriorStrength.STRONG_ACADEMIC)
    assert abs(a - 2.6) < 1e-9
    assert abs(b - 1.4) < 1e-9


def test_beta_prior_rejects_invalid_mean():
    with pytest.raises(ValueError):
        beta_prior_params(prior_mean=1.5, prior_strength=PriorStrength.UNINFORMATIVE)


# ---------------------------------------------------------------------------
# Wilson 95% CI
# ---------------------------------------------------------------------------
def test_wilson_8_of_8_lower_bound_is_about_0_68():
    """AGGREGATED_REVIEW_FINDINGS line 220: 8/8 → Wilson lower ≈ 0.68."""
    lo, hi = wilson_95_ci(k=8, n=8)
    assert abs(lo - 0.6756) < 0.005
    assert hi == 1.0


def test_wilson_7_of_8_lower_bound_is_about_0_53():
    """AGGREGATED_REVIEW_FINDINGS line 221: 7/8 → Wilson lower ≈ 0.53."""
    lo, _hi = wilson_95_ci(k=7, n=8)
    assert abs(lo - 0.529) < 0.01


def test_wilson_zero_n_returns_full_interval():
    assert wilson_95_ci(k=0, n=0) == (0.0, 1.0)


# ---------------------------------------------------------------------------
# SignalProbabilityProfile.from_observations
# ---------------------------------------------------------------------------
def test_from_observations_8_of_8_uninformative_posterior_mean_is_9_over_10():
    """Beta(1,1) prior + 8 hits / 0 misses → Beta(9,1), mean = 9/10 = 0.9."""
    p = SignalProbabilityProfile.from_observations(
        n_events=8, n_signals=8,
        prior_strength=PriorStrength.UNINFORMATIVE,
    )
    assert p.sensitivity == 1.0
    assert abs(p.sensitivity_posterior_mean - 0.9) < 1e-9
    assert p.sensitivity_posterior_alpha == 9.0
    assert p.sensitivity_posterior_beta == 1.0


def test_from_observations_7_of_8_uninformative_posterior_mean_is_8_over_10():
    """Beta(1,1) prior + 7 hits / 1 miss → Beta(8,2), mean = 8/10 = 0.8."""
    p = SignalProbabilityProfile.from_observations(
        n_events=8, n_signals=7,
        prior_strength=PriorStrength.UNINFORMATIVE,
    )
    assert abs(p.sensitivity_posterior_mean - 0.8) < 1e-9


def test_from_observations_carries_wilson_ci_independent_of_prior():
    """Wilson CI is computed from raw counts, not posterior. Two calls
    with different prior strengths must yield the same Wilson lower."""
    p_S2 = SignalProbabilityProfile.from_observations(
        n_events=8, n_signals=8,
        prior_strength=PriorStrength.UNINFORMATIVE,
    )
    p_S4 = SignalProbabilityProfile.from_observations(
        n_events=8, n_signals=8,
        prior_strength=PriorStrength.STRONG_ACADEMIC,
    )
    assert p_S2.sensitivity_wilson_95_ci == p_S4.sensitivity_wilson_95_ci
    assert abs(p_S2.sensitivity_wilson_95_ci[0] - 0.676) < 0.005


def test_from_observations_S4_pulls_posterior_toward_prior_mean():
    """With S=4 + m=0.5, prior is Beta(2,2). For 8/8 the posterior is
    Beta(10,2) (mean 0.833) — shrunk relative to the S=2 result of 0.9."""
    p_S2 = SignalProbabilityProfile.from_observations(
        n_events=8, n_signals=8,
        prior_strength=PriorStrength.UNINFORMATIVE,
    )
    p_S4 = SignalProbabilityProfile.from_observations(
        n_events=8, n_signals=8,
        prior_strength=PriorStrength.STRONG_ACADEMIC,
    )
    assert p_S2.sensitivity_posterior_mean > p_S4.sensitivity_posterior_mean
    assert abs(p_S4.sensitivity_posterior_mean - 10.0 / 12.0) < 1e-9


def test_from_observations_rejects_n_signals_gt_n_events():
    with pytest.raises(ValueError):
        SignalProbabilityProfile.from_observations(n_events=8, n_signals=9)


# ---------------------------------------------------------------------------
# compute_signal_profile (full time-series path)
# ---------------------------------------------------------------------------
def test_compute_signal_profile_perfect_signal():
    """Synthetic: signal fires iff label is 1. Sensitivity = 1, FPR = 0,
    LR+ should be unbounded (sampled posterior median should be huge)."""
    rng = np.random.default_rng(0)
    label = pd.Series(rng.integers(0, 2, size=200),
                      index=pd.date_range("2000-01-01", periods=200, freq="ME"))
    signal = label.copy()  # perfect alignment
    p = compute_signal_profile(
        signal, label, indicator_id="PERFECT",
        prior_strength=PriorStrength.UNINFORMATIVE,
    )
    assert p.sensitivity == 1.0
    assert p.specificity == 1.0
    assert p.precision == 1.0


def test_compute_signal_profile_independent_signal_has_lr_near_one():
    """Independent signal/label: sensitivity ~= FPR, so LR+ ~= 1."""
    rng = np.random.default_rng(7)
    label = pd.Series(rng.integers(0, 2, size=2000),
                      index=pd.date_range("1990-01-01", periods=2000, freq="D"))
    signal = pd.Series(rng.integers(0, 2, size=2000), index=label.index)
    p = compute_signal_profile(
        signal, label, indicator_id="RANDOM",
        prior_strength=PriorStrength.UNINFORMATIVE,
    )
    # With ~2000 observations, LR+ should be tightly around 1.
    assert p.LR_positive_posterior_median is not None
    assert 0.8 < p.LR_positive_posterior_median < 1.2


def test_compute_signal_profile_separates_sensitivity_and_precision():
    """ChatGPT review acceptance: do NOT collapse precision and recall.

    We construct an asymmetric scenario: 1 recession in 100 obs, signal
    fires on 10 of them but only on the recession; precision ≈ 1/10
    while sensitivity = 1.0.
    """
    idx = pd.date_range("2010-01-01", periods=100)
    label = pd.Series(0, index=idx)
    label.iloc[50] = 1
    signal = pd.Series(0, index=idx)
    signal.iloc[45:55] = 1   # 10 signal firings, 1 of them coincides with recession
    p = compute_signal_profile(
        signal, label, indicator_id="ASYM",
        prior_strength=PriorStrength.UNINFORMATIVE,
    )
    assert p.sensitivity == 1.0
    assert abs(p.precision - 0.1) < 1e-9
    assert p.sensitivity != p.precision  # the whole point of B.1
