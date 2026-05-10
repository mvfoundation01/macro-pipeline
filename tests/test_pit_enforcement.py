"""Tests for Layer 3.5B PIT contract enforcement (Option Z).

Per ``LAYER_3_5_BUILD_SPEC.md`` §4.5 + standing-orders §2.7 (≥50% NEG floor).

Final split: 4 NEG / 4 POS = 50%, satisfying §2.7.

Negative tests cover:
- unflagged vintage series → ``PitContractViolationError``
- flag set without rationale → ``ValueError`` at config import
- audit detects an injected mismatch
- ``aggregate_caps`` MIN is invariant to ``None`` derived cap

Positive tests cover:
- SAHMREALTIME load returns Option Z bundle with cap propagated
- audit on the canonical config returns 0 mismatches
- CRPS confidence at 4 anchor dates clamps to 0.70
- ScoredObservation.metadata_extra carries the construction caveat
"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext, load_series
from macro_pipeline.exceptions import PitContractViolationError
from macro_pipeline.models.quality_caps import aggregate_caps
from macro_pipeline.scoring.crps import compute_crps
from macro_pipeline.utils.pit_audit import (
    audit_pit_contracts,
)


# ---------------------------------------------------------------------------
# 1. POS — SAHMREALTIME returns with construction flag + cap
# ---------------------------------------------------------------------------
def test_pit_reader_sahm_returns_with_construction_flag():
    """`load_series('SAHMREALTIME', as_of=...)` returns a bundle whose
    ``pit_safe_basis="by_construction"``, ``pit_safe=True``,
    ``derived_confidence_cap=0.70``, and ``notes`` contains the rationale.
    """
    bundle = load_series("SAHMREALTIME", as_of=pd.Timestamp("2008-09-15"))
    assert bundle.pit_safe is True
    assert bundle.pit_safe_basis == "by_construction"
    assert bundle.derived_confidence_cap == pytest.approx(0.70)
    assert any("pit_safe_by_construction" in n for n in bundle.notes), \
        f"notes did not include construction caveat: {bundle.notes}"


# ---------------------------------------------------------------------------
# 2. NEG — unflagged vintage series raises PitContractViolationError
# ---------------------------------------------------------------------------
def test_pit_reader_unflagged_vintage_series_raises(monkeypatch):
    """Mock a vintage=True series that is neither in
    ``VINTAGE_REQUIRED_SERIES`` nor flagged
    ``pit_safe_by_construction=True``. PIT load must raise."""
    # Stub config so SAHMREALTIME loses Option Z but keeps vintage=True
    from macro_pipeline import config

    sahm_orig = dict(config.FRED_SERIES_API["SAHMREALTIME"])
    sahm_unflagged = dict(sahm_orig)
    sahm_unflagged["pit_safe_by_construction"] = False
    sahm_unflagged["derived_confidence_cap"] = None
    sahm_unflagged["pit_construction_rationale"] = None

    monkeypatch.setitem(
        config.FRED_SERIES_API, "SAHMREALTIME", sahm_unflagged
    )
    with pytest.raises(PitContractViolationError) as exc_info:
        load_series("SAHMREALTIME", as_of=pd.Timestamp("2008-09-15"))
    assert "SAHMREALTIME" in str(exc_info.value)
    assert "VINTAGE_REQUIRED_SERIES" in str(exc_info.value) or \
           "pit_safe_by_construction" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. POS — audit returns 0 mismatches on canonical config
# ---------------------------------------------------------------------------
def test_pit_audit_finds_no_mismatches_post_3_5B():
    report = audit_pit_contracts()
    assert report.total_violations == 0, (
        f"Expected 0 mismatches, got {report.total_violations}: "
        f"{[m.series_id for m in report.mismatches]}"
    )
    # SAHMREALTIME is the canonical (and currently only) Option Z member
    assert "SAHMREALTIME" in report.series_with_pit_safe_by_construction_true


# ---------------------------------------------------------------------------
# 4. POS — CRPS confidence at 4 anchors clamps to 0.70
# ---------------------------------------------------------------------------
def test_crps_with_sahm_caps_overall_confidence_70():
    """At each of the 4 spec anchor dates, CRPS confidence ≤ 0.70 (in
    the [0, 1] scale; ≤ 70 in the [0, 100] scale)."""
    anchors = [
        pd.Timestamp("1998-08-01"),
        pd.Timestamp("2001-04-01"),
        pd.Timestamp("2008-09-15"),
        pd.Timestamp("2020-04-01"),
    ]
    for asof in anchors:
        ctx = PitDataContext(as_of=asof)
        obs = compute_crps(ctx)
        # confidence in [0, 100]; cap is 0.70 → ≤ 70 (with float epsilon)
        assert obs.confidence <= 70.0 + 1e-6, (
            f"At {asof.date()}, confidence={obs.confidence} > 70.0"
        )
        # final_quality_cap should also be ≤ 0.70 (MIN bound)
        assert obs.final_quality_cap <= 0.70 + 1e-9


# ---------------------------------------------------------------------------
# 5. NEG — pit_safe_by_construction without rationale raises ValueError
# ---------------------------------------------------------------------------
def test_pit_safe_by_construction_requires_rationale(monkeypatch):
    """The `_validate_pit_construction_consistency` helper rejects a
    flagged-but-rationaleless config entry."""
    from macro_pipeline import config

    bad_spec = {
        "freq": "M", "vintage": True, "unit": "pct",
        "expected_min": -1.0, "expected_max": 10.0,
        "release_lag_days": 7,
        "pit_safe_by_construction": True,
        "pit_construction_rationale": "",  # empty
        "derived_confidence_cap": 0.70,
        "description": "test",
    }
    fake_api = {**config.FRED_SERIES_API, "TEST_BAD_PIT": bad_spec}
    monkeypatch.setattr(config, "FRED_SERIES_API", fake_api)
    with pytest.raises(ValueError) as exc_info:
        config._validate_pit_construction_consistency()
    assert "rationale" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 6. POS — ScoredObservation.metadata_extra carries construction lineage
# ---------------------------------------------------------------------------
def test_layer_6_displays_construction_caveat_in_notes():
    ctx = PitDataContext(as_of=pd.Timestamp("2008-09-15"))
    obs = compute_crps(ctx)
    extra = obs.metadata_extra
    # Per AM12: surface via metadata_extra until 3.5D adds .notes field
    assert "pit_safe_basis_per_component" in extra
    sahm_basis = extra["pit_safe_basis_per_component"].get("sahm_rule")
    assert sahm_basis == "by_construction"
    assert extra.get("derived_confidence_cap_applied") == pytest.approx(0.70)
    assert any(
        "SAHMREALTIME" in n and "pit_safe_by_construction" in n
        for n in extra.get("pit_construction_notes", [])
    ), f"Construction caveat missing from notes: {extra.get('pit_construction_notes')}"


# ---------------------------------------------------------------------------
# 7. NEG — audit detects an injected mismatch
# ---------------------------------------------------------------------------
def test_pit_audit_detects_injected_mismatch(monkeypatch):
    """If a non-SAHM series has vintage=True but no panel + no flag,
    the audit must flag it."""
    from macro_pipeline import config
    from macro_pipeline.utils import pit_audit

    bad_spec = {
        "freq": "M", "vintage": True, "unit": "pct",
        "release_lag_days": 7,
        "description": "fake unflagged vintage",
    }
    fake_api = {**config.FRED_SERIES_API, "TEST_UNFLAGGED": bad_spec}
    monkeypatch.setattr(pit_audit, "FRED_SERIES_API", fake_api)
    report = pit_audit.audit_pit_contracts()
    assert any(m.series_id == "TEST_UNFLAGGED" for m in report.mismatches), \
        f"Expected TEST_UNFLAGGED in mismatches, got {[m.series_id for m in report.mismatches]}"
    assert report.total_violations >= 1


# ---------------------------------------------------------------------------
# 8. NEG — aggregate_caps MIN is invariant to None derived cap
# ---------------------------------------------------------------------------
def test_aggregate_caps_min_includes_derived_cap():
    """``aggregate_caps`` must:
    (a) ignore None entries — adding None must not change the MIN;
    (b) include the derived cap when it is the binding factor.
    """
    # (a) None invariance
    assert aggregate_caps(0.85, 0.75, None) == pytest.approx(0.75)
    assert aggregate_caps(0.85, None, 0.75) == pytest.approx(0.75)
    # (b) derived cap binds when it is the smallest
    assert aggregate_caps(0.85, 0.75, 0.70) == pytest.approx(0.70)
    # (c) all None → 1.0 (no-op cap)
    assert aggregate_caps(None, None) == 1.0
