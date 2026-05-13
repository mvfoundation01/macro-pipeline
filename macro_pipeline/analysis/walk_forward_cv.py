"""Layer 5-A — Walk-forward cross-validation scaffold.

Produces deterministic walk-forward CV folds for OOS time-series validation
across 4 horizons (1Y / 3Y / 5Y / 10Y) using two complementary schedules:

  * expanding-window primary (train_start fixed at panel start)
  * rolling-20Y robustness (train_start advances; constant 240-month window)

Spec reference: ``LAYER_5_BUILD_SPEC.md`` v6 §5.A (tag ``layer5-spec-v6``).

Q-resolutions locked:
  * Q1 — expanding primary + rolling-20Y robustness (§5.A.4.1)
  * Q2 — horizon-dependent step size (§5.A.4.2)

Public API
----------
``WalkForwardFold``       Frozen dataclass; one fold per (horizon, schedule, fold_id).
``WalkForwardSchedule``   Frozen dataclass; one schedule per (horizon, schedule_type).
``generate_schedule``     Build one schedule.
``generate_all_schedules`` Build all 8 schedules (4 horizons × 2 schedule types).

Contamination invariant
-----------------------
``train_end + gap_months ≤ test_start`` for every fold (gap defaults to
``horizon_months`` per §5.A.1.3). Enforced by ``WalkForwardFold.__post_init__``
AND by per-schedule construction; the AST-walk audit
``test_no_cross_fold_contamination_grep_audit`` provides a third-line
Standing Order #4 universal-claim verification.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from macro_pipeline.analysis.r_squared_panel import HORIZONS
from macro_pipeline.cache import read_cache_validated_subdir
from macro_pipeline.exceptions import CacheValidationError

ScheduleType = Literal["expanding", "rolling_20y"]
HorizonLabel = Literal["1Y", "3Y", "5Y", "10Y"]

# §5.A.1.2 — Step-size policy (Q2 lock).
# Independence-vs-power balance per Pesaran (2007), Hyndman (2018).
STEP_SIZE_MONTHS: dict[str, int] = {
    "1Y": 1,
    "3Y": 1,
    "5Y": 12,
    "10Y": 60,
}

# §5.A.1.1 — Minimum training window (20 years; both schedules).
MIN_TRAIN_WINDOW_MONTHS_DEFAULT: int = 240

# §5.A.2 — Gate 18 fold-count targets per (horizon, schedule_type).
# Derived empirically from 1912+ Fed-era panel span (~1357 months by 2025-01)
# and the Q2-locked step-size policy in §5.A.1.2.
GATE18_FOLD_COUNT_TARGETS: dict[tuple[str, str], int] = {
    ("1Y", "expanding"):   30,
    ("1Y", "rolling_20y"): 30,
    ("3Y", "expanding"):   25,
    ("3Y", "rolling_20y"): 20,
    ("5Y", "expanding"):   12,
    ("5Y", "rolling_20y"): 10,
    ("10Y", "expanding"):  4,
    ("10Y", "rolling_20y"): 3,
}

_VALID_HORIZONS: frozenset[str] = frozenset(HORIZONS.keys())
_VALID_SCHEDULE_TYPES: frozenset[str] = frozenset({"expanding", "rolling_20y"})


@dataclass(frozen=True)
class WalkForwardFold:
    """One walk-forward CV fold for a (horizon, schedule_type) pair.

    Fields per ``LAYER_5_BUILD_SPEC.md`` §5.A.1.1. Construction invariants
    (raised as ``ValueError`` from ``__post_init__``):

      * ``train_start ≤ train_end``
      * ``test_start > train_end`` (with contamination gap)
      * ``train_end + gap_months ≤ test_start``  (calendar-month arithmetic)
      * ``test_end ≥ test_start``
      * ``gap_months ≥ 1``
      * ``n_nominal_train ≥ 1``
      * ``n_eff_nonoverlap_train == n_nominal_train // horizon_months``
        (consistency with §5.A.1.1 field definition)

    Defensive validation: the fold-generation routines (``generate_schedule``,
    ``generate_all_schedules``) enforce these invariants by construction; the
    ``__post_init__`` check catches accidental mis-constructions in tests or
    downstream callers.
    """

    fold_id: int
    horizon: HorizonLabel
    schedule_type: ScheduleType
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    gap_months: int
    n_nominal_train: int
    n_eff_nonoverlap_train: int

    def __post_init__(self) -> None:
        if self.horizon not in _VALID_HORIZONS:
            raise ValueError(
                f"horizon must be one of {sorted(_VALID_HORIZONS)}; "
                f"got {self.horizon!r}"
            )
        if self.schedule_type not in _VALID_SCHEDULE_TYPES:
            raise ValueError(
                f"schedule_type must be one of "
                f"{sorted(_VALID_SCHEDULE_TYPES)}; got {self.schedule_type!r}"
            )
        if self.gap_months < 1:
            raise ValueError(
                f"gap_months must be ≥ 1; got {self.gap_months}"
            )
        if self.train_start > self.train_end:
            raise ValueError(
                f"train_start ({self.train_start.date()}) must be ≤ "
                f"train_end ({self.train_end.date()})"
            )
        if self.test_start <= self.train_end:
            raise ValueError(
                f"test_start ({self.test_start.date()}) must be > "
                f"train_end ({self.train_end.date()}); inverted boundary"
            )
        # Cross-fold contamination invariant: train_end + gap_months ≤ test_start.
        # Calendar-month arithmetic via DateOffset.
        min_test_start = self.train_end + pd.DateOffset(months=self.gap_months)
        if self.test_start < min_test_start:
            raise ValueError(
                f"train_end + gap_months ({min_test_start.date()}) must be ≤ "
                f"test_start ({self.test_start.date()}); contamination gap "
                f"violated for horizon={self.horizon} gap_months={self.gap_months}"
            )
        if self.test_end < self.test_start:
            raise ValueError(
                f"test_end ({self.test_end.date()}) must be ≥ test_start "
                f"({self.test_start.date()})"
            )
        if self.n_nominal_train < 1:
            raise ValueError(
                f"n_nominal_train must be ≥ 1; got {self.n_nominal_train}"
            )
        # n_eff consistency per §5.A.1.1.
        horizon_months = HORIZONS[self.horizon]
        expected_n_eff = self.n_nominal_train // horizon_months
        if self.n_eff_nonoverlap_train != expected_n_eff:
            raise ValueError(
                f"n_eff_nonoverlap_train inconsistent: declared "
                f"{self.n_eff_nonoverlap_train}, expected "
                f"{expected_n_eff} = {self.n_nominal_train} // {horizon_months}"
            )


@dataclass(frozen=True)
class WalkForwardSchedule:
    """One full walk-forward schedule for a (horizon, schedule_type) pair.

    Fields:
        horizon: HorizonLabel
        schedule_type: ScheduleType
        folds: tuple of WalkForwardFold (length = fold count for this schedule)
        panel_path: path-like provenance string (empty if panel-only mode)
        panel_sha256: sha256 digest of the input panel cache (empty if panel-only)

    PIT-safety propagation (§5.A.2 item 5 + test #10): when constructed via
    a panel_path that passes cache validation, ``panel_sha256`` carries the
    sidecar ``data_sha256`` value forward to downstream consumers.
    """

    horizon: HorizonLabel
    schedule_type: ScheduleType
    folds: tuple[WalkForwardFold, ...]
    panel_path: str
    panel_sha256: str

    def __post_init__(self) -> None:
        if self.horizon not in _VALID_HORIZONS:
            raise ValueError(
                f"horizon must be one of {sorted(_VALID_HORIZONS)}; "
                f"got {self.horizon!r}"
            )
        if self.schedule_type not in _VALID_SCHEDULE_TYPES:
            raise ValueError(
                f"schedule_type must be one of "
                f"{sorted(_VALID_SCHEDULE_TYPES)}; got {self.schedule_type!r}"
            )
        # Defensive: assert no overlapping test windows within this schedule.
        # By construction (monotone step_months > 0 and test_end derived
        # from test_start + horizon_months) this should always hold;
        # detect mis-construction in downstream callers per test #8.
        for i in range(len(self.folds) - 1):
            curr = self.folds[i]
            nxt = self.folds[i + 1]
            if nxt.test_start <= curr.test_end:
                raise ValueError(
                    f"overlapping test windows in schedule "
                    f"{self.horizon}/{self.schedule_type}: "
                    f"fold {curr.fold_id} test_end={curr.test_end.date()} "
                    f">= fold {nxt.fold_id} test_start={nxt.test_start.date()}"
                )


def _assert_monthly_contiguous(panel_index: pd.DatetimeIndex) -> None:
    """Raise ValueError if panel_index has month gaps (e.g., missing 1995-02).

    The walk-forward schedule assumes a strict monthly cadence. Gaps invalidate
    fold-boundary calculations. Per §5.A.5 test #12.
    """
    if len(panel_index) < 2:
        return
    sorted_idx = panel_index.sort_values()
    # Compare each consecutive month delta to 1-month DateOffset arithmetic.
    for i in range(len(sorted_idx) - 1):
        a = sorted_idx[i]
        b = sorted_idx[i + 1]
        expected_next = a + pd.DateOffset(months=1)
        # Normalize to month for robust comparison (panel_index entries may
        # be month-start or month-end; both are valid as long as cadence is 1mo).
        if b.to_period("M") != expected_next.to_period("M"):
            raise ValueError(
                f"panel_index must be monthly contiguous; gap between "
                f"{a.date()} and {b.date()} (expected month "
                f"{expected_next.to_period('M')})"
            )


def _validate_panel_cache(panel_path: str | Path) -> str:
    """Validate the panel cache at panel_path; return the sha256 digest.

    Mirrors L3.5b-T cache atomicity discipline. Raises ``CacheValidationError``
    if the parquet's recomputed sha256 does not match the sidecar
    ``data_sha256`` (or any other sidecar invariant is violated).
    """
    path_obj = Path(panel_path)
    if not path_obj.exists():
        raise CacheValidationError(
            path=str(path_obj),
            reason="panel cache file does not exist",
        )

    # Compute sha256 of the parquet file.
    sha = hashlib.sha256()
    with path_obj.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    actual_sha = sha.hexdigest()

    # Locate the sidecar. Two naming conventions in use across the project:
    #   (a) L3D convention (cache.py write helpers; production):
    #       `r_squared_panel.parquet` → `r_squared_panel.meta.json`
    #       (i.e., `.with_suffix('.meta.json')`)
    #   (b) Multi-suffix convention (L5-A test fixture):
    #       `panel.parquet` → `panel.parquet.meta.json`
    #       (i.e., `.with_suffix('.parquet.meta.json')`)
    # Try (a) first (matches production L3D); fall back to (b) for fixture
    # compatibility per S-11 build-time discovery (commit <S-11-commit-sha>).
    sidecar_l3d = path_obj.with_suffix(".meta.json")
    sidecar_multi = path_obj.with_suffix(path_obj.suffix + ".meta.json")
    if sidecar_l3d.exists():
        sidecar = sidecar_l3d
    elif sidecar_multi.exists():
        sidecar = sidecar_multi
    else:
        sidecar = None  # type: ignore[assignment]

    if sidecar is None:
        raise CacheValidationError(
            path=str(path_obj),
            reason=(
                f"sidecar not found at {sidecar_l3d.name} (L3D convention) "
                f"or {sidecar_multi.name} (L5-A test-fixture convention)"
            ),
        )
    else:
        import json
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CacheValidationError(
                path=str(path_obj),
                reason=f"sidecar unreadable: {exc}",
            ) from exc
        sidecar_sha = meta.get("data_sha256")

    if sidecar_sha is None:
        raise CacheValidationError(
            path=str(path_obj),
            reason="sidecar missing data_sha256 field",
        )
    if sidecar_sha != actual_sha:
        raise CacheValidationError(
            path=str(path_obj),
            reason=(
                f"sha256 mismatch: sidecar={sidecar_sha[:12]}... "
                f"recomputed={actual_sha[:12]}..."
            ),
        )
    return actual_sha


def generate_schedule(
    horizon: HorizonLabel,
    schedule_type: ScheduleType,
    panel_index: pd.DatetimeIndex,
    *,
    min_train_window_months: int = MIN_TRAIN_WINDOW_MONTHS_DEFAULT,
    gap_months: int | None = None,
    panel_path: str | Path | None = None,
    panel_sha256: str = "",
) -> WalkForwardSchedule:
    """Generate a walk-forward schedule for ``horizon`` × ``schedule_type``.

    Parameters
    ----------
    horizon:
        One of {"1Y", "3Y", "5Y", "10Y"} (per ``HORIZONS`` from L3D).
    schedule_type:
        One of {"expanding", "rolling_20y"} per Q1 lock.
    panel_index:
        Monthly contiguous DatetimeIndex spanning the available data.
    min_train_window_months:
        Minimum training window length in months; defaults to 240 (20Y) for
        both schedule types per §5.A.1.1.
    gap_months:
        Contamination gap between ``train_end`` and ``test_start``. Defaults
        to ``horizon_months`` (1Y→12, 3Y→36, 5Y→60, 10Y→120). Overrides
        below this minimum raise ``ValueError`` per §5.A.5 test #9.
    panel_path:
        Optional path to the source panel parquet for PIT-safety propagation.
        If provided, the cache is validated (sha256 vs sidecar
        ``data_sha256``); failure raises ``CacheValidationError`` per test #11.
    panel_sha256:
        Optional explicit sha256 override (used when caller has already
        validated the cache via a different helper).

    Returns
    -------
    WalkForwardSchedule
        Immutable schedule with folds tuple + PIT-safety provenance.

    Raises
    ------
    ValueError
        On invalid horizon, schedule_type, gap_months override, panel_index
        not monthly contiguous, or fold construction invariant violation.
    CacheValidationError
        If ``panel_path`` is provided and cache validation fails.
    """
    # ---- Input validation (NEG test surface 6, 9, 12) ----
    if horizon not in _VALID_HORIZONS:
        raise ValueError(
            f"horizon must be one of {sorted(_VALID_HORIZONS)}; "
            f"got {horizon!r} (test #6 — reject horizon outside 1Y/3Y/5Y/10Y)"
        )
    if schedule_type not in _VALID_SCHEDULE_TYPES:
        raise ValueError(
            f"schedule_type must be one of "
            f"{sorted(_VALID_SCHEDULE_TYPES)}; got {schedule_type!r}"
        )
    if not isinstance(panel_index, pd.DatetimeIndex):
        raise TypeError(
            f"panel_index must be pd.DatetimeIndex; got {type(panel_index).__name__}"
        )
    _assert_monthly_contiguous(panel_index)

    horizon_months = HORIZONS[horizon]
    effective_gap = gap_months if gap_months is not None else horizon_months
    if effective_gap < horizon_months:
        raise ValueError(
            f"gap_months ({effective_gap}) must be ≥ horizon_months "
            f"({horizon_months}) for horizon={horizon} "
            f"(test #9 — reject gap_months below horizon minimum)"
        )

    step_months = STEP_SIZE_MONTHS[horizon]

    # ---- PIT-safety: cache validation if panel_path supplied ----
    resolved_sha256 = panel_sha256
    resolved_path = str(panel_path) if panel_path is not None else ""
    if panel_path is not None:
        resolved_sha256 = _validate_panel_cache(panel_path)

    # ---- Fold generation ----
    sorted_idx = panel_index.sort_values()
    panel_start = sorted_idx[0]
    panel_end = sorted_idx[-1]

    # Smallest valid first_test_start: needs ≥ min_train_window_months of
    # training data preceding the gap window. Derivation:
    #   expanding: n_nominal = (test_start - panel_start - gap) + 1 ≥ min_train
    #     ⇒ test_start ≥ panel_start + min_train + gap - 1
    #   rolling:   train_start = test_start - gap - (min_train - 1) ≥ panel_start
    #     ⇒ test_start ≥ panel_start + min_train + gap - 1   (identical)
    first_test_start = panel_start + pd.DateOffset(
        months=min_train_window_months + effective_gap - 1
    )

    folds: list[WalkForwardFold] = []
    current_test_start = first_test_start
    fold_id = 0
    while True:
        # Test partition spans `step_months` observations: [test_start, test_end].
        # Non-overlapping by construction (consecutive folds advance by step).
        # The "test partition" is the set of observation months whose forward-H
        # return is evaluated against the train-fit model.
        current_test_end = current_test_start + pd.DateOffset(
            months=step_months - 1
        )

        # Forward-H realization constraint: the last observation in the test
        # partition (at test_end) needs its H-month forward return realized
        # within the panel, so panel_end ≥ test_end + horizon_months.
        realization_end = current_test_end + pd.DateOffset(months=horizon_months)
        if realization_end > panel_end:
            break

        # train_end: the month BEFORE the gap window starts. With gap_months
        # of separation, train_end = test_start - gap_months (calendar).
        current_train_end = current_test_start - pd.DateOffset(
            months=effective_gap
        )

        # train_start: panel_start for expanding; test_start - (gap + 240mo)
        # for rolling-20Y (so that the training window is exactly 240 months
        # ending at train_end inclusive).
        if schedule_type == "expanding":
            current_train_start = panel_start
        else:  # rolling_20y
            current_train_start = current_train_end - pd.DateOffset(
                months=min_train_window_months - 1
            )

        # n_nominal_train: count of months in [train_start, train_end] inclusive.
        n_nominal = (
            (current_train_end.year - current_train_start.year) * 12
            + (current_train_end.month - current_train_start.month)
            + 1
        )
        n_eff = n_nominal // horizon_months

        fold = WalkForwardFold(
            fold_id=fold_id,
            horizon=horizon,
            schedule_type=schedule_type,
            train_start=current_train_start,
            train_end=current_train_end,
            test_start=current_test_start,
            test_end=current_test_end,
            gap_months=effective_gap,
            n_nominal_train=n_nominal,
            n_eff_nonoverlap_train=n_eff,
        )
        folds.append(fold)
        fold_id += 1
        current_test_start = current_test_start + pd.DateOffset(
            months=step_months
        )

    return WalkForwardSchedule(
        horizon=horizon,
        schedule_type=schedule_type,
        folds=tuple(folds),
        panel_path=resolved_path,
        panel_sha256=resolved_sha256,
    )


def generate_all_schedules(
    panel_index: pd.DatetimeIndex,
    *,
    panel_path: str | Path | None = None,
    panel_sha256: str = "",
) -> tuple[WalkForwardSchedule, ...]:
    """Generate all 8 schedules: 4 horizons × 2 schedule types.

    Ordering: ("1Y", "expanding"), ("1Y", "rolling_20y"), ("3Y", "expanding"),
    ... — horizon-major, schedule-minor for predictable downstream iteration.

    The same ``panel_path`` / ``panel_sha256`` is propagated to every schedule
    so PIT-safety provenance is consistent across the full 8-schedule grid.
    """
    horizon_order: tuple[HorizonLabel, ...] = ("1Y", "3Y", "5Y", "10Y")
    schedule_order: tuple[ScheduleType, ...] = ("expanding", "rolling_20y")

    schedules: list[WalkForwardSchedule] = []
    for h in horizon_order:
        for s in schedule_order:
            schedules.append(
                generate_schedule(
                    horizon=h,
                    schedule_type=s,
                    panel_index=panel_index,
                    panel_path=panel_path,
                    panel_sha256=panel_sha256,
                )
            )
    return tuple(schedules)
