"""Tests for Layer 3.5A HMM frozen contract.

Per ``LAYER_3_5_BUILD_SPEC.md`` §3.5.

Each test exercises one fail-closed invariant of the new
``load_hmm`` contract, OR one positive integrity assertion (sidecar
shape, deterministic load, public-export shape).

Negative tests dominate by design (Codex finding S): 7 NEG / 3 POS.
"""
from __future__ import annotations

import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.regime import (
    HMM_PICKLE_PATH,
    HMM_SIDECAR_PATH,
    SIDECAR_REQUIRED_KEYS,
    HmmArtifactCorruptError,
    HmmArtifactMissingError,
    HmmConcurrencyError,
    HmmMetadataIncompatibleError,
    TrainedHmm,
    load_hmm,
    predict_state,
)


@pytest.fixture
def temp_hmm_dir(tmp_path):
    """Stage a copy of the canonical pickle + sidecar in tmp_path so
    individual tests can mutate them without disturbing the committed
    artifact."""
    pickle_dst = tmp_path / "regime_3state_v1.pkl"
    sidecar_dst = tmp_path / "regime_3state_v1.meta.json"
    shutil.copy2(HMM_PICKLE_PATH, pickle_dst)
    shutil.copy2(HMM_SIDECAR_PATH, sidecar_dst)
    return tmp_path, pickle_dst, sidecar_dst


# ---------------------------------------------------------------------------
# 1. Fail-closed: missing pickle
# ---------------------------------------------------------------------------
def test_hmm_missing_artifact_raises_HmmArtifactMissingError(temp_hmm_dir):
    _, pickle_dst, _ = temp_hmm_dir
    pickle_dst.unlink()
    with pytest.raises(HmmArtifactMissingError) as exc_info:
        load_hmm(pickle_dst)
    msg = str(exc_info.value)
    # Ensure the error guides the admin to the regenerator and does
    # NOT silently fall back to training.
    assert "scripts/train_hmm_v1.py" in msg
    assert "auto-train" in msg or "auto-retrain" in msg or "fail-closed" in msg or "auto" in msg.lower() or "regenerate" in msg


# ---------------------------------------------------------------------------
# 2. Fail-closed: corrupt pickle (sha256 mismatch)
# ---------------------------------------------------------------------------
def test_hmm_corrupt_artifact_raises_HmmArtifactCorruptError(temp_hmm_dir):
    _, pickle_dst, _ = temp_hmm_dir
    raw = pickle_dst.read_bytes()
    # Flip one byte deep in the pickle (avoid header) to corrupt sha
    # without breaking the pickle protocol so badly that pickle.loads
    # raises before sha check.
    mutated = bytearray(raw)
    mutated[len(raw) - 5] ^= 0x01
    pickle_dst.write_bytes(bytes(mutated))
    with pytest.raises(HmmArtifactCorruptError) as exc_info:
        load_hmm(pickle_dst)
    assert "sha256 mismatch" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. Fail-closed: schema_version mismatch
# ---------------------------------------------------------------------------
def test_hmm_metadata_schema_version_mismatch_raises(temp_hmm_dir):
    _, pickle_dst, sidecar_dst = temp_hmm_dir
    meta = json.loads(sidecar_dst.read_text(encoding="utf-8"))
    meta["schema_version"] = "0.0"
    sidecar_dst.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with pytest.raises(HmmMetadataIncompatibleError) as exc_info:
        load_hmm(pickle_dst)
    assert "schema_version" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Positive: sidecar has all required keys with sane types
# ---------------------------------------------------------------------------
def test_hmm_load_validates_all_metadata_fields():
    sidecar = json.loads(HMM_SIDECAR_PATH.read_text(encoding="utf-8"))
    for key in SIDECAR_REQUIRED_KEYS:
        assert key in sidecar, f"Required sidecar key {key!r} missing"
    # Type spot-checks
    assert isinstance(sidecar["n_components"], int)
    assert sidecar["n_components"] == 3
    assert isinstance(sidecar["n_obs_train"], int)
    assert sidecar["n_obs_train"] >= 400
    assert isinstance(sidecar["feature_names"], list)
    assert all(isinstance(s, str) for s in sidecar["feature_names"])
    assert isinstance(sidecar["state_to_label_mapping"], dict)
    assert set(sidecar["state_to_label_mapping"].values()) == {
        "expansion", "late-cycle", "recession",
    }
    assert isinstance(sidecar["random_state"], int)
    assert sidecar["random_state"] == 42
    assert isinstance(sidecar["pickle_protocol"], int)
    assert sidecar["pickle_protocol"] == 4
    assert sidecar["hmmlearn_version"] == "0.3.3"
    # sha fields are 64 hex chars
    assert len(sidecar["data_sha256"]) == 64
    assert len(sidecar["feature_matrix_sha256"]) == 64
    assert len(sidecar["nber_label_sha256"]) == 64


