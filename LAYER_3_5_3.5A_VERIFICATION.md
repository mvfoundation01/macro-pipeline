# LAYER 3.5A — Verification Report (HMM Frozen Contract)

**Commit**: `830bcd0` on `claude/layer-3-5-build`
**Base**: `claude/layer-3-build` @ `2f5990e` (Layer 3D)
**Date**: 2026-05-09
**Author**: Claude Code (build agent)
**Status**: PAUSED awaiting V verification per `HANDOFF_CLAUDE_CODE_v3.md` §2

---

## §1 — Header

| Field | Value |
|---|---|
| Sub-phase | 3.5A — HMM Frozen Contract |
| Spec ref | `LAYER_3_5_BUILD_SPEC.md` §3 |
| Branch / commit | `claude/layer-3-5-build` @ `830bcd0` |
| Tests delta | **+10** new (506 → 516); 0 regressions |
| Gate added | **Gate 12** PASS |
| Gates total | **12/12 green** (1, 2, 3, 4A-D, 8, 9, 10, 11, 12) |
| Deviations filed | none (D20 NOT needed — regenerated pickle byte-equal to master) |
| Effort actual | ~5.5h (vs 9–11h pre-flight estimate; faster because regenerate-and-commit was no-op vs the master pickle) |

---

## §2 — Proof Contract (12 items per spec §3.7)

| # | Spec proof item | Result | Evidence |
|---|---|---|---|
| 1 | `git ls-files data/cache/hmm/` shows pickle and meta.json tracked | PASS | `git ls-files data/cache/hmm/` → `data/cache/hmm/regime_3state_v1.meta.json` + `data/cache/hmm/regime_3state_v1.pkl` |
| 2 | `sha256sum data/cache/hmm/regime_3state_v1.pkl` matches sidecar `data_sha256` | PASS | recomputed `aa813d167e0e3f591c55cf254b06e1f977e48e1fd158f96845ac7b02791514c5` ≡ sidecar.data_sha256 |
| 3 | `python -c "from macro_pipeline.regime import train_and_save_hmm"` raises ImportError | PASS | Test #8 `test_hmm_train_not_in_public_exports` PASSED |
| 4 | `pytest tests/test_regime_hmm_frozen.py` — 10 tests pass | PASS | 10 passed in 6.07s; details in §3 below |
| 5 | mv pickle → load_hmm raises HmmArtifactMissingError (NOT auto-train) | PASS | Test #1 `test_hmm_missing_artifact_raises_HmmArtifactMissingError` PASSED |
| 6 | `python scripts/train_hmm_v1.py --dry-run` shows would-be sha matches | PASS | dry-run output: `would-be pickle sha256: aa813d16…` + `MATCH` against existing |
| 7 | sidecar `hmmlearn_version` = `"0.3.3"` = `uv.lock` resolved version | PASS | sidecar.hmmlearn_version=`"0.3.3"`; uv.lock entry sha256=`1d3c5dc4…` (hmmlearn 0.3.3) |
| 8 | sidecar `nber_overlap_per_state`: recession state highest NBER overlap | PASS | `{"0":0.0, "1":0.5, "2":0.0378}`; `state_to_label_mapping["1"]="recession"` ⇒ recession overlap=0.5 > others |
| 9 | 4-thread concurrent `load_hmm()` test passes | PASS | Test #6 `test_hmm_concurrent_load_safe_no_race` PASSED (filelock serialises; identical bundles returned) |
| 10 | Gate 12 passes in `validation.py` | PASS | `python -m macro_pipeline.validation gate12` → `Gate 12 - Layer 3.5A HMM Frozen Contract: PASS` |
| 11 | Cumulative test count = 516 (or higher) | PASS | full pytest: `516 passed in 101.14s` |
| 12 | Conviction (statistical / operational / actionability) reported | PASS | §6 below |

All 12 items PASS.

---

## §3 — Test Run Detail

### §3.1 New tests (`tests/test_regime_hmm_frozen.py`)

| # | Test | Type | Result |
|---|---|---|---|
| 1 | `test_hmm_missing_artifact_raises_HmmArtifactMissingError` | NEG | PASS |
| 2 | `test_hmm_corrupt_artifact_raises_HmmArtifactCorruptError` | NEG | PASS |
| 3 | `test_hmm_metadata_schema_version_mismatch_raises` | NEG | PASS |
| 4 | `test_hmm_load_validates_all_metadata_fields` | POS | PASS (verifies all 20 SIDECAR_REQUIRED_KEYS present + typed) |
| 5 | `test_hmm_inference_deterministic_across_loads` | POS | PASS (5× predict_state at 2008-09-15 → identical) |
| 6 | `test_hmm_concurrent_load_safe_no_race` | POS/NEG | PASS (4-thread ThreadPoolExecutor; identical bundles) |
| 7 | `test_hmm_no_auto_train_in_inference_path` | NEG | PASS (no train_and_save_hmm in hmm_states module) |
| 8 | `test_hmm_train_not_in_public_exports` | NEG | PASS (ImportError on `from macro_pipeline.regime import train_and_save_hmm`) |
| 9 | `test_hmm_lock_timeout_raises_HmmConcurrencyError` | NEG | PASS (mock filelock.Timeout → HmmConcurrencyError) |
| 10 | `test_hmm_state_to_label_mapping_deterministic` | POS | PASS (sidecar mapping ≡ pickled mapping) |

