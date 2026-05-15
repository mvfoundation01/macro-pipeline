"""Layer 5b-D — tests for
``macro_pipeline.analysis.regime_conditional_validation``.

Test inventory (seven tests; NEG-flavor five of seven equals
seventy-one percent at sub-phase level — floor met):

  D.1  POS       test_l5b_d_regime_sensitivity_flag_fires_on_recession_underperformance
  D.2  POS-inv   test_l5b_d_regime_sensitivity_flag_false_on_stable_performance
  D.3  POS       test_l5b_d_classify_nber_regime_diagnostic_only_three_states
  D.4  NEG       test_l5b_d_dataclass_rejects_invalid_pre_1978_handling
  D.5  NEG       test_l5b_d_dataclass_rejects_missing_no_default_field
  D.6  NEG       test_l5b_d_dataclass_rejects_sensitivity_flag_inconsistency
  D.7  NEG-inv   test_l5b_d_empty_recession_subset_returns_valid_degenerate_diagnostics

L5b-D closes ChatGPT 5.5 Dim-3 OOS rigor regime-conditional mandate.
AP-AUTH-54 seventh-instance internal-implementation variant pattern;
envelope STAYS CLOSED at 4-instance characterization per Strategic
disposition 4 (5 within-envelope sub-characteristics documented).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from macro_pipeline.analysis.regime_conditional_validation import (
    RegimeConditionalDiagnostics,
    classify_nber_regime_diagnostic_only,
    compute_regime_conditional_oos_validation,
)


# ---------------------------------------------------------------------------
# Test D.1 — POS (L5b-D)
# ---------------------------------------------------------------------------
def test_l5b_d_regime_sensitivity_flag_fires_on_recession_underperformance():
    """L5b-D: synthetic fixture where the model performs well in
    expansion (p ≈ y) but poorly in recession (p far from y); the
    aggregator should fire ``regime_sensitivity_flag=True``.

    Construction:
    - Post-1978 dates only (avoid pre-1978 handling path).
    - 100 expansion obs: ``p == y`` exactly (Brier ≈ 0; improvement ≈
      climatology).
    - 50 recession obs: ``p = 1 - y`` (perfectly miscalibrated;
      Brier ≈ 1; improvement very negative).
    - Full sample Brier = (100×0 + 50×1) / 150 ≈ 0.333.
    - Recession Brier ≈ 1.0; recession improvement very negative;
      threshold = 0.5 × full_improvement is far higher.
    - Flag MUST fire."""
    n_exp = 100
    n_rec = 50
    n_total = n_exp + n_rec
    # Generate dates post-1978; alternate expansion / recession ranges.
    dates_exp = pd.date_range("2010-01-01", periods=n_exp, freq="MS")
    dates_rec = pd.date_range("2018-06-01", periods=n_rec, freq="MS")
    dates = dates_exp.append(dates_rec)
    # y: random binary for both regimes (mix of 0s and 1s).
    rng = np.random.default_rng(42)
    y_exp = rng.integers(0, 2, size=n_exp).astype(float)
    y_rec = rng.integers(0, 2, size=n_rec).astype(float)
    y_all = np.concatenate([y_exp, y_rec])
    # p in expansion: perfectly calibrated (p == y); recession:
    # anti-calibrated (p = 1 - y).
    p_exp = y_exp.copy()
    p_rec = 1.0 - y_rec
    p_all = np.concatenate([p_exp, p_rec])
    # Classifier: dates in 2018-06 to 2022-08 are recession.
    rec_start = pd.Timestamp("2018-06-01")
    rec_end = pd.Timestamp("2022-12-01")

    def classifier(date: pd.Timestamp) -> str:
        if rec_start <= date <= rec_end:
            return "recession"
        return "expansion"

    diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,  # L5b-F Phase 2 — required keyword-only kwarg
        ood_reserve_fraction=0.10,
    )
    assert diag.n_recession_obs == n_rec
    assert diag.n_expansion_obs == n_exp
    assert diag.n_pre_1978_obs == 0
    # Expansion: p == y → Brier ≈ 0.
    assert diag.expansion_subset_brier == pytest.approx(0.0, abs=1e-10)
    # Recession: p = 1 - y → Brier ≈ 1.0.
    assert diag.recession_subset_brier == pytest.approx(1.0, abs=1e-10)
    # Sensitivity flag MUST fire (recession improvement << full).
    assert diag.regime_sensitivity_flag is True, (
        f"expected regime_sensitivity_flag=True; got False. "
        f"full_improvement={diag.full_sample_brier_improvement}; "
        f"recession_improvement={diag.recession_brier_improvement}; "
        f"expansion_improvement={diag.expansion_brier_improvement}"
    )


# ---------------------------------------------------------------------------
# Test D.2 — POS-invariant (L5b-D)
# ---------------------------------------------------------------------------
def test_l5b_d_regime_sensitivity_flag_false_on_stable_performance():
    """L5b-D POS-invariant: synthetic fixture where the model performs
    EQUALLY across both regimes; the aggregator should NOT fire the
    sensitivity flag (`regime_sensitivity_flag=False`).

    Construction: model is perfectly calibrated (p == y) across both
    regimes. Brier = 0 in both subsets and full sample; improvements
    equal across subsets; threshold check yields False."""
    n_exp = 80
    n_rec = 60
    dates_exp = pd.date_range("2010-01-01", periods=n_exp, freq="MS")
    dates_rec = pd.date_range("2018-06-01", periods=n_rec, freq="MS")
    dates = dates_exp.append(dates_rec)
    rng = np.random.default_rng(7)
    y_all = rng.integers(0, 2, size=n_exp + n_rec).astype(float)
    # Avoid degenerate y (all 0s or all 1s) which would make
    # climatology=0 and improvement undefined.
    if y_all.sum() == 0:
        y_all[0] = 1
    elif y_all.sum() == len(y_all):
        y_all[0] = 0
    p_all = y_all.copy()  # perfect calibration

    rec_start = pd.Timestamp("2018-06-01")

    def classifier(date: pd.Timestamp) -> str:
        if date >= rec_start:
            return "recession"
        return "expansion"

    diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,  # L5b-F Phase 2 — required keyword-only kwarg
        ood_reserve_fraction=0.10,
    )
    # Stable performance: flag must be False.
    assert diag.regime_sensitivity_flag is False, (
        f"stable performance should yield flag=False; got True. "
        f"full_improvement={diag.full_sample_brier_improvement}; "
        f"recession_improvement={diag.recession_brier_improvement}; "
        f"expansion_improvement={diag.expansion_brier_improvement}"
    )


# ---------------------------------------------------------------------------
# Test D.3 — POS (L5b-D)
# ---------------------------------------------------------------------------
def test_l5b_d_classify_nber_regime_diagnostic_only_three_states():
    """L5b-D: reference NBER classifier returns correct tri-state
    label for pre-1978, in-recession-window, and post-1978-expansion
    probe dates."""
    # Build a recession window mimicking 2008 GFC.
    windows = [(pd.Timestamp("2007-12-01"), pd.Timestamp("2009-06-01"))]
    # Pre-1978 probe: 1975-06-01 → "pre_1978".
    pre = classify_nber_regime_diagnostic_only(
        pd.Timestamp("1975-06-01"), windows,
    )
    assert pre == "pre_1978"
    # In-window probe: 2008-12-15 → "recession".
    rec = classify_nber_regime_diagnostic_only(
        pd.Timestamp("2008-12-15"), windows,
    )
    assert rec == "recession"
    # Post-1978 expansion probe: 2015-06-01 → "expansion".
    exp = classify_nber_regime_diagnostic_only(
        pd.Timestamp("2015-06-01"), windows,
    )
    assert exp == "expansion"


# ---------------------------------------------------------------------------
# Test D.4 — NEG (L5b-D)
# ---------------------------------------------------------------------------
def test_l5b_d_dataclass_rejects_invalid_pre_1978_handling():
    """L5b-D: ``RegimeConditionalDiagnostics(..., pre_1978_handling=
    "bogus")`` raises ``ValueError`` from ``__post_init__`` invariant 1."""
    with pytest.raises(ValueError, match=r"pre_1978_handling="):
        RegimeConditionalDiagnostics(
            full_sample_brier=0.25,
            recession_subset_brier=0.3,
            expansion_subset_brier=0.2,
            full_sample_climatology_brier=0.25,
            recession_climatology_brier=0.25,
            expansion_climatology_brier=0.25,
            full_sample_brier_improvement=0.0,
            recession_brier_improvement=-0.05,
            expansion_brier_improvement=0.05,
            regime_sensitivity_flag=True,
            n_recession_obs=10,
            n_expansion_obs=10,
            n_pre_1978_obs=0,
            pre_1978_handling="bogus",  # invalid tri-state
            # L5b-F Phase 2 — 5 new no-default fields (Phase 2 invariants 5-9)
            horizon=1,
            n_eff_recession=10,
            n_eff_expansion=10,
            max_confidence_cap=0.85,
            diagnostic_only=False,
            reliability_recession=float("nan"),
            resolution_recession=float("nan"),
            uncertainty_recession=float("nan"),
            reliability_expansion=float("nan"),
            resolution_expansion=float("nan"),
            uncertainty_expansion=float("nan"),
            murphy_ci_recession=(float("nan"), float("nan")),
            murphy_ci_expansion=(float("nan"), float("nan")),
            ood_reserve_fraction=0.10,
            lucas_flag=False,
            regime_shift_test=None,
            pre_post_metric_delta=None,
            lucas_warning_text=None,
        )


# ---------------------------------------------------------------------------
# Test D.5 — NEG (L5b-D)
# ---------------------------------------------------------------------------
def test_l5b_d_dataclass_rejects_missing_no_default_field():
    """L5b-D: bare ``RegimeConditionalDiagnostics(...)`` missing any of
    14 no-default fields raises ``TypeError``. AP-AUTH-53 step #3
    contract."""
    # Missing pre_1978_handling.
    with pytest.raises(TypeError, match=r"pre_1978_handling"):
        RegimeConditionalDiagnostics(
            full_sample_brier=0.25,
            recession_subset_brier=0.25,
            expansion_subset_brier=0.25,
            full_sample_climatology_brier=0.25,
            recession_climatology_brier=0.25,
            expansion_climatology_brier=0.25,
            full_sample_brier_improvement=0.0,
            recession_brier_improvement=0.0,
            expansion_brier_improvement=0.0,
            regime_sensitivity_flag=False,
            n_recession_obs=0,
            n_expansion_obs=0,
            n_pre_1978_obs=0,
            # pre_1978_handling omitted — must raise
            # L5b-F Phase 2 fields supplied (so only pre_1978_handling missing):
            horizon=1,
            n_eff_recession=0,
            n_eff_expansion=0,
            max_confidence_cap=0.85,
            diagnostic_only=True,  # min(0, 0) = 0 < 5 → diagnostic_only=True per invariant 9
        )
    # Missing regime_sensitivity_flag.
    with pytest.raises(TypeError, match=r"regime_sensitivity_flag"):
        RegimeConditionalDiagnostics(
            full_sample_brier=0.25,
            recession_subset_brier=0.25,
            expansion_subset_brier=0.25,
            full_sample_climatology_brier=0.25,
            recession_climatology_brier=0.25,
            expansion_climatology_brier=0.25,
            full_sample_brier_improvement=0.0,
            recession_brier_improvement=0.0,
            expansion_brier_improvement=0.0,
            # regime_sensitivity_flag omitted — must raise
            n_recession_obs=0,
            n_expansion_obs=0,
            n_pre_1978_obs=0,
            pre_1978_handling="diagnostic_only",
            # L5b-F Phase 2 fields supplied (so only regime_sensitivity_flag missing):
            horizon=1,
            n_eff_recession=0,
            n_eff_expansion=0,
            max_confidence_cap=0.85,
            diagnostic_only=True,
            reliability_recession=float("nan"),
            resolution_recession=float("nan"),
            uncertainty_recession=float("nan"),
            reliability_expansion=float("nan"),
            resolution_expansion=float("nan"),
            uncertainty_expansion=float("nan"),
            murphy_ci_recession=(float("nan"), float("nan")),
            murphy_ci_expansion=(float("nan"), float("nan")),
            ood_reserve_fraction=0.10,
            lucas_flag=False,
            regime_shift_test=None,
            pre_post_metric_delta=None,
            lucas_warning_text=None,
        )


# ---------------------------------------------------------------------------
# Test D.6 — NEG (L5b-D)
# ---------------------------------------------------------------------------
def test_l5b_d_dataclass_rejects_sensitivity_flag_inconsistency():
    """L5b-D: ``regime_sensitivity_flag`` must match the
    ``_compute_expected_sensitivity_flag()`` helper output per
    invariant 4. Caller passing an inconsistent flag raises
    ``ValueError``.

    Construction: full_improvement=0.10, recession_improvement=0.08
    (above 50% threshold of 0.05), expansion_improvement=0.10 (above
    threshold). Expected flag = False. Pass flag=True; should raise."""
    with pytest.raises(ValueError, match=r"regime_sensitivity_flag=.*inconsistent"):
        RegimeConditionalDiagnostics(
            full_sample_brier=0.20,
            recession_subset_brier=0.22,
            expansion_subset_brier=0.18,
            full_sample_climatology_brier=0.30,
            recession_climatology_brier=0.30,
            expansion_climatology_brier=0.28,
            full_sample_brier_improvement=0.10,   # threshold 0.05
            recession_brier_improvement=0.08,     # >= 0.05; not below
            expansion_brier_improvement=0.10,     # >= 0.05; not below
            regime_sensitivity_flag=True,         # WRONG; should be False
            n_recession_obs=10,
            n_expansion_obs=10,
            n_pre_1978_obs=0,
            pre_1978_handling="diagnostic_only",
            # L5b-F Phase 2 fields (consistent values so invariants 5-9 pass;
            # the violation under test is invariant 4 regime_sensitivity_flag):
            horizon=1,
            n_eff_recession=10,
            n_eff_expansion=10,
            max_confidence_cap=0.85,
            diagnostic_only=False,
            reliability_recession=float("nan"),
            resolution_recession=float("nan"),
            uncertainty_recession=float("nan"),
            reliability_expansion=float("nan"),
            resolution_expansion=float("nan"),
            uncertainty_expansion=float("nan"),
            murphy_ci_recession=(float("nan"), float("nan")),
            murphy_ci_expansion=(float("nan"), float("nan")),
            ood_reserve_fraction=0.10,
            lucas_flag=False,
            regime_shift_test=None,
            pre_post_metric_delta=None,
            lucas_warning_text=None,
        )


# ---------------------------------------------------------------------------
# Test D.7 — NEG-invariant (L5b-D)
# ---------------------------------------------------------------------------
def test_l5b_d_empty_recession_subset_returns_valid_degenerate_diagnostics():
    """L5b-D NEG-invariant: fixture with all-expansion observations
    yields ``n_recession_obs=0``, recession Brier NaN, flag False
    (no finite recession improvement to compare against threshold).
    Valid degenerate diagnostics; invariant 3 admits NaN."""
    n = 50
    dates = pd.date_range("2010-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(11)
    y_all = rng.integers(0, 2, size=n).astype(float)
    if y_all.sum() == 0:
        y_all[0] = 1
    elif y_all.sum() == n:
        y_all[0] = 0
    p_all = y_all.copy()

    # All-expansion classifier.
    def classifier(date: pd.Timestamp) -> str:
        return "expansion"

    diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,  # L5b-F Phase 2 — required keyword-only kwarg
        ood_reserve_fraction=0.10,
    )
    assert diag.n_recession_obs == 0
    assert diag.n_expansion_obs == n
    assert diag.n_pre_1978_obs == 0
    # Recession Brier is NaN on empty subset.
    assert math.isnan(diag.recession_subset_brier)
    assert math.isnan(diag.recession_climatology_brier)
    assert math.isnan(diag.recession_brier_improvement)
    # Sensitivity flag: no finite recession improvement to compare;
    # expansion improvement equals full (single-regime fixture);
    # threshold 0.5 × full; expansion improvement >= threshold for
    # any non-negative full_improvement → flag is False.
    assert diag.regime_sensitivity_flag is False


# ===========================================================================
# L5b-F Phase 2 — F-H2 regime-stratified confidence cap tests (4 new)
# ===========================================================================
# Closes Codex 5.5 + ChatGPT 5.5 R6 finding F-H2 on regime-stratified
# confidence caps + Standing Order #10 (10Y hard cap 0.55).

def test_lf2_aggregator_10y_horizon_caps_at_055():
    """L5b-F F.2.1 POS: aggregator with horizon=10 (10Y regime-
    stratified output) produces max_confidence_cap=0.55 per Standing
    Order #10. Closes R6 finding F-H2."""
    n = 240  # 20 years monthly
    dates = pd.date_range("2000-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(42)
    y_all = rng.integers(0, 2, size=n).astype(float)
    p_all = y_all.copy()  # perfectly calibrated for stable test
    rec_start = pd.Timestamp("2008-01-01")
    rec_end = pd.Timestamp("2009-12-01")

    def classifier(date):
        if rec_start <= date <= rec_end:
            return "recession"
        return "expansion"

    diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=10,  # 10Y → triggers hard cap 0.55
        ood_reserve_fraction=0.10,
    )
    assert diag.horizon == 10
    assert diag.max_confidence_cap == 0.55


