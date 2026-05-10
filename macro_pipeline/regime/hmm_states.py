"""3-state Gaussian HMM regime classifier (Layer 3A; refactored at L3.5A).

Spec: ``LAYER_3_BUILD_SPEC.md`` §4.3.4 + ``LAYER_3_5_BUILD_SPEC.md`` §3.5A.

Hard rules:

1. **Train ONCE on a frozen 1982-2019 sample.** The spec calls for
   1959-2019 but our PHILLY_LEI_PROXY (USSLIND) only starts 1982-01;
   1982-01-01 → 2019-12-31 is the widest window that gives a complete
   feature matrix for every observation. The trained HMM is pickled to
   ``data/cache/hmm/regime_3state_v1.pkl`` and **never retrained from
   inference code**. Regeneration is the responsibility of the
   admin-only ``scripts/train_hmm_v1.py`` utility.

2. **Inference is PIT-safe** via ``PitDataContext``: features are loaded
   through the same vintage / release-lag dispatch used by the rest of
   Layer 3.

3. **State labels are inferred from NBER overlap during training.** We
   never hand-label a state — the state with the highest fraction of
   NBER recession months in training is labeled ``"recession"``, the
   state with the lowest is ``"expansion"``, and the middle is
   ``"late-cycle"``.

4. **(L3.5A) Inference path is fail-closed.** ``load_hmm`` raises
   ``HmmArtifactMissingError`` if the pickle is absent and
   ``HmmArtifactCorruptError`` if the sidecar's ``data_sha256`` does
   not match the on-disk pickle's recomputed sha256. There is NO
   auto-train fallback; that path was a Codex / ChatGPT critical-high
   finding (A, D, O) and a reproducibility blocker (Dim 5, Dim 12).

5. **(L3.5A) Concurrency-safe load** via ``filelock.FileLock`` with
   30s timeout (``HmmConcurrencyError`` on timeout). Cross-process and
   cross-thread serialisation; the artifact and sidecar are read
   under the same lock so partial-update races are impossible.

Feature set (5 monthly series, all non-vintage, 1982-01 → 2019-12):
    T10Y2Y               yield-curve spread (substitute for T10Y3M)
    PHILLY_LEI_PROXY     state leading index aggregate
    IC4WSA               initial jobless claims, 4-week MA (labor stress)
    NFCI                 Chicago Fed financial conditions index
    UMCSENT              U Michigan consumer sentiment index

Why these and not CFNAIMA3 / SAHMREALTIME (which the spec mentions)?
Both are ``vintage_required=True`` and FRED's ALFRED archive only has
realtime vintages starting 2011-05-23. Using them would produce empty
PIT views for any inference ``as_of < 2011-05-23`` (including the
2008-09-15 spec proof-point). IC4WSA and UMCSENT preserve the labor /
sentiment signal across the full training window without breaking PIT
discipline. (BAMLH0A0HYM2 — HY OAS — would help separate stress states
but only starts 1996-12.)
"""
from __future__ import annotations

import hashlib
import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from macro_pipeline.access import PitDataContext, load_series
from macro_pipeline.config import DATA_CACHE
from macro_pipeline.regime.exceptions import (
    HmmArtifactCorruptError,
    HmmArtifactMissingError,
    HmmConcurrencyError,
    HmmMetadataIncompatibleError,
    RegimeClassifierError,
)

log = logging.getLogger(__name__)

HMM_FEATURES = (
    "T10Y2Y",
    "PHILLY_LEI_PROXY",
    "IC4WSA",
    "NFCI",
    "UMCSENT",
)
HMM_TRAINING_START = pd.Timestamp("1982-01-01")
HMM_TRAINING_END = pd.Timestamp("2019-12-31")
HMM_RANDOM_STATE = 42
HMM_N_ITER = 200
HMM_TOL = 1e-4
HMM_PICKLE_PATH = DATA_CACHE / "hmm" / "regime_3state_v1.pkl"
HMM_SIDECAR_PATH = HMM_PICKLE_PATH.with_suffix(".meta.json")
HMM_VERSION = "regime_3state_v1"

# Sidecar contract (Layer 3.5A spec §3.3-1)
SIDECAR_SCHEMA_VERSION = "1.0"
SIDECAR_MODEL_VERSION = "v1"
SIDECAR_REQUIRED_KEYS = (
    "schema_version",
    "model_version",
    "model_family",
    "n_components",
    "training_window_start",
    "training_window_end",
    "n_obs_train",
    "feature_names",
    "feature_matrix_sha256",
    "nber_label_sha256",
    "state_to_label_mapping",
    "nber_overlap_per_state",
    "hmmlearn_version",
    "python_version",
    "pickle_protocol",
    "random_state",
    "data_sha256",
    "created_at_utc",
    "training_script_path",
    "training_script_sha256",
)
HMM_LOCK_TIMEOUT_SECONDS = 30
HMM_LOCK_SUFFIX = ".lock"

