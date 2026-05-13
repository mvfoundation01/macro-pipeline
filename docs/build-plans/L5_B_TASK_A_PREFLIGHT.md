# L5-B Task A Pre-Flight Plan

**Date**: 2026-05-13
**Branch target**: `claude/layer-5-build-plan` (consolidates with `L5_BUILD_PLAN_v1.md` for single Strategic-review surface; rationale: same planning theme; linear history; avoids branch sprawl)
**L5-A precedent**: ACCEPT @ `claude/layer-5-build` tag `l5-a-accept` (commit `20ec8f2`); ChatGPT 5.5 foundation-gate review pending
**Spec ref**: `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` §5.B Task A (lines 561-806)
**Build plan ref**: `claude/layer-5-build-plan @ 32cce8b` ITEM 2 row 2

---

## ITEM 1 — L5-A consumption surface confirmation

### §1.1 Task A's consumption pattern (per spec §5.B.1.1)

```python
def fit_composite_weights(
    schedule: WalkForwardSchedule,           # ← L5-A export
    component_panel: pd.DataFrame,
    event_labels: pd.Series,
    *,
    score_type: str,                          # "CRPS" | "CDRS"
    lambda_grid: tuple[float, ...] = LAMBDA_GRID_DEFAULT,
    drawdown_threshold: float | None = None,
    inner_fold_count: int = 5,
    random_seed: int = 42,
) -> tuple[CompositeWeightRefitResult, ...]:
```

Task A's L5-A dependency: `WalkForwardSchedule` (the schedule for one horizon × schedule_type pair). For each outer fold (`fold.fold_id`, `fold.train_start`, `fold.train_end`, `fold.test_start`, `fold.test_end`), Task A:
1. Builds an inner walk-forward schedule on `[train_start, train_end]` for λ selection (`inner_fold_count=5`)
2. Refits penalized logistic on full outer-fold training window with selected λ
3. Predicts on outer-fold test partition → emits `CompositeWeightRefitResult`

### §1.2 L5-A export surface audit

| Required by Task A | L5-A export | Status |
|---|---|---|
| `WalkForwardSchedule` (class) | Exported from `macro_pipeline.analysis` (and `walk_forward_cv`) | ✓ |
| `WalkForwardFold` (class) | Exported | ✓ |
| `schedule.folds` (tuple of WalkForwardFold) | Provided by dataclass field | ✓ |
| `fold.train_start / train_end / test_start / test_end / fold_id` | Dataclass fields | ✓ |
| `generate_schedule(horizon, schedule_type, panel_index, ...)` | Exported (Task A reuses for inner CV) | ✓ |
| `STEP_SIZE_MONTHS` constant | Exported (Task A inherits step-size policy for inner schedule) | ✓ |
| `MIN_TRAIN_WINDOW_MONTHS_DEFAULT` constant | Exported | ✓ |
| `HORIZONS` mapping | Exported (re-exported from r_squared_panel) | ✓ |

**Verdict: NO L5-A consumption gap.** Task A can be implemented directly against the L5-A public API as currently exported. No pre-emptive Sxx (T1) needed.

### §1.3 Hidden assumption check: inner walk-forward feasibility

Inner CV on `[train_start, train_end]` (typically 240+ months for first fold; up to 1357 months for last expanding fold) with `inner_fold_count=5`:
- For first fold (240 months, expanding/rolling): 5 sub-folds × ~48 months each. With horizon=12 (1Y) and gap=12, first inner test_start needs ≥ 240 + 12 − 1 = 251 months. Inner window of 240 months provides ZERO inner folds → **risk surfaced**.
- For first 5Y/10Y fold (240 months, gap=60/120): inner schedule with `min_train_window_months=240` requires panel index ≥ 240 + gap months. Inner window of 240 months → 0 folds → **same risk**.

**Mitigation candidates for Task A code-exec**:
- Lower `min_train_window_months` for inner CV (e.g., 120 instead of 240); spec §5.B.1.2 doesn't dictate inner-CV minimum
- Use cumulative-residual inner-CV (sklearn TimeSeriesSplit style) instead of full walk-forward generator
- File T1 Sxx during Task A code-exec if inner-CV insufficient for early folds; propose adjustment

**Pre-emptive Sxx now (T1)?** NO — this is a Task A implementation decision (which inner-CV mechanism to use), not a spec ambiguity. Spec §5.B.1.2 prescribes nested walk-forward but does NOT specify inner-CV min_train_window. Task A code-exec will choose; verification report will document.

