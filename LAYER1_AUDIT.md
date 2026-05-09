# Layer 1 Audit — Pre-Codex-Review Snapshot

**Date:** 2026-05-08
**Git tag:** `layer1-complete` (commit `f603cfe`)
**Repo:** https://github.com/mvfoundation01/macro-pipeline
**Python:** 3.12.10 / pandas 2.x / yfinance 1.3.0 / fredapi 0.5.x
**Total tests:** 180 passing
**Total source LOC:** 5,714 (loaders + preprocessing + validation + models)
**Total test LOC:** 1,838

Layer 1 (Raw Ingestion) is complete. This document captures the state of
the codebase at the close of Phase 4D so external reviewers can audit
methodology and code quality before we begin Layer 3 (derived series).

---

## 1. Cold-Cache Rebuild Performance

Reproduce with `rm -rf data/cache/* && python scripts/layer1_cold_sweep.py`.
All 7 gates pass on a cold rebuild.

| Phase | Wall time | Series count |
|---|---|---|
| Phase 1 (FRED API) | 15.94 s | 28 |
| Phase 2 (TV CSV) | 3.18 s | 22 |
| Phase 3 (Yahoo + CFTC SPX) | 15.38 s | 27 (26 Yahoo + 1 CFTC panel) |
| Phase 4A (NAAIM/FINRA/NY Fed/Damodaran) | 1.27 s | 8 |
| Phase 4B (Shiller/ACM/Fernald/HLW/IMF) | 5.36 s | 23 |
| Phase 4C (AAII/Atlanta wage/CFTC Treasury) | 1.89 s | 8 |
| Phase 4D (HLW vintage panel) | 2.49 s | 96 (32 vintages × 3 indicators) |
| **TOTAL** | **45.51 s** | **212** |

Network-bound phases (Phase 1 and Phase 3) account for 31 s / 45 s ≈ 69%
of total time. Local-file phases process ~50 series in 14 s.

---

## 2. Indicator Inventory by Tier

Per Build guide §21.1 tier taxonomy.

| Tier | Source | Count | Loader file | Notes |
|---|---|---|---|---|
| 1A | FRED API | 28 | `fred_loader.py` | Vintage-aware (ALFRED) for revised series |
| 1B | TradingView CSV | 20 | `tv_csv_loader.py` | Excludes 2 Tier 5 entries |
| 2A | Official files | 40 | (12 dedicated parsers) | See breakdown below |
| 2B | NY Fed `allmonth.xls` | 2 | `nyfed_recprob.py` | NYFED_REC_PROB + NBER_REC_LABEL |
| 2C | CFTC Socrata API | 1 panel (13 columns) | `cftc_tff_spx.py` | E-Mini SPX TFF |
| 3 | Yahoo Finance | 26 | `yahoo_loader.py` | Includes 3 dual-series (PRICE + TR) + ^SP500TR |
| 5 | Auxiliary (stale-but-valid) | 2 | (within `tv_csv_loader.py`) | Wilshire 5000 + OECD CCI |
| **TOTAL** | | **119 indicator IDs** | | |

### Tier 2A breakdown (40 series across 12 parsers)

| Loader | Count | Indicator IDs |
|---|---|---|
| `naaim.py` | 1 | NAAIM_NUMBER |
| `finra_margin.py` | 1 | FINRA_MARGIN_DEBT |
| `damodaran_erp.py` | 4 | DAMODARAN_{ERP, EY, DY, TBOND} |
| `shiller.py` | 9 | SHILLER_{PRICE, DIVIDEND, EARNINGS, CPI, GS10, REAL_PRICE, TR_PRICE, CAPE, TR_CAPE} |
| `acm_termpremium.py` | 3 | ACM_{TP_10Y, TP_5Y, RNY_10Y} |
| `fernald_tfp.py` | 2 | FERNALD_{TFP, TFP_UTIL} |
| `hlw_rstar.py` | 3 | HLW_{RSTAR, TREND_GROWTH, OUTPUT_GAP} (current vintage) |
| `imf_cofer.py` | 6 | {USD, EUR, JPY, GBP, CHF, CNY}_RESERVE_SHARE |
| `aaii.py` | 4 | AAII_{BULLISH, BEARISH, BULL_BEAR_SPREAD, BULL_8WMA} |
| `atlanta_wage.py` | 1 | ATLANTA_WAGE_OVERALL |
| `cftc_tff_treasury.py` | 3 | CFTC_TR_10Y_{LV_NET, AM_NET, DEALER_NET} |
| `hlw_rstar_vintage.py` | 3 (× 32 vintages) | HLW_{RSTAR, TREND_GROWTH, OUTPUT_GAP}_VINTAGE |

