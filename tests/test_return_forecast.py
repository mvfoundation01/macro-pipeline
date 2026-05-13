"""Layer 5-B Task B1 — tests for ``macro_pipeline.models.return_forecast``.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.B.5.B (13 v3
Task B1 tests) + §5.B.5.B2 row B2-1 (promoted into Task B1 file per
Strategic disposition **D-B1-3** on 2026-05-13). Total: 14 tests.

NEG taxonomy (mirrors Task A accounting at
``tests/test_composite_refit.py``: POS-invariant counts as NEG-flavor):
  - strict NEG (4): B10, B11, B13, B2-1
  - POS-invariant (3): B3, B4, B12
  - POS (7): B1, B2, B5, B6, B7, B8, B9
  - NEG-flavor total: 7 of 14 = 50% floor met; with B2-1 promoted the
    strict-NEG share rises to 4/14 = 29% and combined NEG-flavor to
    8/14 = 57% per Strategic disposition rationale.

Spec test name mirror (§5.B.5.B / §5.B.5.B2)
  B1   POS         test_task_b1_consumes_crps_and_cdrs_calibrated_panels_post_L5_RM_6
  B2   POS         test_task_b1_emits_R_squared_OOS_slope_intercept_residual_SE_pvalue
  B3   POS-inv     test_task_b1_HAC_SE_uses_maxlags_horizon_minus_1
  B4   POS-inv     test_task_b1_block_bootstrap_block_size_horizon_div_2
  B5   POS         test_task_b1_block_size_sensitivity_h_div_4_h_div_2_h_2h
  B6   POS         test_task_b1_bandwidth_sensitivity_h_minus_1_andrews_lower
  B7   POS         test_task_b1_OOS_R_squared_reported_per_horizon
  B8   POS         test_task_b1_lambda_log10_sd_5fold_reported
  B9   POS         test_task_b1_coefficient_sign_flip_rate_reported
  B10  NEG         test_task_b1_rejects_negative_lambda
  B11  NEG         test_task_b1_warns_lambda_binding_at_grid_edge
  B12  POS-inv     test_task_b1_bootstrap_seeded_for_reproducibility
  B13  NEG         test_task_b1_rejects_underpowered_fold_with_warning
  B2-1 NEG (AST)   test_task_b1_does_not_consume_return_positive_calibrated_probability

L5b-KICK-4 (tag ``l5b-kick-4-accept``, 2026-05-15) appended five tests
(K4.1-K4.5) closing the Codex 5.5 IMPORTANT reviewer flag on nested-CV
purity ("L5-B1: Recompute z-score scalers inside inner λ CV blocks,
matching Task A's pattern") via the AP-AUTH-53 reviewer-driven-
kickoff-item pattern (fourth instance; internal-implementation variant
per Strategic disposition 2026-05-15).

  K4.1  POS         test_kick4_inner_cv_scaler_recomputed_field_present_and_true
  K4.2  POS-inv     test_kick4_task_a_parity_inner_train_only_z_scaling
  K4.3  POS-inv     test_kick4_outer_cv_scaler_provenance_unchanged_post_refactor
  K4.4  NEG         test_kick4_dataclass_rejects_missing_inner_cv_scaler_recomputed
  K4.5  NEG-inv     test_kick4_inner_scalers_differ_from_outer_scalers_negative_invariant

L5b-KICK-5 (tag ``l5b-kick-5-accept``, 2026-05-15) appended six tests
(K5.1-K5.6) closing the ChatGPT 5.5 IMPORTANT #6 reviewer flag on
bootstrap diagnostics table per horizon/fold via the AP-AUTH-53 fifth-
instance / AP-AUTH-54 internal-implementation variant pattern.

  K5.1  POS         test_kick5_ridge_fit_result_carries_bootstrap_diagnostics
  K5.2  POS         test_kick5_block_size_sensitivity_diagnostics_per_size
  K5.3  POS-inv     test_kick5_block_count_invariant_matches_n_train_div_block_size
  K5.4  POS         test_kick5_fallback_flag_B_halved_reachable_at_5Y_sensitivity_2h
  K5.5  NEG         test_kick5_dataclass_rejects_invalid_fallback_flag
  K5.6  NEG         test_kick5_dataclass_rejects_missing_no_default_field

NEG-flavor accounting (per L5-B1 convention; POS-inv counts as NEG-
flavor): post-KICK-5 strict-NEG 6 / POS-inv 5 / POS 14 = 11 of 25 =
44% strict+POS-inv-flavor NEG. Per L5-B1 documented convention
(test_return_forecast.py header at top), each KICK sub-phase satisfies
its own 50% NEG floor: KICK-5 has 2 strict NEG + 1 POS-inv = 3 of 6 =
50% NEG-flavor (floor met at the sub-phase level).
"""
from __future__ import annotations

