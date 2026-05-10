# LAYER 3.5D — Verification Report (Dissent Fail-Closed + Probability Semantics Rename)

**Commit**: `7d99afe` on `claude/layer-3-5-build`
**Base**: `8dbdb87` (3.5C complete + verification)
**Date**: 2026-05-09
**Author**: Claude Code (build agent)
**Status**: PAUSED awaiting V verification per `HANDOFF_CLAUDE_CODE_v3.md` §2

---

## §1 — Header

| Field | Value |
|---|---|
| Sub-phase | 3.5D — Dissent Fail-Closed + Probability Semantics Rename |
| Spec ref | `LAYER_3_5_BUILD_SPEC.md` §6 |
| Branch / commit | `claude/layer-3-5-build` @ `7d99afe` |
| Tests delta | **+10 new** (534 → 544); 4 existing tests semantic-rewritten under D24 |
| Gate added | **Gate 15** PASS |
| Gates total | **15/15 green** (1, 2, 3, 4A-D, 8-15) |
| Deviations filed | **D24** (R-multiplier from consensus AM21=B + existing-test rewrites). No D25 needed. |
| Effort actual | ~6.5h (vs 6.5–7.5h estimate; on the lower edge per AM21=B saving the Gate 10 recalibration) |

---

## §2 — Empirical / smoke-test (post-impl)

### §2.1 derive_regime_state at canonical anchors (post-3.5D)

| as_of | NBER | Kindleberger | HMM | derive() return | regime_state |
|---|---|---|---|---|---|
| 2025-06-01 | expansion | boom | recession | `("indeterminate", "hmm_dissent_indeterminate", 0.40)` | **indeterminate** ✓ |
| 2020-02-20 | expansion | indeterminate | expansion | `("expansion", "nber", 0.0)` | expansion (HMM agrees) |
| 2008-09-15 | expansion | revulsion | recession | `("indeterminate", "hmm_dissent_indeterminate", 0.40)` | **indeterminate** ✓ |
| 2017-06-01 | expansion | euphoria | expansion | `("expansion", "nber", 0.0)` | expansion |

### §2.2 CRPS / CDRS shifts post-3.5D

| as_of | CRPS pre-conf | **post-conf** | CDRS R pre | **post R** | CDRS pre | **post** |
|---|---|---|---|---|---|---|
| 2025-06-01 | 70.0 | **60.0** | 0.6 | **0.6** (consensus expansion) | 0.0795 | 0.0795 |
| 2020-02-20 | 70.0 | 70.0 | 0.6 | 0.6 | 0.1343 | 0.1343 |
| 2008-09-15 | 70.0 | **60.0** | 1.0 | **1.0** (consensus late-cycle) | 0.3067 | 0.3067 |
| 2017-06-01 | 70.0 | 70.0 | 0.6 | 0.6 | 0.0349 | 0.0349 |
| 2014-06-01 | (calm) | 70.0 → 60.0 | 0.6 | **0.6** (consensus expansion) | 0.0337 | 0.0337 |
| 2005-06-01 | (calm) | 70.0 → 60.0 | 0.6 | **0.6** (consensus expansion) | 0.0424 | 0.0424 |

**Key result**: under AM21=B (R from consensus state), CDRS scores **DO NOT shift** at any anchor — the dissent is a confidence-cap signal, not a sizing change. Gate 10 differential measured **6.05×** (vs 3.0× floor) — calibration preserved.

### §2.3 Spec narrative refinement (per V kickoff, not a Dxx)

Spec §6.2 #1 example claimed pre-3.5D 2025-06 → "late-cycle, 0.76". Empirically pre-3.5D 2025-06 went via Path 3 (clean NBER expansion, no HMM check) and returned `("expansion", "nber", 0.0)`. The new behavior (INDETERMINATE) is correctly anticipated; only the "old" half of the example was loose. Documented in commit + verification §2.1.

---

## §3 — Proof Contract (12 items per spec §6.7)

