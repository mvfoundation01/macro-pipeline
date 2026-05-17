# Changelog

All notable changes to the macro-pipeline forecast platform are listed here.
Tags are pushed alongside each layer-complete commit (e.g. `l11-accept`).

The macro pipeline itself (L1-L9) was developed across ~50 convergent sub-phases;
this changelog starts at L10 when the user-facing surface area began shipping.

## [L11.2 — Environment Bootstrap + Launcher Resilience] — 2026-05-17

Tags: `l11-2-accept`, `l11-2-layer-complete`, `launcher-resilient-v1`.

### Bug (continued from L11.1)
L11.1's `check_python_version.py` correctly rejected Python 3.14 with a
clear Vietnamese message, but a user whose only installed Python is 3.14
was left with a closed loop: the launcher told them what to install but
didn't help them install it. They also still hit the cryptic
`... was unexpected at this time.` if PATH ordering surfaced 3.14 before
a usable interpreter. L11.2 closes both.

### Fix
- Python 3.13.13 installed on the dev machine via `py install 3.13`
  (pymanager); confirmed with `py -3.13 --version` → Python 3.13.13.
- `run.bat` refactored: 3-tier interpreter cascade — `py -3.13` first,
  then `py -3.12`, then PATH `python` validated by
  `check_python_version.py`. Each tier verified by running
  `<interpreter> -c ""` so a stale shim never satisfies the check.
- `run.sh` parallel refactor: `python3.13` → `python3.12` → `python3`
  with `check_python_version.py` validation on the generic fallback.
- `standalone_launcher.py` now reconfigures `sys.stdout` and
  `sys.stderr` to UTF-8 at startup. Without `chcp 65001`, the default
  Windows console codepage cp1252 cannot encode Vietnamese characters;
  the launcher crashed with `UnicodeEncodeError` on direct `python -m`
  invocation. `run.bat` already sets the codepage, but ad-hoc dev runs
  and the L11.2 smoke test invoke the launcher directly.
- Both launchers now invoke `python -m macro_pipeline.standalone_launcher`
  (instead of `macro_pipeline.webapp.app`) so they share the polished
  banner, browser-auto-open after 2 s, and OSError-on-port-in-use UX
  with the PyInstaller frozen mode.
- 9 new tests in `tests/test_l11_2_launcher_resilience.py` (44 % NEG),
  including a real subprocess + HTTP smoke test that verifies the
  Flask server returns HTTP 200 + "MACRO FORECAST TERMINAL" within 60 s.

### Verification
- `py install 3.13` → Python 3.13.13 installed (3.14/3.13/3.12 all
  coexist on this machine).
- Direct smoke: `python -m macro_pipeline.standalone_launcher` →
  HTTP 200 + 6743-byte HTML body containing "MACRO FORECAST TERMINAL",
  port 8000 released cleanly on terminate.
- Pytest: 9 new tests + 1486 / 1486 PASS full suite (1477 + 9 L11.2).
- Defense Test 12 + cap_cascade: 11 / 11 PASS (unchanged).
- Ruff (L11.2 scope): clean.

### V's deployment clone
`D:/macro_pipeline/macro-pipeline` updated to the L11.2 commit so V can
double-click `run.bat` and reach `http://localhost:8000` without any
manual Python install (Python 3.13 already on the machine via L11.2 §B).

## [L11.1 — Launcher Python 3.14 compat hotfix] — 2026-05-17

Tags: `l11-1-hotfix`, `launcher-py314-compat`.

### Bug
V tested `run.bat` on a Windows machine where `py -3.14` was the default
Python (3.14.3). The launcher displayed `[INFO] Python version: 3.14.3`
and then crashed with `... was unexpected at this time.`. Root cause: the
launcher never validated the Python version range. The user's 3.14
interpreter created the venv successfully, then `pip install -e .` failed
because `pyproject.toml` declared `requires-python = ">=3.12,<3.14"`. The
cmd parser cascaded the install error into the cryptic message above.

### Fix
- New `scripts/check_python_version.py` — standalone Python script
  callable BEFORE the package is installed, so version-string parsing
  happens in Python (not in cmd or bash). Tolerant of 3-component versions,
  beta tags, trailing whitespace. Returns clear Vietnamese errors with
  exit codes 2 (too old), 3 (unparseable), 4 (too new).
- `run.bat` and `run.sh` both invoke the check before creating the venv;
  abort cleanly when the user's Python is outside `[3.12, 3.14)`.
- 23 new tests in `tests/test_l11_1_launcher_version_check.py` (57% NEG)
  cover supported/too-old/too-new/unparseable inputs + subprocess
  exit-code contract + launcher-script invocation order.
