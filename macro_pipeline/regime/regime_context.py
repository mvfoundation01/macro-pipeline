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
from macro_pipeline.regime.exceptions import (
    PitDataUnavailableError,
    RegimeContextError,
)
from macro_pipeline.regime.hmm_states import HmmStateResult, predict_state
from macro_pipeline.regime.kindleberger import KindlebergerResult, classify_kindleberger
from macro_pipeline.regime.nber_extract import NberStateResult, extract_nber_state

# Kindleberger phase sets used by ``derive_regime_state`` (Layer 3B).
# The trigger sets are deliberate: HMM=recession is corroborated only
# when Kindleberger flags real stress (distress/revulsion); HMM=expansion
# is corroborated by any non-stress Kindleberger phase including
# euphoria (a market top is still an "expansion-like" regime from a
# CRPS standpoint until stress shows up); HMM=late-cycle pairs with
# the late-cycle Kindleberger phases (boom/euphoria).
_KINDLEBERGER_STRESS = frozenset({"distress", "revulsion"})
_KINDLEBERGER_NON_STRESS = frozenset({"displacement", "boom", "euphoria"})
_KINDLEBERGER_LATE = frozenset({"boom", "euphoria"})


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
        """Convenience: prefer HMM state when available, else fall back.

        For backtest scoring, callers should use
        :meth:`derive_regime_state` instead — it implements the
        priority order required by Layer 3B (NBER first, with
        Kindleberger override and HMM-dissent neutralization)."""
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

    def derive_regime_state(self) -> tuple[str, str, float]:
        """Resolve a single ``regime_state`` label for downstream scoring.

        Returns
        -------
        (regime_state, source, confidence_haircut)
            ``regime_state``        ∈ {"expansion", "late-cycle", "recession"}
            ``source``              tag identifying which view drove the call
            ``confidence_haircut``  amount in [0, 1] to subtract from the
                                    ``regime_stability`` input of
                                    ``confidence_score_v2`` to reflect
                                    classifier disagreement.

        Priority order (Layer 3B kickoff):

        1. NBER recession                                       → ("recession", "nber", 0.00)
        2. NBER expansion + Kindleberger ∈ {distress, revulsion}
           → ("late-cycle", "kindleberger_override_nber", 0.10)
        3. NBER expansion                                       → ("expansion", "nber", 0.00)
        4. NBER unavailable (PIT-raised at as_of):
           a. HMM corroborated by Kindleberger (truth table below)
              → (hmm.state, "hmm_corroborated", 0.05)
           b. HMM dissents from Kindleberger
              → ("late-cycle", "hmm_dissent_neutralized", 0.20)
        5. No NBER and no HMM                                   → raise RegimeContextError

        Corroboration truth table (HMM ↔ Kindleberger):

        | HMM         | Kindleberger ∈                      | Corroborated? |
        |-------------|--------------------------------------|---------------|
        | recession   | {distress, revulsion}                | ✓             |
        | expansion   | {displacement, boom, euphoria}       | ✓             |
        | late-cycle  | {boom, euphoria}                     | ✓             |
        | otherwise                                              dissent       |

        The neutralization rule (4b) exists because the HMM v1 has a
        known UMCSENT-driven false-recession bias post-2020. When NBER
        cannot be consulted (e.g. a recent as_of past the 180d release
        lag) and Kindleberger disagrees with the HMM, we refuse to
        commit to either label and fall back to "late-cycle" with a
        20% confidence haircut.
        """
        # Path 1-3: NBER is authoritative when it speaks.
        if self.nber is not None:
            if self.nber.state == "recession":
                return ("recession", "nber", 0.00)
            # NBER says expansion — but Kindleberger stress overrides.
            if self.kindleberger.phase in _KINDLEBERGER_STRESS:
                return ("late-cycle", "kindleberger_override_nber", 0.10)
            return ("expansion", "nber", 0.00)

        # Path 4: NBER unavailable. Need at least HMM to proceed.
        if self.hmm is None:
            raise RegimeContextError(
                reason=(
                    "Cannot derive regime state: NBER unavailable at "
                    f"as_of={self.as_of.date() if self.as_of is not None else None} "
                    "and HMM also missing (e.g. as_of < 1982-01 or pickle "
                    "load failed). Inspect RegimeContext.notes for details."
                ),
                context={
                    "as_of": str(self.as_of) if self.as_of is not None else None,
                    "kindleberger_phase": self.kindleberger.phase,
                    "dalio_phase": self.dalio.phase,
                },
            )

        hmm_state = self.hmm.state
        kphase = self.kindleberger.phase
        corroborated = (
            (hmm_state == "recession" and kphase in _KINDLEBERGER_STRESS)
            or (hmm_state == "expansion" and kphase in _KINDLEBERGER_NON_STRESS)
            or (hmm_state == "late-cycle" and kphase in _KINDLEBERGER_LATE)
        )
        if corroborated:
            return (hmm_state, "hmm_corroborated", 0.05)
        return ("late-cycle", "hmm_dissent_neutralized", 0.20)


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
