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

import math
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

# L6-J D4 (ChatGPT R7 #8 / C-10) registry lineage schema additions.

# `status` field — computed entries vs deferred-to-future-layer entries.
METRIC_STATUS = Literal["computed", "deferred"]
METRIC_STATUS_VALID = frozenset({"computed", "deferred"})

# `deferred_reason` — why a metric is deferred (controlled vocabulary).
DEFERRED_REASON = Literal[
    "scheduling",       # waiting on later-sprint scheduling priority
    "UI",               # UI primitive; needs L8a frontend layer
    "missing_loader",   # upstream data loader not yet implemented
    "portfolio_scope",  # portfolio-level concern; L7 scope
]
DEFERRED_REASON_VALID = frozenset(
    {"scheduling", "UI", "missing_loader", "portfolio_scope"}
)


@dataclass(frozen=True)
class MetricLineage:
    """L6-J D4 — Replication-grade lineage for a computed metric.

    Per ChatGPT R7 Finding #8 (C-10), replication-grade lineage requires
    explicit raw_source → loader → transform → model → aggregator_field →
    output_surface tracing. Each field is Optional[str] to accommodate
    progressive enrichment: at L6-J entries may have many ``None`` slots
    (deferred to L7+ for full population); the dataclass shape is the
    binding schema surface.

    Fields
    ------
    raw_source         e.g., "fred:UMCSENT" or "shiller:CAPE"
    loader             e.g., "macro_pipeline.loaders.fred:FREDLoader.fetch"
    transform          e.g., "macro_pipeline.analysis.forecast_sigma:compute"
    model              e.g., "macro_pipeline.models.return_forecast:Ridge"
    aggregator_field   e.g., "HorizonResult.metric_outputs.confidence"
    output_surface     e.g., "L8a.dashboard.confidence_metric"
    """

    raw_source: Optional[str] = None
    loader: Optional[str] = None
    transform: Optional[str] = None
    model: Optional[str] = None
    aggregator_field: Optional[str] = None
    output_surface: Optional[str] = None

    def __post_init__(self) -> None:
        for f_name in ("raw_source", "loader", "transform", "model",
                       "aggregator_field", "output_surface"):
            val = getattr(self, f_name)
            if val is not None and not isinstance(val, str):
                raise TypeError(
                    f"MetricLineage.{f_name} must be str or None; got "
                    f"{type(val).__name__}"
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
    # L6-J D4 — replication-grade lineage schema (additive; YAML
    # population deferred to L6-K). When None, derives status from
    # legacy fields: computed if computation_path is not None, else
    # deferred (matching existing 40/50 split per L6-G + Codex audit).
    status: Optional[str] = None
    deferred_reason: Optional[str] = None
    lineage: Optional[MetricLineage] = None

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
        # L6-I D1 — finite checks (NaN/inf rejected explicitly; Codex
        # Finding #2 cited line 227: range_min=NaN, range_max=1.0
        # constructs without raising at L6-H because NaN > 1.0 is False).
        if self.range_min is not None and not math.isfinite(self.range_min):
            raise ValueError(
                f"range_min must be finite; got {self.range_min!r} for "
                f"metric_id={self.metric_id!r}"
            )
        if self.range_max is not None and not math.isfinite(self.range_max):
            raise ValueError(
                f"range_max must be finite; got {self.range_max!r} for "
                f"metric_id={self.metric_id!r}"
            )
        if self.typical_range is not None:
            t_min, t_max = self.typical_range
            if not math.isfinite(t_min):
                raise ValueError(
                    f"typical_range[0] must be finite; got {t_min!r} for "
                    f"metric_id={self.metric_id!r}"
                )
            if not math.isfinite(t_max):
                raise ValueError(
                    f"typical_range[1] must be finite; got {t_max!r} for "
                    f"metric_id={self.metric_id!r}"
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
        # L6-J D4 — status + deferred_reason + lineage validation.
        if self.status is not None and self.status not in METRIC_STATUS_VALID:
            raise ValueError(
                f"status must be one of {sorted(METRIC_STATUS_VALID)}; got "
                f"{self.status!r} for metric_id={self.metric_id!r}"
            )
        if (
            self.deferred_reason is not None
            and self.deferred_reason not in DEFERRED_REASON_VALID
        ):
            raise ValueError(
                f"deferred_reason must be one of "
                f"{sorted(DEFERRED_REASON_VALID)}; got "
                f"{self.deferred_reason!r} for metric_id={self.metric_id!r}"
            )
        # If status explicitly set, enforce consistency with lineage/deferred.
        if self.status == "computed":
            if self.deferred_to is not None or self.deferred_reason is not None:
                raise ValueError(
                    f"computed metric {self.metric_id!r} must not have "
                    f"deferred_to or deferred_reason set"
                )
        elif self.status == "deferred":
            if self.deferred_to is None:
                raise ValueError(
                    f"deferred metric {self.metric_id!r} must have "
                    f"deferred_to set"
                )

    def derive_status(self) -> str:
        """L6-J D4 — derive ``status`` from legacy fields when not set.

        Returns ``"computed"`` if explicit ``status="computed"`` OR
        ``computation_path is not None``; else ``"deferred"``. Used by
        registry validation to enforce 40 computed + 50 deferred count
        (Track A L6-G claim) without requiring full YAML migration.
        """
        if self.status is not None:
            return self.status
        if self.computation_path is not None:
            return "computed"
        return "deferred"
