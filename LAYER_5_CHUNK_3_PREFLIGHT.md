# LAYER 5 — Chunk 3 Pre-flight Audit

**Chunk**: 3 of 5 (§5.RM-4 raw/calibrated split + §5.RM-6 isotonic + §5.C Brier/reliability; Q4/Q5 lock)
**Date**: 2026-05-10
**Branch**: `claude/layer-5-spec` @ `684e2d4` (chunk 2 HEAD)
**Standing approval**: active per continuation prompt §0

---

## §1 — Sections to author

| Section | Subsections | Q-resolutions | Test target |
|---|---|---|---|
| §5.RM-4 raw_score vs calibrated_probability split | 0-7 (8 subsections; structural sub-phase) | none (no owning Q) | +8 (≥4 NEG) |
| §5.RM-6 isotonic regression calibration | 0-7 (8 subsections) | **Q4** (per-horizon scope) + **Q5** (recalibration cadence) | +10 (≥5 NEG) |
| §5.C Brier + reliability diagram | 0-7 (8 subsections) | none | +8 (≥4 NEG) |

Total chunk 3 sections: 24 subsections + S-1 reconciliation entry.

---

## §2 — Cross-chunk reconciliation: §3.2 ScoredObservation slot list (S-1 candidate)

**Chunk 1 §3.2 listed 5 NEW slots**:
1. `forecast_sigma: Optional[float] = None`
2. `drawdown_probability_distribution: Optional[dict[str, float]] = None`
3. `dms_adjustment_bps: float = 0.0`
4. `bayesian_shrinkage_weight: float = 0.0`
5. `cv_fold_id: Optional[int] = None`

**Continuation prompt §3.2 chunk 3 contract specifies 5 NEW slots**:
1. `calibrated_probability_band_lower`
2. `calibrated_probability_band_upper`
3. `drawdown_conditional_distribution`
4. `dms_adjustment_bps`
5. `bayesian_shrinkage_weight`

**Differences**:
- `forecast_sigma` (1 slot, sigma form) → `calibrated_probability_band_lower/upper` (2 slots, explicit band form)
- `cv_fold_id` (top-level slot) → dropped; relocate to `calibration_metadata` dict
- `drawdown_probability_distribution` → renamed `drawdown_conditional_distribution`

**Disposition**: file **S-1** in chunk 3 §10 documenting the cross-chunk reconciliation. Adopt continuation prompt list (more recent, more authoritative). §3.2 cross-sub-phase semantic table in `LAYER_5_BUILD_SPEC.md` will be amended in chunk 3 as part of the L5-RM-4 authoring (this is appropriate since L5-RM-4 owns the dataclass migration). Amendment scope: in-place edit of §3.2 rows; preserved as part of cumulative spec build.

**Rationale for adopting continuation prompt**:
1. Explicit band lower/upper is cleaner for downstream consumers (L5-E forecast σ derivation, L5-G shrinkage band reporting); single `forecast_sigma` requires derived computation at every consumer
2. `cv_fold_id` is transient (only meaningful during CV runs, not production scoring); `calibration_metadata` dict is the natural home per L3.5D pattern (`calibration_metadata: dict[str, Any]`)
3. `drawdown_conditional_distribution` better semantic name (explicit conditioning on regime + horizon)

**S-1 routing**: no L5/L7 backlog ref needed — pure cross-chunk reconciliation; documents disposition.

---

## §3 — Q-resolutions to lock chunk 3

### §3.1 Q4 — Isotonic calibration scope

**Locked: per-horizon separate (4 calibrators: 1Y / 3Y / 5Y / 10Y)** per Strategic continuation prompt §2.

Option matrix (to embed in §5.RM-6.4):

| Option | Approach | Reasoning |
|---|---|---|
| A | Single isotonic fit pooled across horizons | REJECT — confounds horizon-specific monotonicity; 10Y forward returns have different distribution than 1Y |
| B | Two calibrators (short: 1Y+3Y / long: 5Y+10Y) | REJECT — partial pooling masks 1Y vs 3Y differences |
| **C** | **Per-horizon separate (4 calibrators)** | **LOCKED**: respects horizon-specific distributions; cross-horizon consistency reported via diagnostics in §5.RM-6.6 |
| D | Per-(horizon × regime_state) (16 calibrators) | DEFER to L5b — sample size at long-horizon × specific-regime cells too small (regime+expansion-1Y has more obs than regime+recession-10Y) |

