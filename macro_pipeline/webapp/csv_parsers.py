"""L12 D3 — Multi-format CSV parsers.

V's institutional workflow exports raw CSVs from three primary providers, each
with a different schema:

* **TradingView**          ``time,close`` (or ``time,open,high,low,close``)
* **FRED direct (web UI)** ``DATE,VALUE`` or ``observation_date,value``
* **L10 templates**        domain-specific columns (``date,2y,10y`` for yield
                           curve, ``date,ig_oas`` for credit spreads,
                           ``date,indicator,value`` for sentiment)

The L10 webapp form only accepted the third format, forcing V to reshape every
raw file manually. L12 generalizes: each parser exposes a uniform
``to_series(df) -> pd.Series`` interface so the higher-level
``LocalDataManager`` can aggregate across providers transparently.

Public API
----------
``CSVParser``            Abstract base class.
``TradingViewParser``    ``time`` + ``close`` (OHLC optional).
``FREDParser``           FRED web-UI export.
``ParserRegistry``       First-match-wins dispatch.
``parse_to_series``      Convenience: try every parser, return ``pd.Series``.
``UnsupportedCSVFormatError``  Raised when no parser matches.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class UnsupportedCSVFormatError(ValueError):
    """Raised when no registered parser recognises the CSV's column layout."""


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class CSVParser(ABC):
    """Each parser examines a DataFrame's columns and, if they match the
    parser's expected schema, projects the data to a single
    ``date``-indexed ``pd.Series``."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in error messages + provenance dicts."""

    @abstractmethod
    def can_parse(self, df: pd.DataFrame) -> bool:
        """Return True iff this parser knows how to handle ``df``."""

    @abstractmethod
    def to_series(self, df: pd.DataFrame) -> pd.Series:
        """Project the DataFrame to a date-indexed float series.

        The index must be a sorted ``pd.DatetimeIndex`` with no NaT values;
        the series's name should be set by the caller after the parser runs.
        """


# ---------------------------------------------------------------------------
# TradingView (time + close; OHLC optional)
# ---------------------------------------------------------------------------
class TradingViewParser(CSVParser):
    """Parses TradingView "Export chart data" CSVs.

    Two variants exist in V's dataset:
      * ``time,close``                        (e.g. FRED_BAMLC0A0CM_1D.csv,
                                                INDEX_S5FI_1D.csv)
      * ``time,open,high,low,close``          (e.g. TVC_US10Y_1D.csv,
                                                CBOE_DLY_VIX_1D.csv)

    Both encode the value of interest in the ``close`` column. ``time`` is
    ISO-8601 (``YYYY-MM-DD``).
    """

    name = "tradingview"

    REQUIRED = ("time", "close")

    def can_parse(self, df: pd.DataFrame) -> bool:
        lowered = {c.lower() for c in df.columns}
        return all(c in lowered for c in self.REQUIRED)

    def to_series(self, df: pd.DataFrame) -> pd.Series:
        # Find the right columns case-insensitively.
        time_col = next(c for c in df.columns if c.lower() == "time")
        close_col = next(c for c in df.columns if c.lower() == "close")
        index = pd.to_datetime(df[time_col], errors="coerce")
        series = pd.Series(
            pd.to_numeric(df[close_col], errors="coerce").to_numpy(),
            index=index,
        )
        # Drop rows where EITHER the date is NaT (unparseable) OR the value is NaN.
        # ``Series.dropna()`` alone only drops NaN VALUES; NaT indices survive
        # and silently corrupt downstream timestamp logic.
        series = series[~series.index.isna()].dropna().sort_index()
        if series.empty:
            raise ValueError(
                "TradingView CSV had no valid (date, close) rows after parsing"
            )
        series.index.name = "date"
        return series


# ---------------------------------------------------------------------------
# FRED direct (DATE + VALUE)
# ---------------------------------------------------------------------------
class FREDParser(CSVParser):
    """Parses FRED website export CSVs (e.g. ``UMCSENT.csv`` downloaded via
    the FRED browser UI). Two header conventions exist:

      * ``DATE,VALUE``               (legacy UI export, all-caps)
      * ``observation_date,value``   (current UI export, lowercase)

    NB: FRED-via-TradingView files (``FRED_*.csv`` in V's tradingview/
    directory) use the TradingView format and are handled by
    ``TradingViewParser``, not this parser.
    """

    name = "fred_direct"

    def _date_col(self, df: pd.DataFrame) -> str | None:
        for c in df.columns:
            if c.lower() in {"date", "observation_date"}:
                return c
        return None

    def _value_col(self, df: pd.DataFrame) -> str | None:
        for c in df.columns:
            if c.lower() == "value":
                return c
        return None

    def can_parse(self, df: pd.DataFrame) -> bool:
        # Distinguish from TradingViewParser which already has "close".
        if "close" in {c.lower() for c in df.columns}:
            return False
        return self._date_col(df) is not None and self._value_col(df) is not None

    def to_series(self, df: pd.DataFrame) -> pd.Series:
        date_col = self._date_col(df)
        value_col = self._value_col(df)
        if date_col is None or value_col is None:
            raise ValueError(
                "FRED parser invoked on a frame missing date/value columns"
            )
        index = pd.to_datetime(df[date_col], errors="coerce")
        series = pd.Series(
            pd.to_numeric(df[value_col], errors="coerce").to_numpy(),
            index=index,
        )
        # Same NaT-index defence as TradingViewParser — `dropna()` alone leaves
        # rows with unparseable dates.
        series = series[~series.index.isna()].dropna().sort_index()
        if series.empty:
            raise ValueError(
                "FRED CSV had no valid (date, value) rows after parsing"
            )
        series.index.name = "date"
        return series


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class ParserRegistry:
    """First-match-wins parser dispatch.

    Order matters: TradingView is checked first because its
    ``close`` column unambiguously identifies the format. FRED is
    secondary because its ``DATE`` / ``VALUE`` headers are common
    enough that a name collision is possible.
    """

    def __init__(self, parsers: list[CSVParser] | None = None) -> None:
        self._parsers: list[CSVParser] = (
            list(parsers)
            if parsers is not None
            else [TradingViewParser(), FREDParser()]
        )

    @property
    def parsers(self) -> list[CSVParser]:
        return list(self._parsers)

    def select(self, df: pd.DataFrame) -> CSVParser:
        for parser in self._parsers:
            if parser.can_parse(df):
                return parser
        column_list = list(df.columns)
        raise UnsupportedCSVFormatError(
            f"no registered parser handles columns {column_list!r}. "
            "Supported formats: TradingView (time,close), FRED (DATE,VALUE)."
        )

    def parse_file(self, filepath: Path) -> tuple[pd.Series, str]:
        """Read ``filepath`` and project to a date-indexed Series.

        Returns ``(series, parser_name)``; the second element is recorded in
        provenance so downstream UI can show which parser handled each file.
        """
        df = pd.read_csv(filepath)
        parser = self.select(df)
        series = parser.to_series(df)
        return series, parser.name


# Convenience module-level helper.
def parse_to_series(filepath: Path) -> tuple[pd.Series, str]:
    """Parse a CSV file to a date-indexed Series using the default registry."""
    return ParserRegistry().parse_file(filepath)
