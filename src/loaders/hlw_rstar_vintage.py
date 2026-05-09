"""HLW r-star vintage-aware loader (Build guide Phase 4D - LAYER 1 FINAL).

File: ``data/raw/official/Holston_Laubach_Williams_real_time_estimates.xlsx``

The file has 33 sheets:
  * ``info`` (skipped)
  * 32 vintage sheets named ``YYYYQN`` (e.g. ``2015Q4``, ``2016Q1``,
    ..., ``2020Q2``, ``2022Q4``, ..., ``2025Q4``).
    Note: there is a documented gap in 2020Q3-2022Q3 (no quarterly
    update was published during that COVID/methodology window).

Vintage sheet schema: NY Fed has shipped THREE distinct layouts in this
file (column count is the discriminator):

* Layout A (21 cols, 2015Q4 - 2019Q4): 4 countries (incl. UK), 4 sections
    section order: Output Gap | Trend Growth | Other Determinants z | r*
    US column indices: gap=2, trend=7, rstar=17

* Layout B (26 cols, 2020Q1 - 2020Q2): 4 countries, 5 sections
    section order: same as A + an "Adjusted Output Gap" trailing section
    US column indices: gap=2, trend=7, rstar=17 (the trailing section is
    out of scope here)

* Layout C (17 cols, 2022Q4 - 2025Q4): 3 countries (no UK), 4 sections
    section order: Trend Growth | Other Determinants z | r* | Output Gap
    US column indices: trend=2, rstar=10, gap=14
    (matches the current_estimates.xlsx layout used in Phase 4B)

The 2020Q3 - 2022Q3 window is missing from this file (NY Fed paused
publication during the COVID/methodology window).

Three indicators per vintage (so 3 columns x 32 vintages of multi-indexed data):
  * HLW_RSTAR_VINTAGE
  * HLW_TREND_GROWTH_VINTAGE
  * HLW_OUTPUT_GAP_VINTAGE

Cache: ``data/cache/official_HLW_VINTAGE.parquet`` with a MultiIndex
``(vintage, date)`` for efficient PIT lookup.

Tier: 2A. Vintage publication-date convention: ``vintage YYYYQX`` is
released approximately at the end of quarter X + 14 days (NY Fed's
typical release cadence). e.g. ``2020Q1`` -> 2020-04-14.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import DATA_CACHE, DATA_RAW
from src.loaders.base import IndicatorMetadata, Loader

log = logging.getLogger(__name__)

HLW_VINTAGE_PATH = (
    DATA_RAW / "official" / "Holston_Laubach_Williams_real_time_estimates.xlsx"
)
INFO_SHEET = "info"
VINTAGE_RE = re.compile(r"^(\d{4})Q([1-4])$")

INDICATOR_RSTAR = "HLW_RSTAR_VINTAGE"
INDICATOR_TREND = "HLW_TREND_GROWTH_VINTAGE"
INDICATOR_GAP = "HLW_OUTPUT_GAP_VINTAGE"
COLUMN_LAYOUTS: dict[int, dict[str, int]] = {
    # Layout A: 4 countries (US/Canada/EA/UK), sections {gap, trend, z, rstar}
    21: {INDICATOR_GAP: 2, INDICATOR_TREND: 7, INDICATOR_RSTAR: 17},
    # Layout B: 4 countries + Adjusted Output Gap section appended
    26: {INDICATOR_GAP: 2, INDICATOR_TREND: 7, INDICATOR_RSTAR: 17},
    # Layout C: 3 countries (no UK), sections {trend, z, rstar, gap}
    17: {INDICATOR_TREND: 2, INDICATOR_RSTAR: 10, INDICATOR_GAP: 14},
}
INDICATOR_IDS: tuple[str, ...] = (
    INDICATOR_RSTAR, INDICATOR_TREND, INDICATOR_GAP,
)


# ---------------------------------------------------------------------------
# Vintage discovery + publication-date arithmetic
# ---------------------------------------------------------------------------
def discover_vintages() -> list[str]:
    """Return sorted list of vintage sheet names (excluding ``info``)."""
    if not HLW_VINTAGE_PATH.exists():
        raise FileNotFoundError(str(HLW_VINTAGE_PATH))
    xl = pd.ExcelFile(HLW_VINTAGE_PATH)
    vintages = [s for s in xl.sheet_names if VINTAGE_RE.match(str(s))]
    return sorted(vintages, key=_vintage_sort_key)


def _vintage_sort_key(v: str) -> tuple[int, int]:
    m = VINTAGE_RE.match(v)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


def vintage_quarter_end(vintage: str) -> pd.Timestamp:
    """Return the last day of the quarter that the vintage covers.

    e.g. ``"2020Q1"`` -> 2020-03-31. The data inside the vintage sheet
    ends at this date; PIT views truncate here.
    """
    m = VINTAGE_RE.match(vintage)
    if not m:
        raise ValueError(f"Invalid vintage key: {vintage!r}")
    year = int(m.group(1))
    quarter = int(m.group(2))
    end_month = quarter * 3
    return pd.Timestamp(year=year, month=end_month, day=1) + pd.offsets.MonthEnd(0)


def vintage_to_publication_date(vintage: str) -> pd.Timestamp:
    """NY Fed publishes the vintage ~14 days after the quarter ends.

    e.g. ``"2015Q4"`` -> 2016-01-14, ``"2020Q1"`` -> 2020-04-14,
    ``"2024Q4"`` -> 2025-01-14.
    """
    return vintage_quarter_end(vintage) + pd.Timedelta(days=14)


# ---------------------------------------------------------------------------
# Vintage sheet reader
# ---------------------------------------------------------------------------
def _read_vintage_sheet(vintage: str) -> pd.DataFrame:
    """Read one vintage sheet, return DataFrame indexed by date with
    columns [HLW_RSTAR_VINTAGE, HLW_TREND_GROWTH_VINTAGE, HLW_OUTPUT_GAP_VINTAGE].

    The full sheet is read first (so the column count is determined by
    the widest header row, not by data-area trailing NaNs). Layout is
    detected from the column count.
    """
    full = pd.read_excel(HLW_VINTAGE_PATH, sheet_name=vintage, header=None)
    # Some early vintages have UK columns that are entirely empty in the
    # data area; the headers carry them so the canonical column count
    # comes from the section banner (row 5), the widest row.
    n_cols = max(
        int(full.iloc[r].notna().sum()) + sum(
            1 for c in range(full.shape[1])
            if pd.notna(full.iloc[r, c])
            and c == full.shape[1] - 1  # placeholder
        )
        for r in range(min(8, full.shape[0]))
    )
    n_cols = full.shape[1]   # actually use the full width pandas reports

    if n_cols not in COLUMN_LAYOUTS:
        raise ValueError(
            f"vintage {vintage}: unrecognized layout with {n_cols} cols; "
            f"known layouts have {sorted(COLUMN_LAYOUTS)} cols. "
            "Inspect the sheet and add a new entry to COLUMN_LAYOUTS."
        )
    layout = COLUMN_LAYOUTS[n_cols]

    # Data starts row 6 (rows 0-5 are headers/banners).
    raw = full.iloc[6:].copy()
    raw[0] = pd.to_datetime(raw[0], errors="coerce")
    raw = raw.dropna(subset=[0]).set_index(0)
    raw.index.name = "date"
    raw = raw[~raw.index.duplicated(keep="last")]

    out: dict[str, pd.Series] = {}
    for indicator_id in INDICATOR_IDS:
        col_idx = layout[indicator_id]
        out[indicator_id] = pd.to_numeric(raw.iloc[:, col_idx], errors="coerce")

    df = pd.DataFrame(out).sort_index()
    # Hard truncate at the vintage's quarter end - the source data inside
    # the sheet shouldn't exceed it, but defend against future appends.
    df = df.loc[df.index <= vintage_quarter_end(vintage)]
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_hlw_vintage(
    vintage: str | None = None,
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    """Load HLW r-star vintage data.

    With ``vintage=None`` returns ``dict[vintage_key -> DataFrame]`` of all
    32 vintages. With a specific vintage like ``"2020Q1"`` returns just
    that one DataFrame.
    """
    if vintage is None:
        return {v: _read_vintage_sheet(v) for v in discover_vintages()}
    if not VINTAGE_RE.match(vintage):
        raise ValueError(
            f"Invalid vintage {vintage!r}; expected pattern YYYYQN"
        )
    available = set(discover_vintages())
    if vintage not in available:
        raise KeyError(
            f"vintage {vintage!r} not in workbook; available: "
            f"{sorted(available)}"
        )
    return _read_vintage_sheet(vintage)


def get_pit_rstar(
    asof_date: str | pd.Timestamp,
    *,
    raise_on_no_vintage: bool = True,
) -> pd.DataFrame | None:
    """Return HLW estimates as known on ``asof_date`` (point-in-time view).

    Looks up the latest vintage whose publication date is on or before
    ``asof_date`` and returns its DataFrame, truncated at the vintage's
    quarter end. The result is also stamped with ``df.attrs["vintage"]``
    and ``df.attrs["publication_date"]``.

    For dates before the earliest vintage publication date, raises
    ``ValueError`` (or returns ``None`` if ``raise_on_no_vintage=False``).

    NEVER returns data from a vintage published AFTER ``asof_date``.
    """
    asof = pd.Timestamp(asof_date)
    vintages = discover_vintages()
    pub_dates = {v: vintage_to_publication_date(v) for v in vintages}
    candidates = [v for v in vintages if pub_dates[v] <= asof]
    if not candidates:
        msg = (
            f"No HLW vintage available on or before {asof.date()}; "
            f"earliest is {vintages[0]} "
            f"(published {pub_dates[vintages[0]].date()})"
        )
        if raise_on_no_vintage:
            raise ValueError(msg)
        log.warning("%s", msg)
        return None
    selected = candidates[-1]
    df = _read_vintage_sheet(selected).copy()
    df.attrs["vintage"] = selected
    df.attrs["publication_date"] = pub_dates[selected].isoformat()
    df.attrs["asof_date"] = asof.isoformat()
    return df


# ---------------------------------------------------------------------------
# Cache as MultiIndex parquet
# ---------------------------------------------------------------------------
def cache_paths() -> tuple[Path, Path]:
    return (
        DATA_CACHE / "official_HLW_VINTAGE.parquet",
        DATA_CACHE / "official_HLW_VINTAGE.meta.json",
    )


def build_cache(*, force_refresh: bool = False) -> tuple[pd.DataFrame, IndicatorMetadata]:
    """Build/refresh the multi-vintage parquet cache.

    Stored shape: rows = MultiIndex(vintage, date), cols = three
    HLW_*_VINTAGE indicators.
    """
    parquet, sidecar = cache_paths()
    if parquet.exists() and not force_refresh:
        df = pd.read_parquet(parquet)
        meta_dict = json.loads(sidecar.read_text()) if sidecar.exists() else {}
        meta = IndicatorMetadata(
            indicator_id="HLW_VINTAGE",
            source="NYFED_HLW_VINTAGE_XLSX",
            frequency="Q",
            first_obs=pd.Timestamp(meta_dict.get("first_obs"))
                if meta_dict.get("first_obs") else df.index.get_level_values("date").min(),
            last_obs=pd.Timestamp(meta_dict.get("last_obs"))
                if meta_dict.get("last_obs") else df.index.get_level_values("date").max(),
            last_update=pd.Timestamp(meta_dict.get("last_update", datetime.now(timezone.utc).replace(tzinfo=None))),
            unit="pct", needs_vintage=True,
            description="HLW vintage panel (multi-index)",
            extra=meta_dict,
        )
        return df, meta

    all_v = load_hlw_vintage()
    parts = []
    for vintage_key, df in all_v.items():
        d = df.copy()
        d.index.name = "date"
        d["vintage"] = vintage_key
        parts.append(d.reset_index())
    long = pd.concat(parts, axis=0, ignore_index=True)
    long = long.set_index(["vintage", "date"]).sort_index()

    DATA_CACHE.mkdir(parents=True, exist_ok=True)
    long.to_parquet(parquet)

    vintages_meta = {
        v: vintage_to_publication_date(v).date().isoformat()
        for v in discover_vintages()
    }
    first_obs = long.index.get_level_values("date").min()
    last_obs = long.index.get_level_values("date").max()
    meta = IndicatorMetadata(
        indicator_id="HLW_VINTAGE",
        source="NYFED_HLW_VINTAGE_XLSX",
        frequency="Q",
        first_obs=first_obs, last_obs=last_obs,
        last_update=pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None)),
        needs_vintage=True,
        unit="pct",
        release_lag_days=14,
        description=(
            "Holston-Laubach-Williams r* / trend growth / output gap "
            "vintage panel for the United States. Stored as a single "
            "MultiIndex(vintage, date) parquet with columns "
            "[HLW_RSTAR_VINTAGE, HLW_TREND_GROWTH_VINTAGE, "
            "HLW_OUTPUT_GAP_VINTAGE]."
        ),
        extra={
            "tier": "2A",
            "vintage": "all",
            "country": "US",
            "source_file": HLW_VINTAGE_PATH.name,
            "n_vintages": len(vintages_meta),
            "vintage_publication_dates": vintages_meta,
            "n_rows": int(long.shape[0]),
            "indicators": list(INDICATOR_IDS),
            "publication_date_rule": (
                "vintage_quarter_end + 14 days (NY Fed convention)"
            ),
        },
    )
    sidecar.write_text(json.dumps(meta.to_dict(), default=str, indent=2))
    return long, meta


class HlwRstarVintageLoader(Loader):
    def load(self):
        df, meta = build_cache()
        return df, {meta.indicator_id: meta}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    df, meta = build_cache(force_refresh=True)
    n_vintages = len(df.index.get_level_values("vintage").unique())
    n_rows = len(df)
    print(f"HLW vintage cache: {n_vintages} vintages, {n_rows:,} rows, "
          f"{df.index.get_level_values('date').min().date()} -> "
          f"{df.index.get_level_values('date').max().date()}")
    print()
    # Demo PIT lookup
    for asof in ["2020-06-15", "2024-12-15"]:
        pit = get_pit_rstar(asof)
        last_us_rstar = pit["HLW_RSTAR_VINTAGE"].dropna().iloc[-1]
        print(f"PIT {asof}: vintage={pit.attrs['vintage']}  "
              f"published={pit.attrs['publication_date'][:10]}  "
              f"latest US r* in that vintage = {last_us_rstar:.3f}%")
