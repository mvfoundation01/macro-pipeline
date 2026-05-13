"""Layer 5-B Task A — composite-weight refit via penalized logistic regression.

Closes ChatGPT 5.5 v1 §E.2 / L5-RISK-2 per S-3. Spec ref:
``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.B.1 (lines 587-748).

Public API
----------
``CompositeWeightRefitResult``  Frozen dataclass; one fit per (horizon × schedule × fold × score_type[ × threshold]).
``LAMBDA_GRID_DEFAULT``         11 log-spaced λ values 1e-4..1e2 (per spec §5.B.4 line 783).
``fit_composite_weights``       Task A's public entry point.

Nested walk-forward CV (per spec §5.B.1.2)
------------------------------------------
For each outer fold from ``schedule.folds``:
  1. Build inner walk-forward blocks on ``[train_start, train_end]`` for λ selection.
  2. For each λ ∈ ``lambda_grid``: fit penalized logistic on inner-train,
     score on inner-test (Brier); average across inner folds.
  3. Select λ* = argmin mean inner Brier.
  4. Refit on full outer-fold training window with λ*.
  5. Predict on outer-fold test partition; emit ``CompositeWeightRefitResult``.

Inner-CV implementation decision (pre-flight risk #4 resolution)
----------------------------------------------------------------
Inner CV uses **time-ordered contiguous blocks WITHOUT a contamination gap**
between inner-train and inner-test. Rationale:
  * Inner CV's purpose is λ selection only; outer CV preserves OOS-evaluation
    integrity via the full ``gap_months`` contamination gap.
  * With the spec's ``min_train_window_months=240`` and gap=120 (10Y horizon),
    inner CV with both gap AND 5-fold split becomes infeasible at small
    outer-train windows. Block-only inner CV is the standard pragmatic
    choice (HTF 2017 §7.10; standard sklearn TimeSeriesSplit pattern).
  * Documented in L5-B Task A verification report (NOT filed as Sxx —
    implementation decision per pre-flight discipline §6).

Train-only z-scoring (per spec §2.5 audit #5 + S-2)
---------------------------------------------------
Feature mean / std computed on training window ONLY; recomputed per fold
(no reuse across folds); applied to test fold via train-statistics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from macro_pipeline.analysis.walk_forward_cv import WalkForwardSchedule

ScoreTypeRefit = Literal["CRPS", "CDRS"]

# Spec §5.B.4 line 783: 11 log-spaced points between 1e-4 and 1e2 inclusive.
LAMBDA_GRID_DEFAULT: tuple[float, ...] = tuple(
    float(x) for x in (10.0 ** np.linspace(-4, 2, 11))
)

# Minimum effective sample size for Task A fold acceptance (per §5.B.2 item 4
# referencing UNDERPOWERED_N_NOMINAL_MIN = 24 from analysis.effective_sample_size).
_MIN_N_TRAIN_OBS: int = 24
_MIN_N_TEST_OBS: int = 1


@dataclass(frozen=True)
class CompositeWeightRefitResult:
    """One Task A fit result for a single (horizon × schedule × fold × score_type[ × threshold]).

    Fields per spec §5.B.1.1 lines 608-629. Construction is via
    ``fit_composite_weights``; this dataclass is the output container.
    """

    fold_id: int
    horizon: str
    schedule_type: str
    score_type: str                           # "CRPS" | "CDRS"
    drawdown_threshold: float | None          # required for CDRS; None for CRPS
    lambda_selected: float
    lambda_grid: tuple[float, ...]
    component_coefficients: dict[str, float]  # per-component β
    intercept: float
    auc_oos: float
    brier_oos: float
    calibration_slope: float
    calibration_intercept: float
    monotone_cdf_check: bool                  # CDRS-only invariant; True by default
    n_train_obs: int
    n_test_obs: int
    grid_edge_bind: bool
    sign_flip_rate: float
    fit_timestamp: pd.Timestamp


def _zscore_fit_transform(
    X_train: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Train-only z-scoring per spec §2.5 audit #5. Returns (X_train_z, mean, std)."""
    mean = X_train.mean(axis=0)
    std = X_train.std(axis=0, ddof=0)
    # Avoid divide-by-zero on degenerate columns (zero-variance feature).
    std = np.where(std < 1e-12, 1.0, std)
    X_train_z = (X_train - mean) / std
    return X_train_z, mean, std


