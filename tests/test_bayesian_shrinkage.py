"""Layer 5-G — tests for ``macro_pipeline.models.bayesian_shrinkage``.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.G.5 (eight tests
v2; five NEG / three POS = 63% NEG per spec header; supersedes stale
§5.G.0 metadata "+6 / 67%" anchor per Strategic D-G-1 disposition
2026-05-13).

Test inventory (mirrors §5.G.5 row order):
  1   POS         test_K_HORIZON_matches_v2_backsolve_5_9_6_7_9_4_11_0
                  (v2 backsolve per S-4; closes ChatGPT v1 §E.3 /
                  L5-RISK-3)
  2   POS         test_DMS_priors_match_Q7_lock_6_5_pct_US_4_5_pct_global
  3   NEG         test_shrinkage_weight_horizon_dependent_AST_walk_audit
                  (Op-G-a runtime audit; Standing Order #4)
  4   NEG-inv     test_shrinkage_weight_asymptotic_zero_at_large_n
  5   NEG         test_rejects_negative_n_eff
  6   NEG         test_rejects_horizon_outside_1Y_3Y_5Y_10Y
  7   POS-inv     test_shrinkage_weight_matches_W_REF_TARGET_within_2_percentage_points_at_N_REF
                  (v2 NEW per S-4; closes ChatGPT §G.3 v2 proof test)
  8   POS         test_k_horizon_sensitivity_0_5x_1x_2x
                  (v2 NEW per S-4; closes ChatGPT §G.3 sensitivity)
"""
from __future__ import annotations

import inspect

import pytest

import macro_pipeline.models.bayesian_shrinkage as _shrinkage_mod
from macro_pipeline.models.bayesian_shrinkage import (
    DMS_PRIOR_REAL_ANNUALIZED_GLOBAL,
    DMS_PRIOR_REAL_ANNUALIZED_US,
    K_HORIZON,
    NOMINAL_SHRINKAGE_WEIGHTS_AT_REFERENCE_N,
    N_REF_NONOVERLAP,
    W_REF_TARGET,
    apply_shrinkage,
    compute_shrinkage_weight,
)


# ---------------------------------------------------------------------------
# Test #1 — POS (v2 amended per S-4)
# ---------------------------------------------------------------------------
def test_K_HORIZON_matches_v2_backsolve_5_9_6_7_9_4_11_0():
    """Spec §5.G.5 test #1 (v2 amended per S-4): ``K_HORIZON`` matches
    v2-backsolved values exactly; NOT v1 arithmetically inconsistent
    ``{180, 540, 900, 1800}`` (v1 produced w ≈ 61/93/98/99% at Fed-era
    n_eff instead of intended 5/15/30/50%; closes ChatGPT v1 §E.3 /
    L5-RISK-3)."""
    assert K_HORIZON == {
        "1Y": 5.9,
        "3Y": 6.7,
        "5Y": 9.4,
        "10Y": 11.0,
    }
    # Sanity check: NOT v1 inconsistent values.
    assert K_HORIZON["1Y"] != 180
    assert K_HORIZON["10Y"] != 1800


# ---------------------------------------------------------------------------
# Test #2 — POS
# ---------------------------------------------------------------------------
def test_DMS_priors_match_Q7_lock_6_5_pct_US_4_5_pct_global():
    """Spec §5.G.5 test #2 + §5.G.4 Q7 lock: DMS prior anchors."""
    assert DMS_PRIOR_REAL_ANNUALIZED_US == 0.065
    assert DMS_PRIOR_REAL_ANNUALIZED_GLOBAL == 0.045


# ---------------------------------------------------------------------------
# Test #3 — NEG (Standing Order #4; Op-G-a runtime audit)
# ---------------------------------------------------------------------------
def test_shrinkage_weight_horizon_dependent_AST_walk_audit():
    """Spec §5.G.5 test #3 — Standing Order #4 AST audit.

    Op-G-a (Strategic-approved 2026-05-13): the literal "AST walk over
    macro_pipeline/" for callers is vacuous truth at L5-G build time
    (no downstream consumer exists yet). The spec property the audit
    must verify is the horizon-dependent dispatch INSIDE
    ``compute_shrinkage_weight`` and the absence of a spurious constant
    ``0.30`` literal elsewhere in the module source (the only legitimate
    ``0.30`` usage is ``W_REF_TARGET["5Y"]``).
    """
    # POS leg: 4 distinct horizon values at reference n_eff prove
    # horizon-dependent dispatch (no single constant weight literal).
    weights = {
        h: compute_shrinkage_weight(N_REF_NONOVERLAP[h], h)
        for h in K_HORIZON.keys()
    }
    assert len(set(weights.values())) == 4, (
        f"Expected four distinct shrinkage weights across horizons; "
        f"got {weights}"
    )

    # NEG leg: module source contains no spurious ``0.30`` float
    # literal in code outside the spec-mandated dict entries. AST-based
    # check ignores docstring/comment text (where "0.30" may appear
    # legitimately in arithmetic-derivation documentation). The only
    # legitimate float-literal occurrences are the ``"5Y": 0.30`` entry
    # in ``W_REF_TARGET`` and the same in
    # ``NOMINAL_SHRINKAGE_WEIGHTS_AT_REFERENCE_N``.
    import ast as _ast
    source = inspect.getsource(_shrinkage_mod)
    tree = _ast.parse(source)
    constant_030_nodes = [
        node for node in _ast.walk(tree)
        if isinstance(node, _ast.Constant)
        and isinstance(node.value, float)
        and abs(node.value - 0.30) < 1e-12
    ]
    assert len(constant_030_nodes) <= 2, (
        f"Found {len(constant_030_nodes)} AST float-literal occurrences "
        "of 0.30 in bayesian_shrinkage source; expected <= 2 "
        "(W_REF_TARGET['5Y'] + NOMINAL_SHRINKAGE_WEIGHTS_AT_REFERENCE_N"
        "['5Y']). Any additional float-literal occurrence suggests a "
        "hard-coded shrinkage weight outside the v2-backsolved "
        "K_HORIZON discipline."
    )


