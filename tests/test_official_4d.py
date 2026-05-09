"""Phase 4D tests: HLW vintage-aware loader (Layer 1 final)."""
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

from src.loaders.hlw_rstar import load_hlw_rstar
from src.loaders.hlw_rstar_vintage import (
    COLUMN_LAYOUTS,
    INDICATOR_GAP,
    INDICATOR_IDS,
    INDICATOR_RSTAR,
    INDICATOR_TREND,
    build_cache,
    discover_vintages,
    get_pit_rstar,
    load_hlw_vintage,
    vintage_quarter_end,
    vintage_to_publication_date,
)


# ---------------------------------------------------------------------------
# Discovery + publication-date arithmetic (offline)
# ---------------------------------------------------------------------------
def test_discover_returns_32_vintages():
    """33 sheets in the file - 1 'info' sheet = 32 vintages."""
    vintages = discover_vintages()
    assert len(vintages) == 32, f"got {len(vintages)} vintages: {vintages}"
    # All match YYYYQN pattern
    for v in vintages:
        assert len(v) == 6 and v[4] == "Q"


def test_vintage_to_publication_date_formula():
    """vintage YYYYQX is published ~14 days after the quarter ends."""
    assert vintage_to_publication_date("2015Q4") == pd.Timestamp("2016-01-14")
    assert vintage_to_publication_date("2020Q1") == pd.Timestamp("2020-04-14")
    assert vintage_to_publication_date("2024Q4") == pd.Timestamp("2025-01-14")
    assert vintage_to_publication_date("2025Q4") == pd.Timestamp("2026-01-14")


def test_vintage_quarter_end():
    assert vintage_quarter_end("2020Q1") == pd.Timestamp("2020-03-31")
    assert vintage_quarter_end("2024Q3") == pd.Timestamp("2024-09-30")
    assert vintage_quarter_end("2024Q4") == pd.Timestamp("2024-12-31")


def test_known_layouts_cover_all_three_widths():
    """Vintage file ships THREE distinct schemas: 17, 21, 26 columns."""
    assert set(COLUMN_LAYOUTS.keys()) == {17, 21, 26}
    for ncols, layout in COLUMN_LAYOUTS.items():
        assert set(layout.keys()) == set(INDICATOR_IDS)


# ---------------------------------------------------------------------------
# Vintage sheet loading
# ---------------------------------------------------------------------------
def test_load_single_vintage_returns_dataframe():
    df = load_hlw_vintage("2020Q1")
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == set(INDICATOR_IDS)
    assert df.index.name == "date"
    assert df[INDICATOR_RSTAR].dropna().shape[0] > 100


def test_load_all_vintages_returns_dict_of_32():
    all_v = load_hlw_vintage()
    assert isinstance(all_v, dict)
    assert len(all_v) == 32
    for v, df in all_v.items():
        assert set(df.columns) == set(INDICATOR_IDS)
        # Each vintage's data is truncated at its quarter end
        assert df.index.max() <= vintage_quarter_end(v)


def test_each_vintage_has_us_rstar():
    """Schema consistency: every vintage exposes US r*."""
    all_v = load_hlw_vintage()
    for v, df in all_v.items():
        s = df[INDICATOR_RSTAR].dropna()
        assert not s.empty, f"vintage {v} has no US r* values"


def test_invalid_vintage_raises():
    with pytest.raises((KeyError, ValueError)):
        load_hlw_vintage("9999Q9")
    with pytest.raises(ValueError):
        load_hlw_vintage("not-a-vintage")


# ---------------------------------------------------------------------------
# PIT lookup
# ---------------------------------------------------------------------------
def test_pit_2020_06_returns_2020q1():
    """asof=2020-06-15: 2020Q1 published 2020-04-14 (<=asof);
    2020Q2 published 2020-07-14 (>asof). Latest valid = 2020Q1."""
    pit = get_pit_rstar("2020-06-15")
    assert pit.attrs["vintage"] == "2020Q1"
    assert pit.attrs["publication_date"] == "2020-04-14T00:00:00"


def test_pit_anchors_5_dates():
    """Anchors verify look-back semantics across the 2020Q3-2022Q3 gap.

    The file has no 2020Q3/Q4 or 2021/2022Q1-Q3 vintages; for any asof
    in that window the PIT helper must surface 2020Q2 (the last
    published before the gap). 2022Q4 isn't published until 2023-01-14.
    """
    cases = {
        "2016-06-15": "2016Q1",
        "2018-12-15": "2018Q3",
        "2020-06-15": "2020Q1",
        "2022-12-15": "2020Q2",  # gap: 2020Q2 latest published before 2023-01-14
        "2024-12-15": "2024Q3",
    }
    for asof, expected in cases.items():
        pit = get_pit_rstar(asof)
        assert pit.attrs["vintage"] == expected, (
            f"asof={asof}: got {pit.attrs['vintage']}, expected {expected}"
        )


def test_pit_2023_02_returns_2022q4():
    """First post-gap vintage 2022Q4 (published 2023-01-14) becomes
    available; verify it surfaces from 2023-01-14 onwards."""
    assert get_pit_rstar("2023-02-01").attrs["vintage"] == "2022Q4"
    assert get_pit_rstar("2023-01-13").attrs["vintage"] == "2020Q2"
    assert get_pit_rstar("2023-01-14").attrs["vintage"] == "2022Q4"


