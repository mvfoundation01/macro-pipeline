# `macro_pipeline.scoring` — Layer 3B+ scoring engines

## §1. Purpose

Production scorers that consume PIT-safe data via `PitDataContext` and
emit a universal `ScoredObservation` record. Today this package
contains the CRPS production scorer (Layer 3B); CDRS arrives in 3C.

| Module | Layer | Output |
|---|---|---|
| `scored_observation.py` | 3B | `ScoredObservation` dataclass + `CompositeBuildError` |
| `crps.py` | 3B | `compute_crps(ctx)` → 12M-forward Recession Risk Score (raw composite; not yet calibrated to probability — see L5-RM-4) |

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
| Refit weights via penalized logistic regression with Gaussian L2 priors | Always (this is why Layer 3B/3C use placeholders) |
| Re-include `lei_3d_rule` | Once a CB LEI loader exists and the double-counting graph is updated to allow it without `PHILLY_LEI_PROXY` |
| Re-include `ism_pmi_neworders` | Once an alternate NAPMNOI source is found |
| Revisit redistribution method | If Layer 5 finds proportional rescaling produces unexpected weight allocations on out-of-sample folds |
| Retrain HMM v2 | When a non-UMCSENT activity feature is sourced (see `regime/README.md` §3) |
| **L5-5** — true CP/GDP profit margin loader | Replaces V5 Damodaran-EY proxy (D8) with a literal corp-profit-margin signal |
| **L5-6** — V/T component-weight refit | Replaces equal-weight placeholders in CDRS V (5×0.20) and T (renormalized 0.25 / 0.20). Should also restore Gate 10's 5× differential (currently 3×) |
| **L5-7** — CDRS-specific regime resolver | Optional: rather than reusing `RegimeContext.derive_regime_state()` from CRPS, fit a regime classifier targeted at drawdown timing. Strategic Claude rejected this for L3 (architectural complexity) but it is the cleanest path back to spec §6.8's >0.65 threshold |
| Update `crps_method` tag from `"expert_priors_v1_pathB"` to `"ridge_logistic_v1"` | After Layer 5 fit |
| Update `cdrs_method` tag from `"two_stage_v1"` to `"two_stage_v2"` | After L5-6 + optional L5-7 |

---

# §CDRS — Layer 3C addendum

## §C1. Vulnerability and Trigger components

### V (5 components, equal-weight 0.20 each)

| # | Code | Indicator | Transform |
|---|---|---|---|
| V1 | `V1_cape_pctile` | SHILLER_CAPE | percentile rank vs 1881-current |
| V2 | `V2_margin_z` | FINRA_MARGIN_DEBT (raw, **D10**) | 24M rolling z-score → sigmoid |
| V3 | `V3_concentration_proxy` | RSP_close / SPX_PRICE (**D7**) | percentile rank inverted (high concentration → high score) |
| V4 | `V4_ey_real_gap_z` | derived: (1/CAPE × 100) − (SHILLER_GS10 − YoY SHILLER_CPI) | 60M rolling z-score → sigmoid(−z) (high gap = cheap = low V) |
| V5 | `V5_ey_deviation` | DAMODARAN_EY (**D8**) | (raw − mean) / std → sigmoid(−z) (low EY = expensive = high V) |

V = mean of active components. Components that fail PIT load (e.g.
RSP pre-2003) are dropped from the average and recorded in
`v_inactive_components`.

### T (5 components, equal-weight 0.20 each, renormalized to 0.25 when T3 dropped)

| # | Code | Indicator | Transform |
|---|---|---|---|
| T1 | `T1_hy_oas_30d_roc` | BAMLH0A0HYM2 | (HY_t − HY_{t-30d}) × 100 bps → sigmoid((Δ-50)/25) |
| T2 | `T2_vix_12m_pctile` | VIX_YAHOO | trailing 252-bday percentile rank |
| T3 | `T3_gamma_sign` (**D9**) | CBOE_GAMMA | binary: 1.0 if latest < 0 else 0.0 (only post-2022-12) |
| T4 | `T4_breadth_thrust` | S5FI | piecewise linear: 0 at ≥80%, 0.5 at 40%, 1.0 at ≤20% |
| T5 | `T5_move_z` | MOVE (^MOVE Yahoo) | 12M rolling z-score → sigmoid |

When T3 has no PIT-safe data at the as_of, the orchestrator drops T3
and the surviving 4 components each weight 0.25 (proportional renorm).
This is recorded in `t_weights_post_renorm` on the result.

## §C2. Time-conditional reach matrix

