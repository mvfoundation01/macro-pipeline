"""Layer 6-C — tests for ``macro_pipeline.ensemble.triple_sigma``.

Spec ref: Strategic L6-C inline spec (Batch 1, post-L6-B) §B.4.
Triple sigma Reporting per Vision §5 BINDING for return forecasts;
cumulative-sigma helper via square-root-of-time scaling with regime-
failure caveats documented in the module docstring.

Test inventory (NEG ratio >= 50% per AP-AUTH-53 discipline):
   1. POS         test_triple_sigma_basic_construction
   2. NEG         test_triple_sigma_negative_return_sigma
   3. NEG         test_triple_sigma_unreasonable_high
   4. NEG         test_triple_sigma_invalid_horizon
   5. POS-inv     test_cumulative_sigma_return_at_5y
   6. POS-inv     test_cumulative_sigma_forecast_error_at_10y
   7. POS-inv     test_cumulative_sigma_analog_at_3y
   8. NEG         test_cumulative_sigma_unknown_type_raises
   9. NEG-inv     test_triple_sigma_frozen
  10. POS         test_triple_sigma_zero_allowed
  11. NEG         test_triple_sigma_negative_forecast_error
  12. NEG         test_triple_sigma_negative_analog_dispersion

NEG count: 2, 3, 4, 8, 9, 11, 12 = 7 NEG-flavor (NEG + NEG-inv).
POS count: 1, 5, 6, 7, 10 = 5 POS-flavor (POS + POS-inv).
NEG floor: 7/12 = 58.3% >= 50% required (AP-AUTH-53).
"""
from __future__ import annotations

import math

import pytest

from macro_pipeline.ensemble.triple_sigma import (
    SIGMA_MAX_REASONABLE,
    TripleSigma,
)


# ===========================================================================
# Test 1 — POS — basic construction
# ===========================================================================


def test_triple_sigma_basic_construction() -> None:
    """POS: valid TripleSigma constructs cleanly; fields preserved."""
    s = TripleSigma(
        return_sigma=0.15,
        forecast_error_sigma=0.03,
        analog_dispersion_sigma=0.08,
        horizon=5,
    )
    assert s.return_sigma == 0.15
    assert s.forecast_error_sigma == 0.03
    assert s.analog_dispersion_sigma == 0.08
    assert s.horizon == 5


# ===========================================================================
# Test 2 — NEG — negative return_sigma
# ===========================================================================


def test_triple_sigma_negative_return_sigma() -> None:
    """NEG: negative return_sigma raises ValueError."""
    with pytest.raises(ValueError, match="return_sigma"):
        TripleSigma(
            return_sigma=-0.01,
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=0.08,
            horizon=5,
        )


# ===========================================================================
# Test 3 — NEG — unreasonably high sigma (unit-error guard)
# ===========================================================================


def test_triple_sigma_unreasonable_high() -> None:
    """NEG: sigma above SIGMA_MAX_REASONABLE (5.0) raises ValueError.

    Catches a common unit error: caller passes 15.0 (thinking percent)
    instead of 0.15 (annualized fraction).
    """
    with pytest.raises(ValueError, match="exceeds reasonable bound"):
        TripleSigma(
            return_sigma=15.0,  # 1500% annualized — clearly a unit error
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=0.08,
            horizon=5,
        )


# ===========================================================================
# Test 4 — NEG — invalid horizon
# ===========================================================================


def test_triple_sigma_invalid_horizon() -> None:
    """NEG: horizon outside (1, 3, 5, 10) raises ValueError."""
    with pytest.raises(ValueError, match="horizon"):
        TripleSigma(
            return_sigma=0.15,
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=0.08,
            horizon=2,
        )
    with pytest.raises(ValueError, match="horizon"):
        TripleSigma(
            return_sigma=0.15,
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=0.08,
            horizon=20,
        )


# ===========================================================================
# Test 5 — POS-inv — cumulative_sigma return_sigma at 5Y
# ===========================================================================


def test_cumulative_sigma_return_at_5y() -> None:
    """POS-inv: cumulative_sigma('return_sigma') == sigma * sqrt(5) at 5Y."""
    s = TripleSigma(
        return_sigma=0.15,
        forecast_error_sigma=0.03,
        analog_dispersion_sigma=0.08,
        horizon=5,
    )
    expected = 0.15 * math.sqrt(5)
    assert s.cumulative_sigma("return_sigma") == pytest.approx(expected)


