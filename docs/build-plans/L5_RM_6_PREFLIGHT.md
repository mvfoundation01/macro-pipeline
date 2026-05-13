# L5-RM-6 Pre-Flight Plan

**Date**: 2026-05-15
**Branch target**: `claude/layer-5-build-plan` (consolidates with prior pre-flights)
**Predecessor**: `l5-rm-4-accept` (commit `056d198`) + S-12 closure commit `a41c98b` on `claude/layer-5-build`; baseline pytest = 643
**Spec ref**: `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` §5.RM-6 (lines 1121-1354)
**Build plan ref**: `claude/layer-5-build-plan @ 32cce8b` ITEM 2 row 4
**Effort budget**: 0.75-1.25h; pause 1.9h

---

## ITEM 1 — L5-RM-4 surface consumption confirmation

### §1.1 Empirical post-RM-4 ScoredObservation surface

Grep + empirical check on `claude/layer-5-build` @ `a41c98b`:

```
$ python -c "from macro_pipeline.scoring.scored_observation import ScoredObservation; \
             print(len(ScoredObservation.__dataclass_fields__))"
29
```

**Field count: 29** (post-RM-4 per S-12 disposition Option A; spec-claimed 31 deferred to L5b-4 backlog).

### §1.2 New L5-RM-4 fields visible to RM-6 (6 of 6 present)

| Field | Present? | RM-6 use |
|---|---|---|
| `calibrated_probability_band_lower` | ✓ | L5-RM-6 populates via bootstrap-SE derivation (placeholder per §5.RM-6.1.1 line 1234) |
| `calibrated_probability_band_upper` | ✓ | Same; L5-RM-6 placeholder until L5-E |
| `drawdown_conditional_distribution` | ✓ | NOT touched by RM-6 (L5-D scope) |
| `dms_adjustment_bps` | ✓ | NOT touched by RM-6 (L5-F scope) |
| `bayesian_shrinkage_weight` | ✓ | NOT touched by RM-6 (L5-G scope) |
| `positive_return_probability` | ✓ | L5-RM-6 Task B (B2) populates via `fit_isotonic_calibrators(score_type="RETURN_POSITIVE", ...)` per §3.3 schema + S-9 |

**Pre-existing fields RM-6 consumes**:
- `raw_score: float ∈ [0, 1]` — input to isotonic calibrator
- `calibrated_probability: float | None` — RM-6 populates (sets None → float)
- `calibration_metadata: dict[str, Any] | None` — RM-6 populates with `{"method": "isotonic", "fit_window": ..., "horizon": h, "monotonicity_audit": "PASS", "cv_fold_id": int | None, "cv_schedule_type": str | None}`

**Conclusion**: 0 surface gap. All 6 new RM-4 fields present + all required pre-existing fields accessible. L5-RM-6 can consume RM-4 surface immediately.

---

## ITEM 2 — L5-RM-6 scope from spec §5.RM-6

### §2.1 Public API (per §5.RM-6.1.1; v3 amended per S-8)

| Symbol | Signature | Purpose |
|---|---|---|
| `IsotonicCalibrationResult` (frozen dataclass) | 11 fields per §5.RM-6.1.1 lines 1151-1164 | Per-calibrator fit result |
| `SAHM_RULE_TRIGGER_THRESHOLD` | `= 0.30` | Q5 Sahm trigger; empirical-tunable |
| `YIELD_CURVE_INVERSION_TRIGGER_MIN_CONSECUTIVE_MONTHS` | `= 2` | Q5 yield curve trigger |
| `fit_isotonic_calibrators(raw_scores, panel, *, fit_window, drawdown_thresholds, bootstrap_iterations, random_seed)` | `→ dict[tuple[str, str], IsotonicCalibrationResult]` | **25 calibrators per refit window** (1 CRPS + 20 CDRS + 4 RETURN_POSITIVE) |
| `build_event_labels(score_type, panel, horizon, *, drawdown_threshold)` | `→ np.ndarray` (bool) | §3.3 schema dispatcher (HARD GATE per S-8) |
| `should_recalibrate(last_refit_date, as_of, sahm_rule_series, yield_curve_series)` | `→ tuple[bool, str]` | Q5 trigger check + 90d cooldown coalescing (S-7) |
| `calibrate_raw_score(raw_score, horizon, calibrator)` | `→ tuple[float, float, float]` | (calibrated, band_lower, band_upper); bands placeholder until L5-E |

