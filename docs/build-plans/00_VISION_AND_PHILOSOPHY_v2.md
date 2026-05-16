# Macro Pipeline — Vision & Philosophy v2.0

**Single source of truth for the entire ecosystem.**

**Version**: 2.0
**Date**: 2026-05-14
**Authored by**: Strategic Claude (Track B) with V's vision
**Authority**: BINDING for all collaborators (Strategic Claude, Claude Code, ChatGPT 5.5, Codex 5.5)
**Status**: ACTIVE from L5b-E onwards

---

## §0 — Why this document exists

This document codifies V's expanded vision so all collaborators operate from one philosophical baseline. V's vision summary:

> "Industrial/mega institutional level + Academic level + cực kì thân thiện UX + đặc biệt nhiều statistics measurements + dễ hiểu cho người mới"

Before this document, four actors (Strategic Claude, Claude Code, ChatGPT 5.5, Codex 5.5) operated with overlapping but not fully aligned guides (v1.x). This v2.0 vision document is the parent reference. All four collaborator-specific guides reference back to this.

Conflicts: this document wins.

---

## §1 — Five-pillar mission (NON-NEGOTIABLE)

The Macro Pipeline serves five masters simultaneously. No pillar is sacrificeable.

### Pillar 1 — Institutional-grade rigor
- 113-year Fed-era reference class (1913-present)
- 11-model ensemble with calibrated weights
- Dimson-Marsh-Staunton survivorship correction mandatory at 5Y/10Y
- Hard sample-size honesty enforced via confidence caps
- Out-of-distribution (OOD) reserve 5-15% mandatory
- Regime-conditional validation across NBER recession/expansion

### Pillar 2 — Academic-grade methodology
- Peer-reviewed statistical methods only:
  - Andrews (1993) supW for structural break detection
  - Bai-Perron (1998) sequential supF for multi-break
  - Benjamini-Hochberg (1995) FDR for multiple testing
  - Politis-Romano (1994) stationary block bootstrap
  - Newey-West (1987) HAC standard errors
  - Hodrick (1992) overlapping observation correction
  - Holston-Laubach-Williams real-time R*
- Replication kit auto-generated for every forecast
- Pre-registered predictions with cryptographic timestamps
- Methodology appendix with full citations
- Sensitivity analysis across methodology choices

### Pillar 3 — Beginner-friendly interpretability
- Every metric has 3-layer explanation: L1 / L2 / L3 (see §11)
- ELI5 mode available for all numeric outputs
- Universal tooltip pattern: 4-part (Plain English / Formal / How to Read / Caveats)
- Auto-generated narrative storytelling from structured data (no hallucination)
- Visual encoding = mathematical meaning
- Search-driven natural-language exploration
- Daily "Statistics Lesson" builds literacy over time

### Pillar 4 — Maximum statistical density
- 90+ statistical measurements tracked simultaneously (see §3)
- Every forecast reports: Probability + % Confidence + Conviction + ≥10 supporting metrics
- Triple σ reporting (return σ, forecast error σ, analog dispersion σ)
- Triple probability decomposition (Probability / Confidence / Conviction — independent)
- Distribution percentiles 5/10/25/50/75/90/95 always shown
- Sensitivity tables for all 5Y/10Y forecasts

### Pillar 5 — Operational discipline
- AP-AUTH register (54 codifications and growing) for institutional learning
- Sxx register for prospective signals
- Gate-based validation (27 gates and growing)
- Sprint retrospectives mandatory at sprint completion
- 25/25+ ACCEPT streak preservation discipline
- Pre-flight read-and-plan + Strategic disposition cycle

---

## §2 — Three audiences, one product

The system simultaneously serves three audiences without compromising any:

### Audience A — V (institutional quant researcher)
- Default view: full statistical density
- Drill-down to methodology immediately accessible
- Numeric outputs preserved exactly (no rounding for "readability")
- Vietnamese-primary with English finance/technical terms preserved
- 3-field conviction (Xác suất / Tin cậy / Tin chắc) on substantive analyses

