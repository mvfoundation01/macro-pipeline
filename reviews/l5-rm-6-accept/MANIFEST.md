# L5-RM-6 ACCEPT — Review Artifact Manifest

**Project**: macro-pipeline
**Build branch**: `claude/layer-5-build` @ `ba0ff1e` (tag `l5-rm-6-accept`)
**Review branch (this)**: `reviews/l5-rm-6-accept`
**Predecessor (FROZEN)**: `claude/layer-5-spec` @ `9f848bb` tag `layer5-spec-v6`
**Foundation tags**: `l5-a-accept` / `l3-component-patch` / `l5-b-task-a-accept` / `l5-rm-4-accept`

---

## Artifact URLs (raw)

| # | Artifact | Purpose | URL |
|---|----------|---------|-----|
| 1 | `L5_RM_6_VERIFICATION.md` | Self-verification report (§§1-8) | https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/reviews/l5-rm-6-accept/reviews/l5-rm-6-accept/artifacts/L5_RM_6_VERIFICATION.md |
| 2 | `test_transcript.txt` | pytest -v output (14 RM-6 tests PASS) | https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/reviews/l5-rm-6-accept/reviews/l5-rm-6-accept/artifacts/test_transcript.txt |
| 3 | `gate21_cli.txt` | Gate 21 CLI PASS | https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/reviews/l5-rm-6-accept/reviews/l5-rm-6-accept/artifacts/gate21_cli.txt |

Source code (build branch):
- `macro_pipeline/models/isotonic_calibrator.py` (NEW; ~600 LOC): https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/claude/layer-5-build/macro_pipeline/models/isotonic_calibrator.py
- `tests/test_isotonic_calibrator.py` (NEW; 14 tests): https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/claude/layer-5-build/tests/test_isotonic_calibrator.py
- `macro_pipeline/validation.py` (modified: Gate 21 + CLI): https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/claude/layer-5-build/macro_pipeline/validation.py
- `docs/build-plans/L5B_BACKLOG.md` (L5b-6 added): https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/claude/layer-5-build/docs/build-plans/L5B_BACKLOG.md

---

## L5-RM-6 summary

**Greenfield implementation** (no existing isotonic in codebase).

**25 calibrators per refit window** per §3.3 schema: 1 CRPS + 20 CDRS + 4 RETURN_POSITIVE.

**Public API**: `fit_isotonic_calibrators`, `build_event_labels` (HARD GATE per S-8), `should_recalibrate` (quarterly always fires; 90d cooldown debounces triggers per Track A interp of §5.RM-6.1.4), `calibrate_raw_score` (bands placeholder until L5-E).

**Tests**: +14 logical / +14 pytest (7 NEG / 7 POS = 50% NEG floor).

**Sxx**: 0 new (PATCH-IMPL decisions per AP-AUTH-52 doc-residue class; L5b-7 backlog candidate noted for L5-H retrospective).

**Pytest baseline**: 643 → **657** (0 regressions; +14 per spec §5.RM-6.5).

**Effort actual**: ~3.5h vs 6.6h std / 8h risk-adj budget (~53% of standard; matches Track A trend).

**Gate 21 CLI**: PASS (criteria 1+2 runtime; 3-9 deferred to pytest per spec).

**Conviction**: stat 0.96 / op 0.93 / act 0.95 ; aggregate 0.93 ; binding operational. ≥0.90 floor cleared.

**Verdict**: ACCEPT.

**Next**: L5-B Task B1 pre-flight (Ridge return forecast; consumes post-RM-6 CRPS + CDRS calibrated panels per S-9).

---

## Integrity hashes (sha256 first 12 chars; AP-AUTH-48 v2 — post-push verified below)

| File | sha256 (first 12) — **served from raw URL** (AP-AUTH-48 v2) |
|------|---|
| L5_RM_6_VERIFICATION.md | 30b9981154a1 |
| test_transcript.txt | <pending post-push curl> |
| gate21_cli.txt | <pending post-push curl> |

**AP-AUTH-48 v2 post-push protocol** (3rd formal application; pattern expected per L5-B Task A + L5-RM-4 precedents):
1. Commit MANIFEST with on-disk hashes
2. Push
3. `curl -sL <each-url> | sha256sum` per artifact
4. If drift detected (CRLF→LF on shell-redirected text) → amend MANIFEST with served hash + re-push

---

**END — MANIFEST.md (initial local hashes; post-push verification in follow-up commit)**
