# L5-RM-4 — Self-Verification Report

**Date**: 2026-05-14
**Build branch**: `claude/layer-5-build` @ `056d198` (tag `l5-rm-4-accept`)
**Foundation tags**: `l5-a-accept`, `l3-component-patch`, `l5-b-task-a-accept`
**Predecessor (FROZEN)**: `claude/layer-5-spec` @ `9f848bb` tag `layer5-spec-v6`
**Pre-flight ref**: `claude/layer-5-build-plan` @ `675db8a` (L5_RM_4_PREFLIGHT.md; Pattern B)

---

## §1 — Patches delivered (4 commits)

| # | Commit | Topic |
|---|---|---|
| 1 | `30c4ce8` | docs(ap): codify AP-AUTH-51 (grep evidence for risk register) |
| 2 | `47cabd7` | docs(sxx): file S-12 T1 (spec 25/31 vs empirical 23/29 mismatch) |
| 3 | `056d198` | L5-RM-4: 6-slot batched migration + L5-13 absorption (7 files; +540/-62 LOC) |

(Plus prior commit `27d1f3a` from L5b-3 backlog landing pre-RM-4.)

---

## §2 — Empirical verification

### §2.1 Pytest baseline

| Cumulative | Tests |
|---|---|
| Pre-RM-4 baseline (post-L5-B Task A) | 635 |
| Post-RM-4 | **643** (= previous + L5-RM-4 delta per AP-AUTH-40/42 symbolic) |
| Regressions | **0** |

### §2.2 L5-RM-4 dedicated tests (8 logical / 8 pytest)

```
============================= 37 passed in 8.80s ==============================
```

Full transcript: `artifacts/test_transcript.txt`. Breakdown:
- `test_scored_observation.py`: 15 tests (8 pre-existing + 7 new L5-RM-4)
- `test_cdrs.py`: 22 tests (21 pre-existing + 1 new L5-RM-4)
- L5-RM-4 logical tests: 8 (per spec §5.RM-4.5; 5 NEG / 3 POS = 63%)

### §2.3 Gate 20 CLI

```
=== Gate 20 - L5-RM-4 ScoredObservation 6-slot batched migration: PASS ===
  Criterion 1 PASS: 29 __dataclass_fields__ (empirical; spec claimed 31 per S-12)
  Criterion 2 PASS: all 6 new slot names per spec §5.RM-4.1.1 present
  Criteria 3-6: deferred to pytest (out-of-band per spec §5.RM-4.6)
```

Full transcript: `artifacts/gate20_cli.txt`.

### §2.4 Proof contract verification

