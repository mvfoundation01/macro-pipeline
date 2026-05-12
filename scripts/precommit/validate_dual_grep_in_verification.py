"""Pre-commit hook: enforce AP-AUTH-41 v6 STRENGTHENED dual-grep discipline.

AP-AUTH-41 v6 mandate (from LAYER_5_BUILD_SPEC.md §12, codified at v6
chunk 14): every claimed mirror-integrity alignment in a verification
report MUST show BOTH:
  - positive grep evidence (new pattern present)
  - negative grep evidence (old pattern absent)
per anchor. Bare "ALIGNED" assertion without both proofs is REVISE-REQUIRED.

Scope (per Strategic prompt PHASE 2.1): docs/**/*.md verification tables only.

This script scans staged markdown files for verification-table rows that
make an alignment claim, and fails if any such row lacks both pos and neg
grep evidence.

Exit codes:
    0 = no violations OR no in-scope files
    1 = one or more violations detected

Usage:
    python validate_dual_grep_in_verification.py [PATH ...]

If no PATH given, exits 0 (no work to do).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# A row makes an "alignment claim" if it asserts mirror integrity status.
# Common patterns in L3.5b/L5 verification reports: "ALIGNED", "✓ aligned",
# "alignment verified", "X/Y alignment", etc. Detection is case-insensitive.
_ALIGNMENT_CLAIM_PATTERNS = (
    re.compile(r"\bALIGNED\b", re.IGNORECASE),
    re.compile(r"alignment\s+verified", re.IGNORECASE),
    re.compile(r"mirror\s+integrity", re.IGNORECASE),
)

# A row provides dual-grep evidence if it contains BOTH tokens indicating
# positive AND negative grep results. Tokens used in L5 v6 chunk 14 verification:
# "pos:" / "neg:" prefixes in the same row.
_POS_TOKEN = re.compile(r"\bpos\s*:", re.IGNORECASE)
_NEG_TOKEN = re.compile(r"\bneg\s*:", re.IGNORECASE)

# Skip rows that are documentation OF the rule itself (meta-references) or
# header rows of tables (`| --- |` separators). A row counts as a "header
# separator" if it consists only of pipes, dashes, colons, spaces.
_HEADER_SEPARATOR = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")


def _is_in_scope(path: Path) -> bool:
    """Return True if path is a docs/**/*.md file (V's prompt scope).

    Path is checked as a POSIX-style string for cross-platform consistency.
    """
    posix = path.as_posix()
    return posix.startswith("docs/") and posix.endswith(".md")


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Scan one file. Return list of (line_no, line_text) violations.

    A violation = a markdown table row containing an alignment claim
    pattern but lacking BOTH pos: and neg: tokens in the same row.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[validate_dual_grep] WARN: cannot read {path}: {exc}",
              file=sys.stderr)
        return []

    violations: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.lstrip().startswith("|"):
            continue
        if _HEADER_SEPARATOR.match(line):
            continue
        if not any(p.search(line) for p in _ALIGNMENT_CLAIM_PATTERNS):
            continue
        has_pos = bool(_POS_TOKEN.search(line))
        has_neg = bool(_NEG_TOKEN.search(line))
        if not (has_pos and has_neg):
            violations.append((lineno, line.strip()))
    return violations


def main(argv: list[str]) -> int:
    if not argv:
        return 0

    total_violations = 0
    for arg in argv:
        path = Path(arg)
        if not path.exists():
            continue
        if not _is_in_scope(path):
            continue
        violations = _scan_file(path)
        for lineno, line in violations:
            print(
                f"[AP-AUTH-41 v6 violation] {path}:{lineno}: "
                f"alignment claim without dual (pos+neg) grep evidence",
                file=sys.stderr,
            )
            print(f"    {line}", file=sys.stderr)
            total_violations += 1

    if total_violations:
        print(
            f"\n[validate_dual_grep] FAIL: {total_violations} alignment "
            "claim(s) missing dual-grep evidence per AP-AUTH-41 v6.",
            file=sys.stderr,
        )
        print(
            "Fix: each alignment-claim row must include both `pos: ...` "
            "AND `neg: ...` tokens (see LAYER_5_V6_CHUNK_14_VERIFICATION.md §3).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
