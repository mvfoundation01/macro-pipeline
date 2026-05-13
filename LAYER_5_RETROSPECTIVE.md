# LAYER 5 — Retrospective

**Spec**: `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` FROZEN since 2026-05-13
**Branch**: `claude/layer-5-build`
**Merge base**: `590e4a5` (L3.5b merge into main)
**HEAD at retrospective time**: `7be853a` (tag `l5-g-accept`); this retrospective lands on the L5-H commit + dual tags `l5-h-accept` + `layer5-complete`.
**Authoring agent**: Track A (Claude Code)
**Strategic counterpart**: Track B (Claude Opus 4.7 1M context)

Per spec §5.H.1 this document mirrors the L3.5b retrospective structure (sections A through I).

---

## §A — Sub-phase metrics summary

Thirteen rows: twelve critical-path nodes plus the L3-patch insertion (intermediate, unblocking L5-B Task A per Sxx S-10).

| # | Sub-phase | ACCEPT tag | Commit | Effort actual / risk-adj | Test count delta | Sxx surfaced | AP-AUTH delta | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | L5-A | `l5-a-accept` | `20ec8f2` | four / eight to ten | sixty-zero-two to six-one-seven (delta of fifteen) | S-11 (Gate 18 sidecar; same-cycle resolution) | AP-AUTH-47 (env-setup discipline) | walk-forward CV scaffold (expanding + rolling 20Y); Gate 18 |
| 2 | L3-patch | `l3-component-patch` | `6d90d48` | three / four to six | six-one-seven to six-two-three (delta of six) | S-10 (component_panel missing) | none | inserted between L5-A and L5-B Task A to ship `component_panel` artifact |
| 3 | L5-B Task A | `l5-b-task-a-accept` | `53deb90` | four-point-seven-five / seven to nine | six-two-three to six-three-five (delta of twelve) | none | AP-AUTH-48 v2 + AP-AUTH-49 | composite-weight refit via penalized logistic; Gate 19-A criteria one through seven |
| 4 | L5-RM-4 | `l5-rm-4-accept` | `056d198` | four-point-five / six to eight | six-three-five to six-four-three (delta of eight) | S-12 (spec base-field count 25 vs production 23) | AP-AUTH-50 + AP-AUTH-51 + AP-AUTH-52 | ScoredObservation six-slot batched migration; Gate 20 |
| 5 | L5-RM-6 | `l5-rm-6-accept` | `ba0ff1e` | five-point-five / seven to ten | six-four-three to six-five-seven (delta of fourteen) | none | none | per-horizon isotonic calibration; twenty-five-calibrator dispatch; Gate 21 |
| 6 | L5-B Task B1 | `l5-b-task-b1-accept` | `908fc22` | five / eight to ten | six-five-seven to six-seven-one (delta of fourteen) | none | none | Ridge return-forecast regression; Gate 19-B1 partial PASS |
| 7 | L5-B Task B2 | `l5-b-task-b2-accept` | `cf9e053` | two-point-five / five-point-four | six-seven-one to six-seven-three (delta of two) | none | none | RETURN_POSITIVE isotonic calibration; Gate 19-B2 partial PASS; Gate 19 monolithic final-close |
| 8 | L5-C | `l5-c-accept` | `17aaa7f` | two-point-five / seven-point-three-five | six-seven-three to six-eight-three (delta of ten pytest instances; eight logical) | none | none | Brier plus reliability diagram plus Murphy decomposition (Murphy identity machine-exact at zero point zero exponential plus zero); Gate 22 |
| 9 | L5-D | `l5-d-accept` | `456f485` | three / nine | six-eight-three to six-nine-five (delta of twelve) | none | none | drawdown probability conditional distributions; Wilson interval per cell; hierarchical pooling; Gate 23 |
| 10 | L5-E | `l5-e-accept` | `34f0178` | one-point-five / six-point-zero-five | six-nine-five to seven-zero-four (delta of nine) | none | none | forecast sigma confidence band; v2 joint bootstrap; Gate 24 |
| 11 | L5-F | `l5-f-accept` | `822f66f` | one / three-point-four-five | seven-zero-four to seven-zero-nine (delta of five) | none | none | DMS survivorship adjustment (Q6 lock; minus one-twenty-five at 5Y; minus one-seventy-five at 10Y); Gate 25 sub-criterion 25 point 1 |
| 12 | L5-G | `l5-g-accept` | `7be853a` | one-point-five / four-point-seven-five | seven-zero-nine to seven-seventeen (delta of eight) | none | none | Bayesian shrinkage to six point five percent real prior (Q7 lock; K_HORIZON v2 backsolve); Gate 25 sub-criterion 25 point 2; Gate 25 composite SEALED |
| 13 | L5-H | `l5-h-accept` + `layer5-complete` | THIS COMMIT | two / five-point-two | seven-seventeen preserved (delta of zero per spec §5.H.5) | none | none | retrospective plus Codex review package; no new code |

