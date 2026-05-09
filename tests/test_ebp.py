"""Tests for src.loaders.ebp (Layer 1.5C.2)."""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.loaders.ebp import EBP_LOCAL_PATH, load_ebp


def _ebp_available() -> bool:
    return EBP_LOCAL_PATH.exists()


@pytest.mark.skipif(not _ebp_available(), reason="EBP CSV not staged")
def test_ebp_loads_monthly_series():
    s, m = load_ebp()
    assert m.indicator_id == "EBP"
    assert m.frequency == "M"
    assert m.unit == "pct"
    assert s.notna().sum() > 200  # > 200 months since 1973


@pytest.mark.skipif(not _ebp_available(), reason="EBP CSV not staged")
def test_ebp_metadata_carries_academic_reference():
    _, m = load_ebp()
    assert m.extra["academic_standard"] is True
    assert "Gilchrist" in m.extra["reference"]


@pytest.mark.skipif(not _ebp_available(), reason="EBP CSV not staged")
def test_ebp_release_lag_about_one_month():
    _, m = load_ebp()
    # FEDS Notes companion file lags ~30 days.
    assert 14 <= m.release_lag_days <= 60


@pytest.mark.skipif(not _ebp_available(), reason="EBP CSV not staged")
def test_ebp_elevated_at_2008_lehman_window():
    """2008-09 / 2008-10: EBP should be > 1 standard deviation above mean
    (at least). Concretely the 2008-09 value is +1.7-ish and ~3 sigma."""
    s, _ = load_ebp()
    sigma = s.std()
    mean = s.mean()
    val = s.loc["2008-09-01"] if pd.Timestamp("2008-09-01") in s.index else s.asof("2008-09-01")
    assert val > mean + sigma


@pytest.mark.skipif(not _ebp_available(), reason="EBP CSV not staged")
def test_ebp_elevated_at_covid_window():
    """March-April 2020 should be elevated relative to the post-1990 mean."""
    s, _ = load_ebp()
    sub = s.loc["2020-03-01":"2020-05-01"]
    assert (sub > 1.0).any(), f"Expected elevated EBP in early 2020, saw {sub.tolist()}"
