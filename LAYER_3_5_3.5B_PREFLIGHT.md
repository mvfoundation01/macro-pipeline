# LAYER 3.5B — Pre-Flight Audit (PIT Enforcement, Option Z)

**Spec ref**: `LAYER_3_5_BUILD_SPEC.md` §4 (3.5B)
**Branch**: `claude/layer-3-5-build` @ `fffaff4` (3.5A complete + AM6 closeout)
**Date**: 2026-05-09
**Author**: Claude Code (build agent)
**Status**: PROCEED-WITH-Dxx if config disposition is Option C+; PAUSE-required only if scope expands

---

## §1 — Audit Result Header

| Field | Value |
|---|---|
| Sub-phase | 3.5B — PIT Enforcement, Option Z |
| Estimated effort (spec) | 3–5h |
| My estimate after audit | **3.5–4.5h** (within range) |
| Tests added (spec target) | +6 (4 NEG / 2 POS) |
| Gate added | Gate 13 |
| Locked decisions (3.5B-D1..D4) | 0.70 cap (D1), MIN aggregation as upper bound (D2/D4), rationale required (D3) |
| Smoke-test result | spec default 0.70 binds appropriately at all 4 anchors → **no D21 needed** |
| Anticipated deviations | None unless config disposition is Option B |
| Conviction (statistical / operational / actionability) | 0.85 / 0.78 / 0.85 — see §10 |

---

## §2 — Empirical Smoke-Test (per spec §2.3 + §4.2)

CRPS confidence at 4 anchor dates with **current** code (pre-3.5B). Anchors 1998/2001/2008/2020 selected because BAMLH0A0HYM2 starts 1996-12 (1990 anchor in spec is unreachable; documented as Path B reality).

| as_of | CRPS score | confidence [0–100] | conf [0–1] | final_quality_cap | 0.70 cap binds? | post-cap conf [0–1] |
|---|---|---|---|---|---|---|
| 1998-08-01 (LTCM era) | 0.3094 | 72.46 | 0.7246 | 0.7500 | **YES** | 0.7000 |
| 2001-04-01 (post-tech) | 0.2794 | 70.21 | 0.7021 | 0.7500 | **YES** | 0.7000 |
| 2008-09-15 (Lehman) | 0.5495 | 72.46 | 0.7246 | 0.7500 | **YES** | 0.7000 |
| 2020-04-01 (COVID) | 0.3153 | 72.46 | 0.7246 | 0.7500 | **YES** | 0.7000 |

**Cap-binding magnitude**: shaves **0.02 – 0.025** off the headline at all 4 anchors. Cap is a meaningful upper bound in the spec §4.6 sense ("high but not unrestricted").

