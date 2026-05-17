# Changelog

All notable changes to the macro-pipeline forecast platform are listed here.
Tags are pushed alongside each layer-complete commit (e.g. `l11-accept`).

The macro pipeline itself (L1-L9) was developed across ~50 convergent sub-phases;
this changelog starts at L10 when the user-facing surface area began shipping.

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
