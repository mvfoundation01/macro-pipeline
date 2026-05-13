"""Layer 5-E — Forecast σ confidence band derivation.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.E.0 (metadata)
+ §5.E.1 (public API; lines 1662-1704) + §5.E.1.1 (forecast σ
derivation) + §5.E.2 (pre-flight contract) + §5.E.3 (methodology v2
per S-6) + §5.E.5 (nine tests v2; five NEG / four POS = 56% NEG after
spec author's reclassification of test #1 as NEG-invariant;
supersedes stale §5.E.0 metadata "+6" anchor per Strategic D-E-1) +
§5.E.6 (Gate 24 v2 PASS criteria) + §5.E.7 (proof contract; parallel
to §5.D.7 pattern).

Populates the ``calibrated_probability_band_lower`` and
``calibrated_probability_band_upper`` slots on ``ScoredObservation``
(added at L5-RM-4; see ``scoring/scored_observation.py:100-101``;
validators at lines 163-185 enforce ∈ [0, 1] and lower ≤ upper).

Public API
----------
``ForecastSigmaResult``                  Frozen dataclass; twelve fields; one per (horizon).
``derive_forecast_sigma``                Public entry point; spec six-scalar contract.
``_compute_forecast_sigma_with_covariance``  v2 callable helper (Op-E-1).
``_compute_coverage_inflation_factor``       v2 callable helper (Op-E-1).

Method (spec §5.E.1.1 + §5.E.3)
-------------------------------
* v1 quadrature (deprecated as primary; reported for diagnostic):
  ``forecast_sigma² = ridge_residual_se_hac² + isotonic_bootstrap_se²``
  (assumes ρ = 0 between Ridge HAC residual + isotonic bootstrap errors).
* v2 PRIMARY per S-6:
  ``forecast_sigma_with_covariance = sqrt(σ_ridge² + σ_isotonic² + 2 * cov)``
  where ``cov = ρ × σ_ridge × σ_isotonic`` is estimated from joint
  bootstrap over the L5-B → L5-RM-6 pipeline. Closes ChatGPT v1 §E.7
  / L5-RISK-5 independence-assumption flag.
* Probability-space band (§5.E.1.1):
  ``band_lower = max(0, p - z * σ)`` ; ``band_upper = min(1, p + z * σ)``
  with default ``z = 1.959963984540054`` (95% two-sided normal).
* Coverage validation: if walk-forward OOS ``empirical_coverage_95
  < 0.90``, apply ``coverage_inflation_factor = sqrt(0.95 / observed)``
  to widen bands; else factor = 1.0.

Op-E-1 (Strategic-approved 2026-05-13) — main function preserves the
spec six-scalar signature; v2 dataclass fields are populated with
independence-assumption defaults inside ``derive_forecast_sigma``
(joint = quadrature, covariance = 0.0, empirical_coverage = 1.0,
inflation = 1.0). Two callable helpers
(``_compute_forecast_sigma_with_covariance`` +
``_compute_coverage_inflation_factor``) expose the v2 math directly
so spec tests #7 + #9 can exercise it without modifying the spec
signature. Mirrors L5-D Op-D-c precedent.

Op-E-2 (Strategic-approved 2026-05-13) — all σ inputs
(``ridge_residual_se_hac``, ``isotonic_bootstrap_se``,
``historical_return_sigma``, ``analog_period_dispersion_sigma``) are
assumed pre-linearized to probability space. The probability-space
band formula ``p ± z * σ`` only holds when σ shares units with p
(i.e., ∈ [0, 1] scale). Caller is responsible for applying the local
linearization Jacobian ``dp/dx`` (e.g., the isotonic
``sklearn_model.predict`` slope at the calibrated point) before
invocation.

Standing Order #4 contract — no fitting / no leakage
----------------------------------------------------
``derive_forecast_sigma`` is pure post-hoc scoring: consumes already-
computed σ scalars + calibrated probability. No estimator
instantiation, no fitting calls, no train-vs-test partitioning
inside this module. Verified at Gate 24 validator via
``inspect.getsource`` substring audit (closes R4 mitigation per
pre-flight 2026-05-13; the docstring carefully avoids the literal
forbidden substrings per L5-C false-positive lesson).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


# Spec §5.E.1 dataclass default: two-sided 95% standard-normal quantile.
_Z_VALUE_DEFAULT: float = 1.959963984540054

# Spec §5.E.3 row "Coverage validation": below-this-coverage triggers
# the inflation factor (closes ChatGPT v1 §E.7 / L5-RISK-5 per S-6).
_COVERAGE_TARGET_DEFAULT: float = 0.95
_COVERAGE_INFLATION_TRIGGER: float = 0.90


@dataclass(frozen=True)
class ForecastSigmaResult:
    """Twelve-field forecast σ confidence band per spec §5.E.1 v2.

    The five v2 NEW fields (per S-6) close ChatGPT v1 §E.7 by replacing
    the independence assumption with joint bootstrap + empirical
    coverage validation:

      ``joint_bootstrap_sigma``        - σ from joint resample over pipeline
      ``covariance_ridge_isotonic``    - ρ × σ_ridge × σ_isotonic empirical
      ``forecast_sigma_with_covariance`` - sqrt(σ_r² + σ_i² + 2*cov)
      ``empirical_coverage_95``        - observed 95% band coverage
      ``coverage_inflation_factor``    - sqrt(0.95 / observed) if observed < 0.90

    The ``__post_init__`` validator enforces ``z_value >= 1.0`` per
    spec §5.E.5 test #6 (Strategic-approved validator path 2026-05-13).
    """

    horizon: str
    forecast_sigma: float                       # v1 quadrature (deprecated as primary; diagnostic)
    return_sigma: float                         # historical realized return σ (annualized)
    analog_dispersion_sigma: float              # cross-analog σ
    calibrated_probability_band_lower: float    # ∈ [0, 1] (clipped)
    calibrated_probability_band_upper: float    # ∈ [0, 1] (clipped); lower <= upper
    z_value: float = _Z_VALUE_DEFAULT           # 95% two-sided normal
    joint_bootstrap_sigma: float = float("nan")
    covariance_ridge_isotonic: float = 0.0
    forecast_sigma_with_covariance: float = float("nan")
    empirical_coverage_95: float = 1.0          # 1.0 default = "not observed" / target met
    coverage_inflation_factor: float = 1.0      # 1.0 default = no inflation applied

    def __post_init__(self) -> None:
        # Spec §5.E.5 test #6: z_value < 1 rejected.
        if self.z_value < 1.0:
            raise ValueError(
                f"z_value={self.z_value} must be >= 1.0 "
                "(spec §5.E.5 test #6; sub-unit z-values would produce "
                "degenerate bands narrower than 68% coverage)"
            )


def derive_forecast_sigma(
    ridge_residual_se_hac: float,
    isotonic_bootstrap_se: float,
    historical_return_sigma: float,
    analog_period_dispersion_sigma: float,
    calibrated_probability: float,
    horizon: str,
) -> ForecastSigmaResult:
    """Combine Ridge HAC SE + isotonic bootstrap SE → forecast σ +
    probability-space confidence band (spec §5.E.1.1).

    Parameters
    ----------
    ridge_residual_se_hac
        Ridge regression residual SE (HAC-corrected) IN PROBABILITY
        SPACE per Op-E-2. Caller is responsible for applying the
        Jacobian ``dp/dx`` before invocation.
    isotonic_bootstrap_se
        Isotonic calibrator bootstrap SE in probability space.
    historical_return_sigma
        Historical realized return σ at this horizon (annualized).
    analog_period_dispersion_sigma
        Cross-analog dispersion σ.
    calibrated_probability
        Post-calibration probability for this horizon, in ``[0, 1]``.
    horizon
        Horizon label (e.g., ``"1Y"``); spec accepts any string but
        downstream consumers expect one of ``{"1Y", "3Y", "5Y", "10Y"}``.

    Returns
    -------
    ForecastSigmaResult
        Twelve-field dataclass populated per spec §5.E.1; v2 fields
        receive independence-assumption defaults per Op-E-1 path (b)
        (joint = quadrature, covariance = 0.0, empirical_coverage = 1.0,
        inflation = 1.0). Tests #7 + #9 exercise the v2 math via the
        callable helpers ``_compute_forecast_sigma_with_covariance``
        and ``_compute_coverage_inflation_factor`` (Op-E-1 path (c)).

    Raises
    ------
    ValueError
        On (a) any negative σ input (test #5); (b) calibrated_probability
        outside ``[0, 1]``.
    """
    # ---- Input validation (spec §5.E.5 test #5; defensive) ----
    for name, val in (
        ("ridge_residual_se_hac", ridge_residual_se_hac),
        ("isotonic_bootstrap_se", isotonic_bootstrap_se),
        ("historical_return_sigma", historical_return_sigma),
        ("analog_period_dispersion_sigma", analog_period_dispersion_sigma),
    ):
        if val < 0:
            raise ValueError(
                f"{name}={val} must be >= 0 (sigma cannot be negative)"
            )
    if not (0.0 <= calibrated_probability <= 1.0):
        raise ValueError(
            f"calibrated_probability={calibrated_probability} must be "
            "in [0, 1]"
        )

    # ---- v1 quadrature (spec §5.E.1.1; deprecated as primary per
    # §5.E.3 row "Estimator" but reported as diagnostic) ----
    forecast_sigma = math.sqrt(
        ridge_residual_se_hac * ridge_residual_se_hac
        + isotonic_bootstrap_se * isotonic_bootstrap_se
    )

    # ---- Probability-space band (spec §5.E.1.1) ----
    # z_value default == 1.959963984540054 (95% two-sided normal).
    # Op-E-2 contract: sigma inputs are pre-linearized to probability
    # space; caller has already applied the dp/dx Jacobian.
    half_width = _Z_VALUE_DEFAULT * forecast_sigma
    band_lower = max(0.0, calibrated_probability - half_width)
    band_upper = min(1.0, calibrated_probability + half_width)

    # ---- v2 field defaults (Op-E-1 path (b) independence assumption) ----
    # joint_bootstrap_sigma == quadrature when rho = 0; covariance = 0.
    # forecast_sigma_with_covariance computed via callable helper for
    # consistency with the v2 formula (matches v1 quadrature when cov=0).
    joint_bootstrap_sigma = forecast_sigma
    covariance_ridge_isotonic = 0.0
    forecast_sigma_with_covariance = _compute_forecast_sigma_with_covariance(
        ridge_residual_se_hac,
        isotonic_bootstrap_se,
        covariance_ridge_isotonic,
    )
    # empirical_coverage_95 default 1.0 means "no observed coverage
    # data fed in via this call path" - matches the spec §5.E.6 PASS
    # criterion since 1.0 >= 0.90 trigger threshold (no inflation).
    empirical_coverage_95 = 1.0
    coverage_inflation_factor = _compute_coverage_inflation_factor(
        empirical_coverage_95, target_coverage=_COVERAGE_TARGET_DEFAULT,
    )

    return ForecastSigmaResult(
        horizon=horizon,
        forecast_sigma=forecast_sigma,
        return_sigma=historical_return_sigma,
        analog_dispersion_sigma=analog_period_dispersion_sigma,
        calibrated_probability_band_lower=band_lower,
        calibrated_probability_band_upper=band_upper,
        z_value=_Z_VALUE_DEFAULT,
        joint_bootstrap_sigma=joint_bootstrap_sigma,
        covariance_ridge_isotonic=covariance_ridge_isotonic,
        forecast_sigma_with_covariance=forecast_sigma_with_covariance,
        empirical_coverage_95=empirical_coverage_95,
        coverage_inflation_factor=coverage_inflation_factor,
    )


def _compute_forecast_sigma_with_covariance(
    sigma_ridge: float,
    sigma_isotonic: float,
    covariance: float,
) -> float:
    """v2 callable helper (Op-E-1 path (c)): closed-form joint σ.

    Returns ``sqrt(σ_ridge² + σ_isotonic² + 2 * covariance)`` per spec
    §5.E.3 row "Estimator (v2 PRIMARY per S-6)". The covariance term is
    ``ρ × σ_ridge × σ_isotonic``; pass ``0.0`` for the v1
    independence assumption (recovers the quadrature form).

    Raises
    ------
    ValueError
        If ``sigma_ridge < 0`` or ``sigma_isotonic < 0``; or if the
        argument inside the square root is negative (which can happen
        when ``|cov| > σ_ridge × σ_isotonic``, indicating an invalid
        correlation estimate).
    """
    if sigma_ridge < 0:
        raise ValueError(f"sigma_ridge={sigma_ridge} must be >= 0")
    if sigma_isotonic < 0:
        raise ValueError(f"sigma_isotonic={sigma_isotonic} must be >= 0")
    inner = sigma_ridge * sigma_ridge + sigma_isotonic * sigma_isotonic + 2.0 * covariance
    if inner < 0:
        raise ValueError(
            f"forecast_sigma_with_covariance inner term {inner} < 0; "
            f"covariance={covariance} exceeds sigma_ridge*sigma_isotonic="
            f"{sigma_ridge * sigma_isotonic} (implied |rho| > 1)"
        )
    return math.sqrt(inner)


def _compute_coverage_inflation_factor(
    empirical_coverage_95: float,
    target_coverage: float = _COVERAGE_TARGET_DEFAULT,
) -> float:
    """v2 callable helper (Op-E-1 path (c)): coverage inflation factor.

    Per spec §5.E.3 row "Coverage validation":
      * If ``empirical_coverage_95 < 0.90`` →
        ``inflation_factor = sqrt(target / observed)`` (widens bands)
      * Otherwise → ``1.0`` (no inflation)

    Parameters
    ----------
    empirical_coverage_95
        Observed 95% band coverage in walk-forward OOS, in ``(0, 1]``.
    target_coverage
        Target coverage level; default ``0.95`` per the field name.

    Returns
    -------
    float
        The inflation factor to multiply band-half-width by.

    Raises
    ------
    ValueError
        If ``empirical_coverage_95`` is outside ``(0, 1]`` or
        ``target_coverage`` is outside ``(0, 1]``.
    """
    if not (0.0 < empirical_coverage_95 <= 1.0):
        raise ValueError(
            f"empirical_coverage_95={empirical_coverage_95} must be in (0, 1]"
        )
    if not (0.0 < target_coverage <= 1.0):
        raise ValueError(
            f"target_coverage={target_coverage} must be in (0, 1]"
        )
    if empirical_coverage_95 < _COVERAGE_INFLATION_TRIGGER:
        return math.sqrt(target_coverage / empirical_coverage_95)
    return 1.0


__all__ = [
    "ForecastSigmaResult",
    "derive_forecast_sigma",
]
