# LAYER 3.5E — Pre-Flight Audit (Cache Atomicity Sweep)

**Spec ref**: `LAYER_3_5_BUILD_SPEC.md` §7 (3.5E)
**Branch**: `claude/layer-3-5-build` @ `8150274` (3.5D complete + verification)
**Date**: 2026-05-10
**Author**: Claude Code (build agent)
**Status**: **PAUSE-REQUIRED** — out-of-scope baseline drift discovered (Gate 15 fails live at 2025-06 anchor); plus AM26 disposition for HLW vintage write granularity (PROCEED-with-Dxx, no PAUSE)
**Session note**: Claude Code resumed in worktree `wizardly-jemison-74d9de` at base `2903b4c` (Layer 1.5D); 3.5D code lives at `keen-torvalds-63c79a`. All inventory + smoke-test ran against the keen-torvalds worktree; this pre-flight is authored at the keen-torvalds path so the artifact lands on the correct branch.

---

## §1 — Audit Result Header

| Field | Value |
|---|---|
| Sub-phase | 3.5E — Cache Atomicity Sweep (FINAL L3.5 sub-phase) |
| Estimated effort (spec) | 6–10h |
| My estimate after audit | **~8.0h** (mid-range; tight if AM26 disposition triggers HLW test redesign) |
| Tests added (spec target) | +10 (6 NEG / 4 POS = 60% NEG, exceeds 50% floor per §2.7) |
| Gate added | Gate 16 |
| Gates touched | 11 (sha-recompute tightening), plus `analysis.load_panel` semantic shift can affect any test that consumes the panel fixture |
| Locked decisions (3.5E-D1..D4) | sha recompute on every load_panel = **YES** (smoke-test approves; <1ms vs 500ms target — 3 orders of magnitude headroom); HLW vintage atomic per-vintage = **AM26 disposition pending** (actual code is single-write); validate_cache_integrity on failure = **report+exit-non-zero**; Gate 11 → all parquet = **YES** |
| Anticipated deviations | **D25** (HLW write granularity — single concatenated write vs per-vintage spec); possibly **D26** (extracting `_write_atomic_subdir` from `r_squared_panel.py` to a public `cache.write_cache_atomic_subdir`); **D27** if Gate 15 baseline drift treated as in-scope |
| Conviction (statistical / operational / actionability) | 0.92 / **0.78** / 0.92 — see §10 |

---

## §2 — Empirical smoke-test (per spec §2.3 + §7.2 #4 + D23 lesson)

### §2.1 sha256 latency on largest parquet + representative sample

Spec target: **<500ms** on largest cached parquet. Smoke-test on 10 files (5 largest + 5 random representatives). Total cache: 137 parquet files, 24.59 MB total.

| File | Size (KB) | sha256 min ms | avg ms | max ms | <500ms target |
|---|---:|---:|---:|---:|:---:|
| `data/cache/fred_USREC.parquet` (largest) | 393.6 | 0.57 | 0.62 | 0.67 | ✓ |
| `official_SHILLER_TR_PRICE.parquet` | 376.6 | 0.53 | 0.56 | 0.61 | ✓ |
| `official_SHILLER_REAL_PRICE.parquet` | 376.4 | 0.51 | 0.56 | 0.59 | ✓ |
| `official_SHILLER_EARNINGS.parquet` | 369.6 | 0.50 | 0.55 | 0.60 | ✓ |
| `official_SHILLER_PRICE.parquet` | 368.8 | 0.53 | 0.55 | 0.57 | ✓ |
| `data/cache/yahoo_XLB.parquet` (random) | 201.6 | 0.44 | 0.49 | 0.55 | ✓ |
| `official_SHILLER_CAPE.parquet` (random) | 352.2 | 0.52 | 0.56 | 0.59 | ✓ |
| `tv_BAMLH0A1HYBB.parquet` (random) | 166.9 | 0.40 | 0.45 | 0.52 | ✓ |
| `fred_T10Y3M.parquet` (random) | 172.1 | 0.42 | 0.45 | 0.49 | ✓ |
| `official_AAII_BULL_BEAR_SPREAD.parquet` (random) | 172.9 | 0.43 | 0.47 | 0.50 | ✓ |
| **Worst measured** | 393.6 | — | — | **0.67** | ✓ |

R² panel specifically: 67.2 KB → min=0.38 / avg=0.46 / max=0.53 ms.

**Verdict**: 3.5E-D1 (sha recompute on every `load_panel()` call) **APPROVE the spec default**. The worst measurement (0.67ms) is **3 orders of magnitude under** the 500ms threshold; even if cache grows 100× to ~2.5 GB, sha recompute remains <70ms. **No D-x for D1**; the spec default holds with massive margin.

### §2.2 Inventory smoke-test (per spec §7.2 #1, #2, #3)

#### #1 — `to_parquet()` direct calls in macro_pipeline/

| Call site | Status | Action |
|---|---|---|
| `cache.py:63` | ✓ inside `atomic_write_parquet` (writes to `.tmp` then renames) | none — already atomic |
| `analysis/r_squared_panel.py:324` | ✓ inside private `_write_atomic_subdir` (mirrors atomic + sidecar) | refactor candidate (AM28 → D26) |
| `loaders/cftc_tff_treasury.py:148` | ✗ **direct, non-atomic** | **MIGRATE** to `write_cache_atomic` |
| `loaders/cftc_tff_spx.py:171` | ✗ **direct, non-atomic** | **MIGRATE** to `write_cache_atomic` |
| `loaders/hlw_rstar_vintage.py:289` | ✗ **direct, non-atomic** | **MIGRATE** to `write_cache_atomic` (AM26 — single concatenated write, NOT per-vintage as spec assumes) |
| `preprocessing.py:254 (cache_series_to_parquet)` | ✓ wrapper that routes through `write_cache_atomic` | none |

Net: **3 loader migrations** (matches spec §7.3-3) plus the `_write_atomic_subdir` refactor question (AM28).

#### #2 — `pd.read_parquet()` reads-without-validation in macro_pipeline/

| Call site | Status | Action |
|---|---|---|
| `cache.py:203` | ✓ inside `read_cache_validated` (validation around it) | none |
| `access.py:142` | reads vintage panel; relies on caller to have written via atomic helper | none for 3.5E (panel-write side validated; access uses path-based read) |
| `validation.py:400, 535, 560, 572, 585, 597, 689, 703, 719, 732, 733` (10 sites) | gate-internal probes; consume cached files for spot-checks | OUT OF 3.5E scope (gate runtime probes); leave as-is |
| `analysis/r_squared_panel.py:363` (`load_panel`) | ✗ **direct, no sidecar validation** | **MIGRATE** to `read_cache_validated_subdir` (matches spec §7.3-2) |
| `loaders/{fred,cftc_tff_spx,hlw_rstar_vintage,tv_csv,yahoo}_loader.py` (5 sites) | reads back what loader-side wrote; existing freshness-check pattern | OUT OF 3.5E scope (existing loaders use is_cache_fresh, not sidecar check); could be future cleanup |

