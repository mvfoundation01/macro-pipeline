# L1.7 MANUAL_INPUT Layer Backlog

**Scope**: L1.7 sprint sub-phase ledger plus latent-debt register. Mirrors `L5B_BACKLOG.md` structure at the institutional-discipline layer.

**Spec source**: Strategic-authored inline across five sub-phase pre-flight prompts (no formal `L1_7_BUILD_SPEC.md` filed; precedent inherited from L5b retroactive-inline pattern). See `L1_7_RETROSPECTIVE.md` §7 latent debt entry three on retroactive spec authoring option.

**Sprint window**: 2026-05-15 (single calendar day)
**Sub-phase count**: five (A schema / B validation / C persistence / D integration / E closure)
**Final state**: tag `l1.7-complete` at L1.7-E ACCEPT commit

---

## L1.7 SPRINT EXECUTION LOG (completed sub-phases)

### L1.7-A — schema definition (2026-05-15)

**ACCEPT tag**: `l1.7-a-accept`
**HEAD**: `296cee5`
**Strategic spec**: Inline at session-bootstrap prompt (§2 schema overview plus §3 pre-flight)
**Approach**: Frozen-dataclass pair (`ManualInputField` plus `ManualInputSchedule`) with YAML load/save stubs; PyYAML dependency added to `pyproject.toml` plus `uv.lock`
**Module additions**: `macro_pipeline/manual_input/__init__.py` plus `macro_pipeline/manual_input/schema.py`
**Test delta**: plus eight tests (eight-hundred-two to eight-hundred-ten); NEG ratio five-of-eight (sixty-two point five percent)
**Gate delta**: zero (Gate 29 reserved for L1.7-D)
**AP-AUTH delta**: zero
**Sxx delta**: zero
**Key design decisions**:
- Four MANUAL_INPUT categories: `recession_p` plus `regime_classifier_override` plus `dms_override` plus `scenario_inputs`
- Precedence model: `manual_only` plus `manual_or_auto` plus `auto_only`
- Persistence format: YAML (human-editable; L8a-UX-ready)
- Schema version one hard-rejected at fresh load (forward-compat shim deferred to L1.7-C)

---

### L1.7-B — validation layer (2026-05-15)

**ACCEPT tag**: `l1.7-b-accept`
**HEAD**: `92385e9`
**Strategic spec**: Inline at L1.7-B pre-flight prompt (§3 V-rules table)
**Approach**: Eight V-rules; V5 fail-closed via `ConfidenceCapViolation`; V1 through V4 plus V6 through V8 accumulate in `ValidationReport`
**Module additions**: `macro_pipeline/manual_input/validation.py`
**Test delta**: plus fifteen tests (eight-hundred-ten to eight-hundred-twenty-five); NEG ratio nine-of-fifteen (sixty percent)
**Gate delta**: zero (Gate 29 reserved for L1.7-D)
**AP-AUTH delta**: zero
**Sxx delta**: zero
**V-rules**:
- V1: recession_p value in zero-to-one
- V2: recession_p non-decreasing in horizon (cumulative probability)
- V3: DMS override sign (less than or equal to zero)
- V4: DMS override range (negative-five-hundred to zero bps)
- V5: confidence cap at ten-year (seventy-percent non-stratified; fifty-five-percent regime-stratified); raise `ConfidenceCapViolation` per Standing Order number nine
- V6: field_id uniqueness across override categories
- V7: regime_classifier_override path validity (existence plus dot-py)
- V8: author plus description non-empty (post-strip)

---

### L1.7-C — persistence plus versioning plus migration (2026-05-15)

**ACCEPT tag**: `l1.7-c-accept`
**HEAD**: `2b000ec`
**Strategic spec**: Inline at L1.7-C pre-flight prompt (§3 LoadResult plus migration matrix plus atomic-write pattern)
**Approach**: Robust YAML load (existence plus parse plus version plus migration); atomic save via sibling tmp plus fsync plus `os.replace` (mirrors `cache.atomic_write_bytes` precedent); migration dispatch with v1 no-op plus v2 forward-compat shim plus v0 NOT IMPLEMENTED
**Module additions**: `macro_pipeline/manual_input/persistence.py`
**Test delta**: plus sixteen tests (eight-hundred-twenty-five to eight-hundred-forty-one); NEG ratio ten-of-sixteen (sixty-two point five percent)
**Gate delta**: zero (Gate 29 reserved for L1.7-D)
**AP-AUTH delta**: zero
**Sxx delta**: zero
**Migration matrix**:
- detected one to target one: no-op
- detected two to target one: forward-compat shim with warning
- detected zero to target one: `ManualInputMigrationError`
- other: `ManualInputMigrationError`
**Replication-kit metadata (Vision section fourteen)**:
- `code_sha` (git rev-parse HEAD; fallback `unknown`)
- `load_timestamp_iso` (UTC ISO 8601)
- `schema_version_detected` (str of int)
- `migration_applied` (str of bool)

