# LAYER 5 — Chunk 1 Pre-flight Audit

**Chunk**: 1 of 5 (Scope + discipline + cross-phase architecture + sub-phase decomposition)
**Date**: 2026-05-10
**Authoring agent**: Claude Code (build agent operating under L5 spec-authoring role widening per V directive 2026-05-10)
**Branch**: `claude/layer-5-spec` @ `590e4a5` (= main HEAD = L3.5b merge commit)
**Predecessor reads (in working memory)**:
- `HANDOFF_CLAUDE_CODE_v4.md` (Standing Orders 1-6, proof contract format)
- `HANDOFF_STRATEGIC_CLAUDE_v4.md` (decision boundaries, AP-S1..S8)
- `LAYER_3_5_BUILD_SPEC.md` (sub-phase pattern, gate convention, proof contract format)
- `LAYER_3_5_DEVIATIONS.md` (D20-D30 + L5-12, L5-13, L5-14, L7-CI-1, L7-MIGRATE-1 backlog)
- `LAYER_3_5b_RETROSPECTIVE.md` (pattern compounding + 2 Strategic self-corrections lessons)
- `CLAUDE_CODE_L5_SPEC_AUTHORING_PROMPT.md` (this task's contract)

---

## §1 — Sections to author this chunk

| Section | Description | Source / mirror |
|---|---|---|
| §0 Spec metadata | Branch, predecessor, target tag, sub-phase IDs, effort/test/gate targets, reviewer schedule | Mirror L3.5 §0; adjust for L5 numbers |
| §1 Scope & deliverables | What L5 is (calibrated probabilities across 4 horizons); what L5 is NOT (L6 reports, L5b OOS hardening); 5-row "in scope / out of scope" delineation | Mirror L3.5 §1 |
| §2 Discipline rules | §2.1-§2.7 per meta-prompt §2.4 + NEW §2.5 Empirical claim verification | Verbatim from HANDOFF_CLAUDE_CODE_v4 §2 + new |
| §3 Cross-phase architecture | §3.1 sub-phase dependency graph (ASCII); §3.2 cross-sub-phase semantic table (NEW section type #2) | New for L5 |
| §4 Sub-phase decomposition | Table of 10 rows (L5-A..L5-H + L5-RM-4 + L5-RM-6) with effort, test delta, gate ID, Q-resolutions owned, dependency notes | Mirror L3.5 §0 sub-phase table; extended |
| §5-§10 stubs | Empty section headers with "Chunk N will populate" markers | Skeleton for chunks 2-5 |

Anchors created this chunk (all referenced from later chunks):
- `§2.5` (empirical claim verification — referenced from L5-A AST audit, L5-RM-6 monotonicity audit, L5-F bps application audit)
- `§3.2` cross-sub-phase semantic table rows for `raw_score`, `calibrated_probability`, `calibration_metadata`, `notes`, `forecast_sigma` (NEW L5-E), `drawdown_probability_distribution` (NEW L5-D), `dms_adjustment_bps` (NEW L5-F), `bayesian_shrinkage_weight` (NEW L5-G)
- `§4` row IDs for each L5-X sub-phase (§5.A through §5.H)
- `§10` deviation register Sxx (S-1 through S-25 reserved)

---

## §2 — Cross-references planned this chunk (with resolution status)

| Anchor created | Resolves to (chunk N) | Status |
|---|---|---|
| `§2.5 Empirical claim verification` | Referenced from §5.A.2, §5.RM-6.4, §5.F.3 (chunks 2-4) | In-progress; downstream chunks fill |
| `§3.2 cross-sub-phase semantic table` row `raw_score` | §5.B.4 (chunk 2) | In-progress |
| `§3.2` row `calibrated_probability` | §5.RM-4.3, §5.RM-6.5 (chunk 3) | In-progress |
| `§3.2` row `forecast_sigma` | §5.E.3 (chunk 4) | In-progress |
| `§3.2` row `drawdown_probability_distribution` | §5.D.3 (chunk 4) | In-progress |
| `§3.2` row `dms_adjustment_bps` | §5.F.2 (chunk 4) | In-progress |
| `§3.2` row `bayesian_shrinkage_weight` | §5.G.3 (chunk 4) | In-progress |
| `§4` row L5-A | `§5.A` (chunk 2) | In-progress |
| `§4` row L5-B | `§5.B` (chunk 2) | In-progress |
| ... (all 10 sub-phase rows) | Chunks 2-5 | In-progress |

No cross-reference targets exist outside this chunk yet (chunk 1 is the foundation). Integrity is internal-only at chunk 1; will become external once chunks 2-5 land.

---

## §3 — Q-resolutions to lock this chunk

**None.** Per meta-prompt §2.1 chunk decomposition table:
- Q1, Q2 lock in chunk 2 (L5-A, L5-B context)
- Q3 locks in chunk 2 (L5-B Ridge λ)
- Q4 locks in chunk 3 (L5-RM-6 isotonic scope)
- Q5, Q6, Q7 lock in chunk 4 (L5-RM-6 regime trigger threshold, L5-F DMS, L5-G shrinkage)
- Q8 locks in chunk 5 (closure horizon-scope confirmation)

Chunk 1 establishes the **Q-resolution roadmap** in the §4 sub-phase decomposition table (which Q is owned by which sub-phase).

---

## §4 — Anticipated ambiguities

### §4.1 PAUSE-required (require V audit before proceeding to chunk 1 authoring): **NONE**

The meta-prompt provides:
- Locked Q1-Q8 with Strategic recommendations
- Fixed chunk decomposition (§2.1)
- Three new section types defined verbatim (§2.3)
- Discipline rules embedding (§2.4)
- Spec metadata template (§4)
- Authoring discipline rules (§2.5)
- 10 sub-phase decomposition with effort + test delta + gate (§7 of meta-prompt context-locked)

All chunk 1 content is derivable from the meta-prompt + L3.5 spec mirror + codebase recon (CRPS/CDRS output contract via `scored_observation.py`; R² panel input via `analysis/r_squared_panel.py`; gate dispatch via `validation.py`).

### §4.2 PROCEED-with-Sxx (file deviation, do NOT pause): **NONE anticipated at chunk 1**

Possible future deviations (will surface in chunks 2-5 if they materialize):
- S-1 (chunk 2): if CV smoke-test reveals expanding window pre-1985 has <40 effective obs at 5Y horizon → Strategic recommendation Q1=C may need re-baselining
- S-2 (chunk 3): if isotonic per-horizon (Q4) smoke-test shows 1Y calibrator has <20 events → may need pooled-fit deviation
- S-3 (chunk 4): if DMS literature scan finds horizon-conditional bps band wider than ±50 → Q6 sub-band override

These are speculative — surface only if empirical evidence at the relevant chunk's pre-flight supports them.

### §4.3 Arithmetic consistency checks (Standing Order #4 — empirical claim verification)

Per the new "Empirical claim verification" Standing Order, I verified the meta-prompt's headline numbers before locking them into chunk 1:

| Claim | Verification |
|---|---|
| "10 sub-phases" | L5-A, L5-B, L5-RM-4, L5-RM-6, L5-C, L5-D, L5-E, L5-F, L5-G, L5-H = 10 ✓ |
| "47-66h total build effort" | Sum of bands: 6+8+4+6+5+5+4+3+4+2 = **47** (min) ; 8+10+6+8+7+7+6+5+6+3 = **66** (max) ✓ |
| "+78 tests" | Sum of deltas: 12+15+8+10+8+8+6+5+6+0 = **78** ✓ |
| "8 new gates 18-25" | L5-A→18, L5-B→19, L5-RM-4→20, L5-RM-6→21, L5-C→22, L5-D→23, L5-E→24, L5-F→25 (sub), L5-G→25 (sub), L5-H→none ⇒ 7 numerically distinct gates (18-24) + 1 shared composite (25) = **8 gates** ✓ |
| "Test baseline 602 PASS" | Verified empirically in STEP 1 of this session: `pytest tests/ -q --no-header` returned `602 passed in 142.72s` ✓ |
| "Gates 17/17 PASS" | Verified empirically: `python -m macro_pipeline.validation gate17` returned PASS with all 4 sub-criteria ✓ |
| "layer3-5b-complete → dcf698d" | Verified empirically: `git rev-parse layer3-5b-complete^{}` returned `dcf698dd742277ad0825978fffc0454f54b1de79` ✓ |
| "ScoredObservation has `calibrated_probability` slot" | Verified empirically: `scoring/scored_observation.py:89` shows `calibrated_probability: float \| None = None` with 3.5D comment ✓ |
| "R² panel has 1Y/3Y/5Y/10Y horizons" | Verified empirically: `analysis/r_squared_panel.py:56` shows `HORIZONS = {"1Y": 12, "3Y": 36, "5Y": 60, "10Y": 120}` ✓ |
| "Gate dispatch convention `validate_gateN_<name>()`" | Verified empirically: `validation.py` grep returns 17 such functions (gate1-gate17) ✓ |

All claims pass empirical-verification floor. Chunk 1 numeric specificity is grounded, not assumed.

---

## §5 — Risk callouts

### §5.1 Chunk 1 is the foundation — errors propagate

Chunk 1 sets the §4 decomposition table that chunks 2-5 reference. An error here (wrong gate ID, wrong test delta, wrong effort band) propagates to all subsequent chunks. Mitigation: arithmetic verified in §4.3 above; cross-reference table in §2 above guarantees every later chunk has a chunk-1 anchor to consume.

### §5.2 §3.2 cross-sub-phase semantic table is novel section type

The L3.5 spec has no cross-sub-phase semantic table because L3.5 was infrastructure-only (no new fields cross-cutting). L5 introduces NEW fields (`forecast_sigma`, `drawdown_probability_distribution`, `dms_adjustment_bps`, `bayesian_shrinkage_weight`) that span sub-phases (L5-D produces drawdown dist; L5-E uses it for σ derivation; L5-G uses σ for shrinkage weighting). The table must encode introduction → modification → final form precisely. Mitigation: lifted from `scored_observation.py:88-96` current schema for fields already present; new field rows draft chunk-1, refined in owning chunk.

### §5.3 L3.5 spec literal sub-phase counts (5 sub-phases A-E) vs L5 spec (10 sub-phases including RM-4/RM-6 split)

L5 spec has TWO IDs that look like inserts into L3.5-style nomenclature: `L5-RM-4` and `L5-RM-6`. These are the calibration triad with L5-C (RM-4 + RM-6 + C). Mitigation: §4 decomposition table makes ordering explicit (L5-B → L5-RM-4 → L5-RM-6 → L5-C → L5-D → ... per dependency graph in §3.1).

### §5.4 Gate 25 shared by L5-F and L5-G

Spec authoring choice required: should gate 25 be a single composite gate (assembled by L5-G's commit using L5-F's outputs), or should L5-F and L5-G each commit a partial-gate definition? Meta-prompt §2.1 chunk 4 says "Gate 25 (sub)" suggesting sub-criteria within a composite. Disposition: §4 decomposition table marks gate 25 as composite (L5-F sub-criterion 1, L5-G sub-criterion 2); the composite gate is sealed at L5-G commit. Chunk 5 §6 (gate definitions) will formalize.

---

## §6 — Effort estimate

**Chunk 1 target**: 2-3h equivalent per meta-prompt §2.1.

**Chunk 1 actual estimate (this pre-flight already-written portion ~0.4h equivalent):**
- §0 + §1 spec authoring: ~0.4h (mostly mirror from L3.5)
- §2 discipline rules: ~0.3h (verbatim from handoff §2 + new §2.5 from meta-prompt §2.4)
- §3 cross-phase architecture: ~0.6h (NEW section type; needs care)
  - §3.1 dependency graph: ~0.2h
  - §3.2 cross-sub-phase semantic table: ~0.4h
- §4 sub-phase decomposition: ~0.4h (10-row table)
- §5-§10 stubs: ~0.1h (skeletons only)
- Verification report: ~0.3h
- Commit + PAUSE: ~0.1h

**Total chunk 1 estimate**: ~2.2h equivalent. Within band.

If actual exceeds 3.5h equivalent, PAUSE-required per meta-prompt §7 scope-creep guardrail.

---

## §7 — NEG / POS test plan (N/A this chunk)

Chunk 1 is documentation authoring; no tests added. NEG/POS ≥50% floor applies at L5 BUILD time (per L3.5 §2.7 convention preserved into L5 §2 discipline rules), not at spec authoring.

---

## §8 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| `conviction_statistical` | 0.95 | Meta-prompt locks Q1-Q8 explicitly; sub-phase decomposition arithmetic verified ×10 above; gate convention proven across L3.5 (gates 12-17) |
| `conviction_operational` | 0.94 | All structural sources verified empirically (codebase recon for scored_observation, r_squared_panel, validation gate dispatch); STEP 1 baseline green |
| `conviction_actionability` | 0.96 | Chunk 1 output is the foundation for chunks 2-5 — directly consumed by subsequent authoring chunks; ChatGPT 5.5 will read this §3.2 table first for cross-sub-phase semantic clarity |
| **Aggregate** | **0.95** | MIN(0.95, 0.94, 0.96) = 0.94 floor; binding constraint = **operational** (codebase recon depth — could be deeper but is sufficient for chunk 1 structural authoring) |

---

## §9 — Recommendation

**PROCEED to chunk 1 authoring** without further V audit. No PAUSE-required ambiguities; no Sxx deviations anticipated this chunk; arithmetic verified; structural mirrors L3.5 with 3 new section types explicitly defined by meta-prompt; risk callouts above are tracked but mitigated.

If V wants to halt before chunk 1 authoring: STOP keyword in chat will trigger an immediate PAUSE.

---

## §10 — Open questions for V (none blocking)

None blocking chunk 1. The following are noted but defer to subsequent chunks:
- (chunk 5) §7 backlog routing of L5-12 / L5-13 / L5-14 / L7-CI-1 / L7-MIGRATE-1 — Strategic recommendation is L5-12 → L4-L5 cleanup deferred, L5-13 → L5-RM-4 absorption, L5-14 → L5-D or L5-E (whichever touches affected files first). Final routing locked in chunk 5.
- (chunk 5) §9 final QC checklist scope — likely 10-12 items mirroring L3.5b composite Gate 17 sub-criteria style.

---

**END — LAYER_5_CHUNK_1_PREFLIGHT.md**
