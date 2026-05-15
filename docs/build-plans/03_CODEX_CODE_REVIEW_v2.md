# Code Review Request — Codex 5.5 — v2.0

**Reviewer authority**: Senior software engineer + code quality auditor + architectural reviewer.
**Style**: Direct, evidence-based, prioritized. Cite line numbers + file paths.
**Output language**: English (Vietnamese if requester prefixes with [VN]).

**Parent document**: `00_VISION_AND_PHILOSOPHY_v2.md` — read first for vision alignment context.

---

## §0 — Vision v2.0 alignment

Code reviews must support Vision v2.0's 5-pillar mission. Specifically:

- **Pillar 5 (Operational discipline)**: code structure should reflect institutional engineering quality
- **Pillar 4 (Statistical density)**: code should support 90+ measurements metadata schema
- **Pillar 3 (Beginner-friendly interpretability)**: code structure should support L1/L2/L3 explanation stack (e.g., metric metadata fields)
- **Pillar 2 (Academic methodology)**: code should be replication-ready

Do not critique architectural choices made for vision alignment as "over-engineering" — V wants this.

---

## §1 — Context (UPDATED)

The Macro Pipeline is at `github.com/mvfoundation01/macro-pipeline` (PUBLIC). As of 2026-05-13:

- **HEAD**: `claude/layer-5-build` @ `92a219c` (tag `l5b-d-accept`)
- **Test count**: 777 passing
- **Gate count**: 27 (Gate 25 SEALED at L5-G; Gate 26 + Gate 27 NEW at L5b-C/D)
- **AP-AUTH register**: 54 codifications
- **Sxx register**: 0 active; 11 prospective-only across L5b sprint
- **Modules built**: data ingestion (L1), indicator catalog (L2), regime classification (L3), scoring (L4), forecast models (L5 complete + L5b sprint nearly complete)

**Pending**: L5b-E (FINAL L5b sub-phase) → L1.7 → L6 → L7 → L8a/b/c.

---

## §2 — Your task

Provide a **code quality review** focused on the following 12 dimensions (10 from v1.x + 2 NEW per v2.0 vision).

For each dimension, give:
- **Verdict**: PASS / NEEDS REVISION / FAIL
- **Specific issue(s)** with file path + line numbers
- **Recommended fix** (concrete, actionable, with code snippet if applicable)
- **Severity**: HIGH / MEDIUM / LOW

---

## §3 — Review dimensions (12 total)

### Dimension 1: TYPE SAFETY + DATACLASS DISCIPLINE

- Are dataclasses frozen?
- Are no-default fields enforced per AP-AUTH-53 step #3?
- Are Literal types used for tri-state semantics?
- Are `__post_init__` invariants comprehensive?
- Are Optional types documented for None-disabling semantic?
- Are tuple types used instead of lists for immutability?

### Dimension 2: ERROR HANDLING

- Are exceptions raised with semantic ValueError vs TypeError?
- Are invariant violations explicit with field name + offending value?
- Are degenerate cases (empty inputs, NaN, edge cases) handled?
- Are error messages helpful (cite expected vs got)?

### Dimension 3: DOCSTRING QUALITY (UPDATED per Vision v2.0)

- Are module docstrings substantive (not stub)?
- Do helpers have docstrings explaining algorithm + cite primary source per AP-AUTH-52?
- **NEW**: Do metric-related code have metadata supporting L1/L2/L3 explanation per Vision §11?

### Dimension 4: TEST COVERAGE + DISCIPLINE

- Are new tests in NEW test files for new modules (separation)?
- POS/NEG ratio ≥50% NEG?
- Mid-stream pytest checkpoint discipline observed?
- Edge cases covered (empty subset, NaN, regime transitions)?
- Test names descriptive (verb-driven)?

### Dimension 5: GATE ARCHITECTURE

- Gate criteria 4-part structure (API + algorithm + runtime + invariant)?
- AST audit substring matches reliable?
- Runtime probe synthesizes representative fixture?
- CLI dispatcher registered?
- Gate report findings string format consistent?

### Dimension 6: AP-AUTH COMPLIANCE

- AP-AUTH-42 v6 cumulative arithmetic discipline observed in retrospective?
- AP-AUTH-46 gratuitous-Sxx guard applied?
- AP-AUTH-50 upstream grep evidence cited at pre-flight?
- AP-AUTH-51 risk register grep evidence cited?
- AP-AUTH-52 magic numbers derivable via citation?
- AP-AUTH-53/54 envelope mechanisms preserved?

### Dimension 7: STATISTICAL METHODOLOGY CORRECTNESS

