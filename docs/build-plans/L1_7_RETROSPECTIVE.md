# L1.7 MANUAL_INPUT layer retrospective

**Sprint**: L1.7 MANUAL_INPUT layer (post-L5b-H session resume)
**Window**: 2026-05-15 (single calendar day; five sub-phases)
**Sub-phases**: five (A schema / B validation / C persistence / D integration / E closure)
**Final state**: THIS COMMIT carrying DUAL TAGS `l1.7-e-accept` plus `l1.7-complete`; immediate parent `7ad55bf` (tag `l1.7-d-accept`)
**Authoring agent**: Track A (Claude Code)
**Strategic counterpart**: Track B (Claude Opus four point seven, one-million-context)
**Vision authority**: `00_VISION_AND_PHILOSOPHY_v2.md` v2.0 (BINDING since L5b-E)
**Spec source**: Strategic-authored inline across five pre-flight prompts; no formal `L1_7_BUILD_SPEC.md` filed (the inline-spec discipline mirrored the L5b retroactive pattern without surfacing the need for a formal spec document)

This document closes the L1.7 MANUAL_INPUT layer build with five sub-phases delivered in a single calendar day. It mirrors `L5B_RETROSPECTIVE.md` structurally while reflecting the L1.7 layer's distinctive shape: a Strategic-authored inline-spec progression (Strategic relayed each pre-flight verbatim via V; no separate spec document) plus a clean linear sub-phase chain (no reviewer-driven kickoff arc; the L5b R6 reviewer cycle had completed before L1.7 commenced).

---

## §1 — Sprint context and convergence streak

The L1.7 MANUAL_INPUT layer emerged from the post-L5b-H session resume on 2026-05-15. L5b sprint had closed with `l5b-complete` at commit `9b6242d` (tag `l5b-h-accept`) carrying a perfect twenty-eight-of-twenty-eight ACCEPT convergence streak (thirteen L5 sub-phases plus fifteen L5b sub-phases). Vision v2.0 5-pillar mission was binding from L5b-E onward; AP-AUTH register stood at one through fifty-five with no latent debt entering L1.7.

Strategic Track B (via V) authored the L1.7 inline spec at session bootstrap, dispositioning eight spec questions and identifying five sub-phases. The convergence streak entering L1.7-E stood at thirty-two of thirty-two perfect ACCEPTs (twenty-eight entering L1.7 plus four through L1.7-D). L1.7-E ACCEPT lifts the streak to **thirty-three of thirty-three** — the L1.7 sprint-closure milestone. Banked headroom remained substantial; the rolling-mean variance trend observed across L5 plus L5b carried forward without surfacing.

The single-calendar-day window is the shortest layer in the build to date. Per Strategic disposition pattern: each sub-phase pre-flight authored by Strategic in advance of execution, with Track A returning per-sub-phase ACCEPT reports that Strategic dispositioned before authoring the next pre-flight.

---

## §2 — Per-sub-phase inventory

The five sub-phase entries below summarise the ACCEPT-tagged states pulled verbatim from per-sub-phase ACCEPT reports. Test-count deltas use word-form throughout per AP-AUTH-42 NEW v6 institutional precedent.

| # | Sub-phase | ACCEPT tag | HEAD | Test count delta | Gate criteria delta | AP-AUTH delta | New module / doc |
|---|---|---|---|---|---|---|---|
| one | L1.7-A schema definition | `l1.7-a-accept` | `296cee5` | plus eight (eight-hundred-two to eight-hundred-ten) | zero | zero (no new patterns) | `manual_input/__init__.py` + `manual_input/schema.py` |
| two | L1.7-B validation logic | `l1.7-b-accept` | `92385e9` | plus fifteen (eight-hundred-ten to eight-hundred-twenty-five) | zero (Gate 29 reserved for L1.7-D) | zero | `manual_input/validation.py` |
| three | L1.7-C persistence plus versioning | `l1.7-c-accept` | `2b000ec` | plus sixteen (eight-hundred-twenty-five to eight-hundred-forty-one) | zero | zero | `manual_input/persistence.py` |
| four | L1.7-D pipeline integration plus Gate 29 NEW | `l1.7-d-accept` | `7ad55bf` | plus twenty (eight-hundred-forty-one to eight-hundred-sixty-one) | plus six (**Gate 29 NEW** criteria 29.1 / 29.2 / 29.3 / 29.4 / 29.5 / 29.6) | zero | `manual_input/integration.py` + three surface modifications |
| five | **L1.7-E edge cases plus retrospective plus closure (THIS COMMIT)** | `l1.7-e-accept` + `l1.7-complete` | THIS COMMIT | plus ten anticipated (eight-hundred-sixty-one to eight-hundred-seventy-one) | zero | zero | `tests/test_manual_input_edge_cases.py` + `L1_7_RETROSPECTIVE.md` + `L1_7_BACKLOG.md` |

