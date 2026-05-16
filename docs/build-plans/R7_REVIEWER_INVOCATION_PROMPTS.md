# R7 External Reviewer Invocation Prompts

**Trigger commit (current)**: `l6-g-accept` (commit SHA `97ada00c1dab52f9edd86312ce8e923fa3af5698`; resolve via `git rev-parse l6-g-accept`).
**Trigger date (current)**: 2026-05-16 (R7-bis sync upgrade post-L6-G ACCEPT).
**Original dispatch (audit footnote)**: R7 reviewers were initially dispatched on 2026-05-15 against `l6-f-accept` (SHA `f2c963b09ca23b2538b0c7e54d66a77aaf1fc333`); fetch target upgraded to `l6-g-accept` on 2026-05-16 after the L6-G Bayesian confidence and conviction refinement landed. See §Addendum L6-G at bottom of this document for the full upgrade scope. Reviewers MAY re-fetch at `l6-g-accept` if review has not yet started, OR finalize verdict at `l6-f-accept` if review is already in progress (both states are ACCEPTed; reviewers choose at their discretion).
**Reviewers**: Codex 5.5 (code review) plus ChatGPT 5.5 (methodology review).
**Dispatch model**: V copies each invocation prompt to the respective reviewer in parallel.
**Expected wall-clock**: three to seven days for both verdicts.
**Findings closure path**: HIGH findings block L6-H closure; MEDIUM findings close at L6-G or L6-H per Strategic disposition; OPERATIONAL findings are informal backlog (no closure required).
**Authority documents on-branch** (post-L6-PREP cherry-pick from main): `docs/build-plans/00_VISION_AND_PHILOSOPHY_v2.md`, `docs/build-plans/01_CLAUDE_CODE_PIPELINE_GUIDE_v2.md`, `docs/build-plans/02_CHATGPT_METHODOLOGY_REVIEW_v2.md`, `docs/build-plans/03_CODEX_CODE_REVIEW_v2.md`, `docs/build-plans/04_STRATEGIC_PM_INSTRUCTIONS_v2.md`.

---

## §1 — Codex 5.5 invocation prompt (paste verbatim to Codex 5.5)

````text
# Codex 5.5 — R7 Code Review of L6 Ensemble Aggregation Layer

You are Codex 5.5, performing external code review of the macro pipeline
L6 ensemble aggregation layer at tag `l6-g-accept` (upgraded from initial
`l6-f-accept` dispatch on 2026-05-16; see audit footnote and §Addendum L6-G
at the top and bottom of this document).

## Authority document
- `docs/build-plans/03_CODEX_CODE_REVIEW_v2.md` (your role plus verdict format)
- `docs/ap_register.md` (AP-AUTH register entries one through fifty-five
  for institutional context, plus the L6-PREP sync-event note appended
  after AP-AUTH-55)

## Fetch plus checkout
```
git fetch origin
git checkout l6-g-accept
```

Per AP-AUTH-55 push verification: confirm `git log origin/claude/layer-5-build -1`
shows the same SHA as `git rev-parse l6-g-accept` before substantive review
begins.

## Review scope

### Code review (entire L6 layer plus integration surfaces)

L6 ensemble package (`macro_pipeline/ensemble/`):
- `metadata.py` plus `registry.py` (L6-A; MetricMetadata frozen dataclass
  plus YAML registry I/O; ninety-measurement catalogue per Vision section three)
- `triple_decomposition.py` (L6-B; defense-in-depth cap enforcement first layer)
- `triple_sigma.py` (L6-C; Triple sigma Reporting plus cumulative scaling caveats)
- `ood_and_caps.py` (L6-D; defense-in-depth cap enforcement second layer plus
  OOD reserve helper)
- `rcf.py` (L6-E; Reference Class Forecasting; eight-dimensional macro state
  vector plus cosine similarity plus Bayesian shrinkage)
- `aggregator.py` (L6-F; end-to-end ensemble aggregation; defense-in-depth
  third instance of the pattern)
- `data/metrics_registry.yaml` (ninety measurements across twelve
  subcategories per Vision section three)

Test suites:
- `tests/test_ensemble_metadata.py` (L6-A; twelve tests)
- `tests/test_triple_decomposition.py` (L6-B; eleven tests)
- `tests/test_triple_sigma.py` (L6-C; twelve tests)
- `tests/test_ood_and_caps.py` (L6-D; fourteen tests)
- `tests/test_rcf.py` (L6-E; twenty-five tests)
- `tests/test_aggregator.py` (L6-F; thirty tests including
  test_aggregate_defense_in_depth_both_layers_fire as the third-instance
  verification)

