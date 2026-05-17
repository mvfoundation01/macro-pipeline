"""L11 D12 — Tests for the bundled data snapshot + SnapshotLoader.

Counts: 6 tests (4 NEG / 2 POS) = 67% NEG.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from macro_pipeline.webapp.snapshot_loader import (
    SnapshotLoader,
    SnapshotManifest,
    SnapshotNotFoundError,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = REPO_ROOT / "macro_pipeline" / "data_snapshot"


# ----------------------------------------------------------------------
# POS — happy paths (2 tests)
# ----------------------------------------------------------------------
def test_default_snapshot_loads_and_manifest_has_panels() -> None:
    """The committed snapshot must have a valid MANIFEST.json with ≥10 panels."""
    if not (DEFAULT_SNAPSHOT / "MANIFEST.json").exists():
        pytest.skip("snapshot not built; run scripts/build_data_snapshot.py")
    loader = SnapshotLoader()
    assert loader.available is True
    assert loader.manifest.panels_copied >= 10
    assert loader.manifest.build_date != "unknown"


def test_load_panel_returns_pandas_dataframe() -> None:
    if not (DEFAULT_SNAPSHOT / "MANIFEST.json").exists():
        pytest.skip("snapshot not built")
    import pandas as pd

    loader = SnapshotLoader()
    df = loader.load("official_SHILLER_TR_PRICE")
    assert isinstance(df, pd.DataFrame)
    assert "SHILLER_TR_PRICE" in df.columns
    assert len(df) > 1000  # historical Shiller series has thousands of obs


# ----------------------------------------------------------------------
# NEG — strict validation (4 tests)
# ----------------------------------------------------------------------
def test_loader_raises_when_snapshot_dir_missing(tmp_path: Path) -> None:
    """Missing snapshot directory → SnapshotNotFoundError on manifest access."""
    fake_dir = tmp_path / "no_snapshot_here"
    loader = SnapshotLoader(snapshot_dir=fake_dir)
    assert loader.available is False
    with pytest.raises(SnapshotNotFoundError, match=r"MANIFEST\.json not found"):
        _ = loader.manifest


def test_loader_raises_when_specific_panel_missing(tmp_path: Path) -> None:
    """Manifest exists but requested panel absent → SnapshotNotFoundError."""
    manifest_path = tmp_path / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {
                "build_timestamp_utc": "2026-05-17T00:00:00+00:00",
                "panels_copied": 0,
                "total_bytes": 0,
                "records": [],
            }
        ),
        encoding="utf-8",
    )
    loader = SnapshotLoader(snapshot_dir=tmp_path)
    with pytest.raises(SnapshotNotFoundError, match="not in snapshot"):
        loader.load("nonexistent_panel")


def test_try_load_returns_none_on_missing_panel(tmp_path: Path) -> None:
    manifest_path = tmp_path / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps({"build_timestamp_utc": "2026-05-17T00:00:00+00:00", "records": []}),
        encoding="utf-8",
    )
    loader = SnapshotLoader(snapshot_dir=tmp_path)
    assert loader.try_load("does_not_exist") is None


def test_manifest_with_malformed_timestamp_returns_unknown_build_date(
    tmp_path: Path,
) -> None:
    """A garbage timestamp must not crash; build_date returns 'unknown'."""
    manifest_path = tmp_path / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(
            {"build_timestamp_utc": "not-a-real-timestamp", "records": []}
        ),
        encoding="utf-8",
    )
    manifest = SnapshotManifest.load(manifest_path)
    assert manifest.build_date == "unknown"
