"""Tests for ``macro_pipeline.scoring.crps`` (Layer 3B, Path B)."""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.models.crps_weights import EXPERT_COEFFICIENT_PRIORS
from macro_pipeline.scoring import (
    LAYER3_ACTIVE_COMPONENTS,
    LAYER3_INACTIVE_COMPONENTS,
    LAYER3_REDISTRIBUTION_METHOD,
    CompositeBuildError,
    ScoredObservation,
    compute_crps,
    crps_layer3_weights,
)

# --- Weight redistribution + placeholder contract ----------------------------

def test_active_components_path_b():
    """Path B has exactly 4 active components in fixed order."""
    assert LAYER3_ACTIVE_COMPONENTS == [
        "yield_curve_nyfed",
        "sahm_rule",
        "nfci_kcfsi",
        "hy_oas_regime",
    ]
    assert "lei_3d_rule" in LAYER3_INACTIVE_COMPONENTS
    assert "ism_pmi_neworders" in LAYER3_INACTIVE_COMPONENTS


def test_weights_sum_to_one_and_are_redistributed_proportionally():
    w = crps_layer3_weights()
    assert w.is_placeholder is True
    assert abs(sum(w.weights.values()) - 1.0) < 1e-9
    assert w.redistribution_method == LAYER3_REDISTRIBUTION_METHOD
    assert set(w.weights.keys()) == set(LAYER3_ACTIVE_COMPONENTS)
    # Proportional check: weight ratio must equal raw mean ratio for any pair.
    raw = {k: float(p.mean) for k, p in EXPERT_COEFFICIENT_PRIORS.items()}
    a, b = "yield_curve_nyfed", "sahm_rule"
    expected_ratio = raw[a] / raw[b]
    actual_ratio = w.weights[a] / w.weights[b]
    assert abs(expected_ratio - actual_ratio) < 1e-9


def test_inactive_components_recorded():
    w = crps_layer3_weights()
    assert "lei_3d_rule" in w.inactive_components
    assert "ism_pmi_neworders" in w.inactive_components


def test_expert_priors_unchanged_layer5_truth():
    """The 6-key EXPERT_COEFFICIENT_PRIORS is the Layer 5 source of
    truth. Layer 3B must NOT mutate it; redistribution lives in
    crps_layer3_weights() instead."""
    assert set(EXPERT_COEFFICIENT_PRIORS.keys()) == {
        "yield_curve_nyfed", "sahm_rule", "lei_3d_rule",
        "ism_pmi_neworders", "nfci_kcfsi", "hy_oas_regime",
    }
    assert EXPERT_COEFFICIENT_PRIORS["yield_curve_nyfed"].mean == 0.30


def test_compute_crps_rejects_non_placeholder_weights():
    from macro_pipeline.models.crps_weights import WeightEstimationResult
    fitted = WeightEstimationResult(
        method="layer5_ridge_fitted",
        weights={k: 0.25 for k in LAYER3_ACTIVE_COMPONENTS},
        is_placeholder=False,
    )
    with pytest.raises(CompositeBuildError, match="placeholder"):
        compute_crps(PitDataContext(as_of=pd.Timestamp("2025-06-01")), weights=fitted)


# --- End-to-end scoring at historical anchors --------------------------------

def test_compute_crps_2025_06_expansion_calm():
    """At as_of=2025-06-01 (post-COVID expansion, late-cycle valuation),
    Path B CRPS should land in the low-mid range (<0.35) because no
    component is fully firing — yield curve is positive, Sahm low,
    NFCI loose, HY OAS tight."""
    ctx = PitDataContext(as_of=pd.Timestamp("2025-06-01"))
    so = compute_crps(ctx)
    assert isinstance(so, ScoredObservation)
    assert so.score_type == "CRPS"
    assert 0.0 <= so.raw_score <= 0.35
    # Layer 3.5D D24: at 2025-06 the HMM v1 reads 'recession' while
    # NBER+Kindleberger consensus is 'expansion' (HMM late-cycle bias
    # post-2008 — see regime/README §3). derive_regime_state correctly
    # flags this as 'indeterminate'.
    assert so.regime_state in {"expansion", "late-cycle", "indeterminate"}
    assert so.metadata_extra["weights_is_placeholder"] is True
    assert so.metadata_extra["redistribution_method"] == "proportional"
    assert "lei_3d_rule" in so.metadata_extra["inactive_components"]