### Audience B — Sophisticated peer (academic / hedge fund analyst)
- Methodology appendix with citations on demand
- Replication kit downloadable
- Sensitivity analysis to methodology choices
- Calibration track record publicly visible
- Comparison view vs Wall Street consensus + GMO + Hussman + Damodaran

### Audience C — Beginner / educated layperson
- Plain English layer prominent in default view
- "Statistics Lesson of the Day" feature
- ELI5 mode toggle
- Glossary with cross-references
- Visual encoding that builds intuition
- Onboarding tour

**UI pattern (binding)**: Progressive Disclosure.
- Default view = Audience C friendly
- Drill-down = Audience B compatibility
- Deep methodology = Audience A native

No audience blocks any other audience's access to depth.

---

## §3 — Statistical measurements inventory (90+ measures)

Master list of measurements the pipeline tracks or computes. Each measurement has metadata: `plain_english`, `formal_definition`, `how_to_read`, `caveats`, `visual_encoding`, `eli5_template`.

### §3.1 Probability measures (8)
P(outcome), P(A|B) conditional, P(A∩B) joint, P(A∪B) union, F(x) cumulative distribution, q_p quantile, tail probability P(X>x), survival function S(x)

### §3.2 Uncertainty measures (7)
Standard deviation σ, confidence interval CI, credible interval (Bayesian posterior), prediction interval, highest posterior density HPD, forecast error σ, analog dispersion σ

### §3.3 Confidence + Conviction (6)
Probability numeric, % Confidence (0-100), Conviction (1-10), Edge, Kelly fraction f*, Fractional Kelly (0.25-0.50f*)

### §3.4 Goodness-of-fit + Calibration (10)
R², adjusted R², Brier score, Brier improvement vs climatology, calibration slope, reliability diagram, sharpness, CRPS (Continuous Ranked Probability Score), AUC-ROC, log loss

### §3.5 Statistical significance (9)
p-value raw, p-value HAC-adjusted (Newey-West), q-value BH FDR-adjusted, test statistic (supW/t/F), effective sample size N_eff, degrees of freedom df, Type I error α, Type II error β, statistical power (1-β)

### §3.6 Bias correction (7)
DMS survivorship adjustment, Bayesian shrinkage λ, Bonferroni correction, bootstrap bias estimate, OOD reserve mass, look-ahead bias check, survivorship bias check

### §3.7 Risk measures (9)
Value at Risk (VaR), Conditional VaR (CVaR / Expected Shortfall), Maximum Drawdown (MDD), Sortino ratio, Sharpe ratio, Calmar ratio, Information ratio, Beta, tail dependence (λ_lower, λ_upper)

### §3.8 Time-series quality (6)
Autocorrelation ρ(k), Hurst exponent H, ADF stationarity test, cointegration test, structural break test Quandt-Andrews supW, Granger causality

### §3.9 Information theory (4)
Shannon entropy H(X), KL divergence D_KL(P||Q), mutual information I(X;Y), cross-entropy

### §3.10 Bayesian measures (7)
Prior P(θ), likelihood P(D|θ), posterior P(θ|D), Bayes factor BF, marginal likelihood P(D), MAP estimate, MCMC R-hat convergence (Gelman-Rubin)

### §3.11 Macro-specific measures (8)
CAPE percentile, ERP (implied + ex-post), Hussman MAPE, Tobin's Q, Buffett Indicator (mkt cap / GDP), real rate vs R-star, ACM term premium, CCC-BB credit spread (distress proxy)

### §3.12 Regime-conditional (9)
Recession-window Brier improvement, expansion-window Brier improvement, regime sensitivity flag, NBER pre-1978 handling tri-state, regime transition probability, Sahm Rule reading, NY Fed recession probit, LEI 3D rule trigger, ISM Mfg New Orders threshold

**Total: 90+ measurements** with full metadata + L1/L2/L3 explanation per §11.

---

## §4 — Triple Probability Decomposition (BINDING everywhere)

Every forecast reports THREE independent concepts. Never conflate.

### Probability (numeric Bayesian posterior)
- Worked derivation: base rate × likelihood adjustment × regime adjustment
- Confidence interval (95% default) reported alongside
- Example: P(positive 12M) = 65.5% ± 8%

