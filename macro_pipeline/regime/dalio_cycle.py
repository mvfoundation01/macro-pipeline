"""Dalio long-term debt-cycle classifier (Layer 3A, rule-based heuristic v1).

Spec: ``LAYER_3_BUILD_SPEC.md`` §4.3.3.

Phases (≥ 2-of-3 triggers per phase):

| Phase         | Triggers                                                      |
|---------------|---------------------------------------------------------------|
| early         | D rank < 30%;  D YoY > 0;     (R − R*) > +1pp                  |
| mid           | 30% ≤ D ≤ 70%;  abs(R − R*) < 1pp;  5 ≤ E ≤ 12                  |
| late          | D rank > 70%;  (R − R*) < 0;       E > 8                       |
| deleveraging  | D YoY < 0;  D below 5y avg;     E falling vs 5y avg            |

Inputs (all PIT-safe):
  D    = ``GFDEGDQ188S`` debt/GDP percentile, with rolling YoY
  R*   = ``HLW_RSTAR`` (vintage-aware)
  R    = real 10Y rate ≈ SHILLER_GS10 − YoY(SHILLER_CPI)
  E    = ``A091RC1Q027SBEA`` (interest payments) / ``FGRECPT`` (receipts) × 100

Tiebreak (more "late-cycle" wins on tie): late > deleveraging > mid > early.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from macro_pipeline.access import PitDataContext, load_series
from macro_pipeline.exceptions import legitimate_missing_data_exceptions

PHASES = ("early", "mid", "late", "deleveraging", "indeterminate")

_TIEBREAK_PRIORITY = {
    "late":          0,
    "deleveraging":  1,
    "mid":           2,
    "early":         3,
    "indeterminate": 4,
}


@dataclass
class DalioResult:
    phase: str
    triggers_hit: dict[str, dict[str, bool | None]]
    metrics: dict[str, float]
    method: str = "rule_based_heuristic_v1"
    as_of: pd.Timestamp | None = None
    notes: list[str] = field(default_factory=list)


def _pit_series(indicator_id: str, ctx: PitDataContext) -> pd.Series:
    bundle = load_series(indicator_id, as_of=ctx.as_of)
    return bundle.data.dropna()


def _percentile_rank(series: pd.Series, value: float) -> float:
    s = series.dropna()
    if s.empty or not np.isfinite(value):
        return float("nan")
    return float((s <= value).mean())


def _yoy_pct(series: pd.Series) -> float:
    """YoY percent change on the last observation, using ~12 months back."""
    s = series.dropna()
    if s.empty:
        return float("nan")
    cutoff = s.index[-1] - pd.DateOffset(years=1)
    past = s[s.index <= cutoff]
    if past.empty:
        return float("nan")
    return float((float(s.iloc[-1]) / float(past.iloc[-1]) - 1.0) * 100.0)


def _real_rate_now(ctx: PitDataContext) -> float | None:
    """Real 10Y yield ≈ nominal 10Y − YoY(CPI). Uses Shiller series."""
    try:
        gs10 = _pit_series("SHILLER_GS10", ctx)
        cpi = _pit_series("SHILLER_CPI", ctx)
    except legitimate_missing_data_exceptions():
        return None
    if gs10.empty or cpi.empty:
        return None
    cpi_yoy = _yoy_pct(cpi)
    if not np.isfinite(cpi_yoy):
        return None
    return float(gs10.iloc[-1]) - cpi_yoy


def _compute_metrics(ctx: PitDataContext) -> tuple[dict[str, float], list[str]]:
    notes: list[str] = []
    m: dict[str, float] = {}

    # ---- Debt / GDP (D) ----
    try:
        d = _pit_series("GFDEGDQ188S", ctx)
        if d.empty:
            notes.append("debt/GDP: empty in PIT view")
        else:
            d_now = float(d.iloc[-1])
            m["debt_gdp_pct"] = d_now
            m["debt_gdp_rank_full"] = _percentile_rank(d, d_now)
            m["debt_gdp_yoy_pct"] = _yoy_pct(d)
            cutoff = d.index[-1] - pd.DateOffset(years=5)
            window = d[d.index >= cutoff]
            if not window.empty:
                m["debt_gdp_5y_avg"] = float(window.mean())
    except legitimate_missing_data_exceptions() as exc:
        notes.append(f"debt/GDP: {type(exc).__name__}: {exc}")

    # ---- Interest expense ratio (E) — A091.../FGRECPT × 100 ----
    try:
        interest = _pit_series("A091RC1Q027SBEA", ctx)
        receipts = _pit_series("FGRECPT", ctx)
        if interest.empty or receipts.empty:
            notes.append("interest/receipts: missing PIT data")
        else:
            i_now = float(interest.iloc[-1])
            r_now = float(receipts.iloc[-1])
            if r_now > 0:
                m["interest_pct_revenue"] = i_now / r_now * 100.0
            # 5y trend
            cutoff = interest.index[-1] - pd.DateOffset(years=5)
            i5 = interest[interest.index >= cutoff]
            r5 = receipts[receipts.index >= cutoff]
            common_idx = i5.index.intersection(r5.index)
            if len(common_idx) >= 4:
                ratio_5y = (i5.loc[common_idx] / r5.loc[common_idx] * 100.0).dropna()
                if not ratio_5y.empty:
                    m["interest_pct_revenue_5y_avg"] = float(ratio_5y.mean())
    except legitimate_missing_data_exceptions() as exc:
        notes.append(f"interest/receipts: {type(exc).__name__}: {exc}")

    # ---- R-star (HLW vintage panel) ----
    try:
        rstar = _pit_series("HLW_RSTAR", ctx)
        if not rstar.empty:
            m["r_star_pct"] = float(rstar.iloc[-1])
        else:
            notes.append("HLW_RSTAR: empty in PIT view")
    except legitimate_missing_data_exceptions() as exc:
        notes.append(f"HLW_RSTAR: {type(exc).__name__}: {exc}")

    # ---- Real 10Y rate ----
    rr = _real_rate_now(ctx)
    if rr is not None:
        m["real_rate_pct"] = rr
        if "r_star_pct" in m:
            m["real_minus_rstar_pp"] = rr - m["r_star_pct"]
    else:
        notes.append("real_rate: insufficient inputs (need SHILLER_GS10 + SHILLER_CPI)")

    return m, notes


def _evaluate_triggers(metrics: dict[str, float]) -> dict[str, dict[str, bool | None]]:
    def opt(key: str) -> float | None:
        v = metrics.get(key)
        return v if v is not None and np.isfinite(v) else None

    d_rank = opt("debt_gdp_rank_full")
    d_yoy = opt("debt_gdp_yoy_pct")
    d_now = opt("debt_gdp_pct")
    d_5y_avg = opt("debt_gdp_5y_avg")
    rmrs = opt("real_minus_rstar_pp")
    e_now = opt("interest_pct_revenue")
    e_5y = opt("interest_pct_revenue_5y_avg")

    triggers: dict[str, dict[str, bool | None]] = {
        "early": {
            "d_rank_below_30":   (d_rank < 0.30) if d_rank is not None else None,
            "d_yoy_positive":    (d_yoy > 0.0) if d_yoy is not None else None,
            "real_minus_rstar_above_1pp": (rmrs > 1.0) if rmrs is not None else None,
        },
        "mid": {
            "d_rank_30_70":            (0.30 <= d_rank <= 0.70) if d_rank is not None else None,
            "real_minus_rstar_within_1pp": (abs(rmrs) < 1.0) if rmrs is not None else None,
            "interest_5_to_12":        (5.0 <= e_now <= 12.0) if e_now is not None else None,
        },
        "late": {
            "d_rank_above_70":         (d_rank > 0.70) if d_rank is not None else None,
            "real_minus_rstar_below_0": (rmrs < 0.0) if rmrs is not None else None,
            "interest_above_8":        (e_now > 8.0) if e_now is not None else None,
        },
        "deleveraging": {
            "d_yoy_negative":   (d_yoy < 0.0) if d_yoy is not None else None,
            "d_below_5y_avg":   (d_now < d_5y_avg) if d_now is not None and d_5y_avg is not None else None,
            "interest_falling": (e_now < e_5y) if e_now is not None and e_5y is not None else None,
        },
    }
    return triggers


def _classify(triggers: dict[str, dict[str, bool | None]]) -> str:
    scores: list[tuple[int, int, str]] = []
    for phase, ts in triggers.items():
        n_true = sum(1 for v in ts.values() if v is True)
        scores.append((-n_true, _TIEBREAK_PRIORITY[phase], phase))
    scores.sort()
    n_true_winner, _, winner = scores[0]
    if -n_true_winner < 2:
        return "indeterminate"
    return winner


def classify_dalio(ctx: PitDataContext) -> DalioResult:
    """Classify the Dalio long-term debt-cycle phase at ``ctx.as_of`` (PIT-safe)."""
    metrics, notes = _compute_metrics(ctx)
    triggers = _evaluate_triggers(metrics)
    phase = _classify(triggers)
    return DalioResult(
        phase=phase,
        triggers_hit=triggers,
        metrics=metrics,
        method="rule_based_heuristic_v1",
        as_of=ctx.as_of,
        notes=notes,
    )


__all__ = [
    "PHASES",
    "DalioResult",
    "classify_dalio",
]
