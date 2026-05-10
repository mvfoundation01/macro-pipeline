# LAYER 3.5D — Pre-Flight Audit (Dissent Fail-Closed + Probability Semantics Rename)

**Spec ref**: `LAYER_3_5_BUILD_SPEC.md` §6 (3.5D)
**Branch**: `claude/layer-3-5-build` @ `8dbdb87` (3.5C complete + verification)
**Date**: 2026-05-09
**Author**: Claude Code (build agent)
**Status**: **PAUSE-REQUIRED** for AM21 (R-multiplier policy for INDETERMINATE) — empirical finding contradicts spec assumption

---

## §1 — Audit Result Header

| Field | Value |
|---|---|
| Sub-phase | 3.5D — Dissent Fail-Closed + Probability Semantics Rename |
| Estimated effort (spec) | 5–8h |
| My estimate after audit | **6.5–8.0h** (within range; tight on the upper edge given the R-multiplier disposition + Gate 10 recalibration if Option A) |
| Tests added (spec target) | +8 (4 NEG / 4 POS) |
| Gate added | Gate 15 |
| Gates touched | 9 (CRPS field assertions), 10 (CDRS calibration *might* need re-recalibration depending on AM21 disposition) |
| Locked decisions (3.5D-D1..D5) | INDETERMINATE cap=0.60 (D1), property alias for `score_value` with DeprecationWarning (D3), add `calibration_metadata` now (D4), "Risk Score" capitalized (D5) — **D2 LOCKED at 1.0 BUT empirically breaks Gate 10** (see AM21 below) |
| Anticipated deviations | D24 (R-multiplier disposition consequence), D25 (existing CDRS calibration tests) — depends on AM21 |
| Conviction (statistical / operational / actionability) | 0.82 / **0.72** / 0.85 — see §10 |

---

## §2 — Empirical smoke-test (per spec §2.3 + §6.2 + V kickoff §1)

### §2.1 HMM dissent landscape across 15 anchors (canonical + Gate-touched)

**Empirical**: HMM v1 dissents from NBER+Kindleberger consensus at **10 of 15 anchors**. The HMM has a known UMCSENT-driven late-cycle/recession bias post-2008 (per `regime/README.md` D2). This is the ROOT CAUSE of the AM21 ambiguity below.

| as_of | NBER | Kindleberger | HMM | Pre-3.5D consensus | HMM dissent? | Post-3.5D state |
|---|---|---|---|---|---|---|
| 1990-09-01 | expansion | distress | recession | late-cycle (Kindleberger override) | YES | INDETERMINATE |
| 1995-06-01 | expansion | indeterminate | late-cycle | expansion | YES | INDETERMINATE |
| 1998-08-01 | expansion | euphoria | late-cycle | expansion | YES | INDETERMINATE |
| 2000-03-15 | expansion | euphoria | expansion | expansion | no | expansion |
| 2001-04-01 | expansion | revulsion | late-cycle | late-cycle | no | late-cycle |
| **2005-06-01** | expansion | boom | late-cycle | expansion | YES | INDETERMINATE |
| 2007-09-15 | expansion | euphoria | expansion | expansion | no | expansion |
| 2008-09-15 | expansion | revulsion | recession | late-cycle | YES | INDETERMINATE |
| 2010-06-01 | recession | distress | late-cycle | recession | YES | INDETERMINATE |
| **2014-06-01** | expansion | euphoria | late-cycle | expansion | YES | INDETERMINATE |
| 2017-06-01 | expansion | euphoria | expansion | expansion | no | expansion |
| 2020-02-20 | expansion | indeterminate | expansion | expansion | no | expansion |
| 2020-04-01 | expansion | distress | recession | late-cycle | YES | INDETERMINATE |
| 2024-01-01 | expansion | euphoria | recession | expansion | YES | INDETERMINATE |
| **2025-06-01** | expansion | boom | recession | expansion | YES | INDETERMINATE |

(Bold rows = Gate 10 calm anchors / 2025-06 = canonical dissent anchor per spec §6.2.)

### §2.2 Pre-3.5D vs Post-3.5D CDRS / CRPS scores at key anchors

Pre-3.5D measurements (current code @ commit `8dbdb87`):

