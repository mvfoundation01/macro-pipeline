"""Layer 5-F — DMS (Dimson-Marsh-Staunton) survivorship adjustment.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.F.0 (metadata) +
§5.F.1 (public API; lines 1787-1819) + §5.F.2 (pre-flight contract;
DMS literature anchor + Standing Order #4 AST audit) + §5.F.3
(methodology rigor) + §5.F.4 (Q6 LOCKED: horizon-conditional bps) +
§5.F.5 (five tests; three NEG / two POS = 60% NEG) + §5.F.6 (Gate 25
sub-criterion 25.1) + §5.F.7 (proof contract; eight items).

Populates the ``dms_adjustment_bps`` slot on ``ScoredObservation``
(added at L5-RM-4; see ``scoring/scored_observation.py:103``;
slot semantics: ``float = 0.0`` default — negative bps for 5Y/10Y;
``0.0`` for 1Y/3Y).

DMS literature anchor
---------------------
**Dimson, Marsh, Staunton** (2002) *Triumph of the Optimists: 101 Years
of Global Investment Returns*. Princeton University Press. Table 1.2 /
1.3 cross-country survivorship correction. 2020 update: *Credit Suisse
Global Investment Returns Yearbook 2020*. Post-2023 rebranded as *UBS
Global Investment Returns Yearbook*. The US-only sample over
1900-present overstates the global true equity return by 100-200 bps
annualized due to survivorship bias (the US economy survived two
world wars + 2008 + 2020 without permanent destruction of the equity
market; many counterpart economies did not).

**Source memo** (L5b-KICK-7, tag ``l5b-kick-7-accept``, 2026-05-15):
``DMS_SOURCE_MEMO.md`` at the worktree root provides the full
derivation chain for the Q6-locked basis-point values below — edition
citation, empirical US-vs-global premium gap, horizon-specific
midpoint reasoning, sensitivity band justification, annual refresh
protocol, and the §4 honest disclaimer explicitly acknowledging that
the specific -125/-175 bps values are institutional judgment within
the empirically-supported DMS range rather than direct-table-derived
precision. Closes Codex 5.5 + ChatGPT 5.5 IMPORTANT reviewer flags on
DMS source-anchoring transparency via the AP-AUTH-53 seventh-instance
documentation-primary variant pattern. Gate 25.1.7 enforces memo
presence + section-header structure at validator time.

Method (spec §5.F.3)
--------------------
* Constant horizon-conditional bps subtraction per Q6 lock (spec §5.F.4):
    - ``1Y / 3Y``: ``0.0`` bps (no adjustment; sensitivity band collapses)
    - ``5Y``:      ``-125.0`` bps central (midpoint of DMS [-100, -150] range)
    - ``10Y``:     ``-175.0`` bps central (midpoint of DMS [-150, -200] range)
* Sensitivity band: ``±50.0`` bps around the central per Q6 lock
  (reported via the lower/upper return values for 5Y/10Y; collapsed
  for 1Y/3Y).

Q6 LOCKED VALUES (per spec §5.F.4)
----------------------------------
These five-element / scalar literals are spec-mandated constants
anchored to DMS literature; they are **NOT magic numbers** in the
AP-AUTH-52 sense (no derivation from ``base + delta`` arithmetic).
Cite spec §5.F.4 line in commit message + this module docstring.

Standing Order #4 contract — no fitting / no leakage
----------------------------------------------------
``apply_dms_adjustment`` is a pure constant-arithmetic function:
horizon lookup followed by scalar addition. No estimator
instantiation, no fitting calls, no train-vs-test partitioning, no
walk-forward CV. Verified at Gate 25 validator via
``inspect.getsource`` substring audit (closes R4 mitigation per
pre-flight 2026-05-13; the docstring carefully avoids the literal
forbidden substrings per L5-C false-positive lesson).
"""
from __future__ import annotations


# Spec §5.F.1 Q6-locked horizon-conditional bps central per spec §5.F.4.
# Negative bps = downward survivorship adjustment. 1Y/3Y receive zero
# (Q6 lock: short-horizon DMS correction is statistically indistinguishable
# from zero and operationally disabled).
DMS_BPS_CENTRAL: dict[str, float] = {
    "1Y": 0.0,
    "3Y": 0.0,
    "5Y": -125.0,
    "10Y": -175.0,
}

# Spec §5.F.1 Q6-locked sensitivity band: ±50 bps around the central per
# spec §5.F.4. Applied symmetrically as lower = central - 50; upper =
# central + 50 for 5Y/10Y horizons (collapsed for 1Y/3Y).
DMS_BPS_SENSITIVITY: float = 50.0

# Horizons where DMS adjustment is applied (sensitivity band non-collapsed).
_ADJUSTED_HORIZONS: frozenset[str] = frozenset({"5Y", "10Y"})

# Horizons where adjustment is 0.0 (band collapses to scalar).
_UNADJUSTED_HORIZONS: frozenset[str] = frozenset({"1Y", "3Y"})


def apply_dms_adjustment(
    raw_forecast_real_annualized_bps: float,
    horizon: str,
) -> tuple[float, float, float]:
    """Apply Q6-locked DMS survivorship bps adjustment per spec §5.F.1.

    Parameters
    ----------
    raw_forecast_real_annualized_bps
        Raw real annualised forecast in basis points (e.g.,
        ``650.0`` for 6.5% real). Caller is responsible for unit
        conversion (return-to-bps).
    horizon
        Horizon label; one of ``{"1Y", "3Y", "5Y", "10Y"}``.

    Returns
    -------
    tuple[float, float, float]
        ``(adjusted_central, adjusted_lower, adjusted_upper)`` in bps.
        For ``1Y / 3Y``: all three values equal (sensitivity band
        collapsed; no adjustment per Q6 lock). For ``5Y / 10Y``:
        ``central = raw + DMS_BPS_CENTRAL[horizon]``;
        ``lower = central - DMS_BPS_SENSITIVITY``;
        ``upper = central + DMS_BPS_SENSITIVITY``.

    Raises
    ------
    ValueError
        If ``horizon`` not in ``DMS_BPS_CENTRAL.keys()`` (spec §5.F.5
        test #4).
    """
    if horizon not in DMS_BPS_CENTRAL:
        raise ValueError(
            f"horizon {horizon!r} not in {sorted(DMS_BPS_CENTRAL.keys())}; "
            "DMS adjustment supports the spec §3.3 horizon set only"
        )

    central_bps = DMS_BPS_CENTRAL[horizon]
    adjusted_central = raw_forecast_real_annualized_bps + central_bps

    if horizon in _UNADJUSTED_HORIZONS:
        # Spec §5.F.1: 1Y/3Y sensitivity band collapses to central per Q6 lock.
        return adjusted_central, adjusted_central, adjusted_central

    # Spec §5.F.1: 5Y/10Y sensitivity band ±DMS_BPS_SENSITIVITY around central.
    adjusted_lower = adjusted_central - DMS_BPS_SENSITIVITY
    adjusted_upper = adjusted_central + DMS_BPS_SENSITIVITY
    return adjusted_central, adjusted_lower, adjusted_upper


__all__ = [
    "DMS_BPS_CENTRAL",
    "DMS_BPS_SENSITIVITY",
    "apply_dms_adjustment",
]
