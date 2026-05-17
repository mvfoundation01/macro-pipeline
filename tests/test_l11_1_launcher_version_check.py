"""L11.1 — Tests for ``scripts/check_python_version.py``.

The launcher (`run.bat` / `run.sh`) delegates Python-version validation to
this script so neither shell needs to parse 3-component versions. Tests
cover the parse function + exit-code contract directly.

Counts: 14 tests (8 NEG / 6 POS) = 57% NEG.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "check_python_version.py"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "check_python_version", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ----------------------------------------------------------------------
# POS — happy paths (6 tests)
# ----------------------------------------------------------------------
def test_script_exists_at_expected_path() -> None:
    assert SCRIPT_PATH.exists(), f"check_python_version.py missing at {SCRIPT_PATH}"


@pytest.mark.parametrize("version", ["3.12.0", "3.12.10", "3.13.0", "3.13.5"])
def test_supported_versions_return_zero(version: str) -> None:
    module = _load_script_module()
    rc, msg = module.check_version(version)
    assert rc == 0, f"expected rc=0 for {version!r}; got rc={rc} msg={msg!r}"
    assert "duoc ho tro" in msg or "OK" in msg


def test_parse_strips_whitespace_and_extracts_major_minor() -> None:
    module = _load_script_module()
    assert module.parse_version("  3.13.2  ") == (3, 13)
    assert module.parse_version("3.14.0b3") == (3, 14)  # beta tag tolerated
    assert module.parse_version("3.12") == (3, 12)  # 2-component


def test_default_uses_running_python_version() -> None:
    """Invoking the script with no args returns rc=0 because pytest itself
    runs under a supported Python (the dev venv is 3.12)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "OK" in result.stdout or "duoc ho tro" in result.stdout


def test_range_flag_prints_supported_range() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--range"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "3.12" in result.stdout
    assert "3.14" in result.stdout  # the exclusive upper bound


def test_supported_range_matches_pyproject_toml() -> None:
    """The script's MAX_VERSION must agree with ``pyproject.toml``'s
    ``requires-python`` cap to prevent V from succeeding the pre-check and
    then failing the pip install."""
    module = _load_script_module()
    pyproject = (SCRIPT_PATH.parent.parent / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    # Expect `requires-python = ">=3.12,<3.14"` (or similar with matching cap).
    expected_cap = f"<{module.MAX_VERSION[0]}.{module.MAX_VERSION[1]}"
    assert (
        expected_cap in pyproject
    ), f"pyproject.toml requires-python must contain {expected_cap!r}"


# ----------------------------------------------------------------------
# NEG — rejections (8 tests)
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "version", ["3.14.3", "3.14.0", "3.14.0b3", "3.15.0", "4.0.0"]
)
def test_too_new_versions_rejected_with_rc4(version: str) -> None:
    module = _load_script_module()
    rc, msg = module.check_version(version)
    assert rc == 4, f"expected rc=4 for {version!r}; got rc={rc} msg={msg!r}"
    assert "chua duoc kiem tra" in msg


@pytest.mark.parametrize("version", ["3.11.99", "3.10.0", "2.7.18"])
def test_too_old_versions_rejected_with_rc2(version: str) -> None:
    module = _load_script_module()
    rc, msg = module.check_version(version)
    assert rc == 2, f"expected rc=2 for {version!r}; got rc={rc} msg={msg!r}"
    assert "qua cu" in msg


def test_unparseable_input_rejected_with_rc3() -> None:
    module = _load_script_module()
    rc, msg = module.check_version("not-a-version")
    assert rc == 3
    assert "Khong nhan dien" in msg


def test_empty_string_unparseable() -> None:
    module = _load_script_module()
    assert module.parse_version("") is None
    rc, _ = module.check_version("")
    assert rc == 3


def test_non_string_input_unparseable() -> None:
    module = _load_script_module()
    assert module.parse_version(None) is None  # type: ignore[arg-type]
    assert module.parse_version(3.14) is None  # type: ignore[arg-type]


def test_subprocess_exit_code_propagates_for_rejection() -> None:
    """Running the script as subprocess with a rejected version exits non-zero
    so run.bat / run.sh's ``errorlevel`` / ``$?`` checks trigger correctly."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "3.14.3"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 4
    assert "chua duoc kiem tra" in result.stdout


def test_run_bat_invokes_check_script() -> None:
    """``run.bat`` must call ``scripts\\check_python_version.py`` so V can't
    silently fall through to pip install with an incompatible Python.

    L11.2 update: substring relaxed from ``python -m venv`` to ``-m venv``
    because L11.2's run.bat invokes venv creation via a variable
    (``!PYTHON_CMD! -m venv .venv``) chosen by the py-launcher cascade.
    """
    repo_root = SCRIPT_PATH.parent.parent
    run_bat = (repo_root / "run.bat").read_text(encoding="utf-8")
    assert "check_python_version.py" in run_bat
    check_idx = run_bat.index("check_python_version.py")
    venv_idx = run_bat.index("-m venv .venv")
    assert check_idx < venv_idx, (
        "run.bat must call check_python_version.py BEFORE creating the venv"
    )


def test_run_sh_invokes_check_script() -> None:
    """L11.2 update: same relaxation as run.bat (variable-driven venv)."""
    repo_root = SCRIPT_PATH.parent.parent
    run_sh = (repo_root / "run.sh").read_text(encoding="utf-8")
    assert "check_python_version.py" in run_sh
    check_idx = run_sh.index("check_python_version.py")
    venv_idx = run_sh.index("-m venv .venv")
    assert check_idx < venv_idx