**NEG / POS split**: 7 NEG + 3 POS. Spec §2.7 requirement (≥50% negative tests) satisfied.

### §3.2 Adapted existing test

`tests/test_regime_hmm.py::test_hmm_pickle_roundtrip_via_script` (renamed from `test_hmm_pickle_roundtrip_identical`): subprocess-invokes `scripts/train_hmm_v1.py --dry-run` and asserts the would-be sha matches the committed pickle. This is the R5 mitigation from pre-flight, replacing the direct `train_and_save_hmm(...)` call that no longer exists in the package.

### §3.3 Full suite

```
516 passed in 101.14s (0:01:41)
```

506 baseline + 10 new = 516. Zero regressions.

### §3.4 Ruff

```
$ ruff check macro_pipeline/ tests/ scripts/
All checks passed!
```

Per-file ignore added for `tests/test_regime_hmm_frozen.py` (E402, N802) — test names embed exception class names by spec §3.5 (math-notation pattern, same precedent as `signal_probability.py`).

---

## §4 — Empirical findings (smoke-test, per spec §2.3)

3.5A had no spec-mandated calibration; the dry-run check is the only empirical step:

| Measurement | Value | Disposition |
|---|---|---|
| Master pickle sha256 (junction-linked from worktree) | `aa813d167e0e3f591c55cf254b06e1f977e48e1fd158f96845ac7b02791514c5` | Ground truth |
| Regenerated pickle sha256 (via new script, protocol=4) | `aa813d167e0e3f591c55cf254b06e1f977e48e1fd158f96845ac7b02791514c5` | **Byte-equal MATCH** |
| state_to_label_mapping (regenerated) | `{0: 'expansion', 2: 'late-cycle', 1: 'recession'}` | Identical to master |
| nber_overlap_per_state | `{0: 0.0, 1: 0.5, 2: 0.0378}` | Identical to master; recession state (idx=1) has highest overlap as expected |
| feature_mean (regenerated) | `[1.0682, 1.3477, 358393.09, -0.2451, 88.0145]` | Identical to master |
| Concurrent load (4 threads, filelock) | All 4 returned identical TrainedHmm bundles | No race |
| Lock timeout (mocked) | HmmConcurrencyError raised on filelock.Timeout | Correct |

**Implication**: the master pickle was already produced under conditions equivalent to the new locked stack (Python 3.12.10 + hmmlearn 0.3.3 + pickle protocol=4 + seed=42). The regeneration ceremony introduces NO methodology change — it only adds the missing sidecar and gives the artifact provable provenance going forward. **No D20 deviation needed.**

---

## §5 — Test count delta (cumulative + this sub-phase)

| Layer | Test count |
|---|---|
| Layer 3 baseline (`2f5990e`) | 506 |
| Layer 3.5A (`830bcd0`) | **516** (+10) |
| Spec §3 target | +10 ✓ |

---

## §6 — Conviction (3-field, per spec §2.4)

| Sub-phase as a whole | Value | Binding constraint |
|---|---|---|
| `conviction_statistical` | 0.92 | Models / data / proofs all agree: pickle sha-stable, sidecar populated, deterministic inference at the 2008-09-15 anchor. Higher than pre-flight (0.78) because the byte-equal regeneration empirically settled R3+R4. |
| `conviction_operational` | 0.85 | Pickle + sidecar committed, atomic write helper proven, filelock concurrency proven, gates green. Slight haircut: `uv.lock` was deferred to V's master worktree per AM6, so the `pyproject.toml` ↔ `uv.lock` consistency is unsealed until V re-runs `uv lock`. **Binding** of overall confidence. |
| `conviction_actionability` | 0.92 | The committed artifact + script + Gate 12 give Layer 5 a deterministic regime-state foundation it can fit Ridge/CDRS weights against. Codex review can re-run §3.7 proof items mechanically. |
| **Aggregate `confidence_overall` (capped per L1.5 §7.6)** | **0.85** | Operational binding; horizon cap at L3.5A is not analysis-horizon-specific (this is an infra fix). |

### Per-Gate conviction (Gate 12)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | 0.95 | Gate's 10 sub-criteria are all decidable from artifacts on disk (sha, sidecar keys, mapping equality, NBER overlap ordering); each has been independently verified. |
| `conviction_operational` | 0.88 | Gate runs against the canonical pickle + sidecar pair; `uv.lock` deferred reduces operational confidence by ~7pp. |
| `conviction_actionability` | 0.95 | Gate is reproducible by anyone with this branch + python 3.12.10 + hmmlearn 0.3.3. |

---