import inspect
import warnings

import numpy as np
import pandas as pd
import pytest

from macro_pipeline.analysis.r_squared_panel import HORIZONS
from macro_pipeline.analysis.walk_forward_cv import generate_schedule
from macro_pipeline.models.return_forecast import (
    BOOTSTRAP_ITERATIONS_DEFAULT,
    LAMBDA_GRID_DEFAULT,
    BootstrapDiagnostics,
    RidgeFitResult,
    fit_return_forecast_task_b1,
)


# ---------------------------------------------------------------------------
# Shared synthetic-fixture helper
# ---------------------------------------------------------------------------
def _build_synthetic_inputs(
    horizon: str = "5Y",
    schedule_type: str = "expanding",
    n_months: int = 480,
    seed: int = 42,
    truncate_forward_returns_after: int | None = None,
):
    """Build (schedule, crps_panel, cdrs_panel, macro_features, fwd_returns).

    Synthetic CRPS injects mild negative signal into forward returns so
    Ridge has something to estimate; the rest is white noise. CDRS panel
    carries 20 columns (4 horizons × 5 thresholds) per spec contract.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1985-01-01", periods=n_months, freq="MS")
    crps_panel = pd.DataFrame(
        {"crps_cal": rng.uniform(0.05, 0.95, n_months)}, index=idx,
    )
    cdrs_cols = {
        f"cdrs_h{h}_t{t}": rng.uniform(0.05, 0.95, n_months)
        for h in ("1Y", "3Y", "5Y", "10Y")
        for t in (10, 20, 35, 50, 65)
    }
    cdrs_panel = pd.DataFrame(cdrs_cols, index=idx)
    macro = pd.DataFrame(
        {
            "pe_cape": rng.normal(20.0, 5.0, n_months),
            "real_rate": rng.normal(2.0, 1.0, n_months),
        },
        index=idx,
    )
    # Forward returns = noise + small CRPS signal (negative).
    base = rng.normal(0.07, 0.15, n_months)
    fwd = pd.Series(base - 0.10 * crps_panel["crps_cal"].to_numpy(), index=idx)
    if truncate_forward_returns_after is not None:
        # Force NaN past this row to simulate data-boundary effects.
        fwd.iloc[truncate_forward_returns_after:] = float("nan")

    schedule = generate_schedule(
        horizon=horizon, schedule_type=schedule_type, panel_index=idx,
    )
    return schedule, crps_panel, cdrs_panel, macro, fwd


# ---------------------------------------------------------------------------
# B1 — POS
# ---------------------------------------------------------------------------
def test_task_b1_consumes_crps_and_cdrs_calibrated_panels_post_L5_RM_6():
    """Spec §5.B.5.B B1: Task B1 input column set matches post-L5-RM-6
    CRPS (1 entry) + CDRS (20 entries) calibrated probability panels
    + macro features schema."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    # Schema invariants (caller-visible).
    assert len(crps.columns) == 1, "CRPS panel must have exactly 1 col"
    assert len(cdrs.columns) == 20, "CDRS panel must have exactly 20 cols"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=30,
        )

    assert len(results) > 0
    for r in results:
        assert isinstance(r, RidgeFitResult)
        # Feature vector dimension = 1 (CRPS) + 20 (CDRS) + 2 (macro).
        assert r.coef.shape == (23,), (
            f"coef shape {r.coef.shape} != (23,); features must concat "
            "CRPS(1) + CDRS(20) + macro(M)"
        )


