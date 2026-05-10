# LAYER 3.5b-T — Pre-Flight Audit (Cache Validation Discipline Tightening)

**Spec ref**: L3.5b inline spec §3 (Codex finding T, HIGH).
**Branch**: `claude/layer-3-5b-build` @ `01b780e` (origin/main, post-L3.5 merge).
**Date**: 2026-05-10
**Author**: Claude Code (build agent)
**Status**: PROCEED-with-Dxx pending V acknowledgement on AM-3.5b-T-1 (migration depth); no PAUSE-required items.

---

## §1 — Audit Result Header

| Field | Value |
|---|---|
| Sub-phase | 3.5b-T — Cache Validation Discipline Tightening |
| Spec effort | 2–3h |
| My estimate after audit | **~2.5h** (within range) |
| Tests added (target) | +6 (4 NEG / 2 POS = 67% NEG, exceeds 50% floor) |
| Cumulative tests post-T | 554 + 6 = **560** |
| Gate touched | Gate 16 (cache_integrity → tightened sub-criterion 5) + Gate 17 sub-criterion 1 (added at end of L3.5b) |
| Codex findings closed | T (HIGH) — completes the C+N closure that 3.5E partially shipped |
| Locked decisions (T-D1..D4) | D1 route through existing helper, D2 sha mandatory, D3 same for subdir, D4 migration policy (empirically post-migration; see AM-3.5b-T-1) |
| Anticipated deviations | **D28** if AM-3.5b-T-1 disposition is approved as recommended (empirically-informed strict-enforcement only; skip dormant migration code) |
| Conviction (statistical / operational / actionability) | 0.94 / 0.88 / 0.94 — see §10 |

---

## §2 — Empirical findings (per spec §3.2 + new "Empirical claim verification" Standing Order)

### §2.1 Audit of `access.py` parquet read paths (grep-audit, post-Standing-Order)

`grep -n "read_parquet" macro_pipeline/access.py` → **1 match**:

| Line | Caller | Pattern | Validates? |
|---:|---|---|:---:|
| **142** | `_read_cached_series_and_meta` (used by `LatestSeriesReader.load`, `_load_via_visibility_shift`, `_load_via_vintage_panel` plumbing) | `df = pd.read_parquet(parquet_path)` direct | **NO** |

Cross-callers of `_read_cached_series_and_meta` (the production scoring data path):

| Line | Caller |
|---:|---|
| 168 | `LatestSeriesReader.load` |
| 245 | `_load_via_visibility_shift` (PIT real-time path) |
| 293 | `_load_via_vintage_panel` (vintage path) |
| 325 | `_load_via_construction_z` (Option Z path) |

**Verdict**: Codex finding T (a) confirmed by grep — production data path has zero sidecar validation across 4 call sites.

### §2.2 Audit of `cache.py` read helpers

| Helper | Behaviour on missing `data_sha256` | Behaviour on sha mismatch | Behaviour on missing files |
|---|---|---|---|
| `read_cache_validated` (line 344) | **bug**: `if expected_hash and actual_hash != expected_hash:` short-circuits → silent pass + return df | warn + return None | return None |
| `read_cache_validated_subdir` (line 227, added 3.5E) | **raises** `CacheValidationError` | raises `CacheValidationError` | raises `FileNotFoundError` |

The asymmetry: 3.5E hardened the new `_subdir` variant fail-closed; the legacy `read_cache_validated` was left with the truthy-guard bug. Codex finding T (b) confirmed.

### §2.3 Migration-state audit (Standing Order: empirical claim verification)

```
$ python -m macro_pipeline.utils.cache_audit
Cache audit: root=...keen-torvalds-63c79a/data/cache
  files_checked = 138
  files_ok      = 138
  issues        = 0
OK — 138/138 cache entries valid
```

```
$ inventory: sidecars without data_sha256 = 0
```

**All 138 caches** carry `data_sha256` post-3.5E STEP 0 (the 5 CFTC + HLW sidecar fixup). The "migration to mandatory `data_sha256`" is empirically COMPLETE in this branch as of `9ea0df6`. This informs AM-3.5b-T-1.

