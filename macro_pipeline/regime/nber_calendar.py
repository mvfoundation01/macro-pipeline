"""NBER announcement calendar (Layer 3.5C).

Replaces the 180-day approximation in ``regime/nber_extract.py`` with
authoritative announcement dates sourced from the NBER Business Cycle
Dating Committee announcements page:

    https://www.nber.org/research/business-cycle-dating/business-cycle-dating-committee-announcements

The CSV at ``data/nber_announcement_calendar.csv`` (committed to the
repo) carries one row per cycle: peak_date / peak_announcement_date /
trough_date / trough_announcement_date / source_url / notes.

Pre-1978 cycles are explicitly NOT included; per Decision Lock 3.5C-D1
(``NBER_PRE_1978_POLICY = "training_only"``) the inference path
fails-closed for as_of < 1978-01 in real-time mode.

Spec: ``LAYER_3_5_BUILD_SPEC.md`` §5.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from macro_pipeline.config import DEFAULT_NBER_CALENDAR_PATH
from macro_pipeline.regime.exceptions import (
    NberCalendarLoadError,
    NberCycleNotFoundError,
)

# The CSV defines pre-1978 to be EXCLUDED. The policy boundary lives in
# config (NBER_PRE_1978_POLICY) but the date threshold is anchored here
# for the calendar's own purposes.
NBER_CALENDAR_BOUNDARY = pd.Period("1978-01", freq="M")

REQUIRED_CSV_COLUMNS = (
    "peak_date",
    "peak_announcement_date",
    "trough_date",
    "trough_announcement_date",
    "source_url",
    "notes",
)


@dataclass(frozen=True)
class NberCycle:
    """One NBER business cycle: peak/trough dates + announcement dates.

    All four date fields are monthly-precision (``pd.Period``) for
    peak/trough dates and daily-precision (``pd.Timestamp``) for
    announcement dates. Announcement dates are unambiguous — NBER
    publishes a press release on a specific calendar day.
    """

    peak_date: pd.Period
    peak_announcement_date: pd.Timestamp
    trough_date: pd.Period
    trough_announcement_date: pd.Timestamp
    source_url: str = ""
    notes: str = ""


@dataclass(frozen=True)
class LastKnownLabel:
    """Result of ``NberCalendarLoader.last_known_label(as_of)``.

    Carries the most recent turning point whose announcement_date <=
    as_of, plus the implied current regime.
    """

    regime: Literal["expansion", "recession"]
    turning_point_date: pd.Period
    turning_point_kind: Literal["peak", "trough"]
    announcement_date: pd.Timestamp


class NberCalendarLoader:
    """Reads the NBER announcement-date CSV at construction time and
    serves announcement-aware lookups.

    Cached at instance scope; re-instantiate to pick up CSV edits during
    a single Python process (rare; see Decision Lock 3.5C-D3 — manual
    quarterly update cadence).
    """

    def __init__(self, csv_path: Path | str | None = None) -> None:
        path = Path(csv_path) if csv_path is not None else DEFAULT_NBER_CALENDAR_PATH
        self._csv_path = path
        self._cycles: list[NberCycle] = self._load(path)

    # ----- public API ----------------------------------------------------
    @property
    def cycles(self) -> list[NberCycle]:
        return list(self._cycles)

    @property
    def csv_path(self) -> Path:
        return self._csv_path

    def is_post_1978(self, date: pd.Period | pd.Timestamp | str) -> bool:
        """True iff ``date`` is on/after 1978-01."""
        period = self._coerce_period(date)
        return period >= NBER_CALENDAR_BOUNDARY

    def get_announcement_date(
        self, turning_point: pd.Period | str, kind: Literal["peak", "trough"]
    ) -> pd.Timestamp:
        """Return the announcement date for the given turning point.

        Raises ``NberCycleNotFoundError`` if the turning point is not in
        the calendar (pre-1978 OR an unrecorded cycle).
        """
        period = self._coerce_period(turning_point)
        for c in self._cycles:
            if kind == "peak" and c.peak_date == period:
                return c.peak_announcement_date
            if kind == "trough" and c.trough_date == period:
                return c.trough_announcement_date
        raise NberCycleNotFoundError(
            f"No {kind} cycle found for {period} in NBER calendar "
            f"({self._csv_path}). Calendar covers 1978+ only."
        )

    def label_visible_at(
        self,
        query_date: pd.Period | pd.Timestamp | str,
        as_of: pd.Timestamp | str,
    ) -> bool:
        """True iff the NBER label for ``query_date`` was publicly
        available by ``as_of`` — i.e., either the most recent turning
        point at or before ``query_date`` had been announced by
        ``as_of``, OR ``query_date`` is on/after 1978-01 and is between
        two turning points already announced by ``as_of``.

        For pre-1978 query_date, always False (calendar doesn't cover).
        """
        qd_period = self._coerce_period(query_date)
        if qd_period < NBER_CALENDAR_BOUNDARY:
            return False
        as_of_ts = pd.Timestamp(as_of)
        try:
            self._last_announced_turning_point(qd_period, as_of_ts)
            return True
        except NberCycleNotFoundError:
            return False

    def last_known_label(
        self, as_of: pd.Timestamp | str
    ) -> LastKnownLabel:
        """Return the most recent turning point announced by ``as_of``,
        plus the regime implied by it.

        The implied regime applies from the month AFTER the turning
        point onward (NBER convention: peak month is last expansion
        month; trough month is last recession month).

        Raises ``NberCycleNotFoundError`` when no turning point has
        been announced by ``as_of`` (e.g., as_of < 1980-06-03 — before
        even the first announcement in the calendar).
        """
        as_of_ts = pd.Timestamp(as_of)
        candidates: list[tuple[pd.Period, str, pd.Timestamp]] = []
        for c in self._cycles:
            if c.peak_announcement_date <= as_of_ts:
                candidates.append((c.peak_date, "peak", c.peak_announcement_date))
            if c.trough_announcement_date <= as_of_ts:
                candidates.append((c.trough_date, "trough", c.trough_announcement_date))
        if not candidates:
            raise NberCycleNotFoundError(
                f"No NBER turning point has been announced by as_of="
                f"{as_of_ts.date()}. Earliest announcement in calendar "
                "is 1980-06-03. Use training mode (is_real_time=False) "
                "for pre-1978 inference."
            )
        # Sort by turning_point_date ASC; pick the most recent.
        candidates.sort(key=lambda x: x[0])
        last_tp_period, last_kind, last_announce = candidates[-1]
        # NBER convention: post-peak → recession; post-trough → expansion.
        regime: Literal["expansion", "recession"] = (
            "recession" if last_kind == "peak" else "expansion"
        )
        return LastKnownLabel(
            regime=regime,
            turning_point_date=last_tp_period,
            turning_point_kind=last_kind,  # type: ignore[arg-type]
            announcement_date=last_announce,
        )

    def state_at(
        self,
        query_date: pd.Period | pd.Timestamp | str,
        as_of: pd.Timestamp | str,
    ) -> Literal["expansion", "recession"]:
        """Return the NBER state at ``query_date`` as known on ``as_of``.

        Algorithm:
          1. Build the list of turning points whose announcement_date
             <= as_of, sorted by turning_point_date.
          2. Find the most recent turning point with turning_point_date
             <= query_date (in monthly precision).
          3. Apply NBER convention:
             - peak → recession from the next month onward
             - trough → expansion from the next month onward
          4. If query_date is BEFORE the earliest announced turning
             point, raise ``NberCycleNotFoundError``.
        """
        qd_period = self._coerce_period(query_date)
        as_of_ts = pd.Timestamp(as_of)
        return self._last_announced_turning_point(qd_period, as_of_ts).regime

    # ----- internals -----------------------------------------------------
    def _last_announced_turning_point(
        self, query_period: pd.Period, as_of_ts: pd.Timestamp
    ) -> LastKnownLabel:
        announced: list[tuple[pd.Period, str, pd.Timestamp]] = []
        for c in self._cycles:
            if c.peak_announcement_date <= as_of_ts:
                announced.append((c.peak_date, "peak", c.peak_announcement_date))
            if c.trough_announcement_date <= as_of_ts:
                announced.append((c.trough_date, "trough", c.trough_announcement_date))
        # Filter to those <= query_period
        relevant = [t for t in announced if t[0] <= query_period]
        if not relevant:
            raise NberCycleNotFoundError(
                f"No NBER turning point at or before {query_period} has "
                f"been announced by as_of={as_of_ts.date()}. Calendar "
                "begins 1980-01 (announced 1980-06-03)."
            )
        relevant.sort(key=lambda x: x[0])
        tp_period, kind, announce = relevant[-1]
        regime: Literal["expansion", "recession"] = (
            "recession" if kind == "peak" else "expansion"
        )
        return LastKnownLabel(
            regime=regime,
            turning_point_date=tp_period,
            turning_point_kind=kind,  # type: ignore[arg-type]
            announcement_date=announce,
        )

    @staticmethod
    def _coerce_period(value: pd.Period | pd.Timestamp | str) -> pd.Period:
        if isinstance(value, pd.Period):
            return value if value.freqstr == "M" else value.asfreq("M")
        ts = pd.Timestamp(value)
        return ts.to_period("M")

    def _load(self, path: Path) -> list[NberCycle]:
        if not path.exists():
            raise NberCalendarLoadError(
                f"NBER calendar CSV not found at {path}. Layer 3.5C "
                "requires this file to be committed to the repo."
            )
        cycles: list[NberCycle] = []
        try:
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames is None or not all(
                    col in reader.fieldnames for col in REQUIRED_CSV_COLUMNS
                ):
                    raise NberCalendarLoadError(
                        f"NBER calendar CSV {path} missing required columns. "
                        f"Required: {REQUIRED_CSV_COLUMNS}; found: "
                        f"{reader.fieldnames}"
                    )
                for row_no, row in enumerate(reader, start=2):
                    try:
                        cycles.append(self._parse_row(row))
                    except (ValueError, KeyError) as exc:
                        raise NberCalendarLoadError(
                            f"NBER calendar CSV {path} row {row_no}: {exc}"
                        ) from exc
        except OSError as exc:
            raise NberCalendarLoadError(
                f"Failed to read NBER calendar CSV {path}: {exc}"
            ) from exc

        if not cycles:
            raise NberCalendarLoadError(
                f"NBER calendar CSV {path} parsed but contains 0 cycles. "
                "Per spec §5.6 there should be ≥6 post-1978 cycles."
            )
        # Invariant: announcement_date strictly after turning_point_date.
        for c in cycles:
            peak_ts = c.peak_date.to_timestamp()
            trough_ts = c.trough_date.to_timestamp()
            if c.peak_announcement_date <= peak_ts:
                raise NberCalendarLoadError(
                    f"Negative lag: {c.peak_date} peak announcement "
                    f"{c.peak_announcement_date.date()} not strictly after "
                    f"peak month."
                )
            if c.trough_announcement_date <= trough_ts:
                raise NberCalendarLoadError(
                    f"Negative lag: {c.trough_date} trough announcement "
                    f"{c.trough_announcement_date.date()} not strictly after "
                    f"trough month."
                )
        return cycles

    @staticmethod
    def _parse_row(row: dict) -> NberCycle:
        return NberCycle(
            peak_date=pd.Period(row["peak_date"], freq="M"),
            peak_announcement_date=pd.Timestamp(row["peak_announcement_date"]),
            trough_date=pd.Period(row["trough_date"], freq="M"),
            trough_announcement_date=pd.Timestamp(row["trough_announcement_date"]),
            source_url=row.get("source_url", "").strip(),
            notes=row.get("notes", "").strip(),
        )


__all__ = [
    "NBER_CALENDAR_BOUNDARY",
    "REQUIRED_CSV_COLUMNS",
    "LastKnownLabel",
    "NberCalendarLoader",
    "NberCycle",
]
