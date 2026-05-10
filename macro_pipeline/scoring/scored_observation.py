"""Layer 3 ``ScoredObservation`` dataclass — Layer 3 → Layer 5/6 interface.

Spec: ``LAYER_3_BUILD_SPEC.md`` §3.3 + ``LAYER_3_5_BUILD_SPEC.md`` §6.

Every Layer 3 score (CRPS today; CDRS in 3C; regime-only outputs in 3A
when consumers want a flat record) produces one ``ScoredObservation``.
The dataclass carries the score itself plus enough lineage that Layer 5
backtests and Layer 6 reports can reproduce it without re-running the
scorer.

Layer 3.5D additions:
- ``raw_score`` (RENAMED from ``score_value``); ``score_value`` remains
  available as a read-only ``@property`` that emits ``DeprecationWarning``
  per Decision Lock 3.5D-D3 (full removal at L4-L5 boundary).
- ``calibrated_probability: Optional[float] = None`` (NEW). Populated
  by Layer 5 (L5-RM-4 for CRPS, L5-RM-6 for CDRS) via blocked
  walk-forward isotonic / logistic calibration.
- ``calibration_metadata: Optional[dict[str, Any]] = None`` (NEW).
  Layer 5 records the calibration method, fit data window, and
  diagnostics here.
- ``notes: list[str] = field(default_factory=list)`` (NEW). Free-text
  trail for downstream consumers; populated by 3.5B/3.5C lineage
  migrations and the 3.5D INDETERMINATE rationale.
- ``regime_state`` validator updated to accept ``"indeterminate"``.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


class CompositeBuildError(Exception):
    """Raised when composite construction fails a guard (double counting,
    signal-type misuse) or precondition (component missing, unit mismatch)."""


_VALID_REGIME_STATES = frozenset(
    {"expansion", "late-cycle", "recession", "indeterminate"}
)
_SCORE_VALUE_DEPRECATION_MSG = (
    "ScoredObservation.score_value is deprecated since Layer 3.5D; "
    "use ``raw_score`` instead. Removal planned at the L4-L5 boundary."
)


@dataclass
class ScoredObservation:
    """One scored observation produced by a Layer 3 scorer.

    See ``LAYER_3_BUILD_SPEC.md`` §3.3 + ``LAYER_3_5_BUILD_SPEC.md`` §6
    for the exhaustive field list. All non-default fields are required
    at construction time.
    """

    as_of: pd.Timestamp
    score_type: str                                  # "CRPS" | "CDRS" | "REGIME"
    raw_score: float                                 # RENAMED from score_value; ∈ [0, 1]

    # ---- Confidence (from confidence_score_v2, horizon-capped) ----
    confidence: float                                # ∈ [0, 100] (we use 0-100 scale)
    confidence_breakdown: dict[str, float]           # 5 components + 2 penalties

    # ---- Conviction (3-field; see Layer 1.5B.3) ----
    conviction_statistical: float                    # ∈ [0, 10]
    conviction_operational: float
    conviction_actionability: float

    # ---- Components and traceability ----
    component_values: dict[str, float]               # raw indicator values used
    component_weights: dict[str, float]              # weights applied (placeholder in L3)
    component_sources: dict[str, str]                # {indicator -> source string}
    component_normalized: dict[str, float]           # post-§5.4.1 transform values
    quality_caps_applied: dict[str, float | None]    # {cap_name -> value}
    final_quality_cap: float                         # min of all applicable caps (∈ [0, 1])

    # ---- Regime context (always populated; from 3A) ----
    regime_state: str                                # via RegimeContext.derive_regime_state
    regime_phase_kindleberger: str
    regime_phase_dalio: str

    # ---- PIT lineage ----
    pit_safe: bool
    pit_source: str                                  # "vintage_panel"|"release_lag"|"non_vintage"|"mixed"

    # ---- Layer 5 calibration slots (3.5D NEW) ----
    calibrated_probability: float | None = None      # ∈ [0, 1], None until L5 calibrates
    calibration_metadata: dict[str, Any] | None = None

    # ---- Free-text trail (3.5D NEW; replaces metadata_extra entries from 3.5B+3.5C) ----
    notes: list[str] = field(default_factory=list)

    # ---- Bag of everything else (regime_state_source, model_version, ...) ----
    metadata_extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.raw_score <= 1.0:
            raise ValueError(
                f"raw_score={self.raw_score} must be in [0, 1] "
                f"(score_type={self.score_type!r})"
            )
        if not 0.0 <= self.final_quality_cap <= 1.0:
            raise ValueError(
                f"final_quality_cap={self.final_quality_cap} must be in [0, 1]"
            )
        if not 0.0 <= self.confidence <= 100.0:
            raise ValueError(
                f"confidence={self.confidence} must be in [0, 100]"
            )
        for name, val in [
            ("conviction_statistical", self.conviction_statistical),
            ("conviction_operational", self.conviction_operational),
            ("conviction_actionability", self.conviction_actionability),
        ]:
            if not 0.0 <= val <= 10.0:
                raise ValueError(f"{name}={val} must be in [0, 10]")
        if self.score_type not in {"CRPS", "CDRS", "REGIME"}:
            raise ValueError(
                f"score_type={self.score_type!r} must be one of "
                "{'CRPS', 'CDRS', 'REGIME'}"
            )
        if self.regime_state not in _VALID_REGIME_STATES:
            raise ValueError(
                f"regime_state={self.regime_state!r} not in valid set "
                f"{sorted(_VALID_REGIME_STATES)}"
            )
        if self.calibrated_probability is not None and not (
            0.0 <= self.calibrated_probability <= 1.0
        ):
            raise ValueError(
                f"calibrated_probability={self.calibrated_probability} "
                "must be in [0, 1] when present"
            )

    @property
    def score_value(self) -> float:
        """Deprecated alias for ``raw_score`` (Layer 3.5D / D24).

        Read-only. Constructors must use ``raw_score=``. Removal at the
        L4–L5 boundary; see Decision Lock 3.5D-D3.
        """
        warnings.warn(
            _SCORE_VALUE_DEPRECATION_MSG,
            DeprecationWarning,
            stacklevel=2,
        )
        return self.raw_score

    def to_dict(self) -> dict[str, Any]:
        """Flat-dict view for serialization / debugging."""
        return {
            "as_of": self.as_of.isoformat(),
            "score_type": self.score_type,
            "raw_score": self.raw_score,
            "calibrated_probability": self.calibrated_probability,
            "calibration_metadata": (
                dict(self.calibration_metadata)
                if self.calibration_metadata is not None
                else None
            ),
            "confidence": self.confidence,
            "confidence_breakdown": dict(self.confidence_breakdown),
            "conviction_statistical": self.conviction_statistical,
            "conviction_operational": self.conviction_operational,
            "conviction_actionability": self.conviction_actionability,
            "component_values": dict(self.component_values),
            "component_weights": dict(self.component_weights),
            "component_sources": dict(self.component_sources),
            "component_normalized": dict(self.component_normalized),
            "quality_caps_applied": dict(self.quality_caps_applied),
            "final_quality_cap": self.final_quality_cap,
            "regime_state": self.regime_state,
            "regime_phase_kindleberger": self.regime_phase_kindleberger,
            "regime_phase_dalio": self.regime_phase_dalio,
            "pit_safe": self.pit_safe,
            "pit_source": self.pit_source,
            "notes": list(self.notes),
            "metadata_extra": dict(self.metadata_extra),
        }


__all__ = ["CompositeBuildError", "ScoredObservation"]
