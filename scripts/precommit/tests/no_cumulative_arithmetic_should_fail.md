# Fixture: should FAIL validate_no_cumulative_arithmetic.py

This file violates AP-AUTH-42 NEW v6 by using hard-coded cumulative
arithmetic in active proof-contract prose.

## §1 — Proof contract (BAD: hard-coded arithmetic in active prose)

8. Cumulative test count: 602 + 8 = 610 cumulative tests; ruff clean.

This is the exact pattern v5 missed and v6 codified AP-AUTH-42 to catch.

## §2 — Another violation

The full regression suite expands from existing 602 + 78 = 680 tests
post-L5 closure.

This second violation tests that the hook reports multiple hits per file.

The hook should exit 1 on this file and emit 2 violation messages.
