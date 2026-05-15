# Claude Code Pipeline Build Guide v2.0

**Authority for Track A (Claude Code) execution.**

**Version**: 2.0
**Date**: 2026-05-14
**Status**: BINDING from L5b-E onwards
**Parent document**: `00_VISION_AND_PHILOSOPHY_v2.md` (read first)

---

## §0 — Read Vision v2.0 first

`00_VISION_AND_PHILOSOPHY_v2.md` is the master source of truth. This guide implements the vision at the engineering level. Conflicts: Vision v2.0 wins.

Quick links to Vision sections binding for Track A:
- §1 — Five-pillar mission
- §3 — 90+ statistical measurements inventory
- §4 — Triple Probability Decomposition formulas
- §10 — Sample Size Honesty caps (10Y revised to 70%)
- §11 — L1/L2/L3 explanation stack
- §12 — UI/UX principles (binding for L8)
- §15 — L8 phasing strategy

---

## §1 — Track A role definition

Track A (Claude Code) executes code-level builds in `D:/macro_pipeline/.claude/worktrees/layer-5-build` (or active layer worktree).

**Responsibilities**:
- Read pre-flight prompts from Strategic Claude (Track B)
- Author read-and-plan outputs (no code-exec until Strategic greenlight)
- Execute Phase 0..N once greenlit
- Author ACCEPT reports with 3-field conviction
- Maintain test discipline, gate validation, AP-AUTH register