Cumulative test count: from L3.5b merge baseline of six-hundred-two, closing at seven-hundred-seventeen — net delta of one-hundred-fifteen across thirteen sub-phases. Spec §5.H.1 expected approximately seventy-eight; actual delta exceeds by thirty-seven, reflecting v2/v3/v4 spec test-expansion cycles (S-2 dataclass slot expansion; S-4 K_HORIZON backsolve verification; S-6 joint bootstrap; S-9 task-split into B1/B2/B2-1-promotion).

---

## §B — ChatGPT 5.5 / Codex findings closure (carryover from L3.5b)

L3.5b retrospective §B contained Codex five-of-five findings closure for the prior layer. L5 build phase **did NOT receive a ChatGPT review prior to this retrospective**; the first L5 ChatGPT review fires post-`layer5-complete` push to GitHub. Therefore §B for L5 is empty by construction. Forward-looking: the L5 Codex review package (sibling document `LAYER_5_CODEX_REVIEW_PACKAGE.md`) is the deliverable that primes the next §B at post-review retrospective time.

---

## §C — Deviations register additions

Three Sxx entries filed during L5 build phase. All RESOLVED. Reserved range was S-10 through S-25; only S-10 through S-12 needed.

### S-10 — component_panel missing from L3 export surface (2026-05-13)

- **Trigger**: T1 (spec-vs-implementation gap)
- **Sub-phase**: L5-B Task A pre-flight Phase 0 hard gate
- **Resolution path**: Option (iv) HYBRID per Strategic disposition — minimal L3 patch shipping `component_panel` export; ISM and CB LEI deferred to L5b-2
- **Build artifact**: L3 component_panel patch (`l3-component-patch` tag at `6d90d48`)

### S-11 — Gate 18 sidecar naming mismatch (2026-05-13)

- **Trigger**: T1 (L3D `<stem>.meta.json` vs L5-A test fixture `<stem>.<suffix>.meta.json`)
- **Sub-phase**: L5-B Task A Phase 3 (Gate 18 CLI runtime)
- **Resolution path**: minimal bug fix in `_validate_panel_cache` to try both conventions
- **Build artifact**: bug-fix commit landed within L5-B Task A retry; both conventions now supported

### S-12 — Spec base-field count (25) vs production empirical (23) magic-number mismatch (2026-05-14)

- **Trigger**: T1 (spec-vs-implementation gap surfaced at L5-RM-4 Phase 0)
- **Sub-phase**: L5-RM-4 dataclass-migration baseline check
- **Resolution path**: RESOLVED-OPTION-A 2026-05-15 (Strategic disposition); ScoredObservation field count uses production empirical (twenty-three plus six equals twenty-nine total); spec residue spawned L5b-4
- **Build artifact**: L5-RM-4 commit (`056d198`); discipline codified as AP-AUTH-52 at sub-phase ACCEPT

**Net Sxx delta**: three filed; three resolved; zero open at `layer5-complete`.

---

## §D — Backlog seeds added (L5b register)

Six L5b items opened during L5 build phase. All LOW or MED priority; none blocking L5 closure.

| Item | Origin | Class | Priority |
|---|---|---|---|
| L5b-2 | S-10 resolution (Option iv HYBRID) | implementation: ISM New Orders + CB LEI loaders | MED |
| L5b-3 | L5-B Task A retry deviation #3 | CLI ergonomics: `--panel-path` flag on gate18 | LOW |
| L5b-4 | S-12 RESOLVED-OPTION-A | doc: v7 spec magic-number cleanup §5.RM-4 | LOW |
| L5b-5 | L5-RM-4 L5-13 step 3 deferral | implementation: NBER pre-1978 caveat | MED |
| L5b-6 | ChatGPT post-RM-4 gate review PASS-WITH-NOTE | doc: Gate 20 parquet vs JSON wording | LOW |
| L5b-7 | L5-B Task B1 onwards | doc-residue: five-bullet aggregate (B1/B2/D/E/G spec narrative drift) | LOW |

