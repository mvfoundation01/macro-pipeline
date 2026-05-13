# LAYER 5 — Codex 5/5 / ChatGPT 5.5 Review Package

**Spec**: `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` FROZEN since 2026-05-13
**Branch**: `claude/layer-5-build`
**Merge base**: `590e4a5` (L3.5b merge into main)
**HEAD at review-window-open**: L5-H final commit (tag `l5-h-accept` + `layer5-complete`)
**Sibling document**: `LAYER_5_RETROSPECTIVE.md` (§A through §I per spec §5.H.1)

Per spec §5.H.1 third deliverable: this document packages the L5 build for ChatGPT 5.5 / Codex 5-of-5 external review.

---

## Op-H-a — Manifest-hash discipline (AP-AUTH-48 v2)

**This document does NOT carry served-URL sha256 manifest hashes at L5-H commit time.** AP-AUTH-48 v2 served-hash discipline activates at **review-publication time** (when V or Strategic schedules ChatGPT review by publishing this package to a reviewable URL, post-`layer5-complete` push to GitHub). At that publication step:

1. Compute sha256 of each artifact referenced below pre-publication
2. After push to remote, verify each served-URL sha256 via `curl -sL <url> | sha256sum`
3. If any served-hash differs from local pre-push hash (Windows CRLF normalization being the typical cause per AP-AUTH-48 v2 codification), amend a MANIFEST file with served-content hashes and push correction

Per Op-H-a Strategic disposition (approved 2026-05-13), the L5-H ACCEPT commit captures review-content-readiness; manifest hash discipline is post-ACCEPT publication-time work.

---

## §1 — Branch link + diff summary against merge base

- **Branch**: `claude/layer-5-build`
- **Merge base**: `590e4a5` (L3.5b merge into main at 2026-05-10)
- **HEAD at `layer5-complete`**: L5-H final commit (sibling tag `l5-h-accept`)
- **Commits since merge base**: twenty-seven
- **Diff statistics** (against merge base): forty-four files changed; eleven-thousand-one-hundred-sixty-three insertions; sixty-two deletions

**Net new artifacts** (over and above L3.5b):

- New modules in `macro_pipeline/analysis/`: `walk_forward_cv.py`, `component_panel.py`, `brier_reliability.py`, `drawdown_conditionals.py`, `forecast_sigma.py`
- New modules in `macro_pipeline/models/`: `composite_refit.py`, `isotonic_calibrator.py`, `return_forecast.py`, `return_calibration.py`, `dms_adjustment.py`, `bayesian_shrinkage.py`
- New test files in `tests/`: eleven new test modules covering the same surfaces
- Modified `macro_pipeline/scoring/scored_observation.py` (L5-RM-4 six-slot batched migration)
- Modified `macro_pipeline/validation.py` (Gate 19-A / 19-B1 / 19-B2 / 20 / 21 / 22 / 23 / 24 / 25 composite validators added)
- New docs: `docs/ap_register.md`, `docs/build-plans/L5B_BACKLOG.md`, `docs/build-plans/L5_BUILD_SXX_LOG.md`, `docs/build-plans/L3_COMPONENT_PANEL_D2_DESIGN.md`

---

## §2 — Test count delta

| Reference point | Test count |
|---|---|
| L3.5b merge baseline (commit `590e4a5` on main) | six-hundred-two |
| L5-H ACCEPT (`layer5-complete`) | seven-hundred-seventeen |
| **Net delta** | **plus one-hundred-fifteen** |

Spec §5.H.1 expected approximately seventy-eight (the original "+78" anchor was a v1 number written before v2/v3/v4 expansion cycles added tests per S-2 / S-4 / S-6 / S-9). Actual delta exceeds the early anchor; symbolic AP-AUTH-52 derivation: net delta equals fifteen (L5-A) plus six (L3-patch) plus twelve (Task A) plus eight (RM-4) plus fourteen (RM-6) plus fourteen (Task B1) plus two (Task B2) plus ten pytest-instances at L5-C (eight logical) plus twelve (L5-D) plus nine (L5-E) plus five (L5-F) plus eight (L5-G) plus zero (L5-H closure) — totals reconcile to one-hundred-fifteen.

