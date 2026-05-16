"""Ensemble aggregator — end-to-end forecast pipeline (L6-F).

Per Strategic L6-F inline pre-flight 2026-05-15 + Pipeline Guide v2.0 §7
+ Vision v2.0 §4 (Triple Probability Decomposition) + §5 (Triple sigma
Reporting) + §6 (Reference Class Forecasting) + §7 (OOD Reserve) +
§10 (Sample Size Honesty) + §14 (Replication & Audit).

The aggregator integrates the L6-A through L6-E primitives with L5b
producer outputs and L1.7 ManualInputSchedule into a single multi-
horizon ``EnsembleResult``:

  L6-A  MetricMetadata registry (90 measurements per Vision §3)
  L6-B  TripleDecomposition (1st defense-in-depth cap layer)
  L6-C  TripleSigma (Triple sigma Reporting per Vision §5)
  L6-D  compute_ood_reserve + enforce_confidence_caps (2nd cap layer)
  L6-E  apply_bayesian_shrinkage (Vision §6; 10Y prior 0.065)
  L5b   producers wrapped via ``ForecastInputs``
  L1.7  ManualInputSchedule via macro_pipeline.manual_input.integration

Defense-in-depth confidence cap (3rd INSTANCE of pattern)
----------------------------------------------------------
The L6-F aggregator is the 3rd instance of the two-layer cap-enforcement
pattern in the codebase:

  1st instance  L1.7-B value-level (validate_schedule V5) +
                L1.7-D forecast-time (enforce_forecast_time_confidence_cap)
                at the MANUAL_INPUT layer
  2nd instance  L6-B construction-time (TripleDecomposition __post_init__)
                + L6-D standalone helper (enforce_confidence_caps) at the
                ENSEMBLE primitive layer
  3rd instance  L6-F aggregator (THIS MODULE) — calls TripleDecomposition
                construction (1st layer) THEN explicit
                enforce_confidence_caps (2nd layer) per horizon

The 3rd instance differs from the 2nd in CALL CONTEXT (aggregator uses
both layers as a deliberate pipeline step rather than the two-layer
pair being independent surfaces). AP-AUTH-46 gratuitous-codification
guard: pattern is fully matured by the 3rd instance; AP-AUTH-56
codification scheduled at L6-H sprint retrospective per Strategic.

Placeholder confidence/conviction logic (L6-F scope; L6-G refines)
------------------------------------------------------------------
At L6-F the confidence + conviction computations are HEURISTIC
placeholders:

  confidence_uncapped = min(0.5 + 0.05 * (n_eff / 30.0), 0.99)
  confidence          = min(confidence_uncapped, horizon_cap)
  conviction          = 1.0 + confidence * 9.0  # linear [1, 10]

L6-G will refine the confidence formula to follow Vision §4 BINDING
(Data Quality + Model Agreement + Regime Stability + Analog Strength
+ Sample Size minus OOD Penalty) and the conviction formula to include
the asymmetry / valuation / trend / tail-risk / crowding / policy /
decay components. The placeholder logic at L6-F is explicitly flagged
in the aggregator docstring + commit message + R7 invocation for
ChatGPT 5.5 methodology review.

Confidence cap regime
---------------------
Standing Order #9 + Vision §10 + L5b-F F-H2:

  horizon  cap (non-stratified)  cap (regime-stratified)
       1                  0.85                    0.85
       3                  0.85                    0.85
       5                  0.85                    0.85
      10                  0.70                    0.55

The 1Y/3Y/5Y cap of 0.85 reflects Vision §10 Sample Size Honesty
(roughly 113 / 38 / 22 non-overlapping windows since 1913); the 10Y
cap of 0.70 / 0.55 reflects the revised-down honest assessment given
N ~ 11 non-overlapping windows + autocorrelation per Vision §10.

Public API
----------
``ForecastInputs``       Frozen wrapper for L5b producer outputs.
``HorizonResult``        Frozen per-horizon ensemble result.
``EnsembleResult``       Frozen multi-horizon aggregate.
``aggregate_ensemble``   Pure function — end-to-end aggregation.
``SUPPORTED_HORIZONS``   ``(1, 3, 5, 10)`` per Vision §1 Pillar 4.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from macro_pipeline.ensemble.ood_and_caps import (
    OODConditions,
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

# Vision §10 Sample Size Honesty: 1Y/3Y/5Y cap.
SHORT_HORIZON_CONFIDENCE_CAP = 0.85

# OOD reserve floor when no conditions provided (Vision §7).
OOD_RESERVE_FLOOR_DEFAULT = 0.05


@dataclass(frozen=True)
class ForecastInputs:
    """Wraps L5b producer outputs + optional L6-E RCF output for aggregator.

    Per Strategic PD2. All per-horizon dicts must contain every horizon
    in ``SUPPORTED_HORIZONS``; ``__post_init__`` validates membership.

    Fields
    ------
    point_estimates           horizon -> central return forecast (float)
    point_estimate_n_eff      horizon -> effective sample size (int)
    forecast_sigmas           horizon -> forecast error sigma (float)
    analog_dispersions        horizon -> analog dispersion sigma (float)
    return_sigmas             horizon -> annualized return sigma (float)
    recession_probabilities   horizon -> P(recession) in [0, 1] (float)
    reference_class           optional L6-E RCF output (passes through)
    dms_adjustments           optional horizon -> DMS bps (passes through)
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


