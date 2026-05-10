# LAYER 3.5b-V — Pre-Flight Audit (Broader AP-6 Narrowing Sweep)

**Spec ref**: L3.5b inline spec §5 (Codex finding V, MED).
**Branch**: `claude/layer-3-5b-build` @ `e92a714` (3.5b-U complete).
**Date**: 2026-05-10
**Author**: Claude Code (build agent)
**Status**: PROCEED-with-Dxx pending V acknowledgement on AM-3.5b-V-1 (scope: surgical 5 sites vs comprehensive 21 sites within Codex-flagged files).

---

## §1 — Audit Result Header

| Field | Value |
|---|---|
| Sub-phase | 3.5b-V — Broader AP-6 Narrowing Sweep |
| Spec effort | 2–3h |
| My estimate after audit | **~2.4h** (lower edge if comprehensive scope approved; mostly mechanical) |
| Tests added (target) | 5 (4 NEG / 1 POS regression = 80% NEG, well above 50% floor) per Strategic recommendation |
| Cumulative tests post-V | 566 + 5 = **571** |
| Codex findings closed | V (MED) |
| Locked decisions (V-D1..D3) | D1 same refined exception tuple as D27; D2 4 Codex sites (per spec literal); D3 shared helper `legitimate_missing_data_exceptions()` |
| Anticipated deviations | **D30** if AM-3.5b-V-1 disposition is approved as recommended (comprehensive sweep within 4 flagged files = 21 sites total) |
| Conviction (statistical / operational / actionability) | 0.93 / 0.88 / 0.92 — see §10 |

---

## §2 — Empirical findings (per spec §5.2 + new "Empirical claim verification" Standing Order)

### §2.1 AST-walk audit of ALL broad except blocks in macro_pipeline/

Per the new Standing Order: ran `ast.walk` over every `*.py` in `macro_pipeline/`, looking for `except Exception` / `except BaseException` / bare-except handlers. **39 broad except blocks** found.

#### Codex-flagged 4 files — sibling broad-except sites per file

The Codex spec listed 4 sites (one per file). The AST audit shows each file has **multiple sibling broad-except blocks** in the same code-path pattern:

| File | Codex line (spec) | Actual line | Function | Sibling count in file |
|---|---:|---:|---|---:|
| `scoring/cdrs_vulnerability.py` | 79 | **81** | `v1_cape_percentile` | **5** (V1 line 81, V2 104, V3 132, V4 163, V5 208) |
| `scoring/cdrs_trigger.py` | 71 | **73** | `t1_hy_oas_30d_roc` | **5** (T1 73, T2 97, T3 119, T4 134, T5 162) |
| `regime/kindleberger.py` | 79 | **87** | `_compute_metrics` (first metric) | **6** (lines 87, 104, 120, 136, 151, 162 — all in `_compute_metrics`) |
| `regime/dalio_cycle.py` | 76 | **81** | `_real_rate_now` | **4** (lines 81, 109, 132, 142) |
| **Total in 4 flagged files** | | | | **20** |

Plus the 1 D27 site at `regime_context.py:295` (already narrowed at L3.5E; consolidation candidate per spec §5.3-D3 + Strategic note 4).

**Surgical scope (per spec D2 literal)**: 4 + 1 = **5 sites**.
**Comprehensive scope within 4 flagged files (intent)**: 20 + 1 = **21 sites**.

#### Out-of-scope broad except blocks (16 sites, NOT in Codex-flagged files)