**Verdict**: spec-locked default of 0.70 is empirically appropriate.
- Difference from default: 0.0 (we don't move the cap).
- Per Standing Orders empirical-calibration override band: ≤0.05 → ADOPT default. **No D21 deviation needed.**

The existing `final_quality_cap=0.7500` is the `tradingview_csv` source-quality cap (per `models/quality_caps.py`); adding `derived_confidence_cap=0.70` to the MIN aggregation will produce `MIN(0.75, 0.70) = 0.70`. The new cap will bind tighter than the existing chain, which is the intended Option Z effect.

---

## §3 — Spec §4.2 + §2.2 Mandatory Items

### §3.1 Item 1 — Files this sub-phase will touch

| File | Action | Existing lines | Notes |
|---|---|---|---|
| `macro_pipeline/config.py` | MODIFY | line 119–139 (`SAHMREALTIME` block) | Add 3 keys: `pit_safe_by_construction=True`, `pit_construction_rationale="..."`, `derived_confidence_cap=0.70`. **DO NOT** change `vintage` from True → False (spec §4.3-2 says CHANGED, but downstream code paths still use `vintage` flag for routing — see AM10 below). |
| `macro_pipeline/loaders/base.py` (or relevant) | MODIFY | TBD (need locate) | Extend `IndicatorMetadata` to carry the 3 new keys via `extra` dict (already supported) so they propagate to the cache sidecar. |
| `macro_pipeline/loaders/fred_loader.py` | MODIFY | line ~240 (extra-keys block) | Add the 3 new keys to the `extra` dict iteration. |
| `macro_pipeline/access.py` | MODIFY | line 285–321 (`_load_via_visibility_shift`) | Replace silent fallback with explicit branching: vintage panel | pit_safe_by_construction | RAISE `PitContractViolationError`. Three cases, one error class. |
| `macro_pipeline/access.py` | MODIFY | line 54 (`IndicatorBundle`) | Add `pit_safe_basis: str` (default "n/a") + `derived_confidence_cap: float \| None` + `notes: list[str]` fields. |
| `macro_pipeline/regime/exceptions.py` | MODIFY | OR new module | Add `PitContractViolationError` class. (Putting it in `regime/exceptions.py` is awkward since access.py is at package root; recommend new module `macro_pipeline/exceptions.py` for cross-cutting exceptions, OR co-locate in `access.py`.) |
| `macro_pipeline/utils/pit_audit.py` | NEW | n/a | Audit utility per spec §4.3-5; CLI runnable. |
| `macro_pipeline/utils/__init__.py` | NEW | n/a | Make `utils` a package (currently does not exist). |
| `macro_pipeline/models/quality_caps.py` | MODIFY | line 176 (`AppliedCaps`), line 194 (`compute_final_confidence_cap`), line 188 (`aggregate_caps`) | Add `derived_confidence_cap` field; populate from meta; participate in MIN aggregation. |
| `macro_pipeline/scoring/crps.py` | MODIFY | line 269 (`_compute_quality_cap`), line 380–415 | Plumb the new cap through. |
| `macro_pipeline/scoring/cdrs.py` | MODIFY | (analog `_compute_quality_cap` block) | Same as CRPS. |
| `macro_pipeline/scoring/scored_observation.py` | LIKELY UNTOUCHED | n/a | `ScoredObservation.metadata_extra` already accommodates the new lineage; no schema change. **Caveat**: spec §4.3-4 says "visible in `ScoredObservation.notes`". The dataclass has no `notes` field. I will surface via `metadata_extra["pit_safe_basis"]` and `metadata_extra["derived_confidence_cap_applied"]` — see AM12. |
| `macro_pipeline/scoring/README.md` | MODIFY | append §D20 | Reference + rationale per spec §4.3-6. |
| `macro_pipeline/validation.py` | MODIFY | append `validate_gate13_*` after `validate_gate12_*` | Plus `_cli_gate13` + `__main__` route. |
| `tests/test_pit_enforcement.py` | NEW | n/a | 6 new tests per spec §4.5. |

### §3.2 Item 2 — Existing tests that may break

| Test | Risk | Disposition |
|---|---|---|
| `tests/test_pit_hlw.py::test_hlw_rstar_pit_does_not_emit_fallback_warning` | Asserts NO fallback warning for HLW_RSTAR. After 3.5B the fallback branch is gone (replaced with explicit branching). HLW_RSTAR routes via `_load_via_hlw_vintage` which is unchanged → test still passes. | LOW — verify post-impl |
| `tests/test_sahm_classification.py` (6 tests) | Read SAHMREALTIME spec dict keys (`signal_type`, `valid_uses`, etc.). Adding new keys does not remove existing keys → tests still pass. | LOW — no change expected |
| `tests/test_crps.py` (16 tests including `test_compute_crps_pit_safety_lineage`) | CRPS at PIT-safe anchor with SAHM contributing. After 3.5B, SAHM's bundle will carry `pit_safe_basis="by_construction"` instead of `pit_safe=True` (silent). Tests assert `pit_safe is True`; that should still be True. Tests assert `pit_source` is in {"vintage_panel", "release_lag", ...}; need to ensure new value `"by_construction_latest"` is in the allowed set OR existing tests use a less-strict assertion. | MEDIUM — review during impl |
| `tests/test_cdrs*.py` | Same pattern. | MEDIUM |
| `tests/test_fred_loader.py` | If sidecar metadata schema changes (new keys), assertions on metadata may fail. | LOW — adding keys, not removing |
| `tests/test_atomic_cache.py` | Cache schema_version validation. We're not bumping schema; new keys go in `extra` which is not part of the SCHEMA_VERSION contract. | LOW |
| Tests touching `access.py::_load_via_visibility_shift` | Specifically tests that exercise SAHM via PIT mode. The fallback warning text (line 294-298) is being removed; any test checking for that warning text would break. Earlier `grep needs_vintage tests/` showed only `test_pit_hlw.py` (which asserts ABSENCE) and the SAHM classification tests (which don't touch the warning). | LOW |

**Net impact**: no test deletions expected; minor adjustments possible on `pit_source` allowed values. Will reverify by running pytest immediately after each commit.

### §3.3 Item 3 — Empirical reading (per spec §2.3 / §4.2)

DONE in §2 above. Spec default 0.70 binds appropriately. No D21 needed.

### §3.4 Item 4 — Ambiguities

| ID | Ambiguity | Spec ref | Proposed resolution | Decision needed? |
|---|---|---|---|---|
| **AM10** | Spec §4.3-2 prescribes `vintage=False, needs_vintage=False, pit_safe_by_construction=True` for SAHMREALTIME. But the existing dict-based config uses `vintage=True` to ROUTE through `_load_via_visibility_shift` (and downstream code depends on that). Setting `vintage=False` would route SAHMREALTIME through the regular non-vintage path, **bypassing** the new `pit_safe_by_construction` branch. The cleanest reading: keep `vintage=True` (preserves routing) AND set `pit_safe_by_construction=True` (signals Option Z); the **new branching logic in `_load_via_visibility_shift` then chooses based on `pit_safe_by_construction` flag**. | §4.3-2 vs §4.3-3 | Keep `vintage=True`; add `pit_safe_by_construction=True`. Branching in access.py keys off the new flag. | **YES — confirmation requested.** |
| **AM11** | `SeriesConfig` dataclass does NOT exist in current codebase. Spec §4.3-1 prescribes one with `__post_init__` validation. `FRED_SERIES_API` is a `dict[str, dict]` with 80+ entries; introducing the dataclass would force migration of all 80+. Three options: A (introduce dataclass + migrate ONLY SAHMREALTIME), B (full migration), **C+ (extend dict pattern with new keys + standalone validation function)**. | §4.3-1 | **Option C+ recommended** — minimal scope, consistent with how prior L1.5C extension keys were added (`signal_type`, `valid_uses`). Validation runs at module import time via a `_validate_pit_construction_consistency()` helper. | **YES — confirmation requested.** |
| **AM12** | Spec §4.3-4 says cap propagation must be "visible in `ScoredObservation.notes` field downstream". The dataclass has `metadata_extra: dict`, NOT a `notes` field. Adding a `notes: list[str]` field would be a 3.5D concern (spec §6.3-4 introduces it). | §4.3-4 vs §6.3-4 | Surface in `metadata_extra["pit_safe_basis"]` + `metadata_extra["derived_confidence_cap_applied"]`. 3.5D will introduce the proper `notes` field; we migrate the metadata_extra entries to `notes` then. | NO — clear procedural fix; documented for cross-phase coordination. |
| **AM13** | Where to put `PitContractViolationError`? Options: (a) `regime/exceptions.py` (existing exceptions module but regime-namespaced), (b) `access.py` (alongside the raising code), (c) new `macro_pipeline/exceptions.py` (cross-cutting). | §4.3-3 | **(c) new `macro_pipeline/exceptions.py`**, parallel to `regime/exceptions.py`. PIT contract is a cross-cutting infrastructure concern, not a regime-specific one. Future PIT-related exceptions go there too. | **YES — confirmation requested** if you have a preference. Recommendation: (c). |
| **AM14** | `pit_audit_report` dataclass shape: spec §4.3-5 sketches fields but does not name. Does it return `PitAuditReport` (PascalCase) dataclass or a plain dict? | §4.3-5 | Use a `@dataclass(frozen=True)` `PitAuditReport` per the type-hint example in spec. | NO — clear from spec text. |
| **AM15** | Spec §4.3-3 raises `PitContractViolationError` for "needs_vintage=True but neither flag (1)/(2)". With AM10 disposition (keep `vintage=True` AND new flag), the trigger condition becomes: `if vintage=True AND not in panel AND not pit_safe_by_construction`. Need to verify NO other vintage=True series falls into this trap (audit done in §3.5 below). | §4.3-3 | Confirmed via audit (§3.5) — only SAHMREALTIME would currently hit this branch, and we're flagging it Option Z. Other 10 vintage=True series are all in `VINTAGE_REQUIRED_SERIES`. So post-3.5B the audit utility returns 0 mismatches, and the raise branch is unreachable from current config. | NO — audit confirms safety. |

### §3.5 Item 5 — Risk callouts

| ID | Risk | P(occurrence) | Impact | Mitigation |
|---|---|---|---|---|
| R-3.5B-1 (REVISED) | SAHMREALTIME spec uses dict pattern; spec §4.3 assumes dataclass. | 100% (verified) | None if Option C+ chosen. | Option C+ — see §3.4 AM11. |
| R-3.5B-2 | `_load_via_visibility_shift` removal of fallback could break series that legitimately need lag-shift behavior (e.g., non-vintage with `release_lag_days > 0`). | LOW 5% | If branching is wrong, gates 8/9/10 fail. | Branching logic preserves existing behavior for the (lag>0, !vintage) path. Tests cover this. |
| R-3.5B-3 | Cache sidecar metadata bumps may invalidate existing parquet caches (schema_version mismatch). | LOW–MED 15–20% | Caches re-fetch on next load. | New keys go in `extra` dict, not part of SCHEMA_VERSION 1.0 surface; no schema bump. |
| R-3.5B-4 | Spec §4.6 Gate 13 #3 prescribes "Removing the flag from SAHMREALTIME (in-memory config mutation in test) causes Gate 13 to fail". This requires the gate to be sensitive to in-memory mutations. Need to ensure the gate reads `FRED_SERIES_API` directly (not a frozen import-time snapshot). | LOW 5% | If gate uses snapshot, this test cannot be written. | Gate 13 reads live config dict; in-memory mutation works. |
| R-3.5B-5 | Vintage panel materialization status check during audit may be flaky if the panel parquets have stale sha. | LOW 10% | Audit reports false-positive mismatch. | Audit checks `series in VINTAGE_REQUIRED_SERIES` (a tuple constant), not whether the panel parquet is on disk. |
| R-3.5B-6 (audit confirms safe) | Other Option Z candidates beyond SAHMREALTIME might surface during audit. | 0% (audit done — see below) | If found, would PAUSE per Standing Orders. | Audit complete; only SAHMREALTIME qualifies. |

### §3.5.1 — `vintage=True` inventory (R-3.5B-6 audit)

| Series | `vintage=True` in config | In `VINTAGE_REQUIRED_SERIES` (panel materialized)? | Disposition (post-3.5B) |
|---|---|---|---|
| PAYEMS | ✓ | ✓ | unchanged — vintage panel path |
| JTSQUR | ✓ | ✓ | unchanged |
| INDPRO | ✓ | ✓ | unchanged |
| RSAFS | ✓ | ✓ | unchanged |
| RRSFS | ✓ | ✓ | unchanged |
| CFNAIMA3 | ✓ | ✓ | unchanged |
| PCEPILFE | ✓ | ✓ | unchanged |
| GFDEGDQ188S | ✓ | ✓ | unchanged |
| A091RC1Q027SBEA | ✓ | ✓ | unchanged |
| FGRECPT | ✓ | ✓ | unchanged |
| **SAHMREALTIME** | ✓ | ✗ | **Option Z** (this sub-phase) |

**11 series total. 10 in panel, 1 needs Option Z. Only SAHMREALTIME qualifies.** No additional Option Z candidates surfaced. PAUSE-required ambiguity from Standing Orders ("audit reveals additional Option Z candidates beyond SAHMREALTIME") is **NOT triggered.**

### §3.6 Item 6 — Effort estimate

| Step | Estimate (h) |
|---|---|
| Author this pre-flight | 0.4 |
| Address ambiguities AM10, AM11, AM13 (V approval) | gate |
| `config.py` SAHMREALTIME 3-key extension + validation function | 0.3 |
| `access.py` `_load_via_visibility_shift` refactor + new branching + `IndicatorBundle` extension | 0.7 |
| `macro_pipeline/exceptions.py` new module + `PitContractViolationError` | 0.2 |
| `loaders/fred_loader.py` extra-keys propagation | 0.2 |
| `models/quality_caps.py` `AppliedCaps` extension + `aggregate_caps` extension + `compute_final_confidence_cap` plumb | 0.4 |
| `scoring/crps.py` + `scoring/cdrs.py` plumb derived cap | 0.4 |
| `scoring/README.md` §D20 | 0.2 |
| `utils/pit_audit.py` + `utils/__init__.py` + CLI | 0.5 |
| Gate 13 in `validation.py` + CLI | 0.4 |
| 6 new tests in `tests/test_pit_enforcement.py` | 0.7 |
| Smoke-test confirmation post-impl (CRPS at 4 anchors, cap binding 0.70) | 0.2 |
| Run pytest, ruff, gates | 0.2 |
| Verification report | 0.3 |
| **Total** | **3.9–4.5** | within spec's 3–5h range |

---

## §4 — Decisions Locked Per Standing Orders

All 21 spec decision points use spec-locked defaults:

| Decision | Locked default |
|---|---|
| 3.5B-D1 (cap value) | 0.70 |
| 3.5B-D2 (cap is upper bound, not floor) | upper bound |
| 3.5B-D3 (rationale required) | YES (validation) |
| 3.5B-D4 (cap aggregation) | MIN |

Empirical smoke-test (§2) confirmed D1=0.70 binds appropriately → no D21 needed.

---

## §5 — Decisions Requested From V / Strategic (BEFORE Coding)

### §5.1 AM10 — `vintage` flag dual-purpose

| Option | Description |
|---|---|
| **A (recommended)** | Keep `vintage=True` (preserves routing through `_load_via_visibility_shift`); add `pit_safe_by_construction=True`. New branching in access.py keys off the construction flag to choose between vintage-panel / option-Z-latest / raise. |
| B | Set `vintage=False` (per spec §4.3-2 literal); reroute SAHMREALTIME through `_load_via_visibility_shift` via a separate `pit_safe_by_construction` check at the top of the dispatcher, before the vintage-panel branch. Requires inserting a new branch in `PitSeriesReader.load`. |

Both achieve the spec intent. **A** is a smaller diff. **B** is closer to spec literal. **Recommend A.**

### §5.2 AM11 — config pattern for new keys (Option A vs B vs C+)

| Option | Description | Effort | Risk |
|---|---|---|---|
| A | Introduce `SeriesConfig` dataclass; migrate ONLY SAHMREALTIME; rest stays dict. | MED (~1h) | MED — parallel patterns, future migration debt. |
| B | Full migration of all 80+ FRED + 22 TV + others to dataclass. | HIGH (~6–8h, scope creep) | HIGH — out of L3.5B scope. |
| **C+ (recommended)** | Extend dict pattern with 3 new keys. Validation function `_validate_pit_construction_consistency()` runs at config import. | LOW (~0.3h) | LOW — proven pattern (mirrors L1.5C extensions). |

**Recommend C+.** Per Standing Orders, this is a PROCEED-WITH-Dxx scenario (file Dxx noting we deferred dataclass migration to a later sub-phase or backlog item).

### §5.3 AM13 — `PitContractViolationError` location

| Option | Description |
|---|---|
| **(c) recommended** | New `macro_pipeline/exceptions.py` (parallel to `regime/exceptions.py`). PIT contract is cross-cutting; exception class belongs at the package root namespace. |
| (a) | `regime/exceptions.py` (regime-scoped — but PIT is broader than regime). |
| (b) | Inline in `access.py` (works but couples class to module). |

**Recommend (c).**

---

## §6 — Anticipated Dxx filing

| ID | Topic | Trigger | Note |
|---|---|---|---|
| (D21 NOT needed) | confidence-cap empirical override | smoke-test §2 shows default binds | spec default 0.70 stands |
| **D21 (likely)** | Config dataclass deferral to a later sub-phase | Option C+ chosen → spec §4.3-1 dataclass form not implemented in this sub-phase | ACCEPT; rationale: scope discipline, dict-based pattern is already idiomatic in this codebase. L5 backlog item: full SeriesConfig migration if/when justified. |
| (other) | TBD during impl | n/a | n/a |

---

## §7 — Implementation Order (post-approval)

1. Add `PitContractViolationError` in new `macro_pipeline/exceptions.py`.
2. Extend `IndicatorBundle` (access.py) with `pit_safe_basis`, `derived_confidence_cap`, `notes` fields.
3. Update SAHMREALTIME spec in `config.py`: add 3 new keys; add `_validate_pit_construction_consistency()` running at module import.
4. Update `loaders/fred_loader.py`: extras-loop includes the 3 new keys so they reach the cache sidecar.
5. Rewrite `access.py::_load_via_visibility_shift` with explicit 3-way branching (vintage_panel | by_construction | RAISE).
6. Extend `models/quality_caps.py`: `AppliedCaps.derived_confidence_cap` + plumbed in `compute_final_confidence_cap` + included in `aggregate_caps` MIN.
7. Plumb derived cap through `scoring/crps.py::_compute_quality_cap` and `scoring/cdrs.py` analog.
8. Add `utils/pit_audit.py` + `utils/__init__.py` + CLI entry.
9. Add `validate_gate13_pit_contracts()` + CLI in `validation.py`.
10. Update `scoring/README.md` §D20.
11. Write 6 new tests in `tests/test_pit_enforcement.py`.
12. Run smoke-test post-impl: confirm CRPS confidence at 4 anchors clamps to 0.70.
13. Full pytest + ruff + all 13 gates.
14. Commit.
15. Compose verification report per §4.7 proof contract (11 items).
16. PAUSE.

---

## §8 — Test plan preview (6 new)

| # | Test | Type | What it asserts |
|---|---|---|---|
| 1 | `test_pit_reader_sahm_returns_with_construction_flag` | POS | `read("SAHMREALTIME")` → bundle has `pit_safe=True`, `pit_safe_basis="by_construction"`, `derived_confidence_cap=0.70`, `notes` includes the cap rationale |
| 2 | `test_pit_reader_unflagged_vintage_series_raises` | NEG | Mock series with `vintage=True`, not in panel, no flag → `PitContractViolationError` |
| 3 | `test_pit_audit_finds_no_mismatches_post_3_5B` | POS | `audit_pit_contracts()` returns 0 mismatches against current config |
| 4 | `test_crps_with_sahm_caps_overall_confidence_70` | POS | At 2008-09-15, CRPS confidence ≤ 0.70 (smoke-test §2 confirmed pre-impl this would clamp from 0.7246) |
| 5 | `test_pit_safe_by_construction_requires_rationale` | NEG | `_validate_pit_construction_consistency` raises ValueError if rationale missing/empty |
| 6 | `test_layer_6_displays_construction_caveat_in_notes` | POS | `ScoredObservation.metadata_extra["pit_safe_basis"]` for SAHM-derived score is "by_construction"; metadata_extra["derived_confidence_cap_applied"] = 0.70 |

NEG/POS split: 2 NEG / 4 POS. **Below the 50% NEG floor of spec §2.7.** Will add 1-2 more NEG tests during impl to meet target — likely candidates:
- `test_pit_reader_construction_flag_without_vintage_logs_warning` (NEG-style)
- `test_aggregate_caps_min_includes_derived_cap` (NEG variant: missing cap doesn't break MIN)

Final NEG/POS will be 4/4 to satisfy ≥50% NEG.

---

## §9 — Proof Contract Mapping (11 items, spec §4.7)

| Spec proof # | How I will demonstrate |
|---|---|
| 1 | `python -m macro_pipeline.utils.pit_audit` stdout shows 0 mismatches |
| 2 | `pytest tests/test_pit_enforcement.py -v` summary line |
| 3 | `git diff config.py` showing `pit_safe_by_construction=True`, rationale ≥100 chars, cap=0.70 |
| 4 | CRPS confidence at 4 anchors post-impl: report 4 values all ≤ 0.70 (paste table) |
| 5 | `git diff access.py` showing `_load_via_visibility_shift` rewritten — fallback branch removed, explicit branching present |
| 6 | `cat scoring/README.md` §D20 |
| 7 | `python -m macro_pipeline.utils.pit_audit` stdout |
| 8 | `python -m macro_pipeline.validation gate13` output |
| 9 | Full pytest passes (516 + 6 = 522 minimum, expect 523-524 with NEG additions) |
| 10 | Cumulative test count |
| 11 | §10 of this document, refreshed at verification time |

---

## §10 — Pre-flight conviction (3-field, per spec §2.4)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | **0.85** | High: smoke-test confirmed cap binds at all 4 anchors (no surprise). Slight haircut because cross-phase plumbing (cap → quality_caps → CRPS → CDRS) crosses 4 modules and one schema. |
| `conviction_operational` | **0.78** | Medium-high: vintage-series inventory clean (only SAHMREALTIME); existing tests low-risk; but the dataclass-vs-dict ambiguity (AM11) needs V's explicit signoff — until then operational confidence is bounded. **Binding.** |
| `conviction_actionability` | **0.85** | High: post-3.5B the look-ahead bias from silent SAHM fallback is closed at the substrate level; L5 walk-forward CV can fit Ridge weights against confidence-capped CRPS without ambiguity. |

Aggregate `confidence_overall` (per L1.5 §7.6 caps): **0.78** (operational binding).

---

## §11 — END

Pre-flight complete. **PAUSED** awaiting:
1. APPROVE (recommendations: AM10=A, AM11=C+, AM13=c — proceed with implementation per §7), OR
2. REVISE (specify alternative for any of AM10, AM11, AM13).

Per Standing Orders + `HANDOFF_CLAUDE_CODE_v3.md` §3, the C+ disposition (AM11) is a PROCEED-WITH-Dxx scenario (Standing Orders §"Ambiguity routing"); however because it touches a spec literal (§4.3-1 dataclass), I am surfacing it explicitly as decision-required rather than auto-Dxx-ing.

If any of AM10/11/13 is REVISE: I'll incorporate before coding.
If APPROVE: I'll execute §7 order, expecting 4–4.5h actual time.
