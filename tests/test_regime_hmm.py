"""Tests for ``macro_pipeline.regime.hmm_states`` (Layer 3A; adapted at L3.5A).

L3.5A relocates ``train_and_save_hmm`` into the admin-only
``scripts/train_hmm_v1.py`` and removes the auto-train fallback from
``load_hmm``. The original determinism / pickle-roundtrip tests now
exercise the script via subprocess instead of importing it.
"""
from __future__ import annotations

import pickle
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.regime import (
    HMM_FEATURES,
    HMM_PICKLE_PATH,
    HMM_TRAINING_END,
    HMM_TRAINING_START,
    HMM_VERSION,
    STATE_NAMES,
    TrainedHmm,
    load_hmm,
    predict_state,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TRAIN_SCRIPT = REPO_ROOT / "scripts" / "train_hmm_v1.py"


@pytest.fixture(scope="module")
def trained_hmm() -> TrainedHmm:
    """Single shared trained HMM (loads the committed canonical pickle)."""
    return load_hmm()


def test_hmm_pickle_exists(trained_hmm: TrainedHmm) -> None:
    """The committed canonical pickle must be present on disk (L3.5A)."""
    assert Path(HMM_PICKLE_PATH).exists()
    assert isinstance(trained_hmm, TrainedHmm)


def test_hmm_training_window_is_frozen(trained_hmm: TrainedHmm) -> None:
    """Training is frozen at 1982-01-01 → 2019-12-31 (no data snooping)."""
    assert trained_hmm.training_start == HMM_TRAINING_START
    assert trained_hmm.training_end == HMM_TRAINING_END
    assert trained_hmm.n_obs >= 400


def test_hmm_features_match_spec(trained_hmm: TrainedHmm) -> None:
    assert trained_hmm.feature_names == HMM_FEATURES
    assert trained_hmm.feature_mean.shape == (len(HMM_FEATURES),)
    assert trained_hmm.feature_std.shape == (len(HMM_FEATURES),)


def test_hmm_state_to_label_uses_three_distinct_labels(trained_hmm: TrainedHmm) -> None:
    labels = set(trained_hmm.state_to_label.values())
    assert labels == set(STATE_NAMES)


def test_hmm_predict_2008_09_recession() -> None:
    """At as_of=2008-09-15, HMM should output state=recession with very
    high probability — the canonical proof point of §4.7."""
    ctx = PitDataContext(as_of=pd.Timestamp("2008-09-15"))
    r = predict_state(ctx)
    assert r.state == "recession"
    assert r.state_probabilities["recession"] > 0.7
    assert abs(sum(r.state_probabilities.values()) - 1.0) < 1e-3
    assert r.model_version == HMM_VERSION


def test_hmm_pickle_roundtrip_via_script(tmp_path: Path) -> None:
    """L3.5A: training is admin-only via ``scripts/train_hmm_v1.py``.

    Run the script in --dry-run mode (subprocess) and verify the
    would-be sha256 matches the committed canonical pickle's sha256
    — i.e. the script reproduces the artifact byte-equal under the
    locked environment.
    """
    result = subprocess.run(
        [sys.executable, str(TRAIN_SCRIPT), "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"train_hmm_v1.py --dry-run failed: stderr={result.stderr!r}"
    )
    out = result.stdout
    assert "would-be pickle sha256:" in out
    assert "MATCH" in out, (
        f"L3.5A repro contract: would-be sha must match committed pickle. "
        f"stdout=\n{out}"
    )


def test_hmm_pickle_loadable_directly() -> None:
    """The pickle should be a TrainedHmm instance when read raw."""
    with Path(HMM_PICKLE_PATH).open("rb") as fh:
        obj = pickle.load(fh)
    assert isinstance(obj, TrainedHmm)
    assert obj.model_version == HMM_VERSION


def test_hmm_state_probabilities_are_valid(trained_hmm: TrainedHmm) -> None:
    """All 3 state probabilities lie in [0, 1] and sum to 1 at any as_of."""
    ctx = PitDataContext(as_of=pd.Timestamp("2017-06-01"))
    r = predict_state(ctx)
    for prob in r.state_probabilities.values():
        assert 0.0 <= prob <= 1.0
    assert abs(sum(r.state_probabilities.values()) - 1.0) < 1e-3
    assert r.state in STATE_NAMES
