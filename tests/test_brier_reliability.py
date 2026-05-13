"""Layer 5-C — tests for ``macro_pipeline.analysis.brier_reliability``.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.C.5 (eight tests;
four NEG / four POS = 50% NEG floor). Test #4 is parametrized × 3
score_types per spec §3.3 (CRPS / CDRS / RETURN_POSITIVE).

Test inventory (mirrors §5.C.5 row order)
  1  POS         test_brier_score_matches_formula_on_synthetic_input
  2  POS-inv     test_murphy_decomposition_algebra_to_1e_neg_10
  3  POS         test_climatology_baseline_matches_constant_prior_brier
  4  POS         test_brier_improvement_positive_post_isotonic_per_horizon_per_score_type
  5  NEG         test_rejects_calibrated_probability_outside_zero_one
  6  NEG         test_rejects_non_binary_forward_returns
  7  NEG         test_rejects_horizon_keys_mismatch_between_p_and_y
  8  NEG         test_rejects_n_bins_below_2
"""
from __future__ import annotations

import warnings

import numpy as np
import pytest

from macro_pipeline.analysis.brier_reliability import (
    BrierDecomposition,
    compute_brier_per_horizon,
)


# ---------------------------------------------------------------------------
# Test #1 — POS
# ---------------------------------------------------------------------------
def test_brier_score_matches_formula_on_synthetic_input():
    """Spec §5.C.5 test #1: ``p=[0.2, 0.7, 0.5]``, ``y=[0, 1, 1]`` ⇒
    ``brier == ((0.2)² + (0.3)² + (0.5)²)/3 = 0.12666...``."""
    p = {"H": np.array([0.2, 0.7, 0.5])}
    y = {"H": np.array([0, 1, 1])}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # bin-underpopulation warning expected at n=3
        r = compute_brier_per_horizon(p, y, bootstrap_iterations=5)
    expected = (0.04 + 0.09 + 0.25) / 3.0
    assert r["H"].brier_score == pytest.approx(expected, abs=1e-12), (
        f"Brier={r['H'].brier_score}, expected {expected}"
    )


# ---------------------------------------------------------------------------
# Test #2 — POS-invariant
# ---------------------------------------------------------------------------
def test_murphy_decomposition_algebra_to_1e_neg_10():
    """Spec §5.C.5 test #2: ``brier == reliability − resolution +
    uncertainty`` to ``1e-10``.

    The Murphy 1973 identity is exact only when each obs's individual
    ``p_i`` equals its bin-mean ``p̄_b`` (no within-bin probability
    variance). Two fixture options satisfy this: (a) each obs in its
    own bin (test #1 fixture, three obs in three different bins);
    (b) all p values exactly at bin centers regardless of n. This
    test exercises (b) at n=1000 for breadth.
    """
    rng = np.random.default_rng(11)
    n = 1000
    bin_centers = (np.arange(10) + 0.5) / 10.0
    p_idx = rng.integers(0, 10, size=n)
    p_arr = bin_centers[p_idx]
    y_arr = (rng.uniform(0, 1, n) < p_arr).astype(int)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = compute_brier_per_horizon(
            {"H": p_arr}, {"H": y_arr}, bootstrap_iterations=10,
        )["H"]
    lhs = r.brier_score
    rhs = r.reliability_term - r.resolution_term + r.uncertainty_term
    assert abs(lhs - rhs) < 1e-10, (
        f"Murphy identity violation: |brier - (R-Res+U)| = {abs(lhs - rhs):.3e} "
        f"(brier={lhs}, R={r.reliability_term}, Res={r.resolution_term}, "
        f"U={r.uncertainty_term})"
    )


# ---------------------------------------------------------------------------
# Test #3 — POS
# ---------------------------------------------------------------------------
def test_climatology_baseline_matches_constant_prior_brier():
    """Spec §5.C.5 test #3 + §5.C.1.1: ``brier_climatology ==
    Brier(predicted=ȳ, actual=y)`` per horizon (equivalently
    ``ȳ × (1 − ȳ)`` by closed form)."""
    rng = np.random.default_rng(17)
    n = 500
    p_arr = rng.uniform(0.1, 0.9, n)
    y_arr = (rng.uniform(0, 1, n) < 0.4).astype(int)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = compute_brier_per_horizon(
            {"H": p_arr}, {"H": y_arr}, bootstrap_iterations=10,
        )["H"]
    y_mean = float(y_arr.mean())
    expected_climatology_constant = float(
        np.mean((np.full(n, y_mean) - y_arr) ** 2)
    )
    expected_closed_form = y_mean * (1.0 - y_mean)
    assert r.brier_climatology == pytest.approx(
        expected_constant_prior := expected_climatology_constant, abs=1e-12,
    )
    assert r.brier_climatology == pytest.approx(expected_closed_form, abs=1e-12)
    # Uncertainty term equals climatology by construction (spec §5.C.1.1).
    assert r.uncertainty_term == pytest.approx(r.brier_climatology, abs=1e-15)