```
              V1   V2   V3   V4   V5  | T1   T2   T3   T4   T5  | Reach verdict
              CAPE Mar  Top  EY   EY  | OAS  VIX  Gam Brth MOVE
                                       gap  dev

1929-08       OK   --   --   OK   --  | --   --   --   --   --  | UNREACHABLE (V 2/5, T 0/5)
1973-09       OK   --   --   OK   --  | --   --   --   --   --  | UNREACHABLE (V 2/5, T 0/5)
2000-03       OK   --   --   OK   OK  | OK   OK   --   --   --  | PARTIAL (V 3/5, T 2/5)
2007-09       OK   OK   OK   OK   OK  | OK   OK   --   OK   OK  | FULL minus T3 (V 5/5, T 4/5)
2020-02       OK   OK   OK   OK   OK  | OK   OK   --   OK   OK  | FULL minus T3 (V 5/5, T 4/5)
2025-06       OK   OK   OK   OK   OK  | OK   OK   OK   OK   OK  | TRUE FULL (V 5/5, T 5/5)
```

Component start dates that drive the reach: BAMLH0A0HYM2 1996-12,
VIX_YAHOO 1990-01, CBOE_GAMMA 2022-12, S5FI 2006-12, MOVE 2002-11,
RSP 2003-05, DAMODARAN_EY 1961.

## §C3. Spec deviations register (D7-D14)

| Tag | Topic | Decision |
|---|---|---|
| **D7** | V3 top-10 concentration not in any Tier 1-4 source | Use `RSP/SPX_PRICE` percentile rank inverted as proxy. Documented in `cdrs_proxy_substitutions = ["V3_RSP_SPX_proxy", ...]` |
| **D8** | V5 profit margin not in Damodaran or any other loader | Use `DAMODARAN_EY` deviation from mean as proxy. Push true CP/GDP loader to **L5-5** backlog |
| **D9** | T3 dealer gamma only exists 2022-12 onward | Per-as_of graceful degradation: drop T3 when PIT empty and proportional-renormalize remaining 4 components to 0.25 each |
| **D10** | V2 margin debt — spec says "FINRA / GDP" | Use raw FINRA + 24M rolling z-score (z is unit-invariant). Avoids GDP loader dependency |
| **D11** | R multiplier extension when regime neutralized | When `RegimeContext.derive_regime_state()` returns `source="hmm_dissent_neutralized"`, R *= 0.95 AND `metadata_extra["regime_neutralized"] = True` |
| **D12** | Gate 10 calibrated to reachable events | Spec §6.8 wanted `>0.65` within ±6M of every drawdown event. Path B reaches at most 0.257 (Lehman) — see §C4. Gate 10 redesigned around 9 assertions: floor + direction + differential + decomposition + guards + caps + unreachable declaration |
| **D13** | Drop the `sigmoid(V) × sigmoid(T)` wrapper from spec §6.2 | V and T are already ∈ [0, 1] as means of percentile-equivalents. Wrapping in sigmoid compresses [0, 1] to [0.5, 0.731] and caps max CDRS at ~0.747 (recession-only path), destroying discriminating power. New formula: `CDRS = V × T × R`, clipped [0, 1]. R values from spec §6.2 retained: expansion=0.6, late-cycle=1.0, recession=1.4 |
| **D14** | Gate 10 calibrated to Path B reality | Spec §6.8 expected CDRS > 0.65 within ±6M; under D13 + equal-weight placeholder V/T, Path B max under recession R=1.4 is ~0.747 but most historical events resolve to expansion or late-cycle R, capping CDRS in [0.13, 0.26]. Gate 10 asserts (a) direction, (b) differential ≥ 3.0×, (c) magnitude floors per event. L5-6 + L5-7 may restore stricter thresholds |

## §C4. Why CDRS is bounded for Path B

The structural cap is `R × 1 × 1 = R`, so CDRS ≤ R for any V, T ∈ [0, 1].
For most historical event dates, `derive_regime_state()` returns
`expansion` or `late-cycle` (NBER had not yet announced the recession,
or the announcement post-dates the as_of), so R ∈ {0.6, 0.95, 1.0} and
CDRS is capped well below the spec's 0.65 expectation. See `D14`.

Empirical Path B anchors (smoke + Gate 10):

| Anchor | V | T | R | CDRS | regime_state_source |
|---|---|---|---|---|---|
| 2007-09-15 (Lehman pre) | 0.651 | 0.657 | 0.600 | 0.257 | hmm_corroborated |
| 2020-02-20 (COVID peak)  | 0.532 | 0.420 | 0.950 | 0.213 | hmm_dissent_neutralized |
| 2000-03-15 (dot-com)     | 0.777 | 0.407 | 0.600 | 0.190 | hmm_corroborated |
| 2005-06-01 (mid-cycle)   | 0.407 | 0.174 | 1.000 | 0.071 | hmm_corroborated |
| 2014-06-01 (post-GFC)    | 0.452 | 0.124 | 1.000 | 0.056 | hmm_corroborated |
| 2017-06-01 (calm trough) | 0.601 | 0.097 | 0.600 | 0.035 | hmm_corroborated |