| File | Lines | Function/category | Classification |
|---|---|---|---|
| `analysis/newey_west_hac.py` | 77 | `fit_ols_hac` | math fallback (numerical edge case) |
| `analysis/r_squared_panel.py` | 167 | `_fit_one_cell` | math fallback (per-cell regression failure) |
| `cache.py` | 50, 65 | `atomic_write_bytes`, `atomic_write_parquet` | tmp-file cleanup (legitimate; rethrows original) |
| `loaders/atlanta_wage.py` | 52 | `_read_atlanta_wage_raw` | loader rebuild flow |
| `loaders/fred_vintage_panel.py` | 248 | `materialize_all_vintage_panels` | loader rebuild flow |
| `loaders/hlw_rstar.py` | 65 | `_read_hlw_raw` | loader rebuild flow |
| `loaders/shiller.py` | 102 | `_read_shiller_raw` | loader rebuild flow |
| `loaders/yahoo_loader.py` | 363, 474 | `load_yahoo_series`, `load_yahoo_all` | loader rebuild flow |
| `validation.py` | 9 sites (1310, 1330, 1518, 1736, 1763, 1853, 2277, 2376, 2450) | various gate handlers | framework-level (gate runtime resilience; gates report errors, don't propagate them) |

These 16 are OUT of 3.5b-V scope. Categories:
- **math fallbacks**: legitimate numerical edge cases; broad catch is appropriate
- **tmp-file cleanup**: legitimate; pattern is `except Exception: cleanup_tmp; raise` (not the AP-6 silent-swallow pattern)
- **loader rebuild flows**: by design — broad catch with rebuild fallback is the rebuild idiom
- **validation gate handlers**: framework-level error reporting; gates collect errors into `findings` rather than propagating

Future hygiene (L4/L5) could narrow each, but spec §5 scope is the scoring/regime tree only.

### §2.2 Codex-finding-V evidence

The 4 flagged files are the scoring/regime metric-component computation tree. Each broad-except block follows the **identical pattern**:

```python
def vN_metric_or_tN_trigger(ctx) -> tuple[float | None, ..., str]:
    try:
        x = _pit_series("INDICATOR", ctx)
    except Exception as exc:
        return None, ..., f"VN/TN load error: {type(exc).__name__}: {exc}"
    # compute metric ...
```

If a `PitContractViolationError` (3.5B Option Z violation) or a `CacheValidationError` (3.5b-T integrity violation) or a `RegimeClassifierError` (env/config issue) is raised inside `_pit_series`, the broad except silently swallows it into a "component missing" note. Downstream V/T aggregation drops that component and continues — the contract violation is invisible.

This is the AP-6 anti-pattern Codex finding V flagged. The fix is the shared helper tuple per spec §5.3-D3.

### §2.3 Empirical: what the helper actually catches at each site

Inspection of `_pit_series` / `load_series` raise inventory:

| Exception type | Source | Caught by helper? | Propagates? |
|---|---|:---:|:---:|
| `HmmArtifactMissingError` | HMM load (only HMM-using sites) | ✓ | — |
| `HmmArtifactCorruptError` | HMM load | ✓ | — |
| `HmmMetadataIncompatibleError` | HMM load | ✓ | — |
| `PitDataUnavailableError` | only `regime/nber_extract.py` (NBER PIT lookup) | ✓ | — |
| `PitContractViolationError` | `access.py:378` (Option Z + vintage contract) | — | ✓ (spec intent) |
| `RegimeClassifierError` | HMM env/config | — | ✓ |
| `HmmConcurrencyError` | HMM filelock timeout | — | ✓ |
| `CacheValidationError` | post-3.5b-T strict validation | — | ✓ |
| `IndicatorLoadError` | typed loader failures | — | ✓ |
| `KeyError` / `ValueError` / `FileNotFoundError` | various | — | ✓ |

At the 4 Codex sites, the helper **effectively catches almost nothing in normal practice** (PitDataUnavailableError is rarely raised by `_pit_series` since it's NBER-extract-specific; HMM artifact errors are not relevant to V/T component computations). The whole effect of narrowing is to make all real errors propagate — exactly the spec intent.

### §2.4 D27 consolidation: contract change at regime_context.py:295

D27 (3.5E) narrowed inline to `(HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError)`. Spec §5.3-D3 helper adds `PitDataUnavailableError`. **This is a slight contract expansion at the D27 site.**

Pre-3.5b-V (D27 era): `predict_state` raising `PitDataUnavailableError` propagates → `build_regime_context` raises → derive_regime_state never called.

Post-3.5b-V (helper): `predict_state` raising `PitDataUnavailableError` caught + logged + `hmm_result=None` → `build_regime_context` returns degraded-mode (HMM=None) → derive_regime_state takes Phase A path.

**Empirical impact**: zero. `predict_state` doesn't raise `PitDataUnavailableError` in current code paths (HMM features come from `load_series` which doesn't raise that type; only `nber_extract` does). The contract expansion is cosmetic.

**The D27 empirical case (filelock-missing → `RegimeClassifierError` → silent swallow into 'expansion')**: still preserved — `RegimeClassifierError` is NOT in the helper tuple, propagates correctly.

Verified via grep audit (per new Standing Order):

```
$ grep -rn "raise PitDataUnavailableError" macro_pipeline/
macro_pipeline/regime/nber_extract.py:76, 92, 100, 159, 182, 199, 220, 234, 278
```

Only `nber_extract.py` raises this type. HMM-feature load path (`load_series`) does not. Consolidation is safe.

---

## §3 — Spec §5.2 mandatory items + §5.3 file inventory

### §3.1 Files this sub-phase will touch (assuming AM-3.5b-V-1 = comprehensive)

| File | Action | Sites narrowed |
|---|---|---:|
| `macro_pipeline/exceptions.py` | MODIFY | ADD `legitimate_missing_data_exceptions()` helper |
| `macro_pipeline/scoring/cdrs_vulnerability.py` | MODIFY | 5 sites (V1-V5 component computations) |
| `macro_pipeline/scoring/cdrs_trigger.py` | MODIFY | 5 sites (T1-T5 trigger computations) |
| `macro_pipeline/regime/kindleberger.py` | MODIFY | 6 sites (_compute_metrics components) |
| `macro_pipeline/regime/dalio_cycle.py` | MODIFY | 4 sites (debt/interest/r* components) |
| `macro_pipeline/regime/regime_context.py` | MODIFY | 1 site (D27 consolidation; replace inline narrow tuple with helper) |
| `tests/test_ap6_narrowing.py` | NEW | 5 tests (4 NEG / 1 POS regression per Strategic rec) |
| **Total** | | **21 narrowing sites** + 1 helper add |

### §3.2 Decisions locked per Standing Orders

| Decision | Locked default | Empirical override needed? |
|---|---|---|
| 3.5b-V-D1 (refined exception tuple per D27) | YES | NO |
| 3.5b-V-D2 (4 sites — spec literal) | 4 sites | **AM-3.5b-V-1**: comprehensive within 4 flagged files (21 sites) |
| 3.5b-V-D3 (shared helper `legitimate_missing_data_exceptions()`) | YES | NO |

### §3.3 Ambiguities

| ID | Topic | Routing | Recommended disposition |
|---|---|---|---|
| **AM-3.5b-V-1** | Scope: surgical (5 sites; spec D2 literal "4 sites") vs comprehensive (21 sites within 4 flagged files; intent). Codex finding text says "Broader scoring/regime tree still has AP-6 style broad catches" — the "broader" wording suggests comprehensive intent. Each flagged file has multiple sibling broad-except blocks following the identical pattern (V1-V5 / T1-T5 / 4-6 metric helpers); narrowing only the first creates an inconsistent surface where some component sites raise on `PitContractViolationError` / `CacheValidationError` / etc. and siblings silently swallow. | **PROCEED-with-Dxx (D30)** | **Recommend comprehensive (21 sites)**. Rationale: (a) consistency across sibling functions; (b) Codex finding text supports broader intent; (c) helper application is mechanical low-risk; (d) leaving siblings broad mostly defeats the protection from narrowing the first. Standard 3.5A AM4 / 3.5B AM10 / 3.5D AM21 / 3.5E D27 / 3.5b-T D28 / 3.5b-U D29 spec-literal-vs-intent precedent. If V prefers surgical: build agent will narrow only the 4+1 sites per spec literal and document the residual 16 AP-6 sites in retrospective. |
| **AM-3.5b-V-2** (informational) | D27 consolidation contract expansion: helper adds `PitDataUnavailableError` to caught types vs D27's strict 3-type tuple. Empirical impact at D27 site = zero (`predict_state` doesn't raise this type in current paths; only `nber_extract` raises it). The D27 empirical case (`RegimeClassifierError` propagation for filelock-missing) is preserved — that type stays out of the helper. | **PROCEED** (no Dxx) | Document the contract expansion in D30 narrative; verify via the +1 POS regression test that filelock-missing case still propagates. |
| **AM-3.5b-V-3** (informational) | Helper signature: `legitimate_missing_data_exceptions() -> tuple[type[Exception], ...]` returning a tuple at runtime, vs `LEGITIMATE_MISSING_DATA_EXCEPTIONS: tuple[...] = (...)` constant at module level. Functional difference: the function delays the import of `regime/exceptions` (lazy import at call site, mirrors D27's inline pattern); the constant evaluates eagerly. | **PROCEED** (no Dxx) | Use the function form per spec literal (§5.3-D3 example). Lazy import avoids circular-import hazards (`exceptions.py` would otherwise import `regime/exceptions.py` at module load — currently it doesn't depend on `regime/`). |