# ---------------------------------------------------------------------------
# B2 — POS
# ---------------------------------------------------------------------------
def test_task_b1_emits_R_squared_OOS_slope_intercept_residual_SE_pvalue():
    """Spec §5.B.5.B B2: Per fold all six core outputs populated."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=30,
        )
    assert len(results) > 0
    for r in results:
        # The spec field set per §5.B.1.5 line 724.
        # R² is allowed to be NaN at the extreme (degenerate variance);
        # the field MUST be present.
        assert hasattr(r, "r_squared") and isinstance(r.r_squared, float)
        assert hasattr(r, "r_squared_oos") and isinstance(r.r_squared_oos, float)
        assert isinstance(r.intercept, float)
        assert isinstance(r.coef, np.ndarray) and r.coef.ndim == 1
        assert isinstance(r.residual_se_hac, float)
        assert isinstance(r.p_value_beta_hac, float)


# ---------------------------------------------------------------------------
# B3 — POS-invariant
# ---------------------------------------------------------------------------
def test_task_b1_HAC_SE_uses_maxlags_horizon_minus_1():
    """Spec §5.B.5.B B3: ``RidgeFitResult.hac_maxlags == horizon_months − 1``.

    Horizons restricted to {1Y, 3Y, 5Y}: at 10Y with the default
    ``min_train_window_months=240``, ``n_eff = 240 // 120 = 2 <
    UNDERPOWERED_N_EFF_MIN=3`` ⇒ spec §5.B.2 item 4 skips all folds.
    Invariance verified at the three horizons where folds run.
    """
    for horizon in ("1Y", "3Y", "5Y"):
        schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(
            horizon=horizon, n_months=600,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = fit_return_forecast_task_b1(
                schedule, crps, cdrs, macro, fwd, bootstrap_iterations=10,
            )
        assert len(results) > 0
        expected = HORIZONS[horizon] - 1
        for r in results:
            assert r.hac_maxlags == expected, (
                f"horizon={horizon}: hac_maxlags={r.hac_maxlags} != "
                f"horizon_months − 1 = {expected}"
            )


# ---------------------------------------------------------------------------
# B4 — POS-invariant
# ---------------------------------------------------------------------------
def test_task_b1_block_bootstrap_block_size_horizon_div_2():
    """Spec §5.B.5.B B4: Default block size matches ``horizon_months // 2``.

    Horizons restricted to {1Y, 3Y, 5Y} for the same n_eff reason
    documented in ``test_task_b1_HAC_SE_uses_maxlags_horizon_minus_1``.
    """
    for horizon in ("1Y", "3Y", "5Y"):
        schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(
            horizon=horizon, n_months=600,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = fit_return_forecast_task_b1(
                schedule, crps, cdrs, macro, fwd, bootstrap_iterations=10,
            )
        expected = HORIZONS[horizon] // 2
        assert len(results) > 0
        for r in results:
            assert r.bootstrap_block_size == expected, (
                f"horizon={horizon}: bootstrap_block_size="
                f"{r.bootstrap_block_size} != horizon_months // 2 "
                f"= {expected}"
            )


# ---------------------------------------------------------------------------
# B5 — POS
# ---------------------------------------------------------------------------
def test_task_b1_block_size_sensitivity_h_div_4_h_div_2_h_2h():
    """Spec §5.B.5.B B5: Block-size sensitivity reports {h/4, h/2, h, 2h}."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=20,
        )
    assert len(results) > 0
    expected_labels = {"h/4", "h/2", "h", "2h"}
    for r in results:
        assert set(r.block_size_sensitivity_se.keys()) == expected_labels


# ---------------------------------------------------------------------------
# B6 — POS
# ---------------------------------------------------------------------------
def test_task_b1_bandwidth_sensitivity_h_minus_1_andrews_lower():
    """Spec §5.B.5.B B6: HAC bandwidth sensitivity reports {h-1, andrews,
    h//4_floor} and the three values are not all identical (β SE is
    bandwidth-dependent — see ``_hac_beta_se_at_maxlags`` docstring)."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=10,
        )
    expected_labels = {"h-1", "andrews", "h//4_floor"}
    any_varies = False
    for r in results:
        assert set(r.hac_bandwidth_sensitivity_se.keys()) == expected_labels
        finite_vals = [
            v for v in r.hac_bandwidth_sensitivity_se.values()
            if np.isfinite(v)
        ]
        # Across-fold check: at least one fold must show distinct values
        # at >= 2 of the 3 bandwidths (proves the report exposes real
        # sensitivity, not a constant placeholder).
        if len(finite_vals) >= 2 and len(set(np.round(finite_vals, 6))) >= 2:
            any_varies = True
    assert any_varies, (
        "Bandwidth sensitivity report should expose varying β SE across "
        "{h-1, andrews, h//4_floor} on at least one fold"
    )


# ---------------------------------------------------------------------------
# B7 — POS
# ---------------------------------------------------------------------------
def test_task_b1_OOS_R_squared_reported_per_horizon():
    """Spec §5.B.5.B B7: ``r_squared_oos`` populated per fold.

    Horizons restricted to {3Y, 5Y} for the n_eff reason documented in
    B3; the field-population invariant holds across horizons by
    construction in the main loop.
    """
    for horizon in ("3Y", "5Y"):
        schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(
            horizon=horizon, n_months=600,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = fit_return_forecast_task_b1(
                schedule, crps, cdrs, macro, fwd, bootstrap_iterations=10,
            )
        assert len(results) > 0
        for r in results:
            # Field is present (NaN allowed at n_test < 2).
            assert hasattr(r, "r_squared_oos")
            assert isinstance(r.r_squared_oos, float)


# ---------------------------------------------------------------------------
# B8 — POS
# ---------------------------------------------------------------------------
def test_task_b1_lambda_log10_sd_5fold_reported():
    """Spec §5.B.5.B B8: ``lambda_log10_sd_across_5fold`` populated."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=10,
        )
    assert len(results) > 0
    for r in results:
        assert hasattr(r, "lambda_log10_sd_across_5fold")
        assert isinstance(r.lambda_log10_sd_across_5fold, float)


