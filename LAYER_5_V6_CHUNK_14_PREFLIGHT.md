# LAYER 5 v6 — Chunk 14 Pre-flight Audit (FINAL SURGICAL SCRUB)

**Chunk**: 14 of 14 (v6 single-chunk surgical scrub per ChatGPT v5 §E)
**Date**: 2026-05-12
**Branch**: `claude/layer-5-spec` @ `036a454` (= tag `layer5-spec-v5`)
**Standing approval**: inherited from v5; pure cleanup scope; AP-AUTH-41 v6 negative-grep mandate active

---

## §1 — NEGATIVE GREP AUDIT (verbatim pre-fix per AP-AUTH-41 v6 mandate)

### §1.1 RM-4 stale 30/5 anchors (8 active sites in §5.RM-4 sub-phase)

```
$ grep -nE "all_30_slots|preserves_5_new_slots|all 30 slots|exactly 30|count = 30|== 30|5-slot|5 new slot|5 slots|all 5 validator" LAYER_5_BUILD_SPEC.md
```

| Line | Site | Stale text |
|---|---|---|
| 928 | §5.RM-4.0 commit message template | `L5-RM-4: ScoredObservation 5-slot batched migration ...` |
| 1026 | §5.RM-4.2 pre-flight smoke-test #2 | `construct ScoredObservation with all 30 slots populated` |
| 1045 | §5.RM-4.4 decision prose | `BATCHED dataclass migration (5 slots in one commit)` |
| 1051 | §5.RM-4.5 test #1 | `test_dataclass_has_all_30_slots` + `exactly 30 fields (25 existing + 5 new)` |
| 1052 | §5.RM-4.5 test #2 | `test_parquet_roundtrip_preserves_5_new_slots` + `all 30 slots` |
| 1066 | §5.RM-4.6 validator docstring | `5-slot batched migration` |
| 1070 | §5.RM-4.6 PASS criterion 1 | `__dataclass_fields__ count = 30` |
| 1081 | §5.RM-4.7 proof item 1 | `assert len(ScoredObservation.__dataclass_fields__) == 30` |

**HISTORICAL (PRESERVE; Sxx audit trail per AP-AUTH-40)**:
- Line 2348: S-1 register entry references "5 new slots" in v1/v2 history — PRESERVE

### §1.2 Cumulative arithmetic in active proof contracts (2 sites)

```
$ grep -nE "602 \+ 8|602 \+ 78|602 \+ [0-9]+" LAYER_5_BUILD_SPEC.md
```

| Line | Site | Stale text |
|---|---|---|
| 1088 | §5.RM-4.7 proof item 8 | `602 + 8 = 610 cumulative tests; ruff clean` |
| 2072 | §5.H.5 prose | `existing 602 + 78 = 680 cumulative test suite is the regression contract` |

**Excluded (structural math, NOT cumulative test arithmetic)**:
- Line 836: NEG count "7 + 1 = 8 strict-NEG of 16 total" — test classification math, not cumulative; PRESERVE

### §1.3 AP-AUTH-41 strengthening + AP-AUTH-42 NEW

Current §12 AP-AUTH-41 requires "verbatim grep output per anchor" but does NOT mandate negative-grep counterpart. v5 audit consequence: positive-only grep confirmed new pattern present but missed 8 stale sites in RM-4. v6 codifies BOTH pos+neg requirement.

AP-AUTH-42 NEW: cumulative arithmetic scrub uses regex `[0-9]+ \+ [0-9]+ =` to catch all variants (v5 AP-AUTH-40 mitigation listed specific instances `602 + 78 = 680` but missed `602 + 8 = 610`).

---

## §2 — Sections to patch

| # | Section | Patch type |
|---|---|---|
| §2.1 | §5.RM-4.0 + §5.RM-4.2 + §5.RM-4.4 + §5.RM-4.5 + §5.RM-4.6 + §5.RM-4.7 — 8 anchor fixes (30→31, 5→6) | HIGH (C.1) |
| §2.2 | §5.RM-4.7 item 8 + §5.H.5 — cumulative arithmetic → symbolic | LOW/MED (C.2) |
| §2.3 | §12 AP-AUTH-41 strengthen + AP-AUTH-42 NEW | LOW (C.3 + Strategic defense) |
| §2.4 | §5.RM-4.X NEW anchor verification table (5-site + 1-mirror map) | Strategic defensive |

---

## §3 — Anticipated Sxx

**0 expected.** All edits are cleanup + 1 new anti-pattern + 1 new defensive table. No methodology decisions. v6 prompt §3.2 PAUSE-required trigger "Sxx filing required → PAUSE" → 0-Sxx target.

§2.1 Step 3 adjudication of §5.RM-4.7 proof item 6 ("All 5 validator checks"): reading current §5.RM-4.6 validator content shows 5 validator paths covering 5 of 6 new slots (`positive_return_probability` slot doesn't have a domain-bound validator in §5.RM-4.1.2 — it's `Optional[float] = None`, validated only when populated to be ∈ [0, 1] which is implicit per docstring). Strategic disposition: **keep "All 5 validator checks" wording** because `positive_return_probability` validator doesn't exist as named check in §5.RM-4.1.2 (only the implicit None-OR-[0,1] semantic). No S-10 needed.

---

## §4 — Effort estimate

| Item | Estimate |
|---|---|
| §2.1 8 RM-4 anchor sites | 0.3h |
| §2.2 2 cumulative arithmetic | 0.1h |
| §2.3 §12 AP-AUTH-41 + AP-AUTH-42 | 0.1h |
| §2.4 §5.RM-4.X anchor table NEW | 0.15h |
| Verification (pos+neg grep both) | 0.15h |
| Summary v6 + commit + tag + readiness report | 0.2h |
| **Chunk 14 total** | **~1.0h** (within 0.5-1h target upper edge) |

Within v6 prompt §3.2 hard PAUSE limit (1.5h).

---

## §5 — Conviction 3-field

| Field | Value | Reason |
|---|---|---|
| stat | 0.98 | Pure cleanup; ChatGPT v5 findings concrete; negative grep evidence enumerated 8+2 sites |
| op | 0.97 | AP-AUTH-41 v6 negative-grep discipline codified; verification report will produce pos+neg grep per anchor |
| act | 0.98 | v6 closes 2/2 v5 findings + AP-AUTH-41/42 codification; expected v6 verdict FREEZE-AS-IS-V6 |
| **Aggregate (MIN)** | **0.97** | Binding: operational |

≥0.92 hard PAUSE floor cleared. v6 scrub proceeding.

---

## §6 — Recommendation

PROCEED. 0 Sxx anticipated. ~1.0h effort. Convergence cycle: v6 = 6th iteration; expected last given Sxx-delta=0, tests-delta=0, methodology-delta=0 trend.

---
