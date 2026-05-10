"""CDRS Stage 2 — Trigger (Layer 3C).

Spec: ``LAYER_3_BUILD_SPEC.md`` §6.5 + Strategic Claude 3C kickoff.

Five components, equal-weighted (0.20 each) when all five are present.
``T3 (CBOE_GAMMA)`` only has data from 2022-12-12 onward — for any
``as_of`` before that, T3 is dropped and the remaining four components
are proportionally renormalized to 0.25 each (D9 graceful degradation).

| # | Component               | Indicator     | Transform                                |
|---|-------------------------|---------------|------------------------------------------|
| T1 | HY OAS 30D RoC         | BAMLH0A0HYM2  | Δ(% over 30d) × 100 bps → sigmoid(...)   |
| T2 | VIX 12M percentile     | VIX_YAHOO     | trailing 252 business-day percentile     |
| T3 | Dealer gamma sign (D9) | CBOE_GAMMA    | binary: latest < 0 → 1.0 else 0.0        |
| T4 | Breadth thrust         | S5FI          | 0 at ≥80%, 0.5 at 40%, 1.0 at ≤20%       |
| T5 | MOVE z                 | MOVE          | 12M rolling z-score → sigmoid            |
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from macro_pipeline.access import PitDataContext, load_series
from macro_pipeline.exceptions import legitimate_missing_data_exceptions
from macro_pipeline.scoring.scored_observation import CompositeBuildError

T_COMPONENTS: tuple[str, ...] = (
    "T1_hy_oas_30d_roc",
    "T2_vix_12m_pctile",
    "T3_gamma_sign",
    "T4_breadth_thrust",
    "T5_move_z",
)


@dataclass
class TriggerResult:
    score: float                          # ∈ [0, 1]
    components_normalized: dict[str, float]
    components_raw: dict[str, float]
    weights: dict[str, float]             # post-renormalization (D9)
    active_components: list[str]
    inactive_components: list[str]
    method: str = "trigger_v1"
    as_of: pd.Timestamp | None = None
    notes: list[str] = field(default_factory=list)


def _pit_series(indicator_id: str, ctx: PitDataContext) -> pd.Series:
    bundle = load_series(indicator_id, as_of=ctx.as_of)
    return bundle.data.dropna()


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _percentile_rank(series: pd.Series, value: float) -> float:
    s = series.dropna()
    if s.empty or not math.isfinite(value):
        return float("nan")
    return float((s <= value).mean())


# ---- T1 -------------------------------------------------------------------

def t1_hy_oas_30d_roc(ctx: PitDataContext) -> tuple[float | None, float | None, str]:
    """30D rate of change in HY OAS (bps), sigmoid'd around +50bps."""
    try:
        hy = _pit_series("BAMLH0A0HYM2", ctx)
    except legitimate_missing_data_exceptions() as exc:
        return None, None, f"T1 HY load error: {type(exc).__name__}: {exc}"
    if hy.empty:
        return None, None, "T1 HY OAS empty in PIT view (starts 1996-12)"
    cutoff = hy.index[-1] - pd.Timedelta(days=30)
    past = hy[hy.index <= cutoff]
    if past.empty:
        return None, None, "T1 HY <30d of history at as_of"
    delta_bps = (float(hy.iloc[-1]) - float(past.iloc[-1])) * 100.0
    # Sigmoid centered around +50bps with width ~25bps (so +50bps → 0.5,
    # +100bps → 0.88, 0bps → 0.12).
    score = _sigmoid((delta_bps - 50.0) / 25.0)
    return score, delta_bps, ""


# ---- T2 -------------------------------------------------------------------

_VIX_PCTILE_WINDOW = 252  # ~12M business days


def t2_vix_12m_pctile(ctx: PitDataContext) -> tuple[float | None, float | None, str]:
    """Trailing 12M percentile rank of latest VIX."""
    try:
        vix = _pit_series("VIX_YAHOO", ctx)
    except legitimate_missing_data_exceptions() as exc:
        return None, None, f"T2 VIX load error: {type(exc).__name__}: {exc}"
    if vix.empty:
        return None, None, "T2 VIX empty in PIT view (starts 1990-01)"
    window = vix.tail(_VIX_PCTILE_WINDOW)
    if len(window) < 60:
        return None, None, "T2 VIX <60 days of history"
    raw = float(vix.iloc[-1])
    pct = _percentile_rank(window, raw)
    return pct, raw, ""


# ---- T3 -------------------------------------------------------------------