### §2.4 Empirical bug reproduction (post-migration regression of strict guard)

Test 1 — direct `pd.read_parquet` bypass at `access.py:142`:

```
$ remove data_sha256 from fred_PAYEMS sidecar
$ python -c "from macro_pipeline.access import load_series; load_series('PAYEMS')"
load_series("PAYEMS") DID NOT RAISE on missing data_sha256 sidecar
  bundle.indicator_id = PAYEMS, data.shape=(22790,), pit_safe=False
  --> Codex finding T (a) confirmed: production read path bypasses validation
```

Test 2 — truthy-guard short-circuit in `cache.read_cache_validated`:

```
$ python -c "from macro_pipeline.cache import read_cache_validated; ..."
read_cache_validated returned df + meta even though sidecar missing data_sha256
  --> Codex finding T (b) confirmed: cache.py:378 truthy-guard short-circuits
```

PAYEMS sidecar restored byte-equal post-test (sha256 matches original).

### §2.5 Tests at risk inventory (with HIGH/MED/LOW classification)

| Test file | Risk | Reason | Mitigation |
|---|---|---|---|
| `tests/test_atomic_cache.py` (9 tests) | **LOW** | Tests `read_cache_validated` happy path + sha-mismatch / schema-mismatch / row-count-mismatch / missing-meta scenarios. Missing-`data_sha256` is NOT exercised (no test for that scenario). My implementation keeps `None` semantics for sha-mismatch + schema + row_count + missing-meta paths; only the missing-`data_sha256` branch becomes a raise. Existing 9 tests should continue to pass. | Run full pytest post-impl |
| `tests/test_cache_validation.py` (4 tests, 3.5E) | LOW | Exercises `read_cache_validated_subdir` (already raises). Unaffected by the legacy helper change. | None |
| `tests/test_cache_atomicity.py` (6 tests, 3.5E) | LOW | POS atomic-write tests; sidecars always have `data_sha256` from `write_cache_atomic`. | None |
| `tests/test_pit_access.py` | MED | Exercises `load_series` against fixture caches. If any fixture cache lacks `data_sha256`, post-3.5b-T `_read_cached_series_and_meta` raises. | grep fixture creators; spot-check before code change |
| `tests/test_pit_enforcement.py` (3.5B) | MED | Same hazard via `load_series`. | Same |
| `tests/test_pit_hlw.py` (3.5C) | MED | Same. | Same |
| `tests/test_fred_loader.py`, `test_yahoo_loader.py`, `test_tv_loader.py`, etc. | LOW | Test loader build paths, not access read paths. `cache_series_to_parquet` writes sidecars with `data_sha256`. | None |
| Loader files using `read_cache_validated` directly: `ebp.py:72`, `ntfs.py:214,281`, `fred_vintage_panel.py:131` | **LOW empirical, MED theoretical** | These callers use `cached = read_cache_validated(...); if cached is None: rebuild`. After 3.5b-T, `None` still returned on schema-mismatch / missing-files / sha-mismatch / row-count-mismatch. Only missing-`data_sha256` raises — empirically zero such caches exist (audit §2.3). | Spot-check; AM-3.5b-T-2 surfaces explicitly |

### §2.6 Cross-call audit: `_read_cached_series_and_meta` callers

After this sub-phase, all 4 callers (lines 168/245/293/325 in `access.py`) inherit validated reads transparently — no per-caller change needed beyond the wrapper refactor.

---

## §3 — Spec §3.2 mandatory items

### §3.1 Files this sub-phase will touch

| File | Action | Notes |
|---|---|---|
| `macro_pipeline/cache.py` | MODIFY | Tighten `read_cache_validated`: replace `if expected_hash and ...` truthy guard with `if not expected_hash: raise` (per AM-3.5b-T-1 disposition) |
| `macro_pipeline/access.py` | MODIFY | `_read_cached_series_and_meta`: route through `read_cache_validated`; raise `CacheValidationError` if helper returns None (production never silent) |
| `macro_pipeline/utils/cache_audit.py` | (no change in 3.5b-T) | Already reports missing `data_sha256` as ERROR (`missing_data_sha256` issue kind, line 99). No change required. |
| `tests/test_cache_validation_strict.py` | NEW | 6 tests per spec §3.5 test plan (4 NEG / 2 POS) |