### % Confidence (0-100, meta-uncertainty)
**Formula** (binding):
```
Confidence Score = Data Quality (×25%)
                 + Model Agreement (×25%)
                 + Regime Stability (×20%)
                 + Analog Strength (×15%)
                 + Sample Size (×10%)
                 - OOD Penalty (×5%)
```

**Hard caps** (binding source: §10 Sample Size Honesty table; §4 mirrors §10):
| Horizon | Max Confidence | Source |
|---|---|---|
| **1Y** | **85%** | §10 N≈113 non-overlapping windows |
| **3Y** | **80%** | §10 N≈38 (tight; revised down from §4 v2.0 initial 85%) |
| **5Y** | **80%** | §10 N≈22 (tight; revised down from §4 v2.0 initial 85%) |
| **10Y, non-stratified** | **70%** | §10 N≈11 with autocorrelation insufficient for >70% |
| **10Y, regime-stratified** | **55%** | Standing Order #9 + §10 (regime stratification halves effective N) |
| Any horizon with signal conflict | 75% | §4 modifier (overlays horizon cap; applied via `min(...)`) |
| Any horizon with OOD vs analogs elevated | 70% | §4 + §7 modifier (overlays; applied via `min(...)`) |

**Cap cascade semantics**: caps compose via `min(...)`. Effective cap at any horizon equals `min(horizon_cap, signal_conflict_cap_if_active, ood_cap_if_active)`. The most restrictive cap wins.

**Cross-reference**: §10 is the canonical source-of-truth for horizon caps; this §4 table mirrors §10 verbatim for reader convenience. If §10 changes, update this table to match.

### Conviction (1-10, position-sizing implication)
**Formula** (binding):
```
Conviction = Expected Return Attractiveness
           + Asymmetry (right-tail vs left-tail)
           + Model Agreement
           + Valuation Support
           + Trend Confirmation
           + Liquidity Support
           - Tail-Risk Penalty
           - Crowding Penalty
           - Policy Uncertainty Penalty
           - Forecast Decay Penalty
```

**Critical rule**: Conviction CAN BE LOWER THAN Confidence if risk/reward asymmetry is poor.

Example: "Confidence 72% (data + models agree); Conviction 5.5/10 (valuation asymmetry poor; left-tail underpriced)."

---

## §5 — Triple σ Reporting (BINDING for all return forecasts)

Every return forecast reports THREE distinct σ:

| σ | Definition | Plain English |
|---|---|---|
| **Return σ** | Annualized regime-conditional volatility | What the asset typically does |
| **Forecast error σ** | Model uncertainty around central estimate | What we might be wrong about |
| **Analog dispersion σ** | Historical dispersion from comparable starting conditions | What historical paths showed |

For multi-horizon (3Y/5Y/10Y): distinguish annualized σ from cumulative σ ≈ ann.σ × √N. Explicitly state √t scaling is approximate and may fail during regime shifts, vol clustering, crises, or policy shocks.

---

## §6 — Reference Class Forecasting (MANDATORY)

Every forecast must:
- Anchor to historical analogs (1913-present)
- Report top 3-5 analogs with similarity scores
- Document where current regime DIVERGES from each analog
- Apply Bayesian shrinkage to long-term real return prior (~6.5% real) at 10Y horizon

**Similarity scoring methodology**: cosine similarity on standardized macro state vector x = (CAPE_z, curve_z, LEI_z, credit_z, sentiment_z, breadth_z, vol_z, concentration_z) using L2 norm in 8-dimensional standardized space.

**Authority**: Tetlock & Gardner (2015) reference class methodology; Kahneman (2011) Chapter 22-24.

---

## §7 — OOD Reserve discipline

5-15% probability mass mandatory for OOD (Out-of-Distribution / Unknown Unknowns) outcomes.

| Condition | OOD bucket |
|---|---|
| Standard conditions | 5-8% |
| Valuation >95th percentile | 8-10% |
| Policy regime unprecedented | 10-12% |
| Geopolitical risk elevated | 10-12% |
| Volatility artificially suppressed | 10-12% |
| Financial leverage opaque (NBFI, private credit) | 10-12% |
| Market concentration historical extreme | 12-15% |
| Macro variables contradictory signals | 12-15% |

