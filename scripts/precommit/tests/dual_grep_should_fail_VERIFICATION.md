# Fixture: should FAIL validate_dual_grep_in_verification.py

This is a synthetic verification report illustrating the AP-AUTH-41 v6
audit-gap pattern: bare "ALIGNED" assertion without dual-grep evidence.

## §1 — Mirror integrity verification

| Sub-phase | Status |
|---|---|
| L5-A | ALIGNED (no proof provided) |
| L5-B | mirror integrity verified |

Both rows above make an alignment claim (ALIGNED / mirror integrity verified)
but neither contains BOTH `pos:` and `neg:` tokens. AP-AUTH-41 v6 mandates
both per anchor. v5 fell into this exact trap — claimed 20/20 alignment
based on positive-only grep, missed 8+ stale negative references.

The hook should exit 1 on this file and emit 2 violation messages.
