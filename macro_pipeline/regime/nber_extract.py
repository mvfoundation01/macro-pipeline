"""NBER recession-state extraction with strict PIT discipline (Layer 3A).

Spec: ``LAYER_3_BUILD_SPEC.md`` §4.3.1.

NBER announces recession peak/trough dates with a 6-18 month delay; FRED's
USREC and the NY Fed ``allmonth.xls`` ``NBER_REC_LABEL`` series are then
back-filled retroactively. A naive ``USREC[t]`` lookup at a historical
``as_of`` therefore leaks future knowledge (the 2007-12 peak was only
announced 2008-12-01, but USREC[2008-09]=1 in today's cache).

We mitigate this in two ways:

1. ``NBER_REC_LABEL`` is the primary source — its loader masks all values
   past ``last_known_label_date`` to NaN, so ``ffill`` cannot manufacture
   a "future" label. With ``release_lag_days=180`` this approximates the
   6-month minimum NBER announcement delay.

2. ``extract_nber_state`` enforces ``query_date <= last_known_label_date``
   in the PIT view at ``ctx.as_of``. If the ground-truth label for
   ``query_date`` is not yet known at ``as_of`` we raise
   ``PitDataUnavailableError`` rather than guess.

The function NEVER ffills past ``last_known_label_date``.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from macro_pipeline.access import IndicatorBundle, PitDataContext, load_series
from macro_pipeline.regime.exceptions import PitDataUnavailableError

NBER_PRIMARY_INDICATOR = "NBER_REC_LABEL"
NBER_FALLBACK_INDICATOR = "USREC"


@dataclass(frozen=True)
class NberStateResult:
    """Result of a PIT-aware NBER state lookup."""

    state: str                              # "expansion" | "recession"
    state_date: pd.Timestamp                # the NBER observation_date used
    last_known_label_date: pd.Timestamp     # last non-null label visible at as_of
    as_of: pd.Timestamp | None              # query as_of (None for full-knowledge mode)
    source: str                             # "NBER_REC_LABEL" | "USREC"


def _last_known_label_date(bundle: IndicatorBundle) -> pd.Timestamp:
    """Most recent observation_date with a non-null label in this bundle.

    For ``NBER_REC_LABEL`` this is the date NBER had last confirmed a
    state; values past this date are NaN by construction (see
    ``loaders/nyfed_recprob.py``). For ``USREC`` (which has no NaN
    masking) this is just the last observation in the visibility-shifted
    PIT view, which is a coarser approximation.
    """
    s = bundle.data.dropna()
    if s.empty:
        raise PitDataUnavailableError(
            indicator_id=bundle.indicator_id,
            reason="no non-null NBER labels visible at as_of",
            as_of=bundle.as_of,
        )
    return pd.Timestamp(s.index.max())


def _state_at(bundle: IndicatorBundle, query_date: pd.Timestamp) -> tuple[str, pd.Timestamp]:
    """Return (state, observation_date) for the most recent label in the
    calendar month of ``query_date`` or earlier.

    Both the FRED ``USREC`` series and NY Fed's NBER label are nominally
    monthly, but the underlying date conventions vary (1959-02-02 first
    obs vs 2026-04-30 last obs). To avoid false-negatives when
    ``query_date`` falls a few days before the actual stamp (e.g.
    ``1973-12-01`` query vs ``1973-12-02`` obs), we treat any
    observation within the same calendar month as visible.

    The caller is responsible for asserting ``query_date <= last_known_label_date``
    BEFORE calling this. We do NOT ffill past the last non-null label —
    if there's no observation at or before ``query_date`` we raise.
    """
    s = bundle.data.dropna()
    if s.empty:
        raise PitDataUnavailableError(
            indicator_id=bundle.indicator_id,
            reason="no non-null NBER labels available",
            as_of=bundle.as_of,
        )
    cutoff = (query_date + pd.tseries.offsets.MonthEnd(0)).normalize()
    valid = s[s.index <= cutoff]
    if valid.empty:
        raise PitDataUnavailableError(
            indicator_id=bundle.indicator_id,
            reason=(f"query_date={query_date.date()} is before earliest "
                    f"label {s.index.min().date()}"),
            as_of=bundle.as_of,
        )
    obs_date = pd.Timestamp(valid.index.max())
    value = float(valid.iloc[-1])
    state = "recession" if value >= 0.5 else "expansion"
    return state, obs_date


def extract_nber_state(
    query_date: pd.Timestamp | str,
    *,
    ctx: PitDataContext | None = None,
    indicator_id: str = NBER_PRIMARY_INDICATOR,
) -> NberStateResult:
    """Return the NBER state at ``query_date``, with optional PIT enforcement.

    Parameters
    ----------
    query_date
        Date to look up. May be ANY timestamp; we resolve to the most
        recent NBER observation at or before it.
    ctx
        - ``None``  → full-knowledge / latest-cache mode (post-hoc
          inspection only — never use for backtest).
        - ``PitDataContext(as_of=...)`` → PIT-safe view; we load the
          NBER series as known at ``as_of`` and refuse to return a state
          for any ``query_date > last_known_label_date(as_of)``.
    indicator_id
        ``"NBER_REC_LABEL"`` (default; NaN-masked past last determination)
        or ``"USREC"`` (no masking; coarser PIT). Use the default unless
        you specifically need USREC for cross-validation.

    Raises
    ------
    PitDataUnavailableError
        If the ground-truth label for ``query_date`` is not yet known at
        ``ctx.as_of`` (i.e. NBER had not yet announced).
    """
    qd = pd.Timestamp(query_date)
    bundle = load_series(indicator_id, as_of=ctx.as_of) if ctx is not None else load_series(indicator_id)
    last_known = _last_known_label_date(bundle)
    if qd > last_known:
        raise PitDataUnavailableError(
            indicator_id=indicator_id,
            reason=(f"query_date={qd.date()} is past last_known_label_date="
                    f"{last_known.date()} in PIT view at "
                    f"as_of={'None' if ctx is None else ctx.as_of.date()} "
                    "(NBER announces with 6-18 month delay; refusing to "
                    "fabricate a label)"),
            as_of=bundle.as_of,
        )
    state, obs_date = _state_at(bundle, qd)
    return NberStateResult(
        state=state,
        state_date=obs_date,
        last_known_label_date=last_known,
        as_of=bundle.as_of,
        source=indicator_id,
    )


def last_known_label_date(
    *,
    ctx: PitDataContext | None = None,
    indicator_id: str = NBER_PRIMARY_INDICATOR,
) -> pd.Timestamp:
    """Return last_known_label_date in the PIT view at ``ctx.as_of`` (or latest)."""
    bundle = load_series(indicator_id, as_of=ctx.as_of) if ctx is not None else load_series(indicator_id)
    return _last_known_label_date(bundle)


__all__ = [
    "NBER_FALLBACK_INDICATOR",
    "NBER_PRIMARY_INDICATOR",
    "NberStateResult",
    "extract_nber_state",
    "last_known_label_date",
]