---

### L1.7-D — pipeline integration plus Gate 29 NEW (2026-05-15)

**ACCEPT tag**: `l1.7-d-accept`
**HEAD**: `7ad55bf`
**Strategic spec**: Inline at L1.7-D pre-flight prompt (§2 five surfaces plus §3 Gate 29 criteria)
**Approach**: Three surfaces add `manual_inputs` keyword param (S1 `fit_return_forecast_task_b1` plus S2 `derive_forecast_sigma_v2` plus S3 `apply_dms_adjustment`); two surfaces helper-only via `macro_pipeline/manual_input/integration.py` (S4 `load_classifier_from_manual_inputs` plus S5 `apply_recession_p_override_for_horizon`); defense-in-depth confidence cap via `enforce_forecast_time_confidence_cap`
**Module additions**: `macro_pipeline/manual_input/integration.py`
**Surface modifications**: three (return_forecast.py plus forecast_sigma.py plus dms_adjustment.py)
**Test delta**: plus twenty tests (eight-hundred-forty-one to eight-hundred-sixty-one); NEG ratio ten-of-twenty (fifty percent)
**Gate delta**: plus six (**Gate 29 NEW** criteria 29.1 / 29.2 / 29.3 / 29.4 / 29.5 / 29.6)
**AP-AUTH delta**: zero
**Sxx delta**: zero
**Surface 5 disposition**: Helper-only — Step 2 grep verified no discrete recession-P composite-computation callable exists in the codebase; per V's standing-pace instruction Track A elected additive design (helper available; no API break needed if future consumer wires); Strategic ratified at L1.7-E pre-flight authorship.

---

### L1.7-E — edge cases plus retrospective plus closure (2026-05-15)

**ACCEPT tag**: `l1.7-e-accept` + `l1.7-complete`
**HEAD**: THIS COMMIT
**Strategic spec**: Inline at L1.7-E pre-flight prompt (§2 three tasks plus §3 ten test plan)
**Approach**: Three coordinated tasks — edge case coverage plus L1.7 retrospective authorship plus sprint closure ceremony
**Module additions**: `tests/test_manual_input_edge_cases.py` plus `docs/build-plans/L1_7_RETROSPECTIVE.md` plus `docs/build-plans/L1_7_BACKLOG.md` (THIS FILE)
**Test delta**: plus ten tests (eight-hundred-sixty-one to eight-hundred-seventy-one); NEG ratio five-of-ten (fifty percent)
**Gate delta**: zero
**AP-AUTH delta**: zero
**Sxx delta**: zero
**Key test (test ten)**: `test_cross_layer_cap_defense_in_depth` — validates the L1.7-B value-level plus L1.7-D forecast-time defense-in-depth architecture at distinct pipeline points
**Closure**: L1.7 sprint TRULY COMPLETE at five-of-five ACCEPT; convergence streak lifts to thirty-three of thirty-three perfect ACCEPTs.

---

## L1.7 latent debt register

Three items captured as informal latent debt entering L6 (not blockers for L1.7 sprint closure; documented in `L1_7_RETROSPECTIVE.md` §7).

| # | Item | Severity | Trigger condition | Forward owner |
|---|---|---|---|---|
| L1.7-D1 | Surface 5 wire-site (no discrete consumer) | LOW | If L6+ introduces a discrete recession-P composite-computation callable, wire `apply_recession_p_override_for_horizon` helper to it | L6 build kickoff (or layer that introduces composite) |
| L1.7-D2 | POSIX CI matrix expansion | LOW | If `os.replace` atomicity correctness needs direct verification on POSIX in addition to Python documentation guarantee | Maintainer CI configuration scope |
| L1.7-D3 | `L1_7_BUILD_SPEC.md` formal authoring (optional) | LOW | If L6 cross-reference plus future reviewer cycle surfaces a need for consolidated spec document beyond the inline pre-flight chain | L6 boundary or external-review prep |

---

## Provenance

- L1.7 sprint window: 2026-05-15 (single calendar day)
- Strategic Track B: Claude Opus four point seven, one-million-context (per V mediation chain)
- Track A: Claude Code
- Spec authority: Strategic-authored inline across five pre-flight prompts (V relays)
- Vision authority: `00_VISION_AND_PHILOSOPHY_v2.md` v2.0 binding
- Master Prompt: v3.1 §15 (build plan reference)
- Convergence baseline entering L1.7: twenty-eight of twenty-eight (L5 plus L5b cumulative)
- Convergence at L1.7 closure: thirty-three of thirty-three
