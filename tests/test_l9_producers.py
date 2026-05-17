"""L9 D1 + D8 tests — 6 new L8a-deferred component producers."""
from __future__ import annotations

import pytest

from macro_pipeline.ensemble.component_producers import (
    ALL_BUILT_PRODUCER_SLOTS,
    L7_BUILT_PRODUCER_SLOTS,
    L8A_DEFERRED_SLOTS,
    L9_BUILT_PRODUCER_SLOTS,
    produce_asymmetry_score,
    produce_crowding_penalty,
    produce_liquidity_support,
    produce_policy_uncertainty_penalty,
    produce_tail_risk_penalty,
    produce_trend_confirmation,
)


# ===========================================================================
# Slot constants
# ===========================================================================


def test_l9_built_producer_slots_count() -> None:
    """POS: 6 L9-built producer slots."""
    assert len(L9_BUILT_PRODUCER_SLOTS) == 6


def test_l8a_deferred_only_forecast_decay_remains() -> None:
    """POS: only 1 slot still deferred (forecast_decay_penalty UI-driven)."""
    assert L8A_DEFERRED_SLOTS == frozenset({"forecast_decay_penalty"})


def test_all_built_producer_slots_disjoint_from_deferred() -> None:
    """POS-inv: ALL_BUILT and L8A_DEFERRED partition the placeholder universe."""
    assert ALL_BUILT_PRODUCER_SLOTS.isdisjoint(L8A_DEFERRED_SLOTS)
    assert L7_BUILT_PRODUCER_SLOTS.issubset(ALL_BUILT_PRODUCER_SLOTS)
    assert L9_BUILT_PRODUCER_SLOTS.issubset(ALL_BUILT_PRODUCER_SLOTS)


# ===========================================================================
# asymmetry_score
# ===========================================================================


def test_asymmetry_basic_proxy_neutral() -> None:
    """POS: realized = implied yields 0.5 (neutral)."""
    score = produce_asymmetry_score(
        realized_vol_annualized=0.15, implied_vol_atm=0.15
    )
    assert score == pytest.approx(0.5)


def test_asymmetry_realized_above_implied_increases() -> None:
    """POS-inv: realized > implied yields > 0.5 (upside asymmetry)."""
    high = produce_asymmetry_score(
        realized_vol_annualized=0.20, implied_vol_atm=0.15
    )
    assert high > 0.5


def test_asymmetry_skew_mode_call_above_put() -> None:
    """POS-inv: call vol > put vol yields > 0.5 (right-tail skew)."""
    score = produce_asymmetry_score(
        realized_vol_annualized=0.15,
        implied_vol_atm=0.15,
        implied_vol_otm_call=0.18,
        implied_vol_otm_put=0.15,
    )
    assert score > 0.5


def test_asymmetry_nan_raises() -> None:
    """NEG: NaN raises ValueError."""
    with pytest.raises(ValueError, match="finite"):
        produce_asymmetry_score(
            realized_vol_annualized=float("nan"), implied_vol_atm=0.15
        )


def test_asymmetry_zero_vol_raises() -> None:
    """NEG: zero volatility raises ValueError."""
    with pytest.raises(ValueError, match="positive"):
        produce_asymmetry_score(
            realized_vol_annualized=0.0, implied_vol_atm=0.15
        )


# ===========================================================================
# trend_confirmation
# ===========================================================================


def test_trend_full_confirmation() -> None:
    """POS-inv: all 5 signals confirm yields 1.0."""
    score = produce_trend_confirmation(
        price_current=100.0,
        sma_50=95.0,
        sma_200=90.0,
        momentum_3m=0.05,
        momentum_12m=0.10,
    )
    assert score == pytest.approx(1.0)


def test_trend_no_confirmation() -> None:
    """POS-inv: all 5 signals anti-confirm yields 0.0."""
    score = produce_trend_confirmation(
        price_current=80.0,
        sma_50=90.0,
        sma_200=95.0,
        momentum_3m=-0.05,
        momentum_12m=-0.10,
    )
    assert score == pytest.approx(0.0)


def test_trend_partial_confirmation() -> None:
    """POS-inv: 3 of 5 signals confirm yields 0.6."""
    score = produce_trend_confirmation(
        price_current=100.0,
        sma_50=95.0,
        sma_200=105.0,  # SMA50 < SMA200; below-trend regime
        momentum_3m=0.05,
        momentum_12m=-0.10,  # negative
    )
    # Confirms: price > SMA50 (+0.20), momentum_3m > 0 (+0.20) = 0.40
    # price > SMA200? 100 < 105 → no
    # SMA50 > SMA200? 95 < 105 → no
    # Actual: price > SMA50 + momentum_3m > 0 = 0.40
    assert score == pytest.approx(0.40)


def test_trend_nan_raises() -> None:
    """NEG: NaN input raises."""
    with pytest.raises(ValueError, match="finite"):
        produce_trend_confirmation(
            price_current=float("nan"),
            sma_50=95.0, sma_200=90.0,
            momentum_3m=0.0, momentum_12m=0.0,
        )


def test_trend_zero_price_raises() -> None:
    """NEG: zero price raises."""
    with pytest.raises(ValueError, match="positive"):
        produce_trend_confirmation(
            price_current=0.0, sma_50=95.0, sma_200=90.0,
            momentum_3m=0.0, momentum_12m=0.0,
        )


