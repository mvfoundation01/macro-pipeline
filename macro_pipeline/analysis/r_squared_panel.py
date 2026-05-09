"""R^2 master regression panel orchestrator (Layer 3D).

Spec: ``LAYER_3_BUILD_SPEC.md`` §7 + Strategic Claude 3D kickoff.

For every (indicator × horizon × target) cell:

  y_t = forward_return(target, t, H)              (annualized)
  x_t = indicator value as of t (asof, monthly)

Fit OLS y = alpha + beta * x with Newey-West HAC at ``maxlags = H − 1``.
Record:

  alpha, beta, r_squared, adj_r_squared, residual_se, p_value_beta_NW,
  n_nominal, n_eff_nonoverlap, is_underpowered, verdict,
  freq_native, sample_start, sample_end, ci_method, maxlags,
  indicator_id, horizon_months, horizon_label, target

Cells with no overlap (NO_OVERLAP) get NaN stats but are kept in the
panel for provenance (D16). MultiIndex indicators (HLW_VINTAGE) are
excluded (D17). Score artifacts (CRPS/CDRS) are excluded (3D-prep-4).

The completed panel is cached atomically per Layer 1.5A.5 to
``data/cache/analysis/r_squared_panel.parquet`` with a sidecar carrying
``data_sha256``, ``schema_version``, and ``row_count``.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from macro_pipeline.access import load_series
from macro_pipeline.analysis.effective_sample_size import (
    VERDICT_NO_OVERLAP,
    classify_verdict,
    is_underpowered,
    n_eff_nonoverlap,
)
from macro_pipeline.analysis.newey_west_hac import fit_ols_hac
from macro_pipeline.analysis.regression_target import (
    SUPPORTED_TARGETS,
    align_indicator_to_target,
    forward_return_series,
    load_target,
)
from macro_pipeline.config import DATA_CACHE

log = logging.getLogger(__name__)


PANEL_CACHE_PATH = DATA_CACHE / "analysis" / "r_squared_panel.parquet"
PANEL_SCHEMA_VERSION = "1.0"

HORIZONS: dict[str, int] = {
    "1Y": 12,
    "3Y": 36,
    "5Y": 60,
    "10Y": 120,
}

SCORE_ARTIFACTS: frozenset[str] = frozenset({
    "CRPS", "CDRS", "REGIME",
    # also exclude score-component intermediates if they show up by id
    "V_score", "T_score",
})

# Indicators that are MultiIndex panels (D17): excluded from the R^2
# regression because they're not single time series.
MULTIINDEX_INDICATORS: frozenset[str] = frozenset({
    "HLW_VINTAGE",
})

# Frequency map — first letter of the cached frequency or known
# alias per indicator.
FREQ_ANNOTATIONS: dict[str, str] = {
    "DAMODARAN_DY":     "A",
    "DAMODARAN_ERP":    "A",
    "DAMODARAN_EY":     "A",
    "DAMODARAN_TBOND":  "A",
}


def discover_panel_indicators() -> list[tuple[str, str]]:
    """Walk the cache and return ``[(indicator_id, freq_native), ...]``.

    Excludes:
      - MultiIndex panels (HLW_VINTAGE etc.)
      - Score artifacts (CRPS, CDRS, REGIME)
      - The two regression targets themselves (SHILLER_TR_PRICE, SP500TR)
    """
    import json
    seen: dict[str, str] = {}
    for meta_path in sorted(DATA_CACHE.glob("*.meta.json")):
        try:
            md = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        iid = md.get("indicator_id")
        if not iid:
            continue
        if iid in seen:
            continue
        if iid in SCORE_ARTIFACTS:
            continue
        if iid in MULTIINDEX_INDICATORS:
            continue
        if iid in SUPPORTED_TARGETS:
            continue
        freq = md.get("frequency") or md.get("freq") or "?"
        # Override when explicit annotation exists (Damodaran annual).
        freq = FREQ_ANNOTATIONS.get(iid, freq)
        seen[iid] = str(freq)
    return sorted(seen.items())


def _empty_row(
    *, indicator_id: str, freq_native: str, target: str,
    horizon_label: str, horizon_months: int,
    verdict: str, n_nominal: int = 0,
) -> dict:
    return {
        "indicator_id":      indicator_id,
        "freq_native":       freq_native,
        "target":            target,
        "horizon_label":     horizon_label,
        "horizon_months":    horizon_months,
        "n_nominal":         n_nominal,
        "n_eff_nonoverlap":  n_eff_nonoverlap(n_nominal, horizon_months),
        "is_underpowered":   is_underpowered(verdict),
        "verdict":           verdict,
        "sample_start":      pd.NaT,
        "sample_end":        pd.NaT,
        "alpha":             float("nan"),
        "beta":              float("nan"),
        "r_squared":         float("nan"),
        "adj_r_squared":     float("nan"),
        "residual_se":       float("nan"),
        "p_value_beta_NW":   float("nan"),
        "maxlags":           max(0, horizon_months - 1),
        "ci_method":         "newey_west_hac",
    }


def _fit_one_cell(
    indicator_id: str,
    freq_native: str,
    target_series: pd.Series,
    horizon_label: str,
    horizon_months: int,
) -> dict:
    """Build a single panel row for one (indicator × horizon × target)."""
    target_id = target_series.name
    # 1. forward returns aligned at month-end
    y = forward_return_series(target_series, horizon_months)
    if y.empty:
        return _empty_row(
            indicator_id=indicator_id, freq_native=freq_native,
            target=target_id, horizon_label=horizon_label,
            horizon_months=horizon_months, verdict=VERDICT_NO_OVERLAP,
        )

    # 2. indicator load + align
    try:
        bundle = load_series(indicator_id)
    except Exception as exc:
        log.warning("indicator %s failed to load: %s", indicator_id, exc)
        return _empty_row(
            indicator_id=indicator_id, freq_native=freq_native,
            target=target_id, horizon_label=horizon_label,
            horizon_months=horizon_months, verdict=VERDICT_NO_OVERLAP,
        )
    s = bundle.data
    if isinstance(s.index, pd.MultiIndex):  # belt-and-suspenders for D17
        return _empty_row(
            indicator_id=indicator_id, freq_native=freq_native,
            target=target_id, horizon_label=horizon_label,
            horizon_months=horizon_months, verdict=VERDICT_NO_OVERLAP,
        )
    s = s.dropna()
    if s.empty:
        return _empty_row(
            indicator_id=indicator_id, freq_native=freq_native,
            target=target_id, horizon_label=horizon_label,
            horizon_months=horizon_months, verdict=VERDICT_NO_OVERLAP,
        )

    x_aligned = align_indicator_to_target(s, y.index)
    df = pd.concat([y.rename("y"), x_aligned.rename("x")], axis=1).dropna()
    n_nom = len(df)
    verdict = classify_verdict(n_nom, horizon_months)

    if verdict == VERDICT_NO_OVERLAP or n_nom < 2:
        return _empty_row(
            indicator_id=indicator_id, freq_native=freq_native,
            target=target_id, horizon_label=horizon_label,
            horizon_months=horizon_months, verdict=VERDICT_NO_OVERLAP,
            n_nominal=n_nom,
        )

    # 3. fit
    fit = fit_ols_hac(
        df["y"], df["x"], horizon_months=horizon_months, drop_na=False,
    )
    if fit is None:
        # Degenerate: keep the row with verdict but NaN stats.
        return _empty_row(
            indicator_id=indicator_id, freq_native=freq_native,
            target=target_id, horizon_label=horizon_label,
            horizon_months=horizon_months, verdict=verdict,
            n_nominal=n_nom,
        ) | {
            "sample_start": df.index.min(),
            "sample_end":   df.index.max(),
        }

    return {
        "indicator_id":      indicator_id,
        "freq_native":       freq_native,
        "target":            target_id,
        "horizon_label":     horizon_label,
        "horizon_months":    horizon_months,
        "n_nominal":         n_nom,
        "n_eff_nonoverlap":  n_eff_nonoverlap(n_nom, horizon_months),
        "is_underpowered":   is_underpowered(verdict),
        "verdict":           verdict,
        "sample_start":      df.index.min(),
        "sample_end":        df.index.max(),
        "alpha":             fit.alpha,
        "beta":              fit.beta,
        "r_squared":         fit.r_squared,
        "adj_r_squared":     fit.adj_r_squared,
        "residual_se":       fit.residual_se,
        "p_value_beta_NW":   fit.p_value_beta_NW,
        "maxlags":           fit.maxlags,
        "ci_method":         fit.ci_method,
    }


def build_panel(
    *,
    indicators: Iterable[tuple[str, str]] | None = None,
    targets: Iterable[str] = SUPPORTED_TARGETS,
    horizons: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Build the full ~960-row R^2 panel.

    Row count = len(indicators) × len(horizons) × len(targets).
    """
    if indicators is None:
        indicators = discover_panel_indicators()
    horizons = horizons or HORIZONS
    indicators_list = list(indicators)

    target_cache: dict[str, pd.Series] = {}
    for tgt in targets:
        target_cache[tgt] = load_target(tgt)

    rows: list[dict] = []
    n_cells = len(indicators_list) * len(horizons) * len(targets)
    log.info(
        "Building R^2 panel: %d indicators x %d horizons x %d targets = %d cells",
        len(indicators_list), len(horizons), len(targets), n_cells,
    )
    for indicator_id, freq_native in indicators_list:
        for tgt in targets:
            for horizon_label, horizon_months in horizons.items():
                row = _fit_one_cell(
                    indicator_id, freq_native, target_cache[tgt],
                    horizon_label, horizon_months,
                )
                rows.append(row)
    df = pd.DataFrame(rows)
    # Stable, deterministic ordering for diff-friendly cache writes.
    df = df.sort_values(
        ["indicator_id", "target", "horizon_months"],
        kind="mergesort",
    ).reset_index(drop=True)
    return df


