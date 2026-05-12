# Layer 5 Spec v6 — Review Artifact Manifest

**Project**: macro-pipeline
**Repo**: github.com/mvfoundation01/macro-pipeline
**Branch under review**: claude/layer-5-spec
**HEAD**: 9f848bb  (tag `layer5-spec-v6`)
**Prior baseline**: 036a454  (tag `layer5-spec-v5`)
**Review mode**: CLOSURE VERIFICATION (post-surgical-scrub)

---

## Artifact URLs (fetch in order)

ChatGPT 5.5: please fetch each URL below via web browse and ingest
the raw text. All files are plain markdown or patch text; no auth
or JS rendering required.

| # | Artifact | Purpose | URL |
|---|----------|---------|-----|
| 1 | `layer5_spec_v6.md` | Primary review object | https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/reviews/layer5-v6/reviews/layer5-v6/artifacts/layer5_spec_v6.md |
| 2 | `layer5_spec_v5.md` | Comparison baseline | https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/reviews/layer5-v6/reviews/layer5-v6/artifacts/layer5_spec_v5.md |
| 3 | `chatgpt55_v5_verdict.md` | Your prior v5 verdict | https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/reviews/layer5-v6/reviews/layer5-v6/artifacts/chatgpt55_v5_verdict.md |
| 4 | `track_a_v6_readiness.md` | Execution evidence | https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/reviews/layer5-v6/reviews/layer5-v6/artifacts/track_a_v6_readiness.md |
| 5 | `sxx_register_l5.md` | Sxx state (9 entries; ACCEPT) | https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/reviews/layer5-v6/reviews/layer5-v6/artifacts/sxx_register_l5.md |
| 6 | `ap_register_v6.md` | AP register snapshot | https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/reviews/layer5-v6/reviews/layer5-v6/artifacts/ap_register_v6.md |
| 7 | `v5_to_v6.patch` | Git diff v5→v6 | https://raw.githubusercontent.com/mvfoundation01/macro-pipeline/reviews/layer5-v6/reviews/layer5-v6/artifacts/v5_to_v6.patch |

---

## v6 closure summary (paste-as-text; redundant với artifact 4)

**v5→v6 effort**: 1.05h
**Sxx filed v6**: 0  (3 consecutive zero-Sxx cycles: v4/v5/v6)
**v5 findings closed**:
- C.1 HIGH (RM-4 anchor 30/5→31/6 at 8 sites): closed via §2.1 pos+neg grep audit
- C.2 LOW/MED (cumulative arithmetic remnants): closed via §2.2 symbolic conversion + AP-AUTH-42 NEW

**Audit-instrument upgrades**:
- AP-AUTH-41 v6 STRENGTHENED: mirror integrity requires BOTH pos AND neg grep
- AP-AUTH-42 NEW: regex-based cumulative-arithmetic scrub
- §5.RM-4.8 NEW: 6-point anchor verification table

**Conviction**: 0.98 (binding: operational; stat 0.99 / op 0.98 / act 0.99)

---

## Artifact deviations (Track A self-disclosure)

| Item | Hint in prompt | Actual | Disposition |
|---|---|---|---|
| layer5_spec_v6.md size | 30-80 KB hint | 186 KB | Out of band; spec grew larger than prompt-author estimated. No action needed. |
| layer5_spec_v5.md size | 30-80 KB hint | 182 KB | Same as above. |
| chatgpt55_v5_verdict.md | Source: V's chat archive OR docs/reviews/ in repo | Neither source present. **RECONSTRUCTED** from in-repo evidence (`LAYER_5_V6_CHUNK_14_PREFLIGHT.md` §1 + chunk 14 verification §1 + spec §12 AP-AUTH-41 v6/AP-AUTH-42 NEW). | Artifact 3 file header carries explicit RECONSTRUCTION NOTICE; ChatGPT 5.5 should treat its own recollection of original v5 verdict as authoritative if discrepancies arise. |
| sxx_register_l5.md source | `docs/sxx_register.md` | No standalone register file in repo. Extracted from `LAYER_5_BUILD_SPEC.md` §10 + `LAYER_5_AUTHORING_SUMMARY.md` §4. | Content verbatim from canonical sources; equivalent. |
| ap_register_v6.md source | `docs/ap_register.md` | No standalone register file in repo. Extracted from `LAYER_5_BUILD_SPEC.md` §12 + `LAYER_5_V6_CHUNK_14_VERIFICATION.md` §7. AP-AUTH-1..38 base set lives in V's local `HANDOFF_CLAUDE_CODE_v4.md` (out-of-repo). | Content explicitly scoped to in-repo APs (AP-16..AP-21 + AP-AUTH-39..46); out-of-repo refs flagged in artifact §0 + §4. |
| v5_to_v6.patch size | 5-30 KB hint | 29 KB | Within hint band; no split needed. |

---

## Integrity hashes (sha256 short — first 12 chars)

| File | sha256 (first 12) |
|------|-------------------|
| layer5_spec_v6.md | 1ccb54a5c9d5 |
| layer5_spec_v5.md | 327944cccc19 |
| chatgpt55_v5_verdict.md | 16e69502fd66 |
| track_a_v6_readiness.md | 690a3fb068d1 |
| sxx_register_l5.md | b669eff7f8b6 |
| ap_register_v6.md | 6bc2855ecc3d |
| v5_to_v6.patch | 744b917465b6 |

---

**END — MANIFEST.md**
