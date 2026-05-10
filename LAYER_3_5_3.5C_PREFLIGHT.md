# LAYER 3.5C — Pre-Flight Audit (NBER Announcement Calendar)

**Spec ref**: `LAYER_3_5_BUILD_SPEC.md` §5 (3.5C)
**Branch**: `claude/layer-3-5-build` @ `44602de` (3.5B complete + verification)
**Date**: 2026-05-09
**Author**: Claude Code (build agent)
**Status**: PROCEED-WITH-Dxx if disposition confirmed; PAUSE only if scope expansion needed

---

## §1 — Audit Result Header

| Field | Value |
|---|---|
| Sub-phase | 3.5C — NBER Announcement Calendar |
| Estimated effort (spec) | 4–6h |
| My estimate after audit | **4.5–5.5h** (within range) |
| Tests added (spec target) | +8 (4 NEG / 4 POS) |
| Gate added | Gate 14 |
| Locked decisions (3.5C-D1..D4) | training_only (D1), CSV in repo (D2), manual quarterly (D3), add new turning points before commit (D4) |
| Anticipated deviations | likely D22 (interpretive: existing NBER PIT tests need update because semantics change) |
| Conviction (statistical / operational / actionability) | 0.86 / 0.82 / 0.88 — see §10 |

---

## §2 — Spec §5.2 Mandatory Items (3.5C-specific)

### §2.1 Item 1+2 — NBER announcement table (1980+, sourced from nber.org)

WebFetched https://www.nber.org/research/business-cycle-dating/business-cycle-dating-committee-announcements:

| Peak | Peak Announced | Trough | Trough Announced | Notes |
|---|---|---|---|---|
| 1980-01 | 1980-06-03 | 1980-07 | 1981-07-08 | (1980 cycle) |
| 1981-07 | 1982-01-06 | 1982-11 | 1983-07-08 | double-dip |
| 1990-07 | 1991-04-25 | 1991-03 | 1992-12-22 | |
| 2001-03 | 2001-11-26 | 2001-11 | 2003-07-17 | |
| 2007-12 | 2008-12-01 | 2009-06 | 2010-09-20 | GFC |
| 2020-02 | 2020-06-08 | 2020-04 | 2021-07-19 | COVID 4-month peak announcement |

**6 cycles total post-1978.** Matches spec §5.2-2 expectation.

### §2.2 Item 3 — December 2007 peak announcement = December 1, 2008 ✓

Confirmed: per ChatGPT Dim 1 finding, the spec §5.2-3 expected value of "December 1, 2008" matches the WebFetched date of "December 1, 2008" exactly. **12-month lag** (peak 2007-12 → announce 2008-12-01).

### §2.3 Item 4 — 2020 COVID peak announcement = June 8, 2020 ✓

Confirmed: WebFetched "June 8, 2020" matches spec §5.2-4 ("June 8, 2020"). **4-month lag** (peak 2020-02 → announce 2020-06-08). Atypically fast.

### §2.4 Item 5 — Pre-1978 cycles + training_only policy

NBER record cycles before 1978 in the WebFetched table:
- 1973-11 peak / 1975-03 trough (no separate announcement date in the data page; would have been retroactively determined)
- The spec lists 1969-12 peak / 1970-11 trough, but the WebFetched data page starts at 1973-11. (Older cycles likely exist; spec §5.2 cites them.)

**Per spec §5.4-D1 + Decision Lock §2.3**: pre-1978 policy = `training_only`. Real-time inference for as_of < 1978-01 raises `PitDataUnavailableError`. Training mode (with explicit `is_real_time=False`) returns label from latest NBER_REC_LABEL data with caveat flag.

---

## §3 — Spec §2.2 Generic Items

### §3.1 Item 1 — Files this sub-phase will touch

