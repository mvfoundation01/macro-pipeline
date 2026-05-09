"""Tests for run_universal_pipeline flags introduced in Layer 1.5A.

Covers:
- A.3 hard-fail unit validation (``fail_on_unit_error=True`` default)
- A.6 cache-hit short-circuit (``_processed=True``)
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.preprocessing import (
    UnitError,
    run_universal_pipeline,
    to_visibility_index,
)


# ---------------------------------------------------------------------------
# A.3 - hard-fail unit validation
# ---------------------------------------------------------------------------
def _bad_pct_series() -> pd.Series:
    """A 'pct' series whose values clearly violate the canonical range
    (-200, 500): we put 1e8 in there to force assert_unit to raise."""
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    return pd.Series([1e8, 1e8, 1e8, 1e8], index=idx)


def test_fail_on_unit_error_default_is_true_and_raises():
    """Codex HIGH #3 fix: a unit assertion failure must abort the
    pipeline by default, not silently log and continue."""
    s = _bad_pct_series()
    with pytest.raises(UnitError):
        run_universal_pipeline(
            s, indicator_id="BAD_PCT", unit="pct", native_freq="D",
        )


def test_fail_on_unit_error_false_continues_with_warning(caplog):
    """Override flag is honored: validation failure is logged, not raised."""
    s = _bad_pct_series()
    with caplog.at_level("WARNING"):
        result = run_universal_pipeline(
            s, indicator_id="BAD_PCT", unit="pct", native_freq="D",
            fail_on_unit_error=False,
        )
    assert result.series.notna().any()
    assert any("inconsistent with unit" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# A.6 - cache hit no-reprocess
# ---------------------------------------------------------------------------
def test_processed_short_circuits_pipeline_stages():
    """When the caller marks data as already-processed (cache hit), the
    pipeline must skip stages 1.1-1.6 and pass the series through
    untouched. Verified by passing a series whose units would otherwise
    cause a hard-fail; with _processed=True the validation is bypassed."""
    s = _bad_pct_series()  # would normally raise under fail_on_unit_error=True
    result = run_universal_pipeline(
        s, indicator_id="BAD_PCT_CACHED", unit="pct", native_freq="D",
        _processed=True,
    )
    # Series is returned untouched (apart from name).
    assert list(result.series.values) == list(s.values)
    assert result.n_outliers == 0


def test_processed_short_circuit_emits_debug_log(caplog):
    """The 'cache hit, skip pipeline' log line is required by the
    proof-of-no-reprocess test in NEXT_STEPS."""
    s = pd.Series([1.0, 2.0], index=pd.date_range("2024-01-01", periods=2))
    with caplog.at_level("DEBUG", logger="src.preprocessing"):
        run_universal_pipeline(
            s, indicator_id="ANY", unit="pct", native_freq="D",
            _processed=True,
        )
    assert any(
        "cache hit, skip pipeline" in rec.message for rec in caplog.records
    )


def test_to_visibility_index_does_not_mutate_input():
    s = pd.Series([1.0, 2.0], index=pd.date_range("2024-01-01", periods=2))
    s_before = s.copy()
    _ = to_visibility_index(s, release_lag_days=5)
    pd.testing.assert_series_equal(s, s_before)