## §C5. ScoredObservation.metadata_extra fields populated by `compute_cdrs`

| Key | Value |
|---|---|
| `cdrs_method` | `"two_stage_v1"` |
| `cdrs_active_components` | union of V active + T active component names |
| `cdrs_inactive_components` | union of V inactive + T inactive component names |
| `cdrs_proxy_substitutions` | `["V3_RSP_SPX_proxy", "V5_DAMODARAN_EY_proxy"]` |
| `regime_neutralized` | True when `derive_regime_state` source = "hmm_dissent_neutralized" |
| `regime_state_source` | from `RegimeContext.derive_regime_state` |
| `regime_state_confidence_haircut` | from `derive_regime_state` (0.00 / 0.05 / 0.10 / 0.20) |
| `V_score` | float ∈ [0, 1] |
| `T_score` | float ∈ [0, 1] |
| `R_multiplier` | float ∈ {0.6, 0.95, 1.0, 1.4 ...} |
| `raw_cdrs_pre_clip` | un-clipped V × T × R for audit |
| `v_active_components` / `v_inactive_components` | per-stage breakdown |
| `t_active_components` / `t_inactive_components` | per-stage breakdown |
| `t_weights_post_renorm` | trigger weight dict after D9 renormalization |
| `v_method` | `"vulnerability_v1"` |
| `t_method` | `"trigger_v1"` |
| `v_notes` / `t_notes` | data-availability notes from each stage |


---

# §D20. Layer 3.5B Option Z — `pit_safe_by_construction` for SAHMREALTIME

**Spec ref**: `LAYER_3_5_BUILD_SPEC.md` §4 (3.5B). **D21** filed for the
config-pattern deferral (full `SeriesConfig` dataclass migration deferred
to L5-12; Option C+ used here — extend dict pattern with the three new keys).

## §D20.1 — Why Option Z exists

`SAHMREALTIME` is a real-time recession indicator constructed by FRED
from only the unemployment data available at each point in time per the
Sahm Rule definition (Atlanta Fed methodology). Loading SAHMREALTIME
in PIT mode currently presents two unsatisfying options:

1. **Materialise an ALFRED vintage panel** for SAHMREALTIME. ALFRED has
   real-time vintages only from 2011-05-23 forward; for any backtest
   ``as_of < 2011-05-23`` (every recession before 2020), a vintage panel
   is empty.
2. **Drop SAHMREALTIME** from CRPS/CDRS. SAHMREALTIME is 28.57% of the
   Path B CRPS weight; dropping it materially weakens the recession
   composite.

Option Z is the third path: treat the latest cache as PIT-safe **by
construction** of the source series, but cap downstream confidence at a
defensible upper bound to defend against (a) seasonal-factor revisions
to recent values (BLS routinely revises seasonally-adjusted UNRATE back
~5 years each annual benchmark) and (b) the residual methodology-vs-
vintage gap.

Option Z is a **methodology choice, not a workaround**. The cap (0.70)
is derived from L1.5 confidence-cap discipline:
- Source quality `free_api` baseline = 1.00
- Derived cap for constructed real-time series = **0.70** (binds tighter
  than the source baseline)
- Aggregation = MIN with all other caps (vintage / staleness / horizon).

## §D20.2 — Configuration

In `macro_pipeline/config.py`, the `SAHMREALTIME` entry carries three
new keys atop the existing dict pattern:

```python
"pit_safe_by_construction": True,
"pit_construction_rationale": "FRED publishes SAHMREALTIME as a real-time series ...",
"derived_confidence_cap": 0.70,
```

Validation runs at module import time
(`_validate_pit_construction_consistency`) and raises `ValueError` if
the flag is set without a non-empty rationale OR with a cap outside
`(0, 1]`.

## §D20.3 — Runtime branching

`macro_pipeline/access.py::PitSeriesReader._load_via_visibility_shift`
now has explicit 3-way branching for any series that reaches it:

| Case | Branch | Returns |
|---|---|---|
| `vintage=True` AND `pit_safe_by_construction=True` | Option Z | latest cache truncated at `as_of`, `pit_safe=True`, `pit_safe_basis="by_construction"`, `derived_confidence_cap` propagated |
| `vintage=True` AND not in `VINTAGE_REQUIRED_SERIES` AND not Option Z | RAISE | `PitContractViolationError` (no silent fallback) |
| `vintage=False` | standard | release-lag visibility shift OR as-of truncation |

The previous silent fallback path (Codex finding B) is gone.

## §D20.4 — Cap propagation