| File | Action | Notes |
|---|---|---|
| `data/nber_announcement_calendar.csv` | NEW (committed) | 6 rows; canonical announcements list |
| `macro_pipeline/regime/nber_calendar.py` | NEW | `NberCycle` dataclass + `NberCalendarLoader` class + `NberCycleNotFoundError` exception |
| `macro_pipeline/regime/nber_extract.py` | MODIFY | replace 180-day visibility-shift logic with calendar-driven lookup; preserve latest-mode pathway for backward compat (gate 8 ground-truth check still uses `extract_nber_state(asof)` without ctx) |
| `macro_pipeline/regime/exceptions.py` | MODIFY | add `NberCycleNotFoundError` |
| `macro_pipeline/regime/__init__.py` | MODIFY | export `NberCalendarLoader`, `NberCycle`, `NberCycleNotFoundError` |
| `macro_pipeline/access.py` | MODIFY | add `is_real_time: bool = True` field to `PitDataContext` (per spec §5.3-4) |
| `macro_pipeline/config.py` | MODIFY | add `NBER_PRE_1978_POLICY: Literal[...] = "training_only"` constant |
| `macro_pipeline/loaders/nyfed_recprob.py` | (LIKELY UNCHANGED) | `release_lag_days=180` becomes irrelevant for `extract_nber_state` (which now uses calendar) but still sane for cache PIT semantics if loader is invoked PIT-mode for other purposes. Recommend leaving in place to avoid scope creep; add docstring note that calendar takes precedence in regime extraction. See AM16. |
| `macro_pipeline/regime/regime_context.py` | MAYBE MINOR DOC UPDATE | the docstring for `_KINDLEBERGER_*` mentions "180d release lag"; may want to update wording but not behavior. |
| `macro_pipeline/validation.py` | MODIFY | add `validate_gate14_nber_calendar()` + `_cli_gate14`; **also update the PIT no-ffill check in `validate_gate8_regime` (lines 1376-1395)** — it uses as_of=2008-12-01 querying 2008-09 expecting raise; post-3.5C the 2007-12 peak is announced 2008-12-01 so this no longer raises. Replacement: query at as_of pre-2008-12-01 (e.g., as_of=2008-11-30) where peak is not yet announced. |
| `tests/test_nber_calendar.py` | NEW | 8 new tests per spec §5.5 |
| `tests/test_regime_nber.py` | MODIFY | `test_nber_pit_raises_when_label_unannounced` (line 41-53) and `test_last_known_label_date_pit_mode` (56-61) — see §3.2 |

### §3.2 Item 2 — Existing tests that may break