---

## 3. Date Coverage

- **Earliest first_obs across all series:** SHILLER_PRICE / SHILLER_DIVIDEND
  / SHILLER_EARNINGS / SHILLER_CPI / SHILLER_GS10 / SHILLER_REAL_PRICE
  / SHILLER_TR_PRICE — all from **1871-01-01** (155 years).
- **Most recent last_obs:** Yahoo daily series (SPX_TR, VIX_YAHOO, etc.)
  and FRED daily series (T10Y2Y, SOFR, etc.) all reach **2026-05-08**
  (today).
- **Master business-day index span across all series:**
  1871-01-01 → 2026-05-08, 40,530 business days.

### Top 10 longest histories

| Rank | Indicator | first_obs | Years |
|---|---|---|---|
| 1 | SHILLER_PRICE / DIVIDEND / EARNINGS / CPI / GS10 / REAL_PRICE / TR_PRICE | 1871-01 | 155 |
| 2 | SHILLER_CAPE / SHILLER_TR_CAPE | 1881-01 | 145 |
| 3 | TVC_US10Y | 1912-06 | 114 |
| 4 | INDPRO | 1919-01 | 107 |
| 5 | FERNALD_TFP / FERNALD_TFP_UTIL | 1947-04 | 79 |
| 6 | FRED_GDP (TV) | 1947-01 | 79 |
| 7 | FGRECPT / A091RC1Q027SBEA / PCEPILFE / PAYEMS / USREC | 1959 (project floor) | 67 |
| 8 | DAMODARAN_EY / DY / TBOND | 1961 | 65 |
| 9 | ACM_TP_10Y / TP_5Y / RNY_10Y | 1961-06 | 65 |
| 10 | HLW (current + 2025Q4 vintage) | 1961-Q1 | 65 |

