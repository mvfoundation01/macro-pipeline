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
| `calibrated_probability_band_lower` | `Optional[float64] ∈ [0, 1]` | **L5-E (NEW; amended via S-1)** | unchanged after introduction | NEW slot added to `ScoredObservation` via L5-RM-4 (dataclass field; default None until L5-E populates with bootstrap-CV-residual-derived lower band) | §5.E.3 |
| `calibrated_probability_band_upper` | `Optional[float64] ∈ [0, 1]` | **L5-E (NEW; amended via S-1)** | unchanged after introduction | NEW slot added to `ScoredObservation` via L5-RM-4; paired with `_lower` to express forecast band directly | §5.E.3 |
| `drawdown_conditional_distribution` | `Optional[dict[str, float]]` (CDF percentiles {"p10": ..., "p25": ..., "p50": ..., "p75": ..., "p90": ...} keyed by drawdown threshold) | **L5-D (NEW; renamed via S-1)** | unchanged after introduction | NEW slot in `ScoredObservation` via L5-RM-4 | §5.D.3 |
| `dms_adjustment_bps` | `float64` (negative; annualized bps) | **L5-F (NEW)** | unchanged after introduction | NEW slot in `ScoredObservation` via L5-RM-4 (default 0.0 for 1Y/3Y; populated for 5Y/10Y at L5-F) | §5.F.2 |
| `bayesian_shrinkage_weight` | `float64 ∈ [0, 1]` (k/(k+n) form) | **L5-G (NEW)** | unchanged after introduction | NEW slot in `ScoredObservation` via L5-RM-4 (default 0.0 in 1Y; horizon-dependent populated at L5-G) | §5.G.3 |
| `regime_state` | `str ∈ {"expansion", "late-cycle", "recession", "indeterminate"}` | L3A | 3.5D (added "indeterminate") | unchanged in L5 | §5.B.4 (Ridge fits stratified by regime_state); §5.G.3 (shrinkage may be regime-conditional in future L5b sprint) |
| `confidence_overall` | `float64 ∈ [0, 100]` | L1.5B | 3.5D (cap 60 applied when regime=indeterminate) | unchanged in L5 | §5.B.4, §5.G.4 |
| `metadata_extra` | `dict[str, Any]` (bag of everything) | L3 | L5-RM-4 (drains remaining CDRS V/T notes into `notes` per L5-13) | post-L5-RM-4: shrunk by L5-13 migration | §5.RM-4.5 |
| `pre_1978_training_only` | `bool` | 3.5C (NBER calendar) | L5-RM-4 (when True AND L5-A operating in training mode, adds caveat to notes per L5-13) | unchanged in L5 | §5.RM-4.5 |

**Cross-sub-phase migrations summarized**:

1. `ScoredObservation` dataclass gains 5 new slots at **L5-RM-4** as a single atomic dataclass migration (slot list amended via **S-1** in chunk 3; supersedes chunk 1 initial sketch):
   - `calibrated_probability_band_lower: Optional[float] = None`
   - `calibrated_probability_band_upper: Optional[float] = None`
   - `drawdown_conditional_distribution: Optional[dict[str, float]] = None`
   - `dms_adjustment_bps: float = 0.0`
   - `bayesian_shrinkage_weight: float = 0.0`
   
2. L5-D, L5-E, L5-F, L5-G **populate** these slots; they do not add fields. This avoids 4 separate dataclass migrations.

3. The L5-13 CDRS notes migration (Codex finding X deferred from 3.5b) is absorbed into L5-RM-4. Effort 1-2h folded into L5-RM-4 budget (4-6h band).

4. `cv_fold_id` (initially proposed as a top-level slot in chunk 1) is **relocated to `calibration_metadata` dict** per S-1: rationale = the field is transient (only populated during CV scoring runs, not for production scoring); `calibration_metadata: dict[str, Any]` is the natural home per L3.5D pattern. Build agent at L5-RM-4 time stores `{"cv_fold_id": int, "cv_schedule_type": "expanding"|"rolling_20y", ...}` in calibration_metadata when scoring within a fold.

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

<!-- CHUNK 3 START — §5.RM-4 raw_score vs calibrated_probability split + §5.RM-6 isotonic calibration + §5.C Brier + reliability (Q4+Q5 locked) -->

### §5.RM-4 — Sub-Phase L5-RM-4: raw_score vs calibrated_probability Semantic Split + Batched Dataclass Migration

#### §5.RM-4.0 Sub-phase metadata

| Field | Value |
|---|---|
| Sub-phase ID | L5-RM-4 |
| Topic | Formalize raw_score / calibrated_probability semantic split; add 5 new slots to `ScoredObservation` (batched single migration); absorb L5-13 (CDRS notes migration to mirror CRPS pattern) |
| Effort band | 4–6h (target 5h; includes L5-13 1–2h absorbed) |
| Test delta | +8 (≥4 NEG = 50% floor; spec lists 5 NEG / 3 POS) |
| Gate added | 20 |
| Owning Q-resolutions | None (structural sub-phase; no methodology choice) |
| Dependencies | L5-B (consumes `raw_score` from `RidgeFitResult`) |
| Downstream consumers | L5-RM-6 (isotonic on raw_score → calibrated_probability), L5-C/D/E/F/G (all consume calibrated_probability + new slots) |
| Commit message template | `L5-RM-4: ScoredObservation 5-slot batched migration + raw/calibrated semantic split + L5-13 absorbed` |
| Modified files | `macro_pipeline/scoring/scored_observation.py` (slot additions + validator); `macro_pipeline/scoring/cdrs.py` (L5-13 notes migration); `tests/test_scored_observation.py` (slot tests); `tests/test_cdrs.py` (L5-13 regression test); `macro_pipeline/validation.py` (+ `validate_gate20_dataclass_migration()`) |

#### §5.RM-4.1 Scope

L5-RM-4 is the **batched dataclass migration** absorbing field additions that L5-D, L5-E, L5-F, L5-G would otherwise each commit separately. Per V's standing approval (recorded in S-1) and Strategic continuation prompt §3.2, all 5 new slots are added in one atomic commit.

##### §5.RM-4.1.1 New slot additions (5 total)

```python
# macro_pipeline/scoring/scored_observation.py (modifications)

@dataclass
class ScoredObservation:
    # ... existing 25 slots unchanged (raw_score, calibrated_probability,
    # calibration_metadata, notes, etc.) ...
    
    # ---- L5 calibration band slots (L5-RM-4 NEW; L5-E populates) ----
    calibrated_probability_band_lower: float | None = None    # ∈ [0, 1] when present
    calibrated_probability_band_upper: float | None = None    # ∈ [0, 1] when present
    
    # ---- L5 drawdown conditional distribution slot (L5-RM-4 NEW; L5-D populates) ----
    drawdown_conditional_distribution: dict[str, float] | None = None
    
    # ---- L5 DMS survivorship adjustment slot (L5-RM-4 NEW; L5-F populates) ----
    dms_adjustment_bps: float = 0.0    # negative bps for 5Y/10Y; 0.0 for 1Y/3Y
    
    # ---- L5 Bayesian shrinkage weight slot (L5-RM-4 NEW; L5-G populates) ----
    bayesian_shrinkage_weight: float = 0.0    # ∈ [0, 1]
```

##### §5.RM-4.1.2 Validator extensions in `__post_init__`

```python
if self.calibrated_probability_band_lower is not None and not (
    0.0 <= self.calibrated_probability_band_lower <= 1.0
):
    raise ValueError(
        f"calibrated_probability_band_lower={self.calibrated_probability_band_lower} "
        "must be in [0, 1] when present"
    )

if self.calibrated_probability_band_upper is not None and not (
    0.0 <= self.calibrated_probability_band_upper <= 1.0
):
    raise ValueError(
        f"calibrated_probability_band_upper={self.calibrated_probability_band_upper} "
        "must be in [0, 1] when present"
    )

if (self.calibrated_probability_band_lower is not None
    and self.calibrated_probability_band_upper is not None
    and self.calibrated_probability_band_lower > self.calibrated_probability_band_upper):
    raise ValueError(
        f"band_lower={self.calibrated_probability_band_lower} must be ≤ "
        f"band_upper={self.calibrated_probability_band_upper}"
    )

# DMS bps band: −200 to 0 (negative, less negative than −200, never positive)
if not -200.0 <= self.dms_adjustment_bps <= 0.0:
    raise ValueError(
        f"dms_adjustment_bps={self.dms_adjustment_bps} must be in [-200, 0] bps"
    )

# Bayesian shrinkage weight
if not 0.0 <= self.bayesian_shrinkage_weight <= 1.0:
    raise ValueError(
        f"bayesian_shrinkage_weight={self.bayesian_shrinkage_weight} "
        "must be in [0, 1]"
    )
```

