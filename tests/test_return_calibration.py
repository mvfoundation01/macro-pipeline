"""Layer 5-B Task B2 — tests for ``macro_pipeline.models.return_calibration``.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.B.5.B2 (3 v3
tests; B2-1 already in ``tests/test_return_forecast.py`` per Strategic
disposition D-B1-3). The remaining 2 are this file:

  B2-2  POS         test_task_b2_consumes_task_b1_return_forecasts_only
  B2-3  POS-inv     test_task_b2_outputs_positive_return_probability_in_zero_one

Test count = 2. Combined Task B (B1 + B2) NEG = 7 strict (B1) + 1 strict (B2-1)
+ 1 strict-NEG sub-assertion in B2-2 = 9 NEG-flavor of 16 total
(57% >= 50% spec floor).
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from macro_pipeline.analysis.walk_forward_cv import generate_schedule
from macro_pipeline.models.isotonic_calibrator import IsotonicCalibrationResult
from macro_pipeline.models.return_calibration import (
    calibrate_return_forecast_task_b2,
)
from macro_pipeline.models.return_forecast import fit_return_forecast_task_b1


# ---------------------------------------------------------------------------
# B2-2 — POS (with strict-NEG sub-assertions on input validation)
# ---------------------------------------------------------------------------
def test_task_b2_consumes_task_b1_return_forecasts_only():
    """Spec §5.B.5.B2 B2-2: ``calibrate_return_forecast_task_b2`` consumes
    ``return_forecasts_by_horizon`` from ``fit_return_forecast_task_b1``
    output; rejects other inputs."""
    # Build real Task B1 outputs at horizon=5Y.
    rng = np.random.default_rng(42)
    idx = pd.date_range("1985-01-01", periods=480, freq="MS")
    crps_panel = pd.DataFrame(
        {"crps_cal": rng.uniform(0.05, 0.95, 480)}, index=idx,
    )
    cdrs_cols = {
        f"cdrs_h{h}_t{t}": rng.uniform(0.05, 0.95, 480)
        for h in ("1Y", "3Y", "5Y", "10Y")
        for t in (10, 20, 35, 50, 65)
    }
    cdrs_panel = pd.DataFrame(cdrs_cols, index=idx)
    macro = pd.DataFrame(
        {
            "pe_cape": rng.normal(20.0, 5.0, 480),
            "real_rate": rng.normal(2.0, 1.0, 480),
        },
        index=idx,
    )
    fwd = pd.Series(rng.normal(0.07, 0.15, 480), index=idx)

    schedule = generate_schedule(
        horizon="5Y", schedule_type="expanding", panel_index=idx,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        b1_results = fit_return_forecast_task_b1(
            schedule, crps_panel, cdrs_panel, macro, fwd,
            bootstrap_iterations=5,
        )

    # Concatenate Task B1 forecast_test arrays across folds → input to B2.
    return_forecasts = {
        "5Y": np.concatenate([r.forecast_test for r in b1_results])
    }
    n = len(return_forecasts["5Y"])
    forward_returns = {"5Y": rng.normal(0.06, 0.15, n)}
    fit_window = (idx[0], idx[-1])

    # POS leg: consumes Task B1 forecasts → IsotonicCalibrationResult.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cal_results = calibrate_return_forecast_task_b2(
            return_forecasts, forward_returns, fit_window=fit_window,
        )
    assert "5Y" in cal_results
    assert isinstance(cal_results["5Y"], IsotonicCalibrationResult)
    assert cal_results["5Y"].horizon == "5Y"
    assert cal_results["5Y"].n_train_obs == n

    # NEG sub-assertions: rejects malformed inputs per spec contract.
    # (a) Invalid horizon outside §3.3 schema.
    bad_forecasts = {"2Y": return_forecasts["5Y"]}
    bad_actuals = {"2Y": forward_returns["5Y"]}
    with pytest.raises(ValueError, match=r"invalid horizon"):
        calibrate_return_forecast_task_b2(
            bad_forecasts, bad_actuals, fit_window=fit_window,
        )

    # (b) Horizon-set mismatch between the two dicts.
    forecasts_only_5y = {"5Y": return_forecasts["5Y"]}
    actuals_only_3y = {"3Y": forward_returns["5Y"]}
    with pytest.raises(
        ValueError, match=r"missing from forward_returns|missing from return_forecasts",
    ):
        calibrate_return_forecast_task_b2(
            forecasts_only_5y, actuals_only_3y, fit_window=fit_window,
        )

    # (c) Per-horizon length mismatch.
    short_actuals = {"5Y": np.zeros(n - 1)}
    with pytest.raises(ValueError, match=r"length mismatch"):
        calibrate_return_forecast_task_b2(
            return_forecasts, short_actuals, fit_window=fit_window,
        )


# ---------------------------------------------------------------------------
# B2-3 — POS-invariant
# ---------------------------------------------------------------------------
def test_task_b2_outputs_positive_return_probability_in_zero_one():
    """Spec §5.B.5.B2 B2-3: Output ``IsotonicCalibrationResult`` values
    clip to ``[0, 1]``; populates ``positive_return_probability`` slot on
    ``ScoredObservation`` (downstream integration not exercised here —
    the [0, 1] invariant is the testable surface)."""
    rng = np.random.default_rng(7)
    horizons = ("1Y", "3Y", "5Y", "10Y")
    n = 60

    # Synthetic forecasts + actuals across all 4 §3.3 horizons.
    return_forecasts = {h: rng.normal(0.07, 0.10, n) for h in horizons}
    forward_returns = {h: rng.normal(0.06, 0.15, n) for h in horizons}
    fit_window = (pd.Timestamp("2000-01-01"), pd.Timestamp("2020-12-01"))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = calibrate_return_forecast_task_b2(
            return_forecasts, forward_returns, fit_window=fit_window,
        )

    assert set(results.keys()) == set(horizons), (
        f"expected all 4 horizons (n={n} > _MIN_N_TRAIN_OBS=24); "
        f"got {sorted(results.keys())}"
    )

    grid = np.linspace(-0.5, 0.5, 100)
    for h, r in results.items():
        # Sklearn IsotonicRegression with out_of_bounds="clip", y_min=0,
        # y_max=1 is the structural invariant (inherited from
        # isotonic_calibrator._fit_one_calibrator); test verifies the
        # contract holds out-of-band.
        preds = r.sklearn_model.predict(grid)
        assert (preds >= 0.0).all(), (
            f"horizon {h}: prediction < 0 at grid index "
            f"{int(np.argmin(preds))} → {preds.min()}"
        )
        assert (preds <= 1.0).all(), (
            f"horizon {h}: prediction > 1 at grid index "
            f"{int(np.argmax(preds))} → {preds.max()}"
        )
        # Calibrator metadata reflects the [0, 1] clip range.
        assert r.fitted_y_min == 0.0
        assert r.fitted_y_max == 1.0
        # Monotonicity audit inherited from RM-6 should pass.
        assert r.monotonicity_audit == "PASS"