Per-sub-phase test count deltas archived in the retrospective §A table.

---

## §3 — Gate count delta

| Reference point | Gate count | New gates added at L5 |
|---|---|---|
| L3.5b merge | seventeen (Gates one through seventeen plus eighteen scaffolding partial) | n/a |
| L5-H ACCEPT | twenty-five | Gate 18 (L3D walk-forward CV; ratified at L5-A) + Gate 19 split into 19-A (Task A) + 19-B1 (Task B1) + 19-B2 (Task B2) per Strategic D-B1-2 + Gate 20 (RM-4 dataclass migration) + Gate 21 (RM-6 isotonic calibration) + Gate 22 (L5-C Brier + reliability + Murphy) + Gate 23 (L5-D drawdown conditionals) + Gate 24 (L5-E forecast sigma) + Gate 25 composite (25 point 1 DMS apply integrity + 25 point 2 Bayesian shrinkage integrity; SEALED at `l5-g-accept`) |

Composite gates: Gate 19 (three partial-PASS milestones 19-A / 19-B1 / 19-B2 across L5-B chain); Gate 25 (two sub-criteria 25 point 1 from L5-F + 25 point 2 from L5-G; SEALED).

CLI invocations: `python -m macro_pipeline.validation gate{N}` for any gate; aggregate "all gates PASS" achievable via sequential CLI sweep.

---

## §4 — Methodology rigor block index

Nine methodology rigor blocks across L5 sub-phases:

| Sub-phase | Section | Topic |
|---|---|---|
| L5-A | §5.A.3 | walk-forward CV regularity conditions |
| L5-B (Task A + Task B) | §5.B.3 | penalized logistic + Ridge with HAC SE + block bootstrap |
| L5-RM-4 | §5.RM-4.3 | dataclass batched migration safety |
| L5-RM-6 | §5.RM-6.3 | isotonic regression PAV monotonicity + quarterly + Sahm + yield-curve triggers |
| L5-C | §5.C.3 | Brier formula closed-form + Murphy decomposition (binned-brier identity exact for fixtures without within-bin probability variance) |
| L5-D | §5.D.3 | empirical exceedance per-cell + hierarchical pooling (v3 three-state taxonomy production / diagnostic_only / pooled; no raw nan) |
| L5-E | §5.E.3 | quadrature plus joint bootstrap (v2 per S-6); coverage inflation factor |
| L5-F | §5.F.3 | constant horizon-conditional bps subtraction (Q6 lock) |
| L5-G | §5.G.3 | k/(k+n) Beta-Binomial conjugate analog with K_HORIZON v2 backsolve per S-4 |

Spec §5.H.1 narrative says "seven blocks"; empirical count is nine (the spec line was authored at an earlier v-version count). Counts reconcile by acknowledging that the §5.B.3 block covers both Task A and Task B (unified per spec §5.B.0 metadata).

---

## §5 — Q1-Q8 lock summary

Eight Q-resolutions documented in spec; locked per Strategic continuation prompt §2 (out-of-tree reference; values verified at sub-phase implementation time).