### §2.2 "25 calibrators per refit window" semantics (§5.RM-6.1.2 line 1246)

Per §3.3 calibration target schema:
- **1× CRPS** at `("CRPS", "1Y")` — only 12M horizon (NBER USREC labels)
- **20× CDRS** = 4 horizons × 5 drawdown thresholds (∈ {0.10, 0.20, 0.35, 0.50, 0.65})
- **4× RETURN_POSITIVE** = 1 per horizon (1Y/3Y/5Y/10Y)

Total = 25 calibrators per refit window (NOT v1's "4 per horizon"; v3 corrected per S-8).

### §2.3 Spec test contract (§5.RM-6.5)

**14 tests total** (per §5.RM-6.5 footer line 1321; NOT the §5.RM-6.0 metadata claim of +10 which is v1 baseline pre-S-2/S-7/S-8 additions):
- 7 NEG strict (tests 2, 7, 8, 9, 10, 11, 13)
- 7 POS (tests 1, 3, 4, 5, 6, 12, 14)
- NEG ratio: 7/14 = 50% (exactly at floor per §2.7)

**Spec-vs-metadata gap**: §5.RM-6.0 line 1130 says `Test delta | +10` but §5.RM-6.5 footer line 1321 says "Total tests = 14". Similar to S-12 magic-number pattern (AP-AUTH-52 class). Documented as DEVIATION below; NOT filing Sxx (per AP-AUTH-52 + L5b-4 backlog: spec magic-number drift is doc-residue; defer cleanup to v7). Track A will implement 14 tests per §5.RM-6.5 authoritative count.

### §2.4 Gate 21 (§5.RM-6.6)

9 PASS criteria; criteria 1+2+5+7+8 runtime-verifiable; criteria 3, 4, 6, 9 require empirical fit + bootstrap (asserted out-of-band via pytest + verification report).

### §2.5 Q-resolution map

- **Q4** (per-horizon scope): locked at C (per-horizon calibrators; v3 reframed as "per (score_type × horizon × threshold)" totalling 25)
- **Q5** (recalibration cadence): locked at C (quarterly + Sahm 0.30 + yield-curve 2-month-inversion; v2 90d cooldown + coalescing per S-7)

---

## ITEM 3 — Effort estimate

### §3.1 Build plan + spec reference + actual trend

| Reference | Effort |
|---|---:|
| Build plan v1 ITEM 2 row 4 (L5-RM-6) | 6-8h |
| Spec §5.RM-6.0 metadata | 6-8h (target 7h) |
| **Track A actual trend (sub-phase precedents)** | L5-A 3h/6-8h; L5-B Task A 3.5h/6.75h; L5-RM-4 3.5h/4.75h — averaging ~50% of upper-band |
| Track A trend-extrapolated estimate | ~4.5h actual for L5-RM-6 (vs 8h upper-band) |

### §3.2 Sub-budgets per phase (Track A estimate; Pattern: spec-mandated)

| Phase | Sub-budget | Rationale |
|---|---|---|
| Phase 0: env-prep + 643 baseline (AP-AUTH-47) | 0.25h | No-op pytest run |
| Phase 1: AP register codification (e.g., if new APs surface; likely none) | 0.1h | Lightweight |
| Phase 2.1: implement IsotonicCalibrationResult + fit_isotonic_calibrators (25-calibrator dispatch) | 1.5h | sklearn IsotonicRegression standard; dispatch logic per §3.3 |
| Phase 2.2: implement build_event_labels (3-way dispatcher; HARD GATE per S-8) | 0.75h | Per spec §5.RM-6.1.1; closes ChatGPT v2 E.1 |
| Phase 2.3: implement should_recalibrate (quarterly + Sahm + yield-curve + 90d cooldown coalescing) | 0.75h | Per §5.RM-6.1.3 + §5.RM-6.1.4 |
| Phase 2.4: implement calibrate_raw_score (clipped) | 0.25h | Mechanical |
| Phase 2.5: 14 tests | 1.5h | 7 NEG + 7 POS; PAV monotonicity audit + Sahm/yield-curve trigger logic |
| Phase 2.6: Gate 21 validator + CLI | 0.5h | Mirrors L5-A Gate 18 + L5-RM-4 Gate 20 |
| Phase 3: per-commit pytest -x + final 657-test verification (previous baseline + L5-RM-6 delta per AP-AUTH-40/42 symbolic) | 0.5h | Pytest 187s × ~2 runs |
| Phase 4: review branch + AP-AUTH-48 v2 + final report | 0.5h | Standard |
| **Total** | **~6.6h** | Within spec 6-8h band; biased toward upper-mid given 25-calibrator dispatch + cooldown logic complexity |

### §3.3 Risk-adjusted bands

- **Standard estimate** (Pattern: spec-mandated 25-calibrator dispatch): **6.6h**
- **Risk-adjusted estimate** (assume PAV monotonicity edge case or bootstrap reproducibility surprise): **8h**
- **Pause threshold** (1.5× upper-band): **~12h hard pause**; soft check at 9h

### §3.4 Trend signal

Track A's sub-phase precedents show ~50% efficiency vs spec upper-band. If L5-RM-6 follows that trend, **actual could come in ~4.5-5h** (vs 6.6h estimate above). However, RM-6 has more methodology complexity (PAV + bootstrap + trigger logic + 25-calibrator dispatch) than the prior 3 sub-phases (L5-A scaffold; L5-B Task A logistic; L5-RM-4 dataclass migration), so 6.6h estimate may be more realistic.

---

## ITEM 4 — Pre-execution risk register (≥5 risks WITH grep evidence per AP-AUTH-51)

| # | Risk | Severity | Probability | Grep evidence | Mitigation | Trigger |
|---|---|---|---|---|---|---|
| 1 | **Isotonic calibrator numerical stability** (PAV monotonicity violations on low-event-count regions) | MED | 20% | `grep -c 'IsotonicRegression\\|monotonic' macro_pipeline/` = 0 sites today (first isotonic in codebase); risk from novel implementation | sklearn `IsotonicRegression(out_of_bounds='clip', y_min=0.0, y_max=1.0)` per §5.RM-6.1.1 + test #2 grep-audit (1000-point grid sweep) | Any monotonicity violation in test #2 → diagnose; if systematic → T7 Sxx (empirical calibration surprise) |
| 2 | **Refit-window boundary conditions** (calibrators fit at quarter boundaries may have edge-of-window observations contaminating fit) | MED | 25% | `grep -c 'fit_window' macro_pipeline/` = 0 sites today (no existing implementation); risk = novel boundary semantics | Spec §5.RM-6.1.1 defines `fit_window: tuple[pd.Timestamp, pd.Timestamp]` as half-open interval [start, end); explicit truncation in `build_event_labels` to fit_window | Edge-case test in test #14 (cooldown coalescing) probes boundary; broader edge surfaces → file T7 Sxx |
| 3 | **25-calibrator parametrization complexity** (dispatch logic per (score_type, horizon, threshold)) | MED | 15% | `grep -c 'score_type\\|drawdown_threshold' macro_pipeline/` = 0 production isotonic sites; dispatch is novel | Spec §5.RM-6.1.1 `fit_isotonic_calibrators` signature explicit; `build_event_labels` is a 3-way dispatcher with HARD GATE test #11 + S-8 ValueError on schema mismatch | Test #1 asserts 25 calibrator dict; test #11 hardens dispatcher; failure → T2 Sxx |
| 4 | **L5-RM-4 surface coupling risk** (Pattern B held; new fields properly visible) | LOW | 5% | `len(ScoredObservation.__dataclass_fields__) == 29` verified empirically pre-flight ITEM 1; 6 new fields all PRESENT | Pattern B contract upheld at RM-4 ACCEPT; surface FROZEN at `l5-rm-4-accept` | Any field rename or removal would have been caught at RM-4 ACCEPT; not anticipated for RM-6 |
| 5 | **Cache-warming requirements (calibrators expensive)** | MED | 30% | `grep -c 'bootstrap_iterations\\|B=1000' macro_pipeline/` = 0 sites today; novel 25-calibrator × 1000-bootstrap will inflate test runtime | 14 tests use small synthetic fit windows + small bootstrap iter (e.g., B=50 in tests, B=1000 only in production); test runtime budget ~10s per full RM-6 test file | If test runtime > 60s for full RM-6 file → optimize bootstrap iter; not test-correctness gate |
| 6 | **Spec §5.RM-6.5 test count drift** (spec metadata says +10; body says 14) | LOW | already known (this pre-flight) | `grep -A1 'Test delta' LAYER_5_BUILD_SPEC.md \| head -20` shows §5.RM-6.0 +10 vs §5.RM-6.5 footer 14 | Use authoritative count (14 per §5.RM-6.5 body); document in verification per AP-AUTH-52 + L5b-4 lineage | No action; already disposed |
| 7 | **Sahm Rule trigger frequency unknown at threshold 0.30** (test #4 + spec §5.RM-6.2 #2 empirical smoke-test) | MED | 30% | `grep -c 'SAHMREALTIME' macro_pipeline/` = 4 hits (real series exists in cache); empirical Sahm history at 0.30 threshold not yet measured | §5.RM-6.2 #2 smoke-test: count historical triggers at 0.30; if >2× annual → spec §5.RM-6.1.4 S-2 candidate + escalate to 0.35 | Empirical Sahm frequency > 2× annual at 0.30 → file T7 Sxx; consider escalation per §5.RM-6.1.4 step 4 |

### §4.1 Severity summary (with grep-evidence column per AP-AUTH-51)

| Severity | Count | Notes |
|---|---:|---|
| HIGH | 0 | No HIGH risks identified per empirical scope |
| MEDIUM | 5 | #1, #2, #3, #5, #7 — concentrated in novel-implementation surface |
| LOW | 2 | #4 (RM-4 surface), #6 (spec doc drift; already disposed) |

Top remaining risk: **#7 Sahm Rule trigger frequency empirical surprise** (30% probability). Mitigation per §5.RM-6.2 smoke-test pre-flight + escalation path defined.

---

## ITEM 5 — Process improvements adopted (from L5-RM-4 + prior cycles)

| AP | Application to L5-RM-6 |
|---|---|
| **AP-AUTH-47** (env-setup beyond collect-only) | Phase 0 will run `pytest -x` full execution; baseline 643 must preserve |
| **AP-AUTH-48 v2** (post-push served-hash verification) | Phase 4 review-branch publication will run `curl -sL <url> \| sha256sum` per artifact; expect 2 of 3 text artifacts to drift (test_transcript + gate21_cli per L5-B Task A + L5-RM-4 precedents); amend MANIFEST accordingly. **3rd formal application expected** (confirms pattern stability) |
| **AP-AUTH-51** (risk register grep evidence) | THIS PRE-FLIGHT ITEM 4 includes Grep evidence column for all 7 risks; AP-AUTH-51 compliance demonstrated |
| **AP-AUTH-52** (spec magic-number derivation) | Tests + Gate 21 use empirical counts where possible; spec metadata vs body drift (+10 vs 14) flagged as #6 LOW risk (per L5b-4 backlog scope) |

---

## ITEM 6 — Coupled-test exposure check (per pre-flight prompt)

Grep at HEAD `a41c98b`:

```
$ grep -rln 'isotonic\|calibrator\|calibrated_probability' --include='*.py' macro_pipeline/
macro_pipeline/scoring/scored_observation.py     (dataclass field reference)
macro_pipeline/validation.py                     (Gate references; comments)

$ grep -rln 'isotonic\|calibrator\|calibrated_probability' --include='*.py' tests/
tests/test_scored_observation.py                 (already updated for RM-4)
tests/test_scored_observation_rename.py          (already updated for RM-4)
```

| Category | Count | Risk |
|---|---:|---|
| Production code references | **2 files** | All references are dataclass-field-name or Gate-comment; ZERO existing isotonic implementations to refactor |
| Test code references | **2 files** | Both already RM-4-updated; consume `calibrated_probability` as dataclass field (None pre-RM-6; will be populated post-RM-6 in production paths) |
| **Call signature patterns** | N/A | No existing isotonic to categorize; L5-RM-6 introduces FIRST isotonic in codebase |

**Conclusion**: L5-RM-6 has **near-zero backward-compat risk** (no existing isotonic to refactor); risk concentrates in **novel-implementation correctness** (PAV monotonicity, 25-calibrator dispatch, Q5 trigger logic, 90d cooldown coalescing).

This profile is fundamentally different from L5-RM-4 (dataclass migration to existing surface) — L5-RM-6 is greenfield implementation with no migration risk.

---

## ITEM 7 — Readiness verdict + conviction

### §7.1 Conviction 3-field

| Field | Value | Drivers |
|---|---|---|
| `conviction_statistical` | **0.95** | Spec §5.RM-6 is precise (Q4 + Q5 locked); sklearn `IsotonicRegression` is well-tested external library (PAV consistency per Robertson-Wright 1988); 14-test contract enumerates correctness gates including PAV monotonicity grep-audit; HARD-GATE test #11 enforces §3.3 schema at fit time |
| `conviction_operational` | **0.93** | Greenfield implementation (no migration risk); 25-calibrator dispatch is the main complexity; Q5 trigger logic + 90d cooldown adds state-machine semantics; bootstrap reproducibility (test #9) enforces determinism. Minor: Sahm trigger frequency empirical (risk #7 MED 30%); if surprises → S-2 escalation path defined |
| `conviction_actionability` | **0.95** | L5-C/D/E/F/G all consume `calibrated_probability` post-RM-6; greenfield implementation means downstream API contract is clean; L5-B Task B2 also consumes `fit_isotonic_calibrators(score_type="RETURN_POSITIVE", ...)` per S-9 — surface aligns |
| **Aggregate (MIN)** | **0.93** | **Binding: operational** (25-calibrator dispatch + state-machine trigger logic + 90d cooldown coalescing — methodology complexity dominant) |

≥0.90 hard floor: **CLEARED**.

### §7.2 Verdict

**READY-FOR-L5-RM-6**.

No conditions; all surface dependencies present (RM-4 + L5-B Task A both done); spec ambiguities documented (S-12 closure + L5-RM-6 #6 risk both per L5b-4 backlog); risk register cites grep evidence per AP-AUTH-51; effort estimate within band.

**Note**: Verdict is READY (not READY-WITH-CONDITIONS) because:
- 0 Strategic decision points needed (Q4 + Q5 already locked; no Pattern A/B/C question; spec is structural-greenfield)
- ChatGPT 5.5 post-RM-4 gate review verdict pending (parallel track) — but does NOT block RM-6 unless REVISE-L5-RM-4 returns (per prompt gating)
- Empirical Sahm/yield-curve frequencies will be measured at Phase 0/Phase 2 smoke-tests; spec defines escalation paths if outside target bands (no pre-flight blocker)

### §7.3 Strategic decisions awaited

**NONE** for greenlight. Two informational/contingent:
1. ChatGPT 5.5 post-RM-4 gate verdict (parallel; if REVISE-L5-RM-4 returns → RM-6 pause)
2. If empirical Sahm trigger frequency at 0.30 threshold falls outside target band 1-2× annual → Strategic escalates per §5.RM-6.1.4 step 4 (Sahm 0.30 → 0.35; not a pre-flight issue)

---

## §8 — Strategic decision points awaited

NONE for greenlight. Two contingencies (above §7.3).

---

**END — L5_RM_6_PREFLIGHT.md**