- `pyproject.toml` left at `requires-python = ">=3.12,<3.14"` —
  empirically verified that `hmmlearn` has no Python 3.14 wheels yet
  and source build fails on Windows without a Visual C++ compiler.
  The check script's `MAX_VERSION` is enforced to match this cap by a
  cross-check test (`test_supported_range_matches_pyproject_toml`).

### Verification
- Manual: `py -3.14 scripts/check_python_version.py` → rc=4 with clear
  Vietnamese instructions to install Python 3.12 or 3.13.
- Pytest: 23 new tests; full suite 1477 / 1477 PASS.
- Defense Test 12 + cap_cascade: 11 / 11 PASS (unchanged).
- Ruff (L11.1 scope): clean.

## [L11 — Producer Integration v1] — 2026-05-17

Tags: `l11-accept`, `l11-layer-complete`, `producer-integration-v1`.

Closes the L10 binding constraint: ForecastInputs is now derived from real
historical panels bundled with the app, not heuristic modulators around L6-H
canonical defaults. Form values overlay the panels as latest observations.

### Added
- `macro_pipeline/data_snapshot/` — 35-panel bundled snapshot (~8 MB total)
  built from V's local `data/cache/` via `scripts/build_data_snapshot.py`.
- `macro_pipeline/webapp/snapshot_loader.py` — `SnapshotLoader` reads parquet
  panels by stem; `SnapshotManifest` parses `MANIFEST.json`.
- `macro_pipeline/webapp/producer_adapter.py` — `ProducerAdapter` derives all
  six ForecastInputs fields from snapshot panels with form overlay:
  - `point_estimates`: historical real-return mean + Campbell-Shiller CAPE
    mean-reversion at 10Y + cyclical form overlay.
  - `point_estimate_n_eff`: count of non-overlapping H-year windows.
  - `forecast_sigmas`: panel-derived shrinkage via `r_squared_panel`.
  - `analog_dispersions`: real cross-period dispersion of H-year forward returns.
  - `return_sigmas`: annualized realized vol from SPX TR / Shiller TR.
  - `recession_probabilities`: USREC base rate × horizon shape + form bumps.
- `scripts/build_data_snapshot.py` — builds the snapshot from V's cache;
  `--list` and `--check` modes for inspection/verification.
- `docs/build-plans/L11_PRODUCER_INTEGRATION_AUDIT.md` — formalized Phase 0
  audit with field→producer→snapshot-panel mapping + form-overlay table.
- PROVENANCE.json written into each report dir; results page renders
  "DATA PROVENANCE" section (Vietnamese) with snapshot date + producers run.
- `.gitignore` carve-out: `!macro_pipeline/data_snapshot/`.
- PyInstaller spec bundles `data_snapshot/` so the standalone exe contains
  the panels (no FRED API / internet required at forecast time).
- 25 new tests across 4 files (52% NEG aggregate; 50% NEG strict on
  `producer_adapter`).

### Changed
- `webapp/data_ingestion.py`: `ForecastInputsBuilder.build()` now delegates to
  `ProducerAdapter` (primary path) and falls back to the L10 heuristic
  modulator on any failure. Public method signature unchanged (Gate 8 BINDING).
  New `last_provenance` attribute set after every `build()` call.
- `webapp/routes/forecast.py`: writes `PROVENANCE.json` alongside the rendered
  L8 report.
- `webapp/routes/results.py`: `show()` now renders the Flask `results.html`
  template with provenance context (instead of serving L8 `index.html`
  directly); `asset()` route preserved for L8 sub-pages.
- `webapp/templates/help.html`: new Vietnamese section "Data Snapshot (L11)"
  explaining the producer path + snapshot rebuild procedure.

### Sensitivity invariant (D7)
- ±1 PMI unit → 1Y forecast Δ = 0.350pp (≥ 0.3pp target).

### Test counts
- L11 new tests: 25
- Full suite: 1454 / 1454 PASS (1429 baseline + 25 L11)
- Defense-in-depth Test 12 + 10 cap_cascade tests: 11 / 11 PASS

## [L10 — UX-First Deliverable v1] — 2026-05-17

Tags: `l10-accept`, `l10-layer-complete`, `ux-first-deliverable-v1`.

### Added
- Flask one-click web app (`macro_pipeline/webapp/`): input page, results page
  (serving L8 reports), Vietnamese help page, 3 Excel template downloads.
- Form-driven `ForecastInputs` construction via heuristic modulators around
  L6-H canonical defaults (closed by L11).
- `run.bat` / `run.sh` one-click launchers.
- PyInstaller standalone build (`pyinstaller/macro_forecast.spec` +
  `scripts/build_standalone.py` + `macro_pipeline/standalone_launcher.py`).
- `scripts/generate_excel_templates.py` — produces 3 Excel templates
  (yield-curve, credit-spreads, sentiment) with Vietnamese instructions.
- 47 tests across 4 files (49% NEG aggregate).
- Full suite at L10: 1429 / 1429 PASS.