---

## ITEM 2 — L5-B Task A scope (extracted from spec §5.B)

### §2.1 Inputs (per spec §5.B.1.1 + §5.B.1.5)

| Input | Type | Source | Notes |
|---|---|---|---|
| `schedule` | `WalkForwardSchedule` | L5-A `generate_schedule(horizon, schedule_type, panel_index, ...)` | One per horizon × schedule_type; Task A iterates `schedule.folds` |
| `component_panel` | `pd.DataFrame` | CRPS: 6 components (`yield_curve, sahm, lei, ism, fci, credit`); CDRS: 4 buckets (`valuation, sentiment, credit_liquidity, vol_breadth_technical`) + subcomponents | **REAL RISK**: component-level panel may not yet exist as L3 export — verify at Phase 0 of code-exec |
| `event_labels` | `pd.Series` | CRPS: NBER USREC 12M-forward labels (from L3.5b NBER calendar); CDRS: drawdown ≥ X% within H labels (compute from SHILLER_TR_PRICE) | NBER calendar exists; drawdown labels likely require helper |
| `score_type` | `str` | `"CRPS"` or `"CDRS"` | Required |
| `drawdown_threshold` | `float \| None` | CDRS only: ∈ {0.10, 0.20, 0.35, 0.50, 0.65} | None for CRPS; required for CDRS (NEG test A8) |
| `lambda_grid` | `tuple[float, ...]` | Default: `LAMBDA_GRID_DEFAULT = 10.0 ** np.linspace(-4, 2, 11)` | Configurable; widen via S-2 if grid-edge-bind rate > 10% |
| `inner_fold_count` | `int` | 5 | Time-ordered (no shuffling) |
| `random_seed` | `int` | 42 | Determinism |

### §2.2 Outputs

`CompositeWeightRefitResult` dataclass (frozen) with 16 fields per spec §5.B.1.1 lines 608-629:
- `fold_id`, `horizon`, `schedule_type`, `score_type`, `drawdown_threshold`
- `lambda_selected`, `lambda_grid`
- `component_coefficients: dict[str, float]` (per-component β; NOT scalar)
- `intercept`
- Metrics: `auc_oos`, `brier_oos`, `calibration_slope`, `calibration_intercept`
- CDRS-specific: `monotone_cdf_check: bool`
- `n_train_obs`, `n_test_obs`
- `grid_edge_bind: bool`
- `sign_flip_rate: float` (vs prior fold; target < 0.20 per A10 NEG test)
- `fit_timestamp: pd.Timestamp`

Return type: `tuple[CompositeWeightRefitResult, ...]` — one entry per fold of input schedule.

### §2.3 Test contract (spec §5.B.5.A; 12 logical tests)

