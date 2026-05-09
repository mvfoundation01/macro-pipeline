"""Phase 4A official-source loader tests.

Covers NAAIM, FINRA Margin, NY Fed Recession Probability + NBER label,
and Damodaran Implied ERP. All read from local files (no network).
"""
from __future__ import annotations

import os

import pandas as pd
import pytest
from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("FRED_API_KEY"):
    pytest.skip(
        "FRED_API_KEY not set (required for src.config import)",
        allow_module_level=True,
    )

from src.loaders.damodaran_erp import load_damodaran_erp
from src.loaders.finra_margin import load_finra_margin
from src.loaders.naaim import load_naaim
from src.loaders.nyfed_recprob import load_nyfed_recprob
from src.validation import validate_gate4a


# ---------------------------------------------------------------------------
# NAAIM
# ---------------------------------------------------------------------------
def test_naaim_loads_returns_series():
    s, meta = load_naaim()
    assert isinstance(s, pd.Series)
    assert meta.indicator_id == "NAAIM_NUMBER"
    assert meta.source == "NAAIM_XLSX"
    assert meta.unit == "pct_exposure"
    assert meta.frequency == "W"
    assert not s.dropna().empty


def test_naaim_dates_are_ascending_after_load():
    """Source is newest-first; loader must sort ascending."""
    s, _ = load_naaim()
    assert s.index.is_monotonic_increasing
    assert s.index.is_unique


def test_naaim_in_pct_exposure_range():
    s, _ = load_naaim()
    obs = s.dropna()
    # NAAIM allows leveraged long up to ~200, leveraged short to ~-200.
    assert -200 <= obs.min() <= obs.max() <= 250


def test_naaim_history_starts_2006():
    s, meta = load_naaim()
    assert meta.first_obs >= pd.Timestamp("2006-01-01")
    assert meta.first_obs <= pd.Timestamp("2007-12-31")


# ---------------------------------------------------------------------------
# FINRA Margin
# ---------------------------------------------------------------------------
def test_finra_loads_returns_series():
    s, meta = load_finra_margin()
    assert meta.indicator_id == "FINRA_MARGIN_DEBT"
    assert meta.source == "FINRA_XLSX"
    assert meta.unit == "M_USD"
    assert not s.dropna().empty


def test_finra_reverse_order_corrected():
    """Source is newest-first; loader must produce ascending index.

    First obs should be ~1997 (oldest), last obs in or after 2025.
    """
    s, meta = load_finra_margin()
    assert s.index.is_monotonic_increasing
    assert meta.first_obs.year <= 1998, (
        f"FINRA first_obs={meta.first_obs.date()} suggests reverse not applied"
    )
    assert meta.last_obs.year >= 2025
    assert meta.extra.get("source_order") == "newest_first_reversed_on_load"


def test_finra_margin_debt_in_plausible_range():
    s, _ = load_finra_margin()
    obs = s.dropna()
    # 1997-era was ~$120B = 120,000 million; 2026 is ~$1.2T = 1.2M million.
    assert 5e4 <= obs.min() <= obs.max() <= 2e6


def test_finra_metadata_release_lag():
    _, meta = load_finra_margin()
    # FINRA releases mid-following-month (~3rd week).
    assert 7 <= meta.release_lag_days <= 35


# ---------------------------------------------------------------------------
# NY Fed Recession Probability + NBER label
# ---------------------------------------------------------------------------
def test_nyfed_returns_two_series():
    series, meta = load_nyfed_recprob()
    assert set(series.keys()) == {"NYFED_REC_PROB", "NBER_REC_LABEL"}
    assert set(meta.keys()) == {"NYFED_REC_PROB", "NBER_REC_LABEL"}


def test_nyfed_rec_prob_is_share_in_unit_interval():
    series, _ = load_nyfed_recprob()
    s = series["NYFED_REC_PROB"].dropna()
    assert s.min() >= 0.0
    assert s.max() <= 1.01


def test_nber_label_is_binary():
    series, _ = load_nyfed_recprob()
    s = series["NBER_REC_LABEL"].dropna()
    unique = set(s.unique())
    assert unique <= {0.0, 1.0}, f"NBER label has non-binary values: {unique}"


def test_nber_label_role_is_backtest_label():
    """NBER_REC_LABEL must be tagged as the backtest training target."""
    _, meta = load_nyfed_recprob()
    assert meta["NBER_REC_LABEL"].extra.get("role") == "backtest_label"


