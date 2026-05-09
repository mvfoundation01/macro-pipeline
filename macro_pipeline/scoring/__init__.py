"""Scoring package (Layer 3B onward).

Public API
----------
``compute_crps(ctx)``                 — main CRPS scorer (Layer 3B)
``crps_layer3_weights()``             — placeholder weight result with
                                         redistribution audit trail
``LAYER3_ACTIVE_COMPONENTS``          — 4 active CRPS components (Path B)
``LAYER3_INACTIVE_COMPONENTS``        — components dropped + reason
``LAYER3_REDISTRIBUTION_METHOD``      — "proportional"
``ScoredObservation``                 — universal Layer 3 → 5/6 record
``CompositeBuildError``               — guard / precondition failure

See ``scoring/README.md`` for D5 (LEI dropped) / D6 (NAPMNOI dropped)
deviations and the Layer 5 follow-up plan.
"""
from __future__ import annotations

from macro_pipeline.scoring.crps import (
    COMPONENT_INDICATOR,
    CRPS_CONTEXT,
    LAYER3_ACTIVE_COMPONENTS,
    LAYER3_INACTIVE_COMPONENTS,
    LAYER3_REDISTRIBUTION_METHOD,
    compute_crps,
    crps_layer3_weights,
    normalize_hy_oas_regime,
    normalize_nfci,
    normalize_sahm,
    normalize_t10y3m,
)
from macro_pipeline.scoring.scored_observation import (
    CompositeBuildError,
    ScoredObservation,
)

__all__ = [
    "COMPONENT_INDICATOR",
    "CRPS_CONTEXT",
    "LAYER3_ACTIVE_COMPONENTS",
    "LAYER3_INACTIVE_COMPONENTS",
    "LAYER3_REDISTRIBUTION_METHOD",
    "CompositeBuildError",
    "ScoredObservation",
    "compute_crps",
    "crps_layer3_weights",
    "normalize_hy_oas_regime",
    "normalize_nfci",
    "normalize_sahm",
    "normalize_t10y3m",
]
