"""L9 D1 — Six previously-L8a-deferred component producers.

Per Strategic L9 single comprehensive pre-flight 2026-05-16
(ACCELERATION PROTOCOL v2.0). Closes 6 of the 6 placeholder slots
in ``ConvictionComponents`` that were deferred from L7 D3:

- asymmetry_score              vol-implied right/left tail asymmetry
- trend_confirmation           50/200 DMA + momentum
- liquidity_support            FCI + credit spreads
- tail_risk_penalty            SKEW + put/call + VIX term
- crowding_penalty             CFTC + dealer gamma
- policy_uncertainty_penalty   Fed reaction signals

Producer design discipline (matches L7 producers):
- Pure functions; deterministic given inputs
- Finite-checked inputs/outputs (AP-AUTH per L6-I D1)
- Documented signal source per producer
- Each returns float in [0, 1]

Component slot status after L9 (11 of 12 producer-backed):
- L9_BUILT_PRODUCER_SLOTS (6 NEW): asymmetry, trend, liquidity, tail_risk,
  crowding, policy_uncertainty
- L9_DEFERRED_SLOTS (1 only): forecast_decay_penalty (L8a UI-driven)
"""
from __future__ import annotations

import math
from typing import Optional


def produce_asymmetry_score(
    realized_vol_annualized: float,
    implied_vol_atm: float,
    implied_vol_otm_call: Optional[float] = None,
    implied_vol_otm_put: Optional[float] = None,
) -> float:
    """L9 D1 — Vision §X asymmetry_score: vol-implied right/left tail premium.

    Two-mode operation:
    - If both OTM call + put implied vols provided: compute proper risk reversal
      (call_vol minus put_vol); positive risk reversal = upside skew = high asymmetry
    - Else: crude proxy from realized vs ATM implied (realized > implied
      suggests market underpriced upside)

    Returns float in [0, 1]. Higher = more right-tail asymmetry.
    """
    if not math.isfinite(realized_vol_annualized):
        raise ValueError("realized_vol_annualized must be finite")
    if not math.isfinite(implied_vol_atm):
        raise ValueError("implied_vol_atm must be finite")
    if realized_vol_annualized <= 0 or implied_vol_atm <= 0:
        raise ValueError("volatilities must be positive")

    if implied_vol_otm_call is not None and implied_vol_otm_put is not None:
        if not math.isfinite(implied_vol_otm_call):
            raise ValueError("implied_vol_otm_call must be finite")
        if not math.isfinite(implied_vol_otm_put):
            raise ValueError("implied_vol_otm_put must be finite")
        skew = implied_vol_otm_call - implied_vol_otm_put
        # Map skew range [-0.10, +0.10] to [0, 1]; center 0 -> 0.5.
        return max(0.0, min(1.0, 0.5 + 5.0 * skew))

    # Fallback proxy.
    ratio = realized_vol_annualized / implied_vol_atm
    return max(0.0, min(1.0, 0.5 + 0.5 * (ratio - 1.0)))


def produce_trend_confirmation(
    price_current: float,
    sma_50: float,
    sma_200: float,
    momentum_3m: float,
    momentum_12m: float,
) -> float:
    """L9 D1 — Vision §X Layer 5 Technical/Trend: 5-signal trend score.

    Each of the 5 signals contributes 0.20 if confirming trend:
    - price > SMA50
    - price > SMA200
    - SMA50 > SMA200 (golden cross regime)
    - momentum_3m > 0
    - momentum_12m > 0

    Returns float in [0, 1]. 0 = no trend; 1 = all 5 signals confirm.
    """
    for fname, val in (
        ("price_current", price_current),
        ("sma_50", sma_50),
        ("sma_200", sma_200),
        ("momentum_3m", momentum_3m),
        ("momentum_12m", momentum_12m),
    ):
        if not math.isfinite(val):
            raise ValueError(f"{fname} must be finite")
    if price_current <= 0 or sma_50 <= 0 or sma_200 <= 0:
        raise ValueError("prices must be positive")

    score = 0.0
    if price_current > sma_50:
        score += 0.20
    if price_current > sma_200:
        score += 0.20
    if sma_50 > sma_200:
        score += 0.20
    if momentum_3m > 0:
        score += 0.20
    if momentum_12m > 0:
        score += 0.20
    return score


def produce_liquidity_support(
    fci_change_3m: float,
    hy_oas_bps: float,
    hy_oas_long_median_bps: float = 450.0,
) -> float:
    """L9 D1 — Vision §X Layer 3 Liquidity/Credit composite.

    Combines:
    - FCI change (negative = easing = positive contribution)
    - HY OAS relative to long-run median (tighter = better liquidity)

    Returns float in [0, 1]. Higher = more liquidity support.
    """
    if not math.isfinite(fci_change_3m):
        raise ValueError("fci_change_3m must be finite")
    if not math.isfinite(hy_oas_bps):
        raise ValueError("hy_oas_bps must be finite")
    if not math.isfinite(hy_oas_long_median_bps):
        raise ValueError("hy_oas_long_median_bps must be finite")
    if hy_oas_long_median_bps <= 0:
        raise ValueError("hy_oas_long_median_bps must be positive")

    fci_score = max(0.0, min(1.0, 0.5 - fci_change_3m))
    spread_ratio = hy_oas_bps / hy_oas_long_median_bps
    spread_score = max(0.0, min(1.0, 1.0 - (spread_ratio - 1.0)))
    return (fci_score + spread_score) / 2.0