### §3.4 Risk callouts

| ID | Risk | Mitigation |
|---|---|---|
| R-V-1 | 21 sites with mechanical change is large; risk of inconsistent application across sites | Use a single regex-style helper function applied uniformly; spot-check each file post-impl |
| R-V-2 | D27 consolidation contract expansion — `PitDataUnavailableError` now caught at D27 site (was raise) | Empirically zero impact (§2.4); +1 POS regression test verifies filelock-missing case still propagates (via `RegimeClassifierError`) |
| R-V-3 | Existing tests at the 4 Codex sites may rely on specific broad-catch behaviour (e.g. assert that V1 returns None on bad cache) | Spot-check before code change; AST audit of test files for assertions matching `vN_metric.*returns.*None` patterns |
| R-V-4 | Potential circular import: `exceptions.py` is currently independent of `regime/`; helper function must avoid eager import of `regime/exceptions.py` | Helper function pattern (lazy import inside body) handles this; verify with test importing helper from clean state |
| R-V-5 | Per new Standing Order: post-impl verification must include grep-audit + AST proof, not just unit-test proof | §6.4 of verification report: AST audit confirming all 21 sites use helper; grep for residual `except Exception` in 4 flagged files (must be zero post-impl) |
| R-V-6 | Test plan size: spec §5.5 is 4 NEG; Strategic recommends adding 1 POS regression test for D27. Per build-agent discretion. | Adopt 5 tests total (4 NEG + 1 POS regression). 80% NEG abundantly above 50% floor. |

