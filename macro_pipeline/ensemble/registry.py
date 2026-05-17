"""Metrics registry YAML I/O for L6 ensemble aggregation (L6-A).

Per Strategic L6-A inline spec §3 Step 5. Loads + saves the Vision §3
ninety-measurement catalogue as a dict[metric_id, MetricMetadata]; mirrors
the L1.7-C persistence-layer pattern (sibling tmp + os.replace atomic
write; YAML safe_load/safe_dump).

Default registry location: ``macro_pipeline/ensemble/data/metrics_registry.yaml``
(co-located with the consuming module; included in the wheel build per
hatchling ``packages = ["macro_pipeline"]`` directive in pyproject.toml).

Public API
----------
``load_metrics_registry(path)``      Load YAML -> dict[metric_id, MetricMetadata].
``save_metrics_registry(reg, path)`` Save dict -> YAML (sorted by subcategory_index then metric_id).
``DEFAULT_REGISTRY_PATH``            Path to the in-package registry.
"""
from __future__ import annotations

import contextlib
import functools
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Union

import yaml

from macro_pipeline.ensemble.metadata import MetricMetadata

# Default path inside the package (relative to this file).
DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parent / "data" / "metrics_registry.yaml"
)


@functools.lru_cache(maxsize=1)
def _load_default_registry_cached() -> Dict[str, MetricMetadata]:
    """L6-J D5 — cached default-path loader.

    Per Codex R7 Finding #3 (C-12), the YAML registry is large (90
    entries, ~2000 lines) and re-parsing it on every aggregator call
    is wasteful. The cache is keyed on the default path (singleton
    maxsize=1); explicit-path loads via ``load_metrics_registry(path)``
    bypass the cache and re-parse on each call (tests + tools may
    need this behaviour).

    The cache stores a frozen dict of MetricMetadata instances; all
    are frozen dataclasses so the returned dict reference is safe to
    share across callers (no defensive copy needed unless the caller
    intends to mutate the OUTER dict, in which case caller responsibility).
    """
    return _load_registry_from_path(DEFAULT_REGISTRY_PATH)


def _clear_registry_cache_for_testing() -> None:
    """L6-J D5 — test-only helper to clear the default-loader cache.

    NOT public API. Tests that mutate the YAML file or need a clean
    re-parse can call this to invalidate the singleton cache.
    """
    _load_default_registry_cached.cache_clear()


