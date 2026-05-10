# LAYER 3.5b-U — Pre-Flight Audit (Option Z Release-Lag Empirical Verification + Fix)

**Spec ref**: L3.5b inline spec §4 (Codex finding U, HIGH).
**Branch**: `claude/layer-3-5b-build` @ `7051bd6` (3.5b-T complete).
**Date**: 2026-05-10
**Author**: Claude Code (build agent)
**Status**: PROCEED-with-Dxx pending V acknowledgement on AM-3.5b-U-1 (disposition unambiguous: Path A) and AM-3.5b-U-2 (calibration scope).

---

## §1 — Audit Result Header

| Field | Value |
|---|---|
| Sub-phase | 3.5b-U — Option Z Release-Lag Empirical Verification + Fix |
| Spec effort | 2–3h |
| My estimate after audit | **~2.7h** (mid-range; calibration adds modest scope per spec §4.3 Path A item 1) |
| Tests added (target) | +6 (3 NEG / 3 POS = 50% NEG, meets floor) |
| Cumulative tests post-U | 560 + 6 = **566** |
| Empirical disposition | **Path A** (observation-month index) — UNAMBIGUOUS, NOT PAUSE-required |
| Codex findings closed | U (HIGH) — empirical look-ahead bias confirmed at 2025-06-15 anchor; fix verified to remove leak |
| Locked decisions (U-D1..D4) | D1 EMPIRICAL FIRST (done — Path A), D2 apply visibility-shift inside branch (do), D3 N/A (Path A path taken), D4 update rationale (do) |
| Anticipated deviations | **D29** (calibrate `release_lag_days` from 7 → 30 per spec §4.3 Path A item 1; empirically motivated) |
| Conviction (statistical / operational / actionability) | 0.94 / 0.88 / 0.93 — see §10 |

---

## §2 — Empirical findings (per spec §4.2 CRITICAL gate)

### §2.1 SAHMREALTIME index structure

`data/cache/fred_SAHMREALTIME.parquet` inspection:

| Property | Value |
|---|---|
| Total rows | 17,572 (business-day frequency, ffilled-from-monthly source) |
| Non-null rows | 17,334 |
| Distinct value-change events | 687 |
| Spacing between adjacent value changes | 29–31 days (proves underlying observations are MONTHLY) |
| Position of value changes | First business day of each month (e.g. 2025-02-03, 2025-03-03, 2025-06-02, 2025-07-01) |
| `last_obs` (sidecar) | 2026-04-01 |
| `last_update` (sidecar) | 2026-05-09T13:19:42 |
| `release_lag_days` (sidecar) | 7 |

Recent observation values (one per month, located at first business day):

| Month index | Value | Index date |
|---|---:|---|
| 2025-04 | 0.27 | 2025-04-01 |
| 2025-05 | 0.27 | 2025-05-01 |
| 2025-06 | 0.17 | 2025-06-02 |
| 2025-07 | 0.10 | 2025-07-01 |
| 2025-08 | 0.13 | 2025-08-01 |
| ... | | |
| 2026-04 | 0.13 | 2026-04-01 |

**Empirical verdict: OBSERVATION-MONTH index** (Path A in spec §4.3). The cache stores native monthly observations placed at first-business-day-of-month, ffilled forward to daily for downstream convenience. Today is 2026-05-10; the latest non-null observation is 2026-04-01 (April 2026 SAHM, 0.13) — published ~2026-05-02 when April UNRATE was released. May 2026 SAHM (which would be published ~2026-06-05 when May UNRATE is released) is correctly absent.

### §2.2 Cross-comparison with FRED metadata + UNRATE

UNRATE is not currently in `data/cache/` for this branch (only the SAHM dependency-chain product is cached). FRED methodology + the Sahm Rule definition (Atlanta Fed) confirm: SAHM index date = first day of observation month; SAHM value at index M is computable from UNRATE through month M; UNRATE M is published first Friday of M+1; therefore SAHM M is publishable concurrent with UNRATE M (~M+30 to M+37 days from index date).

This validates the empirical finding (Path A) without requiring UNRATE cache:
- Sidecar last_obs (2026-04-01) + ~30-37 days = ~2026-05-01 to 2026-05-08 → cache `last_update` (2026-05-09) is consistent.
- Cache contains April 2026 SAHM but NOT May 2026 SAHM → consistent with publication schedule of May SAHM (~2026-06-05).