| as_of | CDRS | V | T | R | CRPS | CRPS conf |
|---|---|---|---|---|---|---|
| 2025-06-01 | 0.0795 | 0.652 | 0.203 | 0.60 | 0.2437 | 70.0 |
| 2020-02-20 | 0.1343 | 0.532 | 0.420 | 0.60 | 0.2553 | 70.0 |
| 2008-09-15 | 0.3067 | 0.372 | 0.825 | 1.00 | 0.5495 | 70.0 |
| 2017-06-01 | 0.0349 | 0.601 | 0.097 | 0.60 | 0.0699 | 70.0 |

Predicted Post-3.5D CDRS (under spec-default R=1.0 for INDETERMINATE):

| as_of | Post-3.5D state | Pre R | Post R | Pre CDRS | Post CDRS | Δ | CRPS conf cap |
|---|---|---|---|---|---|---|---|
| 2025-06 | INDETERMINATE | 0.60 | **1.00** | 0.0795 | **0.1325** | **+67%** | 70 → **60** |
| 2020-02 | expansion | 0.60 | 0.60 | 0.1343 | 0.1343 | 0 | 70 |
| 2008-09 | INDETERMINATE | 1.00 | 1.00 | 0.3067 | 0.3067 | 0 | 70 → **60** |
| 2017-06 | expansion | 0.60 | 0.60 | 0.0349 | 0.0349 | 0 | 70 |

### §2.3 Critical Gate 10 regression under spec-default R=1.0

Gate 10 calibration (calm anchors at 2005-06, 2014-06, 2017-06):

| Anchor | Pre-3.5D R | Pre-3.5D CDRS | Post-3.5D R (spec default) | Post-3.5D CDRS |
|---|---|---|---|---|
| 2005-06 | 0.6 | 0.071 | **1.0** | **0.118** |
| 2014-06 | 0.6 | 0.056 | **1.0** | **0.093** |
| 2017-06 | 0.6 | 0.035 | 0.6 | 0.035 |
| **max calm** | | **0.071** | | **0.118** |

Gate 10 event anchors (no R shift expected):

| Anchor | Pre R | Pre CDRS | Post R | Post CDRS |
|---|---|---|---|---|
| 2007-09 | 0.6 | 0.257 | 0.6 | 0.257 |
| 2020-02 | 0.6 | 0.13 (D23 floor) | 0.6 | 0.13 |
| 2000-03 | 0.6 | 0.190 | 0.6 | 0.190 |

Gate 10 differential check `max(events) ≥ 3.0 × max(calm)`:
- Pre-3.5D: 0.257 / 0.071 = **3.62×** (passes 3.0× floor)
- Post-3.5D under R=1.0: 0.257 / **0.118** = **2.18×** ❌ **FAILS 3.0× floor**

Gate 10 direction check `min(events) > max(calm)`:
- Pre-3.5D: 0.130 > 0.071 ✓
- Post-3.5D under R=1.0: 0.130 > 0.118 ✓ (still holds, but margin is now thin)

**Verdict**: spec-default R=1.0 for INDETERMINATE empirically breaks Gate 10 differential floor by inflating calm-anchor scores via the HMM-dissent-driven INDETERMINATE classification. **PAUSE-REQUIRED per Standing Orders ambiguity routing** ("Empirical finding contradicts spec assumption").

---

## §3 — Spec §6.2 + §2.2 Mandatory Items

### §3.1 Item 1 — Files this sub-phase will touch