def _load_registry_from_path(
    path: Path,
) -> Dict[str, MetricMetadata]:
    """Uncached registry loader. Used by both the cached default-path
    loader and explicit-path loads. Splitting cached vs uncached keeps
    the cache hot path narrow + the I/O implementation single-source.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Metrics registry not found: {path}")
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(
            f"Registry YAML root at {path} is not a mapping; got "
            f"{type(raw).__name__}"
        )
    if "metrics" not in raw:
        raise ValueError(
            f"Registry YAML at {path} missing required key 'metrics'"
        )

    registry: Dict[str, MetricMetadata] = {}
    for entry in raw["metrics"]:
        metadata = _from_dict(entry)
        if metadata.metric_id in registry:
            raise ValueError(
                f"Duplicate metric_id in registry: "
                f"{metadata.metric_id!r}"
            )
        registry[metadata.metric_id] = metadata
    return registry


def load_metrics_registry(
    path: Union[str, Path, None] = None,
) -> Dict[str, MetricMetadata]:
    """Load metrics registry from YAML.

    Parameters
    ----------
    path
        If ``None``, uses ``DEFAULT_REGISTRY_PATH`` (the in-package
        Vision §3 catalogue). Otherwise loads from the supplied path.

    Returns
    -------
    dict[str, MetricMetadata]
        Mapping ``metric_id -> MetricMetadata``.

    Raises
    ------
    FileNotFoundError
        If the path does not exist.
    ValueError
        If the YAML root is not a mapping, the ``metrics`` key is
        missing, or a duplicate ``metric_id`` is detected.
    yaml.YAMLError
        For malformed YAML (propagated from ``yaml.safe_load``).
    """
    # L6-J D5 — default path goes through the singleton cache; explicit
    # paths bypass for tools/tests that need fresh parses.
    if path is None:
        return _load_default_registry_cached()
    return _load_registry_from_path(Path(path))


def validate_registry_counts(
    registry: Dict[str, MetricMetadata],
    expected_computed: int = 40,
    expected_deferred: int = 50,
) -> Dict[str, int]:
    """L6-J D4 — validate registry computed/deferred split per Track A L6-G claim.

    Counts entries by ``derive_status()`` and compares to expected
    values. Raises ``ValueError`` on mismatch; returns the counts dict
    on success.

    L6-G claimed 40 computed + 50 deferred (32 L7 + 18 L8a). Codex
    R7 #6 cited 36 L7 + 14 L8a (different split). This helper enables
    regression detection if the actual split drifts from the claimed
    count at the time of audit. The L6_J_TEST_COUNT_AUDIT.md document
    captures the empirical split.

    Parameters
    ----------
    registry
        Loaded registry dict.
    expected_computed
        Expected count of entries where derive_status() == "computed".
    expected_deferred
        Expected count of entries where derive_status() == "deferred".

    Returns
    -------
    dict[str, int]
        ``{"computed": n_computed, "deferred": n_deferred,
        "deferred_to_l7": n_l7, "deferred_to_l8a": n_l8a, "total": n}``.

    Raises
    ------
    ValueError
        If counts don't match expected (when expected_* are not None).
    """
    n_computed = 0
    n_deferred = 0
    n_l7 = 0
    n_l8a = 0
    for m in registry.values():
        status = m.derive_status()
        if status == "computed":
            n_computed += 1
        else:
            n_deferred += 1
            if m.deferred_to == "L7":
                n_l7 += 1
            elif m.deferred_to == "L8a":
                n_l8a += 1
    total = n_computed + n_deferred
    counts = {
        "computed": n_computed,
        "deferred": n_deferred,
        "deferred_to_l7": n_l7,
        "deferred_to_l8a": n_l8a,
        "total": total,
    }
    if expected_computed is not None and n_computed != expected_computed:
        raise ValueError(
            f"Registry computed count {n_computed} != expected "
            f"{expected_computed} (counts: {counts})"
        )
    if expected_deferred is not None and n_deferred != expected_deferred:
        raise ValueError(
            f"Registry deferred count {n_deferred} != expected "
            f"{expected_deferred} (counts: {counts})"
        )
    return counts


def save_metrics_registry(
    registry: Dict[str, MetricMetadata],
    path: Union[str, Path],
) -> None:
    """Save metrics registry to YAML atomically.

    Sorted deterministically by (subcategory_index, metric_id) for
    stable diff-able output. Uses sibling-tmp + ``os.replace`` atomic
    write pattern (mirrors L1.7-C ``save_manual_inputs_atomic``).
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    sorted_entries = sorted(
        registry.values(),
        key=lambda m: (m.subcategory_index, m.metric_id),
    )
    raw = {
        "registry_version": 1,
        "n_metrics": len(sorted_entries),
        "metrics": [_to_dict(m) for m in sorted_entries],
    }

    tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                raw, f, default_flow_style=False, sort_keys=False
            )
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp), str(target))
    except Exception:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise


def _from_dict(raw: dict) -> MetricMetadata:
    """Convert dict (parsed YAML entry) to MetricMetadata.

    YAML deserializes tuples as lists; convert back to tuples for the
    frozen dataclass invariant. L6-J D4 lineage object is also
    reconstructed from a nested dict when present.
    """
    # Copy to avoid mutating caller's dict.
    fields = dict(raw)
    if fields.get("typical_range") is not None:
        fields["typical_range"] = tuple(fields["typical_range"])
    if fields.get("citations") is not None:
        fields["citations"] = tuple(fields["citations"])
    # L6-J D4 — reconstruct MetricLineage from nested dict (YAML may
    # round-trip via asdict() / safe_dump as a flat dict).
    if fields.get("lineage") is not None and isinstance(
        fields["lineage"], dict
    ):
        from macro_pipeline.ensemble.metadata import MetricLineage
        fields["lineage"] = MetricLineage(**fields["lineage"])
    return MetricMetadata(**fields)


def _to_dict(metadata: MetricMetadata) -> dict:
    """Convert MetricMetadata to dict (for YAML safe_dump)."""
    return asdict(metadata)
