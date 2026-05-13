"""Layer 5-E — tests for ``macro_pipeline.analysis.forecast_sigma``.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.E.5 (nine tests
v2; five NEG / four POS = 56% NEG after spec author's reclassification
of test #1 as NEG-invariant; supersedes stale §5.E.0 metadata "+6"
anchor per Strategic D-E-1 disposition 2026-05-13).

L5b-KICK-2 (tag ``l5b-kick-2-accept``) appended six tests (#10-#15)
closing the Codex 5.5 IMPORTANT + ChatGPT 5.5 CRITICAL #2 reviewer
"diagnostic-helpers-only" flag via the AP-AUTH-53 reviewer-driven-
kickoff-item pattern. New tests cover the v2 production wrapper
``derive_forecast_sigma_v2`` + the no-default ``diagnostic_only``
field. Post-KICK-2 NEG ratio for the L5-E suite: eight NEG / seven
POS = 53% NEG (above the 50% floor).

Test inventory (mirrors §5.E.5 row order; KICK-2 entries flagged):
  1   NEG-inv  test_forecast_sigma_quadrature_and_joint_emitted_per_horizon
  2   POS-inv  test_band_lower_le_calibrated_le_band_upper
  3   POS      test_band_clipped_to_zero_one
  4   NEG-inv  test_triple_sigma_three_distinct_values_emitted
  5   NEG      test_rejects_negative_sigma_input
  6   NEG      test_rejects_z_value_below_one
  7   POS      test_joint_bootstrap_pipeline_emits_covariance_term
  8   POS      test_empirical_coverage_reported_per_horizon
  9   NEG      test_coverage_inflation_factor_applied_when_coverage_below_90
  10  POS      test_kick2_v2_wrapper_emits_diagnostic_only_false       [KICK-2]
  11  POS      test_kick2_v1_legacy_emits_diagnostic_only_true         [KICK-2]
  12  NEG      test_kick2_v2_rejects_missing_required_kwargs           [KICK-2]
  13  NEG      test_kick2_dataclass_rejects_missing_diagnostic_only    [KICK-2]
  14  POS      test_kick2_v2_covariance_and_coverage_propagate_to_result [KICK-2]
  15  NEG      test_kick2_v2_rejects_invalid_covariance_or_coverage_bounds [KICK-2]
"""
from __future__ import annotations

import math

import pytest

from macro_pipeline.analysis.forecast_sigma import (
    ForecastSigmaResult,
    _compute_coverage_inflation_factor,
    _compute_forecast_sigma_with_covariance,
    derive_forecast_sigma,
    derive_forecast_sigma_v2,
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
            diagnostic_only=True,  # KICK-2: no-default field; this construction is diagnostic-flavoured
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
        diagnostic_only=False,  # KICK-2: caller-supplied empirical coverage = production-grade
        empirical_coverage_95=0.92,
    )
    assert custom.empirical_coverage_95 == 0.92
    assert custom.diagnostic_only is False


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


# ===========================================================================
# L5b-KICK-2 tests #10-#15 — v2 production wrapper / diagnostic_only flag
# ---------------------------------------------------------------------------
# Closes Codex 5.5 IMPORTANT + ChatGPT 5.5 CRITICAL #2 reviewer flag
# ("diagnostic-helpers-only" v2 path → production-mandatory pathway) via
# the AP-AUTH-53 reviewer-driven-kickoff-item pattern. Tests probe both
# the v2 wrapper contract (POS) and the no-default field forcing
# semantics (NEG). NEG ratio 3/6 = 50% (floor met).
# ===========================================================================


# ---------------------------------------------------------------------------
# Test #10 — POS (KICK-2)
# ---------------------------------------------------------------------------
def test_kick2_v2_wrapper_emits_diagnostic_only_false():
    """KICK-2: ``derive_forecast_sigma_v2(...)`` returns a Result whose
    ``diagnostic_only is False`` — flags production-grade band derivation
    (caller supplied joint covariance + empirical coverage, not the
    independence-assumption placeholders)."""
    r = derive_forecast_sigma_v2(
        ridge_residual_se_hac=0.07,
        isotonic_bootstrap_se=0.11,
        historical_return_sigma=0.15,
        analog_period_dispersion_sigma=0.12,
        calibrated_probability=0.50,
        horizon="1Y",
        joint_bootstrap_covariance=0.004,
        empirical_coverage_95=0.93,
    )
    assert r.diagnostic_only is False
    # Cross-check: production-grade Result carries the caller-supplied
    # covariance verbatim (not the v1 zero placeholder).
    assert r.covariance_ridge_isotonic == 0.004


