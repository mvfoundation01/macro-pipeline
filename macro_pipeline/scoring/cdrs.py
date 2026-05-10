"""CDRS two-stage orchestrator (Layer 3C).

Spec: ``LAYER_3_BUILD_SPEC.md`` §6 + Strategic Claude 3C kickoff.

Formula: ``CDRS = V × T × R``, clipped to [0, 1].

D13 — drop the sigmoid wrappers from spec §6.2. ``V`` and ``T`` are
already ∈ [0, 1] as means of percentile-equivalents; wrapping them in
sigmoid compresses the input range to [0.5, 0.731] and caps the max
attainable CDRS at ~0.747 (recession-only path), destroying
discriminating power. Direct multiplication preserves the
multiplicative interaction the spec wanted and uses the full [0, R_max]
range. The R multiplier values from spec §6.2 are retained.

Where:
  V = mean of 5 vulnerability percentile-equivalents (Stage 1, §6.4)
  T = mean of {present trigger transforms} (Stage 2, §6.5)
  R = regime multiplier from RegimeContext.derive_regime_state():
        expansion  → 0.6
        late-cycle → 1.0
        recession  → 1.4
      with R *= 0.95 (D11) when source = "hmm_dissent_neutralized".

Active component subsets and inactive flags are recorded in
``ScoredObservation.metadata_extra`` per the kickoff contract.
"""
from __future__ import annotations

import logging

from macro_pipeline.access import PitDataContext
from macro_pipeline.models.confidence import (
    CONFIDENCE_CAPS,
    N_TARGET_RECESSION_EVENTS,
    confidence_score_v2,
    sample_adequacy_ratio,
)
from macro_pipeline.models.quality_caps import (
    aggregate_caps,
    compute_final_confidence_cap,
)
from macro_pipeline.regime import build_regime_context
from macro_pipeline.scoring.cdrs_trigger import compute_trigger
from macro_pipeline.scoring.cdrs_vulnerability import compute_vulnerability
from macro_pipeline.scoring.scored_observation import (
    CompositeBuildError,
    ScoredObservation,
)

log = logging.getLogger(__name__)


REGIME_MULTIPLIER: dict[str, float] = {
    "expansion":  0.6,
    "late-cycle": 1.0,
    "recession":  1.4,
}
REGIME_NEUTRALIZATION_FACTOR = 0.95   # D11 — when source == "hmm_dissent_neutralized"
CDRS_PROXY_SUBSTITUTIONS: list[str] = [
    "V3_RSP_SPX_proxy",         # D7
    "V5_DAMODARAN_EY_proxy",    # D8
]


def _resolve_r_multiplier(
    state: str, source: str, regime_ctx: object | None = None,
) -> tuple[float, bool]:
    """Map (regime_state, derive_regime_state source) → (R, regime_neutralized).

    Layer 3.5D AM21=B: when ``state == "indeterminate"`` (HMM dissents
    from consensus per spec §6.3-2), the R multiplier is taken from the
    **consensus state** (NBER+Kindleberger result), NOT a hard-coded
    1.0. This orthogonalizes the sizing decision (R) from the
    uncertainty signal (the 0.60 confidence cap, applied separately at
    score-aggregation level). Spec §6.4-D2 explicitly lists "R from
    consensus" as alternative #3.

    The pre-3.5D ``hmm_dissent_neutralized`` path (Layer 3B) is now
    dead code in real-time mode for post-1978 dates because the
    Layer 3.5C calendar makes NBER always available; the path is
    preserved here for the (rare) pre-1978 + training-mode case.
    """
    # Layer 3.5D INDETERMINATE: use consensus state's R, return
    # regime_neutralized=False (the 0.60 cap is the dissent signal,
    # not the R multiplier).
    from macro_pipeline.regime.regime_context import RegimeState

    if state == RegimeState.INDETERMINATE.value:
        if regime_ctx is None:
            raise CompositeBuildError(
                "CDRS R multiplier: regime_state='indeterminate' requires "
                "a RegimeContext (regime_ctx=) for consensus resolution."
            )
        consensus = _consensus_state_for_indeterminate(regime_ctx)
        if consensus not in REGIME_MULTIPLIER:
            raise CompositeBuildError(
                f"CDRS R multiplier: consensus state {consensus!r} for "
                f"INDETERMINATE not in REGIME_MULTIPLIER table."
            )
        return REGIME_MULTIPLIER[consensus], False

    if state not in REGIME_MULTIPLIER:
        raise CompositeBuildError(
            f"CDRS R multiplier: unknown regime_state {state!r}; "
            f"expected one of {list(REGIME_MULTIPLIER)}"
        )
    base = REGIME_MULTIPLIER[state]
    neutralized = source == "hmm_dissent_neutralized"
    if neutralized:
        return base * REGIME_NEUTRALIZATION_FACTOR, True
    return base, False