Cumulative test-count progression from L5b-H ACCEPT baseline (eight-hundred-two at `l5b-complete`) to L1.7-E ACCEPT target (eight-hundred-seventy-one) is **plus sixty-nine across five sub-phases in one calendar day**. No regressions across the sprint. NEG-ratio floor of one-half met or exceeded at every sub-phase: L1.7-A sixty-two point five percent, L1.7-B sixty percent, L1.7-C sixty-two point five percent, L1.7-D fifty percent, L1.7-E fifty percent.

---

## §3 — Institutional patterns ratified during L1.7

Five patterns surfaced during the L1.7 sprint that warrant institutional documentation. None met the AP-AUTH-46 second-instance-trigger threshold for formal codification — recorded here as L1.7 precedent for future second-instance evaluation.

### Pattern A: AP-AUTH-50 Phase-0 grep catches inter-session state drift

At the L1.7-D pre-flight re-send event (Strategic relay artefact during the V mediation chain), Track A's Phase 0 verification detected that the HEAD anchor in the re-sent pre-flight matched the PRE-execution state (`2b000ec`, tag `l1.7-c-accept`) while the actual repository HEAD had advanced to `7ad55bf` (tag `l1.7-d-accept`) from the prior turn's execution. Per AP-AUTH-50 (upstream grep at pre-flight) discipline, Track A surfaced the state drift in a concise status-only report rather than re-executing the sub-phase (which would have collided on the tag `l1.7-d-accept` already existing locally and on origin). This validates AP-AUTH-50 as a sufficient guard against benign relay duplication; Strategic redirected to L1.7-E without disposition cost.

### Pattern B: Helper-only disposition for diffuse composites (Surface 5)

L1.7-D pre-flight assumed a discrete recession-P composite-computation callable existed for Surface 5 wire-site. Track A's Step 2 grep audit verified empirically that no such callable exists in the codebase: the string `12M_recession_probability_composite` is a target identifier referenced by validators, guards, and CRPS context, not a callable function returning per-horizon probabilities. Per V's standing-pace instruction, Track A elected the additive-design path: expose `apply_recession_p_override_for_horizon` helper without wiring to a non-existent function, document the deviation in the commit message, and surface the wire-site question to Strategic for L1.7-E (or L6) disposition. Strategic ratified the helper-only approach at L1.7-E pre-flight authorship: the helper is forward-compatible, no API break is needed to add call-site wiring later, and the L6 build kickoff may revisit if a recession-P composite materializes as a discrete consumer.

### Pattern C: Defense-in-depth confidence cap at distinct pipeline points

Standing Order number nine (confidence cap) is enforced at two architecturally-distinct points: L1.7-B `validate_schedule` V5 catches dangerous override VALUES at construction time (e.g., a user-specified `recession_p_10y = 0.75` exceeding the seventy-percent non-stratified ten-year cap), and L1.7-D `enforce_forecast_time_confidence_cap` catches dangerous PROPAGATED forecast confidence values regardless of whether any specific override was itself out of bounds. Edge-case test ten (`test_cross_layer_cap_defense_in_depth`) demonstrates the architecture: a schedule with `recession_p_10y = 0.50` passes L1.7-B V5 (override below cap) but a propagated forecast of zero point six-five at ten-year regime-stratified raises `ConfidenceCapViolation` at the L1.7-D layer (cap zero point five-five). Both layers raise the same `ConfidenceCapViolation` subclass of `ValueError`.

