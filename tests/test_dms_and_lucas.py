"""Layer 6-H D5 — tests for ``macro_pipeline.ensemble.dms_and_lucas``.

Spec ref: Strategic L6-H R7 closure pre-flight 2026-05-16 §3 Phase 6 (D5).
Closes ChatGPT methodology Finding #9 (C-11): DMS adjustment propagation
into HorizonResult + Lucas critique runtime flag + reason codes.

Test inventory:
   1. POS-inv     test_dms_selector_5y_no_risks_tier0_minus100
   2. POS-inv     test_dms_selector_5y_one_risk_tier1_minus150
   3. POS-inv     test_dms_selector_5y_two_risks_tier2_minus200
   4. POS-inv     test_dms_selector_10y_three_risks_tier2_minus200
   5. POS-inv     test_dms_selector_1y_3y_returns_zero_horizon_not_eligible
   6. NEG         test_dms_selector_invalid_horizon_raises
   7. NEG         test_dms_selector_non_bool_flag_raises
   8. POS         test_apply_dms_bps_to_return_basic
   9. POS         test_apply_dms_bps_to_return_zero_bps_passthrough
  10. NEG         test_apply_dms_bps_to_return_nan_raises
  11. POS         test_lucas_diagnostics_no_evidence_returns_no_flag
  12. POS         test_lucas_diagnostics_one_breach_no_flag
  13. POS-inv     test_lucas_diagnostics_two_breaches_flag_fires
  14. POS-inv     test_lucas_diagnostics_three_breaches_sorted_reasons
  15. POS-inv     test_lucas_diagnostics_custom_threshold
  16. NEG         test_lucas_diagnostics_invalid_threshold_raises
  17. NEG         test_lucas_diagnostics_invalid_reason_code_raises
  18. NEG         test_lucas_diagnostics_evidence_out_of_range_raises
  19. POS-inv     test_lucas_diagnostics_dataclass_frozen

NEG count: 6, 7, 10, 16, 17, 18 = 6 NEG.
POS / POS-inv count: 1, 2, 3, 4, 5, 8, 9, 11, 12, 13, 14, 15, 19 = 13.
NEG floor: 6/19 ≈ 31.6% — Strategic-relaxed for L6-H per PD18 (Bayesian/
distinct-surface modules have intrinsically POS-inv test surface for
correctness verification; NEG surface covered cumulatively across
L6-H test files).
"""
from __future__ import annotations

import pytest

from macro_pipeline.ensemble.dms_and_lucas import (
    DMS_REASON_HORIZON_NOT_ELIGIBLE,
    DMS_REASON_TIER_0,
    DMS_REASON_TIER_1,
    DMS_REASON_TIER_2,
    DMS_TIER_0_BPS,
    DMS_TIER_1_BPS,
    DMS_TIER_2_BPS,
    LucasCritiqueDiagnostics,
    apply_dms_bps_to_return,
    compute_lucas_diagnostics,
    select_dms_adjustment_bps,
)


# ===========================================================================
# DMS selector tests
# ===========================================================================


def test_dms_selector_5y_no_risks_tier0_minus100() -> None:
    """POS-inv: 5Y horizon, no risks True → tier-0 -100 bps."""
    bps, reason = select_dms_adjustment_bps(horizon=5)
    assert bps == DMS_TIER_0_BPS == -100.0
    assert reason == DMS_REASON_TIER_0 == "structural_edge_persists"


def test_dms_selector_5y_one_risk_tier1_minus150() -> None:
    """POS-inv: 5Y horizon, 1 risk True → tier-1 -150 bps."""
    bps, reason = select_dms_adjustment_bps(
        horizon=5, valuation_extreme=True
    )
    assert bps == DMS_TIER_1_BPS == -150.0
    assert reason == DMS_REASON_TIER_1 == "single_risk_factor"


def test_dms_selector_5y_two_risks_tier2_minus200() -> None:
    """POS-inv: 5Y horizon, 2 risks True → tier-2 -200 bps."""
    bps, reason = select_dms_adjustment_bps(
        horizon=5,
        valuation_extreme=True,
        concentration_extreme=True,
    )
    assert bps == DMS_TIER_2_BPS == -200.0
    assert reason == DMS_REASON_TIER_2 == "multiple_risk_factors"


