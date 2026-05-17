"""Ensemble aggregator — end-to-end forecast pipeline (L6-F + L6-G + L6-H).

Per Strategic L6-F + L6-G + L6-H inline pre-flights (2026-05-15 / 2026-05-16)
+ Pipeline Guide v2.0 §7 + Vision v2.1 §4 (Triple Probability Decomposition)
+ §5 (Triple sigma Reporting) + §6 (Reference Class Forecasting) + §7 (OOD
Reserve) + §8 (DMS) + §9 (Lucas critique) + §10 (Sample Size Honesty) +
§14 (Replication & Audit).

L6-H refinement summary (2026-05-16)
------------------------------------
Closes 6 ChatGPT R7 methodology HIGH findings (#1, #2, #3, #4, #9 + Op #3):

* **D1** — ``compute_ood_reserve`` now uses Vision §7 severity-tier bucket
  arithmetic with reason codes (replaces L6-D equal-increment heuristic;
  return type ``tuple[float, tuple[str, ...]]``).
* **D2** — Cap cascade across ALL horizons via new
  ``apply_confidence_cap_cascade(...)`` with signal-conflict + OOD-elevated
  modifiers; the legacy ``enforce_confidence_caps`` (raise-helper, 10Y only)
  is PRESERVED UNCHANGED per PD20 for Test 12.
* **D3** — ``compute_bayesian_confidence`` rewritten to Vision §4 6-component
  additive formula (25% DQ + 25% MA + 20% RS + 15% AS + 10% SS − 5% OOD);
  components built via ``derive_confidence_components``.
* **D4** — ``compute_conviction_score`` rewritten to Vision §4 10-component
  distinct risk/reward score (edge + asymmetry + supports MINUS penalties);
  components built via ``derive_conviction_components``. Conviction CAN BE
  LOWER THAN confidence (Vision §4 critical rule preserved by independent
  component set).
* **D5** — DMS adjustment now PROPAGATED INTO the point estimate via
  ``select_dms_adjustment_bps`` + ``apply_dms_bps_to_return``; the L6-G
  ``dms_adjustment_bps`` metric is retained; new ``HorizonResult`` fields
  expose ``dms_raw_point_estimate``, ``dms_adjusted_point_estimate``,
  ``dms_adjustment_bps``, ``dms_selection_reason``, plus
  ``LucasCritiqueDiagnostics``.
* **D6** — Vision §4 cap table re-anchored to §10 (3Y/5Y = 80%, not 85%).
  Aggregator cap cascade now sources caps from §10 via ``ood_and_caps``
  helpers. ``SHORT_HORIZON_CONFIDENCE_CAP`` legacy constant removed.

Defense-in-depth confidence cap (3rd-instance PRESERVED at L6-H)
-----------------------------------------------------------------
The 3rd-instance pattern at the aggregator is PRESERVED through L6-H:

  1. ``apply_confidence_cap_cascade`` computes the final per-horizon
     capped confidence (handles 1Y/3Y/5Y/10Y + signal-conflict + OOD
     elevated modifiers).
  2. ``TripleDecomposition`` is constructed with the capped value
     (Layer 1 ``__post_init__`` fires defensively if cap is bypassed).
  3. ``enforce_confidence_caps`` is called on the capped value
     (Layer 2 raise-helper; defensive — never raises in normal path
     because cascade already capped at step 1).

Test 12 (``test_aggregate_defense_in_depth_both_layers_fire``) verifies
the pattern: direct ``TripleDecomposition`` construction with confidence
> cap raises Layer 1; direct ``enforce_confidence_caps`` call with
confidence > cap raises Layer 2; aggregator pipeline at 10Y stratified
with high-confidence inputs produces final capped value = 0.55.

Public API
----------
``ForecastInputs``       Frozen wrapper for L5b producer outputs.
``HorizonResult``        Frozen per-horizon ensemble result (L6-H expanded).
``EnsembleResult``       Frozen multi-horizon aggregate.
``aggregate_ensemble``   Pure function — end-to-end aggregation.
``SUPPORTED_HORIZONS``   ``(1, 3, 5, 10)`` per Vision §1 Pillar 4.
``populate_metric_outputs``  L6-G helper (extended at L6-H with DMS +
                             Lucas fields).
"""
from __future__ import annotations

import math
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Dict, Optional, Tuple

