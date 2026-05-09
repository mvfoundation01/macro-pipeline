"""3-state Gaussian HMM regime classifier (Layer 3A).

Spec: ``LAYER_3_BUILD_SPEC.md`` §4.3.4.

Hard rules:

1. **Train ONCE on a frozen 1982-2019 sample.** The spec calls for
   1959-2019 but our PHILLY_LEI_PROXY (USSLIND) only starts 1982-01;
   1982-01-01 → 2019-12-31 is the widest window that gives a complete
   feature matrix for every observation. The trained HMM is pickled to
   ``data/cache/hmm/regime_3state_v1.pkl`` and never retrained — doing
   so per ``as_of`` would be data snooping.

2. **Inference is PIT-safe** via ``PitDataContext``: features are loaded
   through the same vintage / release-lag dispatch used by the rest of
   Layer 3.

3. **State labels are inferred from NBER overlap during training.** We
   never hand-label a state — the state with the highest fraction of
   NBER recession months in training is labeled ``"recession"``, the
   state with the lowest is ``"expansion"``, and the middle is
   ``"late-cycle"``.

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

import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from macro_pipeline.access import PitDataContext, load_series
from macro_pipeline.config import DATA_CACHE
from macro_pipeline.regime.exceptions import RegimeClassifierError

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
HMM_VERSION = "regime_3state_v1"

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


def _build_monthly_features(
    *, end: pd.Timestamp, ctx: PitDataContext | None = None,
) -> pd.DataFrame:
    """Build a monthly DataFrame of HMM features ending at ``end``.

    For training (``ctx=None``) we use latest values. For inference
    (``ctx`` provided) we use PIT-safe values as known on ``ctx.as_of``.
    """
    monthly_frames: list[pd.Series] = []
    for sid in HMM_FEATURES:
        bundle = load_series(sid, as_of=ctx.as_of) if ctx is not None else load_series(sid)
        s = bundle.data.dropna()
        if s.empty:
            raise RegimeClassifierError(
                component="hmm",
                reason=f"feature {sid!r} empty after PIT load",
                context={"as_of": str(ctx.as_of) if ctx is not None else "latest"},
            )
        # Resample daily/weekly to month-end last value; monthly series
        # are unchanged.
        monthly = s.resample("ME").last()
        monthly = monthly[monthly.index <= end]
        monthly.name = sid
        monthly_frames.append(monthly)
    df = pd.concat(monthly_frames, axis=1, sort=True).dropna()
    return df


def _fit_hmm(features: np.ndarray) -> object:
    """Fit a 3-state GaussianHMM on the standardized feature matrix."""
    from hmmlearn.hmm import GaussianHMM  # local import: deferred dependency

    hmm = GaussianHMM(
        n_components=3,
        covariance_type="full",
        n_iter=HMM_N_ITER,
        tol=HMM_TOL,
        random_state=HMM_RANDOM_STATE,
        verbose=False,
    )
    hmm.fit(features)
    return hmm


def _label_states_by_nber(
    states: np.ndarray, observation_dates: pd.DatetimeIndex,
) -> tuple[dict[int, str], dict[int, float]]:
    """Map raw HMM state indices → expansion/late-cycle/recession labels.

    Uses NBER_REC_LABEL overlap on the training window: the HMM state
    with the highest mean NBER label is "recession", the lowest is
    "expansion", the middle is "late-cycle".
    """
    from macro_pipeline.access import load_series  # local re-import for clarity

    nber_bundle = load_series("NBER_REC_LABEL")
    nber = nber_bundle.data.dropna()
    nber_monthly = nber.resample("ME").last()
    aligned = nber_monthly.reindex(observation_dates).fillna(0.0).astype(float)

    overlap: dict[int, float] = {}
    for state_idx in range(3):
        mask = states == state_idx
        if mask.sum() == 0:
            overlap[state_idx] = float("nan")
        else:
            overlap[state_idx] = float(aligned.values[mask].mean())

    finite = {k: v for k, v in overlap.items() if np.isfinite(v)}
    if len(finite) < 3:
        raise RegimeClassifierError(
            component="hmm",
            reason="empty HMM state during training (cannot label by NBER overlap)",
            context={"overlap": overlap},
        )
    sorted_states = sorted(finite.items(), key=lambda kv: kv[1])
    state_to_label = {
        sorted_states[0][0]: "expansion",
        sorted_states[1][0]: "late-cycle",
        sorted_states[2][0]: "recession",
    }
    return state_to_label, overlap


def train_and_save_hmm(
    *,
    pickle_path: Path | str | None = None,
    force: bool = False,
) -> TrainedHmm:
    """Fit the frozen HMM on 1982-01 → 2019-12 and pickle to ``pickle_path``.

    If a pickle already exists and ``force=False`` we load it instead of
    refitting. This is the only place HMM training happens.
    """
    pickle_path = Path(pickle_path) if pickle_path is not None else HMM_PICKLE_PATH
    if pickle_path.exists() and not force:
        return load_hmm(pickle_path)

    df = _build_monthly_features(end=HMM_TRAINING_END)
    df = df[df.index >= HMM_TRAINING_START]
    if len(df) < 100:
        raise RegimeClassifierError(
            component="hmm",
            reason=f"training window only has {len(df)} obs (need ≥ 100)",
            context={"start": str(HMM_TRAINING_START.date()),
                     "end": str(HMM_TRAINING_END.date())},
        )

    raw = df.values.astype(float)
    feature_mean = raw.mean(axis=0)
    feature_std = raw.std(axis=0, ddof=1)
    feature_std[feature_std == 0] = 1.0
    standardized = (raw - feature_mean) / feature_std

    hmm = _fit_hmm(standardized)
    states = hmm.predict(standardized)
    state_to_label, overlap = _label_states_by_nber(states, df.index)

    bundle = TrainedHmm(
        model_version=HMM_VERSION,
        feature_names=HMM_FEATURES,
        training_start=HMM_TRAINING_START,
        training_end=HMM_TRAINING_END,
        n_obs=len(df),
        feature_mean=feature_mean,
        feature_std=feature_std,
        state_to_label=state_to_label,
        nber_overlap_per_state=overlap,
        hmm=hmm,
    )
    pickle_path.parent.mkdir(parents=True, exist_ok=True)
    with pickle_path.open("wb") as fh:
        pickle.dump(bundle, fh)
    log.info("HMM trained: %d obs, pickle=%s", len(df), pickle_path)
    return bundle


def load_hmm(pickle_path: Path | str | None = None) -> TrainedHmm:
    """Load the pickled trained HMM. Trains-and-saves if missing."""
    pickle_path = Path(pickle_path) if pickle_path is not None else HMM_PICKLE_PATH
    if not pickle_path.exists():
        return train_and_save_hmm(pickle_path=pickle_path)
    with pickle_path.open("rb") as fh:
        bundle = pickle.load(fh)
    if not isinstance(bundle, TrainedHmm):
        raise RegimeClassifierError(
            component="hmm",
            reason=f"unpickled object is {type(bundle).__name__}, expected TrainedHmm",
            context={"pickle_path": str(pickle_path)},
        )
    return bundle


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
    """
    bundle_obj = load_hmm(pickle_path)
    df = _build_monthly_features(end=ctx.as_of, ctx=ctx)
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
    "HMM_PICKLE_PATH",
    "HMM_TRAINING_END",
    "HMM_TRAINING_START",
    "HMM_VERSION",
    "STATE_NAMES",
    "HmmStateResult",
    "TrainedHmm",
    "load_hmm",
    "predict_state",
    "train_and_save_hmm",
]
