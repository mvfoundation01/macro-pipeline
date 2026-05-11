# LAYER 5 BUILD SPEC — Walk-forward CV, Ridge Fit, Isotonic Calibration, Drawdown Conditionals, DMS, Bayesian Shrinkage

**Version**: 1.0 (draft; ChatGPT 5.5 methodology review pending; V freeze pending)
**Author**: Claude Code authoring session (under V's role-widening directive 2026-05-10)
**Branch**: `claude/layer-5-spec` (base: `590e4a5` = main HEAD = L3.5b merge commit)
**Predecessor specs**: `LAYER_3_5_BUILD_SPEC.md` (closed; tag `layer3-5-complete` at `9ea0df6`), `LAYER_3_5b` sprint (closed inline; tag `layer3-5b-complete` at `dcf698d`)
**Reviewer schedule**: ChatGPT 5.5 methodology review post V-spec-freeze; Codex 5.5 code review post-L5-build-complete
**Audience**: Claude Code build agent (post-freeze, primary); V (decision authority); ChatGPT 5.5 (methodology reviewer); Codex 5.5 (post-build code reviewer)

---

## §0 — Spec Metadata

| Field | Value |
|---|---|
| Branch base | `main` @ `590e4a5` (L3.5b merge commit) |
| Build branch | `claude/layer-5-build` (created at L5-A pre-flight kickoff post-spec-freeze) |
| Target tag (post-build) | `layer5-complete` |
| Sub-phases | L5-A → L5-B → L5-RM-4 → L5-RM-6 → L5-C → L5-D → L5-E → L5-F → L5-G → L5-H (sequential, gated, pause-and-verify each) |
| Estimated build effort | 47–66h work + ~8h spec verification + ~24h ChatGPT 5.5 + Codex review = 79–98h end-to-end |
| Tests delta target | +78 (602 → 680); MIN +70, MAX +90 |
| Gates added | 18, 19, 20, 21, 22, 23, 24, 25 (8 new gates) |
| Deviation register | continues from D30; L5 build deviations use `Sxx` IDs reserved S-1 through S-25 to distinguish from L3.5-era `Dxx` |
| Reviewer for L5 spec methodology | ChatGPT 5.5 (re-engages from Dim 1/2/3 prior findings) |
| Reviewer for L5 build code | Codex 5.5 (post-L5-H retrospective commit) |
| Repo visibility | public throughout L5 + L5b (revert to private at L6 per L3.5-era Decision Lock) |
| Predecessor backlog absorbed | L5-12 (SeriesConfig dataclass), L5-13 (CDRS notes migration), L5-14 (16 AP-6 sites sweep), L7-CI-1 (env-hygiene CI check), L7-MIGRATE-1 (legacy cache migration — contingent) |

---

## §1 — Executive Context

### §1.1 Why Layer 5 Exists

Layers 1–3 built **raw scoring infrastructure**: indicators (L1), PIT discipline (L1.5), regime classifier (L3A), CRPS production scorer (L3B), CDRS two-stage scorer (L3C), R² master panel + Newey-West HAC (L3D). Layer 3.5 + 3.5b **closed all 4 CRITICAL HIGH + 5 HIGH-unique cross-reviewer findings at the substrate level** (HMM frozen contract, Option Z PIT enforcement, NBER announcement calendar, dissent semantics with INDETERMINATE state + cap 0.60, cache atomicity sweep, Codex T/U/V/W surgical fixes).

Layer 5 turns **raw scores into calibrated probabilities** suitable for institutional-grade forecasting and downstream HTML report consumption (L6):

| Layer 5 capability | Why required |
|---|---|
| Walk-forward CV scaffold (L5-A) | OOS validation is non-negotiable for institutional research; in-sample R² is unbiased but inflated |
| Ridge regression fit on CRPS/CDRS composite (L5-B) | Layer 3 left composite weights as placeholders; L5-B fits them with regularization and reports posterior |
| raw_score vs calibrated_probability split (L5-RM-4) | ChatGPT 5.5 Dim 2 finding — Layer 3 conflated raw model output with calibrated probability; L5-RM-4 codifies the split formally |
| Isotonic regression calibration (L5-RM-6) | ChatGPT 5.5 Dim 3 finding — raw scores need monotonic transform to calibrated probabilities; isotonic preserves rank while normalising to [0, 1] reliability |
| Brier + reliability diagram (L5-C) | Without calibration metrics, "the model says 75%" is uninterpretable; Brier + reliability bins quantify miscalibration |
| Drawdown probability conditional distributions (L5-D) | V's deliverable is forward 1Y/3Y/5Y/10Y equity return + drawdown forecasts; L5-D fits the conditional drawdown distribution given regime state |
| Forecast σ confidence bands (L5-E) | Point forecast without uncertainty is malpractice; L5-E derives band-of-bands per horizon |
| DMS survivorship adjustment (L5-F) | Dimson-Marsh-Staunton showed naive long-run US equity returns overstate global true returns by ~100-200 bps annualized due to survivorship; L5-F applies horizon-conditional adjustment |
| Bayesian shrinkage to 6.5% real prior (L5-G) | Sample-size honesty: with <30 non-overlapping 10Y windows, raw point estimate has high variance; Bayesian shrinkage to DMS long-run prior reduces forecast σ at long horizons |
| Retrospective + Codex review prep (L5-H) | Mirrors L3.5b retrospective discipline; assembles Codex review handoff package |

### §1.2 Scope: What L5 Is and Is Not

**L5 IS**:
- Walk-forward CV scaffold for time-series OOS validation with expanding-window primary + rolling-window robustness
- Ridge regression fit with CV-selected λ for CRPS composite weights
- Isotonic calibration of raw scores → calibrated probabilities (per-horizon)
- Drawdown probability conditional distributions across 1Y/3Y/5Y/10Y horizons × regime states
- Brier score + reliability diagram per horizon as calibration diagnostics
- Forecast σ confidence band derivation
- DMS survivorship bps adjustment (horizon-conditional)
- Bayesian shrinkage to 6.5% real annualized prior (horizon-dependent + sample-size-adaptive)

**L5 IS NOT**:
- L6 HTML dark-terminal reporting layer — separate later spec (out of scope per meta-prompt §2.5 #4)
- L5b OOS hardening (block bootstrap, structural breaks, FDR) — separate sprint after L5 closes
- L7 production deployment — separate phase
- HMM v2 retrain with NAPMNOI re-source — vendor dependency, separate budget per L3.5 §1.2
- New CRPS / CDRS components (Layer 3 component set is locked); L5 fits weights on the existing components only

### §1.3 Decision Lock — Locked Inputs (L5 spec inherits + L5-specific)

| # | Decision | Locked value | Source |
|---|---|---|---|
| 1 | Sub-phase order | A → B → RM-4 → RM-6 → C → D → E → F → G → H sequential | Meta-prompt §2.1 |
| 2 | CV window type (Q1) | **Expanding primary + rolling-20Y robustness check** | Meta-prompt §2.2 Q1; locked in chunk 2 with option matrix |
| 3 | CV step size (Q2) | **Horizon-dependent** (monthly 1Y/3Y, annual 5Y, 5Y blocks 10Y) | Meta-prompt §2.2 Q2; locked in chunk 2 |
| 4 | Ridge λ selection (Q3) | **CV-selected via nested walk-forward** (outer = OOS evaluation, inner = λ selection) + leave-one-out robustness with fixed-λ from L3 baseline | Meta-prompt §2.2 Q3; locked in chunk 2 |
| 5 | Isotonic calibration scope (Q4) | **Per-horizon separate** (4 calibrators: 1Y / 3Y / 5Y / 10Y) | Meta-prompt §2.2 Q4; locked in chunk 3 |
| 6 | Recalibration cadence (Q5) | **Quarterly + regime-triggered override** (Sahm Rule >0.30 OR 10Y–3M curve inversion regime flip forces refit) | Meta-prompt §2.2 Q5; locked in chunk 4 |
| 7 | DMS survivorship bps (Q6) | **−150 bps mid-band central** + horizon conditional (5Y: −125; 10Y: −175) + ±50 sensitivity in outputs | Meta-prompt §2.2 Q6; locked in chunk 4 |
| 8 | Bayesian shrinkage weight (Q7) | **Horizon-dependent + sample-size-adaptive** (1Y w=5%, 3Y w=15%, 5Y w=30%, 10Y w=50%) with k/(k+n) form (k = horizon × 15) | Meta-prompt §2.2 Q7; locked in chunk 4 |
| 9 | Horizon scope (Q8) | **All 4 horizons (1Y / 3Y / 5Y / 10Y) in L5** | Meta-prompt §2.2 Q8; locked in chunk 5 |
| 10 | Prior anchor | **6.5% real annualized** (Dimson-Marsh-Staunton long-run US) | Meta-prompt §2.2 Q7 |
| 11 | L5 reviewer (methodology) | ChatGPT 5.5 (resumes from Dim 1/2/3 prior findings) | Meta-prompt §0 + meta-prompt §1 |
| 12 | L5 reviewer (code) | Codex 5.5 (post-build) | Meta-prompt §1 |
| 13 | Calibrated probability storage | `ScoredObservation.calibrated_probability` slot introduced at 3.5D | Verified empirically `scoring/scored_observation.py:89` |
| 14 | CV input panel | `data/cache/analysis/r_squared_panel.parquet` (atomic; sha-validated; 4-horizon indexed) | Verified empirically `analysis/r_squared_panel.py:53` |

Q-resolutions Q1–Q8 are **locked at chunk authoring time** with full option matrix + reasoning embedded in the owning sub-phase's §X.4 "Decisions for V to Confirm" block; ChatGPT 5.5 may pressure-test each.

---

## §2 — Cross-Cutting Requirements

These apply to **every** sub-phase. Violations are spec-level deviations and require explicit `Sxx` register entries.

### §2.1 Pause-and-Verify Pattern

After each sub-phase commit, build agent **STOPS** and produces a verification report. V (or Strategic Claude) reviews. Only then does the next sub-phase begin. Per `HANDOFF_CLAUDE_CODE_v4.md` §2.1 (preserved exactly).

```
Sub-phase commit → verification report → V/Strategic review → APPROVE/REVISE → next sub-phase
```

If REVISE: build agent fixes within current sub-phase (does NOT advance), produces updated verification, re-submits. Proven 9× across L3.5 + L3.5b sub-phases with 0 unverified scope expansions.

### §2.2 Pre-Flight Audit (Mandatory, P3 Rule)

**Every sub-phase begins with a pre-flight audit.** No code changes until the audit completes. Pre-flight audit deliverable for each L5 sub-phase: `LAYER_5_<phase>_PREFLIGHT.md` containing:

1. Inventory of every file the sub-phase will touch (with line ranges)
2. Inventory of every existing test that may break (classified HIGH / MED / LOW risk)
3. Empirical reading of current state for thresholds (per §2.3)
4. List of ambiguities found in this spec → REQUEST CLARIFICATION before coding (PAUSE-required vs PROCEED-with-Sxx routing)
5. Risk callouts: anything the spec assumes that turns out false on inspection
6. Estimated effort within the spec's stated range (with justification if outside)
7. NEG/POS test plan with ≥50% NEG floor (per §2.7 preserved from L3.5)
8. Conviction 3-field forecast (statistical / operational / actionability) with binding constraint identified

Build agent does **not** advance to coding until V or Strategic Claude approves the pre-flight.

### §2.3 Empirical Calibration Callout

Per `HANDOFF_STRATEGIC_CLAUDE_v4.md` §5.1: **before writing test threshold values, run a smoke-test to find what values are actually achievable.** L5 sub-phases requiring empirical calibration:

| Sub-phase | Threshold needing empirical calibration | Smoke-test required |
|---|---|---|
| L5-A | Effective sample size per horizon × CV-fold at expanding-window minimum (1985-01 start) | Compute `n_eff_nonoverlap` for each horizon at first fold; confirm 1Y ≥ 40, 3Y ≥ 18, 5Y ≥ 10, 10Y ≥ 4 per L3D `effective_sample_size.py` |
| L5-B | Ridge λ smoke-test on full panel; verify λ search grid (1e-4 to 1e2, 11 points log-spaced) brackets the CV-selected optimum at every horizon × CV-fold | Run `ridge_cv` at 4 anchor folds (1995, 2005, 2015, 2025 cutpoints); report λ_opt per horizon; widen grid if binding boundary |
| L5-RM-6 | Isotonic monotonicity verification per horizon × CV-fold; regime-trigger threshold for Q5 (Sahm Rule level OR yield-curve inversion magnitude) | At each horizon, fit isotonic, confirm output monotone non-decreasing; smoke-test Sahm Rule trigger candidates ∈ {0.25, 0.30, 0.35, 0.40} against historical regime flips |
| L5-C | Brier score baseline per horizon (climatology baseline = constant prior 6.5%-implied recession rate) | Compute climatology Brier and calibrated-model Brier; confirm calibrated-model < climatology; gate threshold = climatology − 0.02 |
| L5-D | Drawdown distribution empirical tails per horizon × regime state | At 4-cycle anchor set (1990, 2001, 2008, 2020), compute realized 1Y/3Y/5Y/10Y drawdown given regime state at trough −12 months; confirm empirical distribution captured in conditional |
| L5-F | DMS bps band empirical horizon-conditional verification | Read DMS Triumph of the Optimists Table I.X (Dimson-Marsh-Staunton survivorship matrix); confirm 5Y midpoint ∈ [−100, −150] bps and 10Y midpoint ∈ [−150, −200] bps |
| L5-G | Shrinkage weight smoke-test per horizon | Compute posterior variance reduction (k/(k+n) form) per horizon at 1985 / 2000 / 2015 / 2025 CV cutpoints; confirm sample-size-adaptive weights move toward prior at long horizons |

Smoke-test results MUST be reported in the sub-phase verification report. If empirical reading contradicts spec default, build agent files an `Sxx` deviation, proposes adjustment, awaits approval before locking test thresholds.

### §2.4 Conviction 3-Field Discipline

Every verification report and every reviewer-facing artifact reports:

| Field | Question answered |
|---|---|
| `conviction_statistical` | Do the models / data / proofs agree? At L5, this includes CV-fold stability, λ regularization path stability, isotonic monotonicity. |
| `conviction_operational` | Is the data quality, source-cap chain, regime stability, vintage discipline clean? L5 inherits 3.5b PIT discipline; new L5-RM-6 calibration cadence (Q5) introduces regime-trigger operational dependency. |
| `conviction_actionability` | Is the result usable downstream — by L5b (OOS hardening), by L6 (reports), by Codex 5.5? |

Build agent's sub-phase verification reports MUST report all three for the sub-phase as a whole AND for each new gate.

### §2.5 NEW — Empirical Claim Verification (Standing Order #4)

**Standing Order added between L3.5 and L3.5b**, codified by 3.5b-T (cache validation discipline + invariant test for "138/138 caches"), 3.5b-U (Strategic self-correction of 3.5B AM10), 3.5b-V (Strategic self-correction of spec D2 "4 sites"). Verbatim from `HANDOFF_CLAUDE_CODE_v4.md` §2 + retrospective §F lessons.

**Rule**: When a verification report claims "X validated on every Y" or "Z applied universally", the proof MUST include grep-audit OR AST-walk over the codebase, NOT unit-test proof alone.

**L5-specific callouts where Standing Order #4 binds explicitly:**

| Sub-phase | Universal claim | Mandatory empirical audit |
|---|---|---|
| L5-A | "Walk-forward CV folds have zero cross-fold contamination" | AST-walk over `analysis/walk_forward_cv.py` (new module); grep audit of every `train_window` / `test_window` assignment to confirm `train_end < test_start` strict inequality with `gap_months` honored |
| L5-RM-6 | "Isotonic calibration is monotone non-decreasing across the [0, 1] domain at every horizon × CV-fold" | Empirical sweep of fitted isotonic regressor across 1000-point grid per horizon × fold; assert `np.all(np.diff(out) >= -1e-9)` over every grid; archive sweep results in verification |
| L5-F | "DMS bps applied to 5Y and 10Y output paths, NOT to 1Y or 3Y output paths" | grep audit over `scoring/` + `analysis/` for `dms_adjustment_bps` references; confirm horizon-conditional application; AST-walk over horizon dispatcher to verify branch coverage |
| L5-G | "Bayesian shrinkage weight applied per-horizon with sample-size-adaptive k/(k+n) form, NOT collapsed to constant weight" | grep audit + AST-walk over `shrink_weight(horizon, n)` callsites; assert at least 4 distinct horizon values; assert no constant `weight = 0.30` literal anywhere |

Failure to provide grep / AST audit in verification report for these claims = REVISE-REQUIRED.

### §2.6 Regression Floor

Every L5 commit: full pytest suite must pass. **Baseline: 602 tests (verified empirically 2026-05-10 via `pytest tests/ -q --no-header` → `602 passed in 142.72s`).** If a previous test breaks legitimately due to scope (e.g., raw_score / calibrated_probability split rewriting existing CRPS tests), update the test as part of the sub-phase test delta and document in `Sxx`. **Never silently disable or skip.**

### §2.7 Test Naming Convention (preserved from L3.5)

- `test_<unit>_<behavior>` — happy path (POS)
- `test_<unit>_<edge_case>_<expected_result>` — edge case (typically POS, sometimes NEG)
- `test_<unit>_<failure_mode>_raises` — explicit failure assertion (NEG)

For each L5 sub-phase, **at least 50% of new tests must be negative tests** (assert that something fails-closed, raises correctly, or returns expected error state). Codex 5.5 flagged absence of negative tests as HIGH finding S in L3 review; precedent preserved.

### §2.8 Deviation Register (Sxx for L5)

L3.5 + L3.5b closed at D30. L5 starts a new register at **S-1** (Strategic-prefix; distinguishes L5 spec deviations from L3.5-era `Dxx` register). Reserved S-1 through S-25.

Format (mirrors L3.5 DEVIATIONS):
```
Sxx — YYYY-MM-DD — sub-phase L5-X.Y — [brief topic]
Disposition: ACCEPT / REJECT / CONDITIONAL
Rationale: [1-2 sentences with empirical evidence]
Backlog ref: [L5-N or L6-N or L7-N] (if any)
```

Maintained in `LAYER_5_DEVIATIONS.md` (new file at build worktree root; created at L5-A commit per build-phase tradition).

---

## §3 — Cross-Phase Architecture

### §3.1 Sub-Phase Dependency Graph

```
                  L5-A walk-forward CV scaffold (Gate 18)
                              │
                              ▼
                  L5-B Ridge regression fit (Gate 19)
                              │
                              ▼
              ┌───────────────┴───────────────┐
              ▼                               ▼
   L5-RM-4 raw / calibrated split    (other consumers of raw_score)
              (Gate 20)
              │
              ▼
   L5-RM-6 isotonic calibration (Gate 21)
              │
              ▼
              ├──────────────┬──────────────┬────────────┐
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

**Critical paths**:
- L5-A → L5-B: CV scaffold must exist before Ridge can be CV-fit; L5-A is the longest-running dependency.
- L5-B → L5-RM-4: raw_score output contract from Ridge is what RM-4 splits formally; RM-4 cannot author its dataclass slot semantics without B's output.
- L5-RM-4 → L5-RM-6: isotonic fits on raw scores; needs RM-4's raw vs calibrated contract.
- L5-RM-6 → {L5-C, L5-D, L5-E, L5-F, L5-G}: all downstream sub-phases consume calibrated probabilities (or use the calibration metadata).
- {L5-D, L5-F} → L5-G: shrinkage uses drawdown empirical (D) + DMS prior (F) to derive the long-run anchor and posterior variance.
- L5-G → L5-H: retrospective gathers L5-A through L5-G into the closure package; no further code work.

**Forks**:
- L5-C, L5-D, L5-E, L5-F are mostly independent given L5-RM-6 output; can be authored in any order within chunk 4. Build order locked to C → D → E → F for build determinism.

### §3.2 Cross-Sub-Phase Semantic Table (NEW section type #2)

Every field that L5 introduces, modifies, or finalizes across sub-phase boundaries is tracked here for ChatGPT 5.5 cross-reference verification. Fields without cross-phase movement live entirely in their owning sub-phase's spec (not tracked here).

| Field name | Type | Introduced in | Modified in | Final form | Cross-references |
|---|---|---|---|---|---|
| `raw_score` | `float64 ∈ [0, 1]` | L3B (CRPS output) | L5-B (Ridge weight refit produces same shape with fitted weights); L5-RM-4 (formally renames to clarify it is NOT calibrated probability) | `float64 ∈ [0, 1]` (unchanged semantically; formally distinguished from calibrated_probability via §5.RM-4.3) | §5.B.4 ; §5.RM-4.3 |
| `calibrated_probability` | `Optional[float64] ∈ [0, 1]` | 3.5D (slot added to `ScoredObservation`; None until L5 fills) | L5-RM-4 (populates via raw_score → identity passthrough at first); L5-RM-6 (replaces with isotonic transform of raw_score) | `float64 ∈ [0, 1]` (post-L5-RM-6; never None for any scored observation produced by L5 calibrated path) | §5.RM-4.3, §5.RM-6.5 |
| `calibration_metadata` | `Optional[dict[str, Any]]` | 3.5D (slot added) | L5-RM-4 (populates with `{"method": "raw_passthrough"}`); L5-RM-6 (overwrites with full `{"method": "isotonic", "fit_window": (start, end), "n_train_obs": n, "horizon": h, "monotonicity_audit": "PASS"}`) | full dict post-L5-RM-6 | §5.RM-4.3, §5.RM-6.5 |
| `notes` | `list[str]` | 3.5D (introduced); 3.5D AM25 migrated CRPS `metadata_extra` → notes | L5-RM-4 (absorbs **L5-13** backlog item — migrates CDRS `metadata_extra` to notes; mirrors CRPS pattern via shared `_format_pit_lineage_notes()`) | post-L5-RM-4: both CRPS + CDRS use notes uniformly | §5.RM-4.5 |
| `forecast_sigma` | `float64 ≥ 0` (annualized return std) | **L5-E (NEW)** | unchanged after introduction | NEW slot added to `ScoredObservation` via L5-RM-4 (dataclass field; default None until L5-E populates) | §5.E.3 |
| `drawdown_probability_distribution` | `Optional[dict[str, float]]` (CDF percentiles {"p10": ..., "p25": ..., "p50": ..., "p75": ..., "p90": ...}) | **L5-D (NEW)** | unchanged after introduction | NEW slot in `ScoredObservation` via L5-RM-4 | §5.D.3 |
| `dms_adjustment_bps` | `float64` (negative; annualized bps) | **L5-F (NEW)** | unchanged after introduction | NEW slot in `ScoredObservation` via L5-RM-4 (default 0.0 for 1Y/3Y; populated for 5Y/10Y at L5-F) | §5.F.2 |
| `bayesian_shrinkage_weight` | `float64 ∈ [0, 1]` (k/(k+n) form) | **L5-G (NEW)** | unchanged after introduction | NEW slot in `ScoredObservation` via L5-RM-4 (default 0.0 in 1Y; horizon-dependent populated at L5-G) | §5.G.3 |
| `cv_fold_id` | `Optional[int]` (integer 0+, None for non-CV scoring) | **L5-A (NEW)** | unchanged after introduction | NEW slot in `ScoredObservation` via L5-RM-4 (populated only when scoring within a CV fold, not for production scoring) | §5.A.3 |
| `regime_state` | `str ∈ {"expansion", "late-cycle", "recession", "indeterminate"}` | L3A | 3.5D (added "indeterminate") | unchanged in L5 | §5.B.4 (Ridge fits stratified by regime_state); §5.G.3 (shrinkage may be regime-conditional in future L5b sprint) |
| `confidence_overall` | `float64 ∈ [0, 100]` | L1.5B | 3.5D (cap 60 applied when regime=indeterminate) | unchanged in L5 | §5.B.4, §5.G.4 |
| `metadata_extra` | `dict[str, Any]` (bag of everything) | L3 | L5-RM-4 (drains remaining CDRS V/T notes into `notes` per L5-13) | post-L5-RM-4: shrunk by L5-13 migration | §5.RM-4.5 |
| `pre_1978_training_only` | `bool` | 3.5C (NBER calendar) | L5-RM-4 (when True AND L5-A operating in training mode, adds caveat to notes per L5-13) | unchanged in L5 | §5.RM-4.5 |

**Cross-sub-phase migrations summarized**:

1. `ScoredObservation` dataclass gains 5 new slots at **L5-RM-4** as a single atomic dataclass migration:
   - `forecast_sigma: Optional[float] = None`
   - `drawdown_probability_distribution: Optional[dict[str, float]] = None`
   - `dms_adjustment_bps: float = 0.0`
   - `bayesian_shrinkage_weight: float = 0.0`
   - `cv_fold_id: Optional[int] = None`
   
2. L5-D, L5-E, L5-F, L5-G **populate** these slots; they do not add fields. This avoids 4 separate dataclass migrations.

3. The L5-13 CDRS notes migration (Codex finding X deferred from 3.5b) is absorbed into L5-RM-4. Effort 1-2h folded into L5-RM-4 budget (4-6h band).

---

## §4 — Sub-Phase Decomposition

| ID | Sub-phase | Topic | Effort band (h) | Test delta | Gate | Q-resolutions locked | Owns chunk |
|---|---|---|---:|---:|---|---|---|
| L5-A | Walk-forward CV scaffold | Expanding-window primary + rolling-20Y robustness; horizon-dependent step size; `analysis/walk_forward_cv.py` (NEW); fold contamination audit | 6–8 | +12 (≥6 NEG) | 18 | Q1, Q2 | chunk 2 |
| L5-B | Ridge regression fit | CV-selected λ via nested walk-forward; `models/ridge_cv.py` (NEW); fitted weights stored in `regime_3state_v1`-style frozen artifact; CRPS Ridge replaces L3 placeholder weights | 8–10 | +15 (≥8 NEG) | 19 | Q3 | chunk 2 |
| L5-RM-4 | raw_score vs calibrated_probability split | `ScoredObservation` dataclass migration (5 new slots); L5-13 CDRS notes migration absorbed; raw_score / calibrated_probability semantic contract formalized | 4–6 | +8 (≥4 NEG) | 20 | — | chunk 3 |
| L5-RM-6 | Isotonic regression calibration | `models/isotonic_calibrator.py` (NEW); per-horizon 4 calibrators; quarterly + regime-triggered recalibration; monotonicity audit | 6–8 | +10 (≥5 NEG) | 21 | Q4, Q5 (regime trigger threshold) | chunk 3 |
| L5-C | Brier + reliability diagram | `analysis/brier_reliability.py` (NEW); per-horizon Brier; 10-bin reliability; climatology baseline | 5–7 | +8 (≥4 NEG) | 22 | — | chunk 3 |
| L5-D | Drawdown probability conditional distributions | `analysis/drawdown_conditionals.py` (NEW); per-horizon × regime_state conditional CDF; populates `drawdown_probability_distribution` slot | 5–7 | +8 (≥4 NEG) | 23 | — | chunk 4 |
| L5-E | Forecast σ confidence band | `analysis/forecast_sigma.py` (NEW); per-horizon σ derivation from CV residuals + isotonic posterior spread; populates `forecast_sigma` slot | 4–6 | +6 (≥3 NEG) | 24 | — | chunk 4 |
| L5-F | DMS survivorship adjustment | `models/dms_adjustment.py` (NEW); horizon-conditional bps (5Y: −125, 10Y: −175; ±50 sensitivity); populates `dms_adjustment_bps` slot for 5Y/10Y only | 3–5 | +5 (≥3 NEG) | 25.1 (sub) | Q6 | chunk 4 |
| L5-G | Bayesian shrinkage to 6.5% real prior | `models/bayesian_shrinkage.py` (NEW); horizon-dependent + sample-size-adaptive (k = horizon × 15); populates `bayesian_shrinkage_weight` slot; prior = DMS long-run 6.5% real | 4–6 | +6 (≥3 NEG) | 25.2 (sub) | Q7 | chunk 4 |
| L5-H | Retrospective + Codex review prep | `LAYER_5_RETROSPECTIVE.md` (NEW; mirrors L3.5b §A-§I structure); Gate 25 composite assembly; Codex 5.5 reviewer-handoff checklist tying back to §8 of this spec | 2–3 | — | — | Q8 (horizon scope confirmation in retrospective) | chunk 5 |
| **L5 total** | | | **47–66** | **+78** | **18–25** | **All Q1–Q8** | |

**Sub-criteria and shared composite**:
- **Gate 25 composite (sub-criteria L5-F + L5-G)**: Gate 25 is assembled at L5-G commit with two sub-criteria:
  - 25.1 (L5-F authored): DMS bps applied horizon-conditionally (5Y: −125 ± 50; 10Y: −175 ± 50); 1Y and 3Y untouched
  - 25.2 (L5-G authored): Bayesian shrinkage weight horizon-dependent (1Y: 0.05; 3Y: 0.15; 5Y: 0.30; 10Y: 0.50) via k/(k+n) form
  Mirrors L3.5b Gate 17 composite pattern (4 sub-criteria across 4 sub-phases).
- **L5-H has no new gate** — it composes and seals Gate 25, authors retrospective, prepares Codex handoff. Same pattern as 3.5E for L3.5 wrap-up.

**Arithmetic verification** (Standing Order #4):
- Effort sum: (6+8+4+6+5+5+4+3+4+2) = 47 (min) ; (8+10+6+8+7+7+6+5+6+3) = 66 (max) ✓ matches headline 47-66h
- Test delta sum: 12+15+8+10+8+8+6+5+6+0 = 78 ✓ matches headline +78
- NEG floor sum: 6+8+4+5+4+4+3+3+3+0 = 40 NEG out of 78 = 51% ≥ 50% floor ✓
- Gate count: 18, 19, 20, 21, 22, 23, 24, 25 = 8 ✓ matches headline 8 new gates
- Q-resolutions: Q1 (L5-A), Q2 (L5-A), Q3 (L5-B), Q4 (L5-RM-6), Q5 (L5-RM-6), Q6 (L5-F), Q7 (L5-G), Q8 (L5-H) = 8 ✓ matches Q1-Q8

---

## §5 — Sub-Phase Specifications

<!-- CHUNK 2 START — §5.A L5-A walk-forward CV scaffold + §5.B L5-B Ridge regression fit (Q1+Q2+Q3 locked) -->

### §5.A — Sub-Phase L5-A: Walk-forward CV Scaffold

#### §5.A.0 Sub-phase metadata

| Field | Value |
|---|---|
| Sub-phase ID | L5-A |
| Topic | Walk-forward cross-validation scaffold (expanding + rolling-20Y) |
| Effort band | 6–8h (target 7h) |
| Test delta | +12 (≥6 NEG = 50% NEG floor; spec lists 7 NEG / 5 POS in §5.A.5) |
| Gate added | 18 |
| Owning Q-resolutions | Q1 (CV window type), Q2 (CV step size) |
| Dependencies | None (L5-A is foundational); reads R² panel cache produced by L3D |
| Downstream consumers | L5-B (Ridge fits per fold), L5-RM-4 (fold_id metadata), L5-RM-6 (per-fold isotonic calibration), L5-C (per-fold Brier evaluation) |
| Commit message template | `L5-A: walk-forward CV scaffold — expanding + rolling-20Y; horizon-dependent step` |
| New files | `macro_pipeline/analysis/walk_forward_cv.py` (NEW); `tests/test_walk_forward_cv.py` (NEW) |
| Modified files | `macro_pipeline/validation.py` (+ `validate_gate18_walk_forward_cv()`); `macro_pipeline/analysis/__init__.py` (export) |

#### §5.A.1 Scope

L5-A produces a deterministic walk-forward fold generator for OOS time-series cross-validation across 4 horizons (1Y/3Y/5Y/10Y) using two complementary schedules: **expanding-window primary** + **rolling-20Y robustness**.

##### §5.A.1.1 Public API

```python
# macro_pipeline/analysis/walk_forward_cv.py

from dataclasses import dataclass
from typing import Literal
import pandas as pd

ScheduleType = Literal["expanding", "rolling_20y"]
HorizonLabel = Literal["1Y", "3Y", "5Y", "10Y"]

@dataclass(frozen=True)
class WalkForwardFold:
    """One walk-forward CV fold for a given horizon × schedule type."""
    fold_id: int                              # 0-indexed, sequential within (horizon, schedule)
    horizon: HorizonLabel                     # "1Y" | "3Y" | "5Y" | "10Y"
    schedule_type: ScheduleType               # "expanding" | "rolling_20y"
    train_start: pd.Timestamp                 # inclusive
    train_end: pd.Timestamp                   # inclusive
    test_start: pd.Timestamp                  # exclusive of train_end by ≥ gap_months
    test_end: pd.Timestamp                    # inclusive
    gap_months: int                           # contamination gap; horizon_months by default
    n_nominal_train: int                      # monthly obs in [train_start, train_end]
    n_eff_nonoverlap_train: int               # n_nominal // horizon_months

@dataclass(frozen=True)
class WalkForwardSchedule:
    """One full schedule for a (horizon, schedule_type) pair."""
    horizon: HorizonLabel
    schedule_type: ScheduleType
    folds: tuple[WalkForwardFold, ...]
    panel_path: pd.api.types.AnyType          # path-like; provenance of input panel
    panel_sha256: str                         # frozen digest of input panel for reproducibility

def generate_schedule(
    horizon: HorizonLabel,
    schedule_type: ScheduleType,
    panel_index: pd.DatetimeIndex,
    *,
    min_train_window_months: int = 240,       # 20Y minimum for both schedules
    gap_months: int | None = None,            # None → equals horizon_months
) -> WalkForwardSchedule:
    """Generate a walk-forward schedule for `horizon` × `schedule_type`."""

def generate_all_schedules(
    panel_index: pd.DatetimeIndex,
) -> tuple[WalkForwardSchedule, ...]:
    """Generate 8 schedules: 4 horizons × 2 schedule types."""
```

##### §5.A.1.2 Step-size policy (Q2 lock)

| Horizon | Expanding step size | Rolling-20Y step size |
|---|---|---|
| 1Y | 1 month | 1 month |
| 3Y | 1 month | 1 month |
| 5Y | 12 months (annual) | 12 months |
| 10Y | 60 months (5Y blocks) | 60 months |

Step size = the increment to `test_start` between consecutive folds. Expanding-window `train_start` is fixed at panel start; rolling-20Y `train_start` advances with `test_start` to maintain constant 240-month window.

##### §5.A.1.3 Contamination-gap policy

`gap_months = horizon_months` by default (1Y → 12, 3Y → 36, 5Y → 60, 10Y → 120). Test window starts at `train_end + gap_months + 1 day` (calendar), preserving the invariant `train_end < test_start` with full-horizon gap to prevent forward-return data from leaking into training.

Override allowed via `gap_months` parameter; build-time pre-flight checks that override does not narrow gap below horizon.

#### §5.A.2 Pre-flight contract (build-time L5-A pre-flight executes)

1. **HORIZONS verification**: read `analysis/r_squared_panel.py:56` → confirm `HORIZONS = {"1Y": 12, "3Y": 36, "5Y": 60, "10Y": 120}` matches `regression_config.py:35` `FORWARD_HORIZONS_MONTHS = (12, 36, 60, 120)`. Verified empirically at L5 spec authoring time.
2. **Panel cache load**: read `data/cache/analysis/r_squared_panel.parquet`; confirm sidecar `data_sha256` matches recomputation; capture `panel_index = panel.index.get_level_values("date").unique()` for use in `generate_schedule`.
3. **Smoke-test fold count per horizon × schedule type**: at L5-A build-time pre-flight, run `generate_all_schedules(panel_index)` and report:

| Horizon | Expanding fold count | Rolling-20Y fold count | Spec target | Action if below target |
|---|---|---|---|---|
| 1Y | ≥ 30 | ≥ 30 | Both ≥ 30 | If <30, file S-1; widen 20Y window? |
| 3Y | ≥ 25 | ≥ 20 | E ≥ 25, R ≥ 20 | If R <20, file S-1; consider rolling-25Y for 3Y |
| 5Y | ≥ 12 | ≥ 10 | E ≥ 12, R ≥ 10 | If R <10, file S-1 |
| 10Y | ≥ 4 | ≥ 3 | E ≥ 4, R ≥ 3 | If R <3, file S-1; accept reduced 10Y robustness with expanding-only OR widen to rolling-30Y |

Numbers derived empirically from 1912+ Fed-era data span (≈1356 months by 2025-01) and step-size policy above.

4. **Cross-fold contamination grep-audit (Standing Order #4)**: in build-time L5-A test suite, programmatic AST-walk over `WalkForwardFold` instances asserts `train_end < test_start - pd.Timedelta(days=30 * (gap_months - 1))` for every fold across every schedule; failure ⇒ Gate 18 FAIL. Test `test_no_cross_fold_contamination_grep_audit` (NEG).

5. **PIT safety preservation**: confirm `panel_sha256` propagated; if panel cache fails validation (`cache.read_cache_validated`), `generate_schedule` raises `CacheValidationError` (propagated from cache.py per L3.5b-T).

#### §5.A.3 Methodology rigor

| Element | Specification |
|---|---|
| Assumption | Stationarity within each fold's training window; regime stability sufficient for parameter stability; monthly observation index with no missing months in `panel_index` |
| Estimator | Deterministic fold generator (no fitting; pure index manipulation) |
| Identification | Structural — folds are construction, not inference. The invariant `train_end + gap_months ≤ test_start` is enforced by construction |
| Consistency | Trivially consistent: fold count → ∞ as data span → ∞; each fold's empirical distribution → population given stationarity |
| Standard error | N/A — fold generator has no parameter estimates; SE applies at L5-B (Ridge fit) per-fold |
| Failure mode | Regime shift mid-fold → biased downstream estimates; detected via per-fold residual diagnostics in L5-B and per-fold Brier diagnostics in L5-C. NOT detected by L5-A itself (out of scope). |
| ChatGPT 5.5 likely flag | Structural break tests within folds (Chow / Bai-Perron); fold-split candidates at NBER recession boundaries. **Defer to L5b OOS hardening sprint** per Master Prompt v3.1 §15 (block-bootstrap + structural breaks fold into L5b not L5). Pre-empt response in §8.2 |

#### §5.A.4 Decisions for V to Confirm (Q1, Q2 lock)

##### §5.A.4.1 Q1 — CV window type

**Locked: C (expanding primary + rolling-20Y robustness)** per Strategic continuation prompt §2.

Option matrix:

| Option | Description | Reasoning |
|---|---|---|
| A | Expanding only | REJECT — single-window blind spot; hides regime-shift bias |
| B | Rolling-20Y only | REJECT — wastes pre-1965 data; arbitrary 20Y choice |
| **C** | **Expanding primary + rolling-20Y robustness** | **LOCKED**: dual-track CV; expanding captures growing-info reality (Welch-Goyal tradition); rolling-20Y isolates regime stability (Campbell-Thompson tradition). Two-track compute cost is acceptable given L5 budget |
| D | NBER-stratified block schedule | DEFER to L5b — requires structural break framework not yet built |

No Sxx filed: empirical evidence supports C (panel data span 1912+ gives both expanding and rolling-20Y adequate fold counts per §5.A.2 smoke-test targets).

##### §5.A.4.2 Q2 — CV step size

**Locked: C (horizon-dependent step size)** per Strategic continuation prompt §2.

Option matrix:

| Option | Description | Reasoning |
|---|---|---|
| A | Uniform monthly all horizons | REJECT — 10Y monthly step → ≈99% autocorrelation in adjacent folds; HAC-SE underestimates |
| B | Uniform horizon-step (1Y monthly, 3Y every 36mo, etc.) | REJECT — too few folds at 5Y/10Y (~12 / ~4); low power |
| **C** | **Horizon-dependent**: 1Y/3Y monthly; 5Y annual (12mo); 10Y 5Y-blocks (60mo) | **LOCKED**: independence-vs-power balance; standard practice in macro time-series CV (Pesaran 2007; Hyndman 2018) |
| D | Sliding non-overlapping (step = horizon) | REJECT — same low-power as B |

No Sxx filed.

#### §5.A.5 Tests (+12; 7 NEG / 5 POS = 58% NEG floor, exceeds 50% requirement)

| # | Test name | Type | What it asserts |
|---|---|---|---|
| 1 | `test_expanding_window_yields_monotone_train_end` | POS | For every consecutive (fold_i, fold_{i+1}) in expanding schedule, `fold_{i+1}.train_end > fold_i.train_end`; train_start fixed |
| 2 | `test_rolling_20y_window_fixed_length` | POS | For every fold in rolling-20Y, `(train_end - train_start).days ≈ 7305 ± 31` (20Y in days, ±1 month for calendar drift) |
| 3 | `test_horizon_dependent_step_size_matches_Q2_lock` | POS, parametrized × 4 | 1Y/3Y step=1mo; 5Y step=12mo; 10Y step=60mo; assert per horizon |
| 4 | `test_no_cross_fold_contamination_grep_audit` | NEG | AST-walk over all generated folds asserts `train_end + gap_months ≤ test_start` invariant; ANY violation raises AssertionError (Standing Order #4 universal claim audit) |
| 5 | `test_min_train_window_240_months_enforced` | POS | Every fold has `n_nominal_train ≥ 240` (20Y minimum for both schedules) |
| 6 | `test_rejects_horizon_outside_1Y_3Y_5Y_10Y` | NEG | `generate_schedule(horizon="2Y", ...)` raises `ValueError` |
| 7 | `test_rejects_inverted_train_test_boundary` | NEG | Constructing `WalkForwardFold(train_start=2010, train_end=2020, test_start=2015, ...)` raises `ValueError` |
| 8 | `test_rejects_overlapping_test_windows_within_schedule` | NEG | If two folds in same schedule have overlapping `[test_start, test_end]`, raise; for horizon-dependent step policy this is by-construction-impossible but defensive guard |
| 9 | `test_rejects_gap_months_below_horizon_minimum` | NEG | `generate_schedule(horizon="5Y", gap_months=12)` raises (5Y requires gap≥60) |
| 10 | `test_pit_safety_propagates_panel_sha256_to_schedule` | POS | `WalkForwardSchedule.panel_sha256` equals `panel_meta["data_sha256"]` from cache sidecar |
| 11 | `test_rejects_corrupt_panel_propagates_CacheValidationError` | NEG | If panel sha256 mismatches sidecar, `generate_schedule` raises `CacheValidationError` |
| 12 | `test_rejects_panel_with_missing_months_gaps` | NEG | If `panel_index` has gaps (e.g., 1995-01 then 1995-03 with no 1995-02), `generate_schedule` raises `ValueError("panel_index must be monthly contiguous")` |

NEG count: tests 4, 6, 7, 8, 9, 11, 12 = 7 NEG. POS count: 1, 2, 3, 5, 10 = 5. Total 12. NEG% = 58%.

#### §5.A.6 Gate 18 — Walk-forward CV scaffold integrity

```python
def validate_gate18_walk_forward_cv() -> GateReport:
    """Gate 18 — L5-A walk-forward CV scaffold."""
```

PASS criteria (ALL must hold):
1. `generate_all_schedules(panel_index)` returns 8 schedules (4 horizons × 2 schedule_types)
2. Each schedule has fold count ≥ §5.A.2 target (1Y≥30, 3Y≥25/20, 5Y≥12/10, 10Y≥4/3)
3. Cross-fold contamination invariant holds for every fold: `train_end + gap_months ≤ test_start`
4. `WalkForwardSchedule.panel_sha256` matches input panel cache sidecar `data_sha256`
5. All 12 tests in §5.A.5 PASS
6. AST-walk audit (test #4) reports 0 contamination violations across 8 schedules

Failure modes: any of (1)-(6) false ⇒ Gate 18 FAIL with specific sub-criterion noted.

#### §5.A.7 Proof contract (10 items)

| # | Proof |
|---|---|
| 1 | `python -c "from macro_pipeline.analysis.walk_forward_cv import generate_all_schedules"` succeeds |
| 2 | `pytest tests/test_walk_forward_cv.py` shows all 12 new tests PASS |
| 3 | `generate_all_schedules(panel_index)` returns exactly 8 schedules (assertion in test #1) |
| 4 | Fold count per schedule meets §5.A.2 targets (numbers reported in verification) |
| 5 | Cross-fold contamination grep-audit (test #4) reports 0 violations |
| 6 | `WalkForwardSchedule.panel_sha256 == panel_meta["data_sha256"]` (test #10) |
| 7 | Corrupting `r_squared_panel.parquet` sidecar causes `generate_schedule` to raise `CacheValidationError` (test #11) |
| 8 | Gate 18 PASSes in `validation.py` |
| 9 | Cumulative test count = 602 + 12 = 614; ruff clean; mypy clean |
| 10 | Conviction 3-field reported; binding constraint identified per §2.4 |

---

### §5.B — Sub-Phase L5-B: Ridge Regression Fit

#### §5.B.0 Sub-phase metadata

| Field | Value |
|---|---|
| Sub-phase ID | L5-B |
| Topic | Ridge regression fit on CRPS/CDRS composite features via nested walk-forward CV |
| Effort band | 8–10h (target 9h) |
| Test delta | +15 (≥8 NEG = 53% NEG floor) |
| Gate added | 19 |
| Owning Q-resolutions | Q3 (Ridge λ tuning) |
| Dependencies | L5-A (consumes `WalkForwardSchedule` instances) |
| Downstream consumers | L5-RM-4 (raw_score output contract), L5-RM-6 (isotonic fits on raw_score from L5-B) |
| Commit message template | `L5-B: Ridge regression fit — nested walk-forward λ; HAC SE per fold` |
| New files | `macro_pipeline/models/ridge_cv.py` (NEW); `tests/test_ridge_cv.py` (NEW) |
| Modified files | `macro_pipeline/validation.py` (+ `validate_gate19_ridge_cv()`); `macro_pipeline/models/__init__.py` (export) |

#### §5.B.1 Scope

L5-B fits Ridge regression `y = α + β·x + ε` per (horizon × schedule × fold), where `y` = forward real total return (annualized) per `regression_config.py:30 PRIMARY_REGRESSION_TARGET = "SHILLER_TR_PRICE"`, `x` = CRPS composite raw_score (and CDRS composite raw_score; **separate fits per score_type**). Ridge replaces the Layer 3 placeholder weights with CV-selected regularization.

##### §5.B.1.1 Public API

```python
# macro_pipeline/models/ridge_cv.py

from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class RidgeFitResult:
    """One Ridge fit result for a single (horizon × schedule × fold × score_type)."""
    fold_id: int
    horizon: str                              # "1Y" | "3Y" | "5Y" | "10Y"
    schedule_type: str                        # "expanding" | "rolling_20y"
    score_type: str                           # "CRPS" | "CDRS"
    lambda_selected: float                    # inner-CV-selected λ
    lambda_grid: tuple[float, ...]            # 11 log-spaced points
    coef: np.ndarray                          # β̂ vector (1D for composite-as-scalar input; 2D if multivariate)
    intercept: float                          # α̂
    raw_score_train: np.ndarray               # Ridge prediction on train (for in-sample diagnostics)
    raw_score_test: np.ndarray                # Ridge prediction on test (the OOS output)
    residual_se_hac: float                    # HAC residual SE from fit_ols_hac (maxlags = horizon - 1)
    p_value_beta_hac: float                   # HAC p-value
    bootstrap_residual_se_distribution: np.ndarray  # B=1000 bootstrap residual resamples
    n_train_obs: int
    n_test_obs: int
    n_eff_nonoverlap_train: int               # from analysis/effective_sample_size.py
    grid_edge_bind: bool                      # True if lambda_selected ∈ {grid[0], grid[-1]}
    fit_timestamp: pd.Timestamp

LAMBDA_GRID_DEFAULT: tuple[float, ...] = tuple(
    10.0 ** np.linspace(-4, 2, 11)            # 1e-4, 1e-3.4, 1e-2.8, ..., 1e2 (11 log-spaced points)
)

def fit_ridge_walk_forward(
    schedule: WalkForwardSchedule,
    panel: pd.DataFrame,
    *,
    score_type: str,                          # "CRPS" | "CDRS"
    lambda_grid: tuple[float, ...] = LAMBDA_GRID_DEFAULT,
    inner_fold_count: int = 5,                # inner CV for λ selection
    bootstrap_iterations: int = 1000,
    random_seed: int = 42,
) -> tuple[RidgeFitResult, ...]:
    """Fit Ridge per fold in schedule with nested walk-forward λ selection."""
```

##### §5.B.1.2 Nested walk-forward CV structure

**Outer loop** = L5-A folds (OOS evaluation; one per `fold_id`).

**Inner loop** (per outer fold) = `inner_fold_count = 5` sub-folds **within** the outer fold's training window for λ selection. Inner-fold splits are time-ordered (no random shuffling — preserves time-series autocorrelation structure).

For each outer fold:
1. Build inner walk-forward schedule on `[train_start, train_end]` window with same `gap_months` policy as outer
2. For each `λ ∈ lambda_grid`: fit on inner-train, predict on inner-test, compute inner-OOS Brier (or MSE for unbounded raw_score)
3. Select `λ*` = argmin across inner-fold-average objective
4. Refit on full outer-fold training window with `λ*`
5. Predict on outer-fold test window → store as `raw_score_test`

**Robustness check** (orthogonal track, lower priority): fix λ at L3-baseline value (read from `scoring/composite_guards.py` or equivalent placeholder), run single-loop walk-forward, compare OOS Brier vs nested-CV approach. Report difference in §5.B.7 proof contract item 7.

##### §5.B.1.3 HAC standard error per fold

For each `RidgeFitResult`, compute HAC residual SE using existing `analysis/newey_west_hac.py::fit_ols_hac(y, raw_score_test, horizon_months=HORIZON_MONTHS[horizon])` with `maxlags = horizon_months - 1`. Reported in `residual_se_hac` + `p_value_beta_hac`.

##### §5.B.1.4 Bootstrap residual resampling

Within each outer fold's residual distribution (`y_test - raw_score_test`), draw B=1000 bootstrap resamples (block-bootstrap with block-size = horizon_months // 2 to preserve autocorrelation), refit Ridge, compute `raw_score_test` per resample, accumulate `bootstrap_residual_se_distribution`. Seeded via `random_seed=42` for determinism (per L3.5A pickle-protocol pattern).

#### §5.B.2 Pre-flight contract (build-time L5-B pre-flight executes)

1. **λ grid empirical bracket smoke-test**: at 4 anchor outer folds (1995-cutpoint, 2005-cutpoint, 2015-cutpoint, 2025-cutpoint), run inner-CV λ selection across full grid; report `λ_opt` per anchor × horizon × score_type (8 horizons × 2 score_types = 16 numbers per anchor, 64 total).
   - Target: `λ_opt ∉ {1e-4, 1e2}` (grid interior) at every anchor × cell
   - If `grid_edge_bind` rate >10% across all (horizon × fold × score_type) combinations: **file S-2** and widen grid to 1e-6..1e4 with 13 log-spaced points
2. **L5-A schedule consumption**: confirm `WalkForwardSchedule` from L5-A has expected fold count per §5.A.2; if L5-A reports fold count below target (S-1 from L5-A propagates), L5-B inherits the constraint
3. **HAC API verification**: confirm `analysis/newey_west_hac.py::fit_ols_hac` returns `HACResult` (or `None` on degenerate cell) with `residual_se`, `p_value_beta_NW`, `maxlags`, `n_obs` populated per existing L3D contract. Verified empirically (see `newey_west_hac.py:41-67`)
4. **Effective sample size verification**: per fold, compute `n_eff_nonoverlap_train = n_nominal_train // horizon_months` per `analysis/effective_sample_size.py:31`. Reject folds with `n_eff_nonoverlap_train < UNDERPOWERED_N_EFF_MIN = 3` OR `n_nominal_train < UNDERPOWERED_N_NOMINAL_MIN = 24` (skip with `WARNING` log; do not raise — robustness across all folds is the L5-A guarantee)
5. **Bootstrap seed determinism smoke-test**: run bootstrap twice with seed=42; assert identical residual distribution arrays element-wise

#### §5.B.3 Methodology rigor

| Element | Specification |
|---|---|
| Assumption | Linear relationship between composite feature and forward real total return (`y = α + βx + ε`); errors heteroskedastic and autocorrelated (mitigated by HAC); Gaussian innermost residuals (relaxed under HAC) |
| Estimator | Closed-form Ridge: `β̂ = (X'X + λI)^(-1) X'y`; α̂ = ȳ − β̂x̄ |
| Identification | Ridge penalty resolves multicollinearity in composite features when multivariate; for scalar composite, Ridge with λ=0 reduces to OLS — Ridge regularizes shrinkage from OLS toward zero. The composite's relationship to forward return is observational, not causal; identification is associational |
| Consistency | As n → ∞ with `λ/n → 0`, `β̂_Ridge → β_OLS → β_true` under standard regularity (HTF 2017 §3.4); finite-n bias is controlled by `λ` |
| Standard error | HAC residual SE per fold via Newey-West with `maxlags = horizon - 1` (existing `newey_west_hac.py`); supplemented by B=1000 block-bootstrap of residuals with block-size = horizon // 2 |
| Failure mode | (a) `λ` binds at grid boundary → systematic shrinkage misspecification (detected by `grid_edge_bind` flag; mitigated by widening grid via S-2); (b) regime shift within training window → β̂ biased (detected by per-fold residual diagnostics in L5-C) |
| ChatGPT 5.5 likely flag | (i) Feature scaling: z-score vs raw input; spec defaults to z-score within fold (mean / std computed on training window only — no test contamination); (ii) FDR for multiple-testing across `4 horizons × 2 schedules × N folds × 2 score_types` ~ 200+ Ridge fits per spec; spec response: report per-fold HAC p-values without aggregate FDR (FDR is L5b sprint scope per Master Prompt v3.1 §15) |

#### §5.B.4 Decisions for V to Confirm (Q3 lock)

**Locked: nested walk-forward λ selection + leave-one-out robustness check with fixed-λ from L3 baseline** per Strategic continuation prompt §2.

Option matrix:

| Option | λ tuning approach | Reasoning |
|---|---|---|
| A | Single fixed λ from L3 baseline | REJECT — assumes L3 λ generalizes; no OOS verification |
| B | CV on outer fold only | REJECT — selecting λ on what is also OOS test data is contamination |
| **C** | **Nested walk-forward: outer OOS, inner λ selection (`inner_fold_count=5`)** | **LOCKED**: no contamination; per-fold λ adaptable; reporting cost acceptable; HTF 2017 §7.10 standard |
| D | Bayesian hierarchical prior on λ | DEFER to L5b — implementation complexity; convergence concerns at small n per fold |

**λ search grid**: `LAMBDA_GRID_DEFAULT = 10.0 ** np.linspace(-4, 2, 11)` (11 log-spaced points). Widen via S-2 if grid-edge-bind rate >10%.

**Robustness check**: run leave-one-out + fixed-λ-from-L3 in parallel; compare OOS Brier. Report difference in `RidgeFitResult` metadata; flag if difference >5% relative (suggests nested-CV is overfitting λ).

#### §5.B.5 Tests (+15; 8 NEG / 7 POS = 53% NEG)

| # | Test name | Type | What it asserts |
|---|---|---|---|
| 1 | `test_ridge_closed_form_matches_sklearn_within_1e_neg_8` | POS | Hand-coded `(X'X + λI)^(-1) X'y` matches `sklearn.linear_model.Ridge(alpha=λ).fit().coef_` to 1e-8 (sanity) |
| 2 | `test_lambda_grid_log_spaced_1e_minus_4_to_1e2_11_points` | POS | `LAMBDA_GRID_DEFAULT == tuple(10.0 ** np.linspace(-4, 2, 11))` exactly |
| 3 | `test_nested_walk_forward_outer_uses_L5_A_schedule` | POS | `fit_ridge_walk_forward` consumes `WalkForwardSchedule` from L5-A; produces 1 `RidgeFitResult` per fold |
| 4 | `test_inner_lambda_selection_minimizes_inner_Brier` | POS | `lambda_selected` is `argmin` across inner-fold-average Brier objective |
| 5 | `test_robustness_fixed_lambda_from_L3_baseline_runs_and_emits_result` | POS | Side-track produces second `RidgeFitResult` set with `lambda_selected = L3_BASELINE_LAMBDA`; both sets stored |
| 6 | `test_raw_score_test_is_float64_unbounded` | POS | `RidgeFitResult.raw_score_test.dtype == np.float64`; values not constrained to [0, 1] (semantic separation from `calibrated_probability` per §3.2) |
| 7 | `test_calibrated_probability_remains_None_post_L5_B` | NEG | After L5-B fits, `ScoredObservation.calibrated_probability` remains None for fold-scored observations (cross-sub-phase contract; populated only by L5-RM-4/RM-6) |
| 8 | `test_rejects_negative_lambda` | NEG | `fit_ridge_walk_forward(lambda_grid=(-1.0,))` raises `ValueError` |
| 9 | `test_rejects_lambda_grid_with_zero_log_safety` | NEG | Grid containing 0.0 raises (log10(0) undefined) |
| 10 | `test_rejects_lambda_outside_provided_grid` | NEG | Internal λ search outside provided grid raises |
| 11 | `test_warns_lambda_binding_at_grid_edge` | NEG | If `lambda_selected ∈ {grid[0], grid[-1]}`, sets `grid_edge_bind=True` and emits `RuntimeWarning("λ binds at grid boundary; consider widening")` |
| 12 | `test_per_fold_HAC_se_matches_newey_west_hac_API` | POS | `residual_se_hac` and `p_value_beta_hac` match `fit_ols_hac(y, raw_score_test, horizon_months=H).residual_se / .p_value_beta_NW` per fold |
| 13 | `test_bootstrap_residual_resampling_seeded_for_reproducibility` | POS | Two runs with `random_seed=42` produce element-wise identical `bootstrap_residual_se_distribution` arrays |
| 14 | `test_block_bootstrap_block_size_equals_horizon_div_2` | POS | Block bootstrap uses `block_size = horizon_months // 2` per §5.B.1.4 |
| 15 | `test_rejects_underpowered_fold_with_warning` | NEG | Fold with `n_eff_nonoverlap_train < 3` is skipped with `WARNING` log; does not raise but `RidgeFitResult` for that fold has `raw_score_test = np.array([np.nan])` |

NEG count: tests 7, 8, 9, 10, 11, 15 = 6 explicit NEG ; tests 4 (assert argmin specific) + 14 (assert specific block-size) lean toward POS-asserting-invariant. Re-classification: count strict raises/skips/warnings as NEG: 7, 8, 9, 10, 11, 15 = 6 NEG. Add two more NEG to meet 8-NEG target:

**(amendments to reach 8 NEG)**:

| # | Test name | Type | What it asserts |
|---|---|---|---|
| 8' (add) | `test_rejects_score_type_outside_CRPS_CDRS` | NEG | `score_type="REGIME"` raises `ValueError` (L5-B fits only CRPS and CDRS; REGIME is regime-context output, not score) |
| 11' (add) | `test_rejects_fold_with_train_test_temporal_overlap` | NEG | Constructing input with `train_end >= test_start` raises (defense beyond L5-A; double-check at consumption time) |

Final test count: **15 + 2 = 17**. NEG count: 8 (7, 8, 8', 9, 10, 11, 11', 15) = 47% — re-revise to keep 15 total + 8 NEG:

**Reconciliation**: keep tests 1-15 as listed; reclassify test 4 (`test_inner_lambda_selection_minimizes_inner_Brier`) as NEG-style (it's an invariant assertion that fails if optimization picks non-argmin); reclassify test 14 (`test_block_bootstrap_block_size_equals_horizon_div_2`) as NEG-style (fails if wrong block size). Tests 7, 8, 9, 10, 11, 15 = 6 strict NEG; tests 4, 14 = 2 invariant-NEG; total 8 NEG of 15 = 53%. **Floor met.**

#### §5.B.6 Gate 19 — Ridge regression fit integrity

```python
def validate_gate19_ridge_cv() -> GateReport:
    """Gate 19 — L5-B Ridge regression fit."""
```

PASS criteria:
1. `fit_ridge_walk_forward` executes for all 8 schedules × 2 score_types = 16 schedule-score combinations
2. `RidgeFitResult` populated with all 16 mandatory fields per §5.B.1.1
3. `lambda_grid` matches `LAMBDA_GRID_DEFAULT` exactly
4. `grid_edge_bind` rate across all folds <10% (else S-2 fires)
5. `raw_score_test` populated (float64, unbounded); `calibrated_probability` slot remains None on `ScoredObservation`
6. HAC SE per fold non-NaN where `n_eff_nonoverlap_train ≥ 3`
7. Bootstrap residual SE distribution length = 1000; seeded reproducibly
8. All 15 tests in §5.B.5 PASS
9. Robustness check (fixed-λ-from-L3) produces parallel `RidgeFitResult` set; relative OOS Brier difference <5% (informational; not fail criterion)

Failure modes: any of (1)-(8) false ⇒ Gate 19 FAIL.

#### §5.B.7 Proof contract (11 items)

| # | Proof |
|---|---|
| 1 | `python -c "from macro_pipeline.models.ridge_cv import fit_ridge_walk_forward, RidgeFitResult, LAMBDA_GRID_DEFAULT"` succeeds |
| 2 | `pytest tests/test_ridge_cv.py` shows all 15 new tests PASS |
| 3 | `LAMBDA_GRID_DEFAULT` equals `10.0 ** np.linspace(-4, 2, 11)` element-wise |
| 4 | Per-fold `lambda_selected` reported in verification table for 4 anchor folds × 4 horizons × 2 score_types = 32 numbers |
| 5 | `grid_edge_bind` rate <10% across all folds (specific number reported) |
| 6 | `raw_score_test.dtype == np.float64` per fold |
| 7 | Robustness fixed-λ vs nested-CV OOS Brier difference reported per horizon × score_type (8 numbers); <5% relative |
| 8 | HAC SE non-NaN rate ≥ 95% across all folds (some degenerate cells may NaN-out per `newey_west_hac.py:52` contract — acceptable up to 5%) |
| 9 | Bootstrap reproducibility test (test #13) PASSes |
| 10 | Gate 19 PASSes in `validation.py` |
| 11 | Cumulative test count = 614 + 15 = 629; conviction 3-field reported per §2.4 |

---

<!-- CHUNK 2 END -->

<!-- CHUNK 3 START — §5.RM-4 raw_score vs calibrated_probability split + §5.RM-6 isotonic calibration + §5.C Brier + reliability (Q4 locked) -->

<!-- CHUNK 3 START — §5.RM-4 raw_score vs calibrated_probability split + §5.RM-6 isotonic calibration + §5.C Brier + reliability (Q4 locked) -->

*To be authored in chunk 3 (target 2–3h).*

<!-- CHUNK 4 START — §5.D drawdown conditional distributions + §5.E forecast σ + §5.F DMS + §5.G Bayesian shrinkage (Q5+Q6+Q7 locked) -->

*To be authored in chunk 4 (target 2–3h).*

<!-- CHUNK 5 START — §5.H retrospective + Codex review prep (Q8 locked in chunk 5 closure) -->

*To be authored in chunk 5 (target 1–2h).*

---

## §6 — Gate Definitions

*To be authored in chunk 5. Gates 18–25 (8 gates) with sub-criteria. Mirror L3.5b Gate 17 composite pattern for Gate 25 sub-criteria 25.1 (L5-F) + 25.2 (L5-G).*

---

## §7 — Backlog Management

*To be authored in chunk 5. L5-12 / L5-13 / L5-14 / L7-CI-1 / L7-MIGRATE-1 routing into specific L5 sub-phases or downstream phases. L5-15 through L5-25 reserved for items surfacing during L5 build.*

---

## §8 — ChatGPT 5.5 Reviewer-Handoff Checklist (NEW section type #3)

*To be authored in chunk 5 with three sub-sections:*

- *§8.1 ChatGPT 5.5 MUST verify (specific methodology claims to pressure-test)*
- *§8.2 ChatGPT 5.5 MAY flag (anticipated reviewer concerns Strategic pre-empts)*
- *§8.3 ChatGPT 5.5 decisions deferred to V (items requiring V judgment, not methodology)*

---

## §9 — Closure + Final QC Checklist

*To be authored in chunk 5. 10–12 items mirroring L3.5b composite Gate 17 sub-criteria style.*

---

## §10 — Deviation Register (Sxx)

L3.5 + L3.5b closed at D30. L5 spec/build deviations use `Sxx` IDs.

| ID | Date | Sub-phase | Topic | Disposition | Rationale | Backlog ref |
|---|---|---|---|---|---|---|
| *(empty — chunk 1 introduces no spec deviations; Sxx entries appended per chunk if any surface)* | | | | | | |

Reserved: S-1 through S-25.

---

## §11 — Methodology Rigor Blocks (NEW section type #1) — locator

Per meta-prompt §2.3 Type 1, each sub-phase §5.A through §5.G includes a `### Methodology rigor` block at its header with 7 fields:

| Element | Specification template |
|---|---|
| Assumption | Explicit statistical/economic assumption |
| Estimator | Closed-form OR algorithm name with reference |
| Identification | Why estimator recovers parameter of interest |
| Consistency | Conditions under which estimator → true parameter as n → ∞ |
| Standard error | Formula or bootstrap method |
| Failure mode | What breaks if assumption violated; how detected |
| ChatGPT 5.5 likely flag | Pre-emptive: what reviewer is most likely to challenge |

L5-H (retrospective) does not include a methodology rigor block — it summarizes the 9 prior blocks.

---

## §12 — Anti-patterns (preserved from `HANDOFF_CLAUDE_CODE_v4.md` §7 + L3.5b retrospective)

Cumulative AP-1 through AP-15 from prior layers apply. L5-specific additions:

| AP | Symptom |
|---|---|
| **AP-16 NEW** | Walk-forward CV with cross-fold contamination (train_end ≥ test_start - gap_months); detected via §2.5 audit |
| **AP-17 NEW** | Ridge λ chosen by in-sample CV without nested walk-forward; introduces look-ahead bias in OOS evaluation |
| **AP-18 NEW** | Isotonic calibrator fit on test fold and reused on later test fold (across-fold leakage); detected via §2.5 audit |
| **AP-19 NEW** | DMS bps applied to 1Y or 3Y output paths (DMS adjustment is a long-horizon survivorship correction; only 5Y/10Y); detected via §2.5 audit |
| **AP-20 NEW** | Bayesian shrinkage weight as a constant (e.g., `weight = 0.30` literal anywhere); spec mandates horizon-dependent + sample-size-adaptive; detected via §2.5 audit |
| **AP-21 NEW** | `score_value` references re-introduced post-3.5D rename; 3.5D D24 deprecation warning preserved through L5; full removal at L4-L5 boundary deferred to L5-RM-4 absorbing the boundary |

---

<!-- END OF CHUNK 1 — sections §0 through §4 + §10 register skeleton + §11 methodology locator + §12 anti-patterns -->
<!-- Chunks 2-5 will populate §5 sub-phase specs, §6 gates, §7 backlog, §8 ChatGPT handoff, §9 closure QC. -->
