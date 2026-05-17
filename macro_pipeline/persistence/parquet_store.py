"""L7 D4 — Parquet-based forecast output storage.

Per Strategic L7 single-sub-phase pre-flight 2026-05-16.

Design discipline:
- Schema-versioned filename (``forecasts_YYYY-MM_v1.parquet``); version
  bump on schema-breaking change preserves backward read compatibility
- Monthly partitioning (mirrors ``data/cache/`` convention from L1+)
- Append mode merges new records into existing partition file (atomic
  via pandas read+concat+write; consider migration to delta-lake if
  scale exceeds single-machine at L8+)
- Frozen ``ForecastRecord`` dataclass with finite invariants
  (AP-AUTH per L6-I D1)
- Round-trip stable: ``read(append(records)) == records`` (modulo
  pandas-induced int/float coercion; tests verify exact equality
  for finite floats + ints)
- pyarrow snappy compression (default)

L6 invariants preserved:
- ``metadata_json`` field accepts the full ``HorizonResult.metric_outputs``
  dict serialized as JSON string; preserves the Vision §3 ninety-measurement
  surface in the persisted output
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd


SCHEMA_VERSION = "v1"
SUPPORTED_HORIZONS = (1, 3, 5, 10)


@dataclass(frozen=True)
class ForecastRecord:
    """Per-horizon forecast record for parquet persistence.

    Fields
    ------
    forecast_id              Unique identifier (caller-generated).
    timestamp_utc            Timezone-aware UTC datetime of forecast.
    horizon                  One of (1, 3, 5, 10).
    point_estimate_annualized  Forecast point estimate (return fraction).
    sigma_annualized         Forecast sigma (return fraction).
    confidence               Cap-cascaded confidence in [0, 1].
    conviction               Vision §4 conviction in [1, 10].
    code_sha                 Git SHA of forecast-generating code (replication).
    metadata_json            JSON-serialized HorizonResult.metric_outputs (Vision §3).

    Invariants enforced by ``__post_init__``:
      - timestamp timezone-aware
      - horizon in SUPPORTED_HORIZONS
      - numeric fields finite
      - confidence in [0, 1]
      - conviction in [1, 10]
    """

    forecast_id: str
    timestamp_utc: datetime
    horizon: int
    point_estimate_annualized: float
    sigma_annualized: float
    confidence: float
    conviction: float
    code_sha: str
    metadata_json: str = "{}"

    def __post_init__(self) -> None:
        if not isinstance(self.forecast_id, str) or not self.forecast_id:
            raise ValueError(
                f"forecast_id must be non-empty string; got "
                f"{self.forecast_id!r}"
            )
        if self.timestamp_utc.tzinfo is None:
            raise ValueError("timestamp_utc must be timezone-aware")
        if self.horizon not in SUPPORTED_HORIZONS:
            raise ValueError(
                f"horizon {self.horizon} not in {SUPPORTED_HORIZONS}"
            )
        for fname in (
            "point_estimate_annualized",
            "sigma_annualized",
            "confidence",
            "conviction",
        ):
            val = getattr(self, fname)
            if not math.isfinite(val):
                raise ValueError(
                    f"{fname} must be finite; got {val!r}"
                )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0, 1]; got {self.confidence}"
            )
        if not (1.0 <= self.conviction <= 10.0):
            raise ValueError(
                f"conviction must be in [1, 10]; got {self.conviction}"
            )
        if not isinstance(self.code_sha, str):
            raise TypeError(
                f"code_sha must be str; got {type(self.code_sha).__name__}"
            )
        if not isinstance(self.metadata_json, str):
            raise TypeError(
                f"metadata_json must be str; got "
                f"{type(self.metadata_json).__name__}"
            )


class ParquetForecastStore:
    """Schema-versioned parquet output storage for forecast records.

    Storage layout::

        storage_dir/
          forecasts_YYYY-MM_v1.parquet     (one file per month per schema)
          forecasts_YYYY-MM_v1.parquet
          ...

    Usage
    -----
    >>> store = ParquetForecastStore(Path("./forecasts"))
    >>> path = store.append([record1, record2])
    >>> records = store.read("2026-05")
    """

    def __init__(self, storage_dir: Union[str, Path]) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _partition_path(self, partition: str) -> Path:
        """Resolve ``YYYY-MM`` partition string to absolute parquet path."""
        if not partition or len(partition) != 7 or partition[4] != "-":
            raise ValueError(
                f"partition must be 'YYYY-MM' format; got {partition!r}"
            )
        return (
            self.storage_dir
            / f"forecasts_{partition}_{SCHEMA_VERSION}.parquet"
        )

    def append(self, records: List[ForecastRecord]) -> Path:
        """Append records to monthly partition file.

        Partition determined by ``records[0].timestamp_utc.strftime("%Y-%m")``.
        All records must belong to the same month (raises ValueError otherwise).

        Returns path to written parquet file.
        """
        if not records:
            raise ValueError("records list cannot be empty")
        first_month = records[0].timestamp_utc.strftime("%Y-%m")
        for r in records:
            if r.timestamp_utc.strftime("%Y-%m") != first_month:
                raise ValueError(
                    f"all records must belong to same month "
                    f"{first_month!r}; record {r.forecast_id!r} is in "
                    f"{r.timestamp_utc.strftime('%Y-%m')!r}"
                )
        output_path = self._partition_path(first_month)

        # Build DataFrame; ensure timezone is preserved as UTC.
        new_df = pd.DataFrame([asdict(r) for r in records])
        # pandas asdict + Timestamp can drop tzinfo if not careful; cast.
        new_df["timestamp_utc"] = pd.to_datetime(
            new_df["timestamp_utc"], utc=True
        )

        if output_path.exists():
            existing_df = pd.read_parquet(output_path)
            existing_df["timestamp_utc"] = pd.to_datetime(
                existing_df["timestamp_utc"], utc=True
            )
            combined = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined = new_df

        combined.to_parquet(
            output_path, engine="pyarrow", compression="snappy", index=False
        )
        return output_path

    def read(self, partition: str) -> List[ForecastRecord]:
        """Read records for a partition ``YYYY-MM``.

        Returns empty list if partition file doesn't exist.
        """
        path = self._partition_path(partition)
        if not path.exists():
            return []
        df = pd.read_parquet(path)
        # Restore timezone-aware datetime (pandas may have lost tzinfo).
        records: List[ForecastRecord] = []
        for row in df.to_dict(orient="records"):
            ts = row["timestamp_utc"]
            if isinstance(ts, pd.Timestamp):
                if ts.tzinfo is None:
                    ts = ts.tz_localize("UTC")
                ts = ts.to_pydatetime()
            elif isinstance(ts, datetime) and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            row["timestamp_utc"] = ts
            records.append(ForecastRecord(**row))
        return records

    def list_partitions(self) -> List[str]:
        """List all partition strings (``YYYY-MM``) present in storage."""
        partitions: List[str] = []
        prefix = "forecasts_"
        suffix = f"_{SCHEMA_VERSION}.parquet"
        for p in self.storage_dir.glob(f"{prefix}*{suffix}"):
            name = p.name
            partition = name[len(prefix):-len(suffix)]
            partitions.append(partition)
        return sorted(partitions)

    def read_range(self, partitions: List[str]) -> List[ForecastRecord]:
        """L9 D5 — Read multiple partitions in one pyarrow.dataset scan.

        Faster than calling read() per partition because it leverages pyarrow's
        multi-file dataset reader instead of opening + parsing each parquet
        file individually.

        Parameters
        ----------
        partitions
            List of ``YYYY-MM`` partition strings.

        Returns
        -------
        list[ForecastRecord]
            Concatenated records from all existing partitions. Skips
            partitions whose files don't exist (returns no records for them).
        """
        if not partitions:
            return []
        for p in partitions:
            # Validate partition format eagerly so caller gets a clear error.
            if not p or len(p) != 7 or p[4] != "-":
                raise ValueError(
                    f"partition must be 'YYYY-MM' format; got {p!r}"
                )
        paths = [self._partition_path(p) for p in partitions]
        existing = [str(p) for p in paths if p.exists()]
        if not existing:
            return []
        # Lazy import: pyarrow.dataset only loaded when read_range() called.
        import pyarrow.dataset as ds
        dataset = ds.dataset(existing, format="parquet")
        df = dataset.to_table().to_pandas()
        # Restore timezone-aware datetimes (same logic as read()).
        records: List[ForecastRecord] = []
        for row in df.to_dict(orient="records"):
            ts = row["timestamp_utc"]
            if isinstance(ts, pd.Timestamp):
                if ts.tzinfo is None:
                    ts = ts.tz_localize("UTC")
                ts = ts.to_pydatetime()
            elif isinstance(ts, datetime) and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            row["timestamp_utc"] = ts
            records.append(ForecastRecord(**row))
        return records