def test_compute_crps_2008_09_recession_signal():
    """At Lehman week (as_of=2008-09-15), Path B CRPS should fire
    moderately — Sahm peaks, NFCI peaks, HY OAS peaks. Note: T10Y3M
    UN-inverts during recessions as Fed cuts rates, so the yield-curve
    component drops to ~0 and the 4-component Path B max is ~0.57. Spec
    §5.5's >0.85 expectation assumed all 6 components; our active 4 max
    out near 0.57. We assert > 0.40 (well above the expansion baseline).

    Layer 3.5D D24: at 2008-09-15 the HMM v1 reads 'recession' while
    consensus (after Kindleberger=revulsion override of NBER expansion)
    is 'late-cycle'; derive_regime_state correctly flags 'indeterminate'.
    """
    ctx = PitDataContext(as_of=pd.Timestamp("2008-09-15"))
    so = compute_crps(ctx)
    assert so.raw_score > 0.40
    assert so.regime_state in {"recession", "late-cycle", "indeterminate"}
    # Sahm should normalize to 1.0 (rule fully triggered)
    assert so.component_normalized["sahm_rule"] >= 0.99
    # HY OAS should be in extreme widening regime
    assert so.component_normalized["hy_oas_regime"] >= 0.70


def test_compute_crps_2017_06_calm_baseline():
    """Mid-cycle 2017 calm: all signals quiet. Score < 0.20."""
    ctx = PitDataContext(as_of=pd.Timestamp("2017-06-01"))
    so = compute_crps(ctx)
    assert so.raw_score < 0.20
    assert so.component_normalized["sahm_rule"] == 0.0
    assert so.component_normalized["hy_oas_regime"] < 0.30


def test_compute_crps_recession_strictly_above_expansion():
    """Sanity-check ordering: 2008-09 score must exceed 2017-06 score."""
    rec = compute_crps(PitDataContext(as_of=pd.Timestamp("2008-09-15"))).raw_score
    cal = compute_crps(PitDataContext(as_of=pd.Timestamp("2017-06-01"))).raw_score
    assert rec > cal


# --- Composite guards --------------------------------------------------------

def test_composite_double_counting_blocked_by_compute_path():
    """Smoke that the guard machinery is reachable. Direct unit test of
    the guard lives in test_composite_guards; here we just confirm the
    import resolves and that PHILLY_LEI_PROXY co-existing with T10Y3M
    in the call graph would be flagged. The CRPS scorer itself does not
    pass PHILLY_LEI_PROXY (LEI is in inactive_components), so this is a
    contract test on the guard wrapper."""
    from macro_pipeline.models.composite_guards import check_double_counting
    violations = check_double_counting(["PHILLY_LEI_PROXY", "T10Y3M"])
    assert violations, "guard must flag the LEI/T10Y3M overlap"


def test_compute_crps_pit_safety_lineage():
    """Every component bundle must be PIT-safe; the aggregated pit_source
    string is recorded and is one of the documented values."""
    so = compute_crps(PitDataContext(as_of=pd.Timestamp("2008-09-15")))
    assert so.pit_safe is True
    assert any(tag in so.pit_source for tag in (
        "vintage_panel", "release_lag", "asof_truncation",
        "visibility_shift", "non_vintage", "mixed",
    ))


def test_compute_crps_quality_cap_chain():
    """final_quality_cap must equal min of the breakdown values; for
    Path B the TV-sourced BAMLH0A0HYM2 caps source quality at 0.75."""
    so = compute_crps(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    breakdown = {k: v for k, v in so.quality_caps_applied.items() if v is not None}
    assert so.final_quality_cap == min(breakdown.values())
    # 1Y cap dominates only when source quality is high; here the TV
    # CSV cap is tighter, so final ≤ 0.75.
    assert so.final_quality_cap <= 0.75


# --- Component normalizations (§5.4.1) ---------------------------------------

def test_normalize_t10y3m_inversion_high_score():
    from macro_pipeline.scoring import normalize_t10y3m
    assert normalize_t10y3m(0.0) == pytest.approx(0.5)
    # 50bps inversion → sigmoid(1) ≈ 0.731
    assert normalize_t10y3m(-0.50) == pytest.approx(0.731, abs=1e-3)
    # Steep curve → low score
    assert normalize_t10y3m(2.0) < 0.05


def test_normalize_sahm_threshold_ramp():
    from macro_pipeline.scoring import normalize_sahm
    assert normalize_sahm(0.0) == 0.0
    assert normalize_sahm(0.30) == 0.0
    assert normalize_sahm(0.40) == pytest.approx(0.5)
    assert normalize_sahm(0.50) == 1.0
    assert normalize_sahm(1.50) == 1.0


def test_normalize_nfci_tightening_high_score():
    from macro_pipeline.scoring import normalize_nfci
    assert normalize_nfci(0.0) == pytest.approx(0.5)
    assert normalize_nfci(1.0) > 0.85


def test_normalize_hy_oas_regime_percentile_clipped():
    from macro_pipeline.scoring import normalize_hy_oas_regime
    series = pd.Series(
        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        index=pd.date_range("2020-01-01", periods=10, freq="D"),
    )
    # value at 50th pctile → score 0
    assert normalize_hy_oas_regime(5.0, series) == 0.0
    # value at 90th pctile → score 0.8
    assert normalize_hy_oas_regime(9.0, series) == pytest.approx(0.8, abs=1e-9)
    # value above max → score 1.0 (clipped)
    assert normalize_hy_oas_regime(20.0, series) == 1.0