# ===========================================================================
# Test 6 — POS-inv — cumulative_sigma forecast_error_sigma at 10Y
# ===========================================================================


def test_cumulative_sigma_forecast_error_at_10y() -> None:
    """POS-inv: cumulative_sigma('forecast_error_sigma') at 10Y."""
    s = TripleSigma(
        return_sigma=0.15,
        forecast_error_sigma=0.04,
        analog_dispersion_sigma=0.08,
        horizon=10,
    )
    expected = 0.04 * math.sqrt(10)
    assert s.cumulative_sigma("forecast_error_sigma") == pytest.approx(
        expected
    )


# ===========================================================================
# Test 7 — POS-inv — cumulative_sigma analog_dispersion_sigma at 3Y
# ===========================================================================


def test_cumulative_sigma_analog_at_3y() -> None:
    """POS-inv: cumulative_sigma('analog_dispersion_sigma') at 3Y."""
    s = TripleSigma(
        return_sigma=0.15,
        forecast_error_sigma=0.03,
        analog_dispersion_sigma=0.07,
        horizon=3,
    )
    expected = 0.07 * math.sqrt(3)
    assert s.cumulative_sigma("analog_dispersion_sigma") == pytest.approx(
        expected
    )


# ===========================================================================
# Test 8 — NEG — cumulative_sigma unknown type raises
# ===========================================================================


def test_cumulative_sigma_unknown_type_raises() -> None:
    """NEG: cumulative_sigma with unknown sigma_type raises ValueError."""
    s = TripleSigma(
        return_sigma=0.15,
        forecast_error_sigma=0.03,
        analog_dispersion_sigma=0.08,
        horizon=5,
    )
    with pytest.raises(ValueError, match="Unknown sigma_type"):
        s.cumulative_sigma("undefined_sigma")


# ===========================================================================
# Test 9 — NEG-inv — frozen dataclass rejects mutation
# ===========================================================================


def test_triple_sigma_frozen() -> None:
    """NEG-inv: TripleSigma is frozen; mutation raises."""
    s = TripleSigma(
        return_sigma=0.15,
        forecast_error_sigma=0.03,
        analog_dispersion_sigma=0.08,
        horizon=5,
    )
    with pytest.raises(Exception):
        s.return_sigma = 0.20  # type: ignore[misc]
    with pytest.raises(Exception):
        s.horizon = 10  # type: ignore[misc]


# ===========================================================================
# Test 10 — POS — zero sigma allowed (boundary)
# ===========================================================================


def test_triple_sigma_zero_allowed() -> None:
    """POS: zero sigma (boundary value) constructs cleanly.

    A zero forecast_error_sigma is a legitimate edge case (e.g., known-
    deterministic constant). SIGMA_MIN is inclusive.
    """
    s = TripleSigma(
        return_sigma=0.0,
        forecast_error_sigma=0.0,
        analog_dispersion_sigma=0.0,
        horizon=1,
    )
    assert s.return_sigma == 0.0
    assert s.cumulative_sigma("return_sigma") == 0.0


# ===========================================================================
# Test 11 — NEG — negative forecast_error_sigma
# ===========================================================================


def test_triple_sigma_negative_forecast_error() -> None:
    """NEG: negative forecast_error_sigma raises ValueError."""
    with pytest.raises(ValueError, match="forecast_error_sigma"):
        TripleSigma(
            return_sigma=0.15,
            forecast_error_sigma=-0.01,
            analog_dispersion_sigma=0.08,
            horizon=5,
        )


# ===========================================================================
# Test 12 — NEG — negative analog_dispersion_sigma
# ===========================================================================


def test_triple_sigma_negative_analog_dispersion() -> None:
    """NEG: negative analog_dispersion_sigma raises ValueError."""
    with pytest.raises(ValueError, match="analog_dispersion_sigma"):
        TripleSigma(
            return_sigma=0.15,
            forecast_error_sigma=0.03,
            analog_dispersion_sigma=-0.01,
            horizon=5,
        )
