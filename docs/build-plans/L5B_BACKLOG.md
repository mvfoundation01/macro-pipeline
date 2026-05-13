# L5b (OOS Hardening) Backlog

**Scope**: items deferred from L5 build to L5b OOS hardening sprint (per `Master Prompt v3.1 §15` and `LAYER_5_BUILD_SPEC.md` v6 §1.2). Each entry includes effort estimate + priority + provenance.

---

## L5b-2 — Implement L3 loaders for ISM New Orders (NAPMNOI) + CB LEI

**Source**: `scoring/crps.py` lines 14-22 documents that `LAYER3_ACTIVE_COMPONENTS` is currently 4 of spec's 6 components. `ism_pmi_neworders` (NAPMNOI) returns FRED 400 (series does not exist post-2018 ISM licensing change); `lei_3d_rule` (CB LEI 6M annualized) has no Tier 1-4 loader (PHILLY_LEI_PROXY blocked by `check_double_counting` vs T10Y3M).

**Surfaced**: S-10 resolution + L3 component_panel patch shipped 4-component variant (no ISM/LEI columns). Documented in `macro_pipeline/analysis/component_panel.py` docstring + `tests/test_component_panel.py::test_build_component_panel_crps_4_active_columns` asserts explicit absence.

**Effort estimate**: 4-8h
- ISM New Orders alternative source (likely Conference Board direct or Bloomberg) + FRED loader (or replace with proxy): 2-4h
- CB LEI source (CB direct or alternative aggregator) + loader: 2-3h
- 2 unit tests (one per loader) + 1 integration test (component_panel CRPS expands from 4 → 6 columns): ~1h
- Update `LAYER3_ACTIVE_COMPONENTS` (4 → 6) + `_CRPS_NORMALIZER` (add ism_pmi_neworders + lei_3d_rule entries) + `component_panel.CRPS_COLUMNS`: ~0.5h