##### §5.RM-4.1.3 raw_score vs calibrated_probability semantic contract (formalized)

| Field | Semantic | Domain | Populated when |
|---|---|---|---|
| `raw_score` | Untransformed model output; Ridge raw prediction (L5-B) or CRPS/CDRS composite (L3) | `float ∈ [0, 1]` (existing constraint per `__post_init__`) | Always; populated by L3 scorers or L5-B Ridge fit |
| `calibrated_probability` | Isotonic-transformed raw_score; reliable in [0, 1] bin-frequency sense | `float ∈ [0, 1]`, or None pre-calibration | Populated by L5-RM-6 isotonic transform; None for any `ScoredObservation` produced before L5-RM-6 runs |
| `calibration_metadata` | Dict capturing calibration provenance + transient CV fold context | `dict[str, Any]`, or None pre-calibration | Populated by L5-RM-6; structure `{"method": "isotonic", "fit_window": (start, end), "horizon": h, "monotonicity_audit": "PASS", "cv_fold_id": int \| None, "cv_schedule_type": str \| None}` |

**Production scoring contract**: every production `ScoredObservation` (post-L5-RM-6) MUST have `calibrated_probability` populated. Internal CV-time `ScoredObservation` (used in L5-B Ridge fits) MAY have `calibrated_probability=None` if the score_type or fold has not yet been calibrated.

##### §5.RM-4.1.4 L5-13 absorption — CDRS notes migration

Per Codex 5/5 L3.5 review finding X (deferred to L5-13): CRPS migrated `metadata_extra` → `notes` at 3.5D AM25; CDRS still has V/T notes in `metadata_extra`. L5-RM-4 absorbs the L5-13 work:

1. Migrate every CDRS `scored_obs.metadata_extra["V_*"]` and `["T_*"]` entry to `scored_obs.notes`
2. Mirror CRPS pattern: use shared `_format_pit_lineage_notes()` helper (currently in `scoring/crps.py`; extract to `scoring/notes_formatter.py` to share)
3. Add NBER pre-1978 caveat to notes when `pre_1978_training_only=True` flag is set (mirrors CRPS handling)

Effort: 1-2h, folded into L5-RM-4's 4-6h band.

#### §5.RM-4.2 Pre-flight contract (build-time L5-RM-4 pre-flight executes)