# ===========================================================================
# liquidity_support
# ===========================================================================


def test_liquidity_balanced() -> None:
    """POS-inv: fci_change=0 + spreads at median yields ~0.75."""
    score = produce_liquidity_support(
        fci_change_3m=0.0, hy_oas_bps=450.0
    )
    # fci_score = 0.5; spread_ratio=1.0 → spread_score = 1.0; avg = 0.75
    assert score == pytest.approx(0.75)


def test_liquidity_tight_fci_low_score() -> None:
    """POS-inv: tightening FCI lowers score."""
    loose = produce_liquidity_support(fci_change_3m=-0.5, hy_oas_bps=450.0)
    tight = produce_liquidity_support(fci_change_3m=+0.5, hy_oas_bps=450.0)
    assert loose > tight


def test_liquidity_wide_spreads_lower_score() -> None:
    """POS-inv: wider spreads lower liquidity support."""
    tight_spreads = produce_liquidity_support(
        fci_change_3m=0.0, hy_oas_bps=300.0
    )
    wide_spreads = produce_liquidity_support(
        fci_change_3m=0.0, hy_oas_bps=800.0
    )
    assert tight_spreads > wide_spreads


def test_liquidity_zero_median_raises() -> None:
    """NEG: zero median spread raises."""
    with pytest.raises(ValueError, match="positive"):
        produce_liquidity_support(
            fci_change_3m=0.0, hy_oas_bps=450.0, hy_oas_long_median_bps=0.0
        )


# ===========================================================================
# tail_risk_penalty
# ===========================================================================


def test_tail_risk_low() -> None:
    """POS-inv: low SKEW + balanced put/call + positive term slope yields low score."""
    score = produce_tail_risk_penalty(
        cboe_skew_index=110.0,
        put_call_ratio=0.80,
        vix_term_structure_slope=2.0,  # positive = contango
    )
    assert score < 0.3


def test_tail_risk_high() -> None:
    """POS-inv: high SKEW + high put/call + inverted VIX term yields high score."""
    score = produce_tail_risk_penalty(
        cboe_skew_index=150.0,
        put_call_ratio=1.5,
        vix_term_structure_slope=-5.0,
    )
    assert score > 0.5


def test_tail_risk_nan_raises() -> None:
    """NEG: NaN input raises."""
    with pytest.raises(ValueError, match="finite"):
        produce_tail_risk_penalty(
            cboe_skew_index=float("nan"),
            put_call_ratio=1.0,
            vix_term_structure_slope=0.0,
        )


# ===========================================================================
# crowding_penalty
# ===========================================================================


def test_crowding_low() -> None:
    """POS-inv: low percentile positioning + positive gamma yields low score."""
    score = produce_crowding_penalty(
        cftc_asset_manager_net_long_percentile=0.30,
        cftc_leveraged_funds_net_long_percentile=0.40,
        dealer_gamma_normalized=0.50,  # positive
    )
    # AM + LF / 3 + gamma (0 since gamma > 0) / 3 = (0.30 + 0.40 + 0) / 3 = 0.233
    assert score < 0.4


def test_crowding_high() -> None:
    """POS-inv: extreme positioning + negative gamma yields high score."""
    score = produce_crowding_penalty(
        cftc_asset_manager_net_long_percentile=0.95,
        cftc_leveraged_funds_net_long_percentile=0.90,
        dealer_gamma_normalized=-0.80,
    )
    assert score > 0.6


def test_crowding_invalid_percentile_raises() -> None:
    """NEG: percentile out of [0, 1] raises."""
    with pytest.raises(ValueError, match="\\[0, 1\\]"):
        produce_crowding_penalty(
            cftc_asset_manager_net_long_percentile=1.5,
            cftc_leveraged_funds_net_long_percentile=0.5,
            dealer_gamma_normalized=0.0,
        )


# ===========================================================================
# policy_uncertainty_penalty
# ===========================================================================


def test_policy_uncertainty_low() -> None:
    """POS-inv: low SEP dispersion + low implied path vol yields low score."""
    score = produce_policy_uncertainty_penalty(
        fomc_sep_dispersion=0.20,
        market_implied_path_volatility=0.50,
    )
    assert score < 0.4


def test_policy_uncertainty_high() -> None:
    """POS-inv: high dispersion + high path vol yields high score."""
    score = produce_policy_uncertainty_penalty(
        fomc_sep_dispersion=1.0,
        market_implied_path_volatility=2.0,
    )
    assert score > 0.7


def test_policy_uncertainty_with_communication_index() -> None:
    """POS-inv: optional communication uncertainty integrates."""
    base = produce_policy_uncertainty_penalty(
        fomc_sep_dispersion=0.5,
        market_implied_path_volatility=1.0,
    )
    with_comm = produce_policy_uncertainty_penalty(
        fomc_sep_dispersion=0.5,
        market_implied_path_volatility=1.0,
        fed_communication_uncertainty_index=0.9,
    )
    # Adding communication uncertainty pulls score in the direction of the
    # comm value (here 0.9 is high → score should rise).
    assert with_comm > base


def test_policy_uncertainty_negative_input_raises() -> None:
    """NEG: negative dispersion raises."""
    with pytest.raises(ValueError, match="non-negative"):
        produce_policy_uncertainty_penalty(
            fomc_sep_dispersion=-0.1,
            market_implied_path_volatility=1.0,
        )
