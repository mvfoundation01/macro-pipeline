# LAYER 5 BUILD SPEC — Authoring Summary (v4)

**Spec file**: `LAYER_5_BUILD_SPEC.md`
**Branch**: `claude/layer-5-spec` (base: `590e4a5` = main = L3.5b merge commit)
**Authoring agent**: Claude Code under V's role-widening directive (v1: 2026-05-10; v2: 2026-05-11; v3: 2026-05-11; **v4 cross-reference scrub: 2026-05-11**)
**Status**: **v4 draft complete — closes ChatGPT 5.5 v3 review §C.1 HIGH + §C.2/§C.3 MED cross-reference scrub (consolidated §6 gate mirrors synced; Task B1/B2 propagated; §5.D residual prose cleaned); ready for V freeze + ChatGPT 5.5 v4 closure verification**
**Predecessor tags preserved**: `layer5-spec-v1` @ `d776eb4`; `layer5-spec-v2` @ `76ca810`; `layer5-spec-v3` @ `362b71b` (all historical)
**v4 tag**: `layer5-spec-v4` at chunk-12 closure SHA
**Date**: 2026-05-11

---

## §1 — Effort actuals (cumulative chunks 1-10)

| Chunk | Effort actual (h equiv) | Target | Scope |
|---|---:|---:|---|
| 1 | 2.75 | 2-3 | v1 scope + discipline + decomposition |
| 2 | 2.8 | 2-3 | v1 L5-A + L5-B (Q1/Q2/Q3) |
| 3 | 3.8 | 2-3 | v1 L5-RM-4 + L5-RM-6 + L5-C (Q4/Q5; S-1) |
| 4 | 2.7 | 2-3 | v1 L5-D + L5-E + L5-F + L5-G (Q6/Q7; Gate 25 composite) |
| 5 | 1.95 | 1-2 | v1 L5-H + gates + backlog + ChatGPT handoff + closure (Q8) |
| **v1 total** | **14.0** | **9-14** | spec v1 complete |
| 6 (v2) | 1.55 | 1.5-2 | E.1 calibration target schema (S-2) |
| 7 (v2) | 2.9 | 2-3 | E.2 L5-B Task A + Task B split (S-3) |
| 8 (v2) | 1.3 | 1-1.5 | E.3 Bayesian k_h backsolve (S-4) |
| 9 (v2) | 3.1 | 2-3 | E.4 + E.5 + E.6 + E.7 MED fixes (S-5, S-6, S-7) |
| 10 (v2) | ~1.9 | 1-2 | closure + risk register + tag v2 |
| **v2 total** | **~10.75** | **7.5-11.5** | v2 incorporation complete |
| **v1 + v2 grand total** | **~24.75** | budget 9-14 (v1) + 7.5-11.5 (v2) = 16.5-25.5 | within ceiling |
| 11 (v3) | ~3.4 | 2-4 | surgical patch: E.1 hardened + D.2 Task B split + E.3/E.4/E.6 cleanup (S-8 + S-9) |
| **v1 + v2 + v3 grand total** | **~28.15** | combined budget 18.5-29.5 | within ceiling |
| 12 (v4) | ~2.6 | 1.5-3 | cross-reference scrub: §6 consolidated gate sync + §5.B Task B1/B2 propagate + §5.D residual prose + mirror anchors + AP-AUTH-39 (0 Sxx) |
| **v1 + v2 + v3 + v4 grand total** | **~30.75** | combined budget 20-32.5 | within ceiling |

---

## §2 — v2 closures vs ChatGPT 5.5 v1 review

| Finding | Severity | Closure mechanism | Sxx |
|---|---|---|---|
| **E.1** Calibration target schema mismatch | HIGH | §3.3 NEW + §3.2 row + §5.RM-4 6 slots + §5.RM-6 wording + §5.C parametrize + audits #5/#6 | S-2 |
| **E.2** Scalar Ridge cannot refit components | HIGH | §5.B FULL rewrite: Task A (composite-weight refit penalized logistic) + Task B (return-forecast Ridge); dual API; 25 tests vs 15; Gate 19 17 sub-criteria | S-3 |
| **E.3** Bayesian k_h unit inconsistency | HIGH | §5.G.1 backsolved k_h = (w_ref / (1-w_ref)) × n_ref = {5.9, 6.7, 9.4, 11.0}; W_REF_TARGET match within ±2pp test; audit #9 | S-4 |
| **E.4** Drawdown sparse cell nan-cliff | MED | §5.D.1.1 +7 fields; §5.D.1.3 NEW cell sparsity policy with hierarchical pooling; Wilson 95% intervals per threshold; audit #8 | S-5 |
| **E.5+E.7** Block bootstrap + forecast band undercoverage | MED | §5.B.1.4 block-size + bandwidth sensitivity; §5.E.1 +5 fields (joint_bootstrap_sigma, covariance_ridge_isotonic, empirical_coverage_95, coverage_inflation_factor); audit #10 | S-6 |
| **E.6** λ + calibrator stability + trigger thrashing | MED | §5.B Task B B8/B9 (lambda_log10_sd + sign_flip_rate); §5.RM-6.1.4 90d cooldown + coalescing + max 6/year + escalation; §5.RM-6.5 tests #12-14 | S-7 |