### §3.2 Q5 — Recalibration cadence

**Locked: quarterly + regime-triggered override** per Strategic continuation prompt §2.

Option matrix:

| Option | Cadence | Reasoning |
|---|---|---|
| A | Annual | REJECT — too slow to respond to regime shifts (e.g., 2020 COVID; 2008 GFC) |
| B | Monthly | REJECT — calibrator instability at short cadence with low event counts; storage churn |
| **C** | **Quarterly (Mar/Jun/Sep/Dec) + Sahm Rule >0.30 OR 10Y-3M curve flip trigger** | **LOCKED**: balance stability vs responsiveness; trigger thresholds empirically anchored at L5-RM-6 build-time smoke-test |
| D | Event-driven only (no calendar) | REJECT — silent drift in calm periods; quarterly anchor establishes minimum refresh |

**Regime trigger threshold (Sahm Rule)**: 0.30 default per Strategic recommendation. Smoke-test candidates {0.25, 0.30, 0.35, 0.40} to be run at L5-RM-6 build-time pre-flight; if 0.30 binds at >2× annual frequency or <0.5× annual frequency over 1985-2025 sample, file S-2 with empirical recalibration.

**Yield curve trigger**: 10Y-3M < 0 (inverted) for ≥2 consecutive months, OR transition from inverted to non-inverted (regime flip).

---

## §4 — Anticipated ambiguities

### §4.1 PAUSE-required: NONE

### §4.2 PROCEED-with-Sxx
- **S-1**: ScoredObservation slot reconciliation (per §2 above) — **will file in chunk 3 §10**
- S-2 candidate (Sahm Rule threshold empirical): smoke-test contingent at build-time L5-RM-6 pre-flight; NOT spec-authoring concern
- S-3 candidate (Brier improvement <0.02 threshold): smoke-test contingent at build-time L5-C pre-flight

Chunk 3 Sxx budget: 1 filed (S-1). Within §0 hard limit #4 (≤2 per chunk).

---

## §5 — Codebase mini-recon (5 min equivalent)

| Module / file | Needed for | Plan |
|---|---|---|
| `scoring/scored_observation.py:49` | §5.RM-4.2 AST-walk audit | Already in working memory (chunk 1 read full file) |
| `scoring/cdrs.py` `metadata_extra` usages | §5.RM-4 L5-13 absorption pattern | Brief grep (1 call) |
| sklearn `IsotonicRegression` API | §5.RM-6.1 isotonic methodology | Standard library; no recon needed (sklearn 1.x stable) |

Mini-recon executed inline during chunk 3 authoring.

---

## §6 — Effort estimate

| Item | Estimate |
|---|---|
| Codebase mini-recon (CDRS notes grep) | 0.05h |
| §5.RM-4 authoring (8 subsections; structural) | 0.7h |
| §5.RM-6 authoring (8 subsections; methodology rigor + Q4+Q5 lock + tests +10) | 1.2h |
| §5.C authoring (8 subsections; Brier + reliability) | 0.8h |
| §3.2 amendment + §10 S-1 entry | 0.2h |
| Verification report | 0.3h |
| Commit + inline status | 0.05h |
| **Chunk 3 total** | **3.3h** |

Slightly over 2-3h target band. Within §0 hard limit #7 (<5h actual). Running total post-chunk-3 projected: 5.55 + 3.3 = 8.85h of 9-14h budget.

---

## §7 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| `conviction_statistical` | 0.92 | Isotonic PAV is textbook (Robertson-Wright 1988); Brier decomposition is Murphy (1973); Q4/Q5 grounded in standard calibration literature |
| `conviction_operational` | 0.91 | sklearn IsotonicRegression API stable; existing CRPS notes migration (3.5D AM25) provides template for L5-13 CDRS absorption |
| `conviction_actionability` | 0.95 | L5-RM-4 dataclass migration + L5-RM-6 calibrator output is what L5-C/D/E/F/G all consume; the calibration triad is the central deliverable |
| **Aggregate (MIN)** | **0.91** | Binding constraint = **operational** (sklearn API specifics deferred to build-time L5-RM-6 pre-flight) |

Aggregate ≥0.85 → standing approval continues.

---

## §8 — Recommendation

PROCEED to chunk 3 authoring. 1 Sxx anticipated (S-1 reconciliation; pre-disposed ACCEPT). Standing approval continues.

---

**END — LAYER_5_CHUNK_3_PREFLIGHT.md**
