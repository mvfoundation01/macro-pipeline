"""Regime classifier package (Layer 3A; tightened at L3.5A).

Public API
----------
``extract_nber_state(query_date, ctx=...)``  — PIT-aware NBER label lookup
``last_known_label_date(ctx=...)``           — boundary helper
``classify_kindleberger(ctx)``               — 5-phase rule-based classifier
``classify_dalio(ctx)``                      — 4-phase debt-cycle classifier
``predict_state(ctx)``                       — 3-state Gaussian HMM (frozen pickle)
``load_hmm(pickle_path=None)``               — fail-closed pickle loader
``build_regime_context(ctx)``                — aggregate all four views
``RegimeContext``                            — combined output dataclass
``PitDataUnavailableError`` /
``RegimeClassifierError`` / ``HmmArtifact*Error``
                                             — typed exceptions

Note: ``train_and_save_hmm`` was REMOVED from the public surface at
L3.5A (Codex finding R). HMM training is admin-only and lives in
``scripts/train_hmm_v1.py``; the inference path never auto-trains.

See ``LAYER_3_BUILD_SPEC.md`` §4 and ``LAYER_3_5_BUILD_SPEC.md`` §3.5A
for the full spec.
"""
from __future__ import annotations

from macro_pipeline.regime.dalio_cycle import DalioResult, classify_dalio
from macro_pipeline.regime.exceptions import (
    HmmArtifactCorruptError,
    HmmArtifactMissingError,
    HmmConcurrencyError,
    HmmMetadataIncompatibleError,
    NberCalendarLoadError,
    NberCycleNotFoundError,
    PitDataUnavailableError,
    RegimeClassifierError,
    RegimeContextError,
)
from macro_pipeline.regime.hmm_states import (
    HMM_FEATURES,
    HMM_PICKLE_PATH,
    HMM_SIDECAR_PATH,
    HMM_TRAINING_END,
    HMM_TRAINING_START,
    HMM_VERSION,
    SIDECAR_MODEL_VERSION,
    SIDECAR_REQUIRED_KEYS,
    SIDECAR_SCHEMA_VERSION,
    STATE_NAMES,
    HmmStateResult,
    TrainedHmm,
    load_hmm,
    predict_state,
)
from macro_pipeline.regime.kindleberger import KindlebergerResult, classify_kindleberger
from macro_pipeline.regime.nber_calendar import (
    NBER_CALENDAR_BOUNDARY,
    LastKnownLabel,
    NberCalendarLoader,
    NberCycle,
)
from macro_pipeline.regime.nber_extract import (
    NBER_FALLBACK_INDICATOR,
    NBER_PRIMARY_INDICATOR,
    NberStateResult,
    extract_nber_state,
    last_known_label_date,
)
from macro_pipeline.regime.regime_context import RegimeContext, build_regime_context

__all__ = [
    "HMM_FEATURES",
    "HMM_PICKLE_PATH",
    "HMM_SIDECAR_PATH",
    "HMM_TRAINING_END",
    "HMM_TRAINING_START",
    "HMM_VERSION",
    "NBER_CALENDAR_BOUNDARY",
    "NBER_FALLBACK_INDICATOR",
    "NBER_PRIMARY_INDICATOR",
    "SIDECAR_MODEL_VERSION",
    "SIDECAR_REQUIRED_KEYS",
    "SIDECAR_SCHEMA_VERSION",
    "STATE_NAMES",
    "DalioResult",
    "HmmArtifactCorruptError",
    "HmmArtifactMissingError",
    "HmmConcurrencyError",
    "HmmMetadataIncompatibleError",
    "HmmStateResult",
    "KindlebergerResult",
    "LastKnownLabel",
    "NberCalendarLoadError",
    "NberCalendarLoader",
    "NberCycle",
    "NberCycleNotFoundError",
    "NberStateResult",
    "PitDataUnavailableError",
    "RegimeClassifierError",
    "RegimeContext",
    "RegimeContextError",
    "TrainedHmm",
    "build_regime_context",
    "classify_dalio",
    "classify_kindleberger",
    "extract_nber_state",
    "last_known_label_date",
    "load_hmm",
    "predict_state",
]
