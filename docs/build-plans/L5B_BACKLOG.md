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

**END — L5B_BACKLOG.md (L5b-2 only as of 2026-05-13; reserved L5b-1 + L5b-3..N open)**
