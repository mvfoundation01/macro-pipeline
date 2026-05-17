"""L9 D3 — 11 GICS sector outlook synthesizer (Vision §19).

Per Strategic L9 single comprehensive pre-flight 2026-05-16.

Composite scoring formula (Vision §19 BINDING):
- 1Y view: 40% valuation + 40% earnings + 20% macro_sensitivity
- 3Y view: 60% valuation + 30% earnings + 10% macro_sensitivity (more valuation weight at long horizon)
- conviction: 1 + 9 * composite_1y (mapped to [1, 10])
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


SECTOR_IDS: Tuple[str, ...] = (
    "technology",
    "communication_services",
    "consumer_discretionary",
    "industrials",
    "financials",
    "healthcare",
    "staples",
    "utilities",
    "energy",
    "materials",
    "real_estate",
)
assert len(SECTOR_IDS) == 11, "SECTOR_IDS must have exactly 11 GICS sectors"
SECTOR_IDS_VALID = frozenset(SECTOR_IDS)

VALID_VIEWS = frozenset({"overweight", "neutral", "underweight"})


@dataclass(frozen=True)
class SectorRecord:
    """Vision §19 11-GICS-sector outlook record.

    Fields
    ------
    sector_id                  One of SECTOR_IDS (11 GICS).
    valuation_percentile       [0, 1]; higher = more expensive.
    earnings_trend_score       [0, 1]; higher = stronger earnings momentum.
    macro_sensitivity_score    [-1, 1]; positive = pro-cyclical, negative = defensive.
    one_year_view              "overweight" | "neutral" | "underweight".
    three_year_view            "overweight" | "neutral" | "underweight".
    conviction                 [1, 10] position-sizing score.
    """

    sector_id: str
    valuation_percentile: float
    earnings_trend_score: float
    macro_sensitivity_score: float
    one_year_view: str
    three_year_view: str
    conviction: float

    def __post_init__(self) -> None:
        if self.sector_id not in SECTOR_IDS_VALID:
            raise ValueError(
                f"Unknown sector_id {self.sector_id!r}; expected one of "
                f"{sorted(SECTOR_IDS_VALID)}"
            )
        for fname in ("valuation_percentile", "earnings_trend_score"):
            v = getattr(self, fname)
            if not math.isfinite(v):
                raise ValueError(f"{fname} must be finite; got {v!r}")
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"{fname} must be in [0, 1]; got {v}")
        if not math.isfinite(self.macro_sensitivity_score):
            raise ValueError(
                f"macro_sensitivity_score must be finite; got "
                f"{self.macro_sensitivity_score!r}"
            )
        if not (-1.0 <= self.macro_sensitivity_score <= 1.0):
            raise ValueError(
                f"macro_sensitivity_score must be in [-1, 1]; got "
                f"{self.macro_sensitivity_score}"
            )
        if self.one_year_view not in VALID_VIEWS:
            raise ValueError(
                f"one_year_view {self.one_year_view!r} not in {sorted(VALID_VIEWS)}"
            )
        if self.three_year_view not in VALID_VIEWS:
            raise ValueError(
                f"three_year_view {self.three_year_view!r} not in {sorted(VALID_VIEWS)}"
            )
        if not math.isfinite(self.conviction):
            raise ValueError(
                f"conviction must be finite; got {self.conviction!r}"
            )
        if not (1.0 <= self.conviction <= 10.0):
            raise ValueError(
                f"conviction must be in [1, 10]; got {self.conviction}"
            )


def _composite_to_view(composite: float) -> str:
    if composite > 0.65:
        return "overweight"
    if composite >= 0.45:
        return "neutral"
    return "underweight"


def compute_sector_outlook(
    sector_id: str,
    valuation_percentile: float,
    earnings_trend_score: float,
    macro_sensitivity_score: float,
) -> SectorRecord:
    """L9 D3 — Synthesize sector outlook from 3 input scores per Vision §19.

    Lower valuation_percentile + higher earnings_trend + macro_sensitivity
    aligned with regime → higher composite → overweight view + high conviction.
    """
    if sector_id not in SECTOR_IDS_VALID:
        raise ValueError(
            f"Unknown sector_id {sector_id!r}; expected one of "
            f"{sorted(SECTOR_IDS_VALID)}"
        )
    for fname, val in (
        ("valuation_percentile", valuation_percentile),
        ("earnings_trend_score", earnings_trend_score),
        ("macro_sensitivity_score", macro_sensitivity_score),
    ):
        if not math.isfinite(val):
            raise ValueError(f"{fname} must be finite; got {val!r}")
    if not (0.0 <= valuation_percentile <= 1.0):
        raise ValueError(
            f"valuation_percentile must be in [0, 1]; got {valuation_percentile}"
        )
    if not (0.0 <= earnings_trend_score <= 1.0):
        raise ValueError(
            f"earnings_trend_score must be in [0, 1]; got {earnings_trend_score}"
        )
    if not (-1.0 <= macro_sensitivity_score <= 1.0):
        raise ValueError(
            f"macro_sensitivity_score must be in [-1, 1]; got {macro_sensitivity_score}"
        )

    # 1Y composite: 40% valuation (inverted) + 40% earnings + 20% macro.
    composite_1y = (
        (1.0 - valuation_percentile) * 0.4
        + earnings_trend_score * 0.4
        + ((macro_sensitivity_score + 1.0) / 2.0) * 0.2
    )
    one_year_view = _composite_to_view(composite_1y)

    # 3Y: more weight on valuation (long-horizon mean reversion).
    composite_3y = (
        (1.0 - valuation_percentile) * 0.6
        + earnings_trend_score * 0.3
        + ((macro_sensitivity_score + 1.0) / 2.0) * 0.1
    )
    three_year_view = _composite_to_view(composite_3y)

    conviction = 1.0 + 9.0 * composite_1y
    conviction = max(1.0, min(10.0, conviction))

    return SectorRecord(
        sector_id=sector_id,
        valuation_percentile=valuation_percentile,
        earnings_trend_score=earnings_trend_score,
        macro_sensitivity_score=macro_sensitivity_score,
        one_year_view=one_year_view,
        three_year_view=three_year_view,
        conviction=conviction,
    )