**Closure rate: 6/6 (100%)** at spec level. Build-time will verify empirically.

---

## §3 — Q-resolutions (8/8; all v1 + v2 modifiers)

| Q | Locked option | v2 modifier (if any) |
|---|---|---|
| Q1 | C — expanding primary + rolling-20Y | — |
| Q2 | C — horizon-dependent step | — |
| Q3 | C — nested walk-forward + LOO robustness | v2 applies separately Task A + Task B per S-3 |
| Q4 | C — per-horizon separate (4 calibrators) | — |
| Q5 | C — quarterly + Sahm 0.30 + curve flip | **v2 per S-7: 90d cooldown + coalescing + max 6/year + escalation 0.30→0.35 if frequency >6/year** |
| Q6 | C — horizon-conditional DMS bps (5Y=−125 / 10Y=−175; ±50) | — |
| Q7 | C — k/(k+n) horizon-dependent + DMS 6.5% US primary + 4.5% global robustness | **v2 per S-4: k_h backsolved from W_REF_TARGET × N_REF_NONOVERLAP** |
| Q8 | C — all 4 horizons in L5 | — |

---

## §4 — Sxx register (cumulative L5)

| ID | Date | Chunk | Topic | Disposition |
|---|---|---|---|---|
| S-1 | 2026-05-10 | 3 (v1) | ScoredObservation slot list reconciliation | ACCEPT |
| S-2 | 2026-05-11 | 6 (v2) | Calibration target schema (E.1) | ACCEPT |
| S-3 | 2026-05-11 | 7 (v2) | L5-B Task A + Task B split (E.2) | ACCEPT |
| S-4 | 2026-05-11 | 8 (v2) | Bayesian k_h backsolve (E.3) | ACCEPT |
| S-5 | 2026-05-11 | 9 (v2) | Drawdown sparse cell intervals (E.4) | ACCEPT |
| S-6 | 2026-05-11 | 9 (v2) | Block bootstrap + forecast band coverage (E.5+E.7) | ACCEPT |
| S-7 | 2026-05-11 | 9 (v2) | Calibrator stability + trigger cooldown (E.6) | ACCEPT |
| **S-8** | 2026-05-11 | **11 (v3)** | **RM-6 calibration label semantics + 25-calibrator dispatch (closes E.1 partially-closed → CLOSED)** | ACCEPT |
| **S-9** | 2026-05-11 | **11 (v3)** | **L5-B Task B split into B1 + B2 (closes D.2 RETURN_POSITIVE circularity)** | ACCEPT |

**Total cumulative L5 Sxx: 9.** All ACCEPT. None require V override. Reserved S-10 through S-25 for L5 build deviations.

---

## §5 — Risk Register (NEW v2 §13)

| ID | Risk | Severity |
|---|---|---|
| L5-RISK-1 | `calibrated_probability` events mismatch | HIGH (mitigated by S-2) |
| L5-RISK-2 | Scalar Ridge cannot refit components | HIGH (mitigated by S-3) |
| L5-RISK-3 | Shrinkage unit inconsistency | HIGH (mitigated by S-4) |
| L5-RISK-4 | Drawdown 10Y cells overstate precision | MED (mitigated by S-5) |
| L5-RISK-5 | HAC/bootstrap undercoverage | MED (mitigated by S-6) |
| L5-RISK-6 | λ path instability | MED (mitigated by S-7) |
| L5-RISK-7 | Recalibration trigger thrashing | MED (mitigated by S-7) |
| L5-RISK-8 | DMS assumption stale | LOW-MED (mitigated by §1.3 Row 15 annual review) |

---

## §6 — Standing Order #4 audits (10 total; 6 NEW in v2)

