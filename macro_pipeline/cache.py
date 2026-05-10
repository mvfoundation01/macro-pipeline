"""Atomic cache writes with sha256 + schema_version + row_count validation.

Layer 1.5A.5 (Codex review HIGH #6).

Invariants
----------
- Parquet is written *first*, then metadata is enriched with the parquet's
  sha256 and atomically committed on top of the old metadata. A crash mid-
  write leaves either the old (parquet, meta) pair fully intact or a
  ``.tmp`` sidecar that ``read_cache_validated`` will refuse to load.
- ``read_cache_validated`` rejects caches whose schema_version does not
  match SCHEMA_VERSION, whose stored sha256 does not match the parquet's
  bytes, or whose row_count does not match the parquet's row count.
- Cross-platform atomic rename via ``Path.replace`` (== ``os.replace``).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Atomic primitives
# ---------------------------------------------------------------------------
def _tmp_for(path: Path) -> Path:
    """Sibling tmp file with random suffix to avoid same-name collisions."""
    return path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically via tmp + fsync + replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_for(path)
    try:
        with tmp.open("wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            import contextlib
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise


def atomic_write_parquet(path: Path, df: pd.DataFrame) -> None:
    """Write ``df`` to ``path`` as parquet atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_for(path)
    try:
        df.to_parquet(tmp)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            import contextlib
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise


# ---------------------------------------------------------------------------
# Cache metadata format
# ---------------------------------------------------------------------------
def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_cache_atomic(
    stem: str,
    df: pd.DataFrame,
    meta: dict,
    cache_dir: Path,
    *,
    pipeline_processed: bool | None = None,
) -> tuple[Path, Path]:
    """Write ``<stem>.parquet`` + ``<stem>.meta.json`` atomically.

    Order:
      1. parquet first (so its bytes can be hashed)
      2. enrich meta with data_sha256/schema_version/row_count/cache_written_at
         (and optionally pipeline_processed)
      3. atomically commit meta

    Returns the two paths written (parquet, meta).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = cache_dir / f"{stem}.parquet"
    meta_path = cache_dir / f"{stem}.meta.json"

    atomic_write_parquet(parquet_path, df)
    data_sha256 = _sha256_file(parquet_path)

    meta_full = dict(meta)
    meta_full["data_sha256"] = data_sha256
    meta_full["schema_version"] = SCHEMA_VERSION
    meta_full["row_count"] = len(df)
    meta_full["cache_written_at"] = pd.Timestamp.now().isoformat()
    if pipeline_processed is not None:
        meta_full["pipeline_processed"] = bool(pipeline_processed)

    payload = json.dumps(meta_full, default=str, indent=2).encode("utf-8")
    atomic_write_bytes(meta_path, payload)
    return parquet_path, meta_path


def write_pickle_atomic_with_meta(
    *,
    pickle_path: Path,
    pickle_bytes: bytes,
    meta: dict,
) -> tuple[Path, Path]:
    """Atomically write a pickle artifact + sidecar ``.meta.json``.

    Layer 3.5A.AM3: pickle artifacts have a different schema from
    parquet caches (no ``row_count``; instead carry hmmlearn version,
    pickle protocol, training-script sha, etc.). Rather than overload
    the parquet-shaped ``write_cache_atomic`` we keep a parallel
    helper with a focused contract:

      1. Write ``pickle_bytes`` to ``pickle_path`` atomically (tmp +
         fsync + replace).
      2. Compute the pickle's sha256 from disk and stamp it onto
         ``meta`` as ``data_sha256``.
      3. Stamp ``schema_version`` (from ``meta`` if present, else
         ``SCHEMA_VERSION``) and ``cache_written_at`` if not already
         set by caller.
      4. Atomically write ``meta`` JSON next to the pickle as
         ``<pickle_path>.meta.json`` (i.e. ``regime_3state_v1.pkl`` →
         ``regime_3state_v1.meta.json``).

    Returns ``(pickle_path, meta_path)``.
    """
    pickle_path = Path(pickle_path)
    pickle_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(pickle_path, pickle_bytes)

    data_sha256 = _sha256_file(pickle_path)
    meta_full = dict(meta)
    meta_full["data_sha256"] = data_sha256
    meta_full.setdefault("schema_version", meta.get("schema_version", SCHEMA_VERSION))
    meta_full.setdefault("cache_written_at", pd.Timestamp.now().isoformat())

    meta_path = pickle_path.with_suffix(".meta.json")
    payload = json.dumps(meta_full, default=str, indent=2).encode("utf-8")
    atomic_write_bytes(meta_path, payload)
    return pickle_path, meta_path


def read_cache_validated(
    stem: str,
    cache_dir: Path,
) -> tuple[pd.DataFrame, dict] | None:
    """Read cache validating schema_version, sha256, and row_count.

    Returns ``None`` (and logs at WARNING) if either file is missing,
    the metadata is corrupt JSON, the schema_version does not match,
    the row count does not match, or the sha256 does not match.

    Caches written before A.5 (no ``data_sha256``/``schema_version``)
    are rejected. Callers that need to read legacy caches should fall
    back to ``pd.read_parquet`` directly until those caches are
    rewritten through ``write_cache_atomic``.
    """
    parquet_path = cache_dir / f"{stem}.parquet"
    meta_path = cache_dir / f"{stem}.meta.json"
    if not (parquet_path.exists() and meta_path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_bytes())
    except json.JSONDecodeError:
        log.warning("Cache %s: meta.json is not valid JSON; invalidating.", stem)
        return None

    if meta.get("schema_version") != SCHEMA_VERSION:
        log.warning(
            "Cache %s: schema_version mismatch (cached=%s, current=%s); invalidating.",
            stem, meta.get("schema_version"), SCHEMA_VERSION,
        )
        return None

    expected_hash = meta.get("data_sha256")
    actual_hash = _sha256_file(parquet_path)
    if expected_hash and actual_hash != expected_hash:
        log.warning("Cache %s: sha256 mismatch; invalidating.", stem)
        return None

    df = pd.read_parquet(parquet_path)
    expected_rows = meta.get("row_count")
    if expected_rows is not None and len(df) != int(expected_rows):
        log.warning(
            "Cache %s: row_count mismatch (cached=%s, actual=%d); invalidating.",
            stem, expected_rows, len(df),
        )
        return None
    return df, meta


__all__ = [
    "SCHEMA_VERSION",
    "atomic_write_bytes",
    "atomic_write_parquet",
    "read_cache_validated",
    "write_cache_atomic",
    "write_pickle_atomic_with_meta",
]