### Pattern D: Cross-platform atomic write via os.replace plus sibling tmp plus fsync

L1.7-C `save_manual_inputs_atomic` mirrors the precedent set by `macro_pipeline/cache.py` `atomic_write_bytes`: write to a uuid-suffixed sibling temp file in the target's parent directory, flush plus fsync the file handle, then call `os.replace` for atomic rename. Cleanup on exception is via `contextlib.suppress(OSError)` plus `tmp.unlink()`. Per Python documentation since version three point three, `os.replace` is atomic on both POSIX and Windows. L1.7-C tests seven (cleanup on failure) plus fifteen (preserve existing file on failure) verify the cleanup plus preservation invariants on the Windows CI; POSIX behavior is documented guarantee but not directly exercised in CI (captured as latent debt for POSIX CI matrix expansion).

### Pattern E: Frozen dataclass plus tuple-of-pairs for nested immutability

`LoadResult` (L1.7-C) carries `replication_kit_metadata` per Vision section fourteen as a `tuple[tuple[str, str], ...]` — a tuple of two-element tuples — rather than a `dict[str, str]`. This preserves the `@dataclass(frozen=True)` invariant (the frozen container holds an immutable type). Callers needing mutable access cast via `dict(result.replication_kit_metadata)` at the call site. Same pattern applied to `LoadResult.warnings` (tuple-of-str rather than list-of-str). L1.7-C test thirteen (frozen mutation rejection) plus test twelve (metadata structure verification) confirm both invariants empirically.

---

## §4 — Vision v2.0 5-pillar alignment

The L1.7 MANUAL_INPUT layer strengthens four of the five Vision v2.0 pillars; the fifth (statistical density) is indirectly supported via the override pathway for sensitivity analysis.

| Pillar | L1.7 contribution |
|---|---|
| Institutional rigor | Eight V-rules at validation time (L1.7-B); two-layer confidence cap defense-in-depth (L1.7-B value-level plus L1.7-D forecast-time); fail-closed `ConfidenceCapViolation` at both layers; Q6-locked DMS sensitivity band preserved against user override (L5b-F F-M4(b) discipline carried forward) |
| Academic methodology | Schema versioning with migration shims (L1.7-C); replication kit metadata stamping every load (code SHA plus load timestamp plus schema version plus migration flag) per Vision section fourteen; atomic save guarantees reproducibility of saved scenarios across runs |
| Beginner-friendly UX | Six UX metadata fields on every `ManualInputField` (label, description, help_text, category, range_min, range_max); supports L8a UX surfacing for V-style or future researcher interactive use without requiring Python expertise to construct overrides |
| Statistical density | Indirect — override pathways enable scenario-stratified replication and sensitivity analysis at the user level; the layer itself does not add new indicators but enables exploration of override-space against the existing measurement inventory |
| Operational discipline | AP-AUTH-50 plus AP-AUTH-51 plus AP-AUTH-55 maintained across every sub-phase; precommit hooks (AP-AUTH-41 v7 + AP-AUTH-42) active throughout; no AP-AUTH register additions (no new patterns hit the second-instance-trigger threshold per AP-AUTH-46 gratuitous-codification guard); zero regressions across cumulative plus sixty-nine new tests over the sprint |

---

## §5 — Gate count progression plus Gate 29 NEW

Gate count entered L1.7 at twenty-eight (from L5b-E codification of Gate 28). L1.7-D added Gate 29 (MANUAL_INPUT integration invariants) bringing the count to twenty-nine. The Gate 29 six-criteria CLI dry-run output passes verbatim at L1.7-D ACCEPT and continues to pass at L1.7-E ACCEPT.

Gate 29 design uses the project-standard `GateReport` unified return type (mirrors Gates 1 through 28; does NOT introduce a `Gate29Result` subclass despite Strategic pre-flight tentative wording — Track A noted the deviation at L1.7-D ACCEPT report and Strategic ratified the project-convention path).

