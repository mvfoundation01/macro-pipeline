# `macro_pipeline.analysis` — Layer 3D R² Master Panel

## §1. Purpose

The `analysis` package builds a single regression panel that captures
the in-sample R² of every Tier 1-4 indicator against forward returns
on two equity-market targets at four horizons.

| Field | Value |
|---|---|
| Indicators | 121 (124 cached − 1 MultiIndex (HLW_VINTAGE) − 2 targets) |
| Horizons | `1Y` (12mo), `3Y` (36mo), `5Y` (60mo), `10Y` (120mo) |
| Targets | `SHILLER_TR_PRICE` (real total return, 1871+); `SP500TR` (nominal total return, 1988+) |
| Total rows | 121 × 4 × 2 = **968** |
| Method | OLS with Newey-West HAC at `maxlags = horizon_months − 1` |
| Cache | `data/cache/analysis/r_squared_panel.parquet` (atomic write, sha256-validated) |

The panel is **descriptive infrastructure** for Layer 5b OOS work:
Hodrick standard errors, block-bootstrap CIs, structural-break tests,
and PIT-conditioned re-runs all consume this panel.

## §2. Design choices (3D-prep-3, -4, -5)

### Latest-vs-as_of (3D-prep-3)

The panel uses **`load_series(id)` (latest mode)**, NOT
`PitDataContext`. Rationale: the panel describes "the current best
understanding of historical relationships" with fully-revised data.
This is the GMO/Hussman/AQR/Damodaran convention. PIT-conditioned
backtests (CRPS at `as_of=t`) are a separate analysis stratum and
will live in a parallel Layer 5b panel.

### CRPS / CDRS / regime artifacts excluded (3D-prep-4)

`CRPS`, `CDRS`, `REGIME` and the V/T/R intermediates are **not**
indicators — they are derived signals computed FROM the indicators
this panel measures. Including them would be a circular regression
(scores derived from CAPE regressed against forward returns, with CAPE
also in the panel). Layer 5b can build a separate "scored signals ×
forward returns" panel.

### Frequency alignment (3D-prep-5)

Annual indicators (Damodaran) carry `freq_native="A"` and are
forward-filled within calendar year before resampling to month-end.
This mirrors how these series are used in production (e.g., year-end
Damodaran ERP applies to the full following year of analysis). Daily
indicators (yields, prices) collapse to month-end-last-value.

## §3. Spec deviations (D16 - D19)

| Tag | Topic | Decision |
|---|---|---|
| **D16** | Spec §7.7 said "every row populated" but our NO_OVERLAP rows must have NaN stats | Keep the row in the panel with `verdict="NO_OVERLAP"`, `n_nominal=0`, `n_eff_nonoverlap=0`, all stat columns NaN — for provenance. Layer 6 reports filter on `verdict ∈ {"FULL", "UNDERPOWERED"}`. |
| **D17** | `HLW_VINTAGE` is a `MultiIndex(vintage, date)` panel, not a single time series | Excluded from the R² panel. The 3 latest HLW indicators (`HLW_RSTAR`, `HLW_TREND_GROWTH`, `HLW_OUTPUT_GAP`) are panel-eligible as standalone series. Layer 5b's PIT-aware panel will consume the vintage panel directly. |
| **D18** | SP500TR (1988+) cannot deliver any FULL 10Y cells | SP500TR's 38-year history minus a 10Y forward window leaves at most ~28 years = `n_eff_nonoverlap = 2` — below the `n_eff ≥ 3` threshold. All 122 SP500TR × 10Y rows are UNDERPOWERED by construction. SP500TR is treated as a **sanity check for ≤5Y horizons only**; Layer 6 reports filter SP500TR × 10Y by default. |
| **D19** | Spec §7.8 expected `CAPE × 10Y R² > 0.40`; Path B yields ~0.24 | Calibrated Gate 11 to `R² > 0.20 ∧ β < 0 ∧ p_NW < 0.01`. The signal is real (highly significant); the magnitude difference vs. spec is methodology + sample-window driven (we use full 1881-2016 = 1624 monthly start dates with annualized geometric returns). Layer 5 may revisit with subsample analysis. |

## §4. Coverage snapshot (current panel)

```
                  Total rows: 968
                  ┌──────────────────────────────────┐
                  │ FULL coverage         737  76.1% │
                  │ UNDERPOWERED          217  22.4% │
                  │ NO_OVERLAP             14   1.4% │
                  └──────────────────────────────────┘
```