Integration surfaces:
- `macro_pipeline/manual_input/` (L1.7 layer; L6-F aggregator wires
  `apply_recession_p_override_for_horizon` from `manual_input.integration`)
- L5b producer outputs (RidgeFitResult, ForecastSigmaResult,
  RegimeConditionalDiagnostics) consumed via the L6-F ForecastInputs
  wrapper; the aggregator does NOT modify L5b producers (additive only)

## Critical institutional invariants to verify

1. **Confidence cap defense-in-depth (Standing Order number nine)** —
   - First layer: TripleDecomposition `__post_init__` (construction-time;
     raises `ConfidenceCapViolation` if confidence exceeds horizon-specific cap)
   - Second layer: `enforce_confidence_caps` standalone helper (forecast-time;
     raises same exception class on bare-float input)
   - Third instance: L6-F aggregator pipeline calls both layers per horizon
     (TripleDecomposition construction then explicit enforce_confidence_caps
     in `aggregate_ensemble`)
   - Ten-year cap: seventy percent non-stratified; fifty-five percent
     regime-stratified
   - One-year / three-year / five-year cap: eighty-five percent per Vision
     section ten Sample Size Honesty
   - Both layers raise the SAME `ConfidenceCapViolation` class (reused from
     L1.7-B `macro_pipeline.manual_input.validation`); verify class identity

2. **OOD reserve (Vision section seven)** —
   - Bounds [five percent floor, fifteen percent ceiling]
   - Eight condition triggers; equal-weighted increment per trigger
   - L6-D `compute_ood_reserve` plus L6-F aggregator integration

3. **Triple Decomposition (Vision section four; BINDING)** —
   - probability in [zero, one]; confidence in [zero, one];
     conviction in [one, ten]
   - horizon in {1, 3, 5, 10}
   - regime_stratified bool plus binding_constraint Optional[str]

4. **Triple sigma Reporting (Vision section five; BINDING)** —
   - Three distinct sigmas: return_sigma, forecast_error_sigma,
     analog_dispersion_sigma
   - Cumulative scaling via square-root-of-time with explicit caveats
     in module docstring (regime shifts, vol clustering, crises,
     policy shocks)
   - Sanity bound: sigma less than or equal to five point zero
     (unit error guard)

5. **Bayesian shrinkage at ten-year (Vision section six)** —
   - Prior: six point five percent real return constant
     `BAYESIAN_PRIOR_10Y_REAL_RETURN`
   - kappa institutional default ten; tunable
   - Applied only at ten-year; shorter horizons pass through

6. **MetricMetadata registry** —
   - Ninety measurements across twelve subcategories per Vision section three
   - Statistical taxonomy: probability, uncertainty, confidence_conviction,
     goodness_fit_calibration, statistical_significance, bias_correction,
     risk_measures, time_series_quality, information_theory, bayesian,
     macro_specific, regime_conditional
   - L1 plus L2 plus L3 explanation stack per Vision section eleven

7. **Pure function discipline** —
   - L6-E RCF helpers (`standardize_macro_state`, `cosine_similarity`,
     `find_reference_class`, `apply_bayesian_shrinkage`) are pure
   - L6-F aggregator is pure except for git SHA fetch via subprocess
     (graceful degradation to "unknown" on failure)
   - No global state mutation; deterministic given inputs except
     `aggregation_timestamp_iso`

8. **Replication kit metadata (Vision section fourteen)** —
   - Six keys in EnsembleResult.replication_kit_metadata: code_sha,
     aggregation_timestamp_iso, n_horizons, regime_stratified,
     manual_inputs_applied, ood_reserve_fraction
   - code_sha is forty-character hex OR "unknown" fallback

9. **Backward compatibility** —
   - L1.7 plus L5b prior modules unchanged
   - L6-F additive only; aggregator does not modify producers
   - All existing tests continue to pass (zero regressions)

10. **Convergence streak preservation** —
    - Thirty-nine of thirty-nine perfect ACCEPTs entering L6-F
    - L6-F ACCEPT lifts to forty of forty
    - Zero regressions on prior nine-hundred-forty-five tests

## Output format

RATIFY / RATIFY-WITH-FINDINGS / REJECT per `03_CODEX_CODE_REVIEW_v2.md`.

For each finding:
- Severity: HIGH (blocks L6-H closure) / MEDIUM (close at L6-G or L6-H) /
  OPERATIONAL (informal backlog; no closure required)
- Location: file:line reference
- Rationale: institutional invariant plus observed deviation
- Suggested remediation: concrete code change OR design adjustment
````

