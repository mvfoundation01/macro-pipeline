"""L12 D4/D5/D6 — Local data manager.

Scans ``data/raw/official/`` and ``data/raw/tradingview/`` for V's institutional
CSV exports, classifies each file by its filename, and aggregates the per-file
series into the structure the existing L10 forecast pipeline expects (i.e.
the same shape ``ExcelDataIngester.parse_*`` returns: a dict with ``rows``,
``latest``, plus category-specific derived fields like ``inverted`` /
``elevated`` / ``by_indicator``).

Designed so that ``ForecastInputsBuilder.build(uploaded_data=...)`` can ingest
the output without changes: ``LocalDataManager.build_uploaded_data()`` returns
exactly the ``{yield_curve: ..., credit_spreads: ..., sentiment: ...}`` dict
the producer adapter already consumes.

Public API
----------
``LocalDataManager``      Main entry; scan + aggregate.
``DetectedFile``          Frozen record describing a classified file.
``FILENAME_PATTERNS``     Module-level regex → (category, subseries) registry.
``classify_filename``     Helper exposed for tests.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from macro_pipeline.webapp.csv_parsers import ParserRegistry, UnsupportedCSVFormatError

# ---------------------------------------------------------------------------
# Filename → (category, subseries) registry
# ---------------------------------------------------------------------------
# Patterns target the LEAF filename (no directory). All regexes are case-
# insensitive and match anywhere in the name (re.search). The first matching
# pattern wins. Subseries names line up with the column names the existing
# L10 pipeline expects (e.g. "2y" / "10y" for yield curve), so aggregation
# can build the right DataFrame without further mapping.
FILENAME_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # ---- Yield curve ----
    (re.compile(r"TVC[_-]US02Y", re.I), "yield_curve", "2y"),
    (re.compile(r"TVC[_-]US10Y", re.I), "yield_curve", "10y"),
    (re.compile(r"TVC[_-]US03MY", re.I), "yield_curve", "3m"),
    # ---- Credit spreads (ICE BofA OAS series) ----
    (re.compile(r"FRED[_-]BAMLC0A0CM", re.I), "credit_spreads", "ig_oas"),
    (re.compile(r"FRED[_-]BAMLH0A0HYM2", re.I), "credit_spreads", "hy_oas"),
    (re.compile(r"FRED[_-]BAMLH0A1HYBB", re.I), "credit_spreads", "bb_oas"),
    (re.compile(r"FRED[_-]BAMLH0A3HYC", re.I), "credit_spreads", "ccc_oas"),
    # ---- Sentiment / market breadth / vol / fund flows ----
    (re.compile(r"FRED[_-]UMCSENT", re.I), "sentiment", "umich"),
    (re.compile(r"FRED[_-]CSCICP03USM665S", re.I), "sentiment", "consumer_confidence"),
    (re.compile(r"CBOE[_-]DLY[_-]VIX", re.I), "sentiment", "vix"),
    (re.compile(r"CBOE[_-]DLY[_-]GAMMA", re.I), "sentiment", "dealer_gamma"),
    (re.compile(r"INDEX[_-]S5FI", re.I), "sentiment", "spx_above_50dma"),
    (re.compile(r"INDEX[_-]S5TH", re.I), "sentiment", "spx_above_200dma"),
    (re.compile(r"INDEX[_-]HIGN", re.I), "sentiment", "new_highs_minus_lows"),
    (re.compile(r"USI[_-]PCCE", re.I), "sentiment", "put_call_equity"),
    (re.compile(r"USI[_-]ISSU", re.I), "sentiment", "advance_decline_issues"),
    (re.compile(r"FRED[_-]WALCL", re.I), "sentiment", "fed_balance_sheet"),
    (re.compile(r"FRED[_-]RRPONTSYD", re.I), "sentiment", "reverse_repo"),
    (re.compile(r"FRED[_-]WTREGEN", re.I), "sentiment", "treasury_general"),
    (re.compile(r"FRED[_-]WILL5000PR", re.I), "sentiment", "wilshire_5000"),
    (re.compile(r"FRED[_-]GDP", re.I), "sentiment", "gdp"),
    (re.compile(r"TVC[_-]RUT[_-]SP[_-]SPX", re.I), "sentiment", "russell_spx_ratio"),
]


def classify_filename(name: str) -> tuple[str, str] | None:
    """Return ``(category, subseries)`` for ``name`` or ``None`` if no pattern matches."""
    for pattern, category, subseries in FILENAME_PATTERNS:
        if pattern.search(name):
            return category, subseries
    return None


# ---------------------------------------------------------------------------
# DetectedFile record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DetectedFile:
    """One classified file picked up by ``LocalDataManager.scan``."""

    path: Path
    category: str          # "yield_curve" / "credit_spreads" / "sentiment" / "unclassified"
    subseries: str         # e.g. "2y" / "ig_oas" / "umich" / "" if unclassified
    parser_name: str = ""  # populated on successful parse, blank otherwise
    error: str = ""        # populated on parse failure


# ---------------------------------------------------------------------------
# LocalDataManager
# ---------------------------------------------------------------------------
class LocalDataManager:
    """Scan + aggregate V's local raw-data directories into the structure the
    L10 webapp pipeline already consumes (one dict per category).

    Usage
    -----
    >>> mgr = LocalDataManager()
    >>> detected = mgr.scan()
    >>> uploaded_data = mgr.build_uploaded_data(detected)
    >>> # `uploaded_data` matches the L10 `ExcelDataIngester` output shape and
    >>> # can be passed straight to ``ForecastInputsBuilder.build(uploaded_data=...)``.
    """

    DEFAULT_PATHS: tuple[Path, ...] = (
        Path("D:/macro_pipeline/data/raw/official"),
        Path("D:/macro_pipeline/data/raw/tradingview"),
    )

    SUPPORTED_EXTENSIONS = (".csv",)

    def __init__(
        self,
        search_paths: tuple[Path, ...] | None = None,
        registry: ParserRegistry | None = None,
    ) -> None:
        self.search_paths = (
            tuple(search_paths) if search_paths is not None else self.DEFAULT_PATHS
        )
        self.registry = registry or ParserRegistry()

    # ------------------------------------------------------------------
    # scan()
    # ------------------------------------------------------------------
    def scan(self) -> dict[str, list[DetectedFile]]:
        """Walk ``search_paths`` non-recursively, classify each CSV by filename.

        Returns a dict keyed by category (``yield_curve``, ``credit_spreads``,
        ``sentiment``, ``unclassified``). The same file never appears twice.
        Missing directories are silently skipped (they're commonly absent on
        a fresh checkout).
        """
        buckets: dict[str, list[DetectedFile]] = {
            "yield_curve": [],
            "credit_spreads": [],
            "sentiment": [],
            "unclassified": [],
        }
        seen: set[Path] = set()
        for root in self.search_paths:
            if not root.exists() or not root.is_dir():
                continue
            for path in sorted(root.iterdir()):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                    continue
                if path in seen:
                    continue
                seen.add(path)
                classification = classify_filename(path.name)
                if classification is None:
                    buckets["unclassified"].append(
                        DetectedFile(path=path, category="unclassified", subseries="")
                    )
                    continue
                category, subseries = classification
                buckets[category].append(
                    DetectedFile(path=path, category=category, subseries=subseries)
                )
        return buckets

    # ------------------------------------------------------------------
    # Aggregators (one per L10 category)
    # ------------------------------------------------------------------
    def aggregate_yield_curve(
        self, files: list[DetectedFile]
    ) -> dict | None:
        """Combine 2Y + 10Y files into an L10-style yield-curve data dict.

        Requires AT LEAST 2y AND 10y files. Returns ``None`` if either is
        missing (caller falls back to manual upload).

        Return shape matches ``ExcelDataIngester.parse_yield_curve`` output::

            {
                "rows":    [{"date": ts, "2y": float, "10y": float}, ...],
                "latest":  {"date": ts, "2y": float, "10y": float},
                "inverted": bool,
                "source":  "local_files",
                "files":   [<filenames used>, ...],
            }
        """
        by_sub = self._series_by_subseries(files, required={"2y", "10y"})
        if by_sub is None:
            return None
        # Inner-join on date so we only emit rows where both 2Y and 10Y exist.
        combined = pd.concat(
            [by_sub["2y"].rename("2y"), by_sub["10y"].rename("10y")],
            axis=1,
            join="inner",
        ).dropna()
        if combined.empty:
            return None
        rows = [
            {"date": idx.date().isoformat(), "2y": float(r["2y"]), "10y": float(r["10y"])}
            for idx, r in combined.iterrows()
        ]
        latest = rows[-1]
        inverted = latest["2y"] > latest["10y"]
        return {
            "rows": rows,
            "latest": latest,
            "inverted": inverted,
            "source": "local_files",
            "files": sorted(
                f.path.name for f in files if f.subseries in {"2y", "10y"}
            ),
        }

    def aggregate_credit_spreads(
        self, files: list[DetectedFile]
    ) -> dict | None:
        """Build L10-style credit-spreads dict. Requires ``ig_oas``."""
        by_sub = self._series_by_subseries(files, required={"ig_oas"})
        if by_sub is None:
            return None
        s = by_sub["ig_oas"].dropna()
        if s.empty:
            return None
        # FRED publishes OAS in PERCENT (e.g. 0.8 = 80 bps). The L10 template
        # expects basis points; multiply by 100 so downstream thresholds
        # (>200 bps = "elevated") behave identically.
        s_bps = s * 100.0
        rows = [
            {"date": idx.date().isoformat(), "ig_oas": float(v)}
            for idx, v in s_bps.items()
        ]
        latest = rows[-1]
        elevated = latest["ig_oas"] > 200.0
        return {
            "rows": rows,
            "latest": latest,
            "elevated": elevated,
            "source": "local_files",
            "files": sorted(f.path.name for f in files if f.subseries == "ig_oas"),
        }

    def aggregate_sentiment(
        self, files: list[DetectedFile]
    ) -> dict | None:
        """Build L10-style sentiment dict (long format: date / indicator / value).

        Uses ALL files in the sentiment bucket (no required subset). Emits one
        row per (date, indicator) pair, plus a ``by_indicator`` summary of
        latest values keyed by subseries name.
        """
        if not files:
            return None
        rows: list[dict] = []
        by_indicator: dict[str, float] = {}
        used: list[str] = []
        for detected in files:
            try:
                series, parser_name = self.registry.parse_file(detected.path)
            except (UnsupportedCSVFormatError, ValueError, pd.errors.ParserError):
                continue
            series = series.dropna()
            if series.empty:
                continue
            used.append(detected.path.name)
            for idx, value in series.items():
                rows.append(
                    {
                        "date": idx.date().isoformat(),
                        "indicator": detected.subseries,
                        "value": float(value),
                    }
                )
            by_indicator[detected.subseries] = float(series.iloc[-1])
        if not rows:
            return None
        rows.sort(key=lambda r: (r["date"], r["indicator"]))
        latest = rows[-1]
        return {
            "rows": rows,
            "latest": latest,
            "by_indicator": by_indicator,
            "source": "local_files",
            "files": used,
        }

    # ------------------------------------------------------------------
    # Top-level convenience: build the dict ForecastInputsBuilder consumes
    # ------------------------------------------------------------------
    def build_uploaded_data(
        self, detected: dict[str, list[DetectedFile]] | None = None
    ) -> dict[str, dict]:
        """Return the same shape ``ForecastInputsBuilder.build`` consumes via
        its ``uploaded_data`` arg. Categories with insufficient files are
        OMITTED (not returned with ``None``) so the builder can detect a
        missing category and fall back / warn."""
        if detected is None:
            detected = self.scan()
        out: dict[str, dict] = {}
        yc = self.aggregate_yield_curve(detected.get("yield_curve", []))
        if yc is not None:
            out["yield_curve"] = yc
        cs = self.aggregate_credit_spreads(detected.get("credit_spreads", []))
        if cs is not None:
            out["credit_spreads"] = cs
        se = self.aggregate_sentiment(detected.get("sentiment", []))
        if se is not None:
            out["sentiment"] = se
        return out

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _series_by_subseries(
        self, files: list[DetectedFile], required: set[str]
    ) -> dict[str, pd.Series] | None:
        """Parse files in the bucket; return ``{subseries: Series}`` if every
        item in ``required`` is satisfied, else ``None``."""
        by_sub: dict[str, pd.Series] = {}
        for detected in files:
            try:
                series, _ = self.registry.parse_file(detected.path)
            except (UnsupportedCSVFormatError, ValueError, pd.errors.ParserError):
                continue
            by_sub[detected.subseries] = series
        if not required.issubset(by_sub.keys()):
            return None
        return by_sub


# ---------------------------------------------------------------------------
# Module-level constants for tests + UI introspection
# ---------------------------------------------------------------------------
KNOWN_SUBSERIES: frozenset[str] = frozenset(sub for _, _, sub in FILENAME_PATTERNS)
