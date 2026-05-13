"""Layer 5-G — Bayesian shrinkage toward 6.5% real prior.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.G.0 (metadata) +
§5.G.1 (public API; lines 1893-1971) + §5.G.2 (pre-flight contract +
Standing Order #4 AST audit) + §5.G.3 (methodology rigor v2 per S-4
k_h backsolve; closes ChatGPT v1 E.3 / L5-RISK-3) + §5.G.4 (Q7 LOCKED:
horizon-dependent + sample-size-adaptive k/(k+n); US-specific 6.5%
primary + global 4.5% robustness) + §5.G.5 (eight tests v2; five NEG /
three POS = 63% NEG; supersedes stale §5.G.0 metadata "+6" anchor per
Strategic D-G-1) + §5.G.6 (Gate 25 composite seal — both 25.1 (L5-F)
+ 25.2 (this sub-phase) PASS) + §5.G.7 (proof contract; ten items).

Populates the ``bayesian_shrinkage_weight`` slot on ``ScoredObservation``
(added at L5-RM-4; see ``scoring/scored_observation.py:114`` with
validator at line 194 enforcing ``0.0 <= weight <= 1.0``).

DMS prior literature anchor
---------------------------
**Dimson, Marsh, Staunton** (2002) *Triumph of the Optimists: 101 Years
of Global Investment Returns*. Princeton University Press. Long-run
real annualized US equity return ~6.5% over 1900-present. 2020 update:
*Credit Suisse Global Investment Returns Yearbook 2020*. Master Prompt
v3.1 §13 (10-year forecastability section) cites the 6.5% prior as
the long-run anchor for Bayesian shrinkage. Global cross-country mean
~4.5% (DMS Table 1.2 / 1.3) serves as the robustness-check alternative
prior.

Method (spec §5.G.1 + §5.G.3 v2 per S-4)
----------------------------------------
* **Posterior mean (closed-form Beta-Binomial conjugate analog)**:
  ``shrunken = w × prior + (1 − w) × raw_forecast`` where
  ``w = k_h / (k_h + n_eff_nonoverlap)``.
* **K_HORIZON v2 backsolve per S-4** (closes ChatGPT v1 §E.3 /
  L5-RISK-3): v1 used ``k = horizon_months × 15`` which combined with
  Fed-era ``n_eff_nonoverlap`` produced weights wildly inconsistent
  with the stated reference targets (1Y/3Y/5Y/10Y → 61/93/98/99%
  instead of intended 5/15/30/50%). v2 backsolves ``k_h`` from
  ``W_REF_TARGET × N_REF_NONOVERLAP`` via the formula:

      k_h = (w_ref / (1 - w_ref)) × n_ref

  yielding mathematically consistent constants (5.9 / 6.7 / 9.4 / 11.0)
  that reproduce W_REF_TARGET exactly at N_REF_NONOVERLAP (test #7
  verifies within ±2pp tolerance per spec §5.G.5).
* **Q7-locked constants** (per spec §5.G.4): horizon-dependent +
  sample-size-adaptive; US-specific 6.5% primary + global 4.5%
  robustness check.

Public API
----------
``DMS_PRIOR_REAL_ANNUALIZED_US``           Q7 primary anchor: 6.5% real
``DMS_PRIOR_REAL_ANNUALIZED_GLOBAL``       Q7 robustness alt: 4.5% real
``N_REF_NONOVERLAP``                       Fed-era non-overlap counts
``W_REF_TARGET``                           Reference shrinkage weights
``K_HORIZON``                              v2-backsolved k_h per horizon
``NOMINAL_SHRINKAGE_WEIGHTS_AT_REFERENCE_N`` documentation alias for W_REF_TARGET
``compute_shrinkage_weight``               k/(k+n) closed-form
``apply_shrinkage``                        Posterior mean + weight

Standing Order #4 contract — no fitting / no leakage
----------------------------------------------------
This module is pure closed-form conjugate-mean arithmetic: constant
lookup + scalar multiply-add. No estimator instantiation, no fitting
calls, no train-vs-test partitioning, no walk-forward CV. Verified at
Gate 25.2 validator via ``inspect.getsource`` substring audit (closes
R-leakage mitigation per pre-flight 2026-05-13; docstring carefully
avoids the literal forbidden substrings per L5-C false-positive
lesson).
"""
from __future__ import annotations


# Spec §5.G.1 Q7-locked primary anchor: US-specific DMS long-run real
# annualized return (Master Prompt v3.1 §13 reference).
DMS_PRIOR_REAL_ANNUALIZED_US: float = 0.065        # 6.5%

# Spec §5.G.1 Q7-locked robustness anchor: global cross-country mean.
DMS_PRIOR_REAL_ANNUALIZED_GLOBAL: float = 0.045    # 4.5%

# Spec §5.G.1: Fed-era (1913-2025 ≈ 113 years monthly) non-overlapping
# window counts per horizon. Used as the reference cutpoint for the
# K_HORIZON v2 backsolve.
N_REF_NONOVERLAP: dict[str, int] = {
    "1Y": 113,
    "3Y": 38,
    "5Y": 22,
    "10Y": 11,
}

# Spec §5.G.1 Q7-locked reference shrinkage weights at canonical Fed-era
# n_eff per horizon. K_HORIZON is backsolved from these targets.
W_REF_TARGET: dict[str, float] = {
    "1Y": 0.05,
    "3Y": 0.15,
    "5Y": 0.30,
    "10Y": 0.50,
}