from macro_pipeline.ensemble.bayesian_confidence import (
    ConfidenceComponents,
    ConvictionComponents,
    compute_bayesian_confidence,
    compute_conviction_score,
    derive_confidence_components,
    derive_conviction_components,
)
from macro_pipeline.ensemble.dms_and_lucas import (
    LucasCritiqueDiagnostics,
    apply_dms_bps_to_return,
    compute_lucas_diagnostics,
    select_dms_adjustment_bps,
)
from macro_pipeline.ensemble.model_signals import (
    detect_layer_disagreement,
    wrap_point_estimates_as_model_signals,
)
from macro_pipeline.ensemble.ood_and_caps import (
    OODConditions,
    apply_confidence_cap_cascade,
    compute_ood_reserve,
    enforce_confidence_caps,
)
from macro_pipeline.ensemble.rcf import (
    BAYESIAN_PRIOR_10Y_REAL_RETURN,
    ReferenceClass,
    apply_bayesian_shrinkage,
)
from macro_pipeline.ensemble.triple_decomposition import TripleDecomposition
from macro_pipeline.ensemble.triple_sigma import TripleSigma
from macro_pipeline.manual_input.schema import ManualInputSchedule

# Vision §1 Pillar 4 horizon set; ordered for deterministic iteration.
SUPPORTED_HORIZONS: Tuple[int, ...] = (1, 3, 5, 10)

# OOD reserve floor when no conditions provided (Vision §7).
OOD_RESERVE_FLOOR_DEFAULT = 0.05

# OOD elevated threshold for cap cascade (Vision §7 + §4).
OOD_ELEVATED_RESERVE_THRESHOLD = 0.10

# DEPRECATED at L6-H — retained as L6-F/L6-G compatibility alias.
# Vision v2.1 §10 now specifies horizon-conditional caps (1Y=85%; 3Y=80%;
# 5Y=80%; 10Y=70%/55%) sourced from `ood_and_caps.HORIZON_CAPS_*` tables.
# This constant matches the 1Y cap; 3Y/5Y/10Y use ood_and_caps tables.
# Use `apply_confidence_cap_cascade` for new code.
SHORT_HORIZON_CONFIDENCE_CAP = 0.85


@dataclass(frozen=True)
class ForecastInputs:
    """Wraps L5b producer outputs + optional L6-E RCF output for aggregator.

    All per-horizon dicts must contain every horizon in
    ``SUPPORTED_HORIZONS``; ``__post_init__`` validates membership.

    Fields
    ------
    point_estimates           horizon -> central return forecast (float)
    point_estimate_n_eff      horizon -> effective sample size (int)
    forecast_sigmas           horizon -> forecast error sigma (float)
    analog_dispersions        horizon -> analog dispersion sigma (float)
    return_sigmas             horizon -> annualized return sigma (float)
    recession_probabilities   horizon -> P(recession) in [0, 1] (float)
    reference_class           optional L6-E RCF output (passes through)
    dms_adjustments           optional horizon -> DMS bps from L5-F
                              (passes through to metric_outputs; the L6-H
                              aggregator may override this per
                              risk-flag-driven selector — see below).
    """

    point_estimates: Dict[int, float]
    point_estimate_n_eff: Dict[int, int]
    forecast_sigmas: Dict[int, float]
    analog_dispersions: Dict[int, float]
    return_sigmas: Dict[int, float]
    recession_probabilities: Dict[int, float]
    reference_class: Optional[ReferenceClass] = None
    dms_adjustments: Optional[Dict[int, float]] = None

    def __post_init__(self) -> None:
        required = (
            ("point_estimates", self.point_estimates),
            ("point_estimate_n_eff", self.point_estimate_n_eff),
            ("forecast_sigmas", self.forecast_sigmas),
            ("analog_dispersions", self.analog_dispersions),
            ("return_sigmas", self.return_sigmas),
            ("recession_probabilities", self.recession_probabilities),
        )
        for field_name, field_dict in required:
            missing = [h for h in SUPPORTED_HORIZONS if h not in field_dict]
            if missing:
                raise ValueError(
                    f"ForecastInputs.{field_name} missing horizons: "
                    f"{missing}"
                )
        # L6-I D1 — finite invariants on all numeric dict values
        # (Codex Finding #2; NaN/inf inputs would corrupt downstream
        # confidence + conviction + cap-cascade computations silently).
        float_field_names = (
            "point_estimates",
            "forecast_sigmas",
            "analog_dispersions",
            "return_sigmas",
            "recession_probabilities",
        )
        for fname in float_field_names:
            fdict = getattr(self, fname)
            for h, v in fdict.items():
                if not math.isfinite(v):
                    raise ValueError(
                        f"ForecastInputs.{fname}[{h}] must be finite; "
                        f"got {v!r}"
                    )
        # n_eff: non-negative integer check.
        for h, n in self.point_estimate_n_eff.items():
            if not isinstance(n, int) or isinstance(n, bool):
                raise TypeError(
                    f"ForecastInputs.point_estimate_n_eff[{h}] must be "
                    f"int; got {type(n).__name__}"
                )
            if n < 0:
                raise ValueError(
                    f"ForecastInputs.point_estimate_n_eff[{h}] must be "
                    f"non-negative; got {n}"
                )
        # Optional dms_adjustments finite check.
        if self.dms_adjustments is not None:
            for h, v in self.dms_adjustments.items():
                if not math.isfinite(v):
                    raise ValueError(
                        f"ForecastInputs.dms_adjustments[{h}] must be "
                        f"finite; got {v!r}"
                    )
        # L6-I D2 — deep-immutability via MappingProxyType wrapping for
        # all dict fields (Codex Finding #1; frozen dataclass prevents
        # field-rebind but mutable dicts can still be mutated post-init).
        for fname in (
            "point_estimates",
            "point_estimate_n_eff",
            "forecast_sigmas",
            "analog_dispersions",
            "return_sigmas",
            "recession_probabilities",
        ):
            current = getattr(self, fname)
            if not isinstance(current, MappingProxyType):
                object.__setattr__(
                    self, fname, MappingProxyType(dict(current))
                )
        if self.dms_adjustments is not None and not isinstance(
            self.dms_adjustments, MappingProxyType
        ):
            object.__setattr__(
                self,
                "dms_adjustments",
                MappingProxyType(dict(self.dms_adjustments)),
            )