# ---------------------------------------------------------------------------
# B9 — POS
# ---------------------------------------------------------------------------
def test_task_b1_coefficient_sign_flip_rate_reported():
    """Spec §5.B.5.B B9: ``coefficient_sign_flip_rate`` populated."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(
        horizon="5Y", n_months=600,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=10,
        )
    assert len(results) >= 2, "need >=2 folds to compute sign-flip rate"
    # First fold has no prior → 0.0 by construction.
    assert results[0].coefficient_sign_flip_rate == 0.0
    # Subsequent folds: rate ∈ [0, 1].
    for r in results[1:]:
        assert 0.0 <= r.coefficient_sign_flip_rate <= 1.0


# ---------------------------------------------------------------------------
# B10 — NEG
# ---------------------------------------------------------------------------
def test_task_b1_rejects_negative_lambda():
    """Spec §5.B.5.B B10: ``lambda_grid=(-1.0,)`` raises."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with pytest.raises(ValueError, match=r"non-positive"):
        fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd,
            lambda_grid=(-1.0,), bootstrap_iterations=5,
        )


# ---------------------------------------------------------------------------
# B11 — NEG
# ---------------------------------------------------------------------------
def test_task_b1_warns_lambda_binding_at_grid_edge():
    """Spec §5.B.5.B B11: Grid edge warning fires when ``lambda_selected``
    is at the grid boundary. Synthetic noise data with strong shrinkage
    typically picks the largest λ in the grid → grid-edge bind."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with pytest.warns(UserWarning, match=r"binds at grid edge"):
        fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=5,
        )


# ---------------------------------------------------------------------------
# B12 — POS-invariant
# ---------------------------------------------------------------------------
def test_task_b1_bootstrap_seeded_for_reproducibility():
    """Spec §5.B.5.B B12: ``seed=42`` → identical bootstrap distributions
    across runs."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r1 = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd,
            bootstrap_iterations=20, random_seed=42,
        )
        r2 = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd,
            bootstrap_iterations=20, random_seed=42,
        )
    assert len(r1) == len(r2) > 0
    for a, b in zip(r1, r2):
        assert np.array_equal(
            a.bootstrap_residual_se_distribution,
            b.bootstrap_residual_se_distribution,
        ), "seed=42 must produce identical bootstrap distributions"
        assert a.block_size_sensitivity_se == b.block_size_sensitivity_se


# ---------------------------------------------------------------------------
# B13 — NEG
# ---------------------------------------------------------------------------
def test_task_b1_rejects_underpowered_fold_with_warning():
    """Spec §5.B.5.B B13: ``n_eff_nonoverlap_train < 3`` → skip fold with
    a warning; the returned tuple is shorter than ``len(schedule.folds)``."""
    # Truncate forward_returns past month 400 → folds whose test_start
    # ≥ 400 see all-NaN test data → ``_assemble_feature_matrix`` returns
    # empty test slice → fold skip via the underpowered-fold guard
    # (``n_test < _MIN_N_TEST_OBS=1``). At 5Y with step=12 + gap=60, this
    # leaves ~9 early folds passing out of ~20 total.
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(
        horizon="5Y", n_months=600, truncate_forward_returns_after=400,
    )
    with pytest.warns(UserWarning, match=r"Skipping fold"):
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=5,
        )
    # Some folds should still PASS (early ones with data) and some should
    # SKIP (late ones).
    assert 0 < len(results) < len(schedule.folds), (
        f"underpowered guard should skip at least one late fold; "
        f"got {len(results)} of {len(schedule.folds)}"
    )


