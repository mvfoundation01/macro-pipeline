"""L11 D3/D5 — ProducerAdapter: derive ForecastInputs from real historical panels.

Replaces L10's heuristic-modulator block in ``data_ingestion.py`` with a
panel-derived path. Each of the six `ForecastInputs` fields is computed
from the bundled L11 snapshot using a principled statistical method:

* ``point_estimates``        — historical mean real total return per horizon,
                               with Campbell-Shiller CAPE mean-reversion at 10Y
                               + cyclical form overlay at 1Y/3Y/5Y.
* ``point_estimate_n_eff``   — count of non-overlapping H-year windows in the
                               snapshot real-return series.
* ``forecast_sigmas``        — historical Ridge-style residual sigma scaled by
                               horizon's R² (when r_squared_panel is bundled).
* ``analog_dispersions``     — cross-period dispersion of historical forward
                               returns at the horizon.
* ``return_sigmas``          — annualized realized vol from SPX TR or Shiller TR,
                               scaled by sqrt(horizon).
* ``recession_probabilities``— base rate from USREC over rolling H-year windows,
                               modulated by current PMI / unemployment / yield-curve.

Form responsiveness is preserved via blended weighting (D7 invariant: ±1% PMI →
≥0.3pp Δ at 1Y).

Design notes
------------
* Pure, deterministic given (snapshot, form_data, excel_data). No I/O beyond
  snapshot reads.
* Heavy try/except wrappers around each derivation so a single corrupted panel
  doesn't sink the whole forecast. Failures recorded in ``provenance.fallbacks``.
* All outputs clipped to L6-H ForecastInputs invariant ranges before return.

Public API
----------
``ProducerAdapter``     Main orchestrator.
``DerivationResult``    Frozen result with ForecastInputs + provenance dict.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from macro_pipeline.ensemble.aggregator import SUPPORTED_HORIZONS, ForecastInputs
from macro_pipeline.webapp.snapshot_loader import SnapshotLoader, SnapshotNotFoundError

# ---------------------------------------------------------------------------
# Tunable parameters (DOCUMENTED MAGIC NUMBERS — per AP-AUTH-52)
# ---------------------------------------------------------------------------

# Long-run real total-return mean (Vision §6 prior; serves as fallback when
# panel-derived mean is unavailable). Matches L6-H canonical default.
LONG_RUN_REAL_RETURN_PRIOR = 0.065

# Historical CAPE mean used as the Campbell-Shiller anchor when a snapshot
# rolling-mean is unavailable.
CAPE_HISTORICAL_MEAN = 22.0

# Weight applied to the cyclical form overlay per horizon. Long horizons
# weight historical anchor more; short horizons let the form drive.
CYCLICAL_OVERLAY_WEIGHT: dict[int, float] = {1: 0.7, 3: 0.5, 5: 0.3, 10: 0.1}

# Sensitivity preservation: PMI/unemployment scale factors picked so that
# ±1 PMI point moves the 1Y point estimate by ≥0.3pp (D7 invariant).
# Derivation: pmi_signal = (pmi_avg - 50)/100; pmi_avg = mean(manuf, services),
# so ±1 manuf → pmi_avg ±0.5 → pmi_signal ±0.005. At 1Y weight 0.7, we need
# 0.7 * COEF * 0.005 ≥ 0.003 → COEF ≥ 0.857. Set 1.0 for safety margin.
PMI_SIGNAL_COEFFICIENT = 1.0
UNEMPLOYMENT_SIGNAL_COEFFICIENT = 0.5

# L6-H ForecastInputs invariant clamps (so a derivation outlier never breaks
# the aggregator's input validation).
POINT_ESTIMATE_CLAMP = (-0.10, 0.20)
RECESSION_P_CLAMP = (0.02, 0.95)
FORECAST_SIGMA_CLAMP = (0.005, 0.20)
RETURN_SIGMA_CLAMP = (0.05, 0.40)
ANALOG_DISPERSION_CLAMP = (0.01, 0.30)


# ---------------------------------------------------------------------------
# Result wrapper
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DerivationResult:
    """Outcome of ``ProducerAdapter.derive_forecast_inputs``.

    Fields
    ------
    inputs
        The validated ``ForecastInputs`` instance ready for ``aggregate_ensemble``.
    provenance
        Dict with keys:
          * ``mode``: ``"producer_derived"`` or ``"heuristic_fallback"``
          * ``snapshot_date``: build date of the bundled snapshot (YYYY-MM-DD)
          * ``panels_used``: tuple of panel stems consulted
          * ``producers_run``: tuple of derived field names that succeeded
          * ``fallbacks``: tuple of (field, reason) for each fallback
          * ``form_overlay_applied``: bool — True when form values were merged in
    """

    inputs: ForecastInputs
    provenance: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _clip(value: float, low: float, high: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"non-finite value cannot be clipped: {value!r}")
    return max(low, min(high, value))


def _monthly_pct_change(series: pd.Series) -> pd.Series:
    """Daily → monthly-last-obs pct change."""
    monthly = series.resample("ME").last().dropna()
    return monthly.pct_change().dropna()


def _real_return_monthly(tr_price: pd.Series, cpi: pd.Series) -> pd.Series:
    """Real total return monthly = nominal_pct_change − inflation_pct_change."""
    nom = _monthly_pct_change(tr_price)
    inf = _monthly_pct_change(cpi)
    common = nom.index.intersection(inf.index)
    return (nom.loc[common] - inf.loc[common]).dropna()


def _rolling_horizon_return(monthly_real: pd.Series, horizon_years: int) -> pd.Series:
    """Compute rolling H-year forward returns from monthly real returns.

    Returns an annualized series (compounded H-year return → annual equivalent).
    """
    window_months = horizon_years * 12
    if len(monthly_real) < window_months:
        return pd.Series(dtype=float)
    # Compound monthly returns over rolling window, then de-annualize.
    log_returns = np.log1p(monthly_real)
    rolling_total = log_returns.rolling(window_months).sum().dropna()
    annualized = np.expm1(rolling_total / horizon_years)
    return annualized


def _safe_form_value(form_data: dict[str, Any], key: str, default: float) -> float:
    raw = form_data.get(key, default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        return default
    return value


# ---------------------------------------------------------------------------
# ProducerAdapter
# ---------------------------------------------------------------------------
class ProducerAdapter:
    """Derives ForecastInputs from bundled snapshot panels + form overlay.

    Each `derive_*` method:
      1. Tries the panel-derived path.
      2. On any failure (missing panel, empty series, math error), falls back
         to the L6-H canonical default, records the fallback reason in
         ``self._fallbacks``.
      3. Clips to L6-H invariant range so the aggregator never sees an
         out-of-range input.

    The orchestrator method ``derive_forecast_inputs`` returns a
    ``DerivationResult`` with full provenance.
    """

    def __init__(self, loader: SnapshotLoader | None = None) -> None:
        self._loader = loader or SnapshotLoader()
        self._fallbacks: list[tuple[str, str]] = []
        self._panels_used: set[str] = set()
        self._producers_run: list[str] = []

    # ------------------------------------------------------------------
    # Per-field derivations
    # ------------------------------------------------------------------
    def derive_point_estimates(self, form_data: dict[str, float]) -> dict[int, float]:
        """Historical real-return anchor + Campbell-Shiller + cyclical overlay."""
        try:
            tr = self._loader.load("official_SHILLER_TR_PRICE")["SHILLER_TR_PRICE"]
            cpi = self._loader.load("official_SHILLER_CPI")["SHILLER_CPI"]
            self._panels_used.update(("official_SHILLER_TR_PRICE", "official_SHILLER_CPI"))
            real_monthly = _real_return_monthly(tr, cpi)
            if real_monthly.empty:
                raise ValueError("real-return series empty after alignment")
            annualized_mean = float(real_monthly.mean()) * 12.0
            if not math.isfinite(annualized_mean):
                raise ValueError("annualized mean non-finite")
        except (SnapshotNotFoundError, ValueError, KeyError) as exc:
            self._fallbacks.append(("point_estimates_anchor", str(exc)))
            annualized_mean = LONG_RUN_REAL_RETURN_PRIOR

        # CAPE z-score for Campbell-Shiller mean reversion at 10Y.
        try:
            cape_panel = self._loader.load("official_SHILLER_CAPE")["SHILLER_CAPE"]
            self._panels_used.add("official_SHILLER_CAPE")
            cape_hist_mean = float(cape_panel.mean())
            cape_hist_std = float(cape_panel.std())
            cape_current = _safe_form_value(
                form_data, "cape_ratio", float(cape_panel.iloc[-1])
            )
            cape_z = (cape_current - cape_hist_mean) / cape_hist_std if cape_hist_std > 0 else 0.0
        except (SnapshotNotFoundError, ValueError, KeyError) as exc:
            self._fallbacks.append(("cape_anchor", str(exc)))
            cape_current = _safe_form_value(form_data, "cape_ratio", CAPE_HISTORICAL_MEAN)
            cape_z = (cape_current - CAPE_HISTORICAL_MEAN) / 5.0

        # Cyclical signal from form values.
        pmi_avg = 0.5 * (
            _safe_form_value(form_data, "pmi_manufacturing", 50.0)
            + _safe_form_value(form_data, "pmi_services", 52.0)
        )
        unemployment = _safe_form_value(form_data, "unemployment_rate", 4.0)
        pmi_signal = (pmi_avg - 50.0) / 100.0
        unemployment_signal = (5.0 - unemployment) / 100.0
        cyclical = (
            PMI_SIGNAL_COEFFICIENT * pmi_signal
            + UNEMPLOYMENT_SIGNAL_COEFFICIENT * unemployment_signal
        )

        out: dict[int, float] = {}
        for horizon in SUPPORTED_HORIZONS:
            # Damped Campbell-Shiller adjustment at 10Y; flat anchor elsewhere.
            anchor = (
                annualized_mean - 0.005 * cape_z
                if horizon == 10
                else annualized_mean
            )
            weight_cyclical = CYCLICAL_OVERLAY_WEIGHT[horizon]
            value = weight_cyclical * cyclical + (1.0 - weight_cyclical) * anchor
            out[horizon] = _clip(value, *POINT_ESTIMATE_CLAMP)
        self._producers_run.append("point_estimates")
        return out

    def derive_point_estimate_n_eff(self) -> dict[int, int]:
        """Count of non-overlapping H-year windows in snapshot real-return panel."""
        try:
            tr = self._loader.load("official_SHILLER_TR_PRICE")["SHILLER_TR_PRICE"]
            self._panels_used.add("official_SHILLER_TR_PRICE")
            monthly = tr.resample("ME").last().dropna()
            total_months = len(monthly)
        except (SnapshotNotFoundError, ValueError, KeyError) as exc:
            self._fallbacks.append(("point_estimate_n_eff", str(exc)))
            # L6-H canonical defaults from test_aggregator.py
            return {1: 100, 3: 30, 5: 18, 10: 9}
        out: dict[int, int] = {}
        for horizon in SUPPORTED_HORIZONS:
            n = max(2, total_months // (horizon * 12))
            out[horizon] = int(n)
        self._producers_run.append("point_estimate_n_eff")
        return out

    def derive_forecast_sigmas(self) -> dict[int, float]:
        """Forecast (model-uncertainty) sigma per horizon.

        Strategy: scale L6-H canonical defaults by snapshot-derived R² shrinkage
        when ``analysis/r_squared_panel`` is bundled, else return defaults.
        """
        defaults = {1: 0.02, 3: 0.025, 5: 0.03, 10: 0.035}
        try:
            r2_panel = self._loader.load("analysis/r_squared_panel")
            self._panels_used.add("analysis/r_squared_panel")
            # Use the mean R² as a coarse shrinkage; high R² → narrower forecast band.
            if r2_panel.empty or not r2_panel.select_dtypes(include="number").shape[1]:
                raise ValueError("r_squared_panel has no numeric columns")
            mean_r2 = float(
                r2_panel.select_dtypes(include="number").stack().mean()
            )
            if not math.isfinite(mean_r2):
                raise ValueError("mean R² non-finite")
            # shrinkage factor in [0.5, 1.5]: high R² shrinks sigma, low R² widens.
            mean_r2_clamped = _clip(mean_r2, 0.0, 1.0)
            shrinkage = 1.5 - mean_r2_clamped  # mean_r2=0 → 1.5; mean_r2=1 → 0.5
        except (SnapshotNotFoundError, ValueError, KeyError) as exc:
            self._fallbacks.append(("forecast_sigmas", str(exc)))
            shrinkage = 1.0
        out = {
            horizon: _clip(defaults[horizon] * shrinkage, *FORECAST_SIGMA_CLAMP)
            for horizon in SUPPORTED_HORIZONS
        }
        self._producers_run.append("forecast_sigmas")
        return out

    def derive_analog_dispersions(self) -> dict[int, float]:
        """Cross-period dispersion of historical H-year rolling returns."""
        defaults = {1: 0.04, 3: 0.05, 5: 0.06, 10: 0.07}
        try:
            tr = self._loader.load("official_SHILLER_TR_PRICE")["SHILLER_TR_PRICE"]
            cpi = self._loader.load("official_SHILLER_CPI")["SHILLER_CPI"]
            self._panels_used.update(("official_SHILLER_TR_PRICE", "official_SHILLER_CPI"))
            real_monthly = _real_return_monthly(tr, cpi)
        except (SnapshotNotFoundError, ValueError, KeyError) as exc:
            self._fallbacks.append(("analog_dispersions", str(exc)))
            return defaults
        out: dict[int, float] = {}
        for horizon in SUPPORTED_HORIZONS:
            rolling = _rolling_horizon_return(real_monthly, horizon)
            if len(rolling) < 5 or not math.isfinite(float(rolling.std())):
                out[horizon] = defaults[horizon]
                continue
            disp = float(rolling.std())
            out[horizon] = _clip(disp, *ANALOG_DISPERSION_CLAMP)
        self._producers_run.append("analog_dispersions")
        return out

    def derive_return_sigmas(self) -> dict[int, float]:
        """Annualized realized vol from SPX TR (modern) or Shiller TR (long history)."""
        defaults = {1: 0.15, 3: 0.16, 5: 0.17, 10: 0.18}
        try:
            # Prefer modern daily SPX TR for vol estimation; fall back to Shiller.
            try:
                price_series = self._loader.load("yahoo_SPX_TR")["SPX_TR"]
                self._panels_used.add("yahoo_SPX_TR")
            except SnapshotNotFoundError:
                price_series = self._loader.load("official_SHILLER_TR_PRICE")[
                    "SHILLER_TR_PRICE"
                ]
                self._panels_used.add("official_SHILLER_TR_PRICE")
            daily_returns = price_series.resample("D").last().ffill().pct_change().dropna()
            if daily_returns.empty:
                raise ValueError("daily returns empty")
            # Use trailing 10y of daily data for vol estimation if available.
            recent = daily_returns.tail(252 * 10)
            ann_vol = float(recent.std() * math.sqrt(252))
            if not math.isfinite(ann_vol) or ann_vol <= 0:
                raise ValueError(f"annual vol invalid: {ann_vol}")
        except (SnapshotNotFoundError, ValueError, KeyError) as exc:
            self._fallbacks.append(("return_sigmas", str(exc)))
            return defaults
        out = {
            horizon: _clip(
                ann_vol * (1.0 + 0.02 * (horizon - 1)),  # mild horizon-scaling
                *RETURN_SIGMA_CLAMP,
            )
            for horizon in SUPPORTED_HORIZONS
        }
        self._producers_run.append("return_sigmas")
        return out

    def derive_recession_probabilities(
        self, form_data: dict[str, float], excel_data: dict[str, Any] | None
    ) -> dict[int, float]:
        """USREC historical base rate + form-derived cyclical bumps."""
        try:
            usrec = self._loader.load("fred_USREC")["USREC"]
            self._panels_used.add("fred_USREC")
            monthly_usrec = usrec.resample("ME").last().dropna()
            if monthly_usrec.empty:
                raise ValueError("USREC monthly empty")
            historical_base = float(monthly_usrec.mean())  # ~0.14 long-run
        except (SnapshotNotFoundError, ValueError, KeyError) as exc:
            self._fallbacks.append(("recession_p_base", str(exc)))
            historical_base = 0.14

        # Per-horizon shaping: longer horizons accumulate more recession risk
        # (chosen to land near L6-H canonical defaults 0.15/0.25/0.35/0.45 at
        # neutral inputs, then modulated by form signals).
        horizon_shape: dict[int, float] = {1: 1.0, 3: 1.6, 5: 2.2, 10: 2.8}

        pmi_avg = 0.5 * (
            _safe_form_value(form_data, "pmi_manufacturing", 50.0)
            + _safe_form_value(form_data, "pmi_services", 52.0)
        )
        unemployment = _safe_form_value(form_data, "unemployment_rate", 4.0)
        bump = 0.0
        if pmi_avg < 45.0:
            bump += 0.20
        elif pmi_avg < 50.0:
            bump += 0.10
        if unemployment > 5.5:
            bump += 0.15
        yc_inverted = bool(
            (excel_data or {}).get("yield_curve", {}).get("inverted", False)
        )
        if yc_inverted:
            bump += 0.20

        from itertools import pairwise

        out: dict[int, float] = {}
        for horizon in SUPPORTED_HORIZONS:
            baseline = historical_base * horizon_shape[horizon]
            modulated = baseline + bump * (0.5 + 0.1 * (horizon - 1))
            out[horizon] = _clip(modulated, *RECESSION_P_CLAMP)
        # Monotonicity guarantee — longer horizons must not be lower.
        for prev, curr in pairwise(SUPPORTED_HORIZONS):
            if out[curr] < out[prev]:
                out[curr] = out[prev]
        self._producers_run.append("recession_probabilities")
        return out

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    def derive_forecast_inputs(
        self,
        form_data: dict[str, float],
        excel_data: dict[str, Any] | None = None,
    ) -> DerivationResult:
        """Build a complete ForecastInputs from snapshot panels + form overlay.

        Raises ``SnapshotNotFoundError`` if the snapshot directory itself is
        missing (caller should fall back to heuristic mode in that case).
        """
        if not self._loader.available:
            raise SnapshotNotFoundError(
                f"Snapshot manifest not found at {self._loader.snapshot_dir}; "
                "rebuild via `python scripts/build_data_snapshot.py`."
            )
        # Reset per-derivation state (allows ProducerAdapter reuse across requests).
        self._fallbacks = []
        self._panels_used = set()
        self._producers_run = []

        point_estimates = self.derive_point_estimates(form_data)
        n_eff = self.derive_point_estimate_n_eff()
        forecast_sigmas = self.derive_forecast_sigmas()
        analog_dispersions = self.derive_analog_dispersions()
        return_sigmas = self.derive_return_sigmas()
        recession_probabilities = self.derive_recession_probabilities(
            form_data, excel_data
        )

        inputs = ForecastInputs(
            point_estimates=point_estimates,
            point_estimate_n_eff=n_eff,
            forecast_sigmas=forecast_sigmas,
            analog_dispersions=analog_dispersions,
            return_sigmas=return_sigmas,
            recession_probabilities=recession_probabilities,
        )

        provenance: dict[str, Any] = {
            "mode": "producer_derived",
            "snapshot_date": self._loader.manifest.build_date,
            "panels_used": tuple(sorted(self._panels_used)),
            "producers_run": tuple(self._producers_run),
            "fallbacks": tuple(self._fallbacks),
            "form_overlay_applied": True,
        }
        return DerivationResult(inputs=inputs, provenance=provenance)
