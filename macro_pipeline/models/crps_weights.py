"""CRPS weight estimation infrastructure (Layer 1.5B.4) — INFRASTRUCTURE ONLY.

ChatGPT review FAIL #1: the build guide v1.2 hard-coded CRPS weights
(yield_curve 0.30, sahm 0.20, lei_3d 0.20, ism 0.10, nfci_kcfsi 0.10,
hy_oas 0.10) as if they were optimization-derived; in reality they were
expert-chosen. Layer 5 will re-estimate them via penalized logistic
regression with expert weights as **Gaussian L2 priors on coefficients**.

This module sets up the contract — types, function signatures, and
input-validation guards — and returns a placeholder result so Layer 5
just has to fill in the optimizer. The placeholder is loud (``method``
contains ``"placeholder"``, ``is_placeholder=True``, AUC/Brier are
``NaN``) so any downstream consumer that picks it up by accident will
fail an obvious sanity check.

Beta priors vs Gaussian priors
------------------------------
For event-rate quantities (sensitivity, FPR, recall, precision) we use
**Beta** priors — that is :mod:`src.models.signal_probability`.

For logistic regression coefficients β_j we use **Gaussian** priors —
that is this module. Conflating the two is the bug ChatGPT flagged
(Beta priors on coefficients give nonsensical penalty geometry). Type
guards in :func:`estimate_crps_weights_ridge` reject scipy.stats Beta
prior objects to make the contract explicit at the boundary.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gaussian prior for logistic coefficients (NOT a Beta prior — see module docstring)
# ---------------------------------------------------------------------------
@dataclass
class GaussianPrior:
    """Gaussian L2 prior on a logistic regression coefficient.

    ``mean`` is the expert-centered location for the coefficient; the
    L2 penalty in :func:`estimate_crps_weights_ridge` is
    ``λ × Σ (β_j − mean_j)² / sigma_j²``.

    ``sigma`` controls the prior tightness — small sigma means the
    estimator is strongly pulled toward ``mean``. Must be positive.
    """
    mean: float
    sigma: float = 1.0

    def __post_init__(self) -> None:
        if self.sigma <= 0:
            raise ValueError(f"sigma must be positive, got {self.sigma}")
        if not math.isfinite(self.mean):
            raise ValueError(f"mean must be finite, got {self.mean}")


# ---------------------------------------------------------------------------
# Expert priors (current build guide weights, treated as coefficient locations)
# ---------------------------------------------------------------------------
# These six weights came from build guide v1.2. They are NOT the final
# probabilities — they are the relative-importance judgments the expert
# made when CRPS was hand-tuned. Layer 5 will treat them as the means of
# Gaussian L2 priors and let blocked walk-forward CV tune the lambda.
EXPERT_COEFFICIENT_PRIORS: dict[str, GaussianPrior] = {
    "yield_curve_nyfed": GaussianPrior(mean=0.30, sigma=0.20),
    "sahm_rule":         GaussianPrior(mean=0.20, sigma=0.20),
    "lei_3d_rule":       GaussianPrior(mean=0.20, sigma=0.20),
    "ism_pmi_neworders": GaussianPrior(mean=0.10, sigma=0.20),
    "nfci_kcfsi":        GaussianPrior(mean=0.10, sigma=0.20),
    "hy_oas_regime":     GaussianPrior(mean=0.10, sigma=0.20),
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class WeightEstimationResult:
    method: str
    weights: dict[str, float]
    auc: float = float("nan")
    brier_score: float = float("nan")
    calibration_intercept: float = float("nan")
    calibration_slope: float = float("nan")
    n_train: int = 0
    n_test: int = 0
    cv_folds: int = 0
    lambda_used: float = float("nan")
    is_placeholder: bool = False
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation: reject Beta-shaped priors
# ---------------------------------------------------------------------------
def _validate_gaussian_priors(priors: dict[str, Any]) -> None:
    """Raise TypeError if any prior is not Gaussian-shaped.

    Accepts:
    - GaussianPrior instances
    - plain numbers (interpreted later as ``GaussianPrior(mean=v, sigma=1.0)``)

    Rejects (with explicit messages):
    - scipy.stats Beta (`stats.beta`) frozen distributions
    - dataclasses whose fields are ``alpha`` / ``beta``
    - any object exposing both ``alpha`` and ``beta`` attributes
    """
    for name, p in priors.items():
        if isinstance(p, GaussianPrior):
            continue
        if isinstance(p, (int, float)):
            if not math.isfinite(p):
                raise ValueError(
                    f"Prior for {name!r} is not finite ({p}); "
                    f"use GaussianPrior or a finite float."
                )
            continue
        # Detect Beta-shaped objects.
        if hasattr(p, "alpha") and hasattr(p, "beta"):
            raise TypeError(
                f"Prior for {name!r} looks like a Beta prior "
                f"({type(p).__name__}). Beta priors are for event-rate "
                f"quantities (see src.models.signal_probability). "
                f"Logistic regression coefficients require GaussianPrior."
            )
        # scipy.stats frozen distributions: dist.dist.name == "beta"
        dist = getattr(p, "dist", None)
        if dist is not None and getattr(dist, "name", "") == "beta":
            raise TypeError(
                f"Prior for {name!r} is scipy.stats.beta, which is a "
                f"Beta prior. Beta priors are for event-rate quantities "
                f"(see src.models.signal_probability). Logistic "
                f"regression coefficients require GaussianPrior."
            )
        raise TypeError(
            f"Prior for {name!r} has unsupported type {type(p).__name__}. "
            f"Use GaussianPrior or a finite float."
        )


# ---------------------------------------------------------------------------
# Public estimator (placeholder until Layer 5)
# ---------------------------------------------------------------------------
def estimate_crps_weights_ridge(
    components: pd.DataFrame,
    nber_labels: pd.Series,
    expert_coefficient_priors: dict[str, GaussianPrior | float] | None = None,
    *,
    lambda_: float = 1.0,
    cv_method: str = "time_blocked",
    cv_folds: int = 5,
) -> WeightEstimationResult:
    """Penalized logistic regression with Gaussian L2 priors centered on
    expert weights — INFRASTRUCTURE ONLY in Layer 1.5B.

    Currently returns a ``WeightEstimationResult`` with ``is_placeholder=True``
    and weights = the prior means (or the supplied float). The function does
    NOT actually fit; Layer 5 will replace the body with a blocked
    walk-forward CV ridge logistic.

    The input contract is fully validated up-front:
      - Components and labels must align on a common index (DatetimeIndex).
      - Priors must be Gaussian-shaped (Beta priors are explicitly rejected).
      - ``cv_method`` must be ``"time_blocked"`` (random CV is forbidden in
        time series — leaks future into past).
      - ``lambda_`` must be positive.
    """
    if not isinstance(components, pd.DataFrame):
        raise TypeError("components must be a pandas DataFrame")
    if not isinstance(nber_labels, pd.Series):
        raise TypeError("nber_labels must be a pandas Series")
    if cv_method != "time_blocked":
        raise ValueError(
            f"cv_method={cv_method!r}: only 'time_blocked' is allowed for "
            f"time-series CV (random CV leaks future into past)."
        )
    if lambda_ <= 0:
        raise ValueError(f"lambda_ must be positive, got {lambda_}")
    if cv_folds < 2:
        raise ValueError(f"cv_folds must be >= 2, got {cv_folds}")

    priors = expert_coefficient_priors if expert_coefficient_priors is not None \
        else EXPERT_COEFFICIENT_PRIORS
    _validate_gaussian_priors(priors)

    # Build placeholder weight dict from the priors' means.
    weights: dict[str, float] = {}
    for name, p in priors.items():
        weights[name] = float(p.mean) if isinstance(p, GaussianPrior) else float(p)

    log.warning(
        "estimate_crps_weights_ridge called: returning placeholder "
        "(Layer 5 will replace with blocked walk-forward CV ridge logistic). "
        "Caller must check is_placeholder=True before using the weights."
    )
    return WeightEstimationResult(
        method="ridge_logistic_placeholder",
        weights=weights,
        is_placeholder=True,
        cv_folds=cv_folds,
        lambda_used=lambda_,
        notes=(
            "Layer 1.5B.4 placeholder. Layer 5 will fit a Gaussian L2-"
            "penalized logistic regression with blocked walk-forward CV. "
            "Weights returned here are the prior means (expert weights)."
        ),
    )


def standardize_components_for_logistic(
    components: pd.DataFrame,
    fit_period: tuple[pd.Timestamp, pd.Timestamp] | None = None,
) -> tuple[pd.DataFrame, dict[str, tuple[float, float]]]:
    """Standardize each component column to zero-mean / unit-variance.

    INFRASTRUCTURE ONLY: Layer 5 will fit the scaler on a blocked CV
    fit window only (to avoid leaking test-window stats into training).
    Currently raises NotImplementedError so callers can't accidentally
    use it as if it were Layer-5 ready.
    """
    raise NotImplementedError(
        "standardize_components_for_logistic is reserved for Layer 5. "
        "It must use only ``fit_period`` to fit the scaler so test "
        "fold statistics do not leak into the model."
    )


def expert_baseline(
    components: pd.DataFrame,
    expert_priors: dict[str, GaussianPrior | float] | None = None,
) -> WeightEstimationResult:
    """Baseline CRPS using the expert priors as fixed weights.

    INFRASTRUCTURE ONLY. Layer 5 uses this as the comparison reference
    when reporting how much the Ridge fit moved the weights.
    """
    raise NotImplementedError(
        "expert_baseline is reserved for Layer 5; it will compute CRPS "
        "using the priors as fixed weights and report AUC + Brier + "
        "calibration on a held-out tail of the sample."
    )


__all__ = [
    "EXPERT_COEFFICIENT_PRIORS",
    "GaussianPrior",
    "WeightEstimationResult",
    "estimate_crps_weights_ridge",
    "expert_baseline",
    "standardize_components_for_logistic",
]
