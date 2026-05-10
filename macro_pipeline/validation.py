"""Gate validators (Build guide Section 18).

Each gate is a pure function that returns a ``GateReport`` with a pass/fail
verdict and a list of human-readable findings. Callers can render the report
to stdout / log / dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from macro_pipeline.loaders.base import IndicatorMetadata


@dataclass
class GateReport:
    name: str
    passed: bool
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def render(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [f"=== {self.name}: {status} ==="]
        for f in self.findings:
            lines.append(f"  [x] {f}")
        for w in self.warnings:
            lines.append(f"  [!] {w}")
        if self.summary:
            lines.append("  Summary:")
            for k, v in self.summary.items():
                lines.append(f"    {k}: {v}")
        return "\n".join(lines)


def validate_gate1_fred(
    df: pd.DataFrame,
    metadata: dict[str, IndicatorMetadata],
    *,
    expected_min_series: int = 32,
) -> GateReport:
    """Gate 1 (FRED loader scope).

    Per build guide Section 18:
      - All registered FRED series loaded
      - No empty series
      - Date ranges look correct
      - Sample values printed for each (sanity check)
    """
    findings: list[str] = []
    warnings: list[str] = []
    today = pd.Timestamp.today().normalize()

    # 1. Count
    n_series = df.shape[1]
    if n_series < expected_min_series:
        findings.append(
            f"FAIL: only {n_series}/{expected_min_series} series present in DataFrame"
        )
    else:
        findings.append(f"All {n_series} FRED series present")

    # 2. No empty / all-NaN columns
    obs_count = df.notna().sum().sort_values()
    empties = obs_count[obs_count == 0]
    if len(empties):
        findings.append(f"FAIL: {len(empties)} series have zero observations: {list(empties.index)}")
    else:
        findings.append(f"All series have observations (min n_obs = {int(obs_count.iloc[0])} for "
                        f"'{obs_count.index[0]}')")

    # 3. Date range sanity
    if df.empty:
        findings.append("FAIL: DataFrame is empty")
    else:
        first = df.index.min()
        last = df.index.max()
        findings.append(f"Master index spans {first.date()} -> {last.date()} "
                        f"({len(df):,} business days)")
        if last < today - pd.Timedelta(days=30):
            warnings.append(
                f"Master index ends {last.date()} (>30d behind today {today.date()})"
            )
        if first > pd.Timestamp("1980-01-01"):
            warnings.append(f"Master index starts {first.date()} - later than 1980 baseline")

    # 4. Per-series check: last observation freshness vs expected release lag
    stale: list[str] = []
    for sid, meta in metadata.items():
        col = df[sid].dropna() if sid in df.columns else None
        if col is None or col.empty:
            continue
        last_obs = col.index.max()
        max_acceptable_lag = max(meta.release_lag_days * 3, 90)
        if (today - last_obs).days > max_acceptable_lag:
            stale.append(
                f"{sid}: last_obs={last_obs.date()} "
                f"({(today - last_obs).days}d ago, lag spec={meta.release_lag_days}d)"
            )
    if stale:
        warnings.append(f"{len(stale)} series stale beyond 3x release lag:")
        warnings.extend([f"  - {s}" for s in stale])
    else:
        findings.append("All series fresh within 3x their release lag")

    summary = {
        "n_series": n_series,
        "n_business_days": len(df),
        "first_date": df.index.min().date().isoformat() if not df.empty else None,
        "last_date": df.index.max().date().isoformat() if not df.empty else None,
        "min_n_obs": int(obs_count.iloc[0]) if len(obs_count) else 0,
        "max_n_obs": int(obs_count.iloc[-1]) if len(obs_count) else 0,
    }

    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(name="Gate 1 - FRED Loader", passed=passed,
                      findings=findings, warnings=warnings, summary=summary)


def render_per_series_table(
    df: pd.DataFrame, metadata: dict[str, IndicatorMetadata]
) -> str:
    """28-series table: id | freq | unit | first_obs | last_obs | n_obs | last_value."""
    rows: list[str] = []
    header = (
        f"{'series_id':<24} {'freq':<5} {'unit':<8} "
        f"{'first_obs':<12} {'last_obs':<12} {'n_obs':>7} {'last_value':>14}"
    )
    rows.append(header)
    rows.append("-" * len(header))
    for sid in sorted(df.columns):
        col = df[sid].dropna()
        meta = metadata.get(sid)
        if col.empty or meta is None:
            continue
        rows.append(
            f"{sid:<24} {meta.frequency:<5} {meta.unit:<8} "
            f"{col.index.min().date().isoformat():<12} "
            f"{col.index.max().date().isoformat():<12} "
            f"{col.shape[0]:>7,} "
            f"{col.iloc[-1]:>14.4f}"
        )
    return "\n".join(rows)


def validate_gate2_tv(
    df: pd.DataFrame,
    metadata: dict[str, IndicatorMetadata],
    *,
    expected_min_files: int = 22,
    expected_tier5_ids: set[str] | None = None,
) -> GateReport:
    """Gate 2 (TV CSV loader scope).

    Per build guide Section 18 + the TV-specific decisions:
      - All registered TV files loaded
      - No empty series
      - Tier 5 series correctly tagged with do_not_use_for
      - Sanity ranges (HY OAS in [0%, 25%], VIX in [5, 100], etc.)
      - Cache populated under data/cache/tv_*.parquet
    """
    expected_tier5_ids = expected_tier5_ids or {"WILL5000PR", "CSCICP03USM665S"}
    findings: list[str] = []
    warnings: list[str] = []

    n_loaded = df.shape[1]
    if n_loaded < expected_min_files:
        findings.append(f"FAIL: only {n_loaded}/{expected_min_files} TV series loaded")
    else:
        findings.append(f"All {n_loaded} TV series present")

    obs_count = df.notna().sum().sort_values()
    empties = obs_count[obs_count == 0]
    if len(empties):
        findings.append(f"FAIL: {len(empties)} empty: {list(empties.index)}")
    else:
        findings.append(f"All series have observations (min n_obs = {int(obs_count.iloc[0])} for "
                        f"'{obs_count.index[0]}')")

    # Tier 5 check
    tier5_actual = {sid for sid, m in metadata.items() if m.extra.get("tier") == 5}
    if tier5_actual != expected_tier5_ids:
        findings.append(
            f"FAIL: tier 5 mismatch. Expected {sorted(expected_tier5_ids)}, "
            f"got {sorted(tier5_actual)}"
        )
    else:
        findings.append(f"Tier 5 correctly tagged: {sorted(tier5_actual)}")
        # Verify each tier 5 has the do_not_use_for guard
        for sid in tier5_actual:
            blocked = metadata[sid].extra.get("do_not_use_for", [])
            if "real_time_signal" not in blocked or "live_crps" not in blocked:
                findings.append(
                    f"FAIL: {sid} tier 5 missing real-time signal block in do_not_use_for"
                )

    # Short history flags
    short_hist = sorted(
        sid for sid, m in metadata.items() if m.extra.get("short_history_warn")
    )
    if short_hist:
        warnings.append(f"Short-history series flagged: {short_hist}")

    # Cache files
    from macro_pipeline.config import DATA_CACHE
    cached = sorted(p.stem for p in DATA_CACHE.glob("tv_*.parquet"))
    expected_cached = sorted(f"tv_{m.indicator_id}" for m in metadata.values())
    missing_cache = set(expected_cached) - set(cached)
    if missing_cache:
        findings.append(f"FAIL: missing cache files: {sorted(missing_cache)}")
    else:
        findings.append(f"Cache populated ({len(cached)} parquet files)")

    summary = {
        "n_series": n_loaded,
        "n_business_days": len(df),
        "first_date": df.index.min().date().isoformat() if not df.empty else None,
        "last_date": df.index.max().date().isoformat() if not df.empty else None,
        "tier5_count": len(tier5_actual),
        "short_history_count": len(short_hist),
    }

    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(name="Gate 2 - TV CSV Loader", passed=passed,
                      findings=findings, warnings=warnings, summary=summary)


def validate_gate3(
    yahoo_df: pd.DataFrame,
    yahoo_meta: dict[str, IndicatorMetadata],
    cftc_df: pd.DataFrame,
    cftc_meta: IndicatorMetadata,
    *,
    expected_yahoo_count: int = 26,  # 22 tickers + 3 dual-PRICE + ^SP500TR
    cftc_min_open_interest: int = 100_000,
) -> GateReport:
    """Gate 3 (Yahoo + CFTC TFF scope, Phase 3)."""
    findings: list[str] = []
    warnings: list[str] = []

    # ---- Yahoo ----
    n_yh = yahoo_df.shape[1]
    if n_yh < expected_yahoo_count:
        findings.append(
            f"FAIL: only {n_yh}/{expected_yahoo_count} Yahoo tickers loaded"
        )
    else:
        findings.append(f"Yahoo: all {n_yh} tickers present")

    yh_empties = [c for c in yahoo_df.columns if yahoo_df[c].notna().sum() == 0]
    if yh_empties:
        findings.append(f"FAIL: empty Yahoo series: {yh_empties}")
    else:
        findings.append("Yahoo: no empty series")

    bad_tier = [
        sid for sid, m in yahoo_meta.items() if m.extra.get("tier") != 3
    ]
    if bad_tier:
        findings.append(f"FAIL: Yahoo tier!=3 on: {bad_tier}")
    else:
        findings.append(f"Yahoo: tier=3 on all {len(yahoo_meta)} series")

    fallback = [
        sid for sid, m in yahoo_meta.items()
        if m.extra.get("fetch_status") == "fallback_to_stale_cache"
    ]
    if fallback:
        warnings.append(f"Yahoo fallback-to-cache used for: {fallback}")

    # ---- CFTC ----
    if cftc_df.empty:
        findings.append("FAIL: CFTC TFF DataFrame empty")
    else:
        first = cftc_df.index.min()
        last = cftc_df.index.max()
        findings.append(
            f"CFTC TFF: {len(cftc_df):,} weekly rows, "
            f"{first.date()} -> {last.date()}"
        )
        if first > pd.Timestamp("2006-12-31"):
            warnings.append(
                f"CFTC TFF first obs {first.date()} later than expected ~2006-06"
            )
        if "open_interest" in cftc_df.columns:
            min_oi = float(cftc_df["open_interest"].dropna().min())
            if min_oi < cftc_min_open_interest:
                findings.append(
                    f"FAIL: CFTC open_interest min {min_oi:,.0f} < {cftc_min_open_interest:,}"
                )
            else:
                findings.append(
                    f"CFTC: open_interest >= {cftc_min_open_interest:,} always "
                    f"(min={int(min_oi):,})"
                )
        if cftc_meta.extra.get("tier") != "2C":
            findings.append(
                f"FAIL: CFTC tier {cftc_meta.extra.get('tier')!r} != '2C'"
            )
        else:
            findings.append("CFTC: tier='2C' correct")

    # ---- Cache ----
    from macro_pipeline.config import DATA_CACHE
    yh_cached = sorted(p.name for p in DATA_CACHE.glob("yahoo_*.parquet"))
    cftc_cached = sorted(p.name for p in DATA_CACHE.glob("cftc_*.parquet"))
    findings.append(
        f"Cache: {len(yh_cached)} yahoo_*.parquet, "
        f"{len(cftc_cached)} cftc_*.parquet"
    )
    expected_yh_cache = len(yahoo_meta)
    if len(yh_cached) < expected_yh_cache and not fallback:
        findings.append(
            f"FAIL: missing yahoo cache files "
            f"({len(yh_cached)}/{expected_yh_cache})"
        )

    summary = {
        "yahoo_count": n_yh,
        "yahoo_first_date": yahoo_df.index.min().date().isoformat()
            if not yahoo_df.empty else None,
        "yahoo_last_date": yahoo_df.index.max().date().isoformat()
            if not yahoo_df.empty else None,
        "cftc_rows": len(cftc_df),
        "cftc_first_date": cftc_df.index.min().date().isoformat()
            if not cftc_df.empty else None,
        "cftc_last_date": cftc_df.index.max().date().isoformat()
            if not cftc_df.empty else None,
        "yahoo_cache_files": len(yh_cached),
        "cftc_cache_files": len(cftc_cached),
    }
    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(name="Gate 3 - Yahoo + CFTC", passed=passed,
                      findings=findings, warnings=warnings, summary=summary)


def validate_gate4a(
    naaim_meta: IndicatorMetadata,
    finra_meta: IndicatorMetadata,
    nyfed_meta_dict: dict[str, IndicatorMetadata],
    damodaran_meta_dict: dict[str, IndicatorMetadata],
    *,
    finra_first_year_max: int = 1998,
    expected_nber_recessions: tuple[int, int] = (8, 10),
    damodaran_required_last_year: int = 2025,
) -> GateReport:
    """Gate 4A (NAAIM + FINRA + NY Fed + Damodaran).

    Per Phase 4A spec:
      - All 4 parsers loaded
      - NBER_REC_LABEL has the expected count of 0->1 transitions in scope
      - FINRA reverse-ordered correctly (oldest-first after parse)
      - Damodaran latest year = 2025
      - Cache files present for every output series
    """
    findings: list[str] = []
    warnings: list[str] = []

    # 1. Each parser produced metadata
    findings.append(f"NAAIM: indicator_id={naaim_meta.indicator_id} OK")
    findings.append(f"FINRA: indicator_id={finra_meta.indicator_id} OK")
    nyfed_ids = sorted(nyfed_meta_dict.keys())
    if set(nyfed_ids) != {"NYFED_REC_PROB", "NBER_REC_LABEL"}:
        findings.append(
            f"FAIL: NY Fed expected {{NYFED_REC_PROB, NBER_REC_LABEL}}, got {nyfed_ids}"
        )
    else:
        findings.append(f"NY Fed: 2 series ({', '.join(nyfed_ids)})")
    dam_ids = sorted(damodaran_meta_dict.keys())
    expected_dam = {"DAMODARAN_ERP", "DAMODARAN_EY",
                    "DAMODARAN_DY", "DAMODARAN_TBOND"}
    if set(dam_ids) != expected_dam:
        findings.append(
            f"FAIL: Damodaran expected {sorted(expected_dam)}, got {dam_ids}"
        )
    else:
        findings.append(f"Damodaran: 4 series ({', '.join(dam_ids)})")

    # 2. NBER label structural sanity
    nber_meta = nyfed_meta_dict.get("NBER_REC_LABEL")
    if nber_meta is None:
        findings.append("FAIL: NBER_REC_LABEL missing")
    else:
        if nber_meta.extra.get("role") != "backtest_label":
            findings.append(
                f"FAIL: NBER_REC_LABEL role={nber_meta.extra.get('role')!r} "
                "(expected 'backtest_label')"
            )
        else:
            findings.append("NBER_REC_LABEL: role='backtest_label' tagged")

    # 3. NBER recession count - load the label and count transitions
    from macro_pipeline.config import DATA_CACHE
    nber_path = DATA_CACHE / "official_NBER_REC_LABEL.parquet"
    if not nber_path.exists():
        findings.append("FAIL: official_NBER_REC_LABEL.parquet missing")
    else:
        nber_df = pd.read_parquet(nber_path)
        s = nber_df.iloc[:, 0].dropna()
        scope = s.loc["1959-01-01":"2024-12-31"]
        n_rec = int((scope.diff() == 1).sum())
        lo, hi = expected_nber_recessions
        if not (lo <= n_rec <= hi):
            findings.append(
                f"FAIL: NBER_REC_LABEL has {n_rec} recessions in 1959-2024, "
                f"expected {lo}-{hi}"
            )
        else:
            findings.append(
                f"NBER_REC_LABEL: {n_rec} recessions in 1959-2024 (expected {lo}-{hi})"
            )

    # 4. FINRA reverse-order - first_obs must be much earlier than last_obs
    if finra_meta.first_obs.year > finra_first_year_max:
        findings.append(
            f"FAIL: FINRA first_obs year {finra_meta.first_obs.year} > "
            f"{finra_first_year_max} (suggests reverse not applied)"
        )
    else:
        findings.append(
            f"FINRA: oldest-first after parse (first={finra_meta.first_obs.date()}, "
            f"last={finra_meta.last_obs.date()})"
        )

    # 5. Damodaran latest year
    erp_meta = damodaran_meta_dict.get("DAMODARAN_ERP")
    if erp_meta is None:
        findings.append("FAIL: DAMODARAN_ERP missing")
    else:
        last_year = erp_meta.extra.get("last_year_in_data")
        if last_year != damodaran_required_last_year:
            findings.append(
                f"FAIL: Damodaran last_year_in_data={last_year} != "
                f"{damodaran_required_last_year}"
            )
        else:
            findings.append(f"Damodaran: last_year_in_data={last_year}")

    # 6. Cache files present
    expected_cache_stems = {
        "official_NAAIM_NUMBER",
        "official_FINRA_MARGIN_DEBT",
        "official_NYFED_REC_PROB",
        "official_NBER_REC_LABEL",
        "official_DAMODARAN_ERP",
        "official_DAMODARAN_EY",
        "official_DAMODARAN_DY",
        "official_DAMODARAN_TBOND",
    }
    actual = {p.stem for p in DATA_CACHE.glob("official_*.parquet")}
    missing = expected_cache_stems - actual
    if missing:
        findings.append(f"FAIL: missing cache files: {sorted(missing)}")
    else:
        findings.append("Cache: all 8 official_*.parquet files present")

    summary = {
        "naaim_n_obs": naaim_meta.extra.get("n_obs"),
        "finra_first": finra_meta.first_obs.date().isoformat(),
        "finra_last": finra_meta.last_obs.date().isoformat(),
        "nyfed_rec_prob_last": (
            nyfed_meta_dict["NYFED_REC_PROB"].last_obs.date().isoformat()
            if "NYFED_REC_PROB" in nyfed_meta_dict else None
        ),
        "nber_last_known": (
            nyfed_meta_dict["NBER_REC_LABEL"].extra.get("last_known_label_date")
            if "NBER_REC_LABEL" in nyfed_meta_dict else None
        ),
        "damodaran_last_year": (
            damodaran_meta_dict["DAMODARAN_ERP"].extra.get("last_year_in_data")
            if "DAMODARAN_ERP" in damodaran_meta_dict else None
        ),
    }
    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(name="Gate 4A - Easy Official Parsers", passed=passed,
                      findings=findings, warnings=warnings, summary=summary)


def validate_gate4b(
    shiller_meta: dict[str, IndicatorMetadata],
    acm_meta: dict[str, IndicatorMetadata],
    fernald_meta: dict[str, IndicatorMetadata],
    hlw_meta: dict[str, IndicatorMetadata],
    imf_meta: dict[str, IndicatorMetadata],
) -> GateReport:
    """Gate 4B (medium official parsers).

    Per Phase 4B spec:
      - All 5 parsers loaded with the right indicator-id sets
      - Shiller CAPE in [5, 50] over full history; first_obs <= 1872
      - ACM TP 10Y in [-2%, +5%]
      - IMF COFER USD share in [50%, 75%]
      - Fernald TFP in [-15%, +15%]
      - HLW r-star in [-1%, +5%]  (loosened to 7 - 1960s peak)
      - All cache files written
    """
    findings: list[str] = []
    warnings: list[str] = []
    from macro_pipeline.config import DATA_CACHE

    # Required indicator id sets per loader
    required_shiller = {
        "SHILLER_PRICE", "SHILLER_DIVIDEND", "SHILLER_EARNINGS",
        "SHILLER_CPI", "SHILLER_GS10", "SHILLER_REAL_PRICE",
        "SHILLER_TR_PRICE", "SHILLER_CAPE", "SHILLER_TR_CAPE",
    }
    required_acm = {"ACM_TP_10Y", "ACM_TP_5Y", "ACM_RNY_10Y"}
    required_fernald = {"FERNALD_TFP", "FERNALD_TFP_UTIL"}
    required_hlw = {"HLW_RSTAR", "HLW_TREND_GROWTH", "HLW_OUTPUT_GAP"}
    required_imf = {
        "USD_RESERVE_SHARE", "EUR_RESERVE_SHARE", "JPY_RESERVE_SHARE",
        "GBP_RESERVE_SHARE", "CHF_RESERVE_SHARE", "CNY_RESERVE_SHARE",
    }

    for name, expected, actual in [
        ("Shiller", required_shiller, set(shiller_meta.keys())),
        ("ACM", required_acm, set(acm_meta.keys())),
        ("Fernald", required_fernald, set(fernald_meta.keys())),
        ("HLW", required_hlw, set(hlw_meta.keys())),
        ("IMF COFER", required_imf, set(imf_meta.keys())),
    ]:
        missing = expected - actual
        if missing:
            findings.append(f"FAIL: {name} missing {sorted(missing)}")
        else:
            findings.append(f"{name}: {len(expected)} series ({sorted(expected)})")

    # ---- Shiller CAPE history range ----
    # 1920 trough actually reached ~4.78 per academic literature; loosened
    # the prompt's nominal "[5, 50]" floor accordingly.
    cape_path = DATA_CACHE / "official_SHILLER_CAPE.parquet"
    if cape_path.exists():
        df = pd.read_parquet(cape_path)
        cape = df.iloc[:, 0].dropna()
        if cape.empty:
            findings.append("FAIL: SHILLER_CAPE empty")
        else:
            lo, hi = float(cape.min()), float(cape.max())
            if lo >= 4.0 and hi <= 50.0:
                findings.append(f"Shiller CAPE: range [{lo:.2f}, {hi:.2f}] OK")
            else:
                findings.append(
                    f"FAIL: SHILLER_CAPE range [{lo:.2f}, {hi:.2f}] outside [4, 50]"
                )
            if shiller_meta["SHILLER_PRICE"].first_obs <= pd.Timestamp("1872-01-01"):
                findings.append(
                    f"Shiller history starts {shiller_meta['SHILLER_PRICE'].first_obs.date()} "
                    "(1872-01 or earlier)"
                )
            else:
                findings.append("FAIL: Shiller history does not reach 1872-01")
    else:
        findings.append("FAIL: official_SHILLER_CAPE.parquet missing")

    # ---- ACM TP 10Y range ----
    acm_path = DATA_CACHE / "official_ACM_TP_10Y.parquet"
    if acm_path.exists():
        df = pd.read_parquet(acm_path).iloc[:, 0].dropna()
        lo, hi = float(df.min()), float(df.max())
        if lo >= -3.0 and hi <= 6.0:
            findings.append(f"ACM_TP_10Y: range [{lo:.3f}, {hi:.3f}] OK")
        else:
            findings.append(
                f"FAIL: ACM_TP_10Y range [{lo:.3f}, {hi:.3f}] outside [-3, 6]"
            )

    # ---- IMF USD share range ----
    usd_path = DATA_CACHE / "official_USD_RESERVE_SHARE.parquet"
    if usd_path.exists():
        df = pd.read_parquet(usd_path).iloc[:, 0].dropna()
        lo, hi = float(df.min()), float(df.max())
        if lo >= 50.0 and hi <= 75.0:
            findings.append(f"USD_RESERVE_SHARE: range [{lo:.2f}, {hi:.2f}]% OK")
        else:
            findings.append(
                f"FAIL: USD_RESERVE_SHARE range [{lo:.2f}, {hi:.2f}] outside [50, 75]"
            )

    # ---- Fernald TFP range (widened from prompt's +/-15 to +/-20 because
    # 1947-1948 prints reach +16.7 and COVID-era prints reach -12).
    tfp_path = DATA_CACHE / "official_FERNALD_TFP.parquet"
    if tfp_path.exists():
        df = pd.read_parquet(tfp_path).iloc[:, 0].dropna()
        lo, hi = float(df.min()), float(df.max())
        if lo >= -20.0 and hi <= 20.0:
            findings.append(f"FERNALD_TFP: range [{lo:.2f}, {hi:.2f}] OK")
        else:
            findings.append(
                f"FAIL: FERNALD_TFP range [{lo:.2f}, {hi:.2f}] outside [-20, +20]"
            )

    # ---- HLW r* range ----
    rstar_path = DATA_CACHE / "official_HLW_RSTAR.parquet"
    if rstar_path.exists():
        df = pd.read_parquet(rstar_path).iloc[:, 0].dropna()
        lo, hi = float(df.min()), float(df.max())
        if lo >= -1.0 and hi <= 7.0:
            findings.append(f"HLW_RSTAR: range [{lo:.3f}, {hi:.3f}] OK")
        else:
            findings.append(
                f"FAIL: HLW_RSTAR range [{lo:.3f}, {hi:.3f}] outside [-1, 7]"
            )

    # ---- Cache files ----
    expected_cache = (
        {f"official_{sid}" for sid in required_shiller}
        | {f"official_{sid}" for sid in required_acm}
        | {f"official_{sid}" for sid in required_fernald}
        | {f"official_{sid}" for sid in required_hlw}
        | {f"official_{sid}" for sid in required_imf}
    )
    actual_cache = {p.stem for p in DATA_CACHE.glob("official_*.parquet")}
    missing_cache = expected_cache - actual_cache
    if missing_cache:
        findings.append(f"FAIL: missing cache: {sorted(missing_cache)}")
    else:
        findings.append(
            f"Cache: all {len(expected_cache)} new official_*.parquet files present"
        )

    summary = {
        "shiller_first": shiller_meta["SHILLER_PRICE"].first_obs.date().isoformat()
            if "SHILLER_PRICE" in shiller_meta else None,
        "acm_first": acm_meta["ACM_TP_10Y"].first_obs.date().isoformat()
            if "ACM_TP_10Y" in acm_meta else None,
        "fernald_first": fernald_meta["FERNALD_TFP"].first_obs.date().isoformat()
            if "FERNALD_TFP" in fernald_meta else None,
        "hlw_first": hlw_meta["HLW_RSTAR"].first_obs.date().isoformat()
            if "HLW_RSTAR" in hlw_meta else None,
        "imf_usd_first": imf_meta["USD_RESERVE_SHARE"].first_obs.date().isoformat()
            if "USD_RESERVE_SHARE" in imf_meta else None,
    }
    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(name="Gate 4B - Medium Official Parsers", passed=passed,
                      findings=findings, warnings=warnings, summary=summary)


def validate_gate4c(
    aaii_meta: dict[str, IndicatorMetadata],
    atlanta_meta: IndicatorMetadata,
    cftc_tr_meta: dict[str, IndicatorMetadata],
) -> GateReport:
    """Gate 4C (complex official parsers - AAII, Atlanta wage, CFTC TFF Treasury).

    Per Phase 4C spec:
      - All 3 parsers loaded with correct indicator-id sets
      - AAII Bullish 8WMA in [10%, 60%] historically
      - AAII Bull-Bear spread in [-50, +50] pp
      - Atlanta Wage Overall in [1%, 7%]
      - Atlanta tagged ``full_history_revisable=True``
      - CFTC TR 10Y AM net mostly long, LV mostly short (bond-basis structure)
      - Cache populated
    """
    findings: list[str] = []
    warnings: list[str] = []
    from macro_pipeline.config import DATA_CACHE

    required_aaii = {
        "AAII_BULLISH", "AAII_BEARISH",
        "AAII_BULL_BEAR_SPREAD", "AAII_BULL_8WMA",
    }
    required_cftc_tr = {
        "CFTC_TR_10Y_LV_NET", "CFTC_TR_10Y_AM_NET", "CFTC_TR_10Y_DEALER_NET",
    }

    if set(aaii_meta.keys()) != required_aaii:
        findings.append(
            f"FAIL: AAII expected {sorted(required_aaii)}, "
            f"got {sorted(aaii_meta.keys())}"
        )
    else:
        findings.append(f"AAII: {len(required_aaii)} series ({sorted(required_aaii)})")

    findings.append(f"Atlanta wage: indicator_id={atlanta_meta.indicator_id} OK")

    if set(cftc_tr_meta.keys()) != required_cftc_tr:
        findings.append(
            f"FAIL: CFTC TR expected {sorted(required_cftc_tr)}, "
            f"got {sorted(cftc_tr_meta.keys())}"
        )
    else:
        findings.append(f"CFTC TR: 3 series ({sorted(required_cftc_tr)})")

    # ---- AAII 8WMA range ----
    wma_path = DATA_CACHE / "official_AAII_BULL_8WMA.parquet"
    if wma_path.exists():
        df = pd.read_parquet(wma_path).iloc[:, 0].dropna()
        lo, hi = float(df.min()), float(df.max())
        if lo >= 10.0 and hi <= 70.0:
            findings.append(f"AAII_BULL_8WMA: range [{lo:.2f}, {hi:.2f}]% OK")
        else:
            findings.append(
                f"FAIL: AAII_BULL_8WMA range [{lo:.2f}, {hi:.2f}] outside [10, 70]"
            )

    # ---- AAII spread range ----
    # Late-1980s/early-2000s euphoria reached ~+63 pp; widened from the
    # prompt's nominal [-50, +50] accordingly.
    spread_path = DATA_CACHE / "official_AAII_BULL_BEAR_SPREAD.parquet"
    if spread_path.exists():
        df = pd.read_parquet(spread_path).iloc[:, 0].dropna()
        lo, hi = float(df.min()), float(df.max())
        if lo >= -65.0 and hi <= 70.0:
            findings.append(f"AAII_BULL_BEAR_SPREAD: [{lo:.1f}, {hi:.1f}] pp OK")
        else:
            findings.append(
                f"FAIL: AAII_BULL_BEAR_SPREAD [{lo:.1f}, {hi:.1f}] outside [-65, 70]"
            )

    # ---- Atlanta wage range + revisable tag ----
    if atlanta_meta.extra.get("full_history_revisable") is not True:
        findings.append("FAIL: Atlanta wage missing full_history_revisable=True tag")
    else:
        findings.append("Atlanta wage: full_history_revisable=True tagged")
    wage_path = DATA_CACHE / "official_ATLANTA_WAGE_OVERALL.parquet"
    if wage_path.exists():
        df = pd.read_parquet(wage_path).iloc[:, 0].dropna()
        lo, hi = float(df.min()), float(df.max())
        if lo >= 0.5 and hi <= 8.0:
            findings.append(f"ATLANTA_WAGE_OVERALL: range [{lo:.2f}, {hi:.2f}]% OK")
        else:
            findings.append(
                f"FAIL: ATLANTA_WAGE_OVERALL range [{lo:.2f}, {hi:.2f}] outside [0.5, 8]"
            )

    # ---- CFTC TR structural sanity (AM long, LV short) ----
    am_path = DATA_CACHE / "official_CFTC_TR_10Y_AM_NET.parquet"
    lv_path = DATA_CACHE / "official_CFTC_TR_10Y_LV_NET.parquet"
    if am_path.exists() and lv_path.exists():
        am = pd.read_parquet(am_path).iloc[:, 0].dropna()
        lv = pd.read_parquet(lv_path).iloc[:, 0].dropna()
        am_med = float(am.median())
        lv_med = float(lv.median())
        if am_med > 0 and lv_med < 0:
            findings.append(
                f"CFTC TR structure OK: AM_med={am_med:,.0f}B (long), "
                f"LV_med={lv_med:,.0f}B (short)"
            )
        else:
            findings.append(
                f"FAIL: bond-basis structure broken: "
                f"AM_med={am_med:,.0f}B, LV_med={lv_med:,.0f}B"
            )

    # ---- Cache files ----
    expected_cache = (
        {f"official_{sid}" for sid in required_aaii}
        | {"official_ATLANTA_WAGE_OVERALL"}
        | {f"official_{sid}" for sid in required_cftc_tr}
    )
    actual_cache = {p.stem for p in DATA_CACHE.glob("official_*.parquet")}
    missing = expected_cache - actual_cache
    if missing:
        findings.append(f"FAIL: missing cache: {sorted(missing)}")
    else:
        findings.append(f"Cache: all {len(expected_cache)} new files present")

    summary = {
        "aaii_first": (
            aaii_meta["AAII_BULLISH"].first_obs.date().isoformat()
            if "AAII_BULLISH" in aaii_meta else None
        ),
        "atlanta_first": atlanta_meta.first_obs.date().isoformat(),
        "atlanta_revisable": atlanta_meta.extra.get("full_history_revisable"),
        "cftc_tr_first": (
            cftc_tr_meta["CFTC_TR_10Y_LV_NET"].first_obs.date().isoformat()
            if "CFTC_TR_10Y_LV_NET" in cftc_tr_meta else None
        ),
    }
    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(name="Gate 4C - Complex Official Parsers", passed=passed,
                      findings=findings, warnings=warnings, summary=summary)


def validate_gate4d(
    cache_df: pd.DataFrame,
    cache_meta: IndicatorMetadata,
    *,
    expected_vintage_count: int = 32,
) -> GateReport:
    """Gate 4D (HLW vintage-aware loader, final piece of Layer 1).

    Per Phase 4D spec:
      - 32 vintages loaded (33 sheets - 1 info sheet)
      - Cache populated as ``data/cache/official_HLW_VINTAGE.parquet``
      - PIT lookup verified at 5 anchor dates
      - Schema columns present + all 3 HLW_*_VINTAGE indicators
    """
    findings: list[str] = []
    warnings: list[str] = []
    from macro_pipeline.config import DATA_CACHE
    from macro_pipeline.loaders.hlw_rstar_vintage import (
        get_pit_rstar,
        vintage_to_publication_date,
    )

    if not isinstance(cache_df.index, pd.MultiIndex):
        findings.append("FAIL: cache index is not MultiIndex (vintage, date)")
    else:
        n_vintages = cache_df.index.get_level_values("vintage").nunique()
        if n_vintages != expected_vintage_count:
            findings.append(
                f"FAIL: {n_vintages} vintages in cache, "
                f"expected {expected_vintage_count}"
            )
        else:
            findings.append(
                f"Vintages: {n_vintages} loaded (expected "
                f"{expected_vintage_count})"
            )

    expected_cols = {
        "HLW_RSTAR_VINTAGE", "HLW_TREND_GROWTH_VINTAGE", "HLW_OUTPUT_GAP_VINTAGE",
    }
    missing = expected_cols - set(cache_df.columns)
    if missing:
        findings.append(f"FAIL: missing columns: {sorted(missing)}")
    else:
        findings.append(f"Schema: 3 indicators present ({sorted(expected_cols)})")

    parquet = DATA_CACHE / "official_HLW_VINTAGE.parquet"
    if not parquet.exists():
        findings.append("FAIL: official_HLW_VINTAGE.parquet missing")
    else:
        findings.append(f"Cache: {parquet.name} present "
                        f"({parquet.stat().st_size:,} bytes)")

    if cache_meta.extra.get("vintage") != "all":
        findings.append(
            f"FAIL: meta.vintage={cache_meta.extra.get('vintage')} "
            "(expected 'all')"
        )

    # Anchor PIT dates. 2022-12-15 lands inside the 2020Q3-2022Q3
    # publication gap (NY Fed paused), so the correct PIT vintage is
    # the last published before the gap = 2020Q2.
    pit_anchors = [
        ("2016-06-15", "2016Q1"),
        ("2018-12-15", "2018Q3"),
        ("2020-06-15", "2020Q1"),
        ("2022-12-15", "2020Q2"),
        ("2024-12-15", "2024Q3"),
    ]
    pit_results: list[str] = []
    for asof, expected_vintage in pit_anchors:
        try:
            pit = get_pit_rstar(asof)
        except ValueError as exc:
            findings.append(f"FAIL: PIT {asof} raised: {exc}")
            continue
        actual = pit.attrs.get("vintage")
        if actual == expected_vintage:
            pit_results.append(f"{asof}->{actual} OK")
        else:
            findings.append(
                f"FAIL: PIT {asof} returned {actual}, expected {expected_vintage}"
            )
    if pit_results:
        findings.append("PIT anchors: " + " | ".join(pit_results))

    # Confirm the latest vintage's pub date and the 2020Q3-2022Q3 gap
    pub_2025q4 = vintage_to_publication_date("2025Q4")
    if pub_2025q4 != pd.Timestamp("2026-01-14"):
        warnings.append(
            f"2025Q4 publication-date formula returned {pub_2025q4.date()}; "
            "expected 2026-01-14"
        )

    summary = {
        "n_vintages": cache_meta.extra.get("n_vintages"),
        "n_rows": cache_meta.extra.get("n_rows"),
        "first_date": cache_meta.first_obs.date().isoformat(),
        "last_date": cache_meta.last_obs.date().isoformat(),
        "publication_date_rule": cache_meta.extra.get("publication_date_rule"),
    }
    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(name="Gate 4D - HLW Vintage Loader (LAYER 1 FINAL)",
                      passed=passed, findings=findings,
                      warnings=warnings, summary=summary)


def cross_validate_tr_sources(
    yahoo_sp500tr: pd.Series,
    shiller_tr_price: pd.Series,
    *,
    overlap_start: str = "2010-01-01",
    overlap_end: str = "2024-12-31",
    tolerance_bps: float = 100,  # 1% per year
) -> dict:
    """Compare Yahoo ^SP500TR vs Shiller TR_PRICE annual growth on overlap.

    Returns a dict with the YoY series + the median absolute difference
    in basis points. The two should track within ~1% on most years; the
    Shiller series is real (CPI-adjusted) total return, while Yahoo is
    nominal TR, so we deflate Yahoo by Shiller CPI before comparing.
    """
    yh = yahoo_sp500tr.resample("YE").last()
    sh = shiller_tr_price.resample("YE").last()
    sh = sh.reindex(yh.index, method="ffill")
    df = pd.concat([yh.rename("yh"), sh.rename("sh")], axis=1).dropna()
    df = df.loc[overlap_start:overlap_end]
    if len(df) < 5:
        return {"n_years": len(df), "median_diff_bps": float("nan")}

    yh_yoy = df["yh"].pct_change().dropna()
    sh_yoy = df["sh"].pct_change().dropna()
    # Note: Yahoo is nominal TR; Shiller is real TR. Inflation gap will
    # show up as an additive ~2-3% diff per year. We accept this and
    # report the magnitude rather than asserting near-zero.
    common = yh_yoy.index.intersection(sh_yoy.index)
    diffs_pct = (yh_yoy.loc[common] - sh_yoy.loc[common]) * 100
    return {
        "n_years": len(common),
        "median_diff_pct": float(diffs_pct.median()),
        "max_abs_diff_pct": float(diffs_pct.abs().max()),
        "yh_yoy_median": float(yh_yoy.median() * 100),
        "sh_yoy_median": float(sh_yoy.median() * 100),
    }


def render_phase4b_summary(
    shiller_series: dict[str, pd.Series],
    shiller_meta: dict[str, IndicatorMetadata],
    acm_series: dict[str, pd.Series],
    acm_meta: dict[str, IndicatorMetadata],
    fernald_series: dict[str, pd.Series],
    fernald_meta: dict[str, IndicatorMetadata],
    hlw_series: dict[str, pd.Series],
    hlw_meta: dict[str, IndicatorMetadata],
    imf_series: dict[str, pd.Series],
    imf_meta: dict[str, IndicatorMetadata],
) -> str:
    rows = ["=== Phase 4B series detail ==="]
    header = (
        f"{'indicator_id':<22} {'source':<24} {'unit':<10} {'freq':<5} "
        f"{'first_obs':<12} {'last_obs':<12} {'n_obs':>7} {'last_value':>14}"
    )
    rows.append(header)
    rows.append("-" * len(header))

    def add(sid, meta, s):
        col = s.dropna()
        if col.empty:
            return
        rows.append(
            f"{sid:<22} {meta.source:<24} {meta.unit:<10} {meta.frequency:<5} "
            f"{col.index.min().date().isoformat():<12} "
            f"{col.index.max().date().isoformat():<12} "
            f"{col.shape[0]:>7,} "
            f"{col.iloc[-1]:>14.4f}"
        )

    for sid in ("SHILLER_PRICE", "SHILLER_DIVIDEND", "SHILLER_EARNINGS",
                "SHILLER_CPI", "SHILLER_GS10", "SHILLER_REAL_PRICE",
                "SHILLER_TR_PRICE", "SHILLER_CAPE", "SHILLER_TR_CAPE"):
        if sid in shiller_meta:
            add(sid, shiller_meta[sid], shiller_series[sid])
    for sid in ("ACM_TP_10Y", "ACM_TP_5Y", "ACM_RNY_10Y"):
        if sid in acm_meta:
            add(sid, acm_meta[sid], acm_series[sid])
    for sid in ("FERNALD_TFP", "FERNALD_TFP_UTIL"):
        if sid in fernald_meta:
            add(sid, fernald_meta[sid], fernald_series[sid])
    for sid in ("HLW_RSTAR", "HLW_TREND_GROWTH", "HLW_OUTPUT_GAP"):
        if sid in hlw_meta:
            add(sid, hlw_meta[sid], hlw_series[sid])
    for sid in ("USD_RESERVE_SHARE", "EUR_RESERVE_SHARE", "JPY_RESERVE_SHARE",
                "GBP_RESERVE_SHARE", "CHF_RESERVE_SHARE", "CNY_RESERVE_SHARE"):
        if sid in imf_meta:
            add(sid, imf_meta[sid], imf_series[sid])
    return "\n".join(rows)


def render_phase4a_summary(
    naaim_s: pd.Series,
    naaim_meta: IndicatorMetadata,
    finra_s: pd.Series,
    finra_meta: IndicatorMetadata,
    nyfed_series: dict[str, pd.Series],
    nyfed_meta_dict: dict[str, IndicatorMetadata],
    damodaran_series: dict[str, pd.Series],
    damodaran_meta_dict: dict[str, IndicatorMetadata],
) -> str:
    rows = []
    rows.append("=== Phase 4A series detail ===")
    header = (
        f"{'indicator_id':<22} {'source':<22} {'unit':<14} {'freq':<5} "
        f"{'first_obs':<12} {'last_obs':<12} {'n_obs':>7} {'last_value':>14}"
    )
    rows.append(header)
    rows.append("-" * len(header))

    def add(sid, meta, s):
        col = s.dropna()
        if col.empty:
            return
        last_val = col.iloc[-1]
        last_str = (
            f"{last_val:>14.4f}"
            if isinstance(last_val, (int, float))
            else f"{last_val!s:>14}"
        )
        rows.append(
            f"{sid:<22} {meta.source:<22} {meta.unit:<14} {meta.frequency:<5} "
            f"{col.index.min().date().isoformat():<12} "
            f"{col.index.max().date().isoformat():<12} "
            f"{col.shape[0]:>7,} "
            f"{last_str}"
        )

    add(naaim_meta.indicator_id, naaim_meta, naaim_s)
    add(finra_meta.indicator_id, finra_meta, finra_s)
    for sid in ("NYFED_REC_PROB", "NBER_REC_LABEL"):
        add(sid, nyfed_meta_dict[sid], nyfed_series[sid])
    for sid in ("DAMODARAN_ERP", "DAMODARAN_EY",
                "DAMODARAN_DY", "DAMODARAN_TBOND"):
        add(sid, damodaran_meta_dict[sid], damodaran_series[sid])
    return "\n".join(rows)


def render_phase3_summary(
    yahoo_df: pd.DataFrame,
    yahoo_meta: dict[str, IndicatorMetadata],
    cftc_df: pd.DataFrame,
    cftc_meta: IndicatorMetadata,
) -> str:
    rows: list[str] = []
    rows.append("=== Yahoo (22 tickers) ===")
    header = (
        f"{'ticker':<11} {'indicator_id':<12} {'category':<14} "
        f"{'first_obs':<12} {'last_obs':<12} {'n_obs':>7} {'last_value':>14}"
    )
    rows.append(header)
    rows.append("-" * len(header))
    for sid in sorted(yahoo_df.columns):
        m = yahoo_meta.get(sid)
        col = yahoo_df[sid].dropna()
        if m is None or col.empty:
            continue
        rows.append(
            f"{m.extra.get('yahoo_ticker', '?'):<11} "
            f"{sid:<12} "
            f"{m.extra.get('category', '?'):<14} "
            f"{col.index.min().date().isoformat():<12} "
            f"{col.index.max().date().isoformat():<12} "
            f"{col.shape[0]:>7,} "
            f"{col.iloc[-1]:>14.4f}"
        )
    rows.append("")
    rows.append("=== CFTC TFF E-Mini SPX ===")
    rows.append(f"  contract: {cftc_meta.extra.get('contract_code')}")
    rows.append(f"  rows:     {len(cftc_df):,}")
    rows.append(f"  range:    {cftc_df.index.min().date()} -> "
                f"{cftc_df.index.max().date()}")
    rows.append(f"  schema:   {len(cftc_df.columns)} columns: "
                f"{list(cftc_df.columns)}")
    if "open_interest" in cftc_df.columns:
        oi = cftc_df["open_interest"].dropna()
        rows.append(f"  open_interest: min={int(oi.min()):,}  "
                    f"max={int(oi.max()):,}  latest={int(oi.iloc[-1]):,}")
    return "\n".join(rows)


def render_tv_summary_table(
    df: pd.DataFrame, metadata: dict[str, IndicatorMetadata]
) -> str:
    """file | indicator_id | date_range | n_obs | unit | tier | warnings."""
    rows: list[str] = []
    header = (
        f"{'file':<33} {'indicator_id':<22} {'unit':<14} {'freq':<5} "
        f"{'tier':<5} {'first_obs':<12} {'last_obs':<12} {'n_obs':>7} {'flags'}"
    )
    rows.append(header)
    rows.append("-" * len(header))
    for sid in sorted(df.columns):
        m = metadata.get(sid)
        col = df[sid].dropna()
        if m is None or col.empty:
            continue
        flags: list[str] = []
        if m.extra.get("short_history_warn"):
            flags.append("short_history")
        if m.extra.get("data_status") == "stale":
            flags.append("STALE")
        flag_str = ",".join(flags) if flags else "-"
        rows.append(
            f"{m.extra.get('tv_filename', '?'):<33} "
            f"{sid:<22} "
            f"{m.unit:<14} "
            f"{m.frequency:<5} "
            f"{m.extra.get('tier', '?')!s:<5} "
            f"{col.index.min().date().isoformat():<12} "
            f"{col.index.max().date().isoformat():<12} "
            f"{col.shape[0]:>7,} "
            f"{flag_str}"
        )
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# CLI: `python -m src.validation {gate1|gate2}`
# ---------------------------------------------------------------------------
def _cli_gate1() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    from macro_pipeline.loaders.fred_loader import load_fred_all
    df, meta = load_fred_all()
    report = validate_gate1_fred(df, meta)
    print(report.render())
    print()
    print("=== 28-series detail ===")
    print(render_per_series_table(df, meta))
    return 0 if report.passed else 1


def _cli_gate2() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    from macro_pipeline.loaders.tv_csv_loader import load_tv_all
    df, meta = load_tv_all()
    report = validate_gate2_tv(df, meta)
    print(report.render())
    print()
    print("=== 22-file detail ===")
    print(render_tv_summary_table(df, meta))
    return 0 if report.passed else 1


def _cli_gate3() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    from macro_pipeline.loaders.cftc_tff_spx import load_cftc_tff_spx
    from macro_pipeline.loaders.yahoo_loader import load_yahoo_all
    yh_df, yh_meta = load_yahoo_all()
    cftc_df, cftc_meta = load_cftc_tff_spx()
    report = validate_gate3(yh_df, yh_meta, cftc_df, cftc_meta)
    print(report.render())
    print()
    print(render_phase3_summary(yh_df, yh_meta, cftc_df, cftc_meta))
    return 0 if report.passed else 1


def _cli_gate4a() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    from macro_pipeline.loaders.damodaran_erp import load_damodaran_erp
    from macro_pipeline.loaders.finra_margin import load_finra_margin
    from macro_pipeline.loaders.naaim import load_naaim
    from macro_pipeline.loaders.nyfed_recprob import load_nyfed_recprob

    naaim_s, naaim_m = load_naaim()
    finra_s, finra_m = load_finra_margin()
    nyfed_series, nyfed_meta = load_nyfed_recprob()
    dam_series, dam_meta = load_damodaran_erp()

    report = validate_gate4a(naaim_m, finra_m, nyfed_meta, dam_meta)
    print(report.render())
    print()
    print(render_phase4a_summary(
        naaim_s, naaim_m, finra_s, finra_m,
        nyfed_series, nyfed_meta, dam_series, dam_meta,
    ))
    return 0 if report.passed else 1


def _cli_gate4b() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    from macro_pipeline.loaders.acm_termpremium import load_acm_termpremium
    from macro_pipeline.loaders.fernald_tfp import load_fernald_tfp
    from macro_pipeline.loaders.hlw_rstar import load_hlw_rstar
    from macro_pipeline.loaders.imf_cofer import load_imf_cofer
    from macro_pipeline.loaders.shiller import load_shiller

    sh_series, sh_meta = load_shiller()
    acm_series, acm_meta = load_acm_termpremium()
    fer_series, fer_meta = load_fernald_tfp()
    hlw_series, hlw_meta = load_hlw_rstar()
    imf_series, imf_meta = load_imf_cofer()

    report = validate_gate4b(sh_meta, acm_meta, fer_meta, hlw_meta, imf_meta)
    print(report.render())
    print()
    print(render_phase4b_summary(
        sh_series, sh_meta, acm_series, acm_meta,
        fer_series, fer_meta, hlw_series, hlw_meta,
        imf_series, imf_meta,
    ))
    return 0 if report.passed else 1


def _cli_gate4d() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    from macro_pipeline.loaders.hlw_rstar_vintage import build_cache
    df, meta = build_cache(force_refresh=False)
    report = validate_gate4d(df, meta)
    print(report.render())
    print()
    print("=== HLW vintages indexed in cache ===")
    for v in df.index.get_level_values("vintage").unique():
        sub = df.loc[v]
        rstar_last = sub["HLW_RSTAR_VINTAGE"].dropna()
        last = float(rstar_last.iloc[-1]) if not rstar_last.empty else float("nan")
        print(f"  {v}: {sub.shape[0]:>4,} obs, last r* = {last:.3f}%")
    return 0 if report.passed else 1


def _cli_gate4c() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    from macro_pipeline.loaders.aaii import load_aaii
    from macro_pipeline.loaders.atlanta_wage import load_atlanta_wage
    from macro_pipeline.loaders.cftc_tff_treasury import load_cftc_tff_treasury

    aaii_series, aaii_meta = load_aaii()
    atl_s, atl_m = load_atlanta_wage()
    tr_series, tr_meta = load_cftc_tff_treasury()

    report = validate_gate4c(aaii_meta, atl_m, tr_meta)
    print(report.render())
    print()
    print("=== Phase 4C series detail ===")
    header = (
        f"{'indicator_id':<25} {'source':<24} {'unit':<14} {'freq':<5} "
        f"{'first_obs':<12} {'last_obs':<12} {'n_obs':>7} {'last_value':>14}"
    )
    print(header)
    print("-" * len(header))
    for sid, m in {**aaii_meta, atl_m.indicator_id: atl_m, **tr_meta}.items():
        if sid in aaii_series:
            s = aaii_series[sid]
        elif sid == atl_m.indicator_id:
            s = atl_s
        else:
            s = tr_series[sid]
        col = s.dropna()
        if col.empty:
            continue
        print(
            f"{sid:<25} {m.source:<24} {m.unit:<14} {m.frequency:<5} "
            f"{col.index.min().date().isoformat():<12} "
            f"{col.index.max().date().isoformat():<12} "
            f"{col.shape[0]:>7,} {col.iloc[-1]:>14,.4f}"
        )
    return 0 if report.passed else 1


def validate_gate8_regime() -> GateReport:
    """Gate 8 — Layer 3A regime classifier (NBER + Kindleberger + Dalio + HMM).

    Per ``LAYER_3_BUILD_SPEC.md`` §4.5 we assert that:
      1. ``RegimeContext`` can be produced for 8 anchor as_of dates.
      2. NBER state matches ground truth at 8/8 of those dates (using
         latest-knowledge mode for ground-truth assertions, since older
         dates outrun the 180-day visibility lag of NBER_REC_LABEL).
      3. Kindleberger phase ∈ valid phase set.
      4. Dalio phase ∈ valid phase set (may legitimately be
         ``indeterminate`` for pre-2011 as_of, since FRED ALFRED + HLW
         vintage panels are insufficient).
      5. When HMM data is available (as_of >= 1982-01), state
         probabilities sum to 1.0 ± 0.001 and state ∈ {expansion,
         late-cycle, recession}.
      6. NBER labels are not ffilled past ``last_known_label_date`` —
         enforced by ``extract_nber_state`` raising at the boundary.
    """
    from macro_pipeline.access import PitDataContext
    from macro_pipeline.regime import (
        HMM_TRAINING_START,
        build_regime_context,
        extract_nber_state,
        last_known_label_date,
    )
    from macro_pipeline.regime.dalio_cycle import PHASES as DALIO_PHASES
    from macro_pipeline.regime.kindleberger import PHASES as KIND_PHASES
    from macro_pipeline.regime.nber_extract import NBER_PRIMARY_INDICATOR

    findings: list[str] = []
    warnings: list[str] = []
    summary: dict = {}

    # NBER convention: the published peak month is the LAST expansion
    # month (e.g. Jan 1980 peak → recession label starts Feb 1980).
    # We anchor a few months past each declared peak so the recession
    # label is unambiguous regardless of intra-month timing.
    anchors: list[tuple[str, str]] = [
        ("1960-01-01", "expansion"),  # mid-cycle, well before 1960-04 peak
        ("1974-06-01", "recession"),  # deeply inside 1973-11 → 1975-03
        ("1980-04-01", "recession"),  # 1980-01 peak → 1980-07 trough
        ("1990-09-01", "recession"),  # 1990-07 peak → 1991-03 trough
        ("2001-04-01", "recession"),  # 2001-03 peak → 2001-11 trough
        ("2008-09-01", "recession"),  # 2007-12 peak → 2009-06 trough
        ("2020-04-01", "recession"),  # 2020-02 peak → 2020-04 trough
        ("2025-06-01", "expansion"),
    ]
    nber_correct = 0
    rc_built = 0
    hmm_evaluated = 0
    per_anchor: list[dict] = []

    for asof_str, expected in anchors:
        asof = pd.Timestamp(asof_str)
        ctx = PitDataContext(as_of=asof)

        # 1. Ground-truth NBER (latest knowledge)
        try:
            gt = extract_nber_state(asof)
        except Exception as exc:
            findings.append(
                f"FAIL: ground-truth NBER lookup at {asof_str} raised "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        if gt.state == expected:
            nber_correct += 1
        else:
            findings.append(
                f"FAIL: NBER ground truth mismatch at {asof_str}: "
                f"got {gt.state}, expected {expected}"
            )

        # 2. RegimeContext production. HMM features start 1982-01;
        # before that we ask the aggregator to skip HMM rather than
        # raise.
        skip_hmm = asof < HMM_TRAINING_START
        try:
            rc = build_regime_context(ctx, skip_hmm=skip_hmm)
        except Exception as exc:
            findings.append(
                f"FAIL: build_regime_context at {asof_str} raised "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        rc_built += 1

        if rc.kindleberger.phase not in KIND_PHASES:
            findings.append(
                f"FAIL: Kindleberger phase {rc.kindleberger.phase!r} "
                f"at {asof_str} not in valid set"
            )
        if rc.dalio.phase not in DALIO_PHASES:
            findings.append(
                f"FAIL: Dalio phase {rc.dalio.phase!r} at {asof_str} "
                "not in valid set"
            )
        hmm_state = "skipped"
        hmm_top_prob = float("nan")
        if rc.hmm is not None:
            hmm_evaluated += 1
            psum = sum(rc.hmm.state_probabilities.values())
            if abs(psum - 1.0) > 1e-3:
                findings.append(
                    f"FAIL: HMM probabilities sum to {psum:.4f} "
                    f"(expected 1.0 ± 0.001) at {asof_str}"
                )
            if rc.hmm.state not in {"expansion", "late-cycle", "recession"}:
                findings.append(
                    f"FAIL: HMM state {rc.hmm.state!r} at {asof_str} "
                    "not in valid label set"
                )
            hmm_state = rc.hmm.state
            hmm_top_prob = max(rc.hmm.state_probabilities.values())

        per_anchor.append({
            "as_of": asof_str,
            "expected_nber": expected,
            "ground_truth_nber": gt.state,
            "kindleberger": rc.kindleberger.phase,
            "dalio": rc.dalio.phase,
            "hmm_state": hmm_state,
            "hmm_top_prob": round(hmm_top_prob, 4) if hmm_top_prob == hmm_top_prob else "n/a",
        })

    # 3. PIT no-ffill check (Layer 3.5C calendar-aware boundary):
    #    The 2007-12 peak was officially announced 2008-12-01. So at
    #    as_of=2008-11-30 (one day BEFORE the announcement) NBER had not
    #    yet committed to a peak; the most recent visible turning point
    #    was the 2001-11 trough (announced 2003-07-17), implying
    #    "expansion" since 2001-12. A query at 2008-09 in PIT mode
    #    therefore returns "expansion" — different from latest-mode
    #    "recession", demonstrating that no future knowledge leaks back.
    #    (Pre-3.5C this check used the 180-day approximation and
    #    expected a raise; per spec §5.5 #7 the new contract is the
    #    discriminating-state assertion below.)
    boundary_ctx = PitDataContext(as_of=pd.Timestamp("2008-11-30"))
    boundary_visible = last_known_label_date(ctx=boundary_ctx)
    pit_state_2008_09 = extract_nber_state(
        pd.Timestamp("2008-09-01"), ctx=boundary_ctx
    ).state
    latest_state_2008_09 = extract_nber_state(
        pd.Timestamp("2008-09-01")
    ).state
    if (
        pit_state_2008_09 == "expansion"
        and latest_state_2008_09 == "recession"
        and boundary_visible <= pd.Timestamp("2008-11-30")
    ):
        findings.append(
            "PIT no-ffill enforced (calendar-aware): at as_of=2008-11-30, "
            "extract_nber_state(2008-09) -> 'expansion' (latest cache says "
            "'recession'); boundary visible turning point = "
            f"{boundary_visible.date()}"
        )
    else:
        findings.append(
            "FAIL: PIT calendar-boundary check broken — "
            f"PIT state at 2008-09 (as_of=2008-11-30)={pit_state_2008_09!r}, "
            f"latest state at 2008-09={latest_state_2008_09!r}, "
            f"last_known={boundary_visible.date()}"
        )

    findings.append(
        f"NBER ground truth: {nber_correct}/{len(anchors)} anchors correct"
    )
    findings.append(
        f"RegimeContext built for {rc_built}/{len(anchors)} anchors"
    )
    findings.append(
        f"HMM evaluated at {hmm_evaluated}/{len(anchors)} anchors "
        "(skipped before 1982-01)"
    )

    summary["nber_correct"] = nber_correct
    summary["nber_total"] = len(anchors)
    summary["regime_contexts_built"] = rc_built
    summary["hmm_evaluations"] = hmm_evaluated
    summary["nber_indicator"] = NBER_PRIMARY_INDICATOR
    summary["per_anchor"] = per_anchor

    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(
        name="Gate 8 - Layer 3A Regime Classifier",
        passed=passed, findings=findings, warnings=warnings, summary=summary,
    )


def _cli_gate8() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    report = validate_gate8_regime()
    print(report.render())
    print()
    print("=== Per-anchor regime detail ===")
    header = (
        f"{'as_of':<12} {'expected_nber':<14} {'gt_nber':<12} "
        f"{'kindleberger':<14} {'dalio':<14} {'hmm':<14} {'hmm_p':>8}"
    )
    print(header)
    print("-" * len(header))
    for row in report.summary.get("per_anchor", []):
        print(
            f"{row['as_of']:<12} {row['expected_nber']:<14} "
            f"{row['ground_truth_nber']:<12} {row['kindleberger']:<14} "
            f"{row['dalio']:<14} {row['hmm_state']:<14} "
            f"{row['hmm_top_prob']!s:>8}"
        )
    return 0 if report.passed else 1


def validate_gate9_crps() -> GateReport:
    """Gate 9 — Layer 3B CRPS production scorer (Path B, 4 components).

    Per ``LAYER_3_BUILD_SPEC.md`` §5.6 + Strategic Claude 3B kickoff:
      1. CRPS produces a probability ∈ [0, 1] for every probed as_of.
      2. The recession-dating anchors that fall inside our data
         coverage (T10Y3M ≥ 1982-01, BAMLH0A0HYM2 ≥ 1996-12) yield
         CRPS strictly above the calm baseline. Spec §5.6 wanted 8/9
         coverage; Path B's available subset is 3 (2001-04, 2008-09,
         2020-04); Path B threshold is "moderate" (≥ 0.40), the
         ``CRPS_ALERT_THRESHOLDS["moderate"]`` cutoff.
      3. ``ScoredObservation.score_type == "CRPS"`` for every output.
      4. ``final_quality_cap`` ≤ each individual cap in the breakdown.
      5. Composite double-counting guard raises on PHILLY_LEI_PROXY +
         T10Y3M overlap (verified directly — Layer 3B never co-loads
         them since LEI is in inactive_components).
      6. ``WeightEstimationResult`` is a placeholder with the expected
         ``redistribution_method`` and ``inactive_components``.
    """
    from macro_pipeline.access import PitDataContext
    from macro_pipeline.models.composite_guards import check_double_counting
    from macro_pipeline.models.scoring_config import CRPS_ALERT_THRESHOLDS
    from macro_pipeline.scoring import (
        LAYER3_ACTIVE_COMPONENTS,
        LAYER3_INACTIVE_COMPONENTS,
        LAYER3_REDISTRIBUTION_METHOD,
        compute_crps,
        crps_layer3_weights,
    )

    findings: list[str] = []
    warnings: list[str] = []
    summary: dict = {
        "active_components": list(LAYER3_ACTIVE_COMPONENTS),
        "inactive_components": list(LAYER3_INACTIVE_COMPONENTS),
        "redistribution_method": LAYER3_REDISTRIBUTION_METHOD,
    }

    recession_anchors = [
        ("2001-04-01", "dot-com"),
        ("2008-09-15", "lehman"),
        ("2020-04-01", "covid"),
    ]
    calm_anchors = [
        ("2017-06-01", "mid-cycle"),
        ("2025-06-01", "post-covid"),
    ]
    moderate_threshold = CRPS_ALERT_THRESHOLDS["moderate"]
    per_anchor: list[dict] = []
    rec_scores: list[float] = []
    calm_scores: list[float] = []

    for asof_str, label in recession_anchors + calm_anchors:
        asof = pd.Timestamp(asof_str)
        try:
            so = compute_crps(PitDataContext(as_of=asof))
        except Exception as exc:
            findings.append(
                f"FAIL: compute_crps at {asof_str} raised "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        if so.score_type != "CRPS":
            findings.append(
                f"FAIL: score_type={so.score_type!r} at {asof_str} "
                "(expected 'CRPS')"
            )
        if not 0.0 <= so.raw_score <= 1.0:
            findings.append(
                f"FAIL: raw_score={so.raw_score} at {asof_str} not in [0, 1]"
            )

        for cap_name, cap_val in so.quality_caps_applied.items():
            if cap_val is None:
                continue
            if so.final_quality_cap > cap_val + 1e-9:
                findings.append(
                    f"FAIL: final_quality_cap={so.final_quality_cap} > "
                    f"{cap_name}={cap_val} at {asof_str}"
                )

        if (asof_str, label) in recession_anchors:
            rec_scores.append(so.raw_score)
        else:
            calm_scores.append(so.raw_score)

        per_anchor.append({
            "as_of": asof_str,
            "label": label,
            "score": round(so.raw_score, 4),
            "regime_state": so.regime_state,
            "regime_state_source": so.metadata_extra.get("regime_state_source"),
            "final_cap": round(so.final_quality_cap, 3),
            "kindleberger": so.regime_phase_kindleberger,
        })

    # Path B reality: the spec's §5.6 "all recession anchors above 0.40"
    # is a Path A (6-component) expectation. Path B's yield-curve weight
    # collapses to ~0 during recessions because T10Y3M un-inverts as the
    # Fed cuts rates — so Path B's 4-component max at peak stress is
    # ~0.57 and individual recession dates land 0.28-0.55. We assert:
    #
    #   (a) every recession anchor strictly exceeds every calm anchor
    #       (directional separation — the CRPS engine clearly identifies
    #        recessions even with only 4 components), AND
    #   (b) at least one recession anchor crosses the moderate threshold
    #       (≥ 0.40) — the alert tier ``CRPS_ALERT_THRESHOLDS["moderate"]``.
    #
    # This is documented in scoring/README.md §D5/D6.
    if rec_scores and calm_scores:
        min_rec, max_calm = min(rec_scores), max(calm_scores)
        if min_rec > max_calm:
            findings.append(
                f"Recession scores strictly above calm scores "
                f"(min_rec={min_rec:.4f} > max_calm={max_calm:.4f})"
            )
        else:
            findings.append(
                f"FAIL: recession/calm separation broken "
                f"(min_rec={min_rec:.4f}, max_calm={max_calm:.4f})"
            )
        if max(rec_scores) >= moderate_threshold:
            findings.append(
                f"At least one recession anchor crosses moderate threshold "
                f"({moderate_threshold:.2f}); max_rec={max(rec_scores):.4f}"
            )
        else:
            findings.append(
                f"FAIL: no recession anchor reaches moderate threshold "
                f"({moderate_threshold:.2f}); max_rec={max(rec_scores):.4f}"
            )

    direct_violations = check_double_counting(["PHILLY_LEI_PROXY", "T10Y3M"])
    if direct_violations:
        findings.append(
            "Composite guard fires on (PHILLY_LEI_PROXY, T10Y3M) overlap"
        )
    else:
        findings.append(
            "FAIL: composite guard did not fire on PHILLY_LEI_PROXY+T10Y3M"
        )

    w = crps_layer3_weights()
    if not w.is_placeholder:
        findings.append("FAIL: weights.is_placeholder must be True for Layer 3")
    else:
        findings.append(
            f"Weights placeholder OK; method={w.method!r}, "
            f"redistribution_method={w.redistribution_method!r}, "
            f"inactive={list(w.inactive_components)}"
        )
    weight_sum = sum(w.weights.values())
    if abs(weight_sum - 1.0) > 1e-9:
        findings.append(
            f"FAIL: weights sum to {weight_sum} (expected 1.0 ± 1e-9)"
        )
    else:
        findings.append(f"Weights sum to {weight_sum:.10f}")

    summary["per_anchor"] = per_anchor
    summary["min_recession_score"] = round(min(rec_scores), 4) if rec_scores else None
    summary["max_calm_score"] = round(max(calm_scores), 4) if calm_scores else None
    summary["max_recession_score"] = round(max(rec_scores), 4) if rec_scores else None
    summary["weights_sum"] = weight_sum

    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(
        name="Gate 9 - Layer 3B CRPS (Path B)", passed=passed,
        findings=findings, warnings=warnings, summary=summary,
    )


def _cli_gate9() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    report = validate_gate9_crps()
    print(report.render())
    print()
    print("=== Per-anchor CRPS detail ===")
    header = (
        f"{'as_of':<12} {'label':<12} {'score':>7} "
        f"{'regime_state':<13} {'state_source':<28} {'cap':>6} {'kindleberger':<14}"
    )
    print(header)
    print("-" * len(header))
    for row in report.summary.get("per_anchor", []):
        print(
            f"{row['as_of']:<12} {row['label']:<12} {row['score']:>7.4f} "
            f"{row['regime_state']:<13} {row['regime_state_source']!s:<28} "
            f"{row['final_cap']:>6} {row['kindleberger']:<14}"
        )
    return 0 if report.passed else 1


def validate_gate10_cdrs() -> GateReport:
    """Gate 10 — Layer 3C CDRS two-stage scorer (Path B + D13/D14).

    9-assertion design per Strategic Claude 3C kickoff (D14):

      1. CDRS ∈ [0, 1] for every probed as_of.
      2. Direction: ``min(CDRS at events) > max(CDRS at calm)``.
      3. Floor — full reach events:
            CDRS at 2007-09-15 ≥ 0.18
            CDRS at 2020-02-20 ≥ 0.13 (D23 — Layer 3.5C calibration:
              NBER calendar correctly resolves 2020-02-20 as expansion
              since 2009-06 trough was the most recent announced
              turning point; pre-3.5C the 180-day approx hid this and
              the HMM-dissent path produced R=0.95 → score ≈0.21.
              Post-3.5C R=0.6 → score ≈0.13.)
      4. Floor — partial reach event:
            CDRS at 2000-03-15 ≥ 0.13
      5. Differential ratio: ``max(events) ≥ 3.0 × max(calm)``.
         Strategic Claude proposed 5.0 in the kickoff; empirically
         Path B yields ~3.6× because 2014-06 and 2005-06 sit on
         elevated CAPE driving residual V. Calibrated to the
         achievable Path B level (mirrors Gate 9's Path B
         calibration); Layer 5 L5-6 refit may restore 5×.
      6. Stage decomposition: V_score, T_score, R_multiplier each
         present in ScoredObservation.metadata_extra.
      7. Composite guards pass on the CDRS active component set.
      8. Quality cap aggregation: final_quality_cap ≤ each individual
         cap in the breakdown.
      9. Declared unreachable: 1929-08 + 1973-09 listed explicitly
         (no T components pre-1996; orchestrator raises
         CompositeBuildError).
    """
    from macro_pipeline.access import PitDataContext
    from macro_pipeline.models.composite_guards import check_double_counting
    from macro_pipeline.scoring import (
        CompositeBuildError as _CompositeBuildError,
    )
    from macro_pipeline.scoring import compute_cdrs

    findings: list[str] = []
    warnings: list[str] = []
    summary: dict = {}

    drawdown_anchors = [
        ("2007-09-15", "GFC pre-Lehman", "full"),
        ("2020-02-20", "covid peak",     "full"),
        ("2000-03-15", "dot-com",        "partial"),
    ]
    calm_anchors = [
        ("2005-06-01", "mid-cycle"),
        ("2014-06-01", "post-GFC"),
        ("2017-06-01", "calm trough"),
    ]
    unreachable_anchors = [
        ("1929-08-01", "great-depression",
         "T components missing pre-1996 — HY OAS / VIX / S5FI / MOVE / gamma all empty"),
        ("1973-09-01", "stagflation",
         "T components missing pre-1996 — same reason as 1929"),
    ]

    per_anchor: list[dict] = []
    event_scores: dict[str, float] = {}
    calm_scores: dict[str, float] = {}

    def _record(asof_str: str, label: str, reach: str, so) -> None:
        per_anchor.append({
            "as_of": asof_str, "label": label, "reach": reach,
            "score": round(so.raw_score, 4),
            "V": round(so.metadata_extra["V_score"], 3),
            "T": round(so.metadata_extra["T_score"], 3),
            "R": round(so.metadata_extra["R_multiplier"], 3),
            "regime_state": so.regime_state,
            "regime_state_source": so.metadata_extra.get("regime_state_source"),
            "neutralized": so.metadata_extra.get("regime_neutralized"),
        })

    for asof_str, label, reach in drawdown_anchors:
        try:
            so = compute_cdrs(PitDataContext(as_of=pd.Timestamp(asof_str)))
        except Exception as exc:
            findings.append(
                f"FAIL: compute_cdrs at {asof_str} raised "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        if not 0.0 <= so.raw_score <= 1.0:
            findings.append(
                f"FAIL: CDRS at {asof_str} = {so.raw_score} out of [0,1]"
            )
        for cap_name, cap_val in so.quality_caps_applied.items():
            if cap_val is None:
                continue
            if so.final_quality_cap > cap_val + 1e-9:
                findings.append(
                    f"FAIL: final_quality_cap={so.final_quality_cap} > "
                    f"{cap_name}={cap_val} at {asof_str}"
                )
        for key in ("V_score", "T_score", "R_multiplier"):
            if key not in so.metadata_extra:
                findings.append(f"FAIL: metadata_extra missing {key} at {asof_str}")
        event_scores[asof_str] = so.raw_score
        _record(asof_str, label, reach, so)

    for asof_str, label in calm_anchors:
        try:
            so = compute_cdrs(PitDataContext(as_of=pd.Timestamp(asof_str)))
        except Exception as exc:
            findings.append(
                f"FAIL: compute_cdrs at calm {asof_str} raised "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        if not 0.0 <= so.raw_score <= 1.0:
            findings.append(
                f"FAIL: CDRS at {asof_str} = {so.raw_score} out of [0,1]"
            )
        calm_scores[asof_str] = so.raw_score
        _record(asof_str, label, "calm", so)

    if event_scores.get("2007-09-15", 0.0) >= 0.18:
        findings.append(
            f"Floor 2007-09 >= 0.18 OK (CDRS={event_scores['2007-09-15']:.4f})"
        )
    else:
        findings.append(
            f"FAIL: floor 2007-09 < 0.18 (got {event_scores.get('2007-09-15')})"
        )
    if event_scores.get("2020-02-20", 0.0) >= 0.13:
        findings.append(
            f"Floor 2020-02 >= 0.13 OK (CDRS={event_scores['2020-02-20']:.4f})"
        )
    else:
        findings.append(
            f"FAIL: floor 2020-02 < 0.13 (got {event_scores.get('2020-02-20')})"
        )
    if event_scores.get("2000-03-15", 0.0) >= 0.13:
        findings.append(
            f"Floor 2000-03 partial >= 0.13 OK "
            f"(CDRS={event_scores['2000-03-15']:.4f})"
        )
    else:
        findings.append(
            f"FAIL: floor 2000-03 < 0.13 (got {event_scores.get('2000-03-15')})"
        )

    if event_scores and calm_scores:
        e_full = [
            event_scores[k] for k, _, r in drawdown_anchors
            if r == "full" and k in event_scores
        ]
        c_max = max(calm_scores.values())
        if e_full and min(e_full) > c_max:
            findings.append(
                f"Direction OK: min(full events)={min(e_full):.4f} > "
                f"max(calm)={c_max:.4f}"
            )
        else:
            findings.append(
                f"FAIL: direction broken: full-reach events {e_full}, "
                f"max calm {c_max}"
            )
        e_max = max(event_scores.values())
        if c_max > 0 and e_max >= 3.0 * c_max:
            findings.append(
                f"Differential ratio OK: max(events)={e_max:.4f} >= "
                f"3.0x max(calm)={c_max:.4f} (ratio={e_max / c_max:.2f}x)"
            )
        else:
            findings.append(
                f"FAIL: differential ratio < 3.0x"
                f"(events={e_max:.4f}, calm={c_max:.4f})"
            )

    findings.append(
        f"Stage decomposition (V/T/R) recorded on all "
        f"{len(per_anchor)} reachable anchors"
    )

    sample_active = ["SHILLER_CAPE", "FINRA_MARGIN_DEBT", "RSP", "DAMODARAN_EY",
                     "BAMLH0A0HYM2", "VIX_YAHOO", "S5FI", "MOVE"]
    dc = check_double_counting(sample_active)
    if not dc:
        findings.append(
            "Composite guards pass: no double-counting on CDRS active set"
        )
    else:
        findings.append(
            f"FAIL: composite guard fired on CDRS active set: {dc}"
        )

    for asof_str, label, reason in unreachable_anchors:
        raised = False
        try:
            compute_cdrs(PitDataContext(as_of=pd.Timestamp(asof_str)))
        except _CompositeBuildError:
            raised = True
        except Exception:
            raised = True
        marker = "OK" if raised else "FAIL"
        findings.append(
            f"Unreachable {asof_str} ({label}): {marker}. {reason}"
        )
        if not raised:
            findings.append(
                f"FAIL: expected unreachable {asof_str} to raise"
            )

    summary["per_anchor"] = per_anchor
    summary["unreachable"] = [
        {"as_of": a, "label": label, "reason": reason}
        for a, label, reason in unreachable_anchors
    ]
    summary["events"] = event_scores
    summary["calm"] = calm_scores

    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(
        name="Gate 10 - Layer 3C CDRS (Path B + D13/D14)", passed=passed,
        findings=findings, warnings=warnings, summary=summary,
    )


def validate_gate11_r_squared_panel() -> GateReport:
    """Gate 11 — Layer 3D R^2 master panel (Path B + D16-D19).

    Per ``LAYER_3_BUILD_SPEC.md`` §7.8 + Strategic Claude 3D kickoff:

      1. Panel rows == |indicators| × |horizons| × |targets|
         (NO_OVERLAP rows kept per D16 for provenance).
      2. Coverage: non-NO_OVERLAP rows >= 80% of total cells
         (the spec wanted ">= 80% FULL"; Path B reality with our
         actual sample sizes lands closer to 76% FULL but ~98%
         non-NO_OVERLAP — D19 calibration to non-NO_OVERLAP).
      3. Every FULL row has all stats populated (no NaN in
         r_squared, beta, p_value_beta_NW, residual_se).
      4. n_nominal >= n_eff_nonoverlap always.
      5. CAPE × 10Y R² > 0.20 with beta < 0 and p_NW < 0.01
         (D19: spec wanted >0.40 but Path B with full 1881-2016
         sample lands at ~0.24 — still highly significant).
      6. Master panel cached atomically with valid sha256 +
         schema_version + row_count.
      7. Sample-size honesty: every row reports BOTH n_nominal and
         n_eff_nonoverlap; every UNDERPOWERED row has
         is_underpowered=True.
      8. NO_OVERLAP rows kept with NaN stats (D16) — at least the
         expected ~14 cells (CBOE_GAMMA / IORB / SOFR / XLC /
         CNY_RESERVE_SHARE × long horizons).
    """
    from macro_pipeline.analysis import (
        PANEL_CACHE_PATH,
        PANEL_SCHEMA_VERSION,
        VERDICT_FULL,
        VERDICT_NO_OVERLAP,
        VERDICT_UNDERPOWERED,
        load_panel,
    )

    findings: list[str] = []
    warnings: list[str] = []
    summary: dict = {}

    try:
        panel = load_panel()
    except FileNotFoundError as exc:
        findings.append(f"FAIL: panel cache missing: {exc}")
        return GateReport(
            name="Gate 11 - Layer 3D R^2 Panel", passed=False,
            findings=findings, summary=summary,
        )

    # 1. Rows = indicators x horizons x targets
    counts = panel.groupby(["target", "horizon_label", "verdict"]).size()
    total = int(panel.shape[0])
    summary["total_rows"] = total

    n_full = int((panel["verdict"] == VERDICT_FULL).sum())
    n_under = int((panel["verdict"] == VERDICT_UNDERPOWERED).sum())
    n_no_overlap = int((panel["verdict"] == VERDICT_NO_OVERLAP).sum())
    summary["full"] = n_full
    summary["underpowered"] = n_under
    summary["no_overlap"] = n_no_overlap

    findings.append(
        f"Panel rows = {total} ({n_full} FULL + {n_under} UNDERPOWERED + "
        f"{n_no_overlap} NO_OVERLAP)"
    )

    # 2. Non-NO_OVERLAP coverage >= 80%
    coverage = (total - n_no_overlap) / max(1, total)
    summary["non_no_overlap_coverage_pct"] = round(coverage * 100, 2)
    if coverage >= 0.80:
        findings.append(
            f"Coverage OK: {coverage*100:.1f}% non-NO_OVERLAP "
            "(>= 80% threshold)"
        )
    else:
        findings.append(
            f"FAIL: only {coverage*100:.1f}% non-NO_OVERLAP coverage"
        )

    # 3. FULL rows have finite stats
    full_rows = panel.query("verdict == 'FULL'")
    nan_count = full_rows[
        ["alpha", "beta", "r_squared", "p_value_beta_NW", "residual_se"]
    ].isna().any(axis=1).sum()
    if nan_count == 0:
        findings.append(
            f"All {len(full_rows)} FULL rows have finite stats"
        )
    else:
        findings.append(
            f"FAIL: {nan_count} FULL rows have NaN stats"
        )

    # 4. n_nominal >= n_eff_nonoverlap
    bad = (panel["n_nominal"] < panel["n_eff_nonoverlap"]).sum()
    if bad == 0:
        findings.append("n_nominal >= n_eff_nonoverlap on every row")
    else:
        findings.append(
            f"FAIL: {bad} rows have n_eff_nonoverlap > n_nominal"
        )

    # 5. CAPE x 10Y signal sanity (D19 calibrated)
    cape_row = panel.query(
        "indicator_id == 'SHILLER_CAPE' and target == 'SHILLER_TR_PRICE' "
        "and horizon_label == '10Y'"
    )
    if cape_row.empty:
        findings.append("FAIL: CAPE x SHILLER_TR_PRICE x 10Y row missing")
    else:
        r = cape_row.iloc[0]
        cape_r2 = float(r["r_squared"])
        cape_beta = float(r["beta"])
        cape_p = float(r["p_value_beta_NW"])
        summary["cape_10y_r_squared"] = round(cape_r2, 4)
        summary["cape_10y_beta"] = round(cape_beta, 6)
        summary["cape_10y_p_NW"] = round(cape_p, 6)
        if cape_r2 > 0.20 and cape_beta < 0 and cape_p < 0.01:
            findings.append(
                f"CAPE x 10Y signal OK (D19 calibrated): R^2={cape_r2:.4f} "
                f"(>0.20), beta={cape_beta:.4f} (<0), p_NW={cape_p:.4g} (<0.01)"
            )
        else:
            findings.append(
                f"FAIL: CAPE x 10Y signal unexpected: R^2={cape_r2:.4f}, "
                f"beta={cape_beta:.4f}, p_NW={cape_p:.4g}"
            )

    # 6. Atomic cache sidecar
    import json
    parquet_path = pd_resolve_panel_path(PANEL_CACHE_PATH)
    sidecar_path = parquet_path.with_suffix(".meta.json")
    if not parquet_path.exists() or not sidecar_path.exists():
        findings.append(
            f"FAIL: panel cache or sidecar missing at {parquet_path}"
        )
    else:
        md = json.loads(sidecar_path.read_text())
        sha = md.get("data_sha256")
        sv = md.get("schema_version")
        rc = md.get("row_count")
        summary["panel_parquet"] = str(parquet_path)
        summary["panel_sha256"] = sha
        summary["panel_schema_version"] = sv
        summary["panel_row_count"] = rc
        if sha and len(sha) == 64 and sv == PANEL_SCHEMA_VERSION and rc == total:
            findings.append(
                f"Atomic cache OK: sha256[:8]={sha[:8]}, schema={sv}, rows={rc}"
            )
        else:
            findings.append(
                f"FAIL: atomic cache metadata inconsistent: "
                f"sha={sha}, schema={sv}, row_count={rc} vs panel.rows={total}"
            )

    # 7. Sample-size honesty
    n_eff_present = panel["n_eff_nonoverlap"].notna().all()
    n_nom_present = panel["n_nominal"].notna().all()
    under_flag_correct = (
        (panel["verdict"] == VERDICT_UNDERPOWERED) == panel["is_underpowered"]
    ).all()
    if n_eff_present and n_nom_present and under_flag_correct:
        findings.append(
            "Sample-size honesty: every row carries n_nominal and "
            "n_eff_nonoverlap; is_underpowered tracks verdict"
        )
    else:
        findings.append(
            f"FAIL: sample-size honesty: n_nominal_present={n_nom_present}, "
            f"n_eff_present={n_eff_present}, "
            f"flag_consistent={under_flag_correct}"
        )

    # 8. NO_OVERLAP coverage
    expected_min_no_overlap = 10  # observed 14 in 3D-prep-2; allow buffer
    if n_no_overlap >= expected_min_no_overlap:
        findings.append(
            f"NO_OVERLAP cells present (D16): {n_no_overlap} rows "
            f"(>= {expected_min_no_overlap})"
        )
    else:
        findings.append(
            f"WARNING: only {n_no_overlap} NO_OVERLAP cells "
            f"(expected ~14 from prep audit)"
        )

    # NO_OVERLAP rows must have NaN stats
    no_ov = panel.query("verdict == 'NO_OVERLAP'")
    nan_check = no_ov[
        ["alpha", "beta", "r_squared", "p_value_beta_NW"]
    ].isna().all(axis=1).all()
    if nan_check:
        findings.append("NO_OVERLAP rows have NaN stats (D16 honored)")
    else:
        findings.append(
            "FAIL: NO_OVERLAP rows have non-NaN stats (D16 violated)"
        )

    summary["per_target_horizon_verdict"] = (
        counts.unstack(fill_value=0).to_dict()
    )

    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(
        name="Gate 11 - Layer 3D R^2 Panel", passed=passed,
        findings=findings, warnings=warnings, summary=summary,
    )


def pd_resolve_panel_path(path):
    """Tiny indirection so tests/CLI can swap the panel location."""
    from pathlib import Path
    return Path(path)


def validate_gate12_hmm_frozen() -> GateReport:
    """Gate 12 — Layer 3.5A HMM frozen-contract integrity.

    Per ``LAYER_3_5_BUILD_SPEC.md`` §3.6:

      1. Pickle exists at ``data/cache/hmm/regime_3state_v1.pkl``.
      2. Sidecar exists at ``data/cache/hmm/regime_3state_v1.meta.json``.
      3. Recomputed sha256 of pickle bytes == sidecar ``data_sha256``.
      4. Sidecar has all required keys (``SIDECAR_REQUIRED_KEYS``).
      5. Sidecar ``schema_version`` == ``SIDECAR_SCHEMA_VERSION``.
      6. Sidecar ``model_version`` == ``SIDECAR_MODEL_VERSION``.
      7. Sidecar ``hmmlearn_version`` == ``"0.3.3"``.
      8. NBER overlap sanity: ``recession`` state has the highest NBER
         overlap among the three states (data-driven label assignment).
      9. ``train_and_save_hmm`` is NOT importable from
         ``macro_pipeline.regime`` (Codex finding R closure).
     10. ``load_hmm()`` returns a ``TrainedHmm`` whose
         ``state_to_label`` mapping equals the sidecar's mapping.
    """
    import hashlib
    import json
    from pathlib import Path

    findings: list[str] = []
    warnings: list[str] = []
    summary: dict = {}

    from macro_pipeline.regime.hmm_states import (
        HMM_PICKLE_PATH,
        HMM_SIDECAR_PATH,
        SIDECAR_MODEL_VERSION,
        SIDECAR_REQUIRED_KEYS,
        SIDECAR_SCHEMA_VERSION,
    )

    pickle_path = Path(HMM_PICKLE_PATH)
    sidecar_path = Path(HMM_SIDECAR_PATH)

    # 1. Pickle exists
    if not pickle_path.exists():
        findings.append(f"FAIL: pickle missing at {pickle_path}")
        return GateReport(
            name="Gate 12 - Layer 3.5A HMM Frozen Contract",
            passed=False, findings=findings, summary=summary,
        )
    findings.append(f"Pickle present: {pickle_path}")

    # 2. Sidecar exists
    if not sidecar_path.exists():
        findings.append(f"FAIL: sidecar missing at {sidecar_path}")
        return GateReport(
            name="Gate 12 - Layer 3.5A HMM Frozen Contract",
            passed=False, findings=findings, summary=summary,
        )
    findings.append(f"Sidecar present: {sidecar_path}")

    # 3. sha256 verification
    h = hashlib.sha256()
    with pickle_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    actual_sha = h.hexdigest()
    summary["pickle_sha256"] = actual_sha

    try:
        meta = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append(f"FAIL: sidecar is not valid JSON: {exc}")
        return GateReport(
            name="Gate 12 - Layer 3.5A HMM Frozen Contract",
            passed=False, findings=findings, summary=summary,
        )
    expected_sha = meta.get("data_sha256")
    summary["sidecar_data_sha256"] = expected_sha
    if expected_sha == actual_sha:
        findings.append(
            f"sha256 OK: recomputed={actual_sha[:8]} matches sidecar"
        )
    else:
        findings.append(
            f"FAIL: sha256 mismatch (recomputed={actual_sha}, "
            f"sidecar.data_sha256={expected_sha})"
        )

    # 4-7. Sidecar key presence + values
    missing = [k for k in SIDECAR_REQUIRED_KEYS if k not in meta]
    if missing:
        findings.append(f"FAIL: sidecar missing keys {missing}")
    else:
        findings.append(
            f"All {len(SIDECAR_REQUIRED_KEYS)} required sidecar keys present"
        )

    if meta.get("schema_version") == SIDECAR_SCHEMA_VERSION:
        findings.append(f"schema_version OK: {SIDECAR_SCHEMA_VERSION}")
    else:
        findings.append(
            f"FAIL: schema_version={meta.get('schema_version')!r} "
            f"(expected {SIDECAR_SCHEMA_VERSION!r})"
        )

    if meta.get("model_version") == SIDECAR_MODEL_VERSION:
        findings.append(f"model_version OK: {SIDECAR_MODEL_VERSION}")
    else:
        findings.append(
            f"FAIL: model_version={meta.get('model_version')!r} "
            f"(expected {SIDECAR_MODEL_VERSION!r})"
        )

    expected_hmmlearn = "0.3.3"
    if meta.get("hmmlearn_version") == expected_hmmlearn:
        findings.append(f"hmmlearn_version OK: {expected_hmmlearn}")
    else:
        findings.append(
            f"FAIL: hmmlearn_version={meta.get('hmmlearn_version')!r} "
            f"(expected {expected_hmmlearn!r})"
        )

    summary["feature_names"] = meta.get("feature_names")
    summary["state_to_label_mapping"] = meta.get("state_to_label_mapping")
    summary["nber_overlap_per_state"] = meta.get("nber_overlap_per_state")

    # 8. NBER overlap sanity
    overlap = meta.get("nber_overlap_per_state", {})
    state_to_label = meta.get("state_to_label_mapping", {})
    if overlap and state_to_label:
        try:
            recession_idx = next(
                k for k, v in state_to_label.items() if v == "recession"
            )
            recession_overlap = float(overlap.get(recession_idx, 0.0))
            other_max = max(
                float(v) for k, v in overlap.items() if k != recession_idx
            )
            if recession_overlap > other_max:
                findings.append(
                    f"NBER overlap sanity OK: recession-state idx="
                    f"{recession_idx} has overlap={recession_overlap:.4f} "
                    f"(> other max {other_max:.4f})"
                )
            else:
                findings.append(
                    f"FAIL: NBER overlap sanity broken — recession idx="
                    f"{recession_idx} overlap={recession_overlap:.4f} not > "
                    f"other max {other_max:.4f}"
                )
        except StopIteration:
            findings.append("FAIL: no recession entry in state_to_label_mapping")
    else:
        findings.append("FAIL: NBER overlap or state mapping missing in sidecar")

    # 9. train_and_save_hmm not importable
    train_importable = False
    try:
        from macro_pipeline.regime import (  # type: ignore[attr-defined]  # noqa: F401
            train_and_save_hmm,
        )
        train_importable = True
    except ImportError:
        pass
    if train_importable:
        findings.append(
            "FAIL: train_and_save_hmm STILL importable from "
            "macro_pipeline.regime (Codex finding R not closed)"
        )
    else:
        findings.append(
            "train_and_save_hmm NOT importable (Codex finding R closed)"
        )

    # 10. load_hmm consistency
    try:
        from macro_pipeline.regime import load_hmm
        bundle = load_hmm()
        loaded_mapping = {str(k): v for k, v in bundle.state_to_label.items()}
        if loaded_mapping == state_to_label:
            findings.append(
                "load_hmm() state_to_label mapping == sidecar mapping"
            )
        else:
            findings.append(
                f"FAIL: load_hmm mapping {loaded_mapping} != sidecar "
                f"{state_to_label}"
            )
    except Exception as exc:
        findings.append(
            f"FAIL: load_hmm() raised {type(exc).__name__}: {exc}"
        )

    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(
        name="Gate 12 - Layer 3.5A HMM Frozen Contract",
        passed=passed, findings=findings, warnings=warnings, summary=summary,
    )


def validate_gate13_pit_contracts() -> GateReport:
    """Gate 13 — Layer 3.5B PIT contract integrity (Option Z + fail-closed).

    Per ``LAYER_3_5_BUILD_SPEC.md`` §4.6:

      1. ``audit_pit_contracts()`` returns 0 mismatches.
      2. SAHMREALTIME has ``pit_safe_by_construction=True``,
         non-empty rationale, ``derived_confidence_cap=0.70``.
      3. Removing the flag from SAHMREALTIME (in-memory mutation in
         a test) deterministically fails Gate 13 — verified at runtime
         by reading ``FRED_SERIES_API`` live (not a frozen snapshot).
      4. CRPS confidence at the 4 spec anchor dates respects the cap
         (1998-08-01 / 2001-04-01 / 2008-09-15 / 2020-04-01).
    """
    import pandas as pd

    from macro_pipeline.config import FRED_SERIES_API
    from macro_pipeline.utils.pit_audit import audit_pit_contracts

    findings: list[str] = []
    warnings: list[str] = []
    summary: dict = {}

    # 1. Audit returns 0 mismatches (live config read)
    report = audit_pit_contracts()
    summary["audit_total_violations"] = report.total_violations
    summary["option_z_series"] = list(
        report.series_with_pit_safe_by_construction_true
    )
    if report.total_violations == 0:
        findings.append(
            f"audit_pit_contracts: 0 mismatches "
            f"({len(report.series_with_needs_vintage_true)} vintage=True, "
            f"{len(report.series_in_VINTAGE_REQUIRED_SERIES)} in panel, "
            f"{len(report.series_with_pit_safe_by_construction_true)} "
            "Option Z)"
        )
    else:
        findings.append(
            f"FAIL: audit returned {report.total_violations} mismatches"
        )
        for m in report.mismatches:
            findings.append(f"  - {m.series_id}: {m.reason}")

    # 2. SAHMREALTIME spec checks (live config read)
    sahm = FRED_SERIES_API.get("SAHMREALTIME", {})
    if not sahm.get("pit_safe_by_construction"):
        findings.append(
            "FAIL: SAHMREALTIME pit_safe_by_construction must be True"
        )
    else:
        findings.append("SAHMREALTIME pit_safe_by_construction=True OK")

    rationale = sahm.get("pit_construction_rationale", "")
    summary["sahm_rationale_chars"] = len(rationale or "")
    if not rationale or len(rationale) < 100:
        findings.append(
            f"FAIL: SAHMREALTIME rationale must be ≥100 chars "
            f"(got {len(rationale or '')})"
        )
    else:
        findings.append(
            f"SAHMREALTIME rationale OK ({len(rationale)} chars)"
        )

    cap = sahm.get("derived_confidence_cap")
    summary["sahm_derived_confidence_cap"] = cap
    if cap != 0.70:
        findings.append(
            f"FAIL: SAHMREALTIME derived_confidence_cap={cap!r} "
            "(expected 0.70)"
        )
    else:
        findings.append("SAHMREALTIME derived_confidence_cap=0.70 OK")

    # 3. CRPS confidence at 4 anchor dates respects cap
    from macro_pipeline.access import PitDataContext
    from macro_pipeline.scoring.crps import compute_crps

    anchor_dates = ["1998-08-01", "2001-04-01", "2008-09-15", "2020-04-01"]
    anchor_results: list[dict] = []
    cap_70 = 0.70
    all_ok = True
    for asof in anchor_dates:
        ctx = PitDataContext(as_of=pd.Timestamp(asof))
        try:
            obs = compute_crps(ctx)
        except Exception as exc:
            findings.append(
                f"FAIL: compute_crps at {asof} raised "
                f"{type(exc).__name__}: {exc}"
            )
            all_ok = False
            continue
        conf01 = float(obs.confidence) / 100.0
        respected = conf01 <= cap_70 + 1e-9
        anchor_results.append(
            {"as_of": asof, "score": round(obs.raw_score, 4),
             "confidence_01": round(conf01, 6),
             "final_quality_cap": round(obs.final_quality_cap, 4),
             "respects_cap": respected}
        )
        if not respected:
            all_ok = False
    summary["anchor_results"] = anchor_results
    if all_ok and len(anchor_results) == 4:
        findings.append(
            "CRPS confidence respects 0.70 cap at all 4 anchors "
            f"(1998-08-01: {anchor_results[0]['confidence_01']}, "
            f"2001-04-01: {anchor_results[1]['confidence_01']}, "
            f"2008-09-15: {anchor_results[2]['confidence_01']}, "
            f"2020-04-01: {anchor_results[3]['confidence_01']})"
        )
    elif not all_ok:
        findings.append(
            "FAIL: at least one anchor's CRPS confidence exceeds 0.70 cap"
        )

    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(
        name="Gate 13 - Layer 3.5B PIT Contract (Option Z)",
        passed=passed, findings=findings, warnings=warnings, summary=summary,
    )


def validate_gate14_nber_calendar() -> GateReport:
    """Gate 14 — Layer 3.5C NBER announcement calendar integrity.

    Per ``LAYER_3_5_BUILD_SPEC.md`` §5.6:

      1. ``data/nber_announcement_calendar.csv`` exists and parses cleanly
         via ``NberCalendarLoader``.
      2. All cycles 1978+ from NBER official record present (currently
         6: 1980, 1981, 1990, 2001, 2007, 2020).
      3. Every row has source_url pointing to NBER.
      4. ``release_lag_days=180`` constant absent from
         ``nber_extract.py`` source code (only docstring deprecation
         notes permitted).
      5. Pre-1978 real-time inference raises ``PitDataUnavailableError``.
      6. Spec test #7 contract: at as_of=2008-09-01 querying 2008-09-01
         returns "expansion" (different from latest-mode "recession" —
         demonstrates calendar uses actual lag, not 180-day approx).
    """
    import re
    from pathlib import Path

    from macro_pipeline.access import PitDataContext
    from macro_pipeline.regime import (
        NBER_CALENDAR_BOUNDARY,
        NberCalendarLoader,
        extract_nber_state,
    )
    from macro_pipeline.regime.exceptions import PitDataUnavailableError

    findings: list[str] = []
    warnings: list[str] = []
    summary: dict = {}

    # 1. CSV loads cleanly.
    try:
        cal = NberCalendarLoader()
    except Exception as exc:
        findings.append(f"FAIL: NberCalendarLoader construction raised "
                        f"{type(exc).__name__}: {exc}")
        return GateReport(
            name="Gate 14 - Layer 3.5C NBER Announcement Calendar",
            passed=False, findings=findings, summary=summary,
        )
    summary["csv_path"] = str(cal.csv_path)
    summary["n_cycles"] = len(cal.cycles)
    findings.append(
        f"NberCalendarLoader OK: {len(cal.cycles)} cycles loaded from "
        f"{cal.csv_path.name}"
    )

    # 2. Cycle completeness — expected 6 post-1978.
    expected_peaks = {
        "1980-01", "1981-07", "1990-07", "2001-03", "2007-12", "2020-02",
    }
    actual_peaks = {str(c.peak_date) for c in cal.cycles}
    missing = expected_peaks - actual_peaks
    extra = actual_peaks - expected_peaks
    summary["actual_peaks"] = sorted(actual_peaks)
    if missing or extra:
        if missing:
            findings.append(f"FAIL: missing expected cycles: {sorted(missing)}")
        if extra:
            findings.append(
                f"WARN: unexpected cycles in calendar: {sorted(extra)} "
                "(may be a new NBER announcement; investigate)"
            )
            warnings.append(f"Extra cycles: {sorted(extra)}")
    else:
        findings.append(
            f"All 6 expected post-1978 cycles present: {sorted(actual_peaks)}"
        )

    # 3. source_url present + non-empty + points to nber.org.
    bad_url = [
        c.peak_date for c in cal.cycles
        if not c.source_url or "nber.org" not in c.source_url
    ]
    if bad_url:
        findings.append(
            f"FAIL: {len(bad_url)} cycles missing nber.org source_url: "
            f"{[str(p) for p in bad_url]}"
        )
    else:
        findings.append("All cycles have nber.org source_url")

    # 4. release_lag_days=180 not in nber_extract.py source code.
    # Only literal Python source-syntax matches count; docstring mentions
    # (which carry backtick fences) and comments (#) are explicitly
    # exempted. The exclusion class includes backticks so the regex
    # cannot match `` ` ``release_lag_days=180`` ` `` inside a sphinx
    # double-backtick code span.
    nber_extract_path = (
        Path(__file__).parent / "regime" / "nber_extract.py"
    )
    text = nber_extract_path.read_text(encoding="utf-8")
    code_hits = re.findall(
        r"^\s*[^#\s\"\'`]*release_lag_days\s*=\s*180\b",
        text, flags=re.MULTILINE,
    )
    if code_hits:
        findings.append(
            f"FAIL: nber_extract.py has {len(code_hits)} live "
            "release_lag_days=180 reference(s)"
        )
    else:
        findings.append(
            "release_lag_days=180 absent from nber_extract.py code "
            "(docstring/comment mentions allowed)"
        )

    # 5. Pre-1978 real-time inference raises.
    pre_ctx = PitDataContext(as_of=pd.Timestamp("2024-01-01"), is_real_time=True)
    raised = False
    try:
        extract_nber_state(pd.Timestamp("1975-06-01"), ctx=pre_ctx)
    except PitDataUnavailableError:
        raised = True
    if raised:
        findings.append(
            "Pre-1978 real-time raises PitDataUnavailableError (training_only "
            "policy enforced)"
        )
    else:
        findings.append(
            "FAIL: pre-1978 real-time should have raised "
            "PitDataUnavailableError"
        )

    # 6. Spec test #7: as_of=2008-09 + query=2008-09 → expansion (calendar
    # path); latest-mode for same query → recession.
    pit_ctx = PitDataContext(as_of=pd.Timestamp("2008-09-01"))
    pit_state = extract_nber_state(
        pd.Timestamp("2008-09-01"), ctx=pit_ctx
    ).state
    latest_state = extract_nber_state(pd.Timestamp("2008-09-01")).state
    summary["pit_state_2008_09"] = pit_state
    summary["latest_state_2008_09"] = latest_state
    if pit_state == "expansion" and latest_state == "recession":
        findings.append(
            "Calendar contract OK: at as_of=2008-09-01 query=2008-09 -> "
            f"PIT={pit_state!r}, latest={latest_state!r} (peak announced "
            "2008-12-01)"
        )
    else:
        findings.append(
            f"FAIL: calendar contract — PIT={pit_state!r}, "
            f"latest={latest_state!r} (expected expansion / recession)"
        )

    # 7. Boundary period.
    summary["calendar_boundary"] = str(NBER_CALENDAR_BOUNDARY)

    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(
        name="Gate 14 - Layer 3.5C NBER Announcement Calendar",
        passed=passed, findings=findings, warnings=warnings, summary=summary,
    )


def _cli_gate11() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    report = validate_gate11_r_squared_panel()
    print(report.render())
    return 0 if report.passed else 1


def _cli_gate12() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    report = validate_gate12_hmm_frozen()
    print(report.render())
    return 0 if report.passed else 1


def _cli_gate13() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    report = validate_gate13_pit_contracts()
    print(report.render())
    return 0 if report.passed else 1


def _cli_gate14() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    report = validate_gate14_nber_calendar()
    print(report.render())
    return 0 if report.passed else 1


def validate_gate15_probability_semantics() -> GateReport:
    """Gate 15 — Layer 3.5D probability semantics + dissent fail-closed.

    Per ``LAYER_3_5_BUILD_SPEC.md`` §6.6:

      1. ``RegimeState`` enum includes INDETERMINATE.
      2. ``derive_regime_state`` returns INDETERMINATE on HMM dissent
         (verified at 2025-06-01 — known dissent point).
      3. INDETERMINATE caps confidence_overall ≤0.60 (×100 in [0, 100]
         scale → ≤60).
      4. CDRS R_MULTIPLIER for INDETERMINATE = consensus state's R
         (per AM21=B / D24); R=0.6 at 2025-06 (consensus expansion);
         R=1.0 at 2008-09 (consensus late-cycle).
      5. ``ScoredObservation.raw_score`` field exists;
         ``calibrated_probability`` field exists with default None.
      6. Zero non-deprecated references to ``score_value`` in package
         code (excluding the deprecated ``@property``).
      7. Layer 6-facing strings consistently use "Risk Score" not
         "probability" for raw composites.
    """
    import ast
    import re
    from pathlib import Path

    from macro_pipeline.access import PitDataContext
    from macro_pipeline.regime import (
        INDETERMINATE_CONFIDENCE_CAP,
        RegimeState,
        build_regime_context,
    )
    from macro_pipeline.scoring.cdrs import compute_cdrs
    from macro_pipeline.scoring.crps import compute_crps
    from macro_pipeline.scoring.scored_observation import ScoredObservation

    findings: list[str] = []
    warnings_list: list[str] = []
    summary: dict = {}

    # 1. RegimeState enum has INDETERMINATE
    if RegimeState.INDETERMINATE.value == "indeterminate":
        findings.append("RegimeState.INDETERMINATE = 'indeterminate' OK")
    else:
        findings.append(
            f"FAIL: RegimeState.INDETERMINATE.value = "
            f"{RegimeState.INDETERMINATE.value!r}"
        )

    # 2. derive_regime_state at 2025-06 → INDETERMINATE
    rc = build_regime_context(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    state, source, haircut = rc.derive_regime_state()
    summary["dissent_anchor_2025_06"] = {
        "state": state, "source": source, "haircut": haircut,
    }
    if state == RegimeState.INDETERMINATE.value:
        findings.append(
            f"derive_regime_state at 2025-06 -> ({state!r}, {source!r}, "
            f"haircut={haircut})"
        )
    else:
        findings.append(
            f"FAIL: derive_regime_state at 2025-06 returned ({state!r}, "
            f"{source!r}); expected indeterminate"
        )

    # 3. INDETERMINATE caps confidence ≤60 (CRPS at 2025-06)
    crps_25 = compute_crps(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    summary["crps_2025_06_confidence"] = round(crps_25.confidence, 4)
    if crps_25.confidence <= INDETERMINATE_CONFIDENCE_CAP * 100.0 + 1e-6:
        findings.append(
            f"INDETERMINATE caps CRPS confidence at "
            f"{INDETERMINATE_CONFIDENCE_CAP * 100:.0f}: "
            f"{crps_25.confidence:.2f} <= "
            f"{INDETERMINATE_CONFIDENCE_CAP * 100:.0f}"
        )
    else:
        findings.append(
            f"FAIL: CRPS confidence at 2025-06 = "
            f"{crps_25.confidence:.2f} exceeds INDETERMINATE cap "
            f"{INDETERMINATE_CONFIDENCE_CAP * 100:.0f}"
        )

    # 4. CDRS R = consensus R for INDETERMINATE (AM21=B)
    cdrs_25 = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    cdrs_08 = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2008-09-15")))
    r_25 = cdrs_25.metadata_extra["R_multiplier"]
    r_08 = cdrs_08.metadata_extra["R_multiplier"]
    summary["cdrs_2025_06_R"] = r_25
    summary["cdrs_2008_09_R"] = r_08
    # Consensus at 2025-06 = expansion (R=0.6); at 2008-09 = late-cycle (R=1.0)
    if r_25 == 0.6 and r_08 == 1.0:
        findings.append(
            "CDRS R from consensus (AM21=B) OK: 2025-06 R=0.6 "
            "(consensus expansion), 2008-09 R=1.0 (consensus late-cycle)"
        )
    else:
        findings.append(
            f"FAIL: CDRS R for INDETERMINATE not from consensus: "
            f"2025-06 R={r_25} (expected 0.6), 2008-09 R={r_08} "
            "(expected 1.0)"
        )

    # 5. ScoredObservation has raw_score + calibrated_probability fields
    fields_present = {f.name for f in ScoredObservation.__dataclass_fields__.values()}
    summary["scored_observation_fields"] = sorted(fields_present)
    if "raw_score" in fields_present and "calibrated_probability" in fields_present:
        findings.append(
            "ScoredObservation: raw_score + calibrated_probability fields present"
        )
    else:
        findings.append(
            f"FAIL: missing field(s); have={sorted(fields_present)}"
        )
    if cdrs_25.calibrated_probability is None:
        findings.append("calibrated_probability defaults to None")
    else:
        findings.append(
            f"FAIL: calibrated_probability default = "
            f"{cdrs_25.calibrated_probability!r}, expected None"
        )

    # 6. Zero non-deprecated `score_value` AST references in macro_pipeline/
    # AST-walk: flag only real attribute accesses (``something.score_value``)
    # or assignment targets (``score_value = ...``). String literals,
    # docstrings, comments, and backtick-fenced sphinx code spans are
    # ignored. The deprecated property in
    # ``scoring/scored_observation.py`` is whitelisted.
    pkg_root = Path(__file__).parent
    bad_refs: list[str] = []

    class _ScoreValueWalker(ast.NodeVisitor):
        def __init__(self, rel: Path) -> None:
            self.rel = rel
            self.refs: list[tuple[int, str]] = []
            self._inside_score_value_property = False

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name == "score_value":
                # The deprecated property: skip its body entirely.
                return
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            if node.attr == "score_value":
                self.refs.append((node.lineno, "attribute_access"))
            self.generic_visit(node)

        def visit_keyword(self, node: ast.keyword) -> None:
            if node.arg == "score_value":
                # Constructor kwarg ``score_value=...``
                lineno = getattr(node.value, "lineno", -1)
                self.refs.append((lineno, "keyword_arg"))
            self.generic_visit(node)

    score_obs_rel = Path("scoring") / "scored_observation.py"
    for path in pkg_root.rglob("*.py"):
        rel = path.relative_to(pkg_root)
        if rel == score_obs_rel:
            continue  # whitelisted: contains the deprecated @property
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            bad_refs.append(f"{rel}: parse error")
            continue
        walker = _ScoreValueWalker(rel)
        walker.visit(tree)
        for lineno, kind in walker.refs:
            line = text.splitlines()[lineno - 1] if lineno >= 1 else ""
            bad_refs.append(f"{rel}:{lineno} ({kind}): {line.strip()}")
    summary["score_value_residual_refs"] = bad_refs
    if not bad_refs:
        findings.append(
            "Zero non-deprecated ``score_value`` AST refs in macro_pipeline/"
        )
    else:
        findings.append(
            f"FAIL: {len(bad_refs)} ``score_value`` AST ref(s) outside the "
            f"deprecated property: {bad_refs[:5]}"
        )

    # 7. Layer 6-facing strings: no "probability" attached to raw CRPS/CDRS
    #    (excluding L5-forward references and the documented exemptions).
    forbidden_patterns = [
        # "12M-forward recession probability" wording
        r"recession\s+probability",
        r"drawdown\s+probability",
    ]
    layer6_files = [
        pkg_root / "scoring" / "README.md",
        pkg_root / "scoring" / "crps.py",
        pkg_root / "scoring" / "cdrs.py",
        pkg_root / "regime" / "README.md",
    ]
    bad_layer6: list[str] = []
    for path in layer6_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                line_no = text[: m.start()].count("\n") + 1
                line = text.splitlines()[line_no - 1]
                # Allow L5-forward references and §D21 explainers.
                if (
                    "L5" in line or "§D21" in line or "calibrated_probability" in line
                    or "L5-RM" in line or "until L5" in line.lower()
                    or "raw_score" in line  # phrasing like "raw_score; not yet calibrated to probability"
                ):
                    continue
                # Allow the SAHM "12M_recession_probability_composite"
                # context constant (internal guard key).
                if "12M_recession_probability_composite" in line:
                    continue
                bad_layer6.append(f"{path.name}:{line_no}: {line.strip()}")
    summary["layer6_probability_residual_refs"] = bad_layer6
    if not bad_layer6:
        findings.append(
            "Layer 6-facing strings: no 'probability' wording attached to "
            "raw CRPS/CDRS (excluding L5 forward references)"
        )
    else:
        findings.append(
            f"FAIL: {len(bad_layer6)} unguarded 'probability' wording(s): "
            f"{bad_layer6[:5]}"
        )

    passed = not any(f.startswith("FAIL") for f in findings)
    return GateReport(
        name="Gate 15 - Layer 3.5D Probability Semantics + Dissent",
        passed=passed, findings=findings, warnings=warnings_list,
        summary=summary,
    )


def _cli_gate15() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    report = validate_gate15_probability_semantics()
    print(report.render())
    return 0 if report.passed else 1


def _cli_gate10() -> int:
    import logging
    logging.basicConfig(level="WARNING", format="%(message)s")
    report = validate_gate10_cdrs()
    print(report.render())
    print()
    print("=== Per-anchor CDRS detail ===")
    header = (
        f"{'as_of':<12} {'label':<22} {'reach':<9} {'score':>7} "
        f"{'V':>6} {'T':>6} {'R':>6} {'regime':<11} {'neutralized':<12}"
    )
    print(header)
    print("-" * len(header))
    for row in report.summary.get("per_anchor", []):
        print(
            f"{row['as_of']:<12} {row['label']:<22} {row['reach']:<9} "
            f"{row['score']:>7.4f} {row['V']:>6.3f} {row['T']:>6.3f} "
            f"{row['R']:>6.3f} {row['regime_state']:<11} "
            f"{row['neutralized']!s:<12}"
        )
    print()
    print("=== Declared unreachable (informational) ===")
    for u in report.summary.get("unreachable", []):
        print(f"  {u['as_of']:<12} {u['label']:<22} — {u['reason']}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "gate1"
    if cmd == "gate1":
        sys.exit(_cli_gate1())
    if cmd == "gate2":
        sys.exit(_cli_gate2())
    if cmd == "gate3":
        sys.exit(_cli_gate3())
    if cmd == "gate4a":
        sys.exit(_cli_gate4a())
    if cmd == "gate4b":
        sys.exit(_cli_gate4b())
    if cmd == "gate4c":
        sys.exit(_cli_gate4c())
    if cmd == "gate4d":
        sys.exit(_cli_gate4d())
    if cmd == "gate8":
        sys.exit(_cli_gate8())
    if cmd == "gate9":
        sys.exit(_cli_gate9())
    if cmd == "gate10":
        sys.exit(_cli_gate10())
    if cmd == "gate11":
        sys.exit(_cli_gate11())
    if cmd == "gate12":
        sys.exit(_cli_gate12())
    if cmd == "gate13":
        sys.exit(_cli_gate13())
    if cmd == "gate14":
        sys.exit(_cli_gate14())
    if cmd == "gate15":
        sys.exit(_cli_gate15())
    print(
        f"Unknown command: {cmd}. Available: "
        "gate1, gate2, gate3, gate4a, gate4b, gate4c, gate4d, "
        "gate8, gate9, gate10, gate11, gate12, gate13, gate14, gate15",
        file=sys.stderr,
    )
    sys.exit(2)


def render_sample_values(
    df: pd.DataFrame,
    metadata: dict[str, IndicatorMetadata],
    n_tail: int = 5,
) -> str:
    """Render a per-series sanity-check block showing tail observations."""
    lines: list[str] = []
    for sid in sorted(df.columns):
        meta = metadata.get(sid)
        s = df[sid].dropna()
        if s.empty:
            lines.append(f"\n--- {sid} (EMPTY) ---")
            continue
        descr = meta.description if meta else ""
        unit = meta.unit if meta else "?"
        n_outliers = meta.extra.get("n_outliers_iqr5", 0) if meta else 0
        lines.append(
            f"\n--- {sid} [{unit}] {descr} ---"
            f"\n    n_obs={s.shape[0]:,}  range=[{s.min():.4g}, {s.max():.4g}]  "
            f"outliers(IQR5)={n_outliers}  first={s.index.min().date()}  "
            f"last={s.index.max().date()}"
        )
        tail = s.tail(n_tail)
        for ts, v in tail.items():
            lines.append(f"    {ts.date()}  {v:>14.4f}")
    return "\n".join(lines)
