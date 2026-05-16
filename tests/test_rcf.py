"""Layer 6-E — tests for ``macro_pipeline.ensemble.rcf``.

Spec ref: Strategic L6-E inline pre-flight (post-L6-D 2026-05-15) §6.
Reference Class Forecasting per Vision §6: 8D z-scored macro state
vector + cosine-similarity reference-class identification + Bayesian
shrinkage to long-run prior.

Test inventory (NEG ratio >= 50% per AP-AUTH-53 discipline):
   1. POS         test_macro_state_vector_basic_construction
   2. NEG         test_macro_state_vector_sanity_bound_violation
   3. NEG         test_macro_state_vector_nan_raises
   4. NEG         test_macro_state_vector_inf_raises
   5. NEG-inv     test_macro_state_vector_frozen
   6. POS-inv     test_macro_state_vector_as_array_order
   7. POS         test_standardize_basic
   8. NEG         test_standardize_missing_field_in_raw_values
   9. NEG         test_standardize_missing_column_in_panel
  10. NEG         test_standardize_insufficient_history
  11. NEG         test_standardize_zero_sd
  12. POS-inv     test_cosine_similarity_identical_states
  13. POS-inv     test_cosine_similarity_opposite_states
  14. POS-inv     test_cosine_similarity_orthogonal_states
  15. NEG         test_cosine_similarity_zero_norm_raises
  16. POS         test_find_reference_class_basic
  17. NEG         test_find_reference_class_n_neighbors_invalid
  18. NEG         test_find_reference_class_insufficient_panel
  19. NEG         test_find_reference_class_missing_columns
  20. NEG         test_reference_class_n_mismatch
  21. NEG-inv     test_reference_class_frozen
  22. POS-inv     test_bayesian_shrinkage_zero_n_eff_returns_prior
  23. POS-inv     test_bayesian_shrinkage_large_n_eff_approaches_estimate
  24. NEG         test_bayesian_shrinkage_negative_n_eff_raises
  25. NEG         test_bayesian_shrinkage_invalid_kappa_raises

NEG count: 2, 3, 4, 5, 8, 9, 10, 11, 15, 17, 18, 19, 20, 21, 24, 25 = 16 NEG-flavor.
POS count: 1, 6, 7, 12, 13, 14, 16, 22, 23 = 9 POS / POS-inv.
NEG floor: 16/25 = 64% >= 50% required (AP-AUTH-53).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from macro_pipeline.ensemble.rcf import (
    BAYESIAN_PRIOR_10Y_REAL_RETURN,
    DEFAULT_KAPPA,
    MACRO_STATE_FIELDS,
    InsufficientReferenceClassError,
    MacroStateVector,
    ReferenceClass,
    apply_bayesian_shrinkage,
    cosine_similarity,
    find_reference_class,
    standardize_macro_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_state(**overrides) -> MacroStateVector:
    """Build a valid MacroStateVector with default zeros; pass overrides."""
    defaults = {f: 0.0 for f in MACRO_STATE_FIELDS}
    defaults.update(overrides)
    return MacroStateVector(**defaults)


def _make_synthetic_panel(
    n_rows: int = 50,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a synthetic z-scored historical panel with the 8 columns."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1980-01-31", periods=n_rows, freq="ME")
    data = {f: rng.normal(0.0, 1.0, n_rows) for f in MACRO_STATE_FIELDS}
    return pd.DataFrame(data, index=dates)


def _make_raw_panel(n_rows: int = 50, seed: int = 42) -> pd.DataFrame:
    """Build a synthetic RAW historical panel with the 8 raw-stem columns."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1980-01-31", periods=n_rows, freq="ME")
    # Raw-stem columns (no _z suffix); arbitrary scales to test z-scoring.
    raw_stems = [f[: -len("_z")] for f in MACRO_STATE_FIELDS]
    data = {
        "cape": rng.normal(25.0, 5.0, n_rows),
        "yield_curve": rng.normal(1.0, 0.5, n_rows),
        "lei": rng.normal(100.0, 5.0, n_rows),
        "credit_spread": rng.normal(2.0, 0.5, n_rows),
        "sentiment": rng.normal(0.5, 0.2, n_rows),
        "breadth": rng.normal(0.6, 0.1, n_rows),
        "volatility": rng.normal(15.0, 5.0, n_rows),
        "concentration": rng.normal(0.25, 0.05, n_rows),
    }
    assert set(data.keys()) == set(raw_stems)
    return pd.DataFrame(data, index=dates)


