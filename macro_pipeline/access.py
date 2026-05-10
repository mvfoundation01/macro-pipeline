"""Public series-access API with PIT-safe / latest dispatch (Layer 1.5A.1).

Codex review HIGH #1: ``release_lag_days`` lived in metadata but was never
applied during alignment, so ``ffill`` made every observation visible from
its observation_date — letting backtests at date ``t`` see prints that
were not actually published until ``t + lag``.

Public API
----------
``load_series(id, *, as_of=None)``
    - ``as_of=None`` returns the latest-vintage view (for ingestion /
      inspection).
    - ``as_of=ts`` returns the PIT-safe view as known on ``ts`` (for
      backtest / scoring).

``PitDataContext(as_of=...)``
    Wraps the PIT path so backtest code cannot construct a "latest"
    bundle by accident: ``ctx.load(id)`` always carries the same
    ``as_of`` and the bundle is tagged ``pit_safe=True``.

How PIT semantics are enforced
------------------------------
For ``needs_vintage=True`` series listed in
``fred_vintage_panel.VINTAGE_REQUIRED_SERIES`` we look up a materialized
vintage panel and call ``get_pit_series(panel, asof_date)``: the index of
the returned series is the *observation_date* but each value is the
latest vintage with ``realtime_start <= as_of``.

For non-vintage series we shift the index forward by ``release_lag_days``
(via ``preprocessing.to_visibility_index``), truncate at ``as_of``, then
shift the index back to observation_date so the caller sees a series in
its native time axis.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import pandas as pd

from macro_pipeline.config import DATA_CACHE
from macro_pipeline.preprocessing import to_visibility_index

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bundle returned by all readers
# ---------------------------------------------------------------------------
@dataclass
class IndicatorBundle:
    """Result of a series load.

    ``data`` is the series (column name = ``indicator_id``).
    ``metadata`` is the flattened meta.json dict (so ``extra`` keys appear
    at the top level — see ``IndicatorMetadata.to_dict``).
    ``pit_safe`` is True iff this bundle came from the PIT path; backtest
    code should reject any bundle with ``pit_safe=False``.

    Layer 3.5B fields (Option Z bookkeeping):
    ``pit_safe_basis`` — short tag describing WHY the bundle is PIT-safe:
        ``"vintage_panel"`` (FRED ALFRED materialised), ``"hlw_vintage"``
        (HLW quarterly panel), ``"release_lag"`` (visibility-shift via
        ``release_lag_days``), ``"asof_truncation"`` (no lag), or
        ``"by_construction"`` (Option Z — series is constructed from
        only-known-at-the-time data per its publishing methodology;
        SAHMREALTIME is the canonical example).
    ``derived_confidence_cap`` — Option Z upper bound on downstream
        confidence ∈ (0, 1]. ``None`` when the source carries no derived
        cap. Layer 3.5B propagates this through ``compute_final_confidence_cap``
        so CRPS / CDRS aggregate caps reflect it.
    ``notes`` — free-text trail visible to Layer 6 reporting; populated
        by readers and downstream scorers. Same intent as the future
        ``ScoredObservation.notes`` field (3.5D); 3.5B writes here from
        the reader side and 3.5D will plumb the scorer side.
    """
    indicator_id: str
    data: pd.Series
    metadata: dict[str, Any]
    pit_safe: bool
    as_of: pd.Timestamp | None = None
    pit_safe_basis: str = "n/a"
    derived_confidence_cap: float | None = None
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cache discovery
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _cache_registry() -> dict[str, str]:
    """Map ``indicator_id -> cache_stem`` (e.g. ``"PAYEMS" -> "fred_PAYEMS"``).

    Cached at module level via ``lru_cache``; call ``_cache_registry.cache_clear()``
    in tests that mutate the cache directory.
    """
    registry: dict[str, str] = {}
    if not DATA_CACHE.exists():
        return registry
    for meta_path in DATA_CACHE.glob("*.meta.json"):
        try:
            meta = json.loads(meta_path.read_bytes())
        except (json.JSONDecodeError, OSError):
            continue
        iid = meta.get("indicator_id")
        if not iid:
            continue
        stem = meta_path.name[: -len(".meta.json")]
        # If a previous loop added the same iid (e.g. cross-source), keep
        # the first one. Loaders are responsible for using a `_<SOURCE>`
        # suffix when there is genuine collision (HANDOFF naming rule).
        registry.setdefault(iid, stem)
    return registry


def _refresh_registry() -> None:
    _cache_registry.cache_clear()


def _find_cache_stem(indicator_id: str) -> str:
    registry = _cache_registry()
    if indicator_id in registry:
        return registry[indicator_id]
    # The lru_cache might have been built before the file existed (common
    # in tests that just wrote a new cache); refresh once and retry.
    _refresh_registry()
    registry = _cache_registry()
    if indicator_id not in registry:
        raise KeyError(
            f"{indicator_id}: no cache file found under {DATA_CACHE}. "
            f"Run the appropriate loader first to populate the cache."
        )
    return registry[indicator_id]


def _read_cached_series_and_meta(stem: str, indicator_id: str) -> tuple[pd.Series, dict]:
    """Read a cached single-series parquet through the validated cache helper.

    Layer 3.5b-T (closes Codex finding T): the prior implementation
    called ``pd.read_parquet`` directly and ignored the sidecar
    entirely — a tampered parquet, a stale ``data_sha256``, or a
    schema_version drift would all silently feed downstream scoring
    with corrupt or wrong-version data. Production reads now route
    through ``cache.read_cache_validated`` which validates
    schema_version + sha256 + row_count + mandatory ``data_sha256``
    field. Any cache-integrity failure raises
    ``CacheValidationError`` — there is no silent fallback at the
    production boundary.

    Loaders that own a rebuild flow continue to call
    ``read_cache_validated`` directly and treat ``None`` as the
    rebuild signal; this access-layer wrapper has no rebuild flow,
    so ``None`` from the helper (schema mismatch, missing files,
    sha mismatch, row_count mismatch) is converted to a raise.
    """
    from macro_pipeline.cache import read_cache_validated
    from macro_pipeline.exceptions import CacheValidationError

    parquet_path = DATA_CACHE / f"{stem}.parquet"
    result = read_cache_validated(stem, DATA_CACHE)
    if result is None:
        raise CacheValidationError(
            path=str(parquet_path),
            reason=(
                "cache validation failed for production read "
                "(schema_version mismatch, missing files, sha256 "
                "mismatch, or row_count mismatch); rebuild via the "
                "appropriate loader"
            ),
            context={"stem": stem, "indicator_id": indicator_id},
        )
    df, meta = result
    if df.shape[1] == 0:
        raise ValueError(f"{indicator_id}: empty parquet at {parquet_path}")
    # The convention is "column name = bare indicator_id", but legacy
    # files may have used the full stem. Pick the column whose name
    # matches indicator_id, else the first column.
    s = (df[indicator_id] if indicator_id in df.columns else df.iloc[:, 0]).copy()
    s.name = indicator_id
    return s, meta


# ---------------------------------------------------------------------------
# Latest-vintage reader
# ---------------------------------------------------------------------------
@dataclass
class LatestSeriesReader:
    """Returns the most-recent-vintage view of a cached indicator.

    Use this for ingestion, inspection, and report generation — anywhere
    the goal is "what does the data look like *today*". Do NOT use this
    for backtest scoring: it can leak future revisions into past dates.
    """

    def load(self, indicator_id: str) -> IndicatorBundle:
        stem = _find_cache_stem(indicator_id)
        s, meta = _read_cached_series_and_meta(stem, indicator_id)
        return IndicatorBundle(
            indicator_id=indicator_id,
            data=s,
            metadata=meta,
            pit_safe=False,
            as_of=None,
        )


# ---------------------------------------------------------------------------
# PIT reader
# ---------------------------------------------------------------------------
# Map HLW indicator ids (latest-cache names) → vintage-panel column names.
# The Phase 4D vintage cache stores three columns named with a `_VINTAGE`
# suffix; the user-facing latest-cache loader exposes the same indicators
# without the suffix. Both names point to the same underlying series, so
# PIT lookups for the bare names route through the vintage panel.
HLW_VINTAGE_INDICATORS: dict[str, str] = {
    "HLW_RSTAR":         "HLW_RSTAR_VINTAGE",
    "HLW_TREND_GROWTH":  "HLW_TREND_GROWTH_VINTAGE",
    "HLW_OUTPUT_GAP":    "HLW_OUTPUT_GAP_VINTAGE",
}


@dataclass
class PitSeriesReader:
    """Returns a series as known on ``as_of``.

    Dispatches to the right vintage source based on indicator id:

    - In ``fred_vintage_panel.VINTAGE_REQUIRED_SERIES``: uses the
      materialized FRED vintage panel via ``get_pit_series``. The returned
      index is the *observation_date*; each value is the latest vintage
      whose ``realtime_start <= as_of``. ``release_lag_days`` is not
      additionally applied — the panel encodes visibility directly.

    - In ``HLW_VINTAGE_INDICATORS`` (``HLW_RSTAR`` /
      ``HLW_TREND_GROWTH`` / ``HLW_OUTPUT_GAP``): routes through
      ``hlw_rstar_vintage.get_pit_rstar`` (Phase 4D quarterly vintage
      panel). The metadata records the matched ``hlw_vintage`` and its
      ``hlw_vintage_publication_date`` for audit. (Layer 1.5B.5 — closed
      the warning previously emitted by ``_load_via_visibility_shift``.)

    - Otherwise: applies ``to_visibility_index`` (shift index by
      ``release_lag_days``), truncates at ``as_of``, then shifts back so
      the series is again indexed by observation_date.
    """

    def load(self, indicator_id: str, as_of: pd.Timestamp) -> IndicatorBundle:
        as_of_ts = pd.Timestamp(as_of)

        # Local imports to avoid a fred-loader cycle if access.py is
        # imported during fred_loader setup.
        from macro_pipeline.loaders.fred_vintage_panel import (
            VINTAGE_REQUIRED_SERIES,
            get_pit_series,
            load_panel,
        )

        if indicator_id in VINTAGE_REQUIRED_SERIES:
            return self._load_via_vintage_panel(indicator_id, as_of_ts, load_panel, get_pit_series)

        if indicator_id in HLW_VINTAGE_INDICATORS:
            return self._load_via_hlw_vintage(indicator_id, as_of_ts)

        return self._load_via_visibility_shift(indicator_id, as_of_ts)

    def _load_via_hlw_vintage(
        self, indicator_id: str, as_of: pd.Timestamp,
    ) -> IndicatorBundle:
        # Local import keeps the heavy openpyxl/pandas chain off the
        # critical path for callers that never touch HLW.
        from macro_pipeline.loaders.hlw_rstar_vintage import get_pit_rstar

        column_name = HLW_VINTAGE_INDICATORS[indicator_id]
        stem = _find_cache_stem(indicator_id)
        _, latest_meta = _read_cached_series_and_meta(stem, indicator_id)

        df = get_pit_rstar(asof_date=as_of, raise_on_no_vintage=True)
        if column_name not in df.columns:
            raise KeyError(
                f"{indicator_id}: column {column_name!r} missing from HLW "
                f"vintage panel; available: {list(df.columns)}"
            )
        s = df[column_name].dropna().rename(indicator_id)

        # Layer 1.5C.5 / E.2: compute staleness in quarters at as_of and
        # surface it on the metadata. quality_caps.vintage_staleness_cap
        # picks this up to derive an additional 0.80 cap when stale > 2.
        from macro_pipeline.models.quality_caps import (
            stale_quarters_since_release,
            vintage_staleness_cap,
        )
        pub = df.attrs.get("publication_date")
        stale_q = stale_quarters_since_release(pub, as_of)
        staleness_cap = vintage_staleness_cap(stale_q)

        meta = {
            **latest_meta,
            "pit_source": "hlw_vintage_panel",
            "hlw_vintage": df.attrs.get("vintage"),
            "hlw_vintage_publication_date": pub,
            "stale_quarters_since_release": stale_q,
        }
        if staleness_cap is not None:
            meta["vintage_staleness_cap"] = staleness_cap

        return IndicatorBundle(
            indicator_id=indicator_id,
            data=s,
            metadata=meta,
            pit_safe=True,
            as_of=as_of,
            pit_safe_basis="hlw_vintage",
        )

    def _load_via_vintage_panel(
        self,
        indicator_id: str,
        as_of: pd.Timestamp,
        load_panel,
        get_pit_series,
    ) -> IndicatorBundle:
        stem = _find_cache_stem(indicator_id)
        _, meta = _read_cached_series_and_meta(stem, indicator_id)
        panel = load_panel(indicator_id)
        s = get_pit_series(panel, asof_date=as_of)
        s.name = indicator_id

        return IndicatorBundle(
            indicator_id=indicator_id,
            data=s,
            metadata={**meta, "pit_source": "vintage_panel"},
            pit_safe=True,
            as_of=as_of,
            pit_safe_basis="vintage_panel",
        )

    def _load_via_visibility_shift(
        self, indicator_id: str, as_of: pd.Timestamp,
    ) -> IndicatorBundle:
        """Layer 3.5B refactor — explicit 3-way branching:

        1. ``vintage`` flag + Option Z (``pit_safe_by_construction=True``):
           return latest cache truncated at ``as_of``, annotated with
           ``pit_safe_basis="by_construction"`` and ``derived_confidence_cap``
           from config; downstream caps confidence accordingly.
        2. ``vintage`` flag set but neither in ``VINTAGE_REQUIRED_SERIES``
           NOR Option Z flagged: **raise ``PitContractViolationError``**
           (Codex finding B closure — no more silent latest-cache
           fallback claiming ``pit_safe=True``).
        3. No vintage flag: standard release-lag visibility shift (when
           ``release_lag_days > 0``) or as-of truncation (lag=0). This
           is the Tier-1/2/3 indicator path, unchanged from L1.5.
        """
        stem = _find_cache_stem(indicator_id)
        s, meta = _read_cached_series_and_meta(stem, indicator_id)
        needs_vintage = bool(meta.get("needs_vintage", False))

        # Pull config from live source of truth (FRED_SERIES_API) with
        # cache-meta fallback. Config is authoritative because the cache
        # sidecar may have been written before a config update (e.g.,
        # Layer 3.5b-U recalibrated SAHMREALTIME release_lag_days 7→30
        # but the sidecar still records 7 until the next loader rewrite).
        # Test fixtures that mock meta directly continue to work via the
        # fallback.
        from macro_pipeline.config import FRED_SERIES_API
        spec = FRED_SERIES_API.get(indicator_id, {})
        lag = int(spec.get("release_lag_days", meta.get("release_lag_days", 0)))
        pit_safe_by_construction = bool(
            spec.get("pit_safe_by_construction",
                     meta.get("pit_safe_by_construction", False))
        )
        derived_cap = spec.get(
            "derived_confidence_cap", meta.get("derived_confidence_cap")
        )
        construction_rationale = spec.get(
            "pit_construction_rationale",
            meta.get("pit_construction_rationale"),
        )

        # ---- Branch 1: Option Z (Layer 3.5b-U closes Codex finding U) ----
        if needs_vintage and pit_safe_by_construction:
            # Pre-3.5b-U the truncation was a bare ``s[s.index <= as_of]``
            # that ignored ``release_lag_days`` while metadata claimed
            # ``applied_release_lag_days=lag`` — Codex finding U flagged this
            # as a look-ahead-bias source for observation-month-indexed
            # series like SAHMREALTIME. Apply the same visibility-shift
            # discipline as Branch 3 below: shift the index by the
            # configured release lag, truncate at as_of, restore the
            # observation-date index. With SAHM's calibrated lag=30 (D29)
            # this excludes the current observation month before its
            # publication date.
            if lag > 0:
                shifted = to_visibility_index(s, lag)
                visible = shifted[shifted.index <= as_of]
                obs_idx = visible.index - pd.Timedelta(days=lag)
                out = pd.Series(visible.values, index=obs_idx, name=indicator_id)
            else:
                out = s[s.index <= as_of].copy()
                out.name = indicator_id
            note = (
                f"{indicator_id}: pit_safe_by_construction=True; "
                f"derived_confidence_cap={derived_cap}; "
                f"applied_release_lag_days={lag}. "
                f"Rationale: {construction_rationale}"
            )
            log.info(
                "%s: PIT-safe by construction; cap=%s; lag=%dd applied",
                indicator_id, derived_cap, lag,
            )
            return IndicatorBundle(
                indicator_id=indicator_id,
                data=out,
                metadata={
                    **meta,
                    "pit_source": "by_construction_visibility_shift" if lag > 0 else "by_construction_asof",
                    "pit_safe_by_construction": True,
                    "derived_confidence_cap": derived_cap,
                    "applied_release_lag_days": lag,
                },
                pit_safe=True,
                as_of=as_of,
                pit_safe_basis="by_construction",
                derived_confidence_cap=(
                    float(derived_cap) if derived_cap is not None else None
                ),
                notes=[note],
            )

        # ---- Branch 2: contract violation (no panel, no Option Z) ----
        if needs_vintage:
            from macro_pipeline.exceptions import PitContractViolationError
            raise PitContractViolationError(
                indicator_id=indicator_id,
                reason=(
                    f"Series {indicator_id!r} has vintage=True but is "
                    "neither in VINTAGE_REQUIRED_SERIES (no materialized "
                    "vintage panel) nor flagged "
                    "pit_safe_by_construction=True. Required disposition: "
                    "(a) materialise vintage panel, (b) set Option Z flag "
                    "with rationale + derived_confidence_cap, OR (c) set "
                    "vintage=False if the series is genuinely non-vintage."
                ),
                context={
                    "as_of": str(as_of),
                    "needs_vintage": True,
                    "pit_safe_by_construction": False,
                },
            )

        # ---- Branch 3: standard non-vintage path (Tier 1/2/3) ----
        if lag > 0:
            shifted = to_visibility_index(s, lag)
            visible = shifted[shifted.index <= as_of]
            obs_idx = visible.index - pd.Timedelta(days=lag)
            out = pd.Series(visible.values, index=obs_idx, name=indicator_id)
            basis = "release_lag"
        else:
            out = s[s.index <= as_of].copy()
            out.name = indicator_id
            basis = "asof_truncation"

        return IndicatorBundle(
            indicator_id=indicator_id,
            data=out,
            metadata={
                **meta,
                "pit_source": "visibility_shift" if lag > 0 else "asof_truncation",
                "applied_release_lag_days": lag,
            },
            pit_safe=True,
            as_of=as_of,
            pit_safe_basis=basis,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
_LATEST = LatestSeriesReader()
_PIT = PitSeriesReader()


def load_series(
    indicator_id: str,
    *,
    as_of: pd.Timestamp | str | None = None,
) -> IndicatorBundle:
    """Load an indicator series.

    Parameters
    ----------
    indicator_id
        Bare indicator id (e.g. ``"PAYEMS"``, ``"T10Y2Y"``, ``"VIX_YAHOO"``).
    as_of
        ``None`` (default) → latest-vintage view, returned with
        ``pit_safe=False``. Use for ingestion / inspection.
        ``pd.Timestamp`` (or ISO string) → PIT-safe view as known on that
        date, returned with ``pit_safe=True``. Use for backtest /
        scoring.
    """
    if as_of is None:
        return _LATEST.load(indicator_id)
    return _PIT.load(indicator_id, as_of=pd.Timestamp(as_of))


# ---------------------------------------------------------------------------
# Backtest contract
# ---------------------------------------------------------------------------
@dataclass
class PitDataContext:
    """Backtest-safe context. Construct once per ``as_of``, then call ``.load``.

    Layer 5 should require ``PitDataContext`` as the only data-access
    argument so backtest code cannot accidentally pass a latest-view
    bundle. ``as_of=None`` raises immediately at construction time.

    Layer 3.5C: ``is_real_time`` (default ``True``) governs the NBER
    pre-1978 policy. Real-time callers (default) refuse to label
    pre-1978 dates because the announcement chronology is inconsistent
    before that boundary; training-mode callers (``is_real_time=False``)
    explicitly opt in to latest-knowledge labels for historical
    calibration / fitting workflows. See ``NBER_PRE_1978_POLICY`` in
    ``config.py``.
    """
    as_of: pd.Timestamp = field(default=None)  # type: ignore[assignment]
    is_real_time: bool = True

    def __post_init__(self) -> None:
        if self.as_of is None:
            raise ValueError("PitDataContext requires as_of date (got None)")
        self.as_of = pd.Timestamp(self.as_of)

    def load(self, indicator_id: str) -> IndicatorBundle:
        return load_series(indicator_id, as_of=self.as_of)


__all__ = [
    "IndicatorBundle",
    "LatestSeriesReader",
    "PitDataContext",
    "PitSeriesReader",
    "load_series",
]
