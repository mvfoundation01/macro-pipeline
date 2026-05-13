"""Layer 5-RM-6 — Isotonic regression calibration (PAV; per-horizon).

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.RM-6 (lines 1121-1354).

Implements **25 calibrators per refit window** per §3.3 calibration target
schema (v3 corrected per S-8):
- 1× CRPS at ("CRPS", "1Y", None) — calibrates against NBER USREC 12M labels
- 20× CDRS = 4 horizons × 5 drawdown thresholds — calibrates against
  SPX drawdown ≥ threshold within horizon
- 4× RETURN_POSITIVE = 1 per horizon — calibrates against forward real
  return > 0 at horizon

Q-resolutions locked:
- Q4 per-horizon scope (§5.RM-6.4 option C; reframed v3 as "per (score_type ×
  horizon × threshold)" totalling 25)
- Q5 recalibration cadence (§5.RM-6.4 option C; quarterly + Sahm 0.30 + yield
  curve 2-month-inversion; v2 90d cooldown + coalescing per S-7)

Implementation note (dict key type)
-----------------------------------
Spec §5.RM-6.1.1 line 1181 type hint reads ``dict[tuple[str, str], ...]`` but
test #1 (line 1306) enumerates keys including 3-tuple ``("CDRS", h, threshold)``.
Track A implementation uses **3-tuple uniformly**: ``(score_type, horizon,
drawdown_threshold)`` where threshold is ``None`` for CRPS + RETURN_POSITIVE
and a ``float`` for CDRS. Most aligned with test contract; avoids
string-encoded keys. PATCH-IMPL per AP-AUTH-52 doc-residue class (similar
to S-12 spec-vs-implementation gap; no Sxx — gratuitous per AP-AUTH-46).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ScoreType = Literal["CRPS", "CDRS", "RETURN_POSITIVE"]
HorizonLabel = Literal["1Y", "3Y", "5Y", "10Y"]

# §5.RM-6.1.1 constants (Q5 lock; empirical-tunable per §5.RM-6.2 smoke-test)
SAHM_RULE_TRIGGER_THRESHOLD: float = 0.30
YIELD_CURVE_INVERSION_TRIGGER_MIN_CONSECUTIVE_MONTHS: int = 2

# §5.RM-6.1.2 — default 5 drawdown thresholds (v3 per S-8)
CDRS_DRAWDOWN_THRESHOLDS_DEFAULT: tuple[float, ...] = (
    0.10, 0.20, 0.35, 0.50, 0.65,
)

# §5.RM-6.1.4 — 90-day cooldown after refit (v2 per S-7)
COOLDOWN_DAYS_DEFAULT: int = 90

# §5.RM-6.5 test #8 — minimum n_train_obs for fit
_MIN_N_TRAIN_OBS: int = 50

_VALID_SCORE_TYPES: frozenset[str] = frozenset(
    {"CRPS", "CDRS", "RETURN_POSITIVE"}
)
_VALID_HORIZONS: frozenset[str] = frozenset({"1Y", "3Y", "5Y", "10Y"})
_QUARTERLY_REFIT_MONTHS: frozenset[int] = frozenset({3, 6, 9, 12})


@dataclass(frozen=True)
class IsotonicCalibrationResult:
    """One calibrator fit result per spec §5.RM-6.1.1 (lines 1151-1164)."""

    horizon: str
    fit_window_start: pd.Timestamp
    fit_window_end: pd.Timestamp
    n_train_obs: int
    fitted_y_min: float
    fitted_y_max: float
    monotonicity_audit: str
    bootstrap_se_distribution: np.ndarray
    sklearn_model: IsotonicRegression
    random_seed: int
    refit_trigger: str
    refit_trigger_metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Event-label dispatcher (HARD GATE per S-8; spec §5.RM-6.1.1 build_event_labels)
# ---------------------------------------------------------------------------


def _nber_recession_start_within_12m(panel: pd.DataFrame) -> np.ndarray:
    """CRPS event label: NBER recession start within 12M ahead.

    Expected panel column: ``nber_recession_start_within_12m`` (bool).
    """
    col = "nber_recession_start_within_12m"
    if col not in panel.columns:
        raise ValueError(
            f"CRPS event-label build requires panel column {col!r}; "
            f"got columns: {list(panel.columns)}"
        )
    return panel[col].astype(bool).to_numpy()


def _spx_drawdown_ge_threshold_within_h(
    panel: pd.DataFrame, *, threshold: float, horizon: str,
) -> np.ndarray:
    """CDRS event label: SPX max forward-window drawdown ≥ threshold.

    Expected panel column: ``spx_max_drawdown_within_{horizon}`` (float).
    """
    col = f"spx_max_drawdown_within_{horizon}"
    if col not in panel.columns:
        raise ValueError(
            f"CDRS event-label build requires panel column {col!r} "
            f"(horizon={horizon}); got columns: {list(panel.columns)}"
        )
    return (panel[col].astype(float).to_numpy() >= threshold)


def _forward_real_return_gt_zero_h(
    panel: pd.DataFrame, *, horizon: str,
) -> np.ndarray:
    """RETURN_POSITIVE event label: forward real return > 0 at horizon.

    Expected panel column: ``forward_real_return_{horizon}`` (float).
    """
    col = f"forward_real_return_{horizon}"
    if col not in panel.columns:
        raise ValueError(
            f"RETURN_POSITIVE event-label build requires panel column "
            f"{col!r} (horizon={horizon}); got columns: {list(panel.columns)}"
        )
    return (panel[col].astype(float).to_numpy() > 0.0)


def build_event_labels(
    score_type: ScoreType,
    panel: pd.DataFrame,
    horizon: HorizonLabel,
    *,
    drawdown_threshold: float | None = None,
) -> np.ndarray:
    """Build binary event labels per §3.3 calibration target schema.

    HARD GATE per S-8 (closes ChatGPT v2 E.1 partially-closed → CLOSED):
    enforces schema at fit time; mismatch raises ValueError.

    Parameters per spec §5.RM-6.1.1 lines 1192-1216.

    Returns
    -------
    np.ndarray
        Boolean array (dtype=bool) of event labels aligned with panel index.
    """
    if score_type == "CRPS":
        if horizon != "1Y":
            raise ValueError(
                "CRPS calibrates only against 12M NBER recession labels "
                f"per §3.3; horizon={horizon!r} not supported. Extend §3.3 "
                "schema to authorize other horizons."
            )
        return _nber_recession_start_within_12m(panel)
    elif score_type == "CDRS":
        if drawdown_threshold is None:
            raise ValueError(
                "CDRS calibration requires drawdown_threshold per §3.3"
            )
        if horizon not in _VALID_HORIZONS:
            raise ValueError(
                f"Invalid horizon {horizon!r}; "
                f"valid: {sorted(_VALID_HORIZONS)}"
            )
        return _spx_drawdown_ge_threshold_within_h(
            panel, threshold=drawdown_threshold, horizon=horizon,
        )
    elif score_type == "RETURN_POSITIVE":
        if horizon not in _VALID_HORIZONS:
            raise ValueError(
                f"Invalid horizon {horizon!r}; "
                f"valid: {sorted(_VALID_HORIZONS)}"
            )
        return _forward_real_return_gt_zero_h(panel, horizon=horizon)
    else:
        raise ValueError(
            f"score_type {score_type!r} not in §3.3 schema "
            f"{sorted(_VALID_SCORE_TYPES)}"
        )


# ---------------------------------------------------------------------------
# Isotonic fitting helpers
# ---------------------------------------------------------------------------


def _audit_monotonicity(
    model: IsotonicRegression, grid_n: int = 1000,
) -> str:
    """Standing Order #4 universal-claim audit per §5.RM-6.5 test #2.

    Sweeps a uniform [0, 1] grid; asserts monotone non-decreasing within
    1e-9 tolerance. Returns "PASS" or "FAIL <details>".
    """
    grid = np.linspace(0.0, 1.0, grid_n)
    pred = model.predict(grid)
    diff = np.diff(pred)
    if np.all(diff >= -1e-9):
        return "PASS"
    n_violations = int(np.sum(diff < -1e-9))
    max_violation = float(diff.min())
    return (
        f"FAIL n_violations={n_violations} "
        f"max_violation={max_violation:.6g}"
    )


def _detect_non_monotone_input(
    raw_scores: np.ndarray, y_train: np.ndarray,
) -> None:
    """Emit RuntimeWarning if input pattern suggests non-monotone DGP.

    Per spec §5.RM-6.5 test #7: heuristic check on sorted-by-x pairs;
    if y switches direction across rank windows, emit warning. Not a fit
    blocker (PAV will still produce a valid monotone projection).
    """
    if len(raw_scores) < 6:
        return
    order = np.argsort(raw_scores)
    y_sorted = y_train[order]
    # Simple heuristic: split sorted into 3 thirds; check mean ordering
    n = len(y_sorted)
    third = max(1, n // 3)
    m_lo = float(y_sorted[:third].mean())
    m_mid = float(y_sorted[third:2 * third].mean())
    m_hi = float(y_sorted[2 * third:].mean())
    if m_lo > m_mid or m_mid > m_hi:
        warnings.warn(
            f"non-monotone input detected: tertile means lo={m_lo:.3f} "
            f"mid={m_mid:.3f} hi={m_hi:.3f}; PAV will project to monotone",
            RuntimeWarning,
            stacklevel=3,
        )


def _bootstrap_se_distribution(
    raw_scores: np.ndarray,
    y_train: np.ndarray,
    n_iter: int,
    seed: int,
) -> np.ndarray:
    """Per spec §5.RM-6.1.1 lines 1160 + §5.RM-6.3 standard-error row.

    Bootstrap calibration residuals (B=n_iter resamples); seeded for
    reproducibility per test #9.
    """
    rng = np.random.default_rng(seed)
    n = len(raw_scores)
    se_dist = np.zeros(n_iter, dtype=float)
    for b in range(n_iter):
        idx = rng.integers(0, n, size=n)
        x_b = raw_scores[idx]
        y_b = y_train[idx].astype(float)
        try:
            m_b = IsotonicRegression(
                out_of_bounds="clip", y_min=0.0, y_max=1.0,
            )
            m_b.fit(x_b, y_b)
            p_b = m_b.predict(raw_scores)
            residuals = y_train.astype(float) - p_b
            se_dist[b] = float(np.std(residuals, ddof=1))
        except Exception:
            se_dist[b] = float("nan")
    return se_dist


def _fit_one_calibrator(
    raw_scores: np.ndarray,
    panel: pd.DataFrame,
    score_type: str,
    horizon: str,
    fit_window: tuple[pd.Timestamp, pd.Timestamp],
    drawdown_threshold: float | None,
    bootstrap_iterations: int,
    random_seed: int,
    refit_trigger: str,
) -> IsotonicCalibrationResult:
    """Fit one isotonic calibrator for a single (score_type, horizon[, threshold])."""
    y_train = build_event_labels(
        score_type, panel, horizon, drawdown_threshold=drawdown_threshold,
    )

    if len(raw_scores) != len(y_train):
        raise ValueError(
            f"raw_scores length ({len(raw_scores)}) must match panel "
            f"event labels length ({len(y_train)})"
        )

    if len(y_train) < _MIN_N_TRAIN_OBS:
        raise ValueError(
            f"insufficient samples for isotonic: n={len(y_train)} < "
            f"{_MIN_N_TRAIN_OBS} (§5.RM-6.5 test #8)"
        )

    raw_arr = np.asarray(raw_scores, dtype=float)
    y_arr = y_train.astype(bool)

    # Pre-fit: emit warning if input pattern suggests non-monotone DGP
    _detect_non_monotone_input(raw_arr, y_arr)

    model = IsotonicRegression(
        out_of_bounds="clip", y_min=0.0, y_max=1.0,
    )
    model.fit(raw_arr, y_arr.astype(float))

    monotonicity_audit = _audit_monotonicity(model)
    se_dist = _bootstrap_se_distribution(
        raw_arr, y_arr, bootstrap_iterations, random_seed,
    )

    return IsotonicCalibrationResult(
        horizon=horizon,
        fit_window_start=fit_window[0],
        fit_window_end=fit_window[1],
        n_train_obs=int(len(y_arr)),
        fitted_y_min=0.0,
        fitted_y_max=1.0,
        monotonicity_audit=monotonicity_audit,
        bootstrap_se_distribution=se_dist,
        sklearn_model=model,
        random_seed=random_seed,
        refit_trigger=refit_trigger,
        refit_trigger_metadata={
            "score_type": score_type,
            "drawdown_threshold": drawdown_threshold,
        },
    )


# ---------------------------------------------------------------------------
# 25-calibrator dispatcher (spec §5.RM-6.1.1 fit_isotonic_calibrators)
# ---------------------------------------------------------------------------


CalibratorKey = tuple[str, str, float | None]


def fit_isotonic_calibrators(
    raw_scores: dict[tuple[str, str], np.ndarray],
    panel: pd.DataFrame,
    *,
    fit_window: tuple[pd.Timestamp, pd.Timestamp],
    drawdown_thresholds: tuple[float, ...] = CDRS_DRAWDOWN_THRESHOLDS_DEFAULT,
    bootstrap_iterations: int = 1000,
    random_seed: int = 42,
    refit_trigger: str = "initial",
) -> dict[CalibratorKey, IsotonicCalibrationResult]:
    """Fit 25 isotonic calibrators per §3.3 calibration target schema.

    Per spec §5.RM-6.1.1 + §5.RM-6.1.2 + S-8:
        1× ("CRPS", "1Y", None)
        20× ("CDRS", horizon ∈ {1Y, 3Y, 5Y, 10Y}, threshold ∈
            {0.10, 0.20, 0.35, 0.50, 0.65})
        4× ("RETURN_POSITIVE", horizon ∈ {1Y, 3Y, 5Y, 10Y}, None)

    Key type: **3-tuple uniformly** (see module-level "Implementation
    note (dict key type)" docstring) — spec §5.RM-6.1.1 line 1181 type
    hint says 2-tuple but test #1 (§5.RM-6.5) enumerates 3-tuple for
    CDRS; PATCH-IMPL chooses 3-tuple uniformly for type consistency.

    Parameters
    ----------
    raw_scores
        Input dict keyed by (score_type, horizon) 2-tuples. For CDRS,
        the same raw_scores array is fanned out across all 5 drawdown
        thresholds (per spec).
    panel
        DataFrame with expected event-label columns (see
        ``build_event_labels`` helpers).
    fit_window
        (start, end) inclusive-exclusive bounds; stored on result.
    drawdown_thresholds
        5 thresholds for CDRS fan-out; defaults to spec §3.3 set.
    bootstrap_iterations
        B for residual bootstrap; default 1000.
    random_seed
        Determinism per test #9; default 42.
    refit_trigger
        ``"initial"`` | ``"quarterly"`` | ``"sahm_rule"`` | ``"yield_curve"``
        Stored on each result.

    Returns
    -------
    dict[CalibratorKey, IsotonicCalibrationResult]
        Exactly 25 entries when raw_scores contains the full §3.3 fanout.

    Raises
    ------
    ValueError
        On invalid score_type, invalid horizon for the given score_type,
        or insufficient n_train_obs.
    """
    out: dict[CalibratorKey, IsotonicCalibrationResult] = {}

    for (st, h), raw_arr in raw_scores.items():
        if st not in _VALID_SCORE_TYPES:
            raise ValueError(
                f"Unknown score_type {st!r}; "
                f"valid: {sorted(_VALID_SCORE_TYPES)}"
            )

        if st == "CRPS":
            if h != "1Y":
                raise ValueError(
                    f"CRPS calibrates only against 12M; got horizon={h!r}"
                )
            out[(st, h, None)] = _fit_one_calibrator(
                raw_scores=raw_arr,
                panel=panel,
                score_type=st,
                horizon=h,
                fit_window=fit_window,
                drawdown_threshold=None,
                bootstrap_iterations=bootstrap_iterations,
                random_seed=random_seed,
                refit_trigger=refit_trigger,
            )
        elif st == "CDRS":
            if h not in _VALID_HORIZONS:
                raise ValueError(
                    f"CDRS horizon {h!r} not in {sorted(_VALID_HORIZONS)}"
                )
            for thr in drawdown_thresholds:
                out[(st, h, thr)] = _fit_one_calibrator(
                    raw_scores=raw_arr,
                    panel=panel,
                    score_type=st,
                    horizon=h,
                    fit_window=fit_window,
                    drawdown_threshold=thr,
                    bootstrap_iterations=bootstrap_iterations,
                    random_seed=random_seed,
                    refit_trigger=refit_trigger,
                )
        elif st == "RETURN_POSITIVE":
            if h not in _VALID_HORIZONS:
                raise ValueError(
                    f"RETURN_POSITIVE horizon {h!r} not in "
                    f"{sorted(_VALID_HORIZONS)}"
                )
            out[(st, h, None)] = _fit_one_calibrator(
                raw_scores=raw_arr,
                panel=panel,
                score_type=st,
                horizon=h,
                fit_window=fit_window,
                drawdown_threshold=None,
                bootstrap_iterations=bootstrap_iterations,
                random_seed=random_seed,
                refit_trigger=refit_trigger,
            )
    return out


# ---------------------------------------------------------------------------
# Recalibration trigger logic (Q5 + 90d cooldown coalescing per S-7)
# ---------------------------------------------------------------------------


def _is_quarterly_refit_date(d: pd.Timestamp) -> bool:
    """True iff d is the first day of Mar/Jun/Sep/Dec (Q5 quarterly cadence)."""
    return d.month in _QUARTERLY_REFIT_MONTHS and d.day == 1


def _sahm_rule_triggered_since(
    sahm_series: pd.Series, since_date: pd.Timestamp, as_of: pd.Timestamp,
) -> bool:
    """True iff SAHMREALTIME > SAHM_RULE_TRIGGER_THRESHOLD at any point
    in the window (since_date, as_of]."""
    if sahm_series is None or sahm_series.empty:
        return False
    window = sahm_series[
        (sahm_series.index > since_date) & (sahm_series.index <= as_of)
    ]
    return bool((window > SAHM_RULE_TRIGGER_THRESHOLD).any())


def _yield_curve_triggered_since(
    spread_series: pd.Series, since_date: pd.Timestamp, as_of: pd.Timestamp,
) -> bool:
    """True iff 10Y-3M spread negative for ≥
    YIELD_CURVE_INVERSION_TRIGGER_MIN_CONSECUTIVE_MONTHS consecutive
    monthly observations within the window (since_date, as_of]."""
    if spread_series is None or spread_series.empty:
        return False
    window = spread_series[
        (spread_series.index > since_date)
        & (spread_series.index <= as_of)
    ]
    if len(window) < YIELD_CURVE_INVERSION_TRIGGER_MIN_CONSECUTIVE_MONTHS:
        return False
    inverted = (window < 0.0).astype(int).to_numpy()
    # Look for run of >= MIN_CONSECUTIVE_MONTHS of 1s
    run = 0
    for v in inverted:
        run = run + 1 if v else 0
        if run >= YIELD_CURVE_INVERSION_TRIGGER_MIN_CONSECUTIVE_MONTHS:
            return True
    return False


def should_recalibrate(
    last_refit_date: pd.Timestamp,
    as_of: pd.Timestamp,
    sahm_rule_series: pd.Series,
    yield_curve_series: pd.Series,
    *,
    cooldown_days: int = COOLDOWN_DAYS_DEFAULT,
) -> tuple[bool, str]:
    """Q5 trigger check + 90d cooldown coalescing per S-7.

    Per spec §5.RM-6.1.3 + §5.RM-6.1.4 lines 1250-1267.

    Reasons returned:
        - "quarterly_cadence"
        - "sahm_rule_trigger"
        - "yield_curve_trigger"
        - "cooldown_active" (trigger fired but within 90d window)
        - "no_refit"
    """
    days_since_last = (as_of - last_refit_date).days

    # ---- Cooldown gate (90-day window after refit) ----
    # Implementation decision (spec §5.RM-6.1.4 step 1 vs test #3 reconciliation):
    # Spec line 1262 says "no further refit until 90d elapsed" but test #3
    # (line 1308) expects quarterly to fire 59 days after last refit. The
    # "Max refits/year ≤ 6 (= 4 quarterly + 2 trigger)" arithmetic at step 3
    # implies QUARTERLY always fires (4/year); cooldown only debounces
    # TRIGGER refits (Sahm + yield-curve = up to 2 extra refits/year).
    # Track A interpretation: cooldown blocks Sahm + yield-curve triggers
    # ONLY; quarterly cadence always fires. PATCH-IMPL per AP-AUTH-52
    # class (similar S-12 pattern); document in L5_RM_6_VERIFICATION + file
    # L5b-7 backlog candidate at ACCEPT for post-L5 spec cleanup.
    in_cooldown = days_since_last < cooldown_days

    # ---- Check triggers ----
    sahm_fired = _sahm_rule_triggered_since(
        sahm_rule_series, last_refit_date, as_of,
    )
    yc_fired = _yield_curve_triggered_since(
        yield_curve_series, last_refit_date, as_of,
    )
    quarterly_fired = _is_quarterly_refit_date(as_of)

    # Quarterly always fires (4/year cadence)
    if quarterly_fired:
        return True, "quarterly_cadence"

    # Triggers (Sahm + yield-curve) debounced by 90d cooldown per §5.RM-6.1.4
    trigger_fired = sahm_fired or yc_fired
    if in_cooldown and trigger_fired:
        return False, "cooldown_active"

    if sahm_fired:
        return True, "sahm_rule_trigger"
    if yc_fired:
        return True, "yield_curve_trigger"
    return False, "no_refit"


# ---------------------------------------------------------------------------
# Calibration application (spec §5.RM-6.1.1 calibrate_raw_score)
# ---------------------------------------------------------------------------


def calibrate_raw_score(
    raw_score: float,
    horizon: str,
    calibrator: IsotonicCalibrationResult,
) -> tuple[float, float, float]:
    """Transform raw_score → (calibrated_probability, band_lower, band_upper).

    Bands are placeholder (returned equal to calibrated_probability) until
    L5-E populates band derivation from bootstrap_se_distribution. Per
    spec §5.RM-6.1.1 lines 1232-1234.

    Clipped to [0, 1] via sklearn IsotonicRegression ``out_of_bounds='clip'``
    per spec §5.RM-6.5 test #6.
    """
    if not np.isfinite(raw_score):
        raise ValueError(
            f"raw_score must be finite; got {raw_score!r}"
        )
    calibrated = float(
        calibrator.sklearn_model.predict(np.array([raw_score]))[0]
    )
    # Defensive clip in case sklearn returns float outside [0, 1] due to
    # numerical edge cases.
    calibrated = max(0.0, min(1.0, calibrated))
    # Placeholder bands per spec §5.RM-6.1.1 line 1234: (cal, cal, cal)
    # until L5-E populates band derivation.
    return calibrated, calibrated, calibrated


__all__ = [
    "CDRS_DRAWDOWN_THRESHOLDS_DEFAULT",
    "COOLDOWN_DAYS_DEFAULT",
    "CalibratorKey",
    "HorizonLabel",
    "IsotonicCalibrationResult",
    "SAHM_RULE_TRIGGER_THRESHOLD",
    "ScoreType",
    "YIELD_CURVE_INVERSION_TRIGGER_MIN_CONSECUTIVE_MONTHS",
    "build_event_labels",
    "calibrate_raw_score",
    "fit_isotonic_calibrators",
    "should_recalibrate",
]
