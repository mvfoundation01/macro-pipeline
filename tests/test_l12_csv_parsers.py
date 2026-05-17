"""L12 D10 — Tests for ``macro_pipeline.webapp.csv_parsers``.

Counts: 7 tests (4 NEG / 3 POS) = 57% NEG (validation-heavy).
"""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

from macro_pipeline.webapp.csv_parsers import (
    FREDParser,
    TradingViewParser,
    UnsupportedCSVFormatError,
    parse_to_series,
)


def _write_csv(path: Path, rows: list[list]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)


# ----------------------------------------------------------------------
# POS (3 tests)
# ----------------------------------------------------------------------
def test_tradingview_parser_handles_time_close_format(tmp_path: Path) -> None:
    """V's FRED_*.csv / INDEX_*.csv files use the 2-column form."""
    p = tmp_path / "FRED_UMCSENT_1M.csv"
    _write_csv(p, [
        ["time", "close"],
        ["2026-01-01", "65.5"],
        ["2026-02-01", "66.2"],
        ["2026-03-01", "53.3"],
    ])
    series, name = parse_to_series(p)
    assert name == "tradingview"
    assert len(series) == 3
    assert series.iloc[-1] == pytest.approx(53.3)
    assert series.index.name == "date"


def test_tradingview_parser_handles_ohlc_format_and_picks_close(
    tmp_path: Path,
) -> None:
    """TVC_US10Y_1D.csv and CBOE_DLY_VIX_1D.csv use OHLC; we want close only."""
    p = tmp_path / "TVC_US10Y_1D.csv"
    _write_csv(p, [
        ["time", "open", "high", "low", "close"],
        ["2026-01-01", "4.50", "4.60", "4.48", "4.55"],
        ["2026-01-02", "4.55", "4.62", "4.50", "4.58"],
    ])
    series, _ = parse_to_series(p)
    assert series.iloc[-1] == pytest.approx(4.58)
    # Must NOT contain open/high/low values
    assert series.iloc[0] == pytest.approx(4.55)


def test_fred_parser_handles_date_value_format(tmp_path: Path) -> None:
    """FRED web-UI export (lowercase variant)."""
    p = tmp_path / "GDPNOW.csv"
    _write_csv(p, [
        ["observation_date", "value"],
        ["2026-01-01", "2.3"],
        ["2026-04-01", "1.8"],
    ])
    series, name = parse_to_series(p)
    assert name == "fred_direct"
    assert series.iloc[-1] == pytest.approx(1.8)


# ----------------------------------------------------------------------
# NEG (4 tests)
# ----------------------------------------------------------------------
def test_registry_raises_on_unknown_columns(tmp_path: Path) -> None:
    p = tmp_path / "weird.csv"
    _write_csv(p, [["foo", "bar"], ["a", "1"]])
    with pytest.raises(UnsupportedCSVFormatError, match=r"no registered parser"):
        parse_to_series(p)


def test_tradingview_parser_rejects_empty_rows(tmp_path: Path) -> None:
    """A CSV with only the header (no data rows) must raise ValueError, not
    silently return an empty Series."""
    p = tmp_path / "empty.csv"
    _write_csv(p, [["time", "close"]])
    with pytest.raises(ValueError, match=r"no valid \(date, close\) rows"):
        parse_to_series(p)


def test_fred_parser_does_not_trigger_on_close_column(tmp_path: Path) -> None:
    """When BOTH FRED-style (date + value) and TradingView-style (close) columns
    are present, TradingView wins — V's FRED_*.csv files in tradingview/ go
    through the TV parser, not FRED."""
    df = pd.DataFrame({"date": ["2026-01-01"], "value": [1.0], "close": [2.0]})
    fred = FREDParser()
    assert fred.can_parse(df) is False, (
        "FRED parser must defer when a `close` column is present"
    )
    tv = TradingViewParser()
    # TradingViewParser needs `time`; this frame has `date` so it also fails.
    assert tv.can_parse(df) is False


def test_tradingview_parser_rejects_all_unparseable_dates(tmp_path: Path) -> None:
    """If every date cell is garbage, dropna leaves no rows → ValueError."""
    p = tmp_path / "bad_dates.csv"
    _write_csv(p, [
        ["time", "close"],
        ["not-a-date", "5.0"],
        ["also-not", "6.0"],
    ])
    with pytest.raises(ValueError, match=r"no valid \(date, close\) rows"):
        parse_to_series(p)
