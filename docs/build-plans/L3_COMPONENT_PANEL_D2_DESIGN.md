# L3 component_panel Patch — D2 Design Doc (CDRS V×T×R ↔ Spec "4 buckets" Mapping)

**Date**: 2026-05-13
**Branch**: `claude/layer-5-l3-component-patch` (forked from `claude/layer-5-build` @ `711f641`)
**Trigger**: S-10 resolution; Strategic chose Option (iv) HYBRID; D2 mapping needs design + Strategic confirmation BEFORE Phase 2 code
**Spec ref**: `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` §5.B.1 (lines 587 + 663-673)
**Code refs**: `scoring/cdrs.py` (V×T×R formula); `scoring/cdrs_vulnerability.py` lines 36-42 (V structure); `scoring/cdrs_trigger.py` lines 30-36 (T structure)

---

## §1 — Spec verbatim (lines 587)

> Task A | Refit CRPS/CDRS component weights | Component-level feature matrix — CRPS: 6 components (yield curve + Sahm + LEI + ISM + FCI + credit); CDRS: **4 buckets (valuation + sentiment + credit/liquidity + vol/breadth/technical)** | Component coefficients + intercept + λ per fold | Penalized logistic (CRPS against NBER USREC 12M labels per §3.3); penalized logistic / ordinal (CDRS against drawdown threshold labels per §3.3)

Hard constraints from spec:
1. **§5.B.5.A test A1**: `component_panel` DataFrame ≥ **4 columns** for CDRS (≥ 6 for CRPS).
2. **§5.B.6 Gate 19 row 3**: output `component_coefficients: dict[str, float]` with **≥ 4 keys** for CDRS (≥ 6 for CRPS).
3. **§5.B.5.A test A4**: NOT collapsed to scalar β; must be per-component dict.

Anything ≥ 4 columns/keys satisfies the spec literal. The "4 buckets" naming is a structural framing hint, not a hard column-count cap.

---

## §2 — L3 reality: scoring/cdrs.py V×T×R structure

CDRS formula: `CDRS = V × T × R` (clipped to [0, 1]).

| Stage | Internal structure | Cardinality |
|---|---|---|
| **V** (Vulnerability) | Mean of 5 sub-components: V1_cape_pctile, V2_margin_z, V3_concentration_proxy, V4_ey_real_gap_z, V5_ey_deviation. All normalized ∈ [0, 1]. Equal-weight 0.20 each. | **5 columns** |
| **T** (Trigger) | Mean of 5 sub-components: T1_hy_oas_30d_roc, T2_vix_12m_pctile, T3_gamma_sign, T4_breadth_thrust, T5_move_z. All normalized ∈ [0, 1]. Equal-weight 0.20 (post-2022) or 0.25 (pre-2022; T3 graceful degradation). | **5 columns** |
| **R** (Regime multiplier) | Discrete: {expansion=0.6, late-cycle=1.0, recession=1.4}. From `RegimeContext.derive_regime_state()` (L3A + L3.5D INDETERMINATE consensus path). | **1 column** (or one-hot 3-column encoding) |

Total raw column space if exposed: **11 columns** (5 V + 5 T + 1 R). Grouped by Stage: **3 columns** (V_score + T_score + R).

---

## §3 — Three mapping candidates

### §3.1 Candidate M1: Direct V/T sub-components + R (11 columns)

Schema:
```
Index: time (monthly DatetimeIndex matching L5-A panel_index)
Columns:
  V1_cape_pctile, V2_margin_z, V3_concentration_proxy,
  V4_ey_real_gap_z, V5_ey_deviation,
  T1_hy_oas_30d_roc, T2_vix_12m_pctile, T3_gamma_sign,
  T4_breadth_thrust, T5_move_z,
  R_regime_multiplier
```

**Pros**:
- Preserves all L3 information; no signal loss via averaging
- Penalized logistic can discover per-sub-component β coefficients (high methodology rigor per §5.B.3 line 764 "Ridge penalty resolves multicollinearity")
- Strategic could later refine bucket structure post-build via inspection of β patterns

**Cons**:
- Does NOT match spec literal "4 buckets" (11 ≠ 4; structural framing mismatch)
- Higher dimensionality at small fold n_eff (1Y h=12 → n_eff ≈ 20 for 240-month train; 11 columns with n_eff=20 risks overfit even with Ridge penalty)
- Per-component AUC + Brier reporting (12 metrics per fold × N folds × 8 schedules) inflates `CompositeWeightRefitResult` payload
- R as scalar regime multiplier doesn't behave as a "feature" in the penalized-logistic sense (it's a structural rescaling, not a predictor)

### §3.2 Candidate M2: 4-bucket aggregation per spec literal (4 columns)

