"""Tests for src.models.crps_weights (Layer 1.5B.4 — infrastructure only)."""
from __future__ import annotations

import pandas as pd
import pytest
from scipy import stats

from macro_pipeline.models.crps_weights import (
    EXPERT_COEFFICIENT_PRIORS,
    GaussianPrior,
    WeightEstimationResult,
    estimate_crps_weights_ridge,
    expert_baseline,
    standardize_components_for_logistic,
)


# ---------------------------------------------------------------------------
# GaussianPrior
# ---------------------------------------------------------------------------
def test_gaussian_prior_requires_positive_sigma():
    with pytest.raises(ValueError):
        GaussianPrior(mean=0.5, sigma=0.0)
    with pytest.raises(ValueError):
        GaussianPrior(mean=0.5, sigma=-0.1)


def test_gaussian_prior_rejects_non_finite_mean():
    with pytest.raises(ValueError):
        GaussianPrior(mean=float("inf"), sigma=1.0)


# ---------------------------------------------------------------------------
# Expert priors registry
# ---------------------------------------------------------------------------
def test_expert_priors_match_build_guide_v1_2():
    """The 6 component priors from build guide v1.2."""
    expected = {
        "yield_curve_nyfed": 0.30,
        "sahm_rule":         0.20,
        "lei_3d_rule":       0.20,
        "ism_pmi_neworders": 0.10,
        "nfci_kcfsi":        0.10,
        "hy_oas_regime":     0.10,
    }
    for k, v in expected.items():
        assert k in EXPERT_COEFFICIENT_PRIORS
        assert isinstance(EXPERT_COEFFICIENT_PRIORS[k], GaussianPrior)
        assert EXPERT_COEFFICIENT_PRIORS[k].mean == v


# ---------------------------------------------------------------------------
# estimate_crps_weights_ridge stub semantics
# ---------------------------------------------------------------------------
def _toy_inputs(n_components: int = 6) -> tuple[pd.DataFrame, pd.Series]:
    idx = pd.date_range("2000-01-01", periods=120, freq="ME")
    components = pd.DataFrame(
        {f"c{i}": [0.0] * len(idx) for i in range(n_components)}, index=idx,
    )
    labels = pd.Series([0] * len(idx), index=idx)
    return components, labels


def test_ridge_returns_placeholder_with_is_placeholder_true():
    components, labels = _toy_inputs()
    result = estimate_crps_weights_ridge(components, labels)
    assert isinstance(result, WeightEstimationResult)
    assert result.is_placeholder is True
    assert "placeholder" in result.method.lower()
    # AUC/Brier are NaN until Layer 5 actually fits.
    import math
    assert math.isnan(result.auc)
    assert math.isnan(result.brier_score)


def test_ridge_returns_placeholder_weights_match_priors():
    components, labels = _toy_inputs()
    result = estimate_crps_weights_ridge(components, labels)
    for k, p in EXPERT_COEFFICIENT_PRIORS.items():
        assert k in result.weights
        assert abs(result.weights[k] - p.mean) < 1e-9


def test_ridge_rejects_random_cv_method():
    """Random CV is forbidden in time series — leaks future into past."""
    components, labels = _toy_inputs()
    with pytest.raises(ValueError):
        estimate_crps_weights_ridge(components, labels, cv_method="random")


def test_ridge_rejects_non_positive_lambda():
    components, labels = _toy_inputs()
    with pytest.raises(ValueError):
        estimate_crps_weights_ridge(components, labels, lambda_=0.0)


def test_ridge_rejects_too_few_cv_folds():
    components, labels = _toy_inputs()
    with pytest.raises(ValueError):
        estimate_crps_weights_ridge(components, labels, cv_folds=1)


# ---------------------------------------------------------------------------
# Beta-prior rejection (B.4 critical type guard)
# ---------------------------------------------------------------------------
def test_ridge_rejects_scipy_beta_prior():
    """B.4 contract: Beta priors are for event-rate quantities (B.1),
    NOT for logistic regression coefficients."""
    components, labels = _toy_inputs()
    bad_priors = {"yield_curve_nyfed": stats.beta(2, 2)}
    with pytest.raises(TypeError, match="Beta prior"):
        estimate_crps_weights_ridge(components, labels, expert_coefficient_priors=bad_priors)


def test_ridge_rejects_dataclass_with_alpha_beta_attrs():
    """Anything with .alpha and .beta attributes is treated as a Beta-shaped
    prior and rejected to make the contract explicit."""
    from dataclasses import dataclass

    @dataclass
    class FakeBetaPrior:
        alpha: float
        beta: float

    components, labels = _toy_inputs()
    bad_priors = {"yield_curve_nyfed": FakeBetaPrior(alpha=2.0, beta=2.0)}
    with pytest.raises(TypeError, match="Beta prior"):
        estimate_crps_weights_ridge(components, labels, expert_coefficient_priors=bad_priors)


def test_ridge_accepts_plain_floats_as_priors():
    """Plain floats are interpreted as GaussianPrior(mean=v, sigma=1.0)."""
    components, labels = _toy_inputs()
    result = estimate_crps_weights_ridge(
        components, labels,
        expert_coefficient_priors={"yield_curve_nyfed": 0.5, "sahm_rule": 0.25},
    )
    assert result.weights["yield_curve_nyfed"] == 0.5
    assert result.weights["sahm_rule"] == 0.25


# ---------------------------------------------------------------------------
# standardize / expert_baseline are reserved for Layer 5
# ---------------------------------------------------------------------------
def test_standardize_raises_not_implemented():
    components, _ = _toy_inputs()
    with pytest.raises(NotImplementedError):
        standardize_components_for_logistic(components)


def test_expert_baseline_raises_not_implemented():
    components, _ = _toy_inputs()
    with pytest.raises(NotImplementedError):
        expert_baseline(components)