| Q | Spec section | Lock | Sub-phase |
|---|---|---|---|
| Q1 | §5.A.4 | Walk-forward type: expanding plus rolling 20Y dual schedules | L5-A |
| Q2 | §5.A.4 | Step-size policy: horizon-dependent (1Y/3Y: one month; 5Y: twelve months; 10Y: sixty months) | L5-A |
| Q3 | §5.B.4 | Ridge lambda tuning: nested walk-forward (outer OOS + inner lambda selection); fixed-lambda-from-L3 robustness check | L5-B Task A and B1 |
| Q4 | §5.RM-6.4 | Calibration: isotonic regression (PAV monotone) | L5-RM-6 |
| Q5 | §5.RM-6.4 | Recalibration triggers: quarterly plus Sahm rule plus yield-curve inversion (ninety-day cooldown coalescing per S-7) | L5-RM-6 |
| Q6 | §5.F.4 | DMS bps: horizon-conditional (5Y minus one-twenty-five; 10Y minus one-seventy-five; plus-or-minus fifty sensitivity band) | L5-F |
| Q7 | §5.G.4 | Bayesian shrinkage: horizon-dependent plus sample-size-adaptive k/(k+n); US-specific six-point-five percent primary plus global four-point-five percent robustness | L5-G |
| Q8 | §5.H.4 | Horizon scope: all four horizons (1Y / 3Y / 5Y / 10Y) in L5 (REJECT staged options A and B per Master Prompt v3.1 §14) | L5-H |

Every L5-A through L5-G sub-phase produced outputs at all four horizons per Q8 lock; verified in retrospective §A table (sub-phase metrics) and §E section (slot population end-state).

---

## §6 — Sxx register (spec authoring S-1..S-9 plus build-time S-10..S-12)

### Spec-authoring Sxx (S-1 through S-9; closed during spec v1 through v6 cycles)

Per `LAYER_5_BUILD_SPEC.md` §10. Status at v6 freeze: all RESOLVED.

| Sxx | Topic | Resolution |
|---|---|---|
| S-1 | Anchor count drift (slot counts; tests; gates) | v6 anchor-table per §5.RM-4.8 |
| S-2 | RETURN_POSITIVE event-label slot expansion (five to six new slots) | v3 dataclass slot addition |
| S-3 | L5-B task split (Task A composite-weight refit + Task B return forecast) | v2 split per §5.B.1.0 |
| S-4 | K_HORIZON backsolve (v1 horizon_months times fifteen arithmetic inconsistency) | v2 backsolve k_h equals (w_ref / (1 minus w_ref)) times n_ref per §5.G.1 |
| S-5 | Drawdown cell sparsity nan-cliff | v3 three-state taxonomy production / diagnostic_only / pooled per §5.D.1.3 |
| S-6 | Forecast sigma independence assumption | v2 joint bootstrap plus empirical coverage per §5.E.3 |
| S-7 | Isotonic recalibration trigger coalescing (multiple same-window triggers) | v3 ninety-day cooldown per §5.RM-6.1.3 |
| S-8 | Build_event_labels dispatcher hard gate (CRPS / CDRS / RETURN_POSITIVE) | v3 dispatcher implementation per §5.RM-6.1.1 |
| S-9 | RETURN_POSITIVE circularity (Task B1 input vs output) | v3 Task B split into B1 (Ridge forecast input) + B2 (RETURN_POSITIVE calibration output) per §5.B.1.0 |

### Build-time Sxx (S-10 through S-12; closed during L5 build phase; reserved range S-10 through S-25)

| Sxx | Date | Topic | Resolution |
|---|---|---|---|
| S-10 | 2026-05-13 | component_panel not in L3 export surface | Option (iv) HYBRID — minimal L3 patch; ISM and CB LEI to L5b-2 |
| S-11 | 2026-05-13 | Gate 18 sidecar naming mismatch (L3D `<stem>.meta.json` vs L5-A test fixture `<stem>.<suffix>.meta.json`) | bug-fix in `_validate_panel_cache` accepting both conventions |
| S-12 | 2026-05-14 | Spec base-field count (twenty-five) vs production empirical (twenty-three); test #1 magic-number mismatch | RESOLVED-OPTION-A 2026-05-15 — implementation uses production empirical (twenty-nine total dataclass fields after L5-RM-4 six new slots); spec residue to L5b-4 |

### Net Sxx state at `layer5-complete`

- Spec authoring: nine resolved during v1-to-v6 cycles
- Build-time: three resolved in-cycle (S-10 / -11 / -12)
- Open: **zero**

---

## §7 — Standing Order #4 audit results