def _consensus_state_for_indeterminate(regime_ctx: object) -> str:
    """Return the consensus regime_state given a RegimeContext, BYPASSING
    the HMM-dissent check from ``derive_regime_state`` (Layer 3.5D).

    Mirrors the consensus computation in ``derive_regime_state`` Phase A
    but does NOT raise on HMM dissent — the caller has already
    determined dissent is the case.
    """
    # Local import: avoids circular dependency at module import time.
    from macro_pipeline.regime.regime_context import _KINDLEBERGER_STRESS

    nber = regime_ctx.nber
    kindleberger = regime_ctx.kindleberger
    if nber is not None:
        if nber.state == "recession":
            return "recession"
        if kindleberger.phase in _KINDLEBERGER_STRESS:
            return "late-cycle"
        return "expansion"
    # NBER unavailable: use HMM as consensus stand-in (rare; pre-1978
    # training mode).
    if regime_ctx.hmm is not None:
        return regime_ctx.hmm.state
    raise CompositeBuildError(
        "CDRS consensus resolution: NBER unavailable AND HMM unavailable; "
        "INDETERMINATE state is unreachable in this configuration."
    )


def _conviction_from_components(
    *,
    score: float,
    n_v_active: int,
    n_t_active: int,
    final_cap: float,
    confidence_breakdown: dict[str, float],
) -> tuple[float, float, float]:
    """3-field conviction triple per Layer 1.5B.3 (CDRS Layer 3 placeholder).

    Mirrors the CRPS Layer 3B helper but uses CDRS-specific completeness
    (active V components / 5 + active T components / 5).
    """
    sa = float(confidence_breakdown.get("sample_adequacy", 0.0))
    avg_inputs = sum(
        confidence_breakdown.get(k, 0.0)
        for k in ("data_quality", "track_record", "regime_stability",
                  "theoretical_foundation", "sample_adequacy")
    ) / 5.0
    statistical = max(0.0, min(10.0, 10.0 * (0.5 * sa + 0.5 * avg_inputs)))

    completeness = 0.5 * (n_v_active / 5.0) + 0.5 * (n_t_active / 5.0)
    operational = max(0.0, min(10.0, 10.0 * final_cap * completeness))

    actionability = max(0.0, min(10.0, 10.0 * abs(2.0 * score - 1.0)))
    return statistical, operational, actionability


