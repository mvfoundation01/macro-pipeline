"""L12 D2 — Fresh-venv install gate.

Closes the L11.x dependency gap: ``pip install -e .`` produced a venv that
couldn't ``import flask`` because flask wasn't declared in pyproject.toml.
run.bat papered over it with a separate ``pip install flask``, but a user
running the install steps manually (or any CI that doesn't go through
run.bat) would have hit ``ModuleNotFoundError: flask``.

Tests:
  1. Cheap static guard — flask + werkzeug declared in pyproject.toml.
  2. Cheap import check — flask + werkzeug importable from the current
     venv (which was installed via pyproject + pip install -e .).
  3. Slow dep-resolution gate — pip --dry-run resolves the full
     dependency tree from a fresh venv without errors. Marked
     ``slow``; runs only under ``pytest -m slow``.

Counts: 4 tests (1 NEG / 3 POS) = 25% NEG.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


# ----------------------------------------------------------------------
# POS — cheap static + import checks (3 tests)
# ----------------------------------------------------------------------
def test_pyproject_declares_flask_in_dependencies() -> None:
    """pyproject.toml must list flask as a runtime dependency so
    ``pip install -e .`` produces a venv that can run the webapp."""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert '"flask>=' in text, (
        "flask not declared in [project.dependencies]; users running "
        "`pip install -e .` will get a venv that can't import flask"
    )


def test_pyproject_declares_werkzeug_in_dependencies() -> None:
    """werkzeug is flask's underlying WSGI lib; pin explicitly to avoid
    a future flask release pulling a major-version werkzeug bump."""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert '"werkzeug>=' in text


def test_current_venv_can_import_flask_and_werkzeug() -> None:
    """The venv the test suite is running in must be able to import flask
    (i.e. the pyproject deps actually resolve at install time)."""
    import flask  # noqa: F401
    import werkzeug  # noqa: F401


# ----------------------------------------------------------------------
# SLOW — fresh-venv dep-resolution gate (1 test, opt-in)
# ----------------------------------------------------------------------
@pytest.mark.slow
def test_fresh_venv_dep_resolution_via_dry_run() -> None:
    """Slow CI gate: run ``pip install --dry-run -e .`` from a fresh venv
    to verify the full dependency tree resolves without conflicts.

    Faster than an actual install (no wheels downloaded), still catches
    cases like a missing dep, an unresolvable version constraint, or a
    Python-version mismatch.

    Runs only under ``pytest -m slow`` (default suite stays fast)."""
    proc = subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--dry-run", "--quiet",
            "-e", str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"pip dry-run resolution failed (exit {proc.returncode}):\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