### §3.5 Effort estimate

| Step | h |
|---|---:|
| Pre-flight (this) | 0.5 (with AST audit) |
| AM-3.5b-V-1 V acknowledgement | gate |
| Helper function in `exceptions.py` | 0.1 |
| Apply helper at 5 sites in cdrs_vulnerability.py | 0.2 |
| Apply helper at 5 sites in cdrs_trigger.py | 0.2 |
| Apply helper at 6 sites in kindleberger.py | 0.2 |
| Apply helper at 4 sites in dalio_cycle.py | 0.2 |
| Consolidate D27 site in regime_context.py | 0.1 |
| 5 new tests | 0.5 |
| Smoke + ruff + Gate 13/15/16 + grep audit + AST proof | 0.4 |
| Verification report | 0.4 |
| **Total** | **~2.4** within spec 2–3h band (lower edge) |

---

## §4 — Implementation order (post-V acknowledgement on AM-3.5b-V-1)

1. **GATE**: V acknowledges AM-3.5b-V-1 (recommend comprehensive 21 sites). AM-3.5b-V-2 + AM-3.5b-V-3 are informational.
2. Add `legitimate_missing_data_exceptions()` to `macro_pipeline/exceptions.py`:

   ```python
   def legitimate_missing_data_exceptions() -> tuple[type[Exception], ...]:
       """Layer 3.5b-V (D30): the canonical exception tuple for
       'component missing — degrade gracefully' fallbacks at scoring
       and regime metric sites.

       Catch this tuple at sites where a missing component is a
       legitimate degradation path (V1-V5 vulnerability scores, T1-T5
       triggers, kindleberger metrics, dalio metrics, HMM at
       regime_context). Does NOT include PitContractViolationError,
       RegimeClassifierError, HmmConcurrencyError, CacheValidationError,
       IndicatorLoadError, KeyError, ValueError, FileNotFoundError —
       those propagate so contract / config / cache / env issues fail
       loudly rather than silently swallow into 'component missing'
       notes (Codex L3.5 finding V).

       Lazy import of regime/exceptions to avoid module-load cycles.
       """
       from macro_pipeline.regime.exceptions import (
           HmmArtifactCorruptError,
           HmmArtifactMissingError,
           HmmMetadataIncompatibleError,
           PitDataUnavailableError,
       )
       return (
           HmmArtifactMissingError,
           HmmArtifactCorruptError,
           HmmMetadataIncompatibleError,
           PitDataUnavailableError,
       )
   ```