STATE_NAMES = ("expansion", "late-cycle", "recession")


@dataclass
class HmmStateResult:
    state: str                         # expansion | late-cycle | recession
    state_probabilities: dict[str, float]
    observation_date: pd.Timestamp
    feature_values: dict[str, float]
    model_version: str = HMM_VERSION
    as_of: pd.Timestamp | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class TrainedHmm:
    """Frozen HMM bundle pickled to disk after one-time fit."""

    model_version: str
    feature_names: tuple[str, ...]
    training_start: pd.Timestamp
    training_end: pd.Timestamp
    n_obs: int
    feature_mean: np.ndarray   # shape (n_features,)
    feature_std: np.ndarray    # shape (n_features,)
    state_to_label: dict[int, str]  # {hmm_state_index: "expansion"|...}
    nber_overlap_per_state: dict[int, float]  # for diagnostics
    hmm: object  # hmmlearn.hmm.GaussianHMM (typed-erased to avoid eager import)


# ---------------------------------------------------------------------------
# L3.5A — fail-closed loader
# ---------------------------------------------------------------------------
def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_sidecar(sidecar_path: Path) -> dict:
    if not sidecar_path.exists():
        raise HmmArtifactCorruptError(
            f"HMM sidecar missing: {sidecar_path}. Re-run "
            "`python scripts/train_hmm_v1.py` to regenerate the artifact."
        )
    try:
        meta = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HmmArtifactCorruptError(
            f"HMM sidecar is not valid JSON ({sidecar_path}): {exc}. "
            "Regenerate via scripts/train_hmm_v1.py."
        ) from exc
    return meta


def _validate_sidecar(meta: dict, sidecar_path: Path) -> None:
    missing = [k for k in SIDECAR_REQUIRED_KEYS if k not in meta]
    if missing:
        raise HmmMetadataIncompatibleError(
            f"HMM sidecar missing required keys {missing} ({sidecar_path}). "
            "Regenerate via scripts/train_hmm_v1.py."
        )
    if meta["schema_version"] != SIDECAR_SCHEMA_VERSION:
        raise HmmMetadataIncompatibleError(
            f"HMM sidecar schema_version={meta['schema_version']!r} but this "
            f"build expects {SIDECAR_SCHEMA_VERSION!r}. Bump the sidecar by "
            "regenerating via scripts/train_hmm_v1.py."
        )
    if meta["model_version"] != SIDECAR_MODEL_VERSION:
        raise HmmMetadataIncompatibleError(
            f"HMM sidecar model_version={meta['model_version']!r} but this "
            f"build expects {SIDECAR_MODEL_VERSION!r}."
        )


def _acquire_lock(pickle_path: Path):
    """Return a context manager guarding ``pickle_path`` for read.

    Uses ``filelock.FileLock`` (declared in ``pyproject.toml``). On
    timeout, raises ``HmmConcurrencyError`` per the L3.5A contract.
    """
    try:
        from filelock import FileLock, Timeout
    except ImportError as exc:  # pragma: no cover - dependency declared
        raise RegimeClassifierError(
            component="hmm",
            reason=(
                "filelock not installed; cannot acquire HMM artifact lock. "
                "Run `uv sync` (or `pip install filelock>=3.13`)."
            ),
        ) from exc

    lock_path = pickle_path.with_suffix(pickle_path.suffix + HMM_LOCK_SUFFIX)

    class _LockGuard:
        def __init__(self) -> None:
            self._lock = FileLock(str(lock_path), timeout=HMM_LOCK_TIMEOUT_SECONDS)

        def __enter__(self):
            try:
                self._lock.acquire()
            except Timeout as e:
                raise HmmConcurrencyError(
                    f"Failed to acquire HMM artifact lock at {lock_path} "
                    f"within {HMM_LOCK_TIMEOUT_SECONDS}s. Another process "
                    "may be loading or rewriting the artifact; if not, "
                    "remove the stale .lock file."
                ) from e
            return self._lock

        def __exit__(self, exc_type, exc, tb) -> None:
            self._lock.release()

    return _LockGuard()


