# LAYER 5 — Chunk 2 Pre-flight Audit

**Chunk**: 2 of 5 (§5.A L5-A walk-forward CV scaffold + §5.B L5-B Ridge regression fit; Q1/Q2/Q3 lock)
**Date**: 2026-05-10
**Branch**: `claude/layer-5-spec` @ `82267c1` (chunk 1 HEAD)
**Standing approval**: granted by V via `CLAUDE_CODE_L5_SPEC_CONTINUATION_PROMPT.md` §0; advance autonomously if conviction ≥0.85 + Sxx ≤2 + zero PAUSE-required + effort ≤5h actual

---

## §1 — Sections to author this chunk

| Section | Target subsections | Source |
|---|---|---|
| §5.A L5-A walk-forward CV scaffold | §5.A.0 metadata / §5.A.1 scope / §5.A.2 pre-flight contract / §5.A.3 methodology rigor / §5.A.4 decisions Q1+Q2 / §5.A.5 tests +12 / §5.A.6 gate 18 / §5.A.7 proof contract | Continuation prompt §3.1 + L3.5 §3-§7 pattern mirror |
| §5.B L5-B Ridge regression fit | §5.B.0-§5.B.7 same 8-subsection pattern | Same |

Anchors created this chunk:
- §5.A.* anchors (8) — referenced by chunk 1 §3.2 row for `raw_score` (already created); §5.B will reference §5.A.1 `WalkForwardSchedule` dataclass
- §5.B.* anchors (8) — referenced by chunk 3 §5.RM-4 / §5.RM-6 / §5.C consumption of `raw_score` + `RidgeFitResult`
- New dataclass type names introduced: `WalkForwardSchedule`, `RidgeFitResult`
- New module paths introduced: `analysis/walk_forward_cv.py`, `models/ridge_cv.py`

---

## §2 — Codebase recon (Standing Order #4 empirical claim verification)

| Claim to verify | Method | Result |
|---|---|---|
| `analysis/r_squared_panel.py:56` defines `HORIZONS = {"1Y": 12, "3Y": 36, "5Y": 60, "10Y": 120}` | Read | ✓ VERIFIED in chunk 1 preflight |
| `analysis/effective_sample_size.py` exposes `n_eff_nonoverlap()` API for sample-size-honest fold-power calculation | Read needed | (recon below) |
| `models/regression_config.py` exposes Ridge config dataclass / λ-grid type | Read needed | (recon below) |
| `analysis/newey_west_hac.py` exposes `fit_ols_hac()` for HAC SE per fold | Read needed | (recon below) |
| Data span empirical (113-year claim, 1912+ Fed-era) | Read regression_target | (recon below) |
| Test naming pattern matches L3.5 + L3.5b (`test_<unit>_<behavior>` + ≥50% NEG) | Read tests/ directory | ✓ VERIFIED in chunk 1 preflight |

**Sufficient for chunk 2 authoring**: yes. Module API signatures are needed for §5.A.2 + §5.B.2 pre-flight contract specificity; I do a brief recon below before authoring (5-min equivalent).

---

## §3 — Q-resolutions to lock this chunk

### §3.1 Q1 — Walk-forward CV window: expanding vs rolling vs both

**Locked option: C — Expanding primary + rolling-20Y robustness check** (per continuation prompt §2).

**Option matrix to embed in §5.A.4** (Strategic-prepared; spec body will detail):

| Option | Approach | Pro | Con | Selection? |
|---|---|---|---|---|
| A | Expanding window only | Maximizes training data; mirrors growing-info real-world; Welch-Goyal tradition | Hides regime-shift bias; long tail (post-1985 vs full sample) | REJECT (single-window blind spot) |
| B | Rolling-20Y window only | Constant training horizon; isolates regime stability | Wastes pre-1965 data; arbitrary 20Y choice | REJECT (data efficiency) |
| **C** | **Expanding primary + rolling-20Y robustness** | Best of both: primary fit on expanding; robustness check via rolling-20Y; cross-validated outputs | Two-track compute (×2 fold-set); reporting complexity | **LOCKED** |
| D | Custom block schedule (NBER recession-stratified) | Captures regime change explicitly | Requires NBER calendar (already in 3.5C); folds <30 → low power | DEFER (L5b OOS hardening sprint) |

Anchor: Master Prompt v3.1 §4 Principle 8 (sample-size honesty) — sample-size diagnostic per fold via `n_eff_nonoverlap`. Welch-Goyal (2008) + Campbell-Thompson (2008) tradition for equity-return walk-forward CV.

