# L11 Producer Integration Audit (Phase 0 formalization)

**Author**: Track A (Claude Code)
**Date**: 2026-05-17
**Status**: D1 deliverable of L11-REV; ratified by Strategic post Track A's STOP-and-surface

## §0 — Why this document exists

The L10 sub-phase shipped a Flask web app whose `ForecastInputsBuilder` populated the L6-H `ForecastInputs` dataclass via **bounded heuristic modulators** around L6-H canonical defaults (PMI deviation, CAPE mean-reversion, unemployment + yield-curve bumps). The L10 ACCEPT report flagged this as the binding constraint (NOTE-2). L11 closes that gap.

Strategic's first L11 pre-flight referenced directories that do not exist in this codebase. Track A ran a Phase 0 audit, fired §12 STOP trigger #1, and surfaced findings. Strategic ratified Path A (bundle a pre-computed snapshot of the producer-input panels and derive ForecastInputs from real historical data, with the web form acting as latest-observation overlay).

This document is the formalized audit.

---

## §1 — Codebase structure (corrected)

| Strategic's L11 v1 reference | Actually exists at |
|---|---|
| `macro_pipeline/l5b/` | **Does not exist.** L5-B logic lives in `macro_pipeline/models/return_forecast.py` + `macro_pipeline/analysis/forecast_sigma.py` + `macro_pipeline/scoring/*` |
| `macro_pipeline/l6h/` | **Does not exist.** L6-H logic lives in `macro_pipeline/ensemble/aggregator.py` |
| `macro_pipeline/aggregator/` | **Does not exist.** Same as L6-H above |

The three `ensemble/component_producers/*_producers.py` modules populate `ConfidenceComponents` / `ConvictionComponents` (slots inside `TripleDecomposition`), **not** the 6 per-horizon dicts of `ForecastInputs`. Strategic's L11-REV §4 has been corrected to reflect this.

### Where `ForecastInputs` is actually constructed

```
grep -r "ForecastInputs(" macro_pipeline/   →  1 file: webapp/data_ingestion.py
```

The aggregator references the class; only L10 webapp code constructs it. No pre-existing "L5b → ForecastInputs" pipeline exists to wire in.

---

## §2 — ForecastInputs field → producer source → snapshot panels

`ForecastInputs` has six per-horizon dicts (`{1, 3, 5, 10} → float|int`). For each, the table below names the real producer that would generate it in a full backtest run, the panels that producer needs, and the snapshot panels L11 bundles so the value can be derived at request time.

| Field | Real producer (if run via CV) | Snapshot panels L11 uses | L11 derivation strategy |
|---|---|---|---|
| `point_estimates` | `models/return_forecast.py:fit_return_forecast_task_b1` (Ridge over walk-forward folds) | `official_SHILLER_TR_PRICE`, `official_SHILLER_CAPE`, `fred_PCEPILFE`, `fred_PAYEMS` | Historical mean real return per horizon (from SHILLER_TR_PRICE) + Campbell-Shiller CAPE mean-reversion at 10Y + cyclical overlay from form (PMI/unemployment) |
| `point_estimate_n_eff` | walk-forward training-window size per fold | (panel coverage count) | Count of monthly obs in the snapshot SHILLER panel ÷ overlap factor for the horizon |
| `forecast_sigmas` | `analysis/forecast_sigma.py:derive_forecast_sigma_v2` (Ridge HAC residual + isotonic bootstrap) | `official_SHILLER_TR_PRICE`, `analysis/r_squared_panel` | Square-root-of-time scaling of the panel's historical OLS residual sigma + R² shrinkage when available |
| `analog_dispersions` | reference-class historical analog matching | `official_SHILLER_TR_PRICE` | Cross-period dispersion of rolling forward returns per horizon (real measurement, not heuristic) |
| `return_sigmas` | regime-conditional realized vol | `yahoo_SPX_TR`, `cache/hmm/regime_3state_v1.pkl` | Annualized realized vol from SPX TR, scaled by horizon, with HMM regime conditioning as upgrade path |
| `recession_probabilities` | CDRS calibrated panels | `fred_USREC`, form-modulated | Historical NBER recession base rate per horizon window, modulated by current PMI / unemployment / yield-curve inversion |