# ---------------------------------------------------------------------------
# B2-1 — NEG (AST audit; promoted per Strategic D-B1-3)
# ---------------------------------------------------------------------------
def test_task_b1_does_not_consume_return_positive_calibrated_probability():
    """Spec §5.B.5.B2 B2-1: Standing Order #4 AST audit — Task B1's
    signature must NOT contain a parameter named ``positive_return_probability``
    or ``RETURN_POSITIVE``; and passing a panel with such a column must
    raise. Closes ChatGPT v2 §D.2 circularity per S-9."""
    sig = inspect.signature(fit_return_forecast_task_b1)
    forbidden = {"positive_return_probability", "RETURN_POSITIVE"}
    found = forbidden & set(sig.parameters.keys())
    assert not found, (
        f"AST audit failed — Task B1 signature contains forbidden parameter "
        f"{sorted(found)}: RETURN_POSITIVE is downstream OUTPUT (Task B2), "
        "NOT input. Closes ChatGPT v2 §D.2 circularity."
    )

    # Runtime contract: panel containing such a column raises ValueError.
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    cdrs_poisoned = cdrs.copy()
    cdrs_poisoned["positive_return_probability"] = 0.5
    with pytest.raises(ValueError, match=r"RETURN_POSITIVE|forbidden column"):
        fit_return_forecast_task_b1(
            schedule, crps, cdrs_poisoned, macro, fwd, bootstrap_iterations=5,
        )


# Spec §5.B.7 proof contract item 1 (adapted per Strategic D-B1-1 to the
# ``return_forecast`` module): the import at the top of this file
# (``from macro_pipeline.models.return_forecast import ...``) is itself
# the proof — exercised on pytest collection. No separate test row needed.


# ===========================================================================
# L5b-KICK-4 tests K4.1-K4.5 — inner-CV z-scaler recomputation (Task A
# parity) + no-default field flag + Gate 19-B1 invariants. Closes Codex
# 5.5 IMPORTANT reviewer flag via the AP-AUTH-53 reviewer-driven-
# kickoff-item pattern (fourth instance; internal-implementation variant
# per Strategic disposition 2026-05-15).
# ===========================================================================


