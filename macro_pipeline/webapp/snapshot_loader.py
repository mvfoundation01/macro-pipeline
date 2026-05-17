"""L11 D2/D5 — Snapshot loader utility.

Loads parquet panels from ``macro_pipeline/data_snapshot/`` (bundled with
the L11 webapp + PyInstaller exe). Used by ``ProducerAdapter`` to derive
ForecastInputs from real historical data without requiring a FRED API key
or network access.

The L11 audit (`docs/build-plans/L11_PRODUCER_INTEGRATION_AUDIT.md` §5)
documents the deliberate choice NOT to modify the three production loaders
(`fred_loader.py`, `fred_vintage_panel.py`, `yahoo_loader.py`) to fall back
here — instead, ProducerAdapter calls this utility directly. Rationale:
preserves 1,382-test baseline and zero `fredapi` coupling.

Public API
----------
``SnapshotLoader``           Reads panels by stem; caches deserialized DataFrames.
``SnapshotManifest``         Parsed MANIFEST.json with build date + checksums.
``SnapshotNotFoundError``    Raised when the snapshot dir or a requested panel is absent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data_snapshot"
MANIFEST_FILENAME = "MANIFEST.json"


class SnapshotNotFoundError(FileNotFoundError):
    """Raised when the data snapshot directory or a requested panel is missing."""


@dataclass(frozen=True)
class SnapshotManifest:
    """Parsed MANIFEST.json from a built snapshot."""

    build_timestamp_utc: str
    panels_copied: int
    total_bytes: int
    panel_stems: tuple[str, ...]
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, manifest_path: Path) -> SnapshotManifest:
        if not manifest_path.exists():
            raise SnapshotNotFoundError(
                f"MANIFEST.json not found at {manifest_path}. "
                "Run `python scripts/build_data_snapshot.py` to populate "
                "the snapshot from your local data/cache/."
            )
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        stems = tuple(r["stem"] for r in raw.get("records", []))
        return cls(
            build_timestamp_utc=raw.get("build_timestamp_utc", "unknown"),
            panels_copied=raw.get("panels_copied", 0),
            total_bytes=raw.get("total_bytes", 0),
            panel_stems=stems,
            raw=raw,
        )

    @property
    def build_date(self) -> str:
        """Return the build date in YYYY-MM-DD (or 'unknown')."""
        if self.build_timestamp_utc == "unknown":
            return "unknown"
        try:
            return datetime.fromisoformat(self.build_timestamp_utc).date().isoformat()
        except ValueError:
            return "unknown"


class SnapshotLoader:
    """Reads parquet panels from the bundled data snapshot.

    Maintains an in-memory cache of deserialized DataFrames so repeated reads
    inside a single request stay fast.

    Usage
    -----
    >>> loader = SnapshotLoader()
    >>> loader.manifest.panels_copied
    27
    >>> shiller_tr = loader.load("official_SHILLER_TR_PRICE")
    >>> shiller_tr.shape
    (1828, 2)
    """

    def __init__(self, snapshot_dir: Path | None = None) -> None:
        self.snapshot_dir = snapshot_dir or SNAPSHOT_DIR
        self._cache: dict[str, pd.DataFrame] = {}
        self._manifest: SnapshotManifest | None = None

    @property
    def manifest(self) -> SnapshotManifest:
        if self._manifest is None:
            self._manifest = SnapshotManifest.load(
                self.snapshot_dir / MANIFEST_FILENAME
            )
        return self._manifest

    @property
    def available(self) -> bool:
        """True if the snapshot directory + manifest both exist."""
        return (self.snapshot_dir / MANIFEST_FILENAME).exists()

    def has_panel(self, stem: str) -> bool:
        """True if the named panel (parquet) exists on disk."""
        return (self.snapshot_dir / f"{stem}.parquet").exists()

    def load(self, stem: str) -> pd.DataFrame:
        """Load a panel by stem name (e.g. ``"official_SHILLER_TR_PRICE"``).

        Returns the DataFrame. Raises ``SnapshotNotFoundError`` if the panel
        is missing. Cached per loader instance.
        """
        if stem in self._cache:
            return self._cache[stem]
        path = self.snapshot_dir / f"{stem}.parquet"
        if not path.exists():
            raise SnapshotNotFoundError(
                f"Panel {stem!r} not in snapshot at {path}. Available panels: "
                f"{sorted(self.manifest.panel_stems)[:5]}..."
            )
        df = pd.read_parquet(path)
        self._cache[stem] = df
        return df

    def try_load(self, stem: str) -> pd.DataFrame | None:
        """Like ``load`` but returns None on missing panel (no exception)."""
        try:
            return self.load(stem)
        except SnapshotNotFoundError:
            return None
