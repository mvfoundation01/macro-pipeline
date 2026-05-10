# LAYER 3.5b-V — Verification Report (Broader AP-6 Narrowing Sweep)

**Branch**: `claude/layer-3-5b-build` (commit pending)
**Base**: `e92a714` (3.5b-U complete)
**Date**: 2026-05-10
**Author**: Claude Code (build agent)
**Status**: PAUSED awaiting V verification per `HANDOFF_CLAUDE_CODE_v4.md` §2

---

## §1 — Header

| Field | Value |
|---|---|
| Sub-phase | 3.5b-V — Broader AP-6 Narrowing Sweep |
| Spec ref | L3.5b inline spec §5 |
| Codex finding closed | **V (MED)** — broad `except Exception:` blocks across scoring/regime tree |
| Sites narrowed | **21** (5 V1-V5 + 5 T1-T5 + 6 kindleberger + 4 dalio + 1 D27 consolidation) |
| Tests delta | **+5 new** (566 → 571); zero regressions; 1 existing test updated for the side-fix (`test_pit_pre_2015_raises` exception type) |
| Gates touched | Gate 13 + Gate 15 + Gate 16 still PASS (Gate 16 sub-criterion 4 updated to accept helper pattern); Gate 17 sub-criterion 3 satisfied |
| Deviation filed | **D30** (per AM-3.5b-V-1=Comprehensive APPROVED — all 21 sites use shared `legitimate_missing_data_exceptions()` helper) |
| L5 backlog | **L5-14** NEW — comprehensive AP-6 hygiene sweep across 16 out-of-scope sites (loaders, validation, math fallbacks) |
| Effort actual | ~2.7h (vs 2.4h pre-flight estimate; +0.3h for the regression remediation side-fix in `hlw_rstar_vintage.py`) |

---

## §2 — Empirical / smoke-test (post-impl)

### §2.1 21-site narrowing application — grep proof (per new Standing Order)

```
$ grep -c "except Exception" macro_pipeline/scoring/cdrs_vulnerability.py
0
$ grep -c "except Exception" macro_pipeline/scoring/cdrs_trigger.py
0
$ grep -c "except Exception" macro_pipeline/regime/kindleberger.py
0
$ grep -c "except Exception" macro_pipeline/regime/dalio_cycle.py
0
$ grep -c "legitimate_missing_data_exceptions" macro_pipeline/
exceptions.py:                       2  (def + __all__)
regime/dalio_cycle.py:               5  (1 import + 4 sites)
regime/kindleberger.py:              7  (1 import + 6 sites)
regime/regime_context.py:            3  (1 inline import + 1 use + 1 docstring)
scoring/cdrs_trigger.py:             6  (1 import + 5 sites)
scoring/cdrs_vulnerability.py:       6  (1 import + 5 sites)
loaders/hlw_rstar_vintage.py:        1  (PitDataUnavailableError side-fix mention)
```

**Net**: 5 (V) + 5 (T) + 6 (kindleberger) + 4 (dalio) + 1 (D27) = **21 narrowing sites** confirmed via grep. Zero residual `except Exception:` in the 4 Codex-flagged files.

### §2.2 D27 consolidation diff

Before (3.5E D27 era):
```python
try:
    hmm_result = predict_state(ctx)
except (
    HmmArtifactMissingError,
    HmmArtifactCorruptError,
    HmmMetadataIncompatibleError,
) as exc:
    hmm_result = None
    notes.append(f"hmm: {type(exc).__name__}: {exc}")
```

After (3.5b-V D30 consolidation):
```python
from macro_pipeline.exceptions import legitimate_missing_data_exceptions
try:
    hmm_result = predict_state(ctx)
except legitimate_missing_data_exceptions() as exc:
    hmm_result = None
    notes.append(f"hmm: {type(exc).__name__}: {exc}")
```

The helper tuple adds `PitDataUnavailableError` to the caught types. **Empirical impact at D27 site = zero** — `predict_state` doesn't raise `PitDataUnavailableError` in current paths (only `regime/nber_extract.py` raises it; the HMM feature load path uses `load_series` which doesn't raise that type). The D27 empirical case (`RegimeClassifierError` for filelock-missing) still propagates correctly — that type is NOT in the helper.

**Verified by POS regression test #5** (`test_d27_site_still_propagates_regime_classifier_error_post_consolidation`): a synthetic `RegimeClassifierError` raised by `predict_state` propagates out of `build_regime_context` (fail-loudly contract preserved).

### §2.3 Side-fix: `get_pit_rstar` exception type (regression remediation)