**Boundaries**:
- DOES NOT make scope decisions (that's Strategic)
- DOES NOT skip pre-flight (every sub-phase has read-and-plan)
- DOES NOT proceed without explicit greenlight
- DOES NOT modify pre-flight prompts (Strategic authors them)
- DOES surface ambiguity, blockers, scope concerns to Strategic

---

## §2 — Sprint structure

Each sub-phase follows this pattern:

```
1. Strategic authors pre-flight prompt
2. V pastes pre-flight to Track A
3. Track A reads + plans (read-and-plan only; no code-exec)
4. Track A returns read-and-plan output to V
5. V pastes to Strategic
6. Strategic renders disposition (ACCEPT plan / NOTES / REVISION)
7. V pastes greenlight (or revision request) to Track A
8. Track A executes Phase 0..N
9. Track A returns ACCEPT report
10. V pastes to Strategic
11. Strategic confirms ACCEPT (or requests revision)
```

**Discipline points**:
- Phase 0 = baseline smoke test ALWAYS
- Mid-stream pytest checkpoint at appropriate phase
- AP-AUTH-42 preemptive scan before commit
- Pre-commit hooks must PASS
- Conviction floor ≥0.90 for ACCEPT

---

## §3 — Standing Orders (UPDATED per Vision v2.0)

1. **3-field conviction reporting** (Vietnamese-primary; Xác suất / Tin cậy / Tin chắc) with **binding constraint named** — applies to all ACCEPT reports
2. **Empirical claim verification** via grep/AST audit for universal claims
3. **Pause-and-verify** per sub-phase
4. **Conviction floor ≥0.90** for ACCEPT
5. **Cross-reference integrity verification** before commit
6. **AP-AUTH register additions** for institutional learning
7. **NEW: Vision alignment check** — before scope changes, verify alignment with 5-pillar mission
8. **NEW: 90+ measurements awareness** — when implementing user-facing features, ensure relevant metrics from Vision §3 inventory available
9. **NEW: L1/L2/L3 explanation support** — when building data structures, include metadata fields for L1/L2/L3 explanation per Vision §11
10. **NEW: 70% confidence cap at 10Y** — enforce in code (revised from 85%)

---

## §4 — AP-AUTH register (institutional learning)

54 codifications as of 2026-05-13. Highlights for Track A reference:

### AP-AUTH-42 v6: Cumulative arithmetic precommit
Word-form discipline for numerical accumulation across multi-sub-phase documents. Preemptive scan before commit. Critical for retrospectives.

### AP-AUTH-46: Gratuitous-Sxx guard
Prospective-only signals don't get Sxx-numbered registry entries unless production-affecting.

### AP-AUTH-50: Upstream grep at pre-flight
Mandatory grep audit before scoping new sub-phase. Prevents scope-conflict with existing infrastructure.

### AP-AUTH-51: Risk register grep evidence
Risk register entries cite grep evidence (file paths + line numbers).

### AP-AUTH-52: Magic numbers derivable
Every magic number cites primary source (paper / spec / institutional default). No unjustified constants.

### AP-AUTH-53: Reviewer-driven kickoff pattern
7-step closure mechanism for reviewer-driven kickoff items: (1) reviewer concern grep + verdict severity, (2) institutional anchor citation, (3) no-default field discipline, (4) AP-AUTH-50 upstream grep, (5) AP-AUTH-51 risk register, (6) pause-and-verify empirical evidence, (7) Sxx prospective-only marker per AP-AUTH-46.

### AP-AUTH-54: Internal-implementation variant
In-place refactor of internal helper + no-default field on related dataclass + Gate Option Y (signature inspection + AST audit + runtime probe) + pre-flight empirical evidence.

**Envelope range characterization (closed at 4 instances)**:
- KICK-4 heaviest: inner-CV refactor + field + AST
- KICK-5 medium: tuple-return helper + dual fields
- KICK-6 lightest: dataclass discipline only
- L5b-A heavy: stationary block bootstrap

Within-envelope variants accommodate novel sub-characteristics (new files, new gates, Optional types, Callable injection) without redefining envelope range.

---

## §5 — Gate architecture

27 gates as of 2026-05-13. Categories:

| Gate range | Purpose |
|---|---|
| Gates 1-18 | L1-L4 build (data, regime, scoring, layers) |
| Gates 19-25 | L5 build (forecast models, OOS calibration) — Gate 25 SEALED at L5-G |
| Gate 26 | L5b-C FDR gating (first NEW post-SEAL; cross-cutting downstream consumer) |
| Gate 27 | L5b-D regime-conditional validation (2nd NEW post-SEAL) |
| Gate 28 (pending L5b-E) | L5b retrospective file-presence |

**Gate design discipline**:
- Each gate has 4 criteria typically
- Mix of: signature inspection + AST audit + runtime probe + negative probe (e.g., monkeypatch fails)
- CLI dispatcher registration required (`python -m macro_pipeline.validation gateN`)
- Tests cover gate behavior

---

## §6 — Sxx register

Tracking signal-level codifications across the sprint. As of 2026-05-13:

- Sxx-1..12: pre-L5b (various)
- Sxx-13..23: L5b sprint (11 consecutive prospective-only triages per AP-AUTH-46 guard)
- Sxx-24+ : future

All Sxx-13..23 are prospective-only (not production-affecting). Pattern demonstrates AP-AUTH-46 institutional discipline working as designed.

---

## §7 — Pipeline architecture (layers)

### Layer 1 — Data Ingestion (L1)
Multi-source data fetching from FRED, BLS, BEA, Shiller, NBER, Damodaran, etc.

**L1.7 pending**: MANUAL_INPUT framework — V can override specific inputs for nowcasting scenarios.

### Layer 2 — Indicator Catalog (L2)
186+ indicators defined in `us_macro_equity_indicator_catalog_v1.csv` with metadata: source URL, frequency, lead/lag, reliability tier (1-4).

### Layer 3 — Regime Classification (L3)
NBER regime classifier via `NberCalendarLoader.last_known_label(as_of).regime`.

**Decision Lock 3.5C-D1**: pre-1978 NBER dates unreliable; fails-closed at real-time; training-only mode with `is_pre_1978_training_only=True` flag.

### Layer 4 — Scoring (L4)
Drawdown conditionals, forecast σ, component panels.

### Layer 5 — Forecast Models (L5 + L5b)
**Complete**: 11-model ensemble with Ridge baseline + isotonic calibration + Bayesian shrinkage + DMS adjustment + structural break tests + FDR gating + regime-conditional OOS validation.

**Sub-phases delivered**: L5-A..H (8 sub-phases) + L5b-KICK-1..7 (7 kickoff sub-phases) + L5b-A..D (4 hardening sub-phases) + L5b-E (pending FINAL).

### Layer 6 — Ensemble Aggregation (L6) — PENDING
Combines 11-model outputs into final probabilistic forecast distribution. Per Vision v2.0 §1 Pillar 4: produces 90+ measurements per forecast.

### Layer 7 — Scheduling + Alerting (L7) — PENDING
Daily auto-run; alert system with 4 severity levels (INFO/WATCH/ACTION/CRITICAL).

### Layer 8 — GUI + Manual Override (L8) — PENDING
**L8 phased per Vision v2.0 §15**:
- L8a Core UI (MVP)
- L8b Academic Features
- L8c Educational Features

---

## §8 — Implementation requirements per Vision v2.0

### §8.1 Metric metadata schema

Every metric in the pipeline (90+ total per Vision §3) must have a metadata object:

```python
@dataclass(frozen=True)
class MetricMetadata:
    name: str                          # Canonical name
    category: str                      # Per Vision §3 sub-section
    plain_english: str                 # L1 explanation
    formal_definition: str             # L2/L3 academic precise
    how_to_read: list[str]             # Practical interpretation rules
    caveats: list[str]                 # When NOT to trust
    visual_encoding: str               # "bar" | "violin" | "fan" | etc.
    eli5_template: str                 # ELI5 mode auto-generation template
    learn_more_url: str                # Deep-dive link
    related_metrics: list[str]         # Cross-references
    primary_source: str                # Academic citation
```

Implementation: `macro_pipeline/metadata/metric_registry.py` (NEW module; pending L6 or L8a).

### §8.2 Triple decomposition data structure

```python
@dataclass(frozen=True)
class TripleDecomposition:
    probability: float                 # Numeric Bayesian posterior
    probability_ci_lower: float        # 95% CI lower
    probability_ci_upper: float        # 95% CI upper
    confidence_score: float            # 0-100 per Vision §4 formula
    confidence_label: str              # "Low" | "Medium" | "Medium-High" | "High"
    confidence_components: dict[str, float]  # 5 sub-components
    conviction_score: float            # 1-10 per Vision §4 formula
    conviction_label: str              # "Avoid" | "Underweight" | ... | "Aggressive overweight"
    conviction_components: dict[str, float]  # Up to 10 sub-components
    binding_constraint: str            # Named constraint
    horizon: Literal["1Y", "3Y", "5Y", "10Y"]

    def __post_init__(self) -> None:
        # Enforce confidence cap per Vision §4 hard caps.
        if self.horizon == "10Y" and self.confidence_score > 70.0:
            raise ValueError(
                f"Confidence {self.confidence_score} exceeds 10Y hard cap 70% per Vision v2.0 §10"
            )
        # Additional invariants...
```

### §8.3 Triple σ data structure

```python
@dataclass(frozen=True)
class TripleSigma:
    return_sigma_annualized: float     # Regime-conditional volatility
    forecast_error_sigma: float        # Model uncertainty
    analog_dispersion_sigma: float     # Historical analog dispersion
    cumulative_horizon: int            # Years
    scaling_note: str                  # Caveat about √t scaling
```

### §8.4 OOD reserve enforcement

```python
def compute_ood_reserve(conditions: OODConditions) -> float:
    """Compute OOD bucket per Vision v2.0 §7."""
    base = 0.05  # 5% minimum
    extras = 0
    if conditions.valuation_above_p95: extras += 0.02
    if conditions.policy_unprecedented: extras += 0.03
    if conditions.geopolitical_elevated: extras += 0.03
    if conditions.vol_suppressed: extras += 0.03
    if conditions.leverage_opaque: extras += 0.03
    if conditions.concentration_extreme: extras += 0.05
    if conditions.signals_contradictory: extras += 0.05
    # Cap at 15%.
    return min(base + extras, 0.15)
```

### §8.5 Confidence cap enforcement

```python
def enforce_confidence_caps(
    raw_confidence: float,
    horizon: Literal["1Y", "3Y", "5Y", "10Y"],
    signal_conflict: bool,
    ood_vs_analogs: bool,
) -> float:
    """Enforce hard confidence caps per Vision v2.0 §10."""
    if horizon == "10Y":
        return min(raw_confidence, 70.0)
    if signal_conflict:
        return min(raw_confidence, 75.0)
    if ood_vs_analogs:
        return min(raw_confidence, 70.0)
    return min(raw_confidence, 85.0)
```

---

## §9 — Pre-flight read-and-plan template

When Track A receives a Strategic pre-flight prompt, the read-and-plan output should include:

```markdown
# [Sub-phase ID] — Read-and-Plan Output

**Anchors**: HEAD [commit] (tag [tag]) · baseline [N] tests passing · [other anchors]

## ITEM 1 — Upstream grep audit (AP-AUTH-50 evidence)
[Empirical findings; surface conflict with existing infrastructure if any]

## ITEM 2 — Approach disposition
[A/B/C with rationale]

## ITEM 3 — Method design
[Algorithm sketch; dataclass design; helper structure]

## ITEM 4 — Test plan
[N new tests with POS/NEG breakdown; floor ≥50% NEG]

## ITEM 5 — Effort estimate
[Nominal / Risk-adjusted; convergence-prior projection]

## ITEM 6 — Risk register (AP-AUTH-51 grep evidence)
[Risks with severity + mitigation + evidence]

## ITEM 7 — AP-AUTH envelope analysis
[Which envelope variants? Stays closed or re-opens?]

## ITEM 8 — Conviction (3-field Vietnamese-primary) + binding constraint
[Xác suất / Tin cậy / Tin chắc with derivation]

## Phase plan
[Phases 0..N with LOC deltas]

**Standing by for Strategic disposition.**
```

---

## §10 — ACCEPT report template

When Track A completes a sub-phase:

```markdown
# [Sub-phase ID] — ACCEPT REPORT

## Commit anchor
| Field | Value |
|---|---|
| HEAD | [commit] |
| Tag | [tag] |
| Parent | [parent commit] |
| Branch | [branch] |
| Diff stat | +X / -Y lines across N files |

## Files modified
[Table]

## Conviction (3-field Vietnamese-primary)
[Xác suất / Tin cậy / Tin chắc with binding constraint]

## Deltas
| Metric | Before | After | Δ |
|---|---|---|---|
| Test count | | | |
| Gate count | | | |
| ... | | | |

## Watch-points retrospective
[All watch-points from Strategic disposition checked]

## Effort actual vs budget
[Pre-flight read-and-plan + code-exec + pytest sweep]

## Sprint progress
[Where this fits in the larger sprint]

**Track A: [sub-phase] closed. Awaiting Strategic disposition on [next sub-phase].**
```

---

## §11 — Test discipline

- Pre-existing tests must continue passing (zero regression)
- New tests: POS + NEG mix (≥50% NEG-flavor)
- Mid-stream pytest checkpoint at Phase 6 (typical) or appropriate phase
- Final pytest full sweep at Phase 9 (typical) before commit

Test count progression through L5b sprint:
- Pre-L5b: 717 tests
- L5b-KICK-1..7: 753 tests (+36)
- L5b-A: 758 tests (+5)
- L5b-B: 764 tests (+6)
- L5b-C: 770 tests (+6)
- L5b-D: 777 tests (+7)
- L5b-E (pending): 780 tests expected (+3)

---

## §12 — Anti-patterns (DO NOT)

1. ❌ Execute code without Strategic explicit greenlight
2. ❌ Skip Phase 0 baseline smoke test
3. ❌ Skip mid-stream pytest checkpoint
4. ❌ Commit without AP-AUTH-42 preemptive scan
5. ❌ Round numerical outputs in retrospective documents
6. ❌ Re-compute cumulative metrics — pull from sub-phase ACCEPT reports
7. ❌ Modify pre-flight prompts (Strategic-only authority)
8. ❌ Codify new AP-AUTH without Strategic disposition
9. ❌ Bypass gate validation by direct test assertion
10. ❌ Use Unicode chars that trip Windows console encoding (L5b-D lesson; use ASCII alternatives)

---

## §13 — V's preferences (PRESERVED)

V is institutional quant macro-equity researcher. Communication preferences:
- Vietnamese-primary with English finance/technical terms preserved
- Tabular outputs preferred
- 3-field conviction (Xác suất / Tin cậy / Tin chắc) on substantive analyses
- HTML dark financial terminal aesthetic for forecast output (relevant for L8 design)
- Explicit numeric probability + conviction + confidence (Vision §4)

---

## §14 — Update log

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-03 | Initial guide |
| 1.1 | 2026-04 | Reviewer feedback integration |
| 1.2 | 2026-04 | Pre-L5b sprint patterns |
| **2.0** | **2026-05-14** | Per Vision v2.0; new §3-§4 Standing Orders; metric metadata schema; triple decomposition + triple σ data structures; OOD enforcement; confidence cap revision (10Y 85→70%); L8 phasing reference |

---

**END Pipeline Guide v2.0**