Net: **1 read migration** (`analysis.load_panel`) — matches spec §7.3-2.

#### #3 — `except Exception:` blocks

Spec §7.3-5 flags 3 specific locations. **Spec line numbers don't match current code (they shifted post-3.5A-D edits). Semantic identification used.** See AM27.

| Spec ref | Actual location | Code shape | Disposition |
|---|---|---|---|
| `regime/regime_context.py:211-215` | **`regime_context.py:295`** (3 lines later: `try: hmm_result = predict_state(ctx) except Exception as exc: hmm_result = None; notes.append(...)`) | catches HMM-prediction errors, swallows into notes | **NARROW** to `(HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError, HmmConcurrencyError, RegimeClassifierError)`. `MemoryError`/`KeyboardInterrupt`/etc. propagate. |
| `scoring/cdrs.py:133-139` | **`cdrs.py:201`** (loop over indicator_ids; `try: bundle = load_series(...) except Exception: continue`) | swallows per-indicator load failures during quality-cap aggregation | **NARROW** to `(FileNotFoundError, ValueError, KeyError, PitContractViolationError, IndicatorLoadError)`. |
| `scoring/cdrs.py:293-299` | **`cdrs.py:389`** (loop in `_aggregate_pit_source`; same pattern as :201) | swallows per-indicator load failures during PIT-source aggregation | **NARROW** to same tuple as `cdrs.py:201`. |

Other `except Exception:` blocks counted (out-of-3.5E scope; flagged for future Codex-style sweep): 30+ instances across `validation.py`, `regime/dalio_cycle.py` (4), `regime/kindleberger.py` (6), `scoring/cdrs_vulnerability.py` (5), `scoring/cdrs_trigger.py` (5), `loaders/{atlanta_wage,fred_vintage_panel,hlw_rstar,shiller,yahoo_loader}.py`. **Spec scope is 3 sites**; broader sweep deferred to L4/L5 hygiene pass.

#### #4 — sha256 latency on largest cached parquet

Done in §2.1 above. **Pass; spec default holds.**

---

## §3 — Spec §7.2 Mandatory Items + §7.3 File Inventory

### §3.1 Files this sub-phase will touch

| File | Action | Notes |
|---|---|---|
| `macro_pipeline/cache.py` | MODIFY | ADD `read_cache_validated_subdir(subdir, filename, expected_schema_version=None, expected_min_row_count=None) -> tuple[pd.DataFrame, dict]` per spec §7.3-1; **raises** `CacheValidationError` on mismatch (vs. existing `read_cache_validated` which returns `None`); **AM28**: also extract `_write_atomic_subdir` → `write_cache_atomic_subdir(subdir, filename, df, meta) -> tuple[Path, dict]` to give symmetric public read/write helpers |
| `macro_pipeline/exceptions.py` | MODIFY | ADD `CacheValidationError(IndicatorLoadError)` — mirrors the 3.5B precedent for `PitContractViolationError`; **AM29 dispose** here (no Dxx — established precedent) |
| `macro_pipeline/analysis/r_squared_panel.py` | MODIFY | (1) `load_panel` — use `read_cache_validated_subdir(subdir="analysis", filename="r_squared_panel.parquet", expected_schema_version=PANEL_SCHEMA_VERSION, expected_min_row_count=900)`; (2) `build_and_cache(force=False)` — when reusing cache, call `read_cache_validated_subdir` to confirm validity, not just `path.exists()` (spec/Codex finding N); (3) per AM28: `_write_atomic_subdir` either deleted (replaced by `cache.write_cache_atomic_subdir`) or retained as thin wrapper |
| `macro_pipeline/loaders/cftc_tff_spx.py` | MODIFY | Replace lines 170-172 (`df.to_parquet(parquet); sidecar.write_text(...)`) with single `write_cache_atomic(stem=f"cftc_tff_spx_{contract_code}", df=df, meta=meta.to_dict(), cache_dir=DATA_CACHE)` call |
| `macro_pipeline/loaders/cftc_tff_treasury.py` | MODIFY | Replace lines 145-149 (manual parquet + sidecar) with `write_cache_atomic(stem=f"official_{indicator_id}", df=net.to_frame(indicator_id), meta=meta.to_dict(), cache_dir=DATA_CACHE)` |
| `macro_pipeline/loaders/hlw_rstar_vintage.py` | MODIFY | Replace lines 288-289 + 327 (manual parquet + sidecar at end of `build_cache`) with `write_cache_atomic(stem="official_HLW_VINTAGE", df=long, meta=meta.to_dict(), cache_dir=DATA_CACHE)`. **AM26**: spec §7.3-3 assumes per-vintage loop; actual code is single concatenated write to one parquet — `atomic per-vintage` is structurally inapplicable. File **D25**. |
| `macro_pipeline/validation.py` | MODIFY | ADD `validate_gate16_cache_integrity` per §7.6; **TIGHTEN Gate 11** to recompute sha256 on R² panel parquet and compare to sidecar `data_sha256` (currently length-checks at lines 1993-2004) |
| `macro_pipeline/regime/regime_context.py:295` | MODIFY | Narrow `except Exception` to specific HMM/regime exception tuple (see §3.1.5) |
| `macro_pipeline/scoring/cdrs.py:201, 389` | MODIFY | Narrow both `except Exception:` to `load_series` raise tuple |
| `macro_pipeline/utils/cache_audit.py` | NEW | `validate_cache_integrity(report=False) -> int` walking `data/cache/`; CLI `python -m macro_pipeline.utils.cache_audit` |
| `tests/test_cache_validation.py` | NEW | 4 tests (3 NEG + 1 POS) on `read_cache_validated_subdir` contract |
| `tests/test_cache_atomicity.py` | NEW | 6 tests (3 NEG + 3 POS) on 3 loader migrations + Gate 11 + cache_audit + exception narrowing |

### §3.2 Existing tests at risk