---

## §2 — ChatGPT 5.5 invocation prompt (paste verbatim to ChatGPT 5.5)

````text
# ChatGPT 5.5 — R7 Methodology Review of L6 Ensemble Aggregation

You are ChatGPT 5.5, performing external methodology review of the macro
pipeline L6 ensemble aggregation layer at tag `l6-g-accept` (upgraded from
initial `l6-f-accept` dispatch on 2026-05-16; see audit footnote and
§Addendum L6-G at the top and bottom of this document).

## Authority document
- `docs/build-plans/02_CHATGPT_METHODOLOGY_REVIEW_v2.md` (your role plus
  verdict format)
- `docs/build-plans/00_VISION_AND_PHILOSOPHY_v2.md` (Vision sections three
  through fourteen govern methodology)

## Fetch plus checkout
```
git fetch origin
git checkout l6-g-accept
```

Per AP-AUTH-55 push verification: confirm `git log origin/claude/layer-5-build -1`
shows the same SHA as `git rev-parse l6-g-accept` before substantive review.

## Review scope

### Methodology critique (focus areas)

L6-E Reference Class Forecasting (`macro_pipeline/ensemble/rcf.py`):
- Eight-dimensional macro state vector standardization per Vision section six
  (cape_z, yield_curve_z, lei_z, credit_spread_z, sentiment_z, breadth_z,
  volatility_z, concentration_z)
- Cosine similarity for analog identification
- Bayesian shrinkage to six point five percent real return prior at ten-year
- n_neighbors default of ten; kappa default of ten

L6-F Ensemble Aggregation (`macro_pipeline/ensemble/aggregator.py`):
- Triple Decomposition computation logic — PLACEHOLDER heuristic at L6-F;
  L6-G will refine with proper Bayesian computation per Vision section four
- Confidence cap defense-in-depth (Standing Order number nine plus
  Vision section ten)
- OOD reserve from eight condition triggers (Vision section seven)
- Multi-horizon aggregation across one / three / five / ten year horizons

Vision section three ninety-measurement registry
(`macro_pipeline/ensemble/data/metrics_registry.yaml`):
- Statistical taxonomy: twelve subcategories
- L1 / L2 / L3 explanation stack quality (Vision section eleven)
- Citation completeness

## Critical methodology questions to address

Question one — eight-dimensional macro state vector representativeness:
Is the eight-dimensional macro state vector representative? Are there
critical missing dimensions (for example, commodity prices, term premium,
fiscal stance, M-two growth, dollar strength)? Vision section six specifies
these eight; methodology critique invited on additions or substitutions.

Question two — Bayesian shrinkage kappa equals ten calibration:
Is the institutional default kappa equals ten calibrated correctly for the
Fed-era (nineteen-thirteen through present) sample size? Should kappa vary
by horizon? Should kappa vary by reference-class composition (e.g.,
heavier shrinkage when fewer than five neighbors exceed similarity
threshold)?

Question three — OOD reserve eight-condition equal-weighting:
Should some conditions weigh more heavily than others (e.g., financial
leverage opaque versus concentration extreme)? Vision section seven does
not specify weights; the L6-D implementation uses equal increments of
one point two-five percentage points per True condition.

Question four — confidence cap calibration:
Seventy percent non-stratified versus fifty-five percent regime-stratified
at ten-year horizon — empirical justification from sample size honesty
(Vision section ten with N effective approximately eleven non-overlapping
windows)? Are these caps appropriately conservative? Should the one-year /
three-year / five-year horizon eighty-five percent cap be tightened given
autocorrelation reducing N effective below nominal N?

Question five — placeholder confidence / conviction logic at L6-F:
Confidence is computed via heuristic
`confidence = min(0.5 + 0.05 * (n_eff / 30), 0.99)` capped by Standing
Order number nine. Conviction is computed as `1.0 + confidence * 9.0`
(linear mapping to one through ten). L6-G will refine the confidence
formula to follow Vision section four BINDING (Data Quality plus Model
Agreement plus Regime Stability plus Analog Strength plus Sample Size
minus OOD Penalty) and the conviction formula to include the asymmetry /
valuation / trend / tail-risk / crowding / policy / decay components.
Is L6-G refinement scope acceptable, OR should L6-F upgrade the heuristic
immediately?

Question six — cumulative sigma square-root-of-time scaling caveats:
Vision section five warns that sigma times square root of t may fail
during regime shifts, vol clustering, crises, policy shocks. How should
this be quantified or surfaced in EnsembleResult? Should the EnsembleResult
include a flag or warning when the caller requests cumulative sigma at a
horizon where the approximation degrades?

