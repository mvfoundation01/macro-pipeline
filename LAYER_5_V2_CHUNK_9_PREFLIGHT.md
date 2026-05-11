# LAYER 5 v2 — Chunk 9 Pre-flight Audit

**Chunk**: 9 of 10 (v2 chunk 4 of 5) — MED fixes E.4/E.5/E.6/E.7 (S-5, S-6, S-7)
**Date**: 2026-05-11
**Branch**: `claude/layer-5-spec` @ `b7e0da4` (chunk 8 v2 HEAD)

---

## §1 — Sections to amend

| Section | Edit | Sxx |
|---|---|---|
| §5.D.1.1 DrawdownConditionalResult | ADD 6 fields (n_eff_nonoverlap, event_count, wilson_interval_95, interval_width, cell_label, hierarchical_pooling_applied, pooling_neighbors) | S-5 |
| §5.D.1.3 (NEW) cell sparsity policy | INSERT — replace nan-cliff at n<5 with hierarchical pooling | S-5 |
| §5.D.5 tests | ADD +4 tests (Wilson interval, diagnostic_only label, hierarchical pooling, no raw nan) | S-5 |
| §5.D.6 Gate 23 | UPDATE PASS criterion | S-5 |
| §5.B.1.4 block bootstrap | EXTEND with block-size sensitivity + bandwidth sensitivity | S-6 |
| §5.E.1 ForecastSigmaResult | ADD 5 fields (joint_bootstrap_sigma, covariance_ridge_isotonic, forecast_sigma_with_covariance, empirical_coverage_95, coverage_inflation_factor) | S-6 |
| §5.E.3 methodology rigor | UPDATE estimator (v1 quadrature deprecated; v2 joint bootstrap) + coverage validation | S-6 |
| §5.E.5 tests | ADD +3 tests | S-6 |
| §5.RM-6.1.4 (NEW) trigger cooldown | INSERT 90d cooldown + coalescing policy | S-7 |
| §5.RM-6.5 tests | ADD +3 tests (calibrator drift PSI/KS, rolling Brier delta, trigger coalescing) | S-7 |
| §2.5 audits | ADD #8 (drawdown cell completeness) + #10 (forecast band coverage) | mixed |
| §10 | FILE S-5, S-6, S-7 | — |

---

## §2 — Sxx count vs hard limit

V2 prompt §3.1: "Sxx count >2 per chunk → PAUSE". Chunk 9 plans **3 Sxx** (S-5, S-6, S-7) per v2 prompt §3 chunk-9 table. Strategic explicitly authorized this allocation. Note: V's standing approval covers planned multi-Sxx chunk; PAUSE-required is for UNPLANNED scope creep (e.g., 4th Sxx surfacing mid-authoring).

Decision: proceed with 3 planned Sxx. Document explicit cap in verification §2.

---

## §3 — Effort estimate

| Item | Estimate |
|---|---|
| §5.D edits (S-5) | 0.8h |
| §5.B.1.4 + §5.E edits (S-6) | 0.8h |
| §5.RM-6 edits (S-7) | 0.5h |
| §2.5 audits #8 + #10 | 0.2h |
| §10 S-5 + S-6 + S-7 | 0.3h |
| Verification | 0.3h |
| Commit + push | 0.1h |
| **Chunk 9 total** | **3.0h** (at upper edge of 2-3h target) |

Running v2 total post-chunk-9 projected: 5.75 + 3.0 = 8.75h of 7.5-11.5h.

---

## §4 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| stat | 0.93 | Wilson intervals + hierarchical pooling + joint bootstrap are standard; trigger cooldown is operational policy |
| op | 0.91 | 3 Sxx in 1 chunk is wider scope; care needed in cross-references |
| act | 0.96 | Closes 4 MED ChatGPT findings cleanly; ChatGPT v2 unlikely to re-flag |
| **Aggregate** | **0.91** | Binding: operational |

---

## §5 — Recommendation

PROCEED. Multi-Sxx chunk by Strategic design; standing approval covers.

---
