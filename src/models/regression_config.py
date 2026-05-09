"""Convention constants for the R-squared regression layer (Build guide
Section 11, Layer 5b).

This file is loaded by Layer 5b code when computing forward-return
regressions for valuation/macro indicators. The convention is fixed
here so there is no ambiguity at the call site.

Convention
----------
R-squared regression uses REAL total return, NOT nominal.

Source of truth: ``SHILLER_TR_PRICE`` (Phase 4B, real CPI-adjusted total
return cumulative index, monthly, 1871-present). This is the same series
used by currentmarketvaluation.com for their valuation regression
charts. Real-return convention is academic standard (Shiller, Bogle,
Damodaran) and prevents inflation regimes from polluting cross-cycle
comparisons.

Yahoo's ``SP500TR`` (Phase 3) is NOMINAL total return only. It runs
1988-present, ~37 years of history. Use it as a daily/weekly
real-time benchmark and as a cross-validation source for the modern
overlap window - NEVER as the primary regression target.

For pre-1988 backtest windows, only the Shiller series is available;
this is fine because the regression target was never going to be
year-by-year identical with the modern Yahoo series anyway (the
inflation deflator differs across the two real-return conventions).
"""

PRIMARY_REGRESSION_TARGET: str = "SHILLER_TR_PRICE"
TARGET_TYPE: str = "real_total_return"

# Forward horizons (months) for the canonical R-squared table.
# Build guide Section 11.3: 1Y, 3Y, 5Y, 10Y annualized real total return.
FORWARD_HORIZONS_MONTHS: tuple[int, ...] = (12, 36, 60, 120)

# Cross-validation companion (modern only).
CROSS_VALIDATION_TARGET: str = "SP500TR"
CROSS_VALIDATION_TARGET_TYPE: str = "nominal_total_return"
CROSS_VALIDATION_OVERLAP_START: str = "1988-01-04"  # ^SP500TR launch

# Valid use_for tags that imply this series is a regression target.
REGRESSION_TARGET_USE_FOR_TAGS: frozenset[str] = frozenset({
    "forward_return_calc",
    "r_squared_regression",
})


def is_primary_regression_target(meta_or_dict) -> bool:
    """True if the given metadata indicates the *primary* regression target."""
    indicator_id = (
        getattr(meta_or_dict, "indicator_id", None)
        or (meta_or_dict.get("indicator_id") if isinstance(meta_or_dict, dict) else None)
    )
    return indicator_id == PRIMARY_REGRESSION_TARGET
