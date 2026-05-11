# LAYER 5 v2 — Chunk 6 Pre-flight Audit

**Chunk**: 6 of 10 (v2 incorporation chunk 1 of 5)
**Date**: 2026-05-11
**Branch**: `claude/layer-5-spec` @ `d776eb4` (= tag `layer5-spec-v1`)
**Standing approval**: inherited from chunks 2-5 pattern; active for v2 chunks 6-10

---

## §1 — Sections to author / amend

| Edit target | Action | Source spec ref |
|---|---|---|
| §3.3 (NEW) "Calibration target schema" | INSERT before §3.2 | v2 prompt §2.1 item 1 |
| §3.2 semantic table | ADD row for `positive_return_probability` | v2 prompt §2.1 item 2 |
| §5.RM-4.1.1 slot list | EXPAND 5 → 6 slots | v2 prompt §2.1 item 3 |
| §5.RM-6.1.2 wording | REPLACE event-direction wording | v2 prompt §2.1 item 4 |
| §5.RM-6.5 tests | ADD invariant test `test_calibration_target_matches_score_type_per_3_3_table` | same |
| §5.C.5 test #4 | UPDATE to parametrize per score_type | v2 prompt §2.1 item 5 |
| §2.5 audits | ADD #5 (train-only z-scoring) + #6 (no pre-RM-6 calibrated_probability use) | v2 prompt §2.7 |
| §10 Sxx register | FILE S-2 | v2 prompt §2.1 closing |

---

## §2 — Anticipated Sxx

- **S-2**: calibration target schema added; closes ChatGPT E.1 / L5-RISK-1. Disposition: ACCEPT. No backlog.

Sxx budget chunk 6: 1 (within hard limit ≤2).

---

## §3 — Cross-references

| New anchor | Resolves to |
|---|---|
| §3.3 calibration target schema | §3.2 row `positive_return_probability` / §5.RM-4.1.1 / §5.RM-6.1.2 / §5.C.5 |
| §5.RM-4 slot count 5 → 6 | §3.2 + S-2 |
| §2.5 audit #5 train-only z-scoring | §5.B.2 + §5.B Task A/B pre-flight |
| §2.5 audit #6 no pre-RM-6 calibrated_probability use | §5.RM-6.5 grep audit |

No dangling refs.

---

## §4 — Anticipated ambiguities

PAUSE-required: NONE. ChatGPT findings explicit; Strategic specifications in v2 prompt §2.1 + §2.7 verbatim-executable.

---

## §5 — Effort estimate

| Item | Estimate |
|---|---|
| §3.3 calibration target schema (new section, ≈70 lines) | 0.5h |
| §3.2 semantic table row + §5.RM-4.1.1 slot count + §5.RM-6.1.2 wording + §5.RM-6.5 invariant test + §5.C.5 parametrize | 0.5h |
| §2.5 audits 5 + 6 | 0.2h |
| §10 S-2 entry | 0.1h |
| Verification report | 0.2h |
| Commit + push + status | 0.1h |
| **Chunk 6 total** | **1.6h** (within 1.5-2h target) |

---

## §6 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| stat | 0.94 | ChatGPT E.1 finding crystal-clear (CRPS/CDRS are risk-direction; isotonic on return-direction would invert); §3.3 schema is direct closure |
| op | 0.92 | Schema referenced from §3.2 + §5.RM-4 + §5.RM-6 + §5.C; cross-references explicit |
| act | 0.96 | Closes HIGH blocker E.1 cleanly; ChatGPT v2 review will pressure-test directly |
| **Aggregate** | **0.92** | Binding: operational |

≥0.85 → standing approval continues.

---

## §7 — Recommendation

PROCEED. Standing approval active. Begin chunk 6 authoring.

---