**Net L5b register at `layer5-complete`**: six items; five LOW + one MED; zero HIGH; zero blocking.

---

## §E — Pattern compounding insights (cross-phase methodology evolution)

### E.1 Convergence variance trajectory

Effort variance held under risk-adjusted budget for all thirteen sub-phases. Rolling mean variance trended sharper across the chain:

- After L5-A: minus fifty percent
- After L5-B chain (Tasks A/B1/B2 + RM-4 + RM-6): minus forty-four percent
- After L5-C: minus forty-six percent
- After L5-D: minus forty-seven percent
- After L5-E: minus forty-nine percent
- After L5-F: minus fifty-one percent
- After L5-G: minus fifty-one percent (Strategic-confirmed at L5-G ACCEPT)

Mechanism: pre-flight rigor (AP-AUTH-50 upstream grep + AP-AUTH-51 risk register grep evidence) consistently produced over-cautious risk-adjusted budgets; actuals landed closer to nominal projections; convergence prior tightened toward the half-discount mark as the sample size grew.

### E.2 AP-AUTH register expansion

Six new AP-AUTH entries codified during L5 build phase, all at clearly defined trigger sub-phases:

- AP-AUTH-47 (env-setup beyond test collection) — codified at L5-B Task A retry first commit; surfaced at L5-A Phase 3.5
- AP-AUTH-48 v2 (manifest hash from served-URL content post-push) — codified at L5-B Task A retry; surfaced at L3 component_panel patch Phase 5
- AP-AUTH-49 (planning-branch precommit infra hygiene) — codified at L5-B Task A retry; surfaced at L5-B Task A pre-flight commit chain
- AP-AUTH-50 (upstream-export grep at pre-flight) — codified at L5-RM-4 pre-flight; surfaced at L5-B Task A Phase 0
- AP-AUTH-51 (risk register quantifiable scope grep evidence) — codified at L5-RM-4 pre-flight; surfaced at L5-RM-4 pre-flight ITEM 1
- AP-AUTH-52 (spec magic-numbers derivable from base plus delta) — codified at L5-RM-4 ACCEPT; surfaced at S-12

Cumulative register state: AP-AUTH-1 through AP-AUTH-52 codified (forty-six baseline plus six L5-build additions).

### E.3 Standing Order #4 audit pattern emergence

A consistent audit-via-runtime-behavior pattern emerged across sub-phases when literal cross-module call-graph inspection would have been vacuous (no downstream callers existed at build time):

- L5-C R4 mitigation — Gate 22 source-substring audit (post-hoc Brier; no estimator instantiation)
- L5-D R3 mitigation — Gate 23 source-substring audit (post-hoc empirical exceedance)
- L5-E R4 mitigation — Gate 24 source-substring audit (closed-form quadrature)
- L5-F Op-F-a — runtime dispatcher audit on `apply_dms_adjustment` (collapsed band for 1Y/3Y; band width of one-hundred bps for 5Y/10Y)
- L5-G Op-G-a — runtime + AST audit on `compute_shrinkage_weight` (four distinct horizon values; AST float-literal count of zero point three zero kept to two legitimate entries via `ast.walk` over parsed source)

Common discipline: gate validators perform `inspect.getsource` substring audits with the forbidden-pattern set `{".fit(", "train_test_split", "LogisticRegression", "Ridge(", "IsotonicRegression("}`. Docstrings must avoid these literal substrings to prevent false-positives — lesson surfaced at L5-C false-positive and applied uniformly thereafter.

### E.4 ScoredObservation slot population end-state

The six L5-RM-4 slots are now populated by the responsible sub-phases:

- `calibrated_probability_band_lower` / `_upper` — populated by L5-E `derive_forecast_sigma`
- `drawdown_conditional_distribution` — populated by L5-D `fit_drawdown_conditionals`
- `dms_adjustment_bps` — populated by L5-F `apply_dms_adjustment` (caller stores `DMS_BPS_CENTRAL[horizon]`)
- `bayesian_shrinkage_weight` — populated by L5-G `apply_shrinkage` (returns weight as second tuple element)
- `positive_return_probability` — populated by L5-B Task B2 `calibrate_return_forecast_task_b2`

Final dataclass field count: twenty-nine total (twenty-three base plus six L5-RM-4 new). Spec literal v6 §5.RM-4 says thirty-one (twenty-five plus six); spec-vs-empirical gap documented at S-12 and L5b-4.

