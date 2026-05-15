# Fixture: should PASS validate_dual_grep_in_verification.py (v7)

L5b-H AP-AUTH-41 v7 test fixture for heading-scope refinement.

This is a `*_VERIFICATION.md` file (matches v7 filename allowlist).
It has alignment-claim content (the literal word "ALIGNED") BUT NOT
under a verification-section heading. v7 should NOT trip on these
rows because the heading-aware parser only enforces inside
verification/alignment section scope.

## Implementation Notes

| Item | Description |
|---|---|
| Architecture choice | Selected Option A — fully ALIGNED with Strategic disposition |
| Edge case handling | Approach mirror integrity preserved across folds |

The rows above contain alignment-claim phrases ("ALIGNED" and
"mirror integrity") but live under `## Implementation Notes`, which
is NOT a verification scope heading per v7. The hook should exit 0
on this file.

## Performance Characteristics

| Component | Latency | Note |
|---|---|---|
| Component A | 5ms | Performance is mirror integrity insensitive |

Same logic: alignment-claim phrase under non-verification heading;
hook should NOT trip.

The hook should exit 0 on this file (no violations because heading
scope is not verification).
