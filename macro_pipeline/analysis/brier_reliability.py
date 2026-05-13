"""Layer 5-C — Brier score + reliability diagram + Murphy decomposition.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.C.0 (metadata)
+ §5.C.1 (public API; lines 1377-1415) + §5.C.2 (pre-flight contract)
+ §5.C.3 (methodology rigor) + §5.C.5 (eight tests; four NEG / four POS
= 50% floor) + §5.C.6 (Gate 22 — six PASS criteria) + §5.C.7 (proof
contract; ten items).

Public API
----------
``BinDiagnosticStatus``           Literal tri-state (KICK-3): ``"production"`` /
                                   ``"diagnostic_only"`` / ``"fallback_climatology"``.
``BrierDecomposition``            Frozen dataclass; seventeen fields after KICK-3
                                   (fourteen baseline + three no-default KICK-3 fields).
``compute_brier_per_horizon``     Legacy spec entry; v1 path with warning-only
                                   underpopulation signal; always emits
                                   ``bin_diagnostic_status="production"`` per the
                                   v1 contract (caller may inspect bin_counts to
                                   detect underpopulation).
``compute_brier_per_horizon_v2``  L5b-KICK-3 production wrapper; required no-default
                                   ``min_obs_per_bin`` kwarg + adaptive bin
                                   reduction + tri-state diagnostic status.

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

L5b-KICK-3 (tag ``l5b-kick-3-accept``, 2026-05-15) — adaptive reduction
----------------------------------------------------------------------
Closes the Codex 5.5 IMPORTANT reviewer flag ("L5-C: implement adaptive
bin reduction or emit an explicit diagnostic status consumed by
Gate 22; warning-only is weaker than spec.") via the AP-AUTH-53
reviewer-driven-kickoff-item pattern (third instance after KICK-1 +
KICK-2):

* ``compute_brier_per_horizon`` (legacy) preserved verbatim. v1 path
  still emits the warning-only signal when any nonempty bin has
  < ``_MIN_OBS_PER_BIN`` observations; the new ``bin_diagnostic_status``
  field is set to ``"production"`` by v1 unconditionally — caller
  may inspect ``bin_counts`` directly to detect underpopulation in the
  legacy path. This preserves spec §5.C.1 literal protection.
* ``compute_brier_per_horizon_v2`` (KICK-3 NEW) is the production-
  grade entry. Mirrors v1's positional contract plus one REQUIRED
  keyword-only argument with NO default: ``min_obs_per_bin``. The
  no-default contract forces caller intent — closes the Sxx-15
  catastrophic-state surface (production caller silently consuming
  warning-only output as production-grade).
* ``BrierDecomposition`` gained three no-default fields (KICK-3):
  ``bin_reduction_applied`` (bool), ``final_bin_count`` (int),
  ``bin_diagnostic_status`` (tri-state ``Literal``). Bare constructors
  without these fields raise ``TypeError`` (KICK-3 test #15 contract).
  Invalid status string raises ``ValueError`` from
  ``__post_init__`` (KICK-3 test #14 contract).
* Adaptive reduction algorithm (per spec §5.C expectation
  "bin count >= 30 or adaptive reduction documented"):

    1. If total observations < ``2 * min_obs_per_bin``: skip search,
       run v1 once at ``initial_n_bins``, set status =
       ``"fallback_climatology"``.
    2. Otherwise iterate ``candidate_n_bins`` from ``initial_n_bins``
       down to ``n_bins_floor`` (default ``2``) in unit steps. For
       each, run v1 with ``bootstrap_iterations=0`` (Op-K3-1
       suppression) and check whether every nonempty bin has
       >= ``min_obs_per_bin`` observations. If yes, accept this
       bin count, re-run v1 at that count WITH full bootstrap, set
       status = ``"production"``.
    3. If the loop exhausts without a successful candidate, re-run v1
       at ``n_bins_floor`` with full bootstrap, set status =
       ``"diagnostic_only"``.

  Convergence: the ``range(initial_n_bins, n_bins_floor - 1, -1)``
  iterator is BOUNDED — at most ``initial_n_bins - n_bins_floor + 1``
  iterations; cannot infinite-loop (Risk #1 closed by construction).
* Op-K3-1 (Strategic-approved 2026-05-15): bootstrap suppression
  during the reduction search avoids the worst-case
  ``9 x B = 9000`` resample cost that would otherwise be paid per
  horizon. Full bootstrap is enabled only on the winning iteration
  (or the floor iteration when the loop exhausts). Operational
  optimisation; no Result-field contract change.
* Gate 22 hard gate: criteria 7-9 (KICK-3 NEW) extend the validator
  via Option-Y signature inspection (v2 callable importable; v2
  required kwarg + dataclass KICK-3 fields all no-default; runtime
  tri-state probe reaches all three outcomes). The validator now
  distinguishes warning-only v1 from production-mandatory v2 at
  gate time, not just at runtime.

AP-AUTH-53 cited as governing pattern (codified at KICK-2 ACCEPT;
third instance now applied). No new AP-AUTH codification at KICK-3.

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
from typing import Literal

import numpy as np


# L5b-KICK-3 (tag ``l5b-kick-3-accept``, 2026-05-15): tri-state diagnostic
# status for the bin-underpopulation reviewer flag (Codex 5.5 IMPORTANT).
# Mirrors ``drawdown_conditionals.CellLabel`` precedent (line 89 of that
# module). Per AP-AUTH-53 step #3, the dataclass field carrying this
# value has no default — caller intent forced at construction time.
BinDiagnosticStatus = Literal[
    "production",
    "diagnostic_only",
    "fallback_climatology",
]
_VALID_BIN_DIAGNOSTIC_STATUSES: frozenset[str] = frozenset({
    "production",
    "diagnostic_only",
    "fallback_climatology",
})


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

    L5b-KICK-3 NEW fields (no-default per AP-AUTH-53 step #3):
      ``bin_reduction_applied``    True iff v2 wrapper's adaptive
                                   reduction loop fired at least once.
                                   v1 path always sets ``False``.
      ``final_bin_count``          The bin count the v2 algorithm
                                   settled on (equals initial ``n_bins``
                                   if reduction did not fire).
      ``bin_diagnostic_status``    Tri-state ``Literal``:
                                   ``"production"`` / ``"diagnostic_only"``
                                   / ``"fallback_climatology"``.
                                   ``__post_init__`` rejects any other
                                   string (KICK-3 NEG test #14 contract).
    """

    horizon: str
    brier_score: float
    brier_climatology: float                  # baseline using constant prior (= Uncertainty)
    brier_improvement: float                  # climatology − model
    reliability_term: float
    resolution_term: float
    uncertainty_term: float
    n_obs: int
    bin_reduction_applied: bool               # KICK-3: True iff v2 adaptive reduction fired; no default
    final_bin_count: int                      # KICK-3: bin count algorithm settled on; no default
    bin_diagnostic_status: BinDiagnosticStatus  # KICK-3: tri-state; no default (AP-AUTH-53 #3)
    n_bins: int = _DEFAULT_N_BINS
    bin_edges: tuple[float, ...] = _DEFAULT_BIN_EDGES
    bin_avg_predicted: np.ndarray = None      # length n_bins
    bin_avg_actual: np.ndarray = None         # length n_bins
    bin_counts: np.ndarray = None             # length n_bins
    bootstrap_se_distribution: np.ndarray = field(
        default_factory=lambda: np.zeros(0)
    )                                          # length bootstrap_iterations (default B=1000)

    def __post_init__(self) -> None:
        # KICK-3 NEG test #14 contract: tri-state validation enforced
        # at construction time. Mirrors L5-E test #6 z_value validator
        # precedent (frozen-dataclass __post_init__ is admissible).
        if self.bin_diagnostic_status not in _VALID_BIN_DIAGNOSTIC_STATUSES:
            raise ValueError(
                f"bin_diagnostic_status={self.bin_diagnostic_status!r} "
                f"must be one of {sorted(_VALID_BIN_DIAGNOSTIC_STATUSES)} "
                "(spec §5.C KICK-3 tri-state; AP-AUTH-53 step #3)"
            )


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
            bin_reduction_applied=False,        # KICK-3: v1 path never reduces
            final_bin_count=n_bins,             # KICK-3: equals initial
            bin_diagnostic_status="production", # KICK-3: v1 contract = production (warning is informational)
            n_bins=n_bins,
            bin_edges=bin_edges_tuple,
            bin_avg_predicted=bin_avg_predicted,
            bin_avg_actual=bin_avg_actual,
            bin_counts=bin_counts,
            bootstrap_se_distribution=bootstrap_se,
        )

    return results