def test_nber_recession_count_matches_history():
    """1959-2024 sample: 9 NBER recessions per Build guide §21.2."""
    series, _ = load_nyfed_recprob()
    s = series["NBER_REC_LABEL"].dropna().loc["1959-01-01":"2024-12-31"]
    n_transitions = int((s.diff() == 1).sum())
    assert 8 <= n_transitions <= 10, (
        f"got {n_transitions} 0->1 transitions; "
        "Build guide §21.2 lists 9 (2020 sometimes excluded)"
    )


def test_nber_label_post_determination_is_nan():
    """Beyond the last NBER determination, the label must be NaN, not ffilled."""
    series, meta = load_nyfed_recprob()
    last_known = pd.Timestamp(meta["NBER_REC_LABEL"].extra["last_known_label_date"])
    s = series["NBER_REC_LABEL"]
    after = s.loc[s.index > last_known]
    assert after.isna().all(), (
        f"{(~after.isna()).sum()} obs after last_known={last_known.date()} "
        "should be NaN but were ffilled"
    )


# ---------------------------------------------------------------------------
# Damodaran ERP
# ---------------------------------------------------------------------------
def test_damodaran_returns_four_series():
    series, meta = load_damodaran_erp()
    expected = {"DAMODARAN_ERP", "DAMODARAN_EY", "DAMODARAN_DY", "DAMODARAN_TBOND"}
    assert set(series.keys()) == expected
    assert set(meta.keys()) == expected


def test_damodaran_latest_year_is_2025():
    _, meta = load_damodaran_erp()
    assert meta["DAMODARAN_ERP"].extra.get("last_year_in_data") == 2025
    # All four series share the same source file -> same last year
    for sid in meta:
        assert meta[sid].extra.get("last_year_in_data") == 2025


def test_damodaran_erp_in_plausible_range():
    series, _ = load_damodaran_erp()
    obs = series["DAMODARAN_ERP"].dropna()
    # Implied ERP historically [1.5%, 7%] with extremes around 2008
    assert 1.0 <= obs.min() <= obs.max() <= 10.0


def test_damodaran_history_starts_at_first_business_day_after_source():
    """Source dates are year-end (e.g. 1960-12-31, often a weekend). After
    business-day alignment the value first appears on the next business day,
    so:
      * EY: source 1960-12-31 -> visible from 1961-01-02 (year 1961)
      * ERP: source 1961-12-31 (first non-NaN) -> visible from 1962-01-02
    """
    series, _ = load_damodaran_erp()
    erp = series["DAMODARAN_ERP"].dropna()
    ey = series["DAMODARAN_EY"].dropna()
    assert erp.index.min().year == 1962
    assert ey.index.min().year == 1961


# ---------------------------------------------------------------------------
# Cache + Gate 4A
# ---------------------------------------------------------------------------
def test_cache_files_use_official_prefix():
    """Each Phase 4A series caches as data/cache/official_<id>.parquet."""
    from src.config import DATA_CACHE
    load_naaim()
    load_finra_margin()
    load_nyfed_recprob()
    load_damodaran_erp()
    expected = [
        "official_NAAIM_NUMBER", "official_FINRA_MARGIN_DEBT",
        "official_NYFED_REC_PROB", "official_NBER_REC_LABEL",
        "official_DAMODARAN_ERP", "official_DAMODARAN_EY",
        "official_DAMODARAN_DY", "official_DAMODARAN_TBOND",
    ]
    for stem in expected:
        assert (DATA_CACHE / f"{stem}.parquet").exists(), f"missing {stem}.parquet"


def test_cached_parquet_columns_are_bare_indicator_ids():
    """File names carry the official_ prefix; parquet columns are bare ids."""
    from src.config import DATA_CACHE
    load_naaim()
    df = pd.read_parquet(DATA_CACHE / "official_NAAIM_NUMBER.parquet")
    assert df.columns.tolist() == ["NAAIM_NUMBER"]


def test_gate4a_passes():
    naaim_s, naaim_m = load_naaim()
    finra_s, finra_m = load_finra_margin()
    nyfed_series, nyfed_meta = load_nyfed_recprob()
    dam_series, dam_meta = load_damodaran_erp()
    report = validate_gate4a(naaim_m, finra_m, nyfed_meta, dam_meta)
    assert report.passed, "Gate 4A must pass:\n" + report.render()