`models/quality_caps.py::AppliedCaps` carries `derived_confidence_cap`
as a new field; `compute_final_confidence_cap` populates it from the
indicator metadata; `aggregate_caps` includes it in the MIN.

In `scoring/crps.py::compute_crps` and `scoring/cdrs.py::compute_cdrs`,
the headline `confidence` is clamped by `final_quality_cap × 100`
post-`confidence_score_v2`. With SAHM contributing to CRPS at 28.57%
weight, every CRPS observation now respects the 0.70 cap (verified at
4 anchor dates: 1998-08-01, 2001-04-01, 2008-09-15, 2020-04-01 — all
clamp to confidence 70.00 / 0.70).

## §D20.5 — Forward path (L5)

L5-RM-2 (Layer 5 backlog item, see `BACKLOG_LAYER_5_v1.md`) covers the
Ridge-fit refinement that may further tune the cap empirically.
L5-12 (NEW) covers the full `SeriesConfig` dataclass migration deferred
from 3.5B per D21.

## §D20.6 — Auditability

`python -m macro_pipeline.utils.pit_audit` walks `FRED_SERIES_API` and
reports any series that would currently raise
`PitContractViolationError` if loaded in PIT mode. As of L3.5B close
the audit returns 0 mismatches. Gate 13
(`validate_gate13_pit_contracts`) re-runs this audit + the 4-anchor
smoke-test on every gate execution.



---

# §D21. Layer 3.5D — Risk Score, not Probability + INDETERMINATE state

**Spec ref**: `LAYER_3_5_BUILD_SPEC.md` §6 (3.5D).

## §D21.1 — Why "Risk Score" not "probability"

CRPS and CDRS are **risk scores**, not probabilities. The `raw_score`
field on `ScoredObservation` (renamed from `score_value` at Layer 3.5D
per Decision Lock 3.5D-D3) is a weighted/multiplicative composite of
component signals. Until Layer 5's blocked walk-forward calibration
(L5-RM-4 for CRPS, L5-RM-6 for CDRS), the raw composite is **not**
calibrated against 12M-forward NBER recession-start labels (CRPS) or
SPX max-drawdown ≥20% labels (CDRS) and **must not** be interpreted
as an event probability.

The `calibrated_probability` field (NEW at 3.5D, default `None`) is
the future home for the calibrated value. `calibration_metadata` (NEW)
records the calibration method, fit data window, and diagnostics.

## §D21.2 — INDETERMINATE regime state (HMM dissent)

Per spec §6.3-2 + Decision Lock 3.5D-D1: when the HMM disagrees with
the NBER+Kindleberger consensus, `derive_regime_state` returns
`("indeterminate", "hmm_dissent_indeterminate", 0.40)`. Downstream:

- **CRPS confidence** is capped at 0.60 (regime-driven, applied at
  `compute_crps` post-`confidence_score_v2` via
  `aggregate_caps(final_cap, INDETERMINATE_CONFIDENCE_CAP)`).
- **CDRS confidence** is capped at 0.60 (same mechanism).
- **CDRS R multiplier** uses the **consensus state's R**, not a hard-
  coded 1.0 (per Decision Lock 3.5D-D2 / AM21=B / D24). Spec §6.4-D2
  alternative #3 ("R from consensus") was selected after empirical
  smoke-test showed R=1.0 default would inflate calm-anchor CDRS via
  the HMM v1's known late-cycle bias post-2008, breaking Gate 10
  differential floor. AM21=B orthogonalizes sizing (R) from
  uncertainty signal (the 0.60 confidence cap) and preserves the
  Layer 3 calibration intact.

## §D21.3 — score_value deprecation

`ScoredObservation.score_value` is now a read-only `@property` that
returns `self.raw_score` while emitting `DeprecationWarning`.
Constructor callers MUST use `raw_score=`. Full removal at the L4–L5
boundary per Decision Lock 3.5D-D3.

## §D21.4 — notes field migration (3.5B + 3.5C lineage)

Layer 3.5D introduces `ScoredObservation.notes: list[str]`. The pre-
3.5D `metadata_extra` keys carrying PIT lineage are migrated into
`notes` via `_format_pit_lineage_notes()` in `crps.py`:

| Pre-3.5D `metadata_extra` key | Migrated form in `notes` |
|---|---|
| `pit_safe_basis_per_component` | "PIT-safe basis per component: …" (one line, only if any non-default basis) |
| `derived_confidence_cap_applied` | "Derived confidence cap applied: MIN=0.70 …" |
| `pit_construction_notes` | (already strings) |
| 3.5C `is_pre_1978_training_only` | "NBER pre-1978 training-mode label (caveat)" — only when reached |

Dedup: `dict.fromkeys(notes)` preserves insertion order while removing
equivalent strings. Spec §6.3-4 + Decision Lock 3.5D-AM25.