Mid-impl smoke at as_of=2008-09-15 (canonical anchor) regressed: `compute_cdrs(ctx)` raised `ValueError("No HLW vintage available on or before 2008-09-15...")` from `loaders/hlw_rstar_vintage.py:233`. Pre-3.5b-V the broad `except Exception` in `dalio_cycle._compute_metrics::HLW_RSTAR site` silently swallowed it; post-narrowing the unhelpered `ValueError` propagates.

**Root cause**: the raised exception type was conceptually mismatched. "No vintage panel available before 2015Q4" is a "PIT data missing" semantic, not a generic ValueError. **Surgical fix**: change `get_pit_rstar` to raise `PitDataUnavailableError` instead of bare `ValueError`. The helper tuple includes `PitDataUnavailableError` → caught at the dalio HLW_RSTAR site → graceful "missing component" degradation.

This is a clean architectural improvement: matches the established pattern (NBER extract raises `PitDataUnavailableError` for pre-1978 PIT lookups; HLW vintage now raises the same type for pre-2015Q4 PIT lookups). One test updated (`test_official_4d.py::test_pit_pre_2015_raises` from `pytest.raises(ValueError)` to `pytest.raises(PitDataUnavailableError)`).

### §2.4 Gate 16 sub-criterion 4 update

Gate 16's sub-criterion 4 (originally added at 3.5E) checked for the inline narrow tuple at `regime_context.py:295`. After consolidation to helper, the inline tuple is gone — the check needed updating to accept either pattern:

```python
rc_narrow_ok = "except Exception" not in rc_around and (
    # Pre-3.5b-V D27 inline-tuple form (still acceptable)
    (
        "HmmArtifactMissingError" in rc_around
        and "HmmArtifactCorruptError" in rc_around
        and "HmmMetadataIncompatibleError" in rc_around
    )
    # Post-3.5b-V D30 consolidated helper form
    or "legitimate_missing_data_exceptions" in rc_around
)
```

Backward-compatible by design. Gate 16 PASS post-update.

### §2.5 Empirical post-impl smoke-test

```
At as_of=2008-09-15 (canonical anchor):
  rc.hmm.state          = late-cycle
  rc.kindleberger.phase = revulsion
  rc.dalio.phase        = late
  derive_regime_state() = ('late-cycle', 'kindleberger_override', 0.05)
  CRPS confidence       = 60.00 (capped)
  CDRS score            = 0.3067
```

All scoring/regime computations succeed; values match 3.5D verification baseline (Gate 13 anchors stable).

---

## §3 — Proof Contract (6 items per spec §5.6)

| # | Spec proof | Result | Evidence |
|---:|---|---|---|
| 1 | AST audit: all 4 Codex-flagged sites use the helper tuple | PASS | §2.1 grep shows zero `except Exception:` in 4 flagged files; helper applied at all 20 sibling sites (5+5+6+4) |
| 2 | AST audit: D27 site refactored to use shared helper | PASS | §2.2 diff before/after; grep shows `legitimate_missing_data_exceptions` in `regime_context.py` |
| 3 | New tests: 4 NEG tests propagating `PitContractViolationError` / `RegimeClassifierError` / `CacheValidationError` through each of 4 sites | PASS | Tests #1-#4 (one per Codex file; representative-site coverage) |
| 4 | Existing 566 tests still pass | PASS (with 1 inline update) | 571 passed; 1 existing test updated for the side-fix exception type |
| 5 | Cumulative test count = 571 | PASS | matches target |
| 6 | Conviction reported | PASS | §6 below |

**6/6 PASS.**

---

## §4 — Test Run Detail

### §4.1 New tests (5 total — 4 NEG / 1 POS regression = 80% NEG)

`tests/test_ap6_narrowing.py`:
- `test_cdrs_vulnerability_propagates_pit_violation` (NEG) — V1 propagates `PitContractViolationError`
- `test_cdrs_trigger_propagates_pit_violation` (NEG) — T1 propagates `PitContractViolationError`
- `test_kindleberger_propagates_config_error` (NEG) — kindleberger metrics propagate `RegimeClassifierError`
- `test_dalio_cycle_propagates_cache_validation_error` (NEG) — dalio metrics propagate `CacheValidationError`
- `test_d27_site_still_propagates_regime_classifier_error_post_consolidation` (POS regression) — D27 contract preservation

### §4.2 Full pytest

```
571 passed in 114.19s (0:01:54)
```

566 baseline (post-3.5b-U) + 5 new = 571. Zero regressions modulo the 1-test side-fix (`test_pit_pre_2015_raises` updated `ValueError → PitDataUnavailableError`).

### §4.3 Ruff

```
$ ruff check macro_pipeline/ tests/ scripts/
All checks passed!
```

(6 auto-fixable issues from initial test draft were autofixed in place.)

### §4.4 Gates 13, 15, 16 still PASS

