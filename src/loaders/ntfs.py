"""Engstrom-Sharpe Near-Term Forward Spread (Layer 1.5C.1).

The original spec briefly proxied NTFS as ``DGS1 - DGS3MO`` (1Y minus
3M). That is **not** what the Engstrom-Sharpe paper defines and was
flagged by ChatGPT 2026-05-09 as a methodology bug.

Definition (Engstrom & Sharpe 2018/2019/2022, "Don't Fear the Yield Curve"):

    NTFS_t = f_t(18m, 3m) − y_t(3m)

where ``f_t(18m, 3m)`` is the implied 3-month forward rate beginning 18
months ahead, computed from the Federal Reserve Board Gürkaynak-Sack-
Wright (GSW) Svensson zero-coupon curve. With continuous compounding:

    f(T, m) = [y(T+m)·(T+m) − y(T)·T] / m
    f(1.5, 0.25) = [y(1.75)·1.75 − y(1.5)·1.5] / 0.25

Two indicators are produced:

* ``NTFS_OFFICIAL_REPL`` (monthly, TB3MS as the spot 3-month leg).
  Used for CRPS re-estimation and walk-forward backtest in Layer 5.
* ``NTFS_DAILY_DASHBOARD`` (daily, DTB3 as the spot 3-month leg).
  Used for the dashboard view; explicitly tagged
  ``do_not_use_for=["crps_backtest"]`` so a Layer 5 caller that picks
  the wrong indicator can be caught.

Caveat
------
The GSW curve is a Federal Reserve staff research product, not an
official statistical release. Both indicators carry
``non_vintage_perfect=True`` to signal that the underlying parameters
can be revised retroactively without notice.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from src.cache import read_cache_validated, write_cache_atomic
from src.config import DATA_CACHE, DATA_RAW
from src.loaders.base import IndicatorMetadata, Loader
from src.loaders.fred_loader import load_fred_series

log = logging.getLogger(__name__)

GSW_URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv"
GSW_HEADER_ROWS = 9
GSW_TAU2_SENTINEL = -999.99  # replaced with NaN: marks Nelson-Siegel-only days
GSW_LOCAL_PATH = DATA_RAW / "official" / "feds200628.csv"

# Forward-rate window used by Engstrom-Sharpe.
_T_FORWARD = 1.5      # 18 months ahead
_M_FORWARD = 0.25     # 3-month forward window


# ---------------------------------------------------------------------------
# GSW download / parse
# ---------------------------------------------------------------------------
def fetch_gsw_csv(*, force_refresh: bool = False, timeout: float = 60.0) -> Path:
    """Ensure the GSW CSV is on disk under ``data/raw/official/``.

    Returns the path. The file is ~16 MB and only re-downloaded when
    ``force_refresh=True`` or the cached file is missing.
    """
    GSW_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if GSW_LOCAL_PATH.exists() and not force_refresh:
        return GSW_LOCAL_PATH
    log.info("Downloading GSW Svensson CSV from %s", GSW_URL)
    resp = requests.get(GSW_URL, timeout=timeout)
    resp.raise_for_status()
    GSW_LOCAL_PATH.write_bytes(resp.content)
    return GSW_LOCAL_PATH


def load_gsw_params(*, force_refresh: bool = False) -> pd.DataFrame:
    """Return the daily Svensson parameter table indexed by Date.

    Columns: BETA0, BETA1, BETA2, BETA3, TAU1, TAU2 (TAU2 NaN where the
    sentinel −999.99 was used). Pre-1980 dates have BETA3=0 (Nelson-Siegel
    only); the zero-yield helper handles both forms.
    """
    path = fetch_gsw_csv(force_refresh=force_refresh)
    df = pd.read_csv(path, skiprows=GSW_HEADER_ROWS, parse_dates=["Date"])
    df = df.rename(columns={"Date": "date"}).set_index("date").sort_index()
    keep = ["BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2"]
    df = df[keep].copy()
    df["TAU2"] = df["TAU2"].replace(GSW_TAU2_SENTINEL, np.nan)
    for col in keep:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Svensson zero yield
# ---------------------------------------------------------------------------
def svensson_zero_yield(
    tau_years: float,
    beta0: float,
    beta1: float,
    beta2: float,
    beta3: float,
    tau1: float,
    tau2: float,
) -> float:
    """Continuously compounded zero-coupon yield (in percent).

    y(τ) = β₀ + β₁·g₁(τ/τ₁) + β₂·g₂(τ/τ₁) + β₃·g₂(τ/τ₂)
    g₁(x) = (1 − e^−x)/x
    g₂(x) = g₁(x) − e^−x

    Returns NaN if required params are missing or τ ≤ 0. Pre-1980 dates
    that have β₃=0 / τ₂=NaN collapse to Nelson-Siegel cleanly.
    """
    if tau_years <= 0 or pd.isna(beta0) or pd.isna(beta1) or pd.isna(beta2) \
            or pd.isna(tau1) or tau1 <= 0:
        return float("nan")

    x1 = tau_years / tau1
    e_x1 = np.exp(-x1)
    g1_x1 = (1.0 - e_x1) / x1
    g2_x1 = g1_x1 - e_x1

    has_svensson = (not pd.isna(beta3)) and beta3 != 0.0 \
        and (not pd.isna(tau2)) and tau2 > 0.0
    if not has_svensson:
        return beta0 + beta1 * g1_x1 + beta2 * g2_x1

    x2 = tau_years / tau2
    e_x2 = np.exp(-x2)
    g2_x2 = (1.0 - e_x2) / x2 - e_x2
    return beta0 + beta1 * g1_x1 + beta2 * g2_x1 + beta3 * g2_x2


# ---------------------------------------------------------------------------
# Daily forward 3m at 18m
# ---------------------------------------------------------------------------
def compute_forward_3m_18m_ahead(gsw_params: pd.DataFrame) -> pd.Series:
    """For each row of ``gsw_params`` produce the implied 3-month forward
    rate beginning 18 months ahead (continuously compounded, percent).

    f(1.5, 0.25) = [y(1.75)·1.75 − y(1.5)·1.5] / 0.25
    """
    fwd_values: list[tuple[pd.Timestamp, float]] = []
    for date, row in gsw_params.iterrows():
        y_18m = svensson_zero_yield(
            _T_FORWARD,
            row["BETA0"], row["BETA1"], row["BETA2"], row["BETA3"],
            row["TAU1"], row["TAU2"],
        )
        y_21m = svensson_zero_yield(
            _T_FORWARD + _M_FORWARD,
            row["BETA0"], row["BETA1"], row["BETA2"], row["BETA3"],
            row["TAU1"], row["TAU2"],
        )
        if not (np.isfinite(y_18m) and np.isfinite(y_21m)):
            continue
        fwd = ((_T_FORWARD + _M_FORWARD) * y_21m - _T_FORWARD * y_18m) / _M_FORWARD
        fwd_values.append((date, fwd))

    s = pd.Series(
        {ts: v for ts, v in fwd_values},
        name="FWD_3M_18M",
        dtype=float,
    )
    s.index = pd.DatetimeIndex(s.index, name="date")
    return s.sort_index()


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------
def _ntfs_meta_extra() -> dict:
    return {
        "reference": (
            "Engstrom & Sharpe (2018, 2019, 2022) "
            "'Don't Fear the Yield Curve'."
        ),
        "definition": "f_t(18m, 3m) - y_t(3m)",
        "non_vintage_perfect": True,
        "challenger_to": "T10Y3M",
    }


def _common_cache_paths(stem: str) -> tuple[Path, Path]:
    return (DATA_CACHE / f"{stem}.parquet", DATA_CACHE / f"{stem}.meta.json")


def load_ntfs_official_replication(
    *, force_refresh: bool = False,
) -> tuple[pd.Series, IndicatorMetadata]:
    """Monthly NTFS for backtest / CRPS re-estimation.

    Spot 3-month leg: TB3MS (FRED monthly avg secondary-market T-Bill
    rate). Forward leg: monthly mean of the daily GSW-derived
    f(1.5, 0.25) series.
    """
    stem = "fed_NTFS_OFFICIAL_REPL"
    parquet_path, _ = _common_cache_paths(stem)
    if parquet_path.exists() and not force_refresh:
        cached = read_cache_validated(stem, DATA_CACHE)
        if cached is not None:
            df, cmeta = cached
            s = df.iloc[:, 0]
            s.name = "NTFS_OFFICIAL_REPL"
            return s, _build_meta_from_cache("NTFS_OFFICIAL_REPL", cmeta)

    gsw = load_gsw_params(force_refresh=False)
    fwd_daily = compute_forward_3m_18m_ahead(gsw)
    # Monthly mean, MS-aligned (FRED's TB3MS is also MS-aligned).
    fwd_monthly = fwd_daily.resample("MS").mean()
    fwd_monthly.name = "FWD_3M_18M_MONTHLY"

    tb3ms, _ = load_fred_series("TB3MS")
    # tb3ms is on a business-day master index after preprocessing;
    # resample back to MS so it can subtract from fwd_monthly cleanly.
    tb3ms_monthly = tb3ms.resample("MS").mean()

    df = pd.concat(
        [fwd_monthly.rename("fwd"), tb3ms_monthly.rename("tb3ms")], axis=1
    ).dropna()
    series = (df["fwd"] - df["tb3ms"]).rename("NTFS_OFFICIAL_REPL").sort_index()

    extra = {
        **_ntfs_meta_extra(),
        "spot_3m_source": "TB3MS",
        "use_for": ["crps_estimation", "walk_forward_backtest"],
        "do_not_use_for": ["intraday_alerting"],
        "n_obs": int(series.notna().sum()),
    }
    meta = IndicatorMetadata(
        indicator_id="NTFS_OFFICIAL_REPL",
        source="FED_BOARD_GSW + FRED_TB3MS",
        frequency="M",
        first_obs=series.index.min(),
        last_obs=series.index.max(),
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=False,
        unit="pct",
        release_lag_days=1,
        description=(
            "Engstrom-Sharpe Near-Term Forward Spread (monthly, official "
            "replication; spot leg = TB3MS). Backtest variant — see "
            "NTFS_DAILY_DASHBOARD for live monitoring."
        ),
        expected_min=-3.0,
        expected_max=3.0,
        extra=extra,
    )

    write_cache_atomic(stem, series.to_frame("NTFS_OFFICIAL_REPL"),
                       meta.to_dict(), DATA_CACHE, pipeline_processed=True)
    return series, meta


def load_ntfs_daily_dashboard(
    *, force_refresh: bool = False,
) -> tuple[pd.Series, IndicatorMetadata]:
    """Daily NTFS for dashboard / current monitoring.

    Spot 3-month leg: DTB3 (FRED daily T-Bill secondary-market rate).
    Forward leg: daily GSW f(1.5, 0.25). NOT for backtest — use
    ``NTFS_OFFICIAL_REPL`` (monthly) instead.
    """
    stem = "fed_NTFS_DAILY_DASHBOARD"
    parquet_path, _ = _common_cache_paths(stem)
    if parquet_path.exists() and not force_refresh:
        cached = read_cache_validated(stem, DATA_CACHE)
        if cached is not None:
            df, cmeta = cached
            s = df.iloc[:, 0]
            s.name = "NTFS_DAILY_DASHBOARD"
            return s, _build_meta_from_cache("NTFS_DAILY_DASHBOARD", cmeta)

    gsw = load_gsw_params(force_refresh=False)
    fwd_daily = compute_forward_3m_18m_ahead(gsw)

    dtb3, _ = load_fred_series("DTB3")
    df = pd.concat([fwd_daily.rename("fwd"), dtb3.rename("dtb3")], axis=1).dropna()
    series = (df["fwd"] - df["dtb3"]).rename("NTFS_DAILY_DASHBOARD").sort_index()

    extra = {
        **_ntfs_meta_extra(),
        "spot_3m_source": "DTB3",
        "use_for": ["current_monitoring", "dashboard_display"],
        "do_not_use_for": ["crps_backtest"],
        "n_obs": int(series.notna().sum()),
    }
    meta = IndicatorMetadata(
        indicator_id="NTFS_DAILY_DASHBOARD",
        source="FED_BOARD_GSW + FRED_DTB3",
        frequency="D",
        first_obs=series.index.min(),
        last_obs=series.index.max(),
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=False,
        unit="pct",
        release_lag_days=1,
        description=(
            "Engstrom-Sharpe Near-Term Forward Spread (daily, dashboard "
            "variant; spot leg = DTB3). NOT for backtest — use "
            "NTFS_OFFICIAL_REPL (monthly)."
        ),
        expected_min=-3.0,
        expected_max=3.0,
        extra=extra,
    )

    write_cache_atomic(stem, series.to_frame("NTFS_DAILY_DASHBOARD"),
                       meta.to_dict(), DATA_CACHE, pipeline_processed=True)
    return series, meta


def _build_meta_from_cache(indicator_id: str, cmeta: dict) -> IndicatorMetadata:
    """Reconstruct IndicatorMetadata from cached meta dict."""
    return IndicatorMetadata(
        indicator_id=indicator_id,
        source=cmeta.get("source", ""),
        frequency=cmeta.get("frequency", "D"),
        first_obs=pd.Timestamp(cmeta["first_obs"]) if cmeta.get("first_obs") else pd.NaT,
        last_obs=pd.Timestamp(cmeta["last_obs"]) if cmeta.get("last_obs") else pd.NaT,
        last_update=pd.Timestamp(cmeta["last_update"]) if cmeta.get("last_update") else pd.NaT,
        needs_vintage=bool(cmeta.get("needs_vintage", False)),
        unit=cmeta.get("unit", "pct"),
        release_lag_days=int(cmeta.get("release_lag_days", 0)),
        description=cmeta.get("description", ""),
        expected_min=cmeta.get("expected_min"),
        expected_max=cmeta.get("expected_max"),
        extra={k: v for k, v in cmeta.items() if k not in {
            "indicator_id", "source", "frequency", "first_obs", "last_obs",
            "last_update", "needs_vintage", "unit", "release_lag_days",
            "description", "expected_min", "expected_max",
            "data_quality_suspect_periods",
        }},
    )


class NtfsLoader(Loader):
    def load(self) -> tuple[pd.DataFrame, dict[str, IndicatorMetadata]]:
        s_repl, m_repl = load_ntfs_official_replication()
        s_dash, m_dash = load_ntfs_daily_dashboard()
        df = pd.concat([s_repl, s_dash], axis=1)
        return df, {
            m_repl.indicator_id: m_repl,
            m_dash.indicator_id: m_dash,
        }


if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    s_repl, m_repl = load_ntfs_official_replication()
    s_dash, m_dash = load_ntfs_daily_dashboard()
    print(f"NTFS_OFFICIAL_REPL: {len(s_repl)} obs "
          f"{s_repl.index.min().date()} -> {s_repl.index.max().date()} "
          f"latest={s_repl.iloc[-1]:.3f}%")
    print(f"NTFS_DAILY_DASHBOARD: {len(s_dash)} obs "
          f"{s_dash.index.min().date()} -> {s_dash.index.max().date()} "
          f"latest={s_dash.iloc[-1]:.3f}%")
