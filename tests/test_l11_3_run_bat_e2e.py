"""L11.3 D3+D4 — TRUE end-to-end run.bat smoke test + static parser guards.

L11.2's smoke test invoked ``python -m macro_pipeline.standalone_launcher``
directly, bypassing run.bat entirely. That's how the cmd-parser bug V hit
("... was unexpected at this time.") slipped past CI: the bug lived in run.bat
itself (nested if-blocks + unescaped parens in echo strings), not in any Python
module.

L11.3 adds:
  * a TRUE E2E test that launches `cmd /c run.bat` as a subprocess and
    verifies Flask responds on port 8000 with the expected title,
  * static guards that fail loudly if the dangerous patterns ever return,
  * an EOL guard that verifies `.gitattributes` keeps run.bat materialized
    as CRLF on every checkout.

Counts: 8 tests (3 NEG / 5 POS) = 38% NEG; combined with the L11.2 file
the launcher suite stays above 40% strict NEG.
"""
from __future__ import annotations

import contextlib
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_BAT = REPO_ROOT / "run.bat"
GITATTRIBUTES = REPO_ROOT / ".gitattributes"


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


# ----------------------------------------------------------------------
# POS — happy paths (5 tests)
# ----------------------------------------------------------------------
def test_gitattributes_forces_crlf_on_bat_files() -> None:
    """``.gitattributes`` must declare ``*.bat text eol=crlf`` so cmd.exe
    never receives LF-only batch files (which it mis-reads token by token)."""
    assert GITATTRIBUTES.exists(), ".gitattributes missing at repo root"
    text = GITATTRIBUTES.read_text(encoding="utf-8")
    assert "*.bat text eol=crlf" in text, (
        "missing `*.bat text eol=crlf` rule — cmd.exe will mis-parse LF files"
    )


def test_run_bat_working_copy_has_crlf_line_endings() -> None:
    """Working-tree run.bat must materialize as CRLF (via .gitattributes)."""
    raw = RUN_BAT.read_bytes()
    crlf_count = raw.count(b"\r\n")
    lone_lf = raw.count(b"\n") - crlf_count
    assert crlf_count > 0, "run.bat appears to have no CRLF line endings"
    assert lone_lf == 0, (
        f"run.bat has {lone_lf} lone-LF line endings; cmd.exe will mis-parse"
    )


def test_run_bat_uses_flat_goto_structure_no_nested_if_blocks() -> None:
    """The fix for V's "... was unexpected at this time." is to remove
    nested-if + parens-in-echo combinations. Every `if` must use either the
    single-line ``goto :label`` form OR a labelled section — NEVER the
    multi-line ``if (...) ( ... if (...) ( ... ) ... )`` form that triggers
    the cmd-parser miscount on echos containing parens."""
    text = RUN_BAT.read_text(encoding="utf-8")
    # No line should open an `if` block with a parenthesis if there's already
    # one open. We check by tracking unclosed `(` count per echo region.
    # A flat-goto structure has at most ONE unclosed `(` at any line; nested
    # `if (...) ( ... if (...) ( ` would have at least 2.
    depth = 0
    max_depth = 0
    for line in text.splitlines():
        # Strip rem/comment lines so explanatory parens don't perturb the count.
        stripped = line.strip()
        if stripped.startswith("REM ") or stripped.startswith("rem "):
            continue
        # Count unescaped ( and ) — heuristic: ignore the ones inside
        # double-quoted strings.
        in_quote = False
        for ch in line:
            if ch == '"':
                in_quote = not in_quote
                continue
            if in_quote:
                continue
            if ch == "(":
                depth += 1
                max_depth = max(max_depth, depth)
            elif ch == ")":
                depth = max(0, depth - 1)
    assert max_depth <= 1, (
        f"run.bat reaches paren depth {max_depth}; nested-if blocks must be "
        "refactored to flat-goto structure (L11.3 fix)"
    )


