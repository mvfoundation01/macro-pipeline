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

## Sync events (informal; no AP-AUTH codification per AP-AUTH-46 guard)

### 2026-05-15 — L6-PREP authority docs sync

Vision v2.0 + Pipeline Guide v2.0 plus three review docs cherry-picked from `main:4984ec9` to `claude/layer-5-build` to close the institutional gap discovered at L6 read-and-plan (Track A Phase 0 grep audit).

Files synced (five total):

- `docs/build-plans/00_VISION_AND_PHILOSOPHY_v2.md`
- `docs/build-plans/01_CLAUDE_CODE_PIPELINE_GUIDE_v2.md`
- `docs/build-plans/02_CHATGPT_METHODOLOGY_REVIEW_v2.md`
- `docs/build-plans/03_CODEX_CODE_REVIEW_v2.md`
- `docs/build-plans/04_STRATEGIC_PM_INSTRUCTIONS_v2.md`

Rationale: L1.7 plus L5b sprints executed without these binding authority documents on-branch; Track A read them via `git show main:` pattern. L6 work directly implements Vision §3 through §14 plus Pipeline Guide §8 templates; in-branch availability is essential.

Mechanism: Option B copy plus manual commit (mirrors L5b-G AP-AUTH-49 cherry-pick precedent in the reverse direction main into claude/layer-5-build).

This is documented as an informal sync event, NOT a new AP-AUTH codification. The discipline of cross-branch doc availability check at the read-and-plan boundary is captured implicitly via AP-AUTH-50 upstream grep practice; AP-AUTH-46 gratuitous-codification guard precludes promoting a single-instance event into the formal AP-AUTH register.

---

## AP-AUTH-56 (NEW; codified 2026-05-16 at L6-K) — Defense-in-depth confidence cap pattern

