"""Bayesian confidence + conviction computation (L6-G refinement).

Per Strategic L6-G inline pre-flight 2026-05-15. Replaces the L6-F
placeholder heuristic for confidence + conviction with a tractable
Bayesian computation per Vision v2.0 §4 (Triple Probability
Decomposition) + Vision §10 (Sample Size Honesty) + L6-E
``ReferenceClass.mean_similarity`` as evidence-quality weight.

L6-G uses tractable Bayesian subset
------------------------------------
Confidence formula::

    similarity_quality   = max(0, reference_class.mean_similarity)
                           if reference_class else DEFAULT_SIMILARITY_QUALITY
    posterior_precision  = n_eff + KAPPA_EVIDENCE
    evidence_weight      = (similarity_quality * n_eff) / posterior_precision
    confidence_uncapped  = 0.5 + 0.4 * evidence_weight  # range [0.5, 0.9]

Boundary behaviour:

  - ``n_eff == 0``                 → evidence_weight = 0 → confidence = 0.5
                                     (pure prior; no evidence)
  - ``n_eff → infinity``           → evidence_weight → similarity_quality
                                     → confidence → 0.5 + 0.4 * similarity_quality
  - ``similarity_quality == 1.0`` plus large ``n_eff``
                                   → confidence → 0.9 (max evidence-driven value)
  - ``reference_class is None``    → similarity_quality = 0.5 (neutral default)
  - ``mean_similarity < 0``        → clamped to 0 (evidence_weight floor)

Conviction formula (Vision §4 simplified subset)
------------------------------------------------
Vision §4 specifies a ten-component conviction formula (expected return
attractiveness + asymmetry + model agreement + valuation support +
trend confirmation + liquidity support minus tail-risk penalty minus
crowding penalty minus policy uncertainty penalty minus forecast decay
penalty). L6-G adopts a tractable subset suitable for the ensemble
aggregator's current input scope::

    conviction_base = 1.0 + 9.0 * confidence  # linear [1, 10]
    if n_eff < SAMPLE_SIZE_PENALTY_THRESHOLD:
        conviction_base *= SAMPLE_SIZE_PENALTY_FACTOR
    if (reference_class is not None
            and reference_class.mean_similarity < WEAK_ANALOG_THRESHOLD):
        conviction_base *= WEAK_ANALOG_PENALTY_FACTOR
    clamp to [CONVICTION_MIN, CONVICTION_MAX] = [1.0, 10.0]

The full ten-component formula is deferred. R7 ChatGPT 5.5 methodology
review (dispatched at L6-F ACCEPT) explicitly anticipates this scope
question (R7 invocation question five); the explicit subset choice +
deferral path are documented here for reviewer audit.

Cap discipline (Standing Order #9 + Vision §10) is UNCHANGED
------------------------------------------------------------
``compute_bayesian_confidence`` returns an UNCAPPED confidence value;
the Standing-Order-#9 cap discipline is enforced separately by the
existing two defense-in-depth layers:

  Layer 1  ``TripleDecomposition.__post_init__``  (L6-B; construction-time)
  Layer 2  ``enforce_confidence_caps``            (L6-D; forecast-time)

Both layers continue to fire on cap violations. The aggregator
(``aggregate_ensemble`` in ``aggregator.py``) applies the horizon-
conditional cap between the Bayesian compute and the
``TripleDecomposition`` construction; the L6-F third-instance defense-
in-depth pattern is preserved.
"""
from __future__ import annotations

from typing import Optional

from macro_pipeline.ensemble.rcf import ReferenceClass

# Posterior weight scale (per Strategic PD9).
KAPPA_EVIDENCE = 10

# Neutral prior (Vision §4 BINDING starting point pre-evidence).
CONFIDENCE_PRIOR = 0.5

# Maximum evidence-driven confidence (floor on uncertainty; never absolute).
MAX_EVIDENCE_CONFIDENCE = 0.99

# Default similarity quality when reference_class is None (moderate).
DEFAULT_SIMILARITY_QUALITY = 0.5

# Conviction-formula penalty thresholds (Vision §4 simplified subset).
SAMPLE_SIZE_PENALTY_THRESHOLD = 30
WEAK_ANALOG_THRESHOLD = 0.3
SAMPLE_SIZE_PENALTY_FACTOR = 0.8
WEAK_ANALOG_PENALTY_FACTOR = 0.7

# Conviction range bounds (Vision §4).
CONVICTION_MIN = 1.0
CONVICTION_MAX = 10.0

# Supported horizons (mirror aggregator + L6-B).
SUPPORTED_HORIZONS = (1, 3, 5, 10)


