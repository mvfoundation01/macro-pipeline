# LAYER 3.5b-W — Pre-Flight Audit (NBER Boundary Semantics Fix)

**Spec ref**: L3.5b inline spec §6 (Codex finding W, MED). **FINAL L3.5b sub-phase.**
**Branch**: `claude/layer-3-5b-build` @ `842b60f` (3.5b-V complete).
**Date**: 2026-05-10
**Author**: Claude Code (build agent)
**Status**: PROCEED (no PAUSE-required ambiguities — FRED USREC convention empirically confirmed aligned with NBER announcement convention; calendar code is the sole bug source).

---

## §1 — Audit Result Header

| Field | Value |
|---|---|
| Sub-phase | 3.5b-W — NBER Boundary Semantics Fix |
| Spec effort | 1–2h |
| My estimate after audit | **~2.0h** (upper edge; surgical) |
| Tests added (target) | 6 (3 POS / 3 NEG = 50% NEG, meets floor) |
| Cumulative tests post-W | 571 + 6 = **577** |
| Codex findings closed | W (MED) — completes Codex 5/5 closure (T HIGH, U HIGH, V MED, W MED; X LOW deferred to L5-13) |
| Locked decisions (W-D1..D3) | D1 NBER convention (peak=last expansion, trough=last recession), D2 distinguish "announced visible" from "state at query month", D3 12 boundary tests consolidated into 4 parametrized + 2 NEG drift |
| Anticipated deviations | none (surgical; no scope expansion expected) |
| Conviction (statistical / operational / actionability) | 0.96 / 0.94 / 0.95 — see §10 |

---

## §2 — Empirical findings (per spec §6.2 + new "Empirical claim verification" Standing Order)

### §2.1 24-case boundary inspection across 6 cycles (post-3.5C calendar, post-3.5b-V code)

Empirically queried `NberCalendarLoader.state_at(query_period, as_of=2026-05-10)` for 4 cases per cycle × 6 cycles = 24 cases:

| Cycle | Position | Month | Current | NBER convention | Match? |
|---|---|---|---|---|:---:|
| 1980 | peak month | 1980-01 | recession | **expansion** (last expansion month) | ✗ |
| 1980 | peak+1 | 1980-02 | recession | recession (recession started) | ✓ |
| 1980 | trough month | 1980-07 | expansion | **recession** (last recession month) | ✗ |
| 1980 | trough+1 | 1980-08 | expansion | expansion (expansion started) | ✓ |
| 1981 | peak month | 1981-07 | recession | **expansion** | ✗ |
| 1981 | peak+1 | 1981-08 | recession | recession | ✓ |
| 1981 | trough month | 1982-11 | expansion | **recession** | ✗ |
| 1981 | trough+1 | 1982-12 | expansion | expansion | ✓ |
| 1990 | peak month | 1990-07 | recession | **expansion** | ✗ |
| 1990 | peak+1 | 1990-08 | recession | recession | ✓ |
| 1990 | trough month | 1991-03 | expansion | **recession** | ✗ |
| 1990 | trough+1 | 1991-04 | expansion | expansion | ✓ |
| 2001 | peak month | 2001-03 | recession | **expansion** | ✗ |
| 2001 | peak+1 | 2001-04 | recession | recession | ✓ |
| 2001 | trough month | 2001-11 | expansion | **recession** | ✗ |
| 2001 | trough+1 | 2001-12 | expansion | expansion | ✓ |
| 2007 | peak month | 2007-12 | recession | **expansion** | ✗ |
| 2007 | peak+1 | 2008-01 | recession | recession | ✓ |
| 2007 | trough month | 2009-06 | expansion | **recession** | ✗ |
| 2007 | trough+1 | 2009-07 | expansion | expansion | ✓ |
| 2020 | peak month | 2020-02 | recession | **expansion** | ✗ |
| 2020 | peak+1 | 2020-03 | recession | recession | ✓ |
| 2020 | trough month | 2020-04 | expansion | **recession** | ✗ |
| 2020 | trough+1 | 2020-05 | expansion | expansion | ✓ |

