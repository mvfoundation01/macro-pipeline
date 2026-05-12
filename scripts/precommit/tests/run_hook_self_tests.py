"""Self-test runner for pre-commit hook validators.

Runs each validator against its paired should_pass / should_fail fixture
and asserts the expected exit code (0 or 1).

Exit codes:
    0 = all 4 self-tests pass
    1 = any self-test fails

Usage:
    python scripts/precommit/tests/run_hook_self_tests.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PRECOMMIT_DIR = REPO_ROOT / "scripts" / "precommit"
FIXTURES_DIR = PRECOMMIT_DIR / "tests"

# Each tuple: (validator_module, fixture_filename, expected_exit_code, label)
SELF_TESTS = [
    (
        "validate_dual_grep_in_verification.py",
        "dual_grep_should_pass.md",
        0,
        "dual_grep pass",
    ),
    (
        "validate_dual_grep_in_verification.py",
        "dual_grep_should_fail.md",
        1,
        "dual_grep fail",
    ),
    (
        "validate_no_cumulative_arithmetic.py",
        "no_cumulative_arithmetic_should_pass.md",
        0,
        "no_cumulative_arithmetic pass",
    ),
    (
        "validate_no_cumulative_arithmetic.py",
        "no_cumulative_arithmetic_should_fail.md",
        1,
        "no_cumulative_arithmetic fail",
    ),
]


def _staged_path_for_fixture(fixture: Path) -> Path:
    """The validators only scan files whose POSIX path begins with `docs/`.

    For self-test, we stage each fixture under a synthetic docs/ relative
    path so the in-scope check passes. We pass the staged path to the
    validator without actually moving the file; the validator uses
    Path.exists() + Path.as_posix() for the in-scope check.

    Workaround: we pass the fixture path through a docs/ prefix by
    leveraging the validator's `is_in_scope` heuristic. Concretely: we
    create a symlink-like docs/ pointer OR pass the file as `docs/<name>`
    by changing the cwd at invocation. The simplest portable approach is
    to copy the fixture to a temp `docs/` path within the repo for the
    duration of the test, then clean up.
    """
    raise NotImplementedError  # placeholder; see _run_one for actual approach


def _run_one(validator_name: str, fixture_filename: str, expected: int,
             label: str) -> bool:
    """Run one validator against one fixture; return True if pass.

    Strategy: stage the fixture under a temporary docs/ subdirectory so
    the validator's in-scope check passes. Tear down after.
    """
    fixture_src = FIXTURES_DIR / fixture_filename
    if not fixture_src.exists():
        print(f"FAIL [{label}]: fixture not found: {fixture_src}",
              file=sys.stderr)
        return False

    docs_staging = REPO_ROOT / "docs" / "_precommit_selftest"
    docs_staging.mkdir(parents=True, exist_ok=True)
    staged_path = docs_staging / fixture_filename
    staged_path.write_text(
        fixture_src.read_text(encoding="utf-8"), encoding="utf-8"
    )

    validator_path = PRECOMMIT_DIR / validator_name
    try:
        # Use relative path (docs/...) for the in-scope check (validator
        # uses Path.as_posix().startswith("docs/")).
        relative = staged_path.relative_to(REPO_ROOT).as_posix()
        result = subprocess.run(
            [sys.executable, str(validator_path), relative],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
    finally:
        # Clean up the staging file but keep the directory in case other
        # self-tests are concurrent (none currently).
        try:
            staged_path.unlink()
        except OSError:
            pass

    actual = result.returncode
    if actual == expected:
        print(f"PASS [{label}]: exit {actual} as expected")
        return True
    else:
        print(
            f"FAIL [{label}]: expected exit {expected}, got {actual}",
            file=sys.stderr,
        )
        if result.stdout:
            print(f"    stdout:\n{result.stdout}", file=sys.stderr)
        if result.stderr:
            print(f"    stderr:\n{result.stderr}", file=sys.stderr)
        return False


def main() -> int:
    print(f"Running {len(SELF_TESTS)} self-tests on pre-commit validators...\n")
    passed = 0
    failed = 0
    for validator_name, fixture, expected, label in SELF_TESTS:
        if _run_one(validator_name, fixture, expected, label):
            passed += 1
        else:
            failed += 1

    # Clean up staging directory if empty.
    docs_staging = REPO_ROOT / "docs" / "_precommit_selftest"
    try:
        docs_staging.rmdir()
        # Also try to remove parent docs/ if empty (it shouldn't be, but
        # in case this is the only docs/ content).
        try:
            (REPO_ROOT / "docs").rmdir()
        except OSError:
            pass
    except OSError:
        pass

    print(f"\nSummary: {passed} passed, {failed} failed (of {len(SELF_TESTS)})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