# ---------------------------------------------------------------------------
# Test #11 — POS (KICK-2)
# ---------------------------------------------------------------------------
def test_kick2_v1_legacy_emits_diagnostic_only_true():
    """KICK-2: legacy ``derive_forecast_sigma(...)`` returns a Result
    whose ``diagnostic_only is True`` — flags the independence-
    assumption / placeholder-coverage path so downstream consumers can
    detect miswiring."""
    r = derive_forecast_sigma(0.07, 0.11, 0.15, 0.12, 0.50, "1Y")
    assert r.diagnostic_only is True
    # Sanity: v1 path populates v2 fields with placeholders (cov=0,
    # coverage=1.0, inflation=1.0).
    assert r.covariance_ridge_isotonic == 0.0
    assert r.empirical_coverage_95 == 1.0
    assert r.coverage_inflation_factor == 1.0


# ---------------------------------------------------------------------------
# Test #12 — NEG (KICK-2)
# ---------------------------------------------------------------------------
def test_kick2_v2_rejects_missing_required_kwargs():
    """KICK-2: omitting either ``joint_bootstrap_covariance`` or
    ``empirical_coverage_95`` raises ``TypeError`` — no-default
    contract forces caller intent (Sxx-14 catastrophic-state
    mitigation)."""
    # Omit joint_bootstrap_covariance entirely.
    with pytest.raises(TypeError, match=r"joint_bootstrap_covariance"):
        derive_forecast_sigma_v2(
            ridge_residual_se_hac=0.07,
            isotonic_bootstrap_se=0.11,
            historical_return_sigma=0.15,
            analog_period_dispersion_sigma=0.12,
            calibrated_probability=0.50,
            horizon="1Y",
            empirical_coverage_95=0.93,
        )
    # Omit empirical_coverage_95 entirely.
    with pytest.raises(TypeError, match=r"empirical_coverage_95"):
        derive_forecast_sigma_v2(
            ridge_residual_se_hac=0.07,
            isotonic_bootstrap_se=0.11,
            historical_return_sigma=0.15,
            analog_period_dispersion_sigma=0.12,
            calibrated_probability=0.50,
            horizon="1Y",
            joint_bootstrap_covariance=0.004,
        )


# ---------------------------------------------------------------------------
# Test #13 — NEG (KICK-2)
# ---------------------------------------------------------------------------
def test_kick2_dataclass_rejects_missing_diagnostic_only():
    """KICK-2: bare ``ForecastSigmaResult(...)`` construction without
    ``diagnostic_only=`` raises ``TypeError`` — proves the no-default
    contract; protects against silent production-grade flag
    misclassification."""
    with pytest.raises(TypeError, match=r"diagnostic_only"):
        ForecastSigmaResult(
            horizon="1Y",
            forecast_sigma=0.10,
            return_sigma=0.15,
            analog_dispersion_sigma=0.12,
            calibrated_probability_band_lower=0.40,
            calibrated_probability_band_upper=0.60,
            # diagnostic_only deliberately omitted — must raise
        )


# ---------------------------------------------------------------------------
# Test #14 — POS (KICK-2)
# ---------------------------------------------------------------------------
def test_kick2_v2_covariance_and_coverage_propagate_to_result():
    """KICK-2: caller-supplied ``joint_bootstrap_covariance`` +
    ``empirical_coverage_95`` propagate verbatim to the result fields;
    ``forecast_sigma_with_covariance`` recomputed using the supplied
    covariance; ``coverage_inflation_factor`` recomputed via the
    helper. Closed-form to 1e-10."""
    sigma_r, sigma_i = 0.10, 0.15
    cov_in, cov_emp_in = 0.005, 0.85   # coverage below 0.90 → inflation triggers
    r = derive_forecast_sigma_v2(
        ridge_residual_se_hac=sigma_r,
        isotonic_bootstrap_se=sigma_i,
        historical_return_sigma=0.18,
        analog_period_dispersion_sigma=0.14,
        calibrated_probability=0.50,
        horizon="3Y",
        joint_bootstrap_covariance=cov_in,
        empirical_coverage_95=cov_emp_in,
    )
    # Covariance propagation.
    assert r.covariance_ridge_isotonic == cov_in
    expected_fsc = math.sqrt(sigma_r * sigma_r + sigma_i * sigma_i + 2.0 * cov_in)
    assert abs(r.forecast_sigma_with_covariance - expected_fsc) < 1e-10
    # joint_bootstrap_sigma populated with the v2 (with-covariance) estimate.
    assert abs(r.joint_bootstrap_sigma - expected_fsc) < 1e-10
    # Coverage propagation.
    assert r.empirical_coverage_95 == cov_emp_in
    expected_inflation = math.sqrt(0.95 / cov_emp_in)
    assert abs(r.coverage_inflation_factor - expected_inflation) < 1e-10
    # diagnostic_only flag flipped to production-grade.
    assert r.diagnostic_only is False


