"""Layer 5-C — Brier score + reliability diagram + Murphy decomposition.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.C.0 (metadata)
+ §5.C.1 (public API; lines 1377-1415) + §5.C.2 (pre-flight contract)
+ §5.C.3 (methodology rigor) + §5.C.5 (eight tests; four NEG / four POS
= 50% floor) + §5.C.6 (Gate 22 — six PASS criteria) + §5.C.7 (proof
contract; ten items).

Public API
----------
``BrierDecomposition``        Frozen dataclass; one decomposition per horizon.
``compute_brier_per_horizon`` Public entry point; per-horizon Brier + Murphy
                              decomposition + reliability diagram + bootstrap SE.

Method (per spec §5.C.3 row "Estimator")
----------------------------------------
* ``Brier        = (1/n) Σᵢ (pᵢ − yᵢ)²``
* ``Reliability  = (1/n) Σ_bins n_bin × (p̄_bin − ȳ_bin)²``
* ``Resolution   = (1/n) Σ_bins n_bin × (ȳ_bin − ȳ)²``
* ``Uncertainty  = ȳ × (1 − ȳ)``
* ``Brier ≡ Reliability − Resolution + Uncertainty`` (Murphy 1973;
  verified to ``1e-10`` precision in tests/test_brier_reliability.py
  test #2).

Climatology baseline (§5.C.1.1)
-------------------------------
``brier_climatology = Brier(p_const = ȳ, y) = ȳ × (1 − ȳ)``; equals
``Uncertainty`` term by construction.
``brier_improvement = brier_climatology − brier_score``; spec §5.C.6
criterion 3 + test #4 require ``brier_improvement > 0`` per horizon
(post-isotonic calibration beats climatology).

Standing Order #4 contract — no fitting / no leakage
----------------------------------------------------
``compute_brier_per_horizon`` is **post-hoc scoring**: consumes already-
calibrated probabilities + already-realised binary outcomes. No sklearn
estimator instantiation, no fitting calls, no train-vs-test
partitioning inside this module. Verified at Gate 22 validator via
``inspect.getsource`` substring audit (closes R4 mitigation per
pre-flight 2026-05-13).
"""
from __future__ import annotations

import inspect
import warnings
from dataclasses import dataclass, field

import numpy as np


# Spec §5.C.1 dataclass default — 11 edges produce 10 bins covering [0, 1].
_DEFAULT_BIN_EDGES: tuple[float, ...] = (
    0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
)
_DEFAULT_N_BINS: int = 10

# Spec §5.C.2 item 3 + §5.C.6 criterion 4: bin underpopulation threshold.
_MIN_OBS_PER_BIN: int = 30

# Spec §5.C.3: bootstrap default per row "Standard error".
_BOOTSTRAP_ITERATIONS_DEFAULT: int = 1000


@dataclass(frozen=True)
class BrierDecomposition:
    """Murphy 1973 decomposition: Brier = Reliability − Resolution + Uncertainty.

    Fields per spec §5.C.1 lines 1380-1397. The ``np.ndarray = None``
    typed defaults on ``bin_avg_predicted`` / ``bin_avg_actual`` /
    ``bin_counts`` follow the spec literal (Op-C-b approved 2026-05-13);
    ``compute_brier_per_horizon`` always populates them so ``None`` is
    unreachable in production usage.
    """

    horizon: str
    brier_score: float
    brier_climatology: float                  # baseline using constant prior (= Uncertainty)
    brier_improvement: float                  # climatology − model
    reliability_term: float
    resolution_term: float
    uncertainty_term: float
    n_obs: int
    n_bins: int = _DEFAULT_N_BINS
    bin_edges: tuple[float, ...] = _DEFAULT_BIN_EDGES
    bin_avg_predicted: np.ndarray = None      # length n_bins
    bin_avg_actual: np.ndarray = None         # length n_bins
    bin_counts: np.ndarray = None             # length n_bins
    bootstrap_se_distribution: np.ndarray = field(
        default_factory=lambda: np.zeros(0)
    )                                          # length bootstrap_iterations (default B=1000)