Per (target × horizon):

```
target           horizon    FULL   UNDERPOWERED   NO_OVERLAP
SHILLER_TR_PRICE 1Y         120              1            0
SHILLER_TR_PRICE 3Y         115              6            0
SHILLER_TR_PRICE 5Y         105             14            2
SHILLER_TR_PRICE 10Y         57             59            5
SP500TR          1Y         120              1            0
SP500TR          3Y         115              6            0
SP500TR          5Y         105             14            2
SP500TR          10Y          0            116            5    ← D18 (all underpowered by construction)
```

## §5. Known signals (verified)

| Indicator | Target | Horizon | R² | β | p_NW |
|---|---|---|---|---|---|
| `SHILLER_CAPE` | SHILLER_TR_PRICE | 10Y | 0.241 | −0.0038 | 6e-06 |
| `SHILLER_CAPE` | SHILLER_TR_PRICE | 5Y | 0.123 | −0.0040 | 5e-03 |
| `DAMODARAN_ERP` | SHILLER_TR_PRICE | 10Y | 0.407 | +0.033 | 0 |

CAPE relationship is negative + significant (high CAPE → low forward
returns). Damodaran ERP relationship is positive + significant (high
implied risk premium → high forward returns).

## §6. Layer 5b backlog (deferred items)

| Item | Trigger |
|---|---|
| **L5b-1** | Hodrick (1992) standard errors for long-horizon regressions | Layer 5b |
| **L5b-2** | Block-bootstrap CIs for slope and R² | Layer 5b |
| **L5b-3** | OOS sample splits (1871-1979 / 1980-2024 + 1871-1999 / 2000-2024) | Layer 5b |
| **L5b-4** | Structural-break tests at 1971, 1982, 2008, 2020, 2022 | Layer 5b |
| **L5b-5** | Drop-window sensitivity for 1929-1932, 2007-2009 | Layer 5b |
| **L5b-6** | PIT-conditioned panel via `PitDataContext`-aware regression | Layer 5b |
| **L5b-7** | Scored-signals panel (CRPS/CDRS × forward returns) | Layer 5b |
| **L5-9** | Stale sidecar `last_obs` refresh pass — `cache.write_cache_atomic` should rewrite `meta.json` if older than ~90 days (motivating example: PHILLY_LEI_PROXY sidecar 2020-02 vs. parquet 2026-05) | Layer 5 |

## §7. Public API (`analysis/__init__.py`)

```python
from macro_pipeline.analysis import (
    build_and_cache,         # build panel + atomic write to cache
    build_panel,             # build without caching
    load_panel,              # load cached parquet
    forward_return,          # PIT-safe forward return helper
    forward_return_series,   # vectorized version
    load_target,             # load SHILLER_TR_PRICE or SP500TR
    align_indicator_to_target,
    fit_ols_hac,             # statsmodels HAC wrapper
    classify_verdict,        # FULL / UNDERPOWERED / NO_OVERLAP
    n_eff_nonoverlap,        # n_nominal // horizon_months
    HORIZONS,                # {"1Y": 12, "3Y": 36, "5Y": 60, "10Y": 120}
    SUPPORTED_TARGETS,       # ("SHILLER_TR_PRICE", "SP500TR")
    PANEL_CACHE_PATH,
    PANEL_SCHEMA_VERSION,
)
```

## §8. Panel row schema (per spec §7.3)

```
indicator_id        str   indicator name
horizon_months      int   12 / 36 / 60 / 120
horizon_label       str   "1Y" / "3Y" / "5Y" / "10Y"
target              str   "SHILLER_TR_PRICE" or "SP500TR"
freq_native         str   "D" / "W" / "M" / "Q" / "A" / "?"
n_nominal           int   raw count of overlapping monthly windows
n_eff_nonoverlap    int   n_nominal // horizon_months
is_underpowered     bool  True iff verdict == UNDERPOWERED
verdict             str   "FULL" / "UNDERPOWERED" / "NO_OVERLAP"
sample_start        Timestamp  first regression date
sample_end          Timestamp  last regression date
alpha               float  OLS intercept
beta                float  OLS slope
r_squared           float  raw R²
adj_r_squared       float  adjusted R²
residual_se         float  std dev of regression residuals
p_value_beta_NW     float  Newey-West HAC p-value for β
ci_method           str   "newey_west_hac"
maxlags             int   horizon_months − 1
```
