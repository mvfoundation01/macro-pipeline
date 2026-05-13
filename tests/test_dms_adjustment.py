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

L5b-KICK-7 (tag ``l5b-kick-7-accept``, 2026-05-15) appended three tests
(K7.1-K7.3) closing the dual-reviewer (Codex 5.5 + ChatGPT 5.5 IMPORTANT)
DMS source-anchoring transparency flag via the AP-AUTH-53 seventh-
instance documentation-primary variant pattern. NEG-flavor accounting:
strict NEG 1 plus POS-inv 1 of 3 equals 67% NEG-flavor at sub-phase
level (floor met).

  K7.1  POS         test_kick7_dms_source_memo_file_exists
  K7.2  POS-inv     test_kick7_dms_source_memo_contains_required_section_headers
  K7.3  NEG         test_kick7_gate25_1_7_validator_fails_when_memo_missing_via_monkeypatch
"""
from __future__ import annotations

import pathlib

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


# ===========================================================================
# L5b-KICK-7 tests K7.1-K7.3 — DMS source memo presence + content
# structure + Gate 25.1.7 monkeypatch failure path. Closes dual-reviewer
# (Codex 5.5 + ChatGPT 5.5 IMPORTANT) DMS source-anchoring transparency
# flag via the AP-AUTH-53 seventh-instance documentation-primary variant
# pattern. NEG-flavor 2 of 3 = 67% at sub-phase level.
# ===========================================================================


def _resolve_memo_path() -> pathlib.Path:
    """Resolve `DMS_SOURCE_MEMO.md` path at the worktree root using the
    same resolution pattern as Gate 25.1.7 validator (from
    `macro_pipeline/validation.py` → `macro_pipeline/` parent → worktree
    root). This test helper deliberately mirrors the validator's
    resolution so the test fails for the same reason the validator
    would fail if the memo moved."""
    # tests/ lives at worktree-root/tests/; parents[1] from this file
    # is the worktree root.
    return pathlib.Path(__file__).resolve().parents[1] / "DMS_SOURCE_MEMO.md"


# ---------------------------------------------------------------------------
# Test K7.1 — POS (KICK-7)
# ---------------------------------------------------------------------------
def test_kick7_dms_source_memo_file_exists():
    """KICK-7: ``DMS_SOURCE_MEMO.md`` exists at the worktree root.
    Closes Codex 5.5 + ChatGPT 5.5 IMPORTANT DMS source-anchoring
    transparency flag at unit-test level (parallel to Gate 25.1.7
    enforcement at validator level)."""
    memo_path = _resolve_memo_path()
    assert memo_path.is_file(), (
        f"DMS_SOURCE_MEMO.md missing at expected worktree-root path "
        f"{memo_path}; this file is mandated by L5b-KICK-7 to close "
        "Codex 5.5 + ChatGPT 5.5 IMPORTANT reviewer flags on DMS "
        "source-anchoring transparency"
    )


# ---------------------------------------------------------------------------
# Test K7.2 — POS-invariant (KICK-7)
# ---------------------------------------------------------------------------
def test_kick7_dms_source_memo_contains_required_section_headers():
    """KICK-7 POS-invariant: ``DMS_SOURCE_MEMO.md`` contains all five
    required section header substrings. Mirrors Gate 25.1.7 validator
    content check; ensures memo structure is preserved across edits."""
    memo_path = _resolve_memo_path()
    assert memo_path.is_file(), "memo file precondition failed"
    memo_text = memo_path.read_text(encoding="utf-8")
    required_sections = (
        "Source Identification",
        "Empirical Foundation",
        "DMS Adjustment Derivation",
        "Sensitivity Band",
        "Refresh Protocol",
    )
    missing = [s for s in required_sections if s not in memo_text]
    assert not missing, (
        f"DMS_SOURCE_MEMO.md missing required section header "
        f"substring(s): {missing}; required: {list(required_sections)}"
    )
    # Additional invariant: §4 explicit honest-disclaimer wording must
    # be present (Strategic-mandated KICK-7 ITEM 0 transparency clause).
    assert "institutional judgment" in memo_text, (
        "DMS_SOURCE_MEMO.md missing §4 honest-disclaimer 'institutional "
        "judgment' phrasing required per Strategic disposition on ITEM 0"
    )


# ---------------------------------------------------------------------------
# Test K7.3 — NEG (KICK-7)
# ---------------------------------------------------------------------------
def test_kick7_gate25_1_7_validator_fails_when_memo_missing_via_monkeypatch(
    monkeypatch,
):
    """KICK-7 NEG: when the memo file is simulated as missing (via
    monkeypatch on ``pathlib.Path.is_file``), the Gate 25.1.7 sub-
    criterion in the Gate 25 composite validator emits a FAIL finding
    citing the missing memo path. Closes the file-presence enforcement
    surface at validator-level NEG semantics."""
    from macro_pipeline.validation import (
        validate_gate25_dms_shrinkage_composite,
    )

    # Monkeypatch pathlib.Path.is_file globally to always return False.
    # This simulates the memo being missing without actually moving
    # the real file (test isolation; cleanup automatic via monkeypatch).
    real_is_file = pathlib.Path.is_file

    def fake_is_file(self):
        # Return False ONLY for DMS_SOURCE_MEMO.md; preserve real
        # behavior for all other paths so unrelated validator checks
        # still work.
        if self.name == "DMS_SOURCE_MEMO.md":
            return False
        return real_is_file(self)

    monkeypatch.setattr(pathlib.Path, "is_file", fake_is_file)

    # Also block .exists() for the same path (the validator uses
    # exists() AND is_file() per Phase 3 implementation).
    real_exists = pathlib.Path.exists

    def fake_exists(self):
        if self.name == "DMS_SOURCE_MEMO.md":
            return False
        return real_exists(self)

    monkeypatch.setattr(pathlib.Path, "exists", fake_exists)

    report = validate_gate25_dms_shrinkage_composite()
    # The Gate 25.1.7 finding should be FAIL when memo is missing.
    fail_findings = [
        f for f in report.findings
        if "Criterion 25.1.7" in f and f.startswith("FAIL")
    ]
    assert fail_findings, (
        "Gate 25.1.7 should FAIL when DMS_SOURCE_MEMO.md is missing "
        "(monkeypatched), but no FAIL finding found in report. "
        f"Findings: {report.findings}"
    )
    # And the FAIL message should cite the missing path.
    assert "DMS_SOURCE_MEMO.md missing" in fail_findings[0], (
        f"FAIL finding should cite 'DMS_SOURCE_MEMO.md missing'; "
        f"got: {fail_findings[0]}"
    )