### §2.3 Bug reproduction at canonical 2025-06-15 anchor (CRITICAL)

```text
=== CURRENT (buggy) Option Z at as_of=2025-06-15 ===
Latest visible: index=2025-06-13, value=0.17

The June 2025 SAHM value (0.17) is visible at as_of=2025-06-15.
But June 2025 SAHM is computed from UNRATE June 2025, which was
published ~2025-07-04 (first Friday of July) — about 3 WEEKS AFTER
2025-06-15. This is unambiguous look-ahead bias.

=== FIXED Option Z (visibility-shift +7d as currently configured) ===
Latest visible after +7d shift: index=2025-06-13, value=0.17

INSUFFICIENT: the +7d shift only moves June obs (native index
2025-06-02) to visibility 2025-06-09 — still ≤ 2025-06-15. The
configured release_lag_days=7 is empirically TOO SMALL for SAHM's
true publication latency (~30 days for monthly first-of-month
indexed data). See AM-3.5b-U-2.
```

**Bug confirmed.** The +7d shift alone (Codex finding U consistency fix) does NOT remove the leak; **calibration of `release_lag_days` is also required** per spec §4.3 Path A item 1 ("`release_lag_days=30` (or empirically determined value)").

### §2.4 Empirical lag calibration

Required band for `release_lag_days`:
- Lower bound: at as_of=2025-06-15, June 2025 obs (index 2025-06-02) must NOT be visible → `lag > 13 days`
- Upper bound: at as_of=2025-06-15, May 2025 obs (index 2025-05-01) MUST be visible → `lag ≤ 45 days`
- Empirical band: **14 ≤ lag ≤ 45 days**

Anchored to actual publication schedule:
- SAHM index M (first-of-month) published ~M + 30-37 days
- Setting `lag=30` aligns with spec §4.3 Path A literal recommendation and provides clean integer
- At lag=30: June obs (2025-06-02) → visibility 2025-07-02 (NOT visible at as_of=2025-06-15 ✓); May obs (2025-05-01) → visibility 2025-05-31 (visible ✓)

**Disposition**: `release_lag_days` 7 → 30 (per spec §4.3 Path A item 1). File **D29** for the calibration change.

### §2.5 Inventory: callers of Option Z by-construction branch

Per spec §4.2 #3:

| Path | Branch entered |
|---|---|
| `_load_via_visibility_shift` line 379-405 | Branch 1 (Option Z) — only reachable for series with `vintage=True` AND `pit_safe_by_construction=True` |
| Series carrying both flags | **SAHMREALTIME ONLY** (per `pit_audit` validator at `access.py:379-401`) |

Empirical verification via grep:

```
$ grep -nB1 "pit_safe_by_construction.*True" macro_pipeline/config.py
config.py:147:        "pit_safe_by_construction": True,
```

Only one match in `FRED_SERIES_API`. No other config registry has the flag. So Option Z by-construction branch has exactly one caller today. The fix touches only SAHMREALTIME's PIT path.

---

## §3 — Spec §4.2 mandatory items + §4.3 file inventory

### §3.1 Files this sub-phase will touch

| File | Action | Notes |
|---|---|---|
| `macro_pipeline/access.py` | MODIFY | `_load_via_visibility_shift::Branch 1` (Option Z, lines 378-405): replace `out = s[s.index <= as_of].copy()` with the same `to_visibility_index` + truncate + restore observation index pattern used in Branch 3 (lines 429-433) |
| `macro_pipeline/config.py` | MODIFY | `FRED_SERIES_API["SAHMREALTIME"]`: `release_lag_days` 7 → 30 (D29 calibration); update `pit_construction_rationale` to document the empirical lag application |
| `macro_pipeline/utils/pit_audit.py` | MODIFY (small) | Add explicit validator for "Option Z + release_lag_days consistency": if a series has `pit_safe_by_construction=True` AND `release_lag_days >= 1`, the rationale must mention the lag application |
| `tests/test_pit_enforcement.py` | MODIFY (1 test) | Existing `test_sahmrealtime_option_z_*` tests may need to update expected `applied_release_lag_days` from 7 to 30 (D29 cascade); spot-check before code change |
| `tests/test_option_z_release_lag.py` | NEW | 6 tests per spec §4.5 |

