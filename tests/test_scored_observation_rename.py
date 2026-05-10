"""Tests for Layer 3.5D ``ScoredObservation`` rename + new fields.

Per ``LAYER_3_5_BUILD_SPEC.md`` §6.5 + Decision Lock 3.5D-D3/D4.

Negative / positive split: 3 NEG / 1 POS. Combined with
``test_regime_dissent.py`` the 3.5D delta is 4 NEG / 4 POS = 50%.
"""
from __future__ import annotations

import warnings

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.scoring.crps import compute_crps
from macro_pipeline.scoring.scored_observation import ScoredObservation


def _valid_kwargs(**overrides):
    base = dict(
        as_of=pd.Timestamp("2025-06-01"),
        score_type="CRPS",
        raw_score=0.40,
        confidence=72.0,
        confidence_breakdown={
            "data_quality": 0.9, "track_record": 0.8,
            "regime_stability": 0.7, "theoretical_foundation": 0.9,
            "sample_adequacy": 0.7,
            "ood_penalty": 0.0, "revision_penalty": 0.0,
        },
        conviction_statistical=7.0,
        conviction_operational=5.0,
        conviction_actionability=6.0,
        component_values={"a": 1.0},
        component_weights={"a": 1.0},
        component_sources={"a": "FRED_API"},
        component_normalized={"a": 0.4},
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


# ---------------------------------------------------------------------------
# 1. NEG — score_value as kwarg fails (constructor must use raw_score=)
# ---------------------------------------------------------------------------
def test_score_value_kwarg_fails_in_constructor():
    """After Layer 3.5D the constructor takes ``raw_score=``; passing
    ``score_value=...`` should raise TypeError because it is no longer
    a dataclass field."""
    kwargs = _valid_kwargs()
    kwargs.pop("raw_score")  # drop the new name
    with pytest.raises(TypeError):
        ScoredObservation(score_value=0.40, **kwargs)


# ---------------------------------------------------------------------------
# 2. NEG — score_value property emits DeprecationWarning
# ---------------------------------------------------------------------------
def test_score_value_property_emits_deprecation():
    so = ScoredObservation(**_valid_kwargs())
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        val = so.score_value
    assert val == so.raw_score
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert any(
        "score_value" in str(w.message) and "raw_score" in str(w.message)
        for w in deprecations
    ), f"Expected DeprecationWarning re raw_score; got {[str(w.message) for w in caught]}"


# ---------------------------------------------------------------------------
# 3. POS — raw_score field present + typed; calibrated_probability defaults None
# ---------------------------------------------------------------------------
def test_raw_score_field_present_and_calibrated_probability_default_none():
    fields = ScoredObservation.__dataclass_fields__
    assert "raw_score" in fields
    assert fields["raw_score"].type == "float"
    assert "calibrated_probability" in fields
    assert "calibration_metadata" in fields
    assert "notes" in fields

    so = ScoredObservation(**_valid_kwargs())
    assert so.calibrated_probability is None
    assert so.calibration_metadata is None
    assert so.notes == []


# ---------------------------------------------------------------------------
# 4. NEG — calibrated_probability out of range raises
# ---------------------------------------------------------------------------
def test_calibrated_probability_out_of_range_raises():
    with pytest.raises(ValueError, match="calibrated_probability"):
        ScoredObservation(**_valid_kwargs(calibrated_probability=1.2))
    with pytest.raises(ValueError, match="calibrated_probability"):
        ScoredObservation(**_valid_kwargs(calibrated_probability=-0.1))


# ---------------------------------------------------------------------------
# Bonus: cross-phase notes migration smoke (3.5B + 3.5D)
# ---------------------------------------------------------------------------
def test_crps_notes_carry_3_5B_pit_lineage_after_3_5D_migration():
    """At 2008-09-15 (SAHM contributes; INDETERMINATE state from 3.5D),
    notes must carry both: (a) the 3.5B Option Z construction caveat
    (migrated from metadata_extra into notes), and (b) the 3.5D
    INDETERMINATE rationale."""
    ctx = PitDataContext(as_of=pd.Timestamp("2008-09-15"))
    crps = compute_crps(ctx)
    notes_concat = "\n".join(crps.notes).lower()
    assert "by_construction" in notes_concat or "construction" in notes_concat, (
        f"3.5B Option Z note missing from .notes: {crps.notes}"
    )
    assert "indeterminate" in notes_concat, (
        f"3.5D INDETERMINATE note missing from .notes: {crps.notes}"
    )
    # 3.5B metadata_extra keys should be DROPPED post-migration.
    assert "pit_safe_basis_per_component" not in crps.metadata_extra
    assert "derived_confidence_cap_applied" not in crps.metadata_extra
    assert "pit_construction_notes" not in crps.metadata_extra