| Test file | Risk | Mitigation |
|---|---|---|
| `tests/test_atomic_cache.py` (9 tests) | LOW | Adding new helpers leaves existing functions untouched. New tests live in `test_cache_validation.py` / `test_cache_atomicity.py`. |
| `tests/test_r_squared_panel.py::panel` fixture (line 94: `return load_panel()`) → ~10 dependent tests | **MED-HIGH** | Post-migration `load_panel()` raises `CacheValidationError` if sidecar missing/stale. If conftest doesn't ensure sidecar matches, fixture-loading tests break. Mitigation: (a) confirm `data/cache/analysis/r_squared_panel.meta.json` already on disk + sha-matches the parquet (verified in smoke-test §2.1); (b) ensure `build_and_cache` writes a fresh sidecar. |
| `tests/test_r_squared_panel.py::test_panel_atomic_cache_metadata` (line 189) | MED | Currently asserts sidecar fields exist. After migration to `write_cache_atomic_subdir`, sidecar gets `cache_written_at` + `pipeline_processed=True` (mirroring `write_cache_atomic`). If test asserts exact field set, may need update. |
| `tests/test_cftc_tff_spx.py::test_cftc_cache_file_exists_after_load` (line 114) | LOW | Asserts parquet exists post-load; `write_cache_atomic` also creates parquet so still passes. Could augment to also check sidecar exists. |
| `tests/test_pit_hlw.py` (8 tests) | LOW | All read via `load_series` (vintage panel access); cache write granularity change shouldn't affect read path. |
| `tests/test_regime_context.py` + `test_regime_state_derivation.py` + `test_regime_dissent.py` | MED | Narrowing HMM-catch in `regime_context.py:295` means an unexpected exception type (e.g., MemoryError, KeyboardInterrupt) now propagates. None of the existing tests provoke that, but if any test mocks HMM with raise(Exception("...")), the contract changes. Mitigation: NEW NEG test asserts unexpected propagation; verify existing tests still pass. |
| `tests/test_cdrs.py` + `test_cdrs_vulnerability.py` + `test_cdrs_trigger.py` | MED | Same for `cdrs.py:201, 389` narrowing. Most CDRS tests use real `load_series` flow. |
| Validation Gate 11 (R² panel tests + Gate 11 runtime) | MED | Tightening to sha-recompute means any dirty post-cache mutation triggers FAIL. If conftest leaves cache untouched, no regression. |

**Net**: ~11-15 tests at MED risk for indirect interaction; remediation is to ensure baseline cache state is sha-clean (it is — verified in smoke-test) and to NOT mutate cache during test runs.

### §3.3 Empirical reading

DONE in §2 above. Headline: sha256 latency 3 orders of magnitude under target; 3 atomic-write migrations cleanly identified; 3 exception-narrowing sites mapped to current line numbers.

### §3.4 Ambiguities (codified per Standing Orders ambiguity routing)

| ID | Topic | Routing | Spec ref | Recommended disposition |
|---|---|---|---|---|
| **AM26** | HLW vintage write granularity. Spec §7.3-3 assumes per-vintage loop with multiple atomic writes (commit semantics: "atomic per-vintage to minimize blast radius if mid-loop failure"). Actual `hlw_rstar_vintage.py:build_cache` does ONE concatenated `long.to_parquet(parquet)` after building MultiIndex(vintage, date). No per-vintage parquets are written. The "per-vintage atomic" decision is structurally inapplicable. | **PROCEED-with-Dxx** (D25) | §7.3-3 + §7.4-D2 | Use `write_cache_atomic` for the single concatenated write. Atomic semantics: full-vintage-set commit OR rollback (not partial). Spec intent (atomic-write-discipline) preserved; spec literal (per-vintage loop) deviated. Document in D25. |
| **AM27** | Spec line numbers for `except Exception:` blocks no longer match (`regime_context.py:211-215` → actual `:295`; `cdrs.py:133-139,293-299` → actual `:201,:389`). | **PROCEED** (no Dxx) | §7.3-5 | Use semantic identification (HMM-predict catch + 2 load_series catches in CDRS). Document mapping in pre-flight & verification. |
| **AM28** | Refactor `_write_atomic_subdir` (private, in `r_squared_panel.py:305-352`) → public `cache.write_cache_atomic_subdir`? Symmetric to new `read_cache_validated_subdir`. Spec doesn't explicitly require it, but the asymmetry (new public read; existing private write) is awkward. | **PROCEED-with-Dxx** (D26 if extracted) | §7.3-1 (implicit) | Recommend **EXTRACT** to `cache.py` for symmetry; `r_squared_panel.write_panel_atomic` becomes a thin wrapper. Smaller blast radius vs leaving private + asymmetric. |
| **AM29** | Where to define `CacheValidationError`. Spec mentions class but not module. | **PROCEED** (no Dxx) | §7.3-1 (implicit) | `macro_pipeline/exceptions.py` per established 3.5B precedent (`PitContractViolationError`). Inherit from `IndicatorLoadError` for consistency with broader hierarchy. |
| **AM30** | Specific exception types for narrowing — spec gives pattern but not exact tuples. | **PROCEED** (no Dxx) | §7.3-5 | (a) `regime_context.py:295`: `(HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError, HmmConcurrencyError, RegimeClassifierError)`. (b) `cdrs.py:201, 389`: `(FileNotFoundError, ValueError, KeyError, PitContractViolationError, IndicatorLoadError)`. Verified via `predict_state` raise inventory + `load_series` raise inventory. |
| **AM31** | `validate_cache_integrity` CLI exit-code semantics. Spec §7.4-D3 says "report and exit non-zero on failure". On clean state: exit 0. On any issue: exit 1 + reports details. | **PROCEED** (no Dxx) | §7.3-6 + §7.4-D3 | Per spec default. Output: "Cache integrity: OK (137 files, 0 issues)" on success; per-file issue list on fail. |
| **AM32** | Should the `cache_audit` utility cover `data/cache/hmm/regime_3state_v1.pkl`? It's a pickle, not parquet, with its own sha-verified load flow (3.5A frozen contract). | **PROCEED** (no Dxx) | §7.3-6 | YES — extend the walk to handle both `.parquet` (read parquet, sha vs sidecar) and `.pkl` (sha vs sidecar — already implemented in `load_hmm`). Single utility, two code paths. |

### §3.5 Risk callouts

