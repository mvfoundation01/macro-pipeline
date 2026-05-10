"""NBER recession-state extraction with strict PIT discipline.

Layer 3A established the original ``extract_nber_state`` using a fixed
180-day approximation of the NBER announcement lag (via
``release_lag_days=180`` on ``NBER_REC_LABEL`` in ``nyfed_recprob.py``).
Layer 3.5C replaces that approximation with an authoritative
announcement calendar (see ``nber_calendar.py``):

1. ``extract_nber_state`` consults ``NberCalendarLoader.state_at`` for
   1978+ queries. The calendar carries the actual NBER committee
   announcement dates for every cycle since 1980.

2. Pre-1978 + real-time mode → raises
   ``PitDataUnavailableError`` (``NBER_PRE_1978_POLICY="training_only"``).

3. Pre-1978 + training mode (``ctx.is_real_time=False``) → returns the
   latest-knowledge label with ``is_pre_1978_training_only=True`` set
   on the result so downstream consumers can surface the caveat.

4. Latest mode (``ctx=None``) is unchanged from L3A — useful for
   post-hoc inspection / ground-truth assertion in tests / Gate 8.

5. Loader-level ``release_lag_days=180`` in ``nyfed_recprob.py:147``
   is **left in place** per Decision Lock 3.5C-AM16=(a). The calendar
   takes precedence in ``extract_nber_state``; the loader-level lag is
   still applied if NBER_REC_LABEL is loaded directly via
   ``load_series(..., as_of=...)`` for diagnostic / audit purposes
   (which has no caller in the inference path post-3.5C).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from macro_pipeline.access import IndicatorBundle, PitDataContext, load_series
from macro_pipeline.config import NBER_PRE_1978_POLICY
from macro_pipeline.regime.exceptions import (
    NberCycleNotFoundError,
    PitDataUnavailableError,
)
from macro_pipeline.regime.nber_calendar import (
    NBER_CALENDAR_BOUNDARY,
    NberCalendarLoader,
)

NBER_PRIMARY_INDICATOR = "NBER_REC_LABEL"
NBER_FALLBACK_INDICATOR = "USREC"


@dataclass(frozen=True)
class NberStateResult:
    """Result of a PIT-aware NBER state lookup.

    Layer 3.5C: ``announcement_date`` and ``is_pre_1978_training_only``
    are NEW fields. ``is_pre_1978_training_only=True`` flags results
    where NBER_PRE_1978_POLICY="training_only" allowed us to return a
    label despite the calendar boundary; downstream scoring should
    surface this caveat (analog to 3.5B Option Z's
    ``derived_confidence_cap`` propagation per AM12).
    """

    state: str                              # "expansion" | "recession"
    state_date: pd.Timestamp                # the NBER observation_date used
    last_known_label_date: pd.Timestamp     # last firm-determined date visible at as_of
    as_of: pd.Timestamp | None              # query as_of (None for full-knowledge mode)
    source: str                             # "NBER_REC_LABEL" | "USREC" | "calendar"
    announcement_date: pd.Timestamp | None = None
    is_pre_1978_training_only: bool = False


def _last_known_label_date_from_bundle(bundle: IndicatorBundle) -> pd.Timestamp:
    """Most recent observation_date with a non-null label in this bundle."""
    s = bundle.data.dropna()
    if s.empty:
        raise PitDataUnavailableError(
            indicator_id=bundle.indicator_id,
            reason="no non-null NBER labels visible at as_of",
            as_of=bundle.as_of,
        )
    return pd.Timestamp(s.index.max())


def _state_at_from_bundle(
    bundle: IndicatorBundle, query_date: pd.Timestamp,
) -> tuple[str, pd.Timestamp]:
    """Return (state, observation_date) at-or-before ``query_date`` from
    the underlying NBER_REC_LABEL series. Used for latest-mode lookups
    and pre-1978 training-mode fallback."""
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
    calendar: NberCalendarLoader | None = None,
) -> NberStateResult:
    """Return the NBER state at ``query_date``, with optional PIT enforcement.

    Layer 3.5C: when ``ctx`` is provided AND ``query_date >= 1978-01``,
    the lookup uses ``NberCalendarLoader`` (announcement-date-aware).
    Pre-1978 queries follow ``NBER_PRE_1978_POLICY``: real-time mode
    raises ``PitDataUnavailableError``; training mode returns the
    latest-knowledge label with the caveat flag set.

    Latest-knowledge mode (``ctx=None``) is unchanged from Layer 3A.

    Parameters
    ----------
    query_date
        Date to look up.
    ctx
        ``None``  → latest-knowledge / post-hoc inspection mode.
        ``PitDataContext(as_of=...)`` → calendar-aware PIT view.
    indicator_id
        ``NBER_REC_LABEL`` (default; primary FRED+NBER source) or
        ``USREC``.
    calendar
        Optional pre-loaded ``NberCalendarLoader``. Default: lazily
        constructed once per call. Passing your own loader is useful in
        tests or when the canonical CSV path has been overridden.

    Raises
    ------
    PitDataUnavailableError
        If the calendar cannot resolve a state at ``query_date`` from
        ``ctx.as_of`` (e.g., pre-1978 in real-time mode, OR query_date
        is before any announced turning point at ``as_of``).
    """
    qd = pd.Timestamp(query_date)
    qd_period = qd.to_period("M")

    # ---- Latest-knowledge mode (post-hoc inspection / ground truth) ----
    if ctx is None:
        bundle = load_series(indicator_id)
        last_known = _last_known_label_date_from_bundle(bundle)
        if qd > last_known:
            raise PitDataUnavailableError(
                indicator_id=indicator_id,
                reason=(f"query_date={qd.date()} is past last_known_label_date="
                        f"{last_known.date()} in latest cache"),
                as_of=None,
            )
        state, obs_date = _state_at_from_bundle(bundle, qd)
        return NberStateResult(
            state=state,
            state_date=obs_date,
            last_known_label_date=last_known,
            as_of=None,
            source=indicator_id,
            announcement_date=None,
            is_pre_1978_training_only=False,
        )

    # ---- PIT mode: calendar-aware ----
    cal = calendar if calendar is not None else NberCalendarLoader()

    # Pre-1978 cycles: governed by NBER_PRE_1978_POLICY.
    if qd_period < NBER_CALENDAR_BOUNDARY:
        if NBER_PRE_1978_POLICY == "training_only" and ctx.is_real_time:
            raise PitDataUnavailableError(
                indicator_id=indicator_id,
                reason=(
                    f"NBER labels for query_date={qd.date()} (pre-1978) are "
                    "training-only per NBER_PRE_1978_POLICY. Real-time "
                    "inference unavailable: pre-1978 announcement chronology "
                    "is inconsistent (cycles dated retroactively). To use "
                    "training-mode labels, construct PitDataContext with "
                    "is_real_time=False."
                ),
                as_of=ctx.as_of,
            )
        # Training mode (or relaxed policy) — fall back to latest cache,
        # with caveat flag set.
        bundle = load_series(indicator_id, as_of=ctx.as_of)
        last_known = _last_known_label_date_from_bundle(bundle)
        if qd > last_known:
            raise PitDataUnavailableError(
                indicator_id=indicator_id,
                reason=(f"query_date={qd.date()} past last_known_label_date="
                        f"{last_known.date()} in PIT cache"),
                as_of=ctx.as_of,
            )
        state, obs_date = _state_at_from_bundle(bundle, qd)
        return NberStateResult(
            state=state,
            state_date=obs_date,
            last_known_label_date=last_known,
            as_of=ctx.as_of,
            source=indicator_id,
            announcement_date=None,
            is_pre_1978_training_only=True,
        )

    # Post-1978: calendar-driven.
    try:
        last_known = cal.last_known_label(ctx.as_of)
    except NberCycleNotFoundError as exc:
        raise PitDataUnavailableError(
            indicator_id=indicator_id,
            reason=(
                f"No NBER turning point announced by as_of={ctx.as_of.date()}. "
                f"Calendar's earliest announcement is 1980-06-03 "
                f"(1980-01 peak). Detail: {exc}"
            ),
            as_of=ctx.as_of,
        ) from exc

    try:
        announced_at_query = cal._last_announced_turning_point(qd_period, ctx.as_of)
    except NberCycleNotFoundError as exc:
        # query_date is before any announced turning point at this as_of.
        raise PitDataUnavailableError(
            indicator_id=indicator_id,
            reason=(
                f"query_date={qd.date()} predates the earliest NBER "
                f"announcement visible at as_of={ctx.as_of.date()}. "
                f"Calendar covers 1978+ via committee announcements; this "
                "query lands in the pre-announcement region. Detail: "
                f"{exc}"
            ),
            as_of=ctx.as_of,
        ) from exc

    return NberStateResult(
        state=announced_at_query.regime,
        state_date=announced_at_query.turning_point_date.to_timestamp(),
        last_known_label_date=last_known.turning_point_date.to_timestamp(),
        as_of=ctx.as_of,
        source="calendar",
        announcement_date=announced_at_query.announcement_date,
        is_pre_1978_training_only=False,
    )


def last_known_label_date(
    *,
    ctx: PitDataContext | None = None,
    indicator_id: str = NBER_PRIMARY_INDICATOR,
    calendar: NberCalendarLoader | None = None,
) -> pd.Timestamp:
    """Return the last firm-determined NBER label date in the view at
    ``ctx.as_of`` (or latest if ``ctx=None``).

    Layer 3.5C: in PIT mode, this is the most recent turning point's
    date with announcement_date <= as_of (per the NBER calendar).
    Latest mode is unchanged.
    """
    if ctx is None:
        bundle = load_series(indicator_id)
        return _last_known_label_date_from_bundle(bundle)

    cal = calendar if calendar is not None else NberCalendarLoader()
    try:
        last_known = cal.last_known_label(ctx.as_of)
    except NberCycleNotFoundError as exc:
        raise PitDataUnavailableError(
            indicator_id=indicator_id,
            reason=(
                f"No NBER turning point announced by as_of={ctx.as_of.date()}; "
                f"detail: {exc}"
            ),
            as_of=ctx.as_of,
        ) from exc
    return last_known.turning_point_date.to_timestamp()


__all__ = [
    "NBER_FALLBACK_INDICATOR",
    "NBER_PRIMARY_INDICATOR",
    "NberStateResult",
    "extract_nber_state",
    "last_known_label_date",
]