def compute_brier_per_horizon_v2(
    calibrated_probabilities: dict[str, np.ndarray],
    forward_returns_binary: dict[str, np.ndarray],
    *,
    min_obs_per_bin: int,
    initial_n_bins: int = _DEFAULT_N_BINS,
    n_bins_floor: int = 2,
    bootstrap_iterations: int = _BOOTSTRAP_ITERATIONS_DEFAULT,
    random_seed: int = 42,
) -> dict[str, BrierDecomposition]:
    """L5b-KICK-3 production-grade adaptive-reduction wrapper around
    ``compute_brier_per_horizon``.

    Closes the Codex 5.5 IMPORTANT reviewer flag ("L5-C: implement
    adaptive bin reduction or emit an explicit diagnostic status
    consumed by Gate 22; warning-only is weaker than spec.") via the
    AP-AUTH-53 reviewer-driven-kickoff-item pattern (third instance):

    * Approach B (wrapper-pattern): v2 invokes v1 internally; v1 stays
      verbatim (spec §5.C.1 literal protection).
    * No-default required kwarg ``min_obs_per_bin``: forces caller
      intent (Sxx-15 catastrophic-state mitigation).
    * Per-horizon adaptive reduction loop: bounded
      ``range(initial_n_bins, n_bins_floor - 1, -1)`` — at most
      ``initial_n_bins - n_bins_floor + 1`` iterations; CANNOT infinite-
      loop (Risk #1 closed by construction).
    * Op-K3-1 (Strategic-approved 2026-05-15): during the reduction
      search, v1 is invoked with ``bootstrap_iterations=0`` to suppress
      the bootstrap cost; the FULL bootstrap is run only on the winning
      iteration (or the floor iteration when the loop exhausts). This
      avoids the worst-case ``9 × B = 9000`` resample cost without
      altering the Result-field contract.
    * Tri-state ``bin_diagnostic_status``:
        - ``"production"`` — algorithm found a viable bin count
          (all nonempty bins have ≥ ``min_obs_per_bin`` observations).
        - ``"diagnostic_only"`` — reduction loop exhausted at
          ``n_bins_floor`` but some bin still has < ``min_obs_per_bin``.
        - ``"fallback_climatology"`` — total observations <
          ``2 × min_obs_per_bin`` (cannot meaningfully bin at all even
          at the floor); v1 still runs at ``initial_n_bins`` to return
          climatology + brier_score, but the bin counts must be treated
          as diagnostic-only by downstream consumers.

    Parameters
    ----------
    calibrated_probabilities, forward_returns_binary
        Identical contract to v1 ``compute_brier_per_horizon``.

    Keyword-only (required, no default — AP-AUTH-53 step #3)
    --------------------------------------------------------
    min_obs_per_bin
        Per-bin observation floor below which adaptive reduction
        triggers. Spec §5.C.2 item 3 literal is ``30``; KICK-3 exposes
        this as the caller-supplied no-default kwarg per AP-AUTH-53.

    Keyword-only (defaulted)
    ------------------------
    initial_n_bins
        Starting bin count for the reduction search. Default ``10``
        (matches spec §5.C.1 dataclass default).
    n_bins_floor
        Minimum admissible bin count. Default ``2`` per Strategic
        disposition #7 ("minimum viable"). Below this we cannot
        compute the Murphy decomposition meaningfully.
    bootstrap_iterations
        Bootstrap B for the WINNING iteration only. Default
        ``1000`` per spec §5.C.3.
    random_seed
        Determinism control; default 42.

    Returns
    -------
    dict[str, BrierDecomposition]
        One Result per horizon. Each carries
        ``bin_diagnostic_status`` populated from the tri-state taxonomy
        above; ``bin_reduction_applied`` reflects whether the
        candidate_n_bins iterator descended below
        ``initial_n_bins``; ``final_bin_count`` records the bin count
        the algorithm settled on.

    Raises
    ------
    ValueError
        On the standard v1 validation surface (probability out of
        ``[0, 1]``, non-binary outcomes, horizon-key mismatch, length
        mismatch, zero event variance, or ``n_bins < 2``) — propagated
        from v1. Plus KICK-3-specific: ``min_obs_per_bin < 1``,
        ``n_bins_floor < 2``, or ``initial_n_bins < n_bins_floor``.

    Examples
    --------
    >>> import numpy as np
    >>> p = {"1Y": np.linspace(0.05, 0.95, 1000)}
    >>> y = {"1Y": (np.linspace(0.05, 0.95, 1000) > 0.5).astype(int)}
    >>> r = compute_brier_per_horizon_v2(
    ...     p, y, min_obs_per_bin=30, bootstrap_iterations=10,
    ... )
    >>> r["1Y"].bin_diagnostic_status
    'production'
    """
    # ---- KICK-3-specific input validation ----
    if min_obs_per_bin < 1:
        raise ValueError(
            f"min_obs_per_bin={min_obs_per_bin} must be >= 1"
        )
    if n_bins_floor < 2:
        raise ValueError(
            f"n_bins_floor={n_bins_floor} must be >= 2 "
            "(spec §5.C.5 test #8 floor; Murphy decomposition "
            "undefined below this)"
        )
    if initial_n_bins < n_bins_floor:
        raise ValueError(
            f"initial_n_bins={initial_n_bins} must be >= "
            f"n_bins_floor={n_bins_floor}"
        )

    # AP-AUTH-52 magic-number derivation: fallback_climatology threshold
    # is 2 × min_obs_per_bin per Strategic disposition #8
    # (when ``min_obs_per_bin=30`` this evaluates to 60 = 2 × 30).
    fallback_climatology_floor = 2 * min_obs_per_bin

    results: dict[str, BrierDecomposition] = {}

    # Iterate per-horizon (each horizon makes independent reduction
    # decisions based on its own observation density).
    for h in sorted(calibrated_probabilities.keys()):
        # Build single-horizon dict slices for v1 calls.
        p_h = calibrated_probabilities[h]
        y_h = forward_returns_binary[h]
        if h not in forward_returns_binary:
            # Defer the mismatch error to v1's validator (uniform error
            # surface).
            pass
        single_p = {h: p_h}
        single_y = {h: y_h}

        # ---- Edge case (a): fallback_climatology ----
        # Total observations strictly less than 2 × min_obs_per_bin
        # → cannot meaningfully bin at all. Run v1 once at
        # initial_n_bins (suppressing the underpopulation warning since
        # we are explicitly marking the result diagnostic-class).
        n_h = len(np.asarray(p_h))
        if n_h < fallback_climatology_floor:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                v1_dict = compute_brier_per_horizon(
                    single_p, single_y,
                    n_bins=initial_n_bins,
                    bootstrap_iterations=bootstrap_iterations,
                    random_seed=random_seed,
                )
            v1_result = v1_dict[h]
            results[h] = _rebuild_with_kick3_fields(
                v1_result,
                bin_reduction_applied=False,
                final_bin_count=initial_n_bins,
                bin_diagnostic_status="fallback_climatology",
            )
            continue

        # ---- Search loop (bounded; Risk #1 closed by construction) ----
        # Op-K3-1: suppress bootstrap during search; enable on winning
        # iteration only.
        winning_n_bins: int | None = None
        for candidate_n_bins in range(
            initial_n_bins, n_bins_floor - 1, -1,
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                probe_dict = compute_brier_per_horizon(
                    single_p, single_y,
                    n_bins=candidate_n_bins,
                    bootstrap_iterations=0,   # Op-K3-1 suppression
                    random_seed=random_seed,
                )
            probe = probe_dict[h]
            counts = probe.bin_counts
            nonempty_counts = counts[counts > 0]
            if (nonempty_counts >= min_obs_per_bin).all():
                winning_n_bins = candidate_n_bins
                break

        # ---- Determine outcome class ----
        if winning_n_bins is not None:
            # PRODUCTION path: re-run v1 at winning_n_bins WITH full bootstrap.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                final_dict = compute_brier_per_horizon(
                    single_p, single_y,
                    n_bins=winning_n_bins,
                    bootstrap_iterations=bootstrap_iterations,
                    random_seed=random_seed,
                )
            v1_result = final_dict[h]
            results[h] = _rebuild_with_kick3_fields(
                v1_result,
                bin_reduction_applied=(winning_n_bins != initial_n_bins),
                final_bin_count=winning_n_bins,
                bin_diagnostic_status="production",
            )
        else:
            # DIAGNOSTIC_ONLY path: loop exhausted at floor but still
            # underpopulated. Re-run at n_bins_floor with full bootstrap.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                floor_dict = compute_brier_per_horizon(
                    single_p, single_y,
                    n_bins=n_bins_floor,
                    bootstrap_iterations=bootstrap_iterations,
                    random_seed=random_seed,
                )
            v1_result = floor_dict[h]
            results[h] = _rebuild_with_kick3_fields(
                v1_result,
                bin_reduction_applied=True,
                final_bin_count=n_bins_floor,
                bin_diagnostic_status="diagnostic_only",
            )

    return results