def write_panel_atomic(
    panel: pd.DataFrame,
    *,
    pickle_path: Path | str | None = None,
) -> tuple[Path, dict]:
    """Atomic-write the panel parquet + sidecar (Layer 1.5A.5)."""
    pickle_path = Path(pickle_path) if pickle_path is not None else PANEL_CACHE_PATH
    pickle_path.parent.mkdir(parents=True, exist_ok=True)
    # Note: cache.write_cache_atomic writes to <DATA_CACHE>/<stem>.parquet,
    # but we want the file inside data/cache/analysis/. Use the local
    # _write_atomic_subdir helper instead.
    meta = {
        "indicator_id":   "r_squared_panel",
        "schema_version": PANEL_SCHEMA_VERSION,
        "source":         "LAYER_3D_R_SQUARED_PANEL",
        "frequency":      "panel",
        "unit":           "regression_stats",
        "row_count":      int(panel.shape[0]),
    }
    return _write_atomic_subdir(panel, pickle_path, meta)


def _write_atomic_subdir(
    df: pd.DataFrame, target_path: Path, meta: dict,
) -> tuple[Path, dict]:
    """Mirror ``write_cache_atomic`` but allow a non-default subdir."""
    import hashlib
    import json
    import os
    import tempfile

    parent = target_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    sidecar = target_path.with_suffix(".meta.json")

    # Write parquet to a temp file in the same directory then rename.
    fd, tmp_parquet = tempfile.mkstemp(
        prefix="_writing_", suffix=".parquet", dir=str(parent),
    )
    os.close(fd)
    try:
        df.to_parquet(tmp_parquet, index=False)
        with open(tmp_parquet, "rb") as fh:
            data_sha = hashlib.sha256(fh.read()).hexdigest()
        meta_full = {
            **meta,
            "data_sha256": data_sha,
            "row_count":   int(df.shape[0]),
            "pipeline_processed": True,
        }
        # rename parquet
        os.replace(tmp_parquet, target_path)
    finally:
        if os.path.exists(tmp_parquet):
            os.remove(tmp_parquet)

    # Atomic sidecar write
    fd, tmp_sidecar = tempfile.mkstemp(
        prefix="_writing_", suffix=".meta.json", dir=str(parent),
    )
    os.close(fd)
    try:
        with open(tmp_sidecar, "w", encoding="utf-8") as fh:
            json.dump(meta_full, fh, indent=2, default=str)
        os.replace(tmp_sidecar, sidecar)
    finally:
        if os.path.exists(tmp_sidecar):
            os.remove(tmp_sidecar)

    return target_path, meta_full


