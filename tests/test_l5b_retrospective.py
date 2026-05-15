"""Layer 5b-E — tests for L5B_RETROSPECTIVE.md + Gate 28 validator.

Spec ref: Master Prompt v3.1 §15 (L5b OOS hardening sprint closure mandate)
+ Strategic disposition cycle 2026-05-14 §E greenlight block (five rulings
ratified). L5b-E is the FINAL L5b sub-phase; ACCEPT tag ``l5b-e-accept``
plus ``l5b-complete`` (DUAL TAG) closes the L5b sprint with twelve of
twelve perfect ACCEPTs (twenty-five of twenty-five convergence streak).

L5b-E is a documentation-primary sub-phase OUTSIDE the AP-AUTH-54 envelope
per Strategic disposition 4 (envelope STAYS CLOSED at seven instances).
L5b-E mirrors ``LAYER_5_RETROSPECTIVE.md`` (parent L5-H precedent)
structurally, NOT the KICK-7 reviewer-driven kickoff pattern.

Test inventory (three tests; NEG-flavor 2 of 3 = 67% per L5-B1 accounting
convention where POS-inv counts as NEG-flavor; floor met):

  E.1  POS       test_e1_retrospective_file_exists_at_worktree_root
                 (Gate 28.1 + 28.2 + 28.3 PASS path)
  E.2  POS-inv   test_e2_retrospective_contains_seven_required_substrings
                 (Gate 28.2 invariant — seven H2 strings exact match)
  E.3  NEG       test_e3_gate28_validator_fails_when_retrospective_missing_via_monkeypatch
                 (Gate 28.4 NEG monkeypatch probe; mirrors K7.3 pattern
                 at tests/test_dms_adjustment.py:213-240)
"""
from __future__ import annotations

import pathlib

import pytest


# ---------------------------------------------------------------------------
# Test E.1 — POS (L5b-E)
# ---------------------------------------------------------------------------
def test_e1_retrospective_file_exists_at_worktree_root():
    """L5b-E POS: ``L5B_RETROSPECTIVE.md`` exists at expected worktree-
    root path; Gate 28 validator reports PASS for all in-validator
    criteria (28.1 API + 28.2 substrings + 28.3 size)."""
    from macro_pipeline.validation import validate_gate28_l5b_retrospective

    report = validate_gate28_l5b_retrospective()
    assert report.passed, (
        f"Gate 28 should PASS at L5b-E ACCEPT; got findings "
        f"{report.findings}"
    )
    # Path check via summary.
    expected_filename = "L5B_RETROSPECTIVE.md"
    assert expected_filename in report.summary["criterion_28_path"], (
        f"Gate 28 path should reference {expected_filename}; got "
        f"{report.summary['criterion_28_path']}"
    )
    # File-size criterion threshold.
    assert report.summary["criterion_28_3_file_size_bytes"] >= 5000, (
        "Gate 28.3 should report file size >= 5000 bytes; got "
        f"{report.summary['criterion_28_3_file_size_bytes']}"
    )


# ---------------------------------------------------------------------------
# Test E.2 — POS-inv (L5b-E)
# ---------------------------------------------------------------------------
def test_e2_retrospective_contains_seven_required_substrings():
    """L5b-E POS-inv: ``L5B_RETROSPECTIVE.md`` contains all seven
    required H2 section substrings per Gate 28.2 invariant. The seven
    substrings are the single source of truth = Gate 28 validator body
    + L5B_RETROSPECTIVE.md authorship (consistent simultaneous authorship
    guarantees verbatim match per Strategic Note C)."""
    from macro_pipeline.validation import validate_gate28_l5b_retrospective

    report = validate_gate28_l5b_retrospective()
    # Invariant: zero missing sections at L5b-E ACCEPT.
    assert report.summary["criterion_28_2_missing_sections"] == [], (
        "All seven required substrings should be present; got missing: "
        f"{report.summary['criterion_28_2_missing_sections']}"
    )
    # Invariant: required_sections tuple has exactly the seven expected
    # H2 strings in canonical order.
    expected_substrings = [
        "Sprint context and convergence streak",
        "Per-sub-phase inventory",
        "AP-AUTH-54 envelope characterization",
        "Sxx-13..23 inline NOT-TRIGGERED",
        "Cumulative L5b sprint deltas",
        "Reviewer-concern closure scoreboard",
        "Forward readiness and closing recommendation",
    ]
    assert (
        report.summary["criterion_28_2_required_sections"]
        == expected_substrings
    ), (
        "Gate 28.2 required-substring tuple should match the canonical "
        "seven-section L5b-E retrospective contract per Strategic "
        "disposition Note C; got "
        f"{report.summary['criterion_28_2_required_sections']}"
    )
    # Cross-verify each substring is in the actual file content
    # (defense in depth against any future drift between validator
    # tuple and retrospective body).
    retrospective_path = pathlib.Path(
        report.summary["criterion_28_path"]
    )
    retrospective_text = retrospective_path.read_text(encoding="utf-8")
    for substring in expected_substrings:
        assert substring in retrospective_text, (
            f"Required H2 substring '{substring}' missing from "
            f"L5B_RETROSPECTIVE.md content (file at "
            f"{retrospective_path})"
        )