## §7 — Effort actual vs estimated

| Phase | Estimate (h) | Actual (h) | Notes |
|---|---|---|---|
| Pre-flight | 0.6 | 0.6 | as planned |
| Environment setup (junction) | 0.2 | 0.1 | mklink succeeded once stub data/ removed |
| pyproject filelock + local install | 0.2 | 0.4 | `pip install --target .local-deps` workaround for shared-venv permission lock |
| scripts/train_hmm_v1.py + README | 1.5–2.0 | 1.6 | as planned |
| cache.py write_pickle_atomic_with_meta | 0.5 | 0.3 | small parallel helper; trivial |
| Refactor hmm_states.py | 2.0–2.5 | 1.5 | as planned |
| New exceptions + __init__ exports | 0.5 | 0.3 | as planned |
| Gate 12 + CLI | 0.6 | 0.5 | as planned |
| Tests (10 new + 1 adapt) | 2.0–2.5 | 0.8 | quick because the artifact is correct first-try |
| Full pytest + ruff + gates run | 0.5–1.0 | 0.4 | first run green |
| Verification report | 0.5 | 0.4 | this document |
| **Total** | **9.0–11.0** | **~5.5** | under-budget |

The under-spend is mostly because the regenerated pickle was byte-equal to the master on first try (no D20 ceremony, no methodology iteration).

---

## §8 — Deviations filed (D20+ entries)

**None.** The pre-flight anticipated D20 (regenerate-vs-master divergence) but regeneration was byte-equal, so no deviation entry is needed.

This means D20 remains free for the next genuine deviation (e.g. 3.5B confidence-cap empirical adjustment, if smoke-test diverges from the locked 0.70 default).

---

## §9 — Risks for next sub-phase (3.5B)

| ID | Risk for 3.5B | Mitigation |
|---|---|---|
| R-3.5B-1 | `config.py` SAHMREALTIME entry is a `dict`, not a `SeriesConfig` dataclass. Spec §4.3 assumes the dataclass. Need to either introduce the dataclass + migrate, or extend the existing dict-based pattern. | I will resolve in 3.5B pre-flight. Recommend a small dataclass that wraps existing dict semantics so the migration is contained. |
| R-3.5B-2 | `access.py::PitSeriesReader._load_via_visibility_shift` (lines ~285-321) emits a warning + falls back to latest cache for `needs_vintage=True` series not in vintage panel; this is exactly the silent path 3.5B removes. Must preserve correct PIT semantics for the OTHER series that aren't SAHMREALTIME. | Audit during 3.5B pre-flight: list every `needs_vintage=True` series and confirm disposition (panel vs Option Z vs raise). |
| R-3.5B-3 | SAHM contributes 0.29 of CRPS Path B weight (per HANDOFF §7). The 0.70 cap propagation must reach overall CRPS confidence; smoke-test at the 4 spec anchor dates (1990, 2001, 2008, 2020) before locking the cap. | Per spec §4.2, smoke-test in pre-flight. |
| R-3.5B-4 | Cumulative file-touches to `scoring/cdrs.py` and `scoring/crps.py` will grow across 3.5B + 3.5D + 3.5E. Need disciplined modify-only-relevant-sections per standing-orders cross-sub-phase coordination. | Use line-range-targeted edits; run pytest after each commit. |

---

## §10 — Recommendation

**APPROVE for advance to 3.5B.**

All 12 proof-contract items pass; full test suite green (+10 new, 0 regressions); all 12 gates green; ruff clean; conviction ≥ 0.85 aggregate; no deviations filed. The 3.5A frozen-contract surface is closed.

`uv lock` deferral (AM6) remains the only outstanding operational item; per Decision Lock it is V's responsibility to run in master worktree before push.

Per `HANDOFF_CLAUDE_CODE_v3.md` §2 + standing orders, **PAUSED** awaiting your APPROVE / REVISE-WITH-NOTES / RETURN-FOR-REWORK signal before pre-flight for 3.5B.

---

## §11 — Quick-reference artefacts for review

| Artefact | Path |
|---|---|
| Pre-flight | `LAYER_3_5_3.5A_PREFLIGHT.md` |
| Verification (this) | `LAYER_3_5_3.5A_VERIFICATION.md` |
| Training script | `scripts/train_hmm_v1.py` |
| Script README | `scripts/README.md` |
| Pickle | `data/cache/hmm/regime_3state_v1.pkl` |
| Sidecar | `data/cache/hmm/regime_3state_v1.meta.json` |
| New tests | `tests/test_regime_hmm_frozen.py` |
| Gate 12 implementation | `macro_pipeline/validation.py::validate_gate12_hmm_frozen` |
| Refactored module | `macro_pipeline/regime/hmm_states.py` |
| New exceptions | `macro_pipeline/regime/exceptions.py` (Hmm* classes) |
| New cache helper | `macro_pipeline/cache.py::write_pickle_atomic_with_meta` |

---

**END — LAYER_3_5_3.5A_VERIFICATION.md**
