"""Layer 3.5B PIT contract audit utility.

Walks every series in ``FRED_SERIES_API`` and tabulates against
``VINTAGE_REQUIRED_SERIES`` membership and the ``pit_safe_by_construction``
flag, reporting any series that would currently raise
``PitContractViolationError`` if loaded in PIT mode.

Usage:

    python -m macro_pipeline.utils.pit_audit

CLI exits 0 with no mismatches; exits 1 when any series with
``vintage=True`` is neither in the materialised vintage panel nor flagged
``pit_safe_by_construction=True``.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from macro_pipeline.config import FRED_SERIES_API


@dataclass(frozen=True)
class PitAuditMismatch:
    series_id: str
    vintage_in_config: bool
    in_vintage_required: bool
    pit_safe_by_construction: bool
    reason: str


@dataclass
class PitAuditReport:
    series_with_needs_vintage_true: list[str] = field(default_factory=list)
    series_in_VINTAGE_REQUIRED_SERIES: list[str] = field(default_factory=list)
    series_with_pit_safe_by_construction_true: list[str] = field(default_factory=list)
    mismatches: list[PitAuditMismatch] = field(default_factory=list)

    @property
    def total_violations(self) -> int:
        return len(self.mismatches)


def audit_pit_contracts() -> PitAuditReport:
    """Inspect ``FRED_SERIES_API`` and ``VINTAGE_REQUIRED_SERIES`` and
    report any unflagged vintage series that would violate the PIT
    contract on load.
    """
    # Local import to avoid heavy fred-loader dependency just for audit.
    from macro_pipeline.loaders.fred_vintage_panel import VINTAGE_REQUIRED_SERIES

    vintage_required = set(VINTAGE_REQUIRED_SERIES)
    report = PitAuditReport()

    for sid, spec in FRED_SERIES_API.items():
        is_vintage = bool(spec.get("vintage", False))
        in_panel = sid in vintage_required
        is_construction = bool(spec.get("pit_safe_by_construction", False))

        if is_vintage:
            report.series_with_needs_vintage_true.append(sid)
        if in_panel:
            report.series_in_VINTAGE_REQUIRED_SERIES.append(sid)
        if is_construction:
            report.series_with_pit_safe_by_construction_true.append(sid)

        if is_vintage and not in_panel and not is_construction:
            report.mismatches.append(
                PitAuditMismatch(
                    series_id=sid,
                    vintage_in_config=is_vintage,
                    in_vintage_required=in_panel,
                    pit_safe_by_construction=is_construction,
                    reason=(
                        "vintage=True but neither in VINTAGE_REQUIRED_SERIES "
                        "nor pit_safe_by_construction=True. Would raise "
                        "PitContractViolationError on PIT load."
                    ),
                )
            )

    return report


def render_report(report: PitAuditReport) -> str:
    lines = [
        "=== PIT contract audit (Layer 3.5B) ===",
        f"Series with vintage=True: {len(report.series_with_needs_vintage_true)}",
        f"  In VINTAGE_REQUIRED_SERIES: {len(report.series_in_VINTAGE_REQUIRED_SERIES)}",
        f"  Flagged pit_safe_by_construction: {len(report.series_with_pit_safe_by_construction_true)}",
        f"Mismatches (would raise PitContractViolationError): "
        f"{report.total_violations}",
    ]
    if report.series_with_pit_safe_by_construction_true:
        lines.append("Option Z series:")
        for sid in report.series_with_pit_safe_by_construction_true:
            cap = FRED_SERIES_API[sid].get("derived_confidence_cap")
            lines.append(f"  - {sid} (derived_confidence_cap={cap})")
    if report.mismatches:
        lines.append("MISMATCHES:")
        for m in report.mismatches:
            lines.append(f"  - {m.series_id}: {m.reason}")
    else:
        lines.append("No mismatches. PIT contract intact.")
    return "\n".join(lines)


def main() -> int:
    report = audit_pit_contracts()
    print(render_report(report))
    return 0 if report.total_violations == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "PitAuditMismatch",
    "PitAuditReport",
    "audit_pit_contracts",
    "main",
    "render_report",
]
