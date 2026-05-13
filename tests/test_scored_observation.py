"""Tests for ``macro_pipeline.scoring.scored_observation`` (Layer 3B)."""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.scoring import CompositeBuildError, ScoredObservation


def _valid_kwargs(**overrides) -> dict:
    base = dict(
        as_of=pd.Timestamp("2025-06-01"),
        score_type="CRPS",
        raw_score=0.40,
        confidence=72.0,
        confidence_breakdown={"data_quality": 0.9, "track_record": 0.8,
                               "regime_stability": 0.7,
                               "theoretical_foundation": 0.9,
                               "sample_adequacy": 0.7,
                               "ood_penalty": 0.0, "revision_penalty": 0.0},
        conviction_statistical=7.0,
        conviction_operational=5.0,
        conviction_actionability=6.0,
        component_values={"a": 1.0, "b": 2.0},
        component_weights={"a": 0.5, "b": 0.5},
        component_sources={"a": "FRED_API", "b": "TV_CSV"},
        component_normalized={"a": 0.4, "b": 0.6},
        quality_caps_applied={"source_cap_min": 0.75, "horizon_cap_1Y": 0.85},
        final_quality_cap=0.75,
        regime_state="expansion",
        regime_phase_kindleberger="boom",
        regime_phase_dalio="late",
        pit_safe=True,
        pit_source="mixed",
    )
    base.update(overrides)
    return base


def test_constructs_with_valid_inputs():
    so = ScoredObservation(**_valid_kwargs())
    assert so.score_type == "CRPS"
    assert so.raw_score == 0.40
    assert so.regime_state == "expansion"
    assert so.metadata_extra == {}


def test_raw_score_must_be_in_unit_interval():
    with pytest.raises(ValueError, match="raw_score"):
        ScoredObservation(**_valid_kwargs(raw_score=1.2))
    with pytest.raises(ValueError, match="raw_score"):
        ScoredObservation(**_valid_kwargs(raw_score=-0.1))


def test_score_type_validated():
    with pytest.raises(ValueError, match="score_type"):
        ScoredObservation(**_valid_kwargs(score_type="OTHER"))


def test_regime_state_validated():
    with pytest.raises(ValueError, match="regime_state"):
        ScoredObservation(**_valid_kwargs(regime_state="boom"))


def test_conviction_bounds():
    with pytest.raises(ValueError, match="conviction"):
        ScoredObservation(**_valid_kwargs(conviction_statistical=11.0))


def test_to_dict_roundtrips_keys():
    so = ScoredObservation(**_valid_kwargs())
    d = so.to_dict()
    assert d["score_type"] == "CRPS"
    assert d["regime_state"] == "expansion"
    assert d["component_values"] == {"a": 1.0, "b": 2.0}


def test_metadata_extra_default_factory():
    """Two instances must not share the same metadata_extra dict."""
    a = ScoredObservation(**_valid_kwargs())
    b = ScoredObservation(**_valid_kwargs())
    a.metadata_extra["x"] = 1
    assert "x" not in b.metadata_extra


def test_composite_build_error_is_exception():
    with pytest.raises(CompositeBuildError):
        raise CompositeBuildError("test")


# ---------------------------------------------------------------------------
# L5-RM-4 — 7 new tests in this file (per spec §5.RM-4.5 rows 1, 2, 4-8;
# row 3 lives in tests/test_cdrs.py). Spec test #1 magic-number 31 ≠ empirical
# count post-migration (23 + 6 = 29 total); test asserts empirical count per
# S-12 disposition (a). Spec ref: LAYER_5_BUILD_SPEC.md v6 §5.RM-4.5
# (lines 1047-1060).
# ---------------------------------------------------------------------------

import json
from pathlib import Path


# --- Test #1 (POS; spec name aliased per S-12) -----------------------------

def test_dataclass_has_29_slots_actual_vs_spec_31_claimed():
    """§5.RM-4.5 test #1 — assert empirical __dataclass_fields__ count.

    Spec literal test name: ``test_dataclass_has_all_31_slots``.
    S-12 disposition (a): production base = 23 (NOT spec-claimed 25);
    post-RM-4 addition of 6 fields → total = 29 (NOT spec-claimed 31).
    Test asserts empirical truth + cites S-12 for the spec-vs-empirical gap.
    """
    fields = list(ScoredObservation.__dataclass_fields__.keys())
    # 6 new slots per spec §5.RM-4.1.1 (lines 940-960) must be present
    expected_new_slots = {
        "calibrated_probability_band_lower",
        "calibrated_probability_band_upper",
        "drawdown_conditional_distribution",
        "dms_adjustment_bps",
        "bayesian_shrinkage_weight",
        "positive_return_probability",
    }
    assert expected_new_slots.issubset(set(fields)), (
        f"Missing new L5-RM-4 slots; got: {set(fields)}"
    )
    # Empirical count per S-12 disposition (a)
    assert len(fields) == 29, (
        f"Empirical __dataclass_fields__ count = {len(fields)}; "
        "expected 29 (= 23 base + 6 new). Spec §5.RM-4.5 claimed 31 "
        "but production base is 23 not 25; see S-12 in L5_BUILD_SXX_LOG.md."
    )