@dataclass(frozen=True)
class HorizonResult:
    """Per-horizon ensemble result (L6-H expanded).

    Fields
    ------
    horizon                       1 / 3 / 5 / 10
    triple_decomposition          L6-B TripleDecomposition with cap enforced
    triple_sigma                  L6-C TripleSigma
    metric_outputs                metric_id -> float (≥15 keys at L6-H)
    bayesian_shrinkage_applied    True at 10Y (Vision §6 prior); False otherwise
    shrinkage_n_eff               n_eff used in shrinkage; None if not applied

    L6-H additions (D5 — DMS + Lucas surfaced as first-class fields):

    dms_raw_point_estimate        Point estimate BEFORE DMS application
                                  (post-Bayesian-shrinkage at 10Y; equal
                                  to ForecastInputs.point_estimates[h] at
                                  1Y/3Y).
    dms_adjusted_point_estimate   Point estimate AFTER DMS application —
                                  the binding forecast value at this
                                  horizon. Equal to dms_raw at 1Y/3Y
                                  (no adjustment per Vision §8).
    dms_adjustment_bps            DMS bps applied (0.0 at 1Y/3Y; tier-
                                  selected at 5Y/10Y).
    dms_selection_reason          Reason code from select_dms_adjustment_bps.
    lucas_diagnostics             L6-H LucasCritiqueDiagnostics (default:
                                  no-evidence diagnostics with flag=False).
    """

    horizon: int
    triple_decomposition: TripleDecomposition
    triple_sigma: TripleSigma
    metric_outputs: Dict[str, float]
    bayesian_shrinkage_applied: bool
    shrinkage_n_eff: Optional[int] = None
    # L6-H additions (D5):
    dms_raw_point_estimate: float = 0.0
    dms_adjusted_point_estimate: float = 0.0
    dms_adjustment_bps: float = 0.0
    dms_selection_reason: str = "horizon_not_eligible"
    lucas_diagnostics: LucasCritiqueDiagnostics = field(
        default_factory=lambda: LucasCritiqueDiagnostics(
            flag=False, reason_codes=(), structural_break_evidence={}
        )
    )
    # L6-I additions (D5 — layer-disagreement signal):
    layer_disagreement_flag: bool = False
    layer_disagreement_label: str = "consensus"

    def __post_init__(self) -> None:
        # L6-I D1 — finite checks on numeric float fields.
        for fname in (
            "dms_raw_point_estimate",
            "dms_adjusted_point_estimate",
            "dms_adjustment_bps",
        ):
            val = getattr(self, fname)
            if not math.isfinite(val):
                raise ValueError(
                    f"HorizonResult.{fname} must be finite; got {val!r}"
                )
        # L6-I D1 — finite checks on metric_outputs values.
        for k, v in self.metric_outputs.items():
            if not math.isfinite(v):
                raise ValueError(
                    f"HorizonResult.metric_outputs[{k!r}] must be finite; "
                    f"got {v!r}"
                )
        # L6-I D2 — deep-immutability on metric_outputs dict.
        if not isinstance(self.metric_outputs, MappingProxyType):
            object.__setattr__(
                self, "metric_outputs", MappingProxyType(dict(self.metric_outputs))
            )


