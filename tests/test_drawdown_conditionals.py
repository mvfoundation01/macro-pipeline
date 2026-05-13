"""Layer 5-D — tests for ``macro_pipeline.analysis.drawdown_conditionals``.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.D.5 (twelve
tests v2/v3; eight NEG / four POS = 67% NEG; supersedes stale §5.D.0
metadata "+8" anchor per Strategic disposition D-D-1 2026-05-13).

Test inventory (mirrors §5.D.5 row order; v4-amended tests retain their
spec-mandated names verbatim)
  1   POS         test_drawdown_thresholds_match_canonical_5_values
  2   POS-inv     test_exceedance_probability_monotone_with_threshold
  3   POS         test_per_horizon_regime_returns_16_cells
  4   NEG         test_cells_with_n_eff_below_10_or_width_above_0_5_labeled_diagnostic_only
  5   NEG         test_rejects_negative_drawdown_threshold_input
  6   NEG         test_rejects_drawdown_threshold_above_one
  7   NEG         test_rejects_regime_state_outside_4_valid_states
  8   NEG-inv     test_bootstrap_seeded_for_reproducibility
  9   POS         test_wilson_interval_computed_per_threshold
  10  NEG         test_diagnostic_only_label_at_n_eff_below_10_or_width_above_0_5
  11  POS+NEG     test_hierarchical_pooling_when_sparse_uses_cell_label_taxonomy
  12  NEG         test_no_raw_nan_in_drawdown_output_v3_taxonomy
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from macro_pipeline.analysis.drawdown_conditionals import (
    DRAWDOWN_THRESHOLDS,
    DrawdownConditionalResult,
    _validate_drawdown_thresholds,
    fit_drawdown_conditionals,
)
from macro_pipeline.models.signal_probability import wilson_95_ci


# ---------------------------------------------------------------------------
# Shared synthetic-fixture helper
# ---------------------------------------------------------------------------
def _build_synthetic_inputs(
    n_months: int = 1500,
    seed: int = 42,
    regime_weights: tuple[float, float, float, float] = (0.65, 0.18, 0.12, 0.05),
):
    """Build (forward_drawdowns_by_horizon, regime_states) with signed
    drawdowns regime-correlated (deeper in recession + late-cycle)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1900-01-01", periods=n_months, freq="MS")
    regimes = ("expansion", "late-cycle", "recession", "indeterminate")
    regime_arr = rng.choice(regimes, size=n_months, p=list(regime_weights))
    regime_states = pd.Series(regime_arr, index=idx)

    def _gen(h: str):
        base = rng.normal(-0.05, 0.10, n_months)
        base = np.where(regime_arr == "recession", base - 0.20, base)
        base = np.where(regime_arr == "late-cycle", base - 0.05, base)
        return np.clip(base, -0.95, 0.0)

    forward = {h: _gen(h) for h in ("1Y", "3Y", "5Y", "10Y")}
    return forward, regime_states


# ---------------------------------------------------------------------------
# Test #1 — POS
# ---------------------------------------------------------------------------
def test_drawdown_thresholds_match_canonical_5_values():
    """Spec §5.D.5 test #1: ``DRAWDOWN_THRESHOLDS == (0.10, 0.20, 0.35,
    0.50, 0.65)``."""
    assert DRAWDOWN_THRESHOLDS == (0.10, 0.20, 0.35, 0.50, 0.65)


