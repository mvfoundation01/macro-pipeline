"""Layer 5-E — tests for ``macro_pipeline.analysis.forecast_sigma``.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.E.5 (nine tests
v2; five NEG / four POS = 56% NEG after spec author's reclassification
of test #1 as NEG-invariant; supersedes stale §5.E.0 metadata "+6"
anchor per Strategic D-E-1 disposition 2026-05-13).

Test inventory (mirrors §5.E.5 row order):
  1   NEG-inv  test_forecast_sigma_quadrature_and_joint_emitted_per_horizon
  2   POS-inv  test_band_lower_le_calibrated_le_band_upper
  3   POS      test_band_clipped_to_zero_one
  4   NEG-inv  test_triple_sigma_three_distinct_values_emitted
  5   NEG      test_rejects_negative_sigma_input
  6   NEG      test_rejects_z_value_below_one
  7   POS      test_joint_bootstrap_pipeline_emits_covariance_term
  8   POS      test_empirical_coverage_reported_per_horizon
  9   NEG      test_coverage_inflation_factor_applied_when_coverage_below_90
"""
from __future__ import annotations

import math

import pytest

from macro_pipeline.analysis.forecast_sigma import (
    ForecastSigmaResult,
    _compute_coverage_inflation_factor,
    _compute_forecast_sigma_with_covariance,
    derive_forecast_sigma,
)


# ---------------------------------------------------------------------------
# Test #1 — NEG-invariant (per spec §5.E.5 footer reclassification)
# ---------------------------------------------------------------------------
def test_forecast_sigma_quadrature_and_joint_emitted_per_horizon():
    """Spec §5.E.5 test #1: both ``forecast_sigma`` (v1 quadrature) AND
    ``joint_bootstrap_sigma`` (v2 primary) populated; quadrature matches
    ``sqrt(σ_ridge² + σ_isotonic²)`` to 1e-10."""
    sigma_r, sigma_i = 0.07, 0.11
    expected_quadrature = math.sqrt(sigma_r * sigma_r + sigma_i * sigma_i)
    r = derive_forecast_sigma(
        sigma_r, sigma_i, 0.15, 0.12, 0.50, "1Y",
    )
    # Quadrature within 1e-10 (in practice 0.0e+00 by closed-form math).
    assert abs(r.forecast_sigma - expected_quadrature) < 1e-10
    # joint_bootstrap_sigma populated (independence default == quadrature).
    assert r.joint_bootstrap_sigma == r.forecast_sigma
    # Diagnostic: NaN absent from both fields.
    assert math.isfinite(r.forecast_sigma)
    assert math.isfinite(r.joint_bootstrap_sigma)


# ---------------------------------------------------------------------------
# Test #2 — POS-invariant
# ---------------------------------------------------------------------------
def test_band_lower_le_calibrated_le_band_upper():
    """Spec §5.E.5 test #2: ``band_lower <= calibrated <= band_upper``
    for any input. Clip mechanism preserves the invariant even at
    extremes."""
    test_cases = [
        (0.01, 0.02, 0.10, 0.10, 0.50, "1Y"),     # small sigma
        (0.05, 0.07, 0.15, 0.12, 0.30, "3Y"),     # mid case
        (0.30, 0.40, 0.20, 0.15, 0.95, "5Y"),     # high sigma + high p
        (0.30, 0.40, 0.20, 0.15, 0.05, "10Y"),    # high sigma + low p
        (0.0, 0.0, 0.10, 0.10, 0.50, "1Y"),       # zero sigma -> zero-width band
    ]
    for sigma_r, sigma_i, ret, analog, p, h in test_cases:
        r = derive_forecast_sigma(sigma_r, sigma_i, ret, analog, p, h)
        assert r.calibrated_probability_band_lower <= p, (
            f"case ({sigma_r}, {sigma_i}, {p}): "
            f"band_lower={r.calibrated_probability_band_lower} > p={p}"
        )
        assert p <= r.calibrated_probability_band_upper, (
            f"case ({sigma_r}, {sigma_i}, {p}): "
            f"p={p} > band_upper={r.calibrated_probability_band_upper}"
        )


