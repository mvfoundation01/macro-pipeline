"""Layer 6-B — tests for ``macro_pipeline.ensemble.triple_decomposition``.

Spec ref: Strategic L6-B inline spec (Batch 1, post-L6-A 2026-05-15) §A.4.
Triple Probability Decomposition per Vision §4 BINDING; defense-in-depth
construction-time confidence cap layer (the 2nd layer is L6-D's
``enforce_confidence_caps`` helper).

Test inventory (NEG ratio >= 50% per AP-AUTH-53 discipline):
   1. POS         test_triple_decomp_basic_construction
   2. NEG         test_triple_decomp_probability_out_of_range
   3. NEG         test_triple_decomp_confidence_out_of_range
   4. NEG         test_triple_decomp_conviction_below_one
   5. NEG         test_triple_decomp_conviction_above_ten
   6. NEG         test_triple_decomp_invalid_horizon
   7. NEG strict  test_triple_decomp_10y_non_stratified_cap_violation
   8. NEG strict  test_triple_decomp_10y_regime_stratified_cap_violation
   9. POS         test_triple_decomp_10y_below_cap_passes
  10. POS         test_triple_decomp_1y_high_confidence_ok
  11. NEG-inv     test_triple_decomp_frozen

NEG count: 2, 3, 4, 5, 6, 7, 8, 11 = 8 NEG-flavor.
POS count: 1, 9, 10 = 3 POS.
NEG floor: 8/11 = 72.7% >= 50% required (AP-AUTH-53).
"""
from __future__ import annotations

import pytest

from macro_pipeline.ensemble.triple_decomposition import (
    CONFIDENCE_CAP_10Y_NON_STRATIFIED,
    CONFIDENCE_CAP_10Y_REGIME_STRATIFIED,
    TripleDecomposition,
)
from macro_pipeline.manual_input.validation import ConfidenceCapViolation


# ===========================================================================
# Test 1 — POS — basic construction
# ===========================================================================


def test_triple_decomp_basic_construction() -> None:
    """POS: valid TripleDecomposition constructs cleanly; fields preserved."""
    d = TripleDecomposition(
        probability=0.65,
        confidence=0.70,
        conviction=6.5,
        horizon=5,
        regime_stratified=False,
        binding_constraint="data quality + CAPE percentile",
    )
    assert d.probability == 0.65
    assert d.confidence == 0.70
    assert d.conviction == 6.5
    assert d.horizon == 5
    assert d.regime_stratified is False
    assert d.binding_constraint == "data quality + CAPE percentile"


# ===========================================================================
# Test 2 — NEG — probability out of range
# ===========================================================================


def test_triple_decomp_probability_out_of_range() -> None:
    """NEG: probability outside [0, 1] raises ValueError."""
    with pytest.raises(ValueError, match="probability"):
        TripleDecomposition(
            probability=1.5,
            confidence=0.5,
            conviction=5.0,
            horizon=1,
        )
    with pytest.raises(ValueError, match="probability"):
        TripleDecomposition(
            probability=-0.1,
            confidence=0.5,
            conviction=5.0,
            horizon=1,
        )


# ===========================================================================
# Test 3 — NEG — confidence out of range
# ===========================================================================


def test_triple_decomp_confidence_out_of_range() -> None:
    """NEG: confidence outside [0, 1] raises ValueError (range check
    happens BEFORE 10Y cap check; not a ConfidenceCapViolation)."""
    with pytest.raises(ValueError, match="confidence"):
        TripleDecomposition(
            probability=0.5,
            confidence=1.2,
            conviction=5.0,
            horizon=1,
        )
    with pytest.raises(ValueError, match="confidence"):
        TripleDecomposition(
            probability=0.5,
            confidence=-0.05,
            conviction=5.0,
            horizon=1,
        )


# ===========================================================================
# Test 4 — NEG — conviction below 1
# ===========================================================================


def test_triple_decomp_conviction_below_one() -> None:
    """NEG: conviction < 1.0 raises ValueError."""
    with pytest.raises(ValueError, match="conviction"):
        TripleDecomposition(
            probability=0.5,
            confidence=0.5,
            conviction=0.5,
            horizon=1,
        )