# ---------------------------------------------------------------------------
# Test #2 — POS-invariant
# ---------------------------------------------------------------------------
def test_exceedance_probability_monotone_with_threshold():
    """Spec §5.D.5 test #2: per cell,
    ``P(DD>=10%) >= P(DD>=20%) >= ... >= P(DD>=65%)`` since
    ``{DD >= 65%} subset of {DD >= 50%} subset of ...``."""
    forward, regime_states = _build_synthetic_inputs(n_months=1500)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_drawdown_conditionals(
            forward, regime_states, bootstrap_iterations=20,
        )
    for (h, r), cell in results.items():
        probs = [
            cell.exceedance_probability[f"DD>={int(t * 100)}%"]
            for t in DRAWDOWN_THRESHOLDS
        ]
        for i in range(len(probs) - 1):
            assert probs[i] >= probs[i + 1], (
                f"cell ({h}, {r}): monotonicity violated at index {i}: "
                f"probs[{i}]={probs[i]} < probs[{i + 1}]={probs[i + 1]}"
            )


# ---------------------------------------------------------------------------
# Test #3 — POS
# ---------------------------------------------------------------------------
def test_per_horizon_regime_returns_16_cells():
    """Spec §5.D.5 test #3: 4 horizons × 4 regimes = 16 cells in result."""
    forward, regime_states = _build_synthetic_inputs(n_months=1500)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_drawdown_conditionals(
            forward, regime_states, bootstrap_iterations=20,
        )
    horizons = {"1Y", "3Y", "5Y", "10Y"}
    regimes = {"expansion", "late-cycle", "recession", "indeterminate"}
    expected_keys = {(h, r) for h in horizons for r in regimes}
    assert set(results.keys()) == expected_keys
    assert len(results) == 16


# ---------------------------------------------------------------------------
# Test #4 — NEG
# ---------------------------------------------------------------------------
def test_cells_with_n_eff_below_10_or_width_above_0_5_labeled_diagnostic_only():
    """Spec §5.D.5 test #4: ``n_eff < 10 OR interval_width >= 0.5`` →
    ``cell_label == "diagnostic_only"`` (BEFORE pooling can rescue).

    Construct a sparse cell at 10Y horizon (n_eff inherently ≤ 12 over
    a 1500-month panel with regime stratification) where pooling
    cannot bring width below 0.50.
    """
    forward, regime_states = _build_synthetic_inputs(n_months=1500)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_drawdown_conditionals(
            forward, regime_states, bootstrap_iterations=20,
        )
    # At 10Y horizon, n_eff stays small even after pooling — at least
    # one such cell remains "diagnostic_only" in the result.
    diagnostic_cells = [
        (h, r) for (h, r), cell in results.items()
        if cell.cell_label == "diagnostic_only"
    ]
    assert diagnostic_cells, (
        "expected at least one diagnostic_only cell at 10Y horizon "
        "where pooling could not rescue (n_eff <= 12 inherent)"
    )
    for h, r in diagnostic_cells:
        cell = results[(h, r)]
        max_width = max(cell.interval_width.values())
        # Either n_eff is below floor OR width is above threshold (the
        # disjunctive classifier from §5.D.1.3 step 3).
        assert cell.n_eff_nonoverlap < 10 or max_width >= 0.5, (
            f"cell ({h}, {r}) labeled diagnostic_only but n_eff="
            f"{cell.n_eff_nonoverlap} and max_width={max_width:.3f} "
            "do not satisfy the §5.D.1.3 step 3 classifier"
        )


# ---------------------------------------------------------------------------
# Test #5 — NEG
# ---------------------------------------------------------------------------
def test_rejects_negative_drawdown_threshold_input():
    """Spec §5.D.5 test #5: a negative threshold is rejected
    (Op-D-c Strategic disposition: ``_validate_drawdown_thresholds``
    is the callable contract for tests #5 + #6)."""
    with pytest.raises(ValueError, match=r"must be positive"):
        _validate_drawdown_thresholds((-0.10, 0.20))


# ---------------------------------------------------------------------------
# Test #6 — NEG
# ---------------------------------------------------------------------------
def test_rejects_drawdown_threshold_above_one():
    """Spec §5.D.5 test #6: a threshold above 1.0 is rejected."""
    with pytest.raises(ValueError, match=r"must be <= 1.0"):
        _validate_drawdown_thresholds((0.10, 1.5))


