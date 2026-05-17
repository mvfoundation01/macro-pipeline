"""L11.1 — Pre-install Python version gate.

Standalone script callable BEFORE the macro-pipeline package is installed.
Used by ``run.bat`` and ``run.sh`` to reject incompatible Python versions
with a clear Vietnamese message, instead of letting ``pip install -e .`` fail
with the cryptic ``requires-python`` error after the venv is already created.

Why a Python script (not pure batch / shell): version-string parsing in cmd
is fragile (the previous run.bat had no parsing at all; an attempt to parse
``3.14.3`` via simple integer comparisons broke V's machine with "... was
unexpected at this time."). Delegating to Python gives one source of truth,
cross-platform behavior, and a unit-testable function.

Usage
-----
    python scripts/check_python_version.py            # checks running Python
    python scripts/check_python_version.py 3.14.3     # checks explicit version
    python scripts/check_python_version.py --range    # prints supported range

Exit codes:
    0  OK — version is supported
    2  Too old (below MIN_VERSION)
    3  Unparseable input
    4  Too new (>= MAX_VERSION)
"""
from __future__ import annotations

import re
import sys

MIN_VERSION: tuple[int, int] = (3, 12)
MAX_VERSION: tuple[int, int] = (3, 14)  # exclusive — supports 3.12, 3.13
# L11.1 disposition: empirically verified 2026-05-17 that ``hmmlearn`` has
# no Python 3.14 wheels on PyPI; source build fails on Windows without a
# Visual C++ compiler. Until upstream ships 3.14 wheels we keep this cap
# aligned with pyproject.toml's ``requires-python = ">=3.12,<3.14"``.

_VERSION_RE = re.compile(r"^\s*(\d+)\.(\d+)")


def parse_version(version_str: str) -> tuple[int, int] | None:
    """Parse a Python-style version string to ``(major, minor)``.

    Tolerant of trailing patch and prerelease tags:
        "3.14.3"   -> (3, 14)
        "3.14.0b3" -> (3, 14)
        "  3.12  " -> (3, 12)
        "not-a-ver"-> None
    """
    if not isinstance(version_str, str):
        return None
    match = _VERSION_RE.match(version_str)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def check_version(version_str: str) -> tuple[int, str]:
    """Return ``(exit_code, message)`` describing whether ``version_str`` is supported."""
    parsed = parse_version(version_str)
    if parsed is None:
        return 3, (
            f"[ERROR] Khong nhan dien duoc Python version: {version_str!r}. "
            f"Yeu cau Python {MIN_VERSION[0]}.{MIN_VERSION[1]} - "
            f"{MAX_VERSION[0]}.{MAX_VERSION[1] - 1}."
        )
    major, minor = parsed
    if (major, minor) < MIN_VERSION:
        return 2, (
            f"[ERROR] Python {major}.{minor} qua cu. "
            f"Yeu cau Python {MIN_VERSION[0]}.{MIN_VERSION[1]}+. "
            "Tai ban moi tu https://www.python.org/downloads/"
        )
    if (major, minor) >= MAX_VERSION:
        return 4, (
            f"[ERROR] Python {major}.{minor} chua duoc kiem tra voi pipeline. "
            f"Yeu cau Python {MIN_VERSION[0]}.{MIN_VERSION[1]} - "
            f"{MAX_VERSION[0]}.{MAX_VERSION[1] - 1}. "
            "Tai phien ban tuong thich tu https://www.python.org/downloads/"
        )
    return 0, (
        f"[OK] Python {major}.{minor} duoc ho tro "
        f"(range {MIN_VERSION[0]}.{MIN_VERSION[1]} - "
        f"{MAX_VERSION[0]}.{MAX_VERSION[1] - 1})."
    )


def supported_range_str() -> str:
    return (
        f"Python >={MIN_VERSION[0]}.{MIN_VERSION[1]}, "
        f"<{MAX_VERSION[0]}.{MAX_VERSION[1]}"
    )


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "--range":
        print(supported_range_str())
        return 0
    if argv:
        version_str = argv[0]
    else:
        v = sys.version_info
        version_str = f"{v.major}.{v.minor}.{v.micro}"
    rc, msg = check_version(version_str)
    print(msg)
    return rc


if __name__ == "__main__":
    sys.exit(main())
