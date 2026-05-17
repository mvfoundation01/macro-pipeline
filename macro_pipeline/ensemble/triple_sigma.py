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
from typing import Optional, Tuple

# Range bounds (Strategic L6-C spec).
SIGMA_MIN = 0.0
SIGMA_MAX_REASONABLE = 5.0  # 500% annualized; unit-error guard

# Supported horizons per Vision §1 + spec §3.3 (1Y/3Y/5Y/10Y).
SUPPORTED_HORIZONS = frozenset({1, 3, 5, 10})

# Valid sigma-type selectors for the cumulative_sigma helper.
SIGMA_TYPES = frozenset(
    {"return_sigma", "forecast_error_sigma", "analog_dispersion_sigma"}
)

# L6-J D3 (ChatGPT R7 #7 / C-9) sqrt-t validity reason codes per Vision §5
# + §11. Each code names a runtime condition that degrades the sqrt-t
# scaling approximation. The flag fires when any condition is detected.
SIGMA_VALIDITY_REASON_CODES = frozenset({
    "vol_cluster_detected",
    "structural_break_detected",
    "policy_shock_detected",
    "realized_vol_ratio_threshold_breach",
})

# Default realized-vol ratio threshold: when realized vol > 2x ann vol the
# sqrt-t approximation has materially degraded; flag triggers.
DEFAULT_REALIZED_VOL_RATIO_THRESHOLD = 2.0


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
    # L6-J D3 — sqrt-t runtime validity diagnostic (defaults preserve
    # L6-C backward compat).
    sqrt_t_scaling_warning: bool = False
    sqrt_t_validity_reason_codes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Invariant 1 (L6-I D1) — finite checks BEFORE range checks.
        # NaN/inf bypass range comparisons (NaN < x is always False);
        # explicit finite check rejects them with a clear error.
        for field_name, value in (
            ("return_sigma", self.return_sigma),
            ("forecast_error_sigma", self.forecast_error_sigma),
            ("analog_dispersion_sigma", self.analog_dispersion_sigma),
        ):
            if not math.isfinite(value):
                raise ValueError(
                    f"{field_name} must be finite; got {value!r}"
                )
        # Invariant 2 — sigma range checks (per-field).
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
        # Invariant 3 — horizon membership.
        if self.horizon not in SUPPORTED_HORIZONS:
            raise ValueError(
                f"horizon {self.horizon} not in "
                f"{sorted(SUPPORTED_HORIZONS)}"
            )
        # L6-J D3 invariants — sqrt-t validity diagnostics.
        if not isinstance(self.sqrt_t_validity_reason_codes, tuple):
            raise TypeError(
                f"sqrt_t_validity_reason_codes must be tuple; got "
                f"{type(self.sqrt_t_validity_reason_codes).__name__}"
            )
        for code in self.sqrt_t_validity_reason_codes:
            if code not in SIGMA_VALIDITY_REASON_CODES:
                raise ValueError(
                    f"Unknown sqrt_t validity reason code: {code!r}; "
                    f"expected one of "
                    f"{sorted(SIGMA_VALIDITY_REASON_CODES)}"
                )
        # Flag must agree with reason-codes presence (single source of truth).
        expected_warning = len(self.sqrt_t_validity_reason_codes) > 0
        if self.sqrt_t_scaling_warning != expected_warning:
            raise ValueError(
                f"sqrt_t_scaling_warning ({self.sqrt_t_scaling_warning}) "
                f"must equal (reason_codes non-empty: {expected_warning})"
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


# =============================================================================
# L6-J D3 — sqrt-t scaling runtime validity diagnostics
# =============================================================================


def compute_sigma_validity_diagnostics(
    vol_cluster_flag: bool = False,
    structural_break_flag: bool = False,
    policy_shock_flag: bool = False,
    realized_vol_ratio: Optional[float] = None,
    realized_vol_ratio_threshold: float = DEFAULT_REALIZED_VOL_RATIO_THRESHOLD,
) -> Tuple[bool, Tuple[str, ...]]:
    """L6-J D3 — Vision §5 + §11 runtime validity diagnostic for sqrt-t scaling.

    Cumulative sigma ≈ ann. sigma × sqrt(t) is APPROXIMATE per Vision §5.
    The approximation degrades under:

      - vol_cluster_detected           variance non-stationarity / GARCH
                                       heteroscedasticity
      - structural_break_detected      regime shift in mean / variance
      - policy_shock_detected          Fed framework / fiscal dominance shift
      - realized_vol_ratio_threshold_breach
                                       realized_vol > threshold × ann_vol
                                       (default threshold 2.0)

    Producer integration discipline (L6-J): the three boolean flags
    accept defaults of False (no detection). Producers for these flags
    (vol-cluster detector, structural-break test like Quandt-Andrews
    supW, policy-shock indicator) are deferred to L7. The
    ``realized_vol_ratio`` is computable from existing aggregator
    diagnostics (forecast_error_sigma vs return_sigma) and is the
    sole L6-J-empirical flag.

    Parameters
    ----------
    vol_cluster_flag, structural_break_flag, policy_shock_flag
        Optional runtime detector flags. Defaults to False (no detection).
    realized_vol_ratio
        Optional realized/expected vol ratio; ``None`` skips threshold check.
    realized_vol_ratio_threshold
        Threshold above which ``realized_vol_ratio_threshold_breach``
        fires. Default ``DEFAULT_REALIZED_VOL_RATIO_THRESHOLD`` (2.0).

    Returns
    -------
    tuple[bool, tuple[str, ...]]
        ``(sqrt_t_scaling_warning, reason_codes)``. Warning fires iff
        any reason code present. Reason codes are returned in canonical
        order matching ``SIGMA_VALIDITY_REASON_CODES``.

    Raises
    ------
    ValueError
        If ``realized_vol_ratio`` or ``realized_vol_ratio_threshold``
        is non-finite.
    """
    if realized_vol_ratio is not None and not math.isfinite(realized_vol_ratio):
        raise ValueError(
            f"realized_vol_ratio must be finite or None; got "
            f"{realized_vol_ratio!r}"
        )
    if not math.isfinite(realized_vol_ratio_threshold):
        raise ValueError(
            f"realized_vol_ratio_threshold must be finite; got "
            f"{realized_vol_ratio_threshold!r}"
        )

    reasons: list = []
    if vol_cluster_flag:
        reasons.append("vol_cluster_detected")
    if structural_break_flag:
        reasons.append("structural_break_detected")
    if policy_shock_flag:
        reasons.append("policy_shock_detected")
    if (
        realized_vol_ratio is not None
        and realized_vol_ratio > realized_vol_ratio_threshold
    ):
        reasons.append("realized_vol_ratio_threshold_breach")

    warning = len(reasons) > 0
    return (warning, tuple(reasons))