If 2+ conditions active simultaneously: bucket at upper end of range.

---

## §8 — DMS Survivorship Adjustment (MANDATORY 5Y/10Y)

US is the single best-performing major equity market of the 20th century. Long-horizon US-only data is biased upward.

**Default adjustments**:
| Horizon | Adjustment (annualized) |
|---|---|
| 1Y, 3Y | None (cyclical noise dominates) |
| 5Y | -100 to -150 bps |
| 10Y | -150 to -200 bps |

**Range selection**:
- Lower end (-100/-150 bps): global comparison suggests US structural edge persists
- Higher end (-150/-200 bps): valuations / concentration / fiscal risks elevated

**Apply to BOTH nominal AND real returns** (both biased upward).

**Authority**: Dimson, Marsh, Staunton — Credit Suisse Global Investment Returns Yearbook 2024.

---

## §9 — Lucas Critique discipline

Historical relationships may break when policy regimes change. Flag Lucas critique risk when:

- Fed reaction function shifts (e.g., 2008 ZIRP, 2022 fastest hike since Volcker)
- Fiscal dominance risk rises (debt/GDP > 120%)
- Balance-sheet policy becomes dominant
- Inflation target credibility changes
- AI productivity changes earnings/margin dynamics structurally
- Treasury issuance structure changes materially
- NBFI/private credit alters credit-cycle transmission

**Quantitative test (mandatory)**: out-of-sample backtest performance pre-regime-shift vs post-regime-shift. Material divergence:
- >20% AUC drop, OR
- >50 bps RMSE expansion, OR
- Brier improvement falls below 50% of full-sample value

→ Explicit Lucas critique warning in output.

---

## §10 — Sample Size Honesty (REVISED per academic critique)

Hard limits per horizon:

| Horizon | Non-overlapping windows (1913-present) | Max Confidence | Notes |
|---|---|---|---|
| 1Y | ~113 | 85% | Reasonable |
| 3Y | ~38 | 80% | Tight |
| 5Y | ~22 | 80% | Tight |
| **10Y** | **~11** | **70%** | **REVISED DOWN FROM 85%** — N=11 with autocorrelation makes >70% indefensible |

**Effective sample size** N_eff = nominal N / (1 + 2Σρ(k)) where ρ(k) is autocorrelation at lag k.

Report BOTH nominal N and N_eff for transparency. When N_eff << N, prefer N_eff for confidence calculation.

Bayesian shrinkage mandatory at 10Y horizon — pull toward 6.5% real return prior per DMS data.

---

## §11 — L1/L2/L3 Explanation Stack (BINDING for all outputs)

Every metric, every forecast, every visualization simultaneously displays or makes accessible:

### L1 — Plain English
Beginner-accessible. Uses everyday vocabulary. Example:
> "Có khoảng 2/3 khả năng thị trường tăng trong năm tới, nhưng khá không chắc chắn"

### L2 — Numeric Insight
Sophisticated peer level. Uses precise numbers + confidence intervals. Example:
> "P(positive 12M) = 65.5% ± 8% (95% CI); Confidence 72/100 (Medium-High); Conviction 6.5/10"

### L3 — Methodological Detail
Quant / academic native. Full derivation + citations. Example:
> "P(12M positive) = 73.0% × 0.90 × 1.05 × 0.95 = 65.5% derived via [base rate 1913-2024] × [CAPE p96 regression coef -0.18, p_hac=0.003, q_BH=0.018] × [forward EPS revision +2.1σ] × [NY Fed model P=0.34]. CI ±8% from N=11 ensemble bootstrap (Politis-Romano 1994 stationary block)."

**UI implementation**: 3-state toggle per metric (👶 / 📊 / 🎓). Hover → progressive tooltip expansion. Or click → modal overlay.

---

## §12 — UI/UX Principles (BINDING for L8 design)

### Progressive Disclosure
Default = simple; drill-down = complex. NEVER block depth access. Every number can be drilled to its derivation.