3. Refactor each of the 21 narrowing sites:

   ```python
   # OLD
   try:
       x = _pit_series("X", ctx)
   except Exception as exc:
       return None, ..., f"VN load error: {type(exc).__name__}: {exc}"

   # NEW
   from macro_pipeline.exceptions import legitimate_missing_data_exceptions
   try:
       x = _pit_series("X", ctx)
   except legitimate_missing_data_exceptions() as exc:
       return None, ..., f"VN load error: {type(exc).__name__}: {exc}"
   ```

4. Consolidate `regime_context.py:295` (D27 site) to use the helper, replacing inline `(HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError)` tuple. Update the inline comment to reference D30 + the contract-expansion note.

5. Write 5 new tests in `tests/test_ap6_narrowing.py`:
   - 4 NEG: each Codex-flagged file's representative site propagates `PitContractViolationError` / `CacheValidationError` / `RegimeClassifierError` correctly
   - 1 POS regression: D27 site still propagates `RegimeClassifierError` for the filelock-missing case (i.e., consolidation doesn't regress the empirical D27 contract that mattered)

6. Run full pytest + ruff + Gate 13/15/16 + grep audit + AST proof.

7. Empirical post-impl smoke: induce `PitContractViolationError` at each of the 4 representative sites; verify propagation.

8. Author `LAYER_3_5b_V_VERIFICATION.md`.

9. Commit: `Layer 3.5b-V: Broader AP-6 narrowing sweep (closes Codex finding V)`.

10. PAUSE for V/Strategic APPROVE before 3.5b-W pre-flight.

---

## §5 — Test plan preview (5 new = 4 NEG / 1 POS regression = 80% NEG)

| # | Test | Type | Asserts |
|---:|---|---|---|
| 1 | `test_cdrs_vulnerability_propagates_pit_violation` | NEG | Mock `_pit_series` to raise `PitContractViolationError` inside V1; `cdrs_vulnerability.compute_vulnerability_components(ctx)` propagates instead of returning V1=None+note |
| 2 | `test_cdrs_trigger_propagates_pit_violation` | NEG | Same for T1 in `cdrs_trigger.compute_trigger_components` |
| 3 | `test_kindleberger_propagates_config_error` | NEG | Mock `_pit_series` to raise `RegimeClassifierError` inside `kindleberger._compute_metrics`; `classify_kindleberger(ctx)` propagates |
| 4 | `test_dalio_cycle_propagates_cache_validation_error` | NEG | Mock `_pit_series` to raise `CacheValidationError` inside `dalio_cycle._compute_metrics`; `classify_dalio(ctx)` propagates |
| 5 | `test_d27_site_still_propagates_regime_classifier_error_post_consolidation` | POS regression | Mock `predict_state` to raise `RegimeClassifierError` (the empirical filelock-missing case); `build_regime_context(ctx)` still propagates (consolidation preserves D27's strict contract for this type) |

NEG/POS = 4/1 = **80% NEG**, well above 50% floor.

Strategic note: spec §5.5 listed only the 4 NEG tests. Strategic recommended adding 1 POS regression for D27 site. Build agent discretion confirmed: 5 total tests is a reasonable consolidation-robustness footprint.

---

## §6 — Proof-contract mapping (6 items per spec §5.6)

| # | Spec proof | Plan |
|---:|---|---|
| 1 | AST audit: all 4 Codex-flagged sites use the helper tuple | Verification report §6.4 AST/grep proof; expect zero `except Exception:` in 4 flagged files post-impl |
| 2 | AST audit: D27 site refactored to use shared helper | grep for `legitimate_missing_data_exceptions` in `regime_context.py:295` ± 5 lines |
| 3 | New tests: 4 NEG tests propagating `PitContractViolationError` / `ConfigError` / `CacheValidationError` through each of 4 sites | Tests #1-#4 |
| 4 | Existing 566 tests still pass | Full pytest |
| 5 | Cumulative test count = 571 | 566 + 5 |
| 6 | Conviction reported | §10 |

Per new Standing Order ("empirical claim verification") + Strategic note 4: verification report §6 will include explicit grep-audit confirmation that all 21 (or 5 if surgical) sites use the helper; empirical induction of `PitContractViolationError` at 1 representative per file demonstrating propagation; D27 consolidation diff before/after.

---

## §7 — Conviction (3-field, pre-flight)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | **0.93** | High: AST audit gives full inventory (39 broad-except sites; 21 in scope, 16 out-of-scope categorized); helper contract is unambiguous (4 caught types per spec); empirical impact at D27 contract expansion = zero (verified via grep); test plan covers all 4 representative sites + 1 D27 regression. Slight haircut for AM-3.5b-V-1 disposition (literal 5 sites vs intent 21 sites). |
| `conviction_operational` | **0.88** | Medium-high: AM-3.5b-V-1 is the binding ambiguity. If V approves recommended (comprehensive), the 21-site mechanical change is low-risk per site but adds up; spot-check + AST proof mitigates. If V chooses surgical, residual AP-6 sites in 4 flagged files create inconsistent surface (some sites raise on contract violations, siblings silently swallow). **Binding** at 0.88 until V decides. |
| `conviction_actionability` | **0.92** | High: helper function pattern is small + symmetric; each site change is 2-3 lines; post-impl AST proof is a one-shot verification; test plan exercises the contract change cleanly. |
| **Aggregate** | **0.91** | Operational binding (AM-3.5b-V-1 disposition gate). |

---

## §8 — END

Pre-flight complete. **PAUSED** awaiting:

1. **AM-3.5b-V-1** disposition — recommend **comprehensive sweep within 4 flagged files (21 sites)** + D27 consolidation = **21 sites total**. File **D30** for the spec-literal-vs-intent expansion documentation. If V prefers surgical (5 sites; spec literal): build agent will narrow only the 4+1 sites and flag residual 16 AP-6 sites in retrospective + L4/L5 hygiene backlog.
2. (Informational) **AM-3.5b-V-2** D27 contract expansion (PitDataUnavailableError now caught; empirically zero impact; D27 strict-contract case preserved via test #5).
3. (Informational) **AM-3.5b-V-3** helper function-vs-constant choice; recommend function (lazy import).

If V approves AM-3.5b-V-1 = comprehensive: proceed with §4 implementation order; expect ~2.4h total (helper + 21 sites mechanical + 5 tests + verification).

If V prefers surgical: build agent narrows 4+1 sites only (~1.8h); residual 16 sites tracked for L4/L5.

Per Standing Orders pause-and-verify pattern: this is the gating PAUSE before §4 STEP 2 (helper introduction).

---

**END — LAYER_3_5b_V_PREFLIGHT.md**