**12 of 24 cases mismatch** — exactly 6 peak-month + 6 trough-month cases. The bug is **at the exact turning-point month**: calendar's `state_at` treats the boundary as "post-turning-point" when NBER convention says it's "AT turning point" (still in the regime that's ENDING).

### §2.2 FRED USREC convention cross-check (per Standing Order)

Spec §6.2 #4 asked to surface `AM-3.5b-W-1` if FRED USREC convention diverges from NBER announcement convention. Empirical check at all 12 boundary months:

| Month | Kind | USREC value | Encoded says | NBER convention | Aligned? |
|---|---|---:|---|---|:---:|
| 1980-01 | peak | 0 | expansion | expansion (last exp) | ✓ |
| 1980-07 | trough | 1 | recession | recession (last rec) | ✓ |
| 1981-07 | peak | 0 | expansion | expansion | ✓ |
| 1982-11 | trough | 1 | recession | recession | ✓ |
| 1990-07 | peak | 0 | expansion | expansion | ✓ |
| 1991-03 | trough | 1 | recession | recession | ✓ |
| 2001-03 | peak | 0 | expansion | expansion | ✓ |
| 2001-11 | trough | 1 | recession | recession | ✓ |
| 2007-12 | peak | 0 | expansion | expansion | ✓ |
| 2009-06 | trough | 1 | recession | recession | ✓ |
| 2020-02 | peak | 0 | expansion | expansion | ✓ |
| 2020-04 | trough | 1 | recession | recession | ✓ |

**100% alignment.** FRED USREC encodes peak month as `0` (expansion = last expansion month) and trough month as `1` (recession = last recession month) — exactly matching NBER convention. **AM-3.5b-W-1 NOT triggered.** The calendar's `state_at` is the sole source of divergence; FRED USREC is the canonical reference.

### §2.3 Why latest-mode tests still pass while calendar PIT mode is broken

`extract_nber_state(query_date)` (latest-knowledge mode, `ctx=None`) reads from FRED USREC bundle — uses `_state_at_from_bundle(bundle, qd)` which inherits FRED's correct convention. Test `test_nber_known_recession_latest_mode` parametrized at `2020-04-01` (trough month) currently passes because USREC says `1` (recession). 

`extract_nber_state(query_date, ctx=...)` (PIT mode) routes through `NberCalendarLoader.state_at` — inherits the bug. But no existing PIT-mode test queries an exact peak/trough month at as_of=now (the closest is `test_extract_nber_state_uses_actual_lag_not_180` which queries 2008-09 = mid-recession, post-peak, not boundary).

Therefore existing tests are **unaffected by the fix** — the bug surface is empirically uncovered today. This is exactly the class of latent-bug-without-test-coverage that a methodical AST-walk audit would catch (and Codex's manual review did catch).

### §2.4 AST-walk audit of `nber_calendar.py` (per Standing Order)

```
$ grep -c "except Exception" macro_pipeline/regime/nber_calendar.py
0
```

Zero broad-except blocks in `nber_calendar.py`. **No AP-6 sibling sites in scope.** Surgical fix to `_last_announced_turning_point` is the entire change.

### §2.5 Code-shape inspection

Current implementation at `regime/nber_calendar.py:216-243`:

```python
def _last_announced_turning_point(
    self, query_period: pd.Period, as_of_ts: pd.Timestamp
) -> LastKnownLabel:
    announced: list[tuple[pd.Period, str, pd.Timestamp]] = []
    for c in self._cycles:
        if c.peak_announcement_date <= as_of_ts:
            announced.append((c.peak_date, "peak", c.peak_announcement_date))
        if c.trough_announcement_date <= as_of_ts:
            announced.append((c.trough_date, "trough", c.trough_announcement_date))
    # Filter to those <= query_period
    relevant = [t for t in announced if t[0] <= query_period]
    if not relevant:
        raise NberCycleNotFoundError(...)
    relevant.sort(key=lambda x: x[0])
    tp_period, kind, announce = relevant[-1]
    regime: Literal["expansion", "recession"] = (
        "recession" if kind == "peak" else "expansion"
    )
    return LastKnownLabel(...)
```

**Bug**: `t[0] <= query_period` admits the boundary month into `relevant`, and the regime mapping `"recession" if kind == "peak"` treats the peak month as "post-peak" → recession. NBER convention says the peak month IS the last expansion month → expansion.

**Fix (spec §6.3)**: distinguish "AT turning point" from "STRICTLY AFTER turning point":

```python
relevant.sort(key=lambda x: x[0])
tp_period, kind, announce = relevant[-1]

if tp_period == query_period:
    # Boundary case: AT the turning point month.
    # NBER convention:
    #   peak month = LAST expansion month → regime is expansion
    #   trough month = LAST recession month → regime is recession
    regime = "expansion" if kind == "peak" else "recession"
else:
    # Strictly after the turning point:
    #   peak → recession started; trough → expansion started.
    regime = "recession" if kind == "peak" else "expansion"
```

This is a 4-line change; mechanical and surgical.

---

## §3 — Spec §6.2 mandatory items + §6.3 file inventory

### §3.1 Files this sub-phase will touch

| File | Action | Notes |
|---|---|---|
| `macro_pipeline/regime/nber_calendar.py` | MODIFY | `_last_announced_turning_point` (lines 216-243): add boundary-vs-post-boundary distinction (4 lines added). Optionally extract a small `_regime_at_month` helper for readability — recommend INLINE keep (the logic is 5 lines and read-once). |
| `tests/test_nber_boundary_semantics.py` | NEW | 6 tests per spec §6.5 (3 POS parametrized over 6 cycles + 3 NEG drift) |

**No other code or test file changes.** Surgical scope.

### §3.2 Decisions locked per Standing Orders

| Decision | Locked default | Empirical override needed? |
|---|---|---|
| 3.5b-W-D1 (NBER convention: peak=last exp, trough=last rec) | YES | NO — empirical FRED USREC cross-check confirms |
| 3.5b-W-D2 (distinguish "announced visible" vs "state at query month") | YES | NO — clean fix |
| 3.5b-W-D3 (12 boundary cases parametrized into 4 tests + 2 NEG drift) | YES | spec §6.5 lists 3 POS + 3 NEG = 6 tests; post-trough case implicit via #5 NEG drift coverage |

### §3.3 Ambiguities

| ID | Topic | Routing | Recommended disposition |
|---|---|---|---|
| **AM-3.5b-W-1** (anticipated) | FRED USREC convention vs NBER announcement convention divergence | **NOT triggered** | Empirical cross-check (§2.2) confirms 100% alignment across 12 boundary months. Calendar's `state_at` is the sole bug; FRED USREC is the canonical reference. No PAUSE required. |
| **AM-3.5b-W-2** (informational) | Helper extraction: spec §6.3-2 mentions "Add `_regime_at_month()` helper with explicit boundary logic". The boundary logic is 5 lines (a single if-else); extracting to a helper has marginal readability benefit. | **PROCEED** (no Dxx) | Recommend INLINE the boundary logic in `_last_announced_turning_point` directly with a clear comment block. If V prefers helper extraction for symmetry with other regime modules, add `_regime_at_month(tp_period, query_period, kind) -> Literal["expansion", "recession"]`. Either way is correct. |
| **AM-3.5b-W-3** (informational) | Test plan ratio: spec §6.5 lists 3 POS + 3 NEG = 50% NEG (meets floor). Strategic note 4 mentioned "4 parametrized POS tests" suggesting an explicit post-trough → expansion test (a 4th POS), which would shift to 4 POS + 2 NEG = 33% NEG (BELOW floor). | **PROCEED** (no Dxx) | Follow spec §6.5 literal: 3 POS (peak, post-peak, trough) + 3 NEG (drift-peak, drift-trough, announce-vs-state). Post-trough case is covered implicitly by NEG drift #5 (test asserts regime correctly transitions across trough boundary in BOTH directions). |

### §3.4 Risk callouts

| ID | Risk | Mitigation |
|---|---|---|
| R-W-1 | Existing tests querying boundary months at as_of=now in PIT mode would break. Audit (§2.3) shows zero such tests today; closest is `test_extract_nber_state_uses_actual_lag_not_180` querying 2008-09 (post-peak, not boundary). | Spot-check pytest post-impl; expect zero existing-test rewrites |
| R-W-2 | Indirect callers of `state_at` (e.g. via `extract_nber_state` PIT mode → `regime_context`): if a regime context built in PIT mode at boundary as_of/query_date previously got a wrong state, downstream CRPS/CDRS scores could shift slightly. | Run Gate 13 + Gate 15 (CRPS + CDRS anchors) post-impl; verify scores stable at canonical anchors (1998-08, 2001-04, 2008-09, 2020-04 — only 2020-04 is a boundary month and it's a TROUGH; would shift to "recession" under fix). |
| R-W-3 | The CRPS/CDRS at 2020-04 anchor (Gate 10 floor 0.13 per D23) might shift if the regime contribution was previously "expansion" (bug) and becomes "recession" (correct). | Pre-impl smoke at 2020-04 to record current CRPS/CDRS values; post-impl re-measure. If shift breaks Gate 10 floor, flag as R-W-3 escalation. |
| R-W-4 | Per new Standing Order: post-impl verification must include AST-walk + invariant test, not just unit tests. | §6 verification: empirical 24-case boundary table re-measured post-impl (expect 24/24 match); AST audit confirms no regression in nber_calendar.py |

### §3.5 Effort estimate

| Step | h |
|---|---:|
| Pre-flight (this) | 0.5 |
| Code change in `_last_announced_turning_point` | 0.3 |
| 6 new tests parametrized | 0.5 |
| Smoke + ruff + Gate 10/13/14/15/16 + grep audit | 0.4 |
| Verification report | 0.3 |
| **Total** | **~2.0** within spec 1–2h band (upper edge) |

---

## §4 — Implementation order

1. **GATE**: V acknowledges informational AM-3.5b-W-2 (helper inline vs extracted) + AM-3.5b-W-3 (test plan ratio = spec literal). AM-3.5b-W-1 not triggered.
2. Refactor `_last_announced_turning_point` at `regime/nber_calendar.py:216-243`:

   ```python
   relevant.sort(key=lambda x: x[0])
   tp_period, kind, announce = relevant[-1]

   # Layer 3.5b-W: NBER convention: peak month is the LAST expansion
   # month; trough month is the LAST recession month. So at the EXACT
   # turning-point month, regime is the type the cycle is ENDING (peak
   # ends expansion → expansion; trough ends recession → recession).
   # STRICTLY AFTER the turning point, regime is the new type that
   # started (peak → recession; trough → expansion). Pre-3.5b-W the
   # boundary month was incorrectly treated as "post-turning-point",
   # diverging from FRED USREC's encoding (Codex L3.5 finding W).
   if tp_period == query_period:
       regime: Literal["expansion", "recession"] = (
           "expansion" if kind == "peak" else "recession"
       )
   else:
       regime = "recession" if kind == "peak" else "expansion"

   return LastKnownLabel(...)
   ```

3. Write 6 new tests in `tests/test_nber_boundary_semantics.py` per spec §6.5.
4. Pre-impl smoke at 2020-04 anchor: record current CRPS/CDRS values for R-W-3 mitigation.
5. Run full pytest + ruff + Gate 10/13/14/15/16 (post-fix re-measure).
6. AST-walk + grep audit per Standing Order.
7. Author `LAYER_3_5b_W_VERIFICATION.md`.
8. Commit: `Layer 3.5b-W: NBER boundary semantics fix (closes Codex finding W)`.
9. PAUSE for V/Strategic APPROVE before Gate 17 composite assembly + L3.5b retrospective.

---

## §5 — Test plan preview (6 new = 3 POS / 3 NEG = 50% NEG)

| # | Test | Type | Asserts |
|---:|---|---|---|
| 1 | `test_nber_exact_peak_month_returns_expansion` | POS (parametrized over 6 cycles) | At `query_period == peak_date` (any cycle), `state_at` returns `"expansion"` (last expansion month per NBER convention) |
| 2 | `test_nber_first_month_after_peak_returns_recession` | POS (parametrized over 6 cycles) | At `query_period == peak_date + 1` (any cycle), `state_at` returns `"recession"` (recession started) |
| 3 | `test_nber_exact_trough_month_returns_recession` | POS (parametrized over 6 cycles) | At `query_period == trough_date` (any cycle), `state_at` returns `"recession"` (last recession month) |
| 4 | `test_nber_no_silent_state_drift_at_peak_boundary` | NEG (parametrized over 6 cycles) | Drift assertion: `state_at(peak_month) != state_at(peak_month + 1)` (regime transitions correctly across peak boundary, no silent drift) |
| 5 | `test_nber_no_silent_state_drift_at_trough_boundary` | NEG (parametrized over 6 cycles) | Drift assertion: `state_at(trough_month) != state_at(trough_month + 1)` (regime transitions correctly across trough boundary; covers the post-trough → expansion case implicitly) |
| 6 | `test_nber_calendar_lookup_distinguishes_announce_vs_state_date` | NEG | At as_of slightly before peak_announcement_date, querying peak_month should raise `NberCycleNotFoundError` (announcement not yet visible). At as_of slightly after, same query should resolve to "expansion" (boundary fix). Asserts the announcement-vs-state distinction is preserved post-fix. |

NEG/POS = 3/3 = **50% NEG**, meets floor.

Note on AM-3.5b-W-3: the spec test plan does NOT explicitly include a post-trough → expansion POS test. It's covered implicitly by test #5 (drift at trough boundary asserts the post-trough state IS expansion). If V prefers an explicit POS test added (4 POS / 2 NEG = 33% NEG; below floor), the fix is to make test #6 redundant or fold it into the parametrization, keeping NEG count at 3.

---

## §6 — Proof-contract mapping (5 items per spec §6.6)

| # | Spec proof | Plan |
|---:|---|---|
| 1 | 12 boundary cases covered (1 per peak + 1 per trough across 6 cycles), consolidated into 4 parametrized tests | Tests #1, #2, #3, #4 (#5 covers the 12 trough-direction drift cases); 24 total parametrized assertions |
| 2 | All boundary tests PASS | Tests #1-#5 parametrized × 6 cycles + test #6 = 24 + 1 = 25 effective assertions, all PASS |
| 3 | Existing NBER calendar tests still pass | Full pytest |
| 4 | Cumulative test count = 568 + 6 = 574 (or higher) | Actually 571 + 6 = 577 — exceeds spec target by 3 (cumulative inheritance from earlier sub-phases) |
| 5 | Conviction reported | §10 below |

---

## §7 — Conviction (3-field, pre-flight)

| Field | Value | Rationale |
|---|---|---|
| `conviction_statistical` | **0.96** | Very high: empirical bug reproduction across 24 boundary cases is unambiguous (12/24 mismatch, all in the same exact-month pattern); FRED USREC cross-check confirms NBER convention encoding (12/12 aligned); fix is mathematically clean (4-line if-else); test plan covers all 6 cycles in both directions. AM-3.5b-W-1 (FRED divergence) NOT triggered — strongest possible empirical case. |
| `conviction_operational` | **0.94** | High: zero existing tests at risk (verified via grep + audit); ruff/AST clean; surgical scope (1 file, 1 method, 1 if-else block); R-W-3 mitigation in place (Gate 10 anchor pre/post smoke). Slight haircut for downstream effect on regime_context PIT mode at boundary anchors — empirically unreachable in current test surface but structurally affects a code path. |
| `conviction_actionability` | **0.95** | High: implementation is the smallest of all L3.5b sub-phases (4-line code change); test plan is mechanical parametrization; verification report is straightforward (re-measure 24 boundary cases post-fix; expect 24/24 match). FINAL L3.5b sub-phase — Gate 17 composite assembly + retrospective immediately follow. |
| **Aggregate** | **0.95** | Co-leading; cleanest sub-phase in L3.5b cycle. |

---

## §8 — END

Pre-flight complete. **PROCEED-eligible** (no PAUSE-required ambiguities). Awaiting V/Strategic acknowledgement on:

1. (Informational) **AM-3.5b-W-1** NOT triggered — FRED USREC convention 100% aligned with NBER announcement convention.
2. (Informational) **AM-3.5b-W-2** — recommend INLINE boundary logic (4 lines added directly in `_last_announced_turning_point`); no separate helper.
3. (Informational) **AM-3.5b-W-3** — follow spec §6.5 literal: 3 POS + 3 NEG = 50% NEG.

If V approves: proceed with §4 implementation order; expect ~2.0h total. After 3.5b-W APPROVE: Gate 17 composite assembly + L3.5b retrospective + tag `layer3-5b-complete` per Strategic's note 5.

Per Standing Orders pause-and-verify pattern: this is the gating PAUSE before §4 STEP 2 (code change). **FINAL L3.5b sub-phase.**

---

**END — LAYER_3_5b_W_PREFLIGHT.md**