### §3.2 Decisions locked per Standing Orders

| Decision | Locked default | Empirical override needed? |
|---|---|---|
| 3.5b-U-D1 (EMPIRICAL FIRST — index semantics) | Path A | NO — empirical exam (§2.1, §2.3, §2.4) is unambiguous |
| 3.5b-U-D2 (apply `to_visibility_index` inside branch) | YES (Path A) | NO — spec literal aligns with empirical |
| 3.5b-U-D3 (Path B publication-month flag) | N/A — Path A taken | — |
| 3.5b-U-D4 (update `pit_construction_rationale`) | YES | NO |

### §3.3 Ambiguities

| ID | Topic | Routing | Recommended disposition |
|---|---|---|---|
| **AM-3.5b-U-1** | Index semantics: observation-month vs publication-month. Spec §4.2 marks PAUSE-required if ambiguous. | **NOT PAUSE-required** — empirical case is unambiguous (Path A) | Document Path A finding; proceed |
| **AM-3.5b-U-2** | Calibration scope. Spec §4.3 Path A item 1 says `release_lag_days=30 (or empirically determined value)`. Current config is 7 — empirically too small (still leaks at 2025-06-15 anchor with +7d shift). Two readings: (a) consistency-only fix (apply lag, keep 7); (b) consistency + calibrate to 30 (spec literal). | **PROCEED-with-Dxx (D29)** | **Recommend (b)**: spec §4.3 Path A item 1 explicitly says "30 (or empirically determined value)"; empirical value is 30-37 days; (a) consistency-only does NOT actually remove the look-ahead bias the Codex finding U flagged. Without calibration, the fix is theatrical. |
| **AM-3.5b-U-3** (informational) | Test #1 expected behavior post-fix: at as_of=2025-06-15 querying SAHM, latest visible should be May 2025 (index 2025-05-01) with lag=30, NOT June 2025 (index 2025-06-02). Confirms removal of look-ahead. | **PROCEED** (no Dxx) | Standard contract test |
| **AM-3.5b-U-4** (informational) | Existing 3.5B test `test_sahmrealtime_option_z_*` may assert `applied_release_lag_days=7` in metadata. Post-D29 calibration, this becomes 30. May need test value update. | **PROCEED** (no Dxx; in-scope as test cascade per spec §4.5) | Spot-check before code change; if found, update inline as part of impl |

### §3.4 Risk callouts

| ID | Risk | Mitigation |
|---|---|---|
| R-U-1 | Calibration cascade — changing `release_lag_days` from 7 to 30 may affect: (1) Gate 13 PIT-Option-Z validation; (2) `confidence_caps` time-decay; (3) any test asserting the old value of 7. | Pre-impl grep for `release_lag_days.*7` and `applied_release_lag_days.*7` in tests/; document cascade impact before change |
| R-U-2 | The visibility-shift logic restores observation-date index (Branch 3 pattern at lines 432-433). For daily-ffilled SAHM cache, this restores the daily index but with shifted positions — semantically: each visible row now represents the SAHM value as of original observation date M, but shifted by lag. Need to validate this preserves SAHM semantics (downstream consumers expect observation-month-indexed values). | Empirical post-impl smoke at as_of=2025-06-15 + 2025-12-15 + 2026-04-15 confirming visible index dates and values |
| R-U-3 | Existing 3.5B Option Z verification (D21 era) tests assumed lag=7 was "applied" via metadata. Post-D29, the metadata claim becomes 30 and the actual code path applies it. Existing tests must reflect the new contract. | Spot-check test_pit_enforcement.py + test_signal_probability.py + Gate 13; update inline |
| R-U-4 | Calibration value 30 is rounded from empirical 30-37 day band. Spec §4.3 Path A item 1 says "30 (or empirically determined value)". Choosing 30 over 33/35/37 is a judgment call. | Document rationale in D29: spec literal "30" + sufficient margin (June obs visibility 2025-07-02 vs as_of 2025-06-15 gives 17-day buffer); rounder value reduces calibration noise; safe default |
| R-U-5 | New Standing Order ("empirical claim verification"): post-impl verification report must include grep-audit + invariant test, not just unit-test proof. | §6.4 of verification: grep for any remaining `s[s.index <= as_of]` in Option Z branch (should be zero); pytest invariant test demonstrating SAHM PIT at 2025-06-15 returns May obs not June obs |