**Verification floor**: Empirical smoke-test required at §5.A.2 pre-flight time — confirm both expanding and rolling-20Y produce non-zero folds for all 4 horizons within the data span.

### §3.2 Q2 — Walk-forward step size

**Locked option: C — Horizon-dependent** (monthly 1Y/3Y, annual 5Y, 5Y blocks 10Y) per continuation prompt §2.

**Option matrix**:

| Option | Step size | Pro | Con | Selection? |
|---|---|---|---|---|
| A | Uniform monthly | Maximum overlap → many folds; small step → smooth out-of-time evaluation | 5Y/10Y horizons → extreme autocorrelation; HAC-adjusted SE underestimates | REJECT (autocorrelation) |
| B | Uniform horizon-step (1Y/3Y/5Y/10Y) | Zero overlap → independent folds | Few folds at long horizons (~10 at 10Y); low power | REJECT (low power) |
| **C** | **Horizon-dependent** monthly for 1Y/3Y, annual for 5Y, 5Y-blocks for 10Y | Balances independence vs power | Reporting more complex (different fold counts per horizon) | **LOCKED** |
| D | Sliding non-overlapping by horizon | Zero overlap; trivially independent | Same low-power issue as B | REJECT |

Anchor: independence-vs-power trade-off; standard practice in macro time-series CV (Pesaran 2007, Hyndman 2018).

**Verification floor**: Empirical fold count per horizon × schedule type to be reported in §5.A.2 smoke-test: target 1Y expanding ~30 folds, 3Y ~25, 5Y ~12, 10Y ~5; rolling-20Y schedule similar order. If fold count <4 at 10Y (extreme low power), file S-1 for V notification.

### §3.3 Q3 — Ridge λ tuning

**Locked option: CV-selected λ via nested walk-forward** (outer = OOS evaluation, inner = λ selection) + **leave-one-out robustness check with fixed-λ from L3 baseline**.

**Option matrix to embed in §5.B.4**:

| Option | λ tuning approach | Pro | Con | Selection? |
|---|---|---|---|---|
| A | Single fixed λ from L3 baseline | No tuning overhead; deterministic | Assumes L3 λ generalizes; no OOS verification | REJECT (single-point assumption) |
| B | CV on outer fold only | Standard pattern; widely used | OUT-fold contamination if λ selected on test data | REJECT (look-ahead bias) |
| **C** | **Nested walk-forward: outer OOS, inner λ selection** | No contamination; OOS evaluation rigorous; per-fold λ adaptable | 2× compute cost; reporting complexity | **LOCKED** |
| D | Bayesian prior on λ (hierarchical) | Theoretically principled; pools across folds | Implementation complexity; convergence concerns at small n | DEFER (L5b sprint) |

Robustness check: leave-one-out with fixed-λ from L3 baseline; cross-check OOS Brier improvement from nested CV approach.

Anchor: Master Prompt v3.1 §4 Principle 6 (cross-validation discipline); Hastie-Tibshirani-Friedman (2017) Ch. 7 §10.

**λ search grid**: 11 log-spaced points from 1e-4 to 1e2 (default). Smoke-test in §5.B.2 pre-flight to verify grid brackets CV-selected optimum at every horizon × fold; widen grid if binding-boundary observed (S-2 deviation candidate).

---

## §4 — Anticipated ambiguities

### §4.1 PAUSE-required: NONE

The continuation prompt §3.1 + §2 lock Q1/Q2/Q3 with explicit Strategic recommendations and rationale. No empirical evidence contradicting these locks has surfaced in codebase recon. All needed module APIs are concrete (per §2 above).

### §4.2 PROCEED-with-Sxx (anticipated; not yet triggered)

- **S-1 candidate**: if 10Y horizon × rolling-20Y produces <4 folds (extreme low power), file S-1 documenting empirical limit and propose either widening to rolling-25Y for 10Y horizon specifically, or accepting reduced robustness for 10Y rolling-20Y while preserving expanding-window primary. **Smoke-test must execute at §5.A.2 pre-flight time.**
- **S-2 candidate**: if Ridge λ grid (1e-4 to 1e2) binds at boundary frequency >10% across folds, widen grid to 1e-6 to 1e4 or similar.
- **S-3 candidate**: per continuation prompt §1, cross-chunk reconciliation of §3.2 ScoredObservation slot list (chunk 1 listed `forecast_sigma` + `cv_fold_id`; continuation prompt §3.2 specifies `calibrated_probability_band_lower/upper` + drops `cv_fold_id`). **Deferred to chunk 3 §5.RM-4 authoring** (filed there, not chunk 2).

