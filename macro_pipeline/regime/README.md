# `macro_pipeline.regime` — Layer 3A Regime Classifier

## §1. Purpose

The `regime` package produces a `RegimeContext` for any historical
`as_of` from 1959 onward, combining four independently-computed views:

| View | Module | Output |
|---|---|---|
| NBER coincident state | `nber_extract.py` | `"expansion"` / `"recession"` (PIT-aware, refuses to ffill past `last_known_label_date`) |
| Kindleberger phase | `kindleberger.py` | `displacement` / `boom` / `euphoria` / `distress` / `revulsion` / `indeterminate` |
| Dalio long-term debt-cycle phase | `dalio_cycle.py` | `early` / `mid` / `late` / `deleveraging` / `indeterminate` |
| 3-state Gaussian HMM | `hmm_states.py` | `expansion` / `late-cycle` / `recession` (frozen pickle, never retrained) |

Aggregator: `regime_context.py` → `RegimeContext`.

Downstream consumers (`scoring.crps`, `scoring.cdrs` from 3C) call
`RegimeContext.derive_regime_state()` to collapse the four views into a
single `(regime_state, source, confidence_haircut)` tuple — see §4.

## §2. Spec deviations (Strategic Claude approved)

### D1 — HMM training window 1982-2019 (spec called for 1959-2019)

Reason: `PHILLY_LEI_PROXY` (FRED `USSLIND`) only starts 1982-01-01, and
it is one of the trained features. Earlier windows would produce NaN
gaps. 1982-2019 yields 456 monthly observations covering the 1990,
2001, and 2008 recessions — enough for a 3-state Gaussian HMM with
random_state=42, n_iter=200, full covariance.

### D2 — HMM feature substitutions (Strategic Claude severity audit)

| Spec feature | Substituted | Severity | Reason |
|---|---|---|---|
| `T10Y3M` | `T10Y2Y` | **LOW** | T10Y3M was not in the FRED registry at 3A time. (Layer 3B has since added T10Y3M to the registry; the HMM still uses T10Y2Y because retraining is deferred to Layer 5.) |
| `SAHMREALTIME` | _dropped_ | LOW | `vintage_required=True`; FRED's ALFRED archive starts 2011-05-23, would empty PIT views for any inference `as_of < 2011-05-23` (including the 2008-09-15 spec proof point) |
| `CFNAIMA3` | `IC4WSA` | LOW | Same vintage-cutoff issue as SAHM; IC4WSA is non-vintage and a reasonable labor-stress proxy |
| `NAPMNOI` | `UMCSENT` | **HIGH** | NAPMNOI was already missing from the FRED loader; UMCSENT is consumer sentiment, a different signal family (mood vs activity). This swap is the root cause of the 2025 HMM=`recession` false positive — post-COVID UMCSENT has been at recession-era lows even during expansion |
| `BAMLH0A0HYM2` | _dropped_ | LOW | Only starts 1996-12; including would shrink training to ~280 obs |

### D3 — Kindleberger thresholds calibrated to the 2007-06 anchor

Spec table (§4.3.2): euphoria fires when `margin debt 24M z-score > +1.5`.
At as_of=2007-06-01 the actual `margin_z_24m` was +1.16, which fell
short of +1.5 and would have produced `indeterminate` instead of the
expected `euphoria`.

Adjusted euphoria triggers (rule-based heuristic v1):

| Trigger | Threshold |
|---|---|
| `cape_rank_above_85` | CAPE percentile > 0.85 |
| `margin_z_above_1p0` | margin debt 24M z > +1.0 |
| `margin_yoy_above_15` | margin debt YoY > +15% |

All three fire at 2007-06-01 (CAPE rank 0.95, margin z 1.16, margin YoY
+29.0%) — phase = `euphoria`. Method tag
`kindleberger_method="rule_based_heuristic_v1"` is recorded on every
output. Layer 5 may calibrate.

