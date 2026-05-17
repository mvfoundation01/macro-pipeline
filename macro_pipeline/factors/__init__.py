"""L9 D3 — Factor outlook module (13 risk factors per Vision §19).

Per Strategic L9 pre-flight 2026-05-16.
"""
from __future__ import annotations

from .factor_outlook import (
    FACTOR_IDS,
    FactorRecord,
    compute_factor_outlook,
)

__all__ = ["FACTOR_IDS", "FactorRecord", "compute_factor_outlook"]
