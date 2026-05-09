"""Regime-classifier exceptions (Layer 3A)."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class PitDataUnavailableError(Exception):
    """The ground-truth label / observation needed at ``query_date`` is
    not yet known in the PIT view at ``as_of``.

    Raised by ``regime.nber_extract.extract_nber_state`` when NBER had
    not yet announced a peak/trough by ``as_of``, and more generally by
    any regime helper that refuses to fabricate a label past its
    visibility horizon.
    """

    indicator_id: str
    reason: str = ""
    as_of: pd.Timestamp | None = None
    context: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(str(self))

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        parts = [f"[{self.indicator_id}]"]
        if self.reason:
            parts.append(self.reason)
        if self.as_of is not None:
            parts.append(f"as_of={self.as_of.date()}")
        if self.context:
            parts.append(f"context={self.context}")
        return " ".join(parts)


@dataclass
class RegimeClassifierError(Exception):
    """Generic regime-classifier failure (e.g. missing component, bad config)."""

    component: str
    reason: str = ""
    context: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(str(self))

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        parts = [f"[{self.component}]"]
        if self.reason:
            parts.append(self.reason)
        if self.context:
            parts.append(f"context={self.context}")
        return " ".join(parts)


@dataclass
class RegimeContextError(RegimeClassifierError):
    """Raised when ``RegimeContext.derive_regime_state`` cannot resolve
    a regime label because both NBER and HMM are unavailable (Layer 3B)."""

    component: str = "regime_context"


__all__ = ["PitDataUnavailableError", "RegimeClassifierError", "RegimeContextError"]
