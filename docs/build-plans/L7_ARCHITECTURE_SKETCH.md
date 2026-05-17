# L7 Architecture Sketch (pre-staged at L6-K per ACCELERATION PROTOCOL v1.0)

**Authored**: 2026-05-16 at L6-K ACCEPT (Strategic Track B + Track A pre-staging)
**Status**: SKETCH only; no functional implementation at L6-K. Skeleton `__init__.py` modules created in `macro_pipeline/scheduler/` and `macro_pipeline/alerting/` to establish import surface.
**Effort estimate (single sub-phase L7)**: thirty to fifty hours nominal / twelve to twenty hours convergence-adjusted (per L6 minus sixty percent rolling prior).

---

## §1 — L7 mission (per Vision v2.1 + Strategic ACCELERATION PROTOCOL v1.0)

L7 is the **scheduling + alerting + producer-integration** layer. Per ACCELERATION PROTOCOL v1.0 (V mandate 2026-05-16), L7 ships as a **single comprehensive sub-phase** rather than the original L7-A through L7-G decomposition. Quality preserved via:
- Vision-binding formula adherence (already in place at L6-H/J)
- Defense-in-depth six-layer cascade preserved (PD20 invariant)
- AP-AUTH discipline (path-prefix + push verification + reviewer-driven)
- ACCEPT gate criteria at end of single L7 sub-phase

### L7 mission breakdown

1. **Scheduling**: periodic refresh of L6 forecast pipeline (daily/weekly/monthly cron with APScheduler or similar)
2. **Alerting**: detection + dispatch for regime shifts, threshold breaches, OOD events
3. **Component producers**: replace placeholder-neutral confidence + conviction components with producer-backed values (closes L6-J carry-forward MEDIUM finding)
4. **Eleven-model distinct producers**: replace `wrap_point_estimates_as_model_signals` placeholder with eleven actual model_id producers per ChatGPT R7 #5 scope
5. **Lucas structural-break detectors**: per-reason-code detection (L6-H accepted evidence dict; L7 ships detectors)
6. **Triple sigma runtime validity detectors**: vol cluster + structural break + policy shock (L6-J accepted optional flags; L7 ships detectors)
7. **Replication kit serialization**: full JSON-serializable `EnsembleResult` for download-and-reproduce workflows (Vision §14 partial closure)

---

## §2 — L7 single-sub-phase scope (ACCELERATION lever #4)

The original Strategic Track B disposition called for L7-A through L7-G decomposition. ACCELERATION PROTOCOL v1.0 collapses this into **one sub-phase** with the following deliverables (D1 through approximately D10):

| # | Deliverable | Scope |
|---|---|---|
| D1 | `macro_pipeline/scheduler/` module | APScheduler integration + cron jobs for L6 aggregator refresh; environment-variable-driven schedule |
| D2 | `macro_pipeline/alerting/` module | Detection logic (regime shift, threshold breach, OOD event) + dispatch backends (email, Slack, webhook) |
| D3 | Confidence component producers | three L7 producers replacing PLACEHOLDER_NEUTRAL in `derive_confidence_components`: data_quality, model_agreement, regime_stability |
| D4 | Conviction component producers | nine L7 producers replacing PLACEHOLDER_NEUTRAL in `derive_conviction_components`: edge_score, asymmetry_score, model_agreement (mirrors D3), valuation_support, trend_confirmation, liquidity_support, tail_risk_penalty, crowding_penalty, policy_uncertainty_penalty |
| D5 | Eleven distinct model producers | Replace `wrap_point_estimates_as_model_signals` with eleven actual model_id producers per `MODEL_IDS` tuple; each producer reads upstream L4/L5 outputs + computes per-model point estimate + sigma + confidence |
| D6 | Lucas critique structural-break detectors | Seven detectors mapping to Vision §9 reason codes (fed_reaction_shift, fiscal_dominance, balance_sheet_dominance, nbfi_transmission, ai_productivity_shift, inflation_target_credibility, treasury_issuance_structure) |
| D7 | Triple sigma validity detectors | Four detectors mapping to `SIGMA_VALIDITY_REASON_CODES` (vol_cluster, structural_break, policy_shock, realized_vol_ratio) |
| D8 | Replication kit serialization | `EnsembleResult.to_replication_kit_dict()` + `from_replication_kit_dict()` with full lossless round-trip; YAML/JSON export helpers |
| D9 | Integration tests | End-to-end pipeline tests covering scheduler trigger → producer execution → L6 aggregation → alert dispatch |
| D10 | L7 retrospective + L8a prep | Closure document + L8a UI architecture sketch (UI scope deferred to L8a sprint) |

Test target: plus eighty to one hundred fifty new tests; cumulative pytest target 1214 to 1284 collected.

---

## §3 — Component producer integration discipline (D3 + D4)

