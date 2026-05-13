"""Tests for ``macro_pipeline.analysis.component_panel``.

Patch closing S-10 via Option (iv) HYBRID. Test plan per design doc v2 §D:
  T1 POS test_build_component_panel_crps_4_active_columns
  T2 POS test_build_component_panel_cdrs_4_buckets_M2_option_b_mapping
  T3 NEG test_build_component_panel_rejects_invalid_score_type
  T4 NEG test_build_component_panel_rejects_non_monthly_index
  T5 NEG test_build_component_panel_pit_safety_no_look_ahead
  T6 NEG test_build_component_panel_bucket_composition_matches_design_doc_v2

NEG count: T3, T4, T5, T6 = 4 of 6 = 67% (exceeds 50% floor per §2.7).

Spec ref: LAYER_5_BUILD_SPEC.md v6 §5.B.1 (input contract).
Design doc: docs/build-plans/L3_COMPONENT_PANEL_D2_DESIGN.md v2 §C.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from macro_pipeline.analysis.component_panel import (
    CDRS_BUCKET_COLUMNS,
    CDRS_BUCKET_TO_SUBCOMPONENTS,
    CRPS_COLUMNS,
    build_component_panel,
)
from macro_pipeline.scoring.cdrs_trigger import T_COMPONENTS
from macro_pipeline.scoring.cdrs_vulnerability import V_COMPONENTS
from macro_pipeline.scoring.crps import LAYER3_ACTIVE_COMPONENTS


# Test date range — 2023 H1 has all CRPS + CDRS components active (T3
# CBOE_GAMMA available 2022-12+, all V/T components have data).
_TEST_RANGE_START = "2023-01-01"
_TEST_RANGE_END = "2023-06-01"


@pytest.fixture(scope="module")
def panel_index_2023_h1() -> pd.DatetimeIndex:
    return pd.date_range(_TEST_RANGE_START, _TEST_RANGE_END, freq="MS")


# ---------------------------------------------------------------------------
# T1 — POS: CRPS schema has 4 active columns (per LAYER3_ACTIVE_COMPONENTS)
# ---------------------------------------------------------------------------

def test_build_component_panel_crps_4_active_columns(
    panel_index_2023_h1: pd.DatetimeIndex,
) -> None:
    """CRPS panel has 4 active columns matching LAYER3_ACTIVE_COMPONENTS.

    ISM (ism_pmi_neworders) and CB LEI (lei_3d_rule) are NOT in the export
    (deferred to backlog L5b-2). Asserting absence here is the
    'currently-out-of-scope' guard.
    """
    df = build_component_panel(panel_index_2023_h1, score_type="CRPS")

    # Schema
    assert df.shape == (len(panel_index_2023_h1), 4)
    assert tuple(df.columns) == CRPS_COLUMNS
    assert tuple(df.columns) == tuple(LAYER3_ACTIVE_COMPONENTS)

    # ISM + LEI explicitly absent
    assert "ism_pmi_neworders" not in df.columns
    assert "lei_3d_rule" not in df.columns

    # Values ∈ [0, 1] for active months (no NaN expected in 2023 H1)
    for col in df.columns:
        assert df[col].notna().all(), f"{col} has NaN in 2023 H1"
        assert (df[col] >= 0).all() and (df[col] <= 1).all(), (
            f"{col} values outside [0, 1]"
        )


# ---------------------------------------------------------------------------
# T2 — POS: CDRS schema has 4 buckets per Option B mapping
# ---------------------------------------------------------------------------

def test_build_component_panel_cdrs_4_buckets_M2_option_b_mapping(
    panel_index_2023_h1: pd.DatetimeIndex,
) -> None:
    """CDRS panel has 4 bucket columns per D2 v2 §C (Option B)."""
    df = build_component_panel(panel_index_2023_h1, score_type="CDRS")

    # Schema
    assert df.shape == (len(panel_index_2023_h1), 4)
    assert tuple(df.columns) == CDRS_BUCKET_COLUMNS
    assert tuple(df.columns) == (
        "bucket_valuation",
        "bucket_sentiment",
        "bucket_credit",
        "bucket_vol_breadth_technical_gamma",
    )

    # Values ∈ [0, 1] for non-NaN entries (all entries should be active in
    # 2023 H1 since all V/T components have data)
    for col in df.columns:
        non_nan = df[col].dropna()
        assert len(non_nan) > 0, f"{col} has no non-NaN values in 2023 H1"
        assert (non_nan >= 0).all() and (non_nan <= 1).all(), (
            f"{col} values outside [0, 1]"
        )


# ---------------------------------------------------------------------------
# T3 — NEG: rejects invalid score_type
# ---------------------------------------------------------------------------

def test_build_component_panel_rejects_invalid_score_type(
    panel_index_2023_h1: pd.DatetimeIndex,
) -> None:
    """`score_type='UNKNOWN'` raises ValueError."""
    with pytest.raises(ValueError, match="score_type must be one of"):
        build_component_panel(
            panel_index_2023_h1,
            score_type="UNKNOWN",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# T4 — NEG: rejects non-monthly-contiguous panel_index
# ---------------------------------------------------------------------------

def test_build_component_panel_rejects_non_monthly_index() -> None:
    """Panel index with month gaps raises ValueError (mirrors L5-A)."""
    gappy = pd.DatetimeIndex([
        pd.Timestamp("2023-01-01"),
        pd.Timestamp("2023-02-01"),
        pd.Timestamp("2023-04-01"),  # GAP — missing 2023-03
    ])
    with pytest.raises(ValueError, match="monthly contiguous"):
        build_component_panel(gappy, score_type="CRPS")


# ---------------------------------------------------------------------------
# T5 — NEG: PIT safety — no look-ahead beyond as_of
# ---------------------------------------------------------------------------

def test_build_component_panel_pit_safety_no_look_ahead(
    panel_index_2023_h1: pd.DatetimeIndex,
) -> None:
    """At as_of = month T, no values from T+1 or later appear in the row.

    Empirical test: build panel for 2023-01..2023-06; build same panel for
    2023-01..2023-03; assert 2023-01..2023-03 rows are IDENTICAL between
    the two builds (i.e., 2023-04+ data did not back-propagate into
    earlier as_of computations).
    """
    full = build_component_panel(panel_index_2023_h1, score_type="CDRS")
    truncated_index = pd.date_range("2023-01-01", "2023-03-01", freq="MS")
    truncated = build_component_panel(truncated_index, score_type="CDRS")

    # Rows 2023-01..2023-03 must be element-wise identical between builds.
    # (CDRS uses PitDataContext which respects as_of strictly per L3.5b-T/U.)
    common = full.loc[truncated.index]
    for col in CDRS_BUCKET_COLUMNS:
        for ts in truncated.index:
            a = common.at[ts, col]
            b = truncated.at[ts, col]
            # Both NaN OK; otherwise must match exactly.
            if math.isnan(a) and math.isnan(b):
                continue
            assert a == b, (
                f"PIT violation: column {col} at {ts.date()}: full={a} "
                f"differs from truncated={b}"
            )


# ---------------------------------------------------------------------------
# T6 — NEG: bucket composition contract test against design doc v2 §C
# ---------------------------------------------------------------------------

def test_build_component_panel_bucket_composition_matches_design_doc_v2() -> None:
    """Asserts CDRS_BUCKET_TO_SUBCOMPONENTS matches design doc v2 §C verbatim.

    This is the contract test per Strategic prompt PHASE 2 STEP 2.1: the
    bucket mapping in code MUST equal the design doc v2 §C definition. Any
    drift between code and design doc invalidates Phase 1.6 closure.

    Reference: docs/build-plans/L3_COMPONENT_PANEL_D2_DESIGN.md v2 §C:
        bucket_valuation                   = mean(V1_cape_pctile, V4_ey_real_gap_z, V5_ey_deviation)
        bucket_sentiment                   = mean(V2_margin_z, V3_concentration_proxy)
        bucket_credit                      = T1_hy_oas_30d_roc
        bucket_vol_breadth_technical_gamma = mean(T2_vix_12m_pctile, T3_gamma_sign, T4_breadth_thrust, T5_move_z)
    """
    expected: dict[str, tuple[str, ...]] = {
        "bucket_valuation":                   ("V1_cape_pctile", "V4_ey_real_gap_z", "V5_ey_deviation"),
        "bucket_sentiment":                   ("V2_margin_z", "V3_concentration_proxy"),
        "bucket_credit":                      ("T1_hy_oas_30d_roc",),
        "bucket_vol_breadth_technical_gamma": ("T2_vix_12m_pctile", "T3_gamma_sign", "T4_breadth_thrust", "T5_move_z"),
    }
    assert CDRS_BUCKET_TO_SUBCOMPONENTS == expected, (
        "CDRS bucket composition has drifted from design doc v2 §C. "
        "Either update the design doc + this test (with Strategic approval) "
        "OR fix component_panel.py to match the design doc."
    )

    # Cross-check: every V_COMPONENTS entry appears in some bucket; same
    # for T_COMPONENTS. (No sub-component orphaned.)
    all_mapped = set()
    for subs in CDRS_BUCKET_TO_SUBCOMPONENTS.values():
        all_mapped.update(subs)
    v_set = set(V_COMPONENTS)
    t_set = set(T_COMPONENTS)
    expected_all = v_set | t_set
    assert all_mapped == expected_all, (
        f"Sub-component coverage drift: mapped={sorted(all_mapped)}; "
        f"expected V_COMPONENTS ∪ T_COMPONENTS = {sorted(expected_all)}"
    )

    # Cross-check: bucket column tuple matches dict keys (preserves order).
    assert CDRS_BUCKET_COLUMNS == tuple(CDRS_BUCKET_TO_SUBCOMPONENTS.keys())
