"""MetricMetadata schema for L6 ensemble aggregation (L6-A).

Per Strategic L6-A inline spec (post-L6-PREP 2026-05-15) §3 Step 4.
Vision v2.0 §3 (90-measurement catalogue) + §11 (L1/L2/L3 explanation
stack) + Pipeline Guide §8.1 (MetricMetadata template).

Field naming reconciliation
---------------------------
Strategic L6-A pre-flight specifies `description_l1` / `description_l2`
/ `description_l3` per Vision §11 explanation stack — the natural
mapping to the L1/L2/L3 BINDING outputs convention. Pipeline Guide §8.1
template instead uses `plain_english` / `formal_definition` /
`primary_source` as field names; these are the SAME concepts with
different naming. Track A follows Strategic L6-A pre-flight verbatim
(description_l1/l2/l3 naming) and documents the Pipeline Guide §8.1
divergence here; Pipeline Guide §8.1 fields not adopted at L6-A
(visual_encoding, eli5_template, learn_more_url, related_metrics,
how_to_read, caveats) are L8 surface concerns deferred to L8a/L8b/L8c
design per Vision §15 phasing.

Subcategory taxonomy (Vision §3 verbatim)
-----------------------------------------
Strategic L6-A pre-flight tentatively listed twelve subcategory names
(valuation / macro_regime / credit_risk / liquidity / sentiment /
technical / fundamental / volatility / concentration / structural /
geopolitical / behavioral) — these DO NOT MATCH Vision §3 actual
taxonomy. Track A uses Vision §3 names verbatim per Strategic Risk #1
mitigation ("Step 3 read is authoritative"). The actual Vision §3
subcategories are statistical-taxonomy rather than macro-thematic:

  §3.1 probability                 (8 measures)
  §3.2 uncertainty                 (7 measures)
  §3.3 confidence_conviction       (6 measures)
  §3.4 goodness_fit_calibration   (10 measures)
  §3.5 statistical_significance    (9 measures)
  §3.6 bias_correction             (7 measures)
  §3.7 risk_measures               (9 measures)
  §3.8 time_series_quality         (6 measures)
  §3.9 information_theory          (4 measures)
  §3.10 bayesian                   (7 measures)
  §3.11 macro_specific             (8 measures)
  §3.12 regime_conditional         (9 measures)

Total: ninety measurements. The macro-thematic Strategic-hypothesis
names (valuation / etc.) appear at the measurement level — e.g.,
"CAPE percentile" lives under §3.11 macro_specific. Subcategory
indexing matches Vision §3 ordering one through twelve.

Public API
----------
``MetricMetadata``  Frozen dataclass for a single measurement.
``SUBCATEGORY``     Literal type listing the twelve Vision §3 subcategories.
``LAYER_ORIGIN``    Literal type listing producer layers.
``SUBCATEGORY_VALID`` frozenset for runtime validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple

# Vision §3 subcategory names (verbatim ordering §3.1..§3.12).
SUBCATEGORY = Literal[
    "probability",
    "uncertainty",
    "confidence_conviction",
    "goodness_fit_calibration",
    "statistical_significance",
    "bias_correction",
    "risk_measures",
    "time_series_quality",
    "information_theory",
    "bayesian",
    "macro_specific",
    "regime_conditional",
]

SUBCATEGORY_VALID = frozenset(
    {
        "probability",
        "uncertainty",
        "confidence_conviction",
        "goodness_fit_calibration",
        "statistical_significance",
        "bias_correction",
        "risk_measures",
        "time_series_quality",
        "information_theory",
        "bayesian",
        "macro_specific",
        "regime_conditional",
    }
)

# Producer layer indicator. ``L1.7`` is the MANUAL_INPUT layer; ``L6``
# is the ensemble-aggregation layer itself (some measures are L6-derived
# rather than upstream-imported).
LAYER_ORIGIN = Literal["L1", "L2", "L3", "L4", "L5", "L5b", "L1.7", "L6"]

LAYER_ORIGIN_VALID = frozenset(
    {"L1", "L2", "L3", "L4", "L5", "L5b", "L1.7", "L6"}
)

UPDATE_FREQUENCY = Literal[
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "annual",
    "on_request",
    "unspecified",
]

UPDATE_FREQUENCY_VALID = frozenset(
    {
        "daily",
        "weekly",
        "monthly",
        "quarterly",
        "annual",
        "on_request",
        "unspecified",
    }
)


@dataclass(frozen=True)
class MetricMetadata:
    """Metadata for a single Vision §3 measurement.

    Per Strategic L6-A spec + Pipeline Guide §8.1 + Vision §11.

    Required fields:
        metric_id           snake_case registry key (alphanumeric + _).
        name                canonical display name.
        subcategory         one of SUBCATEGORY_VALID.
        subcategory_index   1..12 per Vision §3 ordering.
        layer_origin        producer layer.
        unit                e.g., "ratio", "bps", "percent", "z_score".
        update_frequency    one of UPDATE_FREQUENCY_VALID.
        description_l1      Vision §11 L1 (one beginner-accessible sentence).
        description_l2      Vision §11 L2 (sophisticated peer level; 1-2 sentences).
        description_l3      Vision §11 L3 (academic precise; 1-2 sentences w/ citation).

    Optional fields (with defaults):
        range_min           hard lower bound (e.g., 0.0 for probabilities).
        range_max           hard upper bound (e.g., 1.0 for probabilities).
        typical_range       observed/expected range tuple (t_min, t_max).
        invert_for_signal   True if higher value = bearish (e.g., CAPE).
        citations           tuple of academic citations.
        computation_path    file:line ref to producer; None until L6-G.
        deferred_to         L7 / L8a if not L6 scope (per D7 disposition).
    """

    metric_id: str
    name: str
    subcategory: str
    subcategory_index: int
    layer_origin: str
    unit: str
    update_frequency: str
    description_l1: str
    description_l2: str
    description_l3: str
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    typical_range: Optional[Tuple[float, float]] = None
    invert_for_signal: bool = False
    citations: Tuple[str, ...] = ()
    computation_path: Optional[str] = None
    deferred_to: Optional[str] = None

    def __post_init__(self) -> None:
        # metric_id: non-empty + snake_case (alphanumeric + underscore).
        if not self.metric_id:
            raise ValueError("metric_id must be non-empty")
        if not self.metric_id.replace("_", "").isalnum():
            raise ValueError(
                f"metric_id must be alphanumeric + underscores; got "
                f"{self.metric_id!r}"
            )
        if not self.metric_id.islower():
            raise ValueError(
                f"metric_id must be snake_case (lowercase); got "
                f"{self.metric_id!r}"
            )
        # Subcategory + index.
        if self.subcategory not in SUBCATEGORY_VALID:
            raise ValueError(
                f"subcategory must be one of {sorted(SUBCATEGORY_VALID)}; "
                f"got {self.subcategory!r}"
            )
        if not (1 <= self.subcategory_index <= 12):
            raise ValueError(
                f"subcategory_index must be in [1, 12]; got "
                f"{self.subcategory_index}"
            )
        # Layer origin.
        if self.layer_origin not in LAYER_ORIGIN_VALID:
            raise ValueError(
                f"layer_origin must be one of "
                f"{sorted(LAYER_ORIGIN_VALID)}; got {self.layer_origin!r}"
            )
        # Update frequency.
        if self.update_frequency not in UPDATE_FREQUENCY_VALID:
            raise ValueError(
                f"update_frequency must be one of "
                f"{sorted(UPDATE_FREQUENCY_VALID)}; got "
                f"{self.update_frequency!r}"
            )
        # Description stack (Vision §11 BINDING).
        if not self.description_l1.strip():
            raise ValueError(
                f"description_l1 must be non-empty for metric_id="
                f"{self.metric_id!r}"
            )
        if not self.description_l2.strip():
            raise ValueError(
                f"description_l2 must be non-empty for metric_id="
                f"{self.metric_id!r}"
            )
        if not self.description_l3.strip():
            raise ValueError(
                f"description_l3 must be non-empty for metric_id="
                f"{self.metric_id!r}"
            )
        # Range invariants.
        if self.range_min is not None and self.range_max is not None:
            if self.range_min > self.range_max:
                raise ValueError(
                    f"range_min ({self.range_min}) > range_max "
                    f"({self.range_max}) for metric_id={self.metric_id!r}"
                )
        if self.typical_range is not None:
            t_min, t_max = self.typical_range
            if t_min > t_max:
                raise ValueError(
                    f"typical_range inverted (t_min={t_min} > t_max="
                    f"{t_max}) for metric_id={self.metric_id!r}"
                )
        # deferred_to validation.
        if self.deferred_to is not None and self.deferred_to not in (
            "L7",
            "L8a",
        ):
            raise ValueError(
                f"deferred_to must be None / 'L7' / 'L8a'; got "
                f"{self.deferred_to!r}"
            )
