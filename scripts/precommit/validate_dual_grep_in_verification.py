"""Pre-commit hook: enforce AP-AUTH-41 v7 STRENGTHENED dual-grep discipline.

AP-AUTH-41 v7 mandate (L5b-H 2026-05-15 refinement per R6 reviewer
recommendation; Codex 5.5 + ChatGPT 5.5 concurrence): scope narrowed
to ``*_VERIFICATION.md`` files only; heading-aware parsing restricts
violations to rows under verification/alignment section headings;
``## Update Log`` sections explicitly exempted regardless of content.

The v6 → v7 refinement closes the R5 docs-suite commit false-positive
on version-history annotations (the literal word "Aligned" in update-
log table rows of vision / methodology / methodology-review v2.0
docs). v6 tripped on those rows because the scope was the entire
``docs/**/*.md`` namespace + raw row-level regex; v7 narrows scope on
both axes (filename + heading) so the validator targets ONLY the
verification-report use case it was designed for.

Scope (v7):
  1. **Filename allowlist** — only ``*_VERIFICATION.md`` (case-
     insensitive) under ``docs/``. Other docs files are skipped.
  2. **Heading-aware parsing** — only enforce on table rows under
     headings matching any of: ``Mirror Integrity``,
     ``Alignment Audit``, ``Verification``, ``Alignment``
     (case-insensitive). Rows outside these sections are skipped.
  3. **Update Log exemption** — rows under heading matching
     ``Update Log`` (case-insensitive; any heading level) are
     explicitly skipped regardless of alignment-claim content.

Behavior preserved from v6:
  * Row-level pattern detection (``ALIGNED``, ``alignment verified``,
    ``mirror integrity``) within a verification section still requires
    ``pos:`` AND ``neg:`` tokens in the same row.
  * Header separator rows (``| --- |``) skipped.
  * Exit codes: ``0`` for no violations or no in-scope files;
    ``1`` for any violation detected.

Usage:
    python validate_dual_grep_in_verification.py [PATH ...]

If no PATH given, exits 0 (no work to do).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# v7 filename allowlist regex. Case-insensitive match on basename
# suffix ``_VERIFICATION.md``. Examples that MATCH:
#   - ``MIRROR_INTEGRITY_VERIFICATION.md``
#   - ``layer_5_b_VERIFICATION.md``
#   - ``00_chunk_14_VERIFICATION.md``
# Examples that do NOT match:
#   - ``_VERIFICATION_REPORT.md`` (suffix is ``_REPORT.md``)
#   - ``VISION.md`` / ``00_VISION_AND_PHILOSOPHY_v2.md`` (no
#     ``_VERIFICATION`` token)
#   - ``ap_register.md`` (no ``_VERIFICATION`` token)
_FILENAME_ALLOWLIST = re.compile(r"_VERIFICATION\.md$", re.IGNORECASE)

# v7 heading patterns: ENTER "verification scope" state. Matched
# against the heading text (stripped of leading ``#`` markers and
# whitespace). Matches anywhere in the heading via word boundary —
# real verification reports often use section numbering prefixes
# (e.g., "## §1 — Mirror integrity verification") so a strict
# leading-anchor would miss legitimate verification headings.
_VERIFICATION_HEADING = re.compile(
    r"\b(mirror\s+integrity|alignment\s+audit|verification|alignment)\b",
    re.IGNORECASE,
)

# v7 heading patterns: ENTER "update log exemption" state. Matches
# "Update Log" anywhere in heading (also via word boundary for
# numbered prefixes like "## §X — Update Log"). Update Log exemption
# takes PRECEDENCE over verification scope when both match the same
# heading (e.g., "## Update Log Verification" → state=update_log).
_UPDATE_LOG_HEADING = re.compile(
    r"\bupdate\s+log\b",
    re.IGNORECASE,
)

# Any markdown heading line marker (any heading level). Used to
# detect heading transitions in the state machine.
_HEADING_LINE = re.compile(r"^\s*#+\s")


# A row makes an "alignment claim" if it asserts mirror integrity status.
# Patterns preserved from v6 for backward-compat (verification reports
# may use any of these tokens).
_ALIGNMENT_CLAIM_PATTERNS = (
    re.compile(r"\bALIGNED\b", re.IGNORECASE),
    re.compile(r"alignment\s+verified", re.IGNORECASE),
    re.compile(r"mirror\s+integrity", re.IGNORECASE),
)

# Dual-grep evidence tokens (preserved from v6).
_POS_TOKEN = re.compile(r"\bpos\s*:", re.IGNORECASE)
_NEG_TOKEN = re.compile(r"\bneg\s*:", re.IGNORECASE)

# Header separator row (preserved from v6).
_HEADER_SEPARATOR = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")


def _is_in_scope(path: Path) -> bool:
    """v7: docs/*.md AND filename matches ``*_VERIFICATION.md``.

    Path is checked as a POSIX-style string for cross-platform
    consistency.
    """
    posix = path.as_posix()
    if not posix.startswith("docs/"):
        return False
    if not posix.endswith(".md"):
        return False
    # v7 filename allowlist gate.
    return bool(_FILENAME_ALLOWLIST.search(path.name))


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """v7 heading-aware scan.

    State machine over lines:
    * Heading line transitions the state to one of:
      ``verification`` (active enforcement),
      ``update_log`` (exempted regardless of content),
      ``other`` (no enforcement; default state).
    * Non-heading lines are checked only when in ``verification`` state.
    * Update Log heading transitions state to ``update_log`` and EXITS
      the verification state immediately; subsequent non-heading lines
      are skipped until the next heading.

    Returns list of (line_no, line_text) violations.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[validate_dual_grep] WARN: cannot read {path}: {exc}",
              file=sys.stderr)
        return []

    violations: list[tuple[int, str]] = []
    state = "other"  # one of: "other", "verification", "update_log"

    for lineno, line in enumerate(text.splitlines(), start=1):
        if _HEADING_LINE.match(line):
            # Strip leading # markers + whitespace to get heading text.
            heading_text = line.lstrip("#").strip()
            # Use search() (not match()) to allow phrase to appear
            # anywhere in the heading — handles "§1 — Mirror integrity
            # verification" style numbered headings. Update Log
            # exemption takes precedence when both match same heading.
            if _UPDATE_LOG_HEADING.search(heading_text):
                state = "update_log"
            elif _VERIFICATION_HEADING.search(heading_text):
                state = "verification"
            else:
                state = "other"
            continue

        # Only enforce when in active verification scope.
        if state != "verification":
            continue

        # Row-level checks (preserved from v6).
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
                f"[AP-AUTH-41 v7 violation] {path}:{lineno}: "
                f"alignment claim without dual (pos+neg) grep evidence",
                file=sys.stderr,
            )
            print(f"    {line}", file=sys.stderr)
            total_violations += 1

    if total_violations:
        print(
            f"\n[validate_dual_grep] FAIL: {total_violations} alignment "
            "claim(s) missing dual-grep evidence per AP-AUTH-41 v7 "
            "(verification-scope refined; Update Log exempt).",
            file=sys.stderr,
        )
        print(
            "Fix: each alignment-claim row in a verification section of "
            "a `*_VERIFICATION.md` file must include both `pos: ...` "
            "AND `neg: ...` tokens (see LAYER_5_V6_CHUNK_14_VERIFICATION.md "
            "§3 for the canonical dual-grep pattern).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