def load_panel(pickle_path: Path | str | None = None) -> pd.DataFrame:
    """Load the cached R^2 panel parquet."""
    pickle_path = Path(pickle_path) if pickle_path is not None else PANEL_CACHE_PATH
    if not pickle_path.exists():
        raise FileNotFoundError(
            f"R^2 panel not built: {pickle_path}. Run build_panel + "
            "write_panel_atomic first."
        )
    return pd.read_parquet(pickle_path)


def build_and_cache(force: bool = False) -> tuple[pd.DataFrame, Path]:
    """Convenience: build then atomic-write. If a cache already exists
    and ``force=False``, skip the rebuild and return the cached panel."""
    if not force and PANEL_CACHE_PATH.exists():
        return load_panel(PANEL_CACHE_PATH), PANEL_CACHE_PATH
    panel = build_panel()
    path, _ = write_panel_atomic(panel)
    return panel, path


__all__ = [
    "FREQ_ANNOTATIONS",
    "HORIZONS",
    "MULTIINDEX_INDICATORS",
    "PANEL_CACHE_PATH",
    "PANEL_SCHEMA_VERSION",
    "SCORE_ARTIFACTS",
    "build_and_cache",
    "build_panel",
    "discover_panel_indicators",
    "load_panel",
    "write_panel_atomic",
]
