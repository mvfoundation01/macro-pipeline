"""Layer 3.5E — tests for ``cache.read_cache_validated_subdir`` contract.

Spec: ``LAYER_3_5_BUILD_SPEC.md`` §7.5 #1-#4.

Four tests:
  1. POS — sha is recomputed (sidecar with valid sha succeeds; tampered
     parquet raises).
  2. NEG — corrupted parquet (1-byte flip) raises ``CacheValidationError``.
  3. NEG — modified sidecar (stale sha) raises ``CacheValidationError``.
  4. NEG — missing sidecar raises ``FileNotFoundError`` (parquet only,
     no sidecar).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from macro_pipeline.cache import (
    read_cache_validated_subdir,
    write_cache_atomic_subdir,
)
from macro_pipeline.exceptions import CacheValidationError

SUBDIR = "_test_3_5e_validation"
FILENAME = "smoke.parquet"


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Path:
    """Provide a tmp ``cache_root`` with the standard 3.5E subdir layout."""
    return tmp_path


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({
        "x": [1.0, 2.0, 3.0, 4.0, 5.0],
        "y": ["a", "b", "c", "d", "e"],
    })


@pytest.fixture
def baseline(
    tmp_cache: Path, sample_df: pd.DataFrame,
) -> tuple[Path, Path, dict]:
    """Write a valid pair via ``write_cache_atomic_subdir`` and return
    the parquet path, sidecar path, and meta dict."""
    parquet_path, meta_path = write_cache_atomic_subdir(
        subdir=SUBDIR,
        filename=FILENAME,
        df=sample_df,
        meta={"indicator_id": "smoke", "source": "test"},
        cache_root=tmp_cache,
    )
    meta = json.loads(meta_path.read_text())
    return parquet_path, meta_path, meta


def test_validated_cache_read_recomputes_sha(
    tmp_cache: Path, sample_df: pd.DataFrame, baseline,
) -> None:
    """POS — A successful round trip returns df + meta with ``data_sha256``."""
    df, meta = read_cache_validated_subdir(
        subdir=SUBDIR, filename=FILENAME, cache_root=tmp_cache,
    )
    pd.testing.assert_frame_equal(df, sample_df)
    assert "data_sha256" in meta
    assert len(meta["data_sha256"]) == 64
    # Sanity: row_count matches.
    assert meta["row_count"] == len(sample_df)


def test_corrupted_parquet_raises_CacheValidationError(
    tmp_cache: Path, baseline,
) -> None:
    """NEG — Flipping one byte in the parquet must raise."""
    parquet_path, _meta_path, _meta = baseline
    with parquet_path.open("rb+") as f:
        f.seek(64)
        b = f.read(1)
        f.seek(64)
        f.write(bytes([(b[0] ^ 0xFF) & 0xFF]))
    with pytest.raises(CacheValidationError, match="sha256 mismatch"):
        read_cache_validated_subdir(
            subdir=SUBDIR, filename=FILENAME, cache_root=tmp_cache,
        )


def test_modified_sidecar_raises_CacheValidationError(
    tmp_cache: Path, baseline,
) -> None:
    """NEG — Tampered sidecar (data_sha256 changed) must raise."""
    _parquet_path, meta_path, _meta = baseline
    md = json.loads(meta_path.read_text())
    md["data_sha256"] = "0" * 64
    meta_path.write_text(json.dumps(md, indent=2))
    with pytest.raises(CacheValidationError, match="sha256 mismatch"):
        read_cache_validated_subdir(
            subdir=SUBDIR, filename=FILENAME, cache_root=tmp_cache,
        )


def test_missing_sidecar_raises_FileNotFoundError(
    tmp_cache: Path, baseline,
) -> None:
    """NEG — Parquet present but sidecar deleted must raise."""
    _parquet_path, meta_path, _meta = baseline
    meta_path.unlink()
    with pytest.raises(FileNotFoundError, match="sidecar not found"):
        read_cache_validated_subdir(
            subdir=SUBDIR, filename=FILENAME, cache_root=tmp_cache,
        )
