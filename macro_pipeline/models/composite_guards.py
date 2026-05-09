"""Composite-builder guards for indicator misuse (Layer 1.5C.3 / 1.5C.4).

Two checks live here:

1. ``check_double_counting`` — warn if a CRPS / CDRS components list
   includes both ``PHILLY_LEI_PROXY`` (FRED ``USSLIND``) and one of its
   underlying inputs (T10Y3M, ISM data, IC4WSA). USSLIND is the Philly
   Fed STATE leading-index aggregate; its construction already weights
   the slope and the new-orders index, so a composite that uses both
   USSLIND and the slope double-counts the same signal (ChatGPT review
   2026-05-09 D1).

2. ``check_signal_type_compatibility`` — refuse / warn if a coincident
   indicator (Sahm Rule) is asked to participate in a leading-indicator
   composite (12M_recession_probability_composite,
   12M_leading_indicator). Sahm detects recession START, not the
   probability of recession in the next 12M (ChatGPT review D2 / D6).

The checks are **non-fatal by default** (they log a warning) so callers
can build experimental composites; pass ``raise_on_violation=True`` to
make Layer 5 fail closed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


# Indicators known to mechanically duplicate the slope or ISM blocks.
# Keys = the aggregate, values = the components it already contains.
_DOUBLE_COUNTING_GRAPH: dict[str, frozenset[str]] = {
    "PHILLY_LEI_PROXY": frozenset({
        "T10Y3M", "T10Y2Y",            # term-spread inputs
        "ISM_NEW_ORDERS", "NAPMNOI",   # ISM new orders inputs
        "IC4WSA",                      # initial claims input
    }),
}


# Indicators that are coincident, not 12M-leading.
_COINCIDENT_INDICATORS: frozenset[str] = frozenset({
    "SAHMREALTIME", "SAHM_RULE",
})

# Composite contexts that demand a 12M-leading signal type.
_LEADING_CONTEXTS: frozenset[str] = frozenset({
    "12M_recession_probability_composite",
    "12M_leading_indicator",
    "12M_leading_composite",
    "leading_12m_composite",
})


@dataclass(frozen=True)
class GuardViolation:
    rule: str
    indicator_id: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"[{self.rule}] {self.indicator_id}: {self.detail}"


def check_double_counting(
    components: list[str] | set[str],
    *,
    raise_on_violation: bool = False,
) -> list[GuardViolation]:
    """Check for mechanical double-counting in a CRPS / CDRS components list.

    Returns the list of violations (empty if clean). When
    ``raise_on_violation=True`` raises ``ValueError`` on any violation.
    """
    comp_set = set(components)
    violations: list[GuardViolation] = []
    for aggregate, contained in _DOUBLE_COUNTING_GRAPH.items():
        if aggregate not in comp_set:
            continue
        overlap = sorted(contained & comp_set)
        if overlap:
            v = GuardViolation(
                rule="double_counting",
                indicator_id=aggregate,
                detail=(
                    f"{aggregate} already aggregates {sorted(contained)}. "
                    f"Including it alongside {overlap} double-counts the "
                    f"same signal — drop one or de-correlate weights."
                ),
            )
            log.warning("%s", v)
            violations.append(v)

    if raise_on_violation and violations:
        raise ValueError(
            f"composite double-counting violations: "
            f"{[v.indicator_id for v in violations]}"
        )
    return violations


def check_signal_type_compatibility(
    indicator_id: str,
    context: str,
    *,
    raise_on_violation: bool = False,
) -> GuardViolation | None:
    """Refuse / warn if a coincident indicator is dropped into a leading
    composite. ``context`` is the canonical context tag (e.g.
    ``"12M_recession_probability_composite"``).

    Returns ``None`` on a clean call, the GuardViolation otherwise.
    """
    if indicator_id not in _COINCIDENT_INDICATORS:
        return None
    if context not in _LEADING_CONTEXTS:
        return None
    v = GuardViolation(
        rule="signal_type_mismatch",
        indicator_id=indicator_id,
        detail=(
            f"{indicator_id} is COINCIDENT (detects recession start). "
            f"Context {context!r} demands a 12M-leading signal — these "
            f"are conceptually different. See 1.5C.4 / ChatGPT 2026-05-09."
        ),
    )
    log.warning("%s", v)
    if raise_on_violation:
        raise ValueError(str(v))
    return v


__all__ = [
    "GuardViolation",
    "check_double_counting",
    "check_signal_type_compatibility",
]
