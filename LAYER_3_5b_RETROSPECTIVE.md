# LAYER 3.5b — Retrospective

**Branch**: `claude/layer-3-5b-build`
**Author**: Claude Code (build agent)
**Date**: 2026-05-10
**Sub-phases**: 4 (3.5b-T, 3.5b-U, 3.5b-V, 3.5b-W); all complete
**Codex 5/5 review status**: 4 closed (T, U, V, W); 1 deferred (X → L5-13)
**Final composite gate**: Gate 17 PASS (all 4 sub-criteria green)

---

## §A — Sub-phase metrics summary

| Sub-phase | Spec band (h) | Actual (h) | New tests | Conviction (S/O/A/agg) | Deviation | Notes |
|---|---|---|---|---|---|---|
| 3.5b-T cache validation | 2–3 | **2.4** | +6 (4 NEG / 2 POS) | 0.95/0.92/0.95/**0.94** | **D28** + L7-MIGRATE-1 backlog | Strict enforcement only (spec D4 transitional scaffold deferred — 138/138 caches already migrated post-3.5E STEP 0); empirical bug repro (PAYEMS pre-fix returned valid bundle on tampered sidecar; post-fix raises CacheValidationError) |
| 3.5b-U Option Z release-lag | 2–3 | **2.6** | +6 (3 NEG / 3 POS) | 0.95/0.93/0.94/**0.94** | **D29** | Empirical SAHM index Path A (observation-month); calibration 7→30 with bug-reproduction at 2025-06-15 anchor; live-config-first lag read defends against config-cache drift; Strategic self-correction of 3.5B AM10 |
| 3.5b-V AP-6 narrowing | 2–3 | **2.7** | +5 (4 NEG / 1 POS regression) — 21 sites narrowed | 0.94/0.93/0.93/**0.93** | **D30** + L5-14 backlog | AST-walk audit revealed comprehensive 21 sites vs spec D2 literal "4 sites"; mid-impl `get_pit_rstar` ValueError → PitDataUnavailableError side-fix (architectural improvement matching NBER extract pattern); Strategic self-correction of spec D2 |
| 3.5b-W NBER boundary | 1–2 | **1.6** | +6 nominal / +31 effective (3 POS / 3 NEG, parametrized × 6 cycles) | 0.97/0.96/0.96/**0.96** | none — cleanest sub-phase | 4-line surgical fix; FRED USREC convention 100% aligned (AM-3.5b-W-1 NOT triggered); 24/24 boundary cases match post-fix vs 12/24 pre-fix; canonical anchors bit-for-bit stable |

**L3.5b totals**: ~9.3h actual coding (+ ~2.0h pre-flight + verification effort = ~11.3h end-to-end); +23 nominal tests (+48 with parametrization explosion 31 in 3.5b-W); 3 deviations filed (D28, D29, D30); 4/5 Codex findings closed; aggregate convictions trending UP across the cycle (0.94 → 0.94 → 0.93 → **0.96**).

---

## §B — Codex 5/5 findings closure

| Finding | Severity | Closed by | Closure mechanism |
|---|---|---|---|
| **T** | HIGH | 3.5b-T | Production scoring read path now routes through `cache.read_cache_validated`; truthy-guard fixed; missing `data_sha256` raises `CacheValidationError`. Empirical: pre-fix `load_series('PAYEMS')` with tampered sidecar returned valid bundle (silent pass); post-fix raises. Plus invariant test `test_all_caches_have_sha_post_l3_5b` formalizes the "138/138 caches" claim into mechanically-falsifiable pytest. |
| **U** | HIGH | 3.5b-U | Option Z by-construction branch applies `to_visibility_index(s, lag)` mirroring Branch 3 (was bare `s[s.index <= as_of]`). SAHMREALTIME `release_lag_days` calibrated 7 → 30 (empirical band 14-45; spec literal). Live-config-first lag read defends against cache-vs-config drift. Empirical: pre-fix at as_of=2025-06-15 returned June 2025 SAHM (3-week look-ahead); post-fix returns May 2025 SAHM (correct). |
| **V** | MED | 3.5b-V | 21 sites across scoring/regime metric tree (V1-V5 + T1-T5 + 6 kindleberger + 4 dalio + 1 D27 consolidation) use shared `legitimate_missing_data_exceptions()` helper. Helper catches `(HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError, PitDataUnavailableError)`; propagates `PitContractViolationError`, `RegimeClassifierError`, `HmmConcurrencyError`, `CacheValidationError`, `IndicatorLoadError`, etc. Side-fix: `get_pit_rstar` ValueError → `PitDataUnavailableError` (architectural alignment). |
| **W** | MED | 3.5b-W | `_last_announced_turning_point` now distinguishes "AT the turning point" (regime is the type the cycle is ENDING) from "STRICTLY AFTER" (regime is the new type started). 24/24 boundary cases align with NBER convention; FRED USREC cross-check confirms 100% alignment. |
| **X** | LOW | **Deferred** | **L5-13** backlog entry: CDRS notes migration symmetry with CRPS (Codex flagged that CDRS still uses `metadata_extra` for some V/T notes while CRPS migrated to `notes` field at 3.5D AM25). Empirical impact zero — CDRS doesn't use Option Z components and pre-1978 is unreachable. Right-sized for L5 walk-forward CV window when training-mode code paths are exercised. |

**Codex closure rate**: 4/5 = 80% in-sub-phase, with X explicitly tracked as L5 work (rationale documented).

---

## §C — Deviations register additions (D28-D30)

### D28 — 3.5b-T spec D4 transitional migration scaffold deferred (AM-3.5b-T-1=A)

Spec §3.3-D4 prescribed a 3-state migration ladder for `data_sha256` mandatory enforcement: (1) emit `DeprecationWarning` on first read, (2) auto-recompute + write sidecar, (3) enforce strictly. Empirical state at 138/138 caches post-3.5E STEP 0 (CFTC + HLW sidecar fixup) makes scaffold dormant. Strict-only enforcement implemented per V/Strategic-approved 4-rationale case (empirical 138/138 + bug repro; spec-literal-vs-intent precedent; Codex finding T scope; YAGNI). Discrete migration sprint deferred to **L7-MIGRATE-1** if/when legacy cache state surfaces.

### D29 — 3.5b-U release_lag_days calibrated 7 → 30 + visibility-shift in by-construction branch (AM-3.5b-U-2=(b))

Empirical bug reproduction at canonical 2025-06-15 anchor: pre-fix `load_series('SAHMREALTIME', as_of=2025-06-15)` returned June 2025 SAHM (0.17, published ~2025-07-04) — 3-week look-ahead leak. With prior config `release_lag_days=7` and visibility-shift applied, leak persists. Empirical band 14 ≤ lag ≤ 45 days; calibrated to 30 (spec §4.3 Path A literal + ~3-day safety margin matching SAHM publication on first Friday of M+1, ~30-37 days post observation-month index). Per V/Strategic-approved 5-rationale case including **Strategic self-correction**: 3.5B AM10 disposition was approved without empirical verification of "by construction" claim; 3.5b-U is the first sub-phase to use the new "Empirical claim verification" Standing Order to CORRECT an earlier Strategic Claude approval.

### D30 — 3.5b-V comprehensive scope (21 sites vs spec D2 literal 4) + helper consolidation + get_pit_rstar side-fix (AM-3.5b-V-1=Comprehensive)

L3.5b spec §5 D2 listed 4 sites. AST-walk audit per new "Empirical claim verification" Standing Order revealed each Codex-flagged file has 4-6 sibling broad-except blocks following identical pattern (5 in cdrs_vulnerability + 5 in cdrs_trigger + 6 in kindleberger + 4 in dalio_cycle + 1 D27 consolidation = 21 sites). Codex finding text "broader scoring/regime tree" supports comprehensive intent. Per V/Strategic-approved 6-rationale case including **second Strategic self-correction**: spec D2 "4 sites" was authoring shortcut without AST-walk audit; build agent's AST-walk caught the gap. Side-fix: `loaders/hlw_rstar_vintage.py::get_pit_rstar` raised bare `ValueError` for pre-2015Q4 PIT lookups; changed to `PitDataUnavailableError` matching NBER extract's pre-1978 pattern (architectural alignment, not just regression remediation).

---

## §D — Backlog seeds added

| ID | Severity / Tier | Effort | Trigger | Description |
|---|---|---|---|---|
| **L5-13** | Tier 3 (low) | 1–2h | Codex L3.5 review finding X | CDRS notes migration symmetry with CRPS. CRPS migrated `metadata_extra` → `notes` at 3.5D AM25; CDRS still uses `metadata_extra` for some V/T notes. Not currently biting (CDRS doesn't use Option Z; pre-1978 unreachable). Right-sized for L5 walk-forward CV when training-mode paths exercised. |
| **L5-14** | Tier 3 (low) | 3–5h | 3.5b-V D30 AST-walk found 16 out-of-scope broad-except sites | Comprehensive AP-6 hygiene sweep across out-of-scope categories: math fallbacks (2 sites), tmp-cleanup (2), loader rebuild flows (6), validation framework error reporting (9). Each category has different idioms; sweep needs per-category analysis. |
| **L7-MIGRATE-1** | Tier 4 (cold / contingent) | 1–2h | 3.5b-T D28 | Discrete migration sprint for legacy caches without `data_sha256`. Only triggered if a future fresh deployment surfaces such caches. Pattern: same one-shot fixup applied at 3.5E STEP 0 for the 5 stale CFTC + HLW sidecars. |
| L7-CI-1 (preserved from L3.5) | Tier 2 (medium / hardening) | 1–2h | L3.5 D27 | CI-level env-hygiene check: assert all `pyproject.toml` `dependencies` are actually installed in venv. Forward-prevent gaps like the filelock case at L3.5E STEP 0. |
| L5-12 (preserved from L3.5B) | Tier 3 (low / nice-to-have) | 6–8h | L3.5B D21 | Full `SeriesConfig` dataclass migration. |

**Net L3.5b backlog growth**: +3 entries (L5-13, L5-14, L7-MIGRATE-1). Combined with L3.5 entries (L5-12 from D21, L7-CI-1 from D27), total L3.5/L3.5b backlog stack: **5 deferred items** (2× L5-low, 1× L5-low/3-5h, 2× L7-conditional/medium-cold).

---

## §E — Pattern compounding insights (cross-phase methodology evolution)

The empirical-discipline pattern compounded across 7 sub-phases (3 from L3.5 + 4 from L3.5b):

```
D23 (3.5C post-impl)            — surprise discovered AFTER coding (CDRS 2020-02 recalibration)
        ↓
D24 (3.5D pre-flight smoke-test) — SAME class of issue caught in pre-flight (HMM dissent affects R)
        ↓
D27 (3.5E STEP 0 diagnostic)    — ENTIRE diagnostic flow before any code (filelock + AP-6 swallow)
        ↓
3.5b-T (bug repro + grep + invariant test) — empirical methodology now the default
        ↓
3.5b-U (triple-state empirical exam) — pre/lag-7-only/post comparison; FRED metadata cross-check
        ↓
3.5b-V (AST-walk + comprehensive scope) — exhaustive site inventory caught 4-vs-21 gap
        ↓
3.5b-W (deterministic 24-case boundary exam) — methodology converged into surgical clean fix
```

**Trajectory**: from "discover bug post-impl + fix" → to "audit comprehensively pre-impl + surgical fix with falsifiable evidence". Each step introduced a new methodology element that compounded:
- **D23** introduced post-impl smoke discipline → D24 lifted to pre-flight smoke
- **D24** introduced multi-anchor empirical analysis → D27 lifted to full diagnostic flow before coding
- **D27** introduced grep-audit + invariant-test artifact → became part of the new Standing Order
- **3.5b-T** applied that Standing Order: grep-audit caught what unit-test-only L3.5E missed
- **3.5b-U** caught Strategic Claude shortcut #1 (3.5B AM10 unverified)
- **3.5b-V** caught Strategic Claude shortcut #2 (spec D2 line-numbers shortcut)
- **3.5b-W** delivered cleanest sub-phase ever (4-line fix; zero deviations; aggregate 0.96)

---

## §F — Strategic Claude self-corrections (lessons for L5 spec authoring)

The new "Empirical claim verification" Standing Order (added between L3.5 and L3.5b) caught 2 Strategic-Claude-authored shortcuts in L3.5b sub-phases:

### F.1 — 3.5B AM10 was approved without empirical verification

**Context**: 3.5B Option Z disposition (`vintage=True` + `pit_safe_by_construction=True` for SAHMREALTIME) was approved by Strategic Claude in May 2026 without inspecting whether SAHM's index is observation-month or publication-month.

**Cost**: a 3-week look-ahead-bias bug shipped to L3.5 main. Codex 5.5 review caught it as finding U.

**Closure**: 3.5b-U pre-flight loaded SAHMREALTIME from cache, ran value-change spacing analysis (29-31 days proves monthly observations), confirmed Path A (observation-month) empirically, calibrated lag to 30 days based on FRED publication schedule.

**Lesson for L5 spec authoring**: every "by construction" claim about PIT-safety must include an empirical exam *before* the disposition is locked. The new Standing Order codifies this.

### F.2 — Spec D2 cited Codex line numbers without AST-walk audit

**Context**: L3.5b spec §5 D2 listed "4 sites" for the AP-6 narrowing sweep, citing the line numbers Codex's review highlighted. Strategic Claude did not run an AST audit to check sibling broad-except blocks in those files.

**Cost**: would have shipped a fix that left 16 sibling AP-6 blocks unchanged (5 V1-V5 sibling sites — 4 still broad after narrowing V1; same for T, kindleberger, dalio). Inconsistent surface, mostly defeating the protection from narrowing.

**Closure**: 3.5b-V pre-flight ran AST-walk audit, found 20 sibling sites + 1 D27 consolidation = 21 in scope. V/Strategic approved comprehensive scope (D30). Plus a mid-impl side-fix (`get_pit_rstar` ValueError → PitDataUnavailableError) emerged as a clean architectural improvement.

**Lesson for L5 spec authoring**: spec authoring must include AST-walk / grep audit at the same level as the build agent's pre-flight. Reviewer-flagged surfaces are exemplars of patterns, not exhaustive scope. The build agent should expect to expand scope when sibling-pattern blocks exist.

### F.3 — Build agent role discipline confirmed

The build agent role definition (per `HANDOFF_CLAUDE_CODE_v4.md` §1: "NOT decision-maker. NOT scope-setter") held throughout. In both self-correction cases, the build agent:
1. Ran the empirical audit (pre-flight)
2. Surfaced the gap as an AM (PROCEED-with-Dxx)
3. Awaited V/Strategic explicit approval before scope expansion

This pause-and-verify discipline made the corrections graceful rather than unilateral.

---

## §G — L3.5 + L3.5b combined metrics

### Quantitative

| Metric | L3.5 baseline | L3.5b end | Delta |
|---|---:|---:|---:|
| Tests passing | 506 | **602** | +96 (+19% absolute) |
| Gates green | 11 | **17** | +6 (12, 13, 14, 15, 16, 17) |
| Effort (h, actual) | ~28.5 | ~28.5 + ~11.3 = ~39.8 | +11.3h L3.5b |
| Codex prior findings closed | 13/13 | 13/13 | preserved |
| Codex L3.5 review findings closed | 0/5 | 4/5 (X→L5-13) | +4 |

### Conviction trajectory

| Sub-phase | Aggregate conviction |
|---|---:|
| 3.5A | 0.85 |
| 3.5B | 0.85 |
| 3.5C | 0.85 |
| 3.5D | 0.85 |
| 3.5E | **0.93** (operational binding lifted post-STEP 0 diagnostic) |
| 3.5b-T | 0.94 |
| 3.5b-U | 0.94 |
| 3.5b-V | 0.93 |
| 3.5b-W | **0.96** |

Discipline compounding visible: average conviction L3.5 = 0.866; average conviction L3.5b = 0.943. The new Standing Order shifted methodology; sub-phases settled into a higher-conviction equilibrium.

### Findings closure

- **Codex prior 13/13** (A, B, C, D, E, F, G, N, O, P, Q, R, S) — closed in L3.5
- **Codex L3.5 review 4/5** (T, U, V, W) — closed in L3.5b
- **Codex L3.5 review 1/5 deferred** (X) — tracked as L5-13

**17/18 = 94% closure rate** on Codex review surface. The 1 deferral has explicit empirical rationale (impact = zero today; right-sized for L5 walk-forward CV).

---

## §H — Forward readiness for Layer 5

L3.5b leaves the substrate ready for Layer 5 walk-forward CV + Ridge weights + isotonic calibration:

**Substrate guarantees**:
- ✓ PIT discipline: empirically verified via 3.5b-U bug reproduction; live-config-first lag reads prevent cache-vs-config drift
- ✓ Cache integrity: strict (raises on tampering); 138/138 cache entries valid; cache_audit utility for ongoing checks
- ✓ AP-6 narrowed comprehensively in scoring/regime tree: contract/config/cache errors propagate; only legitimate-component-missing cases swallow
- ✓ NBER boundary semantics correct: 24/24 boundary cases align across 6 cycles; FRED USREC cross-validated
- ✓ HMM frozen contract: sha-verified, filelock-locked, fail-closed (3.5A → preserved through 3.5b)
- ✓ Probability semantics + dissent (3.5D): INDETERMINATE state + cap 0.60; raw_score / calibrated_probability slot ready

**Open backlog for L5**:
- L5-12: SeriesConfig dataclass migration (cosmetic; not blocking)
- L5-13: CDRS notes migration symmetry (right-sized for training-mode CV exercise)
- L5-14: 16 out-of-scope AP-6 sites (loaders/validation/math fallbacks; not blocking)

**Lessons for L5 spec authoring** (per §F):
1. Every "by construction" / "always X" / "all Y validated" claim needs empirical pre-flight verification, not just unit-test proof.
2. Reviewer-flagged surfaces (line numbers, specific sites) are exemplars; AST-walk audit is required to scope comprehensively.
3. Pause-and-verify discipline scales: 9 sub-phases × pause-and-verify = 0 unverified scope expansions across L3.5+L3.5b.

The build agent role + Standing Orders + empirical discipline pattern are now battle-tested across 9 sub-phases. L5's larger scope (calibration, walk-forward CV, Ridge fitting) will benefit from the same discipline; the harness is ready.

---

## §I — Closing recommendation

**APPROVE L3.5b closure.** Codex 4/5 findings closed cleanly; X explicitly deferred to L5-13 with rationale. Gate 17 composite assembled and green. 17/17 gates PASS; 602 tests pass; ruff clean. L3.5b ready for tag/PR/merge.

Tag candidate: `layer3-5b-complete` on the L3.5b closure commit (this commit, after Gate 17 + retrospective + DEVIATIONS update committed together).

---

**END — LAYER_3_5b_RETROSPECTIVE.md**
