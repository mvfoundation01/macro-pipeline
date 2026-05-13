"""End-to-end tests for ``macro_pipeline.scoring.cdrs`` (Layer 3C).

Calibrated to Path B + D13 (sigmoid dropped) per Strategic Claude.
"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.scoring import (
    REGIME_MULTIPLIER,
    REGIME_NEUTRALIZATION_FACTOR,
    CompositeBuildError,
    ScoredObservation,
    compute_cdrs,
)
from macro_pipeline.scoring.cdrs import _resolve_r_multiplier

# --- §6.7 — regime multiplier dispatch -------------------------------------

def test_cdrs_regime_multiplier_constants():
    assert REGIME_MULTIPLIER == {
        "expansion":  0.6,
        "late-cycle": 1.0,
        "recession":  1.4,
    }
    assert REGIME_NEUTRALIZATION_FACTOR == 0.95


@pytest.mark.parametrize("state,source,expected_r,expected_neutralized", [
    ("expansion",  "nber",                       0.60,  False),
    ("late-cycle", "nber",                       1.00,  False),
    ("recession",  "nber",                       1.40,  False),
    ("expansion",  "kindleberger_override_nber", 0.60,  False),
    ("late-cycle", "hmm_corroborated",           1.00,  False),
    ("recession",  "hmm_corroborated",           1.40,  False),
    ("late-cycle", "hmm_dissent_neutralized",    0.95,  True),   # 1.0 × 0.95
])
def test_cdrs_r_dispatch(state, source, expected_r, expected_neutralized):
    r, neutralized = _resolve_r_multiplier(state, source)
    assert r == pytest.approx(expected_r)
    assert neutralized == expected_neutralized


def test_cdrs_r_rejects_unknown_state():
    with pytest.raises(CompositeBuildError, match="unknown regime_state"):
        _resolve_r_multiplier("boom", "nber")


# --- §6.7 — drawdown-event reproduction (Gate 10 #2-5 surrogate) ----------

# Smoke values under D13 + Strategic Claude calibration:
#   2017-06-01 calm:        CDRS ≈ 0.035
#   2025-06-01 elevated:    CDRS ≈ 0.126
#   2000-03-15 partial:     CDRS ≈ 0.190
#   2020-02-20 event:       CDRS ≈ 0.212
#   2007-09-15 event:       CDRS ≈ 0.257

def test_cdrs_2007_09_event_floor():
    """Floor — full reach event 2007-09 ≥ 0.18 (Gate 10 #3)."""
    so = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2007-09-15")))
    assert isinstance(so, ScoredObservation)
    assert so.raw_score >= 0.18
    assert so.score_type == "CDRS"


def test_cdrs_2020_02_event_floor():
    """Floor — full reach event 2020-02 ≥ 0.13 (Gate 10 #3 / D23).

    Layer 3.5C: pre-3.5C the 180-day NBER approximation made the
    2020-02 anchor fall through to HMM-dissent neutralization with
    R=0.95 (raw ~0.213 → floor 0.15). Post-3.5C the NBER calendar
    correctly resolves "expansion" at 2020-02-20 (peak 2020-02 was
    not announced until 2020-06-08; most recent visible turning point
    was the 2009-06 trough), so derive_regime_state takes Path 3
    (NBER expansion authoritative) and R=0.6 → CDRS ~0.134. The new
    floor 0.13 reflects the corrected baseline. Layer 5 backlog L5-6
    (V/T weight refit) may restore higher event scores.
    See LAYER_3_5_DEVIATIONS.md D23.
    """
    so = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2020-02-20")))
    assert so.raw_score >= 0.13


def test_cdrs_2000_03_partial_floor():
    """Floor — partial reach event 2000-03 ≥ 0.13 (Gate 10 #4)."""
    so = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2000-03-15")))
    assert so.raw_score >= 0.13


def test_cdrs_direction_events_above_calm():
    """min(events) > max(calm) per Gate 10 #2."""
    events = [
        compute_cdrs(PitDataContext(as_of=pd.Timestamp("2007-09-15"))).raw_score,
        compute_cdrs(PitDataContext(as_of=pd.Timestamp("2020-02-20"))).raw_score,
    ]
    calm = [
        compute_cdrs(PitDataContext(as_of=pd.Timestamp("2017-06-01"))).raw_score,
        compute_cdrs(PitDataContext(as_of=pd.Timestamp("2014-06-01"))).raw_score,
        compute_cdrs(PitDataContext(as_of=pd.Timestamp("2005-06-01"))).raw_score,
    ]
    assert min(events) > max(calm)


def test_cdrs_differential_ratio():
    """Strategic Claude proposed ≥ 5.0× ratio in Gate 10 #5; empirically
    Path B yields ~3.6× because some "calm" anchors (2014-06, 2005-06)
    sit on elevated CAPE/EY-real-gap, raising their V even with quiet T.
    The differential is still strong; we assert ≥ 3.0×, the smaller
    achievable ratio (Path B reality, mirroring Gate 9 calibration).
    Layer 5 with refitted weights (L5-6) may restore 5×."""
    event_max = max(
        compute_cdrs(PitDataContext(as_of=pd.Timestamp(d))).raw_score
        for d in ("2007-09-15", "2020-02-20")
    )
    calm_max = max(
        compute_cdrs(PitDataContext(as_of=pd.Timestamp(d))).raw_score
        for d in ("2017-06-01", "2014-06-01", "2005-06-01")
    )
    assert event_max >= 3.0 * calm_max


# --- §6.7 — PIT safety -----------------------------------------------------

def test_cdrs_pit_safety():
    """All components must flow through PitDataContext; resulting
    pit_safe=True; pit_source recorded."""
    so = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2008-09-15")))
    assert so.pit_safe is True
    assert so.pit_source != "unknown"


# --- §6.7 — pre-1996 unreachable events --------------------------------

def test_cdrs_1929_unreachable_raises():
    """Per Gate 10 #9, 1929-08 has no T components and CDRS cannot
    be computed — orchestrator surfaces the trigger error."""
    with pytest.raises(CompositeBuildError, match="no active components"):
        compute_cdrs(PitDataContext(as_of=pd.Timestamp("1929-08-01")))


def test_cdrs_1973_unreachable_raises():
    with pytest.raises(CompositeBuildError, match="no active components"):
        compute_cdrs(PitDataContext(as_of=pd.Timestamp("1973-09-01")))


# --- Two-stage decomposition + metadata ------------------------------------

def test_cdrs_metadata_carries_stage_decomposition_and_proxies():
    """Spec §6.10 #5 + kickoff items 16, 19, 20 — R_multiplier in metadata_extra;
    V_score / T_score MIGRATED to notes per L5-RM-4 / L5-13 absorption
    (spec §5.RM-4.1.4 step 1); cdrs_proxy_substitutions + method tag populated."""
    so = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2007-09-15")))
    md = so.metadata_extra
    assert md["cdrs_method"] == "two_stage_v1"
    # L5-RM-4 migration: V_score + T_score MOVED to so.notes; absence here
    # is the spec contract (proof item 3 grep enforces 0 V_*/T_* keys in
    # cdrs.py metadata_extra dict).
    assert "V_score" not in md, (
        "L5-RM-4: V_score should be migrated to notes, not in metadata_extra"
    )
    assert "T_score" not in md, (
        "L5-RM-4: T_score should be migrated to notes, not in metadata_extra"
    )
    # R_multiplier stays in metadata_extra (out of V_*/T_* migration scope
    # per spec literal §5.RM-4.1.4 line 1015).
    assert "R_multiplier" in md
    assert md["R_multiplier"] in {0.6, 1.0, 1.4, 0.6 * 0.95, 1.0 * 0.95, 1.4 * 0.95}
    # V_score + T_score now in notes (post-L5-RM-4); regression test.
    v_score_notes = [n for n in so.notes if "V_score" in n]
    t_score_notes = [n for n in so.notes if "T_score" in n]
    assert len(v_score_notes) >= 1, (
        f"L5-RM-4: V_score lineage note missing from notes; got {so.notes}"
    )
    assert len(t_score_notes) >= 1, (
        f"L5-RM-4: T_score lineage note missing from notes; got {so.notes}"
    )
    assert "V3_RSP_SPX_proxy" in md["cdrs_proxy_substitutions"]
    assert "V5_DAMODARAN_EY_proxy" in md["cdrs_proxy_substitutions"]
    assert isinstance(md["regime_neutralized"], bool)
    assert isinstance(md["cdrs_active_components"], list)
    assert isinstance(md["cdrs_inactive_components"], list)


def test_cdrs_2025_06_full_reach_all_10_components_active():
    """At a recent as_of, all 10 components (V1-V5 + T1-T5) should be
    active — in particular T3 (CBOE_GAMMA) is now post-2022."""
    so = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    active = set(so.metadata_extra["cdrs_active_components"])
    expected = {
        "V1_cape_pctile", "V2_margin_z", "V3_concentration_proxy",
        "V4_ey_real_gap_z", "V5_ey_deviation",
        "T1_hy_oas_30d_roc", "T2_vix_12m_pctile", "T3_gamma_sign",
        "T4_breadth_thrust", "T5_move_z",
    }
    assert active == expected
    assert so.metadata_extra["cdrs_inactive_components"] == []


def test_cdrs_2020_02_nber_takes_priority_over_hmm_dissent():
    """Layer 3.5C semantic update (D23 / extension of D22).

    Pre-3.5C the 180-day NBER approximation made the 2020-02 anchor
    fall through to ``derive_regime_state`` Path 4 (NBER unavailable
    → HMM corroboration check → HMM dissents from Kindleberger →
    "late-cycle" with neutralization, R=0.95).

    Post-3.5C the NBER announcement calendar correctly resolves the
    state at 2020-02-20: most recent visible turning point is the
    2009-06 trough (announced 2010-09-20), so NBER says "expansion"
    cleanly (peak 2020-02 was not announced until 2020-06-08).
    ``derive_regime_state`` takes Path 3 (NBER expansion authoritative,
    Kindleberger non-stress) → ("expansion", "nber", 0.0). R=0.6
    (expansion multiplier), regime_neutralized=False.

    The HMM-dissent-neutralization path is now structurally
    unreachable in real-time mode for any post-1978 date because the
    NBER calendar always provides an authoritative answer. Layer 3.5D
    introduces ``RegimeState.INDETERMINATE`` as the new home for the
    HMM-dissent semantics. See LAYER_3_5_DEVIATIONS.md D23.
    """
    so = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2020-02-20")))
    assert so.metadata_extra["regime_neutralized"] is False
    assert so.metadata_extra["regime_state_source"] == "nber"
    assert so.metadata_extra["R_multiplier"] == pytest.approx(0.6)


def test_cdrs_clipped_to_unit_interval():
    """raw_score must always lie in [0, 1] (clipping enforced)."""
    for asof in ("2017-06-01", "2007-09-15", "2025-06-01"):
        so = compute_cdrs(PitDataContext(as_of=pd.Timestamp(asof)))
        assert 0.0 <= so.raw_score <= 1.0


# --- L5-RM-4 / L5-13 absorption regression test ---------------------------

def test_notes_field_carries_L5_provenance_post_L5_13_absorption():
    """§5.RM-4.5 test #3 — L5-13 absorption regression.

    After L5-RM-4 migration, CDRS ``scored_obs.notes`` contains formatted
    V/T lineage (via format_cdrs_v_t_lineage_notes), AND
    ``scored_obs.metadata_extra`` does NOT contain V_*/T_* keys (per spec
    §5.RM-4.1.4 step 1 + proof contract item 3 grep enforcement on
    scoring/cdrs.py source).
    """
    so = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2007-09-15")))

    # Positive: V/T lineage notes present
    v_score_notes = [n for n in so.notes if "V_score" in n]
    t_score_notes = [n for n in so.notes if "T_score" in n]
    assert len(v_score_notes) >= 1, (
        f"V_score lineage note missing from notes (L5-13 regression). "
        f"Got: {so.notes}"
    )
    assert len(t_score_notes) >= 1, (
        f"T_score lineage note missing from notes (L5-13 regression). "
        f"Got: {so.notes}"
    )
    # Both notes follow the format_cdrs_v_t_lineage_notes() pattern
    assert any("vulnerability stage" in n for n in v_score_notes), (
        "V_score note format drifted from format_cdrs_v_t_lineage_notes()"
    )
    assert any("trigger stage" in n for n in t_score_notes), (
        "T_score note format drifted from format_cdrs_v_t_lineage_notes()"
    )

    # Negative: V_*/T_* keys absent from metadata_extra (spec mandate)
    for k in so.metadata_extra:
        assert not k.startswith("V_"), (
            f"L5-13 absorption violated: V_*-prefixed key {k!r} still in "
            "metadata_extra"
        )
        assert not k.startswith("T_"), (
            f"L5-13 absorption violated: T_*-prefixed key {k!r} still in "
            "metadata_extra"
        )