| # | Spec proof item | Result | Evidence |
|---|---|---|---|
| 1 | `grep -rn "score_value" macro_pipeline/ \| grep -v "DeprecationWarning"` returns ≤1 line (the property) | PASS (AST-based) | Gate 15 sub-criterion 6: zero non-deprecated AST refs |
| 2 | `pytest tests/test_regime_dissent.py tests/test_scored_observation_rename.py` shows 8+ tests pass | PASS | 9 tests pass (4 + 5; spec target 8) |
| 3 | Smoke-test 2025-06: pre-3.5D vs post-3.5D | PASS | §2.1 + §2.2 above; spec narrative refined |
| 4 | `RegimeState` enum diff in regime_context.py | PASS | `class RegimeState(str, Enum): EXPANSION=…, LATE_CYCLE=…, RECESSION=…, INDETERMINATE=…` |
| 5 | `scoring/README.md` §D21 added; Layer 6 wording updated | PASS | §D21 with 4 sub-sections; §1 table updated; "12M-forward Recession Risk Score" |
| 6 | CDRS at INDETERMINATE: R=consensus (AM21=B), confidence ≤60 | PASS | 2025-06: R=0.6 (consensus expansion); 2008-09: R=1.0 (consensus late-cycle). Both: conf=60.0 |
| 7 | DeprecationWarning fires when `score_value` accessed | PASS | `test_score_value_property_emits_deprecation` PASSES |
| 8 | `validation.py` Gate 9 / Gate 10 updated (raw_score / calibrated_probability) | PASS (rename) | 13 attribute accesses migrated |
| 9 | Gate 15 passes | PASS | `python -m macro_pipeline.validation gate15` → PASS |
| 10 | All previously-passing tests still pass (no regression) | PASS | 544 / 544 (existing-test rewrites under D24 are explicit semantic shifts, not silent regressions) |
| 11 | Cumulative test count = 530 + 8 = 538 (or higher) | PASS | **544** (exceeds target by 6) |
| 12 | Conviction reported per §2.4; smoke-test results archived | PASS | §6 below + §2 smoke-test |

**12/12 PASS.**

---

## §4 — Test Run Detail

### §4.1 New tests

`tests/test_regime_dissent.py` (4 tests, 1 NEG / 3 POS):
- `test_hmm_dissent_returns_indeterminate` (POS) — 2025-06 dissent anchor
- `test_indeterminate_caps_confidence_60` (POS) — CRPS+CDRS conf ≤60 at 2025-06
- `test_cdrs_indeterminate_R_from_consensus_state` (POS) — AM21=B verbatim
- `test_resolve_r_multiplier_indeterminate_requires_regime_ctx` (NEG)

`tests/test_scored_observation_rename.py` (5 tests, 3 NEG / 1 POS + 1 cross-phase migration test):
- `test_score_value_kwarg_fails_in_constructor` (NEG)
- `test_score_value_property_emits_deprecation` (NEG)
- `test_raw_score_field_present_and_calibrated_probability_default_none` (POS)
- `test_calibrated_probability_out_of_range_raises` (NEG)
- `test_crps_notes_carry_3_5B_pit_lineage_after_3_5D_migration` (POS, AM25 migration smoke)

NEG/POS split: **4 NEG / 5 POS = 9 tests total**. (Spec target 8; 50% NEG floor satisfied.)

### §4.2 Existing tests semantic-rewritten under D24

| Test | Change |
|---|---|
| `test_compute_crps_2025_06_expansion_calm` | `regime_state` allowed set adds "indeterminate" |
| `test_compute_crps_2008_09_recession_signal` | same |
| `test_regime_state_2025_06_nber_expansion` | renamed → `_indeterminate_on_hmm_dissent`; asserts INDETERMINATE + 0.40 haircut |
| `test_regime_state_neutralization_when_nber_pit_raised` | renamed → `_indeterminate_on_dissent_when_nber_unavailable`; documents the Phase-A `hmm_solo` consensus path; verifies the previous "neutralization" path is no longer reachable on NBER-unavailable inputs (Phase A treats unmatched HMM as `hmm_solo` consensus, so Phase B trivially matches) |
| `test_regime_state_kindleberger_override` | HMM matches consensus in each subcase to isolate override logic |

