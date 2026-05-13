"""Shared notes-formatter helpers for ScoredObservation lineage.

Layer 5-RM-4 (L5-13 absorption): extracted from ``scoring/crps.py`` so that
CDRS (and any future scorer) shares the same PIT-lineage formatting
discipline. Eliminates code duplication and centralizes the lineage
contract that downstream consumers (L5-D, L5-F, audits) depend on.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 §5.RM-4.1.4 (lines 1013-1021).

Public API
----------
``format_pit_lineage_notes(loads)``
    The original CRPS helper (renamed from ``_format_pit_lineage_notes`` to
    drop the leading underscore now that it's a module-public shared
    function). Collects PIT-lineage notes from component ``IndicatorBundle``
    objects, dedups while preserving insertion order, and returns a list[str]
    suitable for the ``ScoredObservation.notes`` field.

``format_cdrs_v_t_lineage_notes(v_score, t_score)``
    NEW CDRS-specific helper. Emits one or two ``str`` notes encoding the V
    + T sub-score values that previously lived in
    ``ScoredObservation.metadata_extra["V_score"]`` /
    ``metadata_extra["T_score"]``. Per spec §5.RM-4.1.4 step 1, these
    uppercase ``V_*`` / ``T_*`` keys are migrated to ``notes`` at L5-RM-4
    (proof contract item 3 grep enforcement).
"""
from __future__ import annotations

from typing import Any


def format_pit_lineage_notes(loads: list[Any]) -> list[str]:
    """Layer 3.5D + L5-RM-4 (renamed from ``_format_pit_lineage_notes``):
    collect PIT-lineage notes from component ``IndicatorBundle`` objects,
    dedup while preserving insertion order, and return a list[str] suitable
    for the ``ScoredObservation.notes`` field.

    Migrates the pre-3.5D ``metadata_extra["pit_safe_basis_per_component"]``,
    ``metadata_extra["derived_confidence_cap_applied"]``, and
    ``metadata_extra["pit_construction_notes"]`` entries into a single
    ordered, deduped list.

    Per Decision Lock 3.5D-AM25: each non-empty source produces one note
    line; ``dict.fromkeys`` preserves order while removing equivalent strings.

    Parameters
    ----------
    loads
        List of `_ComponentLoad`-like objects each exposing:
          * ``name`` (str)
          * ``bundle`` with attributes ``pit_safe_basis``,
            ``derived_confidence_cap``, and ``notes``.

    Returns
    -------
    list[str]
        Deduplicated, order-preserved notes ready for ScoredObservation.notes.
    """
    notes: list[str] = []

    # 1. Per-component PIT basis (one summary line if any non-default)
    bases = {
        cl.name: getattr(cl.bundle, "pit_safe_basis", "n/a")
        for cl in loads
    }
    non_default = {
        name: basis
        for name, basis in bases.items()
        if basis not in ("n/a", "release_lag", "asof_truncation")
    }
    if non_default:
        notes.append(
            "PIT-safe basis per component: "
            + ", ".join(f"{name}={basis}" for name, basis in non_default.items())
        )

    # 2. Derived-cap summary (single line if any component carries a cap)
    derived_caps = [
        getattr(cl.bundle, "derived_confidence_cap", None) for cl in loads
    ]
    bound_caps = [c for c in derived_caps if c is not None]
    if bound_caps:
        notes.append(
            f"Derived confidence cap applied: MIN={min(bound_caps):.2f} "
            f"(from {sum(1 for c in derived_caps if c is not None)} component(s))"
        )

    # 3. Per-component construction notes (already strings)
    for cl in loads:
        for note in getattr(cl.bundle, "notes", []):
            if note:
                notes.append(note)

    # Dedup preserving order.
    return list(dict.fromkeys(notes))


def format_cdrs_v_t_lineage_notes(
    v_score: float, t_score: float,
) -> list[str]:
    """Format CDRS V + T sub-score lineage as notes (L5-RM-4 / L5-13 absorption).

    Spec ref: §5.RM-4.1.4 step 1 — migrate uppercase ``V_*`` / ``T_*`` keys
    from ``metadata_extra`` to ``notes``. Proof item 3 enforces that
    ``scoring/cdrs.py`` post-migration has 0 matches for
    ``metadata_extra["V_"`` and ``metadata_extra["T_"`` patterns.

    Returns one ordered list[str] for ScoredObservation.notes, mirroring the
    CRPS PIT-lineage discipline format.
    """
    return [
        f"CDRS lineage: V_score={v_score:.4f} (vulnerability stage)",
        f"CDRS lineage: T_score={t_score:.4f} (trigger stage)",
    ]


__all__ = [
    "format_cdrs_v_t_lineage_notes",
    "format_pit_lineage_notes",
]
