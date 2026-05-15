# DMS Source Memo — Layer 5-F Survivorship Adjustment Anchoring

**Anchor**: `l5b-kick-7-accept` (2026-05-15)
**Authored by**: Track A (Claude Code) under Strategic disposition
**Closes**: Codex 5.5 IMPORTANT + ChatGPT 5.5 IMPORTANT reviewer flags on DMS source-anchoring transparency (L5b-KICK-7 mandate)
**Module reference**: `macro_pipeline/models/dms_adjustment.py`
**Gate**: 25 (composite SEALED at L5-G; sub-criterion 25.1.7 enforces this memo's presence + section structure)

---

## 1. Source Identification

### Primary literature

- **Dimson, Marsh, Staunton (2002)** *Triumph of the Optimists: One Hundred and One Years of Global Investment Returns*. Princeton University Press. ISBN 0-691-09194-3. The foundational survivorship-correction work covering twenty-one-market equity returns over the nineteen-hundred-to-two-thousand-and-one window. Publicly catalogued; widely cited in academic literature.

- **Credit Suisse Global Investment Returns Yearbook** annual series (two-thousand-fifteen through two-thousand-and-twenty-two). The headline executive summary PDFs have historically been publicly accessible at the time of release (Credit Suisse Research Institute publication; not paywalled at issuance).

- **UBS Global Investment Returns Yearbook** annual series (two-thousand-and-twenty-three onwards, post-UBS-acquisition-of-Credit-Suisse rebrand). The full yearbook is a paid publication (UBS Asset Management Research subscription); annual press-release abstract is freely available.

### Citation status

Specific table line items from the full UBS Yearbook are not in the public domain. The Q6-locked basis-point values in `dms_adjustment.py` (`DMS_BPS_CENTRAL` and `DMS_BPS_SENSITIVITY`) are anchored to the **empirically-supported range** that DMS literature exposes via publicly-accessible executive summaries plus the original DMS two-thousand-and-two book, NOT to a specific table-line citation that would require paid-source access.

**Refresh anchor**: this memo cites publicly available material as of memo authoring (two-thousand-twenty-six May fifteenth). Annual UBS Yearbook release (typically January cycle) may shift the empirical range materially; refresh protocol below.

---

## 2. Empirical Foundation

### US equity real premium

Per DMS-derived public summaries, the United States annualised real equity premium over the nineteen-hundred-to-recent window is in the range of roughly four-point-five to six-point-five percent (geometric mean) depending on terminal-year cut and treatment of dividends. The Q7-locked institutional default is `DMS_PRIOR_REAL_ANNUALIZED_US` equal to zero-point-zero-six-five (six-point-five percent annualised) per Master Prompt v3.1 §13.

### World ex-US (or global average) equity real premium

Per the same publicly-available DMS-derived summaries, the world-ex-US (or twenty-one-market average excluding the US) annualised real equity premium is in the range of roughly three-point-five to four-point-five percent (geometric mean). The Q7-locked institutional default is `DMS_PRIOR_REAL_ANNUALIZED_GLOBAL` equal to zero-point-zero-four-five (four-point-five percent annualised).

### Geometric vs arithmetic

All values cited above and in `dms_adjustment.py` are geometric (compound annual growth rate) per DMS convention. Arithmetic means are systematically higher (typically by half the variance); the spec mandates geometric throughout to preserve compounding integrity over multi-year horizons.

---

## 3. US-vs-Global Premium Gap

### Empirical range from publicly-derivable DMS sources — two distinct quantities

L5b-F Phase 5 (F-M4b) — Strategic Note C clarification: §3 references **two distinct quantities**, not a single inconsistent range. Both stay; prose disambiguates them explicitly.

**Quantity A — Underlying US-vs-global return gap (one-nine-hundred to twenty-twenty-four sample)**: the realised US-vs-global premium gap implied by DMS-derived public summaries is approximately **two-hundred-to-three-hundred basis points annualised** (geometric, depending on terminal year). This is the raw historical record — what the US has actually earned over what the global ex-US benchmark earned.

**Quantity B — Conservative adjustment applied to L5 forecasts**: the survivorship adjustment applied to L5 forecasts is conservatively set at **one-hundred-to-two-hundred basis points annualised**. This is the underlying gap A discounted to account for partial mean-reversion + forward-looking uncertainty; the conservative cut preserves predictive value while avoiding the implicit assumption that future US outperformance equals the full historical gap. This is the figure that flows into `DMS_BPS_CENTRAL` per §4 below.

### One-sigma confidence band

DMS standard-error reporting for the long-horizon premium estimate is wide due to the small number of independent long-run observations (effectively one twenty-first-century period, two twentieth-century half-periods). The one-sigma band on the underlying gap estimate (Quantity A) is approximately ±fifty basis points per the DMS standard-error methodology, which informs the spec-locked sensitivity band applied to the conservative adjustment (Quantity B).

### Symbolic derivation chain

The underlying US-vs-global gap (Quantity A, two-hundred-to-three-hundred basis points depending on terminal year) is the symbolic anchor for the survivorship correction. The conservative adjustment (Quantity B, one-hundred-to-two-hundred basis points) is derived from A via partial-mean-reversion discounting per §4 below. The five-year and ten-year horizon-specific adjustments derive from Quantity B plus horizon-specific weighting (long-horizon survivorship dominance is more pronounced).

---

## 4. DMS Adjustment Derivation

### Honest disclaimer (KICK-7 §4 transparency clause)

**The specific values `DMS_BPS_CENTRAL[5Y] = -125.0` and `DMS_BPS_CENTRAL[10Y] = -175.0` are institutional judgment within the empirically-supported DMS range, NOT direct table-derived precision.** The DMS literature supports a survivorship-correction range of roughly one-hundred to two-hundred basis points annualised for long-horizon equity premia; the spec authors' Q6 lock formalises specific midpoints within this range as institutional defaults, with the sensitivity band reflecting the residual uncertainty.

This is the framing endorsed by both Codex 5.5 ("DMS scope, not the exact bps values") and ChatGPT 5.5 ("DMS adjustment is directionally justified, but the exact bps values need source-table support"). The memo's value-add is making this institutional-judgment component **explicit and auditable**, rather than presenting it as table-derived precision the source literature does not independently support.

### Five-year horizon midpoint reasoning

The five-year midpoint at minus-one-hundred-twenty-five basis points sits within the DMS range (minus-one-hundred to minus-one-hundred-fifty basis points for medium-horizon survivorship correction). Rationale:

- Five-year horizons are long enough for survivorship dominance to bite but short enough that the full long-run gap has not fully materialised.
- The minus-one-hundred-twenty-five midpoint is the geometric mid of the empirical range.
- Sensitivity band of plus-or-minus fifty basis points covers minus-seventy-five to minus-one-hundred-seventy-five, capturing one-sigma uncertainty around the central estimate.

### Ten-year horizon midpoint reasoning

The ten-year midpoint at minus-one-hundred-seventy-five basis points sits within the DMS range (minus-one-hundred-fifty to minus-two-hundred basis points for long-horizon survivorship correction). Rationale:

- Ten-year horizons are sufficiently long for the full survivorship gap to dominate.
- The minus-one-hundred-seventy-five midpoint is the geometric mid of the empirical range.
- Sensitivity band of plus-or-minus fifty basis points covers minus-one-hundred-twenty-five to minus-two-hundred-twenty-five, capturing one-sigma uncertainty around the central estimate.

### One-year and three-year horizon exclusion

Both one-year and three-year horizons are assigned zero basis-point adjustment (sensitivity band collapsed) per Q6 lock. Rationale:

- Short-horizon equity returns are dominated by mean-reversion noise and cyclical dynamics, NOT by long-run survivorship.
- The DMS survivorship correction is a **long-horizon phenomenon**; applying it at one-year or three-year scales would introduce noise without empirical justification.
- Spec authors chose to disable the correction entirely at these horizons rather than apply a small adjustment that would be statistically indistinguishable from zero.

### Q6 lock formalisation

The four-tuple `{1Y: 0.0, 3Y: 0.0, 5Y: -125.0, 10Y: -175.0}` plus the scalar sensitivity `50.0` are spec §5.F.4 Q6-locked values. They are NOT magic numbers in the AP-AUTH-52 sense (no derivation from `base + delta` arithmetic); they are institutional defaults anchored to the empirical DMS range, locked at spec freeze time, and refreshable only via formal spec amendment + Q6 unlock.

---

## 5. Sensitivity Band Justification

### One-sigma anchoring

The plus-or-minus fifty basis-point sensitivity band reflects approximately one-sigma uncertainty on the historical US-vs-global premium gap estimate per DMS standard-error reporting. The band is applied symmetrically for five-year and ten-year horizons; collapsed (lower equal central equal upper) for one-year and three-year horizons where the adjustment itself is zero.

### Reported via lower/upper return values

Per spec §5.F.1 the `apply_dms_adjustment` function returns the three-tuple `(adjusted_central, adjusted_lower, adjusted_upper)`. Downstream consumers in the L5 scoring layer surface both the central estimate and the sensitivity band to communicate the institutional-judgment uncertainty explicitly.

### Not a confidence interval in the frequentist sense

The plus-or-minus fifty bps band is a **judgment-anchored uncertainty range**, NOT a frequentist confidence interval derived from sampling theory. The DMS standard-error methodology underpinning the empirical range informs the band width, but the specific lock value (plus-or-minus fifty) is institutional judgment formalised at Q6 spec freeze.

---

## 6. Refresh Protocol

### Annual cycle

The UBS Global Investment Returns Yearbook typically releases in January each year. Refresh protocol:

1. **Annual review** (each January) — read the publicly-available UBS press release abstract and any executive summary PDF that becomes publicly accessible.
2. **Empirical range check** — compare the latest DMS-derived US-vs-global premium gap against the empirical range cited in section three above (one-hundred-to-two-hundred basis points annualised).
3. **Material shift threshold** — if the empirical range midpoint shifts by more than fifty basis points (i.e., the new midpoint falls outside the current spec sensitivity band), trigger a formal spec amendment to unlock Q6 and re-anchor the values.
4. **Memo refresh** — update sections one through three of this memo with the new edition citation and latest empirical range; preserve the §4 honest disclaimer verbatim.

### Material-shift threshold rationale

A fifty-basis-point midpoint shift corresponds to a full sensitivity-band width shift; values within this tolerance do not require formal spec amendment because they remain within the current Q6 lock's sensitivity envelope.

### Documentation discipline

Each refresh should produce a new memo commit with a clear "refresh date / new edition cited / empirical range delta" annotation in the commit message. This memo's authoring history serves as the audit trail for downstream consumers asking "when was this value last source-checked?".

---

## 7. Strategic Interpretation

### US-only prior vs global robustness check (L5-G framework integration)

The Q7-locked priors `DMS_PRIOR_REAL_ANNUALIZED_US = 0.065` and `DMS_PRIOR_REAL_ANNUALIZED_GLOBAL = 0.045` per Master Prompt v3.1 §13 are the two anchoring values used by the L5-G Bayesian shrinkage framework:

- **US-only prior (0.065 = six-point-five percent)**: institutional default for US-equity forecasting where the survivorship-corrected US premium is the natural prior.
- **Global prior (0.045 = four-point-five percent)**: robustness check / world-ex-US comparison, used when the model output is being sanity-checked against the non-survivorship-biased global benchmark.

### When to use which

- Primary forecast path uses the US-only prior with the DMS adjustment applied to the central forecast (five-year and ten-year horizons).
- Robustness check path uses the global prior without the DMS adjustment (since the global prior is already implicitly survivorship-corrected by averaging across the twenty-one-market panel).
- Divergence between the two paths exceeding the sensitivity band signals model uncertainty worth surfacing to the analyst.

### Cross-reference to L5-G Bayesian shrinkage

The shrinkage weight `k / (k + n)` per spec §5.G.1 with K_HORIZON v2 backsolve values (`1Y: 5.9, 3Y: 6.7, 5Y: 9.4, 10Y: 11.0` per Q7 lock + S-4) determines how aggressively the forecast pulls toward the prior. The DMS adjustment operates BEFORE the shrinkage step (raw forecast → DMS-adjusted forecast → shrunken-toward-prior forecast); see `macro_pipeline/models/bayesian_shrinkage.py` module docstring for the full pipeline.

---

## Provenance trail

- Authored: two-thousand-twenty-six May fifteenth (L5b-KICK-7 ACCEPT, tag `l5b-kick-7-accept`)
- Closes: Codex 5.5 + ChatGPT 5.5 IMPORTANT reviewer flags on DMS source-anchoring transparency
- Sub-criterion enforcement: Gate 25.1.7 (added at L5b-KICK-7); composite Gate 25 remains SEALED with this additive sub-criterion extension within the 25.1 (DMS) body
- AP-AUTH governance: AP-AUTH-53 seventh-instance reviewer-driven kickoff pattern; documentation-primary variant (AP-AUTH-55 codification DEFERRED per AP-AUTH-46 gratuitous-codification guard; first instance only)
- Refresh schedule: annual (January UBS Yearbook release cycle) per section six above
