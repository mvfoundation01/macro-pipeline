"""Aggregator dataclass that bundles all 4 regime views (Layer 3A;
extended at L3.5D for HMM-dissent → INDETERMINATE).

Spec: ``LAYER_3_BUILD_SPEC.md`` §4 + ``LAYER_3_5_BUILD_SPEC.md`` §6.

A ``RegimeContext`` is the universal "what regime are we in at as_of"
output that downstream Layer 3 components (CRPS, CDRS) consume. It
carries the four independently-computed views — NBER, Kindleberger,
Dalio, HMM — plus enough metadata to trace which inputs were used.

Layer 3.5D adds:
- ``RegimeState(str, Enum)`` with EXPANSION / LATE_CYCLE / RECESSION /
  INDETERMINATE (NEW). The enum values are strings, so any caller
  comparing ``regime_state == "indeterminate"`` continues to work.
- ``derive_regime_state`` now performs an HMM-corroboration check on
  every path (not just when NBER is unavailable). When HMM dissents
  from the consensus state, return ``("indeterminate",
  "hmm_dissent_indeterminate", 0.40)``. CRPS / CDRS callers cap
  confidence at 0.60 when ``regime_state == "indeterminate"``. Per
  Decision Lock 3.5D-D2 / AM21 = B, the **R-multiplier in CDRS uses
  the consensus state's R**, not a hard-coded 1.0 (orthogonalizes
  sizing from uncertainty signal).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

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


class RegimeState(str, Enum):
    """Enumeration of regime-state labels (Layer 3.5D).

    Values are strings to preserve backward compatibility with the
    pre-L3.5D ``regime_state: str`` field on ``ScoredObservation``.
    """

    EXPANSION = "expansion"
    LATE_CYCLE = "late-cycle"
    RECESSION = "recession"
    INDETERMINATE = "indeterminate"


# Layer 3.5D: confidence cap when regime_state==INDETERMINATE.
INDETERMINATE_CONFIDENCE_CAP: float = 0.60
# Haircut applied to ``regime_stability`` confidence input in
# ``derive_regime_state`` when the HMM dissents from consensus.
INDETERMINATE_CONFIDENCE_HAIRCUT: float = 0.40


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
            ``regime_state``        ∈ {"expansion", "late-cycle",
                                       "recession", "indeterminate"}
            ``source``              tag identifying which view drove the call
            ``confidence_haircut``  amount in [0, 1] to subtract from the
                                    ``regime_stability`` input of
                                    ``confidence_score_v2`` to reflect
                                    classifier disagreement.

        Priority order (Layer 3.5D refactor of Layer 3B logic):

        1. NBER recession  → consensus = "recession", source = "nber"
        2. NBER expansion + Kindleberger ∈ {distress, revulsion}
                           → consensus = "late-cycle",
                             source = "kindleberger_override_nber"
        3. NBER expansion  → consensus = "expansion", source = "nber"
        4. NBER unavailable + HMM corroborated by Kindleberger
                           → consensus = hmm.state,
                             source = "hmm_corroborated"
        5. NBER unavailable + HMM available but dissents from
           Kindleberger (post-3.5C: structurally unreachable in
           real-time mode for post-1978 dates because the calendar
           always provides an authoritative answer; but reachable for
           pre-1978 training mode)
                           → consensus = hmm.state, source =
                             "hmm_solo" (no neutralization here;
                             dissent surfacing happens below)
        6. No NBER and no HMM → raise ``RegimeContextError``.

        Layer 3.5D HMM-corroboration check on the consensus
        =================================================

        After computing the consensus per (1)–(5), if HMM is available
        AND ``hmm.state != consensus`` we return INDETERMINATE with a
        0.40 confidence haircut and let the caller cap the headline
        confidence at ``INDETERMINATE_CONFIDENCE_CAP`` (0.60). This
        replaces Layer 3B's "late-cycle ×0.95 neutralization" — Codex
        finding F flagged the prior path as too soft and ChatGPT Dim 2
        flagged it as Lucas-critique-fragile.

        Corroboration truth table (HMM ↔ Kindleberger), still used in
        Path 4 above:

        | HMM         | Kindleberger ∈                      | Corroborated? |
        |-------------|--------------------------------------|---------------|
        | recession   | {distress, revulsion}                | ✓             |
        | expansion   | {displacement, boom, euphoria}       | ✓             |
        | late-cycle  | {boom, euphoria}                     | ✓             |
        | otherwise                                              dissent       |
        """
        # ----- Phase A: compute consensus from NBER + Kindleberger + HMM-fallback -----
        consensus_state: str
        consensus_source: str
        consensus_haircut: float

        if self.nber is not None:
            if self.nber.state == "recession":
                consensus_state, consensus_source, consensus_haircut = (
                    "recession", "nber", 0.00,
                )
            elif self.kindleberger.phase in _KINDLEBERGER_STRESS:
                consensus_state, consensus_source, consensus_haircut = (
                    "late-cycle", "kindleberger_override_nber", 0.10,
                )
            else:
                consensus_state, consensus_source, consensus_haircut = (
                    "expansion", "nber", 0.00,
                )
        else:
            # NBER unavailable: HMM is the fallback authority (if present).
            if self.hmm is None:
                raise RegimeContextError(
                    reason=(
                        "Cannot derive regime state: NBER unavailable at "
                        f"as_of={self.as_of.date() if self.as_of is not None else None} "
                        "and HMM also missing (e.g. as_of < 1982-01 or "
                        "pickle load failed). Inspect RegimeContext.notes "
                        "for details."
                    ),
                    context={
                        "as_of": str(self.as_of) if self.as_of is not None else None,
                        "kindleberger_phase": self.kindleberger.phase,
                        "dalio_phase": self.dalio.phase,
                    },
                )
            kphase = self.kindleberger.phase
            hmm_state = self.hmm.state
            corroborated = (
                (hmm_state == "recession" and kphase in _KINDLEBERGER_STRESS)
                or (hmm_state == "expansion" and kphase in _KINDLEBERGER_NON_STRESS)
                or (hmm_state == "late-cycle" and kphase in _KINDLEBERGER_LATE)
            )
            if corroborated:
                consensus_state, consensus_source, consensus_haircut = (
                    hmm_state, "hmm_corroborated", 0.05,
                )
            else:
                # Layer 3.5D: Path 5b reached only when NBER unavailable.
                # Take HMM's read as the consensus and let the dissent
                # check below downgrade to INDETERMINATE.
                consensus_state, consensus_source, consensus_haircut = (
                    hmm_state, "hmm_solo", 0.10,
                )

        # ----- Phase B: HMM-corroboration check on consensus (Layer 3.5D) -----
        # Per Decision Lock 3.5D-D1 / spec §6.3-2: when HMM is available
        # AND its state differs from the consensus, classify the regime
        # as INDETERMINATE. The 0.60 confidence cap is applied
        # downstream by compute_crps / compute_cdrs (orthogonalized from
        # the haircut applied here to ``regime_stability`` input).
        if self.hmm is not None and self.hmm.state != consensus_state:
            return (
                RegimeState.INDETERMINATE.value,
                "hmm_dissent_indeterminate",
                INDETERMINATE_CONFIDENCE_HAIRCUT,
            )

        return (consensus_state, consensus_source, consensus_haircut)


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


__all__ = [
    "INDETERMINATE_CONFIDENCE_CAP",
    "INDETERMINATE_CONFIDENCE_HAIRCUT",
    "RegimeContext",
    "RegimeState",
    "build_regime_context",
]