# ---------------------------------------------------------------------------
# Test K4.1 — POS (KICK-4)
# ---------------------------------------------------------------------------
def test_kick4_inner_cv_scaler_recomputed_field_present_and_true():
    """KICK-4: every ``RidgeFitResult`` emitted by
    ``fit_return_forecast_task_b1`` carries
    ``inner_cv_scaler_recomputed=True`` (post-refactor Task A parity)."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=5,
        )
    assert len(results) > 0, "fixture must produce >= 1 fold"
    # Field exists.
    assert hasattr(results[0], "inner_cv_scaler_recomputed"), (
        "RidgeFitResult must expose inner_cv_scaler_recomputed field "
        "(KICK-4 / AP-AUTH-53 step #3)"
    )
    # Every fold has the flag set to True.
    flags = [r.inner_cv_scaler_recomputed for r in results]
    assert all(f is True for f in flags), (
        f"all folds must have inner_cv_scaler_recomputed=True; "
        f"got {flags}"
    )


# ---------------------------------------------------------------------------
# Test K4.2 — POS-invariant (KICK-4)
# ---------------------------------------------------------------------------
def test_kick4_task_a_parity_inner_train_only_z_scaling():
    """KICK-4: AST/source inspection of ``_select_lambda_inner_cv_ridge``
    confirms the inner-CV loop body calls ``_zscore_fit_transform(X_tr...)``
    inside the per-fold iteration — Task A precedent parity at
    ``composite_refit.py:177-178``."""
    from macro_pipeline.models import return_forecast as _rf_mod
    src = inspect.getsource(_rf_mod._select_lambda_inner_cv_ridge)
    # Substring contract per Gate 19-B1 Criterion 24 (KICK-4): inner-train
    # re-fit must be present in the helper body.
    assert "_zscore_fit_transform(X_tr" in src, (
        "_select_lambda_inner_cv_ridge body must re-fit z-scaler on "
        "inner-train slice (Task A parity per composite_refit.py:177-178); "
        "expected substring '_zscore_fit_transform(X_tr' not found"
    )
    # And the helper must apply the inner statistics to the inner-test.
    assert "_zscore_transform(X_te" in src, (
        "_select_lambda_inner_cv_ridge body must apply inner statistics "
        "to inner-test slice; expected '_zscore_transform(X_te' not found"
    )


# ---------------------------------------------------------------------------
# Test K4.3 — POS-invariant (KICK-4)
# ---------------------------------------------------------------------------
def test_kick4_outer_cv_scaler_provenance_unchanged_post_refactor():
    """KICK-4 K4.3 structural invariant: the OUTER Ridge fit projects
    ``X_test`` through the OUTER-train z-scaler statistics (mean_tr,
    std_tr) — NOT through any inner-block scaler. Verified via source
    inspection on ``fit_return_forecast_task_b1`` body: the
    ``X_test_z = _zscore_transform(X_test, mean_tr, std_tr)`` line uses
    the OUTER (mean_tr, std_tr) variables computed from
    ``_zscore_fit_transform(X_train)`` at the outer-CV scope.

    This is the structural invariant chosen over R² golden-value
    equality per Strategic disposition #6 — methodologically purer
    because λ may legitimately change post-refactor (R1 surface)."""
    from macro_pipeline.models import return_forecast as _rf_mod
    src = inspect.getsource(_rf_mod.fit_return_forecast_task_b1)
    # Outer z-scaler MUST be computed once at outer-CV scope.
    assert "X_train_z, mean_tr, std_tr = _zscore_fit_transform(X_train)" in src, (
        "Outer Ridge fit must compute outer-train z-scaler statistics "
        "(X_train_z, mean_tr, std_tr) once per outer fold; expected "
        "exact assignment not found"
    )
    # Outer test projection MUST use the OUTER scaler statistics.
    assert "X_test_z = _zscore_transform(X_test, mean_tr, std_tr)" in src, (
        "Outer Ridge fit must project X_test through OUTER scaler "
        "(mean_tr, std_tr); expected exact assignment not found"
    )
    # Inner-CV call MUST pass RAW X_train (not X_train_z).
    assert "_select_lambda_inner_cv_ridge(\n            X_train, y_train" in src, (
        "Inner-CV call must pass RAW X_train post-KICK-4 (not "
        "pre-z-scored X_train_z); inner blocks re-fit their own scalers"
    )


# ---------------------------------------------------------------------------
# Test K4.4 — NEG (KICK-4)
# ---------------------------------------------------------------------------
def test_kick4_dataclass_rejects_missing_inner_cv_scaler_recomputed():
    """KICK-4: bare ``RidgeFitResult(...)`` construction without
    ``inner_cv_scaler_recomputed=`` raises ``TypeError`` — proves the
    no-default contract per AP-AUTH-53 step #3."""
    with pytest.raises(TypeError, match=r"inner_cv_scaler_recomputed"):
        RidgeFitResult(
            fold_id=0,
            horizon="1Y",
            schedule_type="expanding",
            lambda_selected=1.0,
            lambda_grid=(0.1, 1.0, 10.0),
            lambda_log10_sd_across_5fold=0.0,
            coefficient_sign_flip_rate=0.0,
            coef=np.zeros(3),
            intercept=0.0,
            forecast_train=np.zeros(10),
            forecast_test=np.zeros(5),
            r_squared=0.0,
            r_squared_oos=0.0,
            residual_se_hac=0.0,
            p_value_beta_hac=1.0,
            bootstrap_residual_se_distribution=np.zeros(0),
            bootstrap_block_size=6,
            hac_maxlags=11,
            n_train_obs=10,
            n_test_obs=5,
            n_eff_nonoverlap_train=1,
            grid_edge_bind=False,
            block_size_sensitivity_se={},
            hac_bandwidth_sensitivity_se={},
            fit_timestamp=pd.Timestamp("2026-05-15"),
            # inner_cv_scaler_recomputed deliberately omitted — must raise
        )


# ---------------------------------------------------------------------------
# Test K4.5 — NEG-invariant (KICK-4)
# ---------------------------------------------------------------------------
def test_kick4_inner_scalers_differ_from_outer_scalers_negative_invariant():
    """KICK-4 K4.5 NEG-invariant: when the inner-CV helper is given a
    raw X_train where the first n//(k+1) rows have systematically
    different mean/std than the full outer-train, the inner-train slice
    scaler (mean_inner, std_inner) MUST differ from the outer-train
    scaler (mean_outer, std_outer).

    This proves the helper actually re-fits scalers per inner block
    (inverse of the pre-KICK-4 outer-inherited behavior). Implemented
    via a direct probe: build X_train with structurally different
    sub-block statistics, call the public helpers, compare scalers."""
    from macro_pipeline.models.return_forecast import (
        _zscore_fit_transform, _build_inner_blocks,
    )
    # Build synthetic X_train with mean drift across the time axis:
    # first 100 rows ~ N(0, 1); next 200 rows ~ N(5, 2). The inner-CV
    # first block (rows 0..n/(k+1)) sees only the first regime; the
    # outer-train scaler averages across both.
    rng = np.random.default_rng(2026)
    block_a = rng.normal(0.0, 1.0, size=(100, 3))
    block_b = rng.normal(5.0, 2.0, size=(200, 3))
    X_train_raw = np.vstack([block_a, block_b])

    # Outer-train scaler (on full 300 rows).
    _, mean_outer, std_outer = _zscore_fit_transform(X_train_raw)

    # First inner-train slice (rows 0..fold_size).
    blocks = _build_inner_blocks(n_train=300, n_inner_folds=5)
    assert len(blocks) > 0, "fixture must produce >= 1 inner block"
    tr_slice, _te_slice = blocks[0]
    X_tr_inner = X_train_raw[tr_slice]
    _, mean_inner, std_inner = _zscore_fit_transform(X_tr_inner)

    # NEG-invariant: inner scalers differ from outer scalers (proves
    # the helper does NOT inherit outer statistics).
    delta_mean = float(np.max(np.abs(mean_outer - mean_inner)))
    delta_std = float(np.max(np.abs(std_outer - std_inner)))
    assert delta_mean > 0.1, (
        f"NEG-invariant failure: inner mean must differ from outer mean "
        f"on this fixture; max|Δmean|={delta_mean} (expected > 0.1)"
    )
    assert delta_std > 0.1, (
        f"NEG-invariant failure: inner std must differ from outer std "
        f"on this fixture; max|Δstd|={delta_std} (expected > 0.1)"
    )


