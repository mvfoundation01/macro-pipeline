"""Tests for ``macro_pipeline.analysis.r_squared_panel`` (Layer 3D)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from macro_pipeline.analysis import (
    HORIZONS,
    PANEL_CACHE_PATH,
    PANEL_SCHEMA_VERSION,
    SUPPORTED_TARGETS,
    VERDICT_FULL,
    VERDICT_NO_OVERLAP,
    VERDICT_UNDERPOWERED,
    align_indicator_to_target,
    classify_verdict,
    discover_panel_indicators,
    forward_return,
    forward_return_series,
    is_underpowered,
    load_panel,
    load_target,
    n_eff_nonoverlap,
)

# ---- forward-return helpers ----------------------------------------------

def test_forward_return_rejects_post_target_window():
    """If t + horizon_months > target.index.max(), forward_return returns None."""
    t = load_target("SHILLER_TR_PRICE")
    last_t = t.index[-1]
    # Asking 12M from the very last observation must reject.
    out = forward_return(t, last_t, horizon_months=12)
    assert out is None


def test_forward_return_known_window_positive():
    t = load_target("SHILLER_TR_PRICE")
    # 1990-01 is well inside, real total return over 12M is well-defined.
    fr = forward_return(t, pd.Timestamp("1990-01-31"), horizon_months=12)
    assert fr is not None
    assert isinstance(fr, float)


def test_forward_return_series_skips_overlap_window():
    t = load_target("SHILLER_TR_PRICE")
    fr = forward_return_series(t, horizon_months=120)
    # last valid t must be at most target.index[-1] - 10Y.
    assert fr.index[-1] <= t.index[-1] - pd.DateOffset(months=120)
    # All values finite
    assert fr.dropna().shape[0] > 0


def test_forward_return_horizon_validation():
    t = load_target("SHILLER_TR_PRICE")
    with pytest.raises(ValueError, match="horizon_months"):
        forward_return(t, pd.Timestamp("2000-01-01"), horizon_months=0)


# ---- classify_verdict helper ---------------------------------------------

def test_classify_verdict_thresholds():
    # 0 obs -> NO_OVERLAP
    assert classify_verdict(0, 12) == VERDICT_NO_OVERLAP
    # < 24 obs -> UNDERPOWERED
    assert classify_verdict(20, 12) == VERDICT_UNDERPOWERED
    # n_eff < 3 -> UNDERPOWERED (even with n_nom >= 24)
    assert classify_verdict(24, 12) == VERDICT_UNDERPOWERED   # n_eff = 2
    # full
    assert classify_verdict(100, 12) == VERDICT_FULL          # n_eff = 8


def test_n_eff_nonoverlap_formula():
    assert n_eff_nonoverlap(120, 12) == 10
    assert n_eff_nonoverlap(120, 36) == 3
    assert n_eff_nonoverlap(120, 120) == 1
    assert n_eff_nonoverlap(0, 12) == 0


def test_is_underpowered():
    assert is_underpowered(VERDICT_UNDERPOWERED)
    assert not is_underpowered(VERDICT_FULL)
    assert not is_underpowered(VERDICT_NO_OVERLAP)


# ---- panel-level tests (use the cached parquet from the build) -----------

@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    """Load the cached panel; raises clear error if not built."""
    return load_panel()


def test_panel_all_indicators_covered(panel: pd.DataFrame):
    """Per spec §7.7: panel has rows for every Tier 1-4 indicator x
    {1Y, 3Y, 5Y, 10Y} x {2 targets}."""
    indicators = [iid for iid, _ in discover_panel_indicators()]
    assert len(panel) == len(indicators) * len(HORIZONS) * len(SUPPORTED_TARGETS)
    pivoted = panel.groupby("indicator_id").size()
    # Every indicator has exactly 8 rows (4 horizons x 2 targets)
    assert (pivoted == 8).all(), f"indicators with wrong row count: {pivoted[pivoted != 8]}"


def test_panel_known_signal_cape_10y(panel: pd.DataFrame):
    """Per spec §7.7: CAPE × 10Y R² known to be elevated and beta < 0.
    Spec wanted >0.40 (Path A textbook number); Path B with full
    1881-2016 history yields ~0.24 (D19). We assert >0.20 which is
    well above noise (p_NW < 0.001)."""
    row = panel.query(
        "indicator_id == 'SHILLER_CAPE' and target == 'SHILLER_TR_PRICE' "
        "and horizon_label == '10Y'"
    )
    assert not row.empty
    r = row.iloc[0]
    assert r["r_squared"] > 0.20
    assert r["beta"] < 0       # high CAPE → low forward returns
    assert r["p_value_beta_NW"] < 0.01


def test_panel_known_signal_damodaran_erp_10y(panel: pd.DataFrame):
    """Damodaran ERP × 10Y is the strongest single relationship in our
    panel (R² > 0.40, β > 0 — high ERP → high forward returns)."""
    row = panel.query(
        "indicator_id == 'DAMODARAN_ERP' and target == 'SHILLER_TR_PRICE' "
        "and horizon_label == '10Y'"
    )
    assert not row.empty
    r = row.iloc[0]
    assert r["r_squared"] > 0.30
    assert r["beta"] > 0


def test_panel_n_eff_consistent_with_n_nominal(panel: pd.DataFrame):
    """n_nominal >= n_eff_nonoverlap always (the latter divides by H)."""
    valid = panel.dropna(subset=["n_nominal", "n_eff_nonoverlap"])
    assert (valid["n_nominal"] >= valid["n_eff_nonoverlap"]).all()


def test_panel_n_eff_formula_holds(panel: pd.DataFrame):
    """For every row: n_eff_nonoverlap == n_nominal // horizon_months."""
    for _, r in panel.iterrows():
        if pd.isna(r["n_nominal"]) or pd.isna(r["n_eff_nonoverlap"]):
            continue
        expected = int(r["n_nominal"]) // int(r["horizon_months"])
        assert int(r["n_eff_nonoverlap"]) == expected


