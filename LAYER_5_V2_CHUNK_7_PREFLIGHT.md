# LAYER 5 v2 — Chunk 7 Pre-flight Audit

**Chunk**: 7 of 10 (v2 chunk 2 of 5) — §2.2 G.2 L5-B Task A + Task B split (E.2 fix); S-3
**Date**: 2026-05-11
**Branch**: `claude/layer-5-spec` @ `b0c42d0` (chunk 6 v2 HEAD)

---

## §1 — Sections to author/amend

| Edit target | Action |
|---|---|
| §5.B title | RENAME (Ridge Regression Fit → Composite-Weight Refit (Task A) + Return-Forecast Regression (Task B)) |
| §5.B.1.0 (NEW) task split overview | INSERT |
| §5.B.1.1 public API | REPLACE with `fit_composite_weights` + `fit_return_forecast` dual API |
| §5.B.1.5 (NEW) mandatory build outputs table | INSERT |
| §5.B.4 decisions | UPDATE (Q3 applies separately Task A + Task B) |
| §5.B.5 tests | EXPAND +15 → +25 (Task A 12 / Task B 13) |
| §5.B.6 Gate 19 | UPDATE |
| §5.B.7 proof contract | EXPAND 11 → 14 items |
| §1.1 Why-L5-exists table row for L5-B | UPDATE |
| §2.5 audits | ADD #7 (Brier per horizon w/ climatology + bin counts) |
| §4 sub-phase decomposition table L5-B row | UPDATE effort 8-10h → 12-16h; test +15 → +25 |
| §10 S-3 entry | FILE |

---

## §2 — Anticipated Sxx

- **S-3**: L5-B split into Task A + Task B; closes E.2 / L5-RISK-2. Effort impact 8-10h → 12-16h. ACCEPT.

Sxx budget chunk 7: 1.

---

## §3 — Effort estimate

| Item | Estimate |
|---|---|
| §5.B title + §5.B.1.0 + §5.B.1.1 + §5.B.1.5 | 1.0h |
| §5.B.4 + §5.B.5 (25 tests) + §5.B.6 + §5.B.7 | 1.0h |
| §1.1 + §4 row updates | 0.2h |
| §2.5 audit #7 | 0.1h |
| §10 S-3 | 0.1h |
| Verification | 0.3h |
| Commit + push + status | 0.1h |
| **Chunk 7 total** | **2.8h** (within 2-3h target) |

---

## §4 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| stat | 0.94 | E.2 finding crystal-clear (scalar Ridge ≠ component refit); Task A/B split is mechanical |
| op | 0.91 | Largest spec amendment in v2; cross-refs to §5.RM-4 (Task B input post-RM-6) carefully tracked |
| act | 0.96 | Closes HIGH blocker E.2; component-level Ridge is the foundation for L5-RM-6 calibration scope |
| **Aggregate** | **0.91** | Binding: operational |

≥0.85 → standing approval continues.

---

## §5 — Recommendation

PROCEED to chunk 7 authoring.

---