The Phase-4B master-index extension fix (see §5 bug #11) recovered the
pre-1959 history that had been silently truncated. Without that fix,
Shiller, INDPRO, TVC_US10Y, FRED_GDP, and FRED_UMCSENT would all have
started at 1959-01-01.

---

## 4. Test Coverage

```
pytest tests/ --cov=src    →    180 passed in 163.70s    →    70% coverage
```

| Module | Stmts | Cover % | Notes |
|---|---|---|---|
| `src/__init__.py` | 0 | 100% | empty |
| `src/config.py` | 23 | 96% | unit registry, FRED metadata |
| `src/preprocessing.py` | 140 | **89%** | universal pipeline + helpers |
| `src/loaders/base.py` | 24 | 100% | `Loader` ABC + `IndicatorMetadata` |
| `src/loaders/hlw_rstar_vintage.py` | 126 | 87% | vintage panel + PIT lookup |
| `src/loaders/cftc_tff_treasury.py` | 58 | 84% | OFR HFM file |
| `src/loaders/fernald_tfp.py` | 66 | 82% | quarterly TFP |
| `src/loaders/shiller.py` | 78 | 82% | 9 series with decimal-date parser |
| `src/loaders/aaii.py` | 59 | 80% | 4 sentiment series |
| `src/loaders/atlanta_wage.py` | 51 | 80% | wage growth tracker |
| `src/loaders/finra_margin.py` | 50 | 80% | margin debt |
| `src/loaders/hlw_rstar.py` | 54 | 80% | current vintage |
| `src/loaders/naaim.py` | 46 | 80% | exposure index |
| `src/loaders/nyfed_recprob.py` | 69 | 80% | rec prob + NBER label |
| `src/loaders/damodaran_erp.py` | 53 | 79% | implied ERP + components |
| `src/loaders/imf_cofer.py` | 86 | 79% | reserve currency shares |
| `src/loaders/acm_termpremium.py` | 55 | 78% | term premium |
| `src/loaders/yahoo_loader.py` | 134 | 75% | 26-series registry |
| `src/loaders/fred_loader.py` | 107 | 74% | 28 FRED series with vintage |
| `src/loaders/tv_csv_loader.py` | 130 | 62% | TV CSV registry, tier-5 tagging |
| `src/loaders/cftc_tff_spx.py` | 84 | 54% | Socrata API |
| `src/validation.py` | 608 | 50% | 7 gate validators + render helpers |
| `src/models/regression_config.py` | 10 | 100% | constants |
| `src/models/scoring_config.py` | 8 | 100% | z-score policy + thresholds |
| **TOTAL** | **2,119** | **70%** | |

**Modules below 80%** are dominated by `__main__` CLI blocks and Gate
render helpers that aren't exercised by pytest. Functional logic in the
loaders is well-covered by per-loader tests + Gate-level tests.

---

## 5. Bugs Caught During Build (chronological)

Every issue surfaced through real-data inspection or gate-validation
failure during the build. None reached merge.

| # | Phase | Severity | Issue | Fix |
|---|---|---|---|---|
| 1 | 1 | Medium | `count_k` unit wrong for IC4WSA / CCSA (FRED returns raw counts, not thousands) | Added `count` unit; reassigned series |
| 2 | 1 | Low | SAHMREALTIME max 9.5 (COVID April 2020) above expected 6 | Widened expected_max to 10 |
| 3 | 1 | Low | INDPRO range starts pre-1959; min=3.7 below expected 20 | Widened to 3 (FRED returns from 1919) |
| 4 | 1 | Low | CFNAIMA3 / GDPNOW / STLFSI4 / CORESTICK ranges too narrow for COVID extremes | Widened registry bounds |
| 5 | 1 | Medium | `pct` unit range (-100, 100) too narrow for share-of-GDP series (debt/GDP=132%) | Widened to (-200, 500) |
| 6 | 1 | Medium | Vintage path (`get_series_all_releases`) was forward-padded to today by master-index | Added `master_end` parameter |
| 7 | 1 | Low | `flag_outliers_iqr` required ≥8 obs (test had 7) | Lowered threshold to ≥4 |
| 8 | 2 | Medium | TV's WALCL/WTREGEN/RRPONTSYD/GDP stored as **raw USD**, not millions/billions per FRED docs | Added `raw_unit_transform` per file |
| 9 | 2 | High | TV's WTREGEN pre-2002 values are ~1000× scale-mismatched (different precursor series) | Tagged with `data_quality_suspect_periods` |
| 10 | 2 | Low | `M_USD` unit min=100 too high for early WTREGEN | Lowered to 1.0 |
| 11 | 2→3 | Medium | Cached parquet column had loader prefix (`fred_PAYEMS`); should be bare ID for Layer-3 joins | Refactored `cache_series_to_parquet` API |
| 12 | 3 | Medium | yfinance `auto_adjust=True` is a NO-OP for ^GSPC/^NDX/^RUT (price-only indices, no embedded dividends) | Documented; added ^SP500TR for true TR; tagged `use_for` for downstream consumers |
| 13 | 3 | Low | ^MOVE Yahoo data is unofficial and intermittent | Added stale-cache fallback with `unofficial_yahoo` tag |
| 14 | 3 | Low | Yahoo VIX namespace collides with TV VIX | Renamed to `VIX_YAHOO` (`<id>_<source>` pattern on collision) |
| 15 | 4B | **Critical** | **`align_to_business_days` hard-coded master index to 1959-01-01**, silently dropping all pre-1959 history | Extended to `min(MASTER_INDEX_START, source.first_obs)`. Recovered Shiller 1871-1959 (88 years), TVC_US10Y 1912-1959, INDPRO 1919-1959, FRED_GDP 1947-1959, FRED_UMCSENT 1952-1959 |
| 16 | 4B | Medium | `index` unit ceiling (1e5) too low for cumulative TR series (Shiller TR_PRICE = 4.7M after 155y compounding) | Widened to 1e10 |
| 17 | 4B | Low | HLW r* 1960s peak above 6 | Widened expected_max to 7 |
| 18 | 4B | Low | Fernald TFP ±15 too narrow for 1947-1948 / COVID extremes | Widened Gate bound to ±20 |
| 19 | 4B | Low | Shiller CAPE 1920 trough = 4.78, below the prompt's "[5, 50]" floor | Loosened Gate floor to 4.0 |
| 20 | 4B | Medium | IMF COFER `SERIES_CODE` prefix is `G001` (the prompt said `G200`) | Used actual prefix; documented |
| 21 | 4B | Medium | Shiller decimal-date `2024.10` vs `2024.01` ambiguous when read as float (trailing zero lost) | Custom `_shiller_decimal_to_ts` formats with `.2f` then splits |
| 22 | 4C | Medium | AAII column names under `header=3` are terse codes (`Spread`, `Mov Avg`), not the multi-row banners | Updated registry |
| 23 | 4C | **High** | **CFTC TFF "POSITION" columns are NOTIONAL USD, not contract counts** (e.g., LF_TY_LONG_POSITION = $27.7B, not 27.7M contracts) | Rescaled to billions; new `B_USD_signed` unit; documented |
| 24 | 4C | Medium | OFR HFM file has per-contract data ONLY for Leveraged Funds; AM/DI/OR are aggregate Treasury (10Y-equivalent) | Tagged `extra.scope` to distinguish `true_10y_notional` vs `agg_treasury_10yreqv` |
| 25 | 4C | Low | OFR file has no `open_interest` column | Skipped OI series; documented for future Socrata fetch |
| 26 | 4C | Low | AAII Bull-Bear spread reaches +63 pp (late-1980s euphoria) | Loosened test/Gate bounds to [-65, +70] |
| 27 | 4C | Low | CFTC LV full-history median is small (basis trade ramped post-2018) | Test now checks 2020+ recent median |
| 28 | 4D | High | HLW vintage file ships **3 distinct schemas** (17, 21, 26 cols) across the 32 vintages | Layout dispatch by column count (`COLUMN_LAYOUTS[n_cols]`) |
| 29 | 4D | Medium | NY Fed paused HLW publication 2020Q3-2022Q3 (9-quarter gap) | PIT helper correctly returns 2020Q2 for asof in the gap; resumes at 2022Q4 from 2023-01-14 |
| 30 | 4D | Low | `read_excel(skiprows=6)` infers fewer columns when trailing data is all-NaN | Read full sheet first, then slice by row |

---

## 6. Known Caveats Carried Forward to Layer 3+

Documented in code; downstream layers must respect:

- **WTREGEN pre-2002**: tagged `data_quality_suspect_periods` (1986-01-01
  → 2002-12-17). Layer-3 derived series like Net Liquidity should
  explicitly mask this window or document its exclusion.
- **Atlanta Wage full-history-revisable**: `extra.full_history_revisable=True`
  + `vintage_caveat`. Backtests using the latest file as if observable
  in real time may have a ~1-3% optimistic bias from methodology
  back-revisions.
- **yfinance `auto_adjust` no-op for price indices**: `^GSPC`, `^NDX`,
  `^RUT` PRICE and TR variants carry identical numerical data. For
  authentic SPX total return use `^SP500TR` (1988+) and Shiller
  `SHILLER_TR_PRICE` (1871+, real). Established as
  `PRIMARY_REGRESSION_TARGET` in `src/models/regression_config.py`.
- **Tier 5 (Wilshire 5000 + OECD CCI)**: tagged `tier=5` with explicit
  `do_not_use_for=["real_time_signal", "current_alert", "live_crps",
  "live_cdrs"]`. Replacements named in metadata (Russell 3000 ×
  calibration, FRED USACSCICP02STSAM).
- **HLW 2020Q3-2022Q3 publication gap**: PIT lookup correctly returns
  2020Q2 throughout this window. No 2021 vintages exist.
- **CFTC TFF Treasury notional, not contracts**: unit is `B_USD_signed`
  (signed billions USD). Layer-5 CDRS scoring MUST z-score-normalize
  before composite — see `src/models/scoring_config.py`
  (`POSITIONING_INDICATORS_REQUIRING_ZSCORE`).
- **CFTC AM/DI 10Y are aggregate Treasury** (10Y-equivalent), not pure
  10Y futures. Only `CFTC_TR_10Y_LV_NET` is true 10Y. Tagged via
  `extra.scope`.
- **NBER label trailing-NaN**: `NBER_REC_LABEL` masked NaN past the last
  NBER determination (instead of forward-filling). Backtest training
  must not treat ffilled "0" as "no recession" beyond the last known
  call.
- **Damodaran annual year-end → next business day**: source dates are
  YYYY-12-31 (often weekends); after pipeline alignment, values become
  visible on the first business day of the next year (e.g. 1960-12-31
  data → 1961-01-02).

---

## 7. Dependency Graph

```
src/config.py                          (0 deps in src/)
   ↑                                       ↑
src/preprocessing.py                   src/loaders/base.py
   ↑                                       ↑
   └────────────┬─────────┬────────────────┘
                ↑         ↑
        all 17 src/loaders/*.py
                ↑
        src/validation.py
                ↑
            tests/

src/models/regression_config.py        (constants only, leaf)
src/models/scoring_config.py           (constants only, leaf)
```

- No circular imports (verified by clean test runs and Python's import
  resolution — `pytest` would surface circular imports as `ImportError`).
- `src/validation.py` imports from every loader; loaders import only
  from `src/config.py`, `src/preprocessing.py`, `src/loaders/base.py`.
- `src/models/*` are leaves — they don't import any pipeline code, so
  they're safe to use anywhere.

---

## 8. Conventions Established (Don't Break in Layer 3+)

1. **Cache file naming**: `data/cache/<source-prefix>_<INDICATOR_ID>.parquet`
   - `fred_*` (FRED API), `tv_*` (TradingView), `yahoo_*` (Yahoo),
     `cftc_*` (CFTC), `official_*` (everything from `data/raw/official/`).
   - The parquet **column** inside is always the bare `INDICATOR_ID`
     (no source prefix). This matters for Layer-3 cross-source joins.
   - Each cache file has a sidecar `<stem>.meta.json`.

2. **Indicator IDs are SCREAMING_SNAKE_CASE** with optional source
   suffix on collision (`VIX_YAHOO` for Yahoo's VIX vs TV's `VIX`).

3. **Universal preprocessing pipeline** (`run_universal_pipeline`):
   Stages 1.1-1.7 — validate → normalize-tz → flag-outliers (k=5, NOT
   removal) → handle-missing → align-to-business-days (forward-fill
   only) → unit-sanity → cache. ALL loaders pipe through this.

4. **Forward-fill ONLY** for frequency alignment. Never backfill.
   Vintage queries cap the master index at `vintage_date`.

5. **Master index extends back to source's first observation** (post the
   Phase-4B fix). `MASTER_INDEX_START` (1959-01-01) is a floor, not a
   ceiling.

