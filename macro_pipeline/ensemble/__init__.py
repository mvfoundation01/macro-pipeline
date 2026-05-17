"""Ensemble aggregation layer (L6).

Per Pipeline Guide v2.0 §7 + Vision v2.1 §3 (90-measurement catalogue).
Layer 6 combines L5b 11-model outputs + L1.7 manual overrides into final
probabilistic forecast distribution with Triple Decomposition + Triple
σ + OOD reserve + Reference Class Forecasting + DMS adjustment + Lucas
critique diagnostics.

Sub-phase ledger
----------------
L6-PREP  authority docs cherry-pick  (COMPLETE — l6-prep-accept @ ca38c0a)
L6-A     MetricMetadata + registry    (COMPLETE — l6-a-accept @ e47ce15)
L6-B     TripleDecomposition + cap __post_init__  (COMPLETE — l6-b-accept @ b3297a5)
L6-C     TripleSigma + cumulative scaling caveats  (COMPLETE — l6-c-accept @ fae2b16)
L6-D     OOD reserve + confidence cap helpers  (COMPLETE — l6-d-accept @ 4fdcf64)
L6-E     Reference Class Forecasting module  (COMPLETE — l6-e-accept @ 2ddbaa4)
L6-F     Ensemble aggregator  (COMPLETE — l6-f-accept @ f2c963b)
L6-G     90+ measurement coverage + Bayesian refinement  (COMPLETE — l6-g-accept @ 97ada00)
L6-H     R7 methodology HIGH closure (Vision §4 additive + cap cascade
         + OOD buckets + DMS propagation + Lucas diagnostics)  (THIS SUB-PHASE)
L6-I     R7 code-review HIGH closure
L6-J     R7 MEDIUM closure + test-count discrepancy audit
L6-K     R7 OPERATIONAL closure + retrospective + sprint closure

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

L6-H additions
--------------
``ConfidenceComponents``      Vision §4 6-component additive confidence inputs.
``ConvictionComponents``      Vision §4 10-component conviction inputs.
``derive_confidence_components``  Build ConfidenceComponents from pipeline.
``derive_conviction_components``  Build ConvictionComponents from pipeline.
``compute_sample_size_adequacy``  Vision §10 sqrt(min(1, n_eff/N_target)).
``apply_confidence_cap_cascade``  Vision §4 + §7 + §10 cap cascade.
``select_dms_adjustment_bps`` L6-H D5 DMS dynamic tier selector.
``apply_dms_bps_to_return``   Apply bps to return-fraction point estimate.
``LucasCritiqueDiagnostics``  Vision §9 runtime flag + reason codes.
``compute_lucas_diagnostics`` Derive flag from structural-break evidence.
"""
from __future__ import annotations

