"""Layer 5-B Task B2 — RETURN_POSITIVE isotonic calibration of Task B1
forecasts.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.B.1.0 (v3 task
split per S-9) + §5.B.1.1 (public API lines 697-722) + §5.B.5.B2 (3
tests; B2-1 promoted into Task B1 per D-B1-3 → 2 here) + §5.B.6
criteria 15-18 + §5.B.7 proof items 10-11.

This sub-phase closes the S-9 unbundling chain (Task A → L5-RM-4 →
L5-RM-6 → Task B1 → **Task B2** terminal) and, with the Gate 19-A/-B1
milestones already shipped, finalises the spec-monolithic Gate 19.

Public API
----------
``calibrate_return_forecast_task_b2``    Task B2's public entry point.

Method (per spec §5.B.1.0 / §5.B.6 criterion 16)
-----------------------------------------------
Internally calls
``isotonic_calibrator.fit_isotonic_calibrators`` with
``score_type="RETURN_POSITIVE"`` (one dispatch per horizon in the input
dict — see "Per-horizon dispatch" rationale below). Each dispatch reuses
the L5-RM-6 calibration machinery (PAV monotonicity audit + B=1000
bootstrap SE distribution + [0, 1] clip via
``IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)``).

Per-horizon dispatch rationale (Strategic D-B2-non-blocking-1, 2026-05-13)
-------------------------------------------------------------------------
``fit_isotonic_calibrators`` requires ``len(raw_scores[(st, h)]) ==
len(panel)`` (see ``isotonic_calibrator._fit_one_calibrator`` lines
288-292). Task B1 produces different-length forecast arrays per horizon
(e.g., 1Y: 337 entries; 5Y: 240 entries; 10Y often empty when the
underpowered-fold guard fires at default ``min_train_window_months=240``,
since ``n_eff = 240 // 120 = 2 < UNDERPOWERED_N_EFF_MIN=3``). A single
batched call across all four horizons therefore cannot satisfy the
length invariant; padded synthetic alignment would degrade the
calibration. Per-horizon iteration is the institutionally correct
choice and still satisfies spec §5.B.6 criterion 16 literal ("Internally
calls ``fit_isotonic_calibrators`` with ``score_type="RETURN_POSITIVE"``")
because every per-horizon dispatch is one such call.

Underpowered-horizon graceful skip (Strategic D-B2-non-blocking-2)
------------------------------------------------------------------
A horizon whose Task B1 output is below ``_MIN_N_TRAIN_OBS = 24`` (the
``UNDERPOWERED_N_NOMINAL_MIN`` floor mirrored from
``analysis.effective_sample_size``) is skipped with a ``UserWarning``;
not raised. Matches the RM-6 + Task B1 robustness pattern. No new Sxx
per AP-AUTH-46 (gratuitous-Sxx guard).

File-location note (Strategic disposition D-B1-1 precedent)
-----------------------------------------------------------
Spec proof contract item 1 references ``macro_pipeline.models.ridge_cv``.
This module lives at ``macro_pipeline.models.return_calibration`` to
continue Task A's (``composite_refit.py``) + Task B1's
(``return_forecast.py``) noun-based naming precedent. Wording drift
tracked in ``L5B_BACKLOG.md`` ``L5b-7``; zero functional impact.
"""
from __future__ import annotations

import warnings
from typing import Mapping

import numpy as np
import pandas as pd

from macro_pipeline.models.isotonic_calibrator import (
    IsotonicCalibrationResult,
    fit_isotonic_calibrators,
)


# Spec §3.3: RETURN_POSITIVE calibrates at 4 horizons.
_VALID_HORIZONS: frozenset[str] = frozenset({"1Y", "3Y", "5Y", "10Y"})

# Per spec §5.B.2 item 4 + isotonic_calibrator._MIN_N_TRAIN_OBS:
# RM-6 enforces a 24-sample floor for any calibrator fit. Task B2 mirrors
# this floor at the horizon level (a horizon with fewer than 24 paired
# samples is skipped with warning rather than fed into RM-6 to raise).
_MIN_N_TRAIN_OBS: int = 24


