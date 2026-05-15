# Fixture: should PASS validate_dual_grep_in_verification.py (v7)

L5b-H AP-AUTH-41 v7 test fixture for Update Log exemption.

This is a `*_VERIFICATION.md` file (matches v7 filename allowlist). It
has a verification section with proper dual-grep evidence (would pass
on its own) AND an Update Log section with a bare "ALIGNED" row that
WOULD have tripped v6 but is EXEMPTED by v7 because it lives under the
`## Update Log` heading.

## §1 — Mirror integrity verification

| Sub-phase | §5.X.5 | Status |
|---|---|---|
| L5-A | pos: "12 tests" present / neg: 0 "10 tests" active | ALIGNED |

The verification table above has proper dual-grep evidence per v7.

## Update Log

| Version | Date | Notes |
|---|---|---|
| 1.0 | 2026-05-01 | Initial draft |
| 2.0 | 2026-05-14 | ALIGNED with Vision v2.0 update — no dual-grep needed here |

The Update Log row above contains "ALIGNED" but lives under the
`## Update Log` heading, which v7 explicitly exempts. The hook
should exit 0 on this file (no violations detected because the
Update Log section is out of scope).

This closes the R5 docs-suite false-positive risk where v6 tripped
on legitimate version-history annotations in vision / methodology /
methodology-review v2.0 docs.
