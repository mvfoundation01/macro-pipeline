"""Aggregator dataclass that bundles all 4 regime views (Layer 3A).

Spec: ``LAYER_3_BUILD_SPEC.md`` §4.

A ``RegimeContext`` is the universal "what regime are we in at as_of"
output that downstream Layer 3 components (CRPS, CDRS) consume. It
carries the four independently-computed views — NBER, Kindleberger,
Dalio, HMM — plus enough metadata to trace which inputs were used.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from macro_pipeline.access import PitDataContext
from macro_pipeline.regime.dalio_cycle import DalioResult, classify_dalio
from macro_pipeline.regime.exceptions import PitDataUnavailableError
from macro_pipeline.regime.hmm_states import HmmStateResult, predict_state
from macro_pipeline.regime.kindleberger import KindlebergerResult, classify_kindleberger
from macro_pipeline.regime.nber_extract import NberStateResult, extract_nber_state


@dataclass
class RegimeContext:
    """Aggregated regime view at one ``as_of``.

    Fields
    ------
    as_of
        The ``PitDataContext.as_of`` used to build this view.
    nber
        ``NberStateResult`` or ``None`` if NBER had not yet announced a
        label by ``as_of`` (``PitDataUnavailableError`` was raised).
    kindleberger / dalio / hmm
        Phase classifications. ``hmm`` may be ``None`` if the trained
        pickle is missing AND we have not been asked to train.
    notes
        Any per-component data-availability or methodology notes the
        sub-classifiers emitted.
    """

    as_of: pd.Timestamp
    nber: NberStateResult | None
    kindleberger: KindlebergerResult
    dalio: DalioResult
    hmm: HmmStateResult | None
    notes: list[str] = field(default_factory=list)

    @property
    def regime_state(self) -> str:
        """Convenience: prefer HMM state when available, else fall back."""
        if self.hmm is not None:
            return self.hmm.state
        if self.nber is not None:
            return self.nber.state
        return "unknown"

    @property
    def regime_phase_kindleberger(self) -> str:
        return self.kindleberger.phase

    @property
    def regime_phase_dalio(self) -> str:
        return self.dalio.phase


def build_regime_context(
    ctx: PitDataContext,
    *,
    nber_query_date: pd.Timestamp | None = None,
    skip_hmm: bool = False,
) -> RegimeContext:
    """Build a ``RegimeContext`` for ``ctx.as_of``.

    Parameters
    ----------
    ctx
        PIT-safe data context.
    nber_query_date
        Date to ask NBER about. Defaults to ``ctx.as_of``. Raising
        ``PitDataUnavailableError`` is converted into ``nber=None`` and
        a note — NBER may not have announced yet.
    skip_hmm
        Skip HMM prediction (e.g. in tests where the pickle is not
        intended to be built). Default False — we will load or train
        the pickle on demand.
    """
    notes: list[str] = []

    # NBER
    nber_q = pd.Timestamp(nber_query_date) if nber_query_date is not None else ctx.as_of
    nber_result: NberStateResult | None
    try:
        nber_result = extract_nber_state(nber_q, ctx=ctx)
    except PitDataUnavailableError as exc:
        nber_result = None
        notes.append(f"NBER: {exc}")

    # Kindleberger
    k = classify_kindleberger(ctx)
    notes.extend(f"kindleberger: {n}" for n in k.notes)

    # Dalio
    d = classify_dalio(ctx)
    notes.extend(f"dalio: {n}" for n in d.notes)

    # HMM
    hmm_result: HmmStateResult | None
    if skip_hmm:
        hmm_result = None
        notes.append("hmm: skipped (skip_hmm=True)")
    else:
        try:
            hmm_result = predict_state(ctx)
        except Exception as exc:
            hmm_result = None
            notes.append(f"hmm: {type(exc).__name__}: {exc}")

    return RegimeContext(
        as_of=ctx.as_of,
        nber=nber_result,
        kindleberger=k,
        dalio=d,
        hmm=hmm_result,
        notes=notes,
    )


__all__ = ["RegimeContext", "build_regime_context"]