@dataclass(frozen=True)
class EnsembleResult:
    """Multi-horizon ensemble forecast.

    Fields
    ------
    horizons                     dict mapping {1, 3, 5, 10} -> HorizonResult
    ood_reserve_fraction         in [0.05, 0.15] per Vision §7
    ood_reason_codes             tuple of active OOD condition keys (L6-H D1)
    reference_class              passes through from ForecastInputs (Vision §6)
    replication_kit_metadata     6 keys (Vision §14)
    aggregation_timestamp_iso    UTC ISO 8601 timestamp
    """

    horizons: Dict[int, HorizonResult]
    ood_reserve_fraction: float
    reference_class: Optional[ReferenceClass]
    replication_kit_metadata: Dict[str, str]
    aggregation_timestamp_iso: str
    # L6-H addition (D1):
    ood_reason_codes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if set(self.horizons.keys()) != set(SUPPORTED_HORIZONS):
            raise ValueError(
                f"EnsembleResult.horizons keys "
                f"{sorted(self.horizons.keys())} != supported "
                f"{sorted(SUPPORTED_HORIZONS)}"
            )
        # L6-I D1 — finite check before range comparison.
        if not math.isfinite(self.ood_reserve_fraction):
            raise ValueError(
                f"ood_reserve_fraction must be finite; got "
                f"{self.ood_reserve_fraction!r}"
            )
        if not (0.05 <= self.ood_reserve_fraction <= 0.15):
            raise ValueError(
                f"ood_reserve_fraction {self.ood_reserve_fraction} "
                f"out of [0.05, 0.15] per Vision §7"
            )
        # L6-I D2 — deep-immutability on horizons + replication_kit_metadata.
        if not isinstance(self.horizons, MappingProxyType):
            object.__setattr__(
                self, "horizons", MappingProxyType(dict(self.horizons))
            )
        if not isinstance(self.replication_kit_metadata, MappingProxyType):
            object.__setattr__(
                self,
                "replication_kit_metadata",
                MappingProxyType(dict(self.replication_kit_metadata)),
            )