Schema:
```
Index: time
Columns:
  bucket_valuation         = mean(V1_cape_pctile, V4_ey_real_gap_z, V5_ey_deviation)
  bucket_sentiment         = mean(V2_margin_z, V3_concentration_proxy)
  bucket_credit_liquidity  = mean(T1_hy_oas_30d_roc, T3_gamma_sign)
  bucket_vol_breadth_technical = mean(T2_vix_12m_pctile, T4_breadth_thrust, T5_move_z)
```

R EXCLUDED from `component_panel` (treated as structural regime multiplier applied post-Task-A; Task A fits **un-regime-adjusted** sub-bucket weights; R applied at downstream L5-RM-6 or L5-D conditional distributions).

**Mapping rationale** (Strategic to confirm):
- **valuation** = V1 (CAPE) + V4 (EY real gap) + V5 (EY deviation) — all 3 are direct valuation metrics
- **sentiment** = V2 (margin debt z) + V3 (concentration proxy) — sentiment / positioning indicators
- **credit/liquidity** = T1 (HY OAS RoC) + T3 (dealer gamma sign) — credit spread shocks + dealer positioning liquidity
- **vol/breadth/technical** = T2 (VIX percentile) + T4 (breadth thrust) + T5 (MOVE z) — volatility + technical breadth

**Pros**:
- Matches spec literal "4 buckets" exactly
- Lower dimensionality (4 cols) reduces overfit risk at small fold n_eff
- Matches L3's placeholder weight structure (Task A is REFITTING bucket weights; L3 currently uses uniform 0.20-each at sub-component level)
- Clean 4-key `CompositeWeightRefitResult.component_coefficients` output

**Cons**:
- Aggregation via simple mean loses sub-component-level signal (e.g., if V1 CAPE is highly predictive but V4/V5 are noise, M2 averages them down)
- Bucket mapping is judgmental (e.g., T4 breadth could be "sentiment" instead of "vol/breadth/technical"; Strategic call)
- ISM + LEI absence in CRPS means cross-score comparability is degraded (CRPS=4 active cols; CDRS=4 buckets); not directly a Task A concern but visible at L5-C Brier comparison

### §3.3 Candidate M3: 4-bucket aggregation + R as 5th column (5 columns)

Schema: M2's 4 columns + `R_regime_multiplier` as scalar column.

**Pros**:
- Matches spec literal "4 buckets" (4 BUCKET columns + 1 R column treated separately)
- Includes R as feature — penalized logistic can discover regime-conditional weighting
- Strategic Q3 lock (Bayesian shrinkage `weight = k_h / (k_h + n_eff)` at L5-G) suggests regime-conditional adjustment is in-scope at L5

**Cons**:
- R is a discrete 3-state variable; penalized logistic on 5-col matrix where 1 col is discrete may need one-hot encoding (7 cols actual) which complicates the "4 bucket" framing
- Spec §5.B Task A doesn't explicitly include regime conditioning — that's L5-G's domain
- Spec test A1 + Gate 19 row 3 expect "4 cols" / "4 keys"; M3's 5 cols/keys may or may not pass (depends on strict interpretation of ≥4)

---

## §4 — Track A recommendation

**RECOMMEND: Candidate M2 (4-bucket aggregation per spec literal).** R excluded from component_panel; treated as downstream structural rescaling.

### §4.1 Why M2 over M1

| Criterion | M1 (11 cols) | M2 (4 buckets) | Winner |
|---|---|---|---|
| Spec literal "4 buckets" match | ✗ (11 cols) | ✓ (4 cols) | **M2** |
| Spec §5.B.5.A test A1 (≥4 col floor) | ✓ | ✓ exactly | tie |
| Spec §5.B.6 Gate 19 row 3 (≥4 key dict) | ✓ | ✓ exactly | tie |
| Overfit risk at small n_eff | HIGH (11 features / 20 obs) | LOW (4 / 20) | **M2** |
| Methodology rigor §5.B.3 line 764 | Higher (more multicollinearity headroom) | Adequate (Ridge still relevant) | M1 marginal |
| Methodology rigor §5.B.4 nested-CV λ selection | Stable | Stable | tie |
| L3 placeholder weight structure match | ✗ (sub-component) | ✓ (bucket-level) | **M2** |
| Strategic decision burden post-confirmation | Higher (per-sub-component β interpretation) | Lower (4 named buckets) | **M2** |

M2 wins 4/8 with 4 ties; M1 wins 0/8.

### §4.2 Why M2 over M3