# ===========================================================================
# Test 1 — POS — basic construction
# ===========================================================================


def test_macro_state_vector_basic_construction() -> None:
    """POS: valid MacroStateVector; all 8 fields preserved."""
    s = MacroStateVector(
        cape_z=1.5,
        yield_curve_z=-0.5,
        lei_z=0.0,
        credit_spread_z=2.0,
        sentiment_z=-1.0,
        breadth_z=0.5,
        volatility_z=-2.5,
        concentration_z=1.8,
    )
    assert s.cape_z == 1.5
    assert s.yield_curve_z == -0.5
    assert s.lei_z == 0.0
    assert s.credit_spread_z == 2.0
    assert s.sentiment_z == -1.0
    assert s.breadth_z == 0.5
    assert s.volatility_z == -2.5
    assert s.concentration_z == 1.8


# ===========================================================================
# Test 2 — NEG — sanity bound violation
# ===========================================================================


def test_macro_state_vector_sanity_bound_violation() -> None:
    """NEG: |z| > 10 raises (unit-error guard per Strategic PD3)."""
    with pytest.raises(ValueError, match="cape_z"):
        _make_valid_state(cape_z=15.0)
    with pytest.raises(ValueError, match="volatility_z"):
        _make_valid_state(volatility_z=-12.5)


# ===========================================================================
# Test 3 — NEG — NaN raises
# ===========================================================================


def test_macro_state_vector_nan_raises() -> None:
    """NEG: NaN field raises ValueError (finite check)."""
    with pytest.raises(ValueError, match="not finite"):
        _make_valid_state(cape_z=float("nan"))


# ===========================================================================
# Test 4 — NEG — inf raises
# ===========================================================================


def test_macro_state_vector_inf_raises() -> None:
    """NEG: infinite field raises ValueError."""
    with pytest.raises(ValueError, match="not finite"):
        _make_valid_state(sentiment_z=float("inf"))
    with pytest.raises(ValueError, match="not finite"):
        _make_valid_state(breadth_z=float("-inf"))


# ===========================================================================
# Test 5 — NEG-inv — frozen rejects mutation
# ===========================================================================


def test_macro_state_vector_frozen() -> None:
    """NEG-inv: MacroStateVector is frozen; mutation raises."""
    s = _make_valid_state(cape_z=1.0)
    with pytest.raises(Exception):
        s.cape_z = 2.0  # type: ignore[misc]


# ===========================================================================
# Test 6 — POS-inv — as_array preserves field order
# ===========================================================================


def test_macro_state_vector_as_array_order() -> None:
    """POS-inv: as_array returns values in MACRO_STATE_FIELDS order."""
    s = MacroStateVector(
        cape_z=1.0,
        yield_curve_z=2.0,
        lei_z=3.0,
        credit_spread_z=4.0,
        sentiment_z=5.0,
        breadth_z=6.0,
        volatility_z=7.0,
        concentration_z=8.0,
    )
    arr = s.as_array()
    assert arr.shape == (8,)
    np.testing.assert_array_equal(
        arr, np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    )
    # Confirm order matches MACRO_STATE_FIELDS
    for i, fname in enumerate(MACRO_STATE_FIELDS):
        assert arr[i] == getattr(s, fname)


# ===========================================================================
# Test 7 — POS — standardize basic
# ===========================================================================


