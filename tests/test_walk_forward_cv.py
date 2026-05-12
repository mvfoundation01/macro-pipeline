"""Layer 5-A — tests for ``macro_pipeline.analysis.walk_forward_cv``.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 §5.A.5 (test delta +12; 7 NEG / 5 POS).

Test inventory (mirrors §5.A.5 row order):
  1.  POS  test_expanding_window_yields_monotone_train_end
  2.  POS  test_rolling_20y_window_fixed_length
  3.  POS  test_horizon_dependent_step_size_matches_Q2_lock (parametrized × 4)
  4.  NEG  test_no_cross_fold_contamination_grep_audit (Standing Order #4)
  5.  POS  test_min_train_window_240_months_enforced
  6.  NEG  test_rejects_horizon_outside_1Y_3Y_5Y_10Y
  7.  NEG  test_rejects_inverted_train_test_boundary
  8.  NEG  test_rejects_overlapping_test_windows_within_schedule
  9.  NEG  test_rejects_gap_months_below_horizon_minimum
  10. POS  test_pit_safety_propagates_panel_sha256_to_schedule
  11. NEG  test_rejects_corrupt_panel_propagates_CacheValidationError
  12. NEG  test_rejects_panel_with_missing_months_gaps

NEG count: 4, 6, 7, 8, 9, 11, 12 = 7 NEG.
POS count: 1, 2, 3, 5, 10 = 5 POS.
NEG floor: 7/12 = 58% ≥ 50% required (§2.7).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from macro_pipeline.analysis.walk_forward_cv import (
    HORIZONS,
    STEP_SIZE_MONTHS,
    WalkForwardFold,
    WalkForwardSchedule,
    generate_all_schedules,
    generate_schedule,
)
from macro_pipeline.exceptions import CacheValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def panel_index_1912_2025() -> pd.DatetimeIndex:
    """Synthetic 1912-01 → 2025-01 monthly panel index (1357 months)."""
    return pd.date_range("1912-01-01", "2025-01-01", freq="MS")


@pytest.fixture(scope="module")
def all_schedules(
    panel_index_1912_2025: pd.DatetimeIndex,
) -> tuple[WalkForwardSchedule, ...]:
    """All 8 schedules generated from the synthetic panel."""
    return generate_all_schedules(panel_index_1912_2025)


# ---------------------------------------------------------------------------
# Test 1 — POS: expanding-window train_end is monotone increasing
# ---------------------------------------------------------------------------

def test_expanding_window_yields_monotone_train_end(
    all_schedules: tuple[WalkForwardSchedule, ...],
) -> None:
    """§5.A.5 #1 — every consecutive (fold_i, fold_{i+1}) in an expanding
    schedule has fold_{i+1}.train_end > fold_i.train_end with train_start fixed."""
    expanding_schedules = [s for s in all_schedules if s.schedule_type == "expanding"]
    assert len(expanding_schedules) == 4  # 4 horizons
    for schedule in expanding_schedules:
        assert len(schedule.folds) >= 2, "need ≥2 folds to check monotonicity"
        train_start_anchor = schedule.folds[0].train_start
        for i in range(len(schedule.folds) - 1):
            assert schedule.folds[i + 1].train_end > schedule.folds[i].train_end, (
                f"{schedule.horizon} expanding: fold {i+1} train_end "
                f"{schedule.folds[i+1].train_end.date()} not > "
                f"fold {i} train_end {schedule.folds[i].train_end.date()}"
            )
            # train_start fixed for expanding.
            assert schedule.folds[i + 1].train_start == train_start_anchor, (
                f"{schedule.horizon} expanding: train_start drifted at fold {i+1}"
            )


# ---------------------------------------------------------------------------
# Test 2 — POS: rolling-20Y train window is fixed length (~7305 days ± 31)
# ---------------------------------------------------------------------------

def test_rolling_20y_window_fixed_length(
    all_schedules: tuple[WalkForwardSchedule, ...],
) -> None:
    """§5.A.5 #2 — every rolling-20Y fold has (train_end − train_start).days
    in [7305 − 31, 7305 + 31] (20Y in days, ±1 month calendar drift)."""
    rolling_schedules = [s for s in all_schedules if s.schedule_type == "rolling_20y"]
    assert len(rolling_schedules) == 4
    for schedule in rolling_schedules:
        for fold in schedule.folds:
            days = (fold.train_end - fold.train_start).days
            assert 7305 - 31 <= days <= 7305 + 31, (
                f"{schedule.horizon} rolling_20y fold {fold.fold_id}: "
                f"train window {days} days outside [7274, 7336]"
            )


# ---------------------------------------------------------------------------
# Test 3 — POS (parametrized × 4): step size matches Q2 lock per horizon
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "horizon, expected_step_months",
    [
        ("1Y", 1),
        ("3Y", 1),
        ("5Y", 12),
        ("10Y", 60),
    ],
)
def test_horizon_dependent_step_size_matches_Q2_lock(
    all_schedules: tuple[WalkForwardSchedule, ...],
    horizon: str,
    expected_step_months: int,
) -> None:
    """§5.A.5 #3 — step size between consecutive test_starts matches Q2 lock
    (1Y/3Y monthly; 5Y annual; 10Y 5Y-blocks). Parametrized across 4 horizons."""
    # Use expanding to check; rolling uses identical step-size policy.
    schedule = next(
        s for s in all_schedules
        if s.horizon == horizon and s.schedule_type == "expanding"
    )
    assert STEP_SIZE_MONTHS[horizon] == expected_step_months
    for i in range(len(schedule.folds) - 1):
        delta = schedule.folds[i + 1].test_start - schedule.folds[i].test_start
        expected_months = expected_step_months
        # Convert to calendar months via period arithmetic for robustness.
        actual_months = (
            (schedule.folds[i + 1].test_start.year - schedule.folds[i].test_start.year) * 12
            + (schedule.folds[i + 1].test_start.month - schedule.folds[i].test_start.month)
        )
        assert actual_months == expected_months, (
            f"{horizon} expanding fold {i}->{i+1}: test_start step "
            f"{actual_months} months, expected {expected_months}"
        )


# ---------------------------------------------------------------------------
# Test 4 — NEG: cross-fold contamination grep-audit (Standing Order #4)
# ---------------------------------------------------------------------------

def test_no_cross_fold_contamination_grep_audit(
    all_schedules: tuple[WalkForwardSchedule, ...],
) -> None:
    """§5.A.5 #4 + §2.5 audit #1 (Standing Order #4) — AST-walk over every
    fold in every schedule asserts ``train_end + gap_months ≤ test_start``.

    The dataclass ``__post_init__`` enforces this invariant per-fold; this
    test provides the empirical-claim verification proof (universal-claim
    audit per §2.5 + AP-16) by iterating ALL folds across ALL 8 schedules.
    Any violation would raise AssertionError; 0 violations expected.
    """
    violations: list[str] = []
    total_folds = 0
    for schedule in all_schedules:
        for fold in schedule.folds:
            total_folds += 1
            min_test_start = fold.train_end + pd.DateOffset(months=fold.gap_months)
            if fold.test_start < min_test_start:
                violations.append(
                    f"{schedule.horizon}/{schedule.schedule_type} fold "
                    f"{fold.fold_id}: train_end+gap={min_test_start.date()} "
                    f"> test_start={fold.test_start.date()}"
                )
    assert violations == [], (
        f"Standing Order #4 universal-claim audit FAILED: {len(violations)} "
        f"contamination violations across {total_folds} folds: "
        f"{violations[:5]}{'...' if len(violations) > 5 else ''}"
    )
    # Affirmative log so verification report can cite total fold count audited.
    assert total_folds > 0


# ---------------------------------------------------------------------------
# Test 5 — POS: minimum 240-month training window enforced everywhere
# ---------------------------------------------------------------------------

def test_min_train_window_240_months_enforced(
    all_schedules: tuple[WalkForwardSchedule, ...],
) -> None:
    """§5.A.5 #5 — every fold has n_nominal_train ≥ 240 (20Y minimum)."""
    for schedule in all_schedules:
        for fold in schedule.folds:
            assert fold.n_nominal_train >= 240, (
                f"{schedule.horizon}/{schedule.schedule_type} fold "
                f"{fold.fold_id}: n_nominal_train={fold.n_nominal_train} < 240"
            )