6. **Outliers are FLAGGED, not removed.** Macro data legitimately
   contains 1973/1987/2008/2020 outliers. The `outlier_flags` series
   sits next to the data; consumers decide.

7. **Per-series `expected_min`/`expected_max`** in registry are
   authoritative. Unit-level `UNIT_EXPECTED_RANGES` is a coarse sanity
   check.

8. **Metadata schema**: every series carries `IndicatorMetadata` with
   `indicator_id, source, frequency, first_obs, last_obs, unit,
   release_lag_days, description, expected_min, expected_max,
   data_quality_suspect_periods, extra`. `extra` is the open dict for
   loader-specific fields (`tier`, `role`, `use_for`, `vintage_*`,
   `unofficial_yahoo`, `full_history_revisable`, etc.).

9. **PIT vintage queries** preserve point-in-time semantics: master
   index ends at `vintage_date` to prevent look-ahead bias.

10. **Backtest training labels** explicitly mask trailing NaN past last
    determination (e.g., NBER_REC_LABEL stops at NBER's last
    declaration, doesn't forward-fill 0).

11. **Regression target convention** (frozen in
    `src/models/regression_config.py`):
    `PRIMARY_REGRESSION_TARGET = "SHILLER_TR_PRICE"` (real total
    return). Yahoo `^SP500TR` is the modern cross-validation companion,
    not the primary target.

12. **Z-score normalization for positioning** (frozen in
    `src/models/scoring_config.py`): every series in
    `POSITIONING_INDICATORS_REQUIRING_ZSCORE` must be transformed
    before composite scoring (units differ across CFTC SPX = contracts,
    CFTC Treasury = B_USD_signed, FINRA = M_USD, NAAIM =
    pct_exposure).

13. **Gate validators in `src/validation.py`**: every phase has a Gate
    function `validate_gateN_*` returning `GateReport(name, passed,
    findings, warnings, summary)`. CLI `python -m src.validation gateN`
    runs end-to-end.

---

## 9. Files Modified During Build

```
src/
├── __init__.py                       (0)
├── config.py                       (264)   FRED registry, units, paths
├── preprocessing.py                (318)   universal pipeline 1.1-1.7
├── validation.py                  (1298)   7 gate validators + CLI
├── loaders/
│   ├── __init__.py                   (0)
│   ├── base.py                      (59)   Loader ABC, IndicatorMetadata
│   ├── fred_loader.py              (284)   28 FRED series + ALFRED vintage
│   ├── tv_csv_loader.py            (442)   22 TV CSVs + tier-5 tagging
│   ├── yahoo_loader.py             (499)   26 Yahoo tickers + dual-series
│   ├── cftc_tff_spx.py             (201)   Socrata E-Mini SPX TFF
│   ├── naaim.py                    (121)
│   ├── finra_margin.py             (132)
│   ├── nyfed_recprob.py            (196)
│   ├── damodaran_erp.py            (138)
│   ├── shiller.py                  (194)
│   ├── acm_termpremium.py          (137)
│   ├── fernald_tfp.py              (150)
│   ├── hlw_rstar.py                (149)   current vintage
│   ├── imf_cofer.py                (193)
│   ├── aaii.py                     (163)
│   ├── atlanta_wage.py             (138)
│   ├── cftc_tff_treasury.py        (170)
│   └── hlw_rstar_vintage.py        (358)   PIT helper + 32-vintage panel
├── models/
│   ├── __init__.py                   (0)
│   ├── regression_config.py         (55)   PRIMARY_REGRESSION_TARGET
│   └── scoring_config.py            (55)   POSITIONING_… + thresholds
TOTAL                              5,714 LOC

tests/
├── test_fred_loader.py             (150)
├── test_tv_loader.py               (241)
├── test_yahoo_loader.py            (299)
├── test_cftc_tff_spx.py            (117)
├── test_gate3.py                    (26)
├── test_official_4a.py             (225)
├── test_official_4b.py             (275)
├── test_official_4c.py             (240)
├── test_official_4d.py             (265)
TOTAL                              1,838 LOC

scripts/
└── layer1_cold_sweep.py            (~110)   cold-cache rebuild + timing
```

Plus `pyproject.toml`, `.env`, `.gitignore`, `.python-version`.

---

## 10. Open Questions for Codex Review

(Things I'd most like a fresh pair of eyes on.)

1. **Universal pipeline ordering** (Stages 1.1→1.7): is there a case
   where outlier flagging *before* missing-data handling produces
   different results than the reverse? The current order flags raw
   gaps as outliers — possibly the wrong side of the trade-off.

2. **Forward-fill semantics across mixed cadence**: when a weekly
   series starts mid-week and a monthly series starts mid-month, the
   business-day reindex with ffill may not match the user's mental
   model of "as known on date t". Is the explicit
   `release_lag_days` field correctly threaded into the PIT logic, or
   are we leaning too hard on raw publication date?

3. **Vintage handling for non-FRED series**: only HLW has a
   vintage-aware loader. PAYEMS, INDPRO, RSAFS, etc. have ALFRED
   vintage support via `fred.get_series_all_releases`, but I haven't
   built a vintage-panel cache for them. Is the lazy-vintage pattern
   sufficient, or should we materialize panels?

4. **`auto_adjust=True` on `^GSPC` is a no-op** — confirmed by direct
   data inspection. Is there a Yahoo ticker or alternative library
   that would give a true SPX TR back to 1928? (Currently we have
   ^SP500TR from 1988 and Shiller TR_PRICE from 1871.)

5. **CFTC OFR file has no open interest** — should we add a Phase-3
   companion that fetches 10-year T-Note OI from Socrata
   (cftc_contract_market_code='043602')? The infrastructure already
   exists in `cftc_tff_spx.py`.

6. **Shiller column-position dispatch**: I'm using positional
   `iloc[:, N]` because Shiller renames columns each release. If
   Shiller adds a column at position ≤ 14, the TR_CAPE extraction
   breaks. Should we add a header-text fingerprint check that fails
   loudly if the layout shifts?

7. **AAII source-storage convention**: I multiply by 100 to convert
   decimal-share to percent. If AAII switches to publishing percent
   directly (some downloads do), the same code would silently produce
   values 100× too large. Add a magnitude check?

8. **Cache freshness vs accuracy**: `CACHE_TTL_DAYS = {"D":1, "W":7,
   "M":30, "Q":30}`. For series with rolling revisions (PAYEMS,
   GDPNow), should we shorten to 0 (always-refetch) at the cost of
   API quota? Or is once-daily acceptable?

9. **TimeStamp normalization**: pandas 2.x deprecation warnings on
   `pd.concat(..., axis=1)` of DatetimeIndex frames. Suppressed for
   now; need explicit `sort=False` everywhere we concat.

10. **Test coverage gaps**: `validation.py` is at 50% (the CLI/render
    paths aren't exercised by pytest). Worth a `tests/test_cli.py`?

---

## 11. Open Questions for ChatGPT Methodology Review

(Things to flag at the methodology layer, not the code layer.)

1. **Real vs nominal regression target**: convention is locked to
   Shiller TR_PRICE (real, CPI-adjusted) per
   `regression_config.py`. Does the academic literature support real
   over nominal for the 1Y/3Y/5Y/10Y horizons? Inflation-regime
   contamination is the standard argument; counterargument is
   compositional drift in the deflator.

2. **NBER recession count for 1959-2024**: this dataset shows 9 0→1
   transitions; the Build guide §21.2 lists 9 recessions. The Phase 4A
   prompt expected 8 (perhaps excluding 2020's 2-month recession).
   Should the 2020 event be excluded from training, or treated as a
   regime-shift outlier with reduced weight?

3. **Atlanta Wage full-history revisability**: the Atlanta Fed
   re-estimates the entire history with each release. Backtesting
   with the latest file overstates the signal's real-time precision.
   What's the right correction — retrain on each vintage (no vintage
   file available), or apply a global ~1-3% bias adjustment?

4. **CFTC positioning z-score windows**: 3-year vs 5-year z-score
   windows for positioning indicators. The bond basis trade only
   ramped up post-2018, so the rolling z-score behavior differs
   sharply pre/post that regime change. Is a 3Y window too short
   when regime breaks happen?

5. **Tier 5 auxiliary data in regression**: Wilshire 5000 (stale
   2024-04) and OECD CCI (stale 2024-01) are blocked from real-time
   scoring but allowed in regression. For long-horizon (10Y) forward
   returns, should we use them at all, given that their effective
   sample ends 2024?

6. **HLW vintage 2020Q3-2022Q3 gap**: 9 quarters with no PIT update.
   The PIT helper correctly returns 2020Q2 throughout, but this means
   any backtest in that window is using a stale r* estimate. Is this
   the correct behavior, or should we interpolate / use a different
   r* proxy (Lubik-Matthes, alternative LW model)?

7. **SHILLER_TR_PRICE as the ground truth**: this is a real-CPI series
   reconstructed by Shiller; its CPI back-extension to 1871 has known
   data quality issues (Boskin Commission methodology debates).
   Should we constrain the regression sample to post-1947 (modern
   CPI) or post-1990 (modern reporting)?

8. **CFTC TFF Treasury "10Y-equivalent" weighting**: AM/DI aggregate
   Treasury positions are reported in 10Y duration-equivalent
   notional. This bundles 2Y/5Y/10Y/30Y futures into one number.
   For our 10Y rate signal, is this the right slice or does it
   introduce noise from short/long-end positioning?

---

## 12. Next Steps After Reviews

1. Aggregate Codex + ChatGPT feedback into a single change list.
2. Update Build guide v1.2 → v1.3 with reviewer findings.
3. Begin **Layer 3 (Derived Series)**:
   - T10Y3M = `TVC_US10Y - TVC_US03MY`
   - T10Y2Y from FRED API (already loaded as scalar)
   - HY-IG spread = `BAMLH0A0HYM2 - BAMLC0A0CM`
   - CCC-BB distress = `BAMLH0A3HYC - BAMLH0A1HYBB`
   - Net Liquidity = `WALCL - WTREGEN - RRPONTSYD` (M_USD throughout)
   - Buffett Indicator HYBRID = stitch Wilshire (Tier 5, 1970-2024-04)
     with Russell 3000 × calibration (2024-04+)
   - ERP = `Earnings Yield - 10Y Treasury`
   - Real ERP = `Earnings Yield - DFII10`
   - Real Rate − r* = `(FedFunds - Core PCE YoY) - HLW_RSTAR`
   - Forward returns from `SHILLER_TR_PRICE` for {12, 36, 60, 120}M
4. Then **Layer 4** (feature engineering: level, MoM, YoY, z-score,
   percentile) and **Layer 5** (CRPS + CDRS composites + R²
   regression table).

---

**Status: Layer 1 closed. Awaiting reviewer feedback before Layer 3.**
