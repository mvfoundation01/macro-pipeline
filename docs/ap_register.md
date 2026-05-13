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

**END — ap_register.md (AP-AUTH-50 + AP-AUTH-51 entries; cumulative provenance §0)**
