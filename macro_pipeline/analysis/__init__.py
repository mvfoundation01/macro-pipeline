"""Analysis package — Layer 3D R^2 master panel.

Public API
----------
``build_and_cache(force=False)``  Build the 124 × 4 × 2 panel and write
                                  atomically to data/cache/analysis/.
``build_panel(...)``              Build without caching.
``load_panel(...)``               Load the cached panel.
``forward_return(target, t, H)``  PIT-safe forward return helper.
``forward_return_series(...)``    Vectorized version.
``load_target(target_id)``        Load SHILLER_TR_PRICE or SP500TR.
``align_indicator_to_target(...)`` ASOF-align indicator to target dates.
``fit_ols_hac(y, x, horizon_months=H)`` Newey-West HAC OLS wrapper.
``classify_verdict(n_nominal, H)``  FULL / UNDERPOWERED / NO_OVERLAP.
``n_eff_nonoverlap(n_nominal, H)``  n_nominal // H.

See ``analysis/README.md`` for the design choices D16-D18 and the
target × horizon coverage matrix.
"""
from __future__ import annotations

from macro_pipeline.analysis.effective_sample_size import (
    UNDERPOWERED_N_EFF_MIN,
    UNDERPOWERED_N_NOMINAL_MIN,
    VERDICT_FULL,
    VERDICT_NO_OVERLAP,
    VERDICT_UNDERPOWERED,
    classify_verdict,
    is_underpowered,
    n_eff_nonoverlap,
)
from macro_pipeline.analysis.newey_west_hac import HACResult, fit_ols_hac
from macro_pipeline.analysis.r_squared_panel import (
    HORIZONS,
    MULTIINDEX_INDICATORS,
    PANEL_CACHE_PATH,
    PANEL_SCHEMA_VERSION,
    SCORE_ARTIFACTS,
    build_and_cache,
    build_panel,
    discover_panel_indicators,
    load_panel,
    write_panel_atomic,
)
from macro_pipeline.analysis.regression_target import (
    SUPPORTED_TARGETS,
    align_indicator_to_target,
    forward_return,
    forward_return_series,
    load_target,
)
from macro_pipeline.analysis.component_panel import (
    CDRS_BUCKET_COLUMNS,
    CDRS_BUCKET_TO_SUBCOMPONENTS,
    CRPS_COLUMNS,
    build_component_panel,
)
from macro_pipeline.analysis.walk_forward_cv import (
    GATE18_FOLD_COUNT_TARGETS,
    MIN_TRAIN_WINDOW_MONTHS_DEFAULT,
    STEP_SIZE_MONTHS,
    HorizonLabel,
    ScheduleType,
    WalkForwardFold,
    WalkForwardSchedule,
    generate_all_schedules,
    generate_schedule,
)

__all__ = [
    "CDRS_BUCKET_COLUMNS",
    "CDRS_BUCKET_TO_SUBCOMPONENTS",
    "CRPS_COLUMNS",
    "GATE18_FOLD_COUNT_TARGETS",
    "HORIZONS",
    "HorizonLabel",
    "MIN_TRAIN_WINDOW_MONTHS_DEFAULT",
    "MULTIINDEX_INDICATORS",
    "PANEL_CACHE_PATH",
    "PANEL_SCHEMA_VERSION",
    "SCORE_ARTIFACTS",
    "STEP_SIZE_MONTHS",
    "SUPPORTED_TARGETS",
    "ScheduleType",
    "UNDERPOWERED_N_EFF_MIN",
    "UNDERPOWERED_N_NOMINAL_MIN",
    "VERDICT_FULL",
    "VERDICT_NO_OVERLAP",
    "VERDICT_UNDERPOWERED",
    "HACResult",
    "WalkForwardFold",
    "WalkForwardSchedule",
    "align_indicator_to_target",
    "build_component_panel",
    "build_and_cache",
    "build_panel",
    "classify_verdict",
    "discover_panel_indicators",
    "fit_ols_hac",
    "forward_return",
    "forward_return_series",
    "generate_all_schedules",
    "generate_schedule",
    "is_underpowered",
    "load_panel",
    "load_target",
    "n_eff_nonoverlap",
    "write_panel_atomic",
]
