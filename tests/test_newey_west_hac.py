"""Tests for ``macro_pipeline.analysis.newey_west_hac`` (Layer 3D)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_pipeline.analysis import HACResult, fit_ols_hac


def _make_xy(n: int, beta: float, alpha: float = 0.0, noise_sd: float = 0.5,
             seed: int = 42) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1990-01-01", periods=n, freq="ME")
    x = pd.Series(rng.normal(0, 1, n), index=idx, name="x")
    y = alpha + beta * x + pd.Series(rng.normal(0, noise_sd, n), index=idx, name="y")
    y.name = "y"
    return y, x


def test_fit_ols_hac_recovers_known_beta():
    y, x = _make_xy(n=240, beta=2.0, alpha=0.5, noise_sd=1.0, seed=42)
    fit = fit_ols_hac(y, x, horizon_months=12)
    assert isinstance(fit, HACResult)
    # large n; HAC should recover slope and intercept tightly
    assert abs(fit.beta - 2.0) < 0.20
    assert abs(fit.alpha - 0.5) < 0.20
    assert fit.maxlags == 11   # H - 1 for 12-month horizon
    assert fit.n_obs == 240


def test_fit_ols_hac_maxlags_per_horizon():
    """maxlags must be horizon_months - 1 for each horizon."""
    y, x = _make_xy(n=200, beta=1.0, seed=1)
    for h in (12, 36, 60, 120):
        fit = fit_ols_hac(y, x, horizon_months=h)
        assert fit is not None
        assert fit.maxlags == h - 1


def test_fit_ols_hac_returns_none_on_too_few_obs():
    y, x = _make_xy(n=1, beta=1.0)
    fit = fit_ols_hac(y, x, horizon_months=12)
    assert fit is None


def test_fit_ols_hac_returns_none_on_zero_variance_x():
    idx = pd.date_range("1990-01-01", periods=60, freq="ME")
    x = pd.Series([5.0] * 60, index=idx, name="x")
    y = pd.Series(np.linspace(0, 1, 60), index=idx, name="y")
    assert fit_ols_hac(y, x, horizon_months=12) is None


def test_fit_ols_hac_drops_na_alignment():
    """NaN in either series must be dropped before regression."""
    idx = pd.date_range("1990-01-01", periods=60, freq="ME")
    x = pd.Series(np.arange(60, dtype=float), index=idx, name="x")
    y = pd.Series(2.0 * np.arange(60, dtype=float) + 1.0, index=idx, name="y")
    x.iloc[5] = np.nan
    y.iloc[10] = np.nan
    fit = fit_ols_hac(y, x, horizon_months=12)
    assert fit is not None
    # 60 - 2 dropped = 58 obs
    assert fit.n_obs == 58


def test_fit_ols_hac_horizon_must_be_positive():
    y, x = _make_xy(n=50, beta=1.0)
    with pytest.raises(ValueError, match="horizon_months"):
        fit_ols_hac(y, x, horizon_months=0)
    with pytest.raises(ValueError, match="horizon_months"):
        fit_ols_hac(y, x, horizon_months=-12)


def test_fit_ols_hac_p_value_is_finite_and_in_unit():
    y, x = _make_xy(n=240, beta=1.0, seed=7)
    fit = fit_ols_hac(y, x, horizon_months=12)
    assert fit is not None
    assert 0.0 <= fit.p_value_beta_NW <= 1.0


def test_fit_ols_hac_residual_se_positive():
    y, x = _make_xy(n=120, beta=1.0, noise_sd=0.5, seed=3)
    fit = fit_ols_hac(y, x, horizon_months=12)
    assert fit is not None
    assert fit.residual_se > 0
