# Anti-Pattern Register — Layer 5 spec authoring cycle (snapshot at v6)

**Project**: macro-pipeline
**Branch**: `claude/layer-5-spec` (HEAD `9f848bb` tag `layer5-spec-v6`)
**Snapshot date**: 2026-05-12
**Scope**: APs codified IN the Layer 5 spec + process-level v6 scope guards from chunk 14 verification

---

## §0 — Provenance notice

This register **consolidates** entries from two sources:

1. **`LAYER_5_BUILD_SPEC.md` §12** (canonical body) — contains L5-specific project anti-patterns (AP-16..AP-21) + Strategic build-discipline anti-patterns (AP-AUTH-39..42).
2. **`LAYER_5_V6_CHUNK_14_VERIFICATION.md` §7** — references process-level scope guards AP-AUTH-43..46 used during the v6 surgical scrub.

**AP-AUTH-1 through AP-AUTH-38 base set**: codified in `HANDOFF_CLAUDE_CODE_v4.md` (V's local file; **not committed to repo**) per spec §12 header note "preserved from `HANDOFF_CLAUDE_CODE_v4.md` §7 + L3.5b retrospective". Cumulative AP-1..AP-15 from prior layers (L1..L3.5) also referenced but not enumerated in this artifact since they pre-date L5. ChatGPT 5.5 reviewing should treat AP-AUTH-1..38 + AP-1..AP-15 as out-of-repo institutional knowledge.

---

## §1 — L5-specific project anti-patterns (AP-16..AP-21; from spec §12)

| AP | Symptom (verbatim from spec §12) |
|---|---|
| **AP-16 NEW** | Walk-forward CV with cross-fold contamination (train_end ≥ test_start - gap_months); detected via §2.5 audit |
| **AP-17 NEW** | Ridge λ chosen by in-sample CV without nested walk-forward; introduces look-ahead bias in OOS evaluation |
| **AP-18 NEW** | Isotonic calibrator fit on test fold and reused on later test fold (across-fold leakage); detected via §2.5 audit |
| **AP-19 NEW** | DMS bps applied to 1Y or 3Y output paths (DMS adjustment is a long-horizon survivorship correction; only 5Y/10Y); detected via §2.5 audit |
| **AP-20 NEW** | Bayesian shrinkage weight as a constant (e.g., `weight = 0.30` literal anywhere); spec mandates horizon-dependent + sample-size-adaptive; detected via §2.5 audit |
| **AP-21 NEW** | `score_value` references re-introduced post-3.5D rename; 3.5D D24 deprecation warning preserved through L5; full removal at L4-L5 boundary deferred to L5-RM-4 absorbing the boundary |

---

## §2 — Strategic build-discipline anti-patterns (AP-AUTH-39..42; from spec §12)

These are the four anti-patterns added during the v4 → v5 → v6 spec authoring cycles. Each codifies a specific class of audit-gap discovered when ChatGPT 5.5 found a defect missed by the prior round's self-audit.

### §2.1 — AP-AUTH-39 NEW v4

**Symptom**: Updating gate PASS criteria in owning §5.X.6 sub-phase WITHOUT updating the consolidated §6.N gate mirror (dual-anchor synchronization miss); detected by grep audit comparing §5.X.6 vs §6.N test counts + API names + literal values; v3 missed Gate 19/21/23/25 sync in §6.2/§6.4/§6.6/§6.8 → ChatGPT v3 §C.1 HIGH flag → v4 fixed all 4 plus added defensive mirror-anchor summary lines per §5.B.5/§5.RM-6.5/§5.D.5/§5.G.5.

**Mitigation discipline**: when patching any §5.X.6 PASS criterion or API name or test count, the build agent MUST also grep-audit §6 consolidated mirror for matching anchor and update in same commit; `LAYER_5_AUTHORING_SUMMARY` mirror integrity table per chunk verification report enforces 4-anchor check (§5.X.5 == §5.X.6 == §5.X.7 == §6.N).

### §2.2 — AP-AUTH-40 NEW v5

**Symptom**: Filing Sxx that documents a change to spec methodology/structure WITHOUT propagating the change to spec body sections AND consolidated mirrors AND proof contracts (Sxx-to-spec-body propagation miss); detected by grep audit comparing Sxx register entry intent vs spec body anchors; **v3 S-2 said "5 → 6 new slots"** but §5.RM-4 metadata (.0) + intro (.1 intro paragraph) + Gate 20 PASS criterion (.6) + proof (.7) + §6.3 consolidated mirror + §4 decomp ALL still said "5 new / 30 total"; v4 AP-AUTH-39 dual-anchor caught §5.X.6/§6.N pairs but NOT the Sxx-to-body propagation because it's a third anchor pattern; ChatGPT v4 §C.2 HIGH flagged → v5 fixed all 5 propagation anchors + added defensive mirror-anchor verification.

**Mitigation discipline**: when filing any Sxx documenting a change to spec methodology, structure, or numbers, the build agent MUST grep-audit FOR every spec section that references the changed item (use Sxx topic keywords) AND update each propagation anchor in same commit; verification report MUST verify Sxx-to-body propagation per anchor with verbatim grep output. Cumulative test count proof contracts MUST use symbolic wording (`previous + L5-X delta`) NOT hard-coded arithmetic to prevent recurrence.

### §2.3 — AP-AUTH-41 v6 STRENGTHENED

**Symptom**: Claiming mirror integrity "verified" without **BOTH** verbatim positive grep (new pattern present) AND verbatim negative grep (old pattern absent) per anchor. v4 self-audit claimed 16/16 alignment but actually 14/16 because §5.X.7 anchors not grepped at all. v5 self-audit claimed 20/20 alignment but actually 17/20 because RM-4 anchors grepped positive-only ("31 slots / 6 new" present) without negative grep ("30 slots / 5-slot" absent), missing 8+ stale references in §5.RM-4.2/.4/.5/.6/.7. v6 codifies: every claimed-alignment anchor requires BOTH pos+neg grep documented in verification report.

**Mitigation**: verification table MUST show `grep -nE "<positive>"` AND `grep -nE "<negative>"` output per anchor; bare assertion "ALIGNED" without both proofs is REVISE-REQUIRED.

### §2.4 — AP-AUTH-42 NEW v6

**Symptom**: Filing cumulative test-count arithmetic in proof contracts as hard-coded numbers (e.g., `602 + 78 = 680` or `602 + 8 = 610`) instead of symbolic placeholders (`previous baseline + L5-X delta`). Prevents future drift when sub-phase test counts change. AP-AUTH-40 mitigation list MUST include grep target regex `[0-9]+ \+ [0-9]+ =` to catch ALL cumulative arithmetic patterns, not just specific instances. v5 missed `602 + 8 = 610` and `602 + 78 = 680` because AP-AUTH-40 mitigation list was specific-instance not regex. v6 codifies: cumulative arithmetic scrub uses regex `[0-9]+ \+ [0-9]+ =` to catch all variants.

**Mitigation discipline**: every proof-contract item containing cumulative test count MUST use symbolic wording; grep regex must catch numeric arithmetic patterns before commit.

---

## §3 — V6 process-level scope guards (AP-AUTH-43..46; from chunk 14 verification §7)

These four scope guards govern the v6 surgical scrub execution discipline. They were enforced by Track A during chunk 14 authoring (compliance recorded 100% per chunk 14 verification §7).

| AP | Symptom (per chunk 14 verification §7) | v6 compliance |
|---|---|---|
| **AP-AUTH-43** | (Referenced as "this chunk's additions"; specific symptom not enumerated in chunk 14 verification §7 — likely scope guard codifying AP-AUTH-41 + AP-AUTH-42 themselves as authoring deliverables for v6) | n/a — adding |
| **AP-AUTH-44** | Modify beyond v6 scope (i.e., touching sections outside the v5 §E + Strategic §2.4 patch list) | NO violation — surgical edits limited to §5.RM-4 + §5.H.5 + §12 + §5.RM-4.8 NEW |
| **AP-AUTH-45** | Force-push v5 tag (overwriting `layer5-spec-v5` annotation/SHA) | NO violation — v5 tag preserved at `036a454`; v6 tag added separately at `9f848bb` |
| **AP-AUTH-46** | File Sxx without methodology need (gratuitous register entries for cleanup-only changes) | NO violation — 0 Sxx filed during v6 (cleanup-only chunk) |

**Note**: AP-AUTH-43..46 are **process-level guards** governing how Strategic Claude authors v6, NOT methodology anti-patterns codified in the spec body. They live in chunk 14 documentation rather than spec §12. ChatGPT 5.5 reviewing v6 should treat them as build-discipline meta-rules, not in-spec methodology requirements.

---

## §4 — Cumulative AP map (out-of-repo references)

Per spec §12 header: "Cumulative AP-1 through AP-15 from prior layers apply." Also per V's `HANDOFF_CLAUDE_CODE_v4.md` (out-of-repo), AP-AUTH-1..38 codify project baseline + L3.5/L3.5b cycle anti-patterns.

| Range | Source | Topic | In repo? |
|---|---|---|---|
| AP-1..AP-15 | L1..L3.5 layer specs + retrospectives | Project baseline methodology anti-patterns | Partially (L3.5b retrospective in repo) |
| AP-AUTH-1..21 | HANDOFF_CLAUDE_CODE_v4.md §7 | Project baseline build-discipline | NO (V's local) |
| AP-AUTH-22..32 | HANDOFF_CLAUDE_CODE_v4.md (v1+v2 cycle additions) | L5 v1+v2 era build-discipline | NO (V's local) |
| AP-AUTH-33..38 | HANDOFF_CLAUDE_CODE_v4.md (v3 cycle additions) | L5 v3 surgical-scope discipline | NO (V's local) |
| **AP-16..AP-21** | **spec §12** | **L5 project methodology anti-patterns** | **YES (this artifact §1)** |
| **AP-AUTH-39..42** | **spec §12** | **L5 v4/v5/v6 audit-instrument anti-patterns** | **YES (this artifact §2)** |
| **AP-AUTH-43..46** | **chunk 14 verification §7** | **v6 process-level scope guards** | **YES (this artifact §3)** |

---

## §5 — v6 audit-gap closure summary

Comparing v3 → v4 → v5 → v6 audit-instrument anti-patterns:

| Cycle | AP added | Gap class closed |
|---|---|---|
| v4 | AP-AUTH-39 | §5.X.6 ↔ §6.N dual-anchor sync miss (ChatGPT v3 §C.1) |
| v5 | AP-AUTH-40 | Sxx-to-spec-body propagation miss (ChatGPT v4 §C.2) |
| v6 | AP-AUTH-41 STRENGTHENED | Mirror-integrity claim without negative-grep (ChatGPT v5 §C.1) |
| v6 | AP-AUTH-42 NEW | Hard-coded cumulative arithmetic in proof contracts (ChatGPT v5 §C.2) |

The pattern: each ChatGPT review round identifies an audit-gap class the prior round's discipline didn't cover, and the subsequent v-cycle codifies a STRENGTHENED or NEW AP to prevent recurrence. v6 was the **first v-cycle to add 2 APs in a single chunk** (vs 1-per-cycle in v4 + v5), reflecting v5's discipline-gap-density.

Expected v6 outcome: ChatGPT 5.5 v6 review confirms convergence (no new AP class identified) → FREEZE-AS-IS-V6 verdict.

---

**END — ap_register_v6.md (snapshot at `9f848bb` tag `layer5-spec-v6`)**
