"""TripleSigma dataclass for L6 ensemble aggregation (L6-C).

Per Strategic L6-C inline spec (Batch 1 of L6 sprint, 2026-05-15).
Implements Vision v2.0 §5 Triple sigma Reporting (BINDING for return
forecasts) + Pipeline Guide §8.3 template.

Three distinct sigma fields per return forecast (Vision §5)
-----------------------------------------------------------
  return_sigma             — Annualized regime-conditional volatility
                             ("what the asset typically does")
  forecast_error_sigma     — Model uncertainty around central estimate
                             ("what we might be wrong about")
  analog_dispersion_sigma  — Historical dispersion across reference-class
                             analogs ("what historical paths showed")

Cumulative scaling (Vision §5 + Strategic PD7)
----------------------------------------------
``cumulative_sigma(sigma_type)`` returns ``base_sigma * sqrt(horizon)``.

**CRITICAL CAVEATS — cumulative sigma ≈ annualized sigma × sqrt(t) is
APPROXIMATE.** Per Vision §5, the square-root-of-time scaling may fail
under:

  - regime shifts (variance non-stationarity)
  - volatility clustering (GARCH-type heteroscedasticity)
  - crises (jump risk, fat tails)
  - policy shocks (Fed regime changes, fiscal dominance)

The approximation degrades at longer horizons. Per Vision §1 Pillar 2
academic methodology + Pillar 5 operational discipline, callers must
document the caveat alongside any cumulative-sigma figure surfaced in
output (Vision §11 L3 layer).

Sanity bound (Strategic PD6 derivative)
---------------------------------------
``SIGMA_MAX_REASONABLE = 5.0`` flags unit-error inputs (e.g., caller
passed 50.0 thinking percent instead of 0.50 as a fraction). For
equity index annualized sigma the empirical range is roughly
[0.05, 0.40]; 5.0 = 500% annualized is unphysical for diversified
indices and triggers a ValueError.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Range bounds (Strategic L6-C spec).
SIGMA_MIN = 0.0
SIGMA_MAX_REASONABLE = 5.0  # 500% annualized; unit-error guard

# Supported horizons per Vision §1 + spec §3.3 (1Y/3Y/5Y/10Y).
SUPPORTED_HORIZONS = frozenset({1, 3, 5, 10})

# Valid sigma-type selectors for the cumulative_sigma helper.
SIGMA_TYPES = frozenset(
    {"return_sigma", "forecast_error_sigma", "analog_dispersion_sigma"}
)


@dataclass(frozen=True)
class TripleSigma:
    """Triple sigma Reporting per Vision v2.0 §5 (BINDING for return forecasts).

    Three distinct sigma fields; never conflate (Vision §5):

      return_sigma             annualized regime-conditional volatility
      forecast_error_sigma     model uncertainty around central forecast
      analog_dispersion_sigma  historical dispersion across analogs

    Invariants enforced by ``__post_init__``
    ----------------------------------------
      1. All three sigmas in [0, 5.0]  (5.0 is unit-error sanity guard;
         legitimate annualized sigma for diversified equity indices
         empirically falls in roughly [0.05, 0.40]).
      2. horizon in (1, 3, 5, 10).

    Methods
    -------
    ``cumulative_sigma(sigma_type)``
        Return ``base_sigma * sqrt(horizon)`` for the requested
        sigma-type. CAVEAT: square-root-of-time approximation may fail
        under regime shifts / volatility clustering / crises / policy
        shocks. See module docstring + Vision §5.
    """

    return_sigma: float
    forecast_error_sigma: float
    analog_dispersion_sigma: float
    horizon: int

    def __post_init__(self) -> None:
        # Invariant 1 — sigma range checks (per-field).
        for field_name, value in (
            ("return_sigma", self.return_sigma),
            ("forecast_error_sigma", self.forecast_error_sigma),
            ("analog_dispersion_sigma", self.analog_dispersion_sigma),
        ):
            if value < SIGMA_MIN:
                raise ValueError(
                    f"{field_name} {value} below {SIGMA_MIN}"
                )
            if value > SIGMA_MAX_REASONABLE:
                raise ValueError(
                    f"{field_name} {value} exceeds reasonable bound "
                    f"{SIGMA_MAX_REASONABLE}; verify units (annualized "
                    f"fraction, not percent)"
                )
        # Invariant 2 — horizon membership.
        if self.horizon not in SUPPORTED_HORIZONS:
            raise ValueError(
                f"horizon {self.horizon} not in "
                f"{sorted(SUPPORTED_HORIZONS)}"
            )

    def cumulative_sigma(self, sigma_type: str = "return_sigma") -> float:
        """Cumulative sigma over ``self.horizon`` years.

        Returns ``base_sigma * sqrt(horizon)`` for the chosen sigma-type.

        CAVEAT
        ------
        The sigma × sqrt(t) scaling is APPROXIMATE per Vision §5. The
        approximation may fail when:

          - variance is non-stationary (regime shifts)
          - returns exhibit volatility clustering (GARCH heteroscedasticity)
          - jump risk is material (crises, fat tails)
          - policy shocks occur (Fed framework changes, fiscal dominance)

        Callers surfacing cumulative-sigma figures in user output MUST
        accompany them with this caveat per Vision §11 L3 layer.

        Parameters
        ----------
        sigma_type
            One of ``"return_sigma"`` / ``"forecast_error_sigma"`` /
            ``"analog_dispersion_sigma"``.

        Raises
        ------
        ValueError
            If ``sigma_type`` is not a valid SIGMA_TYPES member.
        """
        if sigma_type == "return_sigma":
            base = self.return_sigma
        elif sigma_type == "forecast_error_sigma":
            base = self.forecast_error_sigma
        elif sigma_type == "analog_dispersion_sigma":
            base = self.analog_dispersion_sigma
        else:
            raise ValueError(
                f"Unknown sigma_type {sigma_type!r}; expected one of "
                f"{sorted(SIGMA_TYPES)}"
            )
        return base * math.sqrt(self.horizon)
