# Sxx Register — Layer 5 spec authoring cycle (v1 → v6)

**Project**: macro-pipeline
**Branch**: `claude/layer-5-spec` (HEAD `9f848bb` tag `layer5-spec-v6`)
**Snapshot date**: 2026-05-12
**Predecessor register**: L3.5 + L3.5b closed at D30. L5 uses `Sxx` prefix to distinguish from L3.5-era `Dxx`.
**Reserved range**: S-1 through S-25.
**Cumulative count v6**: **9 (S-1..S-9; all ACCEPT)**.
**Delta v3 → v4 → v5 → v6**: 0 / 0 / 0 (three consecutive zero-delta cycles → convergence).

Source-of-truth: `LAYER_5_BUILD_SPEC.md` §10 (canonical body) + `LAYER_5_AUTHORING_SUMMARY.md` §4 (paste-ready table). This file extracts that content into a standalone artifact for review.

---

## §1 — Register table

| ID | Date | Sub-phase / chunk | Topic | Disposition | Backlog ref |
|---|---|---|---|---|---|
| S-1 | 2026-05-10 | chunk 3 (v1) / §3.2 + §5.RM-4 | ScoredObservation new-slot list reconciliation across chunks | ACCEPT | none |
| S-2 | 2026-05-11 | chunk 6 (v2) / §3.3 + §3.2 + §5.RM-4 + §5.RM-6 + §5.C + §2.5 audits #5/#6 | Calibration target schema added; ScoredObservation slot count 5 → 6 (added `positive_return_probability`); closes ChatGPT 5.5 v1 E.1 / L5-RISK-1 | ACCEPT | none |
| S-3 | 2026-05-11 | chunk 7 (v2) / §5.B + §1.1 + §4 + §2.5 audit #7 | L5-B split into Task A (composite-weight refit on component matrix via penalized logistic) + Task B (return-forecast Ridge on post-RM-6 calibrated probabilities); closes ChatGPT 5.5 v1 E.2 / L5-RISK-2 | ACCEPT | none |
| S-4 | 2026-05-11 | chunk 8 (v2) / §5.G.1 + §5.G.3 + §5.G.5 + §5.G.6 + §2.5 audit #9 | Bayesian k_h backsolved from W_REF_TARGET × N_REF_NONOVERLAP; closes ChatGPT 5.5 v1 E.3 / L5-RISK-3 (HIGH) | ACCEPT | none |
| S-5 | 2026-05-11 | chunk 9 (v2) / §5.D.1.1 + §5.D.1.3 + §5.D.5 + §5.D.6 + §2.5 audit #8 | Drawdown sparse cell intervals + hierarchical pooling replace nan-cliff at n<5; closes ChatGPT 5.5 v1 E.4 / L5-RISK-4 (MED) | ACCEPT | none |
| S-6 | 2026-05-11 | chunk 9 (v2) / §5.B.1.4 + §5.E.1 + §5.E.3 + §5.E.5 + §2.5 audit #10 | Block bootstrap block-size + HAC bandwidth sensitivity + joint bootstrap forecast σ + empirical coverage; closes ChatGPT 5.5 v1 E.5 + E.7 / L5-RISK-5 (MED) | ACCEPT | none |
| S-7 | 2026-05-11 | chunk 9 (v2) / §5.RM-6.1.4 + §5.RM-6.5 + §5.B Task B B8/B9 | Trigger cooldown 90d + coalescing + λ/calibrator stability diagnostics; closes ChatGPT 5.5 v1 E.6 / L5-RISK-6 + L5-RISK-7 (MED) | ACCEPT | none |
| S-8 | 2026-05-11 | chunk 11 (v3) / §5.RM-6.1.1 + §5.RM-6.1.2 + §5.RM-6.5 + §5.RM-6.6 + §5.RM-6.7 + §3.2 + §3.3 | RM-6 calibration label semantics aligned with §3.3 schema; `fit_isotonic_per_horizon` → `fit_isotonic_calibrators` (25 calibrators: 1 CRPS + 20 CDRS + 4 RETURN_POSITIVE); `build_event_labels()` NEW dispatcher; test #11 hardened HARD GATE; closes ChatGPT 5.5 v2 E.1 PARTIALLY-CLOSED → CLOSED | ACCEPT | none |
| S-9 | 2026-05-11 | chunk 11 (v3) / §5.B.1.0 + §5.B.1.1 + §5.B.5 + §3.1 dependency graph | L5-B Task B split into Task B1 (Ridge return forecast; RETURN_POSITIVE NOT input) + Task B2 (RETURN_POSITIVE calibration via RM-6 isotonic); closes ChatGPT 5.5 v2 D.2 RETURN_POSITIVE circularity | ACCEPT | none |

Reserved: S-10 through S-25 (L5 build deviations to be filed at build-time).

---

## §2 — Sxx rationale summary

Per `LAYER_5_BUILD_SPEC.md` §10, each Sxx entry has:
- **Rationale** (full mechanism statement; not truncated in this summary — see §10 of spec for verbatim multi-paragraph rationales)
- **Disposition** (ACCEPT / REJECT / DEFER; all current entries ACCEPT)
- **Backlog ref** (link to backlog entry if deferred work; all current entries "none")

Verbatim rationales preserved in spec §10 at lines 2375-2387.

---

## §3 — Sxx cycle attribution

| Cycle | Sxx filed | Cumulative | Driver |
|---|---|---|---|
| v1 (chunks 1-5) | S-1 (1) | 1 | Spec-internal reconciliation (chunk 1 vs chunk 3 slot list) |
| v2 (chunks 6-10) | S-2..S-7 (6) | 7 | Closes ChatGPT 5.5 v1 review E.1..E.7 (3 HIGH + 4 MED) |
| v3 (chunk 11) | S-8, S-9 (2) | 9 | Closes ChatGPT 5.5 v2 partial E.1 + D.2 RETURN_POSITIVE circularity |
| v4 (chunk 12) | 0 | 9 | Cross-reference scrub (gate sync, prose mirror); no methodology decisions |
| v5 (chunk 13) | 0 | 9 | Slot count + cumulative arithmetic scrub; no methodology decisions |
| v6 (chunk 14) | 0 | 9 | RM-4 negative-grep scrub + AP-AUTH-41/42 codification; no methodology decisions |

Convergence pattern: v4 / v5 / v6 = 3 consecutive zero-Sxx cycles. v6 expected to be terminal authoring cycle (FREEZE-AS-IS-V6 prior ~90% per chunk 14 preflight §5).

---

## §4 — All-ACCEPT note

All 9 Sxx entries dispositioned ACCEPT. No REJECT. No DEFER. No V override required.

S-1 through S-7 ACCEPT preserved through 4 ChatGPT 5.5 review rounds (v1→v2→v3→v4→v5→v6). S-8 + S-9 ACCEPT preserved through 3 rounds (v3→v4→v5→v6). Stability of ACCEPT dispositions over multiple review cycles is the primary evidence of methodology convergence.

---

**END — sxx_register_l5.md (snapshot at `9f848bb` tag `layer5-spec-v6`)**