def compute_cdrs(ctx: PitDataContext) -> ScoredObservation:
    """Compute the CDRS production score at ``ctx.as_of`` (Path B Layer 3C).

    Returns a ``ScoredObservation`` with score_type='CDRS' and all the
    Strategic Claude-mandated metadata fields populated.
    """
    # ---- Stage 1 + Stage 2 ----
    v_result = compute_vulnerability(ctx)
    t_result = compute_trigger(ctx)

    # ---- Regime multiplier from derive_regime_state ----
    regime = build_regime_context(ctx, skip_hmm=False)
    state, source, conf_haircut = regime.derive_regime_state()
    r, regime_neutralized = _resolve_r_multiplier(state, source, regime_ctx=regime)

    # ---- Final score (D13 — direct multiplication, no sigmoid wrap) ----
    raw_cdrs = v_result.score * t_result.score * r
    cdrs = max(0.0, min(1.0, raw_cdrs))

    # ---- Quality caps (per spec §6.6) ----
    # Aggregate per-component caps across both stages. We treat each
    # active component equally — if any single component is sourced
    # from a TV CSV (cap 0.75), the headline confidence inherits that
    # cap.
    caps_per_indicator: list[float] = []
    indicator_ids = _collect_indicator_ids(v_result, t_result)
    for indicator_id in indicator_ids:
        from macro_pipeline.access import load_series
        from macro_pipeline.exceptions import (
            IndicatorLoadError,
            PitContractViolationError,
        )
        # Layer 3.5E (D27 — refined §12.4 sub-option a): narrow to the
        # concrete exception types ``load_series`` can raise. Anything
        # else (MemoryError, KeyboardInterrupt, …) propagates so we
        # don't silently mis-aggregate caps when something unexpected
        # breaks.
        try:
            bundle = load_series(indicator_id, as_of=ctx.as_of)
        except (
            FileNotFoundError,
            ValueError,
            KeyError,
            PitContractViolationError,
            IndicatorLoadError,
        ):
            continue
        applied = compute_final_confidence_cap(
            bundle.metadata, as_of=ctx.as_of, horizon_months=12,
        )
        caps_per_indicator.append(applied.final_cap)
    horizon_cap = CONFIDENCE_CAPS["1Y"]
    final_cap = aggregate_caps(
        min(caps_per_indicator) if caps_per_indicator else None,
        horizon_cap,
    )
    caps_breakdown = {
        "source_cap_min":     min(caps_per_indicator) if caps_per_indicator else None,
        "horizon_cap_1Y":     horizon_cap,
    }

    # ---- Confidence (with regime haircut from derive_regime_state) ----
    data_quality = caps_breakdown["source_cap_min"] or 1.0
    track_record = 0.70   # CDRS architecture is newer; lower track record vs CRPS
    regime_stability = max(0.0, 0.80 - conf_haircut)
    theoretical_foundation = 0.85
    sa = sample_adequacy_ratio(
        n_eff=5,  # only 5 major drawdown events with overlap to all components
        n_target=N_TARGET_RECESSION_EVENTS,
    )
    confidence_inputs = {
        "data_quality": data_quality,
        "track_record": track_record,
        "regime_stability": regime_stability,
        "theoretical_foundation": theoretical_foundation,
        "sample_adequacy": sa,
        "ood_penalty": 0.0,
        "revision_penalty": 0.0,
    }
    confidence = confidence_score_v2(**confidence_inputs, horizon="1Y")
    # Layer 3.5B clamp by ``final_cap``. Layer 3.5D adds INDETERMINATE
    # cap (0.60) when regime_state == "indeterminate" — orthogonal to
    # source/derived caps (regime-driven, not indicator-driven).
    from macro_pipeline.regime.regime_context import (
        INDETERMINATE_CONFIDENCE_CAP,
        RegimeState,
    )
    effective_cap = final_cap
    if state == RegimeState.INDETERMINATE.value:
        effective_cap = min(effective_cap, INDETERMINATE_CONFIDENCE_CAP)
    confidence = min(confidence, effective_cap * 100.0)

    # ---- Conviction split ----
    conv_stat, conv_op, conv_act = _conviction_from_components(
        score=cdrs,
        n_v_active=len(v_result.active_components),
        n_t_active=len(t_result.active_components),
        final_cap=final_cap,
        confidence_breakdown=confidence_inputs,
    )

    cdrs_active = list(v_result.active_components) + list(t_result.active_components)
    cdrs_inactive = list(v_result.inactive_components) + list(t_result.inactive_components)

    component_values: dict[str, float] = {}
    component_values.update(v_result.components_raw)
    component_values.update(t_result.components_raw)

    component_normalized: dict[str, float] = {}
    component_normalized.update(v_result.components_normalized)
    component_normalized.update(t_result.components_normalized)

    component_weights: dict[str, float] = {}
    n_v = max(1, len(v_result.active_components))
    for name in v_result.active_components:
        component_weights[name] = 1.0 / n_v
    component_weights.update(t_result.weights)

    component_sources = _component_sources(v_result.active_components, t_result.active_components)
    pit_source = _aggregate_pit_source(indicator_ids, ctx)

    # Layer 3.5D: collect INDETERMINATE rationale + cross-phase notes.
    notes_list: list[str] = []
    if state == RegimeState.INDETERMINATE.value:
        consensus_for_r = _consensus_state_for_indeterminate(regime)
        notes_list.append(
            f"HMM dissent: regime_state=indeterminate; R={r:.2f} from "
            f"consensus={consensus_for_r!r} (per Decision Lock 3.5D-D2 / "
            f"AM21=B); confidence capped at "
            f"{INDETERMINATE_CONFIDENCE_CAP:.2f}."
        )
    # CDRS does not currently load any Option-Z-flagged series (SAHM is
    # CRPS-only); but if any V/T component bundle carries
    # derived_confidence_cap or pit_safe_basis="by_construction" notes,
    # propagate them here for symmetry with CRPS.
    notes_list = list(dict.fromkeys(notes_list))  # dedup preserving order

    return ScoredObservation(
        as_of=ctx.as_of,
        score_type="CDRS",
        raw_score=cdrs,
        confidence=confidence,
        confidence_breakdown=dict(confidence_inputs),
        conviction_statistical=conv_stat,
        conviction_operational=conv_op,
        conviction_actionability=conv_act,
        component_values=component_values,
        component_weights=component_weights,
        component_sources=component_sources,
        component_normalized=component_normalized,
        quality_caps_applied=caps_breakdown,
        final_quality_cap=final_cap,
        regime_state=state,
        regime_phase_kindleberger=regime.regime_phase_kindleberger,
        regime_phase_dalio=regime.regime_phase_dalio,
        pit_safe=True,
        pit_source=pit_source,
        notes=notes_list,
        metadata_extra={
            "cdrs_method": "two_stage_v1",
            "cdrs_active_components": cdrs_active,
            "cdrs_inactive_components": cdrs_inactive,
            "cdrs_proxy_substitutions": list(CDRS_PROXY_SUBSTITUTIONS),
            "regime_neutralized": regime_neutralized,
            "regime_state_source": source,
            "regime_state_confidence_haircut": conf_haircut,
            "V_score": v_result.score,
            "T_score": t_result.score,
            "R_multiplier": r,
            "raw_cdrs_pre_clip": raw_cdrs,
            "v_active_components": list(v_result.active_components),
            "v_inactive_components": list(v_result.inactive_components),
            "t_active_components": list(t_result.active_components),
            "t_inactive_components": list(t_result.inactive_components),
            "t_weights_post_renorm": dict(t_result.weights),
            "v_method": v_result.method,
            "t_method": t_result.method,
            "v_notes": list(v_result.notes),
            "t_notes": list(t_result.notes),
        },
    )