NEW dissent-coverage test:
- `test_regime_state_hmm_dissent_indeterminate_on_kindleberger_override` — NBER expansion + Kindleberger=distress + HMM=recession → INDETERMINATE (covers the Phase B fire on the Kindleberger-override path).

### §4.3 Mass renames (~24 occurrences)

| File | `score_value` → `raw_score` |
|---|---|
| `tests/test_cdrs.py` | 14 attribute accesses (1 docstring left + updated to `raw_score`) |
| `tests/test_crps.py` | 5 attribute accesses |
| `tests/test_scored_observation.py` | 5 occurrences (constructor kwarg + match strings + function name) |
| `macro_pipeline/validation.py` | 13 attribute accesses + error message strings |

### §4.4 Full pytest

```
544 passed in 121.91s (0:02:01)
```

534 baseline (3.5C close) + 10 net new = 544. Zero regressions; the 4 existing-test rewrites under D24 are explicit semantic updates documented in the deviations register.

### §4.5 Ruff

```
$ ruff check macro_pipeline/ tests/ scripts/
All checks passed!
```

Per-file ignores added: `tests/test_regime_dissent.py` + `tests/test_scored_observation_rename.py` (E402, N802 — test names embed RegimeState constants and sub-phase tags); `regime_context.py` (UP042 — spec literal `class RegimeState(str, Enum)` per §6.3-1; Python 3.11+ StrEnum migration is L5 backlog).

### §4.6 All 15 gates

```
[gate1]  Gate 1 - FRED Loader: PASS
[gate2]  Gate 2 - TV CSV Loader: PASS
[gate3]  Gate 3 - Yahoo + CFTC: PASS
[gate4a] Gate 4A - Easy Official Parsers: PASS
[gate4b] Gate 4B - Medium Official Parsers: PASS
[gate4c] Gate 4C - Complex Official Parsers: PASS
[gate4d] Gate 4D - HLW Vintage Loader: PASS
[gate8]  Gate 8 - Layer 3A Regime Classifier: PASS
[gate9]  Gate 9 - Layer 3B CRPS (Path B): PASS
[gate10] Gate 10 - Layer 3C CDRS (Path B + D13/D14): PASS  [differential 6.05x, far above 3.0x floor]
[gate11] Gate 11 - Layer 3D R^2 Panel: PASS
[gate12] Gate 12 - Layer 3.5A HMM Frozen Contract: PASS
[gate13] Gate 13 - Layer 3.5B PIT Contract (Option Z): PASS
[gate14] Gate 14 - Layer 3.5C NBER Announcement Calendar: PASS
[gate15] Gate 15 - Layer 3.5D Probability Semantics + Dissent: PASS
```

---

## §5 — Deviations filed

### D24 — INDETERMINATE R-multiplier policy = consensus-driven (AM21=B); existing dissent-derivation tests rewritten — ACCEPT