### §3.2 Decisions locked per Standing Orders

| Decision | Locked default | Empirical override needed? |
|---|---|---|
| 3.5b-T-D1 (route through existing helper) | YES | NO — clear procedural |
| 3.5b-T-D2 (`data_sha256` mandatory) | YES | NO — spec literal aligns with empirical (138/138 have it) |
| 3.5b-T-D3 (subdir variant same discipline) | YES — already in place from 3.5E | NO |
| 3.5b-T-D4 (migration policy: DeprecationWarning + auto-recompute → enforce strictly) | YES | **AM-3.5b-T-1** — empirically post-migration; recommend strict-only |

### §3.3 Ambiguities

| ID | Topic | Routing | Recommended disposition |
|---|---|---|---|
| **AM-3.5b-T-1** | Migration policy depth (T-D4). Spec literal: build the DeprecationWarning + auto-recompute + write sidecar transitional path, then enforce strictly. Empirical: migration is **already complete** (138/138 caches have `data_sha256` from 3.5E STEP 0). The transitional path would be dormant code — never exercised in production. | **PROCEED-with-Dxx (D28)** | **Recommend strict-only**: implement the "raise on missing `data_sha256`" path; skip the DeprecationWarning + auto-recompute scaffold. Rationale: empirical state is post-migration; dormant code accrues maintenance debt; spec D4's three-state ladder (warn → migrate → enforce) was scoped for greenfield deployments where migration has not run, not for this branch where 3.5E STEP 0 already migrated all caches. Standard 3.5A AM4 / 3.5B AM10 / 3.5D AM21 / 3.5E D27 spec-literal-vs-intent precedent applies. If V prefers spec literal, build agent will add the transitional path (~+0.3h). |
| **AM-3.5b-T-2** | Loader callers of `read_cache_validated` (ebp.py:72, ntfs.py:214/281, fred_vintage_panel.py:131) currently use `cached is None` as the "rebuild" signal. After 3.5b-T, missing `data_sha256` raises rather than returns None. Could break a loader rebuild flow. | **PROCEED** (no Dxx) | **Empirically zero impact**: all loader-written caches today carry `data_sha256` (audit §2.3). The schema-mismatch / file-missing / sha-mismatch / row-count-mismatch paths still return None — loader rebuild flows for those scenarios continue working. Only "sidecar present but missing `data_sha256`" is the new-raise path, which doesn't occur in this branch. |
| **AM-3.5b-T-3** (informational) | Test #6 (`test_all_caches_have_sha_post_l3_5b`) operates on the live `DATA_CACHE`. CI may run with empty cache. | **PROCEED** (no Dxx) | Skip the test if `DATA_CACHE` has zero `*.parquet` files. Test is meaningful only when populated cache is present (local dev, post-loader CI). |

### §3.4 Risk callouts

| ID | Risk | Mitigation |
|---|---|---|
| R-T-1 | New raise behavior in `read_cache_validated` may surface latent integrity issues in caches written before 3.5E (none expected — migration complete; cross-checked by §2.3 audit) | Run full pytest post-impl + cache_audit |
| R-T-2 | `_read_cached_series_and_meta` is hot path (called by 4 access flows). Adding sha-recompute to every call adds latency. | Smoke-test confirmed worst-case 0.67ms on largest parquet (fred_USREC.parquet, 393.6KB) at L3.5E §2.1; L3.5b-T inherits that headroom. Re-measure post-impl on PAYEMS read. |
| R-T-3 | NEW Standing Order ("empirical claim verification") explicitly mandates grep-audit / AST-walk proof. Verification report must include both grep proof + unit test proof. | §6.4 of verification report will include grep output proving zero direct `pd.read_parquet` outside validated paths in `access.py` |

