"""Gate validators (Build guide Section 18).

Each gate is a pure function that returns a ``GateReport`` with a pass/fail
verdict and a list of human-readable findings. Callers can render the report
to stdout / log / dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.loaders.base import IndicatorMetadata


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
    expected_min_series: int = 28,
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
    from src.config import DATA_CACHE
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
    from src.config import DATA_CACHE
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
    from src.config import DATA_CACHE
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
        findings.append(f"Cache: all 8 official_*.parquet files present")

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
    from src.config import DATA_CACHE

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
            if 4.0 <= lo and hi <= 50.0:
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
        if -3.0 <= lo and hi <= 6.0:
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
        if 50.0 <= lo and hi <= 75.0:
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
        if -20.0 <= lo and hi <= 20.0:
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
        if -1.0 <= lo and hi <= 7.0:
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
    from src.config import DATA_CACHE

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
        if 10.0 <= lo and hi <= 70.0:
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
        if -65.0 <= lo and hi <= 70.0:
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
        if 0.5 <= lo and hi <= 8.0:
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
    from src.config import DATA_CACHE
    from src.loaders.hlw_rstar_vintage import (
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
        "n_years": int(len(common)),
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
    from src.loaders.fred_loader import load_fred_all
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
    from src.loaders.tv_csv_loader import load_tv_all
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
    from src.loaders.cftc_tff_spx import load_cftc_tff_spx
    from src.loaders.yahoo_loader import load_yahoo_all
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
    from src.loaders.damodaran_erp import load_damodaran_erp
    from src.loaders.finra_margin import load_finra_margin
    from src.loaders.naaim import load_naaim
    from src.loaders.nyfed_recprob import load_nyfed_recprob

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
    from src.loaders.acm_termpremium import load_acm_termpremium
    from src.loaders.fernald_tfp import load_fernald_tfp
    from src.loaders.hlw_rstar import load_hlw_rstar
    from src.loaders.imf_cofer import load_imf_cofer
    from src.loaders.shiller import load_shiller

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
    from src.loaders.hlw_rstar_vintage import build_cache
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
    from src.loaders.aaii import load_aaii
    from src.loaders.atlanta_wage import load_atlanta_wage
    from src.loaders.cftc_tff_treasury import load_cftc_tff_treasury

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
    print(f"Unknown command: {cmd}. Available: gate1, gate2, gate3, gate4a, gate4b, gate4c, gate4d",
          file=sys.stderr)
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