def test_standardize_basic() -> None:
    """POS: raw values + panel produce a valid MacroStateVector."""
    panel = _make_raw_panel(n_rows=50)
    # Pick "current" raw values close to panel means to keep z-scores reasonable.
    raw_values = {
        "cape": 28.0,
        "yield_curve": 0.8,
        "lei": 102.0,
        "credit_spread": 2.2,
        "sentiment": 0.45,
        "breadth": 0.55,
        "volatility": 17.0,
        "concentration": 0.27,
    }
    s = standardize_macro_state(raw_values, panel)
    assert isinstance(s, MacroStateVector)
    # Each field finite (sanity check; full bound check is __post_init__)
    for f in MACRO_STATE_FIELDS:
        assert math.isfinite(getattr(s, f))


# ===========================================================================
# Test 8 — NEG — missing field in raw_values
# ===========================================================================


def test_standardize_missing_field_in_raw_values() -> None:
    """NEG: raw_values missing a required key raises ValueError."""
    panel = _make_raw_panel(n_rows=50)
    raw_values = {
        # missing 'cape'
        "yield_curve": 0.8,
        "lei": 102.0,
        "credit_spread": 2.2,
        "sentiment": 0.45,
        "breadth": 0.55,
        "volatility": 17.0,
        "concentration": 0.27,
    }
    with pytest.raises(ValueError, match="raw_values missing"):
        standardize_macro_state(raw_values, panel)


# ===========================================================================
# Test 9 — NEG — missing column in panel
# ===========================================================================


def test_standardize_missing_column_in_panel() -> None:
    """NEG: panel missing required column raises ValueError."""
    panel = _make_raw_panel(n_rows=50).drop(columns=["cape"])
    raw_values = {
        "cape": 28.0,
        "yield_curve": 0.8,
        "lei": 102.0,
        "credit_spread": 2.2,
        "sentiment": 0.45,
        "breadth": 0.55,
        "volatility": 17.0,
        "concentration": 0.27,
    }
    with pytest.raises(ValueError, match="historical_panel missing column"):
        standardize_macro_state(raw_values, panel)


# ===========================================================================
# Test 10 — NEG — insufficient history (<30 rows)
# ===========================================================================


def test_standardize_insufficient_history() -> None:
    """NEG: panel with < 30 rows in any column raises ValueError."""
    panel = _make_raw_panel(n_rows=20)  # Below INSUFFICIENT_HISTORY_THRESHOLD=30
    raw_values = {
        "cape": 28.0,
        "yield_curve": 0.8,
        "lei": 102.0,
        "credit_spread": 2.2,
        "sentiment": 0.45,
        "breadth": 0.55,
        "volatility": 17.0,
        "concentration": 0.27,
    }
    with pytest.raises(ValueError, match="insufficient historical data"):
        standardize_macro_state(raw_values, panel)


# ===========================================================================
# Test 11 — NEG — zero/negative SD
# ===========================================================================


def test_standardize_zero_sd() -> None:
    """NEG: constant column (sd = 0) raises ValueError."""
    panel = _make_raw_panel(n_rows=50)
    panel["cape"] = 25.0  # Constant — sd = 0
    raw_values = {
        "cape": 28.0,
        "yield_curve": 0.8,
        "lei": 102.0,
        "credit_spread": 2.2,
        "sentiment": 0.45,
        "breadth": 0.55,
        "volatility": 17.0,
        "concentration": 0.27,
    }
    with pytest.raises(ValueError, match="zero or negative sd"):
        standardize_macro_state(raw_values, panel)


# ===========================================================================
# Test 12 — POS-inv — cosine similarity of identical states is 1.0
# ===========================================================================


def test_cosine_similarity_identical_states() -> None:
    """POS-inv: cos(state, state) == 1.0."""
    s = _make_valid_state(cape_z=1.0, yield_curve_z=2.0, lei_z=-0.5)
    assert cosine_similarity(s, s) == pytest.approx(1.0)


# ===========================================================================
# Test 13 — POS-inv — cosine similarity of opposite states is -1.0
# ===========================================================================


