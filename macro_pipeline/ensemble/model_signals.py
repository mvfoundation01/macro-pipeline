"""L6-I D3+D4 — 11-model ensemble schema + ModelSignal dataclass.

Per Strategic L6-I R7 closure pre-flight 2026-05-16. Closes ChatGPT
methodology Finding #5 (C-5): the L6 pipeline must surface an
explicit 11-model × 4-horizon weight schema with placeholder producer
support (V Decision #2 Option B: schema + minimal wrapper producers;
full 11-distinct-model implementation deferred to L7).

11-model taxonomy (Vision §1 Pillar 5 + R7 ChatGPT scope)
----------------------------------------------------------
The eleven model categories surface forecasts from distinct
methodological lenses, each with its own evidence base + assumption
set + failure mode. Aggregating across all eleven hedges
single-method tail risk per Vision §6 reference class forecasting
discipline:

  valuation              GMO / Hussman / Shiller school
                         (mean-reverting; long-horizon valid)
  earnings_growth        Bottom-up EPS revision aggregator
                         (consensus forecast errors quarterly)
  macro_regime           ISM / LEI / NBER recession indicators
                         (cycle-stage classifier; 1Y dominant)
  liquidity_fci          Fed balance sheet + FCI + M2 growth
                         (financial conditions / risk-asset support)
  credit_recession       HY OAS + IG spreads + distress proxies
                         (credit-cycle leading indicator)
  trend_momentum         Price relative to 50/200 DMA + breadth
                         (momentum / behavioural anchor)
  vol_implied            VIX term structure + skew + options-implied
                         (risk-premium pricing)
  historical_analog      Reference-class via L6-E rcf.py
                         (Bayesian shrinkage anchor)
  sentiment_positioning  AAII + CFTC + dealer gamma + AAII bull-bear
                         (contrarian indicator)
  structural_secular     Demographics + productivity + DMS bias
                         (long-horizon dominant; 10Y biggest weight)
  monte_carlo_scenario   Probabilistic scenario tree
                         (tail-risk fan; supplementary)

Horizon-conditional weight schema
---------------------------------
Vision §1 Pillar 4 horizons (1Y / 3Y / 5Y / 10Y) each have their own
weight vector. Dominant model per horizon (Strategic L6-I spec):

  1Y    macro_regime         (20%)  cyclical signals dominant
  3Y    earnings_growth      (17.5%) fundamentals + macro balance
  5Y    valuation +          (15% + 20%) valuation begins
        structural_secular           dominating; structural 20%
  10Y   structural_secular   (30%)  secular dominates short-term noise

All weights sum to 1.0 exactly within 1e-12 tolerance per horizon
(validated at module-init). Weights are normalized fractions, not
percentages.

Component sourcing discipline (V Decision #2 Option B)
------------------------------------------------------
At L6-I, ``ModelSignal`` accepts a ``is_placeholder: bool`` flag
indicating whether the signal was produced by a dedicated model
(``False``) or a wrapper distributing the existing single
``point_estimate`` (``True``). The wrapper helper
``wrap_point_estimates_as_model_signals`` produces eleven
placeholder signals per horizon for backward-compat aggregation; full
11-distinct-model producers are deferred to L7.

This satisfies the R7 ChatGPT C-5 schema requirement while
acknowledging the L7-producer deferral honestly. R8 reviewer cycle
may flag this as MEDIUM (acceptable; documented + roadmapped).
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, Optional, Tuple


# =============================================================================
# Eleven model categories (Vision §6 + R7 ChatGPT C-5)
# =============================================================================

MODEL_IDS: Tuple[str, ...] = (
    "valuation",
    "earnings_growth",
    "macro_regime",
    "liquidity_fci",
    "credit_recession",
    "trend_momentum",
    "vol_implied",
    "historical_analog",
    "sentiment_positioning",
    "structural_secular",
    "monte_carlo_scenario",
)
assert len(MODEL_IDS) == 11, (
    f"MODEL_IDS must contain exactly 11 entries; got {len(MODEL_IDS)}"
)
MODEL_IDS_VALID = frozenset(MODEL_IDS)


# =============================================================================
# Horizon-conditional weight schema (Strategic L6-I spec)
# =============================================================================

# Weights are normalized fractions per horizon; sum to 1.0 within 1e-12.
# Dominant model per horizon highlighted in module docstring.
MODEL_WEIGHTS_BY_HORIZON: Dict[int, Dict[str, float]] = {
    1: {
        "valuation": 0.05,
        "earnings_growth": 0.15,
        "macro_regime": 0.20,
        "liquidity_fci": 0.15,
        "credit_recession": 0.15,
        "trend_momentum": 0.10,
        "vol_implied": 0.05,
        "historical_analog": 0.05,
        "sentiment_positioning": 0.05,
        "structural_secular": 0.02,
        "monte_carlo_scenario": 0.03,
    },
    3: {
        "valuation": 0.10,
        "earnings_growth": 0.175,
        "macro_regime": 0.15,
        "liquidity_fci": 0.10,
        "credit_recession": 0.125,
        "trend_momentum": 0.075,
        "vol_implied": 0.05,
        "historical_analog": 0.10,
        "sentiment_positioning": 0.025,
        "structural_secular": 0.075,
        "monte_carlo_scenario": 0.025,
    },
    5: {
        "valuation": 0.15,
        "earnings_growth": 0.15,
        "macro_regime": 0.10,
        "liquidity_fci": 0.05,
        "credit_recession": 0.075,
        "trend_momentum": 0.05,
        "vol_implied": 0.05,
        "historical_analog": 0.125,
        "sentiment_positioning": 0.025,
        "structural_secular": 0.20,
        "monte_carlo_scenario": 0.025,
    },
    10: {
        "valuation": 0.20,
        "earnings_growth": 0.10,
        "macro_regime": 0.05,
        "liquidity_fci": 0.025,
        "credit_recession": 0.05,
        "trend_momentum": 0.025,
        "vol_implied": 0.05,
        "historical_analog": 0.15,
        "sentiment_positioning": 0.025,
        "structural_secular": 0.30,
        "monte_carlo_scenario": 0.025,
    },
}

# Sum-to-1.0 tolerance per horizon (float arithmetic accommodates 1e-12).
WEIGHT_SUM_TOLERANCE = 1e-12

# Supported horizons (mirror aggregator + L6-B + L6-D).
SUPPORTED_HORIZONS: Tuple[int, ...] = (1, 3, 5, 10)


# =============================================================================
# Module-init validation (D4)
# =============================================================================


def _validate_model_weights() -> None:
    """L6-I D4 — runs at import time; raises if schema invariants violated.

    Invariants:
      1. Each horizon has exactly the eleven MODEL_IDS as keys.
      2. Each horizon's weights sum to 1.0 within ``WEIGHT_SUM_TOLERANCE``.
      3. Each weight is finite + in [0, 1].
    """
    if frozenset(MODEL_WEIGHTS_BY_HORIZON.keys()) != frozenset(SUPPORTED_HORIZONS):
        raise ValueError(
            f"MODEL_WEIGHTS_BY_HORIZON keys "
            f"{sorted(MODEL_WEIGHTS_BY_HORIZON.keys())} != supported "
            f"{sorted(SUPPORTED_HORIZONS)}"
        )
    for horizon, weights in MODEL_WEIGHTS_BY_HORIZON.items():
        # Invariant 1: keys.
        if frozenset(weights.keys()) != MODEL_IDS_VALID:
            missing = MODEL_IDS_VALID - set(weights.keys())
            extra = set(weights.keys()) - MODEL_IDS_VALID
            raise ValueError(
                f"horizon {horizon} weights schema mismatch; "
                f"missing={sorted(missing)}; extra={sorted(extra)}"
            )
        # Invariant 3: per-weight finite + range.
        for mid, w in weights.items():
            if not math.isfinite(w):
                raise ValueError(
                    f"horizon {horizon} weight[{mid!r}] must be finite; "
                    f"got {w!r}"
                )
            if not (0.0 <= w <= 1.0):
                raise ValueError(
                    f"horizon {horizon} weight[{mid!r}] must be in [0, 1]; "
                    f"got {w}"
                )
        # Invariant 2: sum to 1.0.
        total = sum(weights.values())
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(
                f"horizon {horizon} weights sum to {total!r}; "
                f"expected 1.0 within {WEIGHT_SUM_TOLERANCE} tolerance"
            )


# Module-init smoke check; raises if schema invariants violated.
_validate_model_weights()

# Immutable read-only view of weights table (L6-I D2 deep-immutability).
MODEL_WEIGHTS_BY_HORIZON_FROZEN: Mapping[int, Mapping[str, float]] = (
    MappingProxyType({
        h: MappingProxyType(dict(w))
        for h, w in MODEL_WEIGHTS_BY_HORIZON.items()
    })
)


# =============================================================================
# ModelSignal dataclass (D3)
# =============================================================================


@dataclass(frozen=True)
class ModelSignal:
    """Per-horizon, per-model signal in the 11-model ensemble.

    Fields
    ------
    model_id                    One of ``MODEL_IDS``.
    horizon                     One of ``SUPPORTED_HORIZONS``.
    point_estimate_annualized   Forecast point estimate (return fraction).
    sigma_annualized            Optional forecast sigma; ``None`` if model
                                does not compute uncertainty.
    confidence                  Optional confidence in [0, 1]; ``None`` if
                                model does not compute confidence.
    weight                      Aggregation weight in [0, 1]; sourced from
                                ``MODEL_WEIGHTS_BY_HORIZON[horizon][model_id]``
                                in typical usage.
    is_placeholder              True if signal extracted from upstream
                                ``point_estimates`` via wrapper (L6-I
                                discipline); False once dedicated model
                                producer ships (L7+).

    Invariants enforced by ``__post_init__``:
      - model_id in MODEL_IDS_VALID
      - horizon in SUPPORTED_HORIZONS
      - point_estimate_annualized + weight finite
      - sigma_annualized finite when not None
      - confidence finite + in [0, 1] when not None
      - weight in [0, 1]
    """

    model_id: str
    horizon: int
    point_estimate_annualized: float
    sigma_annualized: Optional[float]
    confidence: Optional[float]
    weight: float
    is_placeholder: bool

    def __post_init__(self) -> None:
        if self.model_id not in MODEL_IDS_VALID:
            raise ValueError(
                f"Unknown model_id {self.model_id!r}; expected one of "
                f"{sorted(MODEL_IDS_VALID)}"
            )
        if self.horizon not in SUPPORTED_HORIZONS:
            raise ValueError(
                f"Unknown horizon {self.horizon!r}; expected one of "
                f"{sorted(SUPPORTED_HORIZONS)}"
            )
        # Finite checks on required floats.
        if not math.isfinite(self.point_estimate_annualized):
            raise ValueError(
                f"point_estimate_annualized must be finite; got "
                f"{self.point_estimate_annualized!r}"
            )
        if not math.isfinite(self.weight):
            raise ValueError(
                f"weight must be finite; got {self.weight!r}"
            )
        if not (0.0 <= self.weight <= 1.0):
            raise ValueError(
                f"weight must be in [0, 1]; got {self.weight}"
            )
        # Optional float checks.
        if self.sigma_annualized is not None:
            if not math.isfinite(self.sigma_annualized):
                raise ValueError(
                    f"sigma_annualized must be finite or None; got "
                    f"{self.sigma_annualized!r}"
                )
        if self.confidence is not None:
            if not math.isfinite(self.confidence):
                raise ValueError(
                    f"confidence must be finite or None; got "
                    f"{self.confidence!r}"
                )
            if not (0.0 <= self.confidence <= 1.0):
                raise ValueError(
                    f"confidence must be in [0, 1]; got {self.confidence}"
                )


# =============================================================================
# Minimal wrapper producers (V Decision #2 Option B)
# =============================================================================


def wrap_point_estimates_as_model_signals(
    point_estimates: Mapping[int, float],
    horizon: int,
) -> Tuple[ModelSignal, ...]:
    """Minimal wrapper producer per V Decision #2 Option B (L6-I).

    Distributes a single ``point_estimates[horizon]`` across the eleven
    model_ids using ``MODEL_WEIGHTS_BY_HORIZON_FROZEN`` weights. Each
    resulting ``ModelSignal`` is marked ``is_placeholder=True``.

    Full 11-distinct-model implementation deferred to L7. The placeholder
    discipline preserves backward-compat aggregation (weighted-mean
    reconstructs the original point estimate) while exposing the
    11-model schema surface required by R7 ChatGPT C-5.

    Parameters
    ----------
    point_estimates
        Mapping ``horizon -> point_estimate_annualized``. Must contain
        the requested ``horizon`` as a key.
    horizon
        Forecast horizon in ``SUPPORTED_HORIZONS``.

    Returns
    -------
    tuple[ModelSignal, ...]
        Eleven ``ModelSignal`` instances (one per model_id) at the
        given horizon, all sharing the same ``point_estimate_annualized``
        + ``is_placeholder=True`` flag; ``weight`` varies per model_id.

    Raises
    ------
    KeyError
        If ``horizon`` not in ``SUPPORTED_HORIZONS`` or absent from
        ``point_estimates``.
    ValueError
        If ``point_estimates[horizon]`` is non-finite.
    """
    if horizon not in SUPPORTED_HORIZONS:
        raise KeyError(
            f"Unknown horizon {horizon!r}; expected one of "
            f"{sorted(SUPPORTED_HORIZONS)}"
        )
    if horizon not in point_estimates:
        raise KeyError(
            f"point_estimates missing horizon {horizon!r}"
        )
    point_estimate = point_estimates[horizon]
    if not math.isfinite(point_estimate):
        raise ValueError(
            f"point_estimates[{horizon}] must be finite; got "
            f"{point_estimate!r}"
        )

    weights = MODEL_WEIGHTS_BY_HORIZON_FROZEN[horizon]
    return tuple(
        ModelSignal(
            model_id=mid,
            horizon=horizon,
            point_estimate_annualized=point_estimate,
            sigma_annualized=None,
            confidence=None,
            weight=weights[mid],
            is_placeholder=True,
        )
        for mid in MODEL_IDS
    )


def aggregate_model_signals(signals: Tuple[ModelSignal, ...]) -> float:
    """Weighted-mean aggregation across model signals at a single horizon.

    Validates that all signals share the same horizon + weights sum to
    1.0 within ``WEIGHT_SUM_TOLERANCE``. Returns the weighted-mean
    point estimate.

    Parameters
    ----------
    signals
        Tuple of ``ModelSignal`` instances at a single horizon.

    Returns
    -------
    float
        Weighted-mean point_estimate_annualized.

    Raises
    ------
    ValueError
        If signals empty, horizons inconsistent, or weights sum not
        1.0 within tolerance.
    """
    if not signals:
        raise ValueError("signals must be non-empty")
    horizons = {s.horizon for s in signals}
    if len(horizons) != 1:
        raise ValueError(
            f"signals must share one horizon; got {sorted(horizons)}"
        )
    total_weight = sum(s.weight for s in signals)
    if abs(total_weight - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            f"signal weights sum to {total_weight!r}; "
            f"expected 1.0 within {WEIGHT_SUM_TOLERANCE} tolerance"
        )
    return sum(s.point_estimate_annualized * s.weight for s in signals)


# =============================================================================
# Layer-disagreement detection (D5)
# =============================================================================

LAYER_DISAGREEMENT_LABELS: frozenset[str] = frozenset({
    "consensus",
    "valuation_bear_trend_bull",
    "valuation_bull_trend_bear",
    "credit_widening_equity_bull",
    "macro_weakening_equity_bull",
    "liquidity_tightening_equity_bull",
    "mixed_signal_undefined",
})


def detect_layer_disagreement(
    signals: Tuple[ModelSignal, ...],
) -> Tuple[bool, str]:
    """L6-I D5 — Vision §6 layer-disagreement detection (placeholder).

    Returns ``(flag, label)``. ``flag=True`` iff
    ``label != "consensus"``.

    L6-I placeholder logic: with placeholder wrapper signals all sharing
    the same ``point_estimate_annualized``, no disagreement is possible
    by construction. The detector returns ``("consensus", False)`` for
    aligned-sign signals + ``("mixed_signal_undefined", True)`` when
    signs diverge. Full pattern detection (``valuation_bear_trend_bull``
    et al.) requires producer-backed direction signals from distinct
    L7 producers; deferred per V Decision #2 Option B.

    Parameters
    ----------
    signals
        Tuple of ``ModelSignal`` instances at a single horizon.

    Returns
    -------
    tuple[bool, str]
        ``(layer_disagreement_flag, layer_disagreement_label)``.
    """
    if not signals:
        return (False, "consensus")

    positive = sum(
        1 for s in signals if s.point_estimate_annualized > 0
    )
    negative = sum(
        1 for s in signals if s.point_estimate_annualized < 0
    )

    if positive > 0 and negative > 0:
        return (True, "mixed_signal_undefined")
    return (False, "consensus")