# ---------------------------------------------------------------------------
# Test E.3 — NEG (L5b-E)
# ---------------------------------------------------------------------------
def test_e3_gate28_validator_fails_when_retrospective_missing_via_monkeypatch(
    monkeypatch,
):
    """L5b-E NEG: when ``L5B_RETROSPECTIVE.md`` is simulated as missing
    (via monkeypatch on ``pathlib.Path.is_file`` plus
    ``pathlib.Path.exists``), the Gate 28 validator emits FAIL findings
    citing the missing path for both Criterion 28.2 and Criterion 28.3.
    Mirrors the K7.3 monkeypatch pattern at
    ``tests/test_dms_adjustment.py:213-240`` closing the file-presence
    enforcement surface at validator-level NEG semantics. Gate 28.4
    out-of-band assertion satisfied by this test."""
    from macro_pipeline.validation import validate_gate28_l5b_retrospective

    # Monkeypatch pathlib.Path.is_file to return False ONLY for
    # L5B_RETROSPECTIVE.md; preserve real behavior for all other paths
    # so unrelated validator state still works.
    real_is_file = pathlib.Path.is_file

    def fake_is_file(self):
        if self.name == "L5B_RETROSPECTIVE.md":
            return False
        return real_is_file(self)

    monkeypatch.setattr(pathlib.Path, "is_file", fake_is_file)

    # Also block .exists() for the same path (the validator uses
    # exists() AND is_file() per Phase 3 implementation, mirroring
    # the Gate 25.1.7 KICK-7 pattern).
    real_exists = pathlib.Path.exists

    def fake_exists(self):
        if self.name == "L5B_RETROSPECTIVE.md":
            return False
        return real_exists(self)

    monkeypatch.setattr(pathlib.Path, "exists", fake_exists)

    report = validate_gate28_l5b_retrospective()
    # All FAIL findings (28.2 + 28.3 should both fail when file missing).
    fail_findings = [
        f for f in report.findings if f.startswith("FAIL")
    ]
    assert fail_findings, (
        "Gate 28 should emit FAIL findings when L5B_RETROSPECTIVE.md "
        "is missing (monkeypatched), but no FAIL finding found in "
        f"report. Findings: {report.findings}"
    )
    # Criterion 28.2 FAIL must cite the missing path.
    fail_28_2 = [f for f in fail_findings if "Criterion 28.2" in f]
    assert fail_28_2, (
        "Criterion 28.2 should FAIL when file missing; got "
        f"fail_findings={fail_findings}"
    )
    assert "L5B_RETROSPECTIVE.md" in fail_28_2[0], (
        "FAIL finding for 28.2 should cite 'L5B_RETROSPECTIVE.md'; "
        f"got: {fail_28_2[0]}"
    )
    # Criterion 28.3 FAIL must also fire (file-size check cannot
    # proceed when file missing).
    fail_28_3 = [f for f in fail_findings if "Criterion 28.3" in f]
    assert fail_28_3, (
        "Criterion 28.3 should FAIL when file missing (file-size "
        f"check cannot proceed); got fail_findings={fail_findings}"
    )
    # Aggregate report-level invariant: validator reports passed=False.
    assert not report.passed, (
        "Gate 28 report should be passed=False when retrospective "
        f"is missing; got passed={report.passed}, findings="
        f"{report.findings}"
    )
    # Criterion 28.1 (API present) should still PASS — it's a self-
    # import check, independent of file presence. Defense in depth
    # against future regressions where 28.1 might be incorrectly
    # gated on file presence.
    pass_28_1 = [
        f for f in report.findings
        if "Criterion 28.1" in f and not f.startswith("FAIL")
    ]
    assert pass_28_1, (
        "Criterion 28.1 should remain PASS even when file missing "
        f"(API self-import is independent of file presence); got "
        f"findings={report.findings}"
    )
