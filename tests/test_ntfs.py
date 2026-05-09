"""Tests for src.loaders.ntfs (Layer 1.5C.1)."""
from __future__ import annotations

import pandas as pd
import pytest

from src.loaders.ntfs import (
    GSW_LOCAL_PATH,
    compute_forward_3m_18m_ahead,
    load_gsw_params,
    load_ntfs_daily_dashboard,
    load_ntfs_official_replication,
    svensson_zero_yield,
)


def _gsw_available() -> bool:
    return GSW_LOCAL_PATH.exists()


# ---------------------------------------------------------------------------
# Svensson math
# ---------------------------------------------------------------------------
def test_svensson_handles_nelson_siegel_only():
    """β3=0 / τ2=NaN means Nelson-Siegel only — must not raise."""
    y = svensson_zero_yield(
        tau_years=2.0, beta0=4.0, beta1=-1.0, beta2=0.5,
        beta3=0.0, tau1=1.0, tau2=float("nan"),
    )
    assert pd.notna(y)


def test_svensson_returns_nan_for_nonpositive_tau():
    y = svensson_zero_yield(
        tau_years=0.0, beta0=4.0, beta1=-1.0, beta2=0.5,
        beta3=0.0, tau1=1.0, tau2=float("nan"),
    )
    assert pd.isna(y)


def test_svensson_long_maturity_approaches_beta0():
    """As τ→∞ all decay terms vanish; y → β0."""
    b0 = 4.0
    y = svensson_zero_yield(
        tau_years=100.0, beta0=b0, beta1=-2.0, beta2=1.0,
        beta3=0.0, tau1=1.0, tau2=float("nan"),
    )
    assert abs(y - b0) < 0.05


# ---------------------------------------------------------------------------
# Daily forward
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _gsw_available(), reason="GSW CSV not staged")
def test_gsw_load_has_required_cols():
    df = load_gsw_params()
    for c in ["BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2"]:
        assert c in df.columns


@pytest.mark.skipif(not _gsw_available(), reason="GSW CSV not staged")
def test_gsw_tau2_sentinel_replaced_with_nan():
    df = load_gsw_params()
    # No TAU2 should equal -999.99 after the sentinel replacement.
    assert (df["TAU2"] == -999.99).sum() == 0


# ---------------------------------------------------------------------------
# Engstrom-Sharpe regime check (negative pre-recession)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _gsw_available(), reason="GSW CSV not staged")
def test_ntfs_official_repl_negative_before_2008_recession():
    """E-S "Don't Fear the Yield Curve" thesis: NTFS turns negative
    ~12 months before recession peak. We require at least one of
    {2007-01, 2007-07, 2008-01} to print negative."""
    s, _ = load_ntfs_official_replication()
    pre = [s.loc[d] for d in ["2007-01-01", "2007-07-01", "2008-01-01"]
           if pd.Timestamp(d) in s.index]
    assert any(v < 0 for v in pre), f"Expected negative pre-2008 NTFS, got {pre}"


@pytest.mark.skipif(not _gsw_available(), reason="GSW CSV not staged")
def test_ntfs_official_repl_negative_in_2019_inversion():
    """2019 yield curve inversion: NTFS turned negative in mid-2019."""
    s, _ = load_ntfs_official_replication()
    period = s.loc["2019-06-01":"2020-02-01"]
    assert (period < 0).any(), "Expected at least one negative NTFS in 2019-2020"


# ---------------------------------------------------------------------------
# Indicator metadata + frequency contract
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _gsw_available(), reason="GSW CSV not staged")
def test_ntfs_official_repl_is_monthly():
    _, m = load_ntfs_official_replication()
    assert m.frequency == "M"
    assert "TB3MS" in m.source


@pytest.mark.skipif(not _gsw_available(), reason="GSW CSV not staged")
def test_ntfs_daily_dashboard_is_daily():
    _, m = load_ntfs_daily_dashboard()
    assert m.frequency == "D"
    assert "DTB3" in m.source


@pytest.mark.skipif(not _gsw_available(), reason="GSW CSV not staged")
def test_ntfs_dashboard_blocked_from_backtest():
    """C.1 contract: NTFS_DAILY_DASHBOARD must NOT be approved for crps_backtest."""
    _, m = load_ntfs_daily_dashboard()
    assert "crps_backtest" in m.extra["do_not_use_for"]


@pytest.mark.skipif(not _gsw_available(), reason="GSW CSV not staged")
def test_ntfs_official_repl_approved_for_backtest():
    _, m = load_ntfs_official_replication()
    assert "walk_forward_backtest" in m.extra["use_for"]


@pytest.mark.skipif(not _gsw_available(), reason="GSW CSV not staged")
def test_ntfs_marked_non_vintage_perfect():
    _, m = load_ntfs_daily_dashboard()
    assert m.extra["non_vintage_perfect"] is True