# ---------------------------------------------------------------------------
# Test #7 — NEG
# ---------------------------------------------------------------------------
def test_rejects_regime_state_outside_4_valid_states():
    """Spec §5.D.5 test #7: an unknown regime state raises."""
    forward, regime_states = _build_synthetic_inputs(n_months=300)
    bad = regime_states.copy()
    bad.iloc[0] = "alien"
    with pytest.raises(ValueError, match=r"unknown state"):
        fit_drawdown_conditionals(forward, bad, bootstrap_iterations=5)


# ---------------------------------------------------------------------------
# Test #8 — NEG-invariant
# ---------------------------------------------------------------------------
def test_bootstrap_seeded_for_reproducibility():
    """Spec §5.D.5 test #8: two seed=42 runs produce identical
    ``bootstrap_se`` element-wise per cell per threshold."""
    forward, regime_states = _build_synthetic_inputs(n_months=600)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r1 = fit_drawdown_conditionals(
            forward, regime_states, bootstrap_iterations=30, random_seed=42,
        )
        r2 = fit_drawdown_conditionals(
            forward, regime_states, bootstrap_iterations=30, random_seed=42,
        )
    assert set(r1.keys()) == set(r2.keys())
    for k in r1.keys():
        assert r1[k].bootstrap_se == r2[k].bootstrap_se, (
            f"cell {k}: bootstrap_se differs between identical-seed runs"
        )


# ---------------------------------------------------------------------------
# Test #9 — POS
# ---------------------------------------------------------------------------
def test_wilson_interval_computed_per_threshold():
    """Spec §5.D.5 test #9: ``wilson_interval_95[threshold]`` populated
    per cell per threshold; matches ``signal_probability.wilson_95_ci``.

    Verified via re-derivation: for a chosen cell, the effective event
    count ``round(p_hat * n_eff)`` and ``n_eff`` should reproduce the
    cell's Wilson interval when fed to ``wilson_95_ci`` directly.
    """
    forward, regime_states = _build_synthetic_inputs(n_months=1500)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_drawdown_conditionals(
            forward, regime_states, bootstrap_iterations=20,
        )
    # Verify Wilson interval populated for every threshold in every cell.
    for (h, r), cell in results.items():
        for t in DRAWDOWN_THRESHOLDS:
            label = f"DD>={int(t * 100)}%"
            assert label in cell.wilson_interval_95
            lo, up = cell.wilson_interval_95[label]
            assert isinstance(lo, float) and isinstance(up, float)
            assert 0.0 <= lo <= up <= 1.0, (
                f"cell ({h}, {r}), {label}: Wilson interval malformed "
                f"({lo}, {up})"
            )

    # Spot check: pick a production cell and re-derive Wilson from
    # public surface. Pooled cells reflect merged samples whose effective
    # event count is hidden from the caller, so the closed-form re-derivation
    # path covers only the non-pooled case.
    production_cells = [
        (h, r) for (h, r), c in results.items()
        if c.cell_label == "production"
    ]
    assert production_cells, "need at least one production cell for spot-check"
    h, r = production_cells[0]
    cell = results[(h, r)]
    for t in DRAWDOWN_THRESHOLDS:
        label = f"DD>={int(t * 100)}%"
        ec = cell.event_count[label]
        if cell.n_obs > 0:
            p_hat = ec / cell.n_obs
            ec_eff = min(int(round(p_hat * cell.n_eff_nonoverlap)),
                         cell.n_eff_nonoverlap)
            expected = wilson_95_ci(ec_eff, cell.n_eff_nonoverlap)
            stored = cell.wilson_interval_95[label]
            assert abs(stored[0] - expected[0]) < 1e-12
            assert abs(stored[1] - expected[1]) < 1e-12


