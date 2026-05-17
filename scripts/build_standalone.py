"""L10 D10 — Build PyInstaller standalone executable.

Per Strategic L10 single comprehensive pre-flight 2026-05-17.

Generates Excel templates first (PyInstaller bundles them as data), then
invokes PyInstaller with ``pyinstaller/macro_forecast.spec`` from the repo
root. Outputs to ``dist/MacroForecastTerminal.exe`` (Windows) or
``dist/MacroForecastTerminal`` (Linux/macOS).

Usage
-----
    python scripts/build_standalone.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).parent.parent
    spec_file = repo_root / "pyinstaller" / "macro_forecast.spec"
    if not spec_file.exists():
        print(f"[ERROR] Spec file missing: {spec_file}")
        return 1

    print("[INFO] Building standalone executable via PyInstaller...")
    print("[INFO] This may take 3-10 minutes on first build.")

    templates_dir = (
        repo_root / "macro_pipeline" / "webapp" / "static" / "templates"
    )
    if not (templates_dir / "yield-curve.xlsx").exists():
        print("[INFO] Generating Excel templates first...")
        gen_script = repo_root / "scripts" / "generate_excel_templates.py"
        result = subprocess.run(
            [sys.executable, str(gen_script)],
            cwd=str(repo_root),
        )
        if result.returncode != 0:
            print("[ERROR] Excel template generation failed.")
            return 1

    pyinstaller_dir = repo_root / "pyinstaller"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(spec_file),
            "--clean",
            "--noconfirm",
            "--distpath",
            str(repo_root / "dist"),
            "--workpath",
            str(repo_root / "build"),
        ],
        cwd=str(pyinstaller_dir),
    )
    if result.returncode != 0:
        print("[ERROR] PyInstaller build failed.")
        return 1

    candidates = [
        repo_root / "dist" / "MacroForecastTerminal.exe",
        repo_root / "dist" / "MacroForecastTerminal",
    ]
    for candidate in candidates:
        if candidate.exists():
            size_mb = candidate.stat().st_size / (1024 * 1024)
            print(f"[OK] Standalone built: {candidate} ({size_mb:.1f} MB)")
            return 0
    print(
        "[WARN] PyInstaller exit-0 but no executable found at expected paths "
        f"({[str(c) for c in candidates]})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