| Test | Risk | Mitigation |
|---|---|---|
| `tests/test_regime_nber.py::test_nber_pit_raises_when_label_unannounced` | **HIGH** — uses as_of=2008-12-01 querying 2008-09 expecting `PitDataUnavailableError`. Post-3.5C: 2007-12 peak is announced 2008-12-01 → at as_of=2008-12-01 the calendar resolves "recession" cleanly; **no raise**. | UPDATE: change as_of to 2008-11-30 (pre-peak-announcement) querying 2008-12 OR querying a future date — assertion still tests "raise on no-info" but with the right semantic. Alternative: keep 2008-12-01 as_of but query 2009-01 (which lacks announcement until 2010-09 trough). I'll choose the latter as it preserves the test's intent (real-time PIT mode refuses to label months past announced turning points where the next is uncertain). |
| `tests/test_regime_nber.py::test_last_known_label_date_pit_mode` | LOW — asserts `boundary ∈ [2007-12-01, 2008-06-30]` at as_of=2008-12-01. Post-3.5C: `last_known_label_date = 2007-12` (the most recent announced turning point's stamp). 2007-12-01 is at the LOWER edge of the asserted range; assertion `boundary <= 2008-06-30` passes (2007-12 < 2008-06-30); assertion `boundary >= 2007-12-01` passes (2007-12 == 2007-12-01). Tight but PASSES. | Verify post-impl. |
| `tests/test_regime_nber.py::test_nber_pit_safe_query_within_visible_window` | LOW — at as_of=2010-06-01 querying 2008-09 expecting "recession". Post-3.5C: 2007-12 peak announced 2008-12 ✓; 2009-06 trough announced 2010-09-20 (after as_of=2010-06). So at as_of=2010-06-01 the most recent visible turning point is the 2007-12 peak → 2008-09 in recession ✓. PASSES. | None |
| `tests/test_regime_nber.py::test_nber_query_before_earliest_label_raises` | LOW — query 1850-01-01 in latest mode. Should still raise (calendar entries do not extend before 1980; latest-mode lookup returns no data for 1850). PASSES. | None |
| `tests/test_regime_nber.py` other tests (latest-mode + USREC) | LOW — latest mode unaffected by calendar overlay. PASSES. | None |
| `macro_pipeline/validation.py::validate_gate8_regime` PIT no-ffill check (lines 1376-1395) | **HIGH** — same root cause as above test. | UPDATE per §3.1 (use as_of=2008-11-30 OR query future date). |
| `tests/test_regime_state_derivation.py` | LOW–MED — derives regime_state from NBER + Kindleberger + HMM; if NBER is None for pre-1978 anchors in real-time mode the test may need adjustment. Need to inspect specific test cases. | Will inspect during impl; predominantly historical anchors should still resolve. |
| `tests/test_regime_context.py` | LOW–MED — same as above. | Will inspect. |
| `tests/test_pit_access.py` | LOW — tests PIT loaders for non-NBER series; orthogonal to NBER calendar. | None |
| Tests at pre-1978 anchors in `validate_gate8_regime` (1960, 1974) | MED — `build_regime_context(ctx)` for these calls `extract_nber_state(query, ctx=ctx)`. Post-3.5C in real-time mode (default `is_real_time=True`), pre-1978 raises → caught in build_regime_context (existing `except PitDataUnavailableError` at line 193-195) → `nber_result=None`. Gate 8 only checks Kindleberger/Dalio phases for these anchors, NOT `derive_regime_state`. So pre-1978 anchors should still pass Gate 8. | Verify post-impl by running gate8. |

**Net impact**: 2 existing tests need explicit update (1 in `test_regime_nber.py`, 1 in `validation.py`); ~3 other regime tests need verification. No mass test rewrites.

### §3.3 Item 3 — Empirical reading

3.5C does not have a §2.3-listed empirical calibration requirement (those are 3.5B confidence cap, 3.5D indeterminate cap, 3.5E sha latency). The 4 spec §5.2 verifications above (§2.1-§2.4) substitute as the pre-flight empirical step.

**Net empirical findings**:
- 6 post-1978 cycles confirmed from NBER official source
- 2007-12 peak / 2008-12-01 announce verified ✓
- 2020-02 peak / 2020-06-08 announce verified (4-month lag) ✓
- pre-1978 cycles begin with 1973-11 peak in the public dating page (older cycles less consistently announced; per spec §5.4-D1, training_only)

### §3.4 Item 4 — Ambiguities

| ID | Ambiguity | Spec ref | Proposed resolution | Decision needed? |
|---|---|---|---|---|
| **AM16** | Loader-level `release_lag_days=180` for NBER_REC_LABEL (`nyfed_recprob.py:147`): post-3.5C the calendar is the authoritative source for `extract_nber_state`. The loader-level lag becomes "irrelevant for regime extraction but still applied if anyone PIT-loads NBER_REC_LABEL via `load_series` directly". Three options: (a) leave in place (no behavior regression for direct loaders), (b) zero-out to 0 (minimum lag), (c) bump to 365 (conservative). | spec §5.6 Gate 14 #4 + §5.7-2 | **(a) leave in place** — Gate 14 #4 says "zero references to literal 180 in nber_extract.py", which is already true (only docstring at line 15 mentions it; will add a deprecation note). The loader-level constant is a different file and serves a different purpose (cache visibility for direct loaders, e.g., HMM training in latest mode is unaffected). Document in scoring/regime README. | **YES — confirm "leave in place" is acceptable.** |
| **AM17** | Spec §5.3-3 says pre-1978 + training mode "returns label with caveat flag". The current `NberStateResult` dataclass has fields `state, state_date, last_known_label_date, as_of, source` — NO caveat flag. Need to add a field OR reuse `source` (but source is the loader provenance). Recommend adding `is_pre_1978_training_only: bool = False` field. | §5.3-3 | Add a new optional field on `NberStateResult` (default False); set True only in pre-1978 training-mode path. | NO — straightforward. |
| **AM18** | Source URL for CSV rows: should each row use a unique URL pointing to the specific announcement memo (e.g., per-cycle press release), OR a single canonical URL pointing to the aggregator page (https://www.nber.org/research/business-cycle-dating/business-cycle-dating-committee-announcements)? Spec §5.7-7 says "each row's source_url HTTP GET returns 200" but doesn't require uniqueness. Per-cycle URLs are fragile (NBER may renumber pages); aggregator URL is stable. | §5.3-1 + §5.7-7 | Use **the aggregator URL for all 6 rows**, with the `notes` field carrying the cycle-specific tag (e.g., "GFC", "COVID 4-month announcement"). Stable and auditable. | NO — clear procedural fix. |
| **AM19** | The `NberCalendarLoader.label_visible_at` method (spec §5.3-2) and the spec example pseudo-code at §5.3-3 (`calendar.last_known_label(as_of)`) — these methods aren't both fleshed out; the implementation needs a small design choice. I'll define: `last_known_label(as_of) → (regime_at_as_of, last_turning_point_date, last_announcement_date)` returning the most recent announced turning point's effect on the as_of regime. | §5.3-2/3 | Define the loader's method surface concretely during implementation. Will keep `last_known_label` returning a structured tuple/dataclass. | NO — design refinement. |
| **AM20** | Caveat: `release_lag_days=60` for `USREC` (config.py:298) is a separate constant. Spec §5.3 talks about NBER calendar replacing the 180-day approximation in `nber_extract.py`. USREC's 60-day lag is the FRED publication lag (FRED publishes USREC monthly, ~60 days after observation). Different concept from NBER announcement lag. Leave USREC unchanged. | §5.3 | Leave `USREC.release_lag_days=60` in config.py untouched. NBER calendar applies only to NBER announcement timing, not FRED publication timing. | NO — clear. |

### §3.5 Item 5 — Risk callouts

| ID | Risk | P(occurrence) | Mitigation |
|---|---|---|---|
| R-3.5C-1 (closed) | NBER announcement-date CSV requires WebFetch from nber.org (no API) | 100% | DONE in §2 above; 6 cycles tabulated. |
| R-3.5C-2 | Removing `release_lag_days=180` constant (or replacing it semantically) must not break Gate 8 PIT no-ffill anchor at as_of=2008-12-01 | 100% (verified) | UPDATE Gate 8 boundary check per §3.2 |
| R-3.5C-3 | Pre-1978 anchors in Gate 8 (1960, 1974) raise PitDataUnavailableError after 3.5C in real-time mode → existing `except PitDataUnavailableError` in build_regime_context catches → `nber=None`. Gate 8 only checks Kindleberger/Dalio for these anchors, not derived state. | LOW 5% | Verify by running gate8 post-impl. |
| R-3.5C-4 | Spec §5.5 test #7 (headline) is the SAME assertion that would have failed under old logic. Need to ensure post-impl the result for as_of=2008-09 querying 2008-09 = "expansion" (not "recession"). | 100% (intentional) | Implement per spec §5.3-3 verbatim. |
| R-3.5C-5 | NBER calendar CSV parsing: pd.Period values like "1980-01" need explicit format hints to avoid pandas guessing. | LOW 5% | Use `pd.Period(s, freq="M")` explicitly. |
| R-3.5C-6 | `is_real_time` default=True breaks anything that constructed PitDataContext positionally. | LOW 5% | Field is keyword-only-default; positional construction `PitDataContext(as_of=...)` unchanged because `as_of` is the first/only positional arg in the existing dataclass. |
| R-3.5C-7 | Cross-phase: 3.5D will need to handle pre-1978 dissent / indeterminate logic too. Not a 3.5C concern but documented. | n/a | Document in 3.5D pre-flight. |
| R-3.5C-8 | If NBER announces a new turning point during L3.5 build (3.5C-D4 says: add to CSV before commit). Right now no signal of imminent recession in 2026. | LOW 2% | Re-check WebFetch source before commit; ignore if no new announcement. |

### §3.6 Item 6 — Effort estimate

| Step | Estimate (h) |
|---|---|
| Pre-flight (this) | 0.5 (with WebFetch + audit) |
| Address ambiguities AM16, AM17 (light V approval) | gate |
| `data/nber_announcement_calendar.csv` (6 rows) | 0.2 |
| `macro_pipeline/regime/nber_calendar.py` (loader + dataclass) | 0.8 |
| `macro_pipeline/regime/exceptions.py` (NberCycleNotFoundError + new fields) | 0.2 |
| `macro_pipeline/regime/nber_extract.py` (refactor; calendar-driven lookup; preserve latest-mode) | 1.0 |
| `macro_pipeline/access.py` (`PitDataContext.is_real_time`) | 0.2 |
| `macro_pipeline/config.py` (`NBER_PRE_1978_POLICY`) | 0.1 |
| `macro_pipeline/regime/__init__.py` (exports) | 0.1 |
| `macro_pipeline/validation.py` Gate 14 + CLI; update Gate 8 PIT-boundary | 0.6 |
| 8 new tests in `tests/test_nber_calendar.py` (4 NEG / 4 POS) | 0.7 |
| Update 1-2 existing tests in `test_regime_nber.py` | 0.3 |
| Smoke-test post-impl (manual REPL: extract_nber_state at 2008-09 / 2008-12) | 0.2 |
| Pytest + ruff + 14 gates | 0.3 |
| Verification report | 0.3 |
| **Total** | **5.5–6.0** | within 4-6h spec band; tight at upper edge. |

---

## §4 — Decisions Locked Per Standing Orders

| Decision | Locked default |
|---|---|
| 3.5C-D1 (pre-1978 policy) | training_only |
| 3.5C-D2 (calendar source) | CSV in repo |
| 3.5C-D3 (update cadence) | manual quarterly |
| 3.5C-D4 (mid-build new announcement) | add to CSV before commit |

No empirical-calibration override needed (3.5C has no §2.3-listed threshold).

---

## §5 — Decisions Requested From V / Strategic (BEFORE Coding)

### §5.1 AM16 — Loader-level `release_lag_days=180` disposition

| Option | Description |
|---|---|
| **(a) recommended** | **Leave `release_lag_days=180` in `nyfed_recprob.py:147`** unchanged; the calendar in `extract_nber_state` overrides for regime extraction. Add a docstring note that calendar takes precedence post-3.5C. Gate 14 #4 ("zero references to literal 180 in nber_extract.py") is satisfied because nber_extract.py only references 180 in a docstring. |
| (b) | Zero-out to 0 in nyfed_recprob.py: NBER_REC_LABEL becomes a "no-lag, NaN-masked-past-determination" series. Could be unintentionally consumed in PIT mode by other callers expecting some lag. |
| (c) | Remove the `release_lag_days` setter entirely from the loader. Consumers of NBER_REC_LABEL must use the calendar. |

**Recommend (a)** — minimal blast radius; calendar takes precedence in the only consumer that matters (regime extraction).

### §5.2 AM17 — `NberStateResult` field for pre-1978 caveat

Recommend: add `is_pre_1978_training_only: bool = False` field. Set True only in pre-1978 training-mode path. NO PAUSE — proceeding with this disposition unless overridden.

### §5.3 AM18 — Source URL strategy (single aggregator URL for all 6 rows)

Recommend: use `https://www.nber.org/research/business-cycle-dating/business-cycle-dating-committee-announcements` for all rows. NO PAUSE — proceeding with this disposition unless overridden.

---

## §6 — Anticipated Dxx filing

| ID | Topic | Trigger |
|---|---|---|
| **D22 (likely)** | Existing PIT NBER tests (`test_nber_pit_raises_when_label_unannounced` and Gate 8's PIT no-ffill check) updated due to spec semantics change. ACCEPT with rationale: post-3.5C, pre-2008-12-01 announcements made the previous "raise at 2008-12 query 2008-09" path unreachable; replacement assertions test the new behavior at as_of pre-announcement (e.g., 2008-11-30) or pre-1978 dates. | spec §5.3 calendar replaces 180-day mechanism; existing tests verified the old approximation, not the new contract. |
| (other) | TBD during impl | n/a |

---

## §7 — Implementation Order (post-approval)

1. Author `data/nber_announcement_calendar.csv` (6 rows, validated against §2 above).
2. Add `NberCycleNotFoundError` to `regime/exceptions.py`; add `is_pre_1978_training_only` field to `NberStateResult` (in `nber_extract.py`).
3. Add `NBER_PRE_1978_POLICY` constant to `config.py`.
4. Add `is_real_time: bool = True` field to `PitDataContext` (`access.py`).
5. Create `macro_pipeline/regime/nber_calendar.py` with `NberCycle` dataclass + `NberCalendarLoader` class.
6. Refactor `macro_pipeline/regime/nber_extract.py` to use the calendar:
   - `extract_nber_state` consults `NberCalendarLoader.last_known_label(as_of)` for 1978+
   - Pre-1978 + real-time → `PitDataUnavailableError`
   - Pre-1978 + training mode → load NBER_REC_LABEL latest, return state with caveat flag
   - Latest mode (no ctx) → unchanged (post-hoc inspection)
7. Update `regime/__init__.py` to export new symbols.
8. Update `validation.py`:
   - Add `validate_gate14_nber_calendar()` + `_cli_gate14`
   - Update Gate 8's PIT no-ffill boundary check (line 1376-1395) to use as_of pre-2008-12 announcement OR query a date past announced trough.
9. Write 8 new tests in `tests/test_nber_calendar.py` (4 NEG / 4 POS per spec §5.5).
10. Update 1-2 tests in `tests/test_regime_nber.py` (per §3.2).
11. Smoke-test post-impl: REPL run `extract_nber_state(2008-09-01, ctx=PitDataContext(as_of=2008-09-01))` → "expansion"; `extract_nber_state(2008-09-01, ctx=PitDataContext(as_of=2008-12-01))` → "recession".
12. Full pytest + ruff + 14 gates green.
13. Commit per spec §5 message template.
14. Author `LAYER_3_5_3.5C_VERIFICATION.md` per spec §5.7 (10 items).
15. PAUSE for V approval.

---

## §8 — Test plan preview (8 new + 2 updates)

### New (`tests/test_nber_calendar.py`)

| # | Test | Type | What it asserts |
|---|---|---|---|
| 1 | `test_nber_dec_2007_peak_announced_dec_2008` | POS | Calendar lookup returns `2008-12-01` announcement for 2007-12 peak |
| 2 | `test_nber_2020_covid_peak_4_month_announcement` | POS | 2020-02 peak → 2020-06-08 announcement |
| 3 | `test_nber_pre_1978_real_time_raises_PitDataUnavailableError` | NEG | as_of=1975-06, is_real_time=True → raises |
| 4 | `test_nber_pre_1978_training_mode_allowed` | POS | as_of=1975-06, is_real_time=False → returns label with `is_pre_1978_training_only=True` |
| 5 | `test_nber_calendar_completeness_post_1978` | POS | All 6 cycles present (1980, 1981, 1990, 2001, 2007, 2020) |
| 6 | `test_nber_announcement_after_peak` | NEG | Every row: peak_announcement_date > peak_date AND trough_announcement_date > trough_date |
| 7 | `test_extract_nber_state_uses_actual_lag_not_180` | POS | At as_of=2008-09-01 query 2008-09-01 → "expansion" (announcement was 2008-12, would have differed under 180-day approx) |
| 8 | `test_pit_data_context_is_real_time_default_true` | POS | Backward compat: `PitDataContext(as_of=...)` has `is_real_time=True` by default |

NEG/POS = 3/5 — below the 50% NEG floor of spec §2.7. **Will add 1 NEG test during impl** to satisfy §2.7:
- `test_nber_calendar_csv_malformed_raises` (NEG): if CSV is missing required columns or has invalid date format, loader raises `NberCalendarLoadError`.

Final NEG/POS = 4/5 (44%). Hmm, still below 50%. To hit 50% with 8 tests, need 4 NEG / 4 POS. So I should swap one POS into NEG. Options:
- Convert `test_pit_data_context_is_real_time_default_true` to NEG variant: `test_pit_data_context_explicit_is_real_time_false_works` — actually that's POS.
- Add another NEG: `test_nber_calendar_loader_unknown_cycle_raises` (querying for a turning point not in calendar → `NberCycleNotFoundError`).

Going with **4 NEG / 4 POS** by:
- Replacing test #5 (`test_nber_calendar_completeness_post_1978`) with NEG variant: `test_nber_calendar_no_negative_lag` (tested both ways; counts as NEG since it asserts a fail-closed invariant).
- Or keep test #5 POS and add `test_nber_calendar_loader_unknown_cycle_raises` (NEG).

Final shape (TBD during impl): 4 NEG / 4 POS, satisfying §2.7. Tests #3, #6, plus 2 of (#5 inversion / unknown cycle / malformed CSV).

### Updated (`tests/test_regime_nber.py`)

| Test | Change |
|---|---|
| `test_nber_pit_raises_when_label_unannounced` | Update: change to as_of=2008-11-30 query=2008-09-01 (pre-peak-announcement → 2001-11 trough is most recent visible → state "expansion" returned, no raise) OR query=future (no announcement). The test's intent is "real-time PIT mode refuses when announcement unavailable"; pick a query where that's still true. **Resolution**: use as_of=2008-11-30, query=2009-01-01. At that as_of, 2007-12 peak NOT yet announced → most recent visible is 2001-11 trough → expansion. The query of 2009-01 lands AFTER 2001-11 trough but no later turning point is announced. So state returned = "expansion" (until further notice). The test's assertion needs to flip from `raises PitDataUnavailableError` to `state=="expansion"`. **Or** repurpose the test to assert pre-1978 + real-time raises (leveraging the new contract). **Simpler**: rename + repurpose to `test_nber_pre_1978_real_time_raises` (overlapping new test #3, can be removed from this file since spec #3 replaces it). |
| `test_last_known_label_date_pit_mode` | Verify post-impl that boundary == 2007-12-01 at as_of=2008-12-01 (within existing assertion range; should pass without change). |

---

## §9 — Proof Contract Mapping (10 items, spec §5.7)

| Spec proof # | How I will demonstrate |
|---|---|
| 1 | `cat data/nber_announcement_calendar.csv` shows ≥6 rows for 1978+ |
| 2 | `grep -n "release_lag_days" macro_pipeline/regime/nber_extract.py` returns no matches OR only docstring deprecation note |
| 3 | `pytest tests/test_nber_calendar.py` shows 8 tests pass |
| 4 | REPL: `from macro_pipeline.regime import extract_nber_state, NberCalendarLoader; from macro_pipeline.access import PitDataContext; extract_nber_state(pd.Timestamp("1975-06-01"), ctx=PitDataContext(as_of="2024-01-01", is_real_time=True))` raises PitDataUnavailableError |
| 5 | REPL: `extract_nber_state(pd.Timestamp("2008-09-01"), ctx=PitDataContext(as_of="2008-09-01"))` returns "expansion" |
| 6 | REPL: `extract_nber_state(pd.Timestamp("2008-09-01"), ctx=PitDataContext(as_of="2008-12-01"))` returns "recession" |
| 7 | manual: `curl -I https://www.nber.org/research/business-cycle-dating/business-cycle-dating-committee-announcements` → HTTP 200 |
| 8 | `python -m macro_pipeline.validation gate14` PASS |
| 9 | full pytest = 524 + 8 = 532 (or higher) |
| 10 | §10 of this document, refreshed at verification time |

---

## §10 — Pre-flight Conviction (3-field)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | 0.86 | High: WebFetch confirms all 6 announcement dates exactly; spec §5.2-3 (Dec 2007 = Dec 2008) and §5.2-4 (Feb 2020 = Jun 2020) match. The 4 spec-headline scenarios are deterministic from this calendar. Slight haircut because the existing `release_lag_days=180` mechanism interacts with the new calendar in subtle ways (AM16). |
| `conviction_operational` | **0.82** | Medium-high: 6-cycle CSV is small + auditable; aggregator URL is stable. Slight haircut: 2 existing PIT NBER tests need explicit semantics-change updates (D22 likely); the spec is interpretive on whether to *replace* or *delete* `test_nber_pit_raises_when_label_unannounced`. **Binding.** |
| `conviction_actionability` | 0.88 | High: post-3.5C the regime classifier returns the spec-correct PIT NBER state at any backtest as_of; L5 walk-forward CV can use this without 180-day approximation drift. |

Aggregate `confidence_overall` (per L1.5): **0.82** (operational binding).

---

## §11 — END

Pre-flight complete. **PAUSED** awaiting:
1. APPROVE (recommendations: AM16=(a) leave loader-lag, AM17 add caveat field, AM18 aggregator URL — execute §7 order), OR
2. REVISE (specify alternative for any of AM16/17/18, OR scope expansion).

Per Standing Orders, AM16/17/18 are PROCEED-WITH-Dxx scenarios (none crosses the PAUSE-required threshold), but I am surfacing them for explicit signoff because AM16 touches a spec-literal interpretation (Gate 14 #4). If APPROVE, I will file D22 noting the existing-test update and proceed to coding (5.5–6.0h estimated).

If APPROVE: I will execute §7 order, expecting verification report ready at ~6h elapsed.