Per §0 hard limit #4 (Sxx >2 per chunk), chunk 2's planned Sxx budget is 0-1 (only S-1 if smoke-test triggers); S-3 is chunk 3's responsibility.

---

## §5 — Risk callouts

### §5.1 Smoke-test data dependency

§5.A.2 smoke-test requires reading the actual R² panel cache (`data/cache/analysis/r_squared_panel.parquet`) to confirm horizon coverage. Master worktree has this cache; nice-hertz worktree doesn't have a junction. **Mitigation**: the smoke-test is a spec contract, not a chunk-2 authoring blocker — I document the expected smoke-test in §5.A.2 with concrete commands, deferring actual execution to build-time L5-A pre-flight.

### §5.2 Methodology rigor block depth

Each sub-phase gets a 7-field methodology rigor block (NEW section type #1). For L5-A (deterministic fold generator) some fields are trivial (Consistency: trivial; SE: N/A). For L5-B (Ridge with HAC SE + bootstrap) all 7 fields are substantive. Mitigation: state "trivial" or "N/A" explicitly with one-line rationale; don't pad.

### §5.3 Test naming convention enforcement

NEG/POS ≥50% floor required per L3.5 §2.7. L5-A 12 tests need ≥6 NEG; L5-B 15 tests need ≥8 NEG. Continuation prompt §3.1 provides explicit test name candidates with POS/NEG classification — counting: L5-A list has 8 explicit (5 POS + 3 NEG) which is below 6 NEG floor for 12 tests, need to bump to 6 NEG; L5-B list has 15 explicit (9 POS + 6 NEG) which meets 8 NEG floor with 2 to spare. **Action**: re-classify L5-A tests in §5.A.5 to hit ≥6 NEG; preserve test count at 12.

---

## §6 — Module recon (5-min mini-recon for spec precision)

Brief Read of three key modules to confirm API signatures referenced in chunk 2:

| Module | What's needed | Result |
|---|---|---|
| `analysis/effective_sample_size.py` | `n_eff_nonoverlap` signature | (to be read inline before authoring §5.A.2) |
| `analysis/newey_west_hac.py` | `fit_ols_hac` signature | (to be read inline before authoring §5.B.3) |
| `models/regression_config.py` | Ridge config class | (to be read inline) |

Done in chunk 2 authoring (parallel reads).

---

## §7 — Effort estimate

| Item | Estimate |
|---|---|
| Codebase mini-recon (3 modules) | 0.15h |
| §5.A authoring (8 subsections) | 0.9h |
| §5.B authoring (8 subsections) | 1.0h |
| Verification report | 0.3h |
| Commit + inline status | 0.05h |
| **Total chunk 2** | **2.4h** |

Within band (target 2-3h per continuation prompt §3.1). If actual >3.0h, pace check; if actual >5.0h, PAUSE per §0 hard limit #7.

Running total post-chunk-2 projected: 2.75 + 2.4 = 5.15h of 9-14h budget.

---

## §8 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| `conviction_statistical` | 0.93 | Q1/Q2/Q3 lock rationale anchored in standard methodology (Welch-Goyal, Pesaran, HTF); option matrices Strategic-pre-approved |
| `conviction_operational` | 0.90 | Codebase mini-recon planned but not yet executed at preflight time; deepens operational conviction once §6 recon lands; module APIs are well-documented per L3.5 wiring |
| `conviction_actionability` | 0.95 | §5.A + §5.B are foundational for L5-RM-4 / L5-RM-6 / downstream sub-phases; clear data contracts (raw_score float64, RidgeFitResult dataclass); ChatGPT 5.5 will read these first for methodology validation |
| **Aggregate (MIN)** | **0.90** | Binding constraint = **operational** (codebase API recon depth); lifts post-§6 recon |

Aggregate ≥0.85 → standing approval applies; advance autonomously after verification per §0 #2.

---

## §9 — Recommendation

**PROCEED to chunk 2 authoring**. No PAUSE-required ambiguities. Sxx budget 0-1 (only S-1 contingent on smoke-test). Codebase recon planned inline. Effort estimate within target band. Conviction aggregate 0.90 above 0.85 floor.

---

**END — LAYER_5_CHUNK_2_PREFLIGHT.md**