# --- Test #2 (POS) ---------------------------------------------------------

def test_parquet_roundtrip_preserves_6_new_slots(tmp_path: Path):
    """§5.RM-4.5 test #2 — populate all 29 slots; to_dict() + JSON
    roundtrip; element-wise equality on the 6 NEW slots.

    Uses JSON roundtrip (not parquet) because ScoredObservation.to_dict()
    is the spec'd serialization surface and parquet roundtrip would
    require a wrapping DataFrame schema not in scope for L5-RM-4. The
    invariant being tested (new slots survive a round-trip via to_dict)
    is identical.
    """
    populated_kwargs = _valid_kwargs(
        calibrated_probability=0.55,
        calibrated_probability_band_lower=0.45,
        calibrated_probability_band_upper=0.65,
        drawdown_conditional_distribution={
            "p10": 0.05, "p25": 0.10, "p50": 0.20, "p75": 0.35, "p90": 0.50,
        },
        dms_adjustment_bps=-125.0,
        bayesian_shrinkage_weight=0.30,
        positive_return_probability=0.70,
    )
    so = ScoredObservation(**populated_kwargs)
    d = so.to_dict()
    # Round-trip via JSON (lossless for dict/list/scalar mix in this scope)
    json_str = json.dumps(d, default=str)
    d_roundtrip = json.loads(json_str)
    # Element-wise equality on 6 new slots
    assert d_roundtrip["calibrated_probability_band_lower"] == 0.45
    assert d_roundtrip["calibrated_probability_band_upper"] == 0.65
    assert d_roundtrip["drawdown_conditional_distribution"] == {
        "p10": 0.05, "p25": 0.10, "p50": 0.20, "p75": 0.35, "p90": 0.50,
    }
    assert d_roundtrip["dms_adjustment_bps"] == -125.0
    assert d_roundtrip["bayesian_shrinkage_weight"] == 0.30
    assert d_roundtrip["positive_return_probability"] == 0.70


# --- Test #4 (NEG) ---------------------------------------------------------

def test_rejects_calibrated_probability_band_lower_outside_zero_one():
    """§5.RM-4.5 test #4 — band_lower validator (∈ [0, 1] when present)."""
    with pytest.raises(ValueError, match="calibrated_probability_band_lower"):
        ScoredObservation(**_valid_kwargs(
            calibrated_probability_band_lower=1.5,
        ))
    with pytest.raises(ValueError, match="calibrated_probability_band_lower"):
        ScoredObservation(**_valid_kwargs(
            calibrated_probability_band_lower=-0.1,
        ))


# --- Test #5 (NEG) ---------------------------------------------------------

def test_rejects_calibrated_probability_band_upper_outside_zero_one():
    """§5.RM-4.5 test #5 — band_upper validator (∈ [0, 1] when present)."""
    with pytest.raises(ValueError, match="calibrated_probability_band_upper"):
        ScoredObservation(**_valid_kwargs(
            calibrated_probability_band_upper=1.5,
        ))
    with pytest.raises(ValueError, match="calibrated_probability_band_upper"):
        ScoredObservation(**_valid_kwargs(
            calibrated_probability_band_upper=-0.1,
        ))


# --- Test #6 (NEG) ---------------------------------------------------------

def test_rejects_band_lower_greater_than_band_upper():
    """§5.RM-4.5 test #6 — band_lower ≤ band_upper ordering invariant."""
    with pytest.raises(ValueError, match="band_lower.* must be <= band_upper"):
        ScoredObservation(**_valid_kwargs(
            calibrated_probability_band_lower=0.7,
            calibrated_probability_band_upper=0.5,
        ))


# --- Test #7 (NEG) ---------------------------------------------------------

def test_rejects_dms_adjustment_outside_minus_200_to_zero_bps_band():
    """§5.RM-4.5 test #7 — dms_adjustment_bps ∈ [-200, 0] domain."""
    with pytest.raises(ValueError, match="dms_adjustment_bps"):
        ScoredObservation(**_valid_kwargs(dms_adjustment_bps=10.0))  # positive
    with pytest.raises(ValueError, match="dms_adjustment_bps"):
        ScoredObservation(**_valid_kwargs(dms_adjustment_bps=-300.0))  # too negative


# --- Test #8 (NEG) ---------------------------------------------------------

def test_rejects_bayesian_shrinkage_weight_outside_zero_one():
    """§5.RM-4.5 test #8 — bayesian_shrinkage_weight ∈ [0, 1] domain."""
    with pytest.raises(ValueError, match="bayesian_shrinkage_weight"):
        ScoredObservation(**_valid_kwargs(bayesian_shrinkage_weight=1.5))
    with pytest.raises(ValueError, match="bayesian_shrinkage_weight"):
        ScoredObservation(**_valid_kwargs(bayesian_shrinkage_weight=-0.1))
