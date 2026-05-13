"""Layer 5-F — tests for ``macro_pipeline.models.dms_adjustment``.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.F.5 (five tests;
three NEG / two POS = 60% NEG). Test #3 uses the runtime-invariant
interpretation per Strategic-approved Op-F-a (2026-05-13): at L5-F
build time there are zero downstream callers of ``apply_dms_adjustment``,
so a literal "AST walk over macro_pipeline/" for callers yields vacuous
truth; the dispatcher pattern is verified instead by exercising the
function across all four horizons and asserting the spec-mandated
behavior (1Y/3Y collapse band; 5Y/10Y produce band width = 100 bps).

Test inventory (mirrors §5.F.5 row order):
  1   POS         test_dms_bps_central_matches_Q6_lock_5Y_minus_125_10Y_minus_175
  2   POS         test_dms_bps_sensitivity_band_plus_minus_50
  3   NEG         test_dms_application_AST_walk_audit
                  (Op-F-a runtime audit; Standing Order #4)
  4   NEG         test_rejects_horizon_outside_1Y_3Y_5Y_10Y
  5   NEG         test_band_lower_equals_central_for_1Y_3Y_no_adjustment
"""
from __future__ import annotations

import pytest

from macro_pipeline.models.dms_adjustment import (
    DMS_BPS_CENTRAL,
    DMS_BPS_SENSITIVITY,
    apply_dms_adjustment,
)


# ---------------------------------------------------------------------------
# Test #1 — POS
# ---------------------------------------------------------------------------
def test_dms_bps_central_matches_Q6_lock_5Y_minus_125_10Y_minus_175():
    """Spec §5.F.5 test #1 + §5.F.4 Q6 lock: canonical horizon-conditional
    central bps values."""
    assert DMS_BPS_CENTRAL == {
        "1Y": 0.0,
        "3Y": 0.0,
        "5Y": -125.0,
        "10Y": -175.0,
    }


# ---------------------------------------------------------------------------
# Test #2 — POS
# ---------------------------------------------------------------------------
def test_dms_bps_sensitivity_band_plus_minus_50():
    """Spec §5.F.5 test #2 + §5.F.4 Q6 lock: sensitivity band ±50 bps."""
    assert DMS_BPS_SENSITIVITY == 50.0


# ---------------------------------------------------------------------------
# Test #3 — NEG (Standing Order #4; Op-F-a runtime audit)
# ---------------------------------------------------------------------------
def test_dms_application_AST_walk_audit():
    """Spec §5.F.5 test #3 — Standing Order #4 AST audit.

    Op-F-a (Strategic-approved 2026-05-13): the literal "AST walk over
    macro_pipeline/" for callers is vacuous truth at L5-F build time
    (no downstream consumer exists yet). The spec property the audit
    must verify is the dispatcher behavior INSIDE
    ``apply_dms_adjustment`` itself: 5Y/10Y trigger the sensitivity
    band; 1Y/3Y do not. This test exercises the function across all
    four §3.3 horizons and asserts the spec invariant per
    ``apply_dms_adjustment`` source body (the
    ``if horizon in ('1Y', '3Y')`` early-return branch).
    """
    raw = 650.0
    # 5Y/10Y branches: sensitivity band non-collapsed; band width =
    # 2 × DMS_BPS_SENSITIVITY = 100.0 bps.
    for h in ("5Y", "10Y"):
        c, l, u = apply_dms_adjustment(raw, h)
        assert l != c, f"horizon={h}: 5Y/10Y branch must produce lower != central"
        assert u != c, f"horizon={h}: 5Y/10Y branch must produce upper != central"
        assert abs((u - l) - 2 * DMS_BPS_SENSITIVITY) < 1e-12, (
            f"horizon={h}: band width = {u - l}, expected "
            f"{2 * DMS_BPS_SENSITIVITY}"
        )
        # And central equals raw + Q6 central.
        assert abs(c - (raw + DMS_BPS_CENTRAL[h])) < 1e-12

    # 1Y/3Y branches: sensitivity band collapsed (NEG assertion); all
    # three values identical to raw (no adjustment).
    for h in ("1Y", "3Y"):
        c, l, u = apply_dms_adjustment(raw, h)
        assert l == c == u == raw, (
            f"horizon={h}: 1Y/3Y branch must collapse band — "
            f"got central={c}, lower={l}, upper={u}; expected all = raw={raw}"
        )


# ---------------------------------------------------------------------------
# Test #4 — NEG
# ---------------------------------------------------------------------------
def test_rejects_horizon_outside_1Y_3Y_5Y_10Y():
    """Spec §5.F.5 test #4: ``apply_dms_adjustment(0.0, "2Y")`` raises
    ``ValueError``."""
    with pytest.raises(ValueError, match=r"horizon '2Y' not in"):
        apply_dms_adjustment(0.0, "2Y")
    # Symmetric NEG checks on additional invalid horizons.
    for bad_h in ("0Y", "15Y", "1y", "", "100Y"):
        with pytest.raises(ValueError, match=r"horizon"):
            apply_dms_adjustment(0.0, bad_h)


# ---------------------------------------------------------------------------
# Test #5 — NEG
# ---------------------------------------------------------------------------
def test_band_lower_equals_central_for_1Y_3Y_no_adjustment():
    """Spec §5.F.5 test #5: for ``1Y`` (and ``3Y`` by extension),
    ``adjusted_lower == adjusted_central == adjusted_upper`` (no
    sensitivity band when no adjustment applied)."""
    for raw_bps in (0.0, 100.0, 650.0, -200.0):
        for h in ("1Y", "3Y"):
            c, l, u = apply_dms_adjustment(raw_bps, h)
            assert l == c, (
                f"horizon={h}, raw={raw_bps}: lower={l} != central={c}"
            )
            assert u == c, (
                f"horizon={h}, raw={raw_bps}: upper={u} != central={c}"
            )
            # And the central equals raw (since DMS_BPS_CENTRAL[h] = 0).
            assert c == raw_bps, (
                f"horizon={h}, raw={raw_bps}: central={c} != raw={raw_bps}"
            )