### E.5 Doc-residue (spec-vs-implementation drift) compounding

L5b-7 grew from one bullet at L5-B Task B1 to five bullets at L5-G:

- bullet 1 — file naming (composite_refit / return_forecast / return_calibration vs spec `ridge_cv.py`)
- bullet 2 — Gate 19 split (19-A / 19-B1 / 19-B2 vs spec monolithic Gate 19)
- bullet 3 — §5.D.0 metadata anchor stale (D-D-1) + §5.D.7 file-name typo (D-D-2)
- bullet 4 — §5.E.0 metadata anchor stale (D-E-1) + §5.E.5 "wait recount" literal + §5.E.7 brevity expansion
- bullet 5 — §5.G.0 metadata anchor stale (D-G-1)

Mechanism: spec v6 underwent multiple revision cycles (v1 through v6); metadata anchors in `.0` sections often lagged behind the v2/v3/v4 expansions in `.5/.6/.7` mirror anchors. Track A's pre-flight reads consistently caught these as doc-residue (NOT Sxx-grade gaps per AP-AUTH-46); Strategic dispositions ratified the "follow canonical mirror anchor" pattern uniformly.

### E.6 Risk de-escalation pattern

Strategic-anchored MED severities consistently de-escalated to LOW empirically at pre-flight read time:

- L5-C R1 (Murphy binning) — MED → LOW (spec formulas closed-form)
- L5-D R1 (drawdown sign convention) — MED → LOW (spec §5.D.1.1 explicit)
- L5-D R2 (Monte Carlo seed) — MED → LOW (spec uses bootstrap, not MC)
- L5-D R3 (walk-forward leakage) — HIGH if fires → LOW (function takes pre-computed inputs; no fitting)
- L5-E R1 (band methodology) — MED → LOW (spec §5.E.3 explicit on v2 PRIMARY)
- L5-E R2 (slot semantics) — MED → LOW (slot exists with validators)
- L5-E R5 (coverage validation walk-forward interaction) — MED → LOW (caller-supplied per Op-E-1)
- L5-F R1 (DMS conditional logic) — MED → LOW (spec §5.F.4 Q6 lock explicit)

Mechanism: grep-evidenced pre-flight (AP-AUTH-50 + AP-AUTH-51) consistently bounded the worst-case severity below Strategic's a-priori ceiling.

---

## §F — Strategic Claude self-corrections (lessons for next-layer spec authoring)

Three categories surfaced during L5 build phase:

### F.1 §5.x.0 metadata anchor staleness across v2/v3/v4 spec expansions

Three sub-phases (L5-D / L5-E / L5-G) had `.0` metadata anchors lagging behind `.5/.6/.7` canonical mirror anchors. Documented as D-D-1 / D-E-1 / D-G-1; aggregated in L5b-7 bullets 3 / 4 / 5. Lesson for L6 spec authoring: when patching a `.5/.6/.7` mirror anchor in a future revision, treat the `.0` metadata anchor as a fourth mirror that must update in the same commit (extends AP-AUTH-39 v4 dual-anchor discipline from §5.X.5 / §5.X.6 / §5.X.7 to also cover §5.X.0).

### F.2 Spec function signature underspecification when v2 fields require non-scalar inputs

L5-E surfaced this most clearly: spec `derive_forecast_sigma` took six scalar parameters but the v2-extended `ForecastSigmaResult` dataclass required bootstrap distributions / OOS observations that scalars cannot provide. Resolution via Op-E-1 path (b) + (c): preserve spec signature with independence-assumption defaults plus callable helpers for the v2 math. Lesson for L6 spec authoring: when a v2 expansion adds dataclass fields, validate that the corresponding function signature can populate them; if not, mandate optional kwargs OR callable helpers in the same spec patch.

### F.3 Pre-flight prompt over-anticipation vs spec literal

L5-H pre-flight prompt over-anticipated work scope (anticipating Gate 26 + integration test + new tests); spec §5.H.5/.6 was much leaner (zero new tests; no new gate). Five-divergence cluster (D-H-1 through D-H-5) all resolved to "follow spec literal" per institutional precedent. Lesson for next-layer pre-flight prompt authoring: state-of-spec verification at pre-flight kickoff should precede the build-plan-derived work expectation; spec-vs-prompt divergence catches reduce downstream rework.

---

## §G — L3.5b plus L5 combined metrics

