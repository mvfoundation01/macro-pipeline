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


# ---------------------------------------------------------------------------
# Layer 3.5A — HMM frozen-contract exceptions (Codex findings A, D, O, Q, R, S)
# ---------------------------------------------------------------------------
class HmmArtifactMissingError(RuntimeError):
    """Raised when the HMM pickle is missing from disk.

    Layer 3.5A invariant: the inference path NEVER auto-trains. If the
    artifact is absent the inference path fails closed; an admin must
    re-run ``scripts/train_hmm_v1.py`` to regenerate it.
    """


class HmmArtifactCorruptError(RuntimeError):
    """Raised when the HMM pickle's sha256 does not match the sidecar's
    ``data_sha256`` — i.e. the artifact has been tampered with or
    truncated. Inference fails closed."""


class HmmMetadataIncompatibleError(RuntimeError):
    """Raised when the sidecar ``schema_version`` or ``model_version``
    does not match the version this build of ``macro_pipeline`` expects.

    Future schema bumps should also bump the version constants in
    ``regime.hmm_states`` so this error can guide admins to regenerate.
    """


class HmmConcurrencyError(RuntimeError):
    """Raised when the HMM artifact's filelock could not be acquired
    within the timeout (default 30s). Indicates contention with another
    inference process or a stale lock from a crashed admin script."""


# ---------------------------------------------------------------------------
# Layer 3.5C — NBER calendar exceptions
# ---------------------------------------------------------------------------
class NberCycleNotFoundError(RuntimeError):
    """Raised when a turning point lookup against the NBER calendar fails
    (no matching cycle for the requested date / kind). Layer 3.5C: caller
    should either fall back to training-mode or accept the failure as a
    pre-1978 / unannounced-region condition."""


class NberCalendarLoadError(RuntimeError):
    """Raised when the NBER calendar CSV is unreadable, malformed, or
    missing required columns. Configuration-time failure (surfaces at
    NberCalendarLoader construction)."""


__all__ = [
    "HmmArtifactCorruptError",
    "HmmArtifactMissingError",
    "HmmConcurrencyError",
    "HmmMetadataIncompatibleError",
    "NberCalendarLoadError",
    "NberCycleNotFoundError",
    "PitDataUnavailableError",
    "RegimeClassifierError",
    "RegimeContextError",
]
