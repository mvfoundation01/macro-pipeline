"""L7 D4 tests — parquet persistence."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from macro_pipeline.persistence import (
    SCHEMA_VERSION,
    ForecastRecord,
    ParquetForecastStore,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(**overrides) -> ForecastRecord:
    base = dict(
        forecast_id="f-001",
        timestamp_utc=_utcnow(),
        horizon=1,
        point_estimate_annualized=0.07,
        sigma_annualized=0.15,
        confidence=0.7,
        conviction=5.5,
        code_sha="abc123",
        metadata_json="{}",
    )
    base.update(overrides)
    return ForecastRecord(**base)


# ===========================================================================
# ForecastRecord
# ===========================================================================


def test_forecast_record_valid() -> None:
    """POS: valid ForecastRecord."""
    r = _make_record()
    assert r.horizon == 1


def test_forecast_record_invalid_horizon_raises() -> None:
    """NEG: horizon not in (1,3,5,10) raises."""
    with pytest.raises(ValueError, match="horizon"):
        _make_record(horizon=7)


def test_forecast_record_nan_point_estimate_raises() -> None:
    """NEG: NaN raises ValueError."""
    with pytest.raises(ValueError, match="finite"):
        _make_record(point_estimate_annualized=float("nan"))


def test_forecast_record_naive_datetime_raises() -> None:
    """NEG: naive datetime raises ValueError."""
    with pytest.raises(ValueError, match="timezone-aware"):
        _make_record(timestamp_utc=datetime(2026, 5, 16))


def test_forecast_record_confidence_out_of_range_raises() -> None:
    """NEG: confidence outside [0, 1] raises."""
    with pytest.raises(ValueError, match="confidence"):
        _make_record(confidence=1.5)


def test_forecast_record_conviction_out_of_range_raises() -> None:
    """NEG: conviction outside [1, 10] raises."""
    with pytest.raises(ValueError, match="conviction"):
        _make_record(conviction=15.0)


# ===========================================================================
# ParquetForecastStore
# ===========================================================================


def test_store_append_single_record(tmp_path: Path) -> None:
    """POS: append creates partition parquet file."""
    store = ParquetForecastStore(tmp_path)
    r = _make_record()
    path = store.append([r])
    assert path.exists()
    partition = r.timestamp_utc.strftime("%Y-%m")
    assert SCHEMA_VERSION in path.name
    assert partition in path.name


def test_store_round_trip_single_record(tmp_path: Path) -> None:
    """POS-inv: append + read returns equivalent record."""
    store = ParquetForecastStore(tmp_path)
    r = _make_record()
    store.append([r])
    partition = r.timestamp_utc.strftime("%Y-%m")
    records = store.read(partition)
    assert len(records) == 1
    assert records[0].forecast_id == r.forecast_id
    assert records[0].horizon == r.horizon
    assert records[0].point_estimate_annualized == pytest.approx(r.point_estimate_annualized)


def test_store_append_merges(tmp_path: Path) -> None:
    """POS-inv: two appends to same partition merge."""
    store = ParquetForecastStore(tmp_path)
    r1 = _make_record(forecast_id="f-001")
    r2 = _make_record(forecast_id="f-002", horizon=3)
    store.append([r1])
    store.append([r2])
    partition = r1.timestamp_utc.strftime("%Y-%m")
    records = store.read(partition)
    assert len(records) == 2
    assert {rec.forecast_id for rec in records} == {"f-001", "f-002"}


def test_store_empty_records_raises(tmp_path: Path) -> None:
    """NEG: append with empty list raises."""
    store = ParquetForecastStore(tmp_path)
    with pytest.raises(ValueError, match="empty"):
        store.append([])


def test_store_mixed_month_records_raises(tmp_path: Path) -> None:
    """NEG: records spanning different months raises."""
    store = ParquetForecastStore(tmp_path)
    may = datetime(2026, 5, 1, tzinfo=timezone.utc)
    june = datetime(2026, 6, 1, tzinfo=timezone.utc)
    r_may = _make_record(forecast_id="f-may", timestamp_utc=may)
    r_june = _make_record(forecast_id="f-june", timestamp_utc=june)
    with pytest.raises(ValueError, match="same month"):
        store.append([r_may, r_june])


def test_store_read_missing_partition_returns_empty(tmp_path: Path) -> None:
    """POS: read non-existent partition returns []."""
    store = ParquetForecastStore(tmp_path)
    assert store.read("2099-12") == []


def test_store_list_partitions(tmp_path: Path) -> None:
    """POS: list_partitions enumerates present partitions."""
    store = ParquetForecastStore(tmp_path)
    r_may = _make_record(
        forecast_id="f-may",
        timestamp_utc=datetime(2026, 5, 16, tzinfo=timezone.utc),
    )
    r_june = _make_record(
        forecast_id="f-june",
        timestamp_utc=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )
    store.append([r_may])
    store.append([r_june])
    parts = store.list_partitions()
    assert "2026-05" in parts
    assert "2026-06" in parts


def test_store_invalid_partition_format_raises(tmp_path: Path) -> None:
    """NEG: invalid partition format raises ValueError."""
    store = ParquetForecastStore(tmp_path)
    with pytest.raises(ValueError, match="YYYY-MM"):
        store.read("2026-13-01")
    with pytest.raises(ValueError, match="YYYY-MM"):
        store.read("invalid")
