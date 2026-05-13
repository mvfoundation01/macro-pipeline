"""Layer 3 component_panel export for Layer 5-B Task A consumption.

Patch closing S-10: provides `build_component_panel(panel_index, score_type)`
returning the spec §5.B.1 input contract — a time-indexed DataFrame with
per-component (CRPS) or per-bucket (CDRS) normalized scores ∈ [0, 1].

Design provenance
-----------------
Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.B.1 (line 587 + 663-673).
Design doc: ``docs/build-plans/L3_COMPONENT_PANEL_D2_DESIGN.md`` v2.
S-10 escalation: ``docs/build-plans/L5_BUILD_SXX_LOG.md``.

CDRS bucket mapping (Option B per D2 v2 §C; Strategic confirmed 2026-05-13):
    bucket_valuation                   = mean(V1_cape_pctile, V4_ey_real_gap_z, V5_ey_deviation)
    bucket_sentiment                   = mean(V2_margin_z, V3_concentration_proxy)
    bucket_credit                      = T1_hy_oas_30d_roc                                          (1-signal)
    bucket_vol_breadth_technical_gamma = mean(T2_vix_12m_pctile, T3_gamma_sign, T4_breadth_thrust, T5_move_z)

R (regime multiplier) EXCLUDED from component_panel per D2 §3 Q3 — treated
as downstream structural rescaling, not an input feature.

CRPS active components (4 of spec's 6 per ``LAYER_3_ACTIVE_COMPONENTS``):
    yield_curve_nyfed, sahm_rule, nfci_kcfsi, hy_oas_regime

CRPS deferred (backlog L5b-2):
    ism_pmi_neworders (NAPMNOI; FRED 400), lei_3d_rule (CB LEI; no loader)
"""
from __future__ import annotations

import math
from typing import Literal

import pandas as pd

from macro_pipeline.access import PitDataContext
from macro_pipeline.scoring.cdrs_trigger import T_COMPONENTS, compute_trigger
from macro_pipeline.scoring.cdrs_vulnerability import (
    V_COMPONENTS,
    compute_vulnerability,
)
from macro_pipeline.scoring.crps import (
    COMPONENT_INDICATOR,
    LAYER3_ACTIVE_COMPONENTS,
    normalize_hy_oas_regime,
    normalize_nfci,
    normalize_sahm,
    normalize_t10y3m,
)

ScoreType = Literal["CRPS", "CDRS"]

CRPS_COLUMNS: tuple[str, ...] = tuple(LAYER3_ACTIVE_COMPONENTS)  # 4 active components

CDRS_BUCKET_COLUMNS: tuple[str, ...] = (
    "bucket_valuation",
    "bucket_sentiment",
    "bucket_credit",
    "bucket_vol_breadth_technical_gamma",
)

# CDRS bucket → sub-component aggregation per D2 v2 §C.
# Used by T6_bucket_composition contract test and the aggregation logic.
CDRS_BUCKET_TO_SUBCOMPONENTS: dict[str, tuple[str, ...]] = {
    "bucket_valuation":                   ("V1_cape_pctile", "V4_ey_real_gap_z", "V5_ey_deviation"),
    "bucket_sentiment":                   ("V2_margin_z", "V3_concentration_proxy"),
    "bucket_credit":                      ("T1_hy_oas_30d_roc",),
    "bucket_vol_breadth_technical_gamma": ("T2_vix_12m_pctile", "T3_gamma_sign", "T4_breadth_thrust", "T5_move_z"),
}

# Mirror of scoring.crps._NORMALIZER (private). Reconstructed here from the
# public normalize_* functions + COMPONENT_INDICATOR to avoid private-API
# coupling. Only active components covered.
_CRPS_NORMALIZER: dict[str, tuple[str, object]] = {
    "yield_curve_nyfed":  ("scalar",  normalize_t10y3m),
    "sahm_rule":          ("scalar",  normalize_sahm),
    "nfci_kcfsi":         ("scalar",  normalize_nfci),
    "hy_oas_regime":      ("history", normalize_hy_oas_regime),
}


def _assert_monthly_contiguous(panel_index: pd.DatetimeIndex) -> None:
    """Raise ValueError if panel_index has month gaps. Mirrors L5-A discipline."""
    if len(panel_index) < 2:
        return
    sorted_idx = panel_index.sort_values()
    for i in range(len(sorted_idx) - 1):
        a = sorted_idx[i]
        b = sorted_idx[i + 1]
        expected_next = a + pd.DateOffset(months=1)
        if b.to_period("M") != expected_next.to_period("M"):
            raise ValueError(
                f"panel_index must be monthly contiguous; gap between "
                f"{a.date()} and {b.date()} (expected month "
                f"{expected_next.to_period('M')})"
            )


def _load_crps_component_normalized(name: str, ctx: PitDataContext) -> float:
    """Return PIT-safe normalized [0, 1] score for one active CRPS component.

    Replicates ``scoring.crps._load_component`` logic using public normalizers
    + COMPONENT_INDICATOR + LAYER3_ACTIVE_COMPONENTS — no private-API access.

    Returns ``float('nan')`` if the component has no PIT-safe observation at
    ``ctx.as_of`` (mirrors scoring.crps graceful-degradation pattern).
    """
    if name not in _CRPS_NORMALIZER:
        raise ValueError(
            f"CRPS component {name!r} not in active normalizer map "
            f"{sorted(_CRPS_NORMALIZER.keys())}; spec deferred ISM + LEI to "
            "backlog L5b-2"
        )
    indicator_id = COMPONENT_INDICATOR[name]
    bundle = ctx.load(indicator_id)
    series = bundle.data.dropna()
    if series.empty:
        return float("nan")
    raw_value = float(series.iloc[-1])
    norm_kind, norm_fn = _CRPS_NORMALIZER[name]
    if norm_kind == "scalar":
        return float(norm_fn(raw_value))
    # "history" kind takes (value, series)
    return float(norm_fn(raw_value, series))


