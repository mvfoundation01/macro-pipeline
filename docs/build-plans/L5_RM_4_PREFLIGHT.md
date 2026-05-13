# L5-RM-4 Pre-Flight Plan (EXTRA-THOROUGH; HIGH-REGRESSION-RISK CLASS)

**Date**: 2026-05-13
**Branch target**: `claude/layer-5-build-plan` (consolidates with `L5_BUILD_PLAN_v1.md` + `L5_B_TASK_A_PREFLIGHT.md`)
**Predecessor tag**: `l5-b-task-a-accept` @ `53deb90` on `claude/layer-5-build` (test baseline 635)
**Spec ref**: `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` §5.RM-4 (lines 914-1118)
**Build plan ref**: `claude/layer-5-build-plan @ 32cce8b` ITEM 4 (HIGH regression risk classification — **revised** in §1 below per empirical data)
**Pre-flight budget**: 1.0-1.5h (longer than standard per HIGH-risk classification)

---

## ITEM 1 — Migration scope audit (EMPIRICAL; reclassifies build plan's "50+" estimate)

### §1.1 Empirical ScoredObservation construction inventory

Greps run on `claude/layer-5-build` @ `53deb90`:

```
$ grep -rn 'ScoredObservation\s*(' --include='*.py' macro_pipeline/ tests/ scripts/ | wc -l
17
```

