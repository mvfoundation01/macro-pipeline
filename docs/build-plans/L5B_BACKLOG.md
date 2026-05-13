# L5b (OOS Hardening) Backlog

**Scope**: items deferred from L5 build to L5b OOS hardening sprint (per `Master Prompt v3.1 §15` and `LAYER_5_BUILD_SPEC.md` v6 §1.2). Each entry includes effort estimate + priority + provenance.

---

## L5b SPRINT EXECUTION LOG (completed sub-phases)

Reviewer-driven KICK-N sub-phases addressing CRITICAL findings from Codex 5.5 + ChatGPT 5.5 independent reviews of `layer5-complete`. Distinct from the L5b-N deferred-items register below.

### KICK-1 — Isotonic train-only `fit_window` invariant enforcement (2026-05-13)

**ACCEPT tag**: `l5b-kick-1-accept`
**Reviewer authority**: Codex 5.5 IMPORTANT + ChatGPT 5.5 CRITICAL #3 (independent convergence on train-only-calibration leakage guard)
**Approach**: B (Strategic-approved 2026-05-13) — `panel.index` MUST be `pd.DatetimeIndex` AND every index date MUST satisfy `fit_window[0] <= date <= fit_window[1]` (inclusive both sides); enforced inside `_fit_one_calibrator`; structured `ValueError` diagnostic per spec section three point three of the KICK-1 pre-flight prompt.
**Sxx-13 triage**: NOT triggered (Strategic's predicted "enforcement-not-present-but-no-active-leakage" state confirmed empirically — Task B2 caller fit_window covered full panel range; no train/test split active; no production downstream caller yet).
**Test delta**: plus four tests (two mandatory NEG/POS-inv + two bonus NEG/POS); seven-hundred-seventeen to seven-hundred-twenty-one.
**Caller updates**: `return_calibration.py` Task B2 builds panel with synthesised monthly DatetimeIndex from `fit_window[0]` plus defensive overrun guard.
**Docstring correction**: `isotonic_calibrator.py:376` "inclusive-exclusive" wording corrected to "inclusive-inclusive" per Strategic ruling two (2026-05-13).
**AP-AUTH delta**: zero (AP-AUTH-53 "Reviewer-driven L5b kickoff item" pattern DEFERRED per AP-AUTH-46 gratuitous-codification guard; re-evaluate at KICK-2 ACCEPT if pattern repeats). **CODIFIED at KICK-2 ACCEPT** — pattern repeated; see entry below.
**Sxx delta**: zero.

---

### KICK-2 — L5-E v2 production wrapper + Gate 24 hard gate (2026-05-13)

**ACCEPT tag**: `l5b-kick-2-accept`
**Reviewer authority**: Codex 5.5 IMPORTANT + ChatGPT 5.5 CRITICAL #2 (independent convergence on "diagnostic-helpers-only" → production-mandatory pathway promotion).
**Approach**: B (Strategic-approved 2026-05-13) — wrapper-pattern `derive_forecast_sigma_v2()` invokes existing `derive_forecast_sigma` then overrides the four independence-assumption placeholder fields with caller-supplied joint covariance + empirical coverage. v1 path preserved verbatim (six-scalar signature + spec literal protection); v2 path adds two required keyword-only args with no defaults (`joint_bootstrap_covariance` + `empirical_coverage_95`). `ForecastSigmaResult` gains a thirteenth field `diagnostic_only` (bool, no default): v1 wrapper passes True; v2 wrapper passes False. Bare construction without the field raises TypeError (KICK-2 test thirteen contract).
**Option**: Y (Strategic-approved 2026-05-13) — Gate 24 extension via signature inspection plus runtime placeholder-pattern probe. Three new criteria (twelve / thirteen / fourteen): v2 importable; v2 required-kwargs have no defaults (caller-intent forcing); v2 vs v1 `diagnostic_only` flag distinguishes production from diagnostic at gate time.
**Sxx-14 triage**: NOT triggered (Strategic's predicted state confirmed empirically — zero production scoring callers exist; only consumers are Gate 24 validator + fifteen-test suite). Prospective-only marker recorded here per AP-AUTH-46 gratuitous-Sxx guard: if a production caller subsequently lands and invokes legacy `derive_forecast_sigma` instead of the v2 wrapper, the resulting `diagnostic_only=True` value MUST be detected by a downstream consumer (Gate 24 criterion fourteen probe covers exactly this case at gate time).
**Test delta**: plus six new tests (numbers ten through fifteen; three POS + three NEG; NEG ratio one-half satisfies the floor); plus two fixups to existing tests six + eight (bare `ForecastSigmaResult(...)` constructors now pass `diagnostic_only=` explicitly). Baseline seven-hundred-twenty-one to seven-hundred-twenty-seven.
**Caller updates**: none in production tree (no production callers exist yet; Sxx-14 prospective-only).
**Math note (NEG test fifteen)**: `joint_bootstrap_covariance` MAY legitimately be negative (anti-correlated noise admissible); inner-term guard at `_compute_forecast_sigma_with_covariance` line two-six-three rejects only `|cov| > σ_ridge × σ_isotonic` (i.e., `|rho| > 1`). Test fifteen probes finiteness (NaN/inf rejected), valid negative covariance (must succeed), invalid `|rho| > 1` (helper propagates ValueError), plus coverage bounds `(0, 1]`.
**AP-AUTH delta**: plus one (AP-AUTH-53 codified — see codification block below).
**Sxx delta**: zero.

---

### AP-AUTH-53 codification (2026-05-13, anchored at `l5b-kick-2-accept`)

**AP-AUTH-53 — Reviewer-driven L5b kickoff item pattern.**

When external reviewers (Codex / ChatGPT) flag a CRITICAL or IMPORTANT issue in a previously-passed gate, the standard institutional closure mechanism is:

1. **Preserve existing API verbatim** (no breaking change to spec literals — protects existing test surface and spec freeze integrity).
2. **Add side-by-side hardened API** with `_v2` suffix function, new dataclass field, OR equivalent isolation pattern.
3. **No-default required kwargs on hardened API** (forces caller intent; closes "silent placeholder" reviewer concerns).
4. **Gate validator extension** via signature-inspection criteria for both legacy and hardened paths (mirrors existing gate idiom).
5. **Test coverage**: minimum five tests, fifty-percent NEG ratio floor, bounds-check NEG when v2 inputs admit invalid ranges, plus missing-kwarg NEG behaviors.
6. **Pre-flight Sxx-N (catastrophic state) triage** via grep evidence; defer entry to L5B_BACKLOG.md if production callers do not yet exist.
7. **Module docstring + L5B_BACKLOG.md SPRINT EXECUTION LOG** documents v1 → v2 architectural drift.

Confirmed via L5b-KICK-1 (isotonic `fit_window` invariant) + L5b-KICK-2 (forecast σ v2 production wrapper). Anticipated to apply at KICK-3 through KICK-7. **KICK-3 confirmed (third instance) at `l5b-kick-3-accept`** — see entry below. **KICK-4 confirmed (fourth instance, internal-implementation variant) at `l5b-kick-4-accept`** — see entry below.

---

### KICK-3 — L5-C adaptive bin reduction + Gate 22 diagnostic status (2026-05-15)

**ACCEPT tag**: `l5b-kick-3-accept`
**Reviewer authority**: Codex 5.5 IMPORTANT — "L5-C: Implement adaptive bin reduction or emit an explicit diagnostic status consumed by Gate 22; warning-only is weaker than spec" — plus ChatGPT 5.5 alignment on per-score-type Brier reporting.
**Approach**: B (Strategic-approved 2026-05-15) — wrapper-pattern `compute_brier_per_horizon_v2()` invokes existing `compute_brier_per_horizon` then applies adaptive reduction loop over a bounded `range(initial_n_bins, n_bins_floor - 1, -1)` iterator. v1 path preserved verbatim (six-positional + two-keyword signature; spec literal protection). v2 path adds one required keyword-only arg with no default (`min_obs_per_bin`); `BrierDecomposition` gains three no-default fields (`bin_reduction_applied: bool`, `final_bin_count: int`, `bin_diagnostic_status: Literal[...]`). Tri-state taxonomy `{"production", "diagnostic_only", "fallback_climatology"}` enforced via `__post_init__` validator. Bare construction without the three fields raises TypeError; invalid status string raises ValueError.
**Option**: Y (Strategic-approved 2026-05-15) — Gate 22 extension via signature inspection plus runtime placeholder-pattern probe covering all three tri-state outcomes. Three new criteria (seven / eight / nine): v2 importable; v2 required-kwarg + dataclass KICK-3 fields all no-default (caller-intent forcing); tri-state runtime probe reaches all three states deterministically per Strategic Watch-point Phase 6 ("All 3 states reachable; not just 1").
**Sxx-15 triage**: NOT triggered (Strategic's predicted state confirmed empirically — zero production scoring callers exist; only consumers are Gate 22 validator + seventeen-test suite). Prospective-only marker recorded per AP-AUTH-46 gratuitous-Sxx guard: if a production caller subsequently consumes a `BrierDecomposition` with `bin_diagnostic_status` ∈ {"diagnostic_only", "fallback_climatology"} as production-grade output, Gate 22 Criterion 9 runtime probe is the trip wire at validator time.
**Algorithm convergence**: bounded `range(initial_n_bins, n_bins_floor - 1, -1)` iterator — at most `initial_n_bins - n_bins_floor + 1 = ten minus two plus one = nine` iterations per horizon. Cannot infinite-loop. Risk #1 closed by construction.
**Op-K3-1** (Strategic-approved 2026-05-15): bootstrap suppression during reduction search. Each search iteration invokes v1 with `bootstrap_iterations=0`; the FULL bootstrap is run only on the winning iteration (or floor iteration when loop exhausts). Avoids worst-case nine times one-thousand equals nine-thousand resample cost per horizon. Operational optimisation; documented inline in module docstring; no L5b backlog tier per Strategic note ("operational, not Sxx-class").
**Test delta**: plus seven new tests (numbers nine through fifteen; three POS + four NEG; NEG ratio four of seven equals fifty-seven percent above the floor); no fixups to existing eight L5-C tests (no bare `BrierDecomposition` constructors in `tests/test_brier_reliability.py`). Single Gate 22 validator probe constructor at `validation.py:4072` fixed up in same commit. Baseline seven-hundred-twenty-seven to seven-hundred-thirty-four.
**Caller updates**: none in production tree (zero production callers exist; Sxx-15 prospective-only).
**Edge cases verified**:
- n strictly below fallback_climatology_floor (= two times min_obs_per_bin) → fallback_climatology path (test eleven; Strategic Watch-point Phase 3 boundary semantics confirmed strict less-than)
- bootstrap_iterations=0 path during search → v1's `_bootstrap_brier_se` returns `np.zeros(0)` cleanly (no Result-contract break)
- Tri-state runtime probe reaches all three states deterministically in Gate 22 Criterion 9 (production via well-spread n=1000; diagnostic_only via n=110 skewed split with min=50; fallback_climatology via n=40 below 60 floor)
**AP-AUTH delta**: zero (AP-AUTH-53 cited as governing pattern; codified at KICK-2 ACCEPT; no new codification this instance).
**Sxx delta**: zero.

---

### KICK-4 — L5-B1 inner-CV z-scaler recomputation (Task A parity) (2026-05-15)

**ACCEPT tag**: `l5b-kick-4-accept`
**Reviewer authority**: Codex 5.5 IMPORTANT — "L5-B1: Recompute z-score scalers inside inner λ CV blocks, matching Task A's pattern. Inner λ selection receives outer-train-z-scored data (`return_forecast.py:677-682`) and does not recompute scalers inside inner blocks (`return_forecast.py:203-234`). This does not leak outer test data, but it weakens nested-CV purity."
**Approach**: B-variant (Strategic-approved 2026-05-15; internal-implementation variant of AP-AUTH-53) — in-place refactor of the private helper `_select_lambda_inner_cv_ridge` (parameter rename `X_train_z` → `X_train`; per-fold body adds `_zscore_fit_transform(X_tr_raw)` + `_zscore_transform(X_te_raw, ...)` matching Task A precedent at `composite_refit.py:177-178`) plus one new no-default field `inner_cv_scaler_recomputed: bool` on `RidgeFitResult` exposing the post-refactor invariant for downstream gating. NOT a `_v2` wrapper-pattern because the helper is private (`_` prefix); no public boundary to wrap. The flag exists for downstream observability + Gate inspection, NOT to allow legacy impure behavior to be selected (correctness fix, not policy).
**Option**: Y (Strategic-approved 2026-05-15) — Gate 19-B1 extension via signature inspection plus AST audit of helper body. Two new criteria (twenty-three / twenty-four): `inner_cv_scaler_recomputed` no-default field check; AST substring audit verifies `_zscore_fit_transform(X_tr` AND `_zscore_transform(X_te` present in `_select_lambda_inner_cv_ridge` source.
**Internal-implementation variant note**: KICK-2 + KICK-3 wrapped PUBLIC production boundaries (`derive_forecast_sigma_v2`, `compute_brier_per_horizon_v2`). KICK-4 modifies an INTERNAL nested-CV helper, not a public boundary. The wrapper-pattern doesn't apply naturally; in-place refactor + no-default field flag is the equivalent AP-AUTH-53-conformant pattern for internal-implementation cases. If this variant repeats at KICK-5+, Strategic codifies as AP-AUTH-54. **No new AP-AUTH codification at KICK-4** — variant documented inline in module docstring + this entry.
**Sxx-16 triage**: NOT triggered (Strategic's predicted state confirmed empirically — zero production scoring callers of `fit_return_forecast_task_b1` exist; only consumers are nineteen-test L5-B1 suite + Gate 19-B1 validator). Prospective-only marker recorded per AP-AUTH-46 gratuitous-Sxx guard: if a production caller subsequently consumes a `RidgeFitResult` with `inner_cv_scaler_recomputed=False`, downstream gate should detect (no such caller exists at KICK-4 ACCEPT).
**Pre-vs-post λ delta** (Strategic deliverable checklist; empirically captured at Phase 4):
- `lambda_selected`: UNCHANGED across three-hundred-ninety-six synthetic-fixture folds across 1Y plus 3Y plus 5Y horizons; every single fold binds at grid-edge λ equal to one-hundred both pre and post refactor. This is the synthetic-fixture characteristic (high-noise white-noise data wants maximal Ridge shrinkage regardless of scaler statistics).
- `lambda_log10_sd_across_5fold`: CHANGED on 1Y/expanding — six of two-hundred-seventeen 1Y folds now report nonzero σ with max σ equal to zero-point-two-four. Methodological signature of the refactor: re-fit scalers per inner block introduce natural inner-fold variance previously suppressed by the shared-scaler pattern. 3Y/expanding + 5Y/expanding remain at σ equal to zero (larger inner blocks → scaler statistics converge regardless of re-fit).
- `inner_cv_scaler_recomputed` flag: True on three-hundred-ninety-six of three-hundred-ninety-six folds (one-hundred-percent post-refactor coverage).
**Test delta**: plus five new tests (K4.1 through K4.5; one POS + two POS-inv + one NEG + one NEG-inv = NEG-flavor four of five equals eighty percent per L5-B1 accounting convention where POS-inv counts as NEG-flavor; above floor). No fixups to existing fourteen L5-B1 tests (none assert specific λ values; outer-CV behavior unchanged by design). Baseline seven-hundred-thirty-four to seven-hundred-thirty-nine.
**Caller updates**: zero in production tree (no production caller of `fit_return_forecast_task_b1` exists; Sxx-16 prospective-only).
**Algorithm verification**:
- AST substring `_zscore_fit_transform(X_tr` present in `_select_lambda_inner_cv_ridge` source (Gate 19-B1 Criterion twenty-four verified)
- AST substring `_zscore_transform(X_te` present (inner statistics applied to inner-test slice)
- Caller at `return_forecast.py:684` passes RAW `X_train` to helper (not `X_train_z`); K4.3 structural invariant test verifies this
- Outer Ridge fit at `return_forecast.py:686-688` continues to use outer-train scaler `(mean_tr, std_tr)` for outer-test projection (K4.3 verifies provenance)
**R1 (λ-drift methodologically expected) closure**: empirical pre-flight snapshot at Phase 0 bounded R1 from HIGH to MED before code-exec began; Phase 4 mid-stream pytest checkpoint confirmed fourteen of fourteen L5-B1 tests pass post-refactor with zero recalibration needed (no test asserts specific λ values; B11 grid-edge warning preserved; B8 lambda_log10_sd field populated regardless of refactor).
**AP-AUTH delta**: zero (AP-AUTH-53 cited as governing pattern; fourth instance; internal-implementation variant documented inline; AP-AUTH-54 deferred per Strategic until variant repeats at KICK-5+).
**Sxx delta**: zero.

---

## L5b-2 — Implement L3 loaders for ISM New Orders (NAPMNOI) + CB LEI

**Source**: `scoring/crps.py` lines 14-22 documents that `LAYER3_ACTIVE_COMPONENTS` is currently 4 of spec's 6 components. `ism_pmi_neworders` (NAPMNOI) returns FRED 400 (series does not exist post-2018 ISM licensing change); `lei_3d_rule` (CB LEI 6M annualized) has no Tier 1-4 loader (PHILLY_LEI_PROXY blocked by `check_double_counting` vs T10Y3M).

**Surfaced**: S-10 resolution + L3 component_panel patch shipped 4-component variant (no ISM/LEI columns). Documented in `macro_pipeline/analysis/component_panel.py` docstring + `tests/test_component_panel.py::test_build_component_panel_crps_4_active_columns` asserts explicit absence.

**Effort estimate**: 4-8h
- ISM New Orders alternative source (likely Conference Board direct or Bloomberg) + FRED loader (or replace with proxy): 2-4h
- CB LEI source (CB direct or alternative aggregator) + loader: 2-3h
- 2 unit tests (one per loader) + 1 integration test (component_panel CRPS expands from 4 → 6 columns): ~1h
- Update `LAYER3_ACTIVE_COMPONENTS` (4 → 6) + `_CRPS_NORMALIZER` (add ism_pmi_neworders + lei_3d_rule entries) + `component_panel.CRPS_COLUMNS`: ~0.5h

**Priority**: **MED** — L5 ships functional 4-component CRPS (covers ~85% of spec's intended composite signal per `EXPERT_COEFFICIENT_PRIORS` mean weights: yield_curve 0.43 + sahm 0.29 + nfci 0.14 + hy_oas 0.14 = 1.00 redistributed from 0.30+0.20+0.10+0.10 = 0.70 of original 1.00 budget; spec ISM+LEI 0.30 weight not covered). ISM + LEI improve coverage but don't BLOCK L5 ship.

**Owner**: L5b OOS hardening cycle (V to schedule post-L5-H ACCEPT).

**Acceptance criteria**:
1. `loaders/<new_loader>.py` produces monthly time series for both NAPMNOI + CB LEI; PIT discipline preserved per L3.5b-T/U.
2. `scoring/crps.py::LAYER3_ACTIVE_COMPONENTS` expands to 6 components.
3. `analysis/component_panel.py::CRPS_COLUMNS` expands to 6.
4. Existing 623-test baseline preserved + 2-3 new tests for the loaders + 1 expanded test for `component_panel CRPS 6 columns`.
5. `test_build_component_panel_crps_4_active_columns` either updated to 6-column variant OR replaced; documented in commit message.

**Provenance trail**:
- S-10 (2026-05-13; build-phase Sxx): component_panel patch surfaced 4-of-6 reality.
- L5 spec §5.B.1 line 587: spec ideal is 6 CRPS components.
- `scoring/crps.py` lines 14-22 (pre-existing L3 docstring): explicit acknowledgement of 4-active reality.

---

## L5b-3 — Expose `--panel-path` flag on `gate18` CLI

**Source**: L5-B Task A retry Phase 3 deviation #3.

**Surfaced**: 2026-05-14 L5-B Task A ACCEPT (commit `53deb90`; review branch `reviews/l5-b-task-a-accept` @ `bdeb2d6`).

Track A's L5-A `_cli_gate18` in `macro_pipeline/validation.py` doesn't accept a `--panel-path` flag; it uses `PANEL_CACHE_PATH` from `analysis.r_squared_panel` as the default. V's L5-B Task A retry prompt PHASE 3 invoked Gate 18 with `--panel-path data/cache/<panel-file>.parquet` syntax which CLI doesn't parse. Workaround was to call via Python script (`python -c "..."`) supplying `panel_index` + `panel_path` explicitly. Functional equivalence achieved; flag-based CLI is a hygiene improvement.

**Effort estimate**: 0.25-0.5h
- Add argparse to `_cli_gate18`: 0.1h
- Update help text + tests: 0.15h
- Update CLI documentation in `validation.py` `__main__` dispatcher: 0.05h

**Priority**: **LOW** — functionality available via Python script (e.g., the script captured at `reviews/l5-b-task-a-accept/artifacts/gate18_cli_runtime.txt`); flag is operational hygiene improvement; not blocking any subsequent sub-phase.

**Owner**: L5b OOS hardening cycle (V to schedule alongside other CLI / ergonomic improvements).

**Acceptance criteria**:
1. `python -m macro_pipeline.validation gate18 --panel-path <path>` accepts an explicit panel cache path.
2. Existing default behavior (no `--panel-path` → uses `PANEL_CACHE_PATH`) preserved for backward compat.
3. Help text describes both invocation modes.

**Provenance trail**:
- L5-B Task A retry execution report (2026-05-14): deviation #3.
- `_cli_gate18` source: `macro_pipeline/validation.py` (post-S-11 commit `53deb90`).

---

---

## L5b-4 — Spec v7 surgical patch: magic-number cleanup §5.RM-4

**Source**: S-12 disposition Option A (RESOLVED-OPTION-A 2026-05-15).

**Surfaced**: L5-RM-4 ACCEPT review (commit `056d198`; verification report §8 deviation #1).

Spec `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` §5.RM-4 contains 4 magic-number sites + 1 header inconsistency that mismatch empirical production base. Sites enumerated in `L5_BUILD_SXX_LOG.md` S-12 entry:
1. §5.RM-4.0 line 921 — "31 slots total (25 base + 6 new)" → should be "29 (23 + 6)"
2. §5.RM-4.5 test #1 line 1051 — `test_dataclass_has_all_31_slots` → should be `_29_slots`
3. §5.RM-4.6 criterion 1 line 1070 — `count = 31` → should be `count = 29`
4. §5.RM-4.7 proof item 1 line 1081 — `== 31` → should be `== 29`
5. §5.RM-4.1.1 header line 935 — "(5 total)" → should be "(6 total)" (body already lists 6)

**Effort estimate**: 1-2h ChatGPT review + 0.5h Track A surgical scrub + 0.5h Strategic disposition ≈ 2-3h cycle (would constitute a v7 spec surgical patch comparable to v6).

**Priority**: **LOW** — doc residue only; zero functional impact. L5-RM-4 implementation works correctly per Pattern B + empirical Gate 20 PASS. Deferral to post-L5 retrospective is the right priority signal.

**Owner**: post-L5 retrospective (NOT during active L5 build; spec FROZEN per scope guard).

**Acceptance criteria**:
1. v7 spec patch updates 4 magic-number sites + 1 header
2. AP-AUTH-52 mitigation discipline enforced in v7: each new total derives from `<base_grep_count> + <delta>` with grep command shown
3. v7 ChatGPT review confirms 0 new magic-numbers introduced
4. L5-RM-4 test #1 + Gate 20 + verification report still align (already correct via Option A; v7 just cleans spec literals)

**Provenance trail**:
- S-12 in `L5_BUILD_SXX_LOG.md` (filed 2026-05-14; CONDITIONAL → RESOLVED-OPTION-A 2026-05-15)
- AP-AUTH-52 codified in `docs/ap_register.md` (2026-05-15)

---

## L5b-5 — Investigate NBER pre-1978 training caveat (spec §5.RM-4 step 3)

**Source**: L5-13 absorption step 3 deferral.

**Surfaced**: L5-RM-4 ACCEPT report (2026-05-15; verification report §5 + §8 deviation #2).

Spec `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` §5.RM-4.1.4 step 3 reads: "Add NBER pre-1978 caveat to notes when `pre_1978_training_only=True` flag is set (mirrors CRPS handling)."

**Deferral rationale**: no `pre_1978_training_only` flag exists in:
- `ScoredObservation` dataclass schema (pre- or post-RM-4)
- `scoring/cdrs.py` code path (no flag set/read)
- Any caller surface (no current data flow constructs the flag)

Spec step 3 reads as speculative — anticipates a future state where pre-1978 training mode is distinguished from post-1978 NBER-announcement-calendar mode. The flag would need to be introduced upstream (likely in `RegimeContext` or `PitDataContext`) before L5-13 step 3 can be implemented.

**Effort estimate**: 2-4h
- Investigate intended semantic of `pre_1978_training_only` (consult L3.5C NBER calendar spec): 1h
- Add `pre_1978_training_only` flag to appropriate dataclass (RegimeContext likely): 1-2h
- Wire flag through CDRS code path; add NBER pre-1978 caveat note formatter helper: 0.5-1h
- 2-3 regression tests covering pre-1978/post-1978 caveat emission: 0.5h

**Priority**: **MED** — validity of pre-1978 NBER labels affects long-horizon drawdown statistics in OOS hardening (L5b scope). Not blocking any L5 sub-phase; relevant for L5b OOS hardening sprint where pre-1978 vs post-1978 sample distinction matters.

**Owner**: L5b OOS hardening cycle (likely L5b-RM-X sub-phase or equivalent).

**Acceptance criteria**:
1. Spec ambiguity resolved (consult L3.5C `regime/nber_calendar.py` + L3.5C verification docs)
2. `pre_1978_training_only` flag introduced (probably `RegimeContext`)
3. CDRS adds caveat to notes when flag is set; CRPS continues current pattern
4. Tests verify caveat presence pre-1978 + absence post-1978

**Provenance trail**:
- L5-RM-4 verification report §5 (L5-13 absorption table; step 3 row marked DEFERRED)
- L5-RM-4 ACCEPT report §8 deviation #2

---

---

## L5b-6 — Gate 20 criterion 3 wording-vs-implementation drift (L5-E awareness)

**Source**: ChatGPT 5.5 post-RM-4 gate review §D.1 + §B.E (PASS-WITH-NOTE).

**Surfaced**: 2026-05-15 post-RM-4 gate review.

**Issue**: Spec `LAYER_5_BUILD_SPEC.md` v6 §5.RM-4 Gate 20 PASS criterion 3 says "Parquet roundtrip smoke-test PASSes (test #2)". RM-4 implementation (commit `056d198`) used a **JSON roundtrip** in `test_parquet_roundtrip_preserves_6_new_slots` because real parquet would require wrapping ScoredObservation into a DataFrame schema that's not in scope for RM-4. The JSON form preserves the same invariant (new fields survive a round-trip via `to_dict()`) but is wording-vs-implementation drift relative to spec criterion 3.

**Acceptable for RM-4** because:
- RM-4 deliverable is the dataclass migration (fields + validators), NOT a production parquet schema
- JSON roundtrip via `to_dict()` exercises the same field-preservation contract
- ChatGPT post-RM-4 gate review explicitly marked this PASS-WITH-NOTE (not REVISE)

**L5-E future scope**: L5-E (forecast σ confidence band) is the sub-phase that builds the production parquet schema for ScoredObservation export. L5-E pre-flight MUST:
1. Implement a real parquet roundtrip (pyarrow schema declaration + write + read + element-wise comparison)
2. NOT cite RM-4 Gate 20 criterion 3 as precedent (RM-4 used JSON; L5-E must use parquet)
3. Verify all 6 RM-4 new fields survive parquet roundtrip (especially `drawdown_conditional_distribution: dict[str, float]` which requires pyarrow Map type)

**Effort estimate**: 0.25h doc-only ticket (this backlog entry); L5-E implementation cost separate (~1-2h for parquet schema declaration + test).

**Priority**: **LOW** (informational; prevents future L5-E error; ChatGPT review accepted current RM-4 state).

**Owner**: L5-E pre-flight + L5b OOS hardening cycle.

**Acceptance criteria** (L5-E):
1. L5-E implements `tests/test_*::test_parquet_roundtrip_*` using actual parquet (NOT JSON)
2. Schema declaration verified for all 6 RM-4 new fields + 23 pre-existing
3. Round-trip element-wise equality
4. L5-E verification report explicitly notes "Gate 20 RM-4 used JSON per L5b-6; L5-E provides real parquet"

**Provenance trail**:
- ChatGPT 5.5 post-RM-4 gate review (2026-05-15; ACCEPT-WITH-NOTES at 86% conf / 8.4/10)
- RM-4 commit `056d198` + L5_RM_4_VERIFICATION.md §2.2 (cites JSON variant)
- Spec §5.RM-4.6 criterion 3 + §5.RM-4.7 proof item 2

---

## L5b-7 — Spec v7 doc-residue: file naming drift + Gate 19 split

**Source**: Strategic disposition D-B1-1 + D-B1-2 (2026-05-13) at L5-B Task B1 pre-flight ACCEPT.

**Surfaced**: L5-B Task B1 pre-flight read-and-plan (this sub-phase).

Spec `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` contains five doc-vs-implementation drifts that do not affect behavior but should be reconciled at a future v7 spec patch:

1. **§5.B.0 + §5.B.1.1 + §5.B.7 proof item 1**: spec literal `macro_pipeline/models/ridge_cv.py` does not exist in the implementation. Task A shipped at `macro_pipeline/models/composite_refit.py` (l5-b-task-a-accept). Task B1 shipped at `macro_pipeline/models/return_forecast.py` (l5-b-task-b1-accept; D-B1-1 disposition). Task B2 shipped at `macro_pipeline/models/return_calibration.py` (l5-b-task-b2-accept; D-B1-1 precedent continued). Spec proof item 1 reads "from macro_pipeline.models.ridge_cv import fit_composite_weights, fit_return_forecast_task_b1, calibrate_return_forecast_task_b2, ...". Actual: three separate import paths.

2. **§5.B.6 Gate 19**: spec authored as a monolithic 22-criterion gate covering Task A + B1 + B2. V's build plan unbundled into per-sub-phase ACCEPT tags, so Gate 19 is split into 19-A (criteria 1-7, Task A, ✓ at `l5-b-task-a-accept`), 19-B1 (criteria 8-14 + 19-22, Task B1, ✓ at `l5-b-task-b1-accept` via `validate_gate19_l5b_task_b1_subcriteria`), and 19-B2 (criteria 15-18, Task B2, ✓ at `l5-b-task-b2-accept` via `validate_gate19_l5b_task_b2_subcriteria`). After all three partial-PASS milestones land, the spec-monolithic Gate 19 is conceptually closed. Sub-criterion 19 "all 28 tests PASS" splits across the three milestones — Task A delta (twelve), Task B1 delta with B2-1 promoted into the Task B1 file (fourteen; was thirteen in spec, plus the promoted B2-1), Task B2 delta minus B2-1 (two; was three in spec, minus the promoted B2-1); total reconciles to twenty-eight, preserving the spec literal mirror anchor exactly per AP-AUTH-52 magic-number derivability discipline.

3. **§5.D.0 metadata anchor stale vs §5.D.5/.6/.7 canonical (D-D-1 + D-D-2)**: spec §5.D.0 metadata table says "Test delta +8 (≥4 NEG = 50% floor; 5 NEG / 3 POS = 63% NEG)" but §5.D.5 header + §5.D.5 footer + §5.D.6 PASS criterion 8 + §5.D.7 proof item 2 + §5.D.7 proof item 9 all assert the canonical "+12 tests" (eight NEG / four POS = 67%). The §5.D.0 anchor is a stale v1 relic that v2/v3/v4 expansions left orphaned. Implementation followed §5.D.5/.6/.7 canonical at `l5-d-accept`. Symbolic derivation per AP-AUTH-52: "+12 = eight v2 baseline + four v2/v3 cell_label taxonomy expansion (test #9 Wilson interval + test #10 diagnostic_only label + test #11 hierarchical pooling v4 amended + test #12 no-raw-nan v3 taxonomy)". D-D-2: §5.D.7 proof item 2 references `tests/test_drawdown_conditional.py` (singular) while §5.D.0 metadata "New files" row uses `tests/test_drawdown_conditionals.py` (plural). Single-letter typo in §5.D.7; implementation followed plural per metadata canonical.

4. **§5.E.0 metadata anchor stale vs §5.E.5 canonical (D-E-1)**: spec §5.E.0 metadata table says "Test delta +6 (≥3 NEG; 3 NEG / 3 POS = 50% NEG)" but §5.E.5 header explicitly contains a "wait recount" literal mid-line — the spec author noticed inconsistency in-place ("v2: +9; 4 NEG / 5 POS = 44% NEG ... wait recount") and the footer reconciles via reclassifying test #1 as NEG-invariant to canonical "+9 tests (five NEG / four POS = 56%)". The §5.E.0 anchor is stale v1 relic; the §5.E.5 mid-line "wait recount" artifact is itself a spec-authoring trace that should be cleaned in v7. Implementation followed §5.E.5 canonical at `l5-e-accept`. Symbolic derivation per AP-AUTH-52: "+9 tests = six v1 baseline + three v2 NEW per S-6 (test #7 joint bootstrap covariance + test #8 empirical coverage + test #9 coverage inflation factor)".

5. **§5.G.0 metadata anchor stale vs §5.G.5/.7 canonical (D-G-1)**: spec §5.G.0 metadata table says "Test delta +6 (≥3 NEG; 4 NEG / 2 POS = 67% NEG)" but §5.G.5 header + §5.G.5 footer + §5.G.7 proof item 4 (v5 amended) + §5.G.7 proof item 8 (v5 symbolic) all assert the canonical "+8 tests" (five NEG / three POS = 63%). The §5.G.0 anchor is stale v1 relic from before the v2 S-4 K_HORIZON backsolve expansion added tests #6 + #7 + #8. Implementation followed §5.G.5/.7 canonical at `l5-g-accept`. Symbolic derivation per AP-AUTH-52: "+8 tests = five v2 baseline + three v2 NEW per S-4 (test #6 horizon rejection + test #7 W_REF_TARGET within ±2pp at N_REF_NONOVERLAP + test #8 k_h sensitivity 0.5×/1×/2× monotone)".

**Effort estimate**: 1–2h ChatGPT review + 0.5h Track A surgical scrub + 0.5h Strategic disposition ≈ 2–3h cycle (similar to L5b-4).

**Priority**: **LOW** — doc-only residue; zero functional impact. Implementation matches Strategic-approved D-B1-1/-2/-3 + D-D-1/-2 + D-E-1 + D-G-1 dispositions, validated through `l5-b-task-b2-accept` (Gate 19 closure), `l5-d-accept` (drawdown_conditionals doc-residue), `l5-e-accept` (forecast_sigma doc-residue + Op-E-1 path (b)+(c) v2 helper resolution), and `l5-g-accept` (bayesian_shrinkage doc-residue + Gate 25 composite SEALED via 25.1 + 25.2 sub-criteria; mirrors L3.5b Gate 17 composite seal pattern per spec §5.G.6).

**Owner**: post-L5 retrospective (NOT during active L5 build; spec FROZEN per scope guard).

**Acceptance criteria**:
1. v7 spec rewrites §5.B.0 + §5.B.1.1 + §5.B.7 proof item 1 to reflect actual module paths (`composite_refit.py` for Task A; `return_forecast.py` for Task B1; future Task B2 path TBD).
2. v7 spec rewrites §5.B.6 Gate 19 as three sub-gates 19-A / 19-B1 / 19-B2, each with its own criterion numbering. Spec sub-criterion 19 anchor count updates from "28 tests" to "29 tests" (derivation cited symbolically: Task A twelve + Task B1 fourteen with B2-1 promoted + Task B2 two; grep evidence required per AP-AUTH-52).
3. AP-AUTH-52 magic-number discipline applied: each new total derives from `<base_grep_count> + <delta>` with grep evidence cited.
4. v7 ChatGPT review confirms 0 new file-naming or gate-split inconsistencies introduced.
5. v7 spec rewrites §5.D.0 metadata "+8 / 63% NEG" stale anchor to canonical "+12 / 67% NEG" per §5.D.5/.6/.7 mirror. Fixes §5.D.7 proof item 2 typo `test_drawdown_conditional.py` (singular) to plural per metadata "New files" row.
6. v7 spec rewrites §5.E.0 metadata "+6 / 50% NEG" stale anchor to canonical "+9 / 56% NEG" per §5.E.5 mirror. Removes §5.E.5 header literal "wait recount" spec-authoring trace; consolidates the test #1 NEG-invariant reclassification into a clean header. Expands §5.E.7 proof contract (currently "parallel to §5.D.7 pattern; brevity") into explicit ten-item enumeration matching the §5.D.7 template.
7. v7 spec rewrites §5.G.0 metadata "+6 / 67% NEG" stale anchor to canonical "+8 / 63% NEG" per §5.G.5/.7 mirror. Documents the v2 K_HORIZON backsolve derivation (per S-4) explicitly in §5.G.1, including the formula `k_h = (w_ref / (1 - w_ref)) × n_ref` cited alongside the resulting constants (5.9 / 6.7 / 9.4 / 11.0).

**Provenance trail**:
- L5-B Task B1 ACCEPT report (2026-05-13) — initial entry surface
- L5-B Task B2 ACCEPT report (2026-05-13) — extended for `return_calibration.py` + Gate 19 final-close confirmation + test-count miscount correction (prior entry asserted "twenty-nine" total; corrected to twenty-eight matching the spec literal mirror anchor since B2-1 is INSIDE the Task B1 file's fourteen, not an additional test)
- L5-D ACCEPT report (2026-05-13) — extended for §5.D.0 stale anchor (D-D-1) + §5.D.7 proof item 2 typo (D-D-2)
- L5-E ACCEPT report (2026-05-13) — extended for §5.E.0 stale anchor (D-E-1) + §5.E.5 header "wait recount" literal + §5.E.7 proof-contract brevity expansion + Op-E-1 path (b)+(c) v2 callable-helper resolution
- L5-G ACCEPT report (2026-05-13) — extended for §5.G.0 stale anchor (D-G-1) + Gate 25 composite SEAL confirmation (25.1 + 25.2 sub-criteria validated; mirrors L3.5b Gate 17 pattern per spec §5.G.6)
- L5-H ACCEPT report (2026-05-13) — no new L5b-7 bullet added at L5-H (Strategic-approved D-H-1 through D-H-5 are all spec-literal-faithful resolutions of Strategic-prompt-vs-spec divergence at L5-H; no narrative drift to backlog). Provenance entry recorded here for L5 chain closure traceability.
- AP-AUTH-52 codified at `docs/ap_register.md` (sibling discipline)
- D-B1-1 / D-B1-2 / D-B1-3 + D-D-1 / D-D-2 + D-E-1 + D-G-1 Strategic dispositions (Track B chat, 2026-05-13)

---

**END — L5B_BACKLOG.md (L5b-2 + L5b-3 + L5b-4 + L5b-5 + L5b-6 + L5b-7 as of 2026-05-13 post-`layer5-complete`; reserved L5b-1 + L5b-8..N open for L5b OOS hardening sprint)**