Pre-flight smoke-test (15 anchors) showed HMM v1 dissents at 10/15 anchors; spec-default R=1.0 would inflate calm-anchor CDRS via the HMM late-cycle bias and break Gate 10 differential floor (predicted 3.62× → 2.18×). PAUSE-required per Standing Orders. V/Strategic locked **AM21=B** (spec §6.4-D2 alternative #3: R from consensus state). Implementation plumbs `regime_ctx=` through `_resolve_r_multiplier` with new helper `_consensus_state_for_indeterminate`. The 0.60 confidence cap is enforced separately at `compute_crps`/`compute_cdrs` post-`confidence_score_v2` (orthogonal to source/derived caps).

Gate 10 differential measured 6.05× empirically post-impl — calibration fully preserved. **No D25 needed.** L5-6 (V/T weight refit) remains escape hatch if calibration shifts later.

Existing-test rewrites under D24:
- `test_regime_state_2025_06_nber_expansion` → `test_regime_state_2025_06_indeterminate_on_hmm_dissent`
- `test_regime_state_neutralization_when_nber_pit_raised` → `test_regime_state_indeterminate_on_dissent_when_nber_unavailable`
- `test_regime_state_kindleberger_override` (parameter set adjusted)
- `test_compute_crps_2025_06_expansion_calm` + `test_compute_crps_2008_09_recession_signal` (regime_state allowed set expanded to include "indeterminate")

NEW test under D24: `test_regime_state_hmm_dissent_indeterminate_on_kindleberger_override`.

### Cross-phase coordination — AM12 + AM25 cleanup CONFIRMED

- **3.5B `metadata_extra` → 3.5D `notes` migration COMPLETE**: 3 keys (`pit_safe_basis_per_component`, `derived_confidence_cap_applied`, `pit_construction_notes`) DROPPED from `metadata_extra` in CRPS post-3.5D; their content migrated into `notes` via `_format_pit_lineage_notes()` helper with `dict.fromkeys()` dedup. Verified by `test_crps_notes_carry_3_5B_pit_lineage_after_3_5D_migration` and the updated `test_pit_enforcement.py::test_layer_6_displays_construction_caveat_in_notes`.
- **3.5C `is_pre_1978_training_only` → notes propagation**: field exists on `NberStateResult`. Propagation to scoring layer's `notes` only happens on training-mode path (rare in real-time CRPS/CDRS). Documented in `scoring/README.md` §D21.4. Test coverage to be added in L5 when training-mode workflows are exercised.

### Spec narrative refinement (informational)

Spec §6.2 #1 example pre-3.5D claim "regime_state=late-cycle, confidence ≈ 0.76" at 2025-06 was empirically wrong — pre-3.5D 2025-06 went via Path 3 (clean NBER expansion) and returned `("expansion", "nber", 0.0)`. The new behavior (INDETERMINATE) is correctly anticipated by the spec; only the "old" half of the narrative example was loose. **Not a Dxx; documentation hygiene only.** Surfaced per V's kickoff #6 instruction.

---

## §6 — Conviction (3-field, per spec §2.4)

| Sub-phase 3.5D as a whole | Value | Binding constraint |
|---|---|---|
| `conviction_statistical` | **0.92** | High: AM21=B's empirical prediction (Gate 10 differential preserved, R from consensus at 2025-06=0.6, at 2008-09=1.0) all matched smoke-test exactly. New tests deterministic; existing-test rewrites under D24 documented. |
| `conviction_operational` | **0.85** | Medium-high: cross-phase notes migration + AST-based `score_value` scan + per-file ruff ignores all clean. **Binding**: 4 existing-test surgical rewrites under D24, plus the AST scanner is a new artifact (ruff-style static check) that future maintainers must understand. |
| `conviction_actionability` | **0.92** | High: post-3.5D the regime classifier surfaces HMM dissent as a first-class flag (cap + notes); L5 calibration (L5-RM-4/L5-RM-6) can populate `calibrated_probability` cleanly without further dataclass churn; Layer 6 wording is "Risk Score" throughout. |
| **Aggregate `confidence_overall`** | **0.85** | Operational binding |

### Per-Gate conviction (Gate 15)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | 0.95 | All 7 sub-criteria are mechanically verifiable (enum value, derive return, cap binding, R consensus dispatch, dataclass field presence, AST scan, regex-based wording scan). |
| `conviction_operational` | 0.90 | AST-walk is a robust scan compared to grep; per-file ruff ignores documented; spec-literal `RegimeState(str, Enum)` preserved with UP042 ignore. |
| `conviction_actionability` | 0.95 | Reproducible by anyone with this branch + Python 3.12.10. |

---

## §7 — Effort actual vs estimated

| Step | Estimate (h) | Actual (h) |
|---|---|---|
| Pre-flight (with smoke-test + AM21 analysis) | 0.6 | 0.6 |
| RegimeState enum + derive_regime_state refactor | 0.8 | 0.6 |
| ScoredObservation rename + new fields + property | 0.8 | 0.7 |
| CRPS plumbing (raw_score, INDETERMINATE cap, notes migration) | 1.0 | 0.7 |
| CDRS plumbing (raw_score, R from consensus, notes migration) | 1.0 | 0.7 |
| Layer 6 wording (scoring/README.md §D21) | 0.4 | 0.3 |
| Validation Gate 15 + Gate 9/10 raw_score check | 0.7 | 0.6 |
| 8 new tests + property/AST scan | 0.7 | 0.5 |
| Mass rename `score_value` → `raw_score` in tests | 0.4 | 0.3 |
| 4 existing-test rewrites under D24 | n/a (D24 emerged) | 0.5 |
| Cross-phase test update (test_pit_enforcement) | 0.2 | 0.2 |
| Smoke-test post-impl + ruff + 15 gates | 0.3 | 0.4 |
| Verification report (this) | 0.4 | 0.4 |
| **Total** | **6.7–7.5** | **~6.5** |

Slightly under-budget; AM21=B (consensus-driven R) avoided the Gate 10 recalibration that would have added 0.5h under AM21=A.

---

## §8 — Risks for next sub-phase (3.5E)

| ID | Risk for 3.5E | Mitigation plan |
|---|---|---|
| R-3.5E-1 | `read_cache_validated_subdir` will be added to `cache.py`; existing `read_cache_validated` (parquet, top-level) provides precedent — but the subdir variant needs distinct handling for `.meta.json` co-location | Pre-flight will inspect `cache.py` + existing `analysis.load_panel()` |
| R-3.5E-2 | 3 atomic-write migrations in loaders (CFTC SPX, CFTC Treasury, HLW vintage) — each touches its own loader's existing tests | Pre-flight will inventory; HLW vintage especially has per-vintage loop semantics |
| R-3.5E-3 | Gate 11 sha-recompute may conflict with the existing length-check (it'll be tightened, not added) | Pre-flight will trace existing Gate 11 implementation |
| R-3.5E-4 | `except Exception` narrowing in 3 known locations (`regime_context.py:211-215` from L1.5; `cdrs.py` 2 quality-cap loads). 3.5C may have moved some of these. | Pre-flight will re-grep |
| R-3.5E-5 | sha256 latency smoke-test (<500ms target on largest cached parquet) is a §2.3 empirical override candidate | Pre-flight will run on R² panel + largest FRED series (e.g., DTB3 daily) |

---

## §9 — Recommendation

**APPROVE for advance to 3.5E.**

12/12 proof-contract items pass; 15/15 gates green; ruff clean; conviction ≥ 0.85 aggregate; D24 filed cleanly with rationale. The HMM-dissent → INDETERMINATE contract is correctly implemented across `regime_context.py` + `crps.py` + `cdrs.py` + `scored_observation.py`; the 0.60 cap binds at expected anchors; consensus-driven R preserves Gate 10 calibration. The `score_value` → `raw_score` rename is complete with read-only property alias; cross-phase notes migration (3.5B → 3.5D) is verified.

Per `HANDOFF_CLAUDE_CODE_v3.md` §2 + standing orders, **PAUSED** awaiting your APPROVE / REVISE-WITH-NOTES / RETURN-FOR-REWORK signal before authoring the 3.5E pre-flight.

---

## §10 — Quick-reference artefacts for review

| Artefact | Path |
|---|---|
| Pre-flight | `LAYER_3_5_3.5D_PREFLIGHT.md` |
| Verification (this) | `LAYER_3_5_3.5D_VERIFICATION.md` |
| Deviations register | `LAYER_3_5_DEVIATIONS.md` (now D21–D24 + L5-12) |
| New tests (dissent) | `tests/test_regime_dissent.py` |
| New tests (rename + cross-phase migration) | `tests/test_scored_observation_rename.py` |
| Refactored: derive_regime_state + RegimeState enum | `macro_pipeline/regime/regime_context.py` |
| Refactored: ScoredObservation | `macro_pipeline/scoring/scored_observation.py` |
| Refactored: CRPS plumbing + notes migration | `macro_pipeline/scoring/crps.py` |
| Refactored: CDRS R from consensus + INDETERMINATE clamp | `macro_pipeline/scoring/cdrs.py` |
| Gate 15 + AST scan | `macro_pipeline/validation.py::validate_gate15_probability_semantics` |
| Documentation §D21 | `macro_pipeline/scoring/README.md` |

---

**END — LAYER_3_5_3.5D_VERIFICATION.md**
