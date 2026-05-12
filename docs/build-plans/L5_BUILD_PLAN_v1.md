# Layer 5 Build Plan v1 — Pre-Flight Readiness Report

**Authoring agent**: Claude Code (Track A) under V's role-widening directive
**Date**: 2026-05-13
**Branch**: `claude/layer-5-build-plan` (forked from `claude/layer-5-spec` @ `9f848bb` = tag `layer5-spec-v6`)
**Predecessor (FROZEN)**: L5 spec v6 at `9f848bb` tag `layer5-spec-v6`
**Scope**: PRE-FLIGHT readiness report ONLY. NO production code in this branch. Spec interpretation deliverable for Strategic Claude review prior to L5-A build greenlight.
**Effort budget**: 1.5–2.5h. Hard pause at 3h.

---

## ITEM 1 — Spec freeze verification

| Check | Required | Actual | Status |
|---|---|---|---|
| `git rev-parse HEAD` on `claude/layer-5-spec` | `9f848bb` | `9f848bb4cc3273109629b3da9155fae0d0e4abb9` | ✓ |
| `git tag --points-at 9f848bb` includes `layer5-spec-v6` | yes | yes (predecessor tags v1..v5 also preserved, all historical) | ✓ |
| Sxx register count | 9 (S-1..S-9; all ACCEPT) | 9 (S-1..S-9; all ACCEPT; verified via spec §10 lines 2373-2387) | ✓ |
| AP register includes AP-AUTH-1..46 with v6 STRENGTHENED items | yes | spec §12 contains AP-16..AP-21 (L5 project APs) + AP-AUTH-39..42 (build-discipline APs incl. AP-AUTH-41 v6 STRENGTHENED + AP-AUTH-42 NEW v6); AP-AUTH-43..46 referenced in chunk 14 verification §7 (process scope guards); AP-AUTH-1..38 base set lives in V's local `HANDOFF_CLAUDE_CODE_v4.md` (out-of-repo) | ✓ (with provenance note) |
| 602 baseline tests on main; no spec-driven test deltas pending | yes | spec §2.6 confirms 602 baseline verified 2026-05-10 (`pytest tests/ -q --no-header` → `602 passed in 142.72s`); no test deltas applied during spec authoring | ✓ |
| ChatGPT 5.5 v6 verdict | FREEZE-AS-IS-V6 | FREEZE-AS-IS-V6 (per V's prompt context: 8/8 PASS, 88% confidence, 8.6/10 conviction) | ✓ |
| `git status` on `claude/layer-5-spec` | clean | clean | ✓ |

**Spec freeze: VERIFIED.** All gates pass. Layer 5 spec is officially frozen for build execution.

---

## ITEM 2 — Sub-phase decomposition + effort table

### §2.1 Canonical sub-phase decomp (12 deliverable units derived from spec §3.1 v3 dependency graph + §4 decomp table)

Per S-9 (v3), L5-B is split into Task A + Task B1 + Task B2. The 10-row §4 decomp table maps to **12 deliverable units** when Task A/B1/B2 are unbundled. Build plan unbundles for granular pause-and-verify.

| # | Sub-phase | Spec section ref | Inputs | Outputs | New tests (v3) | Effort (h) | Gate |
|---|---|---|---|---|---:|---:|---|
| 1 | **L5-A** Walk-forward CV scaffold | §5.A (lines 353-560) | R² panel cache (`data/cache/analysis/r_squared_panel.parquet` from L3D); horizon list {1Y/3Y/5Y/10Y}; CV schedule type {expanding, rolling-20Y} | `analysis/walk_forward_cv.py` (NEW) producing deterministic `(fold_id, train_idx, test_idx, gap_months)` generator per horizon; export `validate_gate18_walk_forward_cv()` | +12 (7 NEG / 5 POS) | 6–8 | 18 |
| 2 | **L5-B Task A** Composite-weight refit (penalized logistic) | §5.B (lines 561-913); §5.B.1 Task A scope | L5-A fold generator; component matrix (CRPS + CDRS components from L3); §3.3 event labels (NBER 12M USREC for CRPS; SPX drawdown for CDRS) | Per-component β coefficients (penalized logistic fit per fold per score_type); refitted composite raw_score panel | +12 | included in 12-16 band | 19 (Task A sub-criteria) |
| 3 | **L5-RM-4** raw/calibrated semantic split + dataclass migration | §5.RM-4 (lines 914-1120) | Task A raw_score output contract; L3.5D ScoredObservation dataclass | `ScoredObservation` v3: **31 total slots / 6 new** (calibrated_probability_band_lower/upper, drawdown_conditional_distribution, dms_adjustment_bps, bayesian_shrinkage_weight, positive_return_probability); L5-13 CDRS notes migration absorbed; raw/calib semantic contract | +8 (5 NEG / 3 POS) | 4–6 | 20 |
| 4 | **L5-RM-6** Isotonic calibration | §5.RM-6 (lines 1121-1356) | RM-4 raw_score field; §3.3 event labels via `build_event_labels()` dispatcher (v3 S-8) | `models/isotonic_calibrator.py` (NEW); **25 calibrators per refit window**: 1 CRPS (12M) + 20 CDRS (4 horizons × 5 thresholds) + 4 RETURN_POSITIVE; quarterly + regime-trigger cadence (Sahm 0.30 → 0.35 escalation; 90d cooldown per S-7) | +14 (6 NEG / 4 POS minimum; v2 +4 net adds via S-2+S-7) | 6–8 | 21 |
| 5 | **L5-B Task B1** Ridge return forecast (v3 S-9) | §5.B Task B1 scope (B.1.0/B.1.1 v3 update) | Post-RM-6 calibrated_probability panel (CRPS + CDRS only; NOT RETURN_POSITIVE); exogenous macro features | Ridge return forecast per horizon; HAC SE + block bootstrap with sensitivity (block-size {h/4,h/2,h,2h} + bandwidth {h-1,Andrews,max(2,h//4)}); joint bootstrap σ + empirical coverage 95 | +13 (Task B1 + initial coverage tests) | included in 12-16 band | 19 (Task B1 sub-criteria) |
| 6 | **L5-B Task B2** RETURN_POSITIVE calibration (v3 S-9) | §5.B Task B2 scope (NEW v3 per S-9) | Task B1 output (Ridge return forecast); §3.3 RETURN_POSITIVE schema | `fit_isotonic_calibrators(score_type="RETURN_POSITIVE", ...)` → 4 calibrators (per horizon); populates `positive_return_probability` ∈ [0,1] | +3 (B2-1 NEG AST audit no-RETURN_POSITIVE-in-B1; B2-2 POS B2 consumes B1; B2-3 POS B2 output ∈ [0,1]) | included in 12-16 band | 19 (Task B2 sub-criteria) |
| 7 | **L5-C** Brier + reliability diagram | §5.C (lines 1357-1487) | Post-RM-6 calibrated_probability panel; climatology baseline = constant prior 6.5%-implied recession rate | `analysis/brier_reliability.py` (NEW); per-horizon Brier decomposition (brier_climatology + bin_counts per §2.5 audit #7); 10-bin reliability per horizon | +8 (4 NEG / 4 POS) | 5–7 | 22 |
| 8 | **L5-D** Drawdown conditional distributions | §5.D (lines 1488-1643) | RM-6 output; regime_state field (L3A 4-state); empirical drawdown realizations from price series | `analysis/drawdown_conditionals.py` (NEW); per-horizon × regime CDF percentiles (p10/p25/p50/p75/p90 per drawdown threshold); 16-cell (4 horizons × 4 regimes) Wilson 95% intervals + hierarchical pooling per cell when n<5 (S-5); populates `drawdown_conditional_distribution` | +12 (8 NEG / 4 POS; v2 +4 net per S-5) | 5–7 | 23 |
| 9 | **L5-E** Forecast σ confidence band | §5.E (lines 1644-1768) | RM-6 + Task B output residuals; CV-fold panel | `analysis/forecast_sigma.py` (NEW); per-horizon σ from CV residuals + isotonic posterior spread; **joint bootstrap σ** with covariance_ridge_isotonic field + empirical_coverage_95 + coverage_inflation_factor (v2 per S-6); populates `calibrated_probability_band_lower/upper` | +9 (4 NEG / 5 POS; v2 +3 net per S-6) | 4–6 | 24 |
| 10 | **L5-F** DMS survivorship adjustment | §5.F (lines 1769-1874) | Horizon dispatcher; DMS bps anchors (5Y: −125; 10Y: −175; ±50 sensitivity); UBS GIRY 2026 reference | `models/dms_adjustment.py` (NEW); horizon-conditional bps; 1Y/3Y untouched (0.0); 5Y/10Y populated; populates `dms_adjustment_bps`; biennial freshness check stub (per Decision Lock 15 / L5-RISK-8) | +5 (3 NEG / 2 POS) | 3–5 | 25.1 (composite sub-criterion) |
| 11 | **L5-G** Bayesian shrinkage to 6.5% real prior | §5.G (lines 1875-end of §5.G) | L5-D conditional drawdowns; L5-F DMS adjustments; CV n_eff_nonoverlap per horizon; `K_HORIZON = {5.9, 6.7, 9.4, 11.0}` (v2 backsolved per S-4); `W_REF_TARGET = {0.05, 0.15, 0.30, 0.50}`; `N_REF_NONOVERLAP = {113, 38, 22, 11}` | `models/bayesian_shrinkage.py` (NEW); horizon-dependent + sample-size-adaptive w_h = k_h / (k_h + n_eff_nonoverlap); populates `bayesian_shrinkage_weight` | +8 (5 NEG / 3 POS; v2 +2 net per S-4) | 25.2 (composite sub-criterion) |
| 12 | **L5-H** Retrospective + Codex review prep | §5.H (lines after L5-G) | All prior sub-phases complete; full test suite passing | `LAYER_5_RETROSPECTIVE.md` (NEW; mirrors L3.5b §A-§I); Gate 25 composite assembly; Codex 5.5 reviewer-handoff checklist | 0 (no new tests; integration only) | 2–3 | — (seals Gate 25 composite; no new gate) |

### §2.2 Effort + test totals (v3 reconciliation)

| Item | v1 (spec headline) | v2 (S-3/4/5/6/7) | v3 (S-8/9 surgical update) | Reconciled v6 total |
|---|---:|---:|---:|---:|
| Effort min (h) | 47 | 62 | 62 | **62** |
| Effort max (h) | 66 | 88 | 88 | **88** |
| Test delta target | +78 | ~+100 (MIN +90 / MAX +115) | ~+104 (via L5-B Task B2 +3 per S-9) | **~+104** |

**Effort estimate within 62-88h band: CONFIRMED.** Sum of mid-band (per-sub-phase): 7+14+5+7+5+5+6+6+5+4+5+2.5 = **71.5h** → within band, biased toward midpoint. No flag required.

Add ~8h for spec verification + per-sub-phase pre-flight audits + ~24h for ChatGPT 5.5 v6 already-completed (sunk) and Codex 5.5 post-build (future) review = end-to-end **94-120h** estimate (consistent with spec §0).

### §2.3 Sub-phase ↔ Q-resolution map

| Q | Locked option | Owning sub-phase |
|---|---|---|
| Q1 (CV window type) | Expanding primary + rolling-20Y | L5-A |
| Q2 (CV step size) | Horizon-dependent (monthly 1Y/3Y, annual 5Y, 5Y blocks 10Y) | L5-A |
| Q3 (Ridge λ selection) | CV-selected nested walk-forward + LOO robustness; v2 applies separately Task A + Task B per S-3 | L5-B |
| Q4 (Isotonic scope) | Per-horizon separate (4 calibrators); v3 corrected to 25 per refit window per S-8 | L5-RM-6 |
| Q5 (Recalibration cadence) | Quarterly + Sahm 0.30 + curve flip; v2 90d cooldown + escalation 0.30→0.35 per S-7 | L5-RM-6 |
| Q6 (DMS bps) | Horizon-conditional (5Y: −125; 10Y: −175; ±50) | L5-F |
| Q7 (Bayesian shrinkage) | k_h/(k_h+n_eff) backsolved per S-4 = {5.9, 6.7, 9.4, 11.0} | L5-G |
| Q8 (Horizon scope) | All 4 horizons in L5 | L5-H confirms in retrospective |

---

## ITEM 3 — Sub-phase execution ordering proposal

### §3.1 Spec dependency graph (verbatim from §3.1 v3 per S-9)

```
                  L5-A walk-forward CV scaffold (Gate 18)
                              │
                              ▼
                  L5-B Task A composite-weight refit (Gate 19; v2 S-3)
                              │
                              ▼
                  L5-RM-4 raw / calibrated split (Gate 20)
                              │
                              ▼
   L5-RM-6 isotonic CRPS + CDRS calibration (Gate 21; 25 calibrators)
                              │
                              ▼
                  L5-B Task B1 Ridge return forecast (v3 S-9)
                              │             (RETURN_POSITIVE NOT input;
                              │              consumes CRPS+CDRS calibrated)
                              ▼
   L5-B Task B2 RETURN_POSITIVE calibration via RM-6 (v3 S-9; 4 calibrators)
                              │
                              ▼
              ┌──────────────┬──────────────┬────────────┐
              ▼              ▼              ▼            ▼
   L5-C Brier + reliab  L5-D drawdown  L5-E forecast σ  L5-F DMS
       (Gate 22)        (Gate 23)      (Gate 24)        (Gate 25.1)
                              │              │            │
                              └──────────────┴────────────┤
                                             ▼            ▼
                                       L5-G Bayesian shrinkage (Gate 25.2)
                                             │
                                             ▼
                                      L5-H retrospective + Codex prep
                                          (no new gate)
```

### §3.2 Hard dependency edges (DAG)

| Predecessor | Successor | Edge constraint |
|---|---|---|
| L5-A | L5-B Task A | Task A penalized-logistic fit needs deterministic CV folds |
| L5-B Task A | L5-RM-4 | Raw_score output contract (post-refit) is what RM-4 splits semantically |
| L5-RM-4 | L5-RM-6 | Isotonic fits on `raw_score`; needs RM-4 dataclass contract + slot semantics |
| L5-RM-6 | L5-B Task B1 | Task B1 consumes post-RM-6 calibrated_probability panel (CRPS+CDRS) as input matrix |
| L5-B Task B1 | L5-B Task B2 | Task B2 calibrates Task B1 output (Ridge return forecast) → `positive_return_probability` |
| L5-B Task B2 | L5-C, L5-D, L5-E, L5-F | All 4 sub-phases consume calibrated_probability + positive_return_probability panels |
| L5-D | L5-G | Bayesian shrinkage uses conditional drawdown distribution as empirical prior input |
| L5-F | L5-G | Bayesian shrinkage uses DMS-adjusted return anchor (6.5% − dms_bps) as long-run prior |
| L5-G | L5-H | Retrospective seals Gate 25 composite (25.1 from F + 25.2 from G) |

### §3.3 Parallel execution candidates

Spec §3.1 line 252-253 states: "L5-C, L5-D, L5-E, L5-F are mostly independent given L5-RM-6 output; can be authored in any order within chunk 4. **Build order locked to C → D → E → F for build determinism.**"

**Parallel candidates that are NOT activated**: {L5-C, L5-D, L5-E, L5-F} as a group. They could theoretically run in parallel after L5-B Task B2 ACCEPT, but spec mandates sequential C→D→E→F.

**Recommendation: PRESERVE spec-mandated sequential C→D→E→F.** Rationale:
1. Build determinism for pause-and-verify discipline — sequential keeps single in_progress sub-phase
2. Each sub-phase's verification report builds incrementally on prior gate evidence
3. Parallel execution risks AP-AUTH-44 (modify beyond scope) if cross-sub-phase coordination is needed mid-flight
4. Effort savings from parallelization (~5h max if all 4 could run truly parallel) is < cost of coordination risk

### §3.4 Critical path identification

**Critical path** = 12 sub-phases sequentially (per §3.3 recommendation):

```
L5-A → L5-B Task A → L5-RM-4 → L5-RM-6 → L5-B Task B1 → L5-B Task B2
     → L5-C → L5-D → L5-E → L5-F → L5-G → L5-H
```

Critical-path mid-band effort sum: **71.5h** (no slack from parallelization).

**Longest single sub-phase**: L5-B (12-16h band; Task A + Task B1 + Task B2 combined; v2/v3 expanded from 8-10h v1). Recommend splitting L5-B into 3 sequential commits (Task A → RM-4 → RM-6 → Task B1 → Task B2) with separate Gates 19a/19b/19c rather than single Gate 19 closure to preserve pause-and-verify granularity.

### §3.5 Foundation-first heuristic compliance

V's heuristic: "data/foundation layer first → modeling sub-phases in spec-numerical order → integration last."

| Layer | Sub-phase(s) | Compliance |
|---|---|---|
| Foundation | L5-A (CV scaffold) | ✓ first |
| Modeling | L5-B Task A → L5-RM-4 → L5-RM-6 → L5-B Task B1 → L5-B Task B2 → L5-C → L5-D → L5-E → L5-F → L5-G | ✓ spec-numerical with v3 S-9 split |
| Integration | L5-H (retrospective seals Gate 25 composite) | ✓ last |

**Foundation-first heuristic: SATISFIED.** No deviation from heuristic; no special justification required.

---

## ITEM 4 — Test contract preservation plan

### §4.1 Per-sub-phase test deltas + module map

| # | Sub-phase | New tests | Module(s) touched | Existing tests at risk | Gate alignment requirement (4/4 mirror) |
|---|---|---:|---|---|---|
| 1 | L5-A | +12 | `analysis/walk_forward_cv.py` (NEW); `validation.py` (add gate18); `analysis/__init__.py` (export) | None (new module). Validation hub touched but additive only. | §5.A.5 (test file) == §5.A.6 (Gate 18 PASS criteria) == §5.A.7 (proof contract) == §6.1 (consolidated Gate 18 mirror) |
| 2 | L5-B Task A | +12 | `analysis/walk_forward_cv.py` (extends); `models/composite_refit.py` (NEW Task A); ScoredObservation NOT touched yet (RM-4 owns) | Existing CRPS/CDRS scoring tests in `tests/test_crps_production_scorer.py` + `tests/test_cdrs_two_stage_scorer.py` — additive (Task A refit doesn't replace L3 baseline weights) | §5.B.5 Task A tests == §5.B.6 Gate 19 Task A sub-criteria == §5.B.7 proof contract == §6.2 |
| 3 | L5-RM-4 | +8 | `scoring/scored_observation.py` (DATACLASS MIGRATION — 6 new slots); `scoring/scored_observation.py:89` (calibrated_probability slot); `validation.py` (Gate 20) | **HIGH RISK**: Every test that constructs a ScoredObservation must verify the 6 new slot defaults don't break. ~50+ existing tests across L3, L3.5, L3.5b touch ScoredObservation. AP-AUTH-44 enforcement: surgical edits only. | §5.RM-4.5 == §5.RM-4.6 == §5.RM-4.7 == §6.3 (RM-4 31/6 anchor per AP-AUTH-41 v6) |
| 4 | L5-RM-6 | +14 | `models/isotonic_calibrator.py` (NEW); `scoring/scored_observation.py` (populates calibrated_probability, positive_return_probability, calibration_metadata via build_event_labels dispatcher per S-8) | Pre-RM-6 calibrated_probability access raises RuntimeError per §2.5 audit #6 — existing tests must be updated to consume only post-RM-6 calibrated_probability | §5.RM-6.5 == §5.RM-6.6 (Gate 21 v3 per S-8) == §5.RM-6.7 == §6.4 |
| 5 | L5-B Task B1 | +13 | `models/return_forecast_ridge.py` (NEW); HAC + block bootstrap utilities | None (new module). Cross-fold contamination check (§2.5 audit #1) extends Task A audit. | §5.B.5 Task B1 == §5.B.6 Gate 19 Task B1 sub-criteria == §5.B.7 == §6.2 |
| 6 | L5-B Task B2 | +3 | `models/isotonic_calibrator.py` (extends; RETURN_POSITIVE score_type path); fit_isotonic_calibrators dispatcher | None (new path). AST audit B2-1 enforces no-RETURN_POSITIVE-in-B1 — protects against circular dependency regression. | §5.B.5 Task B2 == §5.B.6 Gate 19 Task B2 sub-criteria == §5.B.7 == §6.2 |
| 7 | L5-C | +8 | `analysis/brier_reliability.py` (NEW); `validation.py` (Gate 22) | None (new module). Brier baseline must be reported per §2.5 audit #7 (brier_climatology + bin_counts companions). | §5.C.5 == §5.C.6 == §5.C.7 == §6.5 |
| 8 | L5-D | +12 | `analysis/drawdown_conditionals.py` (NEW); `validation.py` (Gate 23); ScoredObservation.drawdown_conditional_distribution populated | None (new module). Cell completeness audit §2.5 #8 enforces all 16 cells have 4 fields. | §5.D.5 == §5.D.6 == §5.D.7 == §6.6 |
| 9 | L5-E | +9 | `analysis/forecast_sigma.py` (NEW); ScoredObservation.calibrated_probability_band_lower/upper populated; coverage_inflation_factor + empirical_coverage_95 fields | None (new module). Coverage audit §2.5 #10 enforces per-horizon empirical reporting. | §5.E.5 == §5.E.6 == §5.E.7 == §6.7 |
| 10 | L5-F | +5 | `models/dms_adjustment.py` (NEW); ScoredObservation.dms_adjustment_bps populated for 5Y/10Y only | **REGRESSION GUARD**: existing 1Y/3Y tests must verify dms_adjustment_bps == 0.0 (no leakage); §2.5 audit #3 grep-audits horizon dispatcher | §5.F.5 == §5.F.6 (Gate 25.1) == §5.F.7 == §6.8 sub-criterion 25.1 |
| 11 | L5-G | +8 | `models/bayesian_shrinkage.py` (NEW); ScoredObservation.bayesian_shrinkage_weight populated horizon-dependent | None (new module). §2.5 audit #4 + #9 enforces horizon-dependent + W_REF_TARGET match within ±2pp; AP-20 enforcement (no constant 0.30 literal). | §5.G.5 == §5.G.6 (Gate 25.2) == §5.G.7 == §6.8 sub-criterion 25.2 |
| 12 | L5-H | 0 | `LAYER_5_RETROSPECTIVE.md` (NEW); no code touch | Final pytest run on full suite (602 baseline + 104 L5 deltas = ~706 target) | Gate 25 composite assembly verifies 25.1 + 25.2 + retrospective §§A-I structure |

### §4.2 Test contract regression risk summary

| Risk level | Sub-phase(s) | Detail |
|---|---|---|
| **HIGH** | L5-RM-4 | Dataclass migration touches every ScoredObservation construction site. AP-AUTH-44 (surgical edits only) + AP-AUTH-41 v6 (dual-grep) mandatory. |
| **MEDIUM** | L5-RM-6 | Pre-RM-6 calibrated_probability access raises; downstream tests must be migrated |
| **LOW** | L5-A, L5-B Task A/B1/B2, L5-C, L5-D, L5-E, L5-F, L5-G, L5-H | New modules; additive; no existing-test regression expected |

### §4.3 Gate alignment requirement (preserve v6 20/20 mirror discipline at code level)

Every sub-phase's verification report MUST present a 4-point alignment table:

```
| Sub-phase | §5.X.5 tests (code) | §5.X.6 PASS criteria | §5.X.7 proof contract | §6.N consolidated gate |
|---|---|---|---|---|
| L5-A | N tests in tests/test_walk_forward_cv.py | N PASS criteria in §5.A.6 | 10 proof items in §5.A.7 | Gate 18 in §6.1 |
| ... etc ... | ... | ... | ... | ... |
```

Each cell requires BOTH positive grep (criterion present) AND negative grep (no contradictory pattern) per AP-AUTH-41 v6 — applied to CODE not spec text. For example: L5-A §5.A.5 NEG test for cross-fold contamination + §5.A.6 Gate 18 PASS criterion mentioning "zero contamination" must align.

### §4.4 Baseline regression floor

- **Pre-build**: `pytest tests/ -q --no-header` MUST report `602 passed in <X>s`
- **Per sub-phase commit**: full pytest suite MUST pass (no skipped, no xfailed)
- **Post-L5-H**: full pytest suite MUST report `~706 passed` (602 + 104 L5 deltas; ±5 tolerance for any sub-phase test-count adjustments documented as build-time Sxx)

---

## ITEM 5 — Sxx escalation protocol for build phase

### §5.1 Spec-authoring Sxx → build-execution Sxx adaptation

Spec authoring filed 9 Sxx (S-1..S-9 all ACCEPT). Build execution Sxx semantics differ: spec authoring catches **methodology decisions**, build execution catches **empirical surprises + implementation gaps**.

Reserved range: spec §2.8 reserves S-10 through S-25 for build-time Sxx.

### §5.2 Build-phase Sxx trigger taxonomy

| Trigger | Detail | Disposition path |
|---|---|---|
| **T1: Discovered spec ambiguity** | Implementation finds 2+ valid interpretations of spec text; spec is FROZEN so can't be reopened directly | File Sxx with **CONDITIONAL** disposition; propose default interpretation; escalate to Strategic for ACCEPT/REJECT/DEFER |
| **T2: Test contract violation** | Existing test breaks unexpectedly OR spec-stated test count differs from achievable | File Sxx with **ACCEPT** if test scope is documented adjustment (e.g., adjusting test count to match achievable n_eff), **CONDITIONAL** if methodology may be implicated |
| **T3: Conviction floor breach** | Sub-phase verification reports conviction <0.90 on stat/op/act | File Sxx **CONDITIONAL**; sub-phase CANNOT advance to next-sub-phase pre-flight; Strategic decides DEFER (continue with caveat) / REVISE (rework current sub-phase) / ESCALATE (ChatGPT 5.5 mid-build review) |
| **T4: AP-AUTH violation detected** | Self-audit OR Strategic review detects an AP-AUTH-1..46 violation in current sub-phase | File Sxx **REVISE-REQUIRED**; immediate sub-phase rework before continuation. Pattern from L3.5b T/U/V/W. |
| **T5: Out-of-distribution input** | Production data exhibits regime/distribution not anticipated by spec (e.g., new Sahm Rule trigger pattern, novel drawdown distribution shape) | File Sxx **CONDITIONAL**; escalate to Strategic; possible ChatGPT 5.5 mid-build review if methodology implication |
| **T6: Effort overrun >25%** | Sub-phase effort actual exceeds spec band upper bound by >25% (e.g., L5-RM-4 at 4-6h spec; actual >7.5h) | File Sxx **ACCEPT** with cause analysis; no methodology change; flag for L5-H retrospective pattern recognition |
| **T7: Empirical calibration surprise** | §2.3 smoke-test empirical reading contradicts spec default (e.g., Ridge λ optimum at grid boundary; isotonic monotonicity violation) | File Sxx **CONDITIONAL**; propose threshold adjustment; await Strategic ACCEPT before locking |

### §5.3 Resolution paths (3-way)

| Path | When | Authority | Effect |
|---|---|---|---|
| **DEFER** | Build-time discovery is real but not blocking sub-phase ACCEPT; can be handled in L5-H retrospective or L5b/L6 future scope | Strategic Claude (Track B) | File Sxx with DEFER + backlog ref; current sub-phase proceeds; doc trail preserved |
| **PATCH SPEC (REOPEN)** | Build-time discovery proves spec is wrong, not just ambiguous; methodology revision needed | Strategic + ChatGPT 5.5 BOTH required; V final authority | Triggers **v7 surgical patch cycle** (mirrors v4/v5/v6 pattern); breaks 3-consecutive-zero-Sxx convergence; reset spec-freeze status until v7 ACCEPT |
| **PATCH IMPLEMENTATION ONLY** | Build-time discovery is scoped to implementation choice within spec degrees of freedom; spec unchanged | Strategic Claude | Implementation-level adjustment within current sub-phase; document in verification report + Sxx |

### §5.4 Sxx filing format + log location

Mirroring spec §2.8 format with build-phase additions:

```markdown
## S-N — YYYY-MM-DD — sub-phase L5-X[.Y] — [brief topic]

**Trigger**: T1/T2/T3/T4/T5/T6/T7
**Disposition**: ACCEPT / CONDITIONAL / REVISE-REQUIRED / DEFER
**Rationale**: [1-3 sentences with empirical evidence; cite spec section + code locator]
**Resolution path**: DEFER / PATCH-SPEC / PATCH-IMPL
**Strategic decision**: [pending / approved / rejected; with date + decision authority]
**Backlog ref**: [L5b-N or L6-N or L7-N] (if any)
**Build artifact**: [link to verification report or PR# where this Sxx surfaces]
```

**Log location**: `docs/build-plans/L5_BUILD_SXX_LOG.md` (NEW file at first build-time Sxx filing on the build branch). Mirrors spec §2.8 Sxx register but live-updates during build. Strategic reviews at each sub-phase ACCEPT cycle.

### §5.5 Spec REOPEN guardrail (AP-AUTH-44 / AP-AUTH-46 compliance)

Per AP-AUTH-44 (modify beyond scope) + AP-AUTH-46 (file Sxx without methodology need):
- **NEVER** modify `LAYER_5_BUILD_SPEC.md` during build phase without explicit V approval + Strategic + ChatGPT 5.5 sign-off
- If build-time discovery flags T1 (spec ambiguity) — PAUSE sub-phase, file Sxx, escalate; do NOT patch spec in-flight
- T6 (effort overrun) alone is NOT spec-REOPEN trigger; file Sxx ACCEPT + continue

---

## ITEM 6 — AP-AUTH honor list for build phase

### §6.1 AP enforcement classification

| AP range | Source | Enforcement during build |
|---|---|---|
| **AP-1..AP-15** | Prior layers L1..L3.5 (per spec §12 header) | Cumulative; preserved; spot-check during code review |
| **AP-AUTH-1..21** | V's `HANDOFF_CLAUDE_CODE_v4.md` §7 (out-of-repo) | Baseline build-discipline; preserved through L5 |
| **AP-AUTH-22..32** | HANDOFF v4 (v1+v2 cycle additions; out-of-repo) | Spec-authoring discipline; mostly N/A during build |
| **AP-AUTH-33..38** | HANDOFF v4 (v3 cycle; out-of-repo) | Spec surgical-scope discipline; mostly N/A during build |
| **AP-16..AP-21** | spec §12 (L5 project methodology APs) | **HIGH PRIORITY** for build; see §6.2 |
| **AP-AUTH-39..42** | spec §12 (v4/v5/v6 audit-instrument APs) | **HIGH PRIORITY** for build; see §6.3 |
| **AP-AUTH-43..46** | chunk 14 verification §7 (v6 process scope guards) | Apply at each sub-phase ACCEPT; see §6.4 |

### §6.2 L5 project methodology APs (AP-16..AP-21) — build-time enforcement

| AP | Symptom | Build-time check |
|---|---|---|
| **AP-16** Walk-forward CV with cross-fold contamination | train_end ≥ test_start - gap_months | L5-A: §2.5 audit #1 (AST-walk over walk_forward_cv.py); CI hook: pytest test `test_no_cross_fold_contamination_regression` |
| **AP-17** Ridge λ in-sample CV without nested walk-forward | λ chosen from train+val combined panel | L5-B Task A + Task B1: §5.B.5 test for nested walk-forward grid; CI hook: AST audit on Ridge fit call sites |
| **AP-18** Isotonic calibrator across-fold leakage | Calibrator fit on fold k reused on fold k+1 | L5-RM-6: §2.5 audit #5 train-only z-scoring extension; CI hook: AST audit on `fit_isotonic_calibrators` call sites |
| **AP-19** DMS bps applied to 1Y/3Y output paths | Non-zero dms_adjustment_bps for horizon ∈ {1Y, 3Y} | L5-F: §2.5 audit #3 horizon dispatcher; CI hook: regression test `test_dms_zero_for_short_horizons` |
| **AP-20** Bayesian shrinkage weight as constant | `weight = 0.30` literal anywhere in code | L5-G: §2.5 audit #4 + #9; CI hook: grep `grep -nrE "weight\s*=\s*0\.[0-9]+" models/` MUST return 0 hits in `bayesian_shrinkage.py` |
| **AP-21** `score_value` references re-introduced post-3.5D rename | Stale `score_value` field access | L5-RM-4: dataclass migration absorbs final L4-L5 boundary cleanup; CI hook: grep `grep -nrE "\.score_value" macro_pipeline/` MUST return 0 hits |

### §6.3 v4/v5/v6 audit-instrument APs (AP-AUTH-39..42) — build-time automation proposals

| AP | Build-time semantics | Pre-commit hook proposal |
|---|---|---|
| **AP-AUTH-39** Sub-phase §5.X.6 ↔ §6.N gate mirror sync miss | At code level: when adding a Gate PASS criterion, verify both source-of-truth code constants + downstream consolidated assertion are in sync | Pre-commit hook `validate_gate_mirror.py`: parses both sub-phase test file + consolidated `validation.py` gate function; asserts gate ID + PASS criteria count alignment. Runs on every commit touching `validation.py`. |
| **AP-AUTH-40** Sxx-to-spec-body propagation miss (cumulative arithmetic regex) | At code level: cumulative test count arithmetic in proof contracts uses symbolic, NOT hard-coded `N + M = K` patterns | Pre-commit hook `validate_no_cumulative_arithmetic.py`: regex `[0-9]+ \+ [0-9]+ =` scans `LAYER_5_*.md` + `tests/test_*.py` docstrings; returns 0 hits or fails commit. Codifies AP-AUTH-42 NEW. |
| **AP-AUTH-41 v6 STRENGTHENED** Mirror integrity requires BOTH pos+neg grep | At code level: every verification report claiming alignment must show both positive AND negative grep output per anchor | Pre-commit hook `validate_dual_grep_in_verification.py`: scans verification reports `LAYER_5_*_VERIFICATION.md` for "pos: ... / neg: ..." patterns in alignment tables; fails commit if alignment claim missing dual-grep evidence. **Strong candidate for automation per V's prompt.** |
| **AP-AUTH-42 NEW v6** Cumulative arithmetic regex-based scrub | Same as AP-AUTH-40 (regex-based) | Same hook as AP-AUTH-40 above; AP-AUTH-42 is the regex-mandate, AP-AUTH-40 is the symbolic-wording-mandate. Both enforced by single hook. |

**Recommended automation integration**:
- **At build start (L5-A pre-flight)**: install 2 pre-commit hooks (`validate_no_cumulative_arithmetic.py` + `validate_dual_grep_in_verification.py`) into `.git/hooks/pre-commit` OR `.pre-commit-config.yaml` per project convention
- **At build branch creation**: configure CI workflow `.github/workflows/build_discipline.yml` to enforce same checks on PR (defense-in-depth)
- **Strategic review burden reduction**: automated pos+neg grep verification removes manual audit at each pause-and-verify cycle

### §6.4 v6 process scope guards (AP-AUTH-43..46) — per sub-phase ACCEPT enforcement

| AP | Per-sub-phase compliance check |
|---|---|
| **AP-AUTH-43** (sub-phase's own additions — likely codify AP-AUTH-44/45/46 as authoring deliverables; placeholder for build-discipline addition) | Each sub-phase verification report §7 mirrors chunk 14 verification §7 format (n/a — adding) |
| **AP-AUTH-44** Modify beyond sub-phase scope | Each sub-phase verification report §7 row: "NO — surgical edits to [list]". Reviewer audits diff scope vs declared. |
| **AP-AUTH-45** Force-push prior sub-phase tag | Tag preservation check: every prior sub-phase tag (e.g., `layer5-l5a-complete`) untouched post-this-sub-phase commit. Reviewer runs `git tag --points-at <prior-sha>` on each prior tag. |
| **AP-AUTH-46** File Sxx without methodology need | Sxx audit: any S-N filed during sub-phase must have valid trigger ∈ {T1..T7 per §5.2}. Reviewer challenges any Sxx without explicit trigger map. |

### §6.5 Build-phase AP additions (proposed; reserved for AP-AUTH-47+)

Subject to filing as build-time emerges. Candidates to reserve numbering for:
- **AP-AUTH-47 candidate**: "Commit message does not declare sub-phase context" (sub-phase commits MUST use template per §5.X.0 metadata commit_message_template)
- **AP-AUTH-48 candidate**: "Test added without NEG counterpart" (≥50% NEG floor per §2.7 enforced at PR review)
- **AP-AUTH-49 candidate**: "Pre-flight audit skipped" (per §2.2 — every sub-phase starts with `LAYER_5_<phase>_PREFLIGHT.md`)

**NOT filing now.** Reserved for build-time discovery if violations emerge.

---

## ITEM 7 — Worktree + branch strategy

### §7.1 Current worktree inventory

| Worktree | Branch | HEAD | Purpose |
|---|---|---|---|
| `D:/macro_pipeline/` | `main` | `590e4a5` | Main repo HEAD; L3.5b merge commit |
| `nice-hertz-8e70f9` | `claude/layer-5-build-plan` | (current build-plan branch) | THIS branch; pre-flight deliverable; **NOT for build code** |
| `mystifying-volhard-1d834b` | `claude/mystifying-volhard-1d834b` | `590e4a5` | Empty branch at main HEAD; available for repurposing |
| `keen-torvalds-63c79a` | `claude/layer-3-5b-build` | `dcf698d` | L3.5b complete (closed); preserved historical |
| Other worktrees | various | various | inactive or task-scoped |

### §7.2 Proposed build worktree

**Recommendation: CREATE NEW WORKTREE** at `D:/macro_pipeline/.claude/worktrees/layer-5-build` forked from `main` at `590e4a5` (= L3.5b merge commit = `git merge-base claude/layer-5-spec main` baseline).

Rationale:
1. Fresh worktree isolates build code from spec authoring + review-publication branches
2. Forking from `main` (not from `claude/layer-5-spec`) means the build starts on a code-only baseline; spec docs live in the parallel spec branch
3. Naming pattern `layer-5-build` follows L3.5b precedent (`hungry-chebyshev-0c5d10` was `claude/layer-3-build`; `keen-torvalds-63c79a` was `claude/layer-3-5b-build`)

**Command** (for V or Strategic to execute when greenlight):
```bash
git -C D:/macro_pipeline worktree add D:/macro_pipeline/.claude/worktrees/layer-5-build -b claude/layer-5-build 590e4a5
```

### §7.3 Branch naming convention proposal

V's prompt presents 2 options:
- **Option A**: `claude/layer-5-build/<sub-phase>` per sub-phase (12 branches)
- **Option B**: single `claude/layer-5-build` with sub-phase commits

**Recommendation: Option B (single branch + sub-phase commits + sub-phase tags).** Rationale:

| Criterion | Option A (per-sub-phase branch) | Option B (single branch) |
|---|---|---|
| Linear history | NO — 12 branches, merge spaghetti | YES — 12 sequential commits |
| Dependency tracking | HARD — each branch needs base bump | EASY — natural commit chain |
| PR per sub-phase | YES (clean) | YES (PR per sub-phase ACCEPT can still be opened via temp branch off each ACCEPT commit) |
| Tag preservation | Per-branch tags | Per-sub-phase tags on single branch (e.g., `layer5-l5a-complete`, `layer5-l5b-complete`, ...) |
| Merge to main complexity | 12 merge commits OR single squashed | Single merge OR rebase-and-merge final |
| Pause-and-verify discipline | Same | Same |
| Precedent | None in this repo | L3.5b used single branch `claude/layer-3-5b-build` ✓ |

**Sub-phase tag naming**: `layer5-l5a-complete`, `layer5-l5b-taska-complete`, `layer5-l5rm4-complete`, `layer5-l5rm6-complete`, `layer5-l5b-taskb1-complete`, `layer5-l5b-taskb2-complete`, `layer5-l5c-complete`, `layer5-l5d-complete`, `layer5-l5e-complete`, `layer5-l5f-complete`, `layer5-l5g-complete`, `layer5-complete` (final after L5-H).

### §7.4 Merge strategy back to main

**Recommendation: integration branch → main only AFTER all sub-phases ACCEPT + L5b OOS hardening pass** (per V's prompt suggestion).

Sequence:
1. Build sub-phases 1-12 committed sequentially to `claude/layer-5-build` with per-sub-phase tags
2. L5-H retrospective committed; `layer5-complete` tag applied
3. Open PR `claude/layer-5-build → main` for L5 closure review (Codex 5.5 reviews here)
4. L5b OOS hardening sprint begins on `claude/layer-5b-oos-hardening` forked from `layer5-complete` tag
5. After L5b ACCEPT, decision: merge L5+L5b to main as single PR OR separate L5 / L5b merges

Decision deferred to V at L5-H ACCEPT time.

### §7.5 Worktree contamination prevention (AP-AUTH-44 enforcement)

- **Do NOT** use `nice-hertz-8e70f9` worktree for build code — it's spec/review-locked
- **Do NOT** modify `claude/layer-5-spec` branch during build — spec is FROZEN
- **Do NOT** cherry-pick commits between `claude/layer-5-build` and `claude/layer-5-spec` — separate concerns
- **Reviewer audit at each sub-phase ACCEPT**: `git -C <build-worktree> log --oneline <build-branch> ^main` shows only L5 commits + no cross-contamination

---

## ITEM 8 — Conviction tracking + reporting cadence

### §8.1 Conviction floor (UNCHANGED per Standing Order #4 + §2.4)

| Field | Floor | Binding constraint context |
|---|---|---|
| `conviction_statistical` | ≥ 0.90 | Build phase: CV-fold stability + λ regularization path stability + isotonic monotonicity + W_REF_TARGET match within ±2pp |
| `conviction_operational` | ≥ 0.90 | Build phase: PIT discipline (inherited from L3.5b); regime-trigger empirical reading; vintage cleanness; 4/4 mirror discipline at code level |
| `conviction_actionability` | ≥ 0.90 | Build phase: downstream consumers (L5b, L6, Codex 5.5) usable; ScoredObservation populated post-RM-6; no None in production calibrated_probability paths |
| **Aggregate (MIN)** | ≥ 0.90 hard floor (PAUSE on breach) |  |

### §8.2 Expected binding constraint shift (build vs spec authoring)

| Phase | Typical binding | Reason |
|---|---|---|
| Spec authoring (L5 v1..v6) | OPERATIONAL (lowest min) | Discipline gaps in audit-instruments dominated |
| **Build (L5-A through L5-H)** | **STATISTICAL** (expected to dominate) | Model correctness on empirical data; CV fold stability; isotonic monotonicity; W_REF target match — these are statistical-correctness gates |
| L5b OOS hardening | STATISTICAL → OPERATIONAL crossover | Block bootstrap + structural break tests stress operational stability |

**Strategic prior on build-time binding**: STATISTICAL. Code at each sub-phase verification will quote 3-field with binding identification; if OPERATIONAL or ACTIONABILITY becomes binding, this is a signal (positive or negative).

### §8.3 Strategic reporting cadence

**Proposal**: at each sub-phase ACCEPT, deliver Readiness Report mirroring v6 quality bar:

| Field | Required content |
|---|---|
| Sxx count + dispositions | Cumulative S-N..S-M filed in this sub-phase; ACCEPT/CONDITIONAL/DEFER counts |
| Test deltas | Pre-sub-phase N; post-sub-phase M; NEG/POS split; ≥50% NEG floor confirmed |
| AP audits | All AP-16..AP-21 checked; all relevant AP-AUTH-39..46 checked (pos+neg grep evidence per AP-AUTH-41 v6) |
| Conviction 3-field + binding | stat / op / act with binding identification + drivers |
| Evidence URLs / refs | Commit SHA; tag name; test file paths; pre-flight + verification doc paths |
| Effort actual vs band | Reported vs §X.0 band; T6 trigger if >25% over upper |
| Gate alignment table | 4/4 mirror check per §4.3 |

**Sub-phase ACCEPT format**: identical to `LAYER_5_V6_CHUNK_14_VERIFICATION.md` template (§1..§8 sections).

### §8.4 External (ChatGPT 5.5) review cadence

**Proposal (per V's prompt)**:
1. **After L5-A ACCEPT** (foundation gate): ChatGPT 5.5 reviews the foundation walk-forward CV scaffold. Locks the OOS validation contract before modeling work proceeds. Lower-cost / lower-stakes than full-L5 review.
2. **After L5-H ACCEPT** (full L5 closure / pre-L5b gate): ChatGPT 5.5 reviews the complete L5 build (similar to v1-v6 spec review cycle). Required before L5b OOS hardening kickoff.

NOT per-sub-phase review (too expensive; cost-benefit unfavorable for sub-phases 2-11).

**Optional mid-build review triggers** (Strategic decides):
- T3 (conviction breach) on sub-phase 5+ → mid-build review
- T5 (OOD input) flagged during L5-D or L5-E → mid-build review
- T6 (effort overrun >25%) on 2+ sub-phases → mid-build review
- Codex 5.5 reviews code post-L5-H; not the same review as ChatGPT 5.5 methodology

### §8.5 Conviction trajectory expectation

Spec authoring trajectory: 0.91 (v2) → 0.97 (v5 prelim) → 0.98 (v6 final). Convergence pattern.

Build trajectory expected:
- L5-A: 0.95+ (foundation; well-specified)
- L5-B Task A: 0.92+ (Ridge familiar; penalized logistic standard)
- L5-RM-4: 0.93+ (dataclass migration mechanical; HIGH-RISK regression risk)
- L5-RM-6: 0.93+ (isotonic familiar; 25-calibrator dispatch needs careful audit)
- L5-B Task B1: 0.92+ (HAC + block bootstrap; familiar territory; coverage audit critical)
- L5-B Task B2: 0.95+ (small scope per S-9)
- L5-C: 0.95+ (Brier standard)
- L5-D: 0.90 floor (hierarchical pooling + Wilson intervals; n_eff<5 cells tricky)
- L5-E: 0.92+ (joint bootstrap; coverage inflation factor)
- L5-F: 0.95+ (DMS bps mechanical)
- L5-G: 0.93+ (k_h backsolved; W_REF target match ±2pp test)
- L5-H: 0.95+ (retrospective composition)

**Trajectory floor expected: ≥0.90 sustained across all 12 sub-phases.** Any sub-phase breaching → T3 trigger.

---

## ITEM 9 — Risk register for L5 build

### §9.1 Top 12 risks (covering V's required categories + 2 extensions)

| # | Risk | Severity | Probability | Mitigation | Trigger to escalate |
|---|---|---|---|---|---|
| 1 | **Spec ambiguity at implementation time** | M | 30% (per sub-phase) | Pre-flight audit §2.2 enumerates ambiguities BEFORE coding; T1 Sxx filing | Sxx CONDITIONAL with 2+ candidate interpretations and no clear default; sub-phase PAUSE |
| 2 | **Test contract regression** (existing pytest breaks) | H (if RM-4 era) / L (other) | 60% at L5-RM-4 / 5% elsewhere | AP-AUTH-44 (surgical edits); RM-4 dataclass migration in single atomic commit; pre-commit `pytest -q` MUST pass | Any sub-phase commit causes >0 prior test failures → T2 Sxx + REVISE |
| 3 | **Effort overrun >25% per sub-phase** | M | 25% (L5-B; L5-D; L5-RM-6 likeliest) | Pre-flight audit declares effort band; mid-sub-phase checkpoint at 50% of upper band; T6 Sxx if exceeds upper +25% | Sub-phase actual >1.25× upper band → T6 Sxx + Strategic decision |
| 4 | **Conviction floor breach** (any field <0.90) | H | 10% | 3-field reporting at each sub-phase + every gate; binding constraint identification; T3 Sxx filing on breach | Aggregate <0.90 → sub-phase PAUSE + Strategic decision (DEFER/REVISE/ESCALATE) |
| 5 | **Out-of-distribution input encountered** | M | 15% (L5-D drawdown cells; L5-RM-6 regime trigger; L5-G shrinkage edge) | §2.3 empirical calibration callout; smoke-test BEFORE locking thresholds; T7 Sxx | Smoke-test empirical contradicts spec default by >2σ → T7 Sxx + threshold adjustment proposal |
| 6 | **Dependency drift** (Python/library version) | L | 5% | `uv.lock` pinned; `.python-version` pinned; pre-build `uv sync --frozen` + `pytest` baseline 602 PASS | uv.lock change OR Python version change during build → manual review required |
| 7 | **Build worktree contamination** | M | 10% | §7.5 enforcement; reviewer audit `git log` for cross-contamination at each ACCEPT | Any commit in `claude/layer-5-build` touching `LAYER_5_BUILD_SPEC.md` → AP-AUTH-44 violation + REVISE |
| 8 | **AP-AUTH violation slips past pre-commit** | M | 15% (without automation; <5% with §6.3 hooks) | Install pre-commit hooks per §6.3; pos+neg grep automation; strategic-review pos+neg grep audit at each ACCEPT | Any AP-AUTH violation found at Strategic review → T4 Sxx + REVISE |
| 9 | **Integration ordering deadlock** (dependency cycle) | L | 5% | §3 DAG topologically sorted; §3.2 spec-mandated C→D→E→F preserves determinism; no in-flight cross-sub-phase coordination | Any sub-phase requires data from later sub-phase to complete → architectural review (likely indicates spec misread; PAUSE) |
| 10 | **L5b OOS hardening preview risk** (early visibility) | M | 30% (block bootstrap empirical coverage in L5-E; structural break sensitivity at long horizons) | L5-E joint bootstrap σ + coverage_inflation_factor per S-6; L5b will harden further | L5-E `empirical_coverage_95 < 0.85` at any horizon → flag for L5b hardening priority |
| 11 | **HMM v2 retrain dependency** (per L3.5 Decision Lock; NAPMNOI re-source) | L | 5% (NOT in L5 scope but L5-RM-6 regime trigger depends on regime_state from HMM v1) | Spec §1.2 declares HMM v2 out-of-scope; L5 uses current `regime_state` field; if HMM v2 emerges mid-build, defer L5 changes to L6 | HMM v2 ETA <30 days from build start → PAUSE + Strategic review |
| 12 | **DMS source freshness drift** (per L5-RISK-8) | L | 5% (annual cadence; biennial smoke-test) | Decision Lock 15 + Q-resolution 7 backsolved; UBS GIRY 2026 anchor stable | New UBS GIRY edition materially differs from 6.5%/4.5% anchors → T5 Sxx + spec REOPEN candidate |

### §9.2 Cross-reference to spec §13 risk register (L5-RISK-1..8)

| Spec L5-RISK-N | Build mitigation | Build-phase artifact |
|---|---|---|
| L5-RISK-1 (calibrated_probability event mismatch) | S-2 + §3.3 schema + §5.RM-6.5 test #11 + §5.RM-6.1.1 build_event_labels dispatcher (v3 S-8) | L5-RM-6 verification report; AP-AUTH-41 v6 dual-grep |
| L5-RISK-2 (scalar Ridge cannot refit components) | S-3 + L5-B Task A penalized logistic; sequential Task A → RM-4 → RM-6 → Task B1 → Task B2 | L5-B Task A verification |
| L5-RISK-3 (Bayesian k_h unit inconsistency) | S-4 + W_REF_TARGET match ±2pp test #7 + AP-20 enforcement | L5-G verification; §2.5 audit #4 + #9 |
| L5-RISK-4 (drawdown 10Y cells overstate precision) | S-5 + Wilson 95% intervals + hierarchical pooling + cell-label policy | L5-D verification; §2.5 audit #8 |
| L5-RISK-5 (HAC/bootstrap undercoverage) | S-6 + block-size {h/4,h/2,h,2h} + bandwidth sensitivity + joint bootstrap σ + coverage_inflation | L5-B Task B1 verification; L5-E coverage report |
| L5-RISK-6 (λ path instability) | S-7 + Task B tests B8/B9 (lambda_log10_sd + sign_flip_rate) | L5-B Task B1 verification |
| L5-RISK-7 (recalibration trigger thrashing) | S-7 + 90d cooldown + coalescing + max 6/year + escalation 0.30→0.35 + Sxx escalation if frequency exceeds | L5-RM-6 verification |
| L5-RISK-8 (DMS source stale) | Decision Lock 15 biennial smoke-test + annual UBS GIRY review | L5-F verification + future L6 cadence |

### §9.3 Risk severity summary

| Severity | Count | Notes |
|---|---:|---|
| HIGH | 2 | #2 (RM-4 test regression; sub-phase-specific), #4 (conviction breach) |
| MEDIUM | 7 | #1, #3, #5, #7, #8, #10, #11 mostly |
| LOW | 3 | #6, #9, #12 |

**Top mitigation lever**: §6.3 pre-commit hook automation — would mitigate #8 (AP-AUTH violation slip) probability from 15% → <5%. **Strongly recommend installing at L5-A pre-flight.**

---

## §10 — Readiness verdict + final conviction

### §10.1 Conviction 3-field (this build plan)

| Field | Value | Reason |
|---|---|---|
| `conviction_statistical` | **0.95** | Spec is FROZEN at v6 (6-iteration convergence; 3 consecutive zero-Sxx cycles); Q-resolutions all locked; dependency graph + effort estimates match spec headlines; test contracts traceable |
| `conviction_operational` | **0.93** | Pre-commit hook automation proposal (§6.3) not yet implemented; build-worktree creation requires V/Strategic action; 4/4 mirror discipline at code level untested (only tested at spec level) |
| `conviction_actionability` | **0.96** | Ready-to-build plan with all 9 items addressed; sub-phase decomp + DAG + Sxx protocol + AP map + conviction cadence all concrete; Strategic can greenlight L5-A with this plan as the build contract |
| **Aggregate (MIN)** | **0.93** | **Binding: operational** (driven by pre-commit hook deferral + build worktree non-existence + 4/4 mirror discipline at code level being a new pattern) |

≥0.90 hard floor cleared.

### §10.2 Readiness verdict

**READY-WITH-CONDITIONS**

3 conditions for full READY-TO-BUILD upgrade:

| Condition | Owner | Effort |
|---|---|---|
| **C1**: Create `claude/layer-5-build` worktree at `D:/macro_pipeline/.claude/worktrees/layer-5-build` from `main` @ `590e4a5` | V or Strategic | <5 min |
| **C2**: Install §6.3 pre-commit hooks (`validate_no_cumulative_arithmetic.py` + `validate_dual_grep_in_verification.py`) before L5-A pre-flight kickoff | Track A at L5-A pre-flight start | ~0.5h |
| **C3**: Strategic + V approve this build plan v1; either as-is OR with revisions before L5-A pre-flight kickoff | Strategic + V | review-time only |

Upon C1+C2+C3 satisfied → **READY-TO-BUILD** verdict; L5-A pre-flight begins.

### §10.3 Strategic-decision routing

| Outcome | Strategic action | Effect |
|---|---|---|
| Greenlight as-is | C2 + C3 satisfied; C1 V/Strategic action queued | Track A proceeds to L5-A pre-flight (separate prompt) |
| Greenlight with revisions | Strategic edits this plan; Track A re-commits revision v2 | Iterate to v2; same gates |
| Escalate to ChatGPT 5.5 build-plan review | Build-plan-review prompt to ChatGPT 5.5; await verdict | Pause L5-A kickoff until ChatGPT 5.5 ACCEPT; mirrors v6 closure pattern |

V's prompt explicitly gates escalation on: conviction <0.90 on plan OR effort estimate >100h OR critical-path uncertainty flagged. **Current state**: conviction 0.93 ≥ 0.90; effort 71.5h (mid-band) < 100h; critical path identified with no uncertainty flagged. **Escalation NOT recommended.**

---

**END — L5_BUILD_PLAN_v1.md**
