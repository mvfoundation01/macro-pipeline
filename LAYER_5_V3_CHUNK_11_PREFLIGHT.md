# LAYER 5 v3 — Chunk 11 Pre-flight Audit (SINGLE-CHUNK SURGICAL PATCH)

**Chunk**: 11 of 11 (v3 single-chunk patch per ChatGPT v2 §E)
**Date**: 2026-05-11
**Branch**: `claude/layer-5-spec` @ `76ca810` (= tag `layer5-spec-v2`)
**Standing approval**: inherited from v2 cycle; surgical scope (no methodology expansion)

---

## §1 — Sections to patch (6 items per ChatGPT v2 §E + 1 Strategic consistency scrub)

| # | Section | Patch type | Sxx |
|---|---|---|---|
| §2.1 | §5.RM-6.1.1 + §5.RM-6.1.2 + §5.RM-6.5 + §5.RM-6.6 + §3.2 | HIGH rewrite — `build_event_labels()` dispatch; 25 calibrators (1+20+4); rename `fit_isotonic_per_horizon` → `fit_isotonic_calibrators` | S-8 |
| §2.2 | §5.B.1.0 + §5.B.1.1 + §3.1 + §5.B test count | MED rewrite — Task B split B1 + B2; +3 tests | S-9 |
| §2.3 | §1.3 Row 8 + grep-scrub stale `horizon × 15` | cleanup | none |
| §2.4 | §5.D.1.1 docstring + §5.D.2 + cell_label taxonomy → 3-state | cleanup | none |
| §2.5 | §5.RM-6.7 Gate 21 proof contract item 3 | cleanup | none |
| §2.6 | §3.3 cross-reference grep audit | cleanup | none |

---

## §2 — Empirical grep audit (Standing Order #4)

### §2.1 Stale `k = horizon × 15` literals to scrub (6 hits)

| Line | Section | Action |
|---|---|---|
| 85 | §1.3 Decision Lock Row 8 | REPLACE per §2.3 |
| 322 | §4 sub-phase decomposition L5-G | REPLACE |
| 1777 | §5.G.1 v1 comment | PRESERVE (explains v1 error in S-4 context) |
| 2091 | §8.1 ChatGPT MUST verify | REPLACE — update to v2 backsolved form |
| 2103 | §8.2 ChatGPT MAY flag | REPLACE — note "RESOLVED in v2" |
| 2168 | §10 S-4 rationale | PRESERVE (historical) |

### §2.2 Stale `n_obs < 5` / `nan` literals to scrub (3 hits)

| Line | Section | Action |
|---|---|---|
| 1424 | §5.D.1.1 docstring | REPLACE per §2.4 |
| 1456 | §5.D.2 pre-flight | REPLACE |
| 2170 | §10 S-5 rationale | PRESERVE (historical; documents fix) |

### §2.3 `forward_return_binary` / `fit_isotonic_per_horizon` references (7 hits)

| Line | Section | Action |
|---|---|---|
| 1096 | §5.RM-6.1.1 API signature | REPLACE per §2.1 (rename + dispatch) |
| 1127 | §5.RM-6.1.2 4-calibrator wording | REPLACE per §2.1 (25 calibrators) |
| 1129 | §5.RM-6.1.2 binary description | REPLACE per §2.1 |
| 1156 | §5.RM-6.2 pre-flight item 5 | UPDATE API name |
| 1187 | §5.RM-6.5 test #1 | UPDATE test name + assertion |
| 1196 | §5.RM-6.5 test #10 | UPDATE test name |
| 1207 | §5.RM-6.6 Gate 21 | REPLACE per §2.1 (25 calibrators) |
| 1220 | §5.RM-6.7 proof contract #1 | UPDATE API name |

### §2.4 §3.3 cross-references (24 matches)

Strategic consistency scrub per §2.6: verify each match cites §3.3's 3 score paths correctly.

---

## §3 — Anticipated Sxx

- **S-8**: §5.RM-6.1.2 API rewrite + 25 calibrators (1 CRPS + 20 CDRS + 4 RETURN_POSITIVE) per §3.3 schema; closes ChatGPT v2 E.1
- **S-9**: L5-B Task B split into B1 (Ridge return forecast; RETURN_POSITIVE NOT input) + B2 (positive_return_probability calibration); closes ChatGPT v2 D.2

Sxx budget chunk 11: 2 (at hard limit; expected).

---

## §4 — Effort estimate

| Item | Estimate |
|---|---|
| §2.1 patch (largest; rewrite RM-6.1.2 + API + tests + Gate 21) | 0.8h |
| §2.2 patch (Task B split + 3 new tests + dependency graph update) | 0.6h |
| §2.3 patch (Row 8 + grep-scrub × 4 stale-literal sites) | 0.3h |
| §2.4 patch (nan scrub + cell_label taxonomy consolidation) | 0.3h |
| §2.5 patch (Gate 21 test count update) | 0.1h |
| §2.6 patch (§3.3 grep audit + consistency fixes) | 0.2h |
| LAYER_5_AUTHORING_SUMMARY.md → v3 | 0.3h |
| §10 S-8 + S-9 entries | 0.2h |
| Verification | 0.3h |
| Commit + force-tag + push | 0.1h |
| Final readiness report | 0.2h |
| **Chunk 11 total** | **3.4h** (within 2-4h target) |

Within ≤5h hard PAUSE limit.

---

## §5 — Cross-reference plan

| New / changed anchor | Resolves to |
|---|---|
| §5.RM-6.1.2 v3 `build_event_labels()` | §3.3 schema (chunk 6 v2) |
| §5.B.1.0 v3 Task A + Task B1 + Task B2 | §3.1 dependency graph (chunk 1 + v3 update) + §5.B.1.1 |
| §5.B.5 v3 +3 tests | Task B1 + Task B2 contract |
| §5.RM-6.5 v3 hardened test #11 | §3.3 + §5.RM-6.1.2 |
| §5.RM-6.6 Gate 21 v3 | 25 calibrators total |
| §10 S-8 + S-9 | respective ChatGPT v2 findings + Risk Register |

No dangling refs anticipated; surgical edits to existing sections.

---

## §6 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| stat | 0.95 | ChatGPT v2 findings are concrete + reviewer-verified; v3 patches are mechanical |
| op | 0.93 | Largest patch (§5.RM-6 rewrite) requires careful preservation of v1+v2 chunks; grep audit reveals exact edit sites |
| act | 0.97 | v3 closes 6/6 ChatGPT v2 findings; expected post-v3 verdict FREEZE-AS-IS or FREEZE-WITH-NOTES |
| **Aggregate (MIN)** | **0.93** | Binding: operational (cross-edit coordination across 6 sections) |

≥0.85 → standing approval applies; proceed.

---

## §7 — Recommendation

**PROCEED to chunk 11 single-chunk patch.** 6 patches in execution order §2.1 → §2.2 → §2.3 → §2.4 → §2.5 → §2.6; expected 2 Sxx (S-8, S-9); ≤3.4h effort target.

---