| ID | Risk | P(occur) | Mitigation |
|---|---|---|---|
| R-3.5E-1 | Spec line numbers shifted (AM27) — implementer reading line numbers literally writes to wrong line | 100% (already true) | Use semantic identification; pre-flight documents new line numbers explicitly; verification report prints actual diff lines |
| R-3.5E-2 | HLW write granularity divergence (AM26) — spec test #7 (`test_hlw_atomic_write_per_vintage`) needs rephrasing as the loop doesn't exist | 100% | Per AM26: rephrase test to `test_hlw_atomic_write_concatenated_or_rollback` — verifies single-write atomicity (mid-write crash → no half-written parquet). NEG test (induce write fault → no leftover state). |
| R-3.5E-3 | New `read_cache_validated_subdir` raise-semantics differ from existing `read_cache_validated` return-None semantics; caller migration must handle the new contract | MED 30% | Only ONE caller migrated in 3.5E (`analysis.load_panel`); existing `read_cache_validated` callers keep their None-return contract. New function is purely additive. |
| R-3.5E-4 | Gate 11 sha-recompute tightening — if `write_panel_atomic` has a latent sha-mismatch bug, Gate 11 currently passes (length check) but would fail post-3.5E | LOW 10% | Smoke-test §2.1 verified panel sha matches sidecar via my own recompute (R² panel sha matches `meta.data_sha256`); existing length-check has been masking nothing. Verify Gate 11 still PASS post-tightening. |
| R-3.5E-5 | Narrowing exception catches → unexpected exceptions previously swallowed propagate. Could cascade. | MED 20% | NEW NEG test #9 verifies unexpected propagation. Manual smoke: induce `MemoryError` mock on `predict_state` → assert `RegimeContextError` or propagation. Likewise for `cdrs.py:201, 389` → induce `MemoryError` on `load_series` → assert propagation. |
| **R-3.5E-6** | **OUT-OF-SCOPE: Gate 15 currently FAILS at 2025-06 anchor** (live runtime). 3.5D verification reported PASS on 2026-05-09; today (2026-05-10) the runtime check fails. Hypothesis: HMM input data (UMCSENT or NFCI) shifted between 3.5D verification day and today, flipping HMM state at 2025-06 from "recession" to "expansion" → no dissent → no INDETERMINATE → cap not bound. **NOT a 3.5E regression**, but baseline is no longer 15/15 green per resume prompt's claim. | 100% (verified) | **PAUSE-required surface** in §5; V/Strategic must decide: (a) accept as known fragility, document, and re-run gate 15 at fresh data; (b) freeze HMM input feature data at 2025-06 (snapshot); (c) re-pin gate 15 contract anchor to a more stable date; (d) defer to L5 calibration. **3.5E does not depend on this anchor**, so 3.5E coding can proceed in parallel — but baseline state assertion in pre-flight cannot claim 15/15 green. |
| R-3.5E-7 | `cftc_tff_spx.py` and `cftc_tff_treasury.py` cache-fresh-check (`_is_cache_fresh(parquet)`) reads parquet path existence, not sidecar validity. Post-migration: `write_cache_atomic` always writes parquet+sidecar pair; if user manually deletes sidecar, `_is_cache_fresh` says "fresh" but `read_cache_validated_subdir`-style reads would fail. | LOW 5% | Out of 3.5E scope (cftc loaders' read path stays as `pd.read_parquet`, not validated read). Future cleanup. |
| R-3.5E-8 | `analysis.build_and_cache(force=False)` currently checks `PANEL_CACHE_PATH.exists()` only. Post-migration: should also call `read_cache_validated_subdir` to verify sidecar validity. If validation fails, fall through to rebuild. | 100% (per spec) | Implement per spec §7.3-2 (Codex finding N): on cache hit, validate; on validation fail, log + rebuild (don't raise). |
| R-3.5E-9 | `cache_audit` utility introducing new dependencies | LOW 5% | Use only stdlib (hashlib, json, pathlib) + pandas (already imported). No new deps. |

### §3.6 Effort estimate

| Step | Estimate (h) |
|---|---|
| Pre-flight (this) | 0.6 (with smoke-test) |
| AM26/AM28 V/Strategic decision | gate (PAUSE) |
| **R-3.5E-6 (Gate 15 baseline)** V/Strategic decision | gate (PAUSE) |
| `CacheValidationError` in `exceptions.py` | 0.1 |
| `read_cache_validated_subdir` in `cache.py` | 0.5 |
| `write_cache_atomic_subdir` extraction (AM28=YES) | 0.5 |
| `analysis.load_panel` migration + `build_and_cache` validity check | 0.5 |
| `cftc_tff_spx.py` migration | 0.4 |
| `cftc_tff_treasury.py` migration | 0.4 |
| `hlw_rstar_vintage.py` migration (AM26 — single write) | 0.5 |
| Gate 11 tightening | 0.3 |
| Exception narrowing — `regime_context.py:295` | 0.3 |
| Exception narrowing — `cdrs.py:201, 389` | 0.4 |
| `cache_audit.py` CLI | 0.7 |
| Gate 16 implementation | 0.6 |
| 10 new tests (4 POS / 6 NEG; see §8) | 1.2 |
| Smoke-test post-impl + ruff + 16 gates | 0.5 |
| Verification report | 0.5 |
| **Total** | **~7.5–8.0h** within 6–10h spec band |

---

## §4 — Decisions Locked Per Standing Orders

| Decision | Locked default | Empirical override needed? |
|---|---|---|
| 3.5E-D1 (sha recompute on every `load_panel`) | YES | **NO** — smoke-test (§2.1) confirms 0.67ms worst-case vs 500ms target (3 orders of magnitude under). Within Standing Orders ≤0.05 / clear-band auto-resolve range. |
| 3.5E-D2 (HLW vintage write granularity = per-vintage) | atomic per-vintage | **YES** — see AM26 (spec literal vs intent reinterpretation; D25 to file). Actual code is single concatenated write. |
| 3.5E-D3 (cache_audit failure behavior = report+exit-non-zero) | report + exit-non-zero | NO — clear procedural |
| 3.5E-D4 (Gate 11 cover all parquet, not just R² panel) | YES | NO — small extra cost; aligned with cache_audit utility scope |

---

## §5 — Decisions Requested From V / Strategic (BEFORE Coding)

### §5.1 OUT-OF-SCOPE finding: Gate 15 baseline drift at 2025-06

**Status as of 2026-05-09 evening (per `LAYER_3_5_3.5D_VERIFICATION.md`)**: Gate 15 PASS — `derive_regime_state` at 2025-06 returns `("indeterminate", "hmm_dissent_indeterminate", 0.40)` because HMM = recession dissents from NBER+Kindleberger consensus = expansion.

**Status as of 2026-05-10 morning (live runtime)**:
```
[gate15] Gate 15 - Layer 3.5D Probability Semantics + Dissent: FAIL
  [x] FAIL: derive_regime_state at 2025-06 returned ('expansion', 'nber'); expected indeterminate
  [x] FAIL: CRPS confidence at 2025-06 = 70.00 exceeds INDETERMINATE cap 60
  [x] CDRS R from consensus (AM21=B) OK: 2025-06 R=0.6, 2008-09 R=1.0
  [x] (5 other sub-criteria PASS)
```

**Hypothesis**: HMM state at 2025-06 has flipped from "recession" → "expansion" because upstream FRED data refreshed between 3.5D verification (2026-05-09) and today (2026-05-10). The HMM artifact (`regime_3state_v1.pkl`) is frozen + sha-verified, but the FEATURE INPUT (UMCSENT, NFCI, T10Y3M, etc. at as_of=2025-06-01) depends on the vintage-resolved values, which can shift with data refreshes. The 3.5D contract anchored on a specific HMM output that was empirically true on May 9 but is no longer true on May 10. **`pytest tests/` still passes 544/544** — the regression is only in the gate-runtime check, not in the unit tests.

**This is OUT of 3.5E scope.** 3.5E touches cache infrastructure (atomicity, sha validation, exception narrowing) — not the dissent contract or HMM input pipeline. But the baseline state assertion for 3.5E ("15/15 green per resume prompt") is **no longer accurate**.

**V/Strategic options**:
| Option | Action | Cost |
|---|---|---|
| **A (recommended for 3.5E coding to proceed)** | Accept Gate 15 fragility as known baseline issue; proceed with 3.5E; document in §5; file **D27** (pre-existing baseline drift). 3.5E verification reports "14/16 baseline + Gate 16 NEW = 15/16 green; Gate 15 fragile per D27". | 0h (acknowledge + document) |
| B | Re-pin Gate 15 contract anchor to a more stable historical date (e.g., 2008-09-15 only — confirmed pre-1978 + post-3.5C calendar resolution). Drop 2025-06 from gate body; keep as live-but-not-gated reporting. | 1-2h |
| C | Snapshot the HMM input feature data at 2025-06 ("as of 2026-05-09") and pin gate 15 against that snapshot. Adds a new artifact like `data/cache/hmm/feature_input_at_2025_06_v1.parquet`. | 2-3h |
| D | Re-run smoke-test today to identify which feature shifted; if a single FRED series moved, deeper investigation. Gate 15 stays broken until root cause identified. | 1-4h depending on root cause |
| E | Defer to L5 calibration window — Gate 15 stays broken; document as known. | 0h (kicks the can) |

**Recommendation**: Option A — accept as known fragility and proceed with 3.5E. Rationale:
- 3.5E doesn't touch this code path
- The gate is auditing a *fragile contract* (an empirical anchor that depends on live data); the 3.5D code semantics are correct (HMM dissent → INDETERMINATE), only the empirical anchor shifted
- L5 calibration is the right place to introduce a more robust gate semantics (e.g., "if HMM dissents at any historic anchor, the dissent path produces correct INDETERMINATE haircut" — verify the path works, not that a specific anchor still triggers it)
- Re-pinning anchor (Option B) is also reasonable but is methodology change beyond 3.5E spec scope

**Decision required from V**: choose A/B/C/D/E. If A: 3.5E pre-flight unblocked.

### §5.2 AM26 — HLW vintage write granularity

Spec §7.3-3 + §7.4-D2 assume per-vintage atomic writes; actual code does ONE concatenated write. **Recommend disposition**: use `write_cache_atomic` for the single write; rephrase test #7 from per-vintage atomicity to single-write-or-rollback atomicity. **File D25.** Decision: confirm or override.

### §5.3 AM28 — Extract `_write_atomic_subdir` to `cache.py` as `write_cache_atomic_subdir`?

**Recommend YES**: provides symmetry with new `read_cache_validated_subdir`; `r_squared_panel.write_panel_atomic` becomes thin wrapper. **File D26** for the refactor scope. Decision: confirm or override.

### §5.4 AM29-AM32 — Informational

All clear procedural. NO PAUSE required; proceeding with recommended dispositions per §3.4. Surfaced for explicit acknowledgement.

---

## §6 — Anticipated Dxx filing

| ID | Topic | Trigger | Disposition |
|---|---|---|---|
| **D25 (likely)** | HLW vintage write granularity — single concatenated write rather than per-vintage loop (AM26) | Spec literal vs spec intent; intent (atomic write) preserved | ACCEPT — methodology divergence documented in scoring/regime READMEs + spec narrative refinement note |
| **D26 (likely if AM28=YES)** | `_write_atomic_subdir` extraction from `r_squared_panel.py` to public `cache.write_cache_atomic_subdir` | Symmetric public API for new `read_cache_validated_subdir`; small refactor outside spec literal scope | ACCEPT — improves API hygiene; no behavior change |
| **D27 (if §5.1 disposition = A)** | Gate 15 baseline drift at 2025-06 anchor (out-of-scope, pre-existing) | Empirical anchor shifted between 3.5D verification day (2026-05-09) and 3.5E pre-flight day (2026-05-10) | ACCEPT-AS-KNOWN — documents the fragility; gate semantics unchanged; L5 calibration is the right home for a more robust contract |
| (D28+) | reserved for verification-time discoveries | — | — |

---

## §7 — Implementation Order (post-V approval on §5)

1. **GATE**: V approves §5.1 (Gate 15 baseline drift disposition) + §5.2 (AM26) + §5.3 (AM28).
2. Add `CacheValidationError(IndicatorLoadError)` to `macro_pipeline/exceptions.py`.
3. Add `read_cache_validated_subdir(subdir, filename, expected_schema_version=None, expected_min_row_count=None)` to `cache.py`. Raises `CacheValidationError`. Distinct from existing `read_cache_validated` (which returns `None`).
4. **AM28=YES**: Add `write_cache_atomic_subdir(subdir, filename, df, meta) -> tuple[Path, dict]` to `cache.py`. Delete `_write_atomic_subdir` from `r_squared_panel.py`; replace `write_panel_atomic` body with thin wrapper.
5. Migrate `analysis.load_panel` to `read_cache_validated_subdir`. Update `analysis.build_and_cache(force=False)` to validate (Codex finding N).
6. Migrate `loaders/cftc_tff_spx.py:170-172` to `write_cache_atomic`.
7. Migrate `loaders/cftc_tff_treasury.py:145-149` to `write_cache_atomic`.
8. Migrate `loaders/hlw_rstar_vintage.py:288-289+327` to `write_cache_atomic` (single write per AM26=D25).
9. Tighten Gate 11 in `validation.py:1993-2004` to recompute sha (not length-check).
10. Narrow `regime_context.py:295` `except Exception` to HMM/regime exception tuple.
11. Narrow `cdrs.py:201` and `cdrs.py:389` `except Exception` to load_series exception tuple.
12. Add `macro_pipeline/utils/cache_audit.py` with `validate_cache_integrity()` + CLI.
13. Add `validate_gate16_cache_integrity` to `validation.py`. Per spec §7.6 — 6 sub-criteria.
14. Write 10 new tests across `tests/test_cache_validation.py` + `tests/test_cache_atomicity.py` (split per §8).
15. Smoke-test post-impl: re-run sha latency on largest parquet (regression check); run `cache_audit` (zero issues); manual corruption test (1 byte flip → CacheValidationError).
16. Full pytest + ruff + 16 gates (Gate 15 status per §5.1 disposition).
17. Commit per spec §7 message template.
18. Author `LAYER_3_5_3.5E_VERIFICATION.md`.
19. PAUSE for V approval.

---

## §8 — Test plan (10 new = 4 POS / 6 NEG; meets §2.7 50% NEG floor with margin to spare)

### NEW (target spec §7.5)

| # | Test | Type | Where | Asserts |
|---|---|---|---|---|
| 1 | `test_validated_cache_read_recomputes_sha` | POS | test_cache_validation | `read_cache_validated_subdir` recomputes (verified by mocking `_sha256_file` to count calls; or by tampered-file → raise) |
| 2 | `test_corrupted_parquet_raises_CacheValidationError` | NEG | test_cache_validation | Write valid parquet+sidecar → flip 1 byte in parquet → `read_cache_validated_subdir` raises `CacheValidationError` |
| 3 | `test_modified_sidecar_raises_CacheValidationError` | NEG | test_cache_validation | Write valid pair → tamper `data_sha256` field in sidecar → raises (sha doesn't match recomputed) |
| 4 | `test_missing_sidecar_raises_FileNotFoundError` | NEG | test_cache_validation | Write parquet only (no sidecar) → raises `FileNotFoundError` |
| 5 | `test_cftc_spx_atomic_write_creates_meta` | POS | test_cache_atomicity | After `load_cftc_tff_spx(force_refresh=True)`, sidecar file exists with `data_sha256`, `schema_version`, `row_count`, `cache_written_at` |
| 6 | `test_cftc_treasury_atomic_write_creates_meta` | POS | test_cache_atomicity | Same pattern for `load_cftc_tff_treasury` |
| 7 | `test_hlw_atomic_write_concatenated_or_rollback` (was `test_hlw_atomic_write_per_vintage` per spec; rephrased per AM26) | NEG | test_cache_atomicity | Mock `to_parquet` to raise mid-write → no leftover `.tmp` file; original parquet (if existed) preserved |
| 8 | `test_gate_11_recomputes_sha_not_length_check` | NEG | test_cache_atomicity | Write valid panel → tamper parquet bytes (preserve length) → `validate_gate11_panel_metadata` FAILS |
| 9 | `test_narrow_exception_in_regime_context_propagates_unexpected` | NEG | test_cache_atomicity | Mock `predict_state` to raise `MemoryError` → `build_regime_context` propagates `MemoryError` (not swallowed into `notes`) |
| 10 | `test_cache_audit_reports_issues` | POS | test_cache_atomicity | CLI runs against tmp cache: clean → exit 0; tampered file → exit 1 + reports the file |

NEG/POS = 6/4 = 60% NEG. **Exceeds spec §2.7 50% NEG floor.**

### Adjacent test reinforcement

Plus inline cross-check (no new test file lines, just re-run):
- `tests/test_atomic_cache.py` — ensure all 9 existing tests pass
- `tests/test_r_squared_panel.py` — ensure panel fixture loads + 18+ existing tests pass (panel sidecar validity)

---

## §9 — Proof Contract Mapping (12 items, spec §7.7)

| # | Spec proof | How I will demonstrate |
|---|---|---|
| 1 | `grep -rn "to_parquet(" macro_pipeline/loaders/` shows zero direct calls | Post-migration: only `cache_series_to_parquet` (wrapper) shows; cftc_tff_spx, cftc_tff_treasury, hlw_rstar_vintage no longer have direct calls |
| 2 | `grep -rn "except Exception" macro_pipeline/regime/ macro_pipeline/scoring/` shows zero matches at flagged sites | Per AM27 mapping: `regime_context.py:295` and `cdrs.py:201, 389` no longer match. Other `except Exception` blocks in regime/scoring exist (out of 3.5E scope) — surface in commit message |
| 3 | `pytest tests/test_cache_validation.py tests/test_cache_atomicity.py` — 10 new tests pass | `pytest` output |
| 4 | Manual corruption test: tamper R² panel parquet, `python -c "from macro_pipeline.analysis import load_panel; load_panel()"` raises | Show in verification §2 (analogous to 3.5C smoke-test format) |
| 5 | sha-recompute timing on largest cached parquet | §2.1 above (and re-measured post-impl in verification): worst case 0.67ms vs 500ms target |
| 6 | `python -m macro_pipeline.utils.cache_audit` exits 0 in clean state | Exit-code dump in verification |
| 7 | Gate 11 fails when sha tampered | Manual induce + verification artifact |
| 8 | Gate 16 passes | `python -m macro_pipeline.validation gate16` → PASS |
| 9 | All previously-passing tests still pass — modulo §5.1 R-3.5E-6 baseline | 544 + 10 = 554 unit tests passing; Gate 15 status per V's §5.1 decision |
| 10 | Cumulative test count = 538 + 10 = 548; actual = 544 + 10 = **554** | Spec target 548; actual 554 — exceeds by 6 (since 3.5D delivered +10 not +8) |
| 11 | Three migrated loaders re-tested with their existing test files | `pytest tests/test_cftc_tff_spx.py tests/test_pit_hlw.py` — no regression |
| 12 | Conviction reported per §2.4; smoke-test results archived | §10 below + §2 |

---

## §10 — Pre-flight Conviction (3-field, per spec §2.4)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | **0.92** | High: smoke-test gives crystal-clear data on sha latency (3 orders of magnitude under target); inventory of `to_parquet`/`read_parquet`/`except Exception` is mechanical; existing infrastructure (`write_cache_atomic`, `exceptions.py`) provides clean precedent. Slight haircut for AM26 (spec assumes per-vintage loop that doesn't exist). |
| `conviction_operational` | **0.78** | Medium: **binding** at this value due to three operational drags: (a) AM26 (HLW write granularity divergence requires D25 + test rephrasing); (b) AM27 (line numbers shifted, must use semantic identification); (c) **out-of-scope baseline drift** (Gate 15 fails live at 2025-06; pre-existing fragility surfaced). The 3.5E work itself is straightforward; the operational complexity is in the surrounding context. |
| `conviction_actionability` | **0.92** | High: implementation order is clear (§7); existing infrastructure is solid; test plan exceeds NEG floor; cache_audit utility cleanly bounded; sha recompute decision is solidly approved by smoke-test data. |
| **Aggregate** | **0.78** | Operational binding. |

### Binding constraint identified

**Operational** is binding because of the **out-of-scope Gate 15 baseline drift** (§5.1, R-3.5E-6). Without V/Strategic decision on disposition, 3.5E coding can technically proceed (cache infrastructure is independent), but the verification will need to assert "15/16 baseline gates green + Gate 16 NEW = 15/16 green; Gate 15 fragile per D27" rather than "16/16 green". The cleanest path is V approves Option A (accept as known fragility, file D27) and 3.5E proceeds in parallel.

---

## §11 — END (initial pre-flight)

Pre-flight complete. **PAUSED** awaiting:

1. **§5.1 disposition** (Gate 15 baseline drift) — recommend Option A (accept as known fragility, file D27, proceed with 3.5E in parallel).
2. **AM26 disposition** (HLW vintage write granularity) — recommend D25 ACCEPT.
3. **AM28 disposition** (extract `_write_atomic_subdir` to `cache.py`) — recommend D26 ACCEPT.
4. (Informational) AM27/AM29/AM30/AM31/AM32 confirmation.

Per Standing Orders ambiguity routing:
- §5.1 R-3.5E-6 is **PAUSE-required** (test failure suggesting pre-existing bug not in scope) — out-of-scope but baseline-affecting.
- AM26 is **PROCEED-with-Dxx** (spec literal vs intent reinterpretation, intent preserved).
- AM27 is **PROCEED** (no Dxx — navigation/documentation only).
- AM28 is **PROCEED-with-Dxx** (refactor opportunity that simplifies without changing contract).

If V approves §5.1=A + AM26=D25 + AM28=D26: execute §7 implementation order; expect ~7.5–8h actual time (within 6–10h spec band). Test count target +10 met (4 POS / 6 NEG). Gate 16 + tightened Gate 11 deliver final L3.5 cache integrity surface.

If §5.1 disposition is B/C (re-pin or snapshot anchor): adds 1-3h but is methodology change beyond 3.5E spec scope; recommend deferring to L4/L5.

If §5.1 is left unresolved: 3.5E coding proceeds; verification report flags 15/16 + open question on Gate 15.

---

## §12 — STEP 0 Diagnostic Findings (executed per Strategic Claude REVISE-WITH-NOTES)

**Date**: 2026-05-10 (~1.0h elapsed for STEP 0 diagnosis + restoration).
**Trigger**: Strategic Claude REVISE-WITH-NOTES (Option C HYBRID): diagnose Gate 15 drift root cause before 3.5E §7 coding; refactor anchor IFF FRED data revision confirmed.

### §12.1 — STEP 0.1: HMM frozen-contract integrity check

| Check | Result |
|---|---|
| Pickle path | `data/cache/hmm/regime_3state_v1.pkl` (2,593 bytes) |
| sha256 (recomputed) | `aa813d167e0e3f591c55cf254b06e1f977e48e1fd158f96845ac7b02791514c5` |
| sha256 (sidecar `data_sha256`) | `aa813d167e0e3f591c55cf254b06e1f977e48e1fd158f96845ac7b02791514c5` |
| MATCH | ✓ |
| State mapping | `{0: 'expansion', 2: 'late-cycle', 1: 'recession'}` — matches 3.5D baseline |
| Sidecar fields | All 21 fields present including `feature_matrix_sha256`, `nber_label_sha256`, `random_state=42`, `hmmlearn_version=0.3.3`, `python_version=3.12.10`, `pickle_protocol=4`, `cache_written_at=2026-05-09T22:00:09` |

**STEP 0.1 verdict**: HMM frozen contract is INTACT. **NOT** the "HMM determinism issue" branch (Strategic's PAUSE branch). No L3.5A invalidation.

### §12.2 — STEP 0.2: HMM inference at 2025-06-01 today

Direct `predict_state(ctx)` invocation at as_of=2025-06-01:

| Field | Value |
|---|---|
| Last decoded state (numeric) | **1** |
| Last decoded state (label) | **`recession`** |
| Posterior probability | `recession=1.0000`, `expansion=2.4e-10`, `late-cycle=6.8e-07` |
| Standardized feature row | `[T10Y2Y=-0.66, PHILLY_LEI_PROXY=0.46, IC4WSA=-1.58, NFCI=-0.33, UMCSENT=-3.04]` |
| Last 6 monthly states | All `recession` (chronologically Dec-2024 → May-2025), p=1.000 each |

Direct `build_regime_context(ctx) + derive_regime_state()` returns:
```
('indeterminate', 'hmm_dissent_indeterminate', 0.4)
```
**Matches 3.5D verification baseline exactly.**

**STEP 0.2 verdict**: HMM output at 2025-06-01 is **stable at `recession` with posterior 1.000**. **NOT** the "FRED data revision" branch (Strategic's D27-anchor-refactor branch).

### §12.3 — STEP 0.3: Where the divergence actually came from

The discrepancy was reproduced and located. Two invocation paths produce DIFFERENT results:

| Invocation | filelock present on `sys.path`? | rc.hmm | derive return | Gate 15 |
|---|---|---|---|---|
| `python -m macro_pipeline.validation gate15` (without `.local-deps`) | **NO** | `None` (silently swallowed) | `('expansion', 'nber', 0.0)` | **FAIL** |
| `python -m macro_pipeline.validation gate15` (with `.local-deps` via PYTHONPATH or installed filelock) | YES | `HmmStateResult(state='recession', ...)` | `('indeterminate', 'hmm_dissent_indeterminate', 0.4)` | **PASS** |
| `pytest tests/` | YES (via conftest.py auto-prepending `.local-deps`) | YES | INDETERMINATE | 544/544 |

**Mechanism**:
1. `D:/macro_pipeline/.venv` did not have `filelock` installed (despite being declared in `pyproject.toml:21` and resolved in `uv.lock`).
2. `python -m macro_pipeline.validation` does NOT load `tests/conftest.py`, so `.local-deps` was not on `sys.path` for validation CLI invocations.
3. `_acquire_lock()` in `regime/hmm_states.py:204-211` raised `RegimeClassifierError("[hmm] filelock not installed; cannot acquire HMM artifact lock")`.
4. `regime/regime_context.py:295` `except Exception as exc:` **silently swallowed** the env-config error into a debug note (`"hmm: RegimeClassifierError: filelock not installed..."`) and set `hmm_result = None`.
5. With `rc.hmm = None`, Phase B at line 237 (`if self.hmm is not None and self.hmm.state != consensus_state`) is FALSE; no INDETERMINATE branch fires.
6. Returns `('expansion', 'nber', 0.0)` from Phase A Path 3 (clean NBER expansion).
7. Gate 15 sub-criteria 2+3 FAIL; the failure is REPORTED as state='expansion', source='nber' — concealing the underlying environment issue.

**STEP 0.3 verdict**: NOT FRED data revision; NOT HMM determinism. Root cause is **AP-6 (broad `except Exception:` blocks that log + continue)** at `regime_context.py:295`, exposed by an environment-hygiene gap (`filelock` missing from master `.venv` despite being declared dep).

This is the EXACT anti-pattern that 3.5E §7.3-5 narrows.

### §12.4 — STEP 0.5: Decision tree application

Strategic's tree:
- "If FRED data revision: file D27 + refactor Gate 15 anchor" — **NOT this branch.** No FRED revision occurred; HMM output stable.
- "If HMM determinism issue: PAUSE + escalate" — **NOT this branch.** Pickle sha matches; deterministic.
- "If 3.5C/3.5D edge case: file appropriate Dxx and surgical fix" — **THIS branch.** AP-6 swallow at `regime_context.py:295` (predates 3.5E but inside 3.5E §7.3-5 scope) caused environment-config error to manifest as silent semantic regression.

**Surgical fix (two layers)**:
1. **Immediate (already applied)**: `pip install "filelock>=3.13"` into master `D:/macro_pipeline/.venv`. Filelock 3.29.0 now installed; aligns master venv with declared dep.
2. **Structural (in 3.5E §7 coding)**: narrow `regime_context.py:295` `except Exception:` per spec §7.3-5 — but with a **refinement** per this finding: distinguish "HMM artifact-data errors" (log + continue legitimate) from "HMM environment/config errors" (propagate). Two sub-options:
   - (a) Catch only artifact-data errors `(HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError)`. Let `HmmConcurrencyError` and `RegimeClassifierError` propagate (these are more severe / environmental). The filelock-missing case would propagate cleanly.
   - (b) Catch all current HMM exception types (`HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError, HmmConcurrencyError, RegimeClassifierError`) but introduce a new `HmmEnvironmentError` for env-config issues (filelock missing, wrong Python version, etc.) that is NOT in the catch tuple → propagates.
   - **Recommendation: (a)** — minimal new infrastructure; semantics of `RegimeClassifierError` are already "broad classifier-level error" per its existing usage. Letting it propagate is the right intent.

### §12.5 — STEP 0.7: Restore Gate 15 PASS on baseline

Action taken: `D:/macro_pipeline/.venv/Scripts/python.exe -m pip install "filelock>=3.13"` — successful (filelock-3.29.0).

Verification:
| Check | Result |
|---|---|
| `python -m macro_pipeline.validation gate15` (no PYTHONPATH override) | **PASS** ✓ |
| `derive_regime_state at 2025-06` | `('indeterminate', 'hmm_dissent_indeterminate', haircut=0.4)` ✓ |
| `crps_2025_06_confidence` | `60.0` (cap binding) ✓ |
| `cdrs_2025_06_R` | `0.6` (consensus expansion) ✓ |
| `cdrs_2008_09_R` | `1.0` (consensus late-cycle) ✓ |
| All other Gate 15 sub-criteria | PASS ✓ |
| `pytest tests/` | **544 passed in 110.93s** ✓ |

**STEP 0.7 verdict**: Gate 15 baseline RESTORED. **15/15 gates PASS** as the resume prompt asserted (the original assertion was correct on 2026-05-09 verification day; the 2026-05-10 morning failure was a transient environment-hygiene artifact, not a regression). Pause-and-verify discipline maintained — 3.5E coding may now proceed against a clean baseline.

### §12.6 — Revised disposition register

| ID | Topic | Status (revised) |
|---|---|---|
| ~~D27 (anchor refactor)~~ | ~~Gate 15 anchor refactor (FRED revision)~~ | **NOT NEEDED** — STEP 0.2 falsified the FRED-revision hypothesis. 2025-06 anchor is empirically stable today. No anchor refactor. |
| **D27 (revised)** | AP-6 swallow at `regime_context.py:295` exposed environment-config gap (filelock absent from master `.venv`); silent semantic regression resulted. Master venv aligned with `pyproject.toml:21` declared dep via `pip install`. Spec §7.3-5 exception narrowing remains the structural fix. | ACCEPT — file in `LAYER_3_5_DEVIATIONS.md` post-3.5E commit |
| D25 (HLW vintage atomic) | Approved by Strategic | ACCEPT |
| D26 (cache.write_cache_atomic_subdir extraction) | Approved by Strategic | ACCEPT |

### §12.7 — Forward-looking adjustments to the implementation plan

1. **Implementation order amendment**: **STEP 0.7 already complete** (filelock installed; Gate 15 PASS). Original §7 plan (steps 2-19) proceeds unchanged. **NO Gate 15 anchor refactor.**
2. **Exception narrowing in `regime_context.py:295`**: implement the refined narrowing per §12.4 sub-option (a) — catch `(HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError)` only; let `HmmConcurrencyError` + `RegimeClassifierError` propagate. This ensures env-config issues (like missing filelock) fail LOUDLY rather than silently swallow into wrong-state.
3. **Test #9 reinforcement**: spec §7.5 #9 (`test_narrow_exception_in_regime_context_propagates_unexpected`) gains direct relevance — assert that `RegimeClassifierError` (e.g., simulated lock-acquire failure) propagates rather than swallows. This pre-flight finding becomes a real-world motivating example in the verification report.
4. **Effort estimate**: STEP 0 diagnosis took ~1.0h; original 7.5–8h estimate intact since STEP 0.7 anchor refactor (which would have added 0.5h) is not needed. **Updated total: 7.5–8.5h** (within spec 6–10h band).
5. **Conviction lift**: operational binding from §10 (0.78) revisits.

### §12.8 — Updated conviction (post-STEP 0)

| Field | Value (was → now) | Rationale (revised) |
|---|---|---|
| `conviction_statistical` | 0.92 → **0.94** | STEP 0.2 confirmed HMM output deterministic at 2025-06; smoke-test still applies at 0.67ms worst case. |
| `conviction_operational` | 0.78 → **0.88** | Baseline restored; root cause clearly identified; surgical fix already half-applied (filelock); structural fix is in scope of §7.3-5 with a refinement. AM26+AM27+AM28 remaining drag is moderate. |
| `conviction_actionability` | 0.92 → **0.94** | Implementation order unchanged; refined narrowing in §12.4 is a small enhancement to spec §7.3-5; STEP 0 lessons enrich verification rationale. |
| **Aggregate** | 0.78 → **0.88** | Operational previously binding; now lifts. Statistical and actionability are co-leading; no single binding. |

**Strategic's post-Option-C target was ≥0.85 — achieved (0.88).**

### §12.9 — Forward-looking lessons (per Strategic note)

Strategic asked me to capture systemic lessons:

1. **AP-6 in regime_context.py:295 silently masks environment issues as data-state shifts.** This is now empirically demonstrated. The 3.5E exception narrowing is the structural fix; the filelock case is the canonical motivating example.
2. **Gates anchored on present-day data are fragile to FRED revisions** (Strategic's note 1) — still a valid principle, but in THIS instance the apparent fragility was an environment artifact, not actual revision sensitivity. The 2025-06 anchor IS revision-stable today; the lesson generalizes (anchor stability should be audited at L3.5 retrospective + L5 walk-forward CV design), but no immediate refactor is needed for 3.5E.
3. **Worktree-local `.local-deps` mechanism (HANDOFF §6.2) only loads via `tests/conftest.py`** — `python -m macro_pipeline.<...>` CLIs don't pick it up. Future hardening: either add `.local-deps` bootstrap to `macro_pipeline/__init__.py` (mirrors conftest), or document that master `.venv` MUST be `uv sync`-ed for non-pytest invocations. Out of 3.5E scope but worth flagging in L3.5 retrospective.
4. **Codex 5.5 review handoff (post-3.5E)**: the §12 audit trail above documents exactly why `regime_context.py:295` narrowing matters and what real-world cost AP-6 has. This is excellent grist for Codex review prose.

---

## §13 — END (post-STEP 0 amendment)

STEP 0 diagnosis complete. **Strategic's HYBRID Option C executed**: diagnose first, refactor anchor IFF FRED revision. Result: NOT FRED revision; root cause is AP-6 + env-hygiene; baseline restored via filelock install (one-line, reversible); structural fix is in scope of 3.5E §7.3-5 with a refinement.

**PAUSED** awaiting V/Strategic acknowledgement that:

1. STEP 0 findings (NOT FRED revision; AP-6 + env-hygiene root cause) are accepted.
2. D27 reframed scope (AP-6 + env-hygiene finding rather than anchor refactor) is acceptable.
3. The refined exception-narrowing approach in §12.4 sub-option (a) — catch `(HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError)` only; let `HmmConcurrencyError, RegimeClassifierError` propagate — is APPROVED.

If APPROVE: execute §7 implementation order (steps 2-19 of original plan). Expected ~7.5–8.5h total. STEP 0 already consumed ~1.0h; remaining ~6.5–7.5h.

If REVISE on §12.4 — e.g., V wants Strategic's original pattern from spec §7.3-5 verbatim (`(FileNotFoundError, ConfigError)`-style) — I'll defer to spec literal and add a note in verification documenting the refinement that was set aside.

If RETURN-FOR-REWORK: STEP 0 has uncovered no actual regression; 3.5E §7 coding can proceed without further investigation. Returning would re-diagnose what's already diagnosed; not recommended.

Per Standing Orders pause-and-verify pattern: this is the gating PAUSE before STEP 1+ (3.5E §7 coding).
