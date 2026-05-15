"""MANUAL_INPUT persistence + versioning + migration (L1.7-C).

Per Strategic L1.7-C inline spec (post-L1.7-B 2026-05-15): robust YAML
serialization, atomic write, schema-version detection, migration shims,
and replication-kit-compatible metadata (Vision v2.0 §14).

Public API
----------
``LoadResult``                Frozen wrapper for loaded schedule + metadata.
``load_manual_inputs_robust`` File-existence + parse + version + migration.
``save_manual_inputs_atomic`` Atomic YAML write via sibling tmp + os.replace.
``migrate_manual_inputs``     Version-dispatch shim (returns dict, applied, warnings).
``ManualInputLoadError``      Load failure (ValueError subclass).
``ManualInputMigrationError`` Migration failure (ValueError subclass).

Atomic-write pattern follows ``macro_pipeline.cache.atomic_write_bytes``
precedent: sibling tmp file (uuid-suffixed) → fsync → ``os.replace`` →
cleanup-on-failure. ``os.replace`` is atomic on both POSIX and Windows
(Python 3.3+ docs).

Migration matrix (v -> 1)
-------------------------
v=1: no-op (migration_applied=False; no warnings).
v=2: forward-compat shim — drop v2-specific fields with warning;
     migration_applied=True. (Placeholder for future v2 spec.)
v=0: NOT IMPLEMENTED → ManualInputMigrationError.
other: ManualInputMigrationError.

Replication kit metadata (per Vision v2.0 §14)
----------------------------------------------
Stamped on every LoadResult as ``replication_kit_metadata`` (tuple-of-pairs
for frozen invariant): ``code_sha`` (current git HEAD), ``load_timestamp_iso``
(UTC ISO 8601), ``schema_version_detected`` (str of int), ``migration_applied``
(str of bool).
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

import yaml

from macro_pipeline.manual_input.schema import (
    ManualInputSchedule,
    _from_dict,
    _to_dict,
)

# Current schema version supported by loaders + savers (mirrors
# schema.SCHEMA_VERSION_CURRENT; duplicated here so persistence is
# self-contained at module load time).
TARGET_SCHEMA_VERSION = 1


class ManualInputLoadError(ValueError):
    """Failure to load a ManualInputSchedule from YAML.

    Causes: file not found; malformed YAML; missing schema_version;
    non-integer schema_version; post-migration dataclass construction
    failure.
    """


class ManualInputMigrationError(ValueError):
    """Failure to migrate raw dict to target schema version.

    Causes: no migration path available for the detected version (e.g.
    v0 → v1 not implemented; unknown version).
    """


@dataclass(frozen=True)
class LoadResult:
    """Wraps loaded ManualInputSchedule + load metadata.

    Frozen invariant requires all field types to be immutable; warnings
    + replication_kit_metadata are tuple containers (not list/dict) for
    that reason. Use ``dict(result.replication_kit_metadata)`` to get a
    mutable copy if needed.

    Fields:
        schedule                 The loaded ManualInputSchedule.
        source_path              Absolute/relative path the file was loaded
                                 from (as passed by caller).
        load_timestamp_iso       ISO 8601 UTC timestamp of load.
        schema_version_detected  Version found in source YAML before
                                 migration.
        migration_applied        True iff migrate_manual_inputs returned a
                                 non-trivial migration.
        warnings                 Warnings emitted by the migration pass.
        replication_kit_metadata Tuple of (key, value) pairs per Vision §14.
    """

    schedule: ManualInputSchedule
    source_path: str
    load_timestamp_iso: str
    schema_version_detected: int
    migration_applied: bool
    warnings: Tuple[str, ...]
    replication_kit_metadata: Tuple[Tuple[str, str], ...]


def load_manual_inputs_robust(path: str) -> LoadResult:
    """Load a ManualInputSchedule with version detection + migration + metadata.

    Pipeline:
        1. File-existence check → ManualInputLoadError if missing.
        2. YAML parse → ManualInputLoadError on syntax error or non-dict root.
        3. schema_version detection → ManualInputLoadError if missing/non-int.
        4. migration dispatch via migrate_manual_inputs().
        5. ManualInputSchedule construction via schema._from_dict.
        6. Replication-kit metadata stamp.

    Raises:
        ManualInputLoadError       Stage 1-3 or stage 5 (construction)
                                   failure.
        ManualInputMigrationError  Stage 4 (no migration path).
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise ManualInputLoadError(f"Manual input file not found: {path}")

    try:
        with open(file_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ManualInputLoadError(f"Malformed YAML at {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ManualInputLoadError(
            f"YAML root at {path} is not a mapping; got "
            f"{type(raw).__name__}"
        )
    if "schema_version" not in raw:
        raise ManualInputLoadError(
            f"Missing schema_version key in {path}"
        )
    detected_version = raw["schema_version"]
    if not isinstance(detected_version, int) or isinstance(detected_version, bool):
        raise ManualInputLoadError(
            f"schema_version must be int; got "
            f"{type(detected_version).__name__} ({detected_version!r})"
        )

    migrated_raw, migration_applied, warnings = migrate_manual_inputs(
        raw, target_version=TARGET_SCHEMA_VERSION
    )

    try:
        schedule = _from_dict(migrated_raw)
    except (TypeError, ValueError, KeyError) as exc:
        raise ManualInputLoadError(
            f"Failed to construct ManualInputSchedule from {path} after "
            f"migration: {exc}"
        ) from exc

    load_timestamp = datetime.now(timezone.utc).isoformat()
    code_sha = _get_current_code_sha()
    replication_metadata: Tuple[Tuple[str, str], ...] = (
        ("code_sha", code_sha),
        ("load_timestamp_iso", load_timestamp),
        ("schema_version_detected", str(detected_version)),
        ("migration_applied", str(migration_applied)),
    )

    return LoadResult(
        schedule=schedule,
        source_path=str(path),
        load_timestamp_iso=load_timestamp,
        schema_version_detected=detected_version,
        migration_applied=migration_applied,
        warnings=tuple(warnings),
        replication_kit_metadata=replication_metadata,
    )


def save_manual_inputs_atomic(schedule: ManualInputSchedule, path: str) -> None:
    """Save a ManualInputSchedule to YAML atomically.

    Follows ``cache.atomic_write_bytes`` precedent: write to sibling
    tmp file (uuid-suffixed) → flush + fsync → ``os.replace`` for
    atomic rename. Cleanup tmp on any failure; pre-existing target
    file is left untouched if the write phase fails.

    ``os.replace`` is atomic on both POSIX and Windows (Python 3.3+).
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_for(target)
    try:
        with tmp.open("w", encoding="utf-8") as f:
            raw = _to_dict(schedule)
            yaml.safe_dump(raw, f, default_flow_style=False, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp), str(target))
    except Exception:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise


def migrate_manual_inputs(
    raw: dict,
    target_version: int = TARGET_SCHEMA_VERSION,
) -> Tuple[dict, bool, List[str]]:
    """Migrate raw dict to target_version.

    Returns:
        (migrated_raw, migration_applied, warnings)

    Raises:
        ManualInputMigrationError: no migration path available.

    Migration matrix (target_version=1):
        detected=1: no-op (returns input unchanged; migration_applied=False).
        detected=2: forward-compat shim; schema_version coerced to 1,
                    warning emitted that v2-specific fields are dropped.
                    Placeholder for a future v2 spec.
        detected=0: NOT IMPLEMENTED (raises ManualInputMigrationError).
        other:      raises ManualInputMigrationError.

    Migrations to target_version != 1 are not supported at L1.7-C.
    """
    detected = raw.get("schema_version")

    if detected == target_version:
        return raw, False, []

    if target_version == 1 and detected == 2:
        migrated = dict(raw)
        migrated["schema_version"] = 1
        warning = (
            "schema_version=2 detected; forward-compat shim active. "
            "v2-specific fields not in v1 spec will be dropped on "
            "ManualInputSchedule construction. Recommend regenerating "
            "with current spec (v1)."
        )
        return migrated, True, [warning]

    if target_version == 1 and detected == 0:
        raise ManualInputMigrationError(
            "schema_version=0 detected; v0 -> v1 migration NOT "
            "IMPLEMENTED. Regenerate with current spec (v1)."
        )

    raise ManualInputMigrationError(
        f"No migration path from schema_version={detected!r} to "
        f"target_version={target_version}"
    )


def _tmp_for(path: Path) -> Path:
    """Sibling tmp file with uuid suffix.

    Mirrors ``macro_pipeline.cache._tmp_for`` pattern (private to cache,
    duplicated here to keep manual_input self-contained without crossing
    package boundaries inward).
    """
    return path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")


def _get_current_code_sha() -> str:
    """Get current git commit SHA for replication kit metadata.

    Returns ``"unknown"`` if git is unavailable, the timeout fires, or
    we're not in a git repository. Vision v2.0 §14 mandates capturing
    code identity in replication kit; absence of git is non-fatal.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            if sha:
                return sha
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "unknown"