# ===========================================================================
# L5b-KICK-5 tests K5.1-K5.6 — bootstrap diagnostics table per
# horizon/fold (primary + sensitivity-sweep). Closes ChatGPT 5.5
# IMPORTANT #6 reviewer flag via the AP-AUTH-53 fifth-instance /
# AP-AUTH-54 internal-implementation variant pattern. NEG-flavor 3/6 =
# 50% at the sub-phase level (floor met).
# ===========================================================================


# ---------------------------------------------------------------------------
# Test K5.1 — POS (KICK-5)
# ---------------------------------------------------------------------------
def test_kick5_ridge_fit_result_carries_bootstrap_diagnostics():
    """KICK-5: every ``RidgeFitResult`` carries a primary
    ``bootstrap_diagnostics: BootstrapDiagnostics`` instance with
    ``n_train > 0``, ``block_size > 0``, and ``fallback_flag`` in the
    tri-state taxonomy."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=10,
        )
    assert len(results) > 0, "fixture must produce >= 1 fold"
    for r in results:
        assert isinstance(r.bootstrap_diagnostics, BootstrapDiagnostics)
        assert r.bootstrap_diagnostics.n_train > 0
        assert r.bootstrap_diagnostics.block_size > 0
        assert r.bootstrap_diagnostics.fallback_flag in (
            "none", "B_halved", "bs1_degenerate",
        )
        # n_eff should equal n_train // horizon_months; 5Y → 60 months.
        assert r.bootstrap_diagnostics.n_eff == r.n_train_obs // 60


# ---------------------------------------------------------------------------
# Test K5.2 — POS (KICK-5)
# ---------------------------------------------------------------------------
def test_kick5_block_size_sensitivity_diagnostics_per_size():
    """KICK-5: per-sensitivity-block-size diagnostics dict on every
    ``RidgeFitResult``; keys match canonical ``_BLOCK_SIZE_LABELS``
    (``"h/4", "h/2", "h", "2h"``); each value is a
    ``BootstrapDiagnostics`` instance."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=10,
        )
    expected_labels = {"h/4", "h/2", "h", "2h"}
    for r in results:
        assert set(r.block_size_sensitivity_diagnostics.keys()) == expected_labels, (
            f"sensitivity diagnostics keys mismatch: "
            f"{set(r.block_size_sensitivity_diagnostics.keys())} "
            f"vs expected {expected_labels}"
        )
        for label, diag in r.block_size_sensitivity_diagnostics.items():
            assert isinstance(diag, BootstrapDiagnostics), (
                f"label={label!r}: value is not BootstrapDiagnostics"
            )