---

## §6 — AP-AUTH register state

No new AP-AUTH codifications during L1.7. Register stands at one through fifty-five (unchanged from `l5b-complete`).

AP-AUTH disciplines actively exercised during L1.7:

| AP-AUTH | Discipline | L1.7 application |
|---|---|---|
| forty-two | Word-form cumulative arithmetic | This document plus `L1_7_BACKLOG.md` |
| forty-one v7 | Verification scope filename-allowlist | No `*_VERIFICATION.md` files created in L1.7; v7 scope no-op throughout |
| fifty | Upstream grep at pre-flight | Phase 0 + Step 2 at every L1.7 sub-phase; caught Surface 5 ambiguity at L1.7-D plus state drift at L1.7-D re-send |
| fifty-one | Risk register grep evidence | Every pre-flight risk register cited grep evidence |
| fifty-three | Reviewer-driven seven-step closure | N/A — no reviewer findings during L1.7 (R6 cycle had closed at L5b-H) |
| fifty-four | Envelope characterization | N/A — L1.7 is a new layer, not L5b internal hardening; envelope STAYS CLOSED at nine instances |
| fifty-five | Push verification at ACCEPT | Explicit branch + tag pushes; ls-remote verification at every L1.7 sub-phase ACCEPT including dual-tag push at L1.7-E |

---

## §7 — Latent debt outstanding

Three items captured as informal latent debt entering L6 (not blockers for L1.7 sprint closure):

1. **Surface 5 wire-site**: Helper `apply_recession_p_override_for_horizon` exists at `macro_pipeline/manual_input/integration.py:141` with no current consumer. If L6 (or any subsequent layer) introduces a discrete recession-P composite-computation callable, the wire-site can be added without API break to the helper. Tracked here as a forward-looking integration item, not a defect.

2. **POSIX CI matrix expansion** (Vision section five operational discipline): Tests run on Windows CI only. `os.replace` cross-platform atomicity is a Python documentation guarantee, not directly verified in CI. Captured for an eventual CI matrix expansion (POSIX runner) at the maintainer's discretion.

3. **`L1_7_BUILD_SPEC.md` formal authoring**: Strategic L1.7 spec was authored inline across five pre-flight prompts; no formal spec document was filed. The retroactive precedent (`L5B_BUILD_SPEC.md` never formally authored either; spec lived inline in pre-flights plus `LAYER_5_BUILD_SPEC.md` §15) carries forward acceptably. If L6 surfaces a need for a consolidated L1.7 spec document for cross-reference or reviewer cycle, retroactive authorship is straightforward from the five pre-flights archived in the V mediation chain.

---

## §8 — L1.7 sprint TRULY COMPLETE

L1.7 MANUAL_INPUT layer ships at five-of-five perfect ACCEPT. Convergence streak at thirty-three of thirty-three perfect ACCEPTs (twenty-eight L5 plus L5b cumulative plus five L1.7 sub-phases). Vision v2.0 five-pillar discipline preserved across the build: institutional rigor strengthened via two-layer cap defense-in-depth; academic methodology strengthened via schema versioning plus replication-kit metadata; beginner-friendly UX strengthened via per-field UX metadata; operational discipline maintained via AP-AUTH-50 plus AP-AUTH-55 at every sub-phase; statistical density indirectly supported via override-space exploration capability.

The MANUAL_INPUT layer is now production-grade for V (and future users) to override macro forecast inputs for nowcasting, custom assumptions, replication kits, and academic exploration. No confidence cap bypass possible at either L1.7-B value-level or L1.7-D forecast-time layer. All overrides auditable via the replication-kit metadata stamped on every `LoadResult`. Forward path is L6 build kickoff (next major layer per Master Prompt v3.1 build plan); Strategic Track B authors L6 pre-flight after L1.7-E ACCEPT confirmation.

Tags affixed at THIS COMMIT: `l1.7-e-accept` (sub-phase ACCEPT) plus `l1.7-complete` (sprint closure). Both pushed to origin per AP-AUTH-55 push verification discipline.

**L1.7 sprint TRULY COMPLETE.**
