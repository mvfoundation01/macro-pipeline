"""Pre-commit hook: enforce AP-AUTH-42 NEW v6 cumulative-arithmetic scrub.

AP-AUTH-42 NEW v6 mandate (from LAYER_5_BUILD_SPEC.md §12): cumulative
test-count arithmetic in proof contracts MUST use symbolic placeholders
(`previous baseline + L5-X delta`) NOT hard-coded numbers like
`602 + 78 = 680` or `602 + 8 = 610`. Codifies regex-based scrub to
catch all variants (v5 specific-instance check missed `602 + 8 = 610`).

Regex (per Strategic prompt PHASE 2.1):
    \\b\\d{2,4}\\s*\\+\\s*\\d{1,3}\\s*=\\s*\\d{2,4}\\b

Scope (per Strategic prompt PHASE 2.1): docs/**/*.md active proof-contract prose.

Exemptions:
    - Content inside fenced code blocks (``` ... ```)
    - Content inside HTML comments (<!-- ... -->)
    - Explicit "block markers": any line range between
      `<!-- v5-comparison -->` and `<!-- /v5-comparison -->`
      OR between `<!-- example -->` and `<!-- /example -->`

Exit codes:
    0 = no violations OR no in-scope files
    1 = one or more violations detected

Usage:
    python validate_no_cumulative_arithmetic.py [PATH ...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Per Strategic prompt PHASE 2.1: matches `NNN + N(N)(N) = NNN` patterns
# where the left operand has 2-4 digits and right operand has 1-3 digits.
# This is narrow enough to skip single-digit sums (e.g., "5 + 5 = 10")
# while catching cumulative-test arithmetic (e.g., "602 + 78 = 680").
_CUMULATIVE_ARITHMETIC = re.compile(
    r"\b\d{2,4}\s*\+\s*\d{1,3}\s*=\s*\d{2,4}\b"
)

# Exemption block markers (paired open/close).
_EXEMPT_OPEN_MARKERS = (
    re.compile(r"<!--\s*v5-comparison\s*-->"),
    re.compile(r"<!--\s*example\s*-->"),
)
_EXEMPT_CLOSE_MARKERS = (
    re.compile(r"<!--\s*/v5-comparison\s*-->"),
    re.compile(r"<!--\s*/example\s*-->"),
)

# Fenced code blocks: lines starting with ``` toggle in/out of code state.
_CODE_FENCE = re.compile(r"^\s*```")


def _is_in_scope(path: Path) -> bool:
    posix = path.as_posix()
    return posix.startswith("docs/") and posix.endswith(".md")


def _strip_html_comments(text: str) -> str:
    """Replace HTML comment content with whitespace (preserves line numbers)."""
    def _blank(match: re.Match[str]) -> str:
        s = match.group(0)
        return "".join("\n" if c == "\n" else " " for c in s)
    return re.sub(r"<!--.*?-->", _blank, text, flags=re.DOTALL)


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_no, line_text, match_text) violations."""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[validate_no_cumulative_arithmetic] WARN: cannot read "
              f"{path}: {exc}", file=sys.stderr)
        return []

    # First pass: remove HTML comments (preserves line numbers).
    text = _strip_html_comments(raw_text)

    violations: list[tuple[int, str, str]] = []
    in_code_block = False
    in_exempt_block = False

    for lineno, line in enumerate(text.splitlines(), start=1):
        raw_line = raw_text.splitlines()[lineno - 1] if lineno - 1 < len(
            raw_text.splitlines()) else ""

        # Toggle code-fence state.
        if _CODE_FENCE.match(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Exempt-block markers operate on the RAW line so the markers
        # themselves (HTML comments) are visible.
        if any(p.search(raw_line) for p in _EXEMPT_OPEN_MARKERS):
            in_exempt_block = True
            continue
        if any(p.search(raw_line) for p in _EXEMPT_CLOSE_MARKERS):
            in_exempt_block = False
            continue
        if in_exempt_block:
            continue

        # Scan post-comment-strip line for the arithmetic pattern.
        match = _CUMULATIVE_ARITHMETIC.search(line)
        if match:
            violations.append((lineno, raw_line.strip(), match.group(0)))

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
        for lineno, line, match_text in violations:
            print(
                f"[AP-AUTH-42 violation] {path}:{lineno}: "
                f"hard-coded cumulative arithmetic `{match_text}` in active prose",
                file=sys.stderr,
            )
            print(f"    {line}", file=sys.stderr)
            total_violations += 1

    if total_violations:
        print(
            f"\n[validate_no_cumulative_arithmetic] FAIL: {total_violations} "
            "hard-coded arithmetic hit(s) per AP-AUTH-42 NEW v6.",
            file=sys.stderr,
        )
        print(
            "Fix: use symbolic wording (e.g., `previous baseline + L5-X delta`) "
            "instead of literal `NNN + N = NNN` (see LAYER_5_BUILD_SPEC.md §12 "
            "AP-AUTH-42 + AP-AUTH-40 propagation discipline). To exempt an "
            "intentional example, wrap in `<!-- example -->` ... "
            "`<!-- /example -->` block markers.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