M3's R-as-5th-column conflicts with L3's V×T×R semantic where R is a **structural multiplier** (rescaling), not a feature. Including R as a feature in Task A's penalized logistic would mean fitting β on R, which conflates regime conditioning (L5-G's domain via Bayesian shrinkage `K_HORIZON / (K_HORIZON + n_eff)`) with composite-weight refit. Cleaner separation: M2 fits bucket weights regime-agnostically; downstream sub-phases apply regime conditioning.

### §4.3 ISM + LEI explicit deferral

The CRPS side already faces 4-active-of-6 truncation (per S-10 Phase 0 finding). M2's CDRS 4-bucket scheme symmetrizes the cross-score column count. ISM + LEI loaders deferred to **backlog L5b-2** per V's prompt PHASE 3 STEP 3.3.

### §4.4 Implementation notes for Phase 2

If M2 confirmed by Strategic:
- New function: `build_component_panel(panel_index: pd.DatetimeIndex, *, score_type: str) -> pd.DataFrame`
  - `score_type="CRPS"` → 4 columns (yield_curve_nyfed, sahm_rule, nfci_kcfsi, hy_oas_regime)
  - `score_type="CDRS"` → 4 buckets (bucket_valuation, bucket_sentiment, bucket_credit_liquidity, bucket_vol_breadth_technical)
- Module location: `macro_pipeline/analysis/component_panel.py` (NEW) — keeps L5-related analysis modules grouped
- Internal: for each date in `panel_index`, build `PitDataContext(as_of=date)`, call existing `cdrs_vulnerability::compute_vulnerability` + `cdrs_trigger::compute_trigger`, aggregate per M2 schema
- PIT discipline preserved via existing `PitDataContext` machinery (L3.5b certified)

### §4.5 Test plan (4-6 tests; ≥50% NEG)