| File | Action | Notes |
|---|---|---|
| `macro_pipeline/regime/regime_context.py` | MODIFY | Introduce `RegimeState(str, Enum)` with EXPANSION/LATE_CYCLE/RECESSION/INDETERMINATE; refactor `derive_regime_state` to add HMM-corroboration check on Path 1/2/3 (currently only Path 4) |
| `macro_pipeline/scoring/scored_observation.py` | MODIFY | rename `score_value` → `raw_score`; add `calibrated_probability`/`calibration_metadata`/`notes`; add `score_value` `@property` alias with `DeprecationWarning`; loosen `regime_state` validator to allow `"indeterminate"` |
| `macro_pipeline/scoring/crps.py` | MODIFY | use `raw_score=` constructor param; INDETERMINATE → confidence cap 0.60; populate `notes` from cross-phase migration (§3.4 below) |
| `macro_pipeline/scoring/cdrs.py` | MODIFY | use `raw_score=`; `R_MULTIPLIER` table updated (depends on AM21 disposition); INDETERMINATE → confidence cap 0.60 + `notes` migration |
| `macro_pipeline/scoring/README.md` | MODIFY | add §D21 "Risk Score not Probability"; update §D5/D6/etc. wording; document R-multiplier policy |
| `macro_pipeline/regime/README.md` | MODIFY | document INDETERMINATE; replace prior "late-cycle ×0.95 neutralization" wording |
| `macro_pipeline/regime/__init__.py` | MODIFY | export `RegimeState` enum |
| `macro_pipeline/validation.py` | MODIFY | new `validate_gate15_probability_semantics`; update Gate 9/10 to verify `raw_score`/`calibrated_probability` slots; **possibly** recalibrate Gate 10 differential 3.0× → 2.0× depending on AM21 (Option A path); update CDRS detail rendering |
| `tests/test_scored_observation.py` | MODIFY | rename `score_value=` → `raw_score=`; add deprecation-warning test |
| `tests/test_cdrs.py` | MODIFY | many `.score_value` → `.raw_score`; possibly adjust 2025-06 / 2014-06 / 2005-06 CDRS expectations under AM21 |
| `tests/test_crps.py` | MODIFY | many `.score_value` → `.raw_score`; verify confidence cap propagation at INDETERMINATE anchors |
| `tests/test_regime_dissent.py` | NEW | 4 tests (POS) re INDETERMINATE on dissent + cap |
| `tests/test_scored_observation_rename.py` | NEW | 4 tests (NEG/POS mix) re rename + deprecation |

### §3.2 Item 2 — Existing tests that may break