def test_lf2_aggregator_1y_horizon_caps_at_085():
    """L5b-F F.2.2 POS: aggregator with horizon=1 (1Y standard output)
    produces max_confidence_cap=0.85 per Vision v2.0 §10. Verifies
    the non-10Y default cap path."""
    n = 100
    dates = pd.date_range("2010-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(7)
    y_all = rng.integers(0, 2, size=n).astype(float)
    p_all = y_all.copy()

    def classifier(date):
        return "expansion"

    diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,  # 1Y → standard cap 0.85
        ood_reserve_fraction=0.10,
    )
    assert diag.horizon == 1
    assert diag.max_confidence_cap == 0.85


def test_lf2_diagnostic_only_fires_when_n_eff_below_threshold():
    """L5b-F F.2.3 POS: when min(n_eff_recession, n_eff_expansion) < 5,
    the diagnostic_only flag fires. Verifies invariant 9 enforcement
    via the aggregator-computed n_eff path."""
    # Construct fixture with small recession subset to drive
    # n_eff_recession below 5.
    # With horizon=1 → horizon_months=12: n_eff = n_obs // 12.
    # For n_eff_recession < 5, need n_recession_obs < 60.
    # Use n_rec = 24 (n_eff = 2 < 5 → diagnostic_only=True).
    n_exp = 240
    n_rec = 24
    dates_exp = pd.date_range("2000-01-01", periods=n_exp, freq="MS")
    dates_rec = pd.date_range("2020-06-01", periods=n_rec, freq="MS")
    dates = dates_exp.append(dates_rec)
    rng = np.random.default_rng(42)
    y_all = rng.integers(0, 2, size=n_exp + n_rec).astype(float)
    p_all = y_all.copy()
    rec_start = pd.Timestamp("2020-06-01")

    def classifier(date):
        if date >= rec_start:
            return "recession"
        return "expansion"

    diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,
        ood_reserve_fraction=0.10,
    )
    assert diag.n_recession_obs == n_rec
    assert diag.n_eff_recession == n_rec // 12  # 24 // 12 = 2 < 5
    assert diag.diagnostic_only is True


