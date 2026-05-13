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

## L5b-7 — Spec v7 doc-residue: file naming drift + Gate 19 split

**Source**: Strategic disposition D-B1-1 + D-B1-2 (2026-05-13) at L5-B Task B1 pre-flight ACCEPT.

**Surfaced**: L5-B Task B1 pre-flight read-and-plan (this sub-phase).

Spec `LAYER_5_BUILD_SPEC.md` v6 @ `9f848bb` contains five doc-vs-implementation drifts that do not affect behavior but should be reconciled at a future v7 spec patch:

1. **§5.B.0 + §5.B.1.1 + §5.B.7 proof item 1**: spec literal `macro_pipeline/models/ridge_cv.py` does not exist in the implementation. Task A shipped at `macro_pipeline/models/composite_refit.py` (l5-b-task-a-accept). Task B1 shipped at `macro_pipeline/models/return_forecast.py` (l5-b-task-b1-accept; D-B1-1 disposition). Task B2 shipped at `macro_pipeline/models/return_calibration.py` (l5-b-task-b2-accept; D-B1-1 precedent continued). Spec proof item 1 reads "from macro_pipeline.models.ridge_cv import fit_composite_weights, fit_return_forecast_task_b1, calibrate_return_forecast_task_b2, ...". Actual: three separate import paths.

2. **§5.B.6 Gate 19**: spec authored as a monolithic 22-criterion gate covering Task A + B1 + B2. V's build plan unbundled into per-sub-phase ACCEPT tags, so Gate 19 is split into 19-A (criteria 1-7, Task A, ✓ at `l5-b-task-a-accept`), 19-B1 (criteria 8-14 + 19-22, Task B1, ✓ at `l5-b-task-b1-accept` via `validate_gate19_l5b_task_b1_subcriteria`), and 19-B2 (criteria 15-18, Task B2, ✓ at `l5-b-task-b2-accept` via `validate_gate19_l5b_task_b2_subcriteria`). After all three partial-PASS milestones land, the spec-monolithic Gate 19 is conceptually closed. Sub-criterion 19 "all 28 tests PASS" splits across the three milestones — Task A delta (twelve), Task B1 delta with B2-1 promoted into the Task B1 file (fourteen; was thirteen in spec, plus the promoted B2-1), Task B2 delta minus B2-1 (two; was three in spec, minus the promoted B2-1); total reconciles to twenty-eight, preserving the spec literal mirror anchor exactly per AP-AUTH-52 magic-number derivability discipline.

3. **§5.D.0 metadata anchor stale vs §5.D.5/.6/.7 canonical (D-D-1 + D-D-2)**: spec §5.D.0 metadata table says "Test delta +8 (≥4 NEG = 50% floor; 5 NEG / 3 POS = 63% NEG)" but §5.D.5 header + §5.D.5 footer + §5.D.6 PASS criterion 8 + §5.D.7 proof item 2 + §5.D.7 proof item 9 all assert the canonical "+12 tests" (eight NEG / four POS = 67%). The §5.D.0 anchor is a stale v1 relic that v2/v3/v4 expansions left orphaned. Implementation followed §5.D.5/.6/.7 canonical at `l5-d-accept`. Symbolic derivation per AP-AUTH-52: "+12 = eight v2 baseline + four v2/v3 cell_label taxonomy expansion (test #9 Wilson interval + test #10 diagnostic_only label + test #11 hierarchical pooling v4 amended + test #12 no-raw-nan v3 taxonomy)". D-D-2: §5.D.7 proof item 2 references `tests/test_drawdown_conditional.py` (singular) while §5.D.0 metadata "New files" row uses `tests/test_drawdown_conditionals.py` (plural). Single-letter typo in §5.D.7; implementation followed plural per metadata canonical.

4. **§5.E.0 metadata anchor stale vs §5.E.5 canonical (D-E-1)**: spec §5.E.0 metadata table says "Test delta +6 (≥3 NEG; 3 NEG / 3 POS = 50% NEG)" but §5.E.5 header explicitly contains a "wait recount" literal mid-line — the spec author noticed inconsistency in-place ("v2: +9; 4 NEG / 5 POS = 44% NEG ... wait recount") and the footer reconciles via reclassifying test #1 as NEG-invariant to canonical "+9 tests (five NEG / four POS = 56%)". The §5.E.0 anchor is stale v1 relic; the §5.E.5 mid-line "wait recount" artifact is itself a spec-authoring trace that should be cleaned in v7. Implementation followed §5.E.5 canonical at `l5-e-accept`. Symbolic derivation per AP-AUTH-52: "+9 tests = six v1 baseline + three v2 NEW per S-6 (test #7 joint bootstrap covariance + test #8 empirical coverage + test #9 coverage inflation factor)".

5. **§5.G.0 metadata anchor stale vs §5.G.5/.7 canonical (D-G-1)**: spec §5.G.0 metadata table says "Test delta +6 (≥3 NEG; 4 NEG / 2 POS = 67% NEG)" but §5.G.5 header + §5.G.5 footer + §5.G.7 proof item 4 (v5 amended) + §5.G.7 proof item 8 (v5 symbolic) all assert the canonical "+8 tests" (five NEG / three POS = 63%). The §5.G.0 anchor is stale v1 relic from before the v2 S-4 K_HORIZON backsolve expansion added tests #6 + #7 + #8. Implementation followed §5.G.5/.7 canonical at `l5-g-accept`. Symbolic derivation per AP-AUTH-52: "+8 tests = five v2 baseline + three v2 NEW per S-4 (test #6 horizon rejection + test #7 W_REF_TARGET within ±2pp at N_REF_NONOVERLAP + test #8 k_h sensitivity 0.5×/1×/2× monotone)".

