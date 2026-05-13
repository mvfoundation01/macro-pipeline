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