Question seven — reference class identification n_neighbors choice:
Top-ten cosine similarity neighbors — is ten the right number for
approximately one-hundred-ten Fed-era one-year observations? Sensitivity
analysis to n_neighbors choice? Should n_neighbors scale with horizon
(more neighbors at one-year where N is larger; fewer at ten-year where
N is approximately eleven)?

Question eight — replication kit completeness:
Six metadata keys (code_sha plus aggregation_timestamp_iso plus n_horizons
plus regime_stratified plus manual_inputs_applied plus ood_reserve_fraction).
Sufficient for Vision section fourteen academic reproducibility? Should
data SHA plus random seeds plus Docker image hash be included? Should the
replication kit include a serialized ForecastInputs JSON for exact
reproduction?

## Output format

RATIFY / RATIFY-WITH-FINDINGS / REJECT per `02_CHATGPT_METHODOLOGY_REVIEW_v2.md`.

For each finding:
- Severity: HIGH (blocks L6-H closure) / MEDIUM (close at L6-G or L6-H) /
  OPERATIONAL (informal backlog; no closure required)
- Location: file:line OR Vision section reference
- Vision or Guide ref: section number citation
- Suggested remediation: methodology change plus implementation impact
````

---

## §3 — V coordination notes

- Dispatch both reviewers in parallel; track responses independently.
- Both reviewers must run `git fetch origin && git checkout l6-g-accept`
  before review (per AP-AUTH-55 push verification discipline). Confirm the
  tag SHA matches `origin/claude/layer-5-build` via `git ls-remote`.
- Expected wall-clock for both verdicts: three to seven days.
- After both verdicts received, V relays to Strategic; Strategic dispositions
  findings plus integrates into L6-G or L6-H scope per severity.
- HIGH findings block L6-H closure; MEDIUM findings close at L6-G or L6-H;
  OPERATIONAL findings are informal backlog.

## §4 — R7 dispatch-ready signal

R7 reviewer invocation prompts are dispatchable to Codex 5.5 plus ChatGPT 5.5
immediately upon L6-G ACCEPT confirmation (originally dispatchable at L6-F
ACCEPT; upgraded to L6-G on 2026-05-16 — see audit footnote at the top).
Both reviewers can fetch at tag `l6-g-accept` and begin parallel review
without further Strategic round-trip. R7 reviewer cycle executed IN PARALLEL
with the L6-G measurement coverage and Bayesian refinement sub-phase per
Strategic disposition; L6-G is now ACCEPTed and reviewers can proceed at
the upgraded tag.

---

## §Addendum L6-G (2026-05-16) — Bayesian confidence and conviction refinement upgrade

This addendum documents the L6-G sub-phase ACCEPT (commit `97ada00`, tag
`l6-g-accept`) that landed on 2026-05-16, after the initial R7 dispatch at
`l6-f-accept` (2026-05-15). L6-G is additive over L6-F; cap-enforcement
semantics (Standing Order number nine plus Vision section ten) are preserved
and the defense-in-depth pattern remains a third-instance invariant at the
aggregator pipeline.

### L6-G changes summary

1. **Bayesian confidence and conviction refinement** —
   The L6-F placeholder heuristic confidence and conviction logic in
   `macro_pipeline/ensemble/aggregator.py` was replaced with a dedicated
   Bayesian module `macro_pipeline/ensemble/bayesian_confidence.py`. Two
   pure functions exposed:
   - `compute_bayesian_confidence(point_estimate, n_eff, reference_class,
     regime_stratified, horizon) -> float` — posterior precision combines
     `n_eff` plus `KAPPA_EVIDENCE` (ten); evidence weight derived from
     reference class mean similarity; confidence uncapped in the range
     zero point five through zero point nine before Standing Order number
     nine cap enforcement applies.
   - `compute_conviction_score(confidence, reference_class, n_eff) -> float`
     — Vision section four simplified subset (linear scaling one through
     ten, with sample-size penalty when `n_eff` is less than thirty and
     weak-analog penalty when reference class mean similarity is less than
     zero point three). Full Vision section four BINDING ten-component
     conviction formula remains deferred to a future refinement; deferral
     documented explicitly in the module docstring.

2. **Vision section three ninety-measurement coverage** —
   `macro_pipeline/ensemble/data/metrics_registry.yaml` now has ninety of
   ninety measurements with explicit disposition: forty measures linked to
   existing L1 through L5b producers via `computation_path`; thirty-two
   measures deferred to L7 (portfolio-level scope) via `deferred_to`;
   eighteen measures deferred to L8a (UI primitives) via `deferred_to`.
   Total coverage at `l6-g-accept`: ninety of ninety.