def _get_code_sha() -> str:
    """Read git HEAD SHA for the replication-kit metadata stamp.

    Returns the 40-char hex SHA on success; ``"unknown"`` otherwise
    (matches L1.7-C ``_get_current_code_sha`` precedent).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            if sha:
                return sha
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "unknown"


def populate_metric_outputs(
    forecast_inputs: ForecastInputs,
    horizon: int,
    point_estimate: float,
    recession_p: float,
    confidence: float,
    conviction: float,
    *,
    # L6-H additions (D5):
    dms_raw_point_estimate: Optional[float] = None,
    dms_adjusted_point_estimate: Optional[float] = None,
    dms_adjustment_bps: Optional[float] = None,
    lucas_flag: Optional[bool] = None,
) -> Dict[str, float]:
    """Populate ``metric_outputs`` dict for a HorizonResult.

    Extends the L6-F eight-key baseline with L6-G (cumulative sigma,
    posterior precision, RCF metrics) and L6-H (DMS raw + adjusted point
    estimate, Lucas flag). Skips measures unavailable at this horizon
    (no NaN population).

    L6-H D5: when ``dms_*`` keyword overrides are provided, those values
    are used in the metric outputs (matching the HorizonResult fields
    populated by the aggregator). Backward-compat: when keywords are
    None, the L6-G behaviour (``dms_adjustment_bps`` from
    ``ForecastInputs.dms_adjustments``) is preserved.

    Parameters
    ----------
    forecast_inputs
        ``ForecastInputs`` wrapping L5b producer outputs + L6-E RCF.
    horizon
        Current horizon in ``SUPPORTED_HORIZONS``.
    point_estimate
        Post-DMS point estimate at this horizon (binding forecast value).
    recession_p
        Recession probability at this horizon (post-manual-override).
    confidence
        Capped confidence from cascade + cap helpers.
    conviction
        Conviction from Vision §4 10-component formula.
    dms_raw_point_estimate, dms_adjusted_point_estimate,
    dms_adjustment_bps, lucas_flag
        Optional L6-H D5 overrides for the corresponding metric keys.

    Returns
    -------
    Dict[str, float]
        Mapping ``metric_id -> float`` populated with baseline + L6-G + L6-H.
    """
    outputs: Dict[str, float] = {
        # L6-F baseline (eight keys).
        "point_estimate_return": point_estimate,
        "recession_probability": recession_p,
        "confidence": confidence,
        "conviction": conviction,
        "n_eff": float(forecast_inputs.point_estimate_n_eff[horizon]),
        "return_sigma": forecast_inputs.return_sigmas[horizon],
        "forecast_error_sigma": forecast_inputs.forecast_sigmas[horizon],
        "analog_dispersion_sigma": forecast_inputs.analog_dispersions[
            horizon
        ],
    }

    # L6-G additions ————————————————————————————————————————————————————————

    # DMS adjustment metric — L6-H D5 override OR L6-G ForecastInputs surface.
    if dms_adjustment_bps is not None:
        outputs["dms_adjustment_bps"] = float(dms_adjustment_bps)
    elif (
        forecast_inputs.dms_adjustments is not None
        and horizon in forecast_inputs.dms_adjustments
    ):
        outputs["dms_adjustment_bps"] = float(
            forecast_inputs.dms_adjustments[horizon]
        )

    # Reference Class metrics (L6-E passthrough when reference_class present).
    if forecast_inputs.reference_class is not None:
        outputs["rcf_mean_similarity"] = float(
            forecast_inputs.reference_class.mean_similarity
        )
        outputs["rcf_n_neighbors"] = float(
            forecast_inputs.reference_class.n_neighbors
        )

    # Cumulative sigma scaling per Vision §5 (caveats per TripleSigma module
    # docstring — square-root-of-time approximation may fail in regime
    # shifts / vol clustering / crises / policy shocks).
    sqrt_h = math.sqrt(horizon)
    outputs["cumulative_return_sigma"] = (
        forecast_inputs.return_sigmas[horizon] * sqrt_h
    )
    outputs["cumulative_forecast_error_sigma"] = (
        forecast_inputs.forecast_sigmas[horizon] * sqrt_h
    )
    outputs["cumulative_analog_dispersion_sigma"] = (
        forecast_inputs.analog_dispersions[horizon] * sqrt_h
    )

    # Posterior-precision indicator (Bayesian evidence weight at this
    # horizon; useful diagnostic for the Vision §10 sample-size honesty
    # surface).
    from macro_pipeline.ensemble.bayesian_confidence import KAPPA_EVIDENCE
    outputs["posterior_precision"] = float(
        forecast_inputs.point_estimate_n_eff[horizon] + KAPPA_EVIDENCE
    )

    # L6-H additions (D5) ——————————————————————————————————————————————————

    if dms_raw_point_estimate is not None:
        outputs["dms_raw_point_estimate"] = float(dms_raw_point_estimate)
    if dms_adjusted_point_estimate is not None:
        outputs["dms_adjusted_point_estimate"] = float(
            dms_adjusted_point_estimate
        )
    if lucas_flag is not None:
        outputs["lucas_critique_flag"] = 1.0 if lucas_flag else 0.0

    return outputs


def aggregate_horizons_pure(
    forecast_inputs: ForecastInputs,
    manual_inputs: Optional[ManualInputSchedule] = None,
    ood_conditions: Optional[OODConditions] = None,
    regime_stratified: bool = False,
    *,
    valuation_extreme: bool = False,
    concentration_extreme: bool = False,
    fiscal_risks_elevated: bool = False,
    reserve_currency_risk: bool = False,
    lucas_evidence: Optional[Dict[str, float]] = None,
    signal_conflict: bool = False,
) -> Tuple[Dict[int, HorizonResult], float, Tuple[str, ...]]:
    """L6-J D6 — Pure horizon aggregation (no timestamp / no git SHA / no I/O).

    Per Codex R7 Finding #5 (C-14), the L6-H ``aggregate_ensemble``
    interleaved pure aggregation with side-effectful replication metadata
    stamping (``datetime.now(timezone.utc)`` + ``subprocess.run(git
    rev-parse)``). L6-J extracts the deterministic core into
    ``aggregate_horizons_pure`` so that:

      - Same inputs → same outputs (reproducible replication kit).
      - Tests no longer race against wall-clock or git state.
      - ``aggregate_ensemble`` (below) wraps this pure core + optional
        injectable timestamp/SHA for orchestrators that need
        deterministic replication metadata.

    Returns a 3-tuple ``(horizon_results, ood_reserve, ood_reason_codes)``
    sufficient to compose ``EnsembleResult`` externally.

    All parameters identical to ``aggregate_ensemble`` minus
    timestamp/SHA injection. See aggregate_ensemble for parameter docs.
    """
    # Step 1 — OOD reserve + reason codes (L6-H D1)
    if ood_conditions is None:
        ood_reserve = OOD_RESERVE_FLOOR_DEFAULT
        ood_reason_codes: Tuple[str, ...] = ()
    else:
        ood_reserve, ood_reason_codes = compute_ood_reserve(ood_conditions)

    # Step 2 — Lucas critique diagnostics (L6-H D5)
    lucas_diag = compute_lucas_diagnostics(structural_break_evidence=lucas_evidence)

    horizon_results: Dict[int, HorizonResult] = {}

    for horizon in SUPPORTED_HORIZONS:
        # Step 3a — point estimate + n_eff
        point = forecast_inputs.point_estimates[horizon]
        n_eff = forecast_inputs.point_estimate_n_eff[horizon]

        # Step 3b — manual recession_p override (L1.7-D integration)
        recession_p = forecast_inputs.recession_probabilities[horizon]
        if manual_inputs is not None:
            from macro_pipeline.manual_input.integration import (
                apply_recession_p_override_for_horizon,
            )
            recession_p = apply_recession_p_override_for_horizon(
                manual_inputs, horizon, recession_p
            )

        # Step 3c — Bayesian shrinkage at 10Y only (Vision §6)
        bayesian_applied = False
        shrinkage_n_eff: Optional[int] = None
        if horizon == 10:
            point = apply_bayesian_shrinkage(
                point_estimate=point,
                prior=BAYESIAN_PRIOR_10Y_REAL_RETURN,
                n_eff=n_eff,
            )
            bayesian_applied = True
            shrinkage_n_eff = n_eff

        # Step 3d — DMS adjustment (L6-H D5)
        dms_raw_pe = point
        dms_bps, dms_reason = select_dms_adjustment_bps(
            horizon=horizon,
            valuation_extreme=valuation_extreme,
            concentration_extreme=concentration_extreme,
            fiscal_risks_elevated=fiscal_risks_elevated,
            reserve_currency_risk=reserve_currency_risk,
        )
        dms_adjusted_pe = apply_dms_bps_to_return(dms_raw_pe, dms_bps)
        point = dms_adjusted_pe

        # Step 3e — Vision §4 additive confidence (L6-H D3)
        confidence_components = derive_confidence_components(
            n_eff=n_eff,
            horizon=horizon,
            reference_class=forecast_inputs.reference_class,
            ood_reserve_fraction=ood_reserve,
        )
        raw_confidence = compute_bayesian_confidence(
            components=confidence_components,
            horizon=horizon,
        )

        # Step 3f — Vision §4 + §7 + §10 cap cascade (L6-H D2)
        confidence = apply_confidence_cap_cascade(
            confidence=raw_confidence,
            horizon=horizon,
            regime_stratified=regime_stratified,
            signal_conflict=signal_conflict,
            ood_elevated=(ood_reserve >= OOD_ELEVATED_RESERVE_THRESHOLD),
            ood_reserve_fraction=ood_reserve,
        )

        # Step 3g — Vision §4 10-component conviction (L6-H D4)
        conviction_components = derive_conviction_components(
            confidence=confidence,
            n_eff=n_eff,
            horizon=horizon,
            reference_class=forecast_inputs.reference_class,
            point_estimate=point,
        )
        conviction = compute_conviction_score(conviction_components)

        # Step 3h — TripleDecomposition (defense-in-depth 1st layer)
        triple_decomp = TripleDecomposition(
            probability=recession_p,
            confidence=confidence,
            conviction=conviction,
            horizon=horizon,
            regime_stratified=regime_stratified,
        )

        # Step 3i — enforce_confidence_caps (defense-in-depth 2nd layer)
        enforce_confidence_caps(confidence, horizon, regime_stratified)

        # Step 3j — TripleSigma (Vision §5)
        triple_sigma = TripleSigma(
            return_sigma=forecast_inputs.return_sigmas[horizon],
            forecast_error_sigma=forecast_inputs.forecast_sigmas[horizon],
            analog_dispersion_sigma=forecast_inputs.analog_dispersions[
                horizon
            ],
            horizon=horizon,
        )

        # Step 3k — metric_outputs
        metric_outputs = populate_metric_outputs(
            forecast_inputs=forecast_inputs,
            horizon=horizon,
            point_estimate=point,
            recession_p=recession_p,
            confidence=confidence,
            conviction=conviction,
            dms_raw_point_estimate=dms_raw_pe,
            dms_adjusted_point_estimate=dms_adjusted_pe,
            dms_adjustment_bps=dms_bps,
            lucas_flag=lucas_diag.flag,
        )

        # L6-I D3+D5 — wrap point_estimates as 11-model placeholder signals
        # + detect layer disagreement.
        model_signals = wrap_point_estimates_as_model_signals(
            point_estimates={h: point if h == horizon else 0.0
                             for h in SUPPORTED_HORIZONS},
            horizon=horizon,
        )
        disagree_flag, disagree_label = detect_layer_disagreement(
            model_signals
        )

        # Step 3l — HorizonResult
        horizon_results[horizon] = HorizonResult(
            horizon=horizon,
            triple_decomposition=triple_decomp,
            triple_sigma=triple_sigma,
            metric_outputs=metric_outputs,
            bayesian_shrinkage_applied=bayesian_applied,
            shrinkage_n_eff=shrinkage_n_eff,
            dms_raw_point_estimate=dms_raw_pe,
            dms_adjusted_point_estimate=dms_adjusted_pe,
            dms_adjustment_bps=dms_bps,
            dms_selection_reason=dms_reason,
            lucas_diagnostics=lucas_diag,
            layer_disagreement_flag=disagree_flag,
            layer_disagreement_label=disagree_label,
        )

    return (horizon_results, ood_reserve, ood_reason_codes)


def aggregate_ensemble(
    forecast_inputs: ForecastInputs,
    manual_inputs: Optional[ManualInputSchedule] = None,
    ood_conditions: Optional[OODConditions] = None,
    regime_stratified: bool = False,
    *,
    # L6-H additions (D5):
    valuation_extreme: bool = False,
    concentration_extreme: bool = False,
    fiscal_risks_elevated: bool = False,
    reserve_currency_risk: bool = False,
    lucas_evidence: Optional[Dict[str, float]] = None,
    signal_conflict: bool = False,
    # L6-J D6 — injectable replication metadata for deterministic tests
    # + replication kits. Defaults preserve L6-H backward compat
    # (dynamic timestamp + git SHA fetch).
    timestamp_utc: Optional[datetime] = None,
    code_sha: Optional[str] = None,
) -> EnsembleResult:
    """End-to-end ensemble aggregation (L6-F base + L6-G/L6-H/L6-I/L6-J refinements).

    L6-K verification (Codex Op #2 closure): the step list below reflects the
    BINDING Vision §4 additive confidence + 10-component conviction formulas
    (not the L6-F placeholder heuristics). The placeholder language Codex
    flagged was removed at L6-G + L6-H + L6-I; no further edits required at L6-K.

    Pipeline
    --------
    1. Compute OOD reserve + reason codes from ``ood_conditions``
       (or floor 0.05 with empty reason codes).
    2. Compute Lucas critique diagnostics from ``lucas_evidence``
       (or no-evidence default).
    3. For each horizon in ``SUPPORTED_HORIZONS``:
       a. Read point estimate + n_eff from forecast_inputs.
       b. Apply manual recession_p override via L1.7-D helper if
          ``manual_inputs`` provided.
       c. Apply Bayesian shrinkage at 10Y (prior 0.065 per Vision §6).
       d. Apply L6-H DMS dynamic selector + ``apply_dms_bps_to_return``
          to point estimate (5Y/10Y only; 1Y/3Y get 0 bps).
       e. Build ConfidenceComponents via ``derive_confidence_components``
          + compute raw confidence via Vision §4 additive formula.
       f. Apply L6-H cap cascade via ``apply_confidence_cap_cascade``
          (Vision §4 + §7 + §10 modifiers).
       g. Build ConvictionComponents via ``derive_conviction_components``
          + compute conviction via Vision §4 10-component formula.
       h. Construct ``TripleDecomposition`` (1st defense-in-depth layer;
          ``__post_init__`` raises ConfidenceCapViolation if cap
          violated at construction).
       i. Call ``enforce_confidence_caps`` (2nd defense-in-depth layer;
          raise-helper; defensive — cascade already capped at step f).
       j. Construct ``TripleSigma`` per Vision §5.
       k. Populate ``metric_outputs`` (≥15 keys per L6-H).
       l. Construct ``HorizonResult`` with DMS + Lucas fields exposed.
    4. Stamp replication-kit metadata (6 keys; Vision §14).
    5. Return ``EnsembleResult``.

    Parameters
    ----------
    forecast_inputs
        ``ForecastInputs`` wrapping L5b producer outputs + optional
        L6-E RCF output.
    manual_inputs
        Optional ``ManualInputSchedule``. When provided, recession_p
        overrides flow through L1.7-D
        ``apply_recession_p_override_for_horizon``.
    ood_conditions
        Optional ``OODConditions`` mapping. When None, OOD reserve
        defaults to the 5% floor per Vision §7 + empty reason codes.
    regime_stratified
        If True, uses the regime-stratified horizon cap table; else
        non-stratified.
    valuation_extreme, concentration_extreme, fiscal_risks_elevated,
    reserve_currency_risk
        L6-H D5 risk flags fed to ``select_dms_adjustment_bps`` for
        DMS tier selection at 5Y/10Y. Default False → tier-0
        (-100 bps "structural_edge_persists") at eligible horizons.
    lucas_evidence
        Optional dict mapping Vision §9 reason codes to evidence in
        [0, 1]. Passed to ``compute_lucas_diagnostics``. When None,
        no-evidence diagnostics with ``flag=False`` are produced.
    signal_conflict
        L6-H D2 cap-cascade modifier. When True, overlays Vision §4
        signal-conflict cap 0.75 in the cascade. Default False.

    Returns
    -------
    EnsembleResult
        Multi-horizon aggregate with per-horizon ``HorizonResult``
        entries plus OOD reserve + reason codes + reference-class
        passthrough + replication-kit metadata.

    Raises
    ------
    ConfidenceCapViolation
        If the defense-in-depth pattern catches a cap violation that
        the cascade missed (this should be unreachable in normal
        execution; serves as the institutional discipline surface).
    ValueError
        Range invariants in ``TripleDecomposition`` / ``TripleSigma``
        / ``EnsembleResult``; or invalid n_eff / kappa propagated into
        ``apply_bayesian_shrinkage``; or invalid OOD / Lucas inputs.
    """
    # L6-J D6 — Step 1+2+3 delegated to pure helper (no I/O, deterministic).
    horizon_results, ood_reserve, ood_reason_codes = aggregate_horizons_pure(
        forecast_inputs=forecast_inputs,
        manual_inputs=manual_inputs,
        ood_conditions=ood_conditions,
        regime_stratified=regime_stratified,
        valuation_extreme=valuation_extreme,
        concentration_extreme=concentration_extreme,
        fiscal_risks_elevated=fiscal_risks_elevated,
        reserve_currency_risk=reserve_currency_risk,
        lucas_evidence=lucas_evidence,
        signal_conflict=signal_conflict,
    )

    # Step 4 — replication-kit metadata (Vision §14).
    # L6-J D6: injectable timestamp + code SHA for deterministic replication
    # kits. None defaults preserve L6-H dynamic behaviour.
    if timestamp_utc is not None:
        if not isinstance(timestamp_utc, datetime):
            raise TypeError(
                f"timestamp_utc must be datetime or None; got "
                f"{type(timestamp_utc).__name__}"
            )
        effective_dt = timestamp_utc
    else:
        effective_dt = datetime.now(timezone.utc)
    timestamp = effective_dt.isoformat()

    if code_sha is not None:
        if not isinstance(code_sha, str):
            raise TypeError(
                f"code_sha must be str or None; got "
                f"{type(code_sha).__name__}"
            )
        effective_sha = code_sha
    else:
        effective_sha = _get_code_sha()

    replication_kit_metadata: Dict[str, str] = {
        "code_sha": effective_sha,
        "aggregation_timestamp_iso": timestamp,
        "n_horizons": str(len(SUPPORTED_HORIZONS)),
        "regime_stratified": str(regime_stratified),
        "manual_inputs_applied": str(manual_inputs is not None),
        "ood_reserve_fraction": f"{ood_reserve:.4f}",
    }

    # Step 5 — return EnsembleResult
    return EnsembleResult(
        horizons=horizon_results,
        ood_reserve_fraction=ood_reserve,
        reference_class=forecast_inputs.reference_class,
        replication_kit_metadata=replication_kit_metadata,
        aggregation_timestamp_iso=timestamp,
        ood_reason_codes=ood_reason_codes,
    )
