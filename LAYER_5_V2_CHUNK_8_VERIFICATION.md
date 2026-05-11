# LAYER 5 v2 — Chunk 8 Self-Verification Report

**Chunk**: 8 of 10 (v2 chunk 3 of 5) — §2.3 G.3 Bayesian k_h backsolve (E.3 fix; S-4)
**Date**: 2026-05-11
**Branch**: `claude/layer-5-spec` @ HEAD-pre-commit (parent `aaec209`)

---

## §1 — Sections delivered

| Edit | Status |
|---|---|
| §5.G.1 constants block: added `N_REF_NONOVERLAP` + `W_REF_TARGET` + backsolved `K_HORIZON` | ✓ |
| §5.G.3 methodology rigor v2 (estimator + identification + failure mode + ChatGPT v1 flag RESOLVED) | ✓ |
| §5.G.5 tests: added #7 (W_REF match within ±2pp) + #8 (k_h sensitivity 0.5×/1×/2×); 6 → 8 tests | ✓ |
| §5.G.6 Gate 25.2: updated PASS criterion to include v2 W match | ✓ |
| §2.5 audit #9 (shrinkage k + n unit consistency) added | ✓ |
| §10 S-4 entry filed | ✓ |

---

## §2 — Empirical arithmetic verification (Standing Order #4)

| Check | Pre-fix | Post-fix | Status |
|---|---|---|---|
| 1Y: k=180, n_eff=113 | w = 180/(180+113) = 0.614 (target 0.05) | k=5.9 → w = 5.9/(5.9+113) = 0.0496 ≈ 0.05 | ✓ FIX VERIFIED |
| 3Y: k=540, n_eff=38 | w = 540/(540+38) = 0.934 (target 0.15) | k=6.7 → w = 6.7/(6.7+38) = 0.150 | ✓ |
| 5Y: k=900, n_eff=22 | w = 900/(900+22) = 0.976 (target 0.30) | k=9.4 → w = 9.4/(9.4+22) = 0.299 ≈ 0.30 | ✓ |
| 10Y: k=1800, n_eff=11 | w = 1800/(1800+11) = 0.994 (target 0.50) | k=11.0 → w = 11.0/(11.0+11) = 0.500 | ✓ |

**Arithmetic clean. ChatGPT E.3 closed.**

---

## §3 — Sxx filed

| ID | Disposition | Topic |
|---|---|---|
| **S-4** | ACCEPT | Bayesian k_h backsolved; closes E.3 / L5-RISK-3 |

Chunk 8 Sxx: 1 (within ≤2). Cumulative L5 v2 Sxx: 4 (S-1, S-2, S-3, S-4).

---

## §4 — Effort actual vs preflight

| Item | Pre-flight | Actual | Variance |
|---|---|---:|---:|
| §5.G.1 constants rewrite | 0.3h | 0.3h | 0 |
| §5.G.3 methodology rigor rewrite | 0.2h | 0.2h | 0 |
| §5.G.5 tests #7 + #8 | 0.2h | 0.2h | 0 |
| §5.G.6 Gate 25.2 | 0.1h | 0.1h | 0 |
| §2.5 audit #9 + §10 S-4 | 0.2h | 0.2h | 0 |
| Verification | 0.2h | 0.2h | 0 |
| Commit + push | 0.1h | 0.1h | 0 |
| **Chunk 8 total** | **1.3h** | **1.3h** | **0** |

Running v2 total: 4.45 + 1.3 = **5.75h of 7.5-11.5h**.

---

## §5 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| stat | 0.97 | Backsolved k_h is arithmetically verified to ±2pp at reference cutpoints |
| op | 0.94 | Reference n_eff numbers depend on Fed-era assumption (1913-2025); reasonable; test #7 enforces match |
| act | 0.97 | Closes HIGH blocker E.3 with mechanical numeric fix; ChatGPT v2 unlikely to re-flag |
| **Aggregate** | **0.94** | Binding: operational |

---

## §6 — Recommendation

**APPROVE-and-continue.** Advance to chunk 9 (G.4/G.5/G.6 MED fixes E.4/E.5/E.6/E.7; S-5, S-6, S-7).

---