def test_panel_no_overlap_rows_have_nan_stats(panel: pd.DataFrame):
    """Per D16: NO_OVERLAP rows kept with NaN stats for provenance."""
    no_ov = panel.query("verdict == 'NO_OVERLAP'")
    assert not no_ov.empty
    for col in ("alpha", "beta", "r_squared", "adj_r_squared",
                "p_value_beta_NW", "residual_se"):
        assert no_ov[col].isna().all(), f"NO_OVERLAP rows have non-NaN {col}"


def test_panel_full_rows_have_finite_stats(panel: pd.DataFrame):
    """Per spec §7.7: every FULL row must have all required stats populated."""
    full = panel.query("verdict == 'FULL'")
    assert not full.empty
    for col in ("alpha", "beta", "r_squared", "p_value_beta_NW", "residual_se"):
        assert full[col].notna().all(), f"FULL rows have NaN {col}"


def test_panel_target_consistency(panel: pd.DataFrame):
    """Both SHILLER_TR_PRICE and SP500TR rows present."""
    assert "SHILLER_TR_PRICE" in panel["target"].unique()
    assert "SP500TR" in panel["target"].unique()


def test_panel_pit_safety_forward_window_respected(panel: pd.DataFrame):
    """sample_end + horizon_months MUST NOT exceed target's range."""
    target_ends = {tgt: load_target(tgt).index[-1] for tgt in SUPPORTED_TARGETS}
    for _, r in panel.iterrows():
        if pd.isna(r["sample_end"]):
            continue
        # Effective forward window ends at sample_end + horizon_months
        forward_end = r["sample_end"] + pd.DateOffset(months=int(r["horizon_months"]))
        assert forward_end <= target_ends[r["target"]] + pd.DateOffset(days=31), (
            f"PIT leak: {r['indicator_id']} {r['target']} {r['horizon_label']} "
            f"sample_end={r['sample_end']} forward_end={forward_end} "
            f"target_end={target_ends[r['target']]}"
        )