Standing Order #4 (Empirical claim verification for universal claims via grep / AST audit) was applied uniformly across L5 sub-phases. Audit results below.

### L5-A panel-sha PIT-safety propagation

- Audit pattern: `panel_sha256` propagation from `_validate_panel_cache` through `generate_schedule` through all eight schedules
- Result: PASS at Gate 18 CLI runtime (post-S-11 fix); panel_sha256 hash propagated correctly to all (1Y / 3Y / 5Y / 10Y) × (expanding / rolling_20y) schedules

### L5-B Task A scalar-vs-component-matrix audit

- Audit pattern: `fit_composite_weights` AST inspection — `component_panel` parameter must be DataFrame with at least four columns (CDRS) or at least six columns (CRPS); scalar `raw_score` rejected
- Result: PASS at test A1 (`test_task_a_composite_uses_component_level_matrix_not_scalar`) plus A5 (`test_task_a_rejects_scalar_raw_score_input`)

### L5-RM-6 PAV monotonicity grep audit

- Audit pattern: PAV monotonicity invariant — sweep one-thousand-point grid over isotonic calibrator; assert monotone non-decreasing within one e-minus-nine tolerance per calibrator across all twenty-five calibrators
- Result: PASS at test #2 (`test_pav_monotonicity_grep_audit`); twenty-five calibrators times one-thousand-point grid equals twenty-five-thousand grid points; zero violations

### L5-B Task B1 RETURN_POSITIVE non-input AST audit

- Audit pattern: `fit_return_forecast_task_b1` signature MUST NOT contain `positive_return_probability` or `RETURN_POSITIVE` parameter; AND input panels must reject any column with these names
- Result: PASS at promoted test B2-1 (`test_task_b1_does_not_consume_return_positive_calibrated_probability`); closes ChatGPT v2 §D.2 circularity per S-9

### L5-C R4 / L5-D R3 / L5-E R4 / L5-F R4 / L5-G R-leakage AST audits

Five Gate validators (Gate 22 / 23 / 24 / 25 point 1 / 25 point 2) perform `inspect.getsource` substring audits confirming absence of forbidden patterns `{".fit(", "train_test_split", "LogisticRegression", "Ridge(", "IsotonicRegression("}` in the corresponding module source. Module docstrings carefully avoid the literal substrings (lesson surfaced at L5-C false-positive and applied uniformly thereafter). All five PASS at sub-phase ACCEPT time.

### L5-F + L5-G Op-F-a / Op-G-a runtime dispatcher audits

- L5-F: `apply_dms_adjustment` exercises all four §3.3 horizons; 5Y/10Y produce band width of one-hundred bps (twice DMS_BPS_SENSITIVITY of fifty); 1Y/3Y collapse band (lower equals central equals upper)
- L5-G: `compute_shrinkage_weight` produces four distinct values at reference N_REF_NONOVERLAP across horizons (four distinct rather than a constant zero-point-three literal); AST float-literal count of zero-point-three kept to two legitimate entries (`W_REF_TARGET["5Y"]` plus alias) via `ast.walk` over parsed source

Both PASS at sub-phase ACCEPT time.

---

## §8 — Cumulative AP-AUTH additions during L5 build phase

Six entries codified at sub-phase ACCEPT times; all live in `docs/ap_register.md`.

| AP-AUTH | Codified | Trigger sub-phase | Discipline |
|---|---|---|---|
| 47 | 2026-05-13 | L5-A Phase 3.5 (190 cache-dependent test failures surfaced post-collect-only) | Build worktree env-setup must run full pytest, not collect-only |
| 48 v2 | 2026-05-13 | L3 component_panel patch Phase 5 (test_transcript.txt CRLF/LF drift) | Manifest hash from served-URL content post-push (Windows normalization) |
| 49 | 2026-05-13 | L5-B Task A pre-flight commit on planning branch | Planning-branch precommit infra hygiene (cherry-pick at branch creation) |
| 50 | 2026-05-13 | L5-RM-4 pre-flight | Upstream-export grep at pre-flight (not code-exec time) |
| 51 | 2026-05-14 | L5-RM-4 pre-flight (50+ → 16 scope gap) | Risk register quantifiable scope must cite grep evidence |
| 52 | 2026-05-15 | L5-RM-4 ACCEPT (S-12 disposition) | Spec magic-numbers must derive from production base plus delta with grep evidence |