def test_dms_selector_10y_three_risks_tier2_minus200() -> None:
    """POS-inv: 10Y horizon, 3 risks True → tier-2 -200 bps (saturates)."""
    bps, reason = select_dms_adjustment_bps(
        horizon=10,
        valuation_extreme=True,
        concentration_extreme=True,
        fiscal_risks_elevated=True,
    )
    assert bps == -200.0
    assert reason == "multiple_risk_factors"


def test_dms_selector_1y_3y_returns_zero_horizon_not_eligible() -> None:
    """POS-inv: 1Y/3Y horizons return 0 bps with horizon_not_eligible.

    Per Vision §8: cyclical noise dominates at 1Y/3Y; no DMS adjustment.
    """
    for h in (1, 3):
        bps, reason = select_dms_adjustment_bps(
            horizon=h,
            valuation_extreme=True,
            concentration_extreme=True,
            fiscal_risks_elevated=True,
            reserve_currency_risk=True,
        )
        assert bps == 0.0
        assert reason == DMS_REASON_HORIZON_NOT_ELIGIBLE


def test_dms_selector_invalid_horizon_raises() -> None:
    """NEG: invalid horizon raises ValueError."""
    with pytest.raises(ValueError, match="not in"):
        select_dms_adjustment_bps(horizon=7)


def test_dms_selector_non_bool_flag_raises() -> None:
    """NEG: non-bool risk flag raises ValueError."""
    with pytest.raises(ValueError, match="must be bool"):
        select_dms_adjustment_bps(
            horizon=5,
            valuation_extreme="yes",  # type: ignore[arg-type]
        )


def test_apply_dms_bps_to_return_basic() -> None:
    """POS: -150 bps applied to 0.065 → 0.050 (return fraction)."""
    result = apply_dms_bps_to_return(0.065, -150.0)
    assert result == pytest.approx(0.050)
    # -100 bps to 0.07 → 0.06.
    result = apply_dms_bps_to_return(0.07, -100.0)
    assert result == pytest.approx(0.06)


def test_apply_dms_bps_to_return_zero_bps_passthrough() -> None:
    """POS: 0 bps → return unchanged."""
    assert apply_dms_bps_to_return(0.065, 0.0) == pytest.approx(0.065)


def test_apply_dms_bps_to_return_nan_raises() -> None:
    """NEG: NaN return raises ValueError."""
    with pytest.raises(ValueError, match="finite"):
        apply_dms_bps_to_return(float("nan"), -100.0)
    with pytest.raises(ValueError, match="finite"):
        apply_dms_bps_to_return(0.065, float("inf"))


# ===========================================================================
# Lucas critique diagnostics tests
# ===========================================================================


def test_lucas_diagnostics_no_evidence_returns_no_flag() -> None:
    """POS: structural_break_evidence=None → flag False, reasons ()."""
    diag = compute_lucas_diagnostics(structural_break_evidence=None)
    assert diag.flag is False
    assert diag.reason_codes == ()
    assert diag.structural_break_evidence == {}


def test_lucas_diagnostics_one_breach_no_flag() -> None:
    """POS: 1 evidence value above threshold → flag False (needs ≥2)."""
    diag = compute_lucas_diagnostics(
        structural_break_evidence={"fed_reaction_shift": 0.9},
    )
    assert diag.flag is False
    assert diag.reason_codes == ()


def test_lucas_diagnostics_two_breaches_flag_fires() -> None:
    """POS-inv: ≥2 evidence values above threshold → flag True."""
    diag = compute_lucas_diagnostics(
        structural_break_evidence={
            "fed_reaction_shift": 0.9,
            "fiscal_dominance": 0.8,
            "ai_productivity_shift": 0.3,
        },
    )
    assert diag.flag is True
    # Only the 2 above threshold (0.5) are in reason codes.
    assert set(diag.reason_codes) == {"fed_reaction_shift", "fiscal_dominance"}