# ---------------------------------------------------------------------------
# Test #4 — NEG-invariant
# ---------------------------------------------------------------------------
def test_shrinkage_weight_asymptotic_zero_at_large_n():
    """Spec §5.G.5 test #4: ``compute_shrinkage_weight(n=1e8, "10Y")
    < 0.001`` (asymptotic unbiasedness limit)."""
    big_n = int(1e8)
    w = compute_shrinkage_weight(big_n, "10Y")
    assert w < 0.001, (
        f"Asymptotic check failed: w(n={big_n}, 10Y) = {w} should be "
        "< 0.001 (k/(k+n) → 0 as n → ∞)"
    )
    # Also check w > 0 (not collapsed to zero arithmetic; remains positive).
    assert w > 0.0


# ---------------------------------------------------------------------------
# Test #5 — NEG
# ---------------------------------------------------------------------------
def test_rejects_negative_n_eff():
    """Spec §5.G.5 test #5: ``compute_shrinkage_weight(-1, "1Y")``
    raises ``ValueError``."""
    with pytest.raises(ValueError, match=r"n_eff_nonoverlap must be >= 0"):
        compute_shrinkage_weight(-1, "1Y")
    # Symmetric NEG check via apply_shrinkage (forwards the same error).
    with pytest.raises(ValueError, match=r"n_eff_nonoverlap must be >= 0"):
        apply_shrinkage(0.065, -5, "5Y")


# ---------------------------------------------------------------------------
# Test #6 — NEG
# ---------------------------------------------------------------------------
def test_rejects_horizon_outside_1Y_3Y_5Y_10Y():
    """Spec §5.G.5 test #6: ``compute_shrinkage_weight(100, "2Y")``
    raises ``ValueError``."""
    with pytest.raises(ValueError, match=r"horizon '2Y' not in"):
        compute_shrinkage_weight(100, "2Y")
    # Multiple invalid horizons reject.
    for bad_h in ("0Y", "15Y", "1y", "", "monthly"):
        with pytest.raises(ValueError, match=r"horizon"):
            compute_shrinkage_weight(50, bad_h)


# ---------------------------------------------------------------------------
# Test #7 — POS-invariant (v2 NEW per S-4)
# ---------------------------------------------------------------------------
def test_shrinkage_weight_matches_W_REF_TARGET_within_2_percentage_points_at_N_REF():
    """Spec §5.G.5 test #7 (v2 NEW per S-4): for each horizon h,
    ``compute_shrinkage_weight(N_REF_NONOVERLAP[h], h)`` is within
    ±2pp of ``W_REF_TARGET[h]``. Closes ChatGPT §G.3 v2 proof test
    requirement.

    Independent verification of the K_HORIZON v2 backsolve formula
    ``k_h = (w_ref / (1 - w_ref)) × n_ref``.
    """
    for h in W_REF_TARGET.keys():
        w = compute_shrinkage_weight(N_REF_NONOVERLAP[h], h)
        target = W_REF_TARGET[h]
        delta_pp = abs(w - target) * 100.0
        assert delta_pp < 2.0, (
            f"horizon={h}: w={w:.6f}, target={target:.2f}, "
            f"delta={delta_pp:.3f}pp (must be < 2pp per spec §5.G.5 "
            "test #7 ±2pp tolerance)"
        )

    # And the alias ``NOMINAL_SHRINKAGE_WEIGHTS_AT_REFERENCE_N`` equals
    # ``W_REF_TARGET`` by spec construction.
    assert NOMINAL_SHRINKAGE_WEIGHTS_AT_REFERENCE_N == W_REF_TARGET


# ---------------------------------------------------------------------------
# Test #8 — POS (v2 NEW per S-4)
# ---------------------------------------------------------------------------
def test_k_horizon_sensitivity_0_5x_1x_2x():
    """Spec §5.G.5 test #8 (v2 NEW per S-4): at each horizon, weight is
    monotone-increasing in k (so 0.5×k → lower w, 2×k → higher w at the
    same n_eff). Closes ChatGPT §G.3 sensitivity requirement."""
    for h in K_HORIZON.keys():
        n_ref = N_REF_NONOVERLAP[h]
        k_orig = K_HORIZON[h]
        # Manually compute w at scaled k_h values via the closed-form
        # formula (the spec function uses K_HORIZON[h] internally; we
        # exercise the sensitivity via the bare formula).
        w_05x = (0.5 * k_orig) / (0.5 * k_orig + n_ref)
        w_1x = k_orig / (k_orig + n_ref)
        w_2x = (2.0 * k_orig) / (2.0 * k_orig + n_ref)
        # Sanity: w_1x must match the function's own output.
        assert abs(w_1x - compute_shrinkage_weight(n_ref, h)) < 1e-12
        # Monotone in k.
        assert w_05x < w_1x < w_2x, (
            f"horizon={h}: sensitivity not monotone: "
            f"w(0.5k)={w_05x}, w(1k)={w_1x}, w(2k)={w_2x}"
        )
