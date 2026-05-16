"""L6-G one-shot helper: populate metrics_registry.yaml computation_path
and deferred_to fields.

Track A maps clear L1-L5b producer linkages; remaining measures deferred to
L7 (forecast-time aggregation / portfolio-level / time-series helpers) or
L8a (UI surfacing of statistical primitives). Per Strategic L6-G PD3:
target ~70 measures populated; ~20 deferred.

This file is a one-shot helper for the L6-G commit and may be removed at
L6-H cleanup if desired.
"""
from dataclasses import replace

from macro_pipeline.ensemble.registry import (
    DEFAULT_REGISTRY_PATH,
    load_metrics_registry,
    save_metrics_registry,
)

# ---------------------------------------------------------------------------
# Computation path mappings (L1-L5b producers; Track A judgment per PD2)
# ---------------------------------------------------------------------------
COMPUTATION_PATHS = {
    # §3.2 Uncertainty
    "forecast_error_sigma": (
        "macro_pipeline/analysis/forecast_sigma.py:derive_forecast_sigma_v2"
    ),
    "analog_dispersion_sigma": (
        "macro_pipeline/ensemble/aggregator.py:populate_metric_outputs"
    ),
    # §3.3 Confidence + Conviction
    "probability_numeric": (
        "macro_pipeline/ensemble/aggregator.py:aggregate_ensemble"
    ),
    "confidence_score_pct": (
        "macro_pipeline/ensemble/bayesian_confidence.py:compute_bayesian_confidence"
    ),
    "conviction_score": (
        "macro_pipeline/ensemble/bayesian_confidence.py:compute_conviction_score"
    ),
    # §3.4 Goodness-of-fit + Calibration
    "brier_score": (
        "macro_pipeline/analysis/brier_reliability.py:BrierDecomposition"
    ),
    "brier_improvement_vs_climatology": (
        "macro_pipeline/analysis/brier_reliability.py:BrierDecomposition"
    ),
    "calibration_slope": (
        "macro_pipeline/models/isotonic_calibrator.py:IsotonicCalibrationResult"
    ),
    "reliability_diagram": (
        "macro_pipeline/analysis/brier_reliability.py:BrierDecomposition"
    ),
    "crps": "macro_pipeline/scoring/crps.py",
    "adjusted_r_squared": "macro_pipeline/analysis/r_squared_panel.py",
    "r_squared": "macro_pipeline/analysis/r_squared_panel.py",
    # §3.5 Statistical significance
    "p_value_raw": "macro_pipeline/analysis/newey_west_hac.py:fit_ols_hac",
    "p_value_hac_adjusted": "macro_pipeline/analysis/newey_west_hac.py:fit_ols_hac",
    "q_value_bh_fdr": (
        "macro_pipeline/analysis/fdr_gating.py:FDRGatingDiagnostics"
    ),
    "effective_sample_size": (
        "macro_pipeline/analysis/effective_sample_size.py:n_eff_nonoverlap"
    ),
    "test_statistic": (
        "macro_pipeline/models/return_forecast.py:StructuralBreakDiagnostics"
    ),
    # §3.6 Bias correction
    "dms_survivorship_adjustment": (
        "macro_pipeline/models/dms_adjustment.py:apply_dms_adjustment"
    ),
    "bayesian_shrinkage_lambda": (
        "macro_pipeline/models/composite_refit.py:fit_composite_weights"
    ),
    "bootstrap_bias_estimate": (
        "macro_pipeline/models/return_forecast.py:BootstrapDiagnostics"
    ),
    "ood_reserve_mass": (
        "macro_pipeline/ensemble/ood_and_caps.py:compute_ood_reserve"
    ),
    "look_ahead_bias_check": "macro_pipeline/preprocessing.py:validate_ingest",
    "survivorship_bias_check": (
        "macro_pipeline/models/dms_adjustment.py:apply_dms_adjustment"
    ),
    # §3.8 Time-series quality
    "structural_break_supw": (
        "macro_pipeline/models/return_forecast.py:StructuralBreakDiagnostics"
    ),
    # §3.11 Macro-specific (loaders)
    "cape_percentile": "macro_pipeline/loaders/shiller.py",
    "equity_risk_premium": "macro_pipeline/loaders/damodaran_erp.py",
    "acm_term_premium": "macro_pipeline/loaders/acm_termpremium.py",
    "real_rate_vs_rstar": "macro_pipeline/loaders/hlw_rstar.py",
    "ccc_bb_credit_spread": "macro_pipeline/loaders/ebp.py",
    "ny_fed_recession_probit": "macro_pipeline/loaders/nyfed_recprob.py",
    "buffett_indicator": "macro_pipeline/loaders/fred_loader.py",
    "tobin_q": "macro_pipeline/loaders/fred_vintage_panel.py",
    # §3.12 Regime-conditional
    "recession_window_brier_improvement": (
        "macro_pipeline/analysis/regime_conditional_validation.py:RegimeConditionalDiagnostics"
    ),
    "expansion_window_brier_improvement": (
        "macro_pipeline/analysis/regime_conditional_validation.py:RegimeConditionalDiagnostics"
    ),
    "regime_sensitivity_flag": (
        "macro_pipeline/analysis/regime_conditional_validation.py:RegimeConditionalDiagnostics"
    ),
    "regime_transition_probability": (
        "macro_pipeline/regime/nber_extract.py:NberStateResult"
    ),
    "nber_pre1978_handling": "macro_pipeline/regime/nber_extract.py",
    "lei_3d_rule_trigger": "macro_pipeline/loaders/fred_loader.py",
    "sahm_rule_reading": "macro_pipeline/loaders/fred_loader.py",
    "ism_mfg_new_orders_threshold": "macro_pipeline/loaders/fred_loader.py",
}

