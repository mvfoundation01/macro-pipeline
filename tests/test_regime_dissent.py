"""Tests for Layer 3.5D HMM-dissent → INDETERMINATE contract.

Per ``LAYER_3_5_BUILD_SPEC.md`` §6.5 + spec §6.6 (Gate 15).

Negative / positive split for this file: 1 NEG / 3 POS. Combined with
``test_scored_observation_rename.py`` (3 NEG / 1 POS) the 3.5D test
delta is 4 NEG / 4 POS = 50% — satisfies standing-orders §2.7 floor.
"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.regime import (
    INDETERMINATE_CONFIDENCE_CAP,
    RegimeState,
    build_regime_context,
)
from macro_pipeline.scoring.cdrs import (
    _resolve_r_multiplier,
    compute_cdrs,
)
from macro_pipeline.scoring.crps import compute_crps
from macro_pipeline.scoring.scored_observation import CompositeBuildError


# ---------------------------------------------------------------------------
# 1. POS — HMM dissent at 2025-06 yields INDETERMINATE
# ---------------------------------------------------------------------------
def test_hmm_dissent_returns_indeterminate():
    """At 2025-06-01 the HMM v1 reads 'recession' while
    NBER+Kindleberger consensus is 'expansion' (HMM has a known
    UMCSENT-driven late-cycle bias post-2008 — see regime/README §3).
    Per spec §6.3-2 + Decision Lock 3.5D-D1, derive_regime_state must
    return ('indeterminate', 'hmm_dissent_indeterminate', 0.40).
    """
    ctx = PitDataContext(as_of=pd.Timestamp("2025-06-01"))
    rc = build_regime_context(ctx)
    state, source, haircut = rc.derive_regime_state()
    assert state == RegimeState.INDETERMINATE.value
    assert source == "hmm_dissent_indeterminate"
    assert haircut == pytest.approx(0.40)


# ---------------------------------------------------------------------------
# 2. POS — INDETERMINATE caps confidence at 0.60 across CRPS + CDRS
# ---------------------------------------------------------------------------
def test_indeterminate_caps_confidence_60():
    ctx = PitDataContext(as_of=pd.Timestamp("2025-06-01"))
    crps = compute_crps(ctx)
    cdrs = compute_cdrs(ctx)
    cap_pct = INDETERMINATE_CONFIDENCE_CAP * 100.0
    assert crps.confidence <= cap_pct + 1e-6
    assert cdrs.confidence <= cap_pct + 1e-6
    # Both should be FLAGGED with the dissent rationale in notes.
    assert any("indeterminate" in n.lower() for n in crps.notes)
    assert any("indeterminate" in n.lower() for n in cdrs.notes)


# ---------------------------------------------------------------------------
# 3. POS — CDRS R for INDETERMINATE comes from consensus state (AM21=B)
# ---------------------------------------------------------------------------
def test_cdrs_indeterminate_R_from_consensus_state():
    """Spec §6.4-D2 alternative #3 (locked at Decision Lock 3.5D-D2 /
    AM21=B): when regime_state == "indeterminate", the R multiplier
    is taken from the **consensus** state (NBER+Kindleberger), not a
    hard-coded 1.0. This orthogonalizes sizing (R) from uncertainty
    signal (the 0.60 confidence cap, applied separately).
    """
    # 2025-06: consensus = expansion → R = 0.6
    cdrs_25 = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2025-06-01")))
    assert cdrs_25.regime_state == RegimeState.INDETERMINATE.value
    assert cdrs_25.metadata_extra["R_multiplier"] == pytest.approx(0.6)

    # 2008-09: consensus = late-cycle (Kindleberger=revulsion override) → R = 1.0
    cdrs_08 = compute_cdrs(PitDataContext(as_of=pd.Timestamp("2008-09-15")))
    assert cdrs_08.regime_state == RegimeState.INDETERMINATE.value
    assert cdrs_08.metadata_extra["R_multiplier"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 4. NEG — _resolve_r_multiplier requires regime_ctx for INDETERMINATE
# ---------------------------------------------------------------------------
def test_resolve_r_multiplier_indeterminate_requires_regime_ctx():
    """If a caller passes state='indeterminate' but no regime_ctx, the
    consensus is unrecoverable → CompositeBuildError. Defends against
    stale callers that haven't been updated to pass the context."""
    with pytest.raises(CompositeBuildError, match="indeterminate"):
        _resolve_r_multiplier("indeterminate", "hmm_dissent_indeterminate")
