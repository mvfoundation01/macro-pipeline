"""FRED ALFRED vintage panel materialization (Layer 1.5A.4).

Codex review HIGH #4: the lazy ``groupby("date").last()`` pattern in
``fred_loader._fetch_vintage`` is non-deterministic without an explicit
``(date, realtime_start)`` sort, has no materialized ``realtime_end``,
and forces a full ALFRED scan per PIT lookup (~14,840 queries for a
1980-2024 walk-forward across 28 vintage series).

This module materializes a panel per series with schema:

    obs_date         | datetime  - the date the observation refers to
    realtime_start   | datetime  - first publication date for this vintage
    realtime_end     | datetime  - publication date of the next vintage
                                   (NaT if this is the current vintage)
    value            | float

Stored under ``data/cache/vintage_panels/<SERIES_ID>_vintage.parquet`` via
``cache.atomic_write_parquet`` so a crash mid-write cannot leave a partial
file.

Sorting note: rows are sorted by ``(obs_date, realtime_start)`` *before*
``realtime_end`` is computed via ``shift(-1)`` within each ``obs_date``
group. This makes the panel deterministic and lets ``get_pit_value`` /
``get_pit_series`` answer "what was known on date X" without re-scanning
the whole history.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from fredapi import Fred

from macro_pipeline.cache import atomic_write_bytes, atomic_write_parquet, read_cache_validated
from macro_pipeline.config import DATA_CACHE, FRED_API_KEY

log = logging.getLogger(__name__)

VINTAGE_PANEL_DIR = DATA_CACHE / "vintage_panels"

# Series that are revised by their issuing agency (BEA / BLS / Fed). These
# are the 12 from LAYER_1_5_FIX_SPRINT_SPEC §A.4. Series like SAHMREALTIME
# also have ALFRED history but are derived; the spec restricts the
# materialization set to these twelve revisable primaries.
VINTAGE_REQUIRED_SERIES: tuple[str, ...] = (
    "PAYEMS",
    "GDPC1",
    "INDPRO",
    "RSAFS",
    "RRSFS",
    "PCEC96",
    "PCEPILFE",
    "JTSQUR",
    "CFNAIMA3",
    "GFDEGDQ188S",
    "A091RC1Q027SBEA",
    "FGRECPT",
)


# ---------------------------------------------------------------------------
# Panel construction
# ---------------------------------------------------------------------------
def build_vintage_panel(series_id: str, fred: Fred | None = None) -> pd.DataFrame:
    """Build a deterministic vintage panel for ``series_id``.

    Returns a DataFrame with columns
        ``[obs_date, value, realtime_start, realtime_end]``
    sorted by ``(obs_date, realtime_start)``.

    The ``realtime_end`` column is computed per ``obs_date`` via
    ``shift(-1)`` on ``realtime_start``: it is the moment a given vintage
    was superseded, or ``NaT`` for the most recent vintage of an
    observation. ``get_pit_value`` interprets the half-open interval
    ``[realtime_start, realtime_end)`` as the visibility window.
    """
    fred = fred or Fred(api_key=FRED_API_KEY)
    raw = fred.get_series_all_releases(series_id)
    if raw is None or raw.empty:
        raise ValueError(f"FRED returned no vintage rows for {series_id}")

    # ALFRED returns ``date`` for the observation date; rename for clarity.
    df = raw.rename(columns={"date": "obs_date"}).copy()
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    df["realtime_start"] = pd.to_datetime(df["realtime_start"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    # Deterministic sort: this is the fix for Codex HIGH #4. Without an
    # explicit (obs_date, realtime_start) sort, ``groupby("date").last()``
    # depended on row order which was not stable across pandas/fredapi
    # releases.
    df = df.sort_values(["obs_date", "realtime_start"], kind="mergesort")
    df = df.drop_duplicates(subset=["obs_date", "realtime_start"], keep="last")

    # Compute realtime_end as the next vintage's realtime_start within the
    # same obs_date. NaT for the latest vintage of each observation.
    df["realtime_end"] = df.groupby("obs_date")["realtime_start"].shift(-1)

    df = df[["obs_date", "value", "realtime_start", "realtime_end"]]
    df = df.reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------
def panel_path(series_id: str) -> Path:
    return VINTAGE_PANEL_DIR / f"{series_id}_vintage.parquet"


def panel_meta_path(series_id: str) -> Path:
    return VINTAGE_PANEL_DIR / f"{series_id}_vintage.meta.json"


def load_panel(series_id: str) -> pd.DataFrame:
    """Load a materialized vintage panel from cache.

    Validates the parquet's sha256 against the meta.json on disk; on
    mismatch (corrupt or stale-schema cache) raises FileNotFoundError so
    the caller can re-materialize.
    """
    p = panel_path(series_id)
    if not p.exists():
        raise FileNotFoundError(f"No vintage panel cached for {series_id} at {p}")

    stem = p.stem  # "<SERIES>_vintage"
    validated = read_cache_validated(stem, VINTAGE_PANEL_DIR)
    if validated is None:
        raise FileNotFoundError(
            f"Vintage panel for {series_id} failed validation; rebuild it "
            f"with materialize_all_vintage_panels(force_refresh=True)."
        )
    df, _meta = validated
    df["obs_date"] = pd.to_datetime(df["obs_date"])
    df["realtime_start"] = pd.to_datetime(df["realtime_start"])
    df["realtime_end"] = pd.to_datetime(df["realtime_end"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# PIT lookups
# ---------------------------------------------------------------------------
def get_pit_value(
    panel: pd.DataFrame,
    observation_date: pd.Timestamp,
    asof_date: pd.Timestamp,
) -> float | None:
    """Return value of ``observation_date`` as known on ``asof_date``.

    Returns ``None`` if no vintage was published on or before ``asof_date``.
    Uses the half-open interval ``[realtime_start, realtime_end)``: the
    latest vintage with ``realtime_start <= asof_date`` wins (its
    ``realtime_end`` will by construction be > asof_date).
    """
    obs = pd.Timestamp(observation_date)
    asof = pd.Timestamp(asof_date)

    rows = panel[panel["obs_date"] == obs]
    if rows.empty:
        return None
    visible = rows[rows["realtime_start"] <= asof]
    if visible.empty:
        return None
    val = visible.iloc[-1]["value"]
    return None if pd.isna(val) else float(val)


def get_pit_series(panel: pd.DataFrame, asof_date: pd.Timestamp) -> pd.Series:
    """Full series view as known on ``asof_date``, indexed by obs_date.

    For each observation date, picks the latest vintage with
    ``realtime_start <= asof_date``. Observations whose first vintage
    was published after ``asof_date`` are dropped.
    """
    asof = pd.Timestamp(asof_date)
    visible = panel[panel["realtime_start"] <= asof]
    if visible.empty:
        return pd.Series(dtype=float, name="value")
    # Within each obs_date take the row with the largest realtime_start.
    # Panel is already sorted by (obs_date, realtime_start) so the last
    # row per obs_date is the latest visible vintage.
    latest = visible.groupby("obs_date", sort=True).tail(1)
    s = latest.set_index("obs_date")["value"].sort_index()
    s.name = "value"
    return s


# ---------------------------------------------------------------------------
# Materialization driver
# ---------------------------------------------------------------------------
def materialize_one(series_id: str, fred: Fred, *, force_refresh: bool = False) -> Path:
    """Build, hash, and write one vintage panel atomically. Returns path."""
    p = panel_path(series_id)
    if p.exists() and not force_refresh:
        log.debug("Vintage panel %s: cache exists, skipping rebuild", series_id)
        return p

    panel = build_vintage_panel(series_id, fred=fred)
    VINTAGE_PANEL_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_parquet(p, panel)

    # Sidecar metadata for the panel — separate from the regular
    # ``write_cache_atomic`` flow because the panel parquet is built first
    # and we want the sidecar's sha256 to refer to the just-written file.
    import hashlib
    data_sha256 = hashlib.sha256(p.read_bytes()).hexdigest()
    meta = {
        "series_id": series_id,
        "source": "FRED_ALFRED_VINTAGE",
        "schema": ["obs_date", "value", "realtime_start", "realtime_end"],
        "schema_version": "1.0",
        "data_sha256": data_sha256,
        "row_count": len(panel),
        "n_obs_dates": int(panel["obs_date"].nunique()),
        "n_vintages": int(panel["realtime_start"].nunique()),
        "first_obs_date": panel["obs_date"].min().isoformat(),
        "last_obs_date": panel["obs_date"].max().isoformat(),
        "first_realtime_start": panel["realtime_start"].min().isoformat(),
        "last_realtime_start": panel["realtime_start"].max().isoformat(),
        "cache_written_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
    }
    atomic_write_bytes(panel_meta_path(series_id), json.dumps(meta, indent=2).encode("utf-8"))
    log.info(
        "Vintage panel %s: materialized %d rows / %d obs dates / %d vintages",
        series_id, len(panel), meta["n_obs_dates"], meta["n_vintages"],
    )
    return p


def materialize_all_vintage_panels(
    *, force_refresh: bool = False, only: list[str] | None = None,
) -> dict[str, Path]:
    """Build vintage panels for every series in ``VINTAGE_REQUIRED_SERIES``.

    Returns ``{series_id: parquet_path}``. When ``force_refresh=False``
    (default) skips series whose parquet already exists.
    """
    targets = list(only) if only else list(VINTAGE_REQUIRED_SERIES)
    fred = Fred(api_key=FRED_API_KEY)
    out: dict[str, Path] = {}
    for sid in targets:
        try:
            out[sid] = materialize_one(sid, fred, force_refresh=force_refresh)
        except Exception as exc:
            log.error("Vintage panel %s: materialize failed - %s", sid, exc)
            raise
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    paths = materialize_all_vintage_panels(force_refresh=False)
    print(f"Materialized {len(paths)} vintage panels under {VINTAGE_PANEL_DIR}")
    for sid, p in paths.items():
        if p.exists():
            print(f"  {sid:24s} {p.stat().st_size / 1024:.1f} KB")
