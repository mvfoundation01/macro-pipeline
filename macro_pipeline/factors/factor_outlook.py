"""L9 D3 — 13 risk factor outlook synthesizer (Vision §19).

Per Strategic L9 single comprehensive pre-flight 2026-05-16.

Factors are common drivers of cross-sectional return dispersion. Each
factor record represents the model's outlook on factor tilt + conviction.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


FACTOR_IDS: Tuple[str, ...] = (
    "growth",
    "value",
    "quality",
    "momentum",
    "low_volatility",
    "high_beta",
    "small_cap",
    "large_cap",
    "equal_weight",
    "dividend_yield",
    "profitability",
    "leverage",
    "revisions",
)
assert len(FACTOR_IDS) == 13, "FACTOR_IDS must have exactly 13 entries"
FACTOR_IDS_VALID = frozenset(FACTOR_IDS)

VALID_TILTS = frozenset({"overweight", "neutral", "underweight"})


@dataclass(frozen=True)
class FactorRecord:
    """Vision §19 risk-factor outlook record.

    Fields
    ------
    factor_id              One of FACTOR_IDS.
    expected_return_bps    Annualized excess-return forecast in bps.
    sigma_bps              Forecast sigma in bps.
    regime_alignment       [-1, 1]; +1 = factor fully aligned with current
                           macro regime; -1 = anti-aligned.
    one_year_tilt          "overweight" | "neutral" | "underweight".
    conviction             [1, 10].
    """

    factor_id: str
    expected_return_bps: float
    sigma_bps: float
    regime_alignment: float
    one_year_tilt: str
    conviction: float

    def __post_init__(self) -> None:
        if self.factor_id not in FACTOR_IDS_VALID:
            raise ValueError(
                f"Unknown factor_id {self.factor_id!r}; expected one of "
                f"{sorted(FACTOR_IDS_VALID)}"
            )
        for fname in ("expected_return_bps", "sigma_bps", "regime_alignment"):
            v = getattr(self, fname)
            if not math.isfinite(v):
                raise ValueError(f"{fname} must be finite; got {v!r}")
        if self.sigma_bps < 0:
            raise ValueError(
                f"sigma_bps must be non-negative; got {self.sigma_bps}"
            )
        if not (-1.0 <= self.regime_alignment <= 1.0):
            raise ValueError(
                f"regime_alignment must be in [-1, 1]; got {self.regime_alignment}"
            )
        if self.one_year_tilt not in VALID_TILTS:
            raise ValueError(
                f"one_year_tilt {self.one_year_tilt!r} not in {sorted(VALID_TILTS)}"
            )
        if not math.isfinite(self.conviction):
            raise ValueError(f"conviction must be finite; got {self.conviction!r}")
        if not (1.0 <= self.conviction <= 10.0):
            raise ValueError(f"conviction must be in [1, 10]; got {self.conviction}")


def compute_factor_outlook(
    factor_id: str,
    expected_return_bps: float,
    sigma_bps: float,
    regime_alignment: float,
) -> FactorRecord:
    """L9 D3 — Vision §19 factor outlook synthesis.

    Combines expected return + sigma + regime alignment into tilt + conviction.
    Tilt thresholds: |expected_return_bps| > 100 = decisive; else neutral.
    Conviction scales with abs(expected_return / sigma) Sharpe-like, plus
    regime_alignment bonus / penalty.
    """
    if factor_id not in FACTOR_IDS_VALID:
        raise ValueError(
            f"Unknown factor_id {factor_id!r}; expected one of "
            f"{sorted(FACTOR_IDS_VALID)}"
        )
    for fname, val in (
        ("expected_return_bps", expected_return_bps),
        ("sigma_bps", sigma_bps),
        ("regime_alignment", regime_alignment),
    ):
        if not math.isfinite(val):
            raise ValueError(f"{fname} must be finite; got {val!r}")
    if sigma_bps < 0:
        raise ValueError(f"sigma_bps must be non-negative; got {sigma_bps}")
    if not (-1.0 <= regime_alignment <= 1.0):
        raise ValueError(
            f"regime_alignment must be in [-1, 1]; got {regime_alignment}"
        )

    # Tilt decision.
    if expected_return_bps > 100:
        tilt = "overweight"
    elif expected_return_bps < -100:
        tilt = "underweight"
    else:
        tilt = "neutral"

    # Conviction: Sharpe-like + regime alignment bonus.
    if sigma_bps > 0:
        sharpe_proxy = abs(expected_return_bps) / sigma_bps
        base = min(0.7, sharpe_proxy / 2.0)  # cap base at 0.7
    else:
        base = 0.0
    regime_bonus = max(0.0, regime_alignment) * 0.3  # 0-0.3 contribution
    composite = base + regime_bonus
    composite = max(0.0, min(1.0, composite))
    conviction = 1.0 + 9.0 * composite

    return FactorRecord(
        factor_id=factor_id,
        expected_return_bps=expected_return_bps,
        sigma_bps=sigma_bps,
        regime_alignment=regime_alignment,
        one_year_tilt=tilt,
        conviction=conviction,
    )