def _crps_row_for_as_of(as_of: pd.Timestamp) -> dict[str, float]:
    """Build one CRPS row (4 active components, normalized ∈ [0, 1])."""
    ctx = PitDataContext(as_of=as_of)
    return {
        name: _load_crps_component_normalized(name, ctx)
        for name in LAYER3_ACTIVE_COMPONENTS
    }


def _cdrs_row_for_as_of(as_of: pd.Timestamp) -> dict[str, float]:
    """Build one CDRS row aggregated into 4 buckets per D2 v2 §C.

    For each bucket, take the mean of available sub-components. Components
    that are PIT-inactive at ``as_of`` (per cdrs_vulnerability /
    cdrs_trigger graceful degradation) are dropped from the bucket mean;
    if a bucket has zero active components, its value is NaN.
    """
    ctx = PitDataContext(as_of=as_of)

    # Try to compute V; if it raises (no active components at all), V is
    # empty and all V-derived buckets become NaN.
    try:
        v_result = compute_vulnerability(ctx)
        v_components = v_result.components_normalized
    except Exception:  # noqa: BLE001 — degrade to NaN for this row
        v_components = {}

    try:
        t_result = compute_trigger(ctx)
        t_components = t_result.components_normalized
    except Exception:  # noqa: BLE001
        t_components = {}

    all_components: dict[str, float] = {**v_components, **t_components}

    row: dict[str, float] = {}
    for bucket, subs in CDRS_BUCKET_TO_SUBCOMPONENTS.items():
        active_values = [
            all_components[s] for s in subs
            if s in all_components and math.isfinite(all_components[s])
        ]
        if not active_values:
            row[bucket] = float("nan")
        else:
            row[bucket] = float(sum(active_values) / len(active_values))
    return row


def build_component_panel(
    panel_index: pd.DatetimeIndex,
    *,
    score_type: ScoreType,
) -> pd.DataFrame:
    """Build the L5-B Task A component_panel input for ``score_type``.

    Parameters
    ----------
    panel_index
        Monthly-contiguous ``pd.DatetimeIndex`` (typically the index of L3D
        ``r_squared_panel.parquet`` or a sub-range thereof). Each date is
        used as ``as_of`` for the PIT-safe component load.
    score_type
        ``"CRPS"`` → 4-column DataFrame with active CRPS components per
        ``LAYER3_ACTIVE_COMPONENTS``.
        ``"CDRS"`` → 4-column DataFrame with bucket aggregation per
        D2 v2 §C (Option B).

    Returns
    -------
    pd.DataFrame
        Time-indexed (DatetimeIndex), 4 columns; values normalized ∈ [0, 1];
        NaN where component / bucket is PIT-inactive at the corresponding
        ``as_of`` (e.g., pre-2022 dates have T3_gamma_sign inactive →
        affects ``bucket_vol_breadth_technical_gamma`` mean).

    Raises
    ------
    ValueError
        If ``score_type`` not in {"CRPS", "CDRS"}, or if ``panel_index`` is
        not monthly contiguous (mirrors L5-A discipline).
    TypeError
        If ``panel_index`` is not ``pd.DatetimeIndex``.

    PIT discipline
    --------------
    Each row is built via ``PitDataContext(as_of=date)`` which propagates
    the L3.5b cache validation + Option Z release-lag semantics. No
    look-ahead: at ``as_of = T``, no values from ``T+1`` or later appear
    in the row.

    Notes
    -----
    * ISM (``ism_pmi_neworders``) and CB LEI (``lei_3d_rule``) components
      from the spec's 6-component CRPS framing are deferred to **backlog
      L5b-2** (no FRED / Tier-1-4 loaders today). CRPS export is 4-column
      until L5b-2 lands.
    * R (regime multiplier) excluded from the panel per D2 §3 Q3 —
      downstream sub-phases (L5-G Bayesian shrinkage) apply regime
      conditioning, NOT Task A's penalized logistic.
    * Effort: ~O(N × C) where N = len(panel_index) and C ≈ 9 loads per
      date (4 CRPS or 5+5 CDRS). For full 1357-month panel × 9 loads ≈
      12K PIT loads; typical build < 2 min.
    """
    if score_type not in ("CRPS", "CDRS"):
        raise ValueError(
            f"score_type must be one of ('CRPS', 'CDRS'); got {score_type!r}"
        )
    if not isinstance(panel_index, pd.DatetimeIndex):
        raise TypeError(
            f"panel_index must be pd.DatetimeIndex; got "
            f"{type(panel_index).__name__}"
        )
    _assert_monthly_contiguous(panel_index)

    sorted_idx = panel_index.sort_values()

    if score_type == "CRPS":
        row_builder = _crps_row_for_as_of
        columns = CRPS_COLUMNS
    else:  # CDRS
        row_builder = _cdrs_row_for_as_of
        columns = CDRS_BUCKET_COLUMNS

    rows: list[dict[str, float]] = [row_builder(d) for d in sorted_idx]
    df = pd.DataFrame(rows, index=sorted_idx, columns=list(columns))
    df.index.name = "date"
    return df


__all__ = [
    "CDRS_BUCKET_COLUMNS",
    "CDRS_BUCKET_TO_SUBCOMPONENTS",
    "CRPS_COLUMNS",
    "ScoreType",
    "build_component_panel",
]