| Metric | L3.5b end-state | L5 end-state | Delta |
|---|---|---|---|
| Test count | six-hundred-two | seven-hundred-seventeen | plus one-hundred-fifteen |
| Gate count | seventeen | twenty-five (with composite Gate 25 SEALED via 25 point 1 plus 25 point 2; Gate 19 split into 19-A / 19-B1 / 19-B2) | plus nine new gates |
| AP-AUTH register | one through forty-six | one through fifty-two | plus six (47 / 48 v2 / 49 / 50 / 51 / 52) |
| Sxx register | S-1 through S-9 (spec authoring; closed) | S-10 through S-12 (build-time; all RESOLVED) | plus three RESOLVED Sxx |
| L5b backlog | empty pre-L5 | six items (L5b-2 / -3 / -4 / -5 / -6 / -7) | plus six LOW/MED priority items |
| Critical-path nodes | n/a | thirteen (twelve plus L3-patch insertion) | thirteen |
| Convergence streak | n/a | thirteen of thirteen under budget (minus fifty-one percent rolling mean) | thirteen |

---

## §H — Forward readiness for L5b OOS hardening sprint

Per build plan v1 §15 (Master Prompt v3.1 §15) the L5b OOS hardening sprint is the natural successor to L5. Scope items pre-committed at L5 build time:

- **L5b-1** — reserved (no allocation yet)
- **L5b-2** — ISM New Orders + CB LEI loaders (MED priority; closes S-10 fork; ~four to eight hours)
- **L5b-3** — gate18 `--panel-path` CLI flag (LOW priority; ~one-quarter to one-half hour)
- **L5b-4** — v7 spec magic-number cleanup §5.RM-4 (LOW priority; ~two to three hours)
- **L5b-5** — NBER pre-1978 caveat investigation (MED priority; ~two to four hours)
- **L5b-6** — Gate 20 parquet vs JSON wording (LOW priority; ~one-quarter hour doc + downstream L5-E implementation cost)
- **L5b-7** — spec narrative drift aggregate (five bullets covering D-B1-1 / D-B1-2 / D-D-1 / D-D-2 / D-E-1 / D-G-1; LOW priority; ~two to three hours)

Additional L5b scope categories per Master Prompt v3.1 §15 (NOT YET filed as L5b items; pending Strategic decision post-Codex review):

- Block bootstrap robustness validation across multiple block-size regimes
- Structural break / regime-shift tests on calibration stability
- FDR (false discovery rate) gating across multi-horizon × multi-score_type test surfaces
- OOS validation rigor on real (non-synthetic) historical data
- Pre-1978 NBER label sensitivity (overlaps L5b-5)
- Cross-validation against ex-US benchmarks (DMS prior calibration)

Recommended L5b kickoff sequence: L5b-2 (ISM + LEI) blocks any cross-validation work; should run first. L5b-4 plus L5b-7 are doc-residue and can run in parallel with implementation items.

---

## §I — Closing recommendation

**L5 is READY for ChatGPT 5.5 / Codex five-of-five review.**

Evidence base:

- All thirteen sub-phases ACCEPT-tagged; conviction floor (zero point nine zero) cleared at every ACCEPT
- Pytest baseline at seven-hundred-seventeen; net delta of one-hundred-fifteen since L3.5b merge; zero regressions
- Gate count expanded from seventeen to twenty-five; Gate 25 composite SEALED with both sub-criteria 25 point 1 (DMS) and 25 point 2 (Bayesian shrinkage) PASS
- Three Sxx surfaced and resolved in-cycle; six L5b items deferred per AP-AUTH-46 discipline
- AP-AUTH register expanded with six new entries codifying institutional learnings from L5 build phase
- Sibling document `LAYER_5_CODEX_REVIEW_PACKAGE.md` provides the Codex-review-ready manifest

Post-`layer5-complete` push to GitHub activates the ChatGPT review window per AP-AUTH-48 v2 served-hash discipline (manifest hashes computed at review-publication time, not L5-H code-exec time, per Op-H-a clarification).

Strategic continuation: L5b OOS hardening sprint pre-flight should commence post-Codex closure.

**Spec-level aggregate conviction** (per spec §5.H.7 proof item 8): **probability zero point nine six / confidence zero point nine five / conviction zero point nine four**. Binding constraint at L5 closure: **operational + procedural** — AP-AUTH-42 discipline applied at scale across this retrospective and the sibling Codex review package; thirteen consecutive sub-phases under budget with no Sxx escalations beyond same-cycle resolution; no methodological or statistical risk axis active.

— Track A (Claude Code), 2026-05-13