```
[gate13] === Gate 13 - Layer 3.5B PIT Contract (Option Z): PASS ===
[gate15] === Gate 15 - Layer 3.5D Probability Semantics + Dissent: PASS ===
[gate16] === Gate 16 - Layer 3.5E Cache Integrity: PASS ===
```

Gate 16 sub-criterion 4 updated to accept the helper pattern (backward-compatible with pre-3.5b-V inline-tuple form).

---

## §5 — Deviations filed

### D30 — Comprehensive AP-6 narrowing sweep within Codex-flagged files (AM-3.5b-V-1=Comprehensive) — ACCEPT

L3.5b spec §5 D2 listed 4 sites (one per file). AST-walk audit per new "Empirical claim verification" Standing Order revealed each Codex-flagged file has 4-6 sibling broad-except blocks following the **identical pattern**: 5 in `cdrs_vulnerability.py` (V1-V5), 5 in `cdrs_trigger.py` (T1-T5), 6 in `kindleberger.py`, 4 in `dalio_cycle.py` — total 20 sibling sites + 1 D27 consolidation = **21 sites in scope**. Codex finding text "**Broader** scoring/regime tree still has AP-6 style broad catches" supports comprehensive intent.

Per V/Strategic-approved 6-rationale case (empirical AST-walk evidence; Codex finding text; architectural consistency; precedent pattern 3.5A AM4 / 3.5B AM10 / 3.5D AM21 / 3.5E D27 / 3.5b-T D28 / 3.5b-U D29; effort within budget; Strategic self-critique that spec D2 "4 sites" was an authoring shortcut without AST-walk audit), implementation narrowed all 21 in-scope sites to use the shared helper `legitimate_missing_data_exceptions()`.

**Helper contract** (`macro_pipeline/exceptions.py`):
- **CATCHES** (legitimate component-missing): `HmmArtifactMissingError`, `HmmArtifactCorruptError`, `HmmMetadataIncompatibleError`, `PitDataUnavailableError`
- **PROPAGATES** (contract / config / cache / env): `PitContractViolationError`, `RegimeClassifierError`, `HmmConcurrencyError`, `CacheValidationError`, `IndicatorLoadError`, `KeyError`, `ValueError`, `FileNotFoundError`, etc.

**D27 consolidation contract expansion** (informational): the helper adds `PitDataUnavailableError` to D27's original 3-type tuple. Empirical impact = zero (`predict_state` doesn't raise this type in current paths; only `nber_extract` raises it). D27 empirical case (`RegimeClassifierError` for filelock-missing) is preserved — the type stays out of the helper. Verified by POS regression test #5.