from macro_pipeline.ensemble.metadata import (
    DEFERRED_REASON,
    DEFERRED_REASON_VALID,
    LAYER_ORIGIN,
    LAYER_ORIGIN_VALID,
    METRIC_STATUS,
    METRIC_STATUS_VALID,
    SUBCATEGORY,
    SUBCATEGORY_VALID,
    UPDATE_FREQUENCY,
    UPDATE_FREQUENCY_VALID,
    MetricLineage,
    MetricMetadata,
)
from macro_pipeline.ensemble.registry import (
    DEFAULT_REGISTRY_PATH,
    _clear_registry_cache_for_testing,
    _load_default_registry_cached,
    load_metrics_registry,
    save_metrics_registry,
    validate_registry_counts,
)
from macro_pipeline.ensemble.triple_sigma import (
    DEFAULT_REALIZED_VOL_RATIO_THRESHOLD,
    SIGMA_VALIDITY_REASON_CODES,
    compute_sigma_validity_diagnostics,
)
from macro_pipeline.ensemble.rcf import (
    BASE_KAPPA_BY_HORIZON,
    DEFAULT_MIN_SIMILARITY_THRESHOLD,
    DEFAULT_TOP_K_REPORTED,
    RCF_OOD_MIN_NEIGHBORS_THRESHOLD,
    SAMPLE_START_BOUNDARY,
    compute_horizon_conditional_kappa,
)
from macro_pipeline.ensemble.triple_decomposition import (
    CONFIDENCE_CAP_10Y_NON_STRATIFIED,
    CONFIDENCE_CAP_10Y_REGIME_STRATIFIED,
    SUPPORTED_HORIZONS,
    TripleDecomposition,
)
from macro_pipeline.ensemble.triple_sigma import (
    SIGMA_MAX_REASONABLE,
    SIGMA_TYPES,
    TripleSigma,
)
from macro_pipeline.ensemble.ood_and_caps import (
    OOD_RESERVE_CEILING,
    OOD_RESERVE_FLOOR,
    OODConditions,
    apply_confidence_cap_cascade,
    compute_ood_reserve,
    enforce_confidence_caps,
)
from macro_pipeline.ensemble.rcf import (
    BAYESIAN_PRIOR_10Y_REAL_RETURN,
    DEFAULT_KAPPA,
    MACRO_STATE_FIELDS,
    InsufficientReferenceClassError,
    MacroStateVector,
    ReferenceClass,
    apply_bayesian_shrinkage,
    cosine_similarity,
    find_reference_class,
    standardize_macro_state,
)
from macro_pipeline.ensemble.aggregator import (
    EnsembleResult,
    ForecastInputs,
    HorizonResult,
    aggregate_ensemble,
    aggregate_horizons_pure,
    populate_metric_outputs,
)
# L6-K D2 (Codex Finding #7 closure): `SUPPORTED_HORIZONS` canonical
# source is `triple_decomposition` (imported above); aggregator
# re-export removed to silence Ruff F811 + clarify single-source-of-truth.
from macro_pipeline.ensemble.bayesian_confidence import (
    KAPPA_EVIDENCE,
    ConfidenceComponents,
    ConvictionComponents,
    compute_bayesian_confidence,
    compute_conviction_score,
    compute_sample_size_adequacy,
    derive_confidence_components,
    derive_conviction_components,
)
from macro_pipeline.ensemble.dms_and_lucas import (
    LucasCritiqueDiagnostics,
    apply_dms_bps_to_return,
    compute_lucas_diagnostics,
    select_dms_adjustment_bps,
)
from macro_pipeline.ensemble.model_signals import (
    LAYER_DISAGREEMENT_LABELS,
    MODEL_IDS,
    MODEL_IDS_VALID,
    MODEL_WEIGHTS_BY_HORIZON,
    MODEL_WEIGHTS_BY_HORIZON_FROZEN,
    WEIGHT_SUM_TOLERANCE,
    ModelSignal,
    aggregate_model_signals,
    detect_layer_disagreement,
    wrap_point_estimates_as_model_signals,
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
    # L6-C Triple sigma Reporting
    "SIGMA_MAX_REASONABLE",
    "SIGMA_TYPES",
    "TripleSigma",
    # L6-D OOD reserve + confidence cap helpers (L6-H expanded)
    "OODConditions",
    "OOD_RESERVE_CEILING",
    "OOD_RESERVE_FLOOR",
    "apply_confidence_cap_cascade",  # L6-H D2
    "compute_ood_reserve",
    "enforce_confidence_caps",
    # L6-E Reference Class Forecasting
    "BAYESIAN_PRIOR_10Y_REAL_RETURN",
    "DEFAULT_KAPPA",
    "MACRO_STATE_FIELDS",
    "InsufficientReferenceClassError",
    "MacroStateVector",
    "ReferenceClass",
    "apply_bayesian_shrinkage",
    "cosine_similarity",
    "find_reference_class",
    "standardize_macro_state",
    # L6-F + L6-G + L6-H Ensemble Aggregator
    "EnsembleResult",
    "ForecastInputs",
    "HorizonResult",
    "aggregate_ensemble",
    "populate_metric_outputs",
    # L6-G + L6-H Bayesian + conviction
    "KAPPA_EVIDENCE",
    "ConfidenceComponents",
    "ConvictionComponents",
    "compute_bayesian_confidence",
    "compute_conviction_score",
    "compute_sample_size_adequacy",
    "derive_confidence_components",
    "derive_conviction_components",
    # L6-H D5 DMS + Lucas
    "LucasCritiqueDiagnostics",
    "apply_dms_bps_to_return",
    "compute_lucas_diagnostics",
    "select_dms_adjustment_bps",
    # L6-I D3/D4/D5 ModelSignal + 11-model schema + layer disagreement
    "LAYER_DISAGREEMENT_LABELS",
    "MODEL_IDS",
    "MODEL_IDS_VALID",
    "MODEL_WEIGHTS_BY_HORIZON",
    "MODEL_WEIGHTS_BY_HORIZON_FROZEN",
    "WEIGHT_SUM_TOLERANCE",
    "ModelSignal",
    "aggregate_model_signals",
    "detect_layer_disagreement",
    "wrap_point_estimates_as_model_signals",
    # L6-J D2 RCF OOD enhancements
    "BASE_KAPPA_BY_HORIZON",
    "DEFAULT_MIN_SIMILARITY_THRESHOLD",
    "DEFAULT_TOP_K_REPORTED",
    "RCF_OOD_MIN_NEIGHBORS_THRESHOLD",
    "SAMPLE_START_BOUNDARY",
    "compute_horizon_conditional_kappa",
    # L6-J D3 triple sigma validity diagnostics
    "DEFAULT_REALIZED_VOL_RATIO_THRESHOLD",
    "SIGMA_VALIDITY_REASON_CODES",
    "compute_sigma_validity_diagnostics",
    # L6-J D4 registry lineage replication-grade
    "DEFERRED_REASON",
    "DEFERRED_REASON_VALID",
    "METRIC_STATUS",
    "METRIC_STATUS_VALID",
    "MetricLineage",
    "validate_registry_counts",
    # L6-J D5 cache helpers (intentionally exported despite underscore
    # prefix — pytest fixtures + downstream test tooling consume these).
    "_clear_registry_cache_for_testing",
    "_load_default_registry_cached",
    # L6-J D6 aggregator purity
    "aggregate_horizons_pure",
]
