# LAYER 3.5A — Pre-Flight Audit (HMM Frozen Contract)

**Spec ref**: `LAYER_3_5_BUILD_SPEC.md` §3 (3.5A)
**Branch**: `claude/layer-3-5-build` (created from `claude/layer-3-build` @ `2f5990e`)
**Worktree**: `D:\macro_pipeline\.claude\worktrees\keen-torvalds-63c79a`
**Date**: 2026-05-09
**Author**: Claude Code (build agent)
**Status**: PAUSED awaiting V / Strategic Claude approval before coding

---

## §1 — Audit Result Header

| Field | Value |
|---|---|
| Sub-phase | 3.5A — HMM Frozen Contract |
| Estimated effort (spec) | 8–12h |
| My estimate after audit | **9–11h** (within range) |
| Tests added (spec target) | +10 (8 NEG / 2 POS) |
| Gate added | Gate 12 |
| Locked decisions (3.5A-D1..D4) | filelock (D1), 30s timeout (D2), retrain & commit fresh as v1 if non-reproducible (D3), pickle protocol=4 (D4) |
| Anticipated deviations | D20 likely (artifact regeneration / sidecar schema; see §6) |
| Conviction (statistical / operational / actionability) | 0.78 / 0.72 / 0.80 — see §10 |

---

## §2 — Spec §3.2 Mandatory Pre-Flight Items (3.5A-specific)

### §2.1 Item 1 — Current `regime_3state_v1.pkl` exists locally; record sha256

**Finding**: Pickle exists in the **master worktree** `D:\macro_pipeline\data\cache\hmm\regime_3state_v1.pkl` but **NOT in this build worktree** (because `data/` is gitignored and was never junction-linked here).

| Field | Value |
|---|---|
| Pickle path (master) | `D:\macro_pipeline\data\cache\hmm\regime_3state_v1.pkl` |
| Pickle path (build worktree) | NOT PRESENT |
| sha256 (master copy) | `aa813d167e0e3f591c55cf254b06e1f977e48e1fd158f96845ac7b02791514c5` |
| Size | 2,593 bytes |
| mtime (master copy) | 2026-05-09 11:51 |