**Status of "running the real producer"**: deferred. `fit_return_forecast_task_b1` is a walk-forward CV pass that takes minutes-to-hours per horizon. Not feasible inside a sub-second HTTP request. The L11 design uses the **outputs of the producer family** (historical panels) rather than re-running the producer at request time, which is the standard architectural compromise for any model-serving system (train offline, serve from artifacts).

---

## §3 — Form-field → panel mapping (latest-observation overlay)

V's web form provides 8 point-in-time scalars. Each scalar overlays the latest observation in a corresponding snapshot panel, so the producer-derived calculation reflects today's macro state rather than the snapshot's build date.

| Form field | Snapshot panel overlaid | Overlay semantics |
|---|---|---|
| `pmi_manufacturing` | (no direct FRED panel; used directly in form-modulation block) | Cyclical-signal overlay on point_estimates and recession_probabilities |
| `pmi_services` | (no direct FRED panel; used directly) | Same |
| `cape_ratio` | `official_SHILLER_CAPE` | Replaces latest CAPE observation; drives 10Y point_estimate mean-reversion |
| `sp500_current` | `yahoo_SPX_PRICE` | Used for current-price anchor in derived sigmas |
| `payrolls_mom` | `fred_PAYEMS` (last-month change) | Used in recession_probabilities cyclical bump |
| `unemployment_rate` | `fred_UNRATE` (if bundled; else used directly) | Drives recession_probabilities |
| `core_cpi_yoy` | `fred_CORESTICKM159SFRBATL` | Used for inflation-regime context (future hook) |
| `fed_funds_rate` | `fred_DFF` (if bundled) | Used for monetary-tightness context (future hook) |

Excel uploads (yield curve, credit spreads, sentiment) overlay additional latest observations:
- Yield-curve upload → 2Y/10Y inversion flag overlays `fred_T10Y2Y` direction
- Credit spreads upload → IG OAS overlays NFCI stress signal
- Sentiment upload → AAII/NAAIM levels overlay sentiment context

---

## §4 — Snapshot panel manifest (Phase 2 D2-D3 input)

Selection criterion: smallest set of panels that enables principled derivation of all 6 `ForecastInputs` fields. Targets ~20-30 MB.

**Tier 1 — Required for derivation** (~6 MB):
- `official_SHILLER_TR_PRICE.parquet` (≈380 KB) — historical real total returns; drives point_estimates + forecast_sigmas + analog_dispersions
- `official_SHILLER_CAPE.parquet` (≈356 KB) — Campbell-Shiller 10Y mean-reversion
- `official_SHILLER_PRICE.parquet` (≈372 KB) — current price anchor
- `official_SHILLER_REAL_PRICE.parquet` (≈380 KB) — real-price series
- `official_SHILLER_TR_CAPE.parquet` (≈356 KB) — TR CAPE
- `official_SHILLER_EARNINGS.parquet` (≈372 KB) — earnings denominator
- `official_SHILLER_DIVIDEND.parquet` (≈372 KB) — dividend context
- `official_SHILLER_GS10.parquet` (≈368 KB) — 10Y Treasury for excess-return
- `official_SHILLER_CPI.parquet` (≈368 KB) — inflation deflator
- `yahoo_SPX_PRICE.parquet` (≈368 KB) — modern daily price
- `yahoo_SPX_TR.parquet` (≈368 KB) — modern total return
- `fred_USREC.parquet` (≈396 KB) — NBER recession indicator (base rate for recession_p)
- `analysis/r_squared_panel.parquet` (≈63 KB) — pre-computed R² for forecast_sigma shrinkage
- `cache/hmm/regime_3state_v1.pkl` + `.meta.json` (≈8 KB) — regime artifact

**Tier 2 — Form-overlay anchors** (~5 MB):
- `fred_PAYEMS.parquet` — payrolls panel
- `fred_PCEPILFE.parquet` — core PCE
- `fred_CORESTICKM159SFRBATL.parquet` — sticky core CPI
- `fred_NFCI.parquet` — financial conditions
- `fred_ANFCI.parquet` — adjusted FCI
- `fred_T10Y2Y.parquet` (if available) — yield curve
- `fed_EBP.parquet` — excess bond premium (credit stress)

