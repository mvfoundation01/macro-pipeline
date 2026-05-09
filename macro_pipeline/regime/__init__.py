"""Regime classifier package (Layer 3A).

Public API
----------
``extract_nber_state(query_date, ctx=...)``  — PIT-aware NBER label lookup
``last_known_label_date(ctx=...)``           — boundary helper
``classify_kindleberger(ctx)``               — 5-phase rule-based classifier
``classify_dalio(ctx)``                      — 4-phase debt-cycle classifier
``predict_state(ctx)``                       — 3-state Gaussian HMM (frozen pickle)
``train_and_save_hmm()``                     — one-time HMM training (pickle reuse)
``build_regime_context(ctx)``                — aggregate all four views
``RegimeContext``                            — combined output dataclass
``PitDataUnavailableError`` /
``RegimeClassifierError``                    — typed exceptions

See ``LAYER_3_BUILD_SPEC.md`` §4 for the full spec.
"""
from __future__ import annotations

from macro_pipeline.regime.dalio_cycle import DalioResult, classify_dalio
from macro_pipeline.regime.exceptions import (
    PitDataUnavailableError,
    RegimeClassifierError,
    RegimeContextError,
)
from macro_pipeline.regime.hmm_states import (
    HMM_FEATURES,
    HMM_PICKLE_PATH,
    HMM_TRAINING_END,
    HMM_TRAINING_START,
    HMM_VERSION,
    STATE_NAMES,
    HmmStateResult,
    TrainedHmm,
    load_hmm,
    predict_state,
    train_and_save_hmm,
)
from macro_pipeline.regime.kindleberger import KindlebergerResult, classify_kindleberger
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
    "HMM_TRAINING_END",
    "HMM_TRAINING_START",
    "HMM_VERSION",
    "NBER_FALLBACK_INDICATOR",
    "NBER_PRIMARY_INDICATOR",
    "STATE_NAMES",
    "DalioResult",
    "HmmStateResult",
    "KindlebergerResult",
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
    "train_and_save_hmm",
]
