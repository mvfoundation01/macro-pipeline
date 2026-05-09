"""Tests for ``macro_pipeline.scoring.scored_observation`` (Layer 3B)."""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.scoring import CompositeBuildError, ScoredObservation


def _valid_kwargs(**overrides) -> dict:
    base = dict(
        as_of=pd.Timestamp("2025-06-01"),
        score_type="CRPS",
        score_value=0.40,
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
    assert so.score_value == 0.40
    assert so.regime_state == "expansion"
    assert so.metadata_extra == {}


def test_score_value_must_be_in_unit_interval():
    with pytest.raises(ValueError, match="score_value"):
        ScoredObservation(**_valid_kwargs(score_value=1.2))
    with pytest.raises(ValueError, match="score_value"):
        ScoredObservation(**_valid_kwargs(score_value=-0.1))


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
