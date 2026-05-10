"""Kindleberger 5-phase classifier (Layer 3A, rule-based heuristic v1).

Spec: ``LAYER_3_BUILD_SPEC.md`` §4.3.2.

Phases (2-of-3 trigger logic; phase fires when at least 2 of its rules
hit at ``as_of``):

| Phase        | Available triggers used                                                  |
|--------------|--------------------------------------------------------------------------|
| displacement | (NOT IMPLEMENTED — requires regime-catalyst metadata not in cache)       |
| boom         | margin debt YoY > 0;   CAPE in 30-70 pctile;   VIX 12M z < 0             |
| euphoria     | CAPE > 85th pctile;    margin debt 24M z > +1.0;   margin debt YoY > 15%   |
| distress     | HY OAS 30D Δ > +50bps; VIX 12M z > +1.5;       equity 5%+ off 52W high   |
| revulsion    | equity drawdown > 20%; HY OAS > LT median+200bps; VIX z > +1.5            |

Metrics are PIT-safe via ``PitDataContext``. Series whose first-obs is
later than the trigger requirement (e.g. BAMLH0A0HYM2 starts 1996-12)
return ``None`` for that trigger; the phase only fires if enough OTHER
triggers hit. The classifier reports `triggers_available` so callers can
audit data coverage.

Layer 5 may calibrate thresholds. For Layer 3 we record
``method="rule_based_heuristic_v1"`` in the output metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from macro_pipeline.access import PitDataContext, load_series
from macro_pipeline.exceptions import legitimate_missing_data_exceptions

PHASES = ("displacement", "boom", "euphoria", "distress", "revulsion", "indeterminate")

# Tiebreak preference (more extreme wins on tie). Lower index = preferred.
_TIEBREAK_PRIORITY = {
    "revulsion":     0,
    "distress":      1,
    "euphoria":      2,
    "boom":          3,
    "displacement":  4,
    "indeterminate": 5,
}


@dataclass
class KindlebergerResult:
    phase: str
    triggers_hit: dict[str, dict[str, bool | None]]    # {phase: {trigger: hit_or_None}}
    metrics: dict[str, float]                           # raw computed metrics
    method: str = "rule_based_heuristic_v1"
    as_of: pd.Timestamp | None = None
    notes: list[str] = field(default_factory=list)


def _pit_series(indicator_id: str, ctx: PitDataContext) -> pd.Series:
    bundle = load_series(indicator_id, as_of=ctx.as_of)
    return bundle.data.dropna()


def _percentile_rank(series: pd.Series, value: float) -> float:
    """Rank ``value`` against full ``series`` history; return percentile in [0, 1]."""
    s = series.dropna()
    if s.empty or not np.isfinite(value):
        return float("nan")
    return float((s <= value).mean())


def _compute_metrics(ctx: PitDataContext) -> tuple[dict[str, float], list[str]]:
    """Compute all metrics needed for Kindleberger triggers.

    Returns ``(metrics, notes)`` where ``notes`` documents missing data.
    """
    notes: list[str] = []
    m: dict[str, float] = {}

    # ---- Valuation: SHILLER_CAPE rank vs full history ----
    try:
        cape = _pit_series("SHILLER_CAPE", ctx)
        if cape.empty:
            notes.append("CAPE: empty in PIT view")
        else:
            cape_now = float(cape.iloc[-1])
            m["cape_value"] = cape_now
            m["cape_rank_full"] = _percentile_rank(cape, cape_now)
    except legitimate_missing_data_exceptions() as exc:
        notes.append(f"CAPE: {type(exc).__name__}: {exc}")

    # ---- Margin debt: FINRA z-score (24M rolling) + YoY growth ----
    try:
        margin = _pit_series("FINRA_MARGIN_DEBT", ctx)
        if not margin.empty and len(margin) >= 24:
            window = margin.tail(24)
            mu, sigma = float(window.mean()), float(window.std(ddof=1))
            margin_now = float(margin.iloc[-1])
            if sigma > 0:
                m["margin_z_24m"] = (margin_now - mu) / sigma
            margin_y_ago = margin[margin.index <= margin.index[-1] - pd.DateOffset(years=1)]
            if not margin_y_ago.empty:
                m["margin_yoy_pct"] = (margin_now / float(margin_y_ago.iloc[-1]) - 1.0) * 100.0
        else:
            notes.append("FINRA margin debt: insufficient history (needs 24+ months)")
    except legitimate_missing_data_exceptions() as exc:
        notes.append(f"FINRA: {type(exc).__name__}: {exc}")

    # ---- HY OAS: 30-day change + LT median + current ----
    try:
        hy = _pit_series("BAMLH0A0HYM2", ctx)
        if not hy.empty:
            m["hy_oas_pct"] = float(hy.iloc[-1])
            m["hy_oas_lt_median"] = float(hy.median())
            cutoff = hy.index[-1] - pd.Timedelta(days=30)
            past = hy[hy.index <= cutoff]
            if not past.empty:
                # bps change over 30 days; series is in % so multiply by 100
                m["hy_oas_30d_delta_bps"] = (float(hy.iloc[-1]) - float(past.iloc[-1])) * 100.0
        else:
            notes.append("HY OAS: empty in PIT view (BAMLH0A0HYM2 starts 1996-12)")
    except legitimate_missing_data_exceptions() as exc:
        notes.append(f"HY OAS: {type(exc).__name__}: {exc}")

    # ---- VIX: 12M rolling z-score ----
    try:
        vix = _pit_series("VIX_YAHOO", ctx)
        # ~252 business days = 12M
        window = vix.tail(252)
        if len(window) >= 60:
            mu, sigma = float(window.mean()), float(window.std(ddof=1))
            vix_now = float(vix.iloc[-1])
            m["vix_value"] = vix_now
            if sigma > 0:
                m["vix_z_12m"] = (vix_now - mu) / sigma
        else:
            notes.append("VIX: insufficient history (needs 60+ days)")
    except legitimate_missing_data_exceptions() as exc:
        notes.append(f"VIX: {type(exc).__name__}: {exc}")

    # ---- Equity drawdown vs 52W high (use SHILLER_REAL_PRICE for long history) ----
    try:
        spx = _pit_series("SHILLER_REAL_PRICE", ctx)
        if not spx.empty:
            # ~252 days; SHILLER is monthly-stamped daily-aligned, so use last 252 obs
            window = spx.tail(252)
            if not window.empty:
                peak = float(window.max())
                cur = float(spx.iloc[-1])
                m["equity_drawdown_pct"] = (cur / peak - 1.0) * 100.0  # negative when below peak
        else:
            notes.append("SHILLER_REAL_PRICE: empty in PIT view")
    except legitimate_missing_data_exceptions() as exc:
        notes.append(f"SHILLER_REAL_PRICE: {type(exc).__name__}: {exc}")

    # ---- AAII bull % rank (sentiment) ----
    try:
        aaii = _pit_series("AAII_BULL_8WMA", ctx)
        if not aaii.empty:
            m["aaii_bull_now"] = float(aaii.iloc[-1])
            m["aaii_bull_rank_full"] = _percentile_rank(aaii, float(aaii.iloc[-1]))
        else:
            notes.append("AAII_BULL_8WMA: empty in PIT view")
    except legitimate_missing_data_exceptions() as exc:
        notes.append(f"AAII: {type(exc).__name__}: {exc}")

    return m, notes


def _evaluate_triggers(metrics: dict[str, float]) -> dict[str, dict[str, bool | None]]:
    """Return ``{phase: {trigger_name: True/False/None}}``.

    ``None`` indicates the trigger could not be evaluated due to missing
    data; phases with mostly-None triggers cannot fire.
    """
    def opt(key: str) -> float | None:
        v = metrics.get(key)
        return v if v is not None and np.isfinite(v) else None

    cape_rank = opt("cape_rank_full")
    margin_z = opt("margin_z_24m")
    margin_yoy = opt("margin_yoy_pct")
    hy_oas = opt("hy_oas_pct")
    hy_med = opt("hy_oas_lt_median")
    hy_30d = opt("hy_oas_30d_delta_bps")
    vix_z = opt("vix_z_12m")
    drawdown = opt("equity_drawdown_pct")
    # NOTE: aaii_bull_rank is computed in metrics for downstream display
    # (e.g. RegimeContext audit) but is not currently used as a trigger;
    # the v1 heuristic relies on margin/CAPE/HY/VIX/equity which are more
    # mechanically observable. Layer 5 may revisit and add an AAII trigger.

    def t(cond: bool | None) -> bool | None:
        return cond

    triggers: dict[str, dict[str, bool | None]] = {
        "boom": {
            "margin_yoy_positive": t(margin_yoy > 0.0) if margin_yoy is not None else None,
            "cape_rank_30_70":     t(0.30 <= cape_rank <= 0.70) if cape_rank is not None else None,
            "vix_z_below_zero":    t(vix_z < 0.0) if vix_z is not None else None,
        },
        "euphoria": {
            "cape_rank_above_85":   t(cape_rank > 0.85) if cape_rank is not None else None,
            "margin_z_above_1p0":   t(margin_z > 1.0) if margin_z is not None else None,
            "margin_yoy_above_15":  t(margin_yoy > 15.0) if margin_yoy is not None else None,
        },
        "distress": {
            "hy_oas_30d_widen_50bps": t(hy_30d > 50.0) if hy_30d is not None else None,
            "vix_z_above_1p5":        t(vix_z > 1.5) if vix_z is not None else None,
            "equity_off_52w_5pct":    t(drawdown < -5.0) if drawdown is not None else None,
        },
        "revulsion": {
            "equity_drawdown_gt_20":   t(drawdown < -20.0) if drawdown is not None else None,
            "hy_oas_gt_lt_median_p2":  (
                t(hy_oas - hy_med > 2.0) if hy_oas is not None and hy_med is not None else None
            ),
            "vix_z_above_1p5":         t(vix_z > 1.5) if vix_z is not None else None,
        },
    }
    return triggers


def _classify(triggers: dict[str, dict[str, bool | None]]) -> str:
    """Pick the phase with the most True triggers (need ≥ 2 to fire).

    Tiebreak: prefer the more extreme phase per ``_TIEBREAK_PRIORITY``.
    """
    scores: list[tuple[int, int, str]] = []
    for phase, ts in triggers.items():
        n_true = sum(1 for v in ts.values() if v is True)
        scores.append((-n_true, _TIEBREAK_PRIORITY[phase], phase))
    scores.sort()
    n_true_winner, _, winner = scores[0]
    if -n_true_winner < 2:
        return "indeterminate"
    return winner


def classify_kindleberger(ctx: PitDataContext) -> KindlebergerResult:
    """Classify the Kindleberger phase at ``ctx.as_of`` (PIT-safe).

    Returns a ``KindlebergerResult`` with the phase, the triggers
    evaluated, the raw metrics, and any data-availability notes.
    """
    metrics, notes = _compute_metrics(ctx)
    triggers = _evaluate_triggers(metrics)
    phase = _classify(triggers)
    return KindlebergerResult(
        phase=phase,
        triggers_hit=triggers,
        metrics=metrics,
        method="rule_based_heuristic_v1",
        as_of=ctx.as_of,
        notes=notes,
    )


__all__ = [
    "PHASES",
    "KindlebergerResult",
    "classify_kindleberger",
]