def test_lf2_dataclass_rejects_inconsistent_max_confidence_cap():
    """L5b-F F.2.4 NEG: invariant 8 violation — horizon=10 with
    max_confidence_cap=0.85 (should be 0.55) raises ValueError.
    Mirrors test D.4/D.6 pattern; counts as strict NEG."""
    with pytest.raises(ValueError, match=r"max_confidence_cap.*inconsistent.*horizon"):
        RegimeConditionalDiagnostics(
            full_sample_brier=0.25,
            recession_subset_brier=0.25,
            expansion_subset_brier=0.25,
            full_sample_climatology_brier=0.25,
            recession_climatology_brier=0.25,
            expansion_climatology_brier=0.25,
            full_sample_brier_improvement=0.0,
            recession_brier_improvement=0.0,
            expansion_brier_improvement=0.0,
            regime_sensitivity_flag=False,
            n_recession_obs=120,
            n_expansion_obs=120,
            n_pre_1978_obs=0,
            pre_1978_handling="diagnostic_only",
            horizon=10,                  # 10Y horizon
            n_eff_recession=10,
            n_eff_expansion=10,
            max_confidence_cap=0.85,     # WRONG: must be 0.55 for 10Y
            diagnostic_only=False,
            reliability_recession=float("nan"),
            resolution_recession=float("nan"),
            uncertainty_recession=float("nan"),
            reliability_expansion=float("nan"),
            resolution_expansion=float("nan"),
            uncertainty_expansion=float("nan"),
            murphy_ci_recession=(float("nan"), float("nan")),
            murphy_ci_expansion=(float("nan"), float("nan")),
            ood_reserve_fraction=0.10,
            lucas_flag=False,
            regime_shift_test=None,
            pre_post_metric_delta=None,
            lucas_warning_text=None,
        )


