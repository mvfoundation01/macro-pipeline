"""L9 D3 + D8 — sector + factor outlook tests."""
from __future__ import annotations

import pytest

from macro_pipeline.factors import (
    FACTOR_IDS,
    FactorRecord,
    compute_factor_outlook,
)
from macro_pipeline.sectors import (
    SECTOR_IDS,
    SectorRecord,
    compute_sector_outlook,
)


# ===========================================================================
# Sectors
# ===========================================================================


def test_sector_ids_count_eleven() -> None:
    """POS: 11 GICS sectors per Vision §19."""
    assert len(SECTOR_IDS) == 11


def test_sector_outlook_overweight_path() -> None:
    """POS-inv: cheap + strong earnings + pro-cyclical → overweight."""
    record = compute_sector_outlook(
        sector_id="technology",
        valuation_percentile=0.20,
        earnings_trend_score=0.90,
        macro_sensitivity_score=0.80,
    )
    assert record.one_year_view == "overweight"
    assert record.conviction > 5.0


def test_sector_outlook_underweight_path() -> None:
    """POS-inv: expensive + weak earnings + counter-cyclical → underweight."""
    record = compute_sector_outlook(
        sector_id="staples",
        valuation_percentile=0.95,
        earnings_trend_score=0.10,
        macro_sensitivity_score=-0.80,
    )
    assert record.one_year_view == "underweight"


def test_sector_record_invalid_sector_raises() -> None:
    """NEG: unknown sector_id raises."""
    with pytest.raises(ValueError, match="sector_id"):
        compute_sector_outlook(
            sector_id="bogus_sector",
            valuation_percentile=0.5,
            earnings_trend_score=0.5,
            macro_sensitivity_score=0.0,
        )


def test_sector_record_out_of_range_valuation_raises() -> None:
    """NEG: valuation_percentile out of [0, 1] raises."""
    with pytest.raises(ValueError, match="valuation_percentile"):
        compute_sector_outlook(
            sector_id="technology",
            valuation_percentile=1.5,
            earnings_trend_score=0.5,
            macro_sensitivity_score=0.0,
        )


def test_sector_record_out_of_range_macro_sensitivity_raises() -> None:
    """NEG: macro_sensitivity_score out of [-1, 1] raises."""
    with pytest.raises(ValueError, match="macro_sensitivity_score"):
        compute_sector_outlook(
            sector_id="technology",
            valuation_percentile=0.5,
            earnings_trend_score=0.5,
            macro_sensitivity_score=1.5,
        )


def test_sector_record_3y_more_valuation_weight() -> None:
    """POS-inv: 3Y view weights valuation more heavily than 1Y."""
    cheap = compute_sector_outlook(
        sector_id="financials",
        valuation_percentile=0.10,  # very cheap
        earnings_trend_score=0.40,  # weak earnings
        macro_sensitivity_score=0.20,
    )
    # 1Y composite: (1-0.10)*0.4 + 0.40*0.4 + 0.60*0.2 = 0.36 + 0.16 + 0.12 = 0.64 → neutral
    # 3Y composite: (1-0.10)*0.6 + 0.40*0.3 + 0.60*0.1 = 0.54 + 0.12 + 0.06 = 0.72 → overweight
    assert cheap.one_year_view == "neutral"
    assert cheap.three_year_view == "overweight"


# ===========================================================================
# Factors
# ===========================================================================


def test_factor_ids_count_thirteen() -> None:
    """POS: 13 risk factors per Vision §19."""
    assert len(FACTOR_IDS) == 13


def test_factor_outlook_overweight_path() -> None:
    """POS-inv: positive expected return + regime-aligned → overweight."""
    record = compute_factor_outlook(
        factor_id="momentum",
        expected_return_bps=200.0,
        sigma_bps=300.0,
        regime_alignment=0.80,
    )
    assert record.one_year_tilt == "overweight"
    assert record.conviction > 3.0


def test_factor_outlook_underweight_path() -> None:
    """POS-inv: negative expected return → underweight."""
    record = compute_factor_outlook(
        factor_id="leverage",
        expected_return_bps=-200.0,
        sigma_bps=400.0,
        regime_alignment=-0.50,
    )
    assert record.one_year_tilt == "underweight"


def test_factor_outlook_neutral_path() -> None:
    """POS-inv: small expected return → neutral."""
    record = compute_factor_outlook(
        factor_id="quality",
        expected_return_bps=50.0,
        sigma_bps=200.0,
        regime_alignment=0.0,
    )
    assert record.one_year_tilt == "neutral"


def test_factor_record_invalid_factor_raises() -> None:
    """NEG: unknown factor_id raises."""
    with pytest.raises(ValueError, match="factor_id"):
        compute_factor_outlook(
            factor_id="bogus_factor",
            expected_return_bps=100.0,
            sigma_bps=300.0,
            regime_alignment=0.5,
        )


def test_factor_record_negative_sigma_raises() -> None:
    """NEG: negative sigma raises."""
    with pytest.raises(ValueError, match="sigma_bps"):
        compute_factor_outlook(
            factor_id="momentum",
            expected_return_bps=100.0,
            sigma_bps=-100.0,
            regime_alignment=0.0,
        )


def test_factor_record_invalid_regime_alignment_raises() -> None:
    """NEG: regime_alignment out of [-1, 1] raises."""
    with pytest.raises(ValueError, match="regime_alignment"):
        compute_factor_outlook(
            factor_id="value",
            expected_return_bps=100.0,
            sigma_bps=300.0,
            regime_alignment=2.0,
        )