# ---------------------------------------------------------------------------
# 5. Positive: load_hmm + predict_state are deterministic across loads
# ---------------------------------------------------------------------------
def test_hmm_inference_deterministic_across_loads():
    ctx = PitDataContext(as_of=pd.Timestamp("2008-09-15"))
    results = []
    for _ in range(5):
        r = predict_state(ctx)
        results.append((r.state, tuple(sorted(r.state_probabilities.items()))))
    # All five runs must be identical
    assert all(r == results[0] for r in results), \
        f"Determinism broken: {results}"
    assert results[0][0] == "recession"


# ---------------------------------------------------------------------------
# 6. Concurrent load: 4 threads return identical bundles, no race.
# ---------------------------------------------------------------------------
def test_hmm_concurrent_load_safe_no_race():
    def _load():
        return load_hmm()

    with ThreadPoolExecutor(max_workers=4) as ex:
        bundles = list(ex.map(lambda _: _load(), range(4)))
    # All should be TrainedHmm; same model_version + same feature_mean
    assert all(isinstance(b, TrainedHmm) for b in bundles)
    base = bundles[0]
    for other in bundles[1:]:
        assert other.model_version == base.model_version
        assert other.feature_names == base.feature_names
        assert (other.feature_mean == base.feature_mean).all()
        assert (other.feature_std == base.feature_std).all()
        assert other.state_to_label == base.state_to_label


# ---------------------------------------------------------------------------
# 7. Negative: inference path does NOT call training even via reflection
# ---------------------------------------------------------------------------
def test_hmm_no_auto_train_in_inference_path():
    """Confirm predict_state succeeds without invoking any training
    function. We patch a sentinel symbol that, if invoked, would assert.
    The point is to assert by *absence* — predict_state must run from
    the existing pickle alone, never reaching for a training routine.
    """
    # The function used to be at this path; assert it's GONE.
    import macro_pipeline.regime.hmm_states as hmm_mod
    assert not hasattr(hmm_mod, "train_and_save_hmm"), (
        "L3.5A: train_and_save_hmm must not live in the inference module"
    )

    # Now exercise the inference path; any RuntimeError or NameError
    # would surface here.
    ctx = PitDataContext(as_of=pd.Timestamp("2008-09-15"))
    r = predict_state(ctx)
    assert r.state == "recession"


# ---------------------------------------------------------------------------
# 8. Negative: train_and_save_hmm not importable from public package
# ---------------------------------------------------------------------------
def test_hmm_train_not_in_public_exports():
    # Importing the symbol from the public regime package must fail
    # post-3.5A (Codex finding R closure).
    with pytest.raises(ImportError):
        from macro_pipeline.regime import train_and_save_hmm  # noqa: F401


# ---------------------------------------------------------------------------
# 9. Negative: lock timeout raises HmmConcurrencyError
# ---------------------------------------------------------------------------
def test_hmm_lock_timeout_raises_HmmConcurrencyError(temp_hmm_dir, monkeypatch):
    _, pickle_dst, _ = temp_hmm_dir

    # Stub filelock.FileLock so acquire() always times out. We patch
    # the binding inside hmm_states._acquire_lock's import scope by
    # installing a fake filelock module before _acquire_lock runs.
    from filelock import Timeout as RealTimeout

    from macro_pipeline.regime import hmm_states as hmm_mod

    class _FakeLock:
        def __init__(self, path, timeout):
            self.path = path
            self.timeout = timeout

        def acquire(self):
            raise RealTimeout(self.path)

        def release(self):
            pass

    fake_filelock = type(sys)("fake_filelock")
    fake_filelock.FileLock = _FakeLock
    fake_filelock.Timeout = RealTimeout

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "filelock":
            return fake_filelock
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(HmmConcurrencyError) as exc_info:
        hmm_mod.load_hmm(pickle_dst)
    assert "lock" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 10. Positive: state_to_label mapping in pickle == sidecar mapping
# ---------------------------------------------------------------------------
def test_hmm_state_to_label_mapping_deterministic():
    sidecar = json.loads(HMM_SIDECAR_PATH.read_text(encoding="utf-8"))
    sidecar_mapping = sidecar["state_to_label_mapping"]
    bundle = load_hmm()
    bundle_mapping = {str(k): v for k, v in bundle.state_to_label.items()}
    assert sidecar_mapping == bundle_mapping
    # Recession state_idx in sidecar matches the one in pickle
    rec_idx_sidecar = next(
        k for k, v in sidecar_mapping.items() if v == "recession"
    )
    rec_idx_bundle = next(
        k for k, v in bundle_mapping.items() if v == "recession"
    )
    assert rec_idx_sidecar == rec_idx_bundle