Each placeholder component slot has a defined producer plan in `macro_pipeline/ensemble/data/component_producer_roadmap.yaml`. L7 implementation maps producer plan to actual code:

### Confidence components (three L7 producers; three currently empirical at L6-J)

| Slot | Status at L6 | L7 producer scope |
|---|---|---|
| `data_quality` | placeholder | FRED vintage age + indicator coverage completeness + outlier-flag count + missing-data rate → normalized to [0, 1] |
| `model_agreement` | placeholder | Eleven-model ensemble dispersion (post-D5); 1 minus normalized stdev of point_estimate_annualized across `MODEL_IDS` at horizon |
| `regime_stability` | placeholder | Extend `rcf.py` with regime_classifier output; (1) regime-transition probability + (2) regime persistence depth |
| `analog_strength` | empirical (L6-E) | unchanged at L7 |
| `sample_size_adequacy` | empirical (L6-H) | unchanged at L7 |
| `ood_penalty` | empirical (L6-H) | unchanged at L7 |

### Conviction components (nine L7 producers; one empirical at L6-H)

| Slot | Status at L6 | L7 producer scope |
|---|---|---|
| `edge_score` | placeholder | Sharpe-like normalized score: forecast vs risk-free benchmark |
| `asymmetry_score` | placeholder | VIX/SKEW/put-call-implied right-tail vs left-tail dispersion |
| `model_agreement` | placeholder | Same producer as confidence variant; reused |
| `valuation_support` | placeholder | CAPE/Tobin/ERP percentile classifier oriented by forecast direction |
| `trend_confirmation` | placeholder | 50/200 DMA + breadth + momentum diagnostics from L4 composite |
| `liquidity_support` | placeholder | FCI + credit spreads + funding-liquidity diagnostics |
| `tail_risk_penalty` | placeholder | VaR/CVaR breach probability from forecast distribution |
| `crowding_penalty` | placeholder | CFTC + dealer gamma + AAII bull-bear extremes |
| `policy_uncertainty_penalty` | placeholder | Fed reaction-function shift signals (partial integration via L6-H Lucas diagnostics) |
| `forecast_decay_penalty` | empirical (L6-H horizon decay table) | L8a UI-driven decay model future refinement |

---

## §4 — Module skeleton (created at L6-K; populated at L7)

The two new modules established at L6-K are empty stubs with placeholder docstrings:

```
macro_pipeline/scheduler/__init__.py    # L7 scheduling module; empty at L6-K
macro_pipeline/alerting/__init__.py     # L7 alerting module; empty at L6-K
```

No functional code at L6-K. The `__init__.py` files exist solely to establish the import surface so that L7 producer code can import from `macro_pipeline.scheduler` and `macro_pipeline.alerting` namespaces without requiring package-tree restructuring at L7 time.

---

## §5 — L8a prep (carry-forward from L7)

L7 D10 includes a brief L8a UI architecture sketch (analogous to D7 here). L8a will be authored as **L8a single sub-phase** per ACCELERATION PROTOCOL v1.0 lever #5 (L8b plus L8c may be parallelizable post-L8a). The L8a UI scope is OUT OF SCOPE for L7; L7 D10 only sketches it.

L8a high-level (preliminary; subject to L7 retrospective refinement):

- L8a-1 Forecast dashboard (Vision §11/12 progressive disclosure)
- L8a-2 Drill-down to L1/L2/L3 explanation stack
- L8a-3 Universal glossary + tooltips
- L8a-4 Storytelling mode auto-generated narratives
- L8a-5 Basic alerts UI surfacing L7 alerting backend
- L8a-6 Search-driven exploration

L8b (Academic features) + L8c (Educational features) target completion per Vision §15: 2026-08-31 + 2026-09-30 respectively.

---

## §6 — Effort estimate + V's quality-preserving acceleration rationale

| Original plan (L7-A through L7-G) | ACCELERATION v1.0 (L7 single) |
|---|---|
| Approximately seventy hours nominal across seven sub-phases | Approximately thirty to fifty hours nominal as one sub-phase |
| Approximately twenty-five to thirty hours convergence-adjusted | Approximately twelve to twenty hours convergence-adjusted |
| Seven ACCEPT cycles | One ACCEPT cycle |

Quality preservation per V mandate 2026-05-16:
- Vision §4 BINDING formulas already in place at L6 (no regression risk in single L7 sub-phase)
- Defense-in-depth six-layer cascade preserved (PD20)
- AP-AUTH register discipline maintained (path-prefix + push verification)
- R7 reviewer cycle equivalent: L7 ACCEPT itself is the integration verification (R8 SKIP per L6-K mandate; if V requests R8, dispatch at L7 ACCEPT)

Net effort savings: approximately twenty to thirty hours wall-clock vs original L7-A..L7-G decomposition; quality preserved.
