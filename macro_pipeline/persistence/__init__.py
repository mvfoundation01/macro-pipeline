"""L7 persistence module — parquet-based forecast output storage.

Per Strategic L7 single-sub-phase pre-flight 2026-05-16
(ACCELERATION PROTOCOL v1.0).

Public API
----------
``ForecastRecord``            Frozen per-horizon forecast record dataclass.
``ParquetForecastStore``      Schema-versioned, monthly-partitioned parquet store.
``SCHEMA_VERSION``            ``"v1"``; bump on schema-breaking change.
"""
from __future__ import annotations

from .parquet_store import (
    SCHEMA_VERSION,
    ForecastRecord,
    ParquetForecastStore,
)

__all__ = [
    "SCHEMA_VERSION",
    "ForecastRecord",
    "ParquetForecastStore",
]