def t3_gamma_sign(ctx: PitDataContext) -> tuple[float | None, float | None, str]:
    """Binary: 1.0 if latest CBOE_GAMMA < 0 (negative gamma → triggers).

    D9: returns ``None`` (and is dropped) when CBOE_GAMMA has no PIT-safe
    data at the as_of (CBOE_GAMMA only starts 2022-12-12).
    """
    try:
        gamma = _pit_series("CBOE_GAMMA", ctx)
    except legitimate_missing_data_exceptions() as exc:
        return None, None, f"T3 gamma load error: {type(exc).__name__}: {exc}"
    if gamma.empty:
        return None, None, "T3 CBOE_GAMMA empty in PIT view (starts 2022-12-12) — D9 drop"
    raw = float(gamma.iloc[-1])
    score = 1.0 if raw < 0 else 0.0
    return score, raw, ""


# ---- T4 -------------------------------------------------------------------

def t4_breadth_thrust(ctx: PitDataContext) -> tuple[float | None, float | None, str]:
    """S5FI breadth: linear ramp 0 at ≥80%, 0.5 at 40%, 1.0 at ≤20%."""
    try:
        s5fi = _pit_series("S5FI", ctx)
    except legitimate_missing_data_exceptions() as exc:
        return None, None, f"T4 S5FI load error: {type(exc).__name__}: {exc}"
    if s5fi.empty:
        return None, None, "T4 S5FI empty in PIT view (starts 2006-12)"
    raw = float(s5fi.iloc[-1])
    if raw >= 80.0:
        score = 0.0
    elif raw <= 20.0:
        score = 1.0
    else:
        # Map 80 -> 0.0, 40 -> 0.5, 20 -> 1.0 (piecewise linear, anchored).
        score = (
            (80.0 - raw) / 80.0          # 80 -> 0, 40 -> 0.5
            if raw >= 40.0
            else 0.5 + (40.0 - raw) / 40.0  # 40 -> 0.5, 20 -> 1.0
        )
    return score, raw, ""


# ---- T5 -------------------------------------------------------------------

_MOVE_Z_WINDOW = 252  # ~12M business days


def t5_move_z(ctx: PitDataContext) -> tuple[float | None, float | None, str]:
    """12M rolling z-score on MOVE → sigmoid."""
    try:
        move = _pit_series("MOVE", ctx)
    except legitimate_missing_data_exceptions() as exc:
        return None, None, f"T5 MOVE load error: {type(exc).__name__}: {exc}"
    if move.empty:
        return None, None, "T5 MOVE empty in PIT view (starts 2002-11)"
    window = move.tail(_MOVE_Z_WINDOW)
    if len(window) < 60:
        return None, None, "T5 MOVE <60 days of history"
    mu = float(window.mean())
    sigma = float(window.std(ddof=1))
    if sigma <= 0:
        return None, None, "T5 MOVE 12M std non-positive"
    raw = float(move.iloc[-1])
    z = (raw - mu) / sigma
    return _sigmoid(z), z, ""


# ---- aggregator -----------------------------------------------------------

_T_COMPONENT_FUNCTIONS = {
    "T1_hy_oas_30d_roc":  t1_hy_oas_30d_roc,
    "T2_vix_12m_pctile":  t2_vix_12m_pctile,
    "T3_gamma_sign":      t3_gamma_sign,
    "T4_breadth_thrust":  t4_breadth_thrust,
    "T5_move_z":          t5_move_z,
}


def compute_trigger(ctx: PitDataContext) -> TriggerResult:
    """Compute Stage-2 trigger score T at ``ctx.as_of`` (D9 graceful)."""
    components_normalized: dict[str, float] = {}
    components_raw: dict[str, float] = {}
    active: list[str] = []
    inactive: list[str] = []
    notes: list[str] = []

    for name, fn in _T_COMPONENT_FUNCTIONS.items():
        normalized, raw, note = fn(ctx)
        if note:
            notes.append(note)
        if normalized is None or not math.isfinite(normalized):
            inactive.append(name)
            continue
        components_normalized[name] = float(normalized)
        components_raw[name] = float(raw) if raw is not None and math.isfinite(raw) else float("nan")
        active.append(name)

    if not active:
        raise CompositeBuildError(
            f"CDRS Trigger: no active components at "
            f"as_of={ctx.as_of.date() if ctx.as_of else None}. "
            f"Notes: {notes}"
        )

    weight_each = 1.0 / len(active)
    weights = {name: weight_each for name in active}
    score = float(np.average([components_normalized[n] for n in active]))
    return TriggerResult(
        score=score,
        components_normalized=components_normalized,
        components_raw=components_raw,
        weights=weights,
        active_components=active,
        inactive_components=inactive,
        as_of=ctx.as_of,
        notes=notes,
    )


__all__ = [
    "T_COMPONENTS",
    "TriggerResult",
    "compute_trigger",
    "t1_hy_oas_30d_roc",
    "t2_vix_12m_pctile",
    "t3_gamma_sign",
    "t4_breadth_thrust",
    "t5_move_z",
]