# ---------------------------------------------------------------------------
# Test #10 — NEG
# ---------------------------------------------------------------------------
def test_diagnostic_only_label_at_n_eff_below_10_or_width_above_0_5():
    """Spec §5.D.5 test #10: sparse cells flagged correctly via the
    disjunctive classifier (n_eff < 10 OR width >= 0.5)."""
    forward, regime_states = _build_synthetic_inputs(n_months=1500)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_drawdown_conditionals(
            forward, regime_states, bootstrap_iterations=20,
        )
    # For each "diagnostic_only" cell, the classifier must hold.
    for (h, r), cell in results.items():
        if cell.cell_label == "diagnostic_only":
            max_w = max(cell.interval_width.values())
            assert cell.n_eff_nonoverlap < 10 or max_w >= 0.5
    # Conversely: production cells must satisfy the NON-sparse condition.
    for (h, r), cell in results.items():
        if cell.cell_label == "production":
            max_w = max(cell.interval_width.values())
            assert cell.n_eff_nonoverlap >= 10
            assert max_w < 0.5


# ---------------------------------------------------------------------------
# Test #11 — POS + NEG (v4 amended)
# ---------------------------------------------------------------------------
def test_hierarchical_pooling_when_sparse_uses_cell_label_taxonomy():
    """Spec §5.D.5 test #11 (v4 amended per §2.3 scrub).

    POS: at least one cell carries ``cell_label == "pooled"`` with
    ``len(pooling_neighbors) > 0`` after pooling rescues a sparse cell.

    NEG (v4): assert that the v2 ``hierarchical_pooling_applied`` bool
    was actually REMOVED from the dataclass per v3 cleanup
    (``not hasattr(cell, "hierarchical_pooling_applied")``).
    """
    forward, regime_states = _build_synthetic_inputs(n_months=1500)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_drawdown_conditionals(
            forward, regime_states, bootstrap_iterations=20,
        )
    pooled_cells = [
        (h, r) for (h, r), cell in results.items()
        if cell.cell_label == "pooled"
    ]
    assert pooled_cells, (
        "POS: expected at least one pooled cell after hierarchical "
        "pooling rescues a sparse cell on the synthetic fixture; got 0"
    )
    for h, r in pooled_cells:
        assert len(results[(h, r)].pooling_neighbors) > 0, (
            f"pooled cell ({h}, {r}): pooling_neighbors must be non-empty"
        )

    # NEG (v4): hierarchical_pooling_applied bool REMOVED in v3 cleanup.
    sparse_cell = results[pooled_cells[0]]
    assert not hasattr(sparse_cell, "hierarchical_pooling_applied"), (
        "v4 NEG: 'hierarchical_pooling_applied' bool should have been "
        "removed in v3 cleanup; redundant with cell_label == 'pooled'"
    )


# ---------------------------------------------------------------------------
# Test #12 — NEG
# ---------------------------------------------------------------------------
def test_no_raw_nan_in_drawdown_output_v3_taxonomy():
    """Spec §5.D.5 test #12 (v3 amended per §2.4 cleanup): no cell
    returns ``nan`` in ``exceedance_probability``; every cell has
    ``cell_label in {"production", "diagnostic_only", "pooled"}``."""
    forward, regime_states = _build_synthetic_inputs(n_months=1500)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        results = fit_drawdown_conditionals(
            forward, regime_states, bootstrap_iterations=20,
        )
    valid_labels = {"production", "diagnostic_only", "pooled"}
    for (h, r), cell in results.items():
        assert cell.cell_label in valid_labels, (
            f"cell ({h}, {r}): unknown cell_label={cell.cell_label!r}"
        )
        for label, p in cell.exceedance_probability.items():
            assert np.isfinite(p), (
                f"cell ({h}, {r}), {label}: raw nan in "
                f"exceedance_probability — v3 taxonomy violation"
            )
            assert 0.0 <= p <= 1.0, (
                f"cell ({h}, {r}), {label}: probability {p} outside [0, 1]"
            )
