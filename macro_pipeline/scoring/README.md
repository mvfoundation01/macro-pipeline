# `macro_pipeline.scoring` — Layer 3B+ scoring engines

## §1. Purpose

Production scorers that consume PIT-safe data via `PitDataContext` and
emit a universal `ScoredObservation` record. Today this package
contains the CRPS production scorer (Layer 3B); CDRS arrives in 3C.

| Module | Layer | Output |
|---|---|---|
| `scored_observation.py` | 3B | `ScoredObservation` dataclass + `CompositeBuildError` |
| `crps.py` | 3B | `compute_crps(ctx)` → 12M-forward recession probability |

## §2. Spec deviations (Strategic Claude approved)

The full 6-component CRPS spec lives in §5.2 of `LAYER_3_BUILD_SPEC.md`.
Layer 3B can only load 4 of those 6 components today; the canonical
6-key `EXPERT_COEFFICIENT_PRIORS` (Layer 1.5B.4) remains untouched as
the Layer 5 source of truth, and weights are *redistributed
proportionally* over the active subset for Layer 3.

### D5 — LEI dropped from CRPS Layer 3 (Path B)

| | |
|---|---|
| Spec component | `lei_3d_rule` (Conference Board LEI 6M annualized rate) |
| Spec weight | 0.20 |
| Why dropped | Conference Board LEI is not in any Tier 1-4 loader (paywalled outside CB's monthly free release; not on FRED). The closest available proxy, `PHILLY_LEI_PROXY` (FRED `USSLIND`), is the Philly Fed STATE leading-index aggregate — and `composite_guards.check_double_counting` correctly raises if you try to use it alongside `T10Y3M` because USSLIND already aggregates the term spread. |
| Decision | DROP. Do NOT override the double-counting guard. Do NOT substitute `PHILLY_LEI_PROXY`. |
| Layer 5 follow-up | Source CB LEI through a paid loader (vendor friction, scope-creep risk) and refit with full 6 components. |

### D6 — NAPMNOI dropped from CRPS Layer 3 (Path B)

| | |
|---|---|
| Spec component | `ism_pmi_neworders` (NAPMNOI on FRED) |
| Spec weight | 0.10 |
| Why dropped | FRED returns HTTP 400 *"The series does not exist"* on `NAPMNOI` — ISM's licensing change ~2018 pulled the data from FRED's public API. Verified via `series` and `series/observations` endpoint probes 2026-05-09 (Layer 3B-prep-1). |
| Decision | DROP. Do NOT silently substitute UMCSENT, CFNAIMA3, or any other series. |
| Layer 5 follow-up | Add an alternate ISM Manufacturing PMI New Orders loader (paid feed, or scrape the press release PDFs) and refit with full 6 components. |

## §3. `LAYER3_ACTIVE_COMPONENTS` and the redistribution policy

`LAYER3_ACTIVE_COMPONENTS = ["yield_curve_nyfed", "sahm_rule", "nfci_kcfsi", "hy_oas_regime"]`
`LAYER3_INACTIVE_COMPONENTS = ["lei_3d_rule", "ism_pmi_neworders"]`
`LAYER3_REDISTRIBUTION_METHOD = "proportional"`

Derivation (proportional re-scaling preserves the relative importance
the expert assigned among the surviving components):

```
raw active sum = 0.30 + 0.20 + 0.10 + 0.10 = 0.70

yield_curve_nyfed = 0.30 / 0.70 = 0.4286
sahm_rule         = 0.20 / 0.70 = 0.2857
nfci_kcfsi        = 0.10 / 0.70 = 0.1429
hy_oas_regime     = 0.10 / 0.70 = 0.1429
                                  ──────
                        Σ      =  1.0000
```

`crps_layer3_weights()` returns a `WeightEstimationResult` with
`is_placeholder=True`, `redistribution_method="proportional"`,
`inactive_components=["lei_3d_rule", "ism_pmi_neworders"]`, and
`extra["raw_expert_means"]` carrying the original 6-key dict for
audit. Layer 5 will use the full 6-key `EXPERT_COEFFICIENT_PRIORS` as
Gaussian-prior means in a penalized logistic fit.

## §4. Path B's score envelope (a known reading you should expect)

The 4-component subset has a smaller range than the 6-component spec.
Two structural effects bound the live score:

1. **`yield_curve_nyfed` collapses during recessions.** T10Y3M
   un-inverts as the Fed cuts rates, so the normalized score for that
   component drops to ~0 right when `sahm_rule` / `nfci_kcfsi` /
   `hy_oas_regime` peak. The yield-curve weight (0.4286) effectively
   contributes zero at the recession trough.
2. **The remaining 0.5714 weight caps the recession peak.** Even if
   Sahm = NFCI = HY OAS all normalize to 1.0, peak Path B CRPS is
   `0.4286·0 + 0.2857 + 0.1429 + 0.1429 = 0.572`.

So Layer 3B's recession anchors land in `[0.28, 0.55]` rather than
spec §5.5's `> 0.85` (a 6-component expectation). The Gate 9 contract
asserts:

- (a) **directional** — every recession anchor strictly exceeds every
      calm anchor, AND
- (b) **alert** — at least one recession anchor crosses
      `CRPS_ALERT_THRESHOLDS["moderate"] = 0.40`.

Both are met today (`min_rec=0.2794 > max_calm=0.2437`,
`max_rec=0.5495`).

## §5. `ScoredObservation.metadata_extra` fields populated by `compute_crps`

| Key | Value |
|---|---|
| `regime_state_source` | one of `"nber"`, `"kindleberger_override_nber"`, `"hmm_corroborated"`, `"hmm_dissent_neutralized"` |
| `regime_state_confidence_haircut` | float ∈ {0.00, 0.05, 0.10, 0.20} subtracted from `regime_stability` input of `confidence_score_v2` |
| `weights_method` | `"layer3_expert_prior_subset_proportional"` |
| `weights_is_placeholder` | `True` |
| `inactive_components` | `["lei_3d_rule", "ism_pmi_neworders"]` |
| `redistribution_method` | `"proportional"` |
| `active_components` | `LAYER3_ACTIVE_COMPONENTS` |
| `crps_method` | `"expert_priors_v1_pathB"` |
| `guard_metadata` | dict including the SAHM signal-type acknowledgment (Sahm is COINCIDENT but participates under the explicit-coincident-treatment context tag) |
| `component_indicator_ids` | `{component_name -> indicator_id}` for traceability |

## §6. Layer 5 follow-ups (do NOT do these in Layer 3)

| Item | Trigger |
|---|---|
| Refit weights via penalized logistic regression with Gaussian L2 priors | Always (this is why Layer 3B uses placeholders) |
| Re-include `lei_3d_rule` | Once a CB LEI loader exists and the double-counting graph is updated to allow it without `PHILLY_LEI_PROXY` |
| Re-include `ism_pmi_neworders` | Once an alternate NAPMNOI source is found |
| Revisit redistribution method | If Layer 5 finds proportional rescaling produces unexpected weight allocations on out-of-sample folds |
| Retrain HMM v2 | When a non-UMCSENT activity feature is sourced (see `regime/README.md` §3) |
| Update `crps_method` tag from `"expert_priors_v1_pathB"` to `"ridge_logistic_v1"` | After Layer 5 fit |
