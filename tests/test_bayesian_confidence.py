"""Layer 6-G — tests for ``macro_pipeline.ensemble.bayesian_confidence``.

Spec ref: Strategic L6-G inline pre-flight (post-L6-F 2026-05-15) §4 Step 7.
Bayesian confidence + conviction computation per Vision §4 + L6-E
ReferenceClass.mean_similarity evidence weight. Tractable subset
(documented L6-G scope; full Vision §4 ten-component conviction
formula deferred).

Strategic-ratified relaxed NEG floor: 40% for Bayesian computation
modules (vs the project-standard 50%). Rationale: Bayesian computation
has more POS-inv test surface (boundary conditions verify mathematical
behaviour, not error rejection); strict 50% would force diluted NEG
tests rather than meaningful boundary verification.

Test inventory (NEG-flavor >= 40% per Strategic L6-G PD15 + §4 §7):
   1. POS         test_bayesian_confidence_zero_n_eff_returns_prior
   2. POS-inv     test_bayesian_confidence_large_n_eff_approaches_evidence
   3. POS-inv     test_bayesian_confidence_high_similarity_increases
   4. POS-inv     test_bayesian_confidence_negative_similarity_clamped
   5. POS         test_bayesian_confidence_no_reference_class_defaults_quality
   6. NEG         test_bayesian_confidence_negative_n_eff_raises
   7. NEG         test_bayesian_confidence_invalid_horizon_raises
   8. NEG         test_bayesian_confidence_horizon_below_one_raises
   9. POS-inv     test_conviction_linear_scaling
  10. POS-inv     test_conviction_low_n_eff_penalty
  11. POS-inv     test_conviction_weak_analog_penalty
  12. POS         test_conviction_no_reference_class_no_analog_penalty
  13. NEG         test_conviction_invalid_confidence_below_zero
  14. NEG         test_conviction_invalid_confidence_above_one
  15. NEG         test_conviction_negative_n_eff_raises

NEG count: 6, 7, 8, 13, 14, 15 = 6 NEG.
POS / POS-inv count: 1, 2, 3, 4, 5, 9, 10, 11, 12 = 9.
NEG floor: 6/15 = 40% — meets Strategic-ratified relaxed floor.
"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.ensemble.bayesian_confidence import (
    CONFIDENCE_PRIOR,
    DEFAULT_SIMILARITY_QUALITY,
    KAPPA_EVIDENCE,
    MAX_EVIDENCE_CONFIDENCE,
    SAMPLE_SIZE_PENALTY_FACTOR,
    SAMPLE_SIZE_PENALTY_THRESHOLD,
    WEAK_ANALOG_PENALTY_FACTOR,
    WEAK_ANALOG_THRESHOLD,
    compute_bayesian_confidence,
    compute_conviction_score,
)
from macro_pipeline.ensemble.rcf import MacroStateVector, ReferenceClass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ref_class(mean_similarity: float, n_neighbors: int = 1) -> ReferenceClass:
    """Build a ReferenceClass with controllable mean_similarity."""
    query = MacroStateVector(
        cape_z=0.0,
        yield_curve_z=0.0,
        lei_z=0.0,
        credit_spread_z=0.0,
        sentiment_z=0.0,
        breadth_z=0.0,
        volatility_z=0.0,
        concentration_z=0.0,
    )
    ts = pd.Timestamp("2000-01-01")
    neighbors = tuple((ts + pd.Timedelta(days=i), mean_similarity) for i in range(n_neighbors))
    return ReferenceClass(
        neighbors=neighbors,
        n_neighbors=n_neighbors,
        mean_similarity=mean_similarity,
        query_state=query,
    )


# ===========================================================================
# Test 1 — POS — n_eff=0 returns prior (no evidence)
# ===========================================================================


def test_bayesian_confidence_zero_n_eff_returns_prior() -> None:
    """POS: n_eff=0 → evidence_weight=0 → confidence == CONFIDENCE_PRIOR (0.5)."""
    result = compute_bayesian_confidence(
        point_estimate=0.05,
        n_eff=0,
        reference_class=_make_ref_class(0.9),
        regime_stratified=False,
        horizon=5,
    )
    assert result == pytest.approx(CONFIDENCE_PRIOR)
    assert result == pytest.approx(0.5)


# ===========================================================================
# Test 2 — POS-inv — large n_eff approaches 0.5 + 0.4 * similarity_quality
# ===========================================================================


def test_bayesian_confidence_large_n_eff_approaches_evidence() -> None:
    """POS-inv: as n_eff → infinity, evidence_weight → similarity_quality;
    confidence → 0.5 + 0.4 * similarity_quality."""
    similarity = 0.9
    result = compute_bayesian_confidence(
        point_estimate=0.05,
        n_eff=100_000,  # n_eff >> kappa (10)
        reference_class=_make_ref_class(similarity),
        regime_stratified=False,
        horizon=10,
    )
    # asymptotic value
    expected_asymptote = 0.5 + 0.4 * similarity
    assert abs(result - expected_asymptote) < 0.001


# ===========================================================================
# Test 3 — POS-inv — high similarity increases confidence
# ===========================================================================


def test_bayesian_confidence_high_similarity_increases() -> None:
    """POS-inv: higher mean_similarity yields higher confidence (monotonic)."""
    low_sim = compute_bayesian_confidence(
        point_estimate=0.05,
        n_eff=100,
        reference_class=_make_ref_class(0.2),
        regime_stratified=False,
        horizon=5,
    )
    high_sim = compute_bayesian_confidence(
        point_estimate=0.05,
        n_eff=100,
        reference_class=_make_ref_class(0.9),
        regime_stratified=False,
        horizon=5,
    )
    assert high_sim > low_sim


# ===========================================================================
# Test 4 — POS-inv — negative mean_similarity clamped to zero
# ===========================================================================


def test_bayesian_confidence_negative_similarity_clamped() -> None:
    """POS-inv: mean_similarity < 0 clamped to 0 → confidence == prior."""
    # Build ReferenceClass with negative similarity (allowed per L6-E
    # invariant which permits mean_similarity in [-1, 1])
    ref = _make_ref_class(-0.5)
    result = compute_bayesian_confidence(
        point_estimate=0.05,
        n_eff=100,
        reference_class=ref,
        regime_stratified=False,
        horizon=5,
    )
    # similarity clamped to 0 → evidence_weight=0 → confidence = prior
    assert result == pytest.approx(CONFIDENCE_PRIOR)


# ===========================================================================
# Test 5 — POS — None reference_class uses DEFAULT_SIMILARITY_QUALITY
# ===========================================================================


def test_bayesian_confidence_no_reference_class_defaults_quality() -> None:
    """POS: reference_class=None → similarity_quality = DEFAULT (0.5)."""
    result = compute_bayesian_confidence(
        point_estimate=0.05,
        n_eff=100,
        reference_class=None,
        regime_stratified=False,
        horizon=5,
    )
    # evidence_weight = (0.5 * 100) / (100 + 10) ≈ 0.4545
    # confidence = 0.5 + 0.4 * 0.4545 ≈ 0.6818
    expected_evidence_weight = (DEFAULT_SIMILARITY_QUALITY * 100) / (100 + KAPPA_EVIDENCE)
    expected_confidence = CONFIDENCE_PRIOR + 0.4 * expected_evidence_weight
    assert result == pytest.approx(expected_confidence)


# ===========================================================================
# Test 6 — NEG — negative n_eff raises
# ===========================================================================


def test_bayesian_confidence_negative_n_eff_raises() -> None:
    """NEG: n_eff < 0 raises ValueError."""
    with pytest.raises(ValueError, match="n_eff must be non-negative"):
        compute_bayesian_confidence(
            point_estimate=0.05,
            n_eff=-1,
            reference_class=None,
            regime_stratified=False,
            horizon=5,
        )


# ===========================================================================
# Test 7 — NEG — invalid horizon raises
# ===========================================================================


def test_bayesian_confidence_invalid_horizon_raises() -> None:
    """NEG: horizon not in (1, 3, 5, 10) raises ValueError."""
    with pytest.raises(ValueError, match="horizon"):
        compute_bayesian_confidence(
            point_estimate=0.05,
            n_eff=100,
            reference_class=None,
            regime_stratified=False,
            horizon=7,
        )


# ===========================================================================
# Test 8 — NEG — horizon below 1 raises
# ===========================================================================


def test_bayesian_confidence_horizon_below_one_raises() -> None:
    """NEG: horizon < 1 raises ValueError (distinct path from generic invalid)."""
    with pytest.raises(ValueError, match="horizon"):
        compute_bayesian_confidence(
            point_estimate=0.05,
            n_eff=100,
            reference_class=None,
            regime_stratified=False,
            horizon=0,
        )
    with pytest.raises(ValueError, match="horizon"):
        compute_bayesian_confidence(
            point_estimate=0.05,
            n_eff=100,
            reference_class=None,
            regime_stratified=False,
            horizon=-5,
        )


# ===========================================================================
# Test 9 — POS-inv — conviction linear scaling
# ===========================================================================


def test_conviction_linear_scaling() -> None:
    """POS-inv: with n_eff>=30 + no weak_analog penalty, conviction is
    linear in confidence: 1.0 + 9.0 * confidence."""
    # No reference_class avoids weak_analog penalty
    # n_eff >= 30 avoids sample_size penalty
    result = compute_conviction_score(
        confidence=0.5,
        reference_class=None,
        n_eff=100,
    )
    assert result == pytest.approx(1.0 + 9.0 * 0.5)
    assert result == pytest.approx(5.5)

    result_high = compute_conviction_score(
        confidence=0.8,
        reference_class=None,
        n_eff=100,
    )
    assert result_high == pytest.approx(1.0 + 9.0 * 0.8)
    assert result_high == pytest.approx(8.2)


# ===========================================================================
# Test 10 — POS-inv — low n_eff triggers sample size penalty
# ===========================================================================


def test_conviction_low_n_eff_penalty() -> None:
    """POS-inv: n_eff < SAMPLE_SIZE_PENALTY_THRESHOLD applies penalty factor."""
    # confidence=0.5, n_eff=20 → base=5.5 * 0.8 = 4.4
    result = compute_conviction_score(
        confidence=0.5,
        reference_class=None,
        n_eff=20,  # < 30
    )
    expected = 1.0 + 9.0 * 0.5
    expected *= SAMPLE_SIZE_PENALTY_FACTOR
    assert result == pytest.approx(expected)
    # n_eff at boundary 29 (still <30) applies penalty
    result_boundary = compute_conviction_score(
        confidence=0.5,
        reference_class=None,
        n_eff=29,
    )
    assert result_boundary == pytest.approx(expected)
    # n_eff at boundary 30 does NOT apply penalty (>= threshold)
    result_no_penalty = compute_conviction_score(
        confidence=0.5,
        reference_class=None,
        n_eff=30,
    )
    assert result_no_penalty == pytest.approx(1.0 + 9.0 * 0.5)


# ===========================================================================
# Test 11 — POS-inv — weak analog triggers penalty
# ===========================================================================


def test_conviction_weak_analog_penalty() -> None:
    """POS-inv: reference_class.mean_similarity < WEAK_ANALOG_THRESHOLD
    applies penalty factor."""
    ref_weak = _make_ref_class(0.2)  # < 0.3 threshold
    result = compute_conviction_score(
        confidence=0.5,
        reference_class=ref_weak,
        n_eff=100,
    )
    expected = 1.0 + 9.0 * 0.5
    expected *= WEAK_ANALOG_PENALTY_FACTOR
    assert result == pytest.approx(expected)
    # Strong analog (>= 0.3) NO penalty
    ref_strong = _make_ref_class(0.7)
    result_strong = compute_conviction_score(
        confidence=0.5,
        reference_class=ref_strong,
        n_eff=100,
    )
    assert result_strong == pytest.approx(1.0 + 9.0 * 0.5)


# ===========================================================================
# Test 12 — POS — no reference_class means no analog penalty
# ===========================================================================


def test_conviction_no_reference_class_no_analog_penalty() -> None:
    """POS: reference_class=None → weak_analog penalty path skipped."""
    # confidence=0.5, n_eff=100 (above sample size threshold) → 5.5
    result = compute_conviction_score(
        confidence=0.5,
        reference_class=None,
        n_eff=100,
    )
    assert result == pytest.approx(5.5)


# ===========================================================================
# Test 13 — NEG — confidence below zero raises
# ===========================================================================


def test_conviction_invalid_confidence_below_zero() -> None:
    """NEG: confidence < 0 raises ValueError."""
    with pytest.raises(ValueError, match="confidence"):
        compute_conviction_score(
            confidence=-0.1,
            reference_class=None,
            n_eff=100,
        )


# ===========================================================================
# Test 14 — NEG — confidence above 1 raises
# ===========================================================================


def test_conviction_invalid_confidence_above_one() -> None:
    """NEG: confidence > 1.0 raises ValueError."""
    with pytest.raises(ValueError, match="confidence"):
        compute_conviction_score(
            confidence=1.5,
            reference_class=None,
            n_eff=100,
        )


# ===========================================================================
# Test 15 — NEG — conviction negative n_eff raises
# ===========================================================================


def test_conviction_negative_n_eff_raises() -> None:
    """NEG: n_eff < 0 raises ValueError."""
    with pytest.raises(ValueError, match="n_eff must be non-negative"):
        compute_conviction_score(
            confidence=0.5,
            reference_class=None,
            n_eff=-1,
        )