# ===========================================================================
# Test 5 — NEG — conviction above 10
# ===========================================================================


def test_triple_decomp_conviction_above_ten() -> None:
    """NEG: conviction > 10.0 raises ValueError."""
    with pytest.raises(ValueError, match="conviction"):
        TripleDecomposition(
            probability=0.5,
            confidence=0.5,
            conviction=10.5,
            horizon=1,
        )


# ===========================================================================
# Test 6 — NEG — invalid horizon
# ===========================================================================


def test_triple_decomp_invalid_horizon() -> None:
    """NEG: horizon outside (1, 3, 5, 10) raises ValueError."""
    with pytest.raises(ValueError, match="horizon"):
        TripleDecomposition(
            probability=0.5,
            confidence=0.5,
            conviction=5.0,
            horizon=2,
        )
    with pytest.raises(ValueError, match="horizon"):
        TripleDecomposition(
            probability=0.5,
            confidence=0.5,
            conviction=5.0,
            horizon=20,
        )


# ===========================================================================
# Test 7 — NEG strict — 10Y non-stratified cap violation
# ===========================================================================


def test_triple_decomp_10y_non_stratified_cap_violation() -> None:
    """NEG strict: 10Y non-stratified confidence > 0.70 raises
    ConfidenceCapViolation (defense-in-depth 1st layer)."""
    with pytest.raises(ConfidenceCapViolation, match="non-stratified"):
        TripleDecomposition(
            probability=0.5,
            confidence=0.75,
            conviction=5.0,
            horizon=10,
            regime_stratified=False,
        )


# ===========================================================================
# Test 8 — NEG strict — 10Y regime-stratified cap violation
# ===========================================================================


def test_triple_decomp_10y_regime_stratified_cap_violation() -> None:
    """NEG strict: 10Y regime-stratified confidence > 0.55 raises
    ConfidenceCapViolation."""
    with pytest.raises(ConfidenceCapViolation, match="regime-stratified"):
        TripleDecomposition(
            probability=0.5,
            confidence=0.60,
            conviction=5.0,
            horizon=10,
            regime_stratified=True,
        )


# ===========================================================================
# Test 9 — POS — 10Y below cap passes
# ===========================================================================


def test_triple_decomp_10y_below_cap_passes() -> None:
    """POS: confidence at or below the cap constructs cleanly at 10Y."""
    # Non-stratified at exact cap
    d_non = TripleDecomposition(
        probability=0.5,
        confidence=CONFIDENCE_CAP_10Y_NON_STRATIFIED,
        conviction=5.0,
        horizon=10,
        regime_stratified=False,
    )
    assert d_non.confidence == CONFIDENCE_CAP_10Y_NON_STRATIFIED
    # Regime-stratified at exact cap
    d_reg = TripleDecomposition(
        probability=0.5,
        confidence=CONFIDENCE_CAP_10Y_REGIME_STRATIFIED,
        conviction=5.0,
        horizon=10,
        regime_stratified=True,
    )
    assert d_reg.confidence == CONFIDENCE_CAP_10Y_REGIME_STRATIFIED


# ===========================================================================
# Test 10 — POS — 1Y high confidence allowed (no cap at 1Y/3Y/5Y)
# ===========================================================================


def test_triple_decomp_1y_high_confidence_ok() -> None:
    """POS: at 1Y/3Y/5Y horizon the 10Y cap does not apply; confidence
    up to 1.0 is allowed."""
    for h in (1, 3, 5):
        d = TripleDecomposition(
            probability=0.5,
            confidence=0.95,
            conviction=5.0,
            horizon=h,
            regime_stratified=False,
        )
        assert d.confidence == 0.95


# ===========================================================================
# Test 11 — NEG-inv — frozen dataclass rejects mutation
# ===========================================================================


def test_triple_decomp_frozen() -> None:
    """NEG-inv: TripleDecomposition is frozen; mutation raises."""
    d = TripleDecomposition(
        probability=0.5,
        confidence=0.5,
        conviction=5.0,
        horizon=1,
    )
    with pytest.raises(Exception):
        d.probability = 0.9  # type: ignore[misc]
    with pytest.raises(Exception):
        d.conviction = 7.0  # type: ignore[misc]
