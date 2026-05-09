"""Layer 3 ``ScoredObservation`` dataclass — Layer 3 → Layer 5/6 interface.

Spec: ``LAYER_3_BUILD_SPEC.md`` §3.3.

Every Layer 3 score (CRPS today; CDRS in 3C; regime-only outputs in 3A
when consumers want a flat record) produces one ``ScoredObservation``.
The dataclass carries the score itself plus enough lineage that Layer 5
backtests and Layer 6 reports can reproduce it without re-running the
scorer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


class CompositeBuildError(Exception):
    """Raised when composite construction fails a guard (double counting,
    signal-type misuse) or precondition (component missing, unit mismatch)."""


@dataclass
class ScoredObservation:
    """One scored observation produced by a Layer 3 scorer.

    See ``LAYER_3_BUILD_SPEC.md`` §3.3 for the exhaustive field list. All
    fields are required at construction time; pass ``None`` / empty dict
    only where the contract permits.
    """

    as_of: pd.Timestamp
    score_type: str                                  # "CRPS" | "CDRS" | "REGIME"
    score_value: float                               # ∈ [0, 1]

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

    # ---- Bag of everything else (regime_state_source, model_version, ...) ----
    metadata_extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.score_value <= 1.0:
            raise ValueError(
                f"score_value={self.score_value} must be in [0, 1] "
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
        if self.regime_state not in {"expansion", "late-cycle", "recession"}:
            raise ValueError(
                f"regime_state={self.regime_state!r} not in valid set"
            )

    def to_dict(self) -> dict[str, Any]:
        """Flat-dict view for serialization / debugging."""
        return {
            "as_of": self.as_of.isoformat(),
            "score_type": self.score_type,
            "score_value": self.score_value,
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
            "metadata_extra": dict(self.metadata_extra),
        }


__all__ = ["CompositeBuildError", "ScoredObservation"]
