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

*To be authored in chunk 2 (target 2–3h).*

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