### §3.5 Effort estimate

| Step | h |
|---|---:|
| Pre-flight (this) | 0.6 (with empirical exam) |
| AM-3.5b-U-1 + AM-3.5b-U-2 V acknowledgement | gate |
| Access.py Option Z branch refactor | 0.4 |
| Config.py SAHM `release_lag_days` calibration + rationale update | 0.2 |
| pit_audit validator addition | 0.3 |
| Existing test cascade fixes (estimated 1-2 tests) | 0.3 |
| 6 new tests | 0.6 |
| Smoke-test post-impl + ruff + Gate 13 + Gate 16 + grep audit | 0.4 |
| Verification report | 0.4 |
| **Total** | **~2.6–2.8** within spec 2–3h band |

---

## §4 — Implementation order (post-V acknowledgement on AM-3.5b-U-1 + AM-3.5b-U-2)

1. **GATE**: V acknowledges AM-3.5b-U-2 (recommend (b) calibration). AM-3.5b-U-1 disposition is informational (Path A unambiguous).
2. `macro_pipeline/access.py::_load_via_visibility_shift` Branch 1 (line 380-405): apply `to_visibility_index` + truncate + restore observation index, mirroring Branch 3:

   ```python
   # ---- Branch 1: Option Z (Layer 3.5b-U fix per Codex finding U + D29) ----
   if needs_vintage and pit_safe_by_construction:
       if lag > 0:
           # Apply the same visibility-shift discipline as Branch 3.
           # Pre-3.5b-U the truncation was s[s.index <= as_of] — leaking
           # current-month observations before publication. Codex finding
           # U + D29 closure applies the configured release_lag_days
           # (calibrated to 30 for SAHM's monthly first-of-month index
           # per the empirical 2025-06-15 anchor verification).
           shifted = to_visibility_index(s, lag)
           visible = shifted[shifted.index <= as_of]
           obs_idx = visible.index - pd.Timedelta(days=lag)
           out = pd.Series(visible.values, index=obs_idx, name=indicator_id)
       else:
           out = s[s.index <= as_of].copy()
           out.name = indicator_id
       # ... (rest of branch unchanged: notes, IndicatorBundle, etc.)
   ```

3. `macro_pipeline/config.py::FRED_SERIES_API["SAHMREALTIME"]`: `release_lag_days` 7 → 30; update `pit_construction_rationale` to mention the empirical lag application.
4. `macro_pipeline/utils/pit_audit.py`: extend the existing `pit_safe_by_construction` validator to require `pit_construction_rationale` to mention "release_lag" if `release_lag_days >= 1`.
5. Spot-check + update existing tests for SAHM `applied_release_lag_days=7 → 30` cascade (estimated 1-2 sites).
6. Write 6 new tests in `tests/test_option_z_release_lag.py` per spec §4.5.
7. Run full pytest + ruff + Gate 13 + Gate 16.
8. Smoke-test post-impl at 2025-06-15 + 2025-12-15 + 2026-04-15 confirming bug fix.
9. Author `LAYER_3_5b_U_VERIFICATION.md`.
10. Commit: `Layer 3.5b-U: Option Z release-lag empirical verification + fix (closes Codex finding U)`.
11. PAUSE for V/Strategic APPROVE before 3.5b-V pre-flight.

---

## §5 — Test plan preview (6 new = 3 NEG / 3 POS = 50% NEG)

