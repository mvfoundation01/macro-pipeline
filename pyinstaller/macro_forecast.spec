# L10 D10 — PyInstaller spec for standalone .exe build.
# -*- mode: python ; coding: utf-8 -*-
#
# Build:  python scripts/build_standalone.py
#
# Bundles: Python + dependencies + Flask app + webapp templates + L8 UI templates
#          + Excel templates (must be generated before build via
#          scripts/generate_excel_templates.py).
from pathlib import Path

block_cipher = None

# When PyInstaller runs this spec, the cwd is `pyinstaller/`, so we resolve
# the repo root one level up. The path is also used inside data tuples below.
spec_root = Path.cwd()
repo_root = spec_root.parent

a = Analysis(
    [str(repo_root / "macro_pipeline" / "standalone_launcher.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=[
        (
            str(repo_root / "macro_pipeline" / "webapp" / "templates"),
            "macro_pipeline/webapp/templates",
        ),
        (
            str(repo_root / "macro_pipeline" / "webapp" / "static"),
            "macro_pipeline/webapp/static",
        ),
        (
            str(repo_root / "macro_pipeline" / "ui" / "templates"),
            "macro_pipeline/ui/templates",
        ),
        (
            str(repo_root / "macro_pipeline" / "ui" / "static"),
            "macro_pipeline/ui/static",
        ),
    ],
    hiddenimports=[
        "flask",
        "jinja2",
        "openpyxl",
        "pyarrow",
        "pandas",
        "macro_pipeline.ensemble.aggregator",
        "macro_pipeline.persistence",
        "macro_pipeline.ui.renderer",
        "macro_pipeline.webapp.app",
        "macro_pipeline.webapp.data_ingestion",
        "macro_pipeline.webapp.routes.home",
        "macro_pipeline.webapp.routes.forecast",
        "macro_pipeline.webapp.routes.results",
        "macro_pipeline.webapp.routes.help",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MacroForecastTerminal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
