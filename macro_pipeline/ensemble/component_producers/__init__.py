"""L7 D3 — Producers for Vision §4 BINDING confidence + conviction components.

Per Strategic L7 single-sub-phase pre-flight 2026-05-16. Replaces
``PLACEHOLDER_NEUTRAL`` (0.5) values in
``bayesian_confidence.derive_confidence_components`` and
``derive_conviction_components`` with producer-backed values where
upstream signal sources exist at L6/L7.

Producer build status at L7 (per Strategic D3 scope):

Confidence components (3 confidence placeholder slots at L6-I):
  - data_quality                  L7 (basic implementation; FRED vintage proxy)
  - model_agreement               L7 (ensemble dispersion via ModelSignal tuple)
  - regime_stability              L7 (RCF top-k similarity proxy)

Conviction components (9 conviction placeholder slots at L6-I):
  - edge_score                    L7 (Sharpe-like normalized forecast/sigma)
  - asymmetry_score               L8a (vol-implied tail data not at L6)
  - model_agreement (reused)      L7 (same producer as confidence variant)
  - valuation_support             L7 (CAPE percentile via existing loader)
  - trend_confirmation            L8a (50/200 DMA + breadth not at L6)
  - liquidity_support             L8a (FCI not at L6)
  - tail_risk_penalty             L8a (VaR/CVaR not at L6)
  - crowding_penalty              L8a (CFTC + dealer gamma not at L6)
  - policy_uncertainty_penalty    L8a (Fed reaction shift signals not at L6)

L7 buildable: 6 producers (3 confidence + 3 conviction).
L8a deferred:  6 producers (all remaining placeholder slots).

The 6 L7 producers cover the highest-impact confidence + conviction
slots. The 6 L8a-deferred slots all require upstream signal sources
(options data, positioning data, NLP) that are out of L6/L7 scope.
Per V Decision #2 Option B + Strategic L7 D3 scope decision.

Public API
----------
``produce_data_quality``           Confidence component producer.
``produce_model_agreement``        Confidence + conviction producer.
``produce_regime_stability``       Confidence component producer.
``produce_edge_score``             Conviction component producer.
``produce_valuation_support``      Conviction component producer.
``L7_BUILT_PRODUCER_SLOTS``        frozenset of slot names with L7 producers.
``L8A_DEFERRED_SLOTS``             frozenset of slot names deferred to L8a.
"""
from __future__ import annotations

from .confidence_producers import (
    produce_data_quality,
    produce_model_agreement,
    produce_regime_stability,
)
from .conviction_producers import (
    produce_edge_score,
    produce_valuation_support,
)
from .l9_producers import (
    produce_asymmetry_score,
    produce_crowding_penalty,
    produce_liquidity_support,
    produce_policy_uncertainty_penalty,
    produce_tail_risk_penalty,
    produce_trend_confirmation,
)

# Slot-to-producer mapping (used by derive_*_components builders).
L7_BUILT_PRODUCER_SLOTS = frozenset({
    "data_quality",
    "model_agreement",
    "regime_stability",
    "edge_score",
    "valuation_support",
})

# L9 D1 — six previously-deferred slots now producer-backed.
L9_BUILT_PRODUCER_SLOTS = frozenset({
    "asymmetry_score",
    "trend_confirmation",
    "liquidity_support",
    "tail_risk_penalty",
    "crowding_penalty",
    "policy_uncertainty_penalty",
})

# Combined view: 11 of 12 component slots producer-backed at L9.
ALL_BUILT_PRODUCER_SLOTS = L7_BUILT_PRODUCER_SLOTS | L9_BUILT_PRODUCER_SLOTS

# L8a-deferred slots after L9: only forecast_decay_penalty remains
# (UI-driven decay model deferred to optional L10+ UI sprint).
L8A_DEFERRED_SLOTS = frozenset({
    "forecast_decay_penalty",
})

__all__ = [
    "ALL_BUILT_PRODUCER_SLOTS",
    "L7_BUILT_PRODUCER_SLOTS",
    "L8A_DEFERRED_SLOTS",
    "L9_BUILT_PRODUCER_SLOTS",
    "produce_asymmetry_score",
    "produce_crowding_penalty",
    "produce_data_quality",
    "produce_edge_score",
    "produce_liquidity_support",
    "produce_model_agreement",
    "produce_policy_uncertainty_penalty",
    "produce_regime_stability",
    "produce_tail_risk_penalty",
    "produce_trend_confirmation",
    "produce_valuation_support",
]
