"""Unit conversion helpers for derived series (Layer 1.5A.2).

Codex review HIGH #2 (Net Liquidity unit mismatch). All cross-source
arithmetic in Layer 3 derived series MUST go through these helpers
(or call ``assert_same_unit`` first) so e.g. ``WALCL - RRPONTSYD``
cannot silently produce a value that is off by 1000x.

Canonical units (must match ``src.config.UNIT_EXPECTED_RANGES``):
    pct, M_USD, B_USD, B_USD_signed, T_USD, count, count_k, count_signed,
    count_10yreqv, index, share, decimal, pct_exposure, binary, ratio
"""
from __future__ import annotations

import pandas as pd

# Re-export the existing UnitError so callers have a single canonical
# exception type. ``preprocessing.UnitError`` is the legacy one used by
# ``assert_unit``; both should be ``isinstance(..., UnitError)``-true.
from src.preprocessing import UnitError


class UnitsError(UnitError):
    """Raised when arithmetic is attempted on incompatible units.

    Subclass of ``preprocessing.UnitError`` so existing
    ``except UnitError`` blocks continue to catch it.
    """


_USD_UNITS = frozenset({"M_USD", "B_USD", "B_USD_signed", "T_USD"})
_PCT_LIKE_UNITS = frozenset({"pct", "share", "decimal", "ratio", "pct_change", "pct_exposure"})


def to_m_usd(s: pd.Series, unit: str) -> pd.Series:
    """Convert a USD-denominated series to millions USD."""
    if unit == "M_USD":
        return s
    if unit in ("B_USD", "B_USD_signed"):
        return s * 1000.0
    if unit == "T_USD":
        return s * 1_000_000.0
    raise UnitsError(f"Cannot convert {unit!r} to M_USD")


def to_b_usd(s: pd.Series, unit: str) -> pd.Series:
    """Convert a USD-denominated series to billions USD."""
    if unit in ("B_USD", "B_USD_signed"):
        return s
    if unit == "M_USD":
        return s / 1000.0
    if unit == "T_USD":
        return s * 1000.0
    raise UnitsError(f"Cannot convert {unit!r} to B_USD")


def to_pct(s: pd.Series, unit: str) -> pd.Series:
    """Convert a percent-like series to percent (4.43 means 4.43%)."""
    if unit in ("pct", "pct_change", "pct_exposure"):
        return s
    if unit in ("share", "decimal", "ratio"):
        return s * 100.0
    raise UnitsError(f"Cannot convert {unit!r} to pct")


def assert_same_unit(*series_with_meta: tuple[pd.Series, str]) -> None:
    """Raise ``UnitsError`` if any units differ.

    Example
    -------
    >>> assert_same_unit((walcl, "M_USD"), (rrp, "M_USD"))   # OK
    >>> assert_same_unit((walcl, "M_USD"), (rrp, "B_USD"))   # raises
    """
    if not series_with_meta:
        return
    units = {meta for _, meta in series_with_meta}
    if len(units) > 1:
        raise UnitsError(
            f"Series have different units: {sorted(units)}. "
            f"Convert (e.g. via to_m_usd / to_b_usd) before arithmetic."
        )


__all__ = [
    "UnitsError",
    "to_m_usd",
    "to_b_usd",
    "to_pct",
    "assert_same_unit",
]