# ===========================================================================
# L5b-F Phase 3 — F-H3 pre-1978 semantics + F-H4 fail-closed classifier (4 new)
# ===========================================================================
# Closes Codex 5.5 + ChatGPT 5.5 R6 findings F-H3 (docstring/code mismatch
# on "include" mode semantics) + F-H4 (classifier output validation).

def test_lf3_pre_1978_include_mode_absorbs_into_expansion():
    """L5b-F F.3.1 POS: pre_1978_handling='include' aggregates pre-1978
    observations into the expansion bucket per docstring §"include"
    semantics ("treat pre-1978 obs as expansion; lossy"). Verifies
    F-H3 semantic alignment between docstring and implementation."""
    # Fixture: 2 pre-1978 obs + 50 post-1978 expansion + 0 recession.
    dates_pre = pd.date_range("1975-01-01", periods=2, freq="MS")
    dates_post = pd.date_range("2010-01-01", periods=50, freq="MS")
    dates = dates_pre.append(dates_post)
    rng = np.random.default_rng(42)
    y_all = rng.integers(0, 2, size=52).astype(float)
    # Ensure non-degenerate climatology (some 0s and some 1s).
    if y_all.sum() == 0:
        y_all[0] = 1
    elif y_all.sum() == 52:
        y_all[0] = 0
    p_all = y_all.copy()
    boundary = pd.Timestamp("1978-01-01")

    def classifier(date):
        if date < boundary:
            return "pre_1978"
        return "expansion"

    diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,
        ood_reserve_fraction=0.10,
        pre_1978_handling="include",
    )
    # Under "include": n_expansion includes the 2 pre-1978 rows
    assert diag.n_expansion_obs == 52, (
        f"L5b-F F-H3: pre_1978_handling='include' should aggregate "
        f"pre-1978 into n_expansion (expected 52 = 50 expansion + 2 "
        f"pre-1978); got {diag.n_expansion_obs}"
    )
    # n_pre_1978_obs reports RAW classifier count for diagnostic
    # visibility (independent of mode).
    assert diag.n_pre_1978_obs == 2
    # expansion_subset_brier must be finite (Brier computed over the
    # 52-obs aggregated expansion subset).
    assert math.isfinite(diag.expansion_subset_brier)