### §3.5 Effort estimate

| Step | h |
|---|---:|
| Pre-flight (this) | 0.5 |
| AM-3.5b-T-1 V acknowledgement | gate |
| Cache.py tightening | 0.3 |
| Access.py wrapper refactor | 0.4 |
| 6 new tests | 0.6 |
| Smoke-test post-impl + ruff + Gate 16 + spot-check loader paths | 0.4 |
| Verification report | 0.3 |
| **Total** | **~2.5** within spec 2–3h band |

---

## §4 — Implementation order (post-V acknowledgement on AM-3.5b-T-1)

1. **GATE**: V acknowledges AM-3.5b-T-1 (recommend strict-only) + AM-3.5b-T-2 confirmation.
2. `macro_pipeline/cache.py::read_cache_validated`: tighten the truthy guard.

   Before:
   ```python
   expected_hash = meta.get("data_sha256")
   actual_hash = _sha256_file(parquet_path)
   if expected_hash and actual_hash != expected_hash:
       log.warning("Cache %s: sha256 mismatch; invalidating.", stem)
       return None
   ```

   After:
   ```python
   expected_hash = meta.get("data_sha256")
   if not expected_hash:
       raise CacheValidationError(
           path=str(parquet_path),
           reason="sidecar missing data_sha256 field (mandatory post-L3.5b-T)",
           context={"meta_path": str(meta_path)},
       )
   actual_hash = _sha256_file(parquet_path)
   if actual_hash != expected_hash:
       log.warning("Cache %s: sha256 mismatch; invalidating.", stem)
       return None  # mismatch → return None (loader rebuild path); access wrapper converts to raise
   ```

3. `macro_pipeline/access.py::_read_cached_series_and_meta`: route through validated helper.

   ```python
   def _read_cached_series_and_meta(stem: str, indicator_id: str) -> tuple[pd.Series, dict]:
       from macro_pipeline.cache import read_cache_validated
       from macro_pipeline.exceptions import CacheValidationError

       result = read_cache_validated(stem, DATA_CACHE)
       if result is None:
           raise CacheValidationError(
               path=str(DATA_CACHE / f"{stem}.parquet"),
               reason=(
                   "cache validation failed for production read "
                   "(sha mismatch / schema mismatch / row_count mismatch / "
                   "missing files); rebuild via the appropriate loader"
               ),
               context={"stem": stem, "indicator_id": indicator_id},
           )
       df, meta = result
       if df.shape[1] == 0:
           raise ValueError(f"{indicator_id}: empty parquet at {DATA_CACHE / f'{stem}.parquet'}")
       s = (df[indicator_id] if indicator_id in df.columns else df.iloc[:, 0]).copy()
       s.name = indicator_id
       return s, meta
   ```

4. Write 6 new tests in `tests/test_cache_validation_strict.py` per spec §3.5 test plan.
5. Run full pytest + ruff + Gate 16.
6. Smoke-test: empirical reproduction of bug fix (corrupt + restore PAYEMS sidecar; assert `load_series` now raises).
7. Author `LAYER_3_5b_T_VERIFICATION.md`.
8. Commit: `Layer 3.5b-T: Cache validation discipline tightening (closes Codex finding T)`.
9. PAUSE for V/Strategic APPROVE before 3.5b-U pre-flight.

---

## §5 — Test plan preview (6 new = 4 NEG / 2 POS)