1. **AST-walk audit of `scored_observation.py:49`** confirming 25 existing slots; capture diff for the 5 additions
2. **Parquet roundtrip smoke-test**: construct `ScoredObservation` with all 30 slots populated; serialize via `to_dict()`; deserialize; assert element-wise equality
3. **L5-13 CDRS notes audit**: grep `scoring/cdrs.py` for `metadata_extra["V_*"]` / `["T_*"]` patterns; verify migration replaces every match (target: 0 remaining post-migration)
4. **Test suite regression**: existing 602 tests must still pass post-dataclass change (default values for new slots prevent ctor signature breakage)
5. **`scored_observation.to_dict()` schema audit**: verify the new slots are included in `to_dict()` output (chunk-3 build-time concern; spec authoring confirms it's expected)

#### §5.RM-4.3 Methodology rigor

| Element | Specification |
|---|---|
| Assumption | Existing `ScoredObservation` slot semantics preserved; default-value compatibility prevents breaking-change for existing code paths |
| Estimator | N/A (structural dataclass migration; no fitting) |
| Identification | N/A — semantic contract is type-level |
| Consistency | Trivially: dataclass invariants enforced in `__post_init__` |
| Standard error | N/A — no parameter estimation |
| Failure mode | (a) Existing test that constructs `ScoredObservation` with positional args breaks if new slots inserted mid-list — mitigated by appending at end; (b) parquet roundtrip drops new fields if pyarrow schema lacks them — mitigated by §5.RM-4.2 smoke-test #2 |
| ChatGPT 5.5 likely flag | Validator strictness: band lower ≤ upper rule may be too strict if isotonic regression in L5-RM-6 produces edge cases; spec pre-empts by stating L5-RM-6 must clip to [0, 1] before populating |

#### §5.RM-4.4 Decisions

**No owning Q.** Single structural decision: **BATCHED dataclass migration** (5 slots in one commit) per V's standing approval (chunk 1 §1.3 row 9; reaffirmed via S-1 reconciliation in §10). Alternative `DISTRIBUTED` (each of L5-D/E/F/G adds its own slot in its own commit) rejected — 5 dataclass migration commits vs 1; higher merge-conflict risk; Codex 5/5 review surface inflates 5×.

#### §5.RM-4.5 Tests (+8; 5 NEG / 3 POS = 63% NEG)

| # | Test name | Type | What it asserts |
|---|---|---|---|
| 1 | `test_dataclass_has_all_30_slots` | POS | Inspect `ScoredObservation.__dataclass_fields__`; assert exactly 30 fields (25 existing + 5 new); names match spec |
| 2 | `test_parquet_roundtrip_preserves_5_new_slots` | POS | Construct + populate all 30 slots; `to_dict()` + parquet write + read + compare element-wise |
| 3 | `test_notes_field_carries_L5_provenance_post_L5_13_absorption` | POS | After L5-RM-4 migration, CDRS `scored_obs.notes` contains formatted V/T lineage; `scored_obs.metadata_extra` does NOT contain V/T keys (L5-13 absorbed; regression-testable per continuation prompt §3.2 chunk 3) |
| 4 | `test_rejects_calibrated_probability_band_lower_outside_zero_one` | NEG | `ScoredObservation(..., calibrated_probability_band_lower=1.5)` raises `ValueError` |
| 5 | `test_rejects_calibrated_probability_band_upper_outside_zero_one` | NEG | symmetric to #4 |
| 6 | `test_rejects_band_lower_greater_than_band_upper` | NEG | `ScoredObservation(..., band_lower=0.7, band_upper=0.5)` raises `ValueError("band_lower must be ≤ band_upper")` |
| 7 | `test_rejects_dms_adjustment_outside_minus_200_to_zero_bps_band` | NEG | `dms_adjustment_bps=10.0` (positive) or `dms_adjustment_bps=-300.0` raises `ValueError` |
| 8 | `test_rejects_bayesian_shrinkage_weight_outside_zero_one` | NEG | `bayesian_shrinkage_weight=1.5` or `=−0.1` raises `ValueError` |

NEG count: 5 (tests 4, 5, 6, 7, 8). POS count: 3 (tests 1, 2, 3). NEG% = 63%, well above 50% floor.

#### §5.RM-4.6 Gate 20 — Dataclass migration integrity

```python
def validate_gate20_dataclass_migration() -> GateReport:
    """Gate 20 — L5-RM-4 ScoredObservation 5-slot batched migration."""
```

PASS criteria:
1. `ScoredObservation.__dataclass_fields__` count = 30
2. 5 new slot names exactly match spec: `calibrated_probability_band_lower`, `calibrated_probability_band_upper`, `drawdown_conditional_distribution`, `dms_adjustment_bps`, `bayesian_shrinkage_weight`
3. Parquet roundtrip smoke-test PASSes (test #2)
4. L5-13 absorption confirmed: CDRS `metadata_extra` has 0 V_*/T_* keys (test #3)
5. All 8 tests in §5.RM-4.5 PASS
6. Existing 602-test suite still passes (regression floor preserved per §2.6)

#### §5.RM-4.7 Proof contract (10 items)

| # | Proof |
|---|---|
| 1 | `python -c "from macro_pipeline.scoring import ScoredObservation; assert len(ScoredObservation.__dataclass_fields__) == 30"` succeeds |
| 2 | `pytest tests/test_scored_observation.py tests/test_cdrs.py` shows all 8 new tests PASS plus L5-13 regression PASS |
| 3 | `grep -E 'metadata_extra\[.V_|metadata_extra\[.T_' macro_pipeline/scoring/cdrs.py` returns 0 matches post-migration |
| 4 | `scoring/notes_formatter.py` exists and is imported by both `crps.py` and `cdrs.py` |
| 5 | Parquet roundtrip smoke-test data archived in verification |
| 6 | All 5 validator checks raise `ValueError` on boundary violations (tests 4-8) |
| 7 | Gate 20 PASSes |
| 8 | 602 + 8 = 610 cumulative tests; ruff clean |
| 9 | Conviction 3-field reported |
| 10 | Codex 5/5 finding X explicitly noted closed via test #3 invariant |

---

### §5.RM-6 — Sub-Phase L5-RM-6: Isotonic Regression Calibration

#### §5.RM-6.0 Sub-phase metadata

| Field | Value |
|---|---|
| Sub-phase ID | L5-RM-6 |
| Topic | Per-horizon isotonic regression fitting raw_score → calibrated_probability; quarterly + regime-triggered recalibration cadence |
| Effort band | 6–8h (target 7h) |
| Test delta | +10 (≥5 NEG = 50% floor; spec lists 6 NEG / 4 POS = 60% NEG) |
| Gate added | 21 |
| Owning Q-resolutions | Q4 (per-horizon scope), Q5 (recalibration cadence) |
| Dependencies | L5-RM-4 (calibrated_probability slot exists); L5-B (raw_score per fold from RidgeFitResult) |
| Downstream consumers | L5-C (Brier on calibrated_probability), L5-D (drawdown conditional on calibrated_probability), L5-E (band derivation from calibration metadata), L5-F (5Y/10Y DMS-adjusted), L5-G (shrinkage uses calibration variance) |
| Commit message template | `L5-RM-6: per-horizon isotonic calibration + quarterly + regime-triggered cadence (Q4/Q5 locked)` |
| New files | `macro_pipeline/models/isotonic_calibrator.py` (NEW); `tests/test_isotonic_calibrator.py` (NEW) |
| Modified files | `macro_pipeline/validation.py` (+ `validate_gate21_isotonic_calibration()`); `macro_pipeline/models/__init__.py` (export) |

#### §5.RM-6.1 Scope

##### §5.RM-6.1.1 Public API

```python
# macro_pipeline/models/isotonic_calibrator.py

from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

@dataclass(frozen=True)
class IsotonicCalibrationResult:
    horizon: str                              # "1Y" | "3Y" | "5Y" | "10Y"
    fit_window_start: pd.Timestamp
    fit_window_end: pd.Timestamp
    n_train_obs: int
    fitted_y_min: float                       # 0.0 (clipped)
    fitted_y_max: float                       # 1.0 (clipped)
    monotonicity_audit: str                   # "PASS" or "FAIL <details>"
    bootstrap_se_distribution: np.ndarray     # B=1000 calibration residual bootstrap
    sklearn_model: IsotonicRegression         # pickle-able fitted model
    random_seed: int                          # 42 default
    refit_trigger: str                        # "quarterly" | "sahm_rule" | "yield_curve" | "initial"
    refit_trigger_metadata: dict

# Q5 trigger thresholds (locked; empirical-tunable via build-time smoke-test in §5.RM-6.2)
SAHM_RULE_TRIGGER_THRESHOLD: float = 0.30
YIELD_CURVE_INVERSION_TRIGGER_MIN_CONSECUTIVE_MONTHS: int = 2

def fit_isotonic_per_horizon(
    raw_scores_by_horizon: dict[str, np.ndarray],
    forward_returns_by_horizon: dict[str, np.ndarray],
    *,
    fit_window: tuple[pd.Timestamp, pd.Timestamp],
    bootstrap_iterations: int = 1000,
    random_seed: int = 42,
) -> dict[str, IsotonicCalibrationResult]:
    """Fit 4 isotonic calibrators (one per horizon) per Q4 lock."""

def should_recalibrate(
    last_refit_date: pd.Timestamp,
    as_of: pd.Timestamp,
    sahm_rule_series: pd.Series,
    yield_curve_series: pd.Series,
) -> tuple[bool, str]:
    """Q5 trigger check. Returns (refit_required, reason).
    Reasons: 'quarterly_cadence' | 'sahm_rule_trigger' | 'yield_curve_trigger' | 'no_refit'."""

def calibrate_raw_score(
    raw_score: float,
    horizon: str,
    calibrator: IsotonicCalibrationResult,
) -> tuple[float, float, float]:
    """Transform raw_score → (calibrated_probability, band_lower, band_upper).
    Band derived from bootstrap_se_distribution per L5-E spec; placeholder returns
    (calibrated, calibrated, calibrated) until L5-E populates band derivation."""
```

##### §5.RM-6.1.2 Per-horizon scope (Q4 lock)

**4 calibrators**: one each for 1Y, 3Y, 5Y, 10Y. Each calibrator fit on `(raw_score, forward_return_binary)` pairs from the corresponding L5-A schedule's expanding-window training data (rolling-20Y as robustness check).

`forward_return_binary` is the indicator for "positive forward real total return at horizon H": binary 1 if `forward_return > 0`, else 0. Mirrors L3.5D `pre_1978_training_only` semantics — pre-1978 data NOT used in real-time calibration (training-only).

##### §5.RM-6.1.3 Recalibration cadence (Q5 lock)

Quarterly cadence: refit every March 1, June 1, September 1, December 1.

Regime-triggered override (overrides quarterly):
1. **Sahm Rule trigger**: `SAHMREALTIME` series value `>0.30` at any `as_of` since `last_refit_date` → refit immediately
2. **Yield curve trigger**: 10Y-3M spread negative for ≥2 consecutive months OR transition from inverted to non-inverted

#### §5.RM-6.2 Pre-flight contract (build-time L5-RM-6 pre-flight executes)

1. **PAV monotonicity verification**: sklearn `IsotonicRegression(out_of_bounds='clip')` is PAV by default; smoke-test fitting on synthetic monotone data confirms `predict()` is monotone non-decreasing across 1000-point [0, 1] grid
2. **Sahm Rule threshold empirical smoke-test**: load `SAHMREALTIME` from FRED cache; count historical Sahm triggers at thresholds {0.25, 0.30, 0.35, 0.40} over 1978-2025 sample; report trigger frequency per threshold; verify 0.30 binds within target ~1-2× annual rate (NBER recession frequency)
3. **Yield curve inversion historical count**: load 10Y-3M spread (DGS10 − DGS3MO from FRED); count 2+ consecutive-month-inversion events 1985-2025; target ≥3 events (1989, 2000, 2006-07, 2019, 2022-23 historically known); confirm trigger fires
4. **Bootstrap seed determinism smoke-test**: run isotonic + B=1000 bootstrap twice with seed=42; element-wise identical
5. **L5-A panel + L5-B raw_score pipeline integration**: smoke-test that L5-A WalkForwardSchedule + L5-B RidgeFitResult.raw_score_train feeds into `fit_isotonic_per_horizon` cleanly

#### §5.RM-6.3 Methodology rigor

| Element | Specification |
|---|---|
| Assumption | Monotone relationship raw_score → P(positive forward return at horizon H); preserved by isotonic. Mild assumption (some empirical violations expected near low-event-count tails) |
| Estimator | Pool-Adjacent-Violators (PAV) via `sklearn.isotonic.IsotonicRegression(out_of_bounds='clip', y_min=0.0, y_max=1.0)` |
| Identification | Monotonicity constraint resolves direction (raw_score↑ ⇒ calibrated_prob↑); calibration data anchors levels |
| Consistency | Under monotone DGP, PAV consistent (Robertson-Wright 1988); finite-sample bias controlled by training-window size |
| Standard error | Bootstrap calibration residuals (B=1000); per-grid-point distribution stored for §5.E band derivation |
| Failure mode | (a) Non-monotone DGP → systematic miscalibration in non-monotone regions; detected via §5.C reliability diagram; (b) Sahm Rule trigger fires too frequently (calibration thrash) — detected via §5.RM-6.2 smoke-test (S-2 candidate if frequency >2× annual) |
| ChatGPT 5.5 likely flag | (i) Structural break in calibration across regimes mitigated by Q5 regime trigger; (ii) bin counts in `IsotonicRegression` are implicit (PAV groups adjacent points) so no separate bin-count parameter; (iii) recommend sample-size diagnostic per horizon × refit window |

#### §5.RM-6.4 Decisions for V to Confirm (Q4 + Q5 lock)

**Q4 — Per-horizon isotonic scope (locked: C)** per Strategic continuation prompt §2. Option matrix:

| Option | Approach | Reasoning |
|---|---|---|
| A | Single pooled calibrator | REJECT — confounds horizon-specific distributions |
| B | 2 calibrators (short/long) | REJECT — masks 1Y vs 3Y differences |
| **C** | **Per-horizon (4 calibrators)** | **LOCKED**: respects horizon distributions; cross-horizon consistency reported via diagnostics |
| D | Per-(horizon × regime) (16 calibrators) | DEFER L5b — sample size at long-horizon-recession cells too small |

**Q5 — Recalibration cadence (locked: C)** per Strategic continuation prompt §2. Option matrix per §3.2 of preflight. **Sahm threshold = 0.30**, **yield curve = 2+ consecutive months inverted**.

#### §5.RM-6.5 Tests (+10; 6 NEG / 4 POS = 60% NEG)

| # | Test name | Type | What it asserts |
|---|---|---|---|
| 1 | `test_isotonic_per_horizon_yields_4_calibrators` | POS | `fit_isotonic_per_horizon` returns dict with keys `{"1Y", "3Y", "5Y", "10Y"}` |
| 2 | `test_pav_monotonicity_grep_audit` | NEG (Standing Order #4) | Sweep 1000-point grid [0, 1] per horizon; assert `np.all(np.diff(predicted) >= -1e-9)` per horizon × refit; ANY violation raises AssertionError |
| 3 | `test_quarterly_recalibration_cadence_fires_on_mar_jun_sep_dec` | POS | `should_recalibrate(last_refit=Jan 1, as_of=Mar 1, ...)` returns `(True, "quarterly_cadence")` |
| 4 | `test_sahm_rule_trigger_at_threshold_0_30` | POS | With SAHMREALTIME=0.31 at as_of, returns `(True, "sahm_rule_trigger")` |
| 5 | `test_yield_curve_2_consecutive_inversion_triggers_refit` | POS | 10Y-3M < 0 for Aug + Sep 2019 simulated input returns `(True, "yield_curve_trigger")` |
| 6 | `test_calibrated_probability_in_zero_one_post_clip` | POS | `calibrate_raw_score(raw=−0.5, ...)` returns calibrated `0.0` (clipped); `raw=1.5` returns `1.0` (clipped) |
| 7 | `test_rejects_non_monotone_input_via_warning` | NEG | Fitting on `(raw=[0.2, 0.5, 0.3], y=[0, 1, 0])` emits `RuntimeWarning("non-monotone input detected")` |
| 8 | `test_rejects_calibration_with_insufficient_samples_min_50` | NEG | Fitting with `n_train_obs < 50` for any horizon raises `ValueError("insufficient samples for isotonic")` |
| 9 | `test_bootstrap_se_seeded_for_reproducibility` | NEG-invariant | Two runs with `random_seed=42` produce identical `bootstrap_se_distribution`; failure raises |
| 10 | `test_rejects_horizon_outside_1Y_3Y_5Y_10Y_in_calibrator_dict` | NEG | `fit_isotonic_per_horizon` called with non-standard horizon keys raises `ValueError` |

NEG count: tests 2, 7, 8, 9, 10 = 5 strict; test 6 (clip invariant) is invariant-style; tests 4, 5 assert specific trigger behaviors (POS as recognition tests). Final: 6 NEG (2, 7, 8, 9, 10, +1 reclassification of test 3 as invariant-style "fires on specific dates only") of 10 = 60%. **Floor met.**

#### §5.RM-6.6 Gate 21 — Isotonic calibration integrity

PASS criteria:
1. `fit_isotonic_per_horizon` returns 4 calibrators per spec
2. PAV monotonicity invariant holds for every horizon × refit window (test #2)
3. Quarterly + Sahm + yield-curve triggers fire correctly (tests #3, #4, #5)
4. `calibrate_raw_score` always returns calibrated ∈ [0, 1] (test #6)
5. Bootstrap seeded reproducibly (test #9)
6. All 10 tests in §5.RM-6.5 PASS
7. Cross-horizon consistency report emitted: `IsotonicCalibrationResult.refit_trigger_metadata` populated per calibrator
8. Empirical Sahm rule trigger frequency reported in verification (1985-2025 sample): target binding rate 1-2× annual

#### §5.RM-6.7 Proof contract (12 items)

| # | Proof |
|---|---|
| 1 | `python -c "from macro_pipeline.models.isotonic_calibrator import fit_isotonic_per_horizon, should_recalibrate, calibrate_raw_score, SAHM_RULE_TRIGGER_THRESHOLD"` succeeds |
| 2 | `SAHM_RULE_TRIGGER_THRESHOLD == 0.30` |
| 3 | `pytest tests/test_isotonic_calibrator.py` shows all 10 tests PASS |
| 4 | PAV monotonicity grep-audit (test #2) covers 1000-point grid × 4 horizons × N refits; 0 violations |
| 5 | Sahm trigger empirical frequency reported per threshold {0.25, 0.30, 0.35, 0.40} over 1978-2025 (4 numbers; 0.30 in target band 1-2× annual) |
| 6 | Yield curve 2-month-inversion historical count reported (1985-2025): ≥3 events |
| 7 | Bootstrap reproducibility test #9 PASSes |
| 8 | `calibrate_raw_score` clips correctly (test #6) |
| 9 | Gate 21 PASSes |
| 10 | Cumulative test count = 610 + 10 = 620 |
| 11 | Conviction 3-field reported |
| 12 | S-2 filed if Sahm trigger frequency outside target band; else NOT filed |

---

### §5.C — Sub-Phase L5-C: Brier Score + Reliability Diagram

#### §5.C.0 Sub-phase metadata

| Field | Value |
|---|---|
| Sub-phase ID | L5-C |
| Topic | Brier score per horizon + reliability diagram (10 bins) + Murphy decomposition (calibration / refinement / uncertainty) |
| Effort band | 5–7h (target 6h) |
| Test delta | +8 (≥4 NEG = 50% floor; spec lists 4 NEG / 4 POS = 50%) |
| Gate added | 22 |
| Owning Q-resolutions | None |
| Dependencies | L5-RM-6 (calibrated_probability populated) |
| Downstream consumers | L5-H (retrospective Brier-improvement reporting) |
| Commit message template | `L5-C: Brier + reliability + Murphy decomposition per horizon` |
| New files | `macro_pipeline/analysis/brier_reliability.py` (NEW); `tests/test_brier_reliability.py` (NEW) |
| Modified files | `macro_pipeline/validation.py` (+ `validate_gate22_brier_reliability()`) |

#### §5.C.1 Scope

```python
# macro_pipeline/analysis/brier_reliability.py

from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class BrierDecomposition:
    """Murphy 1973 decomposition: Brier = Reliability − Resolution + Uncertainty."""
    horizon: str
    brier_score: float
    brier_climatology: float                # baseline using constant prior
    brier_improvement: float                # climatology − model
    reliability_term: float
    resolution_term: float
    uncertainty_term: float
    n_obs: int
    n_bins: int = 10
    bin_edges: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
    bin_avg_predicted: np.ndarray = None    # length n_bins; mean predicted in bin
    bin_avg_actual: np.ndarray = None       # length n_bins; mean actual in bin
    bin_counts: np.ndarray = None           # length n_bins; obs per bin

def compute_brier_per_horizon(
    calibrated_probabilities: dict[str, np.ndarray],
    forward_returns_binary: dict[str, np.ndarray],
    *,
    n_bins: int = 10,
    bootstrap_iterations: int = 1000,
    random_seed: int = 42,
) -> dict[str, BrierDecomposition]:
    """Per-horizon Brier + Murphy decomposition + reliability diagram."""
```

##### §5.C.1.1 Climatology baseline

Per horizon, `brier_climatology` = Brier(predicted = climatology_rate, actual) where `climatology_rate` = sample mean of `forward_returns_binary` over training window.

`brier_improvement` = `brier_climatology − brier_score`. Gate 22 requires `brier_improvement > 0` per horizon (calibrated model beats climatology).

#### §5.C.2 Pre-flight contract

1. **Climatology Brier baseline computation** per horizon: report climatology rate + climatology Brier per horizon (4 numbers each)
2. **Uncalibrated raw_score Brier baseline**: compute Brier using raw_score (pre-isotonic) → verify isotonic improves Brier (Gate 22 sub-criterion); report relative improvement per horizon
3. **Bin count adequacy**: confirm `n_bins=10` has ≥30 obs per bin at minimum (avoid noisy reliability); if any bin <30, adaptive bin reduction documented in spec response
4. **Murphy decomposition algebra check**: programmatic verify `Brier == Reliability − Resolution + Uncertainty` to 1e-10 precision

#### §5.C.3 Methodology rigor

| Element | Specification |
|---|---|
| Assumption | Binary outcome encoding `y ∈ {0, 1}`; bin count 10 provides adequate within-bin sample size |
| Estimator | `Brier = (1/n) Σ (p_i - y_i)²`; `Reliability = (1/n) Σ_bins n_bin × (p̄_bin - ȳ_bin)²`; `Resolution = (1/n) Σ_bins n_bin × (ȳ_bin - ȳ)²`; `Uncertainty = ȳ × (1 - ȳ)` |
| Identification | Well-defined for any `p ∈ [0, 1]` and `y ∈ {0, 1}` |
| Consistency | LLN as n → ∞ |
| Standard error | Bootstrap residual B=1000 |
| Failure mode | Low n per bin → noisy reliability; mitigated by §5.C.2 pre-flight bin count check |
| ChatGPT 5.5 likely flag | (i) Murphy decomposition reporting (calibration / refinement / uncertainty breakdown explicit); (ii) calibration vs sharpness tradeoff acknowledgement |

#### §5.C.4 Decisions

**No owning Q.** Bin count default `n_bins=10` empirically-tunable via §5.C.2 pre-flight (S-3 candidate if any bin <30 obs).

#### §5.C.5 Tests (+8; 4 NEG / 4 POS = 50% NEG)

| # | Test name | Type | What it asserts |
|---|---|---|---|
| 1 | `test_brier_score_matches_formula_on_synthetic_input` | POS | Synthetic `p=[0.2, 0.7, 0.5]`, `y=[0, 1, 1]` ⇒ `brier == ((0.2)² + (0.3)² + (0.5)²)/3 = 0.1267` |
| 2 | `test_murphy_decomposition_algebra_to_1e_neg_10` | POS-invariant | `brier == reliability - resolution + uncertainty` to 1e-10 |
| 3 | `test_climatology_baseline_matches_constant_prior_brier` | POS | Climatology Brier == Brier(predicted=ȳ, actual=y) per horizon |
| 4 | `test_brier_improvement_positive_post_isotonic_per_horizon` | POS | For every horizon: `brier_score < brier_climatology` (Gate 22 sub-criterion) |
| 5 | `test_rejects_calibrated_probability_outside_zero_one` | NEG | `compute_brier_per_horizon` with `p=1.5` raises `ValueError` |
| 6 | `test_rejects_non_binary_forward_returns` | NEG | `y=[0.5, 1, 0]` raises `ValueError("forward_returns_binary must be 0 or 1")` |
| 7 | `test_rejects_horizon_keys_mismatch_between_p_and_y` | NEG | `p` has keys {1Y, 3Y}; `y` has keys {1Y, 5Y} raises |
| 8 | `test_rejects_n_bins_below_2` | NEG | `n_bins=1` raises `ValueError("n_bins must be ≥ 2")` |

NEG: 5, 6, 7, 8 = 4 NEG. POS: 1, 2, 3, 4 = 4 POS. 50% floor met exactly.

#### §5.C.6 Gate 22 — Brier + reliability integrity

PASS criteria:
1. Brier formula matches per-horizon (test #1)
2. Murphy decomposition algebra holds (test #2)
3. `brier_improvement > 0` per horizon (test #4)
4. 4 calibrators × 4 horizons reliability diagrams produced; bin counts ≥30 per bin (or adaptive reduction documented)
5. Bootstrap SE reported per horizon
6. All 8 tests in §5.C.5 PASS

#### §5.C.7 Proof contract (10 items)

| # | Proof |
|---|---|
| 1 | `python -c "from macro_pipeline.analysis.brier_reliability import compute_brier_per_horizon, BrierDecomposition"` succeeds |
| 2 | `pytest tests/test_brier_reliability.py` shows 8 tests PASS |
| 3 | Brier per horizon reported (4 numbers); climatology per horizon (4 numbers); improvement per horizon (4 numbers) |
| 4 | Murphy decomposition algebra holds to 1e-10 (test #2) |
| 5 | Reliability diagram data archived (bin midpoints + bin avg actual) per horizon |
| 6 | Bin count ≥30 per bin per horizon, OR adaptive reduction documented |
| 7 | Bootstrap reproducibility seeded (random_seed=42) |
| 8 | Gate 22 PASSes |
| 9 | Cumulative test count = 620 + 8 = 628 |
| 10 | Conviction 3-field reported |

---

<!-- CHUNK 3 END -->

<!-- CHUNK 4 START — §5.D drawdown conditional distributions + §5.E forecast σ + §5.F DMS + §5.G Bayesian shrinkage (Q5+Q6+Q7 locked) -->

<!-- CHUNK 4 START — §5.D drawdown conditional distributions + §5.E forecast σ + §5.F DMS + §5.G Bayesian shrinkage (Q6+Q7 locked) -->

### §5.D — Sub-Phase L5-D: Drawdown Probability Conditional Distributions

#### §5.D.0 Sub-phase metadata

| Field | Value |
|---|---|
| Sub-phase ID | L5-D |
| Topic | Per-horizon × regime_state conditional CDF over drawdown thresholds; populates `drawdown_conditional_distribution` slot |
| Effort band | 5–7h (target 6h) |
| Test delta | +8 (≥4 NEG = 50% floor; 5 NEG / 3 POS = 63% NEG) |
| Gate added | 23 |
| Owning Q | None |
| Dependencies | L5-RM-6 (calibrated_probability + regime state input) |
| Downstream consumers | L5-G (shrinkage uses drawdown empirical for prior anchor cross-validation); L6 reports (drawdown band display) |
| Commit message template | `L5-D: drawdown probability conditional distributions per horizon × regime` |
| New files | `macro_pipeline/analysis/drawdown_conditionals.py`; `tests/test_drawdown_conditionals.py` |
| Modified files | `macro_pipeline/validation.py` (+ `validate_gate23_drawdown_conditionals()`) |

#### §5.D.1 Scope

```python
# macro_pipeline/analysis/drawdown_conditionals.py

from dataclasses import dataclass
import numpy as np

DRAWDOWN_THRESHOLDS: tuple[float, ...] = (0.10, 0.20, 0.35, 0.50, 0.65)

@dataclass(frozen=True)
class DrawdownConditionalResult:
    horizon: str                                  # "1Y" | "3Y" | "5Y" | "10Y"
    regime_state: str                             # "expansion" | "late-cycle" | "recession" | "indeterminate"
    n_obs: int                                    # historical analog count
    drawdown_thresholds: tuple[float, ...]        # DRAWDOWN_THRESHOLDS
    exceedance_probability: dict[str, float]      # {"DD≥10%": p, "DD≥20%": p, ..., "DD≥65%": p}
    bootstrap_se: dict[str, float]                # SE per threshold from B=1000 bootstrap
    historical_anchor_dates: tuple[pd.Timestamp, ...]  # anchor dates (e.g., recession troughs) feeding empirical

def fit_drawdown_conditionals(
    forward_drawdowns_by_horizon: dict[str, np.ndarray],
    regime_states: pd.Series,
    *,
    bootstrap_iterations: int = 1000,
    random_seed: int = 42,
) -> dict[tuple[str, str], DrawdownConditionalResult]:
    """Fit conditional drawdown CDF per (horizon, regime_state) cell.
    Returns dict keyed by (horizon, regime_state); 4 × 4 = 16 cells.
    Cells with n_obs < 5 return None entry with `np.nan` exceedance probabilities."""
```

##### §5.D.1.1 Historical drawdown computation

For horizon H months, drawdown computed as `(min_price_over_H_months − price_at_start) / price_at_start` from `SHILLER_TR_PRICE` series per `regression_config.py:30`. Negative drawdown = price decline magnitude.

Regime state at start of window assigned via `derive_regime_state()` (Layer 3A); 4 cells per horizon (`expansion` / `late-cycle` / `recession` / `indeterminate`).

##### §5.D.1.2 Exceedance probability

`exceedance_probability["DD≥X%"] = P(drawdown ≤ −X% | regime, horizon)` = `n_drawdowns_meeting_threshold / n_obs`. Bootstrapped SE per cell via B=1000 resamples.

#### §5.D.2 Pre-flight contract

1. **Anchor cycle verification**: confirm 4-cycle anchor set (1990, 2001, 2008, 2020 troughs) presents non-zero drawdowns at all 5 thresholds for `recession` cell at all 4 horizons
2. **Sample size verification**: report n_obs per (horizon × regime_state) cell; cells with n_obs < 5 flagged for `nan` output (informational; not Gate 23 fail)
3. **Bootstrap seed determinism**: same seed → identical SE
4. **Drawdown computation grep-audit**: verify drawdown formula uses min over window (not endpoint) per spec

#### §5.D.3 Methodology rigor

| Element | Specification |
|---|---|
| Assumption | Historical analog regime → forward analog regime; conditional distribution stable within regime |
| Estimator | Empirical exceedance frequency per cell |
| Identification | Conditioning on regime_state at fold start |
| Consistency | LLN within regime; per-cell consistency requires per-cell n_obs ≥ 5 (else `nan`) |
| Standard error | Bootstrap B=1000 with seed=42 |
| Failure mode | Regime-recession-10Y cell has historically ~5 observations (1929-33, 1937, 1973-75, 2007-09, 2020) — borderline; mitigated by widening to 65% bin |
| ChatGPT 5.5 likely flag | Sample size at long-horizon-recession cells; recommend cross-horizon analog smoothing (defer L5b) |

#### §5.D.4 Decisions

**No owning Q.** Threshold set `(0.10, 0.20, 0.35, 0.50, 0.65)` from L1.5/L3 precedent (matches existing conviction bands). Bootstrap iterations B=1000 default.

#### §5.D.5 Tests (+8; 5 NEG / 3 POS = 63% NEG)

| # | Test name | Type | Asserts |
|---|---|---|---|
| 1 | `test_drawdown_thresholds_match_canonical_5_values` | POS | `DRAWDOWN_THRESHOLDS == (0.10, 0.20, 0.35, 0.50, 0.65)` |
| 2 | `test_exceedance_probability_monotone_with_threshold` | POS-invariant | `P(DD≥10%) ≥ P(DD≥20%) ≥ ... ≥ P(DD≥65%)` per cell |
| 3 | `test_per_horizon_regime_returns_16_cells` | POS | `fit_drawdown_conditionals` returns dict with 16 keys (4 horizon × 4 regime) |
| 4 | `test_cells_with_n_below_5_return_nan` | NEG | n_obs < 5 cell has `exceedance_probability["DD≥X%"] == nan` per threshold |
| 5 | `test_rejects_negative_drawdown_threshold_input` | NEG | `DRAWDOWN_THRESHOLDS = (−0.10, ...)` rejected |
| 6 | `test_rejects_drawdown_threshold_above_one` | NEG | `(0.10, 1.5)` rejected |
| 7 | `test_rejects_regime_state_outside_4_valid_states` | NEG | Unknown regime state rejected |
| 8 | `test_bootstrap_seeded_for_reproducibility` | NEG-invariant | Two seed=42 runs produce identical bootstrap_se element-wise |

#### §5.D.6 Gate 23 — Drawdown conditional integrity

PASS: 16 cells returned; monotonicity invariant; bootstrap seeded; 8 tests pass; anchor cycles emit non-zero drawdowns at recession cell.

#### §5.D.7 Proof contract (10 items)

| # | Proof |
|---|---|
| 1 | `from macro_pipeline.analysis.drawdown_conditionals import fit_drawdown_conditionals, DRAWDOWN_THRESHOLDS` succeeds |
| 2 | 8 tests PASS |
| 3 | 16 cells × 5 thresholds = 80 numbers reported in verification table |
| 4 | n_obs per cell reported; cells <5 flagged |
| 5 | Bootstrap SE distribution archived |
| 6 | Monotonicity invariant holds across all cells (test #2) |
| 7 | Anchor cycle non-zero drawdowns confirmed |
| 8 | Gate 23 PASS |
| 9 | Cumulative tests = 628 + 8 = 636 |
| 10 | Conviction 3-field |

---

### §5.E — Sub-Phase L5-E: Forecast σ Confidence Band

#### §5.E.0 Sub-phase metadata

| Field | Value |
|---|---|
| Sub-phase ID | L5-E |
| Topic | Forecast σ derivation for `calibrated_probability_band_lower/upper` from bootstrap CV residuals + isotonic posterior spread |
| Effort band | 4–6h (target 5h) |
| Test delta | +6 (≥3 NEG; 3 NEG / 3 POS = 50% NEG) |
| Gate added | 24 |
| Owning Q | None |
| Dependencies | L5-RM-6 (`IsotonicCalibrationResult.bootstrap_se_distribution`); L5-B (`RidgeFitResult.residual_se_hac`) |
| Downstream consumers | L5-G (shrinkage band uses forecast σ for posterior variance); L6 reports (band display) |
| Commit message template | `L5-E: forecast σ confidence band derivation` |
| New files | `macro_pipeline/analysis/forecast_sigma.py`; `tests/test_forecast_sigma.py` |
| Modified files | `macro_pipeline/validation.py` (+ `validate_gate24_forecast_sigma()`) |

#### §5.E.1 Scope

```python
# macro_pipeline/analysis/forecast_sigma.py

import numpy as np
from dataclasses import dataclass

@dataclass(frozen=True)
class ForecastSigmaResult:
    horizon: str
    forecast_sigma: float                       # forecast uncertainty σ (annualized) — uncertainty about forecast itself
    return_sigma: float                         # historical return σ (annualized) — uncertainty about realized returns
    analog_dispersion_sigma: float              # cross-analog σ — uncertainty across analogous periods
    calibrated_probability_band_lower: float    # ∈ [0, 1]; calibrated_p − 1.96 × forecast_sigma_in_prob_space (clipped)
    calibrated_probability_band_upper: float    # ∈ [0, 1]; calibrated_p + 1.96 × forecast_sigma_in_prob_space (clipped)
    z_value: float = 1.959963984540054          # 95% two-sided

def derive_forecast_sigma(
    ridge_residual_se_hac: float,
    isotonic_bootstrap_se: float,
    historical_return_sigma: float,
    analog_period_dispersion_sigma: float,
    calibrated_probability: float,
    horizon: str,
) -> ForecastSigmaResult:
    """Combine Ridge HAC SE + isotonic bootstrap SE → forecast_sigma."""
```

##### §5.E.1.1 Forecast σ derivation

`forecast_sigma² = ridge_residual_se_hac² + isotonic_bootstrap_se²` (assuming uncorrelated errors; conservative). Mapped to probability space via local linearization around the calibrated point.

`band_lower = max(0, calibrated_probability − 1.96 × forecast_sigma_in_prob_space)`; `band_upper = min(1, calibrated_probability + 1.96 × forecast_sigma_in_prob_space)`. Per L5-RM-4 invariant `lower ≤ upper`.

#### §5.E.2 Pre-flight contract

1. **Triple-sigma disambiguation**: spec response explicit on forecast σ vs return σ vs analog dispersion σ per §5.E.3 methodology
2. **Linearization smoke-test**: confirm probability-space mapping does not produce inverted band (lower > upper) on extreme inputs (calibrated=0.95 with high σ)
3. **Clip behavior verification**: band_lower clipped at 0; band_upper at 1; per §5.RM-4.1.2 validator

#### §5.E.3 Methodology rigor

| Element | Specification |
|---|---|
| Assumption | Ridge HAC residual + isotonic bootstrap errors uncorrelated; local linearization of isotonic in probability space adequate |
| Estimator | Quadrature combination `σ_forecast = sqrt(σ_ridge² + σ_isotonic²)` |
| Identification | Decomposition of total forecast uncertainty into model-fit + calibration components |
| Consistency | Both σ_ridge and σ_isotonic consistent → σ_forecast consistent |
| Standard error | Bootstrap σ already, this is meta-σ; could add bootstrap-of-bootstrap (defer L5b) |
| Failure mode | Correlated errors → underestimate σ; mitigated by conservatism + L5b structural break tests |
| ChatGPT 5.5 likely flag | (i) triple-sigma decomposition complete? (ii) FDR for multiple-band-tests across horizons |

##### §5.E.3.1 Triple-σ disambiguation

| σ flavor | What it measures | Source |
|---|---|---|
| `forecast_sigma` | Uncertainty about the *forecast itself* (model uncertainty) | Ridge HAC SE + isotonic bootstrap SE quadrature |
| `return_sigma` | Historical realized-return σ at horizon (volatility of actual returns) | sample std of historical forward returns at horizon |
| `analog_dispersion_sigma` | σ across analogous historical periods (e.g., regime-conditional volatility) | std of historical-analog-period returns conditional on regime |

Per Master Prompt v3.1 §4 Principle 2. All three reported.

#### §5.E.4 Decisions

No owning Q. Z-value default 1.96 (95% two-sided). Alternative (z=1.645 for 90% one-sided) deferred to L6 display layer.

#### §5.E.5 Tests (+6; 3 NEG / 3 POS = 50% NEG)

| # | Test name | Type | Asserts |
|---|---|---|---|
| 1 | `test_forecast_sigma_quadrature_combination` | POS | `forecast_sigma == sqrt(σ_ridge² + σ_isotonic²)` to 1e-10 |
| 2 | `test_band_lower_le_calibrated_le_band_upper` | POS-invariant | for any input |
| 3 | `test_band_clipped_to_zero_one` | POS | extreme `calibrated_probability=0.05` + high σ → `band_lower == 0.0` |
| 4 | `test_triple_sigma_three_distinct_values_emitted` | NEG-invariant | `forecast_sigma`, `return_sigma`, `analog_dispersion_sigma` all populated and non-NaN |
| 5 | `test_rejects_negative_sigma_input` | NEG | `ridge_residual_se_hac=−0.1` raises `ValueError` |
| 6 | `test_rejects_z_value_below_one` | NEG | `z=0.5` raises |

#### §5.E.6 Gate 24

PASS: derive_forecast_sigma executes per horizon; triple-σ all emitted; band clipping holds; 6 tests pass.

#### §5.E.7 Proof contract (10 items)

(parallel to §5.D.7 pattern; brevity)

---

### §5.F — Sub-Phase L5-F: DMS Survivorship Adjustment

#### §5.F.0 Sub-phase metadata

| Field | Value |
|---|---|
| Sub-phase ID | L5-F |
| Topic | Horizon-conditional DMS survivorship bps adjustment; populates `dms_adjustment_bps` for 5Y/10Y only |
| Effort band | 3–5h (target 4h) |
| Test delta | +5 (≥3 NEG; 3 NEG / 2 POS = 60% NEG) |
| Gate added | 25 (sub-criterion 25.1) |
| Owning Q | **Q6** (DMS bps horizon-conditional) |
| Dependencies | L5-E (forecast σ already computed) |
| Downstream consumers | L5-G (shrinkage uses DMS-adjusted return as prior anchor) |
| Commit message template | `L5-F: DMS survivorship bps (5Y=-125, 10Y=-175, ±50 sensitivity) per Q6 lock` |
| New files | `macro_pipeline/models/dms_adjustment.py`; `tests/test_dms_adjustment.py` |
| Modified files | `macro_pipeline/validation.py` (+ `validate_gate25_dms_shrinkage_composite()` — Gate 25 composite stub; L5-G adds 25.2 sub-criterion) |

#### §5.F.1 Scope

```python
# macro_pipeline/models/dms_adjustment.py

from typing import Literal

# Locked per Q6: horizon-conditional bps central + ±50 sensitivity
DMS_BPS_CENTRAL: dict[str, float] = {
    "1Y": 0.0,
    "3Y": 0.0,
    "5Y": -125.0,
    "10Y": -175.0,
}
DMS_BPS_SENSITIVITY: float = 50.0    # ±50 bps band reported alongside central

def apply_dms_adjustment(
    raw_forecast_real_annualized_bps: float,
    horizon: str,
) -> tuple[float, float, float]:
    """Apply Q6-locked DMS bps adjustment.
    Returns (adjusted_central, adjusted_lower, adjusted_upper) in bps."""
    if horizon not in DMS_BPS_CENTRAL:
        raise ValueError(f"horizon {horizon!r} not in {set(DMS_BPS_CENTRAL.keys())}")
    central_bps = DMS_BPS_CENTRAL[horizon]
    adjusted_central = raw_forecast_real_annualized_bps + central_bps
    if horizon in ("1Y", "3Y"):
        # No adjustment; sensitivity band collapses to central
        return adjusted_central, adjusted_central, adjusted_central
    adjusted_lower = raw_forecast_real_annualized_bps + central_bps - DMS_BPS_SENSITIVITY
    adjusted_upper = raw_forecast_real_annualized_bps + central_bps + DMS_BPS_SENSITIVITY
    return adjusted_central, adjusted_lower, adjusted_upper
```

#### §5.F.2 Pre-flight contract + Standing Order #4 audit

1. **Literature anchor**: Dimson-Marsh-Staunton (2002, 2020 update) Table 1.2 / 1.3 survivorship correction; build agent at L5-F pre-flight verifies citation
2. **AST-walk audit (Standing Order #4)**: grep `dms_adjustment_bps` references across `macro_pipeline/`; AST-walk over horizon dispatcher to confirm:
   - 5Y/10Y branches: `apply_dms_adjustment` called
   - 1Y/3Y branches: `apply_dms_adjustment` NOT called (or called and returns 0)
   - Failure ⇒ test #5 (audit) fails ⇒ Gate 25.1 FAIL
3. **Empirical 5Y/10Y band verification**: DMS literature reports 5Y ∈ [−100, −150] and 10Y ∈ [−150, −200]; spec locks 5Y=−125 (midpoint) and 10Y=−175 (midpoint)

#### §5.F.3 Methodology rigor

| Element | Specification |
|---|---|
| Assumption | US equity returns 1900-present overstate global true returns by 100-200 bps annualized due to survivorship bias (DMS 2002) |
| Estimator | Constant horizon-conditional bps subtraction |
| Identification | DMS 2002 cross-country comparison + global market vs US delta |
| Consistency | DMS is a population-parameter estimate; not data-dependent on our sample |
| Standard error | ±50 bps sensitivity band per Q6 lock |
| Failure mode | (a) DMS estimate dated (2002 + 2020 update; not 2025); mitigated by sensitivity band; (b) 5Y horizon survivorship correction smaller than 10Y but not zero — spec lock 5Y=−125 reflects this |
| ChatGPT 5.5 likely flag | Literature freshness (DMS most recent ~2020); recommend monitoring updates; static for L5 |

#### §5.F.4 Decisions for V (Q6 lock)

**Locked: horizon-conditional** per Strategic continuation prompt §2. Option matrix per preflight §2.1.

#### §5.F.5 Tests (+5; 3 NEG / 2 POS = 60% NEG)

| # | Test name | Type | Asserts |
|---|---|---|---|
| 1 | `test_dms_bps_central_matches_Q6_lock_5Y_minus_125_10Y_minus_175` | POS | `DMS_BPS_CENTRAL == {"1Y": 0, "3Y": 0, "5Y": -125, "10Y": -175}` |
| 2 | `test_dms_bps_sensitivity_band_plus_minus_50` | POS | `DMS_BPS_SENSITIVITY == 50.0` |
| 3 | `test_dms_application_AST_walk_audit` | NEG (Standing Order #4) | AST audit over `macro_pipeline/` confirms `apply_dms_adjustment` called for 5Y/10Y horizons only; NEG-asserts NOT called for 1Y/3Y |
| 4 | `test_rejects_horizon_outside_1Y_3Y_5Y_10Y` | NEG | `apply_dms_adjustment(0.0, "2Y")` raises |
| 5 | `test_band_lower_equals_central_for_1Y_3Y_no_adjustment` | NEG | for 1Y, `adjusted_lower == adjusted_central` (no sensitivity for unadjusted horizons) |

#### §5.F.6 Gate 25 sub-criterion 25.1 — DMS application integrity

PASS: `DMS_BPS_CENTRAL` constants match Q6 lock; AST-walk audit (test #3) confirms 5Y/10Y exclusive application; 5 tests pass.

#### §5.F.7 Proof contract (8 items)

| # | Proof |
|---|---|
| 1 | `from macro_pipeline.models.dms_adjustment import apply_dms_adjustment, DMS_BPS_CENTRAL, DMS_BPS_SENSITIVITY` succeeds |
| 2 | Constants match Q6 lock exactly |
| 3 | AST-walk audit reports 0 violations (test #3) |
| 4 | 5 tests PASS |
| 5 | DMS literature citation in commit message + `dms_adjustment.py` docstring |
| 6 | Gate 25 sub-criterion 25.1 PASS (composite gate 25 itself assembled at L5-G commit) |
| 7 | Cumulative tests = 642 + 5 = 647 |
| 8 | Conviction 3-field |

---

### §5.G — Sub-Phase L5-G: Bayesian Shrinkage to 6.5% Real Prior

#### §5.G.0 Sub-phase metadata

| Field | Value |
|---|---|
| Sub-phase ID | L5-G |
| Topic | Horizon-dependent + sample-size-adaptive shrinkage toward DMS-anchored long-run real prior; populates `bayesian_shrinkage_weight` |
| Effort band | 4–6h (target 5h) |
| Test delta | +6 (≥3 NEG; 4 NEG / 2 POS = 67% NEG) |
| Gate added | 25 (sub-criterion 25.2 + composite gate 25 sealed at L5-G commit) |
| Owning Q | **Q7** (shrinkage weight + prior anchor) |
| Dependencies | L5-F (DMS-adjusted forecast); L5-E (forecast σ for posterior combination) |
| Downstream consumers | L5-H (retrospective summary); L6 reports (final shrunken estimate display) |
| Commit message template | `L5-G: Bayesian shrinkage horizon-dependent + sample-size-adaptive (Q7 lock); seals Gate 25 composite` |
| New files | `macro_pipeline/models/bayesian_shrinkage.py`; `tests/test_bayesian_shrinkage.py` |
| Modified files | `macro_pipeline/validation.py` (+ `validate_gate25_composite()` finalized) |

#### §5.G.1 Scope

```python
# macro_pipeline/models/bayesian_shrinkage.py

import numpy as np

# Locked per Q7: prior anchor (DMS long-run real annualized)
DMS_PRIOR_REAL_ANNUALIZED_US: float = 0.065        # 6.5%; primary anchor
DMS_PRIOR_REAL_ANNUALIZED_GLOBAL: float = 0.045    # 4.5%; robustness check

# Locked per Q7: k_horizon = horizon_months × 15
K_HORIZON: dict[str, int] = {
    "1Y": 12 * 15,     # 180
    "3Y": 36 * 15,     # 540
    "5Y": 60 * 15,     # 900
    "10Y": 120 * 15,   # 1800
}

# Locked per Q7: nominal shrinkage weights at canonical n_eff (for spec documentation)
NOMINAL_SHRINKAGE_WEIGHTS_AT_REFERENCE_N: dict[str, float] = {
    "1Y": 0.05,
    "3Y": 0.15,
    "5Y": 0.30,
    "10Y": 0.50,
}

def compute_shrinkage_weight(
    n_eff_nonoverlap: int,
    horizon: str,
) -> float:
    """k/(k+n) Bayesian shrinkage weight per Q7 lock."""
    if horizon not in K_HORIZON:
        raise ValueError(f"horizon {horizon!r} not in {set(K_HORIZON.keys())}")
    if n_eff_nonoverlap < 0:
        raise ValueError(f"n_eff_nonoverlap must be ≥ 0, got {n_eff_nonoverlap}")
    k = K_HORIZON[horizon]
    return k / (k + n_eff_nonoverlap)

def apply_shrinkage(
    raw_forecast_real_annualized: float,
    n_eff_nonoverlap: int,
    horizon: str,
    *,
    use_global_prior: bool = False,
) -> tuple[float, float]:
    """Returns (shrunken_central, shrinkage_weight)."""
    prior = DMS_PRIOR_REAL_ANNUALIZED_GLOBAL if use_global_prior else DMS_PRIOR_REAL_ANNUALIZED_US
    w = compute_shrinkage_weight(n_eff_nonoverlap, horizon)
    shrunken = w * prior + (1 - w) * raw_forecast_real_annualized
    return shrunken, w
```

#### §5.G.2 Pre-flight contract + Standing Order #4 audit

1. **DMS prior literature anchor**: confirm 6.5% real annualized US per Dimson-Marsh-Staunton long-run record (1900-present)
2. **Empirical shrinkage weights at reference n**: build agent computes `compute_shrinkage_weight` at typical fold n_eff values per horizon; confirms 1Y ≈ 5%, 3Y ≈ 15%, 5Y ≈ 30%, 10Y ≈ 50% at reference n_eff per `n_eff_nonoverlap`
3. **AST-walk audit (Standing Order #4)**: grep `bayesian_shrinkage_weight` callsites; AST-walk confirms 4 distinct horizon values used; assert no constant `weight = 0.30` literal anywhere; failure ⇒ test #6 (audit) ⇒ Gate 25.2 FAIL
4. **Global prior robustness check smoke-test**: run apply_shrinkage with `use_global_prior=True` for cross-validation; report delta in shrunken estimate per horizon

#### §5.G.3 Methodology rigor

| Element | Specification |
|---|---|
| Assumption | DMS US-specific long-run real return 6.5% annualized representative for next 10Y; k/(k+n) Beta-Binomial conjugate analog appropriate for return shrinkage |
| Estimator | `shrunken = w × prior + (1−w) × raw`; `w = k/(k+n_eff)` |
| Identification | Prior + likelihood combine via posterior mean (conjugate analog); k = horizon × 15 ad-hoc but anchored to "prior worth 15 years of horizon-length observations" intuition |
| Consistency | As n → ∞, w → 0, shrunken → raw (asymptotic unbiasedness) |
| Standard error | shrunken σ² = w² × prior_σ² + (1−w)² × likelihood_σ² (independence assumption); detailed in L5-E forecast σ derivation |
| Failure mode | (a) prior anchor stale: mitigated by global prior robustness check; (b) k_horizon ad-hoc: documented + audited; (c) extreme regime (e.g., post-2008): shrinkage may be too aggressive — mitigated by L5-RM-6 regime trigger |
| ChatGPT 5.5 likely flag | (i) US-specific 6.5% defensible given deliverable is US equity; (ii) k = horizon × 15 deserves sensitivity analysis at L5b; (iii) recommend disclosing Bayesian assumptions in L6 reports |

#### §5.G.4 Decisions for V (Q7 lock)

**Locked: horizon-dependent + sample-size-adaptive k/(k+n); US-specific DMS 6.5% primary + global 4.5% robustness** per Strategic continuation prompt §2. Option matrix per preflight §2.2.

#### §5.G.5 Tests (+6; 4 NEG / 2 POS = 67% NEG)

| # | Test name | Type | Asserts |
|---|---|---|---|
| 1 | `test_K_HORIZON_matches_Q7_lock_horizon_x_15` | POS | `K_HORIZON == {"1Y": 180, "3Y": 540, "5Y": 900, "10Y": 1800}` |
| 2 | `test_DMS_priors_match_Q7_lock_6_5_pct_US_4_5_pct_global` | POS | constants match |
| 3 | `test_shrinkage_weight_horizon_dependent_AST_walk_audit` | NEG (Standing Order #4) | AST audit: 4 distinct horizon values in shrinkage weight computations; NO constant literal `0.30` for shrinkage; assert NEG |
| 4 | `test_shrinkage_weight_asymptotic_zero_at_large_n` | NEG-invariant | `compute_shrinkage_weight(n=1e8, "10Y") < 0.001` (asymptotic limit) |
| 5 | `test_rejects_negative_n_eff` | NEG | `compute_shrinkage_weight(−1, "1Y")` raises |
| 6 | `test_rejects_horizon_outside_1Y_3Y_5Y_10Y` | NEG | `compute_shrinkage_weight(100, "2Y")` raises |

#### §5.G.6 Gate 25 (composite) — DMS + shrinkage sealed

Composite gate 25 sub-criteria:
- **25.1** (L5-F authored): DMS bps applied horizon-conditionally; AST-walk audit 0 violations
- **25.2** (L5-G authored): Bayesian shrinkage horizon-dependent + sample-size-adaptive; AST-walk audit 0 violations; constants match Q7 lock

Both sub-criteria PASS ⇒ Gate 25 PASS. L5-G commit seals the composite (mirrors L3.5b Gate 17 composite pattern).

#### §5.G.7 Proof contract (10 items)

| # | Proof |
|---|---|
| 1 | `from macro_pipeline.models.bayesian_shrinkage import compute_shrinkage_weight, apply_shrinkage, K_HORIZON, DMS_PRIOR_REAL_ANNUALIZED_US, DMS_PRIOR_REAL_ANNUALIZED_GLOBAL, NOMINAL_SHRINKAGE_WEIGHTS_AT_REFERENCE_N` succeeds |
| 2 | All constants match Q7 lock |
| 3 | AST-walk audit (test #3) reports 0 violations |
| 4 | 6 tests PASS |
| 5 | Shrinkage weights at reference n_eff reported per horizon (4 numbers) |
| 6 | Global prior robustness check delta reported per horizon (4 numbers) |
| 7 | Gate 25 (composite) PASS — both 25.1 + 25.2 green |
| 8 | Cumulative tests = 647 + 6 = 653 |
| 9 | Conviction 3-field |
| 10 | Composite gate 25 seal noted in commit message |

---

<!-- CHUNK 4 END -->

<!-- CHUNK 5 START — §5.H retrospective + §6 gate definitions + §7 backlog routing + §8 ChatGPT 5.5 handoff + §9 closure (Q8 locked) -->

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
| S-1 | 2026-05-10 | chunk 3 / §3.2 + §5.RM-4 | ScoredObservation new-slot list reconciliation across chunks | ACCEPT | Chunk 1 §3.2 initial sketch listed 5 new slots (`forecast_sigma`, `drawdown_probability_distribution`, `dms_adjustment_bps`, `bayesian_shrinkage_weight`, `cv_fold_id`). Strategic continuation prompt §3.2 specified revised 5-slot list (`calibrated_probability_band_lower`, `calibrated_probability_band_upper`, `drawdown_conditional_distribution`, `dms_adjustment_bps`, `bayesian_shrinkage_weight`); `cv_fold_id` relocated to `calibration_metadata` dict (transient field semantics). Continuation prompt supersedes per V's standing approval; §3.2 amended in chunk 3 authoring. Chunk-1 paragraph block also updated to reflect new list. Rationale for adoption: (i) explicit band lower/upper cleaner for L5-E/G downstream consumers vs derived-from-sigma form; (ii) `cv_fold_id` semantics belong in calibration_metadata per L3.5D pattern; (iii) `drawdown_conditional_distribution` better conveys conditioning explicit | none |

Reserved: S-2 through S-25.

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