def test_lucas_diagnostics_three_breaches_sorted_reasons() -> None:
    """POS-inv: reason codes are sorted alphabetically."""
    diag = compute_lucas_diagnostics(
        structural_break_evidence={
            "treasury_issuance_structure": 0.9,
            "fed_reaction_shift": 0.9,
            "fiscal_dominance": 0.9,
        },
    )
    assert diag.flag is True
    # Alphabetical: fed_reaction_shift < fiscal_dominance < treasury_issuance_structure.
    assert diag.reason_codes == (
        "fed_reaction_shift",
        "fiscal_dominance",
        "treasury_issuance_structure",
    )


def test_lucas_diagnostics_custom_threshold() -> None:
    """POS-inv: threshold override changes flag firing."""
    evidence = {
        "fed_reaction_shift": 0.4,
        "fiscal_dominance": 0.45,
    }
    # Default threshold 0.5: neither breaches → flag False.
    diag = compute_lucas_diagnostics(structural_break_evidence=evidence)
    assert diag.flag is False
    # Lower threshold 0.3: both breach → flag True.
    diag2 = compute_lucas_diagnostics(
        structural_break_evidence=evidence, threshold=0.3
    )
    assert diag2.flag is True


def test_lucas_diagnostics_invalid_threshold_raises() -> None:
    """NEG: threshold out of [0, 1] raises ValueError."""
    with pytest.raises(ValueError, match="in \\[0, 1\\]"):
        compute_lucas_diagnostics(
            structural_break_evidence=None, threshold=1.5
        )
    with pytest.raises(ValueError, match="in \\[0, 1\\]"):
        compute_lucas_diagnostics(
            structural_break_evidence=None, threshold=-0.1
        )


def test_lucas_diagnostics_invalid_reason_code_raises() -> None:
    """NEG: structural_break_evidence with unknown reason code raises."""
    with pytest.raises(ValueError, match="not in valid set"):
        compute_lucas_diagnostics(
            structural_break_evidence={"unknown_reason": 0.9},
        )


def test_lucas_diagnostics_evidence_out_of_range_raises() -> None:
    """NEG: evidence value outside [0, 1] raises ValueError."""
    with pytest.raises(ValueError, match="in \\[0, 1\\]"):
        compute_lucas_diagnostics(
            structural_break_evidence={"fed_reaction_shift": 1.5},
        )


def test_lucas_diagnostics_dataclass_frozen() -> None:
    """POS-inv: LucasCritiqueDiagnostics is frozen (cannot mutate after init)."""
    diag = LucasCritiqueDiagnostics(
        flag=False,
        reason_codes=(),
        structural_break_evidence={},
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        diag.flag = True  # type: ignore[misc]


# ===========================================================================
# Test 20 — NEG — LucasCritiqueDiagnostics flag/reason_codes mismatch raises
# ===========================================================================


def test_lucas_diagnostics_flag_reason_mismatch_raises() -> None:
    """NEG: dataclass invariant — flag must agree with len(reason_codes) >= 2."""
    # flag=True but only 1 reason code → invariant violation.
    with pytest.raises(ValueError, match="disagrees"):
        LucasCritiqueDiagnostics(
            flag=True,
            reason_codes=("fed_reaction_shift",),
            structural_break_evidence={},
        )
    # flag=False but 2 reason codes → invariant violation.
    with pytest.raises(ValueError, match="disagrees"):
        LucasCritiqueDiagnostics(
            flag=False,
            reason_codes=("fed_reaction_shift", "fiscal_dominance"),
            structural_break_evidence={},
        )


# ===========================================================================
# Test 21 — NEG — LucasCritiqueDiagnostics unsorted reason_codes raises
# ===========================================================================


def test_lucas_diagnostics_unsorted_reason_codes_raises() -> None:
    """NEG: reason_codes must be sorted ascending (deterministic ordering)."""
    with pytest.raises(ValueError, match="sorted ascending"):
        LucasCritiqueDiagnostics(
            flag=True,
            reason_codes=("fiscal_dominance", "fed_reaction_shift"),  # not sorted
            structural_break_evidence={},
        )


# ===========================================================================
# Test 22 — NEG — apply_dms_bps_to_return inf bps raises
# ===========================================================================


def test_apply_dms_bps_to_return_inf_raises() -> None:
    """NEG: inf bps raises ValueError."""
    with pytest.raises(ValueError, match="finite"):
        apply_dms_bps_to_return(0.065, float("inf"))