**Symptom**: A single cap-enforcement layer (e.g., end-of-pipeline `min(confidence, cap)`) can be silently bypassed by upstream code paths that produce a confidence value above the cap and propagate it without re-checking. Without redundant enforcement at multiple layers, the institutional cap discipline (Standing Order #9 plus Vision section 10) is one-bug-away from being violated.

**Surfaced**: Pattern emerged organically across L1.7-B then L1.7-D then L6-B then L6-D then L6-F then L6-H sub-phases as the codebase progressively added confidence-bearing surfaces. By L6-G eighth-instance threshold trigger reached. Track A L6-G Test 12 (`test_aggregate_defense_in_depth_both_layers_fire`) verifies independent cap firings at multiple layers; PD20 (preserve Test 12) elevated this from informal practice to formal institutional invariant at L6-H + L6-I + L6-J.

**Mitigation discipline**:

1. **Layered cap enforcement**: any new confidence-bearing surface MUST add cap enforcement at construction time (dataclass `__post_init__`) AND at aggregator integration time (forecast-time helper).
2. **Independent fire-paths**: each cap layer raises `ConfidenceCapViolation` independently when bare-float input exceeds the cap. Bypassing one layer (e.g., constructing TripleDecomposition with capped confidence) MUST still trigger the others (e.g., `enforce_confidence_caps` on the same value would also raise if called directly on the pre-cap input).
3. **Cascade for compositional caps**: when multiple cap modifiers compose (horizon times stratification times signal-conflict times ood-elevated), use a dedicated cascade function (`apply_confidence_cap_cascade`) that takes the minimum across all active caps; keep the raise-helper layer UNCHANGED for invariant preservation (AP-AUTH-58).
4. **Test 12 verification**: every sub-phase that touches confidence computation MUST verify Test 12 passes unchanged. The three-part assertion structure (direct Layer 1 raise; direct Layer 2 raise; integrated pipeline cap) is the canonical regression test.

**Instances** (eight documented at codification time):
1. L1.7-B `manual_input/validation.py` construction-time cap (`ConfidenceCapViolation` introduction)
2. L1.7-D `enforce_forecast_time_confidence_cap` standalone helper
3. L6-B `TripleDecomposition.__post_init__` (10Y cap; ensemble layer first instance)
4. L6-D `enforce_confidence_caps` in `ood_and_caps.py` (ensemble layer second instance)
5. L6-F aggregator end-of-pipeline cap (third-instance pattern verified)
6. L6-G Bayesian module preserves cap discipline (fourth-instance reuse)
7. L6-H `apply_confidence_cap_cascade` with signal_conflict + OOD-elevated modifiers (fifth-instance compositional extension)
8. L6-I D1 NaN-finite invariants strengthen all upstream layers (sixth-instance cross-cutting fortification)

**Enforcement**: Pre-flight prompt template (L6-H onward) includes PD20 as critical invariant. ACCEPT gate criteria mandate Test 12 PASS verification. Future sub-phases adding confidence surfaces (e.g., L7 component producers) MUST add cap enforcement at construction time AND verify Test 12 still passes.

**Cross-reference**:
- `tests/test_aggregator.py::test_aggregate_defense_in_depth_both_layers_fire` (canonical regression test)
- `macro_pipeline/manual_input/validation.py::ConfidenceCapViolation` (single exception class shared across all layers)
- AP-AUTH-58 (cap function bifurcation; companion pattern for preserving invariants when extending API surface)

---

## AP-AUTH-57 (NEW; codified 2026-05-16 at L6-K) — Cross-branch cherry-pick (Option B copy + manual commit)

**Symptom**: `git cherry-pick` complicates branch history when moving infrastructure or authority documents across long-lived branches (e.g., `main` to `claude/layer-5-build` or reverse). The cherry-picked commit retains its parent reference from the source branch, creating subtle graph entanglement that confuses `git log --graph` audits.

**Surfaced**: Pattern emerged at L5b-G AP-AUTH-49 resolution (precommit infrastructure cherry-pick from `claude/layer-5-build` to `main`) and recurred at L6-PREP (Vision v2.0 + Pipeline Guide v2.0 plus three review docs cherry-pick from `main` to `claude/layer-5-build`). At second occurrence the institutional pattern was clear; codification deferred to L6-K retrospective per AP-AUTH-46 second-instance rule.

**Mitigation discipline**:

1. **File-copy approach**: rather than `git cherry-pick`, use `git show <source-branch>:<path>` redirected to `<path>` (or equivalent file-copy) followed by `git add <path>` plus `git commit` on the target branch.
2. **Source SHA citation in commit message**: the commit message MUST cite the source-branch SHA plus path explicitly to preserve audit trail. Example: `cherry-pick path/to/file from main:4984ec9`.
3. **No git cherry-pick command**: explicitly avoid the cherry-pick command for these cross-branch syncs; reserve cherry-pick for intra-branch / short-lived feature-branch surgical commits.
4. **Document as informal sync event**: cross-branch syncs are documented in `docs/ap_register.md` as informal sync events (not new AP-AUTH codifications per AP-AUTH-46 gratuitous-codification guard); the meta-pattern (cross-branch cherry-pick mechanism) IS codified here as AP-AUTH-57 because it reached two-instance threshold.

**Instances** (two documented at codification time):
1. L5b-G (2026-05-15): precommit infrastructure to main (AP-AUTH-49 RESOLVED)
2. L6-PREP (2026-05-15): authority docs (Vision v2.0 + Pipeline Guide v2.0 plus three review docs) to claude/layer-5-build

**Enforcement**: When cross-branch sync is needed, use Option B copy plus manual commit; cite source SHA in commit message; document as informal sync event in `docs/ap_register.md` Sync events section. Future sub-phases that need to move files across long-lived branches (e.g., L8a UI docs from a separate branch into main) follow this mechanism.

**Cross-reference**:
- L5b-G commit `412235d` (precommit infrastructure cherry-pick to main)
- L6-PREP commit `ca38c0a` (authority docs cherry-pick to claude/layer-5-build)
- AP-AUTH-49 RESOLVED note (sibling latent-debt closure pattern)
- `docs/ap_register.md` Sync events section (informal sync events; this codification documents the meta-pattern)

---

## AP-AUTH-58 (NEW; codified 2026-05-16 at L6-K) — Cap function bifurcation for invariant preservation

**Symptom**: When a new API surface (e.g., cap cascade with multiple cap modifiers) would require modifying an existing function's behavior in a way that breaks PD20 critical invariants (defense-in-depth Test 12), a naive in-place rewrite breaks the institutional invariant test. The mandate writer expected modification; the invariant guardian requires preservation.

**Surfaced**: L6-H pre-flight D2 spec called for replacing `enforce_confidence_caps` (raise-helper) with a cap-cascade function returning the capped value. Track A's analysis: the raise-helper's behavior (raise `ConfidenceCapViolation` on bare-float input) is explicitly tested in Test 12 Part 2; replacing it would fail Test 12 then PD20 invariant violation. Strategic Track B ratified Track A's L6-H bifurcation judgment (keep raise-helper UNCHANGED; add NEW `apply_confidence_cap_cascade` with cascade semantics).

**Mitigation discipline**:

1. **Pre-modification invariant check**: before modifying an existing function's behavior, grep for tests that depend on the current behavior; if invariant tests reference the function, evaluate whether modification breaks the invariant.
2. **Additive expansion over mutation**: introduce a NEW function with the new semantics; keep the original function UNCHANGED. Both functions can share underlying constants, helpers, or data layer (no DRY violation since they have different contracts).
3. **Bifurcation naming convention**: the new function should have a name that captures the new semantics (e.g., `apply_*_cascade` vs `enforce_*_caps`); the docstring on each function should cite the other and explain when to use which.
4. **Test 12 invariant is sacred**: never modify the behavior of any function that Test 12 depends on. PD20 is non-negotiable.

**Instances** (one documented at codification time; precedent-setting):
1. L6-H: `enforce_confidence_caps` (UNCHANGED; raises `ConfidenceCapViolation` on bare-float input per Test 12 Part 2) plus NEW `apply_confidence_cap_cascade` (mandate D2 cascade semantics; returns capped value with signal_conflict + OOD-elevated modifiers)

**Enforcement**: When a Strategic pre-flight mandate requires modifying an existing function in a way that conflicts with a PD20 invariant test, Track A's CORRECT response is to bifurcate (new function for new semantics) and document the bifurcation in the ACCEPT report. Strategic Track B will ratify the bifurcation post-hoc if PD20 is preserved. AP-AUTH-58 is precedent-setting; future sub-phases (e.g., L7 producer integration adding new shrinkage functions) may need to bifurcate similarly.

**Cross-reference**:
- L6-H commit `ad4091b` (L6-H ACCEPT with bifurcation)
- `macro_pipeline/ensemble/ood_and_caps.py::enforce_confidence_caps` (raise-helper; UNCHANGED)
- `macro_pipeline/ensemble/ood_and_caps.py::apply_confidence_cap_cascade` (NEW; cascade semantics)
- AP-AUTH-56 (defense-in-depth; companion pattern)
- L6-H ACCEPT report section 4 (Track A bifurcation judgment + Strategic post-hoc ratify)

---

## AP-AUTH-59 (NEW; codified 2026-05-16 at L6-K) — Explicit path-prefix discipline for cross-worktree operations

**Symptom**: When V's Claude Code session shell PWD lives in a session worktree (e.g., `agitated-mclaren-ec5db9`) that is DIFFERENT from the build worktree (e.g., `layer-5-build`), any git operation that relies on implicit cwd-based routing would land on the wrong branch. Without explicit path-prefixing, sub-phase ACCEPTs would commit to the wrong worktree's branch.

**Surfaced**: Track A's worktree audit (`5dd32ee` 2026-05-16) revealed V's session shell PWD was `agitated-mclaren-ec5db9` (a sibling worktree off main, at `412235d`) throughout L6-G + R7-bis + L6-H + L6-I sub-phases. The audit confirmed all eleven sub-phase commits routed correctly to `claude/layer-5-build` because Track A explicitly prefixed every git operation with `git -C <build-path>` or `cd <build-path> && ...`. The pattern was implicit institutional discipline; codification at L6-K elevates it to formal AP-AUTH register entry.

**Mitigation discipline**:

1. **Section 0-prime worktree enforcement section in every pre-flight prompt**: from L6-J onward (when L6-J pre-flight introduced section 0-prime upgrade), every Strategic pre-flight begins with a section 0-prime worktree enforcement block specifying:
   - Build worktree absolute path
   - Main worktree absolute path
   - Branch + expected HEAD verification
   - Path-prefix mandate for all build-worktree operations
2. **Read-only operations**: use `git -C <build-path> <subcommand>`. No `cd` needed.
3. **Write operations needing cwd**: use `cd <build-path> && <command>`. Each Bash tool invocation should chain `cd` + command to ensure cwd-during-command-execution is correct.
4. **File operations**: use absolute paths (`D:/macro_pipeline/.claude/worktrees/layer-5-build/...`) for Read / Edit / Write tool calls.
5. **Verification at start AND end of sub-phase**: section 0-prime worktree verification at Phase 0; AP-AUTH-55 push verification at Phase 7. Both verifications must include `git -C "D:/macro_pipeline" rev-parse HEAD` showing main is UNCHANGED at `412235d` (or whatever the institutional baseline is).

**Instances** (eleven retroactively documented + one forward; codification covers entire L6 sprint):
1-11. All L6 sub-phases (PREP, A, B, C, D, E, F, G, R7-bis, H, I, J) used path-prefix discipline; pre-codification implicit; L6-J pre-flight first formalized as section 0-prime block
12. L6-K (this sub-phase): first sub-phase to begin with section 0-prime + section 0-double-prime (tag-fix authorization) formal blocks

**Enforcement**: Pre-flight prompt template (L6-J onward + all future sub-phases) MUST begin with section 0-prime worktree enforcement section. Track A's response MUST begin with section 0-prime verification before any functional work. AP-AUTH-55 push verification (codified at L5b-H) PLUS AP-AUTH-59 path-prefix discipline (codified here) together form the cross-worktree institutional discipline pair.

**Cross-reference**:
- L6-J pre-audit `5dd32ee` (`docs/build-plans/L6_J_PRE_WORKTREE_AUDIT.md` documents the discovery + forensic)
- L6-J pre-flight introduced section 0-prime block as first formal pre-flight section
- L6-K pre-flight section 0-prime + section 0-double-prime upgrade (section 0-double-prime = bounded destructive authorization for one-shot fix-up)
- AP-AUTH-50 upstream grep at sub-phase boundary (companion discipline)
- AP-AUTH-55 push verification at ACCEPT (companion discipline)

---

## AP-AUTH-60 (NEW; codified 2026-05-16 at L9) — ACCELERATION PROTOCOL v2.0 pattern stack

**Symptom**: Without a documented institutional acceleration protocol, sub-phase decomposition defaults to a slow conservative pattern (5-12 sub-phases per layer; sequential ACCEPTs; 50-day median delivery). When V's mandate explicitly requests speed plus quality preservation, ad-hoc acceleration introduces risk of dropping safeguards (defense-in-depth, PD18 floor, AP-AUTH discipline). Need a codified pattern stack that compresses wall-clock delivery while preserving every institutional quality safeguard.

**Surfaced**: Pattern emerged organically during L6-K (introducing v1.0 with 5 levers) and matured at L8 + L9 (extending to v2.0 with 10 levers). V's standing delegation 2026-05-16 ("self-decide optimal then deliver optimal prompt to claude code for me") enabled Strategic Track B to compress L7 + L8 + L9 each into single comprehensive sub-phases, ultimately delivering FULL-STACK DELIVERABLE v1 within the same day as L7 ACCEPT and FULL-STACK DELIVERABLE v2 within ~1 hour after L8 ACCEPT. Codification at L9 captures the empirically-validated pattern.

**Mitigation discipline (10 levers, v2.0)**:

1. **Scope merging**: consolidate adjacent sub-phases when deliverables share dependencies (e.g., L6-K consolidated 7 deliverables that would have been L6-K + L6-L under pre-acceleration plan)
2. **R8 SKIP conditional**: skip reviewer cycle when prior sub-phase closure quality is high (Strategic prior of zero point eight or higher on SKIP); V override available
3. **Strategic parallel work**: pre-author next pre-flight in current ACCEPT response so V receives it without round-trip
4. **Single sub-phase per layer when feasible**: L7 + L8 + L9 each shipped as one ACCEPT instead of N-sub-phase decomposition (saves N minus 1 round-trips)
5. **Densification**: increase deliverables per sub-phase from seven to ten or twelve via better task granularity (NOT scope creep; each deliverable retains explicit acceptance criteria)
6. **Code scaffolding density**: Strategic provides full module templates in pre-flight (not just signatures); Track A adjusts versus writes from scratch (one point five to two times speedup observed)
7. **Tightened gates**: twenty or more ACCEPT gates per densified sub-phase (was sixteen); PD18 strict forty percent NEG floor (no relax in v2.0)
8. **Triple-tag push discipline**: push branch FIRST then create plus push tags separately (L6-J race-condition lesson: chained `git tag` plus `git push` created tag at wrong commit when precommit blocked the in-flight commit)
9. **Section 0-prime worktree enforcement** (AP-AUTH-59) inherited every sub-phase: path-prefix every git operation via `git -C` or `cd <build-path> && ...`
10. **Pre-emptive triple-tag at single-sub-phase layer-complete**: when a single sub-phase closes an entire layer, push three tags (sub-phase-accept + layer-complete + optional milestone-deliverable) in one ACCEPT cycle

**Quality safeguards (BINDING; never compromise)**:

1. Sixteen or more ACCEPT gates (twenty or more for densified sub-phases)
2. PD18 forty percent NEG floor (STRICT in v2.0; no relax permitted)
3. Defense-in-depth Test 12 PASS (PD20 critical invariant)
4. Three-field conviction (Xác suất / Tin cậy / Tin chắc plus binding constraint named)
5. Vision section X binding compliance
6. Section 0-prime worktree enforcement (AP-AUTH-59)
7. AP-AUTH register integrity (no gratuitous codifications per AP-AUTH-46)
8. Atomic commit discipline (single commit per sub-phase)
9. Path-prefix every cross-worktree operation
10. Push verification at ACCEPT (AP-AUTH-55)

**Calendar evidence** (empirical T-zero-relative validation):

- Pre-acceleration baseline (Strategic prior): T plus fifty days median to full-stack deliverable
- ACCELERATION PROTOCOL v1.0 (introduced at L6-K): T plus seventeen days
- ACCELERATION PROTOCOL v2.0 (introduced at L8): T plus zero days (same day as L7 ACCEPT)
- L9 (this commit): T plus zero days (single sub-phase polish plus retro plus codification)

**When to apply**:

- Apply when convergence variance is at minus sixty percent rolling mean or better (institutional pattern stable)
- Apply when V's mandate explicitly requests acceleration with quality preservation
- Apply when remaining deliverables are cohesive (e.g., L7 scheduling plus alerting plus persistence plus producers are tightly coupled; L8 UI plus academic plus educational share rendering surface)

**Anti-pattern signals (do NOT apply)**:

- Do NOT batch tests post-commit (rejected; violates quality safeguards)
- Do NOT skip non-critical documentation (rejected; violates institutional discipline + AP-AUTH-50 + AP-AUTH-51 grep evidence requirements)
- Do NOT combine ALL remaining layers into one sub-phase (rejected; cognitive overload + scope incoherence)
- Do NOT reduce ACCEPT gate count below sixteen (rejected; quality compromise)
- Do NOT relax PD18 forty percent NEG floor (rejected; relaxation discontinued at v2.0; integration-heavy sub-phases must add supplemental NEG tests to maintain floor)
- Do NOT skip AP-AUTH register codifications when patterns reach two-instance threshold (rejected; AP-AUTH-46 second-instance rule still binding under v2.0)

**Cross-reference**:

- L6-K commit `9ab771d` (v1.0 introduction; 5 levers + 16 gates)
- L7 commit `facd119` (v1.0 lever 4 demonstration: single sub-phase per layer)
- L8 commit `cc0550a` (v2.0 introduction; 10 levers + 20+ gates + PD18 strict + FULL-STACK DELIVERABLE v1)
- L9 commit (this commit; v2.0 codification + FULL-STACK DELIVERABLE v2)
- `docs/build-plans/L1_TO_L8_CUMULATIVE_RETROSPECTIVE.md` (L9 D6 deliverable; full sprint history)
- AP-AUTH-46 (gratuitous-codification guard; AP-AUTH-60 EXCEPTION authorized this cycle per L9 retrospective scope per Strategic disposition)
- AP-AUTH-55 (push verification; lever 8 generalizes branch-first-then-tag discipline)
- AP-AUTH-56 + AP-AUTH-57 + AP-AUTH-58 + AP-AUTH-59 (v1.0/v2.0 institutional precursors)

---

**END — ap_register.md (AP-AUTH-50 + AP-AUTH-51 + AP-AUTH-52 + AP-AUTH-53 + AP-AUTH-54 + AP-AUTH-55 + AP-AUTH-56 + AP-AUTH-57 + AP-AUTH-58 + AP-AUTH-59 + AP-AUTH-60 entries; cumulative provenance §0)**