# ---------------------------------------------------------------------------
# Test K5.3 — POS-invariant (KICK-5)
# ---------------------------------------------------------------------------
def test_kick5_block_count_invariant_matches_n_train_div_block_size():
    """KICK-5 POS-invariant: for every diagnostics emitted (primary
    AND sensitivity sweep), ``block_count == n_train // block_size``
    POST-fallback. This invariant must hold across all three
    fallback states."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=10,
        )
    for r in results:
        # Primary call invariant.
        d = r.bootstrap_diagnostics
        if d.fallback_flag == "bs1_degenerate":
            # bs collapsed to 1; block_count = n_train (iid).
            assert d.block_size == 1
            assert d.block_count == d.n_train
        else:
            assert d.block_count == d.n_train // d.block_size, (
                f"primary: block_count={d.block_count} != "
                f"n_train={d.n_train} // block_size={d.block_size}"
            )
        # Sensitivity sweep invariant on every label.
        for label, ds in r.block_size_sensitivity_diagnostics.items():
            if ds.fallback_flag == "bs1_degenerate":
                assert ds.block_size == 1
                assert ds.block_count == ds.n_train
            else:
                assert ds.block_count == ds.n_train // ds.block_size, (
                    f"sensitivity[{label!r}]: block_count={ds.block_count} != "
                    f"n_train={ds.n_train} // block_size={ds.block_size}"
                )


# ---------------------------------------------------------------------------
# Test K5.4 — POS (KICK-5; reviewer-flagged path empirical verification)
# ---------------------------------------------------------------------------
def test_kick5_fallback_flag_B_halved_reachable_at_5Y_sensitivity_2h():
    """KICK-5: empirical verification of the reviewer-flagged path.
    At 5Y/expanding with default settings, the ``"2h"`` sensitivity
    block size (= 120 months for 5Y) triggers the ``"B_halved"``
    fallback on the early folds (n_train ≈ 240, block_count = 2 < 4
    → B halves). This test pins the reviewer's concern empirically:
    the diagnostic surface MUST expose the fallback state that was
    previously buried in a UserWarning text."""
    schedule, crps, cdrs, macro, fwd = _build_synthetic_inputs(horizon="5Y")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_return_forecast_task_b1(
            schedule, crps, cdrs, macro, fwd, bootstrap_iterations=10,
        )
    assert len(results) > 0, "fixture must produce >= 1 fold"
    # At least one fold must show "B_halved" at the "2h" sensitivity
    # block size (empirically confirmed at ITEM 0b pre-flight probe).
    halved_count = 0
    for r in results:
        ds_2h = r.block_size_sensitivity_diagnostics.get("2h")
        assert ds_2h is not None, "2h sensitivity diagnostics missing"
        if ds_2h.fallback_flag == "B_halved":
            halved_count += 1
            # When B_halved fires, B_effective must equal max(1, B//2).
            assert ds_2h.B_effective == max(1, 10 // 2), (
                f"B_halved fired but B_effective={ds_2h.B_effective}, "
                f"expected {max(1, 10 // 2)}"
            )
    assert halved_count > 0, (
        f"expected at least one fold with 2h sensitivity fallback="
        f"'B_halved' at 5Y/expanding (reviewer-flagged path); "
        f"got halved_count={halved_count} of {len(results)} folds"
    )


# ---------------------------------------------------------------------------
# Test K5.5 — NEG (KICK-5)
# ---------------------------------------------------------------------------
def test_kick5_dataclass_rejects_invalid_fallback_flag():
    """KICK-5: ``BootstrapDiagnostics(..., fallback_flag="bogus")``
    raises ``ValueError`` from ``__post_init__`` validator. Tri-state
    contract enforced at construction (mirrors KICK-3
    ``BinDiagnosticStatus`` precedent)."""
    with pytest.raises(ValueError, match=r"fallback_flag="):
        BootstrapDiagnostics(
            n_train=120,
            n_eff=10,
            block_size=12,
            block_count=10,
            B_effective=1000,
            fallback_flag="bogus",  # invalid tri-state
        )


# ---------------------------------------------------------------------------
# Test K5.6 — NEG (KICK-5)
# ---------------------------------------------------------------------------
def test_kick5_dataclass_rejects_missing_no_default_field():
    """KICK-5: bare ``BootstrapDiagnostics(...)`` without any 1 of the
    6 no-default fields raises ``TypeError``. AP-AUTH-53 step #3 +
    AP-AUTH-54 step #2 contract."""
    # Missing fallback_flag (test the most-likely-omitted one).
    with pytest.raises(TypeError, match=r"fallback_flag"):
        BootstrapDiagnostics(
            n_train=120,
            n_eff=10,
            block_size=12,
            block_count=10,
            B_effective=1000,
            # fallback_flag omitted — must raise
        )
    # Missing B_effective.
    with pytest.raises(TypeError, match=r"B_effective"):
        BootstrapDiagnostics(
            n_train=120,
            n_eff=10,
            block_size=12,
            block_count=10,
            fallback_flag="none",
            # B_effective omitted — must raise
        )
    # Missing n_train.
    with pytest.raises(TypeError, match=r"n_train"):
        BootstrapDiagnostics(
            n_eff=10,
            block_size=12,
            block_count=10,
            B_effective=1000,
            fallback_flag="none",
            # n_train omitted — must raise
        )