**Priority**: **MED** — L5 ships functional 4-component CRPS (covers ~85% of spec's intended composite signal per `EXPERT_COEFFICIENT_PRIORS` mean weights: yield_curve 0.43 + sahm 0.29 + nfci 0.14 + hy_oas 0.14 = 1.00 redistributed from 0.30+0.20+0.10+0.10 = 0.70 of original 1.00 budget; spec ISM+LEI 0.30 weight not covered). ISM + LEI improve coverage but don't BLOCK L5 ship.

**Owner**: L5b OOS hardening cycle (V to schedule post-L5-H ACCEPT).

**Acceptance criteria**:
1. `loaders/<new_loader>.py` produces monthly time series for both NAPMNOI + CB LEI; PIT discipline preserved per L3.5b-T/U.
2. `scoring/crps.py::LAYER3_ACTIVE_COMPONENTS` expands to 6 components.
3. `analysis/component_panel.py::CRPS_COLUMNS` expands to 6.
4. Existing 623-test baseline preserved + 2-3 new tests for the loaders + 1 expanded test for `component_panel CRPS 6 columns`.
5. `test_build_component_panel_crps_4_active_columns` either updated to 6-column variant OR replaced; documented in commit message.

**Provenance trail**:
- S-10 (2026-05-13; build-phase Sxx): component_panel patch surfaced 4-of-6 reality.
- L5 spec §5.B.1 line 587: spec ideal is 6 CRPS components.
- `scoring/crps.py` lines 14-22 (pre-existing L3 docstring): explicit acknowledgement of 4-active reality.

---

## L5b-3 — Expose `--panel-path` flag on `gate18` CLI

**Source**: L5-B Task A retry Phase 3 deviation #3.

**Surfaced**: 2026-05-14 L5-B Task A ACCEPT (commit `53deb90`; review branch `reviews/l5-b-task-a-accept` @ `bdeb2d6`).

Track A's L5-A `_cli_gate18` in `macro_pipeline/validation.py` doesn't accept a `--panel-path` flag; it uses `PANEL_CACHE_PATH` from `analysis.r_squared_panel` as the default. V's L5-B Task A retry prompt PHASE 3 invoked Gate 18 with `--panel-path data/cache/<panel-file>.parquet` syntax which CLI doesn't parse. Workaround was to call via Python script (`python -c "..."`) supplying `panel_index` + `panel_path` explicitly. Functional equivalence achieved; flag-based CLI is a hygiene improvement.

**Effort estimate**: 0.25-0.5h
- Add argparse to `_cli_gate18`: 0.1h
- Update help text + tests: 0.15h
- Update CLI documentation in `validation.py` `__main__` dispatcher: 0.05h

**Priority**: **LOW** — functionality available via Python script (e.g., the script captured at `reviews/l5-b-task-a-accept/artifacts/gate18_cli_runtime.txt`); flag is operational hygiene improvement; not blocking any subsequent sub-phase.

**Owner**: L5b OOS hardening cycle (V to schedule alongside other CLI / ergonomic improvements).

**Acceptance criteria**:
1. `python -m macro_pipeline.validation gate18 --panel-path <path>` accepts an explicit panel cache path.
2. Existing default behavior (no `--panel-path` → uses `PANEL_CACHE_PATH`) preserved for backward compat.
3. Help text describes both invocation modes.

**Provenance trail**:
- L5-B Task A retry execution report (2026-05-14): deviation #3.
- `_cli_gate18` source: `macro_pipeline/validation.py` (post-S-11 commit `53deb90`).

---

---

## L5b-4 — Spec v7 surgical patch: magic-number cleanup §5.RM-4

**Source**: S-12 disposition Option A (RESOLVED-OPTION-A 2026-05-15).

**Surfaced**: L5-RM-4 ACCEPT review (commit `056d198`; verification report §8 deviation #1).

Spec `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` §5.RM-4 contains 4 magic-number sites + 1 header inconsistency that mismatch empirical production base. Sites enumerated in `L5_BUILD_SXX_LOG.md` S-12 entry:
1. §5.RM-4.0 line 921 — "31 slots total (25 base + 6 new)" → should be "29 (23 + 6)"
2. §5.RM-4.5 test #1 line 1051 — `test_dataclass_has_all_31_slots` → should be `_29_slots`
3. §5.RM-4.6 criterion 1 line 1070 — `count = 31` → should be `count = 29`
4. §5.RM-4.7 proof item 1 line 1081 — `== 31` → should be `== 29`
5. §5.RM-4.1.1 header line 935 — "(5 total)" → should be "(6 total)" (body already lists 6)

**Effort estimate**: 1-2h ChatGPT review + 0.5h Track A surgical scrub + 0.5h Strategic disposition ≈ 2-3h cycle (would constitute a v7 spec surgical patch comparable to v6).

**Priority**: **LOW** — doc residue only; zero functional impact. L5-RM-4 implementation works correctly per Pattern B + empirical Gate 20 PASS. Deferral to post-L5 retrospective is the right priority signal.

**Owner**: post-L5 retrospective (NOT during active L5 build; spec FROZEN per scope guard).

**Acceptance criteria**:
1. v7 spec patch updates 4 magic-number sites + 1 header
2. AP-AUTH-52 mitigation discipline enforced in v7: each new total derives from `<base_grep_count> + <delta>` with grep command shown
3. v7 ChatGPT review confirms 0 new magic-numbers introduced
4. L5-RM-4 test #1 + Gate 20 + verification report still align (already correct via Option A; v7 just cleans spec literals)

**Provenance trail**:
- S-12 in `L5_BUILD_SXX_LOG.md` (filed 2026-05-14; CONDITIONAL → RESOLVED-OPTION-A 2026-05-15)
- AP-AUTH-52 codified in `docs/ap_register.md` (2026-05-15)

---

## L5b-5 — Investigate NBER pre-1978 training caveat (spec §5.RM-4 step 3)

**Source**: L5-13 absorption step 3 deferral.

**Surfaced**: L5-RM-4 ACCEPT report (2026-05-15; verification report §5 + §8 deviation #2).

Spec `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` §5.RM-4.1.4 step 3 reads: "Add NBER pre-1978 caveat to notes when `pre_1978_training_only=True` flag is set (mirrors CRPS handling)."

**Deferral rationale**: no `pre_1978_training_only` flag exists in:
- `ScoredObservation` dataclass schema (pre- or post-RM-4)
- `scoring/cdrs.py` code path (no flag set/read)
- Any caller surface (no current data flow constructs the flag)

Spec step 3 reads as speculative — anticipates a future state where pre-1978 training mode is distinguished from post-1978 NBER-announcement-calendar mode. The flag would need to be introduced upstream (likely in `RegimeContext` or `PitDataContext`) before L5-13 step 3 can be implemented.

**Effort estimate**: 2-4h
- Investigate intended semantic of `pre_1978_training_only` (consult L3.5C NBER calendar spec): 1h
- Add `pre_1978_training_only` flag to appropriate dataclass (RegimeContext likely): 1-2h
- Wire flag through CDRS code path; add NBER pre-1978 caveat note formatter helper: 0.5-1h
- 2-3 regression tests covering pre-1978/post-1978 caveat emission: 0.5h

**Priority**: **MED** — validity of pre-1978 NBER labels affects long-horizon drawdown statistics in OOS hardening (L5b scope). Not blocking any L5 sub-phase; relevant for L5b OOS hardening sprint where pre-1978 vs post-1978 sample distinction matters.

**Owner**: L5b OOS hardening cycle (likely L5b-RM-X sub-phase or equivalent).

**Acceptance criteria**:
1. Spec ambiguity resolved (consult L3.5C `regime/nber_calendar.py` + L3.5C verification docs)
2. `pre_1978_training_only` flag introduced (probably `RegimeContext`)
3. CDRS adds caveat to notes when flag is set; CRPS continues current pattern
4. Tests verify caveat presence pre-1978 + absence post-1978

**Provenance trail**:
- L5-RM-4 verification report §5 (L5-13 absorption table; step 3 row marked DEFERRED)
- L5-RM-4 ACCEPT report §8 deviation #2

---

---

## L5b-6 — Gate 20 criterion 3 wording-vs-implementation drift (L5-E awareness)

**Source**: ChatGPT 5.5 post-RM-4 gate review §D.1 + §B.E (PASS-WITH-NOTE).

**Surfaced**: 2026-05-15 post-RM-4 gate review.

**Issue**: Spec `LAYER_5_BUILD_SPEC.md` v6 §5.RM-4 Gate 20 PASS criterion 3 says "Parquet roundtrip smoke-test PASSes (test #2)". RM-4 implementation (commit `056d198`) used a **JSON roundtrip** in `test_parquet_roundtrip_preserves_6_new_slots` because real parquet would require wrapping ScoredObservation into a DataFrame schema that's not in scope for RM-4. The JSON form preserves the same invariant (new fields survive a round-trip via `to_dict()`) but is wording-vs-implementation drift relative to spec criterion 3.

**Acceptable for RM-4** because:
- RM-4 deliverable is the dataclass migration (fields + validators), NOT a production parquet schema
- JSON roundtrip via `to_dict()` exercises the same field-preservation contract
- ChatGPT post-RM-4 gate review explicitly marked this PASS-WITH-NOTE (not REVISE)

**L5-E future scope**: L5-E (forecast σ confidence band) is the sub-phase that builds the production parquet schema for ScoredObservation export. L5-E pre-flight MUST:
1. Implement a real parquet roundtrip (pyarrow schema declaration + write + read + element-wise comparison)
2. NOT cite RM-4 Gate 20 criterion 3 as precedent (RM-4 used JSON; L5-E must use parquet)
3. Verify all 6 RM-4 new fields survive parquet roundtrip (especially `drawdown_conditional_distribution: dict[str, float]` which requires pyarrow Map type)

**Effort estimate**: 0.25h doc-only ticket (this backlog entry); L5-E implementation cost separate (~1-2h for parquet schema declaration + test).

**Priority**: **LOW** (informational; prevents future L5-E error; ChatGPT review accepted current RM-4 state).

**Owner**: L5-E pre-flight + L5b OOS hardening cycle.

**Acceptance criteria** (L5-E):
1. L5-E implements `tests/test_*::test_parquet_roundtrip_*` using actual parquet (NOT JSON)
2. Schema declaration verified for all 6 RM-4 new fields + 23 pre-existing
3. Round-trip element-wise equality
4. L5-E verification report explicitly notes "Gate 20 RM-4 used JSON per L5b-6; L5-E provides real parquet"

**Provenance trail**:
- ChatGPT 5.5 post-RM-4 gate review (2026-05-15; ACCEPT-WITH-NOTES at 86% conf / 8.4/10)
- RM-4 commit `056d198` + L5_RM_4_VERIFICATION.md §2.2 (cites JSON variant)
- Spec §5.RM-4.6 criterion 3 + §5.RM-4.7 proof item 2

---

**END — L5B_BACKLOG.md (L5b-2 + L5b-3 + L5b-4 + L5b-5 + L5b-6 as of 2026-05-15; reserved L5b-1 + L5b-7..N open)**
