"""Tests for src.unit_conversion (Layer 1.5A.2)."""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.preprocessing import UnitError
from macro_pipeline.unit_conversion import (
    UnitsError,
    assert_same_unit,
    to_b_usd,
    to_m_usd,
    to_pct,
)


# ---------------------------------------------------------------------------
# to_m_usd
# ---------------------------------------------------------------------------
def test_to_m_usd_from_b_usd_multiplies_by_1000():
    s = pd.Series([1.122])  # $1.122B in B_USD
    result = to_m_usd(s, "B_USD")
    assert result.iloc[0] == 1122.0


def test_to_m_usd_passthrough():
    s = pd.Series([6_699_950.0])  # $6.7T already in M_USD
    assert to_m_usd(s, "M_USD").iloc[0] == 6_699_950.0


def test_to_m_usd_from_b_usd_signed_preserves_sign():
    s = pd.Series([-2.5, 1.5])
    result = to_m_usd(s, "B_USD_signed")
    assert list(result) == [-2500.0, 1500.0]


# ---------------------------------------------------------------------------
# to_b_usd
# ---------------------------------------------------------------------------
def test_to_b_usd_from_m_usd_divides_by_1000():
    s = pd.Series([6_699_950.0])
    result = to_b_usd(s, "M_USD")
    assert abs(result.iloc[0] - 6699.95) < 0.01


def test_to_b_usd_passthrough():
    s = pd.Series([12.5])
    assert to_b_usd(s, "B_USD").iloc[0] == 12.5


# ---------------------------------------------------------------------------
# to_pct
# ---------------------------------------------------------------------------
def test_to_pct_from_share_multiplies_by_100():
    s = pd.Series([0.43, 0.075])
    result = to_pct(s, "share")
    assert list(result) == [43.0, 7.5]


def test_to_pct_passthrough():
    s = pd.Series([4.43])
    assert to_pct(s, "pct").iloc[0] == 4.43


# ---------------------------------------------------------------------------
# Errors / hard-fail
# ---------------------------------------------------------------------------
def test_unit_error_on_incompatible():
    """to_m_usd raises UnitsError for non-USD inputs."""
    with pytest.raises(UnitsError):
        to_m_usd(pd.Series([1.0]), "pct")


def test_units_error_is_subclass_of_unit_error():
    """preprocessing.UnitError catch blocks should still catch UnitsError."""
    err = UnitsError("test")
    assert isinstance(err, UnitError)


def test_assert_same_unit_passes_when_all_match():
    s1 = (pd.Series([1.0]), "M_USD")
    s2 = (pd.Series([2.0]), "M_USD")
    # No exception
    assert_same_unit(s1, s2)


def test_assert_same_unit_raises_on_mismatch():
    """Layer 3 Net Liquidity arithmetic guard (Codex HIGH #2)."""
    s1 = (pd.Series([1.0]), "M_USD")
    s2 = (pd.Series([2.0]), "B_USD")
    with pytest.raises(UnitsError):
        assert_same_unit(s1, s2)


def test_net_liquidity_pattern_requires_explicit_conversion():
    """Reproduces the Codex HIGH #2 scenario: WALCL is M_USD,
    RRPONTSYD is B_USD; Net_Liquidity must convert before subtracting."""
    walcl_m_usd = pd.Series([6_700_000.0])  # $6.7T in M_USD
    rrp_b_usd = pd.Series([500.0])  # $500B in B_USD

    # Direct subtraction (no conversion) gives a wrong number — proves
    # the bug exists by showing why the guard matters.
    naive = walcl_m_usd.iloc[0] - rrp_b_usd.iloc[0]
    correct = walcl_m_usd.iloc[0] - to_m_usd(rrp_b_usd, "B_USD").iloc[0]
    assert naive != correct  # ~$6.6995T vs ~$6.2T

    # And the guard catches it at the assertion level.
    with pytest.raises(UnitsError):
        assert_same_unit((walcl_m_usd, "M_USD"), (rrp_b_usd, "B_USD"))
