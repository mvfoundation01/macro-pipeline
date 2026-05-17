"""L10 D12 — Tests for ``standalone_launcher.py`` + PyInstaller spec.

Counts: 7 tests (3 NEG / 4 POS) = 43% NEG.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


# ----------------------------------------------------------------------
# POS — happy paths (4 tests)
# ----------------------------------------------------------------------
def test_standalone_launcher_main_callable() -> None:
    from macro_pipeline.standalone_launcher import main

    assert callable(main)


def test_get_resource_path_returns_repo_root_in_dev_mode() -> None:
    from macro_pipeline.standalone_launcher import _get_resource_path

    # In dev mode (not frozen), should return the repo root (two levels up
    # from macro_pipeline/standalone_launcher.py).
    sys_was_frozen = getattr(sys, "frozen", False)
    assert not sys_was_frozen  # test guard — we're in dev mode
    path = _get_resource_path()
    assert path.exists()
    assert (path / "macro_pipeline").exists()


def test_pyinstaller_spec_file_exists() -> None:
    spec = REPO_ROOT / "pyinstaller" / "macro_forecast.spec"
    assert spec.exists()
    text = spec.read_text(encoding="utf-8")
    assert "Analysis(" in text
    assert "MacroForecastTerminal" in text


def test_build_standalone_script_imports_cleanly() -> None:
    """Build script must be importable without side-effects (main not auto-called)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "build_standalone",
        REPO_ROOT / "scripts" / "build_standalone.py",
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    assert hasattr(module, "main")
    assert callable(module.main)


# ----------------------------------------------------------------------
# NEG — strict (3 tests)
# ----------------------------------------------------------------------
def test_run_bat_exists_at_repo_root() -> None:
    """run.bat must exist; missing = D7 not shipped."""
    run_bat = REPO_ROOT / "run.bat"
    assert run_bat.exists()
    text = run_bat.read_text(encoding="utf-8")
    # Must not reference an interactive editor or skip-hooks pattern.
    assert "git rebase -i" not in text
    assert "macro_pipeline.webapp.app" in text


def test_run_sh_exists_and_has_shebang() -> None:
    """run.sh must exist and start with a POSIX shebang."""
    run_sh = REPO_ROOT / "run.sh"
    assert run_sh.exists()
    first_line = run_sh.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("#!"), (
        f"Expected shebang first line; got {first_line!r}"
    )


def test_standalone_launcher_rejects_bound_port_gracefully(monkeypatch) -> None:
    """When app.run raises OSError 'address already in use', main() returns 1."""
    from macro_pipeline import standalone_launcher

    class _FakeApp:
        def run(self, *args, **kwargs):
            raise OSError("[Errno 48] address already in use")

    def fake_create_app(_config=None):
        return _FakeApp()

    monkeypatch.setattr(standalone_launcher, "_open_browser_delayed", lambda *_: None)
    # The factory is imported inside main(); patch its symbol in the source module.
    from macro_pipeline.webapp import app as webapp_app_module

    monkeypatch.setattr(webapp_app_module, "create_app", fake_create_app)
    # input() blocks; replace with a no-op.
    monkeypatch.setattr("builtins.input", lambda *_: "")

    rc = standalone_launcher.main()
    assert rc == 1