def _rebuild_with_kick3_fields(
    v1_result: "BrierDecomposition",
    *,
    bin_reduction_applied: bool,
    final_bin_count: int,
    bin_diagnostic_status: BinDiagnosticStatus,
) -> "BrierDecomposition":
    """Rebuild a v1-produced ``BrierDecomposition`` with KICK-3 fields
    overridden.

    The frozen dataclass forbids in-place mutation; we construct a new
    Result mirroring the v1 fields verbatim, only replacing the three
    KICK-3 fields with the values supplied by the v2 wrapper's
    reduction outcome.
    """
    return BrierDecomposition(
        horizon=v1_result.horizon,
        brier_score=v1_result.brier_score,
        brier_climatology=v1_result.brier_climatology,
        brier_improvement=v1_result.brier_improvement,
        reliability_term=v1_result.reliability_term,
        resolution_term=v1_result.resolution_term,
        uncertainty_term=v1_result.uncertainty_term,
        n_obs=v1_result.n_obs,
        bin_reduction_applied=bin_reduction_applied,
        final_bin_count=final_bin_count,
        bin_diagnostic_status=bin_diagnostic_status,
        n_bins=v1_result.n_bins,
        bin_edges=v1_result.bin_edges,
        bin_avg_predicted=v1_result.bin_avg_predicted,
        bin_avg_actual=v1_result.bin_avg_actual,
        bin_counts=v1_result.bin_counts,
        bootstrap_se_distribution=v1_result.bootstrap_se_distribution,
    )


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
    "BinDiagnosticStatus",
    "BrierDecomposition",
    "compute_brier_per_horizon",
    "compute_brier_per_horizon_v2",
]