# ---------------------------------------------------------------------------
# Test #3 — POS
# ---------------------------------------------------------------------------
def test_band_clipped_to_zero_one():
    """Spec §5.E.5 test #3: extreme ``calibrated=0.05`` + high σ →
    ``band_lower == 0.0``; symmetric ``calibrated=0.95`` + high σ →
    ``band_upper == 1.0``."""
    # Low-probability + high sigma -> band_lower clipped to 0.0
    r_low = derive_forecast_sigma(0.20, 0.30, 0.15, 0.12, 0.05, "1Y")
    assert r_low.calibrated_probability_band_lower == 0.0
    # High-probability + high sigma -> band_upper clipped to 1.0
    r_high = derive_forecast_sigma(0.20, 0.30, 0.15, 0.12, 0.95, "1Y")
    assert r_high.calibrated_probability_band_upper == 1.0


# ---------------------------------------------------------------------------
# Test #4 — NEG-invariant
# ---------------------------------------------------------------------------
def test_triple_sigma_three_distinct_values_emitted():
    """Spec §5.E.5 test #4 + §5.E.3.1 triple-σ disambiguation:
    ``forecast_sigma`` + ``return_sigma`` + ``analog_dispersion_sigma``
    all populated and non-NaN."""
    r = derive_forecast_sigma(0.05, 0.07, 0.15, 0.12, 0.50, "1Y")
    # All three are distinct semantic fields.
    assert hasattr(r, "forecast_sigma")
    assert hasattr(r, "return_sigma")
    assert hasattr(r, "analog_dispersion_sigma")
    # All three populated and finite.
    assert math.isfinite(r.forecast_sigma)
    assert math.isfinite(r.return_sigma)
    assert math.isfinite(r.analog_dispersion_sigma)
    # And they hold the values passed in (return_sigma + analog passed
    # verbatim; forecast_sigma is derived).
    assert r.return_sigma == 0.15
    assert r.analog_dispersion_sigma == 0.12


# ---------------------------------------------------------------------------
# Test #5 — NEG
# ---------------------------------------------------------------------------
def test_rejects_negative_sigma_input():
    """Spec §5.E.5 test #5: ``ridge_residual_se_hac=-0.1`` raises
    ``ValueError``."""
    with pytest.raises(ValueError, match=r"must be >= 0"):
        derive_forecast_sigma(-0.1, 0.05, 0.15, 0.12, 0.50, "1Y")
    # Symmetric NEG check on isotonic_bootstrap_se.
    with pytest.raises(ValueError, match=r"must be >= 0"):
        derive_forecast_sigma(0.05, -0.1, 0.15, 0.12, 0.50, "1Y")


# ---------------------------------------------------------------------------
# Test #6 — NEG
# ---------------------------------------------------------------------------
def test_rejects_z_value_below_one():
    """Spec §5.E.5 test #6: ``z=0.5`` raises ``ValueError``.

    Exercised through ``ForecastSigmaResult`` ``__post_init__``
    validator (Strategic-approved 2026-05-13 — spec doesn't forbid;
    cleanest implementation per Op-E-1).
    """
    with pytest.raises(ValueError, match=r"z_value=.* must be >= 1\.0"):
        ForecastSigmaResult(
            horizon="1Y",
            forecast_sigma=0.10, return_sigma=0.15,
            analog_dispersion_sigma=0.12,
            calibrated_probability_band_lower=0.40,
            calibrated_probability_band_upper=0.60,
            z_value=0.5,  # below allowed minimum
        )