Cumulative register: one through fifty-two codified. L5 build added six.

---

## §9 — L5b backlog seed inventory (deferred items)

Six items deferred per AP-AUTH-46 (gratuitous-Sxx guard); all LOW or MED priority; none blocking.

| Item | Source | Class | Priority | Estimated effort |
|---|---|---|---|---|
| L5b-2 | S-10 Option (iv) HYBRID fork | implementation: ISM New Orders plus CB LEI loaders | MED | four to eight hours |
| L5b-3 | L5-B Task A retry deviation #3 | CLI ergonomics: gate18 `--panel-path` flag | LOW | one-quarter to one-half hour |
| L5b-4 | S-12 RESOLVED-OPTION-A | doc: v7 spec magic-number cleanup §5.RM-4 | LOW | two to three hours |
| L5b-5 | L5-RM-4 L5-13 step 3 deferral | implementation: NBER pre-1978 caveat | MED | two to four hours |
| L5b-6 | ChatGPT post-RM-4 gate review PASS-WITH-NOTE | doc: Gate 20 parquet vs JSON wording | LOW | one-quarter hour doc + downstream L5-E real-parquet cost |
| L5b-7 | L5-B Task B1 onwards | doc-residue aggregate (five bullets covering file naming + Gate 19 split + §5.D.0 anchor + §5.D.7 typo + §5.E.0 anchor + §5.E.5 "wait recount" + §5.G.0 anchor) | LOW | two to three hours |

L5b-1 reserved (no allocation yet); future L5b-8 onwards reserved.

---

## §10 — Recommended Codex review focus areas

For ChatGPT 5.5 / Codex 5-of-5 reviewer convenience, suggested focus areas (NOT binding):

1. **Methodology rigor** (this §4): nine blocks across L5-A through L5-G. Particularly novel patterns: hierarchical pooling cell taxonomy (§5.D.1.3 three-state); joint bootstrap covariance + coverage inflation (§5.E.3 v2 per S-6); K_HORIZON v2 backsolve (§5.G.1 v2 per S-4)
2. **Q1-Q8 option-matrix rationale** (this §5): every Q lock has an Option matrix in the spec `Decisions for V` subsection; reviewer can sanity-check the rejection rationales
3. **Standing Order #4 audits** (this §7): six audit results; reviewer can sanity-check by re-running gate CLIs (`python -m macro_pipeline.validation gate{18..25}`)
4. **Sxx in-cycle resolution discipline** (this §6): three build-time Sxx all RESOLVED in-cycle without spec REOPEN
5. **Doc-residue (L5b-7)** (this §9 + L5B_BACKLOG.md L5b-7): five-bullet aggregate of spec narrative drift caught at pre-flight reads; reviewer may want to confirm priority assessment

Suggested anti-focus (lower priority for review attention):

- Trivial bug fixes (L5-A Gate 18 sidecar; S-11)
- AP-AUTH new entries are institutional-learning preservation, not novel methodology
- L5b backlog items are deferred-by-design per AP-AUTH-46

---

## §11 — Closing readiness statement

**L5 is ready for ChatGPT 5.5 / Codex 5-of-5 review.**

Evidence base summarized in this package; sibling document `LAYER_5_RETROSPECTIVE.md` provides cross-phase metrics and pattern compounding insights.

Manifest hash discipline (AP-AUTH-48 v2) activates at review-publication time per Op-H-a. Until publication, this document is review-content-ready at the L5-H commit.

— Track A (Claude Code), 2026-05-13