# ---------------------------------------------------------------------------
# Test 6 — NEG: rejects horizon outside {1Y, 3Y, 5Y, 10Y}
# ---------------------------------------------------------------------------

def test_rejects_horizon_outside_1Y_3Y_5Y_10Y(
    panel_index_1912_2025: pd.DatetimeIndex,
) -> None:
    """§5.A.5 #6 — ``generate_schedule(horizon='2Y', ...)`` raises ValueError."""
    with pytest.raises(ValueError, match="horizon must be one of"):
        generate_schedule(
            horizon="2Y",  # type: ignore[arg-type]  # intentional invalid input
            schedule_type="expanding",
            panel_index=panel_index_1912_2025,
        )


# ---------------------------------------------------------------------------
# Test 7 — NEG: rejects inverted train/test boundary in WalkForwardFold
# ---------------------------------------------------------------------------

def test_rejects_inverted_train_test_boundary() -> None:
    """§5.A.5 #7 — ``WalkForwardFold(train_start=2010, train_end=2020,
    test_start=2015, ...)`` raises ValueError (test_start inside train range)."""
    with pytest.raises(ValueError, match="(inverted boundary|must be >)"):
        WalkForwardFold(
            fold_id=0,
            horizon="5Y",
            schedule_type="expanding",
            train_start=pd.Timestamp("2010-01-01"),
            train_end=pd.Timestamp("2020-01-01"),
            test_start=pd.Timestamp("2015-01-01"),  # INSIDE train range
            test_end=pd.Timestamp("2016-01-01"),
            gap_months=60,
            n_nominal_train=120,
            n_eff_nonoverlap_train=2,
        )


