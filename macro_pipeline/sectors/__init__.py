"""L9 D3 — Sector outlook module.

Per Strategic L9 pre-flight 2026-05-16. Closes the L8 sector_factor.html
placeholder surface with actual producer-backed sector records.

Vision §19 11 GICS sectors; each sector gets a composite view based on
valuation percentile + earnings trend + macro sensitivity score.
"""
from __future__ import annotations

from .sector_outlook import (
    SECTOR_IDS,
    SectorRecord,
    compute_sector_outlook,
)

__all__ = ["SECTOR_IDS", "SectorRecord", "compute_sector_outlook"]