def compute_bayesian_confidence(
    point_estimate: float,
    n_eff: int,
    reference_class: Optional[ReferenceClass],
    regime_stratified: bool,
    horizon: int,
) -> float:
    """Compute Bayesian confidence per Vision §4 + L6-E reference class.

    Returns an UNCAPPED confidence value in [0.0, MAX_EVIDENCE_CONFIDENCE].
    The Standing Order #9 + Vision §10 caps are applied separately by
    the aggregator pipeline (TripleDecomposition __post_init__ +
    enforce_confidence_caps); this function does NOT apply caps.

    Parameters
    ----------
    point_estimate
        Forecast point estimate. NOT used in the L6-G confidence
        computation directly; reserved for future Bayesian refinement
        that may use the point-estimate magnitude to weight evidence.
    n_eff
        Effective sample size (non-negative integer).
    reference_class
        Optional ``ReferenceClass`` from L6-E. When provided,
        ``mean_similarity`` (clamped to non-negative) is used as the
        evidence-quality weight. When ``None``,
        ``DEFAULT_SIMILARITY_QUALITY = 0.5`` is used.
    regime_stratified
        Forecast regime-stratification flag. Reserved for future
        regime-conditional confidence variation; not used in the
        L6-G formula directly (caps applied externally).
    horizon
        Forecast horizon in years; must be in ``SUPPORTED_HORIZONS``.

    Returns
    -------
    float
        UNCAPPED confidence in [0.0, MAX_EVIDENCE_CONFIDENCE].

    Raises
    ------
    ValueError
        If ``n_eff < 0`` or ``horizon`` not in supported set.
    """
    if n_eff < 0:
        raise ValueError(f"n_eff must be non-negative; got {n_eff}")
    if horizon not in SUPPORTED_HORIZONS:
        raise ValueError(
            f"horizon {horizon} not in {sorted(SUPPORTED_HORIZONS)}"
        )

    if reference_class is not None:
        similarity_quality = max(0.0, reference_class.mean_similarity)
    else:
        similarity_quality = DEFAULT_SIMILARITY_QUALITY

    posterior_precision = n_eff + KAPPA_EVIDENCE
    evidence_weight = (similarity_quality * n_eff) / posterior_precision

    confidence_uncapped = CONFIDENCE_PRIOR + 0.4 * evidence_weight

    # Floor + ceiling (never below 0; never above MAX_EVIDENCE_CONFIDENCE).
    return min(max(confidence_uncapped, 0.0), MAX_EVIDENCE_CONFIDENCE)


def compute_conviction_score(
    confidence: float,
    reference_class: Optional[ReferenceClass],
    n_eff: int,
) -> float:
    """Compute conviction score per Vision §4 simplified subset.

    L6-G applies the Vision §4 conviction concept with a tractable
    subset: linear scaling from confidence plus two penalties (sample
    size + weak analog). Full ten-component formula deferred (see
    module docstring for R7 ChatGPT review anticipation).

    Parameters
    ----------
    confidence
        Confidence value in [0.0, 1.0].
    reference_class
        Optional ``ReferenceClass``. When provided AND
        ``mean_similarity < WEAK_ANALOG_THRESHOLD``, the weak-analog
        penalty applies.
    n_eff
        Effective sample size. When ``n_eff < SAMPLE_SIZE_PENALTY_THRESHOLD``,
        the sample-size penalty applies.

    Returns
    -------
    float
        Conviction in [CONVICTION_MIN, CONVICTION_MAX] = [1.0, 10.0].

    Raises
    ------
    ValueError
        If ``confidence`` outside [0, 1] or ``n_eff < 0``.
    """
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"confidence {confidence} outside [0, 1]")
    if n_eff < 0:
        raise ValueError(f"n_eff must be non-negative; got {n_eff}")

    # Linear scaling [1, 10].
    conviction_base = 1.0 + 9.0 * confidence

    # Sample size penalty (Vision §10 N_eff sensitivity).
    if n_eff < SAMPLE_SIZE_PENALTY_THRESHOLD:
        conviction_base *= SAMPLE_SIZE_PENALTY_FACTOR

    # Weak analog penalty (Vision §6 reference class quality gate).
    if (
        reference_class is not None
        and reference_class.mean_similarity < WEAK_ANALOG_THRESHOLD
    ):
        conviction_base *= WEAK_ANALOG_PENALTY_FACTOR

    # Clamp to Vision §4 conviction range.
    return float(
        min(max(conviction_base, CONVICTION_MIN), CONVICTION_MAX)
    )