| # | Test | Type | Notes |
|---|---|---|---|
| T1 | `test_build_component_panel_crps_4_active_columns` | POS | CRPS schema: 4 active components from `LAYER3_ACTIVE_COMPONENTS` |
| T2 | `test_build_component_panel_cdrs_4_buckets_M2_mapping` | POS | CDRS 4-bucket M2 schema (after Strategic confirms) |
| T3 | `test_build_component_panel_rejects_invalid_score_type` | NEG | `score_type="UNKNOWN"` raises ValueError |
| T4 | `test_build_component_panel_rejects_non_monthly_index` | NEG | Non-monotonic / gap-y index raises (mirrors L5-A test #12) |
| T5 | `test_build_component_panel_pit_safety_no_look_ahead` | NEG | At `as_of = month_T`, no values from `month_T+1` or later appear |
| T6 | `test_build_component_panel_excludes_ism_lei` | NEG | ISM + LEI column names absent (backlog L5b-2 reference) |

NEG count: T3, T4, T5, T6 = 4 of 6 = 67% (exceeds 50% floor).

---

## §5 — Strategic confirmation requested

**Question 1**: Confirm M2 (4-bucket aggregation) for CDRS portion of `component_panel`.
**Question 2**: Confirm bucket mapping in §3.2 (or propose adjustment):
- `valuation = mean(V1, V4, V5)`
- `sentiment = mean(V2, V3)`
- `credit_liquidity = mean(T1, T3)`
- `vol_breadth_technical = mean(T2, T4, T5)`
**Question 3**: Confirm R excluded from component_panel (downstream-only).
**Question 4**: Confirm Phase 2 module location `macro_pipeline/analysis/component_panel.py` (or specify alternative).
**Question 5**: Confirm test plan in §4.5 (or adjust count / NEG ratio).

If Strategic confirms all 5 questions as proposed → Phase 2 proceeds immediately. If any question changes → Track A revises this doc and Phase 2 code accordingly.

---

## v2 — Q2 bucket finalization (post-Strategic pushback)

**Trigger**: Strategic confirmed Q1/Q3/Q4/Q5 but pushed back on Q2 `credit_liquidity = mean(T1, T3)`. Concern: T1 (continuous mean-reverting credit shock) + T3 (near-binary persistent positioning) are heterogeneous — averaging produces a bucket dominated by T1 variance in stress and T3 sign drag in calm, collapsing bucket interpretability.

### v2 §A — Spec re-read findings (per Phase 1.6 STEP 1.6.1)

Grep audits against `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb`:

| Audit query | Result |
|---|---|
| `gamma` (case-insensitive) | **0 matches** (spec never mentions dealer gamma OR T3_gamma_sign by name) |
| `T3` (literal) | **0 matches** |
| `dealer` | **0 matches** |
| `liquidity` | **0 matches** outside the compound phrase `credit/liquidity` |
| `bucket` + `V[1-5]_` / `T[1-5]_` | Generic `4 buckets × subcomponents` at lines 716, 894 (no sub-component → bucket map) |
| `credit/liquidity` framing | Only line 587 generic ("CDRS: 4 buckets (valuation + sentiment + credit/liquidity + vol/breadth/technical)") |
| `vol/breadth/technical` framing | Only line 587 generic |
| `CDRS.*component` | Lines 587, 716, 894, 856, 2145, 2437 — all reference "4 buckets × subcomponents" hierarchically; **none specify the sub-component → bucket map** |

**Spec verdict on T3 placement: SILENT.** No explicit assignment to any bucket. No worked example forcing a placement.

### v2 §B — Decision tree application

Per prompt PHASE 1.6 STEP 1.6.2:
- IF spec EXPLICITLY assigns T3 → bucket: Option C. **Not triggered.**
- ELSE IF spec EXPLICITLY assigns T3 elsewhere: adopt that. **Not triggered.**
- ELSE IF spec is silent: **Option B** (T3 → vol_breadth_technical_gamma). **TRIGGERED.**
- Option A (equal-count reweighting): only if spec mandates 4-equal-count. **Not triggered** (lines 716/894 explicitly allow asymmetric "4 buckets × subcomponents").

**Decision: ADOPT OPTION B.** Track A reasoning aligns with Strategic semantic-coherence preference: T3 (dealer gamma sign) is a positioning / vol-regime signal, not a credit-spread signal. Pairing it with T1 (HY OAS shock) bundles incompatible signal types. Moving T3 to the vol/breadth/technical bucket pairs it with T2 (VIX) + T4 (breadth) + T5 (MOVE) which all share volatility / market-internals semantics.

### v2 §C — Final bucket mapping (post-Option-B; supersedes §3.2)

CDRS `component_panel` schema (4 columns):

```
Index: time (monthly DatetimeIndex matching L5-A panel_index)
Columns:
  bucket_valuation                   = mean(V1_cape_pctile, V4_ey_real_gap_z, V5_ey_deviation)
  bucket_sentiment                   = mean(V2_margin_z, V3_concentration_proxy)
  bucket_credit                      = T1_hy_oas_30d_roc                                          # single-signal bucket
  bucket_vol_breadth_technical_gamma = mean(T2_vix_12m_pctile, T3_gamma_sign, T4_breadth_thrust, T5_move_z)
```

Sub-component → bucket sizes: 3 / 2 / 1 / 4 = 10 total V+T signals (5 V + 5 T). Asymmetric counts (1-4 range) accepted per Phase 1.6 guidance ("asymmetric counts are acceptable; semantic coherence wins").

R EXCLUDED (unchanged from §3 / §4.2; Q3 strongly confirmed by Strategic).

### v2 §D — Test plan revision (1 new test per Strategic's Phase 2 requirement)

T6 from §4.5 replaced with **T6_bucket_composition** (contract test against this v2 design doc):

| # | Test | Type | Notes |
|---|---|---|---|
| T1 | `test_build_component_panel_crps_4_active_columns` | POS | CRPS schema: 4 active components |
| T2 | `test_build_component_panel_cdrs_4_buckets_M2_option_b_mapping` | POS | CDRS 4-bucket per v2 §C schema |
| T3 | `test_build_component_panel_rejects_invalid_score_type` | NEG | `score_type="UNKNOWN"` raises ValueError |
| T4 | `test_build_component_panel_rejects_non_monthly_index` | NEG | Non-monotonic / gap-y index raises |
| T5 | `test_build_component_panel_pit_safety_no_look_ahead` | NEG | `as_of = month_T` excludes data from `T+1` |
| **T6** | `test_build_component_panel_bucket_composition_matches_design_doc_v2` | NEG (contract test) | Asserts CDRS columns match v2 §C verbatim: 4 named columns + correct sub-component aggregation |

NEG count: T3, T4, T5, T6 = 4 of 6 = 67% (exceeds 50% floor per §2.7). ISM/LEI exclusion test merged into T1 docstring assertions (no longer separate test).

### v2 §E — Phase 2 implementation impact

Module `macro_pipeline/analysis/component_panel.py` (NEW) implements `build_component_panel(panel_index, *, score_type)`:
- `score_type="CRPS"` → 4 columns: yield_curve_nyfed, sahm_rule, nfci_kcfsi, hy_oas_regime
- `score_type="CDRS"` → 4 columns per v2 §C
- ISM + LEI explicitly absent; docstring cites backlog L5b-2

Internal: iterate `panel_index`; per date build `PitDataContext(as_of=date)`; call `cdrs_vulnerability::compute_vulnerability` + `cdrs_trigger::compute_trigger` (existing PIT-safe loaders); extract per-sub-component normalized values from `components_normalized` dict; aggregate per v2 §C bucket mapping.

---

**END — L3_COMPONENT_PANEL_D2_DESIGN.md v2 (Option B finalized; T6 contract test added)**
