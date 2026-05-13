"""Layer 5-D — Drawdown probability conditional distributions.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.D.0 (metadata)
+ §5.D.1 (public API; lines 1506-1579) + §5.D.2 (pre-flight contract)
+ §5.D.3 (methodology rigor; v4 scrub: no raw nan) + §5.D.5 (twelve
tests v2/v3; eight NEG / four POS = 67% NEG) + §5.D.6 (Gate 23 - PASS
criteria) + §5.D.7 (proof contract; ten items).

Populates the ``drawdown_conditional_distribution`` slot on
``ScoredObservation`` (added at L5-RM-4; see
``scoring/scored_observation.py:105``).

Public API
----------
``DRAWDOWN_THRESHOLDS``         Module-level five-element constant per spec §5.D.1.
``DrawdownConditionalResult``   Frozen dataclass; one cell per (horizon × regime).
``fit_drawdown_conditionals``   Public entry point; returns sixteen-cell dict.

Method (per spec §5.D.1 + §5.D.1.2 + §5.D.1.3)
----------------------------------------------
* Empirical exceedance frequency per cell:
  ``exceedance_probability['DD>=X%'] = count(drawdown <= -X%) / n_obs``
* Wilson 95% interval per cell per threshold via
  ``models/signal_probability.wilson_95_ci`` (spec test #9 reference).
* Bootstrap SE per cell per threshold: B=1000 resamples seeded via
  ``np.random.default_rng(random_seed)``.
* Cell sparsity v3 three-state taxonomy (spec §5.D.1.3 step 3):
    - ``"production"``       : ``n_eff >= 10`` AND ``interval_width < 0.30``
    - ``"production"`` (flagged) : ``n_eff >= 10`` AND ``0.30 <= width < 0.50``
    - ``"diagnostic_only"``  : ``n_eff < 10`` OR ``width >= 0.50`` (initial)
    - ``"pooled"``           : after hierarchical pooling succeeded
* Hierarchical pooling on initial ``"diagnostic_only"`` cells (Op-D-a
  approved 2026-05-13): linear regime adjacency ``expansion <->
  late-cycle <-> recession <-> indeterminate``. Pooling priority:
  (1) adjacent regime same horizon, (2) same regime adjacent shorter
  horizon, (3) fallback keep as ``"diagnostic_only"`` if all neighbours
  also sparse (Op-D-b approved).
* **NO cell ever returns raw nan** (spec §5.D.3 row "Consistency";
  closes ChatGPT v2 E.4 per v3 taxonomy).

Standing Order #4 contract — no fitting / no leakage
----------------------------------------------------
``fit_drawdown_conditionals`` is **post-hoc empirical scoring**: consumes
already-realised forward drawdowns + already-classified regime states.
No estimator instantiation, no fitting calls, no train-vs-test
partitioning inside this module. Verified at Gate 23 validator via
``inspect.getsource`` substring audit (closes R3 mitigation per
pre-flight 2026-05-13).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Literal, Mapping

import numpy as np
import pandas as pd

from macro_pipeline.analysis.r_squared_panel import HORIZONS
from macro_pipeline.models.signal_probability import wilson_95_ci


# Spec §5.D.1 (line ~1517): canonical five-element threshold tuple.
DRAWDOWN_THRESHOLDS: tuple[float, ...] = (0.10, 0.20, 0.35, 0.50, 0.65)

# Spec §5.D.1.3 step 3 thresholds for cell-sparsity classification.
_N_EFF_FLOOR: int = 10
_WIDTH_PRODUCTION_FLAG: float = 0.30   # n_eff>=10 AND width in [0.30, 0.50)
_WIDTH_DIAGNOSTIC_FLOOR: float = 0.50  # n_eff<10 OR width >= 0.50

# Spec §3.3 + scoring/scored_observation.py:40 — four valid regime states.
_VALID_REGIME_STATES: frozenset[str] = frozenset(
    {"expansion", "late-cycle", "recession", "indeterminate"}
)

# Op-D-a (Strategic-approved linear adjacency 2026-05-13). Tuple ordering
# defines the chain; index +/- 1 gives the regime neighbours.
_REGIME_LINEAR_CHAIN: tuple[str, ...] = (
    "expansion", "late-cycle", "recession", "indeterminate",
)

# Horizon adjacency for pooling step (2): shorter-horizon neighbour.
_HORIZON_LINEAR_CHAIN: tuple[str, ...] = ("1Y", "3Y", "5Y", "10Y")

# Spec §5.D.3 row "Standard error": default bootstrap iterations.
_BOOTSTRAP_ITERATIONS_DEFAULT: int = 1000


CellLabel = Literal["production", "diagnostic_only", "pooled"]


@dataclass(frozen=True)
class DrawdownConditionalResult:
    """One conditional-drawdown cell per (horizon, regime_state).

    Fifteen fields per spec §5.D.1 v3 cleanup. The v2
    ``hierarchical_pooling_applied: bool`` was REMOVED in v3 (redundant
    with ``cell_label == 'pooled'``); spec test #11 v4 amendment
    explicitly verifies its absence on the dataclass.
    """

    horizon: str                                          # "1Y" | "3Y" | "5Y" | "10Y"
    regime_state: str                                     # "expansion" | "late-cycle" | "recession" | "indeterminate"
    n_obs: int                                            # historical analog count
    drawdown_thresholds: tuple[float, ...]                # = DRAWDOWN_THRESHOLDS
    exceedance_probability: dict[str, float]              # {"DD>=10%": p, ..., "DD>=65%": p}
    bootstrap_se: dict[str, float]                        # SE per threshold from B=1000 bootstrap
    historical_anchor_dates: tuple[pd.Timestamp, ...]     # anchor dates feeding empirical
    n_eff_nonoverlap: int                                 # = n_obs // horizon_months
    event_count: dict[str, int]                           # raw event count per threshold
    wilson_interval_95: dict[str, tuple[float, float]]    # Wilson CI per threshold
    interval_width: dict[str, float]                      # CI upper - lower per threshold
    cell_label: CellLabel                                 # v3 three-state taxonomy
    pooling_neighbors: tuple[str, ...] = ()               # populated when cell_label == "pooled"


def _validate_drawdown_thresholds(thresholds: tuple[float, ...]) -> None:
    """Op-D-c (Strategic-approved 2026-05-13): callable validator for
    spec tests #5 + #6 to exercise threshold-rejection contracts.

    Raises
    ------
    ValueError
        If ``thresholds`` is empty, contains a non-positive value
        (test #5: negative threshold rejected), or contains a value
        > 1 (test #6: threshold above one rejected).
    """
    if not thresholds:
        raise ValueError("drawdown thresholds must be a non-empty tuple")
    for t in thresholds:
        if t <= 0.0:
            raise ValueError(
                f"drawdown threshold {t!r} must be positive "
                "(thresholds are positive-magnitude per spec §5.D.1.2)"
            )
        if t > 1.0:
            raise ValueError(
                f"drawdown threshold {t!r} must be <= 1.0 "
                "(thresholds are fractional magnitudes in (0, 1])"
            )


def fit_drawdown_conditionals(
    forward_drawdowns_by_horizon: Mapping[str, np.ndarray],
    regime_states: pd.Series,
    *,
    bootstrap_iterations: int = _BOOTSTRAP_ITERATIONS_DEFAULT,
    random_seed: int = 42,
) -> dict[tuple[str, str], DrawdownConditionalResult]:
    """Fit conditional drawdown CDF per (horizon, regime_state) cell
    (spec §5.D.1 v3 / §5.D.1.3 cell sparsity + hierarchical pooling).

    Parameters
    ----------
    forward_drawdowns_by_horizon
        Dict keyed by horizon label (one of ``"1Y" / "3Y" / "5Y" / "10Y"``)
        mapping to a 1-D ``np.ndarray`` of signed forward drawdown values
        (negative = price decline magnitude per spec §5.D.1.1).
    regime_states
        ``pd.Series`` of regime-state labels aligned element-wise to the
        forward-drawdown arrays. Must contain only values in
        ``{"expansion", "late-cycle", "recession", "indeterminate"}``
        (test #7 rejects unknown states).

    Keyword-only
    ------------
    bootstrap_iterations
        ``B`` for per-threshold bootstrap SE distribution. Default 1000
        (spec §5.D.3 row "Standard error").
    random_seed
        Determinism control; default 42 (spec test #8).

    Returns
    -------
    dict[tuple[str, str], DrawdownConditionalResult]
        Sixteen cells = four horizons × four regimes. Every cell
        populated; NO raw ``nan`` returned per spec §5.D.3 v4 scrub.

    Raises
    ------
    ValueError
        On unknown horizon key OR unknown regime state OR per-horizon
        length mismatch between forward-drawdown array and
        ``regime_states`` Series.
    """
    # ---- Input validation ----
    _validate_drawdown_thresholds(DRAWDOWN_THRESHOLDS)

    invalid_horizons = set(forward_drawdowns_by_horizon.keys()) - set(_HORIZON_LINEAR_CHAIN)
    if invalid_horizons:
        raise ValueError(
            f"forward_drawdowns_by_horizon has unknown horizon(s) "
            f"{sorted(invalid_horizons)}; must be subset of "
            f"{sorted(_HORIZON_LINEAR_CHAIN)} per spec §3.3"
        )

    bad_regimes = set(regime_states.astype(str)) - _VALID_REGIME_STATES
    if bad_regimes:
        raise ValueError(
            f"regime_states contains unknown state(s) {sorted(bad_regimes)}; "
            f"must be subset of {sorted(_VALID_REGIME_STATES)} per "
            "scoring/scored_observation.py:40"
        )

    for h, dd_arr in forward_drawdowns_by_horizon.items():
        if len(dd_arr) != len(regime_states):
            raise ValueError(
                f"horizon {h!r}: forward_drawdowns length "
                f"{len(dd_arr)} != regime_states length "
                f"{len(regime_states)}"
            )

    rng = np.random.default_rng(random_seed)
    regime_arr = regime_states.astype(str).to_numpy()
    anchor_index = (
        regime_states.index if isinstance(regime_states.index, pd.DatetimeIndex)
        else None
    )

    # ---- Stage A: per-cell sample partition + initial classification ----
    # cell_samples[(h, r)] = np.ndarray of drawdowns for (h, r) cell
    cell_samples: dict[tuple[str, str], np.ndarray] = {}
    cell_anchor_dates: dict[tuple[str, str], tuple[pd.Timestamp, ...]] = {}
    for h in _HORIZON_LINEAR_CHAIN:
        if h not in forward_drawdowns_by_horizon:
            # Horizon not provided: still produce four empty cells for that
            # horizon to keep the 16-cell invariant. Pooling will fill them
            # from neighbouring horizons.
            for r in _REGIME_LINEAR_CHAIN:
                cell_samples[(h, r)] = np.empty(0, dtype=float)
                cell_anchor_dates[(h, r)] = ()
            continue
        dd_arr = np.asarray(forward_drawdowns_by_horizon[h], dtype=float)
        for r in _REGIME_LINEAR_CHAIN:
            mask = (regime_arr == r) & np.isfinite(dd_arr)
            cell_samples[(h, r)] = dd_arr[mask]
            if anchor_index is not None:
                cell_anchor_dates[(h, r)] = tuple(anchor_index[mask])
            else:
                cell_anchor_dates[(h, r)] = ()

    # Stage B: compute cell metrics from sample (may be called twice — initial
    # + post-pooling — so factored into helper).
    def _compute_cell_metrics(
        horizon: str, regime: str, sample: np.ndarray,
    ) -> tuple[
        int,                       # n_obs
        int,                       # n_eff
        dict[str, int],            # event_count
        dict[str, float],          # exceedance_probability
        dict[str, tuple[float, float]],  # wilson_interval_95
        dict[str, float],          # interval_width
        dict[str, float],          # bootstrap_se
    ]:
        n_obs = int(len(sample))
        horizon_months = HORIZONS[horizon]
        n_eff = n_obs // horizon_months if horizon_months > 0 else 0

        event_count: dict[str, int] = {}
        exceedance: dict[str, float] = {}
        wilson_ci: dict[str, tuple[float, float]] = {}
        width: dict[str, float] = {}
        boot_se: dict[str, float] = {}
        for t in DRAWDOWN_THRESHOLDS:
            label = f"DD>={int(round(t * 100))}%"
            # Sign convention (spec §5.D.1.1 + §5.D.1.2): drawdown values
            # are negative price declines; threshold ``t`` is positive
            # magnitude. Event = drawdown ≤ -t.
            event_mask = sample <= -t
            ec = int(np.sum(event_mask))
            event_count[label] = ec
            exceedance[label] = float(ec / n_obs) if n_obs > 0 else 0.0
            # Wilson CI uses (effective event count, n_eff) per spec
            # §5.D.1.3 step 2. The autocorrelation correction reduces
            # n_obs (overlapping) to n_eff (non-overlapping); scale
            # event count proportionally to preserve the empirical
            # exceedance rate while widening the CI.
            if n_obs > 0 and n_eff > 0:
                p_hat = ec / n_obs
                ec_eff = min(int(round(p_hat * n_eff)), n_eff)
            else:
                ec_eff = 0
            lo, up = wilson_95_ci(ec_eff, max(n_eff, 0))
            wilson_ci[label] = (lo, up)
            width[label] = up - lo
            boot_se[label] = _bootstrap_threshold_se(
                sample, t, bootstrap_iterations, rng,
            )
        return n_obs, n_eff, event_count, exceedance, wilson_ci, width, boot_se

    # ---- Stage C: classify each cell + attempt pooling for sparse cells ----
    results: dict[tuple[str, str], DrawdownConditionalResult] = {}

    for h in _HORIZON_LINEAR_CHAIN:
        for r in _REGIME_LINEAR_CHAIN:
            sample = cell_samples[(h, r)]
            n_obs, n_eff, ec, exc, wci, wid, bse = _compute_cell_metrics(
                h, r, sample,
            )

            # Classify per spec §5.D.1.3 step 3.
            max_width = max(wid.values()) if wid else float("inf")
            if n_eff < _N_EFF_FLOOR or max_width >= _WIDTH_DIAGNOSTIC_FLOOR:
                initial_label: CellLabel = "diagnostic_only"
            else:
                initial_label = "production"

            cell_label: CellLabel = initial_label
            pooling_neighbors: tuple[str, ...] = ()

            # ---- Hierarchical pooling (Op-D-a + Op-D-b) ----
            if initial_label == "diagnostic_only":
                pooled_sample, pooled_neighbors = _try_hierarchical_pooling(
                    target=(h, r), cell_samples=cell_samples,
                )
                if pooled_sample is not None:
                    # Recompute metrics on pooled sample.
                    n_obs_p, n_eff_p, ec_p, exc_p, wci_p, wid_p, bse_p = (
                        _compute_cell_metrics(h, r, pooled_sample)
                    )
                    max_width_p = max(wid_p.values()) if wid_p else float("inf")
                    if max_width_p < _WIDTH_DIAGNOSTIC_FLOOR:
                        # Pool succeeded.
                        n_obs, n_eff, ec, exc, wci, wid, bse = (
                            n_obs_p, n_eff_p, ec_p, exc_p, wci_p, wid_p, bse_p,
                        )
                        cell_label = "pooled"
                        pooling_neighbors = pooled_neighbors
                    # else: pool didn't bring width below threshold; keep
                    # diagnostic_only per Op-D-b (no escalation).

            results[(h, r)] = DrawdownConditionalResult(
                horizon=h,
                regime_state=r,
                n_obs=n_obs,
                drawdown_thresholds=DRAWDOWN_THRESHOLDS,
                exceedance_probability=exc,
                bootstrap_se=bse,
                historical_anchor_dates=cell_anchor_dates[(h, r)],
                n_eff_nonoverlap=n_eff,
                event_count=ec,
                wilson_interval_95=wci,
                interval_width=wid,
                cell_label=cell_label,
                pooling_neighbors=pooling_neighbors,
            )

    return results


def _try_hierarchical_pooling(
    target: tuple[str, str],
    cell_samples: dict[tuple[str, str], np.ndarray],
) -> tuple[np.ndarray | None, tuple[str, ...]]:
    """Op-D-a linear-adjacency hierarchical pooling per spec §5.D.1.3
    step 4.

    Pooling priority:
      (1) adjacent regime, same horizon (``_REGIME_LINEAR_CHAIN`` neighbours)
      (2) same regime, adjacent shorter horizon (``_HORIZON_LINEAR_CHAIN``
          shorter-direction neighbour)

    Returns
    -------
    tuple[np.ndarray | None, tuple[str, ...]]
        ``(pooled_sample, neighbours)`` if any neighbour merge produced a
        non-empty pool; ``(None, ())`` otherwise. The first non-empty
        pool encountered along the priority chain is returned (does NOT
        check width-improvement here; the caller decides whether to
        accept the pool by checking the recomputed Wilson width).
    """
    h_target, r_target = target
    base = cell_samples.get(target, np.empty(0, dtype=float))

    # Step 1: adjacent regime, same horizon.
    if r_target in _REGIME_LINEAR_CHAIN:
        idx = _REGIME_LINEAR_CHAIN.index(r_target)
        regime_neighbours = []
        if idx > 0:
            regime_neighbours.append(_REGIME_LINEAR_CHAIN[idx - 1])
        if idx + 1 < len(_REGIME_LINEAR_CHAIN):
            regime_neighbours.append(_REGIME_LINEAR_CHAIN[idx + 1])
        merged = base.copy()
        used: list[str] = []
        for r_nb in regime_neighbours:
            nb_sample = cell_samples.get((h_target, r_nb), np.empty(0))
            if nb_sample.size > 0:
                merged = np.concatenate([merged, nb_sample])
                used.append(f"{r_nb}x{h_target}")
        if used and merged.size > base.size:
            return merged, tuple(used)

    # Step 2: same regime, adjacent shorter horizon.
    if h_target in _HORIZON_LINEAR_CHAIN:
        idx = _HORIZON_LINEAR_CHAIN.index(h_target)
        if idx > 0:
            h_nb = _HORIZON_LINEAR_CHAIN[idx - 1]
            nb_sample = cell_samples.get((h_nb, r_target), np.empty(0))
            if nb_sample.size > 0:
                merged = np.concatenate([base, nb_sample])
                return merged, (f"{r_target}x{h_nb}",)

    return None, ()


def _bootstrap_threshold_se(
    sample: np.ndarray,
    threshold: float,
    bootstrap_iterations: int,
    rng: np.random.Generator,
) -> float:
    """Block-free residual bootstrap of the exceedance-probability SE
    for a single threshold.

    Resamples ``sample`` indices with replacement ``B`` times; computes
    exceedance fraction per resample; returns the SD of that
    distribution. Returns ``0.0`` if sample has zero observations
    (no SE definable). Returns ``0.0`` if ``bootstrap_iterations < 2``.
    """
    n = sample.size
    if n < 1 or bootstrap_iterations < 2:
        return 0.0
    se_dist = np.empty(bootstrap_iterations, dtype=float)
    for b in range(bootstrap_iterations):
        idx = rng.integers(0, n, size=n)
        resample = sample[idx]
        se_dist[b] = float(np.sum(resample <= -threshold) / n)
    return float(np.std(se_dist, ddof=1)) if bootstrap_iterations > 1 else 0.0


__all__ = [
    "DRAWDOWN_THRESHOLDS",
    "DrawdownConditionalResult",
    "fit_drawdown_conditionals",
]