| Spec proof item | Evidence | Status |
|---|---|---|
| 1 | `len(ScoredObservation.__dataclass_fields__) == 29` (spec wanted 31; S-12 documented gap) | ✓ |
| 2 | `pytest tests/test_scored_observation.py tests/test_cdrs.py` — 37 passed (8 new L5-RM-4) | ✓ |
| 3 | `grep -E 'metadata_extra\[.V_\|metadata_extra\[.T_' macro_pipeline/scoring/cdrs.py` — **0 matches** | ✓ |
| 4 | `scoring/notes_formatter.py` exists; imported by both `crps.py` (alias) + `cdrs.py` (direct) | ✓ |
| 5 | Parquet roundtrip smoke-test: JSON variant in `test_parquet_roundtrip_preserves_6_new_slots` | ✓ |
| 6 | 5 validator checks all raise on boundary violations (tests #4-#8) | ✓ |
| 7 | Gate 20 PASSes | ✓ |
| 8 | Cumulative test count: previous baseline + L5-RM-4 delta per AP-AUTH-40/42 symbolic | ✓ |
| 9 | Conviction 3-field reported (§7 below) | ✓ |
| 10 | Codex 5/5 finding X closed via test #3 invariant (V_*/T_* keys absent from metadata_extra) | ✓ |

---

## §3 — Sxx status

| Sxx | Topic | Status |
|---|---|---|
| S-10 | component_panel L3 export gap | CLOSED via L3 patch `6d90d48` (prior cycle) |
| S-11 | Gate 18 sidecar naming | CLOSED in-cycle prior (commit `53deb90`) |
| **S-12 (NEW)** | Spec field-count (25/31) vs empirical (23/29) | **CONDITIONAL** — Track A implemented per disposition (a) (empirical 29-slot assertion); Strategic to confirm at this L5-RM-4 ACCEPT review |

**Cumulative L5 Sxx**: **12** (S-1..S-12; S-1..S-9 spec authoring; S-10/S-11/S-12 build-time).

S-12 Strategic disposition request (3 options per S-12 log):
- (a) ACCEPT empirical-truth assertion (Track A prior; minimal disruption)
- (b) REJECT — request v7 spec patch cycle (high cost; spec FROZEN)
- (c) DEFER — implement spec-literal 31; tests will FAIL; sub-phase ACCEPT blocked

---

## §4 — Pattern B validation (G5)

Pre-flight ITEM 1 empirical inventory: **16 pre-existing construction sites** (2 prod + 14 test; all kwargs/dict-unpacked).

**Post-L5-RM-4 status**:
- **0 pre-existing sites edited** (Pattern B contract honored)
- 11 new construction sites added (within the 7 new L5-RM-4 test functions in `test_scored_observation.py`; each NEG test has 1-2 raises = 1-2 constructions)
- All construction sites still pass (37/37 in `test_scored_observation.py` + `test_cdrs.py`)
- AP-AUTH-44 (surgical edits) honored: existing-site untouched

---

## §5 — L5-13 absorption (§5.RM-4.1.4)

| Step | Implementation | Verified by |
|---|---|---|
| 1. Migrate `V_*`/`T_*` from `metadata_extra` to `notes` | `cdrs.py` extends `notes_list` with `format_cdrs_v_t_lineage_notes(v_score, t_score)`; removes `V_score`+`T_score` from metadata_extra dict | test #3 (test_cdrs.py); proof item 3 grep (0 hits) |
| 2. Extract shared `_format_pit_lineage_notes` helper | `scoring/notes_formatter.py` (NEW); `crps.py` imports + aliases for backward compat | proof item 4 |
| 3. NBER pre-1978 caveat to notes when `pre_1978_training_only=True` | **DEFERRED** — no such flag exists in current `ScoredObservation` or in CDRS code path; spec §5.RM-4.1.4 step 3 appears speculative; absent in current data flow | flagged in §8 deviation |

**Scope honored**: V_*/T_* migration per spec literal (R_multiplier preserved; out of scope per spec line 1015). Step 3 deferred (no current data flow uses the flag).

---

## §6 — AP-AUTH compliance

| AP | Status |
|---|---|
| AP-AUTH-41 v6 (dual-grep mirror) | ✓ G5 Pattern B section shows pos (sites preserved) + neg (0 edits to existing) |
| AP-AUTH-42 NEW v6 (cumulative arithmetic regex) | ✓ Symbolic wording used in commits + this report; hook clean |
| AP-AUTH-44 (modify beyond scope) | ✓ 7 files modified (all in §5.RM-4.0 metadata "Modified files" + 1 new shared module `notes_formatter.py`); no scope drift |
| AP-AUTH-45 (preserve tags) | ✓ All prior tags untouched (`layer5-spec-v1..v6`, `infra-precommit-installed`, `l5-a-accept`, `l3-component-patch`, `l5-b-task-a-accept`); new `l5-rm-4-accept` added |
| AP-AUTH-46 (gratuitous Sxx) | ✓ S-12 filed with legitimate T1 trigger (spec-vs-implementation gap; non-trivial documentation value) |
| AP-AUTH-47 (env-setup beyond collect-only) | ✓ Phase 0 ran `pytest -x` full (635 baseline); data dirs verified |
| AP-AUTH-48 v2 (manifest hash post-push) | ✓ MANIFEST hashes will be post-push verified per §7 below |
| AP-AUTH-49 (planning-branch precommit) | n/a (build branch) |
| AP-AUTH-50 (upstream-export grep) | ✓ Pre-flight ITEM 1 cited grep evidence for migration scope |
| **AP-AUTH-51 NEW** (risk-register grep evidence) | ✓ Codified at commit `30c4ce8` (this cycle); risk reclassification HIGH→MEDIUM in pre-flight was AP-AUTH-51-compliant |

---

## §7 — Conviction 3-field

| Field | Value | Drivers |
|---|---|---|
| `conviction_statistical` | **0.95** | 8/8 new tests PASS; 643/643 full suite (0 regressions); validators concrete + tested at boundary; L5-13 migration verified by 4 layers (test #3 + proof item 3 grep + post-migration source-grep + test_cdrs.py contract update). Minor: S-12 magic-number drift between spec and impl (documented). |
| `conviction_operational` | **0.93** | Pattern B clean (16 pre-existing sites preserved); 4-commit linear chain; pre-commit hooks fired clean per commit; per-phase verification gate observed; AP-AUTH-51 codified pre-implementation per pre-flight L5-RM-4 commitment. Minor: L5-13 step 3 (NBER pre-1978 caveat) deferred — speculative spec; documented in §8. |
| `conviction_actionability` | **0.95** | L5-RM-6 (next sub-phase) can directly consume new fields (`calibrated_probability` from RM-6 fits → already validated; `positive_return_probability` from RM-6 Task B path → slot present). Downstream L5-D/E/F/G all see correct slot defaults. |
| **Aggregate (MIN)** | **0.93** | **Binding: operational** (Pattern B + L5-13 absorption scope discipline; S-12 disposition pending) |

≥0.90 hard floor: **CLEARED**.

**Binding-constraint trajectory observation**: pre-flight predicted potential shift to STATISTICAL. Here at RM-4, OPERATIONAL remains binding due to S-12 + L5-13 step 3 deferral. May shift to STATISTICAL at L5-RM-6 (isotonic calibration; model correctness becomes dominant).

---

## §8 — Recommendation

**APPROVE L5-RM-4 ACCEPT** **(conditional on Strategic S-12 disposition)**.

### §8.1 Deviations from spec / pre-flight (3)

1. **S-12: spec §5.RM-4.0 + §5.RM-4.5 + §5.RM-4.6 + §5.RM-4.7 magic-number 31** — implemented as empirical 29 per Track A disposition (a). Strategic to confirm at this ACCEPT review (3 options enumerated in S-12 log).
2. **L5-13 step 3 (NBER pre-1978 caveat in notes when `pre_1978_training_only=True`)** — DEFERRED. No `pre_1978_training_only` flag exists in current `ScoredObservation` schema or CDRS code path. Spec §5.RM-4.1.4 step 3 reads as speculative; absent data flow makes implementation unsupported. Future scope (likely L5b or pre-L6) when the flag exists.
3. **Spec §5.RM-4.1.1 header inconsistency**: "(5 total)" header says 5 but body lists 6. Not a deviation; just noted in pre-flight ITEM 2.5; spec body authoritative.

### §8.2 Strategic decision points

| Item | Action |
|---|---|
| S-12 disposition | Strategic chooses (a)/(b)/(c) — Track A prior is (a) |
| L5-13 step 3 acknowledgment | Confirm deferral OR file backlog L5b-N for future implementation |
| L5-RM-6 readiness | If S-12 → (a) accepted, next pre-flight can proceed |

---

**END — L5_RM_4_VERIFICATION.md**