# ---------------------------------------------------------------------------
# Test 8 — NEG: rejects overlapping test windows within a schedule
# ---------------------------------------------------------------------------

def test_rejects_overlapping_test_windows_within_schedule() -> None:
    """§5.A.5 #8 — constructing a ``WalkForwardSchedule`` whose folds have
    overlapping ``[test_start, test_end]`` raises ValueError.

    By-construction-impossible for ``generate_schedule`` outputs (step ≥ 1
    and test_end = test_start + step - 1), but the defensive guard in
    ``WalkForwardSchedule.__post_init__`` catches mis-construction in
    downstream callers.
    """
    # fold_a: standard valid fold. train_end + gap = 2004-12 + 60mo = 2009-12;
    # test_start=2010-01 ≥ 2009-12 ✓.
    fold_a = WalkForwardFold(
        fold_id=0,
        horizon="5Y",
        schedule_type="expanding",
        train_start=pd.Timestamp("1985-01-01"),
        train_end=pd.Timestamp("2004-12-01"),
        test_start=pd.Timestamp("2010-01-01"),
        test_end=pd.Timestamp("2010-12-01"),  # 12-month test partition for 5Y step
        gap_months=60,
        n_nominal_train=240,
        n_eff_nonoverlap_train=4,
    )
    # fold_b: contamination-valid but OVERLAPS fold_a at month 2010-12.
    # train_end + gap = 2005-12 + 60mo = 2010-12; test_start=2010-12 ✓ (equal OK).
    fold_b = WalkForwardFold(
        fold_id=1,
        horizon="5Y",
        schedule_type="expanding",
        train_start=pd.Timestamp("1986-01-01"),
        train_end=pd.Timestamp("2005-12-01"),
        test_start=pd.Timestamp("2010-12-01"),  # OVERLAPS fold_a.test_end (2010-12)
        test_end=pd.Timestamp("2011-11-01"),
        gap_months=60,
        n_nominal_train=240,
        n_eff_nonoverlap_train=4,
    )
    with pytest.raises(ValueError, match="overlapping test windows"):
        WalkForwardSchedule(
            horizon="5Y",
            schedule_type="expanding",
            folds=(fold_a, fold_b),
            panel_path="",
            panel_sha256="",
        )


# ---------------------------------------------------------------------------
# Test 9 — NEG: rejects gap_months below horizon minimum
# ---------------------------------------------------------------------------

