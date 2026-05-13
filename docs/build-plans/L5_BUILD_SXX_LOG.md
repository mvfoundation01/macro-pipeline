# L5 Build-Time Sxx Log

**Branch**: `claude/layer-5-build`
**Authoring agent**: Track A (Claude Code)
**Reserved range**: S-10 through S-25 (build-time; spec authoring used S-1..S-9 per `LAYER_5_BUILD_SPEC.md` §10)
**Format**: per build plan v1 §5.4 (`L5_BUILD_PLAN_v1.md` on `claude/layer-5-build-plan`)

---

## S-10 — 2026-05-13 — sub-phase L5-B Task A — component_panel not in L3 export surface

**Trigger**: T1 (spec ambiguity / spec-vs-implementation gap discovered at code-exec time)

**Disposition**: **CONDITIONAL** — awaiting Strategic decision per L5-B Task A code-exec prompt PHASE 0 decision tree

**Rationale**: Spec `LAYER_5_BUILD_SPEC.md` v6 §5.B.1.1 line 663-673 (`fit_composite_weights`) requires `component_panel: pd.DataFrame` as Task A's primary input — "Component-level feature matrix — CRPS: 6 components (yield curve + Sahm + LEI + ISM + FCI + credit); CDRS: 4 buckets (valuation + sentiment + credit/liquidity + vol/breadth/technical)" (spec line 587). Phase 0 grep audit at L5-B Task A code-exec kickoff confirms:

1. **No `component_panel` literal reference** anywhere in the codebase (`rg 'component_panel|component_features|component_matrix'` returns 0 files; only this log entry post-filing).
2. **CRPS partial component-level surface exists but not as panel artifact**: `scoring/crps.py` has `COMPONENT_INDICATOR` dict (6 keys), `LAYER3_ACTIVE_COMPONENTS` list (4 keys), `_load_component()` function that loads ONE component PIT-safe per `as_of` timestamp. No panel artifact (DataFrame keyed by date × component_id). Lines 14-22 of `scoring/crps.py` explicitly document that L3 uses Path B 4-component active subset because `ism_pmi_neworders` (NAPMNOI) returns FRED 400 and `lei_3d_rule` (CB LEI) has no Tier 1-4 loader.
3. **CDRS structure mismatched with spec "4 bucket" framing**: `scoring/cdrs.py` uses `V × T × R` formula where `V` = mean of 5 vulnerability percentiles, `T` = mean of trigger transforms, `R` = regime multiplier ∈ {0.6, 1.0, 1.4}. Per-`as_of` computation pattern, not panel artifact. Spec's "4 buckets (valuation + sentiment + credit/liquidity + vol/breadth/technical)" does NOT map cleanly to V/T/R sub-structure.
4. **L3D `r_squared_panel.py::build_panel()` produces an unrelated panel**: 124 indicators × 4 horizons × 2 targets keyed by `(indicator_id, target_id, horizon)`. Not a CRPS/CDRS component panel.

Per L5-B Task A pre-flight (`claude/layer-5-build-plan @ 9a25619` ITEM 4 row 2): risk #2 "Component panel not exported by L3" rated severity HIGH at 30% probability. Outcome: **RISK REALIZED**.

**Resolution path**: PATCH-IMPL (preferred) OR DEFER (alternative)

Three options per prompt PHASE 0 decision tree CASE C (verbatim):
| # | Option | Effort impact | Methodology impact |
|---|---|---|---|
| (i) | DEFER L5-B Task A until L3 patch | L3 patch is itself a scope expansion (build panel artifact in L3 that L5-B consumes); +4-8h L3 work | None for L5-B; L3 spec gains a new artifact-export contract |
| (ii) | AUTHORIZE component_panel construction WITHIN Task A scope | +1-2h Task A implementation (helper `build_component_panel(panel_index, score_type)` calling existing `_load_component()`-equivalents per-date in a loop); Task A budget 6.75h → 8.0-8.75h (still within L5-B 12-16h umbrella) | Task A implements the spec's `component_panel` input contract (rather than consume it); spec §5.B.1 still satisfied. CRPS 4-component subset acknowledged (matches L3 reality; not 6 components); CDRS V/T/R → 4-bucket mapping needs Strategic clarification |
| (iii) | OTHER (e.g., partial-Task-A: implement function signature + dataclass; defer integration test that requires real component_panel) | +0.5h Task A; partial closure | Task A's tests A2, A3 (event label compliance against real labels) couldn't fully verify on synthetic component_panel; weaker closure of L5-RISK-2 |

**Recommendation (Track A's prior)**: option (ii) — authorize component_panel construction within Task A scope, with explicit Strategic clarification on CRPS 6→4 component drift (use L3 reality 4 active components; cite `LAYER3_ACTIVE_COMPONENTS`) and CDRS V/T/R → 4 bucket mapping (Strategic to decide: a) keep CDRS as 3-stage V×T×R input matrix; b) decompose V into 5 sub-percentile columns + T into trigger columns to approximate 4-bucket framing; c) other).

**Strategic decision**: **RESOLVED** 2026-05-13 — Strategic chose **Option (iv) HYBRID** (variant of option (ii)): minimal L3 patch shipping `component_panel` export, 4-active-component CRPS subset, ISM + LEI deferred to backlog L5b-2.

**Resolution**: L3 component_panel patch landed at commit `60f18033e24f115ddf30d8659e76ebd91b16612d` on branch `claude/layer-5-l3-component-patch` (off `claude/layer-5-build` @ `711f641`). Phase 2 implementation: `macro_pipeline/analysis/component_panel.py` (NEW) + `tests/test_component_panel.py` (6 tests; 4 NEG / 2 POS = 67%) + export wiring in `macro_pipeline/analysis/__init__.py`. CDRS bucket mapping per design doc v2 §C (Option B; Strategic confirmed). PIT discipline preserved.

**Resolution date**: 2026-05-13

**Backlog spawned**: **L5b-2** — ISM New Orders (NAPMNOI) + CB LEI loaders, ~4-8h effort, MED priority. See `docs/build-plans/L5B_BACKLOG.md`.

**Status**: **RESOLVED**.

**Build artifact**: L3 component_panel patch branch `claude/layer-5-l3-component-patch` @ `60f1803`; merge to build branch + tag `l3-component-patch` per L5-B Task A retry pre-flight authorization.

---

**END — L5_BUILD_SXX_LOG.md (S-10 RESOLVED; cumulative count 10; reserved range 11-25 open)**
