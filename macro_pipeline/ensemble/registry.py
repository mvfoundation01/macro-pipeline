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
    resolved = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    if not resolved.is_file():
        raise FileNotFoundError(
            f"Metrics registry not found: {resolved}"
        )
    with open(resolved, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(
            f"Registry YAML root at {resolved} is not a mapping; got "
            f"{type(raw).__name__}"
        )
    if "metrics" not in raw:
        raise ValueError(
            f"Registry YAML at {resolved} missing required key 'metrics'"
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
    frozen dataclass invariant.
    """
    # Copy to avoid mutating caller's dict.
    fields = dict(raw)
    if fields.get("typical_range") is not None:
        fields["typical_range"] = tuple(fields["typical_range"])
    if fields.get("citations") is not None:
        fields["citations"] = tuple(fields["citations"])
    return MetricMetadata(**fields)


def _to_dict(metadata: MetricMetadata) -> dict:
    """Convert MetricMetadata to dict (for YAML safe_dump)."""
    return asdict(metadata)