### Universal Tooltips (4-part)
Every statistical term has:
1. **📖 Plain English**: everyday vocabulary
2. **📊 Formal Definition**: mathematical / academic precise
3. **🎯 How to Read It**: practical interpretation rules
4. **⚠️ Caveats**: when NOT to trust

### Visual = Mathematical
Every visual element encodes specific data. No decoration without meaning.

| Encoding | Meaning |
|---|---|
| Bar length | Magnitude |
| Color saturation | Confidence (washed out = low) |
| Position | Quantile / percentile |
| Animation | Time evolution |
| Cone width | Forecast uncertainty (fan chart) |

### Storytelling Mode
Auto-generated narratives from structured data. No hallucination — only data-to-text templates. Each sentence has citation to specific metric.

### Search-driven exploration
Natural language → structured query.
- "What's recession probability?" → recession page
- "CAPE" → CAPE entry with full context
- "Why is conviction low?" → conviction derivation
- "What changed today?" → diff vs yesterday

### ELI5 mode (toggle)
Child-friendly translation of all outputs. Example translations:
- "P(DD >35%) = 18%" → "Picture 100 futures. In 18 of them, market falls more than a third."
- "Conviction 6.5/10" → "If a friend asked how much to bet, you'd say: put in some money, but don't bet the house."
- "Confidence interval: 57-73%" → "We're not 100% sure the probability is 65%. Real answer could be 57% to 73%."

### Daily Statistics Lesson
Mini-lesson every morning. Builds statistical literacy. Linked to today's forecast where the concept applies.

---

## §13 — Calibration Public Accountability

Live calibration track record:

```
CALIBRATION TRACK RECORD (Last 12 Months)
When system said P=60-70%: outcome happened X%
When system said P=70-80%: outcome happened Y%
When system said P=80-90%: outcome happened Z%
Brier score (lower = better): N.NNN
Brier improvement vs climatology: +N.NNN (+N%)
Sharpness (concentration): N.NNN
Reliability slope: 1.00 ± 0.05 (perfect = 1.00)
```

Pre-registered predictions: timestamp + cryptographic hash + replication kit attached. No retroactive fudging possible.

**Authority**: Tetlock superforecasting research; FiveThirtyEight calibration methodology.

---

## §14 — Replication & Audit Discipline

Every forecast version-stamped with:
- Git commit hash of generating code
- Data vintage (timestamp of inputs)
- Methodology version (e.g., v3.1)
- Random seed
- Computational environment (Docker image hash)

**Replication kit** auto-generated on download contains:
- Code (Python) reproducing forecast from scratch
- Raw data (CSV) used
- Random seeds + numerical precision config
- Docker image hash for environment
- Expected output (forecast distribution as JSON)
- Test suite verifying replication

**Read-only audit trail** of every output viewed (who, when, what version, what data vintage) — compliance-grade for SEC examination / IIROC if needed.

---

## §15 — L8 Phasing Strategy

L8 (GUI + Manual Override) split into THREE phases to protect MVP delivery:

### L8a — Core UI (MVP)
**Features**:
- Default forecast view (Audience C friendly)
- Drill-down to derivation (Audience A/B compatibility)
- Universal glossary
- Storytelling mode auto-generated
- Basic alerts (info/watch/action/critical)
- Search bar (natural language)

**Target completion**: 2026-07-28 (median)

### L8b — Academic Features
**Features**:
- Replication kit downloads
- Methodology appendix with citations
- Sensitivity analysis to methodology choices (DMS on/off, frequentist vs Bayesian, etc.)
- Public calibration tracker
- Comparison view vs Wall Street consensus + GMO + Hussman + Damodaran
- Pre-registered prediction archive

**Target completion**: 2026-08-31

### L8c — Educational Features
**Features**:
- ELI5 mode toggle
- Daily Statistics Lesson
- Glossary deep-dive with cross-references
- Beginner onboarding tour (15-min interactive walkthrough)
- "How wrong have we been?" public calibration display
- Statistical literacy progression tracking

**Target completion**: 2026-09-30

**Phasing rationale**: protects MVP delivery while preserving full vision realization. L8a is the minimum lovable product; L8b makes it academically defensible publicly; L8c makes it accessible to broader audience.

---

## §16 — Collaborator alignment