# ---------------------------------------------------------------------------
# Test #4 — POS @ parametrize × 3 score_types
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("score_type", ["CRPS", "CDRS", "RETURN_POSITIVE"])
def test_brier_improvement_positive_post_isotonic_per_horizon_per_score_type(
    score_type: str,
):
    """Spec §5.C.5 test #4: for every (horizon, score_type) combination
    per §3.3 calibration target schema, ``brier_score < brier_climatology``
    (Gate 22 sub-criterion 3).

    Horizons per §3.3:
      * CRPS:            1Y only (NBER USREC 12M)
      * CDRS:            1Y / 3Y / 5Y / 10Y (one representative
                         threshold per horizon per Op-C-a)
      * RETURN_POSITIVE: 1Y / 3Y / 5Y / 10Y

    Fixture builds calibrated probabilities + binary labels with
    sharp signal (Bernoulli with p=calibrated_prob). The improvement
    invariant holds for any reasonable calibration → climatology
    asymmetry, which is what spec §5.C.6 criterion 3 requires.
    """
    if score_type == "CRPS":
        horizons = ("1Y",)
    else:
        horizons = ("1Y", "3Y", "5Y", "10Y")

    rng = np.random.default_rng(101)
    n = 500
    calibrated_probabilities: dict[str, np.ndarray] = {}
    forward_returns_binary: dict[str, np.ndarray] = {}
    for h in horizons:
        # Calibrated probabilities: smooth distribution across [0.1, 0.9].
        p_arr = np.clip(
            rng.beta(2.0, 2.0, n) * 0.8 + 0.1, 0.01, 0.99,
        )
        # Binary outcomes correlated with p (so the model beats climatology).
        y_arr = (rng.uniform(0, 1, n) < p_arr).astype(int)
        calibrated_probabilities[h] = p_arr
        forward_returns_binary[h] = y_arr

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = compute_brier_per_horizon(
            calibrated_probabilities, forward_returns_binary,
            bootstrap_iterations=20,
        )

    assert set(results.keys()) == set(horizons), (
        f"score_type={score_type}: expected horizons {sorted(horizons)}, "
        f"got {sorted(results.keys())}"
    )
    for h in horizons:
        assert results[h].brier_improvement > 0.0, (
            f"score_type={score_type}, horizon={h}: brier_improvement="
            f"{results[h].brier_improvement} should be > 0 "
            f"(brier={results[h].brier_score}, "
            f"climatology={results[h].brier_climatology})"
        )


# ---------------------------------------------------------------------------
# Test #5 — NEG
# ---------------------------------------------------------------------------
def test_rejects_calibrated_probability_outside_zero_one():
    """Spec §5.C.5 test #5: ``p=1.5`` raises ``ValueError``."""
    p = {"H": np.array([0.2, 1.5, 0.5])}
    y = {"H": np.array([0, 1, 1])}
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        compute_brier_per_horizon(p, y, bootstrap_iterations=5)


# ---------------------------------------------------------------------------
# Test #6 — NEG
# ---------------------------------------------------------------------------
def test_rejects_non_binary_forward_returns():
    """Spec §5.C.5 test #6: ``y=[0.5, 1, 0]`` raises
    ``ValueError(\"forward_returns_binary must be 0 or 1\")``."""
    p = {"H": np.array([0.2, 0.7, 0.5])}
    y = {"H": np.array([0.5, 1, 0])}
    with pytest.raises(ValueError, match=r"\{0, 1\}"):
        compute_brier_per_horizon(p, y, bootstrap_iterations=5)


# ---------------------------------------------------------------------------
# Test #7 — NEG
# ---------------------------------------------------------------------------
def test_rejects_horizon_keys_mismatch_between_p_and_y():
    """Spec §5.C.5 test #7: keys ``{1Y, 3Y}`` vs ``{1Y, 5Y}`` raises."""
    p = {"1Y": np.array([0.2, 0.7]), "3Y": np.array([0.3, 0.6])}
    y = {"1Y": np.array([0, 1]), "5Y": np.array([1, 0])}
    with pytest.raises(ValueError, match=r"horizon keys mismatch"):
        compute_brier_per_horizon(p, y, bootstrap_iterations=5)


# ---------------------------------------------------------------------------
# Test #8 — NEG
# ---------------------------------------------------------------------------
def test_rejects_n_bins_below_2():
    """Spec §5.C.5 test #8: ``n_bins=1`` raises
    ``ValueError(\"n_bins must be >= 2\")``."""
    p = {"H": np.array([0.2, 0.7, 0.5])}
    y = {"H": np.array([0, 1, 1])}
    with pytest.raises(ValueError, match=r"n_bins must be >= 2"):
        compute_brier_per_horizon(p, y, n_bins=1, bootstrap_iterations=5)