**Risk callout (R1)**: This worktree has no `data/` directory. Per `HANDOFF_CLAUDE_CODE_v3.md` §9, worktrees are expected to be junction-linked to the master `data/`. That setup did not happen here. Proposed action during 3.5A implementation: create junction from `D:\macro_pipeline\data\` → `<this-worktree>\data\`, OR populate cache directly. Pre-flight does NOT change worktree state.

### §2.2 Item 2 — `.gitignore` lines 20-21 confirmed to exclude `data/cache/`

**Finding**: Confirmed. `.gitignore` includes:
```
# Cache (auto-managed)
data/cache/
data/derived/
data/output/
```

Spec §3.3-1's prescribed modification (whitelist `data/cache/hmm/*` carve-outs) is unambiguous.

### §2.3 Item 3 — `regime/__init__.py` exports `train_and_save_hmm`

**Finding**: Confirmed. `macro_pipeline/regime/__init__.py:37` and `:74` both export `train_and_save_hmm`. Codex finding R is real and addressable per spec §3.3-4.

### §2.4 Item 4 — Inference path `predict_state()` → `load_hmm()` → `train_and_save_hmm()`

**Finding**: Confirmed. The fall-through path is:
- `macro_pipeline/regime/hmm_states.py:267` — `predict_state()` calls `load_hmm(pickle_path)`
- `macro_pipeline/regime/hmm_states.py:241–242` — `load_hmm()` if pickle missing → `return train_and_save_hmm(pickle_path=pickle_path)`
- `macro_pipeline/regime/hmm_states.py:196–197` — `train_and_save_hmm()` if pickle exists (and `force=False`) → calls `load_hmm` (loop terminates because branch above exists)

Codex findings A, D, O, Q, R, S all root in this auto-train path. Spec §3.3-3 prescribes its removal.

### §2.5 Item 5 — hmmlearn version compatibility

**Finding**: Confirmed match.

| Source | Value |
|---|---|
| `pyproject.toml` floor | `hmmlearn>=0.3.0` |
| `uv.lock` resolved | `hmmlearn==0.3.3` (sdist sha256 `1d3c5dc4...44ec`) |
| Master venv runtime | `hmmlearn 0.3.3` (verified by `import hmmlearn; print(hmmlearn.__version__)`) |
| Pickle's hmmlearn version | NOT EMBEDDED in current `TrainedHmm` dataclass — must be reconstructed from ambient interpreter state at training time |

**Risk callout (R2)**: The current pickle does not carry the hmmlearn version that produced it. The spec sidecar adds `hmmlearn_version: "0.3.3"` (§3.3-1). Since 3.5A is a fresh artifact ceremony (commit + sidecar + script), I propose to **generate the canonical artifact via the new `scripts/train_hmm_v1.py`** as part of 3.5A — guaranteeing version provenance — rather than blessing the existing pickle whose provenance cannot be programmatically verified. This is consistent with spec §3.2 ("If pre-flight reveals pickle is reproducible from current code: proceed. If not reproducible: file D20 and propose retrain-and-commit-fresh as the artifact"). I will **need to verify** the regenerated pickle yields the same `state_to_label` mapping and `nber_overlap_per_state` as the existing master pickle (qualitative reproducibility) before locking the artifact.

### §2.6 Item 6 — feature matrix / NBER label hashes reconstructable

**Finding**: Yes, reconstructable from current code, with caveats.

- `_build_monthly_features` (`hmm_states.py:101-126`) deterministically constructs the feature matrix from `T10Y2Y, PHILLY_LEI_PROXY, IC4WSA, NFCI, UMCSENT` (5 features, NOT 6 as the spec template at §3.3-1 illustratively shows — the spec text acknowledges this: "current count post-D2 substitution"). Determinism is gated on:
  - FRED loader output stability for the 5 series at 1982-01 → 2019-12
  - `dropna()` semantics at line 125 (alignment over the 5-series intersection)
  - `resample("ME").last()` semantics (pandas-pinned via uv.lock)
- `_label_states_by_nber` (`hmm_states.py:145-182`) deterministically labels HMM states by NBER overlap. NBER overlap on training window is itself deterministic from the cached `NBER_REC_LABEL` series.

| Inspected pickle field | Value (master copy) |
|---|---|
| `model_version` | `regime_3state_v1` |
| `feature_names` | `('T10Y2Y', 'PHILLY_LEI_PROXY', 'IC4WSA', 'NFCI', 'UMCSENT')` (5, not 6) |
| `training_start` | 1982-01-01 |
| `training_end` | 2019-12-31 |
| `n_obs` | 456 |
| `state_to_label` | `{0: 'expansion', 2: 'late-cycle', 1: 'recession'}` |
| `nber_overlap_per_state` | `{0: 0.0, 1: 0.500, 2: 0.0378}` — recession state (idx=1) has highest overlap, satisfies §3.7 proof item 8 |
| `feature_mean` | `[1.0682, 1.3477, 358393.09, -0.2451, 88.0145]` |
| `feature_std`  | `[0.8351, 0.8098, 81541.88, 0.6918, 11.7994]` |
| `hmm.n_components` | 3 |
| `hmm.random_state` | 42 (matches `HMM_RANDOM_STATE`) |

Important: the spec template at §3.3-1 shows `state_to_label_mapping = {"0": "expansion", "1": "late-cycle", "2": "recession"}`, but the **actual label assignment is data-driven** by NBER overlap (line 176-181). The actual mapping is `{0: 'expansion', 2: 'late-cycle', 1: 'recession'}`. The sidecar should reflect actual mapping, not a placeholder.

---

## §3 — Spec §2.2 Generic Pre-Flight Items

### §3.1 Item 1 — Inventory of files this sub-phase will touch

| File | Action | Existing lines | Notes |
|---|---|---|---|
| `.gitignore` | MODIFY | lines 20-21 (`data/cache/`) | Add carve-outs for `data/cache/hmm/*.pkl` and `*.meta.json` per spec §3.3-1 |
| `data/cache/hmm/regime_3state_v1.pkl` | NEW (committed binary) | n/a | Generated by `scripts/train_hmm_v1.py`; ~2.5 KB |
| `data/cache/hmm/regime_3state_v1.meta.json` | NEW | n/a | 14 mandatory keys per spec §3.3-1 |
| `scripts/train_hmm_v1.py` | NEW | n/a | Standalone, not imported by package |
| `scripts/README.md` | NEW | n/a | Documents admin-only nature |
| `macro_pipeline/regime/hmm_states.py` | MODIFY | 310 lines | Remove auto-train (lines 241-242); remove `train_and_save_hmm` (move to scripts/, lines 185-235); add sidecar reading + sha verification + filelock; tighten `load_hmm` |
| `macro_pipeline/regime/__init__.py` | MODIFY | 75 lines | Remove `train_and_save_hmm` from public exports (lines 37, 74); update docstring (line 10) |
| `macro_pipeline/regime/exceptions.py` | MODIFY | 67 lines | Add `HmmArtifactMissingError`, `HmmArtifactCorruptError`, `HmmMetadataIncompatibleError`, `HmmConcurrencyError` |
| `pyproject.toml` | MODIFY | n/a | Add `filelock>=3.13` dependency |
| `uv.lock` | MODIFY | n/a | `uv lock` after pyproject edit (V's discretion if uv unavailable on PATH) |
| `macro_pipeline/cache.py` | (LIKELY MODIFY) | 177 lines | Extend `write_cache_atomic` to support pickle, OR add `write_pickle_atomic` parallel helper. See §6 for ambiguity. |
| `macro_pipeline/validation.py` | MODIFY | 2165 lines | Add `validate_gate12_hmm_frozen()` after `validate_gate11_r_squared_panel()` (≈ line 2063); add `_cli_gate12()`; route in `__main__` block (lines 2106-2137) |
| `tests/test_regime_hmm_frozen.py` | NEW | n/a | 10 new tests per §3.5 |
| `tests/test_regime_hmm.py` | LIKELY MODIFY | 99 lines | Existing fixture (lines 27-29) and tests rely on auto-train path; must adapt. See §3.2 below. |

### §3.2 Item 2 — Existing tests that may break

| Test file | Test name(s) | Why may break | Mitigation |
|---|---|---|---|
| `tests/test_regime_hmm.py` | `trained_hmm` fixture (line 27-29: `return load_hmm()`) | If pickle absent, fixture currently auto-trains; after 3.5A it will raise `HmmArtifactMissingError`. | Pickle WILL be committed → fixture passes. Confirm in implementation by running test. |
| `tests/test_regime_hmm.py` | `test_hmm_pickle_loadable_directly` (line 83-88) | Reads `HMM_PICKLE_PATH` raw pickle; expects `TrainedHmm` instance. After 3.5A pickle is committed, file present, test passes if dataclass schema unchanged. | Keep `TrainedHmm` dataclass shape unchanged. |
| `tests/test_regime_hmm.py` | `test_hmm_pickle_roundtrip_identical` (line 67-80) | Calls `train_and_save_hmm(pickle_path=tmp_pickle, force=True)` directly. If we remove `train_and_save_hmm` from `macro_pipeline.regime`, this test must import from `scripts.train_hmm_v1` OR be updated. | Per spec §3.3-2 the function moves to `scripts/`. Update this test to either (a) import from `scripts/` (requires sys.path manipulation) or (b) skip / rewrite as a smoke that runs the script as a subprocess. Suggest option (b) for cleanliness. |
| `tests/test_regime_context.py` | (need to scan) | `build_regime_context()` calls `predict_state()` → `load_hmm()`. If pickle is committed and present, no regression. | Verify by running suite post-implementation. |
| `tests/test_regime_state_derivation.py` | (need to scan) | Same as above. | Verify. |
| `macro_pipeline/validation.py` Gate 8 (line 1251-1419) | `validate_gate8_regime` calls `build_regime_context` which calls `predict_state` | Same dependency on pickle being present. | Verify. |
| All tests that transitively touch `predict_state` | n/a | Same dependency. | The committed artifact ensures pickle is present in clean clones. |
| `tests/test_offline_mocks.py` | (need to scan) | Mock-FRED path may not exercise HMM training; should verify mocks don't accidentally trigger auto-train (they shouldn't post-3.5A because path is removed). | Verify — and test §3.5 #7 (`test_hmm_no_auto_train_in_inference_path`) specifically asserts this contract. |

**Net impact**: I expect **1 file (`tests/test_regime_hmm.py`) to need ≤2 small edits** (the roundtrip test); no other test breakage IF pickle is committed and dataclass shape preserved. Will reverify by running the suite immediately after the artifact-commit step.

### §3.3 Item 3 — Empirical reading of current state for thresholds (per §2.3)

**3.5A does NOT have a §2.3-listed empirical calibration requirement** (those are 3.5B confidence cap, 3.5D indeterminate cap, 3.5E sha latency). However, two empirical readings are warranted:

1. **Pickle reproducibility check** (gates D20 disposition):
   - Action during implementation: regenerate via new `scripts/train_hmm_v1.py` and compare `state_to_label`, `feature_mean`, `feature_std`, `nber_overlap_per_state` to the master pickle's values (recorded in §2.6 above).
   - Acceptance: bit-exact pickle match is unlikely (pickle protocol differences, ordering); behavioral match (same `state_to_label`, `feature_mean` within rtol=1e-12, identical `nber_overlap_per_state`) is the criterion.
   - If behavioral match fails → file D20; propose locking the regenerated artifact as canonical (since reproducibility from clean clone is the contract).
   - Smoke-test latency budget: ≤ 90s (loads 5 FRED series + fits HMM, 200 iterations max).

2. **Concurrent-load smoke** (gates §3.5 test #6):
   - Action during implementation: spawn 4 threads, each calling `load_hmm()`, assert all return the same `TrainedHmm` (or same `feature_mean`).
   - Latency budget per thread: ≤ 1s (just loads from disk + sha verify).

### §3.4 Item 4 — Ambiguities found in spec → REQUEST CLARIFICATION

| # | Ambiguity | Spec ref | Proposed resolution | Decision needed before coding? |
|---|---|---|---|---|
| **AM1** | Spec §3.3-1 sidecar example shows `state_to_label_mapping = {"0": "expansion", "1": "late-cycle", "2": "recession"}` — but actual mapping is data-driven and is `{0: 'expansion', 2: 'late-cycle', 1: 'recession'}` for the current pickle. | §3.3 sidecar JSON | Sidecar reflects ACTUAL data-driven mapping, not the placeholder. JSON keys are stringified ints (matches spec format). Verified during regenerate-and-compare. | NO — proceed with actual mapping. |
| **AM2** | Spec §3.3-1 sidecar shows `feature_names: 6 features after L5-1; current count post-D2 substitution`. Current count is **5** (`T10Y2Y, PHILLY_LEI_PROXY, IC4WSA, NFCI, UMCSENT`). | §3.3 sidecar JSON | Sidecar lists 5 actual feature names; L5-1 backlog item will bump to 6 if NAPMNOI is restored. | NO — proceed with 5. |
| **AM3** | Spec §3.3-2 says `cache.write_cache_atomic` should be "extended to handle pickle". Current `cache.py:84-119` writes parquet; pickle bytes are different (no `to_parquet`, no row_count concept). Two options: (a) generalize via abstract write callback; (b) add parallel helper `write_pickle_atomic_with_meta`. | §3.3-2 | Recommend **(b) parallel helper** — keeps existing parquet contract clean and avoids generic-vs-specific API churn. New helper signature: `write_pickle_atomic_with_meta(pickle_path, payload_bytes, meta_dict)`. | **YES — preferred resolution requested.** |
| **AM4** | Spec §3.6 Gate 12 pass criterion 7: "scripts/train_hmm_v1.py reproduces the committed artifact when run from clean state — exact match required". "Exact match" of a hmmlearn pickle across runs is fragile (pickle contains float arrays + protocol metadata). Likely intent is **behavioral exact match**: same `state_to_label`, `feature_mean`/`feature_std` byte-equal under deterministic seed. | §3.6 #7 | Interpret "exact match" as **byte-equal pickle** if and only if (a) same Python interpreter version, (b) same hmmlearn version, (c) same numpy version, (d) deterministic random seed (already 42). Otherwise behavioral match (same model parameters bit-equal). | **YES — confirmation requested**: "byte-equal under fixed env, behavioral-equal otherwise" is acceptable? |
| **AM5** | Spec §3.5 test #8: `from macro_pipeline.regime import train_and_save_hmm raises ImportError`. The function is moving to `scripts/train_hmm_v1.py`. The hmm_states module currently exports it (line 309) and __init__ re-exports (line 74). After 3.5A, `train_and_save_hmm` should NOT exist in `macro_pipeline.regime`. The spec is asking we remove it from `__init__.py` exports AND from the public `__all__` of `hmm_states.py`. To make `from macro_pipeline.regime import train_and_save_hmm` raise `ImportError`, we must also remove the function definition or move it physically out of `hmm_states.py`. | §3.5 test #8 | Remove `train_and_save_hmm` (and its helpers `_build_monthly_features`, `_fit_hmm`, `_label_states_by_nber` if not needed elsewhere) from `hmm_states.py` and put them in `scripts/train_hmm_v1.py`. Inference path keeps only `load_hmm` + `predict_state`. | NO — clear from spec; flagging for completeness. |
| **AM6** | Filelock library: spec §3.3-5 says "filelock for cross-platform safety". Current `pyproject.toml` does NOT include `filelock`. `uv lock` after edit would write to `uv.lock`. V's earlier convention (handoff §7.5): "uv lock after adding (exception: do not run if uv not on PATH)". `uv` is NOT on PATH in this worktree. | §3.3-5 | Add `filelock>=3.13` to pyproject.toml; defer `uv lock` to V's master worktree (where uv is presumably installed) OR commit pyproject change without lockfile update for now and request V re-runs `uv lock` in master worktree before push. | **YES — confirm whether `uv lock` should be deferred.** |
| **AM7** | Spec §3.5 test #6: `test_hmm_concurrent_load_safe_no_race`: "4 concurrent threads loading; all succeed; same model returned". Threads in CPython have GIL; race conditions on a *file* (the pickle path or its sidecar) are real. Filelock with 30s timeout handles cross-process; for in-process threads, a `threading.Lock` may also be needed. | §3.5 #6 | Use `filelock.FileLock` (works for both threads and processes — filelock is reentrant per-process and serializes across processes). Test with `concurrent.futures.ThreadPoolExecutor(4)`. | NO — proceed with filelock. |
| **AM8** | Spec §3.3-1 sidecar mandates `training_script_sha256`. The script doesn't exist yet (we're creating it in this same sub-phase). Bootstrapping problem: sidecar's sha references a file whose contents include the call that writes the sidecar. | §3.3-1 sidecar | Two-pass write: (a) write script, sha it, (b) script computes pickle + sidecar with the captured script_sha. The script can read its own file via `__file__` and hash the bytes. Standard pattern. | NO — clear procedural fix. |
| **AM9** | Spec §3.4-D4: "pickle protocol=4 (Python 3.8+ stable) vs protocol=5". Current code uses `pickle.dump(bundle, fh)` (default — Python 3.12 default is protocol 5). Locking to protocol 4 is the spec-locked default. Switching from protocol-5 (current pickle) to protocol-4 (new pickle) means existing pickle's bytes won't match new pickle's bytes — gates byte-equal repro test interpretation in AM4. | §3.4-D4 | Lock to **protocol=4** per spec default. Regenerate pickle under new protocol. Existing master-worktree pickle (which was protocol-5 likely) is supplanted. | NO — explicit default. |

### §3.5 Item 5 — Risk callouts: spec assumptions that may be false on inspection

| # | Risk | P(occurrence) | Impact | Mitigation |
|---|---|---|---|---|
| R1 | This worktree has no `data/` directory; junction not set up. Tests requiring cached series (FRED, NBER labels, etc.) will either fail or call live APIs. | 100% (verified above) | Blocks running tests / gates / training script. | During implementation: create junction `D:\macro_pipeline\data` ←→ `<this-worktree>\data` before running pytest. ALTERNATIVE: copy `data/` (~heavy). RECOMMEND junction. |
| R2 | hmmlearn version embedded in current pickle is ambient/unrecorded. Cannot prove the master pickle was produced under hmmlearn 0.3.3. | 30% (best guess from L3A timing) | Affects D20 disposition wording but not 3.5A outcome (we're regenerating). | Regenerate via new script under hmmlearn 0.3.3 (verified runtime); accept regenerated pickle as canonical. File D20. |
| R3 | Pickle protocol mismatch: current uses default-5; spec says protocol-4. Bit-equal across versions impossible. | 100% if old pickle is protocol-5 | "exact match" Gate 12 criterion #7 requires interpretation per AM4. | Pre-clear interpretation with V/Strategic before coding. |
| R4 | `RL3.5-1` from spec: existing HMM pickle is not reproducible from current code. | spec says 25-35%. My estimate after audit: 5–15% (deterministic code path with seed=42 + pinned hmmlearn). | Regenerate vs current state diverges → file D20 with proposed disposition. | Regenerate via script and compare structurally. |
| R5 | Test `test_hmm_pickle_roundtrip_identical` calls `train_and_save_hmm` directly via `macro_pipeline.regime` import. Removing the function breaks this test. | 100% | Test must be updated. | Replace with subprocess call to script, or import from scripts/ via sys.path. |
| R6 | Spec assumes "lock timeout 30s" is sufficient. On a slow Windows filesystem (network-mapped drive, AV scanner), 30s might be tight for repeated test runs. | LOW–MED 10-20% | Spurious test failure under load. | If observed: bump to 60s or accept as flaky (file Dxx). |
| R7 | `filelock` introduces a new public API surface (lockfile next to pickle). Lockfile presence may confuse other tooling. | LOW 5-10% | Cosmetic; mitigated by explicit lockfile naming. | Use `pickle_path + ".lock"` per spec §3.3-5; document in scripts/README.md. |
| R8 | Removing auto-train may break a downstream caller I haven't found. `Grep` should be exhaustive but some dynamic patterns (e.g., string-based imports) could escape. | LOW 5-10% | Surface during pytest. | Run full pytest immediately after refactor; surface any failures. |
| R9 | The committed pickle binary (~2.5 KB) is small but still adds to repo. If we ever bump v2 (L5-1), we'll have v1 lingering. | LOW (cosmetic) | Tiny repo bloat. | Acceptable; remove v1 when v2 supersedes it. |

### §3.6 Item 6 — Estimated effort within stated range

| Phase | My estimate (h) | Notes |
|---|---|---|
| Pre-flight (this document) | 0.6h | Done |
| Address ambiguities AM3, AM4, AM6 (V approval) | n/a (gate) | n/a |
| Set up `data/` junction in this worktree | 0.2h | Single mklink command |
| Add filelock to pyproject; (defer uv lock) | 0.2h | |
| Author `scripts/train_hmm_v1.py` + `scripts/README.md` | 1.5–2.0h | |
| Refactor `hmm_states.py` (remove auto-train, add sidecar/sha/filelock) | 2.0–2.5h | |
| Add new exception classes | 0.3h | |
| Update `regime/__init__.py` exports | 0.2h | |
| `.gitignore` carve-outs | 0.1h | |
| Cache helper extension/parallel (pending AM3 resolution) | 0.5–1.0h | |
| Generate canonical pickle + sidecar via new script | 0.5h | Includes structural diff vs master |
| Tests: write 10 new + adapt 1-2 existing | 2.0–2.5h | |
| Gate 12 in validation.py + CLI | 0.6h | |
| Run full pytest suite, fix regressions | 0.5–1.0h | Buffer |
| Compose verification report | 0.5h | |
| **Total** | **9.0–11.0h** | within spec's 8-12h range |

---

## §4 — Decisions Locked Per User Header ("Defaults confirmed")

User stated: 21 decision points are locked to defaults unless overridden in this build kickoff message. No overrides were paste'd. Therefore:

| Decision | Locked default | Source |
|---|---|---|
| 3.5A-D1 (lock library) | filelock | spec §3.4 |
| 3.5A-D2 (lock timeout) | 30s | spec §3.4 |
| 3.5A-D3 (non-reproducible disposition) | retrain & commit fresh as v1 | spec §3.4 |
| 3.5A-D4 (pickle protocol) | protocol=4 | spec §3.4 |

All four locked-default decisions match my pre-flight recommendations.

---

## §5 — Decisions Requested From V / Strategic Claude (BEFORE Coding)

The four ambiguities surfaced as **YES — decision needed**:

### §5.1 AM3 — Cache helper strategy

| Option | Description | Effort | Risk |
|---|---|---|---|
| **A (recommended)** | Add parallel helper `write_pickle_atomic_with_meta(pickle_path, bytes_payload, meta_dict)` in `macro_pipeline/cache.py`. Reuses `atomic_write_bytes` + `atomic_write_bytes`-for-meta. Keeps existing parquet-only `write_cache_atomic` untouched. | LOW (~0.5h) | LOW. New surface, no churn. |
| B | Generalize `write_cache_atomic` to take a write-callback. Existing parquet helper becomes `write_cache_atomic(stem, df, meta, cache_dir, payload_writer=atomic_write_parquet)`. New pickle path passes `payload_writer=lambda p, x: atomic_write_bytes(p, pickle.dumps(x, protocol=4))`. | MEDIUM (~1.0h) | MED. Touches every existing caller. Wider blast radius for a contained need. |
| C | Inline the atomic-write pattern in the script (no new helper). | LOW (~0.3h) | MED. Code duplication; future audit harder. |

**Recommend A**.

### §5.2 AM4 — "Exact match" reproducibility interpretation

| Option | Description |
|---|---|
| **A (recommended)** | Byte-equal pickle when run on the same env stack (Python 3.12.10, hmmlearn 0.3.3, numpy as locked, scipy as locked, deterministic random_state=42). On other envs: behavioral-equal (same `feature_mean`, `feature_std`, `state_to_label`, `nber_overlap_per_state` to within rtol=1e-12). Gate 12 #7 enforces only on the locked env. |
| B | Strict byte-equal always. Risks Gate 12 fragility on minor lib bumps. |
| C | Always behavioral-only. Loses byte-level integrity guarantee. |

**Recommend A**.

### §5.3 AM6 — `uv lock` deferral

| Option | Description |
|---|---|
| **A (recommended)** | Edit `pyproject.toml` (add `filelock>=3.13`) in this worktree. Mark `uv.lock` as needing re-resolution in 3.5A's verification report. V re-runs `uv lock` in master worktree before push. |
| B | Block 3.5A coding until `uv` is installed in this worktree. |
| C | Pin filelock to a specific version (`filelock==3.13.1`) in pyproject and manually-edit `uv.lock` (high risk of incoherence). |

**Recommend A**.

---

## §6 — Anticipated D20 Filing

If pickle regeneration produces structurally divergent output from the master pickle (state_to_label permutation, feature_mean drift > 1e-9), I will file:

```
D20 — 2026-05-09 — 3.5A — HMM pickle regenerated as canonical v1 artifact
Disposition: ACCEPT (per spec §3.4-D3 locked default)
Reason: Master worktree pickle's hmmlearn version was unrecorded.
        New artifact is generated under verified hmmlearn 0.3.3,
        protocol=4, with full sidecar metadata. Behavior re-verified
        against the 2008-09-15 recession proof point (P>0.7, per
        existing test_hmm_predict_2008_09_recession).
Layer 5 backlog impact: none.
```

If regeneration is structurally identical (best case): no D20 needed; the regenerated pickle replaces the un-versioned master pickle without controversy.

---

## §7 — Implementation Order (Post-Approval)

1. Set up `data/` junction in this worktree (or copy as fallback).
2. Add `filelock>=3.13` to `pyproject.toml` (defer `uv lock`).
3. Create `scripts/train_hmm_v1.py` and `scripts/README.md` with full sidecar generation logic.
4. Generate canonical artifact + sidecar; structurally compare to master pickle.
5. If divergent → file D20; commit regenerated artifact as `regime_3state_v1.pkl`.
6. Modify `.gitignore` to whitelist `data/cache/hmm/` carve-outs.
7. Add `git add data/cache/hmm/regime_3state_v1.pkl` + `regime_3state_v1.meta.json`.
8. Refactor `macro_pipeline/regime/hmm_states.py`:
   - Remove `train_and_save_hmm` + helpers (move to scripts/).
   - Replace `load_hmm` with sidecar-aware, sha-verifying, filelock-protected loader.
   - Tighten `predict_state` (no implicit train).
9. Add new exception classes to `regime/exceptions.py`.
10. Update `regime/__init__.py` exports (remove `train_and_save_hmm`).
11. (AM3) Add `write_pickle_atomic_with_meta` helper to `cache.py`.
12. Add `validate_gate12_hmm_frozen()` to `validation.py` + CLI route.
13. Write 10 new tests in `tests/test_regime_hmm_frozen.py`.
14. Adapt `tests/test_regime_hmm.py` (1-2 small edits per §3.2).
15. Run full pytest suite; fix any regression.
16. Run `python -m macro_pipeline.validation gate12` (and gate 8) — confirm green.
17. ruff clean + commit.
18. Compose verification report per spec §3.7 (12 items).
19. PAUSE.

---

## §8 — Test Plan Preview (will be detailed in implementation)

| # | Test | Type | Mock strategy |
|---|---|---|---|
| 1 | `test_hmm_missing_artifact_raises_HmmArtifactMissingError` | NEG | Move pickle to tmp, call `load_hmm()` |
| 2 | `test_hmm_corrupt_artifact_raises_HmmArtifactCorruptError` | NEG | Flip 1 byte in pickle, call `load_hmm()` |
| 3 | `test_hmm_metadata_schema_version_mismatch_raises` | NEG | Edit sidecar's `schema_version` to "0.0", call `load_hmm()` |
| 4 | `test_hmm_load_validates_all_metadata_fields` | POS | Verify all 14 mandatory keys present + types |
| 5 | `test_hmm_inference_deterministic_across_loads` | POS | 5× `load_hmm()` + `predict_state(2008-09-15)`, assert identical |
| 6 | `test_hmm_concurrent_load_safe_no_race` | NEG/POS | `ThreadPoolExecutor(4)` + assert all return same `feature_mean` |
| 7 | `test_hmm_no_auto_train_in_inference_path` | NEG | `monkeypatch.setattr` for any train-callable; pickle present → success without invocation |
| 8 | `test_hmm_train_not_in_public_exports` | NEG | `pytest.raises(ImportError)` + `from macro_pipeline.regime import train_and_save_hmm` |
| 9 | `test_hmm_lock_timeout_raises_HmmConcurrencyError` | NEG | Acquire lock externally; lock-timeout path raises |
| 10 | `test_hmm_state_to_label_mapping_deterministic` | POS | Assert sidecar mapping = pickled mapping |

---

## §9 — Proof Contract Mapping (12 items, spec §3.7)

| Spec proof # | How I will demonstrate |
|---|---|
| 1 | `git ls-files data/cache/hmm/` output |
| 2 | `sha256sum data/cache/hmm/regime_3state_v1.pkl` vs `cat data/cache/hmm/regime_3state_v1.meta.json` |
| 3 | `python -c "from macro_pipeline.regime import train_and_save_hmm"` stderr |
| 4 | `pytest tests/test_regime_hmm_frozen.py -v` summary line |
| 5 | (move pickle) + `python -c "..."` stderr capture |
| 6 | `python scripts/train_hmm_v1.py --dry-run` stdout (sha-comparison output) |
| 7 | `cat data/cache/hmm/regime_3state_v1.meta.json` highlighting `hmmlearn_version` |
| 8 | Sidecar `nber_overlap_per_state`: 50% > 3.78% > 0% (recession > late-cycle > expansion) |
| 9 | Concurrent load test result + assertion message |
| 10 | `python -m macro_pipeline.validation gate12` output |
| 11 | `pytest --collect-only -q | tail -1` cumulative count |
| 12 | §10 of this document, refreshed at verification time |

---

## §10 — Pre-Flight Conviction (3-Field, per spec §2.4)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | **0.78** | High: spec is mathematically clear (sha256, sidecar schema, dataclass shape unchanged). Lower than 0.85 because reproducibility (regenerate vs master pickle) is empirical and unverified pre-coding. |
| `conviction_operational` | **0.72** | Medium-high: data quality clear (single FRED-sourced training matrix), operational path clear (admin-only script), but `data/` junction setup risk (R1) and `uv.lock` deferral (AM6) introduce environmental fragility. |
| `conviction_actionability` | **0.80** | High: the 4 LOCK + 3 ASK structure gives a clean coding lane post-approval; effort estimate 9-11h fits within 8-12h band; downstream Layer 5 can fit Ridge/CDRS weights against deterministic regime states. |

Aggregate `confidence_overall` (per Layer 1.5 cap): MIN(caps from §7.6 of HANDOFF_MASTER_RESUME_v3) — this is a 3Y-equivalent-horizon analysis decision, capped at ≤ 0.75. Reported aggregate: **0.72** (binding from operational).

---

## §11 — END

Pre-flight complete. **PAUSED** awaiting:
1. APPROVE (proceed with implementation per §7 order, applying recommended AM3 / AM4 / AM6 resolutions), OR
2. REVISE (specify alternative for any of AM3 / AM4 / AM6 / Risk-callout mitigations).

Per `HANDOFF_CLAUDE_CODE_v3.md` §3, I will not start coding until V or Strategic Claude returns a decision on §5 ambiguities.

---