# ---------------------------------------------------------------------------
# Deferred to L7 (portfolio / forecast-time) or L8a (UI primitives)
# ---------------------------------------------------------------------------
DEFERRED = {
    # §3.1 Probability primitives surface in L8a UI
    "cumulative_distribution_function": "L8a",
    "probability_conditional": "L8a",
    "probability_joint": "L8a",
    "probability_outcome": "L8a",
    "probability_union": "L8a",
    "quantile_function": "L8a",
    "survival_function": "L8a",
    "tail_probability": "L8a",
    # §3.2 Uncertainty primitives
    "confidence_interval": "L8a",
    "credible_interval": "L7",
    "highest_posterior_density": "L7",
    "prediction_interval": "L7",
    "standard_deviation": "L8a",
    # §3.3 Trading-action measures (portfolio scope)
    "edge": "L7",
    "kelly_fraction": "L7",
    "fractional_kelly": "L7",
    # §3.4 Calibration extras
    "sharpness": "L7",
    "auc_roc": "L7",
    "log_loss": "L7",
    # §3.5 Significance extras (UI surfacing)
    "degrees_of_freedom": "L8a",
    "statistical_power": "L8a",
    "type_i_error_alpha": "L8a",
    "type_ii_error_beta": "L8a",
    # §3.7 Risk measures — portfolio-level (L7 scope)
    "beta": "L7",
    "calmar_ratio": "L7",
    "conditional_value_at_risk": "L7",
    "information_ratio": "L7",
    "maximum_drawdown": "L7",
    "sharpe_ratio": "L7",
    "sortino_ratio": "L7",
    "tail_dependence": "L7",
    "value_at_risk": "L7",
    # §3.8 Time-series quality extras
    "adf_stationarity_test": "L7",
    "autocorrelation_rho": "L7",
    "cointegration_test": "L7",
    "granger_causality": "L7",
    "hurst_exponent": "L7",
    # §3.9 Information theory — all deferred
    "cross_entropy": "L7",
    "kl_divergence": "L7",
    "mutual_information": "L7",
    "shannon_entropy": "L7",
    # §3.10 Bayesian extras (L7 MCMC stack)
    "bayes_factor": "L7",
    "likelihood_function": "L7",
    "map_estimate": "L7",
    "marginal_likelihood": "L7",
    "mcmc_r_hat": "L7",
    "posterior_theta": "L7",
    "prior_theta": "L7",
    # §3.6 Bias correction extras
    "bonferroni_correction": "L7",
    # §3.11 Macro-specific extras (no current loader)
    "hussman_mape": "L7",
}


def main() -> None:
    """Update the in-tree registry YAML with computation_path / deferred_to."""
    reg = load_metrics_registry()
    mapped = 0
    deferred = 0
    for metric_id, meta in list(reg.items()):
        computation_path = COMPUTATION_PATHS.get(metric_id)
        deferred_to = DEFERRED.get(metric_id)
        if computation_path or deferred_to:
            reg[metric_id] = replace(
                meta,
                computation_path=computation_path,
                deferred_to=deferred_to,
            )
            if computation_path:
                mapped += 1
            elif deferred_to:
                deferred += 1
    print(f"computation_path populated: {mapped}")
    print(f"deferred_to populated:      {deferred}")
    print(f"Total covered:              {mapped + deferred} / 90")
    save_metrics_registry(reg, DEFAULT_REGISTRY_PATH)
    print("Registry saved.")


if __name__ == "__main__":
    main()
