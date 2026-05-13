"""CRPS production scorer (Layer 3B).

Spec: ``LAYER_3_BUILD_SPEC.md`` §5.

Scope policy
------------
- Layer 3 USES expert priors as weights (placeholder mode). Layer 5 will
  refit. ``WeightEstimationResult.is_placeholder`` is always ``True``
  here.
- The full 6-key ``EXPERT_COEFFICIENT_PRIORS`` (Layer 1.5B.4) remains the
  canonical source of truth for Layer 5. Layer 3 builds a *Path B*
  active subset because two of the spec's 6 components cannot be loaded
  today:
    * ``ism_pmi_neworders`` (NAPMNOI) — FRED returns 400 ("series does
      not exist"; ISM licensing change ~2018).
    * ``lei_3d_rule`` (Conference Board LEI 6M annualized) — CB LEI is
      not in any Tier 1-4 loader; ``PHILLY_LEI_PROXY`` (USSLIND) is
      blocked by the ``check_double_counting`` guard against T10Y3M.
- Weights are redistributed *proportionally* over the active subset and
  the result is recorded in ``WeightEstimationResult.weights`` together
  with ``inactive_components`` and ``redistribution_method`` for full
  audit. See ``scoring/README.md`` §D5/§D6.

Active subset (Path B, 4 components)
------------------------------------
    yield_curve_nyfed   T10Y3M           0.4286 (was 0.30)
    sahm_rule           SAHMREALTIME     0.2857 (was 0.20)
    nfci_kcfsi          NFCI             0.1429 (was 0.10)
    hy_oas_regime       BAMLH0A0HYM2     0.1429 (was 0.10)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from macro_pipeline.access import IndicatorBundle, PitDataContext
from macro_pipeline.models.composite_guards import (
    check_double_counting,
    check_signal_type_compatibility,
)
from macro_pipeline.models.confidence import (
    CONFIDENCE_CAPS,
    N_TARGET_RECESSION_EVENTS,
    confidence_score_v2,
    sample_adequacy_ratio,
)
from macro_pipeline.models.crps_weights import (
    EXPERT_COEFFICIENT_PRIORS,
    WeightEstimationResult,
)
from macro_pipeline.models.quality_caps import (
    AppliedCaps,
    aggregate_caps,
    compute_final_confidence_cap,
)
from macro_pipeline.regime import build_regime_context
from macro_pipeline.scoring.scored_observation import (
    CompositeBuildError,
    ScoredObservation,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Active component subset and redistribution policy
# ---------------------------------------------------------------------------
# Keys are the names used in ``EXPERT_COEFFICIENT_PRIORS``. Order is fixed
# so iteration is deterministic.
LAYER3_ACTIVE_COMPONENTS: list[str] = [
    "yield_curve_nyfed",
    "sahm_rule",
    "nfci_kcfsi",
    "hy_oas_regime",
]
LAYER3_INACTIVE_COMPONENTS: list[str] = [
    "lei_3d_rule",          # CB LEI not feasibly sourced
    "ism_pmi_neworders",    # NAPMNOI removed from FRED
]
LAYER3_REDISTRIBUTION_METHOD: str = "proportional"

# Map ``EXPERT_COEFFICIENT_PRIORS`` keys → indicator IDs the scorer pulls
# from cache via PitDataContext. ``signal_horizon_match`` Strategic Claude
# decision: NFCI used (KCFSI is a fallback only).
COMPONENT_INDICATOR: dict[str, str] = {
    "yield_curve_nyfed":  "T10Y3M",
    "sahm_rule":          "SAHMREALTIME",
    "ism_pmi_neworders":  "NAPMNOI",       # active in Path A only
    "nfci_kcfsi":         "NFCI",
    "hy_oas_regime":      "BAMLH0A0HYM2",
    "lei_3d_rule":        "PHILLY_LEI_PROXY",  # active only when CB LEI is sourced
}


def crps_layer3_weights() -> WeightEstimationResult:
    """Build the Layer 3 placeholder weight result.

    Sums the Gaussian-prior means for the active components, then
    redistributes proportionally so the active weights sum to 1.0. Full
    6-key prior dict is kept untouched as the Layer 5 source of truth.
    """
    raw_means = {k: float(p.mean) for k, p in EXPERT_COEFFICIENT_PRIORS.items()}
    active_sum = sum(raw_means[k] for k in LAYER3_ACTIVE_COMPONENTS)
    if active_sum <= 0:
        raise CompositeBuildError(
            "Sum of active expert-prior means is non-positive; cannot "
            f"redistribute (raw={raw_means})"
        )
    redistributed = {
        k: raw_means[k] / active_sum for k in LAYER3_ACTIVE_COMPONENTS
    }
    # Sanity: weights must sum to 1 within float tolerance.
    s = sum(redistributed.values())
    if abs(s - 1.0) > 1e-9:
        raise CompositeBuildError(
            f"Redistributed weights must sum to 1.0 ± 1e-9; got {s}"
        )
    return WeightEstimationResult(
        method="layer3_expert_prior_subset_proportional",
        weights=redistributed,
        is_placeholder=True,
        inactive_components=list(LAYER3_INACTIVE_COMPONENTS),
        redistribution_method=LAYER3_REDISTRIBUTION_METHOD,
        notes=(
            "Layer 3B placeholder. Active subset weights redistributed "
            "proportionally from EXPERT_COEFFICIENT_PRIORS. Layer 5 will "
            "refit via Gaussian-prior penalized logistic regression "
            "with blocked walk-forward CV — and re-include NAPMNOI / "
            "CB LEI once a loader exists for them."
        ),
        extra={
            "raw_expert_means": raw_means,
            "active_sum_pre_redistribution": active_sum,
            "active_components": list(LAYER3_ACTIVE_COMPONENTS),
        },
    )


# ---------------------------------------------------------------------------
# §5.4.1 Component normalizations  (each → score ∈ [0, 1])
# ---------------------------------------------------------------------------
def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def normalize_t10y3m(value: float) -> float:
    """Yield curve: ``sigmoid(-T10Y3M / 0.50)``. Inversion → high score."""
    if not math.isfinite(value):
        return float("nan")
    return _sigmoid(-value / 0.50)


def normalize_sahm(value: float) -> float:
    """Sahm rule: 1.0 if >= 0.50; 0.0 if <= 0.30; linear ramp between."""
    if not math.isfinite(value):
        return float("nan")
    if value >= 0.50:
        return 1.0
    if value <= 0.30:
        return 0.0
    return (value - 0.30) / 0.20


def normalize_nfci(value: float) -> float:
    """NFCI: ``sigmoid(NFCI / 0.5)``. Positive (tightening) → high score."""
    if not math.isfinite(value):
        return float("nan")
    return _sigmoid(value / 0.5)


def normalize_hy_oas_regime(value: float, history: pd.Series) -> float:
    """HY OAS percentile-based score.

    score = (current_percentile − 50) / 50, clipped to [0, 1].
    history is the full PIT-safe series ending at as_of (used for
    percentile rank).
    """
    if not math.isfinite(value) or history.empty:
        return float("nan")
    pct = float((history <= value).mean())  # ∈ [0, 1]
    score = (pct * 100.0 - 50.0) / 50.0
    return max(0.0, min(1.0, score))


_NORMALIZER = {
    "yield_curve_nyfed":  ("scalar", normalize_t10y3m),
    "sahm_rule":          ("scalar", normalize_sahm),
    "nfci_kcfsi":         ("scalar", normalize_nfci),
    "hy_oas_regime":      ("history", normalize_hy_oas_regime),
}


# ---------------------------------------------------------------------------
# Composite-guard application (§5.4.2)
# ---------------------------------------------------------------------------
CRPS_CONTEXT = "12M_recession_probability_composite_with_explicit_coincident_treatment"


def _apply_composite_guards(component_indicators: list[str]) -> dict[str, Any]:
    """Run the 1.5C.3 / 1.5C.4 guards. Raise CompositeBuildError on
    double-counting; record signal-type acknowledgments in metadata.
    """
    dc_violations = check_double_counting(component_indicators)
    if dc_violations:
        raise CompositeBuildError(
            "Double-counting detected: "
            + "; ".join(str(v) for v in dc_violations)
        )

    sahm_ack = check_signal_type_compatibility(
        "SAHMREALTIME",
        CRPS_CONTEXT,
        raise_on_violation=False,
    )
    sahm_ack_str = str(sahm_ack) if sahm_ack is not None else "no violation"
    return {
        "sahm_signal_type_acknowledgment": (
            f"SAHMREALTIME is COINCIDENT but participates in CRPS "
            f"under context {CRPS_CONTEXT!r}. Guard returned: {sahm_ack_str}"
        ),
    }


# ---------------------------------------------------------------------------
# CRPS production scorer
# ---------------------------------------------------------------------------
@dataclass
class _ComponentLoad:
    name: str
    indicator_id: str
    bundle: IndicatorBundle
    raw_value: float
    normalized: float


def _load_component(
    name: str,
    ctx: PitDataContext,
) -> _ComponentLoad:
    """Load one CRPS component PIT-safe and compute its normalized score."""
    indicator_id = COMPONENT_INDICATOR[name]
    bundle = ctx.load(indicator_id)
    series = bundle.data.dropna()
    if series.empty:
        raise CompositeBuildError(
            f"CRPS component {name!r} ({indicator_id}) has no PIT-safe "
            f"observations at as_of={ctx.as_of.date()}. Drop the as_of, "
            "load latest separately, or extend the data backfill."
        )
    raw_value = float(series.iloc[-1])
    norm_kind, norm_fn = _NORMALIZER[name]
    if norm_kind == "scalar":
        normalized = float(norm_fn(raw_value))
    else:  # "history"
        normalized = float(norm_fn(raw_value, series))
    return _ComponentLoad(
        name=name,
        indicator_id=indicator_id,
        bundle=bundle,
        raw_value=raw_value,
        normalized=normalized,
    )


# Layer 5-RM-4 (L5-13 absorption): the PIT-lineage formatter is now in the
# shared ``scoring/notes_formatter.py`` module so CDRS + future scorers
# inherit the same discipline. Local alias preserves existing call sites
# in this module (``crps_score`` continues to call ``_format_pit_lineage_notes``)
# without churning the import surface.
from macro_pipeline.scoring.notes_formatter import (
    format_pit_lineage_notes as _format_pit_lineage_notes,
)


def _compute_quality_cap(loads: list[_ComponentLoad], ctx: PitDataContext) -> tuple[float, dict[str, float | None]]:
    """Aggregate per-component quality caps and the 1Y horizon cap.

    Layer 3.5B: include ``derived_confidence_cap`` from any Option Z
    component (e.g. SAHMREALTIME at 0.70) in the MIN aggregation.
    """
    per_component: list[AppliedCaps] = []
    for cl in loads:
        per_component.append(
            compute_final_confidence_cap(
                cl.bundle.metadata,
                as_of=ctx.as_of,
                horizon_months=12,
            )
        )
    source_cap_min = min(c.source_cap for c in per_component)
    vintage_caps = [c.vintage_confidence_cap for c in per_component if c.vintage_confidence_cap is not None]
    staleness_caps = [c.vintage_staleness_cap for c in per_component if c.vintage_staleness_cap is not None]
    derived_caps = [c.derived_confidence_cap for c in per_component if c.derived_confidence_cap is not None]

    horizon_cap = CONFIDENCE_CAPS["1Y"]  # 0.85
    final = aggregate_caps(
        source_cap_min,
        min(vintage_caps) if vintage_caps else None,
        min(staleness_caps) if staleness_caps else None,
        min(derived_caps) if derived_caps else None,
        horizon_cap,
    )
    return final, {
        "source_cap_min":      source_cap_min,
        "vintage_cap_min":     min(vintage_caps) if vintage_caps else None,
        "staleness_cap_min":   min(staleness_caps) if staleness_caps else None,
        "derived_cap_min":     min(derived_caps) if derived_caps else None,
        "horizon_cap_1Y":      horizon_cap,
    }


def _aggregate_pit_source(loads: list[_ComponentLoad]) -> str:
    """Single string summarizing the PIT path each component took."""
    sources = {cl.bundle.metadata.get("pit_source", "unknown") for cl in loads}
    if len(sources) == 1:
        return next(iter(sources))
    return "mixed:" + ",".join(sorted(sources))


def _conviction_from_components(
    *,
    score: float,
    n_components_active: int,
    n_components_total: int,
    final_cap: float,
    confidence_breakdown: dict[str, float],
) -> tuple[float, float, float]:
    """Lightweight conviction triple per §5.4.4 (Layer 3 placeholder).

    Each output ∈ [0, 10]. Layer 5 will refine using OOS AUC / Brier /
    coefficient stability. Here we use simple, defensible proxies:

    * **Statistical** = 10 × (sample adequacy + mean of confidence inputs) / 2.
      Variance proxy: sample_adequacy is in confidence_breakdown.
    * **Operational** = 10 × (final_cap × completeness)
      where completeness = active_components / total_components.
    * **Actionability** = 10 × |2·score − 1|, peaks near 0/1, valley
      around 0.5 (signal asymmetric only when extreme).
    """
    sa = float(confidence_breakdown.get("sample_adequacy", 0.0))
    avg_conf_inputs = sum(
        confidence_breakdown.get(k, 0.0)
        for k in ("data_quality", "track_record", "regime_stability",
                  "theoretical_foundation", "sample_adequacy")
    ) / 5.0
    statistical = max(0.0, min(10.0, 10.0 * (0.5 * sa + 0.5 * avg_conf_inputs)))

    completeness = n_components_active / max(1, n_components_total)
    operational = max(0.0, min(10.0, 10.0 * final_cap * completeness))

    actionability = max(0.0, min(10.0, 10.0 * abs(2.0 * score - 1.0)))
    return statistical, operational, actionability


def compute_crps(
    ctx: PitDataContext,
    *,
    weights: WeightEstimationResult | None = None,
) -> ScoredObservation:
    """Compute the CRPS production score at ``ctx.as_of``.

    Returns a ``ScoredObservation`` with score_type='CRPS'. PIT discipline
    is enforced via the ``PitDataContext``; if any active component has
    no PIT-safe observations, ``CompositeBuildError`` is raised.
    """
    weights = weights if weights is not None else crps_layer3_weights()
    if not weights.is_placeholder:
        raise CompositeBuildError(
            "Layer 3 CRPS only accepts placeholder weights. Got "
            f"is_placeholder=False (method={weights.method!r}). Layer 5 "
            "is the right place for fitted weights."
        )

    # 1. Load each active component
    loads = [_load_component(name, ctx) for name in LAYER3_ACTIVE_COMPONENTS]

    # 2. Composite guards (1.5C.3 + 1.5C.4)
    component_indicators = [cl.indicator_id for cl in loads]
    guard_metadata = _apply_composite_guards(component_indicators)

    # 3. Weighted sum of normalized scores
    score = 0.0
    for cl in loads:
        if not math.isfinite(cl.normalized):
            raise CompositeBuildError(
                f"Component {cl.name} normalized to non-finite value "
                f"({cl.normalized}); raw={cl.raw_value}"
            )
        score += weights.weights[cl.name] * cl.normalized
    score = max(0.0, min(1.0, score))

    # 4. Quality caps and confidence (§5.4.3)
    final_cap, caps_breakdown = _compute_quality_cap(loads, ctx)

    regime = build_regime_context(ctx, skip_hmm=False)
    regime_state, regime_state_source, conf_haircut = regime.derive_regime_state()

    # Confidence inputs — defensible Layer 3 defaults until Layer 5 fits.
    # data_quality and track_record proxy via the source cap min and a
    # fixed academic baseline; regime_stability is haircut by the
    # derive_regime_state output; sample_adequacy uses CRPS recession
    # event count.
    data_quality = caps_breakdown["source_cap_min"] or 1.0
    track_record = 0.80  # NY Fed Estrella-Mishkin yield curve has decades of OOS validation
    regime_stability = max(0.0, 0.80 - conf_haircut)
    theoretical_foundation = 0.90
    sa = sample_adequacy_ratio(
        n_eff=10,  # 10 NBER recessions in the modern training sample
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
    # Layer 3.5B: clamp by ``final_cap`` (which now includes Option Z
    # ``derived_confidence_cap`` via MIN aggregation). Confidence in
    # [0, 100] respects MIN(source_cap, vintage_cap, staleness_cap,
    # derived_cap, horizon_cap). Pre-3.5B this clamp was only via
    # the horizon cap inside ``confidence_score_v2``; now the full
    # source-quality + Option Z chain binds.
    # Layer 3.5D: when regime_state == "indeterminate" (HMM dissents
    # from consensus), additionally cap at INDETERMINATE_CONFIDENCE_CAP
    # (0.60) per Decision Lock 3.5D-D1. The cap is regime-driven, not
    # indicator-driven, so it lives at the score-aggregation level
    # (separate from the source/derived cap chain).
    from macro_pipeline.regime.regime_context import (
        INDETERMINATE_CONFIDENCE_CAP,
        RegimeState,
    )
    effective_cap = final_cap
    if regime_state == RegimeState.INDETERMINATE.value:
        effective_cap = min(effective_cap, INDETERMINATE_CONFIDENCE_CAP)
    confidence = min(confidence, effective_cap * 100.0)

    # 5. Conviction split (§5.4.4)
    conv_stat, conv_op, conv_act = _conviction_from_components(
        score=score,
        n_components_active=len(LAYER3_ACTIVE_COMPONENTS),
        n_components_total=len(EXPERT_COEFFICIENT_PRIORS),
        final_cap=final_cap,
        confidence_breakdown=confidence_inputs,
    )

    # 6. Build ScoredObservation (Layer 3.5D: raw_score; notes from
    #    cross-phase migration; INDETERMINATE rationale appended).
    notes_list = _format_pit_lineage_notes(loads)
    if regime_state == RegimeState.INDETERMINATE.value:
        notes_list.append(
            f"HMM dissent: regime_state=indeterminate; confidence "
            f"capped at {INDETERMINATE_CONFIDENCE_CAP:.2f}. Per Decision "
            "Lock 3.5D-D1 / spec §6.3-2."
        )
    notes_list = list(dict.fromkeys(notes_list))  # dedup preserving order

    return ScoredObservation(
        as_of=ctx.as_of,
        score_type="CRPS",
        raw_score=score,
        confidence=confidence,
        confidence_breakdown=dict(confidence_inputs),
        conviction_statistical=conv_stat,
        conviction_operational=conv_op,
        conviction_actionability=conv_act,
        component_values={cl.name: cl.raw_value for cl in loads},
        component_weights=dict(weights.weights),
        component_sources={cl.name: cl.bundle.metadata.get("source", "unknown") for cl in loads},
        component_normalized={cl.name: cl.normalized for cl in loads},
        quality_caps_applied=caps_breakdown,
        final_quality_cap=final_cap,
        regime_state=regime_state,
        regime_phase_kindleberger=regime.regime_phase_kindleberger,
        regime_phase_dalio=regime.regime_phase_dalio,
        pit_safe=True,
        pit_source=_aggregate_pit_source(loads),
        notes=notes_list,
        metadata_extra={
            "regime_state_source": regime_state_source,
            "regime_state_confidence_haircut": conf_haircut,
            "weights_method": weights.method,
            "weights_is_placeholder": weights.is_placeholder,
            "inactive_components": list(weights.inactive_components),
            "redistribution_method": weights.redistribution_method,
            "active_components": list(LAYER3_ACTIVE_COMPONENTS),
            "crps_method": "expert_priors_v1_pathB",
            "guard_metadata": guard_metadata,
            "component_indicator_ids": dict(zip(
                [cl.name for cl in loads],
                [cl.indicator_id for cl in loads],
                strict=True,
            )),
        },
    )


__all__ = [
    "COMPONENT_INDICATOR",
    "CRPS_CONTEXT",
    "LAYER3_ACTIVE_COMPONENTS",
    "LAYER3_INACTIVE_COMPONENTS",
    "LAYER3_REDISTRIBUTION_METHOD",
    "compute_crps",
    "crps_layer3_weights",
    "normalize_hy_oas_regime",
    "normalize_nfci",
    "normalize_sahm",
    "normalize_t10y3m",
]