# Spec §5.G.1 v2 BACKSOLVED k_h per S-4 (closes ChatGPT v1 §E.3 /
# L5-RISK-3). Formula: k_h = (w_ref / (1 - w_ref)) × n_ref. Verified
# arithmetic:
#   1Y:  0.05 / 0.95 × 113 = 5.947… → 5.9
#   3Y:  0.15 / 0.85 × 38  = 6.706… → 6.7
#   5Y:  0.30 / 0.70 × 22  = 9.429… → 9.4
#   10Y: 0.50 / 0.50 × 11  = 11.0   → 11.0
# Round to one decimal per spec literal. Test #7 verifies the resulting
# weights match W_REF_TARGET within ±2pp at N_REF_NONOVERLAP.
# NOT magic numbers per AP-AUTH-52 — backsolve derivation cited above.
K_HORIZON: dict[str, float] = {
    "1Y": 5.9,
    "3Y": 6.7,
    "5Y": 9.4,
    "10Y": 11.0,
}

# Spec §5.G.1: documentation alias for W_REF_TARGET (the two are equal
# by construction; preserved for spec proof item 1 import surface).
NOMINAL_SHRINKAGE_WEIGHTS_AT_REFERENCE_N: dict[str, float] = {
    "1Y": 0.05,
    "3Y": 0.15,
    "5Y": 0.30,
    "10Y": 0.50,
}


def compute_shrinkage_weight(
    n_eff_nonoverlap: int,
    horizon: str,
) -> float:
    """k/(k+n) Bayesian shrinkage weight per Q7 lock (spec §5.G.1).

    Parameters
    ----------
    n_eff_nonoverlap
        Effective non-overlapping sample count (``n_obs //
        horizon_months``). Caller computes from upstream walk-forward
        CV fold counts (e.g., ``RidgeFitResult.n_eff_nonoverlap_train``
        from L5-B Task B1).
    horizon
        Horizon label; one of ``{"1Y", "3Y", "5Y", "10Y"}``.

    Returns
    -------
    float
        Shrinkage weight ``w ∈ [0, 1]``. ``w → 0`` as ``n_eff → ∞``
        (asymptotic unbiasedness; test #4). ``w → 1`` as ``n_eff → 0``
        (maximum prior weight). At reference ``n_eff = N_REF_NONOVERLAP``,
        ``w`` matches ``W_REF_TARGET`` within ±2pp (test #7).

    Raises
    ------
    ValueError
        If ``horizon`` not in ``K_HORIZON.keys()`` (test #6) or
        ``n_eff_nonoverlap < 0`` (test #5).
    """
    if horizon not in K_HORIZON:
        raise ValueError(
            f"horizon {horizon!r} not in {sorted(K_HORIZON.keys())}; "
            "Bayesian shrinkage supports the spec §3.3 horizon set only"
        )
    if n_eff_nonoverlap < 0:
        raise ValueError(
            f"n_eff_nonoverlap must be >= 0, got {n_eff_nonoverlap}"
        )
    k = K_HORIZON[horizon]
    return k / (k + n_eff_nonoverlap)


def apply_shrinkage(
    raw_forecast_real_annualized: float,
    n_eff_nonoverlap: int,
    horizon: str,
    *,
    use_global_prior: bool = False,
) -> tuple[float, float]:
    """Apply Q7-locked Bayesian shrinkage per spec §5.G.1.

    Computes posterior mean as a convex combination of the prior anchor
    and the raw forecast, weighted by the k/(k+n) shrinkage weight per
    horizon.

    Parameters
    ----------
    raw_forecast_real_annualized
        Raw real annualised forecast as a fraction (e.g., ``0.065`` for
        6.5%). Caller is responsible for unit conversion (bps-to-fraction
        if upstream pipeline reports bps; L5-F's
        ``apply_dms_adjustment`` works in bps, so the unit translation
        happens at the L5-H caller).
    n_eff_nonoverlap
        Effective non-overlapping sample count.
    horizon
        Horizon label; one of ``{"1Y", "3Y", "5Y", "10Y"}``.

    Keyword-only
    ------------
    use_global_prior
        If ``True``, anchor against ``DMS_PRIOR_REAL_ANNUALIZED_GLOBAL``
        (4.5% global) for robustness check per spec §5.G.4 Q7 lock.
        Default ``False`` (US-specific 6.5% primary).

    Returns
    -------
    tuple[float, float]
        ``(shrunken_central, shrinkage_weight)``. ``shrunken_central``
        is in the same unit as ``raw_forecast_real_annualized``
        (fractional real annualised). ``shrinkage_weight`` ∈ [0, 1]
        matches ``compute_shrinkage_weight(n_eff_nonoverlap, horizon)``.

    Raises
    ------
    ValueError
        Forwarded from ``compute_shrinkage_weight`` on invalid horizon
        or negative n_eff.
    """
    prior = (
        DMS_PRIOR_REAL_ANNUALIZED_GLOBAL
        if use_global_prior
        else DMS_PRIOR_REAL_ANNUALIZED_US
    )
    w = compute_shrinkage_weight(n_eff_nonoverlap, horizon)
    shrunken = w * prior + (1.0 - w) * raw_forecast_real_annualized
    return shrunken, w


__all__ = [
    "DMS_PRIOR_REAL_ANNUALIZED_GLOBAL",
    "DMS_PRIOR_REAL_ANNUALIZED_US",
    "K_HORIZON",
    "NOMINAL_SHRINKAGE_WEIGHTS_AT_REFERENCE_N",
    "N_REF_NONOVERLAP",
    "W_REF_TARGET",
    "apply_shrinkage",
    "compute_shrinkage_weight",
]