def calibrate_return_forecast_task_b2(
    return_forecasts_by_horizon: Mapping[str, np.ndarray],
    forward_returns_by_horizon: Mapping[str, np.ndarray],
    *,
    fit_window: tuple[pd.Timestamp, pd.Timestamp],
    random_seed: int = 42,
) -> dict[str, IsotonicCalibrationResult]:
    """Isotonic calibrate Task B1 return forecasts into
    ``positive_return_probability`` per horizon (per spec §5.B.1.1 v3 / S-9).

    Parameters
    ----------
    return_forecasts_by_horizon
        Dict keyed by horizon label (one of ``"1Y" / "3Y" / "5Y" / "10Y"``)
        mapping to a 1-D ``np.ndarray`` of Ridge forecast values produced
        by ``return_forecast.fit_return_forecast_task_b1`` (concatenated
        ``forecast_test`` across folds for the horizon).
    forward_returns_by_horizon
        Dict keyed by the same horizon labels mapping to a 1-D
        ``np.ndarray`` of realised forward real total returns aligned
        element-wise with ``return_forecasts_by_horizon``. The RETURN_POSITIVE
        event label is computed as ``forward_returns > 0``.

    Keyword-only
    ------------
    fit_window
        ``(start, end)`` calendar-time bracket for the calibration fit.
        Stored on each ``IsotonicCalibrationResult`` as metadata; the
        underlying isotonic regression fits on the FULL paired arrays
        supplied (caller is responsible for pre-slicing to fit_window —
        see "Train-only contract" below).
    random_seed
        Determinism control for the per-horizon bootstrap SE
        distribution; default 42.

    Returns
    -------
    dict[str, IsotonicCalibrationResult]
        One result per horizon present in both input dicts with at
        least ``_MIN_N_TRAIN_OBS=24`` paired samples. Horizons below the
        floor are skipped with a ``UserWarning``; missing horizons are
        omitted from the result silently.

    Raises
    ------
    ValueError
        On (a) horizon keys in either dict outside the §3.3 schema
        ``{"1Y","3Y","5Y","10Y"}``, (b) horizon set mismatch between the
        two dicts (a horizon present in forecasts must also be in
        actuals and vice-versa), or (c) per-horizon length mismatch
        between forecasts and actuals.

    Train-only contract
    -------------------
    The isotonic fit uses every observation supplied in
    ``return_forecasts_by_horizon[h]`` / ``forward_returns_by_horizon[h]``;
    ``fit_window`` is recorded as metadata only (see
    ``isotonic_calibrator._fit_one_calibrator`` lines 285+, 318-322).
    Callers MUST pre-slice both arrays to the training window before
    invocation — passing test/OOS data here would leak future
    information into the calibrator. Standing Order #4 universal-claim
    AST audit verifies this at the Task B1 ↔ Task B2 boundary in the
    downstream pipeline.
    """
    # ---- Input validation ----
    forecast_horizons = set(return_forecasts_by_horizon.keys())
    actual_horizons = set(forward_returns_by_horizon.keys())

    invalid_forecast = forecast_horizons - _VALID_HORIZONS
    if invalid_forecast:
        raise ValueError(
            f"return_forecasts_by_horizon has invalid horizon(s) "
            f"{sorted(invalid_forecast)}; must be subset of "
            f"{sorted(_VALID_HORIZONS)} (§3.3 schema)"
        )
    invalid_actual = actual_horizons - _VALID_HORIZONS
    if invalid_actual:
        raise ValueError(
            f"forward_returns_by_horizon has invalid horizon(s) "
            f"{sorted(invalid_actual)}; must be subset of "
            f"{sorted(_VALID_HORIZONS)} (§3.3 schema)"
        )

    only_forecast = forecast_horizons - actual_horizons
    only_actual = actual_horizons - forecast_horizons
    if only_forecast:
        raise ValueError(
            f"horizon(s) {sorted(only_forecast)} present in "
            "return_forecasts_by_horizon but missing from "
            "forward_returns_by_horizon"
        )
    if only_actual:
        raise ValueError(
            f"horizon(s) {sorted(only_actual)} present in "
            "forward_returns_by_horizon but missing from "
            "return_forecasts_by_horizon"
        )

    for h in sorted(forecast_horizons):
        n_forecast = len(return_forecasts_by_horizon[h])
        n_actual = len(forward_returns_by_horizon[h])
        if n_forecast != n_actual:
            raise ValueError(
                f"horizon {h!r}: length mismatch "
                f"(return_forecasts={n_forecast}, "
                f"forward_returns={n_actual}); each pair must align "
                "element-wise per spec §5.B.1.1"
            )

    # ---- Per-horizon dispatch (D-B2-non-blocking-1 approved 2026-05-13) ----
    results: dict[str, IsotonicCalibrationResult] = {}

    for h in sorted(forecast_horizons):
        forecasts = np.asarray(return_forecasts_by_horizon[h], dtype=float)
        actuals = np.asarray(forward_returns_by_horizon[h], dtype=float)
        n_obs = len(forecasts)

        if n_obs < _MIN_N_TRAIN_OBS:
            warnings.warn(
                f"Skipping RETURN_POSITIVE calibration for horizon={h!r}: "
                f"n_obs={n_obs} < _MIN_N_TRAIN_OBS={_MIN_N_TRAIN_OBS} "
                "(spec §5.B.2 item 4 mirror; AP-AUTH-46 graceful skip)",
                stacklevel=2,
            )
            continue

        # Horizon-local single-column panel matching the
        # _forward_real_return_gt_zero_h contract at
        # isotonic_calibrator.py:117-131 (column = forward_real_return_{horizon}).
        # L5b-KICK-1 (Strategic-approved Approach B 2026-05-13): synthesise a
        # monthly DatetimeIndex starting at fit_window[0] so the panel
        # satisfies the fit_window train-only invariant enforced inside
        # _fit_one_calibrator. Defensive guard surfaces caller error if
        # fit_window is too narrow for the observation count.
        synthetic_index = pd.date_range(
            start=fit_window[0], periods=len(actuals), freq="MS",
        )
        if synthetic_index[-1] > fit_window[1]:
            raise ValueError(
                f"Task B2 fit_window {fit_window} is too narrow for "
                f"{len(actuals)} observations at monthly cadence "
                f"(synthesised index would extend to "
                f"{synthetic_index[-1].date()})"
            )
        panel = pd.DataFrame(
            {f"forward_real_return_{h}": actuals},
            index=synthetic_index,
        )

        # Single-entry raw_scores dict; satisfies spec §5.B.6 criterion 16
        # literal "Internally calls fit_isotonic_calibrators with
        # score_type='RETURN_POSITIVE'" — once per horizon.
        raw_scores = {("RETURN_POSITIVE", h): forecasts}

        cal_dict = fit_isotonic_calibrators(
            raw_scores=raw_scores,
            panel=panel,
            fit_window=fit_window,
            random_seed=random_seed,
        )

        # fit_isotonic_calibrators keys are 3-tuples
        # (score_type, horizon, drawdown_threshold); RETURN_POSITIVE has
        # threshold=None per isotonic_calibrator.py:443-456.
        results[h] = cal_dict[("RETURN_POSITIVE", h, None)]

    return results


__all__ = [
    "calibrate_return_forecast_task_b2",
]
