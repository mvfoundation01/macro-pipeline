"""Tests for the USSLIND -> PHILLY_LEI_PROXY rename (Layer 1.5C.3)."""
from __future__ import annotations

import logging

import pytest

from macro_pipeline.config import FRED_SERIES_API
from macro_pipeline.loaders.fred_loader import load_fred_series
from macro_pipeline.models.composite_guards import check_double_counting


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def test_usslind_registered_with_alias():
    spec = FRED_SERIES_API["USSLIND"]
    assert spec.get("indicator_id") == "PHILLY_LEI_PROXY"
    assert spec.get("double_counting_risk") is True
    assert "T10Y3M" in spec.get("overlap_components", [])


def test_load_fred_series_returns_aliased_indicator_id():
    s, m = load_fred_series("USSLIND")
    assert m.indicator_id == "PHILLY_LEI_PROXY"
    assert s.name == "PHILLY_LEI_PROXY"
    assert m.extra["fred_series_id"] == "USSLIND"


def test_load_fred_series_metadata_carries_double_counting_flag():
    _, m = load_fred_series("USSLIND")
    assert m.extra["double_counting_risk"] is True
    assert "T10Y3M" in m.extra["overlap_components"]


# ---------------------------------------------------------------------------
# Composite guard
# ---------------------------------------------------------------------------
def test_double_counting_clean_when_only_phl_lei():
    violations = check_double_counting(["PHILLY_LEI_PROXY", "VIX"])
    assert violations == []


def test_double_counting_warns_when_phl_lei_plus_t10y3m():
    """C.3 acceptance: combining PHILLY_LEI_PROXY + T10Y3M must surface
    a double-counting warning."""
    violations = check_double_counting(
        ["PHILLY_LEI_PROXY", "T10Y3M", "NFCI"],
    )
    assert len(violations) == 1
    v = violations[0]
    assert v.indicator_id == "PHILLY_LEI_PROXY"
    assert "T10Y3M" in v.detail


def test_double_counting_warns_on_ism_overlap():
    violations = check_double_counting(["PHILLY_LEI_PROXY", "ISM_NEW_ORDERS"])
    assert len(violations) == 1
    assert "ISM_NEW_ORDERS" in violations[0].detail


def test_double_counting_can_raise_on_violation():
    with pytest.raises(ValueError, match="double-counting"):
        check_double_counting(
            ["PHILLY_LEI_PROXY", "T10Y3M"], raise_on_violation=True,
        )


def test_double_counting_log_at_warning_level(caplog):
    with caplog.at_level(logging.WARNING, logger="macro_pipeline.models.composite_guards"):
        check_double_counting(["PHILLY_LEI_PROXY", "T10Y3M"])
    assert any(
        "double_counting" in rec.message and "PHILLY_LEI_PROXY" in rec.message
        for rec in caplog.records
    )