@dataclass(frozen=True)
class HorizonResult:
    """Per-horizon ensemble result. Per Strategic PD4.

    Fields
    ------
    horizon                       1 / 3 / 5 / 10
    triple_decomposition          L6-B TripleDecomposition with cap enforced
    triple_sigma                  L6-C TripleSigma
    metric_outputs                metric_id -> float (minimum 8 keys per PD15;
                                  L6-G expands coverage to Vision §3 90 measures)
    bayesian_shrinkage_applied    True at 10Y (Vision §6 prior); False otherwise
    shrinkage_n_eff               n_eff used in shrinkage; None if not applied
    """

    horizon: int
    triple_decomposition: TripleDecomposition
    triple_sigma: TripleSigma
    metric_outputs: Dict[str, float]
    bayesian_shrinkage_applied: bool
    shrinkage_n_eff: Optional[int] = None


@dataclass(frozen=True)
class EnsembleResult:
    """Multi-horizon ensemble forecast. Per Strategic PD5.

    Fields
    ------
    horizons                     dict mapping {1, 3, 5, 10} -> HorizonResult
    ood_reserve_fraction         in [0.05, 0.15] per Vision §7
    reference_class              passes through from ForecastInputs (Vision §6)
    replication_kit_metadata     6 keys per Strategic PD16 (Vision §14)
    aggregation_timestamp_iso    UTC ISO 8601 timestamp
    """

    horizons: Dict[int, HorizonResult]
    ood_reserve_fraction: float
    reference_class: Optional[ReferenceClass]
    replication_kit_metadata: Dict[str, str]
    aggregation_timestamp_iso: str

    def __post_init__(self) -> None:
        if set(self.horizons.keys()) != set(SUPPORTED_HORIZONS):
            raise ValueError(
                f"EnsembleResult.horizons keys "
                f"{sorted(self.horizons.keys())} != supported "
                f"{sorted(SUPPORTED_HORIZONS)}"
            )
        if not (0.05 <= self.ood_reserve_fraction <= 0.15):
            raise ValueError(
                f"ood_reserve_fraction {self.ood_reserve_fraction} "
                f"out of [0.05, 0.15] per Vision §7"
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


def aggregate_ensemble(
    forecast_inputs: ForecastInputs,
    manual_inputs: Optional[ManualInputSchedule] = None,
    ood_conditions: Optional[OODConditions] = None,
    regime_stratified: bool = False,
) -> EnsembleResult:
    """End-to-end ensemble aggregation per Strategic L6-F PD7.

    Pipeline
    --------
    1. Compute OOD reserve from ``ood_conditions`` (or floor 0.05).
    2. For each horizon in ``SUPPORTED_HORIZONS``:
       a. Read point estimate + n_eff from forecast_inputs.
       b. Apply manual recession_p override via L1.7-D helper if
          ``manual_inputs`` provided.
       c. Apply Bayesian shrinkage at 10Y (prior 0.065 per Vision §6).
       d. Compute confidence (placeholder; L6-G refines per Vision §4).
       e. Apply Standing Order #9 cap at 10Y (0.70 / 0.55); apply
          Vision §10 cap at 1Y/3Y/5Y (0.85).
       f. Compute conviction (placeholder; L6-G refines).
       g. Construct ``TripleDecomposition`` (1st defense-in-depth layer;
          ``__post_init__`` raises ConfidenceCapViolation if cap
          violated at construction).
       h. Call ``enforce_confidence_caps`` (2nd defense-in-depth layer;
          raises same exception class if propagated confidence > cap).
       i. Construct ``TripleSigma`` per Vision §5.
       j. Populate ``metric_outputs`` (8+ keys per PD15;
          ``dms_adjustment_bps`` added when ``dms_adjustments``
          provided).
    3. Stamp replication-kit metadata (6 keys per PD16; Vision §14).
    4. Return ``EnsembleResult``.

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
        defaults to the 5% floor per Vision §7.
    regime_stratified
        If True, uses the 0.55 regime-stratified 10Y cap; else 0.70.

    Returns
    -------
    EnsembleResult
        Multi-horizon aggregate with per-horizon ``HorizonResult``
        entries for ``SUPPORTED_HORIZONS`` plus OOD reserve plus
        reference-class passthrough plus replication-kit metadata.

    Raises
    ------
    ConfidenceCapViolation
        If any horizon's computed confidence exceeds the applicable
        cap (defense-in-depth either layer fires).
    ValueError
        Range invariants in ``TripleDecomposition`` /
        ``TripleSigma`` / ``EnsembleResult``; or invalid n_eff /
        kappa propagated into ``apply_bayesian_shrinkage``.
    """
    # Step 1 — OOD reserve
    if ood_conditions is None:
        ood_reserve = OOD_RESERVE_FLOOR_DEFAULT
    else:
        ood_reserve = compute_ood_reserve(ood_conditions)

    horizon_results: Dict[int, HorizonResult] = {}

    for horizon in SUPPORTED_HORIZONS:
        # Step 2a — point estimate + n_eff
        point = forecast_inputs.point_estimates[horizon]
        n_eff = forecast_inputs.point_estimate_n_eff[horizon]

        # Step 2b — manual recession_p override (L1.7-D integration)
        recession_p = forecast_inputs.recession_probabilities[horizon]
        if manual_inputs is not None:
            # Lazy import keeps top-of-module import graph minimal +
            # mirrors L5b surface modifications precedent at L1.7-D.
            from macro_pipeline.manual_input.integration import (
                apply_recession_p_override_for_horizon,
            )
            recession_p = apply_recession_p_override_for_horizon(
                manual_inputs, horizon, recession_p
            )

        # Step 2c — Bayesian shrinkage at 10Y only (Vision §6)
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

        # Step 2d — confidence placeholder (L6-G refines per Vision §4)
        confidence_uncapped = min(0.5 + 0.05 * (n_eff / 30.0), 0.99)

        # Step 2e — horizon-conditional cap (Standing Order #9 + Vision §10)
        if horizon == 10:
            cap = 0.55 if regime_stratified else 0.70
            confidence = min(confidence_uncapped, cap)
        else:
            confidence = min(
                confidence_uncapped, SHORT_HORIZON_CONFIDENCE_CAP
            )

        # Step 2f — conviction placeholder (L6-G refines per Vision §4)
        conviction = 1.0 + confidence * 9.0

        # Step 2g — TripleDecomposition (defense-in-depth 1st layer)
        triple_decomp = TripleDecomposition(
            probability=recession_p,
            confidence=confidence,
            conviction=conviction,
            horizon=horizon,
            regime_stratified=regime_stratified,
        )

        # Step 2h — enforce_confidence_caps (defense-in-depth 2nd layer)
        enforce_confidence_caps(confidence, horizon, regime_stratified)

        # Step 2i — TripleSigma (Vision §5)
        triple_sigma = TripleSigma(
            return_sigma=forecast_inputs.return_sigmas[horizon],
            forecast_error_sigma=forecast_inputs.forecast_sigmas[horizon],
            analog_dispersion_sigma=forecast_inputs.analog_dispersions[
                horizon
            ],
            horizon=horizon,
        )

        # Step 2j — metric_outputs (8+ keys; PD15)
        metric_outputs: Dict[str, float] = {
            "point_estimate_return": point,
            "recession_probability": recession_p,
            "confidence": confidence,
            "conviction": conviction,
            "n_eff": float(n_eff),
            "return_sigma": forecast_inputs.return_sigmas[horizon],
            "forecast_error_sigma": forecast_inputs.forecast_sigmas[
                horizon
            ],
            "analog_dispersion_sigma": forecast_inputs.analog_dispersions[
                horizon
            ],
        }
        if (
            forecast_inputs.dms_adjustments is not None
            and horizon in forecast_inputs.dms_adjustments
        ):
            metric_outputs["dms_adjustment_bps"] = float(
                forecast_inputs.dms_adjustments[horizon]
            )

        horizon_results[horizon] = HorizonResult(
            horizon=horizon,
            triple_decomposition=triple_decomp,
            triple_sigma=triple_sigma,
            metric_outputs=metric_outputs,
            bayesian_shrinkage_applied=bayesian_applied,
            shrinkage_n_eff=shrinkage_n_eff,
        )

    # Step 3 — replication-kit metadata (Vision §14)
    timestamp = datetime.now(timezone.utc).isoformat()
    replication_kit_metadata: Dict[str, str] = {
        "code_sha": _get_code_sha(),
        "aggregation_timestamp_iso": timestamp,
        "n_horizons": str(len(SUPPORTED_HORIZONS)),
        "regime_stratified": str(regime_stratified),
        "manual_inputs_applied": str(manual_inputs is not None),
        "ood_reserve_fraction": f"{ood_reserve:.4f}",
    }

    # Step 4 — return EnsembleResult
    return EnsembleResult(
        horizons=horizon_results,
        ood_reserve_fraction=ood_reserve,
        reference_class=forecast_inputs.reference_class,
        replication_kit_metadata=replication_kit_metadata,
        aggregation_timestamp_iso=timestamp,
    )
