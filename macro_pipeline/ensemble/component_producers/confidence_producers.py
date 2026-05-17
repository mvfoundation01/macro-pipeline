"""L7 D3 — Confidence component producers (Vision §4 BINDING).

Three confidence component slots were placeholder at L6-I:
- data_quality (weight 0.25)
- model_agreement (weight 0.25)
- regime_stability (weight 0.20)

All three replaced with producer-backed values at L7. Each producer
returns a float in [0, 1]; ConfidenceComponents __post_init__
validates the range invariant.

Producer design discipline:
- Pure functions (no I/O, no global state, deterministic given inputs)
- Finite-checked inputs/outputs (AP-AUTH per L6-I D1)
- Clear fallback semantics (defined output when upstream signal missing)
- Documented signal source for each producer
"""
from __future__ import annotations

import math
import statistics
from typing import Optional, Tuple

from macro_pipeline.ensemble.model_signals import ModelSignal
from macro_pipeline.ensemble.rcf import ReferenceClass


def produce_data_quality(
    *,
    indicator_coverage_ratio: float = 1.0,
    vintage_age_days: int = 0,
    outlier_count: int = 0,
    missing_data_ratio: float = 0.0,
) -> float:
    """L7 D3 — Vision §4 ``data_quality`` confidence component producer.

    Composite quality score across four sub-signals:
      - ``indicator_coverage_ratio``: fraction of expected indicators
        present at forecast time (1.0 = complete).
      - ``vintage_age_days``: days since most-recent indicator vintage
        (0 = fresh; degrades after 30 days).
      - ``outlier_count``: count of indicators flagged as outliers in
        validation; each outlier subtracts 0.05.
      - ``missing_data_ratio``: fraction of expected data points missing
        (0.0 = complete).

    Composite formula::

        coverage_term     = indicator_coverage_ratio
        vintage_term      = max(0, 1 - vintage_age_days / 30)
        outlier_term      = max(0, 1 - 0.05 * outlier_count)
        missing_term      = 1 - missing_data_ratio
        score             = 0.40 * coverage_term + 0.30 * vintage_term
                          + 0.20 * outlier_term + 0.10 * missing_term

    Clamped to [0, 1].

    Defaults: all sub-signals at "perfect" values → score = 1.0.
    Callers from L8a UI / future producers will supply real values.

    Parameters
    ----------
    indicator_coverage_ratio
        Fraction in [0, 1]; 1.0 = all expected indicators present.
    vintage_age_days
        Non-negative integer; 0 = fresh.
    outlier_count
        Non-negative integer.
    missing_data_ratio
        Fraction in [0, 1]; 0.0 = no missing data.

    Returns
    -------
    float
        Data quality score in [0, 1].

    Raises
    ------
    ValueError
        Any input non-finite or out of valid range.
    """
    # Input validation (finite + range).
    if not math.isfinite(indicator_coverage_ratio):
        raise ValueError(
            f"indicator_coverage_ratio must be finite; got "
            f"{indicator_coverage_ratio!r}"
        )
    if not (0.0 <= indicator_coverage_ratio <= 1.0):
        raise ValueError(
            f"indicator_coverage_ratio must be in [0, 1]; got "
            f"{indicator_coverage_ratio}"
        )
    if not isinstance(vintage_age_days, int) or isinstance(vintage_age_days, bool):
        raise TypeError(
            f"vintage_age_days must be int; got "
            f"{type(vintage_age_days).__name__}"
        )
    if vintage_age_days < 0:
        raise ValueError(
            f"vintage_age_days must be non-negative; got "
            f"{vintage_age_days}"
        )
    if not isinstance(outlier_count, int) or isinstance(outlier_count, bool):
        raise TypeError(
            f"outlier_count must be int; got "
            f"{type(outlier_count).__name__}"
        )
    if outlier_count < 0:
        raise ValueError(
            f"outlier_count must be non-negative; got {outlier_count}"
        )
    if not math.isfinite(missing_data_ratio):
        raise ValueError(
            f"missing_data_ratio must be finite; got "
            f"{missing_data_ratio!r}"
        )
    if not (0.0 <= missing_data_ratio <= 1.0):
        raise ValueError(
            f"missing_data_ratio must be in [0, 1]; got "
            f"{missing_data_ratio}"
        )

    coverage_term = indicator_coverage_ratio
    vintage_term = max(0.0, 1.0 - vintage_age_days / 30.0)
    outlier_term = max(0.0, 1.0 - 0.05 * outlier_count)
    missing_term = 1.0 - missing_data_ratio

    score = (
        0.40 * coverage_term
        + 0.30 * vintage_term
        + 0.20 * outlier_term
        + 0.10 * missing_term
    )
    return max(0.0, min(1.0, score))


