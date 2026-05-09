"""Tests for ``macro_pipeline.regime.regime_context`` (Layer 3A)."""
from __future__ import annotations

import pandas as pd

from macro_pipeline.access import PitDataContext
from macro_pipeline.regime import RegimeContext, build_regime_context


def test_regime_context_full_aggregation_modern_as_of() -> None:
    """At as_of=2025-06-01 every classifier has data. NBER for the as_of
    month itself is past the visibility horizon (release_lag_days=180)
    so we point it at a past date that is comfortably visible."""
    ctx = PitDataContext(as_of=pd.Timestamp("2025-06-01"))
    rc = build_regime_context(ctx, nber_query_date=pd.Timestamp("2024-01-01"))
    assert isinstance(rc, RegimeContext)
    assert rc.as_of == pd.Timestamp("2025-06-01")
    assert rc.nber is not None
    assert rc.nber.state == "expansion"
    assert rc.kindleberger is not None
    assert rc.dalio is not None
    assert rc.dalio.phase == "late"
    assert rc.hmm is not None
    assert rc.hmm.state in ("expansion", "late-cycle", "recession")


def test_regime_context_partial_at_2008_09() -> None:
    """At as_of=2008-09-15, NBER refuses to label (announcement delay)
    and the FRED + HLW vintage panels are unusable, so dalio is
    indeterminate. HMM and Kindleberger should still work."""
    ctx = PitDataContext(as_of=pd.Timestamp("2008-09-15"))
    rc = build_regime_context(ctx)
    assert rc.nber is None
    assert any("NBER" in n for n in rc.notes)
    assert rc.kindleberger is not None
    assert rc.dalio.phase == "indeterminate"
    assert rc.hmm is not None
    assert rc.hmm.state == "recession"


def test_regime_context_skip_hmm_yields_none_hmm() -> None:
    ctx = PitDataContext(as_of=pd.Timestamp("2025-06-01"))
    rc = build_regime_context(ctx, skip_hmm=True)
    assert rc.hmm is None
    assert any("hmm" in n.lower() for n in rc.notes)


def test_regime_context_convenience_properties() -> None:
    ctx = PitDataContext(as_of=pd.Timestamp("2025-06-01"))
    rc = build_regime_context(ctx)
    assert rc.regime_state in ("expansion", "late-cycle", "recession", "unknown")
    assert isinstance(rc.regime_phase_kindleberger, str)
    assert isinstance(rc.regime_phase_dalio, str)


def test_regime_context_explicit_nber_query_date() -> None:
    """Caller can override NBER query date independently of ctx.as_of."""
    ctx = PitDataContext(as_of=pd.Timestamp("2025-06-01"))
    rc = build_regime_context(ctx, nber_query_date=pd.Timestamp("2008-09-01"))
    assert rc.nber is not None
    assert rc.nber.state == "recession"