def test_cosine_similarity_opposite_states() -> None:
    """POS-inv: cos(state, -state) == -1.0."""
    s_a = _make_valid_state(cape_z=1.0, yield_curve_z=2.0, lei_z=-0.5)
    s_b = _make_valid_state(cape_z=-1.0, yield_curve_z=-2.0, lei_z=0.5)
    assert cosine_similarity(s_a, s_b) == pytest.approx(-1.0)


# ===========================================================================
# Test 14 — POS-inv — orthogonal states have similarity 0.0
# ===========================================================================


def test_cosine_similarity_orthogonal_states() -> None:
    """POS-inv: orthogonal vectors (dot product = 0) have cos sim ≈ 0."""
    # cape_z=1.0 only; sentiment_z=1.0 only — orthogonal in 8D.
    s_a = _make_valid_state(cape_z=1.0)
    s_b = _make_valid_state(sentiment_z=1.0)
    assert cosine_similarity(s_a, s_b) == pytest.approx(0.0, abs=1e-12)


# ===========================================================================
# Test 15 — NEG — zero-norm raises
# ===========================================================================


def test_cosine_similarity_zero_norm_raises() -> None:
    """NEG: zero-vector state has undefined similarity; raises."""
    zero_state = _make_valid_state()  # All zeros by default
    other = _make_valid_state(cape_z=1.0)
    with pytest.raises(ValueError, match="Zero-norm"):
        cosine_similarity(zero_state, other)
    with pytest.raises(ValueError, match="Zero-norm"):
        cosine_similarity(other, zero_state)


# ===========================================================================
# Test 16 — POS — find_reference_class returns top-N sorted descending
# ===========================================================================


def test_find_reference_class_basic() -> None:
    """POS: find_reference_class returns top-N sorted descending by similarity."""
    panel = _make_synthetic_panel(n_rows=50)
    query = _make_valid_state(cape_z=1.0, yield_curve_z=-0.5, lei_z=0.3)
    ref = find_reference_class(query, panel, n_neighbors=5)
    assert isinstance(ref, ReferenceClass)
    assert ref.n_neighbors == 5
    assert len(ref.neighbors) == 5
    # Sorted descending
    sims = [s for _, s in ref.neighbors]
    assert sims == sorted(sims, reverse=True)
    # mean_similarity matches the top-5 mean
    assert ref.mean_similarity == pytest.approx(sum(sims) / 5)
    assert ref.query_state == query


# ===========================================================================
# Test 17 — NEG — n_neighbors < 1 raises
# ===========================================================================


def test_find_reference_class_n_neighbors_invalid() -> None:
    """NEG: n_neighbors < 1 raises ValueError."""
    panel = _make_synthetic_panel(n_rows=50)
    query = _make_valid_state()
    with pytest.raises(ValueError, match="n_neighbors must be >= 1"):
        find_reference_class(query, panel, n_neighbors=0)
    with pytest.raises(ValueError, match="n_neighbors must be >= 1"):
        find_reference_class(query, panel, n_neighbors=-3)


# ===========================================================================
# Test 18 — NEG — insufficient panel raises InsufficientReferenceClassError
# ===========================================================================


def test_find_reference_class_insufficient_panel() -> None:
    """NEG: panel with fewer rows than n_neighbors raises
    InsufficientReferenceClassError (subclass of ValueError)."""
    panel = _make_synthetic_panel(n_rows=3)
    query = _make_valid_state(cape_z=0.5)
    with pytest.raises(
        InsufficientReferenceClassError, match="need >= 10"
    ):
        find_reference_class(query, panel, n_neighbors=10)
    # Subclass: catching ValueError still catches
    panel2 = _make_synthetic_panel(n_rows=3)
    with pytest.raises(ValueError):
        find_reference_class(query, panel2, n_neighbors=10)


# ===========================================================================
# Test 19 — NEG — panel missing required columns raises
# ===========================================================================


def test_find_reference_class_missing_columns() -> None:
    """NEG: panel missing z-suffixed columns raises ValueError."""
    panel = _make_synthetic_panel(n_rows=50).drop(columns=["cape_z"])
    query = _make_valid_state()
    with pytest.raises(ValueError, match="missing columns"):
        find_reference_class(query, panel, n_neighbors=5)


