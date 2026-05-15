# Fixture: should PASS validate_dual_grep_in_verification.py

This is a synthetic verification report illustrating proper dual-grep
evidence per AP-AUTH-41 v6 STRENGTHENED.

## §1 — Mirror integrity verification

| Sub-phase | §5.X.5 | §5.X.6 | §5.X.7 | §6.N | Status |
|---|---|---|---|---|---|
| L5-A | pos: "12 tests" ✓ / neg: 0 "10 tests" active ✓ | pos: "12 tests" ✓ / neg: 0 ✓ | pos: "12 tests PASS" ✓ / neg: 0 ✓ | pos: "12 tests" ✓ / neg: 0 ✓ | ALIGNED |
| L5-B | pos: "28 tests" ✓ / neg: 0 "15 tests" Task B generic ✓ | pos: "28 tests in §5.B.5" ✓ / neg: 0 active "15 tests" ✓ | pos: "28 new tests" ✓ / neg: 0 active "15 tests" ✓ | pos: "28 tests" ✓ / neg: 0 ✓ | ALIGNED |

Every alignment claim above presents BOTH positive grep evidence
(new pattern present) AND negative grep evidence (old pattern absent)
in the same row, satisfying AP-AUTH-41 v6.

The hook should exit 0 on this file.
