"""Revised confidence scoring (Layer 1.5B.2).

ChatGPT review FAIL #5: the original formula gave Sample Size only 10%
of weight while pushing Theoretical Foundation to 15%. With 8-9
recession events and 11 non-overlapping 10Y windows, that distribution
treats the most uncertainty-driving variable (effective sample size) as
a minor input — production research should do the opposite.

Revised weights
---------------
    DataQuality           20%
    TrackRecord           20%
    RegimeStability       15%
    TheoreticalFoundation 10%
    SampleAdequacy        30%   (was 10%)
    − OODPenalty           up to 100% subtractive
    − RevisionPenalty      up to 100% subtractive

Horizon caps
------------
    1Y:  85%   (only if OOS-calibrated)
    3Y:  75%
    5Y:  70%
    10Y: 65%   (NOT 85% — N_eff ≈ 11 non-overlapping windows)

Sample-adequacy ratio
---------------------
``sqrt(N_eff / N_target)`` capped at 1. Rooted because we want a
diminishing-returns shape — going from 5→20 events should help more
than going from 100→115.
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Reference targets (per ChatGPT 2026-05-09)
# ---------------------------------------------------------------------------
N_TARGET_REGRESSION_LONG_HORIZON = 30   # for 5Y/10Y forward returns
N_TARGET_RECESSION_EVENTS = 20          # for binary recession models


# ---------------------------------------------------------------------------
# Horizon caps
# ---------------------------------------------------------------------------
CONFIDENCE_CAPS: dict[str, float] = {
    "1Y": 0.85,
    "3Y": 0.75,
    "5Y": 0.70,
    "10Y": 0.65,
}


# ---------------------------------------------------------------------------
# Component weights (must sum to 0.95 — the remaining 0.05 is "headroom"
# absorbed by penalties without driving the headline below 0).
# ---------------------------------------------------------------------------
W_DATA_QUALITY = 0.20
W_TRACK_RECORD = 0.20
W_REGIME_STABILITY = 0.15
W_THEORETICAL_FOUNDATION = 0.10
W_SAMPLE_ADEQUACY = 0.30
_WEIGHT_SUM = (
    W_DATA_QUALITY + W_TRACK_RECORD + W_REGIME_STABILITY
    + W_THEORETICAL_FOUNDATION + W_SAMPLE_ADEQUACY
)
assert abs(_WEIGHT_SUM - 0.95) < 1e-9, f"Weights must sum to 0.95, got {_WEIGHT_SUM}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sample_adequacy_ratio(n_eff: int, n_target: int) -> float:
    """``sqrt(N_eff / N_target)`` capped at 1.

    The square root makes the ratio give diminishing returns: each
    additional event matters less past N_target. Below N_target the
    ratio degrades sharply.
    """
    if n_target <= 0:
        raise ValueError(f"n_target must be positive, got {n_target}")
    if n_eff < 0:
        raise ValueError(f"n_eff must be >= 0, got {n_eff}")
    return min(1.0, math.sqrt(n_eff / n_target))


def confidence_score_v2(
    *,
    data_quality: float,
    track_record: float,
    regime_stability: float,
    theoretical_foundation: float,
    sample_adequacy: float,
    ood_penalty: float = 0.0,
    revision_penalty: float = 0.0,
    horizon: str = "1Y",
) -> float:
    """Return a 0-100 confidence score, capped per horizon.

    All input components are 0-1. Penalties are 0-1 (subtracted as
    full points, not weighted). The final score is min(raw, cap*100)
    where the cap is read from ``CONFIDENCE_CAPS[horizon]``. Use
    ``sample_adequacy_ratio`` to compute the ``sample_adequacy`` input.
    """
    for name, val in [
        ("data_quality", data_quality),
        ("track_record", track_record),
        ("regime_stability", regime_stability),
        ("theoretical_foundation", theoretical_foundation),
        ("sample_adequacy", sample_adequacy),
    ]:
        if not 0 <= val <= 1:
            raise ValueError(f"{name}={val} must be in [0, 1]")
    for name, val in [("ood_penalty", ood_penalty), ("revision_penalty", revision_penalty)]:
        if not 0 <= val <= 1:
            raise ValueError(f"{name}={val} must be in [0, 1]")
    if horizon not in CONFIDENCE_CAPS:
        raise KeyError(
            f"Unknown horizon {horizon!r}. Use one of {sorted(CONFIDENCE_CAPS)}."
        )

    raw = (
        data_quality * W_DATA_QUALITY
        + track_record * W_TRACK_RECORD
        + regime_stability * W_REGIME_STABILITY
        + theoretical_foundation * W_THEORETICAL_FOUNDATION
        + sample_adequacy * W_SAMPLE_ADEQUACY
    ) * 100.0 - ood_penalty * 100.0 - revision_penalty * 100.0

    cap = CONFIDENCE_CAPS[horizon] * 100.0
    return max(0.0, min(raw, cap))


__all__ = [
    "CONFIDENCE_CAPS",
    "N_TARGET_RECESSION_EVENTS",
    "N_TARGET_REGRESSION_LONG_HORIZON",
    "W_DATA_QUALITY",
    "W_REGIME_STABILITY",
    "W_SAMPLE_ADEQUACY",
    "W_THEORETICAL_FOUNDATION",
    "W_TRACK_RECORD",
    "confidence_score_v2",
    "sample_adequacy_ratio",
]