**Effort estimate**: 1–2h ChatGPT review + 0.5h Track A surgical scrub + 0.5h Strategic disposition ≈ 2–3h cycle (similar to L5b-4).

**Priority**: **LOW** — doc-only residue; zero functional impact. Implementation matches Strategic-approved D-B1-1/-2/-3 + D-D-1/-2 + D-E-1 + D-G-1 dispositions, validated through `l5-b-task-b2-accept` (Gate 19 closure), `l5-d-accept` (drawdown_conditionals doc-residue), `l5-e-accept` (forecast_sigma doc-residue + Op-E-1 path (b)+(c) v2 helper resolution), and `l5-g-accept` (bayesian_shrinkage doc-residue + Gate 25 composite SEALED via 25.1 + 25.2 sub-criteria; mirrors L3.5b Gate 17 composite seal pattern per spec §5.G.6).

**Owner**: post-L5 retrospective (NOT during active L5 build; spec FROZEN per scope guard).

**Acceptance criteria**:
1. v7 spec rewrites §5.B.0 + §5.B.1.1 + §5.B.7 proof item 1 to reflect actual module paths (`composite_refit.py` for Task A; `return_forecast.py` for Task B1; future Task B2 path TBD).
2. v7 spec rewrites §5.B.6 Gate 19 as three sub-gates 19-A / 19-B1 / 19-B2, each with its own criterion numbering. Spec sub-criterion 19 anchor count updates from "28 tests" to "29 tests" (derivation cited symbolically: Task A twelve + Task B1 fourteen with B2-1 promoted + Task B2 two; grep evidence required per AP-AUTH-52).
3. AP-AUTH-52 magic-number discipline applied: each new total derives from `<base_grep_count> + <delta>` with grep evidence cited.
4. v7 ChatGPT review confirms 0 new file-naming or gate-split inconsistencies introduced.
5. v7 spec rewrites §5.D.0 metadata "+8 / 63% NEG" stale anchor to canonical "+12 / 67% NEG" per §5.D.5/.6/.7 mirror. Fixes §5.D.7 proof item 2 typo `test_drawdown_conditional.py` (singular) to plural per metadata "New files" row.
6. v7 spec rewrites §5.E.0 metadata "+6 / 50% NEG" stale anchor to canonical "+9 / 56% NEG" per §5.E.5 mirror. Removes §5.E.5 header literal "wait recount" spec-authoring trace; consolidates the test #1 NEG-invariant reclassification into a clean header. Expands §5.E.7 proof contract (currently "parallel to §5.D.7 pattern; brevity") into explicit ten-item enumeration matching the §5.D.7 template.
7. v7 spec rewrites §5.G.0 metadata "+6 / 67% NEG" stale anchor to canonical "+8 / 63% NEG" per §5.G.5/.7 mirror. Documents the v2 K_HORIZON backsolve derivation (per S-4) explicitly in §5.G.1, including the formula `k_h = (w_ref / (1 - w_ref)) × n_ref` cited alongside the resulting constants (5.9 / 6.7 / 9.4 / 11.0).

**Provenance trail**:
- L5-B Task B1 ACCEPT report (2026-05-13) — initial entry surface
- L5-B Task B2 ACCEPT report (2026-05-13) — extended for `return_calibration.py` + Gate 19 final-close confirmation + test-count miscount correction (prior entry asserted "twenty-nine" total; corrected to twenty-eight matching the spec literal mirror anchor since B2-1 is INSIDE the Task B1 file's fourteen, not an additional test)
- L5-D ACCEPT report (2026-05-13) — extended for §5.D.0 stale anchor (D-D-1) + §5.D.7 proof item 2 typo (D-D-2)
- L5-E ACCEPT report (2026-05-13) — extended for §5.E.0 stale anchor (D-E-1) + §5.E.5 header "wait recount" literal + §5.E.7 proof-contract brevity expansion + Op-E-1 path (b)+(c) v2 callable-helper resolution
- L5-G ACCEPT report (2026-05-13) — extended for §5.G.0 stale anchor (D-G-1) + Gate 25 composite SEAL confirmation (25.1 + 25.2 sub-criteria validated; mirrors L3.5b Gate 17 pattern per spec §5.G.6)
- L5-H ACCEPT report (2026-05-13) — no new L5b-7 bullet added at L5-H (Strategic-approved D-H-1 through D-H-5 are all spec-literal-faithful resolutions of Strategic-prompt-vs-spec divergence at L5-H; no narrative drift to backlog). Provenance entry recorded here for L5 chain closure traceability.
- AP-AUTH-52 codified at `docs/ap_register.md` (sibling discipline)
- D-B1-1 / D-B1-2 / D-B1-3 + D-D-1 / D-D-2 + D-E-1 + D-G-1 Strategic dispositions (Track B chat, 2026-05-13)

---

**END — L5B_BACKLOG.md (L5b-2 + L5b-3 + L5b-4 + L5b-5 + L5b-6 + L5b-7 as of 2026-05-13 post-`layer5-complete`; reserved L5b-1 + L5b-8..N open for L5b OOS hardening sprint)**