This document is binding for four actors:

| Actor | How to use |
|---|---|
| **Strategic Claude (Track B)** | Reference for all PM decisions; check vision alignment before scope decisions; cite this doc's section numbers when applicable |
| **Claude Code (Track A)** | Reference when implementing UI / interpretability features; ensure code structure supports vision (e.g., metric metadata schema) |
| **ChatGPT 5.5 methodology reviewer** | Reference for methodology critique scope; ensure critiques align with vision (don't critique features V intentionally chose) |
| **Codex 5.5 code reviewer** | Reference for architectural review; check code structure supports vision pillars |

**Update protocol**:
- Minor (v2.0 → v2.1): clarifications, examples, minor corrections — Strategic authors, V approves via paste/git commit
- Major (v2.0 → v3.0): philosophy changes, new pillars — V explicit approval required; Strategic drafts

---

## §17 — Vision conviction (binding format example)

Strategic Claude's calibrated assessment of this vision:

| Trục | Đánh giá | Lý do |
|---|---|---|
| **Xác suất** vision realizable with current architecture | **0.91** | L1-L5 đã build; L5b sprint nearly complete; L6/L7/L8 spec anchored; institutional discipline proven (25+/25+ ACCEPT streak) |
| **Tin cậy** về methodology academic-grade-ness | **0.94** | All methods peer-reviewed; explicit citations; L1/L2/L3 layering grounded in UX research (Nielsen, Tufte); progressive disclosure pattern industry-standard |
| **Tin chắc** about full-stack delivery by 2026-09-30 (L8c) | **0.78** | Calendar reasonable with L8 phasing; binding constraint = V's discipline maintaining sprint pattern through 4 more sprints (L1.7, L6, L7, L8a) before MVP |

**Binding constraint**: V's sprint discipline portable to L6/L7/L8a as it was through L5b. Banked headroom ~88-92h absorbs surprises.

---

## §18 — Anti-patterns (NEVER do)

In addition to standard anti-patterns from existing guides:

1. ❌ Hide complexity from users — Audience C deserves access to depth via progressive disclosure
2. ❌ Dumb down metrics in default view — show numeric, explain accessibly
3. ❌ Auto-generate narratives that don't trace to data — no hallucination
4. ❌ Visual decoration without mathematical meaning — every pixel earns its place
5. ❌ Skip the L3 methodology layer to "simplify" — always available
6. ❌ Round probabilities to "feel cleaner" (e.g., 65.5% → 65%) — preserve precision
7. ❌ Suppress confidence intervals — always show
8. ❌ Backdate forecasts (look-ahead bias) — vintage discipline mandatory
9. ❌ Cherry-pick analogs — top N by similarity, no exclusions
10. ❌ Claim certainty where sample size doesn't support — honor §10 caps
11. ❌ Conflate Probability / Confidence / Conviction — three distinct concepts
12. ❌ Hide methodology to protect "proprietary edge" — full open-source transparency

---

## §19 — Update log

| Version | Date | Author | Changes |
|---|---|---|---|
| 2.0 | 2026-05-14 | Strategic Claude + V | Initial v2.0; consolidates v1.x ecosystem into single source of truth; adds Pillars 3-4 (interpretability + statistical density); L8 phasing; 90+ metric inventory; revised 10Y confidence cap 85→70% |
| 2.1 | 2026-05-16 | Strategic Claude (Track B) + Track A (L6-H exec) | §4 cap table aligned to §10 binding source: 3Y cap 85→80%; 5Y cap 85→80% (matches §10 sample-size-derived caps); 10Y regime-stratified 55% cap surfaced explicitly; cap cascade semantics (compose via `min(...)`); §4 marked as mirror of canonical §10 source. Resolves ChatGPT R7 methodology review Op #3 (HIGH-DOC). No formula change; aggregator + helper cap implementations re-anchored to this table at L6-H. Authority: Strategic L6-H pre-flight 2026-05-16; ChatGPT 5.5 R7 verdict at `l6-g-accept`. |

Future updates appended here with rationale.

---

**END VISION v2.0**

This document is BINDING for all forward sprints. All collaborator guides reference back to specific sections of this document.