def compute_brier_per_horizon(
    calibrated_probabilities: dict[str, np.ndarray],
    forward_returns_binary: dict[str, np.ndarray],
    *,
    n_bins: int = _DEFAULT_N_BINS,
    bootstrap_iterations: int = _BOOTSTRAP_ITERATIONS_DEFAULT,
    random_seed: int = 42,
) -> dict[str, BrierDecomposition]:
    """Per-horizon Brier + Murphy decomposition + reliability diagram +
    bootstrap SE (spec §5.C.1 + §5.C.2 + §5.C.3).

    Parameters
    ----------
    calibrated_probabilities
        Dict keyed by horizon label mapping to a 1-D ``np.ndarray`` of
        calibrated probability values, each in ``[0, 1]``. Spec §3.3 row
        for the score_type controls which horizon set is meaningful;
        this function is score_type-agnostic — caller normalizes.
    forward_returns_binary
        Dict keyed by the same horizon labels mapping to a 1-D
        ``np.ndarray`` of binary outcomes ``{0, 1}`` aligned element-
        wise with ``calibrated_probabilities``.

    Keyword-only
    ------------
    n_bins
        Number of reliability-diagram bins. Default 10. Must be ``>= 2``
        (spec §5.C.5 test #8).
    bootstrap_iterations
        ``B`` for bootstrap SE distribution. Default 1000 (spec §5.C.3
        row "Standard error").
    random_seed
        Determinism control for bootstrap; default 42.

    Returns
    -------
    dict[str, BrierDecomposition]
        One ``BrierDecomposition`` per horizon present in both input
        dicts.

    Raises
    ------
    ValueError
        On (a) ``n_bins < 2``; (b) any calibrated probability outside
        ``[0, 1]``; (c) any forward-return value outside ``{0, 1}``;
        (d) horizon-key mismatch between the two dicts; (e) per-horizon
        length mismatch; (f) degenerate horizon with zero event variance
        (``ȳ ∈ {0, 1}``).

    Notes
    -----
    Standing Order #4 contract: this function is purely post-hoc — no
    fitting, no estimator instantiation, no leakage potential. The
    inputs are already-calibrated probabilities + already-realised
    outcomes. Verified at Gate 22 via ``inspect.getsource`` audit.
    """
    # ---- Input validation ----
    if n_bins < 2:
        raise ValueError(f"n_bins must be >= 2; got {n_bins}")

    p_horizons = set(calibrated_probabilities.keys())
    y_horizons = set(forward_returns_binary.keys())
    if p_horizons != y_horizons:
        only_p = p_horizons - y_horizons
        only_y = y_horizons - p_horizons
        raise ValueError(
            f"horizon keys mismatch between calibrated_probabilities "
            f"and forward_returns_binary; "
            f"in p only: {sorted(only_p)}; in y only: {sorted(only_y)}"
        )

    for h in sorted(p_horizons):
        p = np.asarray(calibrated_probabilities[h], dtype=float)
        y = np.asarray(forward_returns_binary[h])
        if len(p) != len(y):
            raise ValueError(
                f"horizon {h!r}: length mismatch "
                f"(calibrated_probabilities={len(p)}, "
                f"forward_returns_binary={len(y)})"
            )
        # Calibrated probabilities must be in [0, 1].
        if np.any((p < 0.0) | (p > 1.0) | ~np.isfinite(p)):
            raise ValueError(
                f"horizon {h!r}: calibrated_probabilities must lie in "
                f"[0, 1]; found min={float(np.nanmin(p))}, "
                f"max={float(np.nanmax(p))}"
            )
        # Binary outcomes must be {0, 1} (accept int or bool).
        y_int = np.asarray(y).astype(float)
        if not np.all((y_int == 0.0) | (y_int == 1.0)):
            raise ValueError(
                f"horizon {h!r}: forward_returns_binary must be in "
                f"{{0, 1}} (int or bool); found values outside set"
            )

    # ---- Per-horizon computation ----
    results: dict[str, BrierDecomposition] = {}
    bin_edges_arr = np.asarray(_DEFAULT_BIN_EDGES if n_bins == _DEFAULT_N_BINS
                               else np.linspace(0.0, 1.0, n_bins + 1))
    bin_edges_tuple = tuple(float(e) for e in bin_edges_arr)
    rng = np.random.default_rng(random_seed)

    for h in sorted(p_horizons):
        p = np.asarray(calibrated_probabilities[h], dtype=float)
        y = np.asarray(forward_returns_binary[h], dtype=float)
        n = len(p)

        y_mean = float(np.mean(y))
        if y_mean == 0.0 or y_mean == 1.0:
            raise ValueError(
                f"horizon {h!r}: forward_returns_binary has zero event "
                f"variance (y_mean={y_mean}); cannot compute Brier "
                "improvement against climatology baseline"
            )

        brier_score = float(np.mean((p - y) ** 2))
        uncertainty = float(y_mean * (1.0 - y_mean))
        brier_climatology = uncertainty  # Brier(p_const=ȳ, y) ≡ ȳ(1-ȳ)
        brier_improvement = brier_climatology - brier_score

        # Bin assignments: digitize with right=False yields indices in
        # [1, n_bins + 1]; subtract 1 to index into [0, n_bins]. Then
        # clip p == 1.0 (which lands in index n_bins) back to n_bins - 1.
        bin_idx = np.digitize(p, bin_edges_arr[1:-1], right=False)
        bin_idx = np.clip(bin_idx, 0, n_bins - 1)

        bin_avg_predicted = np.zeros(n_bins, dtype=float)
        bin_avg_actual = np.zeros(n_bins, dtype=float)
        bin_counts = np.zeros(n_bins, dtype=int)

        for b in range(n_bins):
            mask = (bin_idx == b)
            cnt = int(np.sum(mask))
            bin_counts[b] = cnt
            if cnt > 0:
                bin_avg_predicted[b] = float(np.mean(p[mask]))
                bin_avg_actual[b] = float(np.mean(y[mask]))
            else:
                bin_avg_predicted[b] = np.nan
                bin_avg_actual[b] = np.nan

        # Reliability + Resolution: skip empty bins (n_bin = 0 contributes 0).
        nonempty = bin_counts > 0
        reliability = float(np.sum(
            bin_counts[nonempty]
            * (bin_avg_predicted[nonempty] - bin_avg_actual[nonempty]) ** 2
        ) / n)
        resolution = float(np.sum(
            bin_counts[nonempty]
            * (bin_avg_actual[nonempty] - y_mean) ** 2
        ) / n)

        # §5.C.2 item 3: bin underpopulation warning if any nonempty
        # bin has <30 obs. (Empty bins are allowed — common when the
        # calibrated probability distribution is concentrated.)
        underpopulated = nonempty & (bin_counts < _MIN_OBS_PER_BIN)
        if np.any(underpopulated):
            warnings.warn(
                f"horizon {h!r}: {int(np.sum(underpopulated))} of "
                f"{int(np.sum(nonempty))} nonempty bins have <30 obs "
                "(spec §5.C.2 item 3 threshold); reliability diagram "
                "may be noisy. Consider adaptive bin reduction.",
                stacklevel=2,
            )

        # ---- Phase 3: bootstrap SE distribution (B resamples) ----
        bootstrap_se = _bootstrap_brier_se(
            p, y, bootstrap_iterations, rng,
        )

        results[h] = BrierDecomposition(
            horizon=h,
            brier_score=brier_score,
            brier_climatology=brier_climatology,
            brier_improvement=brier_improvement,
            reliability_term=reliability,
            resolution_term=resolution,
            uncertainty_term=uncertainty,
            n_obs=n,
            n_bins=n_bins,
            bin_edges=bin_edges_tuple,
            bin_avg_predicted=bin_avg_predicted,
            bin_avg_actual=bin_avg_actual,
            bin_counts=bin_counts,
            bootstrap_se_distribution=bootstrap_se,
        )

    return results


def _bootstrap_brier_se(
    p: np.ndarray,
    y: np.ndarray,
    bootstrap_iterations: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Bootstrap SE distribution for the Brier statistic.

    Resamples paired (p, y) indices with replacement B times; computes
    Brier per resample; returns the length-B distribution. Seeded via
    the caller's pre-constructed ``rng`` for spec §5.C.7 proof item 7
    determinism contract.
    """
    n = len(p)
    if n < 1 or bootstrap_iterations < 1:
        return np.zeros(0, dtype=float)
    se_dist = np.empty(bootstrap_iterations, dtype=float)
    for b in range(bootstrap_iterations):
        idx = rng.integers(0, n, size=n)
        se_dist[b] = float(np.mean((p[idx] - y[idx]) ** 2))
    return se_dist


__all__ = [
    "BrierDecomposition",
    "compute_brier_per_horizon",
]