def test_rejects_gap_months_below_horizon_minimum(
    panel_index_1912_2025: pd.DatetimeIndex,
) -> None:
    """§5.A.5 #9 — ``generate_schedule(horizon='5Y', gap_months=12)`` raises
    because 5Y requires gap ≥ 60 (= horizon_months) per §5.A.1.3."""
    with pytest.raises(ValueError, match="gap_months .* must be >= horizon_months|gap_months .* must be ≥ horizon_months"):
        generate_schedule(
            horizon="5Y",
            schedule_type="expanding",
            panel_index=panel_index_1912_2025,
            gap_months=12,  # below 5Y's 60-month minimum
        )


# ---------------------------------------------------------------------------
# Test 10 — POS: PIT-safety propagates panel_sha256 from cache sidecar
# ---------------------------------------------------------------------------

def test_pit_safety_propagates_panel_sha256_to_schedule(
    tmp_path: Path,
    panel_index_1912_2025: pd.DatetimeIndex,
) -> None:
    """§5.A.5 #10 — ``WalkForwardSchedule.panel_sha256`` equals the validated
    sidecar ``data_sha256`` when ``generate_schedule`` is invoked with
    ``panel_path``."""
    panel_path = tmp_path / "panel.parquet"
    # Write a small dummy parquet (panel content is opaque to the cv module;
    # only the SHA-256 digest matters for PIT-safety propagation).
    pd.DataFrame({"col": range(10)}).to_parquet(panel_path)

    digest = hashlib.sha256(panel_path.read_bytes()).hexdigest()
    sidecar = panel_path.with_suffix(panel_path.suffix + ".meta.json")
    sidecar.write_text(json.dumps({"data_sha256": digest}), encoding="utf-8")

    schedule = generate_schedule(
        horizon="5Y",
        schedule_type="expanding",
        panel_index=panel_index_1912_2025,
        panel_path=str(panel_path),
    )
    assert schedule.panel_sha256 == digest
    assert schedule.panel_path == str(panel_path)


# ---------------------------------------------------------------------------
# Test 11 — NEG: rejects corrupt panel (sha mismatch) with CacheValidationError
# ---------------------------------------------------------------------------

def test_rejects_corrupt_panel_propagates_CacheValidationError(
    tmp_path: Path,
    panel_index_1912_2025: pd.DatetimeIndex,
) -> None:
    """§5.A.5 #11 — panel sha256 mismatching sidecar raises CacheValidationError.

    Simulates the post-write integrity failure mode codified at L3.5b-T
    (cache atomicity sweep) and propagated through L5 per §5.A.2 item 5.
    """
    panel_path = tmp_path / "panel.parquet"
    pd.DataFrame({"col": range(10)}).to_parquet(panel_path)

    # Sidecar declares a stale / mismatched sha256.
    sidecar = panel_path.with_suffix(panel_path.suffix + ".meta.json")
    sidecar.write_text(
        json.dumps({"data_sha256": "00" * 32}),  # impossible-to-match digest
        encoding="utf-8",
    )

    with pytest.raises(CacheValidationError):
        generate_schedule(
            horizon="5Y",
            schedule_type="expanding",
            panel_index=panel_index_1912_2025,
            panel_path=str(panel_path),
        )


# ---------------------------------------------------------------------------
# Test 12 — NEG: rejects panel_index with month gaps
# ---------------------------------------------------------------------------

def test_rejects_panel_with_missing_months_gaps() -> None:
    """§5.A.5 #12 — ``generate_schedule`` raises ValueError if panel_index has
    month gaps (e.g., 1995-01 then 1995-03 with no 1995-02)."""
    # Build a non-monthly-contiguous index: 1990-01-01, 1990-02-01,
    # 1990-04-01 (missing 1990-03).
    gappy = pd.DatetimeIndex(
        [
            pd.Timestamp("1990-01-01"),
            pd.Timestamp("1990-02-01"),
            pd.Timestamp("1990-04-01"),  # GAP — missing 1990-03
        ]
    )
    with pytest.raises(ValueError, match="monthly contiguous"):
        generate_schedule(
            horizon="1Y",
            schedule_type="expanding",
            panel_index=gappy,
        )