| Test file | Risk | Mitigation |
|---|---|---|
| `tests/test_scored_observation.py` | **HIGH** — every test uses `score_value=` constructor; rename will break | Mass-rename `score_value` → `raw_score` in test bodies; add explicit deprecation test |
| `tests/test_cdrs.py` | **HIGH** — 14+ uses of `.score_value`; plus the Gate 10 calm anchors at 2005-06 / 2014-06 may shift under AM21 | Mass-rename + verify post-impl CDRS expectations |
| `tests/test_crps.py` | MEDIUM — 7+ uses of `.score_value` | Mass-rename |
| `tests/test_regime_state_derivation.py` | MEDIUM — tests Path 4 (HMM corroboration) which becomes unreachable post-3.5D in real-time mode for post-1978; some tests may need update or repurposing | Will inspect during impl; pre-3.5D Path 4 covered cases that 3.5C closed |
| `tests/test_regime_context.py` | LOW | should be unaffected (only docstrings change) |
| `tests/test_pit_enforcement.py` (3.5B) | MEDIUM — `test_layer_6_displays_construction_caveat_in_notes` reads `metadata_extra["pit_construction_notes"]`. After 3.5D migrates to `.notes`, this test path needs update. | Update assertion to read `obs.notes` (and verify the cross-phase migration leaves zero entries in metadata_extra) |
| `tests/test_nber_calendar.py::test_nber_pre_1978_training_mode_allowed` (3.5C) | LOW — asserts `r.is_pre_1978_training_only is True` on `NberStateResult`. Field stays; no change to that assertion. The 3.5D migration to scoring layer's `.notes` is a NEW propagation path, not a field rename. | None |
| Validation Gate 9 + 10 | MEDIUM | Gate 9 likely unaffected (CRPS scores don't depend on R); Gate 10 affected per AM21. |

**Net**: ~30+ tests need surgical `.score_value` → `.raw_score` rename. The change is mechanical (sed-style); risk is LOW for the rename itself but MEDIUM for AM21 (R-multiplier). Plus 1 cross-phase migration test update (3.5B) and possibly 1-2 dissent-derivation tests (3.5D scope).

### §3.3 Item 3 — Empirical reading (per spec §2.3 / §6.2)

DONE in §2 above. Spec §6.2 #1 prediction "old returns regime_state=late-cycle, confidence ≈ 0.76; new returns INDETERMINATE, confidence ≤0.60" applies to dissent points where the old derive logic chose late-cycle (Path 4b). At 2025-06, the smoke-test shows derive currently returns ("expansion", "nber", 0.0) — **NOT late-cycle**. The spec's example was wrong about the OLD logic at 2025-06: 2025-06 currently goes through Path 3 (NBER expansion clean, no HMM check) and returns "expansion". Post-3.5D (with HMM check on Path 3), it becomes INDETERMINATE.

Net: spec §6.2 narrative slightly misstates the OLD behavior at 2025-06. The NEW behavior (INDETERMINATE) is correctly anticipated.

### §3.4 Item 4 — Ambiguities

| ID | Ambiguity | Spec ref | Proposed resolution | Decision needed? |
|---|---|---|---|---|
| **AM21** | INDETERMINATE R-multiplier policy: spec-locked default = **R=1.0**. Empirically (per §2.3) this breaks Gate 10 differential floor 3.0× → 2.18× because 2 of 3 calm anchors (2005-06, 2014-06) get HMM-dissent-flagged INDETERMINATE → R bumps from 0.6 to 1.0 → calm CDRS scores inflate ~67%. Two viable resolutions: (a) ACCEPT R=1.0 + recalibrate Gate 10 differential floor to 2.0× (Dxx); (b) Use R from consensus state (spec §6.4-D2 alternative #3) — preserves Gate 10 calibration, treats INDETERMINATE as "uncertainty flag, defer to consensus for sizing"; (c) R=0.8 (spec alt #1) — partial mitigation, still fails 3.0× (2.7×). | §6.4-D2 + §6.6-#4 + §2.3 above | **Recommend (b)**: R from consensus state. Rationale: orthogonalizes "R = sizing decision" from "0.60 confidence cap = uncertainty signal". The spec-default R=1.0 conflates both into the multiplier. Consensus-driven R preserves L3 calibration while properly signaling HMM dissent through the cap and `notes`. | **YES — PAUSE-REQUIRED** |
| **AM22** | `derive_regime_state` return signature: currently returns `tuple[str, str, float]` = `(regime_state, source, confidence_haircut)`. Post-3.5D INDETERMINATE: what `source` and `haircut`? Spec pseudocode at §6.3-2 shows returning a `RegimeContext` (different signature). Three options: (a) add new tuple value `("indeterminate", "hmm_dissent_indeterminate", 0.40)` — preserves tuple shape; (b) extend tuple to 4-tuple `(state, source, haircut, confidence_cap)`; (c) return a frozen dataclass. | §6.3-2 | **(a) preserve tuple shape**: source = "hmm_dissent_indeterminate"; haircut = 0.40 (from 0.80 cap on regime_stability input → 0.80 - 0.40 = 0.40 → confidence_score_v2 input ≤0.40). Confidence cap 0.60 enforced separately via aggregate_caps in CRPS/CDRS. Cleanest: minimal API churn; tuple-shape callers continue to work. | NO — clear procedural fix. |
| **AM23** | Where to enforce the 0.60 cap for INDETERMINATE: at `compute_final_confidence_cap` (next to source/derived caps via MIN aggregation), OR at `compute_crps`/`compute_cdrs` (post-confidence-score)? | §6.3-3 | **At compute_crps/compute_cdrs** — the cap is regime-driven, not indicator-driven. Adding it via `aggregate_caps(final_cap, regime_indeterminate_cap)` after `_compute_quality_cap` returns. Mirrors the `final_cap × 100` clamp pattern from 3.5B. Cleaner separation of concerns. | NO — clear. |
| **AM24** | `regime_state: str` field on `ScoredObservation` currently has `__post_init__` validator at line 92: `if self.regime_state not in {"expansion", "late-cycle", "recession"}`. Need to add "indeterminate" to the valid set. Should I keep validator as a string-set check, OR migrate to `RegimeState` enum check? | §6.3-1 | **Keep string-set check + add "indeterminate"** — minimal blast radius. The `RegimeState(str, Enum)` values are still strings, so `regime_state="indeterminate"` from `RegimeState.INDETERMINATE.value` works. Migration to enum-typed field is L5 backlog. | NO — clear. |
| **AM25** | Notes-field migration policy (V kickoff §1 #6: "exactly once; dedup if equivalent"): current 3.5B entries are: `pit_safe_basis_per_component` (dict), `derived_confidence_cap_applied` (float\|None), `pit_construction_notes` (list[str]). Plus 3.5C `is_pre_1978_training_only` (bool on `NberStateResult`, not currently propagated to scoring layer). Migrate exactly one structured representation to `notes: list[str]`. | §6.3-4 + V kickoff §1 #6 | Migration policy: each non-empty 3.5B entry produces ONE note line. Dedup: deterministic sort + `dict.fromkeys(notes).keys()` to preserve order while removing duplicates. After migration, drop the 3 keys from `metadata_extra`. The `is_pre_1978_training_only` propagates as a note IFF it surfaced (training-mode path; rare in real-time). | NO — clear procedural. |
| **AM26** | `score_value` deprecation property: read-only or read/write? `ScoredObservation` is a dataclass with `__post_init__`; if dataclass is frozen=False (current), the rename means `score_value` setter must also work for backward compat. Spec §6.3-4 says "property alias" — implies read-only is sufficient. Existing test sites assign `score_value=...` in constructor only (no post-construction reassignment). | §6.3-4 + §6.4-D3 | Read-only `@property`. Constructor uses `raw_score=`. The `@property` returns `self.raw_score`. Setter not implemented → existing assignment-style construction (`ScoredObservation(score_value=...)`) breaks: callers must use `raw_score=`. Mass test rename per §3.2. | NO — clear. |

### §3.5 Item 5 — Risk callouts

| ID | Risk | P(occurrence) | Mitigation |
|---|---|---|---|
| R-3.5D-1 | **AM21 disposition affects Gate 10 thresholds** | 100% | PAUSE for V approval before coding |
| R-3.5D-2 | `score_value` rename touches ~43 refs (19 in macro_pipeline/, 24 in tests/) | 100% (verified) | Mass-rename via grep+sed; validate via Gate 15 #6 ("zero non-deprecated references") |
| R-3.5D-3 | New `RegimeState` enum interacts with existing string `regime_state` field on ScoredObservation. AM24 disposition keeps string field but loosens valid-set | LOW 5% | Per AM24, keep string field; just expand valid set |
| R-3.5D-4 | Cross-phase notes migration: dedup logic in CRPS+CDRS (separate compute paths) must be consistent | LOW 5% | Helper function `_format_pit_lineage_notes(loads)` shared across CRPS/CDRS |
| R-3.5D-5 | The pre-existing dissent-neutralization path (Path 4b of derive_regime_state) is reachable when NBER is unavailable AND HMM dissents from Kindleberger. Post-3.5D it's REPLACED with INDETERMINATE. Existing `derive_regime_state` callers expecting "late-cycle" + 0.20 haircut as the dissent return need rewiring. | MED 15% | grep + audit; Gate 10's pre-3.5C `regime_neutralized=True` path was already orphaned by 3.5C calendar; 3.5D INDETERMINATE is the home for those semantics. |
| R-3.5D-6 | Tests at 2025-06 currently expect specific CDRS values (e.g. test_cdrs_2025_06_full_reach_all_10_components_active). Post-3.5D the value shifts ~67% under AM21=A, 0% under AM21=B. | 100% if AM21=A | Post-impl smoke-test confirms; existing tests adjusted with D24 documentation. |
| R-3.5D-7 | DeprecationWarning emission in pytest may pollute test output noise. | LOW 10% | Filter via `pytest.filterwarnings` in pyproject.toml or `warnings.simplefilter` per-test. |
| R-3.5D-8 | Spec §6.5 #4 test: `test_score_value_zero_internal_references` is a static-scan grep-style assertion. Need a robust implementation (subprocess `grep` or AST-walk) that excludes the property definition itself. | LOW–MED 10% | Use AST-walk: parse macro_pipeline/, find any `Attribute` access named `score_value` excluding the `ScoredObservation.score_value` property; assert ≤1 per file. |

### §3.6 Item 6 — Effort estimate

| Step | Estimate (h) |
|---|---|
| Pre-flight (this) | 0.6 (with smoke-test + R-multiplier analysis) |
| AM21 V/Strategic decision | gate |
| `RegimeState` enum + `derive_regime_state` refactor | 0.8 |
| `regime_context.py` HMM-check on Paths 1/2/3 | 0.5 |
| `ScoredObservation` rename + `notes`/`calibrated_probability`/`calibration_metadata` fields + property alias | 0.8 |
| CRPS+CDRS plumbing (rename + INDETERMINATE cap + notes migration) | 1.0 |
| Layer 6 wording updates (`scoring/README.md` §D21, docstrings) | 0.4 |
| `validation.py` Gate 15 + Gate 9/10 raw_score field check + (possibly) Gate 10 recalibration | 0.7 |
| 8 new tests (4 NEG / 4 POS) | 0.7 |
| Mass-rename `score_value` → `raw_score` in tests + adapt CDRS-test thresholds (if AM21=A) | 0.7 |
| Cross-phase migration test update (test_pit_enforcement #6) | 0.2 |
| Smoke-test post-impl + ruff + 15 gates | 0.3 |
| Verification report | 0.4 |
| **Total** | **6.7–7.5** | within 5–8h spec band |

---

## §4 — Decisions Locked Per Standing Orders

| Decision | Locked default | Empirical override needed? |
|---|---|---|
| 3.5D-D1 (INDETERMINATE confidence cap) | 0.60 | No (Standing-Orders ≤0.05 band; default works) |
| 3.5D-D2 (R multiplier for INDETERMINATE) | **1.0** | **YES — empirical breakage; PAUSE per AM21** |
| 3.5D-D3 (deprecation policy) | property alias + DeprecationWarning, removal at L4-L5 | No |
| 3.5D-D4 (calibration_metadata field) | add now | No |
| 3.5D-D5 (Layer 6 wording) | "Risk Score" capitalized | No |

---

## §5 — Decisions Requested From V / Strategic (BEFORE Coding)

### §5.1 AM21 — INDETERMINATE R-multiplier policy

**Empirical context** (§2.3 above): under spec-default R=1.0, Gate 10 differential floor breaks (3.0× → 2.18×).

| Option | Description | Gate 10 differential post-impl | Other impacts |
|---|---|---|---|
| **A (spec-default)** | R=1.0 for INDETERMINATE, recalibrate Gate 10 differential 3.0× → 2.0× | 2.18× ✓ (under 2.0× threshold) | File D24: Gate 10 differential calibration update; existing `test_cdrs_*` thresholds at 2025-06 / 2014-06 / 2005-06 need adjustment (~67% shift). L5-6 (V/T weight refit) may restore 3.0× later. |
| **B (recommended)** | R from consensus state when INDETERMINATE: at 2025-06 (consensus expansion) → R=0.6; at 2008-09 (consensus late-cycle) → R=1.0; at 2010-06 (consensus recession) → R=1.4. Cap confidence at 0.60 separately. | 3.62× ✓ (preserves Gate 10) | Cleaner orthogonalization; existing CDRS calibration preserved; no Gate 10 recalibration needed; minimal test churn. |
| **C** | R=0.8 (downweight INDETERMINATE) | 2.71× ✗ (still fails 3.0×) | Half-measure; same problems as A but less severe. Not recommended. |

**Recommendation: B**. Rationale:
- Treats INDETERMINATE as an "uncertainty flag, defer to consensus for sizing" — orthogonalizes R (sizing) from confidence cap (uncertainty)
- Preserves the L3 calibration that the Gate 10 floors were tuned to
- Spec §6.4-D2 lists "R from consensus instead" as alternative #3 — explicitly supported
- The 0.60 confidence cap continues to signal model disagreement to downstream consumers
- L5-6 (V/T weight refit) is the right place to revisit if calibration shifts justify a change

### §5.2 AM22, AM23, AM24, AM25, AM26 — informational

All clear procedural. NO PAUSE required; will proceed with recommended dispositions per §3.4. Surfaced for explicit acknowledgement.

---

## §6 — Anticipated Dxx filing

| ID | Topic | Trigger | Disposition |
|---|---|---|---|
| **D24 (likely)** | INDETERMINATE R-multiplier policy: AM21 disposition | Whichever option is chosen. ACCEPT with rationale documented in scoring/README.md §D21. If A: also document Gate 10 differential floor recalibration. If B: cleanest path, no recalibration. | ACCEPT |
| **D25 (only if AM21=A)** | CDRS calibration tests at 2025-06 / 2014-06 / 2005-06 require threshold adjustments due to R=1.0 inflation | If AM21=A is chosen | ACCEPT — methodology-tracking, not test-fitting. L5-6 V/T weight refit may resolve. |
| (D26+) | Property-alias deprecation warnings emitted in pytest output | If pytest noise becomes a problem | filter with `warnings.simplefilter` |

---

## §7 — Implementation Order (post-AM21 approval)

1. Add `RegimeState(str, Enum)` to `regime/regime_context.py` with EXPANSION/LATE_CYCLE/RECESSION/INDETERMINATE values.
2. Refactor `derive_regime_state` to add HMM-corroboration check on Paths 1, 2, 3 (currently only Path 4):
   - Compute consensus per existing logic (paths 1–4)
   - If `hmm` is not None AND `hmm.state != consensus.state` → return ("indeterminate", "hmm_dissent_indeterminate", 0.40)
   - Else: return existing (consensus, source, haircut)
3. `ScoredObservation` rename in `scoring/scored_observation.py`:
   - Field: `score_value` → `raw_score`
   - Add `calibrated_probability: Optional[float] = None`
   - Add `calibration_metadata: Optional[dict[str, Any]] = None`
   - Add `notes: list[str] = field(default_factory=list)`
   - `@property score_value` returns `self.raw_score` + emits `DeprecationWarning`
   - `__post_init__` validator: allow "indeterminate" in `regime_state` set
4. CRPS plumbing:
   - Use `raw_score=` constructor; populate `notes` via `_format_pit_lineage_notes(loads)` helper
   - INDETERMINATE → `regime_indeterminate_cap = 0.60`; pass through `aggregate_caps(final_cap, regime_indeterminate_cap)`
   - confidence clamp at `min(confidence, final_cap_with_indeterminate * 100)`
   - Drop `pit_safe_basis_per_component` / `derived_confidence_cap_applied` / `pit_construction_notes` from metadata_extra (now in notes)
5. CDRS plumbing:
   - Same as CRPS for raw_score, notes, INDETERMINATE cap
   - Per AM21 disposition: update `R_MULTIPLIER` table + `_resolve_r_multiplier` accordingly
6. `regime/__init__.py` export `RegimeState`.
7. `validation.py`:
   - new `validate_gate15_probability_semantics`: 7 sub-criteria per spec §6.6
   - Gate 9 + 10 add `raw_score` field assertions
   - per AM21=A: Gate 10 differential floor 3.0× → 2.0× + threshold updates at 2025-06 / 2014-06 / 2005-06
8. Documentation:
   - `scoring/README.md` §D21 added (per spec §6.3-5 verbatim text); update §D5/D6 wording
   - `regime/README.md` §4 updated (INDETERMINATE replaces dissent-neutralized path)
9. Tests:
   - NEW `tests/test_regime_dissent.py` (4 POS): INDETERMINATE at 2025-06, cap 0.60, CDRS R per AM21, derivation contract
   - NEW `tests/test_scored_observation_rename.py` (4 NEG): rename complete (zero refs scan), property emits warning, calibrated_probability default None, "Risk Score" wording scan
   - MODIFY tests/test_cdrs.py + tests/test_crps.py + tests/test_scored_observation.py: mass-rename `score_value` → `raw_score`
   - MODIFY tests/test_pit_enforcement.py #6: read `obs.notes` instead of `metadata_extra["pit_construction_notes"]`
10. Smoke-test post-impl: confirm 2025-06 → INDETERMINATE; CRPS conf 60 at INDETERMINATE-flagged anchors; Gate 10 differential under chosen AM21.
11. ruff + full pytest + 15 gates.
12. Commit (spec §6 message template).
13. Author `LAYER_3_5_3.5D_VERIFICATION.md`.
14. PAUSE for V approval.

---

## §8 — Test plan preview (8 new + ~30 existing renames)

### NEW (target spec §6.5: 4 NEG / 4 POS = 50%)

| # | Test | Type | What it asserts |
|---|---|---|---|
| 1 | `test_hmm_dissent_returns_indeterminate` | POS | At 2025-06, regime_state==RegimeState.INDETERMINATE.value |
| 2 | `test_indeterminate_caps_confidence_60` | POS | CRPS confidence ≤60 at INDETERMINATE anchor |
| 3 | `test_cdrs_indeterminate_R_multiplier` | POS | Per AM21 disposition; if B: R=consensus state's R; if A: R=1.0 |
| 4 | `test_score_value_zero_internal_references` | NEG | AST-walk: zero non-deprecated `score_value` references in macro_pipeline/ |
| 5 | `test_score_value_property_emits_deprecation` | NEG | `obs.score_value` access emits DeprecationWarning |
| 6 | `test_raw_score_field_present_and_typed` | POS | `ScoredObservation` has `raw_score: float` field; `score_value` is a property |
| 7 | `test_calibrated_probability_none_default` | POS | New field defaults to None |
| 8 | `test_layer_6_strings_no_probability_attached_to_raw_score` | NEG | Static scan: docstrings/log strings for "probability" near CRPS/CDRS = 0 (excluding L5 forward references) |

NEG/POS = 4/4 = 50% ✓.

### MODIFIED (mass rename score_value → raw_score)

| File | Approximate rename count |
|---|---|
| tests/test_cdrs.py | ~14 |
| tests/test_crps.py | ~7 |
| tests/test_scored_observation.py | ~3 |
| Total | ~24 |

---

## §9 — Proof Contract Mapping (12 items, spec §6.7)

| Spec proof # | How I will demonstrate |
|---|---|
| 1 | `grep -rn "score_value" macro_pipeline/ --include="*.py" \| grep -v "DeprecationWarning"` returns ≤1 line (the property definition) |
| 2 | `pytest tests/test_regime_dissent.py tests/test_scored_observation_rename.py -v` 8 tests pass |
| 3 | Smoke-test 2025-06 (this pre-flight §2.2): pre-3.5D (expansion, nber, 0.0); post-3.5D (indeterminate, hmm_dissent_indeterminate, 0.40) with confidence ≤60 |
| 4 | `RegimeState` enum diff in regime_context.py |
| 5 | `cat scoring/README.md` §D21; updated §D5/D6 wording |
| 6 | CDRS at 2025-06: per AM21 disposition. If B: R=0.6 + confidence ≤60. If A: R=1.0 + confidence ≤60. |
| 7 | DeprecationWarning capture in pytest output |
| 8 | `validation.py` Gate 9 / Gate 10 updated |
| 9 | `python -m macro_pipeline.validation gate15` → PASS |
| 10 | full pytest = 534 + 8 = 542 (renamed tests don't add to count) |
| 11 | conviction reported per §10 |
| 12 | smoke-test results archived in §2 of verification |

---

## §10 — Pre-flight Conviction (3-field)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | **0.82** | High-medium: smoke-test maps the dissent landscape clearly; AM21 empirical impact is unambiguous; 8 new tests assert the new contract. Slight haircut: spec §6.2 narrative slightly misstates pre-3.5D behavior at 2025-06 (it goes through Path 3 = expansion clean, not Path 4b = late-cycle dissent). |
| `conviction_operational` | **0.72** | Medium: AM21 is PAUSE-required (Gate 10 calibration shift under spec default); cross-phase notes migration touches 3.5B+3.5C entries; ~30 mass renames in tests. **Binding.** |
| `conviction_actionability` | **0.85** | High: the spec's intent (HMM dissent → fail-closed indeterminate) is sound and will be deliverable in a coherent code surface; "Risk Score" wording aligns Layer 6 with calibration discipline; L5 is explicitly the home for `calibrated_probability`. |
| **Aggregate** | **0.72** | Operational binding (AM21 needs decision) |

---

## §11 — END

Pre-flight complete. **PAUSED** awaiting:
1. **AM21 disposition** (Option A=spec default + Gate 10 recalibration / B=R from consensus / C=0.8) — recommendation B.
2. (informational) AM22/23/24/25/26 confirmation.

Per Standing Orders ambiguity routing, AM21 is PAUSE-REQUIRED ("Empirical finding contradicts spec assumption"). The spec-default R=1.0 was selected absent the empirical impact analysis; this pre-flight surfaces that impact.

If APPROVE for B (recommended): execute §7 implementation order; expect ~6.5–7h actual time. No Gate 10 recalibration needed.
If APPROVE for A: same execution order; +0.5h for Gate 10 recalibration + CDRS test threshold updates; D24+D25 filed.
If REVISE to C or other: surface revised plan in pre-flight v2.