def produce_tail_risk_penalty(
    cboe_skew_index: float,
    put_call_ratio: float,
    vix_term_structure_slope: float,
) -> float:
    """L9 D1 — Vision §X Layer 4 Sentiment/Positioning tail-risk score.

    Combines:
    - CBOE SKEW index (long-run mean ~118; >145 = elevated)
    - Put/call ratio (>1.2 = elevated put hedging)
    - VIX term structure inversion (negative slope = tail risk pricing)

    Returns float in [0, 1]. Higher = more tail risk (penalty value).
    """
    for fname, val in (
        ("cboe_skew_index", cboe_skew_index),
        ("put_call_ratio", put_call_ratio),
        ("vix_term_structure_slope", vix_term_structure_slope),
    ):
        if not math.isfinite(val):
            raise ValueError(f"{fname} must be finite")

    skew_score = max(0.0, min(1.0, (cboe_skew_index - 100.0) / 50.0))
    pc_score = max(0.0, min(1.0, (put_call_ratio - 0.7) / 0.7))
    if vix_term_structure_slope < 0:
        term_score = max(
            0.0, min(1.0, -vix_term_structure_slope / 5.0)
        )
    else:
        term_score = 0.0
    return (skew_score + pc_score + term_score) / 3.0


def produce_crowding_penalty(
    cftc_asset_manager_net_long_percentile: float,
    cftc_leveraged_funds_net_long_percentile: float,
    dealer_gamma_normalized: float,
) -> float:
    """L9 D1 — Vision §X Layer 4 positioning crowding score.

    Combines:
    - CFTC asset manager net long (already [0, 1] percentile)
    - CFTC leveraged funds net long (already [0, 1] percentile)
    - Dealer gamma normalized (negative = pro-cyclical crowding intensifier)

    Returns float in [0, 1]. Higher = more crowded (penalty value).
    """
    for fname, val in (
        ("cftc_asset_manager_net_long_percentile",
         cftc_asset_manager_net_long_percentile),
        ("cftc_leveraged_funds_net_long_percentile",
         cftc_leveraged_funds_net_long_percentile),
        ("dealer_gamma_normalized", dealer_gamma_normalized),
    ):
        if not math.isfinite(val):
            raise ValueError(f"{fname} must be finite")
    if not (0.0 <= cftc_asset_manager_net_long_percentile <= 1.0):
        raise ValueError(
            f"cftc_asset_manager_net_long_percentile must be in [0, 1]"
        )
    if not (0.0 <= cftc_leveraged_funds_net_long_percentile <= 1.0):
        raise ValueError(
            f"cftc_leveraged_funds_net_long_percentile must be in [0, 1]"
        )

    if dealer_gamma_normalized < 0:
        gamma_score = max(0.0, min(1.0, -dealer_gamma_normalized))
    else:
        gamma_score = 0.0
    return (
        cftc_asset_manager_net_long_percentile
        + cftc_leveraged_funds_net_long_percentile
        + gamma_score
    ) / 3.0


def produce_policy_uncertainty_penalty(
    fomc_sep_dispersion: float,
    market_implied_path_volatility: float,
    fed_communication_uncertainty_index: Optional[float] = None,
) -> float:
    """L9 D1 — Vision §9 Lucas-critique support: policy uncertainty score.

    Combines:
    - FOMC SEP dispersion (Summary of Economic Projections rate-path variance)
    - Market-implied rate-path volatility (OIS / SOFR options)
    - Optional: Fed communication uncertainty (NLP-derived)

    Returns float in [0, 1]. Higher = more policy uncertainty (penalty value).
    """
    if not math.isfinite(fomc_sep_dispersion):
        raise ValueError("fomc_sep_dispersion must be finite")
    if not math.isfinite(market_implied_path_volatility):
        raise ValueError("market_implied_path_volatility must be finite")
    if fomc_sep_dispersion < 0:
        raise ValueError("fomc_sep_dispersion must be non-negative")
    if market_implied_path_volatility < 0:
        raise ValueError("market_implied_path_volatility must be non-negative")

    sep_score = max(0.0, min(1.0, fomc_sep_dispersion / 1.0))
    path_score = max(0.0, min(1.0, market_implied_path_volatility / 2.0))

    if fed_communication_uncertainty_index is not None:
        if not math.isfinite(fed_communication_uncertainty_index):
            raise ValueError(
                "fed_communication_uncertainty_index must be finite"
            )
        comm_score = max(0.0, min(1.0, fed_communication_uncertainty_index))
        return (sep_score + path_score + comm_score) / 3.0
    return (sep_score + path_score) / 2.0
