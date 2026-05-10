# scripts/ — admin-only utilities

This directory holds **admin-only** utilities that are NOT part of the
`macro_pipeline` package's public surface and MUST NOT be imported by
package modules. The purpose is to keep maintenance / training /
artifact-generation tools physically separated from the inference path
so the inference path stays deterministic and audit-clean.

Discipline (per `LAYER_3_5_BUILD_SPEC.md` §3.5A):

- `scripts/` is **not** a Python package (no `__init__.py`).
- Files here are runnable as `python scripts/<name>.py` from the repo
  root. They may use `from macro_pipeline...` imports.
- The reverse is forbidden: `macro_pipeline/` MUST NOT import anything
  from `scripts/`.
- Artifacts written by these scripts (e.g. the HMM pickle and sidecar)
  are **the** committed artifacts for that release; the inference path
  loads them and never regenerates.

## Tools

### `train_hmm_v1.py`

Refits the 3-state Gaussian HMM regime classifier on the frozen
1982-2019 window per `LAYER_3_BUILD_SPEC.md` §4.3.4 / Layer 3A.
Writes `data/cache/hmm/regime_3state_v1.pkl` and the matching
`regime_3state_v1.meta.json` sidecar atomically.

Usage:

```bash
# Re-run training and overwrite the artifact (requires --force-overwrite
# if the pickle already exists with a different sha256)
python scripts/train_hmm_v1.py [--force-overwrite]

# Compute what the artifact would be without writing; print sha256 +
# diff vs existing artifact (if any)
python scripts/train_hmm_v1.py --dry-run
```

#### Reproducibility contract (per Decision Lock 3.5A AM4)

Two-tier:

1. **Fixed environment** — Python 3.12.10, hmmlearn 0.3.3,
   numpy/scipy as locked in `uv.lock`, deterministic `random_state=42`,
   pickle protocol=4: produces a **byte-equal** pickle (sha256 match
   between runs).

2. **Cross environment** — different interpreter / library minor
   versions: produces a **behaviorally-equal** pickle (same
   `state_to_label` mapping, same `feature_mean` and `feature_std`
   within `rtol=1e-12`, identical predictions on the validation
   anchor 2008-09-15). Sha256 may differ but the trained model is
   semantically identical.

Gate 12 enforces byte-equal repro under the locked environment via
`scripts/train_hmm_v1.py --dry-run` whose output includes the would-be
pickle sha and compares it to the committed artifact.

#### Sidecar schema (1.0)

The sidecar `.meta.json` carries:

| Key | Type | Purpose |
|---|---|---|
| `schema_version` | str | Sidecar schema version (currently `"1.0"`) |
| `model_version` | str | Model version (`"v1"`) |
| `model_family` | str | Always `"GaussianHMM"` |
| `n_components` | int | Always `3` for v1 |
| `training_window_start` | str (`YYYY-MM`) | First training month |
| `training_window_end` | str (`YYYY-MM`) | Last training month |
| `n_obs_train` | int | Number of monthly observations used |
| `feature_names` | list[str] | Ordered feature list (5 in v1; 6 if NAPMNOI restored at L5-1) |
| `feature_matrix_sha256` | str | sha256 of CSV-serialized training matrix |
| `nber_label_sha256` | str | sha256 of CSV-serialized NBER labels at training time |
| `state_to_label_mapping` | dict[str,str] | HMM state index → semantic label |
| `nber_overlap_per_state` | dict[str,float] | Mean NBER label per HMM state |
| `hmmlearn_version` | str | hmmlearn version that produced the pickle |
| `python_version` | str | Python interpreter version |
| `pickle_protocol` | int | Pickle protocol (locked at 4) |
| `random_state` | int | HMM `random_state` (locked at 42) |
| `data_sha256` | str | sha256 of `regime_3state_v1.pkl` itself |
| `created_at_utc` | str (ISO 8601) | UTC timestamp of write |
| `training_script_path` | str | Path of this script |
| `training_script_sha256` | str | sha256 of this script's bytes |

#### Failure modes

- hmmlearn version mismatch (≠ 0.3.3): exit 1
- Existing artifact present, sha256 differs from would-be artifact, no
  `--force-overwrite`: exit 2 with diff explanation
- Training matrix has < 100 obs (data drift): exit 3
