"""Abstract loader interface and shared metadata model.

Every loader returns a (DataFrame | Series, metadata dict) pair where the
metadata is keyed by indicator id. Build guide Section 5.1.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class IndicatorMetadata:
    indicator_id: str
    source: str
    frequency: str  # 'D', 'W', 'M', 'Q'
    first_obs: pd.Timestamp
    last_obs: pd.Timestamp
    last_update: pd.Timestamp
    needs_vintage: bool = False
    unit: str = "raw"
    release_lag_days: int = 0
    description: str = ""
    expected_min: float | None = None
    expected_max: float | None = None
    # Periods inside which the source-of-truth differs from the rest of the
    # series (scale change, methodology change, discontinued precursor, ...).
    # Each entry: {start_date, end_date, reason}. Downstream consumers
    # decide whether to mask, exclude, or document.
    data_quality_suspect_periods: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator_id": self.indicator_id,
            "source": self.source,
            "frequency": self.frequency,
            "first_obs": self.first_obs.isoformat() if pd.notna(self.first_obs) else None,
            "last_obs": self.last_obs.isoformat() if pd.notna(self.last_obs) else None,
            "last_update": self.last_update.isoformat() if pd.notna(self.last_update) else None,
            "needs_vintage": self.needs_vintage,
            "unit": self.unit,
            "release_lag_days": self.release_lag_days,
            "description": self.description,
            "expected_min": self.expected_min,
            "expected_max": self.expected_max,
            "data_quality_suspect_periods": self.data_quality_suspect_periods,
            **self.extra,
        }


class Loader(ABC):
    """Abstract loader. Subclasses must return (DataFrame, metadata-by-id)."""

    @abstractmethod
    def load(self) -> tuple[pd.DataFrame, dict[str, IndicatorMetadata]]: ...