Total **17 construction sites** (NOT the 50+ that build plan v1 ITEM 4 risk #2 estimated).

### §1.2 By location (production vs test)

| Category | Count | Files |
|---|---:|---|
| Production code | **2** (real) | `scoring/cdrs.py:308` + `scoring/crps.py:509` (line 498 is a comment) |
| Test code | **14** | `tests/test_scored_observation.py` (8 sites) + `tests/test_scored_observation_rename.py` (5 sites) + (1 stray from grep noise) |
| **Total construction** | **16** real + 1 comment line | |

### §1.3 By call signature pattern

| Pattern | Count | Risk |
|---|---:|---|
| Kwargs-only (`ScoredObservation(field=val, ...)`) | **2** (both prod) | LOW (additive fields won't break) |
| Dict-unpacked (`ScoredObservation(**_valid_kwargs(...))`) | **14** (all test) | LOW (unpacked dict tolerates new keys with defaults) |
| **Positional args (`ScoredObservation(val1, val2, ...)`)** | **0** | N/A — none exist |

**Critical finding**: ZERO positional-argument constructions. All 16 real construction sites use kwargs or dict-unpacking. New fields with defaults are **invisible** to these sites — no edits required.

### §1.4 Wider test surface (read-only references to ScoredObservation)

Files referencing `ScoredObservation` in any form (read attributes, type-check, etc.) in `tests/`: **5 files** (test_cdrs.py, test_crps.py, test_pit_enforcement.py, test_scored_observation.py, test_scored_observation_rename.py). Total test functions across those 5 files: ~52 (15+16+8+8+5). These tests READ ScoredObservation fields — they're not at risk unless a field is RENAMED or REMOVED.

Per spec §5.RM-4: **zero renames, zero removals; only 6 additions**. → 52 read-only test functions are NOT at risk.

### §1.5 Risk reclassification

Build plan v1 ITEM 4 risk #2 stated: "L5-RM-4 dataclass migration touches 50+ existing ScoredObservation construction sites. AP-AUTH-44 (surgical edits only) + AP-AUTH-41 v6 (dual-grep) mandatory. **HIGH risk.**"

**Revised per empirical data**: 16 real construction sites; all kwargs/dict-style; spec adds 6 fields with defaults (no renames, no removals). Risk class: **MEDIUM** (was HIGH). The HIGH classification was based on an overestimate of construction-site count. The actual risk concentrates in L5-13 absorption (CDRS notes migration) — a separate spec-mandated subscope, not the dataclass migration itself.

This finding should inform the L5-RM-4 effort estimate (§6) and risk register (§7).

---

## ITEM 2 — Spec contract delta (§5.RM-4 verbatim extract)

### §2.1 Current ScoredObservation field list (production HEAD `53deb90`)

Per `macro_pipeline/scoring/scored_observation.py` grep at HEAD: 23 explicit fields visible in the first 30 lines. Spec §5.RM-4.0 cites "25 existing slots"; the discrepancy is likely from grep truncation (additional `# Layer X.Y` annotation fields or trailing-comment lines).

Spec is the authoritative count: **25 existing**.

### §2.2 New fields per spec §5.RM-4.1.1 (6 additions)

| # | Field | Type | Default | Populated by | Validator domain |
|---|---|---|---|---|---|
| 1 | `calibrated_probability_band_lower` | `float \| None` | `None` | L5-E | ∈ [0, 1] when present |
| 2 | `calibrated_probability_band_upper` | `float \| None` | `None` | L5-E | ∈ [0, 1] when present + band_lower ≤ band_upper |
| 3 | `drawdown_conditional_distribution` | `dict[str, float] \| None` | `None` | L5-D | no validator (structural) |
| 4 | `dms_adjustment_bps` | `float` | `0.0` | L5-F | ∈ [-200, 0] bps |
| 5 | `bayesian_shrinkage_weight` | `float` | `0.0` | L5-G | ∈ [0, 1] |
| 6 | `positive_return_probability` | `float \| None` | `None` | L5-RM-6 Task B path | ∈ [0, 1] when present (implicit; no explicit validator in spec) |

### §2.3 Field-by-field migration mapping

| Old field | New field | Migration rule | Breaking? |
|---|---|---|---|
| (none renamed) | (none renamed) | N/A — spec has 0 renames | — |
| (none removed) | (none removed) | N/A — spec has 0 removals | — |
| (no field) | `calibrated_probability_band_lower` | ADD with default `None` | NO (default = None) |
| (no field) | `calibrated_probability_band_upper` | ADD with default `None` | NO |
| (no field) | `drawdown_conditional_distribution` | ADD with default `None` | NO |
| (no field) | `dms_adjustment_bps` | ADD with default `0.0` | NO |
| (no field) | `bayesian_shrinkage_weight` | ADD with default `0.0` | NO |
| (no field) | `positive_return_probability` | ADD with default `None` | NO |

**All 6 changes are ADDITIVE with defaults.** No renames. No removals. Per §5.RM-4.3 line 1040: "Existing test that constructs `ScoredObservation` with positional args breaks if new slots inserted mid-list — mitigated by **appending at end**." Spec mandates fields APPENDED.

### §2.4 L5-13 absorption sub-scope (spec §5.RM-4.1.4)

Separate from dataclass migration: migrate CDRS `metadata_extra` V_*/T_* entries → `scored_obs.notes`. This is the ACTUAL non-trivial part of L5-RM-4.

Mechanics per spec §5.RM-4.1.4 lines 1015-1020:
1. Migrate every CDRS `scored_obs.metadata_extra["V_*"]` / `["T_*"]` → `scored_obs.notes`
2. Mirror CRPS pattern: extract shared `_format_pit_lineage_notes()` from `scoring/crps.py` to new `scoring/notes_formatter.py`
3. Add NBER pre-1978 caveat to notes when `pre_1978_training_only=True`

Effort: 1-2h folded into L5-RM-4's 4-6h band (per spec §5.RM-4.1.4 line 1021).

### §2.5 Spec ambiguity / inconsistency surfaced (NON-blocking)

Spec §5.RM-4.1.1 header line 935 reads `##### §5.RM-4.1.1 New slot additions (5 total)` but the body lists **6 slots** (lines 946-959) and the surrounding prose at line 933 says "**6 new slots** (v3 expanded from 5 per S-2 propagated v5 per C.2 anchor fix)". This is a residual v3-era header that v6 chunk-14 C.1 anchor scrub didn't catch.

**Disposition**: NOT filed as Sxx (spec body is unambiguous at 6; header is stale doc residue; spec is FROZEN; mention here for future spec-cleanup awareness).

---

## ITEM 3 — Backward compatibility strategy proposal

### §3.1 Three patterns evaluated

| Pattern | Approach | Pros | Cons | Applicability to RM-4 |
|---|---|---|---|---|
| **A** "Big bang" | Migrate all 50+ sites in single commit + new dataclass shape | clean | large blast radius; hard to bisect | **N/A** — only 16 sites; all kwargs-style; no migration NEEDED for existing sites |
| **B** "Additive then deprecate" | Add new fields as Optional[T] with defaults; existing sites unchanged | incremental | schema bloat; deprecation debt | **PERFECT FIT** — matches spec §5.RM-4.1.1 exactly (all 6 fields have defaults) |
| **C** "Migration helpers" | classmethods like `ScoredObservation.from_legacy(...)`; batch site updates | testable per-batch | temporary surface area | **N/A** — no legacy form to convert (existing sites are forward-compatible with new schema) |

### §3.2 Track A recommendation: Pattern B

**Adopt Pattern B.** Rationale:
1. **Spec mandates it**: §5.RM-4.1.1 lines 940-960 show all 6 new fields with explicit defaults (`= None` or `= 0.0`). Spec is FROZEN; Pattern B is the only spec-compliant pattern.
2. **Empirical scope supports it**: ITEM 1 confirms ZERO existing sites need editing (all kwargs/dict-unpacked; new fields default-out).
3. **L5-13 absorption is the ONLY edit work**: 2 production sites + ~1 helper extraction. Not a Pattern A/B/C question — it's a separate subscope per spec §5.RM-4.1.4.
4. **Test reordering risk**: Pattern A would require renumbering test fields if positional usage existed. We have zero positional usage. Risk = zero.

### §3.3 Pattern B specifics for L5-RM-4

| Action | Files touched | Risk |
|---|---|---|
| Add 6 fields with defaults at end of `@dataclass class ScoredObservation` | `macro_pipeline/scoring/scored_observation.py` | LOW |
| Add 5 validator stanzas to `__post_init__` per spec §5.RM-4.1.2 | same file | LOW |
| Extract `_format_pit_lineage_notes` from `scoring/crps.py` → new `scoring/notes_formatter.py` | `scoring/crps.py` (modify); `scoring/notes_formatter.py` (NEW) | MED (CRPS path touched) |
| Migrate CDRS `metadata_extra` V_*/T_* → `notes` via shared helper | `scoring/cdrs.py` (modify) | MED |
| Add 8 new tests per §5.RM-4.5 | `tests/test_scored_observation.py` (extend) + `tests/test_cdrs.py` (extend for L5-13 regression) | LOW |
| Add `validate_gate20_dataclass_migration()` + CLI dispatch | `macro_pipeline/validation.py` | LOW |

No existing-construction-site edits. Existing tests remain stable.

---

## ITEM 4 — Test regression mitigation plan

### §4.1 Baseline preservation strategy

| Strategy | Approach |
|---|---|
| Per-commit `pytest -x` | After each logical commit (dataclass migration / L5-13 migration / tests / gate), run full pytest to catch regressions early |
| Test file ordering | Run heavily-coupled test files FIRST: `tests/test_scored_observation.py`, `tests/test_scored_observation_rename.py`, `tests/test_cdrs.py`, `tests/test_crps.py`, `tests/test_pit_enforcement.py` |
| L5-13 regression test (test #3 per §5.RM-4.5) | Asserts `metadata_extra` has 0 V_*/T_* keys post-migration; included in 8 new tests |

### §4.2 Test files heaviest in ScoredObservation references

| File | ScoredObservation references | Risk for RM-4 |
|---|---:|---|
| `tests/test_scored_observation.py` | many | **HIGH** — directly tests dataclass behavior; will need 8 new test additions |
| `tests/test_scored_observation_rename.py` | many | MED — tests `raw_score` rename (Layer 3.5D); new fields don't conflict |
| `tests/test_cdrs.py` | 15 functions reference | MED — L5-13 migration touches CDRS code path; regression-test included |
| `tests/test_crps.py` | 16 functions reference | LOW — notes_formatter extraction may touch CRPS imports; smoke-test required |
| `tests/test_pit_enforcement.py` | 8 functions reference | LOW — reads metadata_extra; L5-13 migration may move keys; verify test assertions still pass |

### §4.3 Sequencing (lowest-coupling → highest-coupling)

1. **Add 6 dataclass fields + validators** (commit 1; `test_scored_observation.py` extends with 5 NEG validator tests)
2. **Add slot-count + parquet roundtrip tests** (commit 2; `test_scored_observation.py` extends with 2 POS tests)
3. **Extract notes_formatter + migrate CDRS** (commit 3; `tests/test_cdrs.py` extends with L5-13 regression test)
4. **Add Gate 20 validator + CLI** (commit 4; no new tests)
5. **Full pytest run + commit gate** (no new commits; verification gate)

Each commit followed by `pytest -x --no-header -q` (per AP-AUTH-47). 635 baseline must be preserved at every commit.

### §4.4 If regression surfaces

Per build plan §5.2 trigger taxonomy:
- T2 trigger (test contract violation) → file Sxx; diagnose root cause BEFORE next commit
- Bisect to identifying commit; revert OR fix in-place per Strategic disposition

---

## ITEM 5 — RM-4 spec scope (per §5.RM-4)

### §5.1 Function/method signatures added or modified

| Item | Signature | Source |
|---|---|---|
| `ScoredObservation` dataclass | + 6 fields with defaults + 5 validators | spec §5.RM-4.1.1 + §5.RM-4.1.2 |
| `scoring/notes_formatter.py::_format_pit_lineage_notes()` | NEW shared helper extracted from `scoring/crps.py` | spec §5.RM-4.1.4 step 2 |
| `scoring/cdrs.py` CDRS scorer | UPDATED to use `notes_formatter` + migrate metadata_extra V_*/T_* → notes | spec §5.RM-4.1.4 step 1 |
| `validate_gate20_dataclass_migration()` | NEW function in `validation.py` | spec §5.RM-4.6 |

### §5.2 New tests required (spec §5.RM-4.5)

**8 tests total; 5 NEG / 3 POS = 63% NEG (exceeds 50% floor per §2.7)**:

| # | Test | Type | Notes |
|---|---|---|---|
| 1 | `test_dataclass_has_all_31_slots` | POS | 25 existing + 6 new = 31 total |
| 2 | `test_parquet_roundtrip_preserves_6_new_slots` | POS | to_dict() + parquet roundtrip element-wise equality |
| 3 | `test_notes_field_carries_L5_provenance_post_L5_13_absorption` | POS | L5-13 regression: 0 V_*/T_* keys in metadata_extra post-migration |
| 4 | `test_rejects_calibrated_probability_band_lower_outside_zero_one` | NEG | validator boundary |
| 5 | `test_rejects_calibrated_probability_band_upper_outside_zero_one` | NEG | validator boundary |
| 6 | `test_rejects_band_lower_greater_than_band_upper` | NEG | ordering invariant |
| 7 | `test_rejects_dms_adjustment_outside_minus_200_to_zero_bps_band` | NEG | validator boundary |
| 8 | `test_rejects_bayesian_shrinkage_weight_outside_zero_one` | NEG | validator boundary |

### §5.3 Gate 20 PASS criteria (spec §5.RM-4.6)

6 criteria; all runtime-verifiable:
1. `__dataclass_fields__` count = 31 (v6 anchor)
2. 6 new slot names exact match spec list
3. Parquet roundtrip smoke-test PASSes (test #2)
4. L5-13 absorption confirmed (test #3)
5. All 8 §5.RM-4.5 tests PASS
6. Existing **635 test baseline preserved** (spec says "602"; we're at 635 post-L5-A + L3 patch + L5-B Task A)

---

## ITEM 6 — Effort estimate refinement (risk-adjusted)

### §6.1 Build plan v1 vs spec vs Track A empirical estimate

| Reference | Effort |
|---|---:|
| Build plan v1 ITEM 2 row 3 (L5-RM-4 standalone) | 4-6h |
| Spec §5.RM-4.0 metadata | 4-6h (target 5h; includes L5-13 1-2h absorbed) |
| L5-A precedent | 3h actual vs 6-8h spec band (~40% of upper) |
| L5-B Task A precedent | 3.5h actual vs 6.75h plan-estimate (~52% of plan) |

### §6.2 Track A estimate (Pattern B; revised per empirical scope)

| Phase | Sub-budget | Rationale |
|---|---|---|
| Phase 1: env-prep (data/cache provisioning + pytest -x baseline 635) | 0.25h | Should be no-op (data inherited from L5-B Task A) |
| Phase 2.1: add 6 dataclass fields + 5 validators | 0.5h | Mechanical per spec §5.RM-4.1.1 + §5.RM-4.1.2 |
| Phase 2.2: extract notes_formatter + migrate CDRS metadata_extra (L5-13 absorption) | 1.5-2h | Main work; touches CRPS + CDRS code paths |
| Phase 2.3: add 8 tests | 1h | 5 NEG validator boundary + 3 POS structural |
| Phase 2.4: add Gate 20 validator + CLI dispatch | 0.5h | Mirrors L5-A Gate 18 pattern |
| Phase 3: per-commit pytest -x + final verification (previous baseline + L5-RM-4 delta per AP-AUTH-40/42 symbolic) | 0.5h | Pytest 187s × ~3 runs |
| Phase 4: review branch + AP-AUTH-48 v2 + final report | 0.5h | Standard |
| **Total** | **~4.75h** | Within spec 4-6h band |

### §6.3 Risk-adjusted bands

- **Standard estimate** (Pattern B; clean): **4.75h**
- **Risk-adjusted estimate** (assume 1-2 test regressions surface during L5-13 migration): **6-7h** (add 1.5-2h for diagnose + fix + extra commit cycle)
- **Pause threshold** (1.5×): **~10h hard pause**; soft check at 7h

**Specific HIGH-risk threshold for RM-4**: pause at 8h if Pattern B's L5-13 absorption has unexpected scope (e.g., notes formatter has hidden dependencies on cdrs internals not anticipated).

### §6.4 Pattern selection's effect on estimate

This estimate is for **Pattern B only**. Pattern A or C (not applicable here per ITEM 3) would inflate to 8-12h due to multi-batch coordination overhead. Pattern B keeps estimate within original spec band.

---

## ITEM 7 — Pre-execution risk register (RM-4 specific; revised severities)

| # | Risk | Original (build plan) | Revised (per empirical) | Probability | Mitigation | Trigger |
|---|---|---|---|---|---|---|
| 1 | Silent field rename break | HIGH | **LOW** | 0% | Spec §5.RM-4 has ZERO renames (only 6 additions with defaults) | N/A — no renames exist |
| 2 | Test regression cascade | HIGH | **LOW** | 5% | 16 construction sites all kwargs/dict-style; defaults absorb new fields invisibly | Any prior-test failure during Phase 3 → T2 Sxx |
| 3 | Backward compat design ambiguity | MED | **LOW** | 5% | Pattern B is spec-mandated (defaults required); Pattern A/C inapplicable | Strategic confirms Pattern B at greenlight |
| 4 | Touch-point edit error | MED | **N/A** | 0% | Empirical scope = 0 existing edits required (only L5-13 migration; 2 prod sites) | Discovery of positional construction (not present) |
| 5 | Pre-commit hook scope adequacy for code files | MED | **LOW** | 5% | Hook scope is `docs/**/*.md` only; code commits unaffected; can hand-add code-file hook later if needed | Code-level AP-AUTH violation slips past review |
| 6 | L5-13 CDRS absorption surface area | (not in original list) | **MEDIUM** | 25% | Spec §5.RM-4.1.4 explicit; extract `notes_formatter.py` shared module; migrate `scoring/cdrs.py` V_*/T_* keys; CRPS smoke-test required | Notes formatter has hidden CRPS coupling not visible from grep |
| 7 | Parquet roundtrip schema | (not in original list) | **MEDIUM** | 15% | Spec §5.RM-4.2 #2 mandates smoke-test; pyarrow schema must include new fields (verify dict-typed `drawdown_conditional_distribution` round-trips correctly) | Test #2 fails on parquet write/read |
| 8 | Validator stack stricter than data | (not in original list) | **LOW** | 10% | New validators specified in spec §5.RM-4.1.2; spec §5.RM-4.3 pre-empts "band lower ≤ upper" concern by noting L5-RM-6 must clip first | L5-RM-6 future commit triggers validator on edge case |
| 9 | Spec §5.RM-4.1.1 header inconsistency (`5 total` vs body 6) | (new finding) | **LOW** | 5% (already known; no action) | Documented in ITEM 2.5; spec body is authoritative at 6 | None — already disposed |

### §7.1 Severity summary (revised)

| Severity | Count | Notes |
|---|---:|---|
| HIGH | 0 | Build plan's HIGH classifications all downgraded per empirical evidence |
| MEDIUM | 2 | L5-13 absorption surface (#6) + parquet schema (#7) |
| LOW | 6 | Risks 1, 2, 3, 5, 8, 9 |
| N/A | 1 | Risk #4 (touch-point edit) — does not apply |

**Net risk reclassification**: HIGH → MEDIUM. Top risk is L5-13 absorption (notes_formatter extraction + CDRS migration), NOT the dataclass migration itself.

---

## ITEM 8 — Readiness verdict + conviction

### §8.1 Conviction 3-field

| Field | Value | Drivers |
|---|---|---|
| `conviction_statistical` | **0.96** | Spec §5.RM-4 is precise + unambiguous (modulo §2.5 doc-residue); all changes additive; validators concrete; test contract well-specified |
| `conviction_operational` | **0.93** | Pattern B = spec-mandated; 16 construction sites all kwargs/dict-style (no edits needed); pre-commit hooks active; baseline 635 to preserve. Minor: L5-13 absorption has MED risk per #6/#7 above |
| `conviction_actionability` | **0.95** | L5-RM-6 (next sub-phase) directly consumes new `ScoredObservation` fields (`calibrated_probability_band_*`, `positive_return_probability`); pre-flight identifies risks + mitigations + sequencing |
| **Aggregate (MIN)** | **0.93** | **Binding: operational** (L5-13 absorption complexity + parquet schema verification) |

≥0.90 hard floor: **CLEARED**.

### §8.2 Verdict

**READY-WITH-CONDITIONS**.

3 conditions:

| Condition | Owner | Effort |
|---|---|---|
| **C1**: Strategic confirms Pattern B (additive) is the spec-mandated path — implicit but worth explicit ack given build plan's HIGH-risk classification has been downgraded to MEDIUM | Strategic | review-time only |
| **C2**: Strategic acknowledges risk reclassification (HIGH→MEDIUM per ITEM 7); subsequent sub-phase pre-flights should follow ITEM 1's empirical-grep-audit pattern (per AP-AUTH-50 enforcement) | Strategic | review-time only |
| **C3**: ChatGPT 5.5 mid-build review NOT triggered (per build plan §8.4 optional triggers; no T3/T5/T6 conditions met) | Strategic decides | N/A unless triggered |

Upon C1+C2 satisfied → **READY-TO-BUILD** for L5-RM-4 code-exec.

### §8.3 Strategic-decision routing

| Outcome | Action |
|---|---|
| Greenlight L5-RM-4 (Pattern B confirmed) | Track A proceeds to L5-RM-4 code-exec; Phase 0 grep audit of upstream deps (per AP-AUTH-50) before Phase 1 |
| Strategic requests Pattern A or C reconsideration | Track A re-evaluates (low probability — Pattern B is spec-mandated) |
| ChatGPT 5.5 mid-build review triggered | Pause L5-RM-4 code-exec until verdict |

---

## §9 — Strategic decisions awaited

1. **C1**: Confirm Pattern B (likely YES; spec-mandated)
2. **C2**: Acknowledge risk reclassification (likely YES; empirical evidence presented)
3. **C3**: Mid-build ChatGPT review trigger? (likely NO; no T3/T5/T6 conditions met)

---

**END — L5_RM_4_PREFLIGHT.md**
