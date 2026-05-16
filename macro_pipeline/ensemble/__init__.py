"""Ensemble aggregation layer (L6).

Per Pipeline Guide v2.0 §7 + Vision v2.0 §3 (90-measurement catalogue).
Layer 6 combines L5b 11-model outputs + L1.7 manual overrides into final
probabilistic forecast distribution with Triple Decomposition + Triple
σ + OOD reserve + Reference Class Forecasting.

Sub-phase ledger
----------------
L6-PREP  authority docs cherry-pick  (COMPLETE — l6-prep-accept @ ca38c0a)
L6-A     MetricMetadata + registry    (COMPLETE — l6-a-accept @ e47ce15)
L6-B     TripleDecomposition + cap __post_init__  (THIS SUB-PHASE)
L6-C     TripleSigma + cumulative scaling caveats
L6-D     OOD reserve + confidence cap helpers
L6-E     Reference Class Forecasting module
L6-F     Ensemble aggregator
L6-G     Measurement coverage pass
L6-H     Gate 30 + retrospective + sprint closure

Public API (L6-A)
-----------------
``MetricMetadata``            Frozen dataclass for a single Vision §3 measure.
``SUBCATEGORY``               Literal type listing 12 Vision §3 subcategories.
``SUBCATEGORY_VALID``         frozenset for runtime subcategory validation.
``LAYER_ORIGIN``              Literal type listing producer layers.
``LAYER_ORIGIN_VALID``        frozenset for runtime layer-origin validation.
``UPDATE_FREQUENCY``          Literal type for update cadence.
``UPDATE_FREQUENCY_VALID``    frozenset for runtime update-frequency validation.
``load_metrics_registry``     YAML -> dict[metric_id, MetricMetadata].
``save_metrics_registry``     dict -> YAML (atomic; deterministic ordering).
``DEFAULT_REGISTRY_PATH``     Path to the in-package Vision §3 catalogue.
"""
from __future__ import annotations

from macro_pipeline.ensemble.metadata import (
    LAYER_ORIGIN,
    LAYER_ORIGIN_VALID,
    SUBCATEGORY,
    SUBCATEGORY_VALID,
    UPDATE_FREQUENCY,
    UPDATE_FREQUENCY_VALID,
    MetricMetadata,
)
from macro_pipeline.ensemble.registry import (
    DEFAULT_REGISTRY_PATH,
    load_metrics_registry,
    save_metrics_registry,
)
from macro_pipeline.ensemble.triple_decomposition import (
    CONFIDENCE_CAP_10Y_NON_STRATIFIED,
    CONFIDENCE_CAP_10Y_REGIME_STRATIFIED,
    SUPPORTED_HORIZONS,
    TripleDecomposition,
)

__all__ = [
    # L6-A schema + registry
    "DEFAULT_REGISTRY_PATH",
    "LAYER_ORIGIN",
    "LAYER_ORIGIN_VALID",
    "MetricMetadata",
    "SUBCATEGORY",
    "SUBCATEGORY_VALID",
    "UPDATE_FREQUENCY",
    "UPDATE_FREQUENCY_VALID",
    "load_metrics_registry",
    "save_metrics_registry",
    # L6-B Triple Probability Decomposition
    "CONFIDENCE_CAP_10Y_NON_STRATIFIED",
    "CONFIDENCE_CAP_10Y_REGIME_STRATIFIED",
    "SUPPORTED_HORIZONS",
    "TripleDecomposition",
]
