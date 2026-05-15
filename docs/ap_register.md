# Anti-Pattern Register — Build-phase additions

**Branch**: `claude/layer-5-build` (cumulative across patch branches merged in)
**Scope**: build-phase APs codified post-L5-A. Spec-authoring APs (AP-16..AP-21, AP-AUTH-39..46) live in `LAYER_5_BUILD_SPEC.md` v6 §12 (FROZEN at `9f848bb`). Earlier base set AP-AUTH-1..38 lives in V's local `HANDOFF_CLAUDE_CODE_v4.md` (out-of-repo).

This file collects NEW APs added during L5 build execution.

---

## Cumulative pre-build inventory (provenance only; not re-stated here)

- **AP-1..AP-15**: prior layers (L1..L3.5) — referenced by spec §12.
- **AP-AUTH-1..21**: project baseline (V's HANDOFF_CLAUDE_CODE_v4.md §7).
- **AP-AUTH-22..32**: L5 spec v1+v2 cycle additions (HANDOFF).
- **AP-AUTH-33..38**: L5 spec v3 surgical-scope discipline (HANDOFF).
- **AP-16..AP-21**: L5 project methodology APs (spec §12 lines 2417-2422).
- **AP-AUTH-39..42**: L5 v4/v5/v6 audit-instrument APs (spec §12 lines 2423-2426).
- **AP-AUTH-43..46**: L5 v6 process scope guards (`LAYER_5_V6_CHUNK_14_VERIFICATION.md` §7).
- **AP-AUTH-47..49**: **codified 2026-05-13** at L5-B Task A retry first commit (this file §AP-AUTH-47, §AP-AUTH-48 v2, §AP-AUTH-49 below).

---

## AP-AUTH-47 (NEW; codified 2026-05-13) — Build worktree env-setup beyond test collection

**Symptom**: `pytest --collect-only` succeeds on a fresh build worktree (no cache files needed for collection) but `pytest -x` fails on 190+ cache-dependent tests because `data/cache/` and `data/raw/` are gitignored per-worktree (not present in fresh worktree checkout).

**Surfaced**: L5-A Phase 3.5 (full pytest revealed 190 failures + 12 errors after Phase 1 collect-only "baseline" had reported "602 tests collected"; root cause = build worktree missing data dirs that exist in main worktree).

**Mitigation discipline**: Phase 1 of any L5 sub-phase code-exec MUST include AS DISCRETE STEPS:
1. `cp -r D:/macro_pipeline/data/cache D:/macro_pipeline/data/raw <build-worktree>/data/` (one-time per worktree; gitignored dirs).
2. `pytest -x --no-header -q` (full execution; NOT `--collect-only`).
3. Verification report Phase 1 section MUST cite full pytest pass count, NOT collection count.

**Enforcement**: pre-flight prompts MUST mandate full pytest; reviewer rejects sub-phase ACCEPT if verification report cites only `--collect-only` baseline. Future sub-phase Phase 0 audits include data-dir-existence check.

**Cross-reference**: L5-A Phase 1 (validated 617 collect-only; surfaced 190 failures full); L3 component_panel patch Phase 0 (correctly ran full pytest 623); this L5-B Task A retry Phase 0 (correctly ran full 623 — discipline now established).

---

## AP-AUTH-48 v2 (NEW; codified 2026-05-13) — Manifest hash computed from served-URL content post-push (Windows CRLF/LF normalization)

**Symptom**: MANIFEST.md ships with sha256 hashes computed from local on-disk content pre-commit. On Windows with git autocrlf=true, text files with CRLF line endings (e.g., pytest output captured via `pytest > file 2>&1` shell redirection) are normalized to LF in the git blob on `git add`. Result: local on-disk hash ≠ served blob hash. Reviewer fetches served content (LF) → sha256 mismatch with MANIFEST claim (CRLF) → integrity verification fails.

**v1 surfaced at ChatGPT 5.5 L5-A foundation review §D.1** (placeholder `<fill>` issue; mitigation: populate hashes pre-push).

**v2 surfaced at L3 component_panel patch Phase 5** (`test_transcript.txt` exhibited drift: local `c03210a5f6ca` vs served `5aa50cde909f`; required correction commit `52a0bd3`).

**Mitigation discipline**:
1. Compute manifest hashes pre-push (as v1).
2. **POST-PUSH** (new v2 step): verify each artifact URL via `curl -sL <url> | sha256sum`.
3. If any served-hash ≠ MANIFEST claim: amend MANIFEST with served-content hash; commit + push correction.
4. Final state: every MANIFEST entry sha256 must equal `curl -sL <its-URL> | sha256sum` output (first 12 chars).

**Enforcement**: Phase 4/5 (review branch publication) procedure MUST include post-push curl verification step. Pre-push check is INSUFFICIENT (catches placeholder bug but not normalization drift). Track A's L3 patch Phase 5 introduced the discipline; this AP codifies for all subsequent sub-phases.

**Why v2 (not new AP number)**: AP-AUTH-48 v1 already addressed "manifest hash placeholders shipped unfilled". v2 strengthens the discipline to cover line-ending normalization drift — same AP class (manifest hash integrity), one cycle deeper. Mirrors AP-AUTH-41 v6 STRENGTHENED pattern from spec authoring.

**Cross-reference**: L3 component_panel patch commit `52a0bd3` (the correction commit demonstrating v2 mitigation); ChatGPT 5.5 L5-A review §D.1 (v1 origin).

---

## AP-AUTH-49 (NEW; codified 2026-05-13) — Planning-only branch precommit infra hygiene

**Symptom**: Planning/docs-only branch (e.g., `claude/layer-5-build-plan`) has docs/**/*.md commits that trigger the shared `.git/hooks/pre-commit` hook, but the hook tries to invoke `<cwd>/scripts/precommit/validate_*.py` which only exist on the build branch (`claude/layer-5-build`). Hook fails (script not found) and blocks the commit. Without explicit handling, the only escape paths are `--no-verify` (forbidden) or cherry-picking the precommit infra onto the planning branch (scope bloat).

**Surfaced**: L5-B Task A pre-flight commit on `claude/layer-5-build-plan` (commit chain: `9a25619` — required cherry-pick `f223eb3` of `0dc3e8d` from build branch before commit could land).

**Mitigation discipline**:
1. **Preferred**: planning-only branches must inherit precommit infra (cherry-pick from build branch) at branch creation. Scope penalty acceptable since validators are lightweight (~10 files).
2. **Alternative**: tag the branch with `hook-scope-override` (would require .git/hooks/pre-commit to read a branch-level config; not yet implemented).
3. **Pre-commit script auto-detection enhancement** (proposed; not yet implemented): if validators absent from `$REPO_ROOT/scripts/precommit/`, hook emits actionable error (`"Validators missing on branch X; run scripts/precommit/install_hook.py from a branch that has them, OR cherry-pick infra commit from claude/layer-5-build"`) instead of generic script-not-found failure.

**Enforcement**: at planning-branch creation, Track A applies cherry-pick by default (validated by L5-B Task A pre-flight). Future enhancement: auto-detection per (3) above.

**Cross-reference**: commit `f223eb3` (cherry-pick of precommit infra onto build-plan branch).

---

## AP-AUTH-50 (NEW; codified 2026-05-13) — Foundation-adjacent sub-phase requires upstream layer export; check at pre-flight time, not code-exec time

**Symptom**: L5-B Task A PHASE 0 hard gate triggered CASE C (component_panel absent as L3 export); resolution required an L3 patch and ~3h additional work that should have been visible at pre-flight time. The L5-B Task A pre-flight (`L5_B_TASK_A_PREFLIGHT.md` ITEM 4 risk #2) DID identify "component panel not exported by L3" as a HIGH 30% risk, but did NOT include a grep transcript proving absence — only a forward-looking mitigation ("Phase 0 of code-exec grep audit"). The grep audit was deferred to code-exec time, where it triggered a hard gate + S-10 escalation + 2-3h L3 patch cycle.

**Surfaced at**: L5-B Task A PHASE 0 audit (commit `711f641`; S-10 escalation).

**Mitigation discipline**:
1. Pre-flight prompt template for any sub-phase consuming upstream-layer exports MUST include an explicit grep audit of the upstream surface (not just a downstream-contract description).
2. Risk register entries about "upstream-export-absence" MUST be elevated to HIGH severity when no grep evidence is presented at the pre-flight stage.
3. Future sub-phase pre-flight prompts MUST cite a grep transcript showing upstream export presence (or absence) BY NAME, with file path and line number. Examples:
   - For Task A consuming `component_panel`: `rg 'def build_component_panel' --type py macro_pipeline/` returns hits + line refs.
   - For Task B consuming `calibrated_probability` post-RM-6: similar.
4. **Build plan template update proposal for L5_BUILD_PLAN_v2**: add to ITEM 4 risk register format a mandatory "grep evidence" column for any HIGH-severity upstream-dependency risk.

**Enforcement**: post-pre-flight Strategic review now expects an upstream-grep-audit citation for HIGH-severity upstream-export risks. Absence of citation = pre-flight is incomplete; Track A revises before code-exec greenlight.

**Cross-reference**: S-10 (resolved by L3 component_panel patch); L5-B Task A pre-flight ITEM 4 risk #2 (the under-cited risk); `LAYER_5_BUILD_SPEC.md` §5.B.1 (the spec-side input contract that exposed the gap).

---

## AP-AUTH-51 (NEW; codified 2026-05-14) — Risk register entries with quantifiable scope must cite grep evidence

**Symptom**: Build plan v1 ITEM 4 risk #2 stated "L5-RM-4 dataclass migration touches 50+ existing ScoredObservation construction sites" → HIGH severity classification. Empirical grep at L5-RM-4 pre-flight returned **16 real construction sites** (2 production + 14 test; 1 grep noise comment line). Scope gap: -68% vs narrative estimate. Risk class reclassified HIGH → MEDIUM in pre-flight; "extra-thorough" pre-flight protocol invoked unnecessarily (1.0h spent vs ~0.5h needed if scope correctly estimated upfront).

**Surfaced**: L5-RM-4 pre-flight (commit `675db8a` on `claude/layer-5-build-plan`; risk reclassification documented in ITEM 7 §7.1).

**Mitigation discipline**:
1. Future risk register entries that reference **quantifiable scope** (touch-point counts, file counts, line counts, test counts) MUST cite the grep command + count in an evidence column or footnote.
2. Narrative estimates without grep evidence default to **LOW severity** unless explicit empirical evidence is supplied. (Burden of proof shifts to the estimator for HIGH/MEDIUM classifications.)
3. AP-AUTH-50 already mandated upstream-export grep at pre-flight; AP-AUTH-51 extends the discipline to **all quantifiable risk dimensions** (not just upstream-export presence/absence).
4. Reviewer audit at pre-flight ACCEPT: any HIGH/MEDIUM risk without grep evidence column → REVISE-REQUIRED.

**Enforcement**: build-plan template update proposal for **L5_BUILD_PLAN_v2** — add "Grep evidence" column to all risk register entries; absence triggers downgrade-to-LOW default. Deferred to post-L5 retrospective implementation; codification at AP register is sufficient discipline-signal for current sub-phase work.

**Cross-reference**: L5-RM-4 pre-flight ITEM 1 (empirical grep that exposed the 50+ → 16 gap); AP-AUTH-50 (parent discipline; upstream-export pre-flight grep); build plan v1 ITEM 4 risk #2 (the over-cited risk).

---

## AP-AUTH-52 (NEW; codified 2026-05-15) — Spec magic-numbers must be derivable from production base + delta, not asserted as opaque totals

**Symptom**: Spec `LAYER_5_BUILD_SPEC.md` v6 §5.RM-4.0 + §5.RM-4.5 + §5.RM-4.6 + §5.RM-4.7 asserted "31 total slots" (= 25 base + 6 new) without enumerating the 25 base components or citing a grep command that would produce 25. Empirical `len(ScoredObservation.__dataclass_fields__)` at production HEAD `056d198` = 23 (NOT 25). Discrepancy surfaced only at code-exec time (S-12 filed 2026-05-14), requiring Strategic disposition mid-sub-phase.

The 4 magic-number sites in §5.RM-4 + 1 header inconsistency (§5.RM-4.1.1 "(5 total)") all derive from the same root cause: spec authoring asserted opaque arithmetic without a grep-traceable base.

**Surfaced**: L5-RM-4 code-exec Phase 0 baseline check (S-12 in `L5_BUILD_SXX_LOG.md`; resolution path RESOLVED-OPTION-A 2026-05-15 disposed by Strategic).

**Mitigation discipline**:
1. Spec authoring procedure for any sub-phase modifying a production type (dataclass, enum, function signature with side effects) MUST derive any new "total count" assertion as **`<base_grep_count> + <delta>` with the grep command shown in spec**, not assert opaque totals like "X total".
2. Cross-check at v6-style spec closure review: any "N total" assertion without a corresponding `grep` command + count citation is REVISE-REQUIRED.
3. AP-AUTH-50 (upstream-export grep at pre-flight) + AP-AUTH-51 (risk register grep evidence) + AP-AUTH-52 (spec-time grep evidence) form a complete discipline triple: code-exec, pre-flight, AND spec authoring all cite grep evidence for quantifiable claims.
4. Reviewer audit at spec closure: any methodology-section "N base / M new / K total" arithmetic without `K = N + M` derivation cited from empirical grep → REVISE-REQUIRED.

**Enforcement**: post-L5 spec template update (L5b-4 candidate). For active L5 build, AP-AUTH-52 codification serves as discipline-signal for any future spec-vs-implementation gaps encountered (Track A and Strategic should file Sxx + cite AP-AUTH-52 when a similar magic-number gap surfaces).

**Cross-reference**:
- S-12 (`L5_BUILD_SXX_LOG.md`) — the gap that triggered codification
- AP-AUTH-50 (upstream-export grep) — parent at pre-flight stage
- AP-AUTH-51 (risk register grep) — sibling at pre-flight stage
- L5b-4 (`L5B_BACKLOG.md`) — backlog item to retroactively patch spec v7

---

## AP-AUTH-53 (NEW; codified 2026-05-13; migrated to formal register at L5b-E 2026-05-14) — Reviewer-driven L5b kickoff item pattern

**Symptom**: External reviewers (Codex 5.5 / ChatGPT 5.5) flag a CRITICAL or IMPORTANT issue in a previously-passed gate after the layer-completion commit + push activate the dual-reviewer review window. The reviewer-flagged surface requires institutional closure mechanism without breaking the spec freeze or the existing test surface; ad-hoc "patch the API" approaches create both spec literal drift and re-review burden. The standard closure mechanism for reviewer-driven kickoff items must be codified so future L5b+ kickoff sub-phases reuse the same seven-step pattern.

**Surfaced**: L5b-KICK-1 ACCEPT (2026-05-13, tag `l5b-kick-1-accept`) — first reviewer-driven kickoff item closure (isotonic train-only `fit_window` invariant; closes Codex 5.5 IMPORTANT #1 + ChatGPT 5.5 CRITICAL #3 dual-reviewer convergence). Codification deferred at KICK-1 ACCEPT per AP-AUTH-46 gratuitous-codification first-instance rule. **CODIFIED at L5b-KICK-2 ACCEPT** (2026-05-13, tag `l5b-kick-2-accept`) when the pattern repeated (forecast σ v2 production wrapper plus Gate 24 hard gate; closes ChatGPT 5.5 CRITICAL #2). Pattern continued to apply through KICK-3 (L5-C adaptive bin reduction; closes Codex 5.5 IMPORTANT #2) plus KICK-4 (L5-B1 inner-CV z-scaler; internal-implementation variant — see AP-AUTH-54) plus KICK-5 (bootstrap diagnostics; AP-AUTH-54 codified; closes ChatGPT 5.5 IMPORTANT #6) plus KICK-6 (Ridge inference labeling; closes ChatGPT 5.5 IMPORTANT #5) plus KICK-7 (DMS source memo; documentation-primary variant; AP-AUTH-55 candidacy DEFERRED per AP-AUTH-46; closes Codex 5.5 IMPORTANT #4 + ChatGPT 5.5 IMPORTANT dual).

**Mitigation discipline** (seven-step closure mechanism for reviewer-driven L5b kickoff items):

1. **Preserve existing API verbatim** (no breaking change to spec literals — protects existing test surface and spec freeze integrity).
2. **Add side-by-side hardened API** with `_v2` suffix function, new dataclass field, OR equivalent isolation pattern.
3. **No-default required kwargs on hardened API** (forces caller intent; closes "silent placeholder" reviewer concerns).
4. **Gate validator extension** via signature-inspection criteria for both legacy and hardened paths (mirrors existing gate idiom).
5. **Test coverage**: minimum five tests, fifty-percent NEG ratio floor, bounds-check NEG when v2 inputs admit invalid ranges, plus missing-kwarg NEG behaviors.
6. **Pre-flight Sxx-N (catastrophic state) triage** via grep evidence; defer entry to `L5B_BACKLOG.md` if production callers do not yet exist.
7. **Module docstring + `L5B_BACKLOG.md` SPRINT EXECUTION LOG** documents v1 → v2 architectural drift.

Confirmed via L5b-KICK-1 (isotonic `fit_window` invariant) + L5b-KICK-2 (forecast σ v2 production wrapper); pattern continued through KICK-3 / KICK-4 / KICK-5 / KICK-6 / KICK-7 as documented in `docs/build-plans/L5B_BACKLOG.md` per-sub-phase entries.

**Enforcement**: pre-flight prompt template for any L5b-or-later reviewer-driven kickoff sub-phase MUST cite the seven-step closure mechanism as the governing approach pattern. Strategic disposition cycle validates the seven steps are honored before greenlighting code-exec. Reviewer audit at sub-phase ACCEPT confirms all seven steps applied (or documents within-envelope variance per AP-AUTH-54 internal-implementation variant or future AP-AUTH-55 documentation-primary variant family).

**Cross-reference**:
- L5b-KICK-1 (isotonic `fit_window` invariant; pre-codification first instance) at `docs/build-plans/L5B_BACKLOG.md:11-21`
- L5b-KICK-2 (forecast σ v2 wrapper; codification commit at this ACCEPT) at `docs/build-plans/L5B_BACKLOG.md:25-36`
- L5b-KICK-3 / KICK-4 / KICK-5 / KICK-6 / KICK-7 (subsequent applications) at `docs/build-plans/L5B_BACKLOG.md:58-185`
- AP-AUTH-46 (gratuitous-codification first-instance rule; governs deferral at KICK-1 and codification at KICK-2)
- AP-AUTH-54 (internal-implementation variant; codified at `l5b-kick-5-accept` post-KICK-4 repetition; below)
- AP-AUTH-55 candidacy (documentation-primary variant; DEFERRED at `l5b-kick-7-accept` per AP-AUTH-46 first-instance rule)
- Migration source: inline codification block at `docs/build-plans/L5B_BACKLOG.md:40-54` (verbatim mitigation discipline preserved here; format normalized to Symptom / Surfaced / Mitigation / Enforcement / Cross-reference template per Strategic disposition 1 at L5b-E 2026-05-14)

---

## AP-AUTH-54 (NEW; codified 2026-05-15; migrated to formal register at L5b-E 2026-05-14) — Internal-implementation variant of AP-AUTH-53

**Symptom**: AP-AUTH-53 closure mechanism step #2 (add side-by-side hardened API with `_v2` suffix) is ceremonial when the reviewer-flagged surface is an internal helper (`_` prefix) or private estimator mechanic rather than a public production boundary. Adding a `_v2` wrapper to a private helper doubles the maintenance surface without exposing a public boundary that callers need to choose between. A four-step variant of AP-AUTH-53 is required for internal-implementation cases that preserves AP-AUTH-53's institutional discipline at the dataclass-field level rather than the public-function-signature level.

**Surfaced**: L5b-KICK-4 ACCEPT (2026-05-15, tag `l5b-kick-4-accept`) — first internal-implementation instance (L5-B1 inner-CV z-scaler recomputation matching Task A pattern; private helper `_select_lambda_inner_cv_ridge`; new field `inner_cv_scaler_recomputed` on `RidgeFitResult`; closes Codex 5.5 IMPORTANT #3). Codification deferred at KICK-4 ACCEPT per AP-AUTH-46 gratuitous-codification first-instance rule. **CODIFIED at L5b-KICK-5 ACCEPT** (2026-05-15, tag `l5b-kick-5-accept`) when the pattern repeated (bootstrap diagnostics table per horizon / fold; private helpers `_block_bootstrap_residual_se` plus `_compute_block_size_sensitivity`; closes ChatGPT 5.5 IMPORTANT #6).

**Mitigation discipline** (four-step variant; mirrors AP-AUTH-53 but adapted for internal helpers):

1. **In-place refactor of the internal helper** — change signature, return contract, or body as needed to expose the post-refactor invariant. No `_v2` wrapper required (would be ceremonial for internal helpers).
2. **No-default field on a related public dataclass** — exposes the refactor's surface state to downstream consumers for gating and runtime inspection. AP-AUTH-53 step #3 (force caller intent) is satisfied at the dataclass field rather than at the public function signature.
3. **Gate validator extension via Option Y** — signature inspection on the public dataclass + AST audit on the internal helper body OR runtime probe on a synthesized fit.
4. **Pre-flight empirical evidence** — when reviewer concern targets an edge-case path (e.g., fallback, degenerate state), pre-flight read-and-plan should demonstrate the path is empirically reachable in production fixtures before Phase 0, to confirm the discipline isn't ceremonial.

Confirmed via L5b-KICK-4 (inner-CV z-scaler purity; private helper `_select_lambda_inner_cv_ridge`; field `inner_cv_scaler_recomputed`) + L5b-KICK-5 (bootstrap diagnostics table; private helpers `_block_bootstrap_residual_se` + `_compute_block_size_sensitivity`; fields `bootstrap_diagnostics` + `block_size_sensitivity_diagnostics`).

**Envelope characterization** (CLOSED at four-instance-range characterization preserved across seven AP-AUTH-54 applications spanning KICK-4 through L5b-D per Strategic disposition 4 ratified at L5b-B / L5b-C / L5b-D and re-ratified at L5b-E 2026-05-14):

- KICK-4 heaviest: helper refactor (z-scaler purity) + field + AST audit
- KICK-5 medium: tuple-return helper (`_block_bootstrap_residual_se` plus `_compute_block_size_sensitivity`) + dual fields + runtime probe (codification commit at this ACCEPT)
- KICK-6 lightest-weight: dataclass discipline only (no helper change; `inference_label` field + docstring rewrite + runtime probe)
- L5b-A heavy: helper refactor (stationary block sampling per Politis-Romano 1994) + new helper (`_sample_stationary_block_lengths`) + field expansion + AST audit + runtime probe + empirical snapshot
- L5b-B heavy-medium: two new helpers (Quandt-Andrews supW per Andrews 1993 + Bai-Perron sequential supF per Bai-Perron 1998 simplified) + NEW dataclass + Optional field
- L5b-C medium-cross-cutting: NEW module (`macro_pipeline/analysis/fdr_gating.py`) + NEW gate (Gate 26) + NEW test file + BH (1995) step-up algorithm
- L5b-D heavy-cross-cutting: NEW module (`macro_pipeline/analysis/regime_conditional_validation.py`) + NEW gate (Gate 27) + largest dataclass (fourteen fields + four invariants) + Callable injection caller pattern

L5b-E is OUTSIDE this envelope per Strategic disposition 4 at L5b-E ACCEPT — sprint retrospective mirrors `LAYER_5_RETROSPECTIVE.md` (parent L5-H precedent) structurally, NOT KICK-7 (reviewer-driven kickoff). Documentation-primary variant precedent set at KICK-7 (AP-AUTH-55 candidacy DEFERRED per AP-AUTH-46) does NOT re-open this envelope for sprint-level retrospectives.

**Enforcement**: pre-flight prompt template for any L5b-or-later internal-implementation variant of a reviewer-driven kickoff item MUST cite the four-step variant mechanism as the governing approach pattern. Strategic disposition cycle validates the four steps are honored before greenlighting code-exec. Reviewer audit at sub-phase ACCEPT confirms all four steps applied + envelope-weight bucket documented per the four-instance characterization above.

**Cross-reference**:
- L5b-KICK-4 (inner-CV z-scaler purity; first internal-implementation instance pre-codification) at `docs/build-plans/L5B_BACKLOG.md:78-99`
- L5b-KICK-5 (bootstrap diagnostics table; codification commit at this ACCEPT) at `docs/build-plans/L5B_BACKLOG.md:103-123`
- L5b-KICK-6 (lightest-weight envelope variant) at `docs/build-plans/L5B_BACKLOG.md:142-160`
- L5b-A / L5b-B / L5b-C / L5b-D (continued applications) at `docs/build-plans/L5B_BACKLOG.md:256-336`
- AP-AUTH-53 (parent pattern; codified at `l5b-kick-2-accept`; above in this file)
- AP-AUTH-46 (gratuitous-codification first-instance rule; governs deferral at KICK-4 and codification at KICK-5)
- Migration source: inline codification block at `docs/build-plans/L5B_BACKLOG.md:127-138` (verbatim mitigation discipline preserved here; format normalized to Symptom / Surfaced / Mitigation / Envelope / Enforcement / Cross-reference template per Strategic disposition 1 at L5b-E 2026-05-14)

---

## AP-AUTH-55 (NEW; codified 2026-05-15 at L5b-H) — Push verification at ACCEPT cycle

**Symptom**: Track A ACCEPT reports cite "HEAD at XXXXXXX" without distinguishing local-HEAD from origin-HEAD. Local commits never explicitly pushed to origin cause downstream reviewer reachability gaps. External reviewers' `git fetch origin XXXXXXX` fails with "couldn't find remote ref"; full review cycle blocked on procedural visibility.

**Surfaced**: R5 push remediation cycle (2026-05-15) — both R6 external reviewers (Codex 5.5 + ChatGPT 5.5) returned procedural REJECT verdicts because `origin/claude/layer-5-build` was at `e13db61` while local HEAD was at `59cb6d0`. Twelve L5b sprint commits plus thirteen tags had been authored locally but never pushed. Root cause: no Strategic disposition explicitly required `git push origin <branch>` at sub-phase ACCEPT cycle; Track A's "HEAD at XXXXXXX" wording in ACCEPT reports did not distinguish local versus remote state, and the discipline gap went undetected until external reviewers attempted to fetch the artifacts.

**Mitigation discipline**:

1. **ACCEPT report MUST cite both LOCAL HEAD and ORIGIN HEAD as match**. Phrase: "HEAD (local) ... HEAD (origin) ... synced". Bare "HEAD at XXXXXXX" is REVISE-REQUIRED.
2. **Phase 7 (commit + tag) procedure MUST include explicit push steps**: `git push origin <branch>` followed by `git push origin <tag-name>` (explicit tag name only; NEVER `git push origin --tags` which would publish unrelated tags).
3. **Verification step**: post-push `git ls-remote --heads --tags origin` showing branch HEAD + relevant tag(s) both point to the ACCEPT commit. Capture verbatim output in ACCEPT report.
4. **Reviewer prompts MUST require external reviewers to do** `git fetch && git log origin/<branch> -1` confirmation before substantive review begins. If `git fetch origin <commit>` returns "couldn't find remote ref", reviewer surfaces back to Track A for push completion before substantive review.

**Enforcement**: Strategic disposition templates updated to mandate Phase 7 push step plus ACCEPT report cross-reference (local + origin). Track A pre-flight prompt templates updated to mandate push verification before declaring sub-phase complete. Future ACCEPT reports without push verification are institutionally incomplete; Strategic surfaces back to Track A for push completion before formal ACCEPT confirmation. The R5 remediation cycle (2026-05-15) is the canonical example of this discipline gap; this entry codifies the corrective discipline.

**Cross-reference**:
- R5 push remediation cycle (2026-05-15): `origin/claude/layer-5-build` advanced from `e13db61` to `59cb6d0` via explicit fast-forward push (twelve L5b sprint commits) plus thirteen explicit L5b tag pushes
- Strategic L5b-F Note E (informal enforcement at L5b-F + L5b-G + L5b-H ACCEPT cycles)
- Strategic L5b-H pre-flight Task T3 (codification mandate; this entry)
- AP-AUTH-49 RESOLVED (L5b-G, 2026-05-15) — sibling latent-debt closure pattern at same sprint sub-phase cadence

---

**END — ap_register.md (AP-AUTH-50 + AP-AUTH-51 + AP-AUTH-52 + AP-AUTH-53 + AP-AUTH-54 + AP-AUTH-55 entries; cumulative provenance §0)**
