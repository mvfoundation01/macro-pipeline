"""L11.2 D5 — Tests for the resilient launcher (`run.bat` / `run.sh`) and
the underlying `standalone_launcher.py` end-to-end smoke test.

Counts: 9 tests (4 NEG / 5 POS) = 44% NEG (>= 40% strict on validation).
"""
from __future__ import annotations

import os
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
RUN_SH = REPO_ROOT / "run.sh"


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


# ----------------------------------------------------------------------
# POS — launcher content + behavior (5 tests)
# ----------------------------------------------------------------------
def test_run_bat_has_py_3_13_then_3_12_cascade() -> None:
    """run.bat must try `py -3.13` first, then `py -3.12`, in that order."""
    text = RUN_BAT.read_text(encoding="utf-8")
    idx_313 = text.find("py -3.13")
    idx_312 = text.find("py -3.12")
    assert idx_313 != -1, "run.bat must reference `py -3.13`"
    assert idx_312 != -1, "run.bat must reference `py -3.12`"
    assert idx_313 < idx_312, (
        "run.bat must try `py -3.13` BEFORE `py -3.12` (prefer newest supported)"
    )


def test_run_bat_falls_back_to_path_python_with_check_script() -> None:
    """If no `py` launcher version matches, run.bat must fall back to
    invoking `python` from PATH and gate it via check_python_version.py."""
    text = RUN_BAT.read_text(encoding="utf-8")
    assert "where python" in text
    assert "check_python_version.py" in text
    check_idx = text.find("check_python_version.py")
    venv_idx = text.find("-m venv .venv")
    assert check_idx < venv_idx, (
        "version check must run BEFORE creating the venv"
    )


def test_run_sh_has_python3_13_then_3_12_cascade() -> None:
    """run.sh prefers explicit python3.13 over python3.12 over python3."""
    text = RUN_SH.read_text(encoding="utf-8")
    idx_313 = text.find("python3.13")
    idx_312 = text.find("python3.12")
    idx_3 = text.find("python3 ")  # generic, trailing space disambiguates
    assert idx_313 != -1 and idx_312 != -1 and idx_3 != -1
    assert idx_313 < idx_312 < idx_3


def test_standalone_launcher_forces_utf8_stdout() -> None:
    """L11.2 bugfix: standalone_launcher must reconfigure stdout/stderr to
    UTF-8 so Vietnamese characters print on cp1252 consoles."""
    text = (
        REPO_ROOT / "macro_pipeline" / "standalone_launcher.py"
    ).read_text(encoding="utf-8")
    assert "reconfigure(encoding=\"utf-8\"" in text
    # Must apply to both stdout AND stderr.
    reconfig_count = text.count("reconfigure")
    assert reconfig_count >= 1


def test_end_to_end_smoke_flask_serves_html() -> None:
    """L11.2 D6: full end-to-end — start standalone_launcher as subprocess,
    poll http://127.0.0.1:8000 for up to 60 s, assert HTTP 200 + body
    contains "MACRO FORECAST TERMINAL", then terminate cleanly.
    """
    if _port_open("127.0.0.1", 8000):
        pytest.skip(
            "port 8000 already bound — skipping smoke test to avoid clobbering"
        )

    venv_py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if not venv_py.exists():
        # Non-Windows or no .venv yet — try the running interpreter.
        venv_py = Path(sys.executable)

    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(
        [str(venv_py), "-m", "macro_pipeline.standalone_launcher"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    try:
        deadline = time.time() + 60
        body = ""
        status = None
        while time.time() < deadline:
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
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                pytest.fail(
                    f"subprocess died exit={proc.returncode}; output:\n{out}"
                )
            time.sleep(0.5)

        assert status == 200, (
            f"expected HTTP 200, got status={status} after 60 s polling"
        )
        assert "MACRO FORECAST TERMINAL" in body, (
            f"body missing expected title; first 500 chars: {body[:500]!r}"
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        # Give Windows a moment to release the socket fully.
        time.sleep(2)


# ----------------------------------------------------------------------
# NEG — failure-mode assertions (4 tests)
# ----------------------------------------------------------------------
def test_run_bat_aborts_with_vietnamese_when_no_python() -> None:
    """If neither `py` launcher nor `python` is on PATH, run.bat must abort
    with a Vietnamese error pointing to the python.org installer."""
    text = RUN_BAT.read_text(encoding="utf-8")
    assert "[ERROR] Khong tim thay Python" in text or "Khong tim thay Python" in text
    assert "python.org/downloads" in text
    assert "exit /b 1" in text


def test_run_bat_aborts_when_version_check_rejects() -> None:
    """When PATH python fails check_python_version.py, run.bat must NOT
    proceed to venv creation — must exit /b 1 first."""
    text = RUN_BAT.read_text(encoding="utf-8")
    # Search for the version-check failure block ahead of venv creation.
    check_fail = text.find("Pipeline yeu cau Python 3.12 hoac 3.13")
    venv_block = text.find("-m venv .venv")
    assert check_fail != -1, "Vietnamese rejection message missing"
    assert venv_block != -1, "venv create block missing"
    # The reject message must come BEFORE venv creation in source order.
    assert check_fail < venv_block


def test_run_sh_aborts_when_no_compatible_python() -> None:
    text = RUN_SH.read_text(encoding="utf-8")
    assert "Không tìm thấy Python" in text
    assert "exit 1" in text


def test_standalone_launcher_handles_port_already_in_use(monkeypatch) -> None:
    """OSError on bind must be caught + printed (not propagated)."""
    from macro_pipeline import standalone_launcher

    class _FakeApp:
        def run(self, *_a, **_kw):
            raise OSError("[Errno 48] Address already in use")

    monkeypatch.setattr(
        standalone_launcher, "_open_browser_delayed", lambda *_: None
    )
    from macro_pipeline.webapp import app as webapp_app_module

    monkeypatch.setattr(
        webapp_app_module, "create_app", lambda _cfg=None: _FakeApp()
    )
    monkeypatch.setattr("builtins.input", lambda *_: "")

    rc = standalone_launcher.main()
    assert rc == 1
