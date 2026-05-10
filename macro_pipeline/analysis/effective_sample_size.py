"""Effective sample size helpers for the R^2 master panel (Layer 3D).

Spec: ``LAYER_3_BUILD_SPEC.md`` §7.6.

For overlapping forward-return regressions, ``n_nominal`` (raw count of
observations) overstates the effective degrees of freedom because
adjacent windows overlap. ``n_eff_nonoverlap = n_nominal // horizon_months``
is the count of strictly non-overlapping windows.

Verdict tags:

  | verdict        | condition                                    |
  |----------------|----------------------------------------------|
  | NO_OVERLAP     | n_nominal == 0 (no shared data)              |
  | UNDERPOWERED   | n_nominal < 24 OR n_eff_nonoverlap < 3       |
  | FULL           | both thresholds met                          |

Reports MUST display BOTH ``n_nominal`` and ``n_eff_nonoverlap`` per
spec §7.6 (Sample-size honesty, Dim 10).
"""
from __future__ import annotations

VERDICT_FULL = "FULL"
VERDICT_UNDERPOWERED = "UNDERPOWERED"
VERDICT_NO_OVERLAP = "NO_OVERLAP"

UNDERPOWERED_N_NOMINAL_MIN = 24
UNDERPOWERED_N_EFF_MIN = 3


def n_eff_nonoverlap(n_nominal: int, horizon_months: int) -> int:
    """Return the number of strictly non-overlapping ``horizon_months``-windows
    available in ``n_nominal`` consecutive monthly observations."""
    if horizon_months <= 0:
        raise ValueError(f"horizon_months must be positive, got {horizon_months}")
    if n_nominal < 0:
        raise ValueError(f"n_nominal must be >= 0, got {n_nominal}")
    return n_nominal // horizon_months


def classify_verdict(n_nominal: int, horizon_months: int) -> str:
    """Return one of NO_OVERLAP / UNDERPOWERED / FULL."""
    if n_nominal <= 0:
        return VERDICT_NO_OVERLAP
    n_eff = n_eff_nonoverlap(n_nominal, horizon_months)
    if n_nominal < UNDERPOWERED_N_NOMINAL_MIN or n_eff < UNDERPOWERED_N_EFF_MIN:
        return VERDICT_UNDERPOWERED
    return VERDICT_FULL


def is_underpowered(verdict: str) -> bool:
    return verdict == VERDICT_UNDERPOWERED


__all__ = [
    "UNDERPOWERED_N_EFF_MIN",
    "UNDERPOWERED_N_NOMINAL_MIN",
    "VERDICT_FULL",
    "VERDICT_NO_OVERLAP",
    "VERDICT_UNDERPOWERED",
    "classify_verdict",
    "is_underpowered",
    "n_eff_nonoverlap",
]