- BH step-up monotone form correct (np.minimum.accumulate reverse)?
- Quandt-Andrews supW simplified Wald approximation documented?
- Politis-Romano stationary block sampling geometric distribution correct?
- Newey-West HAC bandwidth selection (Andrews 1991)?
- Confidence cap enforcement at code level (per Vision §10)?

### Dimension 8: NUMERICAL PRECISION

- Float comparisons use tolerance (np.allclose with explicit atol/rtol)?
- Subset Brier with empty inputs returns NaN cleanly?
- Probability bounds [0, 1] enforced?
- Magic-number rounding avoided (preserve precision per Vision anti-pattern)?

### Dimension 9: MODULE ORGANIZATION

- New modules placed in correct subdirectory (analysis/ vs models/ vs scoring/)?
- Cross-module dependencies minimized?
- Single Responsibility Principle observed?
- Imports organized (stdlib / third-party / first-party)?

### Dimension 10: CONCURRENCY + REPRODUCIBILITY (UPDATED per Vision v2.0)

- Random seeds explicit?
- **NEW**: Replication kit can be auto-generated per Vision §14?
- Vintage data handling preserves point-in-time validity (no look-ahead)?
- Docker / environment hash captured?

### Dimension 11: METRIC METADATA SCHEMA SUPPORT (NEW per Vision v2.0)

Vision v2.0 §3 requires 90+ measurements with metadata supporting L1/L2/L3 explanation.

**Critique questions**:
- Does current code structure support adding `MetricMetadata` schema to all metric-producing functions?
- Are metric names canonical / referenceable across modules?
- Is there a central registry pattern for metric metadata (e.g., `macro_pipeline/metadata/metric_registry.py`)?
- Can metrics be tagged with category (probability / uncertainty / etc.) cleanly?
- Are metric outputs serializable to JSON for replication kits?

### Dimension 12: VISION-ALIGNMENT CODE PATTERNS (NEW per Vision v2.0)

Vision v2.0 §11 mandates L1/L2/L3 explanation; §12 mandates Progressive Disclosure UX.

**Critique questions**:
- Are forecast output dataclasses (`TripleDecomposition`, `TripleSigma`) designed to support multi-level rendering?
- Does code support both raw numeric output AND human-readable rendering?
- Are confidence caps enforced via `__post_init__` invariants per Vision §10?
- Is OOD reserve computation centralized per Vision §7?
- Is DMS adjustment centralized per Vision §8?

---

## §4 — Deliverable structure (UPDATED)

```markdown
# Code Review v2.0 — [Date]

## Overall Assessment
[1-paragraph: PASS / NEEDS MAJOR REVISION / FAIL]

## Vision v2.0 Alignment
[1-paragraph: code structure support for vision pillars]

## Findings by Dimension (1-12)

### 1. Type Safety + Dataclass Discipline
- **Verdict**: [PASS / NEEDS REVISION / FAIL]
- **Severity**: [HIGH / MEDIUM / LOW]
- **File:line citations**: [...]
- **Issues**: [...]
- **Recommendations** (with code snippets where applicable): [...]

[Repeat for dimensions 2-12]

## Top 5 Critical Fixes (Ranked)
1. ...
[etc.]

## Refactoring Opportunities
- ...

## Things Done Well (Preserve)
- ...

## Vision v2.0 Code Recommendations
[Suggestions for code structure to better support vision pillars]
```

---

## §5 — Reviewer constraints

- DO comment on code quality, architecture, type safety, test discipline
- DO NOT comment on methodology choices (that's ChatGPT's job)
- DO cite specific file paths + line numbers
- DO provide code snippets for fixes
- DO challenge AP-AUTH compliance if violated
- **NEW: Check alignment with Vision v2.0 code patterns (Dimensions 11-12)**
- **NEW: Do NOT critique architectural complexity if it serves vision pillars** (e.g., 14-field dataclass for `RegimeConditionalDiagnostics` is justified by Vision §3 statistical density requirement)

---

## §6 — Calibration check

Before submitting:
- ✓ Cited specific file paths + line numbers
- ✓ Provided ≥3 actionable code-level recommendations
- ✓ Flagged any HIGH-severity issues
- ✓ **Checked metric metadata schema support per Dimension 11** (NEW)
- ✓ **Verified vision-alignment code patterns per Dimension 12** (NEW)
- ✓ Honestly assessed where critique is itself uncertain

If yes to all, submit. If no, refine.

---

## §7 — Update log

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-04 | Initial code review request |
| **2.0** | **2026-05-14** | Per Vision v2.0; added Dimensions 11-12; updated Dimension 3 (metric metadata) and Dimension 10 (replication kit) |

---

**END Code Review v2.0**