3. **Aggregator extension** —
   `aggregator.py` adds a `populate_metric_outputs` helper that extends the
   L6-F eight-key per-horizon baseline to fifteen keys per horizon when
   reference class plus DMS adjustments are provided (DMS adjustment in
   basis points; RCF mean similarity; RCF neighbour count; three cumulative
   sigmas via square-root-of-time scaling; plus Bayesian shrinkage flag).
   Backward compatibility preserved at the EnsembleResult API level.

### Strategic pre-dispositions executed (PD18 plus PD19 plus PD20)

- **PD18 (NEG-flavor floor relaxed to forty percent for Bayesian module
  tests)** — `tests/test_bayesian_confidence.py` contains fifteen tests
  with NEG ratio six of fifteen (forty percent), per Strategic-ratified
  relaxed floor for Bayesian computation modules where the
  boundary-condition test surface is intrinsically POS-inv heavy.
  Supplemental NEG coverage in `test_aggregator.py` covers `ForecastInputs`
  and horizon range cases.
- **PD19 (test refactor authority for L6-F aggregator tests)** —
  Two L6-F aggregator tests (Tests ten and eleven) refactored: reference
  class fixtures added so that the Bayesian formula `0.5 + 0.4 *
  evidence_weight` exceeds horizon caps and the cap-enforcement path
  remains testable post-Bayesian replacement.
- **PD20 (Test twelve defense-in-depth preservation)** —
  `test_aggregate_defense_in_depth_both_layers_fire` (third-instance
  verification of the defense-in-depth pattern) PASSES unchanged
  post-Bayesian replacement. Institutional invariant preserved.

### R7 reviewer impact

- **ChatGPT methodology review question five (placeholder confidence and
  conviction logic at L6-F)** — proactively addressed by the L6-G Bayesian
  refinement. The placeholder heuristic is no longer present at
  `l6-g-accept`. The Vision section four BINDING full ten-component
  conviction formula remains deferred (documented in module docstring);
  ChatGPT review MAY still flag this scope as a MEDIUM finding for L6-H
  closure.
- **Vision section three measurement coverage question** — fully addressed
  at `l6-g-accept`: ninety of ninety measurements have explicit disposition.
- **Expected impact on finding counts** — MEDIUM-finding count expected to
  be lower at `l6-g-accept` than would have been at `l6-f-accept`-only
  state, since question five is partially closed (Bayesian refinement
  landed; only the full ten-component formula remains deferred) and
  Vision section three ninety-measurement coverage is complete.

### Reviewer fetch choice

Reviewers have two valid paths:

1. **Re-fetch at `l6-g-accept`** — if review has not yet started, fetch at
   the upgraded tag for the most current state. Recommended path.
2. **Finalize at `l6-f-accept`** — if review is already in progress,
   finalize verdict at the original dispatch tag. L6-F is an ACCEPTed
   state; the verdict will be valid, and Strategic disposition will
   reconcile findings against L6-G changes at L6-H closure.

Both paths are sanctioned; reviewers choose at their discretion.

### Anchors

| Anchor | Value |
|---|---|
| L6-G commit SHA | `97ada00c1dab52f9edd86312ce8e923fa3af5698` |
| L6-G tag | `l6-g-accept` |
| L6-F commit SHA (original dispatch; tag not moved) | `f2c963b09ca23b2538b0c7e54d66a77aaf1fc333` |
| L6-F tag | `l6-f-accept` |
| Pytest count at `l6-g-accept` | one thousand four collected; one thousand four passed |
| origin/main | `412235d` (UNCHANGED; main has not received L6 work) |
| New files added at L6-G | `macro_pipeline/ensemble/bayesian_confidence.py`; `tests/test_bayesian_confidence.py`; `tests/test_metric_outputs_coverage.py`; `scripts/l6g_update_registry.py` |
| Modified files at L6-G | `macro_pipeline/ensemble/aggregator.py`; `macro_pipeline/ensemble/__init__.py`; `macro_pipeline/ensemble/data/metrics_registry.yaml`; `tests/test_aggregator.py` |

### AP-AUTH register

No new AP-AUTH codification at this R7-bis sync (per AP-AUTH-46
gratuitous-codification guard). AP-AUTH-56 (defense-in-depth pattern;
third instance at L6-F aggregator) and AP-AUTH-57 (cross-branch
cherry-pick pattern; second instance at L6-PREP) remain candidate
codifications deferred to the L6-H retrospective.
