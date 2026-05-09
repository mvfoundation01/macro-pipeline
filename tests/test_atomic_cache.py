"""Tests for src.cache atomic-write + sha256 + schema_version (Layer 1.5A.5)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.cache import (
    SCHEMA_VERSION,
    atomic_write_bytes,
    atomic_write_parquet,
    read_cache_validated,
    write_cache_atomic,
)


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Path:
    d = tmp_path / "cache"
    d.mkdir()
    return d


@pytest.fixture
def sample_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    return pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0, 5.0]}, index=idx)


# ---------------------------------------------------------------------------
# Atomic primitives
# ---------------------------------------------------------------------------
def test_atomic_write_bytes_no_orphan_after_success(tmp_cache):
    p = tmp_cache / "out.bin"
    atomic_write_bytes(p, b"hello")
    assert p.read_bytes() == b"hello"
    # No leftover .tmp files.
    leftover = list(tmp_cache.glob(".*.tmp"))
    assert leftover == []


def test_atomic_write_parquet_round_trips(tmp_cache, sample_df):
    p = tmp_cache / "out.parquet"
    atomic_write_parquet(p, sample_df)
    back = pd.read_parquet(p)
    # parquet round-trip drops the DatetimeIndex.freq attr; check the
    # values and the index entries explicitly.
    pd.testing.assert_frame_equal(back, sample_df, check_freq=False)
    leftover = list(tmp_cache.glob(".*.tmp"))
    assert leftover == []


# ---------------------------------------------------------------------------
# write_cache_atomic / read_cache_validated round-trip
# ---------------------------------------------------------------------------
def test_write_cache_atomic_populates_required_meta_fields(tmp_cache, sample_df):
    write_cache_atomic("foo", sample_df, {"indicator_id": "FOO"}, tmp_cache,
                       pipeline_processed=True)

    meta = json.loads((tmp_cache / "foo.meta.json").read_bytes())
    assert meta["indicator_id"] == "FOO"
    assert meta["schema_version"] == SCHEMA_VERSION
    assert meta["row_count"] == len(sample_df)
    assert "data_sha256" in meta and len(meta["data_sha256"]) == 64
    assert meta["pipeline_processed"] is True
    assert "cache_written_at" in meta


def test_read_cache_validated_round_trip(tmp_cache, sample_df):
    write_cache_atomic("bar", sample_df, {"indicator_id": "BAR"}, tmp_cache,
                       pipeline_processed=True)
    result = read_cache_validated("bar", tmp_cache)
    assert result is not None
    df, meta = result
    pd.testing.assert_frame_equal(df, sample_df, check_freq=False)
    assert meta["indicator_id"] == "BAR"


def test_cache_hash_mismatch_invalidates(tmp_cache, sample_df):
    write_cache_atomic("baz", sample_df, {}, tmp_cache, pipeline_processed=True)
    parquet_path = tmp_cache / "baz.parquet"
    # Tamper with the parquet so its sha256 no longer matches the meta.
    parquet_path.write_bytes(parquet_path.read_bytes() + b"\x00")
    assert read_cache_validated("baz", tmp_cache) is None


def test_cache_schema_version_mismatch_invalidates(tmp_cache, sample_df):
    write_cache_atomic("qux", sample_df, {}, tmp_cache, pipeline_processed=True)
    meta_path = tmp_cache / "qux.meta.json"
    meta = json.loads(meta_path.read_bytes())
    meta["schema_version"] = "0.0-legacy"
    meta_path.write_bytes(json.dumps(meta).encode())
    assert read_cache_validated("qux", tmp_cache) is None


def test_cache_row_count_mismatch_invalidates(tmp_cache, sample_df):
    write_cache_atomic("zap", sample_df, {}, tmp_cache, pipeline_processed=True)
    meta_path = tmp_cache / "zap.meta.json"
    meta = json.loads(meta_path.read_bytes())
    # Hash will be recomputed against the parquet on read; we keep the
    # parquet untouched but lie about the row count to prove the
    # row-count check is independent.
    meta["row_count"] = 99
    meta_path.write_bytes(json.dumps(meta).encode())
    assert read_cache_validated("zap", tmp_cache) is None


def test_read_cache_validated_returns_none_when_meta_missing(tmp_cache, sample_df):
    parquet_path = tmp_cache / "nometa.parquet"
    sample_df.to_parquet(parquet_path)
    assert read_cache_validated("nometa", tmp_cache) is None


def test_no_tmp_files_after_successful_write(tmp_cache, sample_df):
    """Codex HIGH #6 acceptance: the .tmp file must be renamed on success."""
    write_cache_atomic("clean", sample_df, {"indicator_id": "CLEAN"}, tmp_cache,
                       pipeline_processed=True)
    leftover = list(tmp_cache.glob(".*.tmp"))
    assert leftover == [], f"Unexpected .tmp leftovers: {leftover}"
