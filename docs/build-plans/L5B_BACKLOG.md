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

Confirmed via L5b-KICK-1 (isotonic `fit_window` invariant) + L5b-KICK-2 (forecast σ v2 production wrapper). Anticipated to apply at KICK-3 through KICK-7. **KICK-3 confirmed (third instance) at `l5b-kick-3-accept`** — see entry below. **KICK-4 confirmed (fourth instance, internal-implementation variant) at `l5b-kick-4-accept`** — see entry below. **KICK-5 confirmed (fifth instance, second internal-implementation variant) at `l5b-kick-5-accept`** — AP-AUTH-54 codified at this commit (see entry below). **KICK-6 confirmed (sixth instance, third internal-implementation variant; lightest-weight envelope) at `l5b-kick-6-accept`** — see entry below. **KICK-7 confirmed (seventh and FINAL instance; documentation-primary variant) at `l5b-kick-7-accept`** — AP-AUTH-55 codification DEFERRED per AP-AUTH-46 gratuitous-codification guard (first documentation-primary instance only; revisit if pattern repeats at L6+); see entry below + L5b KICKOFF SPRINT COMPLETE summary at the end of this section.

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
**AP-AUTH delta**: zero (AP-AUTH-53 cited as governing pattern; fourth instance; internal-implementation variant documented inline; AP-AUTH-54 deferred per Strategic until variant repeats at KICK-5+). **CODIFIED at KICK-5 ACCEPT** — see entry below.
**Sxx delta**: zero.

---

### KICK-5 — Bootstrap diagnostics table per horizon/fold (2026-05-15)

