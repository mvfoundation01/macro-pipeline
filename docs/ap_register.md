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
- **AP-AUTH-47..49**: codification PENDING at L5-B Task A retry per Strategic prompt (env-setup beyond collect-only; manifest hash placeholders; planning-branch precommit scope hygiene). Validated empirically during patch work but commit deferred to L5-B Task A first-commit per Strategic scoping.

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

**END — ap_register.md (AP-AUTH-50 entry; cumulative provenance §0)**