# ---------------------------------------------------------------------------
# Test #7 — POS (v2 NEW per S-6)
# ---------------------------------------------------------------------------
def test_joint_bootstrap_pipeline_emits_covariance_term():
    """Spec §5.E.5 test #7: ``forecast_sigma_with_covariance =
    sqrt(σ_ridge² + σ_isotonic² + 2 × cov_term)`` to 1e-10.

    Exercises ``_compute_forecast_sigma_with_covariance`` helper
    directly per Op-E-1 (callable v2 helper exposes the v2 math
    without modifying the spec function signature)."""
    sigma_r, sigma_i, cov = 0.10, 0.15, 0.005
    result = _compute_forecast_sigma_with_covariance(sigma_r, sigma_i, cov)
    expected = math.sqrt(sigma_r * sigma_r + sigma_i * sigma_i + 2.0 * cov)
    assert abs(result - expected) < 1e-10
    # Independence limit (cov=0) recovers v1 quadrature.
    indep = _compute_forecast_sigma_with_covariance(sigma_r, sigma_i, 0.0)
    quadrature = math.sqrt(sigma_r * sigma_r + sigma_i * sigma_i)
    assert abs(indep - quadrature) < 1e-10
    # Main function default populates this with the cov=0 result.
    r = derive_forecast_sigma(sigma_r, sigma_i, 0.15, 0.12, 0.50, "1Y")
    assert r.covariance_ridge_isotonic == 0.0
    assert abs(r.forecast_sigma_with_covariance - quadrature) < 1e-10


# ---------------------------------------------------------------------------
# Test #8 — POS (v2 NEW per S-6)
# ---------------------------------------------------------------------------
def test_empirical_coverage_reported_per_horizon():
    """Spec §5.E.5 test #8: ``empirical_coverage_95`` populated per
    horizon; reported in verification."""
    for h in ("1Y", "3Y", "5Y", "10Y"):
        r = derive_forecast_sigma(0.05, 0.07, 0.15, 0.12, 0.50, h)
        assert hasattr(r, "empirical_coverage_95")
        assert math.isfinite(r.empirical_coverage_95)
        # Main function defaults to 1.0 (no observed coverage data
        # passed; v1 path means target met by construction).
        assert r.empirical_coverage_95 == 1.0
        # No inflation under default coverage.
        assert r.coverage_inflation_factor == 1.0

    # Caller may construct ForecastSigmaResult with explicit
    # empirical_coverage_95 for downstream walk-forward reporting.
    custom = ForecastSigmaResult(
        horizon="5Y", forecast_sigma=0.10, return_sigma=0.15,
        analog_dispersion_sigma=0.12,
        calibrated_probability_band_lower=0.40,
        calibrated_probability_band_upper=0.60,
        empirical_coverage_95=0.92,
    )
    assert custom.empirical_coverage_95 == 0.92


# ---------------------------------------------------------------------------
# Test #9 — NEG (v2 NEW per S-6)
# ---------------------------------------------------------------------------
def test_coverage_inflation_factor_applied_when_coverage_below_90():
    """Spec §5.E.5 test #9: force ``empirical_coverage_95=0.85`` →
    ``coverage_inflation_factor = sqrt(0.95/0.85) ≈ 1.058``; bands
    widened accordingly.

    Exercises ``_compute_coverage_inflation_factor`` helper directly
    per Op-E-1."""
    factor = _compute_coverage_inflation_factor(0.85)
    expected = math.sqrt(0.95 / 0.85)
    assert abs(factor - expected) < 1e-10
    # Sanity: the spec example "≈ 1.058" matches within rounding.
    assert abs(factor - 1.058) < 0.01

    # No inflation at or above 0.90 trigger (NEG-invariant check on
    # the threshold mechanism).
    assert _compute_coverage_inflation_factor(0.90) == 1.0
    assert _compute_coverage_inflation_factor(0.95) == 1.0
    assert _compute_coverage_inflation_factor(1.0) == 1.0

    # Domain validation: out-of-range observed coverage raises.
    with pytest.raises(ValueError, match=r"empirical_coverage_95="):
        _compute_coverage_inflation_factor(0.0)
    with pytest.raises(ValueError, match=r"empirical_coverage_95="):
        _compute_coverage_inflation_factor(1.5)