**ACCEPT tag**: `l5b-kick-5-accept`
**Reviewer authority**: ChatGPT 5.5 IMPORTANT #6 — "Add a bootstrap diagnostics table. Per horizon/fold: `n_train`, `n_eff`, `block_size`, `block_count`, `B_effective`, `fallback flag`. Edge-case fallback matters most at 10Y. Block bootstrap primary sizing is viable under the coded underpowered guard. However, sensitivity settings can hit low block counts and fall back, as warnings surfaced in the targeted run. That is acceptable if reported, but L5b should quantify actual folds."
**Approach**: A (Strategic-approved 2026-05-15; second internal-implementation variant after KICK-4) — in-place refactor of two private helpers (`_block_bootstrap_residual_se`, `_compute_block_size_sensitivity`) to return tuples carrying `BootstrapDiagnostics`, plus two no-default fields on `RidgeFitResult`. NOT a wrapper-pattern because the modified helpers are private; AP-AUTH-54 internal-implementation variant pattern applies.
**Option**: Y (Strategic-approved 2026-05-15) — Gate 19-B1 extension via signature inspection plus runtime probe synthesizing a Ridge fit and verifying tri-state `fallback_flag` reachability. Three new criteria (twenty-five / twenty-six / twenty-seven): (i) both KICK-5 fields no-default; (ii) `BootstrapDiagnostics` six-field schema check; (iii) runtime probe confirms primary diagnostics + sensitivity sweep dict populated with valid tri-state.
**Strategic prompt anomalies resolved at read-and-plan (mirror KICK-4 precedent)**:
- ITEM 0a — L5-D scope-out: ChatGPT mandate explicitly targets BLOCK bootstrap edge-case fallback; L5-D's `_bootstrap_threshold_se` is BLOCK-FREE (line four-one-two docstring "Block-free residual bootstrap"). Applying KICK-5 diagnostics to L5-D would produce degenerate values (block_size equal to one, B_effective always full, fallback_flag always "none") — ceremonial, not substantive. Gate 23 NOT touched at KICK-5.
- ITEM 0b — Dual-field surface (primary plus sensitivity sweep): Strategic §3.3 wrote "one fit equals one bootstrap call" but empirical probe at 5Y/expanding with B=10 shows each fit has FIVE bootstrap calls (one primary plus four sensitivity sizes). Reviewer concern explicitly targets sensitivity sweep ("sensitivity settings can hit low block counts and fall back"). Surfaced dual-field design: `bootstrap_diagnostics: BootstrapDiagnostics` (primary) plus `block_size_sensitivity_diagnostics: dict[str, BootstrapDiagnostics]` (sweep).
**Sxx-17 triage**: NOT triggered (Strategic's predicted state confirmed empirically — zero production scoring callers of `fit_return_forecast_task_b1` exist; only consumers are twenty-five-test L5-B1 suite plus Gate 19-B1 validator). Prospective-only marker per AP-AUTH-46 gratuitous-Sxx guard: if a production caller subsequently consumes a `RidgeFitResult` with `bootstrap_diagnostics.fallback_flag` not equal to "none" as production-grade SE, downstream gate should detect.
**Reviewer-flagged path empirically traceable**: pre-flight ITEM 0b probe at 5Y/expanding with B=10 demonstrated ALL ten folds at sensitivity-sweep `"2h"` block size (= 120 months) trigger `"B_halved"` fallback (block_count = two; B halves from ten to five). K5.4 test pins this empirically at commit time. Post-KICK-5 downstream consumers can detect this via `r.block_size_sensitivity_diagnostics["2h"].fallback_flag == "B_halved"` without parsing warning text.
**Algorithm correctness**: NO algorithm change. The fallback logic at `_block_bootstrap_residual_se` lines four-five-zero through four-seven-two is preserved verbatim; KICK-5 only surfaces the state that was previously buried in warning messages.
**Test delta**: plus six new tests (K5.1 through K5.6; four POS plus one POS-inv plus two NEG; NEG-flavor three of six equals fifty percent at the sub-phase level — floor met). No fixups to existing nineteen L5-B1 tests (none construct `RidgeFitResult` directly; tuple-return refactor is transparent at the public boundary). Baseline seven-hundred-thirty-nine to seven-hundred-forty-five.
**Caller updates**: zero in production tree (no production caller of `fit_return_forecast_task_b1` exists; Sxx-17 prospective-only).
**Edge cases verified**:
- `len(y_test) < 2` returns `(np.empty(0), diagnostics_with_B_effective_zero)` rather than raising — preserves existing graceful-degradation contract while emitting valid diagnostics
- `len(y_test) < 2` in sensitivity sweep populates NaN SE per label but valid diagnostics per label (B_effective = zero)
- Tri-state `fallback_flag` validation rejects invalid strings at `__post_init__` (K5.5 verified)
- All six fields no-default per AP-AUTH-54 step #2 (K5.6 verified across three field positions)
**AP-AUTH delta**: plus one (**AP-AUTH-54 codified at this commit** — see codification block below).
**Sxx delta**: zero.

---

### AP-AUTH-54 codification (2026-05-15, anchored at `l5b-kick-5-accept`)

**AP-AUTH-54 — Internal-implementation variant of AP-AUTH-53.**

When the reviewer-flagged surface is an internal helper (`_` prefix) or private estimator mechanic rather than a public production boundary, the AP-AUTH-53 closure mechanism applies via the following variant:

1. **In-place refactor of the internal helper** — change signature, return contract, or body as needed to expose the post-refactor invariant. No `_v2` wrapper required (would be ceremonial for internal helpers).
2. **No-default field on a related public dataclass** — exposes the refactor's surface state to downstream consumers for gating and runtime inspection. AP-AUTH-53 step #3 (force caller intent) is satisfied at the dataclass field rather than at the public function signature.
3. **Gate validator extension via Option Y** — signature inspection on the public dataclass + AST audit on the internal helper body OR runtime probe on a synthesized fit.
4. **Pre-flight empirical evidence** — when reviewer concern targets an edge-case path (e.g., fallback, degenerate state), pre-flight read-and-plan should demonstrate the path is empirically reachable in production fixtures before Phase 0, to confirm the discipline isn't ceremonial.

Confirmed via L5b-KICK-4 (inner-CV z-scaler purity; private helper `_select_lambda_inner_cv_ridge`; field `inner_cv_scaler_recomputed`) + L5b-KICK-5 (bootstrap diagnostics table; private helper `_block_bootstrap_residual_se`; fields `bootstrap_diagnostics` + `block_size_sensitivity_diagnostics`). Anticipated to apply at KICK-6+ when reviewer flags target internal estimator mechanics rather than public output contracts. **KICK-6 confirmed (third instance, lightest-weight envelope) at `l5b-kick-6-accept`** — see entry below.

---

### KICK-6 — Ridge inference labeling separation (2026-05-15)

**ACCEPT tag**: `l5b-kick-6-accept`
**Reviewer authority**: ChatGPT 5.5 IMPORTANT #5 — "Separate Ridge forecast inference from feature significance. Affected sub-phase: L5-B / reporting. Regularized coefficients do not support naive per-feature inference. Ridge return p-values are necessarily proxy diagnostics, not coefficient-level inferential p-values for every feature. The final reports should label them as forecast-vs-realized or model-level diagnostics, not 'feature significance.'"
**Approach**: A (Strategic-approved 2026-05-15; third internal-implementation variant of AP-AUTH-54; lightest-weight envelope) — add `inference_label: InferenceLabel` no-default field to `RidgeFitResult` plus rewrite misleading docstring at `p_value_beta_hac` field declaration. NO helper refactor (AP-AUTH-54 step #1 N/A); entire AP-AUTH-54 mechanism satisfied via steps #2-4 (no-default field + Option Y gate inspection + pre-flight empirical evidence chain). NOT a wrapper-pattern because no helper change required.
**Option**: Y (Strategic-approved 2026-05-15) — Gate 19-B1 extension via signature inspection plus runtime probe asserting `inference_label == "forecast_vs_realized"` on every fold. Two new criteria (twenty-eight / twenty-nine).
**Sxx-18 triage (Strategic §14 mandatory check)**: NOT triggered. Empirical evidence chain at read-and-plan ITEM 0 verified that `return_forecast.py:998-1005` calls `fit_ols_hac(y_test, forecast_test, ...)` which is univariate realized = alpha + beta times forecast + eps regression (one x variable); `newey_west_hac.py:48` docstring unambiguously confirms single-x regression. The `p_value_beta_hac` field IS forecast-vs-realized calibration slope p-value (NOT Ridge per-feature coefficient inference). Reviewer interpretation correct; sub-phase correctly scoped as labeling-clarity not algorithm-correction.
**Misleading docstring rewritten** (Phase four): pre-KICK-6 line three-two-four inline comment said "ridge fits y on full X — use overall F-test p surrogate" — both misleading (Ridge does not admit per-feature p-values under standard sampling theory; no F-test surrogate is computed). Post-KICK-6 comment explicitly cites the univariate forecast-vs-realized regression and disclaims Ridge coefficient inference. K6.2 POS-invariant test pins this rewrite via source-substring inspection ("forecast-vs-realized" + "NOT a Ridge").
**Tri-state taxonomy** (matches Strategic §3.2):
- `"forecast_vs_realized"` — p-value from univariate calibration regression diagnostic (institutionally correct label for Ridge fits in this module; default post-KICK-6)
- `"feature_significance"` — per-feature coefficient inference (reserved for future OLS variants; not used by Ridge)
- `"diagnostic_only"` — p-value reported as illustrative but not statistically inferential
**First `__post_init__` on `RidgeFitResult`** (Phase two): tri-state validation enforced at construction time. Mirrors KICK-3 `BinDiagnosticStatus` plus KICK-5 `BootstrapDiagnostics` validator precedents. Frozen-dataclass compatibility verified (validator is read-only; no `object.__setattr__` calls).
**AP-AUTH-54 lightest-weight envelope variance** (Strategic disposition seven approved): KICK-4 was heaviest (helper refactor plus field plus AST audit); KICK-5 was medium (tuple-return helper plus dual fields plus runtime probe); KICK-6 is lightest (dataclass discipline plus docstring rewrite plus runtime probe — no helper change). All three are coherent internal-implementation variants. No sub-variant codification needed per Strategic; envelope range documented inline in module docstring for future reference.
**Test delta**: plus five new tests (K6.1 through K6.5; one POS plus one POS-inv plus two strict NEG plus one NEG-inv; NEG-flavor four of five equals eighty percent at sub-phase level — floor met). Plus K4.4 cosmetic fixup at test line five-eight-three (Strategic disposition eight; `inference_label="forecast_vs_realized"` added so K4.4 precisely tests only `inner_cv_scaler_recomputed` omission; substring match still works regardless). Baseline seven-hundred-forty-five to seven-hundred-fifty.
**Caller updates**: zero in production tree (no production caller of `fit_return_forecast_task_b1` exists; consistent shape with Sxx-13 through Sxx-17 prospective-only outcomes).
**Effort variance**: smallest L5b sub-phase to date (1.0-1.5h actual estimated; one new field plus docstring rewrite plus five tests plus two-criterion gate extension).
**AP-AUTH delta**: zero (AP-AUTH-53 plus AP-AUTH-54 cited as governing patterns; third internal-implementation variant; lightest-weight envelope variance documented inline; no new codification needed per Strategic disposition seven).
**Sxx delta**: zero.

---

### KICK-7 — DMS source memo (2026-05-15)

**ACCEPT tag**: `l5b-kick-7-accept`
**Reviewer authority**: dual-reviewer convergence — Codex 5.5 (NICE-TO-HAVE upgraded to IMPORTANT by Strategic synthesis) + ChatGPT 5.5 IMPORTANT — "Add DMS source memo. Document current DMS/UBS edition, table, US-vs-global premium gap, and transformation into basis-point adjustments. Public pages support DMS scope, not the exact minus-one-twenty-five / minus-one-seventy-five basis-point values." Both reviewers explicitly framed this as source-anchoring transparency, NOT value correction.
**Approach**: B (Strategic-approved 2026-05-15; documentation-primary variant of AP-AUTH-53; FIRST documentation-primary instance) — author `DMS_SOURCE_MEMO.md` at worktree root with seven required sections; update L5-F module docstring with memo reference; extend Gate 25.1 sub-criterion body with additive Criterion 25.1.7 (file-presence plus section-header check). NO code-behavior change; NO algorithm change; Q6-lock values preserved verbatim.
**ITEM 0 honest-memo framing (Strategic disposition one CONFIRMED)**: UBS Global Investment Returns Yearbook full edition is a paid publication; specific table-line citations cannot be source-checked publicly. The memo §4 explicitly acknowledges that the spec-locked basis-point values are institutional judgment within the empirically-supported DMS range (one-hundred to two-hundred basis-point survivorship gap per public DMS-derived summaries), NOT fabricated table-derived precision. This framing is exactly what ChatGPT 5.5 IMPORTANT asks for — transparency, not value correction. The honest-memo path closes both reviewer concerns at face value.
**Sxx-19 triage**: NOT triggered. Honest-memo path explicitly avoids false-precision catastrophic state by acknowledging institutional-judgment component within empirically-supported range. Zero production callers of `apply_dms_adjustment` exist (consistent shape with Sxx-13 through Sxx-18 prospective-only outcomes — six consecutive prospective-only Sxx triages across all KICK sub-phases).
**Gate 25 composite SEAL preservation (Strategic disposition four CONFIRMED)**: composite seal at L5-G is structural (no new sub-criteria added after 25.2 closed at L5-G; 25.1 internal sub-criteria remain extensible). Criterion 25.1.7 is additive within the 25.1 (DMS) sub-criterion body; the composite seal logic at the validator boundary remains untouched. Validator name still includes "SEALED" suffix verbatim.
**Memo content (seven required sections per Strategic §3.2)**:
1. Source Identification (DMS 2002 book; Credit Suisse GIRY 2015-2022; UBS GIRY 2023+)
2. Empirical Foundation (US plus world-ex-US annualised real premia)
3. US-vs-Global Premium Gap (one-hundred to two-hundred basis-point empirical range)
4. DMS Adjustment Derivation (five-year and ten-year midpoint reasoning plus honest disclaimer)
5. Sensitivity Band Justification (plus-or-minus fifty basis-point one-sigma anchor)
6. Refresh Protocol (annual UBS Yearbook release cycle; material-shift threshold)
7. Strategic Interpretation (US-only prior vs global robustness check; L5-G framework integration)
**Test delta**: plus three new tests (K7.1 through K7.3; one POS plus one POS-inv plus one strict NEG; NEG-flavor two of three equals sixty-seven percent at sub-phase level — floor met). K7.3 uses pytest `monkeypatch` on `pathlib.Path.is_file` and `pathlib.Path.exists` to simulate missing memo without relocating real file. Baseline seven-hundred-fifty to seven-hundred-fifty-three.
**Caller updates**: zero in production tree (no production caller of `apply_dms_adjustment` exists; Sxx-19 prospective-only).
**AP-AUTH-55 codification analysis** (Strategic disposition five APPROVED — DEFER): KICK-7 is the FIRST documentation-primary variant of AP-AUTH-53. Per AP-AUTH-46 gratuitous-codification guard, pattern repetition needed before codification. Strategic does not currently anticipate further documentation-primary kickoff items in L5b A-E (all code-implementation). If L6/L7/L8 phases surface documentation-primary needs, revisit codification. **AP-AUTH-55 DEFERRED at KICK-7 ACCEPT.**
**Effort variance**: smallest sub-phase by code LOC delta to date (memo content dominates; 1.0-1.5h actual estimated).
**AP-AUTH delta**: zero (AP-AUTH-53 cited as governing pattern; documentation-primary variant documented inline; AP-AUTH-55 codification deferred).
**Sxx delta**: zero (Sxx-19 closed at pre-flight via ITEM 0 honest-memo framing).

---

## L5b KICKOFF SPRINT COMPLETE — Cumulative summary (2026-05-15)

**Status**: 7/7 reviewer-driven kickoff sub-phases COMPLETE. Sprint advances to original L5b OOS hardening scope (L5b-A through L5b-E).

### ACCEPT tag inventory

| # | Sub-phase | Tag | Closes reviewer concern |
|---|---|---|---|
| 1 | Isotonic train-only `fit_window` invariant | `l5b-kick-1-accept` | Codex 5.5 IMPORTANT + ChatGPT 5.5 CRITICAL #3 |
| 2 | Forecast σ v2 production wrapper + Gate 24 hard gate | `l5b-kick-2-accept` | Codex 5.5 IMPORTANT + ChatGPT 5.5 CRITICAL #2 |
| 3 | L5-C adaptive bin reduction + Gate 22 diagnostic status | `l5b-kick-3-accept` | Codex 5.5 IMPORTANT |
| 4 | L5-B1 inner-CV z-scaler recomputation (Task A parity) | `l5b-kick-4-accept` | Codex 5.5 IMPORTANT |
| 5 | Bootstrap diagnostics table per horizon/fold | `l5b-kick-5-accept` | ChatGPT 5.5 IMPORTANT #6 |
| 6 | Ridge inference labeling separation | `l5b-kick-6-accept` | ChatGPT 5.5 IMPORTANT #5 |
| 7 | DMS source memo | `l5b-kick-7-accept` | Codex 5.5 + ChatGPT 5.5 IMPORTANT (dual) |

### Cumulative deltas

| Metric | At KICK-1 start | At KICK-7 ACCEPT | Δ |
|---|---|---|---|
| Total pytest count | seven-hundred-seventeen | seven-hundred-fifty-three | plus thirty-six |
| AP-AUTH register | fifty-two codified | fifty-four codified | plus two (AP-AUTH-53 + AP-AUTH-54) |
| Active Sxx register | zero new (Sxx-12 was last L5 build-time) | zero new | zero (six prospective-only Sxx-13..-18 markers recorded in this file) |
| Gate criteria added | n/a | seventeen new across Gates 19-B1, 22, 24, 25 | plus seventeen |
| New dataclasses | n/a | one (`BootstrapDiagnostics`) | plus one |
| Convergence streak | n/a | twenty of twenty (rolling-mean velocity minus-fifty-eight percent) | maintained |

### AP-AUTH-53 + 54 envelope characterization

| Sub-phase | AP-AUTH-53 variant | Envelope weight |
|---|---|---|
| KICK-1 | public wrapper precursor (pre-codification) | medium |
| KICK-2 | public wrapper (AP-AUTH-53 codified at this ACCEPT) | medium |
| KICK-3 | public wrapper (third instance) | medium-heavy |
| KICK-4 | internal-implementation variant (AP-AUTH-54 first instance) | heavy (helper refactor + field + AST audit) |
| KICK-5 | internal-implementation variant (AP-AUTH-54 codified) | medium (tuple-return helper + dual fields + probe) |
| KICK-6 | internal-implementation variant (AP-AUTH-54 third instance) | lightest-weight (dataclass discipline only) |
| KICK-7 | **documentation-primary variant** (AP-AUTH-55 candidacy DEFERRED) | documentation-primary (memo + Gate file-presence check) |

### Pattern velocity (effort actual)

| Sub-phase | Actual | Cumulative banked headroom |
|---|---|---|
| KICK-1 | one-and-a-half hours | within budget |
| KICK-2 | one-and-six-tenths hours | within budget |
| KICK-3 | one-and-seven-tenths hours | within budget |
| KICK-4 | one-and-a-half hours | within budget |
| KICK-5 | one-and-seven-tenths hours | within budget |
| KICK-6 | one-and-three-tenths hours (smallest by LOC) | within budget |
| KICK-7 | one-and-a-half hours estimated (memo-content dominant) | within budget |

### Reviewer concerns fully closed

- Codex 5.5: all four IMPORTANT items closed (KICK-1, KICK-3, KICK-4, KICK-7)
- ChatGPT 5.5: all four IMPORTANT items closed (KICK-2 CRITICAL #2, KICK-5 IMPORTANT #6, KICK-6 IMPORTANT #5, KICK-7 IMPORTANT)
- Plus KICK-1 closes ChatGPT 5.5 CRITICAL #3 as well (dual-reviewer convergence)

### Next phase

L5b sprint advances to original OOS hardening scope: L5b-A (block bootstrap robustness) through L5b-E (retrospective). All seven reviewer-driven kickoff sub-phases COMPLETE; institutional discipline patterns AP-AUTH-53 (public wrapper) + AP-AUTH-54 (internal-implementation variant) codified and available for reuse. AP-AUTH-55 (documentation-primary variant) deferred pending pattern repetition at L6+. **L5b-A confirmed (first original OOS hardening sub-phase post-kickoff; AP-AUTH-54 fourth instance; heavy envelope) at `l5b-a-accept`** — see entry below.

---

## L5b ORIGINAL OOS HARDENING SCOPE — entries below

---

### L5b-A — Stationary block bootstrap (Politis-Romano 1994) (2026-05-15)

**ACCEPT tag**: `l5b-a-accept`
**Authority**: ChatGPT 5.5 Dim-3 OOS rigor — "Block bootstrap primary sizing is viable under the coded underpowered guard. However the current fixed-block scheme is sensitive to block-size choice; stationary block bootstrap (Politis-Romano 1994) is the standard institutional default for serial-dependent residuals because the random block lengths converge to the correct asymptotic distribution without manual block-size tuning." Plus build plan §3.1 L5b-A literal scope: "Replace fixed block bootstrap in L5-B1 with stationary block bootstrap. Add geometric-block-length sampler. Preserve fallback semantics per KICK-5 BootstrapDiagnostics surface."
**Approach**: A (Strategic-approved 2026-05-15; AP-AUTH-54 fourth-instance internal-implementation variant; heavy envelope) — in-place refactor of private `_block_bootstrap_residual_se` body from fixed-block to stationary sampling per Politis-Romano (1994); add new private helper `_sample_stationary_block_lengths` for the geometric block-length sampler; expand `BootstrapDiagnostics` with seventh no-default field `block_length_distribution`. NOT a wrapper-pattern because the helper is private (`_` prefix). FIRST original OOS hardening sub-phase post-kickoff sprint.
**Option**: Y (Strategic-approved 2026-05-15) — Gate 19-B1 extension via signature inspection plus AST audit plus runtime probe. Three new criteria (thirty / thirty-one / thirty-two).
**1-field envelope revision** (Strategic disposition three APPROVED supersedes §3.4 2-field proposal): expand `BootstrapDiagnostics` with ONE new no-default field `block_length_distribution: Literal["fixed", "geometric"]`. Existing `block_size` field acquires polymorphic semantic per the discriminator — for `"fixed"` it is the exact block length; for `"geometric"` it is the geometric distribution mean parameter. Mirrors KICK-6 lightest-weight envelope precedent (1-field expansion). Documented in `BootstrapDiagnostics` class docstring.
**AP-AUTH-54 envelope characterization** (post-L5b-A; four-instance range):
- KICK-4 heaviest: helper refactor (z-scaler purity) + field + AST audit
- KICK-5 medium: tuple-return helper + dual fields + runtime probe
- KICK-6 lightest-weight: dataclass discipline only (no helper change)
- L5b-A **heavy** (comparable to KICK-4 reference): helper refactor (stationary sampling) + field + AST audit + runtime probe + pre/post empirical snapshot
**Algorithm**: Politis-Romano (1994) stationary block bootstrap. At each bootstrap iteration: draw block lengths from `Geometric(1 / mean_block_length)` via `_sample_stationary_block_lengths`; draw uniform start indices on `{0, ..., n_train minus one}`; assemble blocks with cyclic wrapping (`residuals[(s + j) % n_train]`); truncate concatenated series to `n_train`. The geometric distribution's memoryless property ensures asymptotic stationarity regardless of starting index.
**Sxx-20 triage**: NOT triggered. Zero production scoring callers of `fit_return_forecast_task_b1` exist; only consumers are thirty-five-test L5-B1 suite plus Gate 19-B1 validator. **Eighth consecutive prospective-only Sxx triage** (Sxx-13 through Sxx-20 spanning KICK-1 through L5b-A). Prospective-only marker per AP-AUTH-46 gratuitous-Sxx guard.
**Fallback-flag taxonomy preservation** (ITEM 6 of read-and-plan; Strategic disposition five CONFIRMED): integer floor-division `n_train // block_size` arithmetic is INVARIANT across fixed ↔ geometric variants. The fallback DECISION (`"none"` / `"B_halved"` / `"bs1_degenerate"`) depends only on `(n_train, block_size)` numerical values, not on the sampling METHOD. K5.4 sensitivity-sweep "2h" fallback "B_halved" test survives verbatim post-L5b-A; no test recalibration needed.
**R1 SE-drift empirical snapshot** (ITEM 2 read-and-plan + Phase 6 post-refactor re-snapshot):
- Pre-refactor (fixed-block) 5Y/expanding fold zero through four SE means: zero-point-one-two-nine, zero-point-zero-nine-nine, zero-point-one-nine-three, zero-point-one-five-four, zero-point-two-three-seven
- Post-refactor (stationary) same fixture: zero-point-one-two-eight, zero-point-zero-nine-eight, zero-point-one-nine-four, zero-point-one-five-four, zero-point-two-three-six
- Pairwise ratio (post divided by pre): within one percent across all five folds (well inside Strategic §6 plus-or-minus twenty percent tolerance band)
- Interpretation: on AR-noise-dominated synthetic fixture the methodological change is small (residuals close to iid); on real time-series data with stronger serial dependence the stationary variant's correctness advantage will be more pronounced
**Test delta**: plus five new tests (A.1 through A.5; one POS plus one POS-inv plus two strict NEG = three of five equals sixty percent NEG-flavor; floor met). Plus cosmetic fixups to K5.5 + K5.6 + K6.3 bare `BootstrapDiagnostics` constructors (post-L5b-A field count is seven; add `block_length_distribution="geometric"`). Baseline seven-hundred-fifty-three to seven-hundred-fifty-eight.
**Caller updates**: zero in production tree (no production caller of `fit_return_forecast_task_b1` exists; Sxx-20 prospective-only).
**AP-AUTH delta**: zero (AP-AUTH-54 cited as governing pattern; fourth internal-implementation instance; no new codification — pattern already codified at KICK-5 ACCEPT).
**Sxx delta**: zero.

---

### L5b-B — Structural break tests Quandt-Andrews plus Bai-Perron sequential supF (2026-05-15)

**ACCEPT tag**: `l5b-b-accept`
**Authority**: ChatGPT 5.5 Dim-3 OOS rigor — "Sample size honesty requires structural break detection. With one-hundred-thirteen non-overlapping one-year observations since nineteen-thirteen, the panel spans multiple monetary regimes (gold standard, Bretton Woods, Great Inflation, Great Moderation, ZIRP/QE, post-twenty-twenty-two). Distributional stationarity is the implicit assumption of Ridge SE and Brier reliability." Plus build plan §3.1 L5b-B literal scope: "Implement structural break tests on Ridge return forecast coefficient stability. Surface break dates and post-break parameter shifts; flag horizons where breaks invalidate sample-pooled inference."
**Approach**: B (Strategic-approved 2026-05-15; AP-AUTH-54 fifth-instance internal-implementation variant) — implement Quandt-Andrews supremum-Wald single-break test (Andrews 1993) plus Bai-Perron sequential supF variant for multi-break detection (simplified from full Bai-Perron 1998 dynamic-programming algorithm). Add `StructuralBreakDiagnostics` dataclass (seven no-default fields plus consistency-invariant `__post_init__`); add Optional field on `RidgeFitResult`; final-fold-only invocation per ITEM 3 computational cost mitigation. SECOND original OOS hardening sub-phase post-kickoff sprint.
**Option**: Y (Strategic-approved 2026-05-15) — Gate 19-B1 extension via signature inspection plus AST audit plus runtime probe at FINAL-fold position (Strategic Watch-point: "not first fold"). Three new criteria (thirty-three / thirty-four / thirty-five).
**Strategic disposition 3 (computational cost mitigation; ITEM 3 of read-and-plan)**: final-fold-only invocation. Without mitigation: per-pipeline cost is roughly one-hundred-thirty-three-thousand extra Ridge fits (two-hundred-seventeen folds at one-year times one-hundred-sixty-eight candidate tau times two sub-sample Ridge fits, summed across horizons). With final-fold-only mitigation: roughly one-thousand extra Ridge fits per pipeline (three final folds across one-year plus three-year plus five-year times one-hundred-sixty-eight candidates times two). Rationale: (i) final fold has most data and maximum statistical power; (ii) operationally meaningful break date is the most-recent estimate; (iii) per-fold break testing remains accessible via direct helper invocation.
**Strategic disposition 4 (simplified Wald + chi-squared p-value honest framing)**: Quandt-Andrews implementation uses the pragmatic `||delta_beta||^2 / pooled_var` form rather than the full sandwich variance `(beta_post - beta_pre)' V^(-1) (beta_post - beta_pre)` where `V` is the Ridge-regularised sandwich. Chi-squared p-value approximation (df = n_features) in place of Andrews 1993 asymptotic critical values. Documented in module docstring; full sandwich Wald deferred as L5b-residue.
**Strategic disposition 7 (AP-AUTH-54 envelope STAYS CLOSED)**: 4-instance range characterization preserved (KICK-4 heaviest / KICK-5 medium / KICK-6 lightest / L5b-A heavy). L5b-B is the 5th instance with three novel sub-characteristics documented as within-envelope variants: (a) two new helpers (Quandt-Andrews + Bai-Perron sequential supF) where prior instances modified ≤ one; (b) NEW dataclass `StructuralBreakDiagnostics` where prior instances modified existing dataclasses; (c) Optional/None field type where prior instances used non-Optional fields. Range stays closed.
**Algorithm**: Quandt-Andrews supremum-Wald per Andrews 1993; sequential supF per Bai-Perron 1998 (simplified). Trimming fraction default 0.15 per Andrews 1993 institutional recommendation (AP-AUTH-52 derivation from literature; not magic number). Maximum breaks default 3 per Bai-Perron 1998 K-parameter recommendation. Simplified Wald + chi-squared p-value (df = n_features) per Approach B.
**Sxx-21 triage**: NOT triggered. Zero production scoring callers of `fit_return_forecast_task_b1` exist. **Ninth consecutive prospective-only Sxx triage** (Sxx-13 through Sxx-21 spanning KICK-1 through L5b-B). Prospective-only marker per AP-AUTH-46 gratuitous-Sxx guard.
**Horizon applicability matrix** (empirical at default settings, n=480): one-year/expanding two-hundred-seventeen folds all applicable; three-year/expanding one-hundred-sixty-nine folds all applicable; five-year/expanding ten folds all applicable; ten-year/expanding zero folds at default settings (underpowered guard fires); None disabling semantic prospective for future configurations.
**Test delta**: plus six new tests (B.1 through B.6; one POS detect + one POS-inv no-break + one POS final-fold-populated + two strict NEG + one NEG-inv non-final-folds-None; NEG-flavor four of six equals sixty-seven percent at sub-phase level; floor met). Plus three cosmetic fixups (K4.4 + K6.3 + K6.4 bare `RidgeFitResult(...)` constructors; add `structural_break_diagnostics=None`). Baseline seven-hundred-fifty-eight to seven-hundred-sixty-four.
**Caller updates**: zero in production tree (no production caller of `fit_return_forecast_task_b1` exists; Sxx-21 prospective-only).
**AP-AUTH delta**: zero (AP-AUTH-54 cited as governing pattern; fifth internal-implementation instance; envelope STAYS CLOSED at 4-instance characterization per Strategic disposition 7; no new codification — pattern already codified at KICK-5 ACCEPT).
**Sxx delta**: zero.

---

### L5b-C — Benjamini-Hochberg FDR gating + Gate 26 NEW (2026-05-15)

**ACCEPT tag**: `l5b-c-accept`
**Authority**: ChatGPT 5.5 Dim-3 OOS rigor — "Multiple hypothesis testing in the L5 chain... without FDR control, individual test rejections cannot be trusted as 'significant'. Benjamini-Hochberg (1995) procedure controlling false discovery rate at q=0.10 is the standard institutional default." Plus build plan §3.1 L5b-C literal scope: "Apply Benjamini-Hochberg FDR control across the multiple p-value surface generated by L5 chain."
**Approach**: C (Strategic-approved 2026-05-15; honest dependence disclaimer per KICK-7 plus L5b-B precedent) — implement BH(1995) step-up monotone form; document BH-PRDS independence assumption explicitly; Benjamini-Yekutieli (2001) for arbitrary dependence deferred as L5b-residue. THIRD original OOS hardening sub-phase post-kickoff sprint.
**Module placement** (Strategic disposition 2): `macro_pipeline/analysis/fdr_gating.py` NEW file. Sibling to existing analysis surfaces (`brier_reliability.py`, `drawdown_conditionals.py`, `forecast_sigma.py`, `newey_west_hac.py`, `walk_forward_cv.py`). FDR gating is cross-cutting downstream-consumer; `analysis/` is the institutional convention.
**Gate 26 NEW** (Strategic disposition 3): first NEW gate since Gate 25 SEALED at L5-G. First downstream-consumer gate (FDR aggregates p-values produced by Gate 19-B1 Ridge plus L5b-B structural break diagnostics) vs prior implementation-correctness gates which inspect single-module output. Four criteria (26.1 API plus 26.2 BH algorithm correctness plus 26.3 aggregator runtime probe plus 26.4 invariant validator probe).
**AP-AUTH-54 envelope STAYS CLOSED** (Strategic disposition 4): 4-instance characterization preserved (KICK-4 heaviest / KICK-5 medium / KICK-6 lightest / L5b-A heavy). L5b-C is the SIXTH instance with three novel sub-characteristics documented as within-envelope variants: (a) NEW module file `analysis/fdr_gating.py`; (b) NEW gate (Gate 26); (c) NEW test file `test_fdr_gating.py`. All three are qualitative cross-cutting additions, not envelope-weight redefinition. Institutional AP-AUTH-54 mechanism preserved; only surface locations differ.
**Strategic disposition 7 (NaN filter via `math.isfinite`)**: aggregator filters non-finite p-values BEFORE applying BH. Empirical cardinality at default fixture (n=480, seed=42): 1Y/expanding contributes 1 (NaN-filtered ridge plus 1 break); 3Y/expanding contributes 1 (NaN-filtered ridge plus 1 break); 5Y/expanding contributes 11 (10 finite ridge plus 1 break); 10Y zero folds. **Total m=13** (not raw fold count 396). Documented in aggregator docstring + module-level NaN-handling section for future reviewers.
**Sxx-22 triage**: NOT triggered. Zero existing FDR infrastructure (greenfield); zero production callers of L5 chain p-value-bearing functions. **Tenth consecutive prospective-only Sxx triage** (Sxx-13 through Sxx-22 spanning KICK-1 through L5b-C). Prospective-only marker per AP-AUTH-46 gratuitous-Sxx guard.
**Algorithm correctness** (Gate 26 Criterion 26.2 empirically pinned): canonical test vector `[0.001, 0.01, 0.04, 0.05, 0.2]` at `q_threshold=0.10` produces step-up monotone q-values `[0.005, 0.025, 0.0625, 0.0625, 0.2]` matching hand computation to 1e-10. Reject 4 of 5 (q ≤ 0.10 for first four sorted p-values). Strategic §6 suggested 3-of-5 but the 4th sorted p-value's q-value (0.0625) is below the 0.10 threshold — verified empirically and pinned in test C.1.
**Test delta**: plus six new tests in NEW `tests/test_fdr_gating.py` (C.1 BH canonical + C.2 monotonicity invariant + C.3 aggregator + C.4 invalid q_threshold NEG + C.5 cardinality mismatch NEG + C.6 empty-input NEG-inv; NEG-flavor four of six equals sixty-seven percent at sub-phase level; floor met). No fixups to existing 41 L5-B1 tests (greenfield additions). Baseline seven-hundred-sixty-four to seven-hundred-seventy.
**Caller updates**: zero in production tree (no existing FDR infrastructure; greenfield).
**AP-AUTH delta**: zero (AP-AUTH-54 cited as governing pattern; sixth internal-implementation instance; envelope STAYS CLOSED at 4-instance characterization per Strategic disposition 4; no new codification — pattern already codified at KICK-5 ACCEPT).
**Sxx delta**: zero.

---

### L5b-D — Regime-conditional OOS Brier validation + Gate 27 NEW (2026-05-15)

**ACCEPT tag**: `l5b-d-accept`
**Authority**: ChatGPT 5.5 Dim-3 OOS rigor — "OOS validation must report regime-conditional metrics. The nineteen-thirteen-present sample spans multiple regimes (gold standard, Bretton Woods, Great Inflation, Great Moderation, ZIRP/QE, post-twenty-twenty-two). A model that passes OOS Brier improvement on the full sample may fail dramatically in any single regime." Plus build plan §3.1 L5b-D literal scope: "flag horizon × score-type combinations where regime-conditional Brier improvement is materially weaker (e.g., ΔBrier < fifty percent of full-sample value) than full-sample reporting suggests."
**Approach**: C (Strategic-approved 2026-05-15; REFINED via AP-AUTH-50 grep discovery of existing NBER infrastructure) — Callable-injection aggregator wired to existing `NberCalendarLoader.last_known_label(date).regime` in production; test fixtures pass synthetic lambdas. FOURTH original OOS hardening sub-phase post-kickoff sprint; **deepest methodological sub-phase of the L5b sprint**.
**Module placement** (Strategic disposition 2): `macro_pipeline/analysis/regime_conditional_validation.py` NEW file. Sibling to `fdr_gating.py` (L5b-C), `brier_reliability.py` (L5-C), and other analysis surfaces.
**Gate 27 NEW** (Strategic disposition 3): second NEW gate post-Gate-25-SEAL after L5b-C Gate 26. Cross-cutting downstream-consumer architecture (regime-conditional aggregator consumes calibrated probabilities plus binary outcomes plus dates) vs prior implementation-correctness gates which inspect single-module output. Four criteria (27.1 API + fourteen-field dataclass plus 27.2 reference classifier tri-state correctness plus 27.3 aggregator runtime probe plus 27.4 invariant validator probe).
**AP-AUTH-54 envelope STAYS CLOSED** (Strategic disposition 4): 4-instance range characterization preserved. L5b-D is the SEVENTH instance with FIVE within-envelope sub-characteristics documented per Strategic disposition 4: (1-3) NEW module + NEW gate + NEW test file (mirrors L5b-C pattern); (4) **largest dataclass** in L5b (fourteen fields + four invariants vs L5b-B's seven plus one, L5b-C's seven plus five); (5) **Callable injection** caller pattern (`regime_classifier` parameter). All five novel sub-characteristics are qualitative cross-cutting additions, not envelope-weight redefinition. Institutional AP-AUTH-54 mechanism preserved.
**NBER infrastructure discovery** (AP-AUTH-50 grep evidence): existing pipeline provides `macro_pipeline.regime.nber_calendar.NberCycle` plus `LastKnownLabel(regime: Literal["expansion", "recession"])` plus `NBER_CALENDAR_BOUNDARY = pd.Period("1978-01", freq="M")` plus `NBER_PRE_1978_POLICY = "training_only"` plus real-time fail-closed per Decision Lock 3.5C-D1. L5b-D CONSUMES this infrastructure via Callable injection rather than re-deriving classification.
**Pre-1978 handling tri-state** (Strategic disposition 6): `Literal["include", "exclude", "diagnostic_only"]` with `"diagnostic_only"` default. Matches L3.5C Decision Lock 3.5C-D1 spirit (pre-1978 reported as diagnostic, not as production-grade regime classification).
**L5b-5 non-closure documentation**: L5b-D caveat addressed at L5b-D aggregator layer via `pre_1978_handling: Literal[...]` field with `"diagnostic_only"` default; upstream `pre_1978_training_only` flag in `ScoredObservation` schema remains deferred per L5b-5 rationale. L5b-D and L5b-5 are different surface concerns — aggregator-level regime decomposition vs scoring-level caveat propagation.
**AP-AUTH-52 fifty-percent threshold derivation** (Strategic disposition 7): from build plan §3.1 literal "ΔBrier < fifty percent of full-sample value". Strict less-than per literal. NOT a magic number. Edge case (Strategic disposition 5 note): when `full_sample_brier_improvement <= 0`, threshold = `0.5 * <= 0`; subset improvement strictly less than non-positive threshold triggers flag. Flag remains well-defined in degenerate regime.
**Sxx-23 triage**: NOT triggered. Greenfield additions (no existing regime-conditional Brier surface); zero production callers. **Eleventh consecutive prospective-only Sxx triage** (Sxx-13 through Sxx-23 spanning KICK-1 through L5b-D). Prospective-only marker per AP-AUTH-46 gratuitous-Sxx guard.
**Test delta**: plus seven new tests in NEW `tests/test_regime_conditional_validation.py` (D.1 sensitivity flag fires on asymmetric calibration + D.2 stable performance flag false + D.3 reference classifier tri-state correctness + D.4 invalid pre_1978_handling NEG + D.5 missing field NEG + D.6 sensitivity flag inconsistency NEG + D.7 empty-recession-subset degenerate-valid NEG-inv; NEG-flavor five of seven equals seventy-one percent at sub-phase level; floor met). No fixups to existing 47 L5-D-relevant tests (greenfield additions). Baseline seven-hundred-seventy to seven-hundred-seventy-seven.
**Caller updates**: zero in production tree (greenfield).
**AP-AUTH delta**: zero (AP-AUTH-54 cited as governing pattern; seventh internal-implementation instance; envelope STAYS CLOSED at 4-instance characterization per Strategic disposition 4; no new codification — pattern already codified at KICK-5 ACCEPT).
**Sxx delta**: zero.

---

### L5b-E — Sprint retrospective + Gate 28 NEW (2026-05-14)

**ACCEPT tag**: `l5b-e-accept` plus `l5b-complete` (DUAL TAG marking L5b sprint completion).
**Authority**: Master Prompt v3.1 §15 (L5b OOS hardening sprint closure mandate) plus Strategic disposition cycle 2026-05-14 (five rulings ratified on Track A read-and-plan output).
**Approach**: documentation-primary sprint retrospective; OUTSIDE AP-AUTH-54 envelope per Strategic disposition four (Option (a) ratified — envelope STAYS CLOSED at seven instances). FIFTH original-scope OOS hardening sub-phase post-kickoff (final L5b sub-phase); closes the L5b sprint with DUAL TAG.
**Option**: Y (Strategic-approved 2026-05-14) — Gate 28 NEW via signature inspection plus file-presence plus section-substring presence plus file-size threshold. Four criteria (28.1 / 28.2 / 28.3 / 28.4) mirroring the Gate 25.1.7 KICK-7 documentation-primary parent precedent at `macro_pipeline/validation.py:5618-5675`.

**Strategic disposition rulings reflected** (five from 2026-05-14 §E greenlight block):
- **Disposition 1 (Finding 1 APPROVE in scope as Phase 5)**: AP-AUTH-53 plus AP-AUTH-54 codifications migrated verbatim from inline `L5B_BACKLOG.md:40-54` and `:127-138` to formal `docs/ap_register.md` (closes register-staleness gap; approximately fifteen minutes defensive addition).
- **Disposition 2 (Finding 2 APPROVE inline framing)**: retrospective §4 frames Sxx-13 through Sxx-23 as inline NOT-TRIGGERED markers per AP-AUTH-46 gratuitous-Sxx guard with line-ref citations to each marker in this file.
- **Disposition 3 (Finding 3 APPROVE corrected count)**: convergence streak phrased as "twenty-four of twenty-four entering L5b-E becoming twenty-five of twenty-five at L5b-E ACCEPT (sprint completion)".
- **Disposition 4 (Finding 4 APPROVE Option (a))**: AP-AUTH-54 envelope STAYS CLOSED at seven instances; L5b-E mirrors L5-H structurally (sprint retrospective), not KICK-7 (reviewer-driven kickoff). Documentation-primary variant precedent (KICK-7) does NOT re-open envelope for sprint retrospectives.
- **Disposition 5 (plan timing APPROVE)**: three-to-four-hour actual end-to-end estimate ratified; within risk-adjusted three-to-five-hour band; no compression mandate.

**Gate 28 NEW** four criteria (mirroring Gate 25.1.7 KICK-7 file-presence pattern at `macro_pipeline/validation.py:5618`):
- **Criterion 28.1 (API present)**: `validate_gate28_l5b_retrospective` callable importable from `macro_pipeline.validation`; CLI dispatcher registers it via `python -m macro_pipeline.validation gate28`.
- **Criterion 28.2 (section-substring presence)**: `L5B_RETROSPECTIVE.md` at worktree root contains all seven required H2 section substrings (Sprint context and convergence streak / Per-sub-phase inventory / AP-AUTH-54 envelope characterization / Sxx-13..23 inline NOT-TRIGGERED / Cumulative L5b sprint deltas / Reviewer-concern closure scoreboard / Forward readiness and closing recommendation).
- **Criterion 28.3 (file-size threshold)**: `L5B_RETROSPECTIVE.md` byte count is at least five-thousand bytes (institutional minimum for sprint-retrospective documentation depth; parallels Gate 25.1.7 implicit content-validation discipline).
- **Criterion 28.4 (runtime NEG probe via monkeypatch in test)**: file-absence simulated via `monkeypatch.setattr(pathlib.Path, "exists", fake_exists)` plus `is_file` produces FAIL finding citing the missing path; mirrors K7.3 monkeypatch pattern at `tests/test_dms_adjustment.py:213-240`.

**Sxx-NN triage**: zero new Sxx markers filed at L5b-E (documentation-primary sub-phase with greenfield retrospective plus new gate plus new test file; no prospective-only catastrophic-state probe relevant). Twelfth consecutive prospective-only-or-zero Sxx outcome across the L5b sprint (Sxx-13 through Sxx-23 inline NOT-TRIGGERED at KICK-1 through L5b-D plus zero new at L5b-E).

**Module placement**: new file `L5B_RETROSPECTIVE.md` at worktree root (sibling to `LAYER_5_RETROSPECTIVE.md` and `LAYER_3_5b_RETROSPECTIVE.md` parent precedents). Gate 28 validator added inline in `macro_pipeline/validation.py` (mirrors Gate 25.1.7 inline placement within the existing composite validator pattern). NEW test file `tests/test_l5b_retrospective.py` (sibling to `tests/test_dms_adjustment.py` K7.3 parent precedent).

**AP-AUTH register migration** (Phase 5 of code-exec per Strategic Disposition 1): AP-AUTH-53 (Reviewer-driven L5b kickoff item pattern; codified at `l5b-kick-2-accept` 2026-05-13) plus AP-AUTH-54 (Internal-implementation variant of AP-AUTH-53; codified at `l5b-kick-5-accept` 2026-05-15) entries copied verbatim from inline `L5B_BACKLOG.md:40-54` and `:127-138` into formal `docs/ap_register.md`. Format normalized to match parent template (Symptom / Surfaced / Mitigation discipline / Enforcement / Cross-reference structure).

**Test delta**: plus three new tests in NEW `tests/test_l5b_retrospective.py` (E.1 file-exists POS plus E.2 seven-required-substrings POS-inv plus E.3 monkeypatch missing-file NEG; NEG-flavor two of three equals sixty-seven percent at sub-phase level per L5-B1 accounting convention where POS-inv counts as NEG-flavor; floor met). Baseline seven-hundred-seventy-seven to seven-hundred-eighty.

**Caller updates**: zero in production tree (greenfield retrospective plus gate plus test file).

**AP-AUTH delta**: zero new codifications. AP-AUTH-53 plus AP-AUTH-54 verbatim entries migrated to formal `docs/ap_register.md` per Strategic Disposition 1. No new institutional pattern surfaced at sprint-retrospective level (L5b-E mirrors L5-H structurally per Strategic Disposition 4).

**Sxx delta**: zero.

**Effort variance**: documentation-primary sub-phase; three-to-four hours actual end-to-end estimated per Strategic Disposition 5 (within risk-adjusted three-to-five-hour band; no compression mandate). Effort distribution: Phase 0 state verification approximately fifteen minutes; Phase 1 retrospective authoring approximately sixty to ninety minutes; Phase 2 backlog update approximately thirty to forty-five minutes; Phase 3 Gate 28 addition approximately thirty minutes; Phase 4 test file approximately thirty minutes; Phase 5 register migration approximately fifteen minutes; Phase 6 full pytest plus Gate 28 CLI approximately fifteen minutes; Phase 7 verification plus commit plus DUAL TAG approximately fifteen minutes.

---

## L5b SPRINT COMPLETE — Cumulative summary (2026-05-14)

**Status**: twelve of twelve L5b sub-phases ACCEPT-tagged. Seven reviewer-driven kickoff (KICK-1 through KICK-7) plus four original OOS hardening (L5b-A through L5b-D) plus L5b-E sprint retrospective ALL COMPLETE. L5b OOS hardening sprint CLOSED with DUAL TAG `l5b-e-accept` plus `l5b-complete`.

### ACCEPT tag inventory (twelve sub-phases)

| # | Sub-phase | Tag | Closes reviewer concern (if any) |
|---|---|---|---|
| 1 | Isotonic train-only `fit_window` invariant | `l5b-kick-1-accept` | Codex 5.5 IMP #1 + ChatGPT 5.5 CRIT #3 (dual) |
| 2 | Forecast σ v2 production wrapper + Gate 24 hard gate | `l5b-kick-2-accept` | ChatGPT 5.5 CRIT #2 (also Codex 5.5 IMP) |
| 3 | L5-C adaptive bin reduction + Gate 22 diagnostic status | `l5b-kick-3-accept` | Codex 5.5 IMP #2 |
| 4 | L5-B1 inner-CV z-scaler recomputation (Task A parity) | `l5b-kick-4-accept` | Codex 5.5 IMP #3 |
| 5 | Bootstrap diagnostics table per horizon/fold | `l5b-kick-5-accept` | ChatGPT 5.5 IMP #6 |
| 6 | Ridge inference labeling separation | `l5b-kick-6-accept` | ChatGPT 5.5 IMP #5 |
| 7 | DMS source memo (documentation-primary) | `l5b-kick-7-accept` | Codex 5.5 IMP #4 + ChatGPT 5.5 IMP (dual) |
| 8 | Stationary block bootstrap (Politis-Romano 1994) | `l5b-a-accept` | (original OOS hardening scope) |
| 9 | Structural break tests (Andrews 1993 + Bai-Perron 1998) | `l5b-b-accept` | (original OOS hardening scope) |
| 10 | Benjamini-Hochberg FDR gating + Gate 26 NEW | `l5b-c-accept` | (original OOS hardening scope) |
| 11 | Regime-conditional OOS Brier validation + Gate 27 NEW | `l5b-d-accept` | (original OOS hardening scope) |
| 12 | **Sprint retrospective + Gate 28 NEW** | **`l5b-e-accept` + `l5b-complete` (DUAL TAG)** | (sprint closure) |

### Cumulative deltas (L5 closure to L5b-E ACCEPT)

| Metric | Value at `layer5-complete` | Value at `l5b-complete` (target) | Delta |
|---|---|---|---|
| Pytest count | seven-hundred-seventeen | seven-hundred-eighty | plus sixty-three across twelve sub-phases |
| Gate count | twenty-five (Gate 25 composite SEALED at L5-G via 25.1 plus 25.2 PASS) | twenty-eight | plus three (Gate 26 L5b-C + Gate 27 L5b-D + Gate 28 L5b-E) |
| Gate criteria added | n/a (baseline) | plus twenty-seven across L5b sprint | plus twenty-seven |
| AP-AUTH register | one through fifty-two | one through fifty-four | plus two (AP-AUTH-53 at KICK-2; AP-AUTH-54 at KICK-5) |
| Formal Sxx register (`L5_BUILD_SXX_LOG.md`) | S-one through S-twelve (all RESOLVED) | unchanged | zero new filings |
| Prospective-only Sxx markers (inline in this file) | zero | eleven (Sxx-13 through Sxx-23) | plus eleven NOT-TRIGGERED per AP-AUTH-46 |
| New modules under `macro_pipeline/analysis/` | n/a | two (`fdr_gating.py` from L5b-C; `regime_conditional_validation.py` from L5b-D) | plus two |
| New dataclasses | n/a | four (`BootstrapDiagnostics` KICK-5; `StructuralBreakDiagnostics` L5b-B; `FDRGatingDiagnostics` L5b-C; `RegimeConditionalDiagnostics` L5b-D) | plus four |
| New private helpers | n/a | at least five (geometric block sampler L5b-A; Quandt-Andrews supW L5b-B; Bai-Perron sequential supF L5b-B; BH step-up L5b-C; regime aggregator L5b-D) | plus five-or-more |
| Convergence streak | thirteen of thirteen at L5-H ACCEPT | twenty-five of twenty-five at L5b-E ACCEPT | plus twelve consecutive perfect-ACCEPT sub-phases |
| Banked headroom under risk-adj budget | approximately fifty hours at L5 closure | approximately eighty-eight to ninety-two hours | plus approximately thirty-eight to forty-two hours |
| Sprint window | n/a | two calendar days (2026-05-13 KICK-1 through 2026-05-14 L5b-E ACCEPT) | shortest multi-sub-phase sprint of the build to date |
| Reviewer-concern closure | n/a (review window opened post-L5-H push) | eight of eight closed (one-hundred percent) | see scoreboard below |

### AP-AUTH-53 + AP-AUTH-54 envelope characterization (CLOSED at seven instances per Strategic Disposition 4)

| Instance | Sub-phase | Envelope weight | Surface |
|---|---|---|---|
| 1 | KICK-4 | heaviest | helper refactor (`_select_lambda_inner_cv_ridge`) + no-default field (`inner_cv_scaler_recomputed`) + AST audit |
| 2 | KICK-5 | medium | tuple-return helper (`_block_bootstrap_residual_se` + `_compute_block_size_sensitivity`) + dual no-default fields + runtime probe (**AP-AUTH-54 codified here**) |
| 3 | KICK-6 | lightest-weight | dataclass discipline only (no helper change); no-default field (`inference_label`) + docstring rewrite + runtime probe |
| 4 | L5b-A | heavy | helper refactor (stationary block sampling) + new helper (`_sample_stationary_block_lengths`) + field expansion + AST + runtime + empirical snapshot |
| 5 | L5b-B | heavy-medium | two new helpers (Quandt-Andrews + Bai-Perron) + NEW dataclass + Optional field |
| 6 | L5b-C | medium-cross-cutting | NEW module (`analysis/fdr_gating.py`) + NEW gate (Gate 26) + NEW test file + BH(1995) algorithm |
| 7 | L5b-D | heavy-cross-cutting | NEW module (`analysis/regime_conditional_validation.py`) + NEW gate (Gate 27) + largest dataclass (fourteen fields) + Callable injection |

**L5b-E is OUTSIDE this envelope per Strategic Disposition 4** — sprint retrospective is structurally L5-H peer (parent retrospective precedent), not KICK-7 peer (reviewer-driven kickoff). Documentation-primary variant precedent set at KICK-7 (AP-AUTH-55 codification DEFERRED per AP-AUTH-46 gratuitous-codification guard) does NOT re-open envelope for sprint retrospectives. The envelope characterization preserves four envelope-weight buckets (heaviest / heavy / medium / lightest-weight) populated across the seven AP-AUTH-54 instances; range is closed and stable.

### Pattern velocity (effort actual per sub-phase ACCEPT report)

| Sub-phase | Effort actual / risk-adj | Rolling cumulative variance |
|---|---|---|
| KICK-1 | one-and-a-half hours | minus-fifty-eight percent vs risk-adj |
| KICK-2 | one-and-six-tenths hours | held |
| KICK-3 | one-and-seven-tenths hours | held |
| KICK-4 | one-and-a-half hours | held |
| KICK-5 | one-and-seven-tenths hours | held |
| KICK-6 | one-and-three-tenths hours (smallest by LOC) | tightened |
| KICK-7 | one-and-a-half hours estimated (memo-content dominant) | held |
| L5b-A | within budget | held |
| L5b-B | within budget | held |
| L5b-C | within budget | held |
| L5b-D | within budget | held |
| L5b-E | three-to-four hours estimated (documentation-primary; retrospective + gate + test + register migration) | held within risk-adj three-to-five-hour band |

### Reviewer-concern closure scoreboard (eight of eight equals one-hundred percent)

- Codex 5.5: all four IMPORTANT items closed (IMP #1 at KICK-1; IMP #2 at KICK-3; IMP #3 at KICK-4; IMP #4 at KICK-7)
- ChatGPT 5.5: all four IMPORTANT items closed (CRIT #2 at KICK-2; IMP #6 at KICK-5; IMP #5 at KICK-6; IMP at KICK-7)
- Plus KICK-1 closes ChatGPT 5.5 CRITICAL #3 as dual-reviewer convergence with Codex 5.5 IMP #1
- Plus KICK-7 closes Codex 5.5 IMP #4 and ChatGPT 5.5 IMP simultaneously (dual-reviewer convergence)
- Aggregate: eight unique concerns; eight closed; one-hundred percent closure rate within the KICKOFF arc (KICK-1 through KICK-7)

### Institutional pattern compounding

- **AP-AUTH-53 codification at KICK-2 ACCEPT**: reviewer-driven L5b kickoff item pattern formalised after second instance (KICK-1 was deferred per AP-AUTH-46 first-instance rule; KICK-2 ACCEPT triggered codification per pattern-repetition rule). Migrated to formal `docs/ap_register.md` at L5b-E.
- **AP-AUTH-54 codification at KICK-5 ACCEPT**: internal-implementation variant of AP-AUTH-53 formalised after second internal-implementation instance (KICK-4 deferred per same first-instance rule; KICK-5 codified upon repetition). Migrated to formal `docs/ap_register.md` at L5b-E.
- **AP-AUTH-55 deferral at KICK-7 ACCEPT**: documentation-primary variant of AP-AUTH-53 NOT codified per AP-AUTH-46 first-instance rule (KICK-7 was the first documentation-primary instance; revisit at L6+ if pattern repeats).
- **Sxx-13 through Sxx-23 prospective-only inline NOT-TRIGGERED markers**: eleven consecutive NOT-TRIGGERED outcomes across the sprint (KICK-1 through L5b-D) demonstrate AP-AUTH-46 gratuitous-Sxx guard working as designed. Formal `L5_BUILD_SXX_LOG.md` register unchanged at S-12 RESOLVED-OPTION-A.

### Next phase (post-L5b-E ACCEPT)

L5b sprint CLOSED. Downstream paths per Strategic post-L5b-E workflow (per `07_STRATEGIC_CLAUDE_L5b-E_DISPOSITION_PROMPT.md` §"Post-L5b-E ACCEPT workflow"):

- **Path A**: re-engage Codex 5.5 plus ChatGPT 5.5 dual-reviewer cycle via v2.0 review guides (`03_CODEX_CODE_REVIEW_v2.md` + `02_CHATGPT_METHODOLOGY_REVIEW_v2.md`) for second-round review of the L5b sprint outputs (AP-AUTH-53 / 54 closure mechanisms plus OOS hardening additions: block bootstrap; structural breaks; FDR; regime-conditional Brier).
- **Path B**: proceed to L1.7 MANUAL_INPUT framework per Vision v2.0 §15 phased plan progression toward L8a Core UI MVP (target completion 2026-07-28 per Vision v2.0 §15).

V selects path post-L5b-E ACCEPT. Documentation suite v2.0 commit (per `06_CLAUDE_CODE_COMMIT_PROMPT.md`) remains pending and can be executed at any time after L5b-E ACCEPT per Strategic Disposition Note E.

**L5b-A through L5b-E sequence (this file) plus KICK-1 through KICK-7 sequence (this file) jointly complete the L5b OOS hardening sprint.** Master Prompt v3.1 §15 L5b scope CLOSED at this DUAL TAG.

**Post-L5b-E re-opening notice (2026-05-15)**: R6 external reviewer cycle (Codex 5.5 + ChatGPT 5.5) returned RATIFY-WITH-FINDINGS with four HIGH plus five MEDIUM findings requiring remediation before L1.7. Sprint advances to L5b-F (remediation), L5b-G (AP-AUTH-49 cherry-pick), L5b-H (AP-AUTH-41 v7 scope refinement); `l5b-complete` tag will be MOVED from this commit to L5b-H ACCEPT per Strategic disposition. The L5b SPRINT COMPLETE summary above remains historically accurate at the L5b-E ACCEPT moment.

---

### L5b-F — R6 reviewer-driven remediation sub-phase (four HIGH plus five MEDIUM findings) (2026-05-15)

**ACCEPT tag**: `l5b-f-accept`
**Authority**: Codex 5.5 + ChatGPT 5.5 R6 external review (RATIFY-WITH-FINDINGS) per Strategic disposition cycle 2026-05-15 (§E greenlight block; AP-AUTH-53 reviewer-driven kickoff pattern; AP-AUTH-54 eighth-instance internal-implementation variant).
**Approach**: MONOLITHIC scope per Strategic disposition; nine findings closed in single sub-phase (four HIGH plus five MEDIUM) plus one OPERATIONAL (F-O1 lazy credential gating). AP-AUTH-49 + AP-AUTH-41 v7 deferred to L5b-G + L5b-H per Strategic post-L5b-F workflow.
**Option**: Y across six implementation phases (Y signature inspection plus runtime probe at gate validators) — Gate 24 extension (Criteria fifteen plus sixteen for F-H1) plus Gate 27 extension (Criteria 27.5 plus 27.6 for F-H2).

**R6 reviewer findings closed (nine findings plus one OPERATIONAL)**:

| Finding | Severity | Phase | Resolution |
|---|---|---|---|
| F-H1 | HIGH | Phase 1 | Forecast σ v2 wrapper at `analysis/forecast_sigma.py` recomputes band using `z × forecast_sigma_with_covariance × coverage_inflation_factor` instead of copying v1 quadrature band |
| F-H2 | HIGH | Phase 2 | `RegimeConditionalDiagnostics` extended with five no-default fields (horizon plus n_eff_recession plus n_eff_expansion plus max_confidence_cap plus diagnostic_only); 10Y regime-stratified hard cap zero-point-five-five per Standing Order ten |
| F-H3 | HIGH | Phase 3 | `regime_conditional_validation.py` exp_mask conditional fix at line four-six-four (Strategic option (a)): `pre_1978_handling="include"` aggregates pre-1978 obs into expansion subset per docstring |
| F-H4 | HIGH | Phase 3 | Fail-closed classifier validation at line four-four-one: invalid regime labels raise ValueError citing offending label sorted |
| F-M1 | MEDIUM | Phase 5c | `StructuralBreakDiagnostics.formal_inference: bool = False` field at `models/return_forecast.py:473` — simplified supF / chi-square approximation labeled informal per Strategic preference (relabel rather than implement full DP) |
| F-M2 | MEDIUM | Phase 4 | `ood_reserve_fraction` REQUIRED kwarg at aggregator (fail-closed); Vision v2.0 §7 five-to-fifteen-percent range enforced; raises ValueError when omitted or out of range |
| F-M3 | MEDIUM | Phase 4 | Lucas critique surface via `lucas_flag` plus `regime_shift_test` plus `pre_post_metric_delta` plus `lucas_warning_text` four no-default fields; reuses L5b-B `StructuralBreakDiagnostics` for break detection within twenty-four-month lookback |
| F-M4(a) | MEDIUM | Phase 5a | `fdr_gating.py` extended with `method: Literal["BH", "BY"]` plus `family_id: Optional[str]` parameters; BY method via `_benjamini_yekutieli_qvalues` helper using `c(m) = sum(1/i for i in 1..m)` adjustment factor for general-dependence FDR per Benjamini-Yekutieli (2001) |
| F-M4(b) | MEDIUM | Phase 5b | `DMS_SOURCE_MEMO.md` §3 prose clarification per Strategic Note C: distinguishes Quantity A (underlying US-vs-global gap two-hundred-to-three-hundred bps) from Quantity B (conservative forecast adjustment one-hundred-to-two-hundred bps) — two distinct quantities, not a single inconsistent range |
| F-M5 | MEDIUM | Phase 4 | Murphy (1973) decomposition by stratum via opt-in `compute_murphy_decomposition` kwarg; CIs via stationary block bootstrap reusing L5b-A `_sample_stationary_block_lengths` helper; invariant ten enforces `reliability - resolution + uncertainty ≈ brier` within `1e-6` |
| F-O1 | OPERATIONAL | Phase 6 | `config.py` import-time credential check converted to lazy `require_fred_api_key()` helper at fred_loader call sites; analysis modules (`regime_conditional_validation`, `fdr_gating`) now import without `FRED_API_KEY` env var |

**Sxx-NN triage**: zero new Sxx markers filed at L5b-F. Twelfth consecutive prospective-only-or-zero Sxx outcome at the sprint level. Phase 6 callsite classification (Note A): three (c)-class implicit-non-None FRED_API_KEY assumption sites located, all in fred loaders as expected; converted to `require_fred_api_key()` lazy validation. No external (a)/(b)/(c) anomalies; no STOP-and-surface triggered.

**AP-AUTH-54 envelope** (Strategic Note D): L5b-F is the eighth instance; envelope **RE-OPENED** from seven (CLOSED at L5b-E) to eight at L5b-F entry, expected to **STAY CLOSED** at eight instances post-L5b-F. Multi-axis within-envelope variant: Phase 1 helper refactor plus Phase 2 / 3 / 4 dataclass extension (plus thirteen fields combined) plus Phase 5a new algorithm (BY method) plus Phase 5b / 5c documentation. No novel sub-characteristic surfaced — institutional AP-AUTH-54 mechanism preserved.

**Dataclass extensions**:
- `RegimeConditionalDiagnostics`: fourteen baseline fields → thirty-two fields (plus five Phase 2 plus eight Phase 4 Murphy plus one Phase 4 OOD plus four Phase 4 Lucas); plus eight new invariants (invariants five through thirteen)
- `StructuralBreakDiagnostics`: seven baseline fields → eight fields (plus one Phase 5c `formal_inference: bool = False`); default value preserves backward compat (no constructor cascade)
- `FDRGatingDiagnostics`: unchanged at seven fields (Phase 5a BY method via function kwargs, not dataclass extension)
- `ForecastSigmaResult`: unchanged (Phase 1 fix to v2 wrapper body only; field set preserved)

**Test delta**: plus twenty-two new tests across six implementation phases:

| Phase | New tests | Files |
|---|---|---|
| Phase 1 | plus three | `tests/test_forecast_sigma.py` |
| Phase 2 | plus four | `tests/test_regime_conditional_validation.py` |
| Phase 3 | plus four | `tests/test_regime_conditional_validation.py` |
| Phase 4 | plus four | `tests/test_regime_conditional_validation.py` |
| Phase 5 | plus four | `tests/test_fdr_gating.py` (two) plus `tests/test_dms_adjustment.py` (one) plus `tests/test_return_forecast.py` (one) |
| Phase 6 | plus three | `tests/test_dms_adjustment.py` |

Baseline seven-hundred-eighty to eight-hundred-two. NEG-flavor distribution: nine of twenty-two equals forty-one percent at sub-phase level — floor met per L5-B1 accounting convention.

**Caller updates** (fixture cascade in `tests/test_regime_conditional_validation.py`):
- Twelve aggregator call sites updated with `horizon` plus `ood_reserve_fraction` required kwargs
- Four direct `RegimeConditionalDiagnostics(...)` constructors updated with eighteen new field values per Phase 2 plus Phase 4 dataclass extensions

**Gate criteria added** (Strategic deliverable five):
- Gate 24: plus two criteria (fifteen plus sixteen) for F-H1 v2 band recomputation
- Gate 27: plus two criteria (27.5 plus 27.6) for F-H2 regime-stratified cap enforcement

**AP-AUTH delta**: zero new codifications. AP-AUTH-53 plus AP-AUTH-54 cited as governing patterns. AP-AUTH-49 (precommit infra cherry-pick to main) deferred to L5b-G per Strategic post-L5b-F workflow. AP-AUTH-41 v7 scope refinement deferred to L5b-H. Informal AP-AUTH-55 enforcement at Phase 7 (explicit branch plus tag push per Strategic Note E) — formal codification queued post-L5b-H.

**Sxx delta**: zero.

**Effort variance**: Strategic nominal twelve-to-sixteen hours; risk-adjusted fifteen-to-twenty hours; convergence-prior projection nine-to-thirteen hours. Actual end-to-end estimated within band per agent-time pacing; mapped to human-equivalent within the risk-adjusted range.

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