# ---------------------------------------------------------------------------
# Test #15 — NEG (KICK-2 §revision bounds-check per Strategic ruling #4)
# ---------------------------------------------------------------------------
def test_kick2_v2_rejects_invalid_covariance_or_coverage_bounds():
    """KICK-2 §revision: v2 wrapper enforces bounds on the two new
    required kwargs.

    Math note: ``joint_bootstrap_covariance`` MAY legitimately be
    negative (anti-correlated noise admissible per
    ``_compute_forecast_sigma_with_covariance`` line 263); the inner-
    term guard ``|cov| <= sigma_ridge * sigma_isotonic`` (i.e.,
    ``|rho| <= 1``) provides the natural bound, not a flat non-
    negativity assertion. Coverage_95 is bounded strict-positive ≤ 1.0.

    Asserts:
    * NaN covariance rejected at v2 entry (finiteness guard)
    * inf covariance rejected at v2 entry (finiteness guard)
    * NEGATIVE covariance ACCEPTED when within |rho|<=1 (sanity:
      mathematically valid anti-correlated case must not raise)
    * Covariance violating |rho|<=1 propagates ValueError from helper
    * Coverage = 0.0 rejected (strict-positive bound)
    * Coverage = 1.5 rejected (above 1.0 bound)
    """
    sigma_r, sigma_i = 0.10, 0.15
    # ---- Finiteness guard ----
    with pytest.raises(ValueError, match=r"joint_bootstrap_covariance.*must be finite"):
        derive_forecast_sigma_v2(
            ridge_residual_se_hac=sigma_r,
            isotonic_bootstrap_se=sigma_i,
            historical_return_sigma=0.15,
            analog_period_dispersion_sigma=0.12,
            calibrated_probability=0.50,
            horizon="1Y",
            joint_bootstrap_covariance=float("nan"),
            empirical_coverage_95=0.95,
        )
    with pytest.raises(ValueError, match=r"joint_bootstrap_covariance.*must be finite"):
        derive_forecast_sigma_v2(
            ridge_residual_se_hac=sigma_r,
            isotonic_bootstrap_se=sigma_i,
            historical_return_sigma=0.15,
            analog_period_dispersion_sigma=0.12,
            calibrated_probability=0.50,
            horizon="1Y",
            joint_bootstrap_covariance=float("inf"),
            empirical_coverage_95=0.95,
        )

    # ---- Sanity: negative covariance WITHIN |rho|<=1 must succeed
    # (anti-correlated noise is mathematically admissible). ----
    safe_negative_cov = -0.5 * sigma_r * sigma_i   # |rho|=0.5
    r = derive_forecast_sigma_v2(
        ridge_residual_se_hac=sigma_r,
        isotonic_bootstrap_se=sigma_i,
        historical_return_sigma=0.15,
        analog_period_dispersion_sigma=0.12,
        calibrated_probability=0.50,
        horizon="1Y",
        joint_bootstrap_covariance=safe_negative_cov,
        empirical_coverage_95=0.95,
    )
    assert r.covariance_ridge_isotonic == safe_negative_cov
    assert r.diagnostic_only is False

    # ---- |rho|>1 propagates ValueError from helper ----
    impossible_cov = -2.0 * sigma_r * sigma_i   # implies |rho|=2
    with pytest.raises(ValueError, match=r"forecast_sigma_with_covariance inner term"):
        derive_forecast_sigma_v2(
            ridge_residual_se_hac=sigma_r,
            isotonic_bootstrap_se=sigma_i,
            historical_return_sigma=0.15,
            analog_period_dispersion_sigma=0.12,
            calibrated_probability=0.50,
            horizon="1Y",
            joint_bootstrap_covariance=impossible_cov,
            empirical_coverage_95=0.95,
        )

    # ---- Coverage bounds ----
    with pytest.raises(ValueError, match=r"empirical_coverage_95.*must be in"):
        derive_forecast_sigma_v2(
            ridge_residual_se_hac=sigma_r,
            isotonic_bootstrap_se=sigma_i,
            historical_return_sigma=0.15,
            analog_period_dispersion_sigma=0.12,
            calibrated_probability=0.50,
            horizon="1Y",
            joint_bootstrap_covariance=0.004,
            empirical_coverage_95=0.0,
        )
    with pytest.raises(ValueError, match=r"empirical_coverage_95.*must be in"):
        derive_forecast_sigma_v2(
            ridge_residual_se_hac=sigma_r,
            isotonic_bootstrap_se=sigma_i,
            historical_return_sigma=0.15,
            analog_period_dispersion_sigma=0.12,
            calibrated_probability=0.50,
            horizon="1Y",
            joint_bootstrap_covariance=0.004,
            empirical_coverage_95=1.5,
        )