def load_hmm(pickle_path: Path | str | None = None) -> TrainedHmm:
    """Load the pickled trained HMM with full integrity verification.

    Layer 3.5A contract (no auto-train, fail-closed on missing/corrupt):

    1. Acquire ``filelock`` on the pickle path; ``HmmConcurrencyError``
       on timeout.
    2. Verify pickle exists; ``HmmArtifactMissingError`` if not.
    3. Verify sidecar exists, is valid JSON, has all required keys, and
       schema/model versions match build expectations;
       ``HmmMetadataIncompatibleError`` otherwise.
    4. Recompute sha256 of pickle bytes, compare to sidecar
       ``data_sha256``; ``HmmArtifactCorruptError`` on mismatch.
    5. Unpickle and return the ``TrainedHmm`` bundle.
    """
    pickle_path = Path(pickle_path) if pickle_path is not None else HMM_PICKLE_PATH
    sidecar_path = pickle_path.with_suffix(".meta.json")

    with _acquire_lock(pickle_path):
        if not pickle_path.exists():
            raise HmmArtifactMissingError(
                f"HMM pickle missing: {pickle_path}. Inference path will not "
                "auto-train; run `python scripts/train_hmm_v1.py` to "
                "regenerate the artifact (admin-only utility)."
            )

        meta = _read_sidecar(sidecar_path)
        _validate_sidecar(meta, sidecar_path)

        actual_sha = _sha256_file(pickle_path)
        expected_sha = meta.get("data_sha256")
        if expected_sha != actual_sha:
            raise HmmArtifactCorruptError(
                f"HMM pickle sha256 mismatch ({pickle_path}): "
                f"recomputed={actual_sha}, sidecar.data_sha256={expected_sha}. "
                "Artifact may be corrupt or the sidecar stale; regenerate "
                "via scripts/train_hmm_v1.py."
            )

        with pickle_path.open("rb") as fh:
            bundle = pickle.load(fh)
        if not isinstance(bundle, TrainedHmm):
            raise HmmArtifactCorruptError(
                f"Unpickled object is {type(bundle).__name__}, expected "
                f"TrainedHmm ({pickle_path})."
            )
        return bundle


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------
def _build_pit_features(
    *, end: pd.Timestamp, ctx: PitDataContext,
) -> pd.DataFrame:
    """Build a monthly DataFrame of HMM features ending at ``end``,
    PIT-safe via ``ctx``."""
    monthly_frames: list[pd.Series] = []
    for sid in HMM_FEATURES:
        bundle = load_series(sid, as_of=ctx.as_of)
        s = bundle.data.dropna()
        if s.empty:
            raise RegimeClassifierError(
                component="hmm",
                reason=f"feature {sid!r} empty after PIT load",
                context={"as_of": str(ctx.as_of)},
            )
        monthly = s.resample("ME").last()
        monthly = monthly[monthly.index <= end]
        monthly.name = sid
        monthly_frames.append(monthly)
    df = pd.concat(monthly_frames, axis=1, sort=True).dropna()
    return df


def predict_state(
    ctx: PitDataContext,
    *,
    pickle_path: Path | str | None = None,
) -> HmmStateResult:
    """Predict the HMM state at ``ctx.as_of`` using PIT-safe features.

    Decoding strategy: build the full PIT-safe feature history up to
    ``ctx.as_of``, run Viterbi on the entire sequence, and report the
    state at the LAST observation. We also expose the per-state
    posterior probabilities at the last step (from the forward pass) so
    Layer 3 can quantify regime uncertainty.

    L3.5A: no implicit training. ``load_hmm`` is the only entry-point;
    if the artifact is missing it fails closed, surfacing the
    ``HmmArtifactMissingError`` to the caller.
    """
    bundle_obj = load_hmm(pickle_path)
    df = _build_pit_features(end=ctx.as_of, ctx=ctx)
    if df.empty:
        raise RegimeClassifierError(
            component="hmm",
            reason="no observations available at as_of after PIT load",
            context={"as_of": str(ctx.as_of)},
        )
    raw = df.values.astype(float)
    standardized = (raw - bundle_obj.feature_mean) / bundle_obj.feature_std
    states = bundle_obj.hmm.predict(standardized)
    posteriors = bundle_obj.hmm.predict_proba(standardized)

    last_state = int(states[-1])
    last_probs = posteriors[-1, :]
    state_label = bundle_obj.state_to_label[last_state]
    probabilities = {
        bundle_obj.state_to_label[i]: float(last_probs[i]) for i in range(3)
    }

    feature_values = {name: float(df.iloc[-1][name]) for name in df.columns}
    return HmmStateResult(
        state=state_label,
        state_probabilities=probabilities,
        observation_date=pd.Timestamp(df.index[-1]),
        feature_values=feature_values,
        model_version=bundle_obj.model_version,
        as_of=ctx.as_of,
    )


__all__ = [
    "HMM_FEATURES",
    "HMM_LOCK_TIMEOUT_SECONDS",
    "HMM_PICKLE_PATH",
    "HMM_SIDECAR_PATH",
    "HMM_TRAINING_END",
    "HMM_TRAINING_START",
    "HMM_VERSION",
    "SIDECAR_MODEL_VERSION",
    "SIDECAR_REQUIRED_KEYS",
    "SIDECAR_SCHEMA_VERSION",
    "STATE_NAMES",
    "HmmStateResult",
    "TrainedHmm",
    "load_hmm",
    "predict_state",
]
