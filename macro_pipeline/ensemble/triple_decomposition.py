"""TripleDecomposition dataclass for L6 ensemble aggregation (L6-B).

Per Strategic L6-B inline spec (Batch 1 of L6 sprint, 2026-05-15).
Implements Vision v2.0 §4 Triple Probability Decomposition (BINDING
everywhere) + Pipeline Guide §8.2 template.

Three numerical fields with binding constraint name (Vision §4):

  probability  — Objective Bayesian posterior on outcome   [0.0, 1.0]
  confidence   — Meta-uncertainty about probability estimate [0.0, 1.0]
  conviction   — Position-sizing weight                    [1.0, 10.0]

Defense-in-depth confidence cap (Standing Order #9 + L5b-F F-H2)
----------------------------------------------------------------
``__post_init__`` enforces a 10Y confidence cap as the FIRST LAYER of
defense-in-depth. The standalone forecast-time helper
``enforce_confidence_caps`` (L6-D, ``macro_pipeline.ensemble.ood_and_caps``)
provides the SECOND LAYER. Both layers raise the same
``ConfidenceCapViolation`` exception (reused from L1.7-B
``macro_pipeline.manual_input.validation``); construction-time + forecast-
time caps share one exception class for unified caller handling.

This is the 2nd INSTANCE of the defense-in-depth pattern; the 1st was
L1.7-B value-level + L1.7-D forecast-time cap pair. Per AP-AUTH-46
gratuitous-codification guard, the pattern reaches the second-instance
threshold at L6-D; codification scheduled at the L6-H sprint
retrospective (AP-AUTH-56 candidate).

Naming convention (Strategic PD11)
----------------------------------
English field names (``probability`` / ``confidence`` / ``conviction``)
not Vietnamese (``xác_suất`` / ``tin_cậy`` / ``tin_chắc``). Vietnamese
appears in user-facing output via Standing Order #1 conviction reporting,
not in code-level field names.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from macro_pipeline.manual_input.validation import ConfidenceCapViolation

# Range bounds (Strategic PD2/PD3/PD4 + Vision §4).
PROBABILITY_MIN = 0.0
PROBABILITY_MAX = 1.0
CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 1.0
CONVICTION_MIN = 1.0
CONVICTION_MAX = 10.0

# Confidence cap thresholds (Standing Order #9 + Vision §10 + L5b-F F-H2).
# Mirror constants live in L1.7-B/D and L6-D; the duplicate here keeps the
# dataclass module self-contained at import time.
CONFIDENCE_CAP_10Y_NON_STRATIFIED = 0.70
CONFIDENCE_CAP_10Y_REGIME_STRATIFIED = 0.55

# Supported horizons per Vision §1 + spec §3.3 (1Y/3Y/5Y/10Y).
SUPPORTED_HORIZONS = frozenset({1, 3, 5, 10})


@dataclass(frozen=True)
class TripleDecomposition:
    """Triple Probability Decomposition per Vision v2.0 §4 (BINDING).

    Three independent concepts; never conflate:

      probability  — numeric Bayesian posterior in [0, 1]
      confidence   — meta-uncertainty about that posterior in [0, 1]
      conviction   — position-sizing weight in [1, 10]

    Vision §4 critical rule: conviction CAN BE LOWER THAN confidence
    when risk/reward asymmetry is poor. The two scales are independent.

    Fields
    ------
    probability             [0, 1] objective posterior
    confidence              [0, 1] meta-uncertainty / Confidence Score
    conviction              [1, 10] position-sizing weight
    horizon                 supported horizon in {1, 3, 5, 10}
    regime_stratified       if True applies the 55% regime-stratified cap
                            at 10Y; else the 70% non-stratified cap
    binding_constraint      Vision §4 BINDING-with-name slot (named-
                            constraint string accompanying the conviction
                            number)

    Invariants enforced by ``__post_init__``
    ----------------------------------------
      1. probability in [0, 1]
      2. confidence in [0, 1]
      3. conviction in [1, 10]
      4. horizon in SUPPORTED_HORIZONS
      5. (horizon == 10) confidence cap (defense-in-depth 1st layer):
         non-stratified cap 0.70; regime-stratified cap 0.55.

    Raises
    ------
    ValueError
        Invariants 1-4 (range / horizon).
    ConfidenceCapViolation
        Invariant 5 (10Y cap). Reused from L1.7-B
        ``macro_pipeline.manual_input.validation`` per defense-in-depth
        single-exception-class convention.
    """

    probability: float
    confidence: float
    conviction: float
    horizon: int
    regime_stratified: bool = False
    binding_constraint: Optional[str] = None

    def __post_init__(self) -> None:
        # L6-I D1 — finite checks BEFORE range checks (explicit NaN/inf
        # rejection with clear error messages; NaN bypasses range via
        # `NaN <= x` always False, so range check would still raise but
        # with a misleading "outside [0.0, 1.0]" message).
        for field_name, value in (
            ("probability", self.probability),
            ("confidence", self.confidence),
            ("conviction", self.conviction),
        ):
            if not math.isfinite(value):
                raise ValueError(
                    f"{field_name} must be finite; got {value!r}"
                )
        # Invariant 1 — probability bounds.
        if not (PROBABILITY_MIN <= self.probability <= PROBABILITY_MAX):
            raise ValueError(
                f"probability {self.probability} outside "
                f"[{PROBABILITY_MIN}, {PROBABILITY_MAX}]"
            )
        # Invariant 2 — confidence bounds.
        if not (CONFIDENCE_MIN <= self.confidence <= CONFIDENCE_MAX):
            raise ValueError(
                f"confidence {self.confidence} outside "
                f"[{CONFIDENCE_MIN}, {CONFIDENCE_MAX}]"
            )
        # Invariant 3 — conviction bounds.
        if not (CONVICTION_MIN <= self.conviction <= CONVICTION_MAX):
            raise ValueError(
                f"conviction {self.conviction} outside "
                f"[{CONVICTION_MIN}, {CONVICTION_MAX}]"
            )
        # Invariant 4 — horizon membership.
        if self.horizon not in SUPPORTED_HORIZONS:
            raise ValueError(
                f"horizon {self.horizon} not in "
                f"{sorted(SUPPORTED_HORIZONS)}"
            )
        # Invariant 5 — 10Y confidence cap (defense-in-depth 1st layer).
        if self.horizon == 10:
            cap = (
                CONFIDENCE_CAP_10Y_REGIME_STRATIFIED
                if self.regime_stratified
                else CONFIDENCE_CAP_10Y_NON_STRATIFIED
            )
            if self.confidence > cap:
                label = (
                    "regime-stratified"
                    if self.regime_stratified
                    else "non-stratified"
                )
                raise ConfidenceCapViolation(
                    f"TripleDecomposition confidence "
                    f"{self.confidence:.4f} exceeds {label} 10Y cap of "
                    f"{cap}. Per Standing Order #9 + Vision §4 + L5b-F "
                    f"F-H2 (defense-in-depth construction-time layer)."
                )