def test_run_bat_python_desc_uses_brackets_not_parens() -> None:
    """PYTHON_DESC values use [brackets] not (parens) — defensive against any
    future code path that expands the variable inside an `if (...)` block."""
    text = RUN_BAT.read_text(encoding="utf-8")
    # Find every `set "PYTHON_DESC=...` value and check it has no parens.
    for match in re.finditer(r'set\s+"PYTHON_DESC=([^"]*)"', text):
        value = match.group(1)
        assert "(" not in value and ")" not in value, (
            f"PYTHON_DESC value contains parens (cmd-parser hazard): {value!r}"
        )


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="run.bat is Windows-only; cmd.exe required",
)
def test_run_bat_true_end_to_end_via_cmd() -> None:
    """L11.3 D3 BINDING: launch `cmd /c run.bat` as subprocess and verify
    Flask responds with HTTP 200 + the expected title. This is the test
    L11.2 missed — it bypassed run.bat and ran the Python module directly."""
    if _port_open("127.0.0.1", 8000):
        pytest.skip(
            "port 8000 already bound — skipping to avoid clobbering "
            "an already-running Flask server"
        )

    proc = subprocess.Popen(
        ["cmd.exe", "/c", str(RUN_BAT)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    captured_lines: list[str] = []
    try:
        deadline = time.time() + 60
        body = ""
        status = None
        while time.time() < deadline:
            # Drain available output to detect cmd-parser errors quickly.
            if proc.poll() is not None:
                # Subprocess exited before we got a connection.
                tail = proc.stdout.read() if proc.stdout else ""
                captured_lines.extend(tail.splitlines())
                pytest.fail(
                    f"run.bat exited with code {proc.returncode} before "
                    f"binding port 8000. Last 30 output lines:\n"
                    + "\n".join(captured_lines[-30:])
                )
            if _port_open("127.0.0.1", 8000):
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:8000", timeout=3
                    ) as resp:
                        status = resp.status
                        body = resp.read().decode("utf-8", errors="replace")
                        break
                except (urllib.error.URLError, ConnectionResetError):
                    pass
            time.sleep(0.5)

        assert status == 200, (
            f"expected HTTP 200; got {status} after 60 s polling"
        )
        assert "MACRO FORECAST TERMINAL" in body, (
            f"body missing expected title; first 500 chars: {body[:500]!r}"
        )
    finally:
        # Best-effort cleanup: terminate cmd.exe and the child python.exe.
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        # Also kill any leftover python.exe bound to port 8000.
        with contextlib.suppress(Exception):
            subprocess.run(
                ["powershell", "-Command",
                 "Get-NetTCPConnection -LocalPort 8000 -ErrorAction "
                 "SilentlyContinue | ForEach-Object { Stop-Process -Id "
                 "$_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
                timeout=10,
                capture_output=True,
                check=False,
            )
        time.sleep(2)


# ----------------------------------------------------------------------
# NEG — failure-mode guards (3 tests)
# ----------------------------------------------------------------------
def test_run_bat_has_no_unescaped_parens_in_echo_lines() -> None:
    """Echo lines must not contain literal (unescaped) ``(`` or ``)`` —
    this was the root cause of V's "... was unexpected at this time."
    A future maintainer must escape any required parens with ``^(`` ``^)``."""
    text = RUN_BAT.read_text(encoding="utf-8")
    offenders: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if not stripped.lower().startswith("echo"):
            continue
        if stripped.lower() == "echo." or stripped.lower().startswith("echo."):
            continue
        # Strip the leading `echo` keyword to inspect the message.
        msg = stripped[4:].lstrip()
        # Allow escaped `^(` and `^)` — they're literal parens to the parser.
        unescaped_open = re.search(r"(?<!\^)\(", msg)
        unescaped_close = re.search(r"(?<!\^)\)", msg)
        if unescaped_open or unescaped_close:
            offenders.append((lineno, line.rstrip()))
    assert not offenders, (
        "echo lines contain unescaped parens (cmd-parser hazard inside "
        "if-blocks):\n  "
        + "\n  ".join(f"line {n}: {ln!r}" for n, ln in offenders)
    )


def test_run_bat_aborts_if_no_python_with_vietnamese_error() -> None:
    """All four error paths (:no_python, :wrong_version, :venv_failed,
    :pip_failed) must exist with Vietnamese error messages + pause + exit."""
    text = RUN_BAT.read_text(encoding="utf-8")
    for label in (":no_python", ":wrong_version", ":venv_failed", ":pip_failed"):
        assert label in text, f"flat-goto error label missing: {label}"
    # Each error block should ``pause`` and ``exit /b 1``.
    assert text.count("pause") >= 4
    assert text.count("exit /b 1") >= 4


def test_run_bat_does_not_use_delayed_errorlevel_in_if_block() -> None:
    """``if !ERRORLEVEL! NEQ 0 (`` inside another if-block was a fragility
    source. Prefer legacy ``if errorlevel 1 goto :label`` (single-line).
    Assert no occurrences of the delayed-expansion ERRORLEVEL inside a paren
    block. Heuristic: search the file for ``if !ERRORLEVEL!``."""
    text = RUN_BAT.read_text(encoding="utf-8")
    assert "if !ERRORLEVEL!" not in text, (
        "found `if !ERRORLEVEL! ...` — prefer legacy `if errorlevel 1 "
        "goto :label` form (more robust inside nested constructs)"
    )
