# LAYER 5 — Chunk 4 Pre-flight Audit

**Chunk**: 4 of 5 (§5.D drawdown + §5.E forecast σ + §5.F DMS + §5.G Bayesian shrinkage; Q6/Q7 lock)
**Date**: 2026-05-10
**Branch**: `claude/layer-5-spec` @ `ba89afd` (chunk 3 HEAD)
**Standing approval**: active

---

## §1 — Sections to author

| Section | Subsections | Q | Test target |
|---|---|---|---|
| §5.D L5-D drawdown conditional distributions | 0-7 | none | +8 (≥4 NEG) |
| §5.E L5-E forecast σ confidence band | 0-7 | none | +6 (≥3 NEG) |
| §5.F L5-F DMS survivorship adjustment | 0-7 | **Q6** (DMS bps horizon-conditional) | +5 (≥3 NEG) |
| §5.G L5-G Bayesian shrinkage | 0-7 | **Q7** (shrinkage weight + prior anchor) | +6 (≥3 NEG) |

Total chunk 4: 32 subsections + Q6/Q7 lock; Gate 25 composite sub-criteria 25.1 (L5-F) + 25.2 (L5-G).

---

## §2 — Q-resolutions to lock

### §2.1 Q6 — DMS survivorship bps within −100 to −200 band

**Locked: horizon-conditional** per Strategic continuation prompt §2:
- 5Y default: **−125 bps** annualized
- 10Y default: **−175 bps** annualized
- ±50 bps sensitivity reported in `RidgeFitResult.metadata` for both
- 1Y / 3Y: **0 bps** (DMS adjustment doesn't apply — short horizons don't accumulate enough survivorship bias to matter)

Anchor: Dimson-Marsh-Staunton "Triumph of the Optimists" 2002 + "Credit Suisse Global Investment Returns Yearbook" annual updates; Master Prompt v3.1 §4 Principle 6 (DMS correction mandatory for 5Y/10Y).

Option matrix (to embed in §5.F.4):

| Option | DMS bps approach | Reasoning |
|---|---|---|
| A | Constant −150 bps all horizons | REJECT — over-corrects short horizons |
| B | −150 bps for 5Y AND 10Y; 1Y/3Y zero | REJECT — under-corrects 10Y (cumulative survivorship larger) |
| **C** | **Horizon-conditional: 5Y=−125, 10Y=−175; 1Y/3Y=0; ±50 sensitivity** | **LOCKED**: 5Y less cumulative; 10Y more cumulative; sensitivity bands report robustness |
| D | Empirically-estimated per-horizon | DEFER L5b — requires global market data + survivorship correction analysis beyond L5 scope |

### §2.2 Q7 — Bayesian shrinkage weight

**Locked: horizon-dependent + sample-size-adaptive** per Strategic continuation prompt §2:
- 1Y: w = 5% (k_1Y = 12 × 15 = 180)
- 3Y: w = 15% (k_3Y = 36 × 15 = 540)
- 5Y: w = 30% (k_5Y = 60 × 15 = 900)
- 10Y: w = 50% (k_10Y = 120 × 15 = 1800)

**Form**: `w_horizon = k_horizon / (k_horizon + n_eff_nonoverlap_horizon)` where `n_eff_nonoverlap_horizon` is the count of strictly non-overlapping `horizon`-month windows in the training data per `analysis/effective_sample_size.py:31`.

**Prior anchor**: **US-specific DMS 6.5% real annualized primary** + **global/developed-market 4.5% robustness check** per Strategic continuation prompt §2.

Option matrix (to embed in §5.G.4):

| Option | Shrinkage approach | Reasoning |
|---|---|---|
| A | Constant w = 0.30 all horizons | REJECT — over-shrinks 1Y (high power); under-shrinks 10Y (low power) |
| B | k_horizon = horizon × 15; same prior all horizons (6.5%) | DEFER — adopted partially but adds robustness check |
| **C** | **Horizon-dependent + sample-size-adaptive (k/(k+n) form) + DMS 6.5% primary + 4.5% robustness** | **LOCKED**: Master Prompt v3.1 §4 Principle 6 (DMS correction); k = horizon × 15 ad-hoc but empirically anchored |
| D | Bayesian hierarchical shrinkage with cross-horizon pooling | DEFER L5b — implementation complexity |

---

## §3 — Codebase recon needs

| Need | Module | Plan |
|---|---|---|
| Bootstrap block-bootstrap helper | (may exist; check `analysis/`) | Brief grep |
| Existing prior-anchor literals | Check if `6.5%` already cited anywhere | Grep |

(Mini-recon executed inline.)

---

## §4 — Anticipated Sxx

- S-2 candidate: if Sahm Rule trigger frequency empirically diverges (deferred from chunk 3) — N/A this chunk (build-time concern)
- No new Sxx anticipated this chunk
- Chunk 4 Sxx budget: 0; within hard limit #4

---

## §5 — Risk callouts

### §5.1 Standing Order #4 audits at L5-F and L5-G

Per §2.5 of spec, L5-F requires AST-walk audit confirming `dms_adjustment_bps` applied to 5Y/10Y output paths only (NOT 1Y/3Y). L5-G requires AST-walk audit confirming `bayesian_shrinkage_weight` is horizon-dependent, NOT collapsed to constant. Both audits explicitly tested in §5.F.5 + §5.G.5.

### §5.2 Forward σ vs return σ vs analog dispersion σ

Per continuation prompt §3.3 L5-E: methodology rigor block must distinguish forecast σ (uncertainty about forecast) from return σ (historical return volatility) from analog dispersion σ (variance across analogous historical periods). Master Prompt v3.1 §4 Principle 2 triple-sigma. **Mitigation**: explicit table in §5.E.3 methodology rigor block disambiguating.

### §5.3 Drawdown CDF percentile choice

§3.2 specifies `drawdown_conditional_distribution: Optional[dict[str, float]]` keyed by drawdown threshold (e.g., {"DD≥10%": p, "DD≥20%": p, "DD≥35%": p, "DD≥50%": p, "DD≥65%": p}). 5 thresholds × 4 horizons × 4 regimes = 80 cells. Cells with low historical n flagged with `np.nan`.

---

## §6 — Effort estimate

| Item | Estimate |
|---|---|
| Mini-recon | 0.05h |
| §5.D drawdown (8 sub) | 0.7h |
| §5.E forecast σ (8 sub) | 0.7h |
| §5.F DMS (8 sub + Q6 + AST audit) | 0.6h |
| §5.G shrinkage (8 sub + Q7 + AST audit) | 0.6h |
| Verification | 0.3h |
| Commit + status | 0.05h |
| **Chunk 4 total** | **3.0h** |

Within band. Running total post-chunk-4 projected: 9.35 + 3.0 = 12.35h of 9-14h budget. Tight on 14h ceiling; chunk 5 must come in at ≤1.65h equivalent.

---

## §7 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| stat | 0.92 | DMS literature anchored (Dimson-Marsh-Staunton 2002); Bayesian k/(k+n) form classical; drawdown bootstrap standard |
| op | 0.90 | empirical DMS bps band sourcing relies on book figures (not internal data); shrinkage weights ad-hoc-but-anchored |
| act | 0.94 | L5-D/E/F/G produce final-form `ScoredObservation` data consumed by L6 reporting |
| agg | 0.90 | binding: operational (literature sourcing) |

Aggregate ≥0.85 → advance.

---

## §8 — Recommendation

PROCEED. No PAUSE-required. Standing approval active.

---

**END — LAYER_5_CHUNK_4_PREFLIGHT.md**