def test_lf3_pre_1978_three_modes_produce_correct_counts():
    """L5b-F F.3.2 POS-invariant: all three pre_1978_handling modes
    produce the documented count semantics. Aggregates "exclude" +
    "diagnostic_only" + "include" cases in one fixture (defense in
    depth against silent mode drift). Counts as POS-inv = NEG-flavor
    per L5-B1 accounting convention."""
    # Fixture: 3 pre-1978 + 40 expansion + 10 recession.
    dates_pre = pd.date_range("1975-01-01", periods=3, freq="MS")
    dates_post_exp = pd.date_range("2010-01-01", periods=40, freq="MS")
    dates_post_rec = pd.date_range("2018-06-01", periods=10, freq="MS")
    dates = dates_pre.append(dates_post_exp).append(dates_post_rec)
    rng = np.random.default_rng(7)
    y_all = rng.integers(0, 2, size=53).astype(float)
    if y_all.sum() == 0:
        y_all[0] = 1
    elif y_all.sum() == 53:
        y_all[0] = 0
    p_all = y_all.copy()

    boundary = pd.Timestamp("1978-01-01")
    rec_start = pd.Timestamp("2018-06-01")
    rec_end = pd.Timestamp("2022-12-01")

    def classifier(date):
        if date < boundary:
            return "pre_1978"
        if rec_start <= date <= rec_end:
            return "recession"
        return "expansion"

    # "diagnostic_only" mode — n_expansion = raw expansion (40).
    diag_diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,
        ood_reserve_fraction=0.10,
        pre_1978_handling="diagnostic_only",
    )
    assert diag_diag.n_recession_obs == 10
    assert diag_diag.n_expansion_obs == 40
    assert diag_diag.n_pre_1978_obs == 3

    # "exclude" mode — n_expansion = raw expansion (40); pre-1978
    # diagnostic count still reported.
    diag_excl = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,
        ood_reserve_fraction=0.10,
        pre_1978_handling="exclude",
    )
    assert diag_excl.n_recession_obs == 10
    assert diag_excl.n_expansion_obs == 40
    assert diag_excl.n_pre_1978_obs == 3

    # "include" mode — n_expansion aggregates pre-1978 (40 + 3 = 43).
    diag_incl = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,
        ood_reserve_fraction=0.10,
        pre_1978_handling="include",
    )
    assert diag_incl.n_recession_obs == 10
    assert diag_incl.n_expansion_obs == 43  # 40 + 3 pre-1978 absorbed
    assert diag_incl.n_pre_1978_obs == 3   # diagnostic count preserved


