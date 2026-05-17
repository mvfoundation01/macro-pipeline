"""Reference Class Forecasting (RCF) — Vision v2.1 §6 (+ L6-J D2 OOD upgrade).

Per Strategic L6-E inline pre-flight 2026-05-15 + L6-J pre-flight
2026-05-16 D2. L6-J closes ChatGPT R7 Finding #6 (C-8) by adding:

  - Minimum-similarity threshold (default 0.30; configurable)
  - Top-3-5 analogs reporting (Vision §6 BINDING requirement)
  - Sample boundary validation (1913 Fed era start; flag analogs that
    pre-date the institutional sample window)
  - Reference-class OOD flag (fires when <3 analogs above threshold)
  - Horizon-conditional + similarity-conditional kappa for the
    Bayesian shrinkage scale

Backward compatibility: new ReferenceClass fields default to neutral
values; existing callers unaffected. New find_reference_class
keyword arguments default to preserve L6-E behaviour.

Vision §6 mandates Reference Class Forecasting for every forecast:

  > Anchor to historical analogs (1913-present)
  > Report top 3-5 analogs with similarity scores
  > Document where current regime DIVERGES from each analog
  > Apply Bayesian shrinkage to long-run real return prior (~6.5% real)
  >   at 10Y horizon

  > Similarity scoring methodology: cosine similarity on standardized
  > macro state vector x = (CAPE_z, curve_z, LEI_z, credit_z,
  > sentiment_z, breadth_z, vol_z, concentration_z) using L2 norm in
  > 8-dimensional standardized space.

  > Authority: Tetlock & Gardner (2015) reference class methodology;
  > Kahneman (2011) Chapter 22-24.

Public API
----------
``MacroStateVector``               Frozen 8D z-scored state vector.
``ReferenceClass``                 Frozen RCF result (top-N neighbors).
``InsufficientReferenceClassError`` Raised when panel can't yield n_neighbors.
``standardize_macro_state``         Raw values + historical panel -> z-scored vector.
``cosine_similarity``               Pairwise similarity in [-1, 1].
``find_reference_class``            Top-N most-similar historical periods.
``apply_bayesian_shrinkage``        Shrink point estimate toward prior.
``BAYESIAN_PRIOR_10Y_REAL_RETURN``  0.065 per Vision §6.
``DEFAULT_KAPPA``                   10 (institutional default; tunable at L6-H).
``MACRO_STATE_FIELDS``              Tuple of the 8 z-suffixed field names.

Pure-function discipline (Strategic PD15)
-----------------------------------------
All four functions are pure: no I/O, no globals mutated, no side
effects, deterministic given inputs. The four constants
(``BAYESIAN_PRIOR_10Y_REAL_RETURN``, ``DEFAULT_KAPPA``,
``MACRO_STATE_DIMS``, ``INSUFFICIENT_HISTORY_THRESHOLD``) are read-only
module-level scalars.

Tuning notes
------------
- Sanity bound ``|z| > 10`` (Strategic PD3) is an institutional default
  designed to catch unit errors (e.g., passing percent values where
  z-scores are expected). Real Fed-era extremes (1932 deflation, 1979
  inflation) may approach but rarely exceed this threshold for the
  eight standardized macro dimensions. L6-H retrospective may relax
  if empirical calibration surfaces a false-positive case.
- ``DEFAULT_KAPPA = 10`` is an institutional default for Bayesian
  shrinkage scale; horizon-conditional tuning deferred to L6-H per
  Strategic PD11. Caller passes explicit ``kappa`` to override.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Module constants (Strategic L6-E pre-flight)
# ---------------------------------------------------------------------------

# Vision §6 long-run real return prior at 10Y horizon (DMS-anchored).
BAYESIAN_PRIOR_10Y_REAL_RETURN = 0.065

# Strategic PD11 institutional default shrinkage scale.
DEFAULT_KAPPA = 10

# Vision §6 8D macro state specification.
MACRO_STATE_DIMS = 8

# Strategic PD6 insufficient-history threshold (minimum rows per column).
INSUFFICIENT_HISTORY_THRESHOLD = 30

# Strategic PD2 + PD3 sanity bound (catches unit errors at MacroStateVector
# construction time).
MACRO_STATE_Z_SANITY_BOUND = 10.0

# L6-J D2 (ChatGPT R7 #6 / C-8) RCF OOD constants.
# Default minimum similarity threshold below which analogs are excluded
# from the top-k report (analog quality insufficient for reliable
# reference-class shrinkage).
DEFAULT_MIN_SIMILARITY_THRESHOLD = 0.30

# Vision §6 BINDING: report top 3-5 analogs. Default to 5; callers may
# request fewer down to 3.
DEFAULT_TOP_K_REPORTED = 5

# Vision §10 Fed-era institutional sample boundary. Analogs that pre-date
# this timestamp are flagged via `sample_boundary_violation=True`.
SAMPLE_START_BOUNDARY = pd.Timestamp("1913-01-01")

# Reference-class OOD trigger: fires when fewer than this many analogs
# exceed `min_similarity_threshold`. Default 3 = Vision §6 minimum
# (top 3 to 5 BINDING requirement).
RCF_OOD_MIN_NEIGHBORS_THRESHOLD = 3

# L6-J D2 horizon-conditional Bayesian shrinkage base kappa.
# Longer horizons have lower N_eff (Vision §10: 113 / 38 / 22 / 11
# non-overlapping windows for 1Y / 3Y / 5Y / 10Y), so kappa scales up
# to enforce more shrinkage toward the prior when the empirical
# evidence is weaker. Caller may override via explicit `kappa` arg
# to `apply_bayesian_shrinkage`.
BASE_KAPPA_BY_HORIZON: dict[int, float] = {
    1: 5.0,
    3: 8.0,
    5: 12.0,
    10: 20.0,
}

# Similarity-conditional kappa scaling floor. When mean_similarity_top_k
# is very low, kappa_eff inflates; this floor prevents division by zero
# / kappa_eff explosion when similarity approaches zero.
SIMILARITY_KAPPA_FLOOR = 0.10

# 8D macro state field names (z-scored). Order is fixed; ``as_array``
# returns values in this order; YAML/JSON serialization preserves this
# canonical ordering.
MACRO_STATE_FIELDS: Tuple[str, ...] = (
    "cape_z",
    "yield_curve_z",
    "lei_z",
    "credit_spread_z",
    "sentiment_z",
    "breadth_z",
    "volatility_z",
    "concentration_z",
)


# ---------------------------------------------------------------------------
# Exception class (Strategic PD8)
# ---------------------------------------------------------------------------


class InsufficientReferenceClassError(ValueError):
    """Raised when the historical panel cannot yield ``n_neighbors``.

    Subclass of ``ValueError`` per Strategic PD8. Distinguishes from
    generic ``ValueError`` for callers that want to handle the sparse-
    panel case specifically (e.g., fall back to a smaller ``n_neighbors``
    or surface a Vision §10 sample-size-honesty warning).
    """


# ---------------------------------------------------------------------------
# Frozen dataclasses (Strategic PD2 + PD9)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MacroStateVector:
    """Eight-dimensional z-scored macro state vector per Vision §6.

    All eight fields are z-scored against the Fed-era (1913-present)
    historical distribution of the corresponding raw macro variable.

    Strategic invariants (PD3 + PD4):
      - Each field must be finite (NaN/inf rejected).
      - Each field must satisfy ``|z| <= 10`` (sanity bound; catches
        unit errors at construction).
    """

    cape_z: float
    yield_curve_z: float
    lei_z: float
    credit_spread_z: float
    sentiment_z: float
    breadth_z: float
    volatility_z: float
    concentration_z: float

    def __post_init__(self) -> None:
        for name in MACRO_STATE_FIELDS:
            val = getattr(self, name)
            if not math.isfinite(val):
                raise ValueError(f"{name} not finite: {val}")
            if abs(val) > MACRO_STATE_Z_SANITY_BOUND:
                raise ValueError(
                    f"{name} z-score {val} exceeds |"
                    f"{MACRO_STATE_Z_SANITY_BOUND}|; verify standardization "
                    f"(unit error guard per Strategic PD3 + L6-E module "
                    f"docstring)"
                )

    def as_array(self) -> np.ndarray:
        """Return the eight z-scored values as a ``numpy.ndarray`` in
        canonical ``MACRO_STATE_FIELDS`` order.

        Used by ``cosine_similarity`` for dot-product computation.
        """
        return np.array(
            [getattr(self, f) for f in MACRO_STATE_FIELDS],
            dtype=float,
        )


@dataclass(frozen=True)
class ReferenceClass:
    """Result of reference-class identification per Vision §6 (+ L6-J D2 OOD).

    Stores top-N most-similar historical periods together with the query
    state, aggregate similarity statistics, and L6-J OOD diagnostics.

    Frozen invariants:
      - ``n_neighbors`` matches ``len(neighbors)``.
      - ``n_neighbors >= 1``.
      - ``mean_similarity`` finite + in [-1, 1].
      - L6-J D2: ``top_k_analogs`` length in [0, 10]; similarities
        finite + in [-1, 1]; ``mean_similarity_top_k`` finite + in
        [-1, 1]; ``min_similarity_threshold`` finite + in [0, 1].

    ``neighbors`` is stored as ``tuple[tuple[pd.Timestamp, float], ...]``
    (Strategic PD9) to preserve the frozen-dataclass immutability
    invariant.

    L6-J D2 OOD fields (ChatGPT R7 #6 closure)
    ------------------------------------------
    ``top_k_analogs``                 Top 3-5 above-threshold analogs
                                      (subset of ``neighbors``). Empty
                                      tuple when ``reference_class_ood``
                                      fires.
    ``mean_similarity_top_k``         Mean similarity across
                                      ``top_k_analogs``. 0.0 when empty.
    ``min_similarity_threshold``      Threshold used to filter analogs
                                      into ``top_k_analogs``. Defaults
                                      to neutral value when caller
                                      doesn't supply (backward compat).
    ``reference_class_ood``           Fires when
                                      ``len(top_k_analogs) < 3``;
                                      indicates analog evidence is too
                                      weak for reference-class shrinkage.
    ``sample_boundary_violation``     Fires when any neighbor predates
                                      ``SAMPLE_START_BOUNDARY`` (1913).
    """

    neighbors: Tuple[Tuple[pd.Timestamp, float], ...]
    n_neighbors: int
    mean_similarity: float
    query_state: MacroStateVector
    # L6-J D2 additions (default values preserve L6-E backward compat).
    top_k_analogs: Tuple[Tuple[pd.Timestamp, float], ...] = ()
    mean_similarity_top_k: float = 0.0
    min_similarity_threshold: float = DEFAULT_MIN_SIMILARITY_THRESHOLD
    reference_class_ood: bool = False
    sample_boundary_violation: bool = False

    def __post_init__(self) -> None:
        if self.n_neighbors != len(self.neighbors):
            raise ValueError(
                f"n_neighbors ({self.n_neighbors}) != len(neighbors) "
                f"({len(self.neighbors)})"
            )
        if self.n_neighbors < 1:
            raise ValueError(
                f"n_neighbors must be >= 1; got {self.n_neighbors}"
            )
        # L6-I D1 — explicit finite check (NaN bypasses range comparison
        # already raises via `<=` False-fall-through, but explicit check
        # produces a clearer error for NaN/inf inputs).
        if not math.isfinite(self.mean_similarity):
            raise ValueError(
                f"mean_similarity must be finite; got "
                f"{self.mean_similarity!r}"
            )
        if not (-1.0 <= self.mean_similarity <= 1.0):
            raise ValueError(
                f"mean_similarity {self.mean_similarity} outside [-1, 1]"
            )
        # L6-J D2 invariants.
        if len(self.top_k_analogs) > 10:
            raise ValueError(
                f"top_k_analogs length {len(self.top_k_analogs)} > 10 "
                f"(Vision §6 BINDING requires top 3-5; >10 implies "
                f"misconfigured top_k_reported)"
            )
        for analog_ts, analog_sim in self.top_k_analogs:
            if not math.isfinite(analog_sim):
                raise ValueError(
                    f"top_k_analog similarity must be finite; got "
                    f"{analog_sim!r}"
                )
            if not (-1.0 <= analog_sim <= 1.0):
                raise ValueError(
                    f"top_k_analog similarity {analog_sim} outside [-1, 1]"
                )
        if not math.isfinite(self.mean_similarity_top_k):
            raise ValueError(
                f"mean_similarity_top_k must be finite; got "
                f"{self.mean_similarity_top_k!r}"
            )
        if not (-1.0 <= self.mean_similarity_top_k <= 1.0):
            raise ValueError(
                f"mean_similarity_top_k {self.mean_similarity_top_k} "
                f"outside [-1, 1]"
            )
        if not math.isfinite(self.min_similarity_threshold):
            raise ValueError(
                f"min_similarity_threshold must be finite; got "
                f"{self.min_similarity_threshold!r}"
            )
        if not (0.0 <= self.min_similarity_threshold <= 1.0):
            raise ValueError(
                f"min_similarity_threshold {self.min_similarity_threshold} "
                f"outside [0, 1]"
            )


# ---------------------------------------------------------------------------
# Pure functions (Strategic PD15)
# ---------------------------------------------------------------------------


def standardize_macro_state(
    raw_values: dict,
    historical_panel: pd.DataFrame,
) -> MacroStateVector:
    """Z-score raw macro values against a historical panel.

    Per Strategic PD5: ``historical_panel`` has eight columns named with
    the raw stems (``cape`` / ``yield_curve`` / ``lei`` /
    ``credit_spread`` / ``sentiment`` / ``breadth`` / ``volatility`` /
    ``concentration``), indexed by ``pd.Timestamp``, with RAW (not
    z-scored) values.

    For each of the eight Vision §6 dimensions, the helper:
      1. Reads ``raw_values[raw_stem]`` (raises if missing).
      2. Reads ``historical_panel[raw_stem]`` (raises if missing).
      3. Drops NaN rows from the historical column.
      4. Requires at least ``INSUFFICIENT_HISTORY_THRESHOLD`` rows
         (Strategic PD6); raises otherwise.
      5. Computes mean + sample SD (``ddof=1``); raises if SD <= 0.
      6. Computes ``z = (raw - mean) / sd``.

    Returns a ``MacroStateVector`` whose construction-time invariants
    (``|z| <= 10``, finiteness) apply to the resulting z-scores.

    Parameters
    ----------
    raw_values
        Mapping ``raw_stem -> float``. Must contain all eight raw stems
        (the field names without the ``_z`` suffix).
    historical_panel
        ``pd.DataFrame`` with the eight raw-stem columns. Index is
        ``pd.Timestamp``; values are RAW (not z-scored).

    Returns
    -------
    MacroStateVector
        With all eight z-scored fields populated.

    Raises
    ------
    ValueError
        Missing key in ``raw_values``, missing column in
        ``historical_panel``, insufficient history (< 30 rows), or
        zero/negative SD.
    """
    z_values: dict = {}
    for field in MACRO_STATE_FIELDS:
        raw_stem = field[: -len("_z")]
        if raw_stem not in raw_values:
            raise ValueError(
                f"raw_values missing key: {raw_stem!r} (needed for "
                f"{field})"
            )
        if raw_stem not in historical_panel.columns:
            raise ValueError(
                f"historical_panel missing column: {raw_stem!r}"
            )
        col = historical_panel[raw_stem].dropna()
        if len(col) < INSUFFICIENT_HISTORY_THRESHOLD:
            raise ValueError(
                f"insufficient historical data for {raw_stem!r}: "
                f"{len(col)} < {INSUFFICIENT_HISTORY_THRESHOLD}"
            )
        mean = col.mean()
        sd = col.std(ddof=1)
        if sd <= 0:
            raise ValueError(
                f"zero or negative sd for {raw_stem!r}: {sd}"
            )
        z_values[field] = float((raw_values[raw_stem] - mean) / sd)
    return MacroStateVector(**z_values)


def cosine_similarity(
    state_a: MacroStateVector,
    state_b: MacroStateVector,
) -> float:
    """Cosine similarity between two ``MacroStateVector`` instances.

    Returns ``dot(a, b) / (||a|| * ||b||)`` in ``[-1.0, 1.0]``.

    Raises
    ------
    ValueError
        If either input has zero L2 norm (similarity undefined).
    """
    a = state_a.as_array()
    b = state_b.as_array()
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0 or norm_b == 0:
        raise ValueError(
            "Zero-norm state vector; cosine similarity undefined"
        )
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_reference_class(
    current_state: MacroStateVector,
    historical_panel: pd.DataFrame,
    n_neighbors: int = 10,
    *,
    min_similarity_threshold: float = DEFAULT_MIN_SIMILARITY_THRESHOLD,
    top_k_reported: int = DEFAULT_TOP_K_REPORTED,
) -> ReferenceClass:
    """Identify the top-N most-similar historical periods.

    Computes ``cosine_similarity`` between ``current_state`` and each
    valid row of the historical panel, then returns the top-N highest-
    similarity matches sorted descending.

    Parameters
    ----------
    current_state
        Query ``MacroStateVector`` (already z-scored against the same
        baseline as ``historical_panel``).
    historical_panel
        ``pd.DataFrame`` with the eight columns named by
        ``MACRO_STATE_FIELDS`` (already z-scored); index is
        ``pd.Timestamp``.
    n_neighbors
        Number of top-similar periods to return (default 10).

    Returns
    -------
    ReferenceClass
        With neighbors sorted descending by similarity, plus
        ``mean_similarity`` across the top-N.

    Raises
    ------
    ValueError
        ``n_neighbors < 1`` or historical_panel missing required
        columns.
    InsufficientReferenceClassError
        Panel has fewer valid rows than ``n_neighbors`` (subclass of
        ``ValueError``; callers may catch specifically per Strategic
        PD8).
    """
    if n_neighbors < 1:
        raise ValueError(f"n_neighbors must be >= 1; got {n_neighbors}")
    # L6-J D2 input validation.
    if not math.isfinite(min_similarity_threshold):
        raise ValueError(
            f"min_similarity_threshold must be finite; got "
            f"{min_similarity_threshold!r}"
        )
    if not (0.0 <= min_similarity_threshold <= 1.0):
        raise ValueError(
            f"min_similarity_threshold must be in [0, 1]; got "
            f"{min_similarity_threshold}"
        )
    if not (1 <= top_k_reported <= 10):
        raise ValueError(
            f"top_k_reported must be in [1, 10]; got {top_k_reported}"
        )

    missing = [
        f for f in MACRO_STATE_FIELDS if f not in historical_panel.columns
    ]
    if missing:
        raise ValueError(
            f"historical_panel missing columns: {missing}"
        )

    panel = historical_panel.dropna(subset=list(MACRO_STATE_FIELDS))
    if len(panel) < n_neighbors:
        raise InsufficientReferenceClassError(
            f"historical_panel has {len(panel)} valid rows; need "
            f">= {n_neighbors}"
        )

    similarities: list = []
    for date_idx, row in panel.iterrows():
        try:
            historical_state = MacroStateVector(
                **{f: float(row[f]) for f in MACRO_STATE_FIELDS}
            )
            sim = cosine_similarity(current_state, historical_state)
            similarities.append((date_idx, sim))
        except ValueError:
            # Skip rows that violate MacroStateVector invariants (e.g.,
            # |z| > 10 sanity-bound trip) or have zero-norm.
            continue

    if len(similarities) < n_neighbors:
        raise InsufficientReferenceClassError(
            f"Only {len(similarities)} valid historical rows after "
            f"filtering; need >= {n_neighbors}"
        )

    similarities.sort(key=lambda x: x[1], reverse=True)
    top_n: Tuple[Tuple[pd.Timestamp, float], ...] = tuple(
        similarities[:n_neighbors]
    )
    mean_sim = float(sum(s for _, s in top_n) / n_neighbors)

    # L6-J D2 — top-k above-threshold filtering + OOD diagnostics.
    above_threshold = [
        (ts, sim) for ts, sim in top_n if sim >= min_similarity_threshold
    ]
    top_k: Tuple[Tuple[pd.Timestamp, float], ...] = tuple(
        above_threshold[:top_k_reported]
    )
    mean_sim_top_k = (
        float(sum(s for _, s in top_k) / len(top_k)) if top_k else 0.0
    )
    rc_ood = len(top_k) < RCF_OOD_MIN_NEIGHBORS_THRESHOLD

    # Sample boundary check: any neighbor predating 1913 = institutional
    # sample boundary violation per Vision §10 Fed-era discipline.
    sample_bound_violation = any(
        pd.Timestamp(ts) < SAMPLE_START_BOUNDARY for ts, _ in top_n
    )

    return ReferenceClass(
        neighbors=top_n,
        n_neighbors=n_neighbors,
        mean_similarity=mean_sim,
        query_state=current_state,
        top_k_analogs=top_k,
        mean_similarity_top_k=mean_sim_top_k,
        min_similarity_threshold=min_similarity_threshold,
        reference_class_ood=rc_ood,
        sample_boundary_violation=sample_bound_violation,
    )


def compute_horizon_conditional_kappa(
    horizon: int,
    mean_similarity_top_k: float,
    base_kappa: float | None = None,
) -> float:
    """L6-J D2 — Vision §6 + §10 horizon + similarity-conditional kappa.

    Longer horizons + weaker analogs both shrink the empirical estimate
    further toward the prior. Kappa scales:

      kappa_eff = base_kappa(horizon) / max(mean_similarity_top_k,
                                            SIMILARITY_KAPPA_FLOOR)

    The denominator floor (``SIMILARITY_KAPPA_FLOOR = 0.10``) prevents
    explosion when similarity approaches zero. With high similarity
    (~0.85) at 10Y: kappa_eff = 20.0 / 0.85 ≈ 23.5. With low similarity
    (0.20) at 10Y: kappa_eff = 20.0 / 0.20 = 100.0 (strong prior pull).

    Parameters
    ----------
    horizon
        Forecast horizon; must be a key in ``BASE_KAPPA_BY_HORIZON``.
    mean_similarity_top_k
        Mean similarity across top-k analogs from
        ``ReferenceClass.mean_similarity_top_k``. Should be in [0, 1].
    base_kappa
        Optional override for the horizon's base kappa. ``None`` reads
        from ``BASE_KAPPA_BY_HORIZON[horizon]``.

    Returns
    -------
    float
        Effective kappa for ``apply_bayesian_shrinkage``.

    Raises
    ------
    KeyError
        ``horizon`` not in ``BASE_KAPPA_BY_HORIZON``.
    ValueError
        ``mean_similarity_top_k`` non-finite or outside [-1, 1].
        ``base_kappa`` non-finite or non-positive.
    """
    if not math.isfinite(mean_similarity_top_k):
        raise ValueError(
            f"mean_similarity_top_k must be finite; got "
            f"{mean_similarity_top_k!r}"
        )
    if not (-1.0 <= mean_similarity_top_k <= 1.0):
        raise ValueError(
            f"mean_similarity_top_k must be in [-1, 1]; got "
            f"{mean_similarity_top_k}"
        )
    if base_kappa is None:
        if horizon not in BASE_KAPPA_BY_HORIZON:
            raise KeyError(
                f"horizon {horizon} not in {sorted(BASE_KAPPA_BY_HORIZON.keys())}"
            )
        bk = BASE_KAPPA_BY_HORIZON[horizon]
    else:
        if not math.isfinite(base_kappa) or base_kappa <= 0:
            raise ValueError(
                f"base_kappa must be finite + positive; got "
                f"{base_kappa!r}"
            )
        bk = float(base_kappa)
    denom = max(mean_similarity_top_k, SIMILARITY_KAPPA_FLOOR)
    return bk / denom


def apply_bayesian_shrinkage(
    point_estimate: float,
    prior: float,
    n_eff: int,
    kappa: int = DEFAULT_KAPPA,
) -> float:
    """Bayesian shrinkage of ``point_estimate`` toward ``prior``.

    Returns the weighted combination::

        weight_estimate * point_estimate + weight_prior * prior

    where::

        weight_estimate = n_eff / (n_eff + kappa)
        weight_prior    = kappa / (n_eff + kappa)

    Per Vision §6 + §10 horizon-conditional shrinkage discipline. At
    10Y horizon Vision §6 specifies a 6.5% real return prior; the
    constant ``BAYESIAN_PRIOR_10Y_REAL_RETURN`` exposes that value for
    callers.

    Semantics
    ---------
    - ``n_eff = 0`` gives full weight to the prior (no data evidence).
    - ``n_eff >> kappa`` gives near-full weight to the point estimate.
    - ``n_eff = kappa`` weights both equally (50/50).

    ``n_eff`` is the effective sample size relevant to the point
    estimate's horizon. Callers (Strategic PD12) determine n_eff per
    Vision §10 ``N_eff = N / (1 + 2 * sum rho(k))`` per the
    application context.

    Parameters
    ----------
    point_estimate
        Empirical point estimate.
    prior
        Shrinkage target (e.g., ``BAYESIAN_PRIOR_10Y_REAL_RETURN``
        at 10Y).
    n_eff
        Effective sample size (non-negative integer).
    kappa
        Shrinkage scale (default ``DEFAULT_KAPPA = 10``; institutional
        default per Strategic PD11; tunable at L6-H retrospective).

    Returns
    -------
    float
        Shrunk estimate.

    Raises
    ------
    ValueError
        ``n_eff < 0`` or ``kappa < 1``.
    """
    if n_eff < 0:
        raise ValueError(f"n_eff must be non-negative; got {n_eff}")
    if kappa < 1:
        raise ValueError(f"kappa must be >= 1; got {kappa}")
    weight_estimate = n_eff / (n_eff + kappa)
    weight_prior = kappa / (n_eff + kappa)
    return float(
        weight_estimate * point_estimate + weight_prior * prior
    )