**Tier 3 — Optional context** (~10 MB):
- Sector ETFs (`yahoo_XLK`, `yahoo_XLF`, etc.)
- VIX panels (`yahoo_VIX*`)
- Vintage panels (`cache/vintage_panels/*`)

Total Tier 1+2 ≈ 11 MB. Adding Tier 3 selectively brings total to ~20-25 MB.

---

## §5 — Architectural decision: snapshot loader path

Strategic's L11-REV §5 Phase 2 step 5 specifies modifying `fred_loader.py`, `fred_vintage_panel.py`, `yahoo_loader.py` to fall back to `data_snapshot/`. Track A audit recommends a **deviation**:

**Recommendation**: Do NOT modify the 3 existing loaders. Instead, ship a separate `macro_pipeline/webapp/snapshot_loader.py` that the new `ProducerAdapter` calls directly. Reasons:

1. **Risk**: modifying the three loaders that 1,382 baseline tests depend on risks regressing the L1-L9 test surface.
2. **Lazy credential gating**: the existing loaders import `fredapi` at module load and require `FRED_API_KEY` at call site (per L5b-F F-O1). The webapp must work without a FRED key. A separate loader has zero `fredapi` coupling.
3. **Scope discipline**: the L11 mandate is "ForecastInputs derived from producer chain". The web app is the only caller; the rest of the codebase is unaffected by the snapshot mechanism.
4. **Standing Order #8 (defense-in-depth preservation)**: minimal-surface-area change ⇒ minimal regression risk to the cap cascade.

Effort delta: zero (the snapshot loader is a 30-line module either way; it just doesn't live inside the existing loaders).

---

## §6 — Fallback strategy (D8)

The new ProducerAdapter wraps its work in `try/except`. If anything fails (snapshot missing, panel corrupted, producer derivation raises), the request transparently falls back to the L10 heuristic modulator path. Provenance dict records `fallback_mode=heuristic` and the user-facing results page surfaces a warning in Vietnamese.

This satisfies §11 risk #2 (form responsiveness preservation): even when the producer path fails, the form still produces a meaningful forecast.

---

## §7 — Sensitivity preservation guard (D7)

L10's modulators guaranteed that ±1% PMI moves the 1Y forecast by ≥0.3pp. The L11 producer-derived path could over-damp this sensitivity if the snapshot anchor is too strong. To prevent silent regression:

- Test `test_l11_form_responsiveness.py` asserts the ±1% / ≥0.3pp invariant
- ProducerAdapter blends historical anchor (weight 0.4-0.7 depending on horizon) with form-derived cyclical overlay (weight 0.3-0.6) — same shape as the L10 weighting but with the constant baseline replaced by a real historical mean
- 10Y horizon adds a Campbell-Shiller CAPE mean-reversion term anchored on the real CAPE history rather than a hardcoded 22

---

## §8 — Risks remaining after L11 ships

- **Snapshot staleness**: V's actual cache will update monthly; the bundled snapshot will not. Help-page guidance: rebuild via `scripts/build_data_snapshot.py` and rebuild the .exe. (Acceptable: V is a single user with control over both.)
- **Form-overlay calibration**: the historical anchor + form-cyclical blend weights are calibrated heuristically. A future L12+ pass could fit them via the same walk-forward CV the real producers use.
- **HMM regime conditioning** is included as a Tier 1 artifact but not yet wired into `return_sigmas` — opportunity for a future polish pass.

---

## §9 — Acceptance for this document

- ✅ Formalizes Phase 0 STOP-surface findings
- ✅ Maps 6/6 ForecastInputs fields → snapshot panels → derivation strategy
- ✅ Maps 8/8 form fields → panel overlays
- ✅ Declares snapshot manifest (Tier 1 + Tier 2 = ~11 MB; +Tier 3 selective ≈ 20-25 MB)
- ✅ Documents Strategic-deviation recommendation (snapshot loader vs 3-loader modification) with reasoning
- ✅ Defines fallback strategy + sensitivity guard

L11-REV D1 deliverable: **complete**.