def test_lf3_classifier_invalid_label_raises_value_error():
    """L5b-F F.3.3 NEG: classifier returning a label outside the
    canonical tri-state {"recession", "expansion", "pre_1978"} raises
    ValueError citing the offending label. Closes F-H4 fail-closed
    classifier validation surface."""
    n = 20
    dates = pd.date_range("2010-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(11)
    y_all = rng.integers(0, 2, size=n).astype(float)
    p_all = y_all.copy()

    def bad_classifier(date):
        # Return a label NOT in the canonical tri-state.
        if date.month == 1:
            return "typo"  # invalid
        return "expansion"

    with pytest.raises(ValueError, match=r"invalid regime label.*typo"):
        compute_regime_conditional_oos_validation(
            calibrated_probabilities=p_all,
            forward_returns_binary=y_all,
            observation_dates=dates,
            regime_classifier=bad_classifier,
            horizon=1,
            ood_reserve_fraction=0.10,
        )


def test_lf3_classifier_multiple_invalid_labels_all_reported():
    """L5b-F F.3.4 NEG-invariant: classifier returning MULTIPLE
    invalid labels has all reported (sorted) in the ValueError
    message. Defense in depth on the F-H4 fail-closed pathway —
    ensures all offending labels are surfaced, not just the first."""
    n = 20
    dates = pd.date_range("2010-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(13)
    y_all = rng.integers(0, 2, size=n).astype(float)
    p_all = y_all.copy()

    def bad_classifier(date):
        # Return TWO distinct invalid labels.
        if date.month == 1:
            return "alpha_invalid"
        if date.month == 7:
            return "beta_invalid"
        return "expansion"

    with pytest.raises(ValueError, match=r"invalid regime label") as exc_info:
        compute_regime_conditional_oos_validation(
            calibrated_probabilities=p_all,
            forward_returns_binary=y_all,
            observation_dates=dates,
            regime_classifier=bad_classifier,
            horizon=1,
            ood_reserve_fraction=0.10,
        )
    # Both offending labels must appear in the error message.
    msg = str(exc_info.value)
    assert "alpha_invalid" in msg
    assert "beta_invalid" in msg


# ===========================================================================
# L5b-F Phase 4 — Murphy decomposition + OOD + Lucas (4 new tests)
# ===========================================================================
# Closes Codex 5.5 + ChatGPT 5.5 R6 findings F-M5 (Murphy), F-M2 (OOD
# fail-closed), and F-M3 (Lucas critique surface).

def test_lf4_murphy_decomposition_identity_holds():
    """L5b-F F.4.1 POS: Murphy 1973 identity ``Brier = reliability -
    resolution + uncertainty`` holds within 1e-6 per stratum when
    ``compute_murphy_decomposition=True``. Closes R6 finding F-M5."""
    n_exp = 200
    n_rec = 100
    dates_exp = pd.date_range("2010-01-01", periods=n_exp, freq="MS")
    dates_rec = pd.date_range("2026-09-01", periods=n_rec, freq="MS")
    dates = dates_exp.append(dates_rec)
    rng = np.random.default_rng(42)
    y_all = rng.integers(0, 2, size=n_exp + n_rec).astype(float)
    if y_all.sum() == 0:
        y_all[0] = 1
    elif y_all.sum() == len(y_all):
        y_all[0] = 0
    # Mildly noisy calibration to produce non-zero reliability + resolution
    p_all = np.clip(y_all + rng.normal(0.0, 0.1, size=len(y_all)), 0.0, 1.0)
    rec_start = pd.Timestamp("2026-09-01")

    def classifier(date):
        if date >= rec_start:
            return "recession"
        return "expansion"

    diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,
        ood_reserve_fraction=0.10,
        compute_murphy_decomposition=True,
    )
    # Murphy identity must hold per stratum within 1e-6 (enforced by
    # invariant 10; this test makes the contract explicit).
    rec_identity = (
        diag.reliability_recession
        - diag.resolution_recession
        + diag.uncertainty_recession
    )
    assert math.isclose(rec_identity, diag.recession_subset_brier, abs_tol=1e-6), (
        f"L5b-F F-M5: Murphy identity violation in recession stratum "
        f"({rec_identity} != {diag.recession_subset_brier})"
    )
    exp_identity = (
        diag.reliability_expansion
        - diag.resolution_expansion
        + diag.uncertainty_expansion
    )
    assert math.isclose(exp_identity, diag.expansion_subset_brier, abs_tol=1e-6), (
        f"L5b-F F-M5: Murphy identity violation in expansion stratum "
        f"({exp_identity} != {diag.expansion_subset_brier})"
    )


def test_lf4_murphy_ci_lower_le_upper_via_stationary_bootstrap():
    """L5b-F F.4.2 POS: Murphy CIs computed via stationary block
    bootstrap (Politis-Romano 1994 reuse of L5b-A
    ``_sample_stationary_block_lengths`` helper). Lower bound must
    be <= upper bound per invariant 11."""
    n_exp = 180
    n_rec = 96
    dates_exp = pd.date_range("2010-01-01", periods=n_exp, freq="MS")
    dates_rec = pd.date_range("2025-01-01", periods=n_rec, freq="MS")
    dates = dates_exp.append(dates_rec)
    rng = np.random.default_rng(7)
    y_all = rng.integers(0, 2, size=n_exp + n_rec).astype(float)
    if y_all.sum() == 0:
        y_all[0] = 1
    elif y_all.sum() == len(y_all):
        y_all[0] = 0
    p_all = np.clip(y_all + rng.normal(0.0, 0.15, size=len(y_all)), 0.0, 1.0)
    rec_start = pd.Timestamp("2025-01-01")

    def classifier(date):
        if date >= rec_start:
            return "recession"
        return "expansion"

    diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,
        ood_reserve_fraction=0.10,
        compute_murphy_decomposition=True,
    )
    rec_lo, rec_hi = diag.murphy_ci_recession
    exp_lo, exp_hi = diag.murphy_ci_expansion
    assert math.isfinite(rec_lo) and math.isfinite(rec_hi)
    assert math.isfinite(exp_lo) and math.isfinite(exp_hi)
    assert rec_lo <= rec_hi, (
        f"L5b-F F-M5: murphy_ci_recession lower {rec_lo} > upper {rec_hi}"
    )
    assert exp_lo <= exp_hi, (
        f"L5b-F F-M5: murphy_ci_expansion lower {exp_lo} > upper {exp_hi}"
    )