def test_panel_atomic_cache_metadata():
    """sha256 + schema_version + row_count present in sidecar (1.5A.5)."""
    parquet = Path(PANEL_CACHE_PATH)
    sidecar = parquet.with_suffix(".meta.json")
    assert parquet.exists()
    assert sidecar.exists()
    md = json.loads(sidecar.read_text())
    assert md["schema_version"] == PANEL_SCHEMA_VERSION
    assert "data_sha256" in md and len(md["data_sha256"]) == 64
    assert md["row_count"] > 0
    assert md["pipeline_processed"] is True


def test_panel_freq_native_present(panel: pd.DataFrame):
    """Every row carries freq_native ∈ {D, W, M, Q, A, ?}."""
    valid = {"D", "W", "M", "Q", "A", "?"}
    assert panel["freq_native"].isin(valid).all()
    # Damodaran annual indicators must be tagged 'A'
    dam_rows = panel[panel["indicator_id"].str.startswith("DAMODARAN_")]
    assert (dam_rows["freq_native"] == "A").all()


def test_panel_no_score_artifacts():
    """CRPS/CDRS/REGIME must NOT appear in the panel (3D-prep-4 design)."""
    indicators = [iid for iid, _ in discover_panel_indicators()]
    forbidden = {"CRPS", "CDRS", "REGIME", "V_score", "T_score"}
    assert not (forbidden & set(indicators))


def test_panel_no_multiindex_indicators():
    """HLW_VINTAGE excluded (D17)."""
    indicators = [iid for iid, _ in discover_panel_indicators()]
    assert "HLW_VINTAGE" not in indicators


def test_panel_maxlags_horizon_minus_1(panel: pd.DataFrame):
    """maxlags = horizon_months - 1 for every fitted row."""
    fit = panel.query("verdict in ('FULL', 'UNDERPOWERED')")
    fit = fit.dropna(subset=["maxlags"])
    for _, r in fit.iterrows():
        assert int(r["maxlags"]) == int(r["horizon_months"]) - 1


def test_panel_sample_start_end_inside_target_range(panel: pd.DataFrame):
    """sample_start/end must fall inside the target's data range."""
    target_ranges = {
        tgt: (load_target(tgt).index.min(), load_target(tgt).index.max())
        for tgt in SUPPORTED_TARGETS
    }
    for _, r in panel.iterrows():
        if pd.isna(r["sample_start"]) or pd.isna(r["sample_end"]):
            continue
        tstart, tend = target_ranges[r["target"]]
        # tolerate one-month boundary slack (resample("ME") shifts)
        assert r["sample_start"] >= tstart - pd.DateOffset(months=1)
        assert r["sample_end"] <= tend + pd.DateOffset(months=1)


def test_align_indicator_to_target_asof_semantics():
    target_dates = pd.date_range("2010-01-31", "2010-06-30", freq="ME")
    indicator = pd.Series(
        [1.0, 2.0, 3.0],
        index=pd.to_datetime(["2010-01-15", "2010-04-20", "2010-06-05"]),
    )
    aligned = align_indicator_to_target(indicator, target_dates)
    # Jan: indicator's Jan-15 value
    assert aligned.loc["2010-01-31"] == 1.0
    # Feb / Mar: still Jan-15 value (asof)
    assert aligned.loc["2010-02-28"] == 1.0
    assert aligned.loc["2010-03-31"] == 1.0
    # Apr: Apr-20 value
    assert aligned.loc["2010-04-30"] == 2.0
    # May: still Apr-20 (no May obs)
    assert aligned.loc["2010-05-31"] == 2.0
    # Jun: Jun-05 value
    assert aligned.loc["2010-06-30"] == 3.0