| # | Test | Type | Notes |
|---|---|---|---|
| A1 | `test_task_a_composite_uses_component_level_matrix_not_scalar` | NEG (Standing Order #4 AST audit) | Universal-claim audit: component_panel ≥ 4 cols (CDRS) or ≥ 6 cols (CRPS) |
| A2 | `test_task_a_crps_against_nber_12m_labels` | POS | §3.3 event label compliance |
| A3 | `test_task_a_cdrs_against_drawdown_threshold_labels` | POS | §3.3 event label compliance |
| A4 | `test_task_a_outputs_per_component_coefficient_not_single_beta` | NEG | dict[str, float] not scalar |
| A5 | `test_task_a_rejects_scalar_raw_score_input` | NEG | 1-col DF raises |
| A6 | `test_task_a_lambda_selection_minimizes_brier` | POS-invariant | argmin verification |
| A7 | `test_task_a_auc_brier_calibration_slope_emitted_per_fold` | POS | All 4 metrics populated |
| A8 | `test_task_a_rejects_cdrs_without_drawdown_threshold` | NEG | CDRS w/o threshold raises |
| A9 | `test_task_a_per_component_coefficient_stability_across_folds` | POS-invariant | Cross-fold SD informational |
| A10 | `test_task_a_sign_flip_rate_below_20_percent` | NEG | Stability gate |
| A11 | `test_task_a_l2_coefficient_drift_reported` | POS | ‖β_t − β_{t-1}‖_2 per fold |
| A12 | `test_task_a_pit_safety_inherited_from_L5_A_folds` | NEG | panel_sha256 mismatch raises |

**NEG ratio**: A1, A4, A5, A8, A10, A12 = 6 strict + A6 invariant-NEG = 7/12 = 58% (≥ 50% floor per §2.7).

**Pytest instances**: probably 12 logical = 12 pytest instances (no parametrization in spec rows). However, CDRS-specific tests (A3, A8) may naturally parametrize × 5 drawdown thresholds. Build-time decision; spec is silent.

### §2.4 Gate 19 sub-criteria for Task A (spec §5.B.6 rows 1-7)

Gate 19 is the L5-B composite gate (Task A + Task B1 + Task B2). Task A contributes 7 sub-criteria (numbered 1-7 in spec §5.B.6):
1. `fit_composite_weights` executes for CRPS + CDRS across all 8 schedules × CDRS 5 drawdown_thresholds
2. AST audit confirms scalar `raw_score` NOT accepted (component matrix required)
3. `component_coefficients` is `dict[str, float]` with ≥ 4 keys (CDRS) or ≥ 6 keys (CRPS)
4. AUC + Brier + calibration slope/intercept populated per fold
5. CDRS monotone CDF check (`P(DD≥10%) ≥ P(DD≥20%) ≥ ... ≥ P(DD≥65%)` per fold)
6. `sign_flip_rate < 0.20` across consecutive folds (Standing Order #4 audit)
7. All 12 Task A tests in §5.B.5.A PASS

Task A's verification report can report **Task A sub-gate PASS** (sub-criteria 1-7) ahead of L5-B Task B1/B2 completion. Full Gate 19 closure deferred to post-Task-B2 acceptance.

### §2.5 Q-resolution applies

Q3 (Ridge λ tuning): locked at C (nested walk-forward; `inner_fold_count=5`). v2 amendment per S-3: lock applies **separately** to Task A (penalized logistic λ) and Task B (Ridge λ). Each task runs its own nested CV.

---

## ITEM 3 — Effort estimate refinement

### §3.1 Build plan v1 estimate vs L5-A actual

| Reference | Effort | Notes |
|---|---|---|
| Build plan v1 ITEM 2 row 2 | "included in 12-16 band" (L5-B umbrella) | Task A subdivision not explicit |
| Spec §5.B.0 metadata | 8-10h (target 9h) v1; **v2 expansion**: 12-16h post-S-3 split | Combined Task A + Task B1 + Task B2 |
| L5-A actual precedent | 3h actual vs 6-8h spec band → ~40% of upper-band | Foundation simplicity; precedent for similar discount on Task A |

### §3.2 Task A standalone effort estimate (v2)

| Phase | Sub-budget | Rationale |
|---|---|---|
| Phase 1: build worktree env-prep (cache + data/raw copy) + 602-baseline `pytest -x` full execution | 0.5h | Process improvement from L5-A dev #2; pre-emptive cache copy |
| Phase 2: read spec §5.B + §5.B.5.A + spec §3.3 calibration target schema (for event labels) | 0.5h | Already done in this pre-flight; minor refresh at code-exec |
| Phase 3.1: implement `CompositeWeightRefitResult` dataclass + `fit_composite_weights` function | 2.5h | Penalized logistic via sklearn; per-fold inner CV + outer fit; ~250 LOC estimated |
| Phase 3.2: implement 12 Task A tests | 1.5h | Test design clearer than L5-A (event label semantics fixed); fixture data may need helper |
| Phase 3.3: integration with NBER label loader + drawdown label helper | 0.75h | Reuse L3.5b NBER calendar; drawdown helper may already exist in L3C |
| Phase 4: full pytest + Gate 19 Task A sub-gate verification | 0.5h | `pytest -x` full execution (not collect-only) |
| Phase 5: review branch + commit + tag + report | 0.5h | Mirrors L5-A pattern |
| **Total** | **6.75h** | Within spec L5-B 12-16h band (allocating ~6.75h to Task A + 5-9h to B1 + 1-2h to B2) |

### §3.3 1.5× pause threshold

- Hard pause at **10h** for Task A alone (1.5× of 6.75h estimate).
- Soft check at 5h (75% of estimate): if more than 50% of remaining work outstanding, file T6 Sxx + escalate.

### §3.4 Variance from L5-A precedent

L5-A actual = 3h vs 6-8h spec band → ~40% of upper-band. Task A est. = 6.75h vs spec subdivision of 12-16h L5-B umbrella (Task A ≈ half) → ~45% of upper-band. **Consistent discount factor**; supports estimate reasonableness.

---

## ITEM 4 — Pre-execution risk register (Task A specific)

| # | Risk | Severity | Probability | Mitigation | Trigger to escalate |
|---|---|---|---|---|---|
| 1 | **L5-A surface API mismatch with Task A consumption** | L | 5% | §1 audit confirms no gap; Task A consumes only documented public surface | If discovered mid-code-exec → file T1 Sxx; do NOT silently extend L5-A surface |
| 2 | **Component panel not exported by L3** | **H** | 30% | Phase 0 of code-exec: grep `macro_pipeline/scoring/` + `macro_pipeline/analysis/` for `component_panel`-shaped export. If absent → file T1 Sxx + propose helper construction from existing CRPS/CDRS internals | Helper construction effort >1h → escalate (could materially change Task A budget) |
| 3 | **NBER USREC 12M-forward label availability + drawdown threshold labels** | M | 20% | NBER calendar exists from L3.5b. Drawdown labels: compute from SHILLER_TR_PRICE via rolling-max minus current. Helper may not exist; estimate 0.5h to author | Helper construction itself triggers methodology decisions → T7 Sxx (empirical calibration) |
| 4 | **Inner walk-forward CV insufficient at early folds (240-month train window with 5 sub-folds)** | M | 25% | §1.3 surfaced; implementation decision at code-exec; sklearn TimeSeriesSplit or custom mechanism | If `inner_fold_count` adjustment needed → T7 Sxx |
| 5 | **Test parametrization × 5 drawdown thresholds inflates pytest count beyond ±2 of build-plan estimate** | L | 30% | Build plan ITEM 2 says +12 (Task A); pytest may report 12 + 5×N parametrized = up to 30+ instances. Within G2 tolerance if reported as "12 logical / N pytest instances" | If logical count drifts → T2 Sxx |
| 6 | **Build worktree env setup (cache + data/raw) not done — Phase 1 baseline silently passes collection but fails full run** | M | repeated risk; 50% if not codified | **Adopt as process improvement** (see ITEM 5); Phase 1 includes `cp -r D:/macro_pipeline/data/{cache,raw} D:/macro_pipeline/.claude/worktrees/layer-5-build/data/` THEN `pytest -x --no-header` (NOT `--collect-only`) | If hit → file T4 Sxx (AP-AUTH violation detected) + add AP-AUTH-47 to register |

### §4.1 Severity summary

- **HIGH**: 1 (component panel availability — could materially change effort)
- **MEDIUM**: 3 (label helpers, inner CV minimum, env setup)
- **LOW**: 2 (L5-A surface gap; pytest instance count)

**Top mitigation lever**: Phase 0 code-exec MUST grep for component_panel export presence BEFORE estimating implementation effort. If absent, file T1 Sxx + propose helper at start, not mid-implementation.

---

## ITEM 5 — Process improvement adoption (from L5-A retrospective)

### §5.1 L5-A deviations summary (from L5-A report)

L5-A reported 4 deviations:
1. Pre-commit framework absent → direct `.git/hooks/pre-commit` install (handled; no follow-up needed)
2. **Phase 1 baseline was `pytest --collect-only` not full execution → 190 cache-related failures surfaced in Phase 3.5** ← adopt mitigation
3. Test #3 parametrization × 4 → 15 pytest instances vs 12 logical (within G2 tolerance; documented)
4. Gate 18 Criterion 4 SKIP in panel_only fixture mode (documented warning, not failure)

### §5.2 Deviation #2 mitigation (mandatory for Task A code-exec)

**Phase 1 of L5-B Task A code-exec MUST**:
1. Copy data from main worktree: `cp -r D:/macro_pipeline/data/cache D:/macro_pipeline/data/raw D:/macro_pipeline/.claude/worktrees/layer-5-build/data/`
2. Run **full** `pytest -x --no-header` (NOT `--collect-only`); expected: **617 passed** (602 baseline + 15 L5-A from `l5-a-accept` tag)
3. Verification report Phase 1 section MUST cite pytest pass count, NOT collection count

### §5.3 Build plan ITEM 7 update proposal (do NOT execute)

Propose for Strategic review: add to `L5_BUILD_PLAN_v1.md` ITEM 7.2 (build worktree creation):

> Build worktree env-setup completeness check:
> 1. `git worktree add ... -b claude/layer-5-build origin/main`
> 2. **`cp -r D:/macro_pipeline/data/cache D:/macro_pipeline/data/raw D:/macro_pipeline/.claude/worktrees/layer-5-build/data/`** (NEW; copy cache + raw data which are gitignored)
> 3. **`pytest -x --no-header`** (NEW; full execution; NOT `--collect-only`); verify 617 pass (602 + L5-A 15)

### §5.4 Candidate AP-AUTH-47 (proposed entry text)

```
| **AP-AUTH-47 NEW post-L5-A** | Build worktree env-setup beyond test collection — failing to provision `data/cache/` + `data/raw/` (gitignored per-worktree) from main worktree before Phase 1 baseline verification. `pytest --collect-only` succeeds (no cache needed for collection) but `pytest -x` fails on 190+ cache-dependent tests in test_r_squared_panel.py + test_tv_loader.py + cache-dependent suites. L5-A Phase 1 surfaced this as deviation #2; AP-AUTH-47 codifies the discipline. **Mitigation discipline**: Phase 1 of each L5 sub-phase code-exec MUST include `cp -r D:/macro_pipeline/data/{cache,raw} <build-worktree>/data/` AS A DISCRETE STEP, AND must run `pytest -x --no-header` (NOT `--collect-only`) to surface any data-dependency failure BEFORE proceeding to Phase 2. Verification report MUST cite full pytest pass count, not collection count. |
```

**Status**: PROPOSED. Strategic to approve before adding to spec §12 (would require v7 spec patch cycle) OR adding to build-phase AP register (separate document; preferred path since spec is FROZEN per AP-AUTH-44).

---

## ITEM 6 — Readiness verdict + conviction

### §6.1 Conviction 3-field

| Field | Value | Drivers |
|---|---|---|
| `conviction_statistical` | **0.94** | Task A spec is precise (penalized logistic + per-fold AST audit + sign-flip stability gate); inner-CV pattern standard (HTF 2017 §7.10); λ grid empirical bracket smoke-test defined; CDRS monotone CDF check well-defined |
| `conviction_operational` | **0.91** | L5-A foundation in place (no surface gap); pre-commit hooks active; process improvement from L5-A dev #2 adopted in §5.2. Remaining op risk: component panel availability (R2 HIGH; 30% probability); env-setup discipline new — first application of AP-AUTH-47-candidate at Task A code-exec |
| `conviction_actionability` | **0.94** | With Strategic greenlight + ChatGPT foundation gate ACCEPT, Task A can proceed immediately. Pre-flight identifies all known risks; mitigations enumerated; effort estimate 6.75h within precedent band |
| **Aggregate (MIN)** | **0.91** | **Binding: operational** (R2 component panel availability + env-setup discipline first-application) |

≥0.90 hard floor: **CLEARED**.

### §6.2 Verdict

**READY-WITH-CONDITIONS**.

3 conditions for full READY-TO-BUILD upgrade:

| Condition | Owner | Effort |
|---|---|---|
| **C1**: ChatGPT 5.5 foundation-gate review on L5-A returns ACCEPT-L5-A-FOUNDATION (or ACCEPT-WITH-NOTES) | ChatGPT 5.5 + V relay | ~6-24h after deployment |
| **C2**: Phase 0 of L5-B Task A code-exec confirms `component_panel` exportable from L3 (or files T1 Sxx with helper-construction proposal if not) | Track A at Task A Phase 0 | ~0.25h grep audit |
| **C3**: Strategic + V approve AP-AUTH-47-candidate (§5.4) for build-phase AP register OR explicitly defer adoption | Strategic + V | review-time only |

Upon C1 + C2 + C3 satisfied → **READY-TO-BUILD**; L5-B Task A code-exec begins per process discipline in §5.

### §6.3 Strategic-decision routing

| Outcome | Strategic action |
|---|---|
| Greenlight Task A (post-ChatGPT ACCEPT-L5-A) | Track A proceeds to Task A code-exec; component panel availability verified at Phase 0 |
| ChatGPT REVISE-L5-A returns | Task A blocked; pivot to L5-A patch cycle; this pre-flight remains valid for post-patch Task A kickoff |
| Strategic requests pre-flight revision | Track A iterates to v2 of this doc |

---

**END — L5_B_TASK_A_PREFLIGHT.md**
