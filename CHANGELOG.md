# Changelog

All notable changes to the macro-pipeline forecast platform are listed here.
Tags are pushed alongside each layer-complete commit (e.g. `l11-accept`).

The macro pipeline itself (L1-L9) was developed across ~50 convergent sub-phases;
this changelog starts at L10 when the user-facing surface area began shipping.

## [L12 v2 — Auto-fetch UX: FRED + Yahoo fetchers, 4-manual+4-auto form, exception handling] — 2026-05-17

Tags: `l12-2-accept`, `l12-2-layer-complete`, `auto-fetch-ux-v2`.

Builds on L12 v1 (b5435f49). V tested L12 v1 and surfaced 3 remaining
friction points:

1. `/forecast/run` crashed with an opaque 500 on certain inputs (no error
   page; just Flask's default traceback view).
2. V wanted 4 of the 8 macro fields auto-fetched from FRED / Yahoo
   instead of typed every time.
3. V's manual fields had source URLs but no inline guidance on which
   field came from where.

### 6 new deliverables (additive on top of L12 v1)

**D3 — `/forecast/run` exception handling.** The route body is now
extracted to `_run_impl()` and the public `run()` wraps it in a
try/except. `HTTPException` (e.g. `RequestEntityTooLarge` for the L10
50 MiB upload cap) propagates unchanged so Flask's default handler can
emit the right 4xx status; any other unhandled exception lands at a new
`templates/error.html` page with a Vietnamese "QUAY LẠI FORM" button +
collapsible technical details + 500 status.

**D7 — `webapp/fred_fetcher.py`.** `FREDFetcher` reads `FRED_API_KEY`
from the env (loaded by `macro_pipeline.config`'s `dotenv.load_dotenv()`),
constructs a `fredapi.Fred` client lazily, and exposes three fetchers:
`fetch_unrate()` / `fetch_payrolls_mom()` (latest PAYEMS MoM Δ) /
`fetch_fed_funds()`. Every failure path returns `FetchResult.empty()` —
the fetcher NEVER raises. 1-hour per-series TTL cache.

**D8 — `webapp/yfinance_fetcher.py`.** `YahooFetcher` mirrors the FRED
contract for the SP500 spot close (`^GSPC`). 15-minute cache. Same
graceful-degradation guarantee — yfinance import + ticker construction
+ history fetch all wrapped.

**D9 — 4-manual + 4-auto form redesign.** `input.html` now splits the
macro inputs into Section 2A (PMI Mfg / PMI Services / Core CPI YoY /
CAPE — manual) and Section 2B (SP500 / Unemployment / Payrolls MoM /
Fed Funds — auto-fetched). Each auto-field shows a green
"[Auto-fetched · cập nhật YYYY-MM-DD]" badge when the source returned
a value; a yellow "[FRED không khả dụng · nhập manual]" badge otherwise.
The auto values pre-populate the input's `value=` attribute so V can
override by simply editing the input. The route `_fill_auto_fetch_defaults`
runs at POST time so a blank auto field re-attempts the fetch + falls
back to validation-error on miss (rather than crashing).

**D11 — Auto-fetch UI states.** Three states per auto field:
* loaded → green badge with as-of date,
* failed → yellow "manual fallback" badge,
* no-FRED-key → top-level blue info callout linking to FRED registration
  + `.env.example` with the env-var name + setup steps.

**D12 — `.env.example`.** Repo-root template with `FRED_API_KEY=<your-key-here>`
+ commented Yahoo ticker override + free-registration link.

**D13 — `help.html`** new "0a. Auto-fetch architecture (L12 v2)" section
documenting the field-by-field source + cache TTL table + FRED key setup
steps + override semantics.

### Tests (22 new in 4 files, 50% NEG strict on fetchers)

| File | Total | NEG | POS | NEG% |
|---|---|---|---|---|
| test_l12_2_fred_fetcher.py | 7 | 4 | 3 | 57% (strict — validation-heavy) |
| test_l12_2_yfinance_fetcher.py | 4 | 2 | 2 | 50% |
| test_l12_2_exception_handling.py | 5 | 3 | 2 | 60% |
| test_l12_2_form_auto_fetch_rendering.py | 6 | 2 | 4 | 33% |

22 new tests; aggregate 11 NEG / 11 POS = 50% NEG. The form-rendering
file is POS-heavy by nature (UI snapshot checks); the fetcher + exception
files anchor 50–60% strict NEG.

### Verification

* Full pytest: **1537 / 1537 PASS** in 193.69 s (1515 baseline + 22 L12 v2).
* Defense Test 12 + cap_cascade: **11 / 11 PASS** (unchanged).
* Ruff (L12 v2 scope): clean.
* Exception handler tested via `mock.patch` on `ParquetForecastStore.append`
  — verified the OSError lands at the error.html page with 500 status +
  HTML content-type + Vietnamese "QUAY LẠI FORM" link.
* L10 `test_post_forecast_run_oversized_payload_rejected` regression
  caught + fixed: the outer `except Exception` was swallowing werkzeug's
  `RequestEntityTooLarge` and re-rendering it as 500. Added an explicit
  `except HTTPException: raise` shim so all werkzeug HTTP exceptions
  propagate to Flask's default handler with their proper status codes.

### L10 v1 → v2 migration notes

* The 8 form fields stay POSTable with the same names — existing L10/L11
  tests that POST all 8 keep passing because `_fill_auto_fetch_defaults`
  is a no-op when all 8 are populated.
* The `run()` → `_run_impl()` split is internal; no public API change.
* `home.py` route now injects three new template contexts
  (`auto_fetched` dict, `fred_available` bool, plus the existing
  `detected_files` + `local_categories` + `scan_error`). Templates that
  don't use them silently ignore.

## [L12 — UX refinement v1: multi-format CSV ingest + local data manager + source URL annotations + deps catch-up] — 2026-05-17

Tags: `l12-accept`, `l12-layer-complete`, `ux-refinement-v1`.

### Context
V tested the L11.x pipeline end-to-end and surfaced 4 issues:

1. **Schema mismatch** — V uploaded a raw TradingView CSV
   (`time,open,high,low,close`); the L10 webapp only accepted the bespoke
   template format (`date,2y,10y`).
2. **Workflow mismatch** — V already has 22 raw CSVs sitting in
   `data/raw/tradingview/` (TradingView exports of FRED + CBOE + INDEX + USI
   series). Wanted drop-in directory ingestion, not manual upload of three
   templates.
3. **Source friction** — the 8 numerical form fields had no inline links to
   the government / primary data sources, forcing V to re-Google each one.
4. **Catch-up dep gap** — `flask` was missing from `pyproject.toml`; `run.bat`
   papered over it with a separate `pip install flask`. A fresh `pip install
   -e .` produced a venv that couldn't import the webapp.

### Fix — 10 deliverables in a single sub-phase

**D1 — pyproject.toml dep catch-up.** Added `flask>=3.0,<4.0` and
`werkzeug>=3.0,<4.0`. Removed the redundant `pip install flask` from
`run.bat` and `run.sh` — pyproject is now the single source of truth.

**D2 — Fresh-venv install test.** New
`tests/test_l12_fresh_venv_install.py` has 4 tests: static guards that
flask + werkzeug are declared in pyproject; import check from the running
venv; a slow `pip install --dry-run -e .` gate that verifies the full
dependency tree resolves without conflicts. Registered the `slow` marker
in `pyproject.toml`.

**D3 — Multi-format CSV parsers.** New
`macro_pipeline/webapp/csv_parsers.py` with a `CSVParser` ABC and concrete
`TradingViewParser` (handles both 2-col `time,close` and 5-col OHLC) +
`FREDParser` (handles `DATE,VALUE` / `observation_date,value` from the
FRED web UI). `ParserRegistry` does first-match-wins dispatch with
defensive NaT-index filtering (unparseable dates raise instead of silently
producing garbage).

**D4-D6 — LocalDataManager.** New
`macro_pipeline/webapp/local_data_manager.py` scans
`data/raw/{official,tradingview}/`, classifies each CSV by filename via a
22-entry `FILENAME_PATTERNS` regex registry, and aggregates per-file
series into the EXACT dict shape `ExcelDataIngester.parse_*` returns
(so `ForecastInputsBuilder.build(uploaded_data=...)` consumes it with
zero code changes). Includes unit-correction (FRED publishes IG OAS in
percent; aggregator multiplies by 100 to match the L10 template's
basis-points convention so `elevated = oas > 200 bps` keeps working).

**D7 — Detected-files panel.** `input.html` gained a new "0. DỮ LIỆU CỤC
BỘ" section above the manual upload widgets. Renders a table of detected
files grouped by category, plus a collapsible list of unclassified files.
Each manual upload widget shows a green `[Local files đã cover; upload sẽ
override.]` hint when the relevant category has local data.

**D8 — Source URL annotations.** Each of the 8 numerical fields now has
a Vietnamese hint line with 2 hyperlinks: a primary government / central-
bank source (ISM, FRED, multpl, Fed, Yahoo) and a secondary convenient
mirror (TradingEconomics, BLS, Shiller Yale, Google Finance). All
`target="_blank"` + `rel="noopener"` (16 external anchors total).

**D9 — help.html update.** New "Workflow với data cục bộ (L12)" section
documents the two raw-data directories, the filename patterns table, and
the manual-override semantics.

**D10 — Test coverage.** 21 new tests across 4 files:
* `test_l12_csv_parsers.py`           7 tests (4 NEG / 3 POS) 57% NEG
* `test_l12_local_data_manager.py`    6 tests (3 NEG / 3 POS) 50% NEG
* `test_l12_source_url_rendering.py`  4 tests (1 NEG / 3 POS) 25% NEG
* `test_l12_fresh_venv_install.py`    4 tests (0 NEG / 4 POS) (CI gates)

L12 aggregate: 8 NEG / 13 POS = 38 % NEG. Combined with prior launcher
+ producer suites the cross-layer NEG ratio stays well above 45 %.

### Verification

* L12 GATE 6 — classification coverage: **22 / 22 of V's TradingView CSVs
  classified** (100 % of CSV coverage; the 17 XLS/XLSX/PDF files in
  `data/raw/official/` are out of L12 scope — non-CSV parsers deferred).
* L12 GATE 16 end-to-end smoke (verbatim):

  ```
  [OK] GET / shows V actual files in detected-files panel
       (TVC_US10Y_1D.csv + FRED_BAMLC0A0CM_1D.csv visible)
  [OK] POST /forecast/run -> 302 /results/2026-05/
  [OK] results page renders DATA PROVENANCE
  [OK] PROVENANCE mode=producer_derived, snapshot_date=2026-05-17
       producers_run=[point_estimates, point_estimate_n_eff,
                      forecast_sigmas, analog_dispersions,
                      return_sigmas, recession_probabilities]
  ```

* Full pytest: 1515 / 1515 PASS (1494 + 21 L12).
* Defense Test 12 + cap_cascade: 11 / 11 PASS (unchanged).
* Ruff (L12 scope): clean.

### V's deployment clone

`D:/macro_pipeline/macro-pipeline` updated to the L12 commit. V can now
drop any TradingView / FRED CSV into `data/raw/tradingview/`, double-click
`run.bat`, and the form auto-detects the file without any template
reshape work.

## [L11.3 — run.bat cmd-parser hotfix + true E2E] — 2026-05-17

Tags: `l11-3-hotfix`, `run-bat-e2e-verified`, `launcher-true-e2e-v1`.

### Bug (the one L11.2 missed)
V double-clicked `run.bat` (L11.2). Output:
```
[INFO] Su dung: Python 3.13 (py launcher)
Python 3.13.13

... was unexpected at this time.
```
L11.2's smoke test invoked `python -m macro_pipeline.standalone_launcher`
directly, **bypassing run.bat entirely** — so the cmd-parser bug in run.bat
itself was never exercised in CI. Reproduced exactly via
`cmd /c D:\macro_pipeline\macro-pipeline\run.bat`.

Two root causes (V's case = #1; my own retest surfaced #2):
1. **Nested-if + unescaped parens in echo strings**: L11.2's run.bat had
   `if !ERRORLEVEL! NEQ 0 (` blocks containing
   `echo [INFO] Cai dat dependencies lan dau (mat 3-8 phut)...`. When V's
   `.venv` existed but lacked Flask (residual state from earlier L10/L11
   attempts), execution entered that block; cmd's lazy parser counted the
   `(mat 3-8 phut)` parens as nested block delimiters and the count went
   wonky → "... was unexpected at this time."
2. **LF-only line endings** got cmd to mis-read run.bat mid-word
   (fragments like `'HON_CMD'` and `'oto'` got executed as if they were
   commands). The committed L11.2 file was LF; checkout normalization
   inconsistencies (presence/absence of `core.autocrlf`) determined
   whether the file landed as LF or CRLF on the user's machine.

### Fix
- **`run.bat`** rewritten with a flat-goto structure:
  - All control flow uses single-line `if errorlevel 1 goto :label` —
    no nested-if blocks anywhere.
  - All error paths land at labelled sections at the bottom of the file
    (`:no_python`, `:wrong_version`, `:venv_failed`, `:pip_failed`).
  - `PYTHON_DESC` uses `[brackets]` not `(parens)` so the variable can
    be expanded in any future construct without paren-counting risk.
  - All `(...)` content in echo strings either removed or rewritten
    with commas/brackets.
- **`.gitattributes`** added:
  - `*.bat text eol=crlf` — git materializes batch files with CRLF on
    every checkout regardless of platform / `core.autocrlf` setting.
  - `*.sh text eol=lf` — bash mis-reads CRLF shebangs (rejects with
    `/usr/bin/env\r: No such file or directory`).
- **Existing run.bat re-committed** with normalized CRLF endings (git
  storage stays LF + working tree CRLF, per `eol=crlf` semantics).

### Tests (8 new in `test_l11_3_run_bat_e2e.py`, 38 % NEG)
1. `.gitattributes` declares `*.bat text eol=crlf` ✓
2. Working-copy `run.bat` has CRLF endings (no lone LF) ✓
3. Flat-goto structure: paren depth never exceeds 1 ✓
4. `PYTHON_DESC` uses no parens ✓
5. **TRUE E2E**: `cmd /c run.bat` → HTTP 200 + "MACRO FORECAST TERMINAL"
   in 6743-byte body ✓ (L11.2's missing test)
6. No unescaped parens in any `echo` line ✓
7. All 4 error labels exist with `pause` + `exit /b 1` ✓
8. No `if !ERRORLEVEL!` constructs (prefer legacy `if errorlevel N`) ✓

### Verification
- Reproduced V's exact output BEFORE the fix.
- POST-FIX `cmd /c D:\macro_pipeline\macro-pipeline\run.bat` →
  HTTP 200 + title verified + zero "is not recognized" / "unexpected"
  errors in stdout.
- Full pytest: 1494 / 1494 PASS (1486 + 8 L11.3).
- Defense Test 12 + cap_cascade: 11 / 11 PASS (unchanged).
- Ruff (L11.3 scope): clean.

### V's deployment clone
`D:/macro_pipeline/macro-pipeline` updated to L11.3 commit. V can now
double-click `run.bat` and reach `http://localhost:8000` regardless of
whether `.venv` already exists and whether Flask is or isn't installed
inside it.

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