def test_pit_never_returns_future_vintage():
    """For asof=2018-01-01, must NOT pick 2018Q4 (published 2019-01-14)."""
    pit = get_pit_rstar("2018-01-01")
    pub = pd.Timestamp(pit.attrs["publication_date"])
    assert pub <= pd.Timestamp("2018-01-01"), (
        f"PIT lookup returned vintage published {pub.date()} (future)"
    )


def test_pit_truncates_at_vintage_quarter_end():
    """Vintage 2020Q1 must not show data from after 2020-Q1."""
    pit = get_pit_rstar("2020-06-15")
    assert pit.attrs["vintage"] == "2020Q1"
    assert pit.index.max() <= pd.Timestamp("2020-03-31")


def test_pit_pre_2015_raises():
    """The earliest vintage in this file is 2015Q4 (published 2016-01-14).
    asof before that should raise (no vintage available)."""
    with pytest.raises(ValueError, match="No HLW vintage"):
        get_pit_rstar("2010-01-01")


def test_pit_pre_2015_no_raise_returns_none():
    pit = get_pit_rstar("2010-01-01", raise_on_no_vintage=False)
    assert pit is None


# ---------------------------------------------------------------------------
# Cross-vintage revisions
# ---------------------------------------------------------------------------
def test_vintage_revisions_visible():
    """The same observation date gets different r* estimates across vintages."""
    v_old = load_hlw_vintage("2015Q4")
    v_new = load_hlw_vintage("2025Q4")
    target_date = pd.Timestamp("2015-01-01")
    if target_date not in v_old.index or target_date not in v_new.index:
        pytest.skip("2015-Q1 not present in both vintages")
    old_val = float(v_old.loc[target_date, INDICATOR_RSTAR])
    new_val = float(v_new.loc[target_date, INDICATOR_RSTAR])
    assert old_val != new_val, (
        "expected r* for 2015-Q1 to differ between 2015Q4 and 2025Q4 vintages"
    )


def test_2025q4_vintage_matches_current_estimates_loader():
    """The 2025Q4 vintage IS the current snapshot in different packaging."""
    v_2025q4 = load_hlw_vintage("2025Q4")
    cur_series, _ = load_hlw_rstar()
    cur_rstar = cur_series["HLW_RSTAR"]
    # Compare on overlap dates (cur_rstar is on business-day index after pipeline;
    # vintage is on quarter-start dates).
    for date in v_2025q4.index[-12:]:  # last 3 years
        if date not in cur_rstar.index:
            continue
        v_val = float(v_2025q4.loc[date, INDICATOR_RSTAR])
        c_val = float(cur_rstar.loc[date])
        assert abs(v_val - c_val) < 0.001, (
            f"{date.date()}: vintage 2025Q4 r* = {v_val:.4f}, "
            f"current r* = {c_val:.4f}"
        )


# ---------------------------------------------------------------------------
# Cache + Gate 4D
# ---------------------------------------------------------------------------
def test_build_cache_writes_multiindex_parquet():
    df, meta = build_cache(force_refresh=True)
    assert isinstance(df.index, pd.MultiIndex)
    assert df.index.names == ["vintage", "date"]
    assert df.index.get_level_values("vintage").nunique() == 32
    assert set(df.columns) == set(INDICATOR_IDS)


def test_cache_metadata_records_all_publication_dates():
    _, meta = build_cache(force_refresh=False)
    pubs = meta.extra.get("vintage_publication_dates")
    assert isinstance(pubs, dict)
    assert len(pubs) == 32
    assert pubs["2020Q1"] == "2020-04-14"
    assert pubs["2025Q4"] == "2026-01-14"


def test_cache_file_exists():
    from src.config import DATA_CACHE
    parquet = DATA_CACHE / "official_HLW_VINTAGE.parquet"
    sidecar = DATA_CACHE / "official_HLW_VINTAGE.meta.json"
    build_cache(force_refresh=False)
    assert parquet.exists()
    assert sidecar.exists()


def test_gate4d_passes():
    from src.validation import validate_gate4d
    df, meta = build_cache(force_refresh=False)
    report = validate_gate4d(df, meta)
    assert report.passed, "Gate 4D must pass:\n" + report.render()


# ---------------------------------------------------------------------------
# Item A: scoring-config constants
# ---------------------------------------------------------------------------
def test_scoring_config_positioning_zscore_list():
    from src.models.scoring_config import (
        CDRS_ALERT_THRESHOLDS,
        CRPS_ALERT_THRESHOLDS,
        POSITIONING_INDICATORS_REQUIRING_ZSCORE,
        ZSCORE_WINDOW_DEFAULT_YEARS,
        requires_zscore,
    )
    # All required positioning sources must be in the list
    expected_subset = {
        "FINRA_MARGIN_DEBT", "NAAIM_NUMBER",
        "CFTC_TR_10Y_AM_NET", "CFTC_TR_10Y_LV_NET", "CFTC_TR_10Y_DEALER_NET",
    }
    assert expected_subset.issubset(set(POSITIONING_INDICATORS_REQUIRING_ZSCORE))
    assert ZSCORE_WINDOW_DEFAULT_YEARS == 3
    assert CRPS_ALERT_THRESHOLDS["high"] == 0.60
    assert CDRS_ALERT_THRESHOLDS["high"] == 0.70

    # Helper works
    assert requires_zscore("FINRA_MARGIN_DEBT") is True
    assert requires_zscore("SHILLER_CAPE") is False