def _zscore_transform(
    X: np.ndarray, mean: np.ndarray, std: np.ndarray,
) -> np.ndarray:
    return (X - mean) / std


def _calibration_slope_intercept(
    y_true: np.ndarray, y_pred_proba: np.ndarray,
) -> tuple[float, float]:
    """Fit logistic on (logit_pred, actual) → (slope, intercept).

    Perfect calibration ⇒ slope = 1, intercept = 0. Returns (NaN, NaN) when
    test set lacks event variation (single class).
    """
    if len(set(y_true.tolist())) < 2:
        return float("nan"), float("nan")
    p = np.clip(y_pred_proba, 1e-6, 1 - 1e-6)
    logit_p = np.log(p / (1 - p))
    cal_lr = LogisticRegression(C=1e6, max_iter=1000)  # near-OLS via large C
    cal_lr.fit(logit_p.reshape(-1, 1), y_true.astype(int))
    return float(cal_lr.coef_[0, 0]), float(cal_lr.intercept_[0])


def _build_inner_blocks(
    n_train: int, n_inner_folds: int,
) -> list[tuple[slice, slice]]:
    """Time-ordered contiguous blocks for inner CV (NO contamination gap).

    For ``n_inner_folds = K``, partition ``n_train`` into ``K+1`` equal-size
    chunks; for ``k = 0..K-1``, inner_train = chunks[0..k+1], inner_test = chunks[k+1].
    Returns list of (inner_train_slice, inner_test_slice).

    Per spec §5.B.1.2 line 723: time-ordered, no random shuffling. Gap omitted
    by design (rationale in module docstring).
    """
    fold_size = max(1, n_train // (n_inner_folds + 1))
    blocks: list[tuple[slice, slice]] = []
    for k in range(n_inner_folds):
        train_end = fold_size * (k + 1)
        test_start = train_end
        test_end = min(test_start + fold_size, n_train)
        if train_end >= test_end or train_end < 2:
            break
        blocks.append((slice(0, train_end), slice(test_start, test_end)))
    return blocks


def _select_lambda_inner_cv(
    X_train: np.ndarray,
    y_train: np.ndarray,
    lambda_grid: tuple[float, ...],
    inner_fold_count: int,
    random_seed: int,
) -> float:
    """Inner-CV λ selection: minimize mean Brier across inner blocks."""
    blocks = _build_inner_blocks(len(X_train), inner_fold_count)
    if not blocks:
        # Too few obs for inner CV; pick mid-grid λ (graceful degradation).
        return float(lambda_grid[len(lambda_grid) // 2])

    brier_per_lambda: list[float] = []
    for lam in lambda_grid:
        C = 1.0 / max(lam, 1e-12)
        briers: list[float] = []
        for tr_slice, te_slice in blocks:
            X_tr = X_train[tr_slice]
            y_tr = y_train[tr_slice]
            X_te = X_train[te_slice]
            y_te = y_train[te_slice]
            if len(set(y_tr.tolist())) < 2 or len(y_te) == 0:
                continue
            X_tr_z, mean_tr, std_tr = _zscore_fit_transform(X_tr)
            X_te_z = _zscore_transform(X_te, mean_tr, std_tr)
            lr = LogisticRegression(C=C, max_iter=1000, random_state=random_seed)
            lr.fit(X_tr_z, y_tr)
            p_pred = lr.predict_proba(X_te_z)[:, 1]
            briers.append(float(brier_score_loss(y_te, p_pred)))
        brier_per_lambda.append(
            float(np.mean(briers)) if briers else float("inf")
        )
    best_idx = int(np.argmin(brier_per_lambda))
    return float(lambda_grid[best_idx])


def fit_composite_weights(
    schedule: WalkForwardSchedule,
    component_panel: pd.DataFrame,
    event_labels: pd.Series,
    *,
    score_type: ScoreTypeRefit,
    lambda_grid: tuple[float, ...] = LAMBDA_GRID_DEFAULT,
    drawdown_threshold: float | None = None,
    inner_fold_count: int = 5,
    random_seed: int = 42,
) -> tuple[CompositeWeightRefitResult, ...]:
    """Task A: Refit Layer 3 component weights via penalized logistic regression.

    Iterates ``schedule.folds`` (outer walk-forward) and for each fold runs
    inner-CV λ selection over ``lambda_grid``, then refits on the outer
    training window with the selected λ. Per-fold metrics + per-component
    coefficients are emitted as ``CompositeWeightRefitResult``.

    Parameters
    ----------
    schedule
        ``WalkForwardSchedule`` from L5-A (one per horizon × schedule_type).
    component_panel
        DataFrame with **≥ 4 columns** (spec §5.B.5.A test A1). Index must
        be ``pd.DatetimeIndex`` overlapping ``schedule`` fold boundaries.
        Rows with any NaN are dropped from both train and test per fold.
    event_labels
        Per spec §3.3 (CRPS = NBER USREC 12M; CDRS = drawdown ≥ X within H;
        caller's responsibility to construct). Indexed by ``pd.DatetimeIndex``
        matching ``component_panel``. Binary {0, 1}.
    score_type
        ``"CRPS"`` or ``"CDRS"``. CDRS requires ``drawdown_threshold``.
    lambda_grid
        λ values to search. Default ``LAMBDA_GRID_DEFAULT`` (11 log-spaced
        points 1e-4..1e2 per spec §5.B.4 line 783).
    drawdown_threshold
        For CDRS: ∈ {0.10, 0.20, 0.35, 0.50, 0.65} per §3.3. ``None`` for CRPS.
    inner_fold_count
        Inner walk-forward folds for λ selection. Default 5 per spec §5.B.1.2.
    random_seed
        For reproducible LogisticRegression initialization. Default 42.

    Returns
    -------
    tuple[CompositeWeightRefitResult, ...]
        One result per accepted outer fold. Folds with
        ``n_train_obs < 24`` or single-class training labels are skipped
        (per spec §5.B.2 item 4 underpowered-fold policy).

    Raises
    ------
    ValueError
        On invalid ``score_type``, scalar ``component_panel``,
        ``score_type='CDRS'`` without ``drawdown_threshold``, or non-Series
        ``event_labels``.
    """
    # ---- Input validation (test A1, A4, A5, A8) ----
    if score_type not in ("CRPS", "CDRS"):
        raise ValueError(
            f"score_type must be one of ('CRPS', 'CDRS'); got {score_type!r}"
        )
    if not isinstance(component_panel, pd.DataFrame):
        raise ValueError(
            f"component_panel must be pd.DataFrame; "
            f"got {type(component_panel).__name__}"
        )
    if component_panel.shape[1] < 4:
        raise ValueError(
            f"component_panel must have >= 4 columns per spec §5.B.5.A "
            f"test A1 (scalar raw_score input is REJECTED); got "
            f"{component_panel.shape[1]} columns"
        )
    if score_type == "CDRS" and drawdown_threshold is None:
        raise ValueError(
            "score_type='CDRS' requires drawdown_threshold (per §3.3 schema; "
            "test A8 - cannot identify CDRS event without threshold)"
        )
    if not isinstance(event_labels, pd.Series):
        raise ValueError(
            f"event_labels must be pd.Series; "
            f"got {type(event_labels).__name__}"
        )

    component_names = list(component_panel.columns)

    results: list[CompositeWeightRefitResult] = []
    prior_coefs: dict[str, float] | None = None
    fit_now = pd.Timestamp.now(tz="UTC")

    for fold in schedule.folds:
        # Train / test slices on component_panel index
        train_idx = component_panel.index[
            (component_panel.index >= fold.train_start)
            & (component_panel.index <= fold.train_end)
        ]
        test_idx = component_panel.index[
            (component_panel.index >= fold.test_start)
            & (component_panel.index <= fold.test_end)
        ]

        X_train_df = component_panel.loc[train_idx].dropna()
        X_test_df = component_panel.loc[test_idx].dropna()
        y_train = event_labels.reindex(X_train_df.index).dropna()
        y_test = event_labels.reindex(X_test_df.index).dropna()

        # Align indices (X and y must share index after dropna).
        X_train_df = X_train_df.loc[y_train.index]
        X_test_df = X_test_df.loc[y_test.index]

        n_train_obs = len(y_train)
        n_test_obs = len(y_test)

        # Underpowered fold skip per spec §5.B.2 item 4
        if n_train_obs < _MIN_N_TRAIN_OBS or n_test_obs < _MIN_N_TEST_OBS:
            continue
        if len(set(y_train.astype(int).tolist())) < 2:
            # No event variation in training fold; cannot fit logistic.
            continue

        X_train = X_train_df.to_numpy(dtype=float)
        X_test = X_test_df.to_numpy(dtype=float)
        y_train_arr = y_train.to_numpy(dtype=int)
        y_test_arr = y_test.to_numpy(dtype=int)

        # ---- Inner-CV λ selection ----
        lambda_selected = _select_lambda_inner_cv(
            X_train, y_train_arr, lambda_grid, inner_fold_count, random_seed
        )

        # ---- Refit on full outer training window with selected λ ----
        X_train_z, mean_tr, std_tr = _zscore_fit_transform(X_train)
        X_test_z = _zscore_transform(X_test, mean_tr, std_tr)
        C = 1.0 / max(lambda_selected, 1e-12)
        lr = LogisticRegression(C=C, max_iter=1000, random_state=random_seed)
        lr.fit(X_train_z, y_train_arr)

        p_test = lr.predict_proba(X_test_z)[:, 1]

        # ---- Per-fold metrics ----
        if len(set(y_test_arr.tolist())) >= 2:
            auc_oos = float(roc_auc_score(y_test_arr, p_test))
        else:
            auc_oos = float("nan")
        brier_oos = float(brier_score_loss(y_test_arr, p_test))
        cal_slope, cal_intercept = _calibration_slope_intercept(
            y_test_arr, p_test
        )

        # Per-component coefficients (dict per spec test A4)
        coefs_dict: dict[str, float] = {
            name: float(lr.coef_[0, i]) for i, name in enumerate(component_names)
        }

        # sign_flip_rate vs prior fold (closes ChatGPT E.6 stability per S-7)
        if prior_coefs is None:
            sign_flip_rate = 0.0
        else:
            non_trivial = [
                n for n in component_names
                if abs(coefs_dict[n]) > 1e-6
                and abs(prior_coefs.get(n, 0.0)) > 1e-6
            ]
            if not non_trivial:
                sign_flip_rate = 0.0
            else:
                flips = sum(
                    1 for n in non_trivial
                    if np.sign(coefs_dict[n]) != np.sign(prior_coefs[n])
                )
                sign_flip_rate = flips / len(non_trivial)
        prior_coefs = coefs_dict.copy()

        # grid_edge_bind: True if selected λ at grid boundary
        grid_edge_bind = (
            lambda_selected == lambda_grid[0]
            or lambda_selected == lambda_grid[-1]
        )

        # monotone_cdf_check: caller's responsibility across multiple thresholds
        # for CDRS (single fit cannot self-verify). Single-call default True.
        monotone_cdf_check = True

        result = CompositeWeightRefitResult(
            fold_id=fold.fold_id,
            horizon=fold.horizon,
            schedule_type=fold.schedule_type,
            score_type=score_type,
            drawdown_threshold=drawdown_threshold,
            lambda_selected=lambda_selected,
            lambda_grid=tuple(lambda_grid),
            component_coefficients=coefs_dict,
            intercept=float(lr.intercept_[0]),
            auc_oos=auc_oos,
            brier_oos=brier_oos,
            calibration_slope=cal_slope,
            calibration_intercept=cal_intercept,
            monotone_cdf_check=monotone_cdf_check,
            n_train_obs=n_train_obs,
            n_test_obs=n_test_obs,
            grid_edge_bind=grid_edge_bind,
            sign_flip_rate=sign_flip_rate,
            fit_timestamp=fit_now,
        )
        results.append(result)

    return tuple(results)


__all__ = [
    "LAMBDA_GRID_DEFAULT",
    "CompositeWeightRefitResult",
    "ScoreTypeRefit",
    "fit_composite_weights",
]
