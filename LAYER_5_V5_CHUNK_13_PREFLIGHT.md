# LAYER 5 v5 — Chunk 13 Pre-flight Audit (FINAL SURGICAL SCRUB)

**Chunk**: 13 of 13 (v5 single-chunk surgical scrub per ChatGPT v4 §E)
**Date**: 2026-05-11
**Branch**: `claude/layer-5-spec` @ `5caf678` (= tag `layer5-spec-v4`)

---

## §1 — Slot-count reconciliation (per v5 prompt §2.1 critical step)

**Empirical reading of §5.RM-4.1 dataclass** (line 307):
- `positive_return_probability` IS already in the slot list ✓ (added in v2 per S-2)
- Adjacent §3.2 row + §5.B.1.0 + §5.RM-6 + §3.3 schema all reference it
- Line 301 "**6 new slots**" + line 307 enumerates the 6th slot ✓

**However, several anchors STILL say "5 new / 30 total"**:

| Line | Section | Stale text | Required fix |
|---|---|---|---|
| 323 | §4 decomp L5-RM-4 row | "5 new slots" | → 6 new slots |
| 921 | §5.RM-4.0 metadata Topic | "add 5 new slots" | → 6 |
| 933 | §5.RM-4.1 intro paragraph | "all 5 new slots are added" | → 6 |
| 1071 | §5.RM-4.6 Gate 20 PASS criterion 2 | "5 new slot names exactly match spec: ..." (5-name list) | → 6 names; add `positive_return_probability` |
| 2143 | §6.3 Gate 20 consolidated mirror | "30 slots total; 5 new slot names" | → 31 / 6 |

**Reconciliation disposition**: §5.RM-4.1 dataclass is CORRECT (6 slots present); v4 missed propagating to §4 + §5.RM-4.0 + §5.RM-4.1 intro + §5.RM-4.6 + §6.3 Gate 20 (which is the AP-AUTH-40 pattern Strategic is adding in §2.5). **No S-10 needed** — cleanup only.

---

## §2 — Sections to patch

| # | Section | Patch type |
|---|---|---|
| §2.1 | §4 decomp / §5.RM-4.0 / §5.RM-4.1 intro / §5.RM-4.6 / §6.3 Gate 20 — slot count 5→6 / 30→31 | HIGH (C.2) |
| §2.2 | §5.D.7 proof item 2 ("8 tests" → "12 tests") + item 9 cumulative ("628+8=636" → symbolic/12) | MED (C.1 L5-D) |
| §2.3 | §5.G.7 proof item 4 ("6 tests PASS" → "8 tests") + item 8 cumulative ("647+6=653" → symbolic/8) | MED (C.1 L5-G) |
| §2.4 | Global grep for stale cumulative arithmetic; replace with symbolic where appropriate | LOW/MED (C.3) |
| §2.5 | §12 AP-AUTH-40 NEW anti-pattern (Sxx-to-spec-body propagation) | defensive |

---

## §3 — Empirical grep audit (pre-fix counts)

| Stale literal | Pre-fix hits | Owner section |
|---|---:|---|
| "5 new slot" or "30 slots total" in active prose | 5 (lines 323/921/933/1071/2143) | §4 / §5.RM-4 / §6.3 |
| "6 tests PASS" (§5.G.7 item 4) | 1 (line 2000) | §5.G.7 |
| "Cumulative tests = 628 + 8 = 636" (§5.D.7 item 9) | 1 (line 1612) | §5.D.7 |
| "Cumulative tests = 647 + 6 = 653" (§5.G.7 item 8) | 1 (line 2004) | §5.G.7 |

Total active stale references: 8 sites. v5 scrubs all.

---

## §4 — Anticipated Sxx

**0 expected.** Per v5 prompt §3.2: only file S-10 if slot count reconciliation reveals fundamental ambiguity. Reconciliation completed in §1 above: no ambiguity — §5.RM-4.1 has 6 slots correctly; v4 propagation miss is documentation only.

---

## §5 — Effort estimate

| Item | Estimate |
|---|---|
| §2.1 slot count 5→6 / 30→31 (5 sites) | 0.4h |
| §2.2 §5.D.7 (2 items) | 0.15h |
| §2.3 §5.G.7 (2 items) | 0.15h |
| §2.4 global cumulative arithmetic grep + scrub | 0.15h |
| §2.5 AP-AUTH-40 | 0.05h |
| Summary v5 + verification | 0.4h |
| Commit + force-tag + push | 0.1h |
| Final readiness report | 0.1h |
| **Chunk 13 total** | **1.5h** (at upper end of 0.75-1.5h target) |

Within ≤2h hard PAUSE limit per v5 prompt §3.2.

---

## §6 — 20-point mirror integrity (v5 expanded; will verify in verification report)

| Sub-phase | §5.X.5 | §5.X.6 | §5.X.7 | §6.N | Target |
|---|---|---|---|---|---|
| L5-B | 28 ✓ | 28 ✓ | 28 ✓ (v4) | 28 ✓ (v4) | ALIGNED post-v4 |
| L5-RM-4 | n/a | "6 new" → fix v5 | "6 new" → fix v5 | "31 / 6" → fix v5 | TO ALIGN v5 |
| L5-RM-6 | 14 ✓ | 14 ✓ | 14 ✓ (v4) | 14 ✓ (v4) | ALIGNED post-v4 |
| L5-D | 12 ✓ | 12 ✓ | **8 → fix v5** | 12 ✓ (v4) | TO ALIGN v5 |
| L5-G | 8 ✓ | 8 ✓ | **6 → fix v5** | 8 ✓ (v4) | TO ALIGN v5 |

**Post-v5: 20/20 alignment expected** (was 16/20 post-v4 since RM-4 anchor count not previously tallied).

---

## §7 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| stat | 0.98 | Pure scrub; ChatGPT v4 findings concrete; reconciliation step verified pre-flight (no ambiguity) |
| op | 0.96 | Verbatim grep output per anchor required at verification per v5 prompt §3.1 step 3 |
| act | 0.98 | v5 closes 4/4 v4 findings; expected v5 verdict FREEZE-AS-IS |
| **Aggregate (MIN)** | **0.96** | Binding: operational |

≥0.90 → standing approval continues. v5 scrub commencing.

---

## §8 — Recommendation

PROCEED. 0 Sxx anticipated. ~1.5h effort. Reconciliation clean: §5.RM-4.1 dataclass has 6 slots correctly; v5 propagates the count to 5 documentation anchors.

---