| # | Test | Type | Asserts |
|---:|---|---|---|
| 1 | `test_sahm_option_z_applies_release_lag` | POS | At as_of=2025-06-15, `load_series('SAHMREALTIME', as_of=...)` returns latest visible obs at index ≤ 2025-05-31 (NOT June 2025). Path A canonical anchor. |
| 2 | `test_sahm_option_z_metadata_matches_behavior` | POS | Returned bundle has `applied_release_lag_days=30` AND the actual data window respects that lag (no observation with index > as_of - 30 days visible) |
| 3 | `test_option_z_branch_release_lag_consistency_validator` | NEG | Synthetic series with `pit_safe_by_construction=True` + `release_lag_days=10` + `pit_construction_rationale` lacking "release_lag" mention → pit_audit validator raises |
| 4 | `test_sahm_pit_at_2025_06_15_respects_lag` | POS | The canonical 2025-06-15 anchor: latest visible value is May 2025 SAHM (0.27), NOT June 2025 SAHM (0.17). Empirical look-ahead removed. |
| 5 | `test_option_z_construction_rationale_must_address_release_lag` | NEG | Spec §4.4 D-aligned: validator raises when rationale text doesn't mention release_lag handling for series with `release_lag_days > 0` |
| 6 | `test_load_sahm_with_inconsistent_release_lag_metadata_raises` | NEG | If config has `release_lag_days=30` but cache sidecar has `release_lag_days=7` (legacy), the access path raises (or the audit catches) — defends against config-cache drift |

NEG/POS = 3/3 = **50% NEG**, meets floor.

---

## §6 — Proof-contract mapping (7 items per spec §4.6)

| # | Spec proof | Plan |
|---:|---|---|
| 1 | Empirical SAHM index inspection documented in pre-flight | §2.1, §2.3, §2.4 above |
| 2 | Code path matches empirical finding (Path A or Path B) | Path A taken; visibility-shift inside Branch 1 |
| 3 | Test: at as_of=2025-06-15, SAHM latest observation respects appropriate lag | Test #4 (`test_sahm_pit_at_2025_06_15_respects_lag`) |
| 4 | Test: release_lag_days mismatch between metadata and applied behavior raises validation error | Test #6 (`test_load_sahm_with_inconsistent_release_lag_metadata_raises`) |
| 5 | Existing 560 tests still pass (post-3.5b-T baseline) | Full pytest |
| 6 | Cumulative test count = 566 | 560 + 6 |
| 7 | Conviction reported | §10 |

---

## §7 — Conviction (3-field, pre-flight)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | **0.94** | High: empirical exam unambiguous (Path A; value-change spacing 30-31 days proves monthly observations; first-business-day positions confirm observation-month indexing); look-ahead bias reproduced + measured at 2025-06-15 anchor (June 2025 obs visible 3 weeks before publication); calibration band derived empirically (14 ≤ lag ≤ 45). Slight haircut for "empirically determined value 33-37 vs spec literal 30" — choosing 30 leaves 17-day margin which is comfortable but not maximal. |
| `conviction_operational` | **0.88** | Medium-high: AM-3.5b-U-2 calibration is the binding ambiguity. If V approves recommended (b), implementation is straightforward; if V chooses (a) consistency-only, the fix is theatrical (lag=7 doesn't remove the leak). Existing test cascade (R-U-3) is small (1-2 sites estimated) but requires inline updates. **Binding** at 0.88 until V decides. |
| `conviction_actionability` | **0.93** | High: implementation pattern mirrors Branch 3 (lines 429-433) — proven safe; new tests are mechanical at known anchors; new Standing Order's grep-audit + invariant test satisfied by post-impl smoke. |
| **Aggregate** | **0.91** | Operational binding (AM-3.5b-U-2 disposition gate). |

---

## §8 — END

Pre-flight complete. **PAUSED** awaiting:

1. **AM-3.5b-U-2** disposition — recommend **(b) consistency + calibrate to 30**. If V approves: file **D29** for the calibration change. If V prefers (a) consistency-only: build agent will note "fix is theatrical at empirical lag=7" in verification, and Codex finding U closure becomes partial (Codex's specific concern was the leak; a fix that doesn't remove the leak warrants flagging).
2. (Informational) AM-3.5b-U-1 (Path A unambiguous), AM-3.5b-U-3 (test #1 expected behavior), AM-3.5b-U-4 (existing test cascade) — surfaced for explicit acknowledgement.

If V approves AM-3.5b-U-2=(b): proceed with §4 implementation order; expect ~2.5–2.8h coding + tests + verification.

If V prefers AM-3.5b-U-2=(a): re-author this pre-flight with `release_lag_days` unchanged at 7; verification will document the persistent look-ahead bias and propose D30 for follow-up.

Per Standing Orders pause-and-verify pattern: this is the gating PAUSE before §4 STEP 2 (access.py refactor).

---

**END — LAYER_3_5b_U_PREFLIGHT.md**