### D4 — Dalio returns `indeterminate` for `as_of < ~2011`

Reason: FRED ALFRED vintage panels for `GFDEGDQ188S` /
`A091RC1Q027SBEA` / `FGRECPT` only start 2011-05-23, and the HLW R-star
vintage panel earliest is 2015Q4 published 2016-01-14. PIT views for
older `as_of` are empty for these inputs. The classifier degrades
gracefully and records the missing-data reason in `notes` rather than
fabricating a phase from latest-knowledge data.

## §3. Known limitations

### HMM v1 false-recession bias post-2020

The HMM trained on 1982-2019 didn't see the post-COVID UMCSENT
paradox (sentiment at recession-era lows during expansion), so it
flags 2025-06-01 as `recession` with probability ~1.0 even though
NBER, Kindleberger, and Dalio all read expansion / late-cycle.

**Mitigation today**: `RegimeContext.derive_regime_state()` (Layer
3B) implements an HMM-dissent-neutralization rule when NBER cannot
be consulted at the as_of (i.e. PIT-raised due to the 180d release
lag). When the HMM disagrees with Kindleberger, the function returns
`"late-cycle"` with a 20% confidence haircut. This prevents a single
classifier's drift from dominating downstream CRPS / CDRS scoring.

**Long-term fix** (Layer 5):

1. Add an `NAPMNOI` (or substitute) loader so the HMM is retrained
   with an activity-side signal that doesn't rely on consumer mood.
2. Retrain HMM v2 on 1982-current with the recovered feature set.
3. Validate against post-2020 NBER labels.

### Pre-1982 inference

`build_regime_context` accepts `skip_hmm=True` for as_ofs before the
HMM training window. NBER + Kindleberger + Dalio still run; HMM is
`None` and the conservative properties degrade accordingly.

## §4. `derive_regime_state` priority order + truth table

Signature: `RegimeContext.derive_regime_state() -> tuple[str, str, float]`
returning `(regime_state, source, confidence_haircut)`.

```
Priority:
  1. NBER recession              -> ("recession", "nber", 0.00)
  2. NBER expansion AND Kindleberger ∈ {distress, revulsion}
                                 -> ("late-cycle", "kindleberger_override_nber", 0.10)
  3. NBER expansion              -> ("expansion", "nber", 0.00)
  4. NBER unavailable (PIT-raised at as_of):
     a. HMM corroborated         -> (hmm.state, "hmm_corroborated", 0.05)
     b. HMM dissents              -> ("late-cycle", "hmm_dissent_neutralized", 0.20)
  5. No NBER and no HMM          -> raise RegimeContextError
```

Corroboration truth table (HMM ↔ Kindleberger):

| HMM         | Kindleberger ∈                       | Corroborated? |
|-------------|--------------------------------------|---------------|
| recession   | {distress, revulsion}                | ✓             |
| expansion   | {displacement, boom, euphoria}       | ✓             |
| late-cycle  | {boom, euphoria}                     | ✓             |
| otherwise   |                                      | dissent       |

The `confidence_haircut` flows into `confidence_score_v2` via the
`regime_stability` input (subtracted), so any classifier disagreement
shows up as lower headline confidence on the resulting
`ScoredObservation`.

## §5. Method tags / model versions

| Output field | Value (Layer 3A) |
|---|---|
| `KindlebergerResult.method` | `rule_based_heuristic_v1` |
| `DalioResult.method` | `rule_based_heuristic_v1` |
| `HmmStateResult.model_version` | `regime_3state_v1` |
| HMM pickle path | `data/cache/hmm/regime_3state_v1.pkl` |
| HMM training period | `1982-01-01` to `2019-12-31` (frozen, gitignored pickle) |
| HMM `random_state` / `n_iter` / `tol` | `42` / `200` / `1e-4` |

Layer 5 will introduce HMM v2 with a different `model_version` string
and pickle filename so the v1 results stay reproducible.
