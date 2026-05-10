"""Forward-return target loaders for the R^2 master panel (Layer 3D).

Spec: ``LAYER_3_BUILD_SPEC.md`` §7.2 + §8.1.

Two targets are supported:

| target              | source        | range          | use                          |
|---------------------|---------------|----------------|------------------------------|
| ``SHILLER_TR_PRICE``| Shiller XLS   | 1871 → present | PRIMARY (real total return)  |
| ``SP500TR``         | Yahoo ^SP500TR| 1988 → present | sanity (nominal total return)|

The ``forward_return`` helper rejects target observations past
``t + horizon_months`` so downstream regressions cannot peek into
future target values. Per spec §7.3, forward N-month return at time t
is computed as ``(target[t+N] / target[t]) − 1`` and is **annualized**
(geometric) so all horizons are comparable.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from macro_pipeline.access import load_series

log = logging.getLogger(__name__)

SUPPORTED_TARGETS: tuple[str, ...] = ("SHILLER_TR_PRICE", "SP500TR")


def load_target(target_id: str) -> pd.Series:
    """Load the target series, dropna, sort by date.

    Uses ``load_series`` (latest mode) per the 3D-prep-3 design choice:
    the R^2 panel describes "current best understanding of historical
    relationships" with fully-revised data; PIT-conditioned regressions
    are a separate stratum (Layer 5b).
    """
    if target_id not in SUPPORTED_TARGETS:
        raise ValueError(
            f"Unsupported target {target_id!r}. Use one of {SUPPORTED_TARGETS}."
        )
    bundle = load_series(target_id)
    s = bundle.data.dropna().sort_index()
    if s.empty:
        raise ValueError(f"target {target_id!r} loaded empty")
    s.name = target_id
    return s


def forward_return(
    target: pd.Series,
    t: pd.Timestamp,
    horizon_months: int,
    *,
    annualize: bool = True,
) -> float | None:
    """Forward return on ``target`` from ``t`` over ``horizon_months``.

    Returns ``None`` if ``t + horizon_months`` falls past the target's
    last observation (the only way to look up the forward value would
    be to peek past the data — refused).

    The returned value is annualized geometric return when
    ``annualize=True`` (default): ``(1 + raw)**(12 / horizon_months) - 1``.
    For ``horizon_months == 12`` annualization is a no-op.
    """
    if horizon_months <= 0:
        raise ValueError(f"horizon_months must be positive, got {horizon_months}")
    target_end = target.index[-1]
    cutoff = pd.Timestamp(t) + pd.DateOffset(months=horizon_months)
    if cutoff > target_end:
        return None
    # Pick the value at or just after t (we have monthly cadence).
    # Use asof which returns the latest value <= t for both legs.
    p_t = target.asof(pd.Timestamp(t))
    p_tH = target.asof(cutoff)
    if pd.isna(p_t) or pd.isna(p_tH) or p_t == 0:
        return None
    raw = float(p_tH) / float(p_t) - 1.0
    if not annualize or horizon_months == 12:
        return raw
    return (1.0 + raw) ** (12.0 / horizon_months) - 1.0


def forward_return_series(
    target: pd.Series,
    horizon_months: int,
    *,
    annualize: bool = True,
) -> pd.Series:
    """Vectorized forward return: returns one value per t in the target's
    valid backward-looking window.

    The output series is indexed by ``t`` (the START of the forward
    window) and stops at the latest ``t`` for which ``t + horizon_months``
    fits within the target's range.
    """
    if horizon_months <= 0:
        raise ValueError(f"horizon_months must be positive, got {horizon_months}")
    target = target.dropna().sort_index()
    if target.empty:
        return pd.Series(dtype=float, name=f"{target.name}_fwd_{horizon_months}m_ann")
    target_end = target.index[-1]
    # Resample to monthly month-end last value to align all horizons cleanly.
    monthly = target.resample("ME").last().dropna()
    cutoff = monthly.index[-1] - pd.DateOffset(months=horizon_months)
    starts = monthly.index[monthly.index <= cutoff]
    if len(starts) == 0:
        return pd.Series(dtype=float, name=f"{target.name}_fwd_{horizon_months}m_ann")
    rows: list[float] = []
    valid_starts: list[pd.Timestamp] = []
    for t in starts:
        # Forward end: same calendar day + horizon_months. Use asof to
        # find the actual observation at or before that date.
        p_t = monthly.asof(t)
        p_tH = monthly.asof(t + pd.DateOffset(months=horizon_months))
        if pd.isna(p_t) or pd.isna(p_tH) or p_t == 0:
            continue
        if t + pd.DateOffset(months=horizon_months) > target_end:
            continue
        raw = float(p_tH) / float(p_t) - 1.0
        ret = raw if (not annualize or horizon_months == 12) else (
            (1.0 + raw) ** (12.0 / horizon_months) - 1.0
        )
        rows.append(ret)
        valid_starts.append(t)
    return pd.Series(rows, index=pd.DatetimeIndex(valid_starts),
                     name=f"{target.name}_fwd_{horizon_months}m_ann")


def align_indicator_to_target(
    indicator: pd.Series, target_dates: pd.DatetimeIndex,
) -> pd.Series:
    """Resample an indicator to month-end and reindex to target dates,
    using ``asof`` semantics (latest known value at each target date).

    Returns a series with the same index as ``target_dates``; values are
    NaN where the indicator has no observation at or before the target
    date. Caller is responsible for dropping NaN before regression.
    """
    if indicator.empty:
        return pd.Series(np.nan, index=target_dates, name=indicator.name)
    monthly = indicator.dropna().sort_index().resample("ME").last()
    out = pd.Series(np.nan, index=target_dates, name=indicator.name)
    for d in target_dates:
        v = monthly.asof(d)
        if pd.notna(v):
            out.loc[d] = float(v)
    return out


__all__ = [
    "SUPPORTED_TARGETS",
    "align_indicator_to_target",
    "forward_return",
    "forward_return_series",
    "load_target",
]