| # | Owning sub-phase | Universal claim |
|---|---|---|
| 1 | L5-A | Walk-forward CV zero cross-fold contamination |
| 2 | L5-RM-6 | Isotonic PAV monotonicity preservation |
| 3 | L5-F | DMS bps 5Y/10Y exclusive application |
| 4 | L5-G | Bayesian shrinkage horizon-dependent (no constant 0.30) |
| **5 NEW v2** | L5-B Task A + Task B | Train-only z-scoring (no test contamination) |
| **6 NEW v2** | L5-RM-6 | No pre-RM-6 calibrated_probability use |
| **7 NEW v2** | L5-C | Brier improvement w/ climatology + bin counts |
| **8 NEW v2** | L5-D | Drawdown cell completeness (all 16 cells have n + event + width + label) |
| **9 NEW v2** | L5-G | Shrinkage k_h + n_eff unit consistency (reference weights numerically verified) |
| **10 NEW v2** | L5-E | Forecast band empirical coverage reported per horizon |

---

## §7 — ChatGPT 5.5 v2 paste-block pointers

V pastes the following to a NEW ChatGPT 5.5 chat for v2 methodology review:

1. `LAYER_5_BUILD_SPEC.md` v2 (the spec — ≈155 KB after chunks 1-10)
2. `HANDOFF_REVIEWER_METHODOLOGY_v2.md` (V controls)
3. **This file** (`LAYER_5_AUTHORING_SUMMARY.md` v2) — single-page summary
4. `LAYER_5_CHUNK_6_through_10_VERIFICATION.md` × 5 (chunks 6-10 v2 self-verifications)
5. ChatGPT 5.5 v1 review document (so reviewer can see what was closed)
6. Reference: `LAYER_3_5_BUILD_SPEC.md` + `LAYER_3_5b_RETROSPECTIVE.md` for predecessor context

Expected reviewer latency: 2-4 days. Expected verdict: **FREEZE-WITH-NOTES** (3 HIGH all closed; 4 MED all closed; 8 risk items registered; 6 new audits added).

---

## §8 — Spec-level v2 conviction aggregate

| Field | v1 value | v2 chunks min | v2 binding-constraint chain |
|---|---|---|---|
| `conviction_statistical` | 0.93 | min(0.95 / 0.95 / 0.97 / 0.94 / 0.95) = 0.94 | improved post-v2 |
| `conviction_operational` | 0.91 | min(0.93 / 0.91 / 0.94 / 0.91 / 0.94) = 0.91 | unchanged |
| `conviction_actionability` | 0.95 | min(0.96 / 0.96 / 0.97 / 0.96 / 0.97) = 0.96 | improved post-v2 |
| **Aggregate (MIN across v1+v2)** | 0.91 | **0.91** | binding: operational |

Aggregate 0.91 ≥ 0.90 freeze floor → **APPROVE-FOR-FREEZE v2**.

---

## §9 — V's next 2 actions

1. **Review this Authoring Summary v2 + LAYER_5_BUILD_SPEC.md v2** (~10 min)
2. **Either**:
   - **APPROVE-AS-IS** → open NEW ChatGPT 5.5 chat with paste-block per §7
   - **OVERRIDE** → request Strategic to edit spec; then re-tag (force-push)

---

## §10 — v1 vs v2 commit chain (`claude/layer-5-spec`)

| Chunk | Phase | SHA | Commit message |
|---|---|---|---|
| 1 | v1 | `82267c1` | scope + discipline + sub-phase decomposition |
| 2 | v1 | `684e2d4` | L5-A walk-forward CV + L5-B Ridge fit (Q1/Q2/Q3) |
| 3 | v1 | `ba89afd` | calibration triad RM-4/RM-6/C (Q4/Q5; 9-slot batched; L5-13 absorbed; S-1) |
| 4 | v1 | `ea6df2f` | distribution + horizon-prior tetrad D/E/F/G (Q6/Q7; Gate 25) |
| 5 | v1 | `d776eb4` | closure + gates + backlog + ChatGPT handoff + QC (Q8) — **tag `layer5-spec-v1`** |
| 6 | v2 | `b0c42d0` | calibration target schema (E.1 fix; S-2) |
| 7 | v2 | `aaec209` | L5-B Task A + Task B split (E.2 fix; S-3) |
| 8 | v2 | `b7e0da4` | Bayesian k_h backsolve (E.3 fix; S-4) |
| 9 | v2 | `effce45` | MED fixes E.4/E.5/E.6/E.7 (S-5/S-6/S-7) |
| 10 | v2 | (pending) | closure + risk register + tag layer5-spec-v2 |

Branch tip post-chunk-10: ready for V inspection / freeze v2 / paste to ChatGPT 5.5.

---

**END — LAYER_5_AUTHORING_SUMMARY.md v2**