| # | Test | Type | Asserts |
|---:|---|---|---|
| 1 | `test_load_series_raises_on_corrupted_cache` | NEG | Tamper a fixture parquet (1-byte flip preserving snappy structure not always possible — instead use sidecar `data_sha256` modification to force "tampered post-cache" path); `load_series` raises `CacheValidationError` |
| 2 | `test_load_series_raises_on_missing_sha_sidecar` | NEG | Remove `data_sha256` field from sidecar; `load_series` raises `CacheValidationError` |
| 3 | `test_load_series_raises_on_tampered_sidecar` | NEG | Modify `data_sha256` to a fake hex string; `load_series` raises `CacheValidationError` (via mismatch → `read_cache_validated` returns None → wrapper raises) |
| 4 | `test_read_cache_validated_mandatory_sha` | NEG | Direct call to `read_cache_validated` with sidecar missing `data_sha256`; raises `CacheValidationError` (spec D2 enforcement) |
| 5 | `test_load_series_succeeds_on_valid_cache` | POS | Round-trip: write valid cache via `write_cache_atomic`; `load_series` returns matching `IndicatorBundle` |
| 6 | `test_all_caches_have_sha_post_l3_5b` | POS | Walk `DATA_CACHE`; assert every `*.meta.json` has non-empty `data_sha256`. Skip if cache empty (CI). |

NEG/POS = 4/2 = **67% NEG**, exceeds 50% floor.

---

## §6 — Proof-contract mapping (8 items per spec §3.6)

| # | Spec proof | Plan |
|---:|---|---|
| 1 | `grep -n "pd.read_parquet" macro_pipeline/access.py` returns ZERO matches outside validated paths | Verification report §6.4 grep-audit (per new Standing Order); expect zero |
| 2 | `grep -n "pd.read_parquet" macro_pipeline/loaders/` returns only loader writes (not reads); audit all loader reads use validated helpers | Loader read paths use `cache_series_to_parquet` wrapper or `read_cache_validated` already (per §2.2); verification report logs the audit |
| 3 | `python -m macro_pipeline.utils.cache_audit` reports 0 entries with missing `data_sha256` | Pre-impl baseline already 138/138 OK (§2.3). Post-impl confirmation in verification. |
| 4 | `test_load_series_raises_on_corrupted_cache` PASSES | Test #1 + #3 (corruption variants) |
| 5 | `test_load_series_raises_on_missing_sha_sidecar` PASSES | Test #2 |
| 6 | Existing 554 tests still pass (zero regressions) | Full pytest post-impl |
| 7 | Cumulative test count = **560** | 554 + 6 |
| 8 | Conviction 3-field reported with binding identified | §10 + verification report |

---

## §7 — Conviction (3-field, pre-flight)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | **0.94** | High: empirical bug reproduction (§2.4) is unambiguous on both Codex paths (a) and (b); migration state cleanly verified (§2.3); test plan exceeds NEG floor with margin. Slight haircut for AM-3.5b-T-1 disposition (spec-literal-vs-intent reinterpretation). |
| `conviction_operational` | **0.88** | Medium-high: post-impl regression risk concentrated in `test_pit_access.py` / `test_pit_enforcement.py` / `test_pit_hlw.py` MED-risk tests; mitigation = full pytest. Loader rebuild-flow concern (AM-3.5b-T-2) empirically zero-impact. **Binding** at 0.88 due to MED-risk tests requiring confirmation. |
| `conviction_actionability` | **0.94** | High: implementation is small, surgical (~50 lines across 2 files); proof contract is 8 mechanically-verifiable items; new Standing Order's grep-audit requirement is straightforward to satisfy. |
| **Aggregate** | **0.92** | Operational binding (MED-risk tests until full pytest passes). |

---

## §8 — END

Pre-flight complete. **PAUSED** awaiting:

1. **AM-3.5b-T-1** disposition — recommend strict-only (no transitional DeprecationWarning + auto-recompute path; empirically post-migration). File **D28** if approved as recommended.
2. (Informational) AM-3.5b-T-2 + AM-3.5b-T-3 confirmation.

If V approves AM-3.5b-T-1=A (strict-only): proceed with §4 implementation order; expect ~2.0–2.5h coding + tests + verification.

If V prefers spec literal (full migration scaffold): build agent adds DeprecationWarning + auto-recompute path inside `read_cache_validated`; +0.3h.

Per Standing Orders pause-and-verify pattern: this is the gating PAUSE before §4 STEP 2 (cache.py tightening).

---

**END — LAYER_3_5b_T_PREFLIGHT.md**
