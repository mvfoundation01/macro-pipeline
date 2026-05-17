"""L7 D3 — Conviction component producers (Vision §4 BINDING).

Two L7-buildable conviction component slots (out of 9 placeholder at L6-I):
- edge_score (weight 0.20)            L7 producer (this module)
- valuation_support (weight 0.15)     L7 producer (this module)

Six other conviction component slots deferred to L8a per Strategic L7 D3
scope decision (signal sources require options data / positioning data /
NLP / UI integration not at L6/L7):
- asymmetry_score
- trend_confirmation
- liquidity_support
- tail_risk_penalty
- crowding_penalty
- policy_uncertainty_penalty

The L7 ``model_agreement`` producer (in ``confidence_producers.py``) is
reused for the conviction ``model_agreement`` slot (same signal source).

Producer design discipline mirrors confidence_producers.py.
"""
from __future__ import annotations

import math


def produce_edge_score(
    point_estimate_annualized: float,
    sigma_annualized: float,
    *,
    risk_free_rate: float = 0.03,
) -> float:
    """L7 D3 — Vision §4 ``edge_score`` producer.

    Sharpe-like edge score: (point_estimate - risk_free_rate) / sigma,
    transformed to [0, 1] via sigmoid-like saturation.

    Formula::

        excess          = point_estimate_annualized - risk_free_rate
        if sigma_annualized <= 0: return 0.5 (degenerate)
        sharpe_proxy    = excess / sigma_annualized
        # Saturate via sigmoid centered at 0:
        #   sharpe_proxy = 0   → score 0.5
        #   sharpe_proxy = +1  → score ~ 0.73
        #   sharpe_proxy = +2  → score ~ 0.88
        #   sharpe_proxy = -1  → score ~ 0.27
        score           = 1 / (1 + exp(-sharpe_proxy))

    Default risk_free_rate = 0.03 (institutional 3 percent placeholder; L8a
    UI may override with current Fed funds rate).

    Parameters
    ----------
    point_estimate_annualized
        Forecast return point estimate (return fraction; e.g., 0.07 = 7%).
    sigma_annualized
        Forecast sigma (return fraction; e.g., 0.15 = 15%).
    risk_free_rate
        Risk-free benchmark; default 0.03.

    Returns
    -------
    float
        Edge score in [0, 1].

    Raises
    ------
    ValueError
        Any input non-finite.
    """
    for name, val in (
        ("point_estimate_annualized", point_estimate_annualized),
        ("sigma_annualized", sigma_annualized),
        ("risk_free_rate", risk_free_rate),
    ):
        if not math.isfinite(val):
            raise ValueError(f"{name} must be finite; got {val!r}")

    if sigma_annualized <= 0:
        # Degenerate (zero or negative sigma); neutral.
        return 0.5

    excess = point_estimate_annualized - risk_free_rate
    sharpe_proxy = excess / sigma_annualized
    # Sigmoid saturation; clamp extreme inputs to avoid overflow.
    if sharpe_proxy > 50:
        return 1.0
    if sharpe_proxy < -50:
        return 0.0
    return 1.0 / (1.0 + math.exp(-sharpe_proxy))


def produce_valuation_support(
    cape_percentile: float,
    *,
    forecast_direction: str = "long_equity",
) -> float:
    """L7 D3 — Vision §4 ``valuation_support`` producer from CAPE percentile.

    For long-equity forecast direction: low CAPE percentile (cheap) =
    high valuation support; high CAPE percentile (expensive) = low support.

    For short-equity / hedge forecast: opposite mapping.

    Formula (long_equity)::

        support = 1 - cape_percentile
        # CAPE pct 0.10 (10th pct; cheap) → support 0.90
        # CAPE pct 0.50 (median) → support 0.50
        # CAPE pct 0.90 (90th pct; expensive) → support 0.10

    Formula (short_equity)::

        support = cape_percentile

    Parameters
    ----------
    cape_percentile
        CAPE percentile rank in [0, 1] vs full historical sample.
    forecast_direction
        ``"long_equity"`` or ``"short_equity"``.

    Returns
    -------
    float
        Valuation support score in [0, 1].

    Raises
    ------
    ValueError
        cape_percentile non-finite or out of [0, 1]; unknown
        forecast_direction.
    """
    if not math.isfinite(cape_percentile):
        raise ValueError(
            f"cape_percentile must be finite; got {cape_percentile!r}"
        )
    if not (0.0 <= cape_percentile <= 1.0):
        raise ValueError(
            f"cape_percentile must be in [0, 1]; got {cape_percentile}"
        )
    if forecast_direction == "long_equity":
        return 1.0 - cape_percentile
    if forecast_direction == "short_equity":
        return cape_percentile
    raise ValueError(
        f"forecast_direction must be 'long_equity' or 'short_equity'; "
        f"got {forecast_direction!r}"
    )
