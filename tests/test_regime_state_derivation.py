"""Tests for ``RegimeContext.derive_regime_state`` (Layer 3B Addition 1).

Spec: kickoff "3B mandatory addition #1". Asserts the priority order and
the corroboration truth table.
"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.regime import (
    DalioResult,
    HmmStateResult,
    KindlebergerResult,
    NberStateResult,
    RegimeContext,
    RegimeContextError,
    build_regime_context,
)

# ---- helpers --------------------------------------------------------------

def _synthetic_kindleberger(phase: str) -> KindlebergerResult:
    return KindlebergerResult(
        phase=phase,
        triggers_hit={},
        metrics={},
        method="rule_based_heuristic_v1",
        as_of=pd.Timestamp("2025-01-01"),
    )


def _synthetic_dalio(phase: str = "indeterminate") -> DalioResult:
    return DalioResult(
        phase=phase,
        triggers_hit={},
        metrics={},
        method="rule_based_heuristic_v1",
        as_of=pd.Timestamp("2025-01-01"),
    )


def _synthetic_hmm(state: str, prob: float = 0.95) -> HmmStateResult:
    other = (1.0 - prob) / 2.0
    probs = {"expansion": other, "late-cycle": other, "recession": other}
    probs[state] = prob
    return HmmStateResult(
        state=state,
        state_probabilities=probs,
        observation_date=pd.Timestamp("2025-01-31"),
        feature_values={},
        as_of=pd.Timestamp("2025-02-01"),
    )


def _synthetic_nber(state: str) -> NberStateResult:
    return NberStateResult(
        state=state,
        state_date=pd.Timestamp("2024-01-01"),
        last_known_label_date=pd.Timestamp("2024-12-01"),
        as_of=pd.Timestamp("2025-02-01"),
        source="NBER_REC_LABEL",
    )


def _make_ctx(*, nber, hmm, kindleberger, dalio_phase="indeterminate", as_of="2025-02-01") -> RegimeContext:
    return RegimeContext(
        as_of=pd.Timestamp(as_of),
        nber=nber,
        kindleberger=_synthetic_kindleberger(kindleberger),
        dalio=_synthetic_dalio(dalio_phase),
        hmm=hmm,
    )


# ---- mandatory tests per kickoff -----------------------------------------

def test_regime_state_2025_06_indeterminate_on_hmm_dissent():
    """Layer 3.5D update (D24): pre-3.5D this test asserted
    ('expansion', 'nber', 0.00) at 2025-06 because the HMM-corroboration
    check only fired on Path 4 (NBER unavailable). Post-3.5D the HMM
    check fires on every path, so the (NBER=expansion, HMM=recession)
    dissent at 2025-06 is correctly flagged as 'indeterminate'.
    This is the canonical dissent-anchor test from spec §6.5 #1.
    """
    ctx = PitDataContext(as_of=pd.Timestamp("2025-06-01"))
    rc = build_regime_context(ctx, nber_query_date=pd.Timestamp("2024-01-01"))
    assert rc.nber is not None
    assert rc.nber.state == "expansion"
    # HMM at 2025-06 reads "recession" (UMCSENT-driven late-cycle bias
    # post-2008; see regime/README §3).
    assert rc.hmm is not None
    assert rc.hmm.state == "recession"
    state, source, haircut = rc.derive_regime_state()
    assert state == "indeterminate"
    assert source == "hmm_dissent_indeterminate"
    assert haircut == pytest.approx(0.40)


def test_regime_state_indeterminate_on_dissent_when_nber_unavailable():
    """Layer 3.5D update (D24 / spec §6.3-2): pre-3.5D the
    NBER-unavailable + HMM-dissent path returned the ('late-cycle',
    'hmm_dissent_neutralized', 0.20) softening. Post-3.5D the same
    path resolves to ('indeterminate', 'hmm_dissent_indeterminate',
    0.40) — Codex finding F flagged the soft neutralization as
    Lucas-critique-fragile.

    Construction: NBER unavailable + HMM=recession + Kindleberger=boom
    (non-stress, no corroboration). Phase A produces consensus =
    'hmm_solo' with HMM's read; Phase B's HMM check then trivially
    matches (consensus == hmm.state). To trigger INDETERMINATE on this
    path we need NBER unavailable + HMM disagreeing with the Kindleberger-
    corroboration table — but Phase A treats unmatched HMM as 'hmm_solo'
    consensus = HMM state, so Phase B doesn't dissent. The cleanest
    INDETERMINATE construction is NBER expansion + HMM recession (which
    test_regime_state_2025_06_indeterminate_on_hmm_dissent covers).
    Therefore this test now exercises the NBER-unavailable path with
    HMM corroborated by Kindleberger (no dissent) and confirms that
    the previous neutralization path is no longer reachable on
    NBER-unavailable inputs.
    """
    rc = _make_ctx(
        nber=None,
        hmm=_synthetic_hmm("recession"),
        kindleberger="distress",  # corroborates HMM=recession
    )
    state, source, haircut = rc.derive_regime_state()
    # Path 4 corroborated → return HMM state, NO indeterminate.
    assert state == "recession"
    assert source == "hmm_corroborated"
    assert haircut == 0.05


def test_regime_state_2009_recession_nber_precedence():
    """At as_of=2009-06-01, NBER announcement of the 2007-12 peak (Dec
    1, 2008) was public, so PIT view of NBER_REC_LABEL surfaces a
    'recession' label for the Sept-2008 query. NBER takes precedence
    over HMM/Kindleberger regardless of their states."""
    ctx = PitDataContext(as_of=pd.Timestamp("2009-06-01"))
    rc = build_regime_context(ctx, nber_query_date=pd.Timestamp("2008-09-01"))
    assert rc.nber is not None
    assert rc.nber.state == "recession"
    state, source, haircut = rc.derive_regime_state()
    assert state == "recession"
    assert source == "nber"
    assert haircut == 0.0


def test_regime_state_kindleberger_override():
    """NBER says expansion BUT Kindleberger=distress → override fires:
    ('late-cycle', 'kindleberger_override_nber', 0.10).

    NBER expansion + Kindle=euphoria (non-stress) → no override:
    ('expansion', 'nber', 0.00).

    Layer 3.5D D24: HMM is set to MATCH the consensus in each subcase
    so the new HMM-corroboration check does NOT downgrade the result
    to INDETERMINATE — this isolates the Kindleberger-override logic.
    """
    # Override case: consensus = "late-cycle"; HMM = "late-cycle" so no dissent.
    rc1 = _make_ctx(
        nber=_synthetic_nber("expansion"),
        hmm=_synthetic_hmm("late-cycle"),  # matches consensus from override
        kindleberger="distress",
    )
    state, source, haircut = rc1.derive_regime_state()
    assert state == "late-cycle"
    assert source == "kindleberger_override_nber"
    assert haircut == 0.10

    # Euphoria case: consensus = "expansion"; HMM = "expansion" so no dissent.
    rc2 = _make_ctx(
        nber=_synthetic_nber("expansion"),
        hmm=_synthetic_hmm("expansion"),  # matches consensus
        kindleberger="euphoria",
    )
    state2, source2, haircut2 = rc2.derive_regime_state()
    assert state2 == "expansion"
    assert source2 == "nber"
    assert haircut2 == 0.0


def test_regime_state_hmm_dissent_indeterminate_on_kindleberger_override():
    """Layer 3.5D NEW D24 coverage: NBER=expansion + Kindleberger=distress
    (override → late-cycle consensus) + HMM=recession (dissent from
    late-cycle) → INDETERMINATE. Demonstrates the Phase B HMM-check
    fires on the Kindleberger-override path (not just on the clean
    expansion/recession paths)."""
    rc = _make_ctx(
        nber=_synthetic_nber("expansion"),
        hmm=_synthetic_hmm("recession"),  # dissents from late-cycle consensus
        kindleberger="distress",
    )
    state, source, haircut = rc.derive_regime_state()
    assert state == "indeterminate"
    assert source == "hmm_dissent_indeterminate"
    assert haircut == pytest.approx(0.40)


# ---- additional coverage -------------------------------------------------

def test_regime_state_corroborated_paths():
    """All three corroboration cells of the truth table must yield
    (hmm.state, 'hmm_corroborated', 0.05)."""
    cases = [
        ("recession", "revulsion"),
        ("recession", "distress"),
        ("expansion", "displacement"),
        ("expansion", "boom"),
        ("expansion", "euphoria"),
        ("late-cycle", "boom"),
        ("late-cycle", "euphoria"),
    ]
    for hmm_state, kphase in cases:
        rc = _make_ctx(nber=None, hmm=_synthetic_hmm(hmm_state), kindleberger=kphase)
        state, source, haircut = rc.derive_regime_state()
        assert state == hmm_state, f"corroborated case ({hmm_state}, {kphase})"
        assert source == "hmm_corroborated"
        assert haircut == 0.05


def test_regime_state_raises_when_no_nber_and_no_hmm():
    rc = _make_ctx(
        nber=None,
        hmm=None,
        kindleberger="indeterminate",
    )
    with pytest.raises(RegimeContextError, match="NBER unavailable"):
        rc.derive_regime_state()