def test_lf4_lucas_flag_fires_on_recent_structural_break():
    """L5b-F F.4.3 POS: when ``regime_shift_test`` provides a break
    date within ``lucas_lookback_months`` of the most-recent
    observation, the aggregator sets ``lucas_flag=True`` AND populates
    ``lucas_warning_text``. Closes R6 finding F-M3 (Lucas critique
    surface)."""
    from types import SimpleNamespace

    n_exp = 100
    n_rec = 30
    dates_exp = pd.date_range("2018-01-01", periods=n_exp, freq="MS")
    # Place recession start ~12 months before end (well within 24M lookback)
    dates_rec = pd.date_range("2025-08-01", periods=n_rec, freq="MS")
    dates = dates_exp.append(dates_rec)
    rng = np.random.default_rng(11)
    y_all = rng.integers(0, 2, size=n_exp + n_rec).astype(float)
    if y_all.sum() == 0:
        y_all[0] = 1
    elif y_all.sum() == len(y_all):
        y_all[0] = 0
    p_all = y_all.copy()
    rec_start = pd.Timestamp("2025-08-01")

    def classifier(date):
        if date >= rec_start:
            return "recession"
        return "expansion"

    # Construct a minimal regime_shift_test with break_dates_detected
    # pointing to a date within the most-recent-24M Lucas window.
    most_recent = dates.max()
    break_date = most_recent - pd.DateOffset(months=6)  # well within 24M
    fake_shift_test = SimpleNamespace(
        break_dates_detected=(break_date,),
    )

    diag = compute_regime_conditional_oos_validation(
        calibrated_probabilities=p_all,
        forward_returns_binary=y_all,
        observation_dates=dates,
        regime_classifier=classifier,
        horizon=1,
        ood_reserve_fraction=0.10,
        regime_shift_test=fake_shift_test,
        lucas_lookback_months=24,
    )
    assert diag.lucas_flag is True, (
        f"L5b-F F-M3: lucas_flag should fire when break detected "
        f"within 24M window; got {diag.lucas_flag}"
    )
    assert diag.regime_shift_test is fake_shift_test
    assert diag.lucas_warning_text is not None
    assert "Lucas critique" in diag.lucas_warning_text


def test_lf4_ood_reserve_missing_raises_type_error():
    """L5b-F F.4.4 NEG: aggregator called without ``ood_reserve_fraction``
    raises TypeError (missing required keyword-only argument). Closes
    R6 finding F-M2 (OOD reserve fail-closed per Vision §7)."""
    n = 50
    dates = pd.date_range("2010-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(42)
    y_all = rng.integers(0, 2, size=n).astype(float)
    p_all = y_all.copy()

    def classifier(date):
        return "expansion"

    # Missing ood_reserve_fraction → TypeError from required keyword-only
    with pytest.raises(TypeError, match=r"ood_reserve_fraction"):
        compute_regime_conditional_oos_validation(
            calibrated_probabilities=p_all,
            forward_returns_binary=y_all,
            observation_dates=dates,
            regime_classifier=classifier,
            horizon=1,
            # ood_reserve_fraction OMITTED — fail-closed per F-M2
        )
