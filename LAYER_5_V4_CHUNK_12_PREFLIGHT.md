# LAYER 5 v4 — Chunk 12 Pre-flight Audit (SINGLE-CHUNK CROSS-REFERENCE SCRUB)

**Chunk**: 12 of 12 (v4 single-chunk surgical scrub per ChatGPT v3 §E)
**Date**: 2026-05-11
**Branch**: `claude/layer-5-spec` @ `362b71b` (= tag `layer5-spec-v3`)
**Standing approval**: inherited from v3 cycle; pure cross-reference scrub scope

---

## §1 — Sections to patch

| # | Section | Patch type | Sxx |
|---|---|---|---|
| §2.1 | §6.2 Gate 19 + §6.4 Gate 21 + §6.6 Gate 23 + §6.8 Gate 25 | HIGH sync (consolidated mirrors stale vs §5.X.6 v3) | none |
| §2.2 | §5.B.6 + §5.B.7 (Task B1/B2 propagate) | MED sync | none |
| §2.3 | §5.D.3 Consistency row + §5.D.5 test #11 | MED scrub | none |
| §2.4 | §5.B.5/RM-6.5/D.5/G.5 mirror anchor summary lines | defensive | none |
| §2.5 | §12 AP-AUTH-39 new anti-pattern | doc only | none |

---

## §2 — Empirical grep audit (pre-fix counts; Standing Order #4)

| Stale literal | Pre-fix hits | Action |
|---|---|---|
| `fit_return_forecast` (no `_task_b1` suffix) in §6.2 | 2 (lines 862, 882) | RENAME to `fit_return_forecast_task_b1` + `calibrate_return_forecast_task_b2` per §2.1 + §2.2 |
| `4 per-horizon calibrators; 10 tests` in §6.4 (line 2106) | 1 | REPLACE per §2.1 (25 calibrators, 14 tests) |
| `K_HORIZON == {1Y: 180, 3Y: 540, 5Y: 900, 10Y: 1800}` in §6.8 (line 2129) | 1 | REPLACE per §2.1 (v3 backsolved {5.9, 6.7, 9.4, 11.0}) |
| `hierarchical_pooling_applied=True` in §5.D.5 test #11 (line 1580) | 1 | REPLACE per §2.3 (cell_label = "pooled") |
| `cells <5 flagged` in §5.D.7 (line 1594) | 1 | UPDATE per §2.3 |
| `n_obs ≥ 5 (else nan)` in §5.D.3 Consistency row | 0 (none active; only S-5 historical) | N/A — verify |

**Total active stale references: 6** (across 5 lines). v4 scrubs all.

---

## §3 — Anticipated Sxx

**0 expected.** All edits are cross-reference scrubs + 1 new anti-pattern. Per v4 prompt §3.2 hard limit "Sxx filing required → PAUSE", strict 0-Sxx target.

---

## §4 — Effort estimate

| Item | Estimate |
|---|---|
| §2.1 §6.2/§6.4/§6.6/§6.8 sync (4 gates) | 0.8h |
| §2.2 §5.B.6/§5.B.7 Task B1/B2 propagate | 0.5h |
| §2.3 §5.D.3 + §5.D.5 test #11 scrub | 0.2h |
| §2.4 mirror anchor summary lines (4 sections) | 0.3h |
| §2.5 §12 AP-AUTH-39 | 0.05h |
| LAYER_5_AUTHORING_SUMMARY.md → v4 | 0.2h |
| Verification + mirror integrity table | 0.3h |
| Commit + force-tag + push | 0.1h |
| Final readiness report | 0.15h |
| **Chunk 12 total** | **2.6h** (within 1.5-3h target) |

Within ≤5h hard PAUSE limit. Within ≤3h calendar target.

---

## §5 — Mirror integrity targets (to verify post-fix)

| Sub-phase | Test count | §5.X.5 anchor | §5.X.6 PASS criterion N | §5.X.7 proof item | §6.N consolidated |
|---|---|---|---|---|---|
| L5-B | 28 | §5.B.5 (= 12 A + 13 B1 + 3 B2) | §5.B.6 item 12 | §5.B.7 item 2 + 14 | §6.2 PASS criterion 12 |
| L5-RM-6 | 14 | §5.RM-6.5 (= 13 v2 + 1 v3 hard gate) | §5.RM-6.6 item 7 | §5.RM-6.7 item 3 | §6.4 PASS criterion 8 |
| L5-D | 12 | §5.D.5 (= 8 v2 + 4 v3 taxonomy) | §5.D.6 item 8 | §5.D.7 item 2 | §6.6 PASS criterion 8 |
| L5-G | 8 | §5.G.5 (= 5 v2 + 3 v3 backsolve tests) | §5.G.6 25.2 sub-criterion | §5.G.7 item 4 | §6.8 25.2 sub-criterion |

Each row: §5.X.5 == §5.X.6 == §5.X.7 == §6.N → 4-anchor alignment.

---

## §6 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| stat | 0.97 | Pure cross-reference scrub; ChatGPT v3 findings concrete; mechanical execution |
| op | 0.95 | Grep audit pre-identified all 6 stale-reference sites; 4-anchor mirror integrity check eliminates miss-recurrence |
| act | 0.98 | v4 closes 3/3 ChatGPT v3 findings; expected ChatGPT v4 verdict FREEZE-AS-IS |
| **Aggregate (MIN)** | **0.95** | Binding: operational (mirror integrity discipline) |

≥0.85 → standing approval continues.

---

## §7 — Recommendation

PROCEED to chunk 12 single-chunk surgical scrub. 0 Sxx anticipated; ≤2.6h effort.

---
