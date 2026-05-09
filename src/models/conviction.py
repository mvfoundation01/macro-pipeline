"""Three-field conviction split (Layer 1.5B.3).

ChatGPT review issue #6: the original "conviction 1-10" scalar conflated
three orthogonal dimensions — how reliable is the inference, how clean
is the data pipeline, and how actionable is the signal in a real
portfolio. Collapsing them hides which one is driving the headline.

Dimensions
----------
- ``statistical_reliability``: OOS AUC, OOS Brier, coefficient stability
- ``operational_reliability``: latency, revision risk, source quality
- ``portfolio_actionability``: payoff asymmetry, implementation cost,
  signal-horizon match

Aggregates
----------
Two aggregates are exposed because the right one depends on the use case:
- ``aggregate_conservative()``: ``min`` across the three. Recommended for
  position sizing (fractional Kelly) — a chain is as strong as its
  weakest link.
- ``aggregate_geomean()``: weighted geometric mean. Recommended for
  ranking comparisons where smooth gradients are preferred over the
  hard-min discontinuity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ConvictionProfile:
    """Three orthogonal conviction dimensions, each on a 0-10 scale.

    Never collapsed into a single field implicitly — callers must pick
    an aggregate function explicitly so the choice is visible at the
    call site.
    """
    statistical_reliability: float
    operational_reliability: float
    portfolio_actionability: float

    def __post_init__(self) -> None:
        for name, val in [
            ("statistical_reliability", self.statistical_reliability),
            ("operational_reliability", self.operational_reliability),
            ("portfolio_actionability", self.portfolio_actionability),
        ]:
            if not 0 <= val <= 10:
                raise ValueError(f"{name}={val} must be in [0, 10]")

    # ---- Aggregates (explicit, never default-implicit) ----
    def aggregate_conservative(self) -> float:
        """``min`` across all three dimensions. Recommended for position sizing."""
        return min(
            self.statistical_reliability,
            self.operational_reliability,
            self.portfolio_actionability,
        )

    def aggregate_geomean(
        self,
        *,
        weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
    ) -> float:
        """Weighted geometric mean across the three dimensions.

        ``weights`` are unnormalized; the function normalizes internally.
        Returns 0 if any dimension is 0 (geometric-mean property — keeps
        the "weakest link still kills you" semantics but smoother than min).
        """
        if any(w < 0 for w in weights):
            raise ValueError("weights must be non-negative")
        w_sum = sum(weights)
        if w_sum <= 0:
            raise ValueError("weights must sum to a positive value")
        w = [wi / w_sum for wi in weights]
        vals = [
            self.statistical_reliability,
            self.operational_reliability,
            self.portfolio_actionability,
        ]
        if any(v == 0 for v in vals):
            return 0.0
        log_sum = sum(wi * math.log(v) for wi, v in zip(w, vals))
        return math.exp(log_sum)

    def to_dict(self) -> dict[str, float]:
        return {
            "statistical_reliability": self.statistical_reliability,
            "operational_reliability": self.operational_reliability,
            "portfolio_actionability": self.portfolio_actionability,
        }


# ---------------------------------------------------------------------------
# Component scoring helpers (0-10 outputs, ChatGPT 2026-05-09 spec)
# ---------------------------------------------------------------------------
def compute_statistical_reliability(
    *,
    oos_auc: float,
    oos_brier: float,
    coefficient_stability: float,
) -> float:
    """0-10 score: rewards OOS performance + coefficient stability.

    Inputs are 0-1. Brier is converted to (1 - brier) since lower Brier
    is better.
    """
    for name, val in [
        ("oos_auc", oos_auc),
        ("oos_brier", oos_brier),
        ("coefficient_stability", coefficient_stability),
    ]:
        if not 0 <= val <= 1:
            raise ValueError(f"{name}={val} must be in [0, 1]")
    return 10.0 * (
        0.4 * oos_auc
        + 0.3 * (1 - oos_brier)
        + 0.3 * coefficient_stability
    )


def compute_operational_reliability(
    *,
    latency_days: int,
    revision_risk: float,
    source_quality: float,
) -> float:
    """0-10 score: penalizes lag, revisions, and low source quality.

    ``latency_days`` is the publication lag (raw days). ``revision_risk``
    and ``source_quality`` are 0-1.
    """
    if latency_days < 0:
        raise ValueError(f"latency_days must be >= 0, got {latency_days}")
    for name, val in [("revision_risk", revision_risk), ("source_quality", source_quality)]:
        if not 0 <= val <= 1:
            raise ValueError(f"{name}={val} must be in [0, 1]")
    latency_score = max(0.0, 1.0 - latency_days / 30.0)  # 0 if 30+ days lag
    return 10.0 * (
        0.4 * latency_score
        + 0.3 * (1 - revision_risk)
        + 0.3 * source_quality
    )


def compute_portfolio_actionability(
    *,
    payoff_asymmetry: float,
    implementation_cost: float,
    signal_horizon_match: float,
) -> float:
    """0-10 score: rewards right-tail payoff and low cost.

    ``payoff_asymmetry`` is right-tail vs left-tail balance (0-1, 1 =
    fully right-skewed). ``implementation_cost`` 0-1, lower is better.
    ``signal_horizon_match`` 0-1, 1 = matches investor horizon.
    """
    for name, val in [
        ("payoff_asymmetry", payoff_asymmetry),
        ("implementation_cost", implementation_cost),
        ("signal_horizon_match", signal_horizon_match),
    ]:
        if not 0 <= val <= 1:
            raise ValueError(f"{name}={val} must be in [0, 1]")
    return 10.0 * (
        0.4 * payoff_asymmetry
        + 0.3 * (1 - implementation_cost)
        + 0.3 * signal_horizon_match
    )


__all__ = [
    "ConvictionProfile",
    "compute_statistical_reliability",
    "compute_operational_reliability",
    "compute_portfolio_actionability",
]