def produce_model_agreement(
    signals: Tuple[ModelSignal, ...],
) -> float:
    """L7 D3 — Vision §4 ``model_agreement`` producer from 11-model ensemble.

    Computes proportion of signals within plus/minus 1 sample-stdev of the
    weighted-mean point estimate. High agreement (signals tightly clustered)
    → high score; low agreement (dispersion across models) → low score.

    Formula::

        weighted_mean   = sum(s.weight * s.point_estimate_annualized)
        deviations      = [|s.point_estimate - weighted_mean| for s in signals]
        sigma_proxy     = sample-stdev of point_estimates (or 0 when n=1)
        agreement_count = count of signals within plus/minus sigma_proxy
        score           = agreement_count / len(signals)

    When all signals are placeholder-equal (L6-I default wrapper produces
    11 same-valued signals): sigma_proxy = 0, all signals within 0 of
    mean → score = 1.0 (perfect agreement; appropriate for the
    placeholder case).

    Parameters
    ----------
    signals
        Tuple of ``ModelSignal`` instances at a single horizon.

    Returns
    -------
    float
        Agreement score in [0, 1].

    Raises
    ------
    ValueError
        If signals empty or contains non-finite point estimates.
    """
    if not signals:
        raise ValueError("signals must be non-empty")
    point_estimates = [s.point_estimate_annualized for s in signals]
    weights = [s.weight for s in signals]
    for pe in point_estimates:
        if not math.isfinite(pe):
            raise ValueError(f"signal point_estimate must be finite; got {pe!r}")
    weight_sum = sum(weights)
    if weight_sum <= 0 or not math.isfinite(weight_sum):
        raise ValueError(
            f"signal weights sum must be positive + finite; got {weight_sum!r}"
        )
    weighted_mean = (
        sum(pe * w for pe, w in zip(point_estimates, weights)) / weight_sum
    )
    if len(point_estimates) == 1:
        sigma_proxy = 0.0
    else:
        sigma_proxy = statistics.stdev(point_estimates)
    if sigma_proxy == 0.0:
        # All identical → perfect agreement.
        return 1.0
    agreement_count = sum(
        1 for pe in point_estimates
        if abs(pe - weighted_mean) <= sigma_proxy
    )
    return agreement_count / len(point_estimates)


def produce_regime_stability(
    reference_class: Optional[ReferenceClass],
) -> float:
    """L7 D3 — Vision §4 ``regime_stability`` producer from RCF L6-J output.

    Uses ``ReferenceClass.mean_similarity_top_k`` as regime-stability
    proxy: high top-k analog similarity implies current regime closely
    resembles historical analogs, hence "stable" in the institutional
    sense (analogs are interpretable + reference shrinkage is reliable).

    L6-J ``reference_class_ood`` flag triggers conservative score
    (0.3 instead of derived value) because OOD by definition means
    unstable regime.

    Sample boundary violation also degrades the score by 0.1 (analogs
    from pre-Fed era are less applicable to current regime).

    Formula::

        if reference_class is None: return 0.5 (neutral; no info)
        if reference_class.reference_class_ood: return 0.3
        base_score = reference_class.mean_similarity_top_k (clamped to [0, 1])
        if reference_class.sample_boundary_violation:
            base_score -= 0.1
        return clamp(base_score, 0, 1)

    Parameters
    ----------
    reference_class
        Optional ``ReferenceClass`` from L6-E RCF (with L6-J OOD fields).
        ``None`` returns 0.5 (neutral).

    Returns
    -------
    float
        Regime stability score in [0, 1].
    """
    if reference_class is None:
        return 0.5
    if reference_class.reference_class_ood:
        return 0.3
    base_score = max(0.0, min(1.0, reference_class.mean_similarity_top_k))
    if reference_class.sample_boundary_violation:
        base_score = max(0.0, base_score - 0.1)
    return base_score
