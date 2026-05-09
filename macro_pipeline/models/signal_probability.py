"""Calibrated probability profile for binary recession signals (Layer 1.5B.1).

Addresses ChatGPT review FAIL #2 ("Probability semantics undefined"): the
build guide reported values like "yield curve 75-82%" without specifying
whether they were precision, recall, or likelihood ratios. This module
codifies the distinction in a single dataclass and refuses to collapse
the dimensions.

Bayesian priors
---------------
- ``PriorStrength`` enum maps to S = α + β (total prior pseudo-counts).
- ``beta_prior_params(prior_mean=m, prior_strength=S)`` returns
    α = 1 + m × (S − 2),  β = 1 + (1 − m) × (S − 2)
  The leading 1+ structure is per ChatGPT 2026-05-09: it prevents
  α<1 / β<1 (which would make the prior bimodal at 0/1) and collapses
  to the uniform prior Beta(1,1) when S = 2.
- Hard cap S ≤ 5: with only 8-9 recession events in the modern sample,
  any larger S lets the prior dominate the data and violates the
  sample-size honesty principle this whole sprint is enforcing.

Beta priors apply *only* to event-rate quantities (sensitivity, FPR,
recall, precision). Logistic regression coefficients (CRPS weights, B.4)
use a Gaussian prior — those are different mathematical objects, do not
conflate.

Likelihood ratios
-----------------
LR+ and LR− are ratios of Bernoulli rates, so a single point estimate is
unstable when the denominator is small. We sample LR+ posteriors via
Monte Carlo from the two Beta posteriors (sensitivity & FPR) and report
the median + 95% percentile interval.

Wilson interval
---------------
Independent of any prior, we always also report Wilson 95% CIs on
sensitivity and FPR for callers that prefer a frequentist headline.
This is the interval the AGGREGATED_REVIEW_FINDINGS doc cites (8/8
hits → Wilson lower ≈ 0.68) and is what gates display in production.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------------------
# Prior strength enum + Beta prior parameterization
# ---------------------------------------------------------------------------
class PriorStrength(IntEnum):
    """S = α + β. Hard ceiling 5 (with 8-9 recession events, S=5 already
    equals ~50% of actual event count)."""

    UNINFORMATIVE = 2     # Beta(1,1) regardless of m. Use for proxy/manual sources.
    NORMAL_EXPERT = 3     # Most CRPS components.
    STRONG_ACADEMIC = 4   # Yield curve / NTFS / Sahm Rule.
    EXCEPTIONAL = 5       # Hard cap; only with independent OOS validation.

    # Short aliases (S2..S5) for ergonomic call sites.
    S2 = UNINFORMATIVE
    S3 = NORMAL_EXPERT
    S4 = STRONG_ACADEMIC
    S5 = EXCEPTIONAL


_PRIOR_STRENGTH_HARD_CAP = 5


def beta_prior_params(prior_mean: float, prior_strength: PriorStrength) -> tuple[float, float]:
    """Return Beta(α, β) parameters with the safe (1+) parameterization.

    α = 1 + m × (S − 2)
    β = 1 + (1 − m) × (S − 2)

    With ``prior_strength=PriorStrength.UNINFORMATIVE`` (S=2) returns
    Beta(1,1) regardless of ``prior_mean``.

    Hard cap S ≤ 5 is enforced (ChatGPT 2026-05-09 sample-size honesty).
    """
    S = int(prior_strength)
    if S > _PRIOR_STRENGTH_HARD_CAP:
        raise ValueError(
            f"PriorStrength S={S} exceeds hard cap {_PRIOR_STRENGTH_HARD_CAP} "
            f"(see ChatGPT 2026-05-09: with 8-9 events S=5 is already ~50% "
            f"of actual count)."
        )
    if not 0 <= prior_mean <= 1:
        raise ValueError(f"prior_mean must be in [0, 1], got {prior_mean}")
    alpha = 1 + prior_mean * (S - 2)
    beta = 1 + (1 - prior_mean) * (S - 2)
    return alpha, beta


# ---------------------------------------------------------------------------
# Wilson 95% CI for binomial proportion (frequentist, prior-independent)
# ---------------------------------------------------------------------------
def wilson_95_ci(k: int, n: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score 95% CI for k successes out of n trials.

    Returns (lower, upper). For n=0 returns (0.0, 1.0) by convention.
    The default z is the two-sided 95% standard-normal quantile.
    """
    if n <= 0:
        return (0.0, 1.0)
    if k < 0 or k > n:
        raise ValueError(f"k={k} must be in [0, n={n}]")
    p_hat = k / n
    z_sq = z * z
    denom = 1.0 + z_sq / n
    center = (p_hat + z_sq / (2 * n)) / denom
    half = (z * math.sqrt(p_hat * (1 - p_hat) / n + z_sq / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


# ---------------------------------------------------------------------------
# Profile dataclass
# ---------------------------------------------------------------------------
@dataclass
class SignalProbabilityProfile:
    """Calibrated probability profile for a binary recession signal.

    The dataclass deliberately keeps sensitivity / specificity / precision /
    LR+ / LR− as separate fields. ChatGPT review FAIL #2: collapsing them
    into a single "hit %" is the bug — values reported as "yield curve
    75-82%" historically mixed all of those quantities.
    """

    indicator_id: str
    sample_period: tuple[pd.Timestamp | None, pd.Timestamp | None] = (None, None)

    # Confusion matrix
    n_events: int = 0
    n_no_events: int = 0
    n_true_positives: int = 0
    n_false_positives: int = 0
    n_false_negatives: int = 0
    n_true_negatives: int = 0

    # Frequentist point estimates
    sensitivity: float | None = None
    specificity: float | None = None
    precision: float | None = None

    # Likelihood ratios (point estimates from Bernoulli rates)
    LR_positive: float | None = None
    LR_negative: float | None = None

    # Calibration (continuous models only — None for binary signals)
    brier_score: float | None = None
    calibration_intercept: float | None = None
    calibration_slope: float | None = None

    # Bayesian posterior for sensitivity (Beta with prior Beta(α,β) updated by TP/FN)
    sensitivity_posterior_alpha: float | None = None
    sensitivity_posterior_beta: float | None = None
    sensitivity_posterior_mean: float | None = None
    sensitivity_posterior_95_ci: tuple[float, float] | None = None

    # Bayesian posterior for FPR (Beta with prior Beta(α,β) updated by FP/TN)
    fpr_posterior_alpha: float | None = None
    fpr_posterior_beta: float | None = None
    fpr_posterior_mean: float | None = None
    fpr_posterior_95_ci: tuple[float, float] | None = None

    # Wilson 95% CIs (frequentist, prior-independent)
    sensitivity_wilson_95_ci: tuple[float, float] | None = None
    fpr_wilson_95_ci: tuple[float, float] | None = None

    # LR+ posterior via Monte Carlo
    LR_positive_posterior_median: float | None = None
    LR_positive_posterior_95_ci: tuple[float, float] | None = None

    # Audit trail of prior choices
    prior_strength_used: PriorStrength = PriorStrength.UNINFORMATIVE
    sensitivity_prior_mean: float = 0.5
    fpr_prior_mean: float = 0.5

    extra: dict[str, Any] = field(default_factory=dict)

    # ---- Convenience constructors ----
    @classmethod
    def from_observations(
        cls,
        *,
        n_events: int,
        n_signals: int,
        prior_strength: PriorStrength = PriorStrength.UNINFORMATIVE,
        sensitivity_prior_mean: float = 0.5,
        indicator_id: str = "ad_hoc",
        sample_period: tuple[pd.Timestamp | None, pd.Timestamp | None] = (None, None),
    ) -> SignalProbabilityProfile:
        """Build a sensitivity-only profile from pre-aggregated counts.

        ``n_events`` is the total number of recessions in the sample.
        ``n_signals`` is the count caught (TP). FN = n_events − n_signals.
        FP and TN are unknown so specificity / precision / LR+ / LR− are
        left None.

        Use this constructor for the textbook "yield curve called 8 of 9
        recessions" scenario. For full computation from time-series binary
        flags, use :func:`compute_signal_profile`.
        """
        if not 0 <= n_signals <= n_events:
            raise ValueError(
                f"n_signals={n_signals} must be in [0, n_events={n_events}]"
            )
        TP = int(n_signals)
        FN = int(n_events - n_signals)

        sens_alpha_prior, sens_beta_prior = beta_prior_params(
            sensitivity_prior_mean, prior_strength,
        )
        sens_alpha = sens_alpha_prior + TP
        sens_beta = sens_beta_prior + FN
        sens_mean = sens_alpha / (sens_alpha + sens_beta)
        sens_ci = stats.beta.interval(0.95, sens_alpha, sens_beta)

        sens_wilson = wilson_95_ci(TP, n_events) if n_events > 0 else None
        sens_point = TP / n_events if n_events > 0 else None

        return cls(
            indicator_id=indicator_id,
            sample_period=sample_period,
            n_events=int(n_events),
            n_true_positives=TP,
            n_false_negatives=FN,
            sensitivity=sens_point,
            sensitivity_posterior_alpha=sens_alpha,
            sensitivity_posterior_beta=sens_beta,
            sensitivity_posterior_mean=sens_mean,
            sensitivity_posterior_95_ci=(float(sens_ci[0]), float(sens_ci[1])),
            sensitivity_wilson_95_ci=sens_wilson,
            prior_strength_used=prior_strength,
            sensitivity_prior_mean=sensitivity_prior_mean,
        )


# ---------------------------------------------------------------------------
# Full computation from time-series binary signal/label
# ---------------------------------------------------------------------------
def compute_signal_profile(
    signal: pd.Series,
    label: pd.Series,
    *,
    indicator_id: str,
    prior_strength: PriorStrength = PriorStrength.UNINFORMATIVE,
    sensitivity_prior_mean: float = 0.5,
    fpr_prior_mean: float = 0.5,
    n_lr_samples: int = 10_000,
    rng_seed: int = 42,
) -> SignalProbabilityProfile:
    """Compute the full profile from aligned binary time series.

    Beta priors apply to sensitivity AND FPR independently. LR+ posterior
    is sampled via Monte Carlo from the two posteriors so the ratio of
    Bernoullis stays well-behaved when the FPR posterior includes 0.
    """
    df = pd.concat([signal.rename("s"), label.rename("y")], axis=1).dropna()
    if df.empty:
        raise ValueError(f"{indicator_id}: signal and label have no overlap")

    TP = int(((df["s"] == 1) & (df["y"] == 1)).sum())
    FP = int(((df["s"] == 1) & (df["y"] == 0)).sum())
    FN = int(((df["s"] == 0) & (df["y"] == 1)).sum())
    TN = int(((df["s"] == 0) & (df["y"] == 0)).sum())

    P = TP + FN
    N = FP + TN

    sensitivity = TP / P if P > 0 else None
    specificity = TN / N if N > 0 else None
    precision = TP / (TP + FP) if (TP + FP) > 0 else None
    fpr = (1 - specificity) if specificity is not None else None

    LR_pos = (sensitivity / fpr) if (sensitivity is not None and fpr not in (None, 0.0)) else None
    LR_neg = ((1 - sensitivity) / specificity) if (
        sensitivity is not None and specificity not in (None, 0.0)
    ) else None

    sens_alpha_prior, sens_beta_prior = beta_prior_params(sensitivity_prior_mean, prior_strength)
    sens_alpha = sens_alpha_prior + TP
    sens_beta = sens_beta_prior + FN
    sens_mean = sens_alpha / (sens_alpha + sens_beta)
    sens_ci = stats.beta.interval(0.95, sens_alpha, sens_beta)

    fpr_alpha_prior, fpr_beta_prior = beta_prior_params(fpr_prior_mean, prior_strength)
    fpr_alpha = fpr_alpha_prior + FP
    fpr_beta = fpr_beta_prior + TN
    fpr_mean = fpr_alpha / (fpr_alpha + fpr_beta)
    fpr_ci = stats.beta.interval(0.95, fpr_alpha, fpr_beta)

    rng = np.random.default_rng(rng_seed)
    sens_samples = rng.beta(sens_alpha, sens_beta, size=n_lr_samples)
    fpr_samples = rng.beta(fpr_alpha, fpr_beta, size=n_lr_samples)
    fpr_safe = np.where(fpr_samples > 0, fpr_samples, np.nan)
    lr_pos_samples = sens_samples / fpr_safe
    lr_pos_samples = lr_pos_samples[~np.isnan(lr_pos_samples)]
    if len(lr_pos_samples) > 0:
        lr_pos_median = float(np.median(lr_pos_samples))
        lr_pos_ci = (
            float(np.percentile(lr_pos_samples, 2.5)),
            float(np.percentile(lr_pos_samples, 97.5)),
        )
    else:
        lr_pos_median = None
        lr_pos_ci = None

    return SignalProbabilityProfile(
        indicator_id=indicator_id,
        sample_period=(df.index.min(), df.index.max()),
        n_events=P,
        n_no_events=N,
        n_true_positives=TP,
        n_false_positives=FP,
        n_false_negatives=FN,
        n_true_negatives=TN,
        sensitivity=sensitivity,
        specificity=specificity,
        precision=precision,
        LR_positive=LR_pos,
        LR_negative=LR_neg,
        sensitivity_posterior_alpha=sens_alpha,
        sensitivity_posterior_beta=sens_beta,
        sensitivity_posterior_mean=sens_mean,
        sensitivity_posterior_95_ci=(float(sens_ci[0]), float(sens_ci[1])),
        sensitivity_wilson_95_ci=wilson_95_ci(TP, P) if P > 0 else None,
        fpr_posterior_alpha=fpr_alpha,
        fpr_posterior_beta=fpr_beta,
        fpr_posterior_mean=fpr_mean,
        fpr_posterior_95_ci=(float(fpr_ci[0]), float(fpr_ci[1])),
        fpr_wilson_95_ci=wilson_95_ci(FP, N) if N > 0 else None,
        LR_positive_posterior_median=lr_pos_median,
        LR_positive_posterior_95_ci=lr_pos_ci,
        prior_strength_used=prior_strength,
        sensitivity_prior_mean=sensitivity_prior_mean,
        fpr_prior_mean=fpr_prior_mean,
    )


__all__ = [
    "PriorStrength",
    "SignalProbabilityProfile",
    "beta_prior_params",
    "compute_signal_profile",
    "wilson_95_ci",
]