# ===========================================================================
# Test 20 — NEG — ReferenceClass n_mismatch raises
# ===========================================================================


def test_reference_class_n_mismatch() -> None:
    """NEG: n_neighbors != len(neighbors) raises ValueError."""
    query = _make_valid_state(cape_z=1.0)
    timestamp_a = pd.Timestamp("2000-01-01")
    timestamp_b = pd.Timestamp("2001-01-01")
    with pytest.raises(ValueError, match="!= len"):
        ReferenceClass(
            neighbors=((timestamp_a, 0.9), (timestamp_b, 0.7)),
            n_neighbors=5,  # mismatch (actual len 2)
            mean_similarity=0.8,
            query_state=query,
        )


# ===========================================================================
# Test 21 — NEG-inv — ReferenceClass frozen
# ===========================================================================


def test_reference_class_frozen() -> None:
    """NEG-inv: ReferenceClass is frozen; mutation raises."""
    query = _make_valid_state(cape_z=1.0)
    ts = pd.Timestamp("2000-01-01")
    ref = ReferenceClass(
        neighbors=((ts, 0.9),),
        n_neighbors=1,
        mean_similarity=0.9,
        query_state=query,
    )
    with pytest.raises(Exception):
        ref.n_neighbors = 5  # type: ignore[misc]


# ===========================================================================
# Test 22 — POS-inv — Bayesian shrinkage n_eff=0 returns prior
# ===========================================================================


def test_bayesian_shrinkage_zero_n_eff_returns_prior() -> None:
    """POS-inv: n_eff=0 gives full weight to prior."""
    result = apply_bayesian_shrinkage(
        point_estimate=0.10,
        prior=BAYESIAN_PRIOR_10Y_REAL_RETURN,  # 0.065
        n_eff=0,
        kappa=DEFAULT_KAPPA,
    )
    assert result == pytest.approx(BAYESIAN_PRIOR_10Y_REAL_RETURN)


# ===========================================================================
# Test 23 — POS-inv — Bayesian shrinkage large n_eff approaches estimate
# ===========================================================================


def test_bayesian_shrinkage_large_n_eff_approaches_estimate() -> None:
    """POS-inv: n_eff >> kappa gives near-full weight to point estimate."""
    point = 0.10
    prior = 0.065
    # n_eff=10000 with kappa=10 -> weight_estimate = 10000/10010 ≈ 0.999
    result = apply_bayesian_shrinkage(
        point_estimate=point,
        prior=prior,
        n_eff=10_000,
        kappa=10,
    )
    # Result should be very close to point estimate; within (point - prior)/1000
    assert abs(result - point) < abs(point - prior) / 1000
    # And n_eff == kappa case: 50/50 weighting (sanity)
    eq = apply_bayesian_shrinkage(point, prior, n_eff=10, kappa=10)
    assert eq == pytest.approx((point + prior) / 2)


# ===========================================================================
# Test 24 — NEG — negative n_eff raises
# ===========================================================================


def test_bayesian_shrinkage_negative_n_eff_raises() -> None:
    """NEG: n_eff < 0 raises ValueError."""
    with pytest.raises(ValueError, match="n_eff must be non-negative"):
        apply_bayesian_shrinkage(
            point_estimate=0.10,
            prior=0.065,
            n_eff=-1,
            kappa=10,
        )


# ===========================================================================
# Test 25 — NEG — kappa < 1 raises
# ===========================================================================


def test_bayesian_shrinkage_invalid_kappa_raises() -> None:
    """NEG: kappa < 1 raises ValueError."""
    with pytest.raises(ValueError, match="kappa must be >= 1"):
        apply_bayesian_shrinkage(
            point_estimate=0.10,
            prior=0.065,
            n_eff=5,
            kappa=0,
        )
    with pytest.raises(ValueError, match="kappa must be >= 1"):
        apply_bayesian_shrinkage(
            point_estimate=0.10,
            prior=0.065,
            n_eff=5,
            kappa=-2,
        )