**Side-fix** (regression remediation, in-scope as architectural improvement): `loaders/hlw_rstar_vintage.py::get_pit_rstar` previously raised bare `ValueError("No HLW vintage available...")` for pre-2015Q4 PIT lookups; the helper does not catch generic `ValueError`. Changed to raise `PitDataUnavailableError` (semantically correct — matches NBER extract's pre-1978 PIT-unavailability pattern). One existing test updated to expect the new exception type.

### Cross-phase notes

- **L5-14** NEW backlog entry: comprehensive AP-6 hygiene sweep across 16 out-of-scope sites identified in 3.5b-V AST-walk (loaders rebuild flows, validation framework error reporting, math fallbacks). Tier 3 priority. ~3-5h effort.

---

## §6 — Conviction (3-field, post-impl)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | **0.94** | High: AST-walk audit gave exhaustive site inventory (39 broad-except sites; 21 in scope, 16 out-of-scope categorized); helper contract is unambiguous (4 caught types per spec); 5/5 new tests pass deterministically; D27 consolidation contract preservation verified by POS regression test #5; side-fix (HLW exception type) is architecturally correct. Pre-flight 0.93 nudged up post-impl. |
| `conviction_operational` | **0.93** | High: zero unintended regressions (1 test surgical update for the side-fix is documented + intentional); Gate 13/15/16 all PASS post-update; ruff clean; new Standing Order's grep + AST proof requirements satisfied. Pre-flight binding (0.88) lifted to 0.93 post-impl. |
| `conviction_actionability` | **0.93** | High: 21-site mechanical change applied uniformly via single helper; verification report has complete diff/grep proof; consolidated tuple makes future audits easier (one place to update). |
| **Aggregate** | **0.93** | Co-leading. |

Aggregate exceeds 0.85 clean APPROVE threshold by a healthy margin.

---

## §7 — Effort actual vs estimated

| Step | Pre-flight estimate (h) | Actual (h) |
|---|---:|---:|
| Pre-flight (with AST audit) | 0.5 | 0.5 |
| AM-3.5b-V-1 V acknowledgement | gate | gate |
| Helper function in `exceptions.py` | 0.1 | 0.1 |
| Apply helper at 5 sites in cdrs_vulnerability.py | 0.2 | 0.2 |
| Apply helper at 5 sites in cdrs_trigger.py | 0.2 | 0.2 |
| Apply helper at 6 sites in kindleberger.py | 0.2 | 0.2 |
| Apply helper at 4 sites in dalio_cycle.py | 0.2 | 0.2 |
| Consolidate D27 site in regime_context.py | 0.1 | 0.1 |
| **Side-fix: HLW vintage exception type + Gate 16 update** | n/a | **0.3** |
| 5 new tests | 0.5 | 0.4 |
| Smoke + ruff + Gate 13/15/16 + grep audit + AST proof | 0.4 | 0.4 |
| Verification report | 0.4 | 0.4 |
| **Total** | **2.4** | **~2.7** |

Slightly over the lower-edge estimate (2.7h vs 2.4h). The +0.3h was the side-fix for the HLW vintage exception type — a regression discovered mid-impl that turned into a legitimate architectural improvement (matching NBER extract's PIT-unavailability pattern). Within spec 2-3h band.

---

## §8 — Risks / forward-looking notes for next sub-phase (3.5b-W)

| ID | Note | Forward action |
|---|---|---|
| N-1 | The helper-based pattern is now the canonical "legitimate component-missing fallback" surface across scoring + regime trees. Any new scoring/regime metric helper added in L4/L5 should adopt the helper at its load-error site. | Document in L3.5b retrospective; add to L4/L5 onboarding |
| N-2 | 16 out-of-scope broad-except sites tracked in **L5-14** backlog (loaders rebuild flows, validation framework error reporting, math fallbacks). Each category has different idioms; a sweep would need per-category analysis. | L5/L7 hygiene |
| N-3 | The side-fix to `get_pit_rstar` (ValueError → PitDataUnavailableError) is a small contract change in the loader API. Downstream callers that catch `ValueError` for HLW pre-vintage cases need awareness. Audit for other callers showed only `dalio_cycle._compute_metrics::HLW_RSTAR site` uses this path; that site uses the helper which catches the new type. | Document in retrospective; flag for Codex review |
| N-4 | 3.5b-W (next, FINAL L3.5b): NBER boundary semantics fix at `nber_calendar.py:225`. Pre-flight should re-read NBER methodology, document current behavior at 12 boundary months across 6 cycles, surface AM-3.5b-W-1 if FRED USREC convention diverges. Surgical scope (1 file, 1 method). | Standard pre-flight workflow |

---

## §9 — Recommendation

**APPROVE — sub-phase 3.5b-V COMPLETE; proceed to 3.5b-W pre-flight.**

6/6 proof-contract items pass; 571 tests passing (zero unintended regressions); ruff clean; Gates 13/15/16 still PASS; aggregate conviction 0.93 (above 0.85 clean APPROVE threshold). D30 filed cleanly with the 6-rationale empirical case. New "Empirical claim verification" Standing Order continues to compound: AST-walk audit caught the 4-vs-21 site gap that spec D2 literal missed. Strategic self-critique pattern preserved.

The architectural improvement (helper consolidation + HLW vintage exception type alignment with NBER extract pattern) goes slightly beyond Codex's literal scope but stays within Codex's intent. The 16 out-of-scope broad-except sites are tracked in **L5-14** for future hygiene.

**Per `HANDOFF_CLAUDE_CODE_v4.md` §2 + Standing Orders, PAUSED** awaiting V/Strategic APPROVE / REVISE-WITH-NOTES / RETURN-FOR-REWORK signal before 3.5b-W pre-flight authoring (the FINAL L3.5b sub-phase).

---

## §10 — Quick-reference artefacts for review

| Artefact | Path |
|---|---|
| Pre-flight | `LAYER_3_5b_V_PREFLIGHT.md` |
| Verification (this) | `LAYER_3_5b_V_VERIFICATION.md` |
| New helper | `macro_pipeline/exceptions.py::legitimate_missing_data_exceptions` |
| Refactored sites (21 total) | `scoring/cdrs_vulnerability.py` (5), `scoring/cdrs_trigger.py` (5), `regime/kindleberger.py` (6), `regime/dalio_cycle.py` (4), `regime/regime_context.py:295` (1) |
| Side-fix (regression remediation) | `loaders/hlw_rstar_vintage.py::get_pit_rstar` (ValueError → PitDataUnavailableError) + `tests/test_official_4d.py::test_pit_pre_2015_raises` (test type updated) |
| Gate 16 sub-criterion 4 update | `validation.py::validate_gate16_cache_integrity` (accept helper pattern OR inline tuple) |
| New tests | `tests/test_ap6_narrowing.py` (5 tests) |
| Deviations register update | `LAYER_3_5_DEVIATIONS.md` (D30 + L5-14 backlog) |

---

**END — LAYER_3_5b_V_VERIFICATION.md**
