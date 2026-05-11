# LAYER 5 v2 — Chunk 8 Pre-flight Audit

**Chunk**: 8 of 10 (v2 chunk 3 of 5) — §2.3 G.3 Bayesian k_h backsolve (E.3 fix); S-4
**Date**: 2026-05-11
**Branch**: `claude/layer-5-spec` @ `aaec209` (chunk 7 v2 HEAD)

---

## §1 — Sections to amend

| Edit target | Action |
|---|---|
| §5.G.1 constants block | REPLACE — k_h backsolved from W_REF_TARGET × N_REF_NONOVERLAP |
| §5.G.3 methodology rigor | UPDATE — acknowledge unit reconciliation; v1 ERROR documented |
| §5.G.5 tests | ADD test #7 (W_REF_TARGET match within ±2pp) + #8 (k_horizon sensitivity 0.5×/1×/2×) |
| §5.G.6 Gate 25.2 | UPDATE PASS criterion |
| §2.5 audits | ADD #9 (shrinkage k + n unit consistency) |
| §10 S-4 entry | FILE |

---

## §2 — Anticipated Sxx

- **S-4**: Bayesian k_h backsolved; closes E.3 / L5-RISK-3. ACCEPT.

Sxx budget chunk 8: 1.

---

## §3 — Empirical verification (Standing Order #4)

ChatGPT E.3 arithmetic verified at Strategic level:
- v1 k = horizon_months × 15 → k = 180/540/900/1800
- n_eff_nonoverlap at Fed-era (1913-2025) ≈ 113/38/22/11 per horizon
- v1 w = k/(k+n) = 180/(180+113) / 540/(540+38) / 900/(900+22) / 1800/(1800+11) = 0.614 / 0.934 / 0.976 / 0.994 — NOT 5/15/30/50% stated
- v2 fix: backsolve k_h from W_REF_TARGET × N_REF_NONOVERLAP:
  - 1Y: k = 0.05/0.95 × 113 = 5.95
  - 3Y: k = 0.15/0.85 × 38 = 6.71
  - 5Y: k = 0.30/0.70 × 22 = 9.43
  - 10Y: k = 0.50/0.50 × 11 = 11.00

Arithmetic clean. Spec uses rounded values 5.9 / 6.7 / 9.4 / 11.0 per v2 prompt §2.3 item 1.

---

## §4 — Effort estimate

| Item | Estimate |
|---|---|
| §5.G.1 constants rewrite | 0.3h |
| §5.G.3 methodology rigor rewrite | 0.2h |
| §5.G.5 tests #7 + #8 | 0.2h |
| §5.G.6 Gate 25.2 update | 0.1h |
| §2.5 audit #9 | 0.1h |
| §10 S-4 | 0.1h |
| Verification | 0.2h |
| Commit + push | 0.1h |
| **Chunk 8 total** | **1.3h** (within 1-1.5h target) |

---

## §5 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| stat | 0.96 | Backsolved k_h is arithmetically verified; clean closure of E.3 |
| op | 0.93 | Reference n_eff numbers depend on Fed-era data span (1913-2025); reasonable assumption |
| act | 0.97 | Closes HIGH blocker E.3 with mechanical fix |
| **Aggregate** | **0.93** | Binding: operational |

---

## §6 — Recommendation

PROCEED.

---