def _collect_indicator_ids(v_result, t_result) -> list[str]:
    """Map active V/T component names → underlying indicator ids."""
    name_to_indicator = {
        # V mappings
        "V1_cape_pctile":          "SHILLER_CAPE",
        "V2_margin_z":             "FINRA_MARGIN_DEBT",
        "V3_concentration_proxy":  "RSP",        # paired with SPX_PRICE; one cap is enough
        "V4_ey_real_gap_z":        "SHILLER_CAPE",
        "V5_ey_deviation":         "DAMODARAN_EY",
        # T mappings
        "T1_hy_oas_30d_roc":       "BAMLH0A0HYM2",
        "T2_vix_12m_pctile":       "VIX_YAHOO",
        "T3_gamma_sign":           "CBOE_GAMMA",
        "T4_breadth_thrust":       "S5FI",
        "T5_move_z":               "MOVE",
    }
    seen: set[str] = set()
    out: list[str] = []
    for n in list(v_result.active_components) + list(t_result.active_components):
        ind = name_to_indicator.get(n)
        if ind and ind not in seen:
            seen.add(ind)
            out.append(ind)
    return out


def _component_sources(v_active: list[str], t_active: list[str]) -> dict[str, str]:
    """Map component name → source string for ScoredObservation lineage."""
    source_map = {
        "V1_cape_pctile":          "SHILLER_XLS",
        "V2_margin_z":             "FINRA_XLSX",
        "V3_concentration_proxy":  "YAHOO_FINANCE (RSP/SPX)",
        "V4_ey_real_gap_z":        "SHILLER_XLS (derived)",
        "V5_ey_deviation":         "DAMODARAN_CSV",
        "T1_hy_oas_30d_roc":       "TV_CSV (BAMLH0A0HYM2)",
        "T2_vix_12m_pctile":       "YAHOO_FINANCE",
        "T3_gamma_sign":           "TV_CSV (CBOE_GAMMA)",
        "T4_breadth_thrust":       "TV_CSV (S5FI)",
        "T5_move_z":               "YAHOO_FINANCE",
    }
    return {n: source_map.get(n, "unknown") for n in list(v_active) + list(t_active)}


def _aggregate_pit_source(indicator_ids: list[str], ctx: PitDataContext) -> str:
    """Aggregated PIT source label across components."""
    from macro_pipeline.access import load_series
    from macro_pipeline.exceptions import (
        IndicatorLoadError,
        PitContractViolationError,
    )
    sources: set[str] = set()
    for ind in indicator_ids:
        # Layer 3.5E (D27 — refined §12.4 sub-option a): narrow to
        # known ``load_series`` raise tuple. Unknown exceptions
        # propagate.
        try:
            bundle = load_series(ind, as_of=ctx.as_of)
        except (
            FileNotFoundError,
            ValueError,
            KeyError,
            PitContractViolationError,
            IndicatorLoadError,
        ):
            continue
        sources.add(bundle.metadata.get("pit_source", "unknown"))
    if not sources:
        return "unknown"
    if len(sources) == 1:
        return next(iter(sources))
    return "mixed:" + ",".join(sorted(sources))


__all__ = [
    "CDRS_PROXY_SUBSTITUTIONS",
    "REGIME_MULTIPLIER",
    "REGIME_NEUTRALIZATION_FACTOR",
    "compute_cdrs",
]
