# Fixture: should PASS validate_no_cumulative_arithmetic.py

This file uses symbolic wording for cumulative test-count proof
contracts per AP-AUTH-42 NEW v6 mandate.

## §1 — Proof contract example

8. Cumulative test count = previous baseline + L5-A delta (+12); ruff clean.

This is the symbolic form that survives future test-count changes
without drift, per AP-AUTH-40 + AP-AUTH-42 discipline.

## §2 — Single-digit arithmetic (out of regex band)

A simple `5 + 5 = 10` example uses single-digit operands which are
out of the `\b\d{2,4}\s*\+\s*\d{1,3}\s*=\s*\d{2,4}\b` band; the hook
intentionally does not flag these.

## §3 — Explicit examples wrapped in exempt markers

<!-- example -->
The v5 audit-gap pattern was hard-coded arithmetic like `602 + 78 = 680`
in proof contracts. v6 codifies AP-AUTH-42 to forbid this in active prose.
<!-- /example -->

The block above is an intentional documentation example wrapped in
exempt markers; the hook ignores it.

## §4 — Code block (also exempt)

```
# Example from chunk 14 preflight
602 + 8 = 610
```

Content inside fenced code blocks is also exempt.

The hook should exit 0 on this file.
