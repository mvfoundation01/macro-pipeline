"""Tests for the Sahm Rule re-classification (Layer 1.5C.4)."""
from __future__ import annotations

import pytest

from macro_pipeline.config import FRED_SERIES_API
from macro_pipeline.loaders.fred_loader import load_fred_series
from macro_pipeline.models.composite_guards import check_signal_type_compatibility


# ---------------------------------------------------------------------------
# Spec metadata
# ---------------------------------------------------------------------------
def test_sahm_signal_type_is_coincident():
    spec = FRED_SERIES_API["SAHMREALTIME"]
    assert spec["signal_type"] == "coincident"


def test_sahm_valid_uses_match_chatgpt_spec():
    spec = FRED_SERIES_API["SAHMREALTIME"]
    assert "recession_start_detection" in spec["valid_uses"]
    assert "real_time_recession_indicator" in spec["valid_uses"]


def test_sahm_invalid_uses_block_12m_leading():
    spec = FRED_SERIES_API["SAHMREALTIME"]
    assert "12M_recession_probability_composite" in spec["INVALID_uses"]
    assert "12M_leading_indicator" in spec["INVALID_uses"]


def test_sahm_loaded_metadata_carries_signal_type():
    _, m = load_fred_series("SAHMREALTIME")
    assert m.extra["signal_type"] == "coincident"
    assert "12M_recession_probability_composite" in m.extra["INVALID_uses"]


# ---------------------------------------------------------------------------
# Composite-guard semantics
# ---------------------------------------------------------------------------
def test_signal_type_guard_clean_for_correct_context():
    v = check_signal_type_compatibility(
        "SAHMREALTIME", "recession_start_detection",
    )
    assert v is None


def test_signal_type_guard_flags_12m_leading_context():
    v = check_signal_type_compatibility(
        "SAHMREALTIME", "12M_recession_probability_composite",
    )
    assert v is not None
    assert v.indicator_id == "SAHMREALTIME"
    assert "COINCIDENT" in v.detail


def test_signal_type_guard_flags_12m_leading_alias():
    v = check_signal_type_compatibility(
        "SAHMREALTIME", "12M_leading_indicator",
    )
    assert v is not None


def test_signal_type_guard_can_raise():
    with pytest.raises(ValueError):
        check_signal_type_compatibility(
            "SAHMREALTIME", "12M_recession_probability_composite",
            raise_on_violation=True,
        )


def test_signal_type_guard_passes_for_non_coincident_indicators():
    v = check_signal_type_compatibility(
        "T10Y3M", "12M_recession_probability_composite",
    )
    assert v is None
