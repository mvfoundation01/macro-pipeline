"""Newey-West HAC wrapper (Layer 3D).

Spec: ``LAYER_3_BUILD_SPEC.md`` §7.3.

Forward-return regressions at horizon H months have overlapping
windows that violate iid; raw OLS standard errors are biased downward.
Newey-West HAC (Heteroskedasticity- and Autocorrelation-Consistent)
correction at ``maxlags = H − 1`` is the canonical fix
(Hansen-Hodrick / Newey-West 1987).

The wrapper here is statsmodels with one specific config:

    OLS(y, X).fit(cov_type='HAC', cov_kwds={'maxlags': H - 1})

We expose a small dataclass result so callers don't depend on
statsmodels internals.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm


@dataclass
class HACResult:
    alpha: float
    beta: float
    r_squared: float
    adj_r_squared: float
    residual_se: float           # std error of residuals
    p_value_beta_NW: float       # Newey-West HAC p-value for beta
    maxlags: int
    n_obs: int
    ci_method: str = "newey_west_hac"


def fit_ols_hac(
    y: pd.Series,
    x: pd.Series,
    *,
    horizon_months: int,
    drop_na: bool = True,
) -> HACResult | None:
    """Fit ``y = alpha + beta * x + eps`` with Newey-West HAC SE.

    ``maxlags`` is set to ``horizon_months - 1`` per spec §7.3.

    Returns ``None`` when:
      - aligned (y, x) has fewer than 2 observations
      - x has zero variance (degenerate regressor)
      - statsmodels raises (e.g. perfect multicollinearity, singular X)
    """
    if horizon_months <= 0:
        raise ValueError(f"horizon_months must be positive, got {horizon_months}")
    if not isinstance(y, pd.Series) or not isinstance(x, pd.Series):
        raise TypeError("y and x must be pandas Series")

    # Inner-join + drop NA so OLS sees aligned data only.
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1)
    if drop_na:
        df = df.dropna()
    if len(df) < 2:
        return None
    if float(df["x"].std(ddof=0)) == 0.0:
        return None

    X = sm.add_constant(df["x"].values)
    try:
        model = sm.OLS(df["y"].values, X).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": max(0, horizon_months - 1)},
        )
    except Exception:
        return None

    alpha = float(model.params[0])
    beta = float(model.params[1])
    p_beta = float(model.pvalues[1])
    r2 = float(model.rsquared)
    r2_adj = float(model.rsquared_adj)
    # statsmodels stores residual standard error as scale ** 0.5; we
    # report the raw residual standard deviation for downstream display.
    residuals = np.asarray(df["y"].values, dtype=float) - model.predict(X)
    residual_se = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else float("nan")

    if not math.isfinite(p_beta):
        p_beta = float("nan")

    return HACResult(
        alpha=alpha,
        beta=beta,
        r_squared=r2,
        adj_r_squared=r2_adj,
        residual_se=residual_se,
        p_value_beta_NW=p_beta,
        maxlags=max(0, horizon_months - 1),
        n_obs=len(df),
    )


__all__ = ["HACResult", "fit_ols_hac"]
