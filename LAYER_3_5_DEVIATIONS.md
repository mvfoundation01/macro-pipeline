# LAYER 3.5 — Deviation Register (D20+)

**Layer 3** closed at D19. **Layer 3.5** continues from D20.

This file is the canonical register for all 3.5-era deviations. Each
entry includes ID, date, sub-phase, topic, disposition, rationale, and
Layer 5 backlog reference (if any).

---

## Register

| ID | Date | Sub-phase | Topic | Disposition | Rationale | L5 backlog ref |
|---|---|---|---|---|---|---|
| D20 | — | (not filed) | (3.5A pickle regeneration would have triggered D20 if pickle had structurally diverged from master; regenerated pickle was byte-equal sha-match → no deviation needed) | n/a | n/a | n/a |
| D21 | 2026-05-09 | 3.5B | Config dataclass deferral — Option C+ chosen | ACCEPT | Spec §4.3-1 prescribes a `SeriesConfig` frozen dataclass for series config. Existing codebase uses dict-based pattern across 80+ FRED + 22 TV CSV + others. Full migration is 6–8h scope creep beyond L3.5B's 3–5h budget. **Option C+** taken: extend dict pattern with three new keys (`pit_safe_by_construction`, `pit_construction_rationale`, `derived_confidence_cap`); add standalone `_validate_pit_construction_consistency()` helper running at config import. Achieves spec intent (mandatory rationale + cap range validation per 3.5B-D3) without dataclass churn. Mirrors precedent of L1.5C extension keys (`signal_type`, `valid_uses`, `INVALID_uses`). | **L5-12 NEW** |
| D22 | 2026-05-09 | 3.5C | Existing NBER PIT tests rewritten for calendar-based contract | ACCEPT | The Layer 3A `test_nber_pit_raises_when_label_unannounced` test (and the analogous boundary check inside `validate_gate8_regime`) asserted the 180-day approximation behavior: at as_of=2008-12-01 querying 2008-09 must raise `PitDataUnavailableError`. Post-3.5C the calendar resolves the 2007-12 peak (announced 2008-12-01) → state="recession" cleanly; no raise. Tests rewritten to exercise the new contract: at as_of=2008-11-30 (one day before peak announcement) querying 2008-09 returns "expansion" (most recent visible turning point = 2001-11 trough). Latest mode would have returned "recession" — the divergence demonstrates calendar-aware PIT discipline. Same semantic update applied to `test_regime_context_partial_at_2008_09` (no-longer-None NBER) and Gate 8's PIT no-ffill check. | none |
| D23 | 2026-05-09 | 3.5C | CDRS 2020-02 anchor recalibrated; HMM-dissent path unreachable in real-time mode for post-1978 dates | ACCEPT | Pre-3.5C the 180-day NBER approximation made the 2020-02 anchor PIT-raise → fall through to `derive_regime_state` Path 4 (HMM-corroboration check) → HMM dissents from Kindleberger → "late-cycle" with R=0.95 neutralization → CDRS ≈ 0.21. Post-3.5C the calendar correctly resolves NBER as "expansion" at 2020-02-20 (most recent visible turning point = 2009-06 trough, announced 2010-09-20; 2020-02 peak not announced until 2020-06-08). `derive_regime_state` takes Path 3 (NBER expansion authoritative, Kindleberger non-stress) → R=0.6 → CDRS ≈ 0.13. **Updates**: (1) `test_cdrs_2020_02_event_floor` floor 0.15 → 0.13; (2) `test_cdrs_2020_02_regime_neutralized_path` repurposed to `test_cdrs_2020_02_nber_takes_priority_over_hmm_dissent` asserting the new contract; (3) Gate 10 floor 0.15 → 0.13 with rationale. The HMM-dissent-neutralization path is now structurally unreachable in real-time mode for any post-1978 date because the NBER calendar always provides an authoritative answer. **Layer 3.5D will introduce `RegimeState.INDETERMINATE`** as the new home for the dissent semantics. | L5-6 (V/T weight refit) may restore higher event scores; tracked. |
| D24 | 2026-05-09 | 3.5D | INDETERMINATE R-multiplier policy = consensus-driven (AM21=B); existing dissent-derivation tests rewritten | ACCEPT | Spec §6.4-D2 default was `R=1.0` for INDETERMINATE. Empirical pre-flight smoke-test (15 anchors) showed HMM v1 dissents at 10/15 anchors (UMCSENT-driven late-cycle bias post-2008), inflating Gate 10 calm-anchor CDRS scores under R=1.0 (predicted differential 3.62× → 2.18×, breaking 3.0× floor). Per Standing Orders ambiguity routing ("Empirical finding contradicts spec assumption" → PAUSE), V/Strategic resolved as **AM21=B** — Spec §6.4-D2 alternative #3 ("R from consensus state"). Implementation: `_resolve_r_multiplier` takes `regime_ctx=` and, when `state == "indeterminate"`, returns `REGIME_MULTIPLIER[consensus]` where consensus is computed from NBER+Kindleberger via `_consensus_state_for_indeterminate`. The 0.60 confidence cap is applied separately at score-aggregation level (orthogonalized from R). Existing tests rewritten because spec-default behavior was assumed: `test_regime_state_2025_06_nber_expansion` → `test_regime_state_2025_06_indeterminate_on_hmm_dissent` (now asserts INDETERMINATE); `test_regime_state_neutralization_when_nber_pit_raised` → `test_regime_state_indeterminate_on_dissent_when_nber_unavailable` (asserts the path where Phase A produces consensus = HMM-solo and Phase B trivially matches; the old "neutralization" semantic is replaced by INDETERMINATE on cross-component dissent paths); `test_regime_state_kindleberger_override` parameter set adjusted so HMM matches consensus to isolate override logic; new test `test_regime_state_hmm_dissent_indeterminate_on_kindleberger_override` covers the override + dissent → INDETERMINATE path; CRPS anchor tests at 2025-06 + 2008-09 add `"indeterminate"` to allowed regime_state set. Gate 10 differential measured 6.05× empirically post-impl (preserves Gate 10 calibration; spec narrative refinement: pre-3.5D 2025-06 was via Path 3 not Path 4b). | L5-6 (V/T weight refit) remains escape hatch for AM21 if calibration shifts later. |
| D25 | 2026-05-10 | 3.5E | HLW vintage atomic-write granularity = single concatenated write (AM26) | ACCEPT | Spec §7.3-3 + §7.4-D2 assume per-vintage atomic writes ("atomic per-vintage to minimize blast radius if mid-loop failure"). Empirical reading of `loaders/hlw_rstar_vintage.py:build_cache` shows actual code does ONE concatenated `long.to_parquet(parquet)` after building MultiIndex(vintage, date) — no per-vintage parquets are written. The "per-vintage atomic" decision is structurally inapplicable. Disposition: route the single concatenated write through `cache.write_cache_atomic`. Atomic semantics: full-vintage-set commit OR rollback (not partial). Spec intent (atomic-write-discipline) preserved; spec literal (per-vintage loop) deviated. Standard 3.5A AM4 / 3.5B AM10 / 3.5D AM21 spec-literal-vs-intent precedent. Test #7 rephrased from `test_hlw_atomic_write_per_vintage` to `test_hlw_atomic_write_concatenated_or_rollback` covering the single-write rollback contract. | none |
| D26 | 2026-05-10 | 3.5E | Extracted `_write_atomic_subdir` from `analysis/r_squared_panel.py` to public `cache.write_cache_atomic_subdir` (AM28) | ACCEPT | Spec §7.3-1 introduced `read_cache_validated_subdir` as a new public helper. Symmetric `write_cache_atomic_subdir` was implicit in spec but not explicit. The previous private `_write_atomic_subdir` in `r_squared_panel.py` mirrored the parquet-+-sidecar atomic-write contract; making the read public while leaving the write private is asymmetric. Disposition: extract to `cache.py` as `write_cache_atomic_subdir(subdir, filename, df, meta, *, cache_root=None)`; rewire `r_squared_panel.write_panel_atomic` as a thin wrapper. Behaviour preserved (same target path, same sidecar fields); `pipeline_processed=True` migrated into the meta dict passed to the helper. | none |
| D27 | 2026-05-10 | 3.5E | AP-6 swallow at `regime_context.py:295` exposed env-hygiene gap (filelock declared in `pyproject.toml`/`uv.lock` but missing from master `.venv`); reframed from initial "Gate 15 anchor refactor due to FRED data revision" hypothesis | ACCEPT | Strategic Claude REVISE-WITH-NOTES on 3.5E pre-flight prescribed Option C HYBRID: diagnose Gate 15 drift root cause first; refactor anchor IFF FRED data revision confirmed. Build agent's STEP 0 diagnosis (1.0h) falsified the FRED-revision hypothesis with hard evidence: (1) HMM pickle sha256 matches sidecar `data_sha256=aa813d16...` exactly (3.5A frozen contract intact); (2) `predict_state` at as_of=2025-06-01 returns `recession` with posterior 1.000 — matches 3.5D verification baseline. Root cause: the broad `except Exception:` at `regime/regime_context.py:295` (AP-6) silently swallowed a `RegimeClassifierError("filelock not installed")` raised when `python -m macro_pipeline.validation` ran without `.local-deps` on `sys.path` (`tests/conftest.py:38-42` auto-prepends `.local-deps` for pytest, but the validation CLI doesn't). Surgical fix (two layers): (1) `pip install "filelock>=3.13"` into master `D:/macro_pipeline/.venv` aligns the env with the declared dep; (2) `regime_context.py:295` narrowed to `(HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError)` per refined §12.4 sub-option (a) — `HmmConcurrencyError` and `RegimeClassifierError` now propagate, so env/config issues fail loudly rather than silently swallow into wrong-state ('expansion' instead of 'indeterminate'). NEG test #9 (`test_narrow_exception_in_regime_context_propagates_unexpected`) asserts both `MemoryError` and `RegimeClassifierError` propagate correctly. **NO Gate 15 anchor refactor needed** — the 2025-06 anchor is empirically revision-stable. | **L7-CI-1** (NEW) |

---

## L5 backlog additions (deferrals from L3.5)

### L5-12 — Full `SeriesConfig` dataclass migration

**Status**: pending (deferred from 3.5B per D21).
**Effort**: 6–8h.
**Triggered by**: D21.
**Priority**: Tier 3 (low / nice-to-have).
**Description**: Migrate the 80+ FRED + 22 TV CSV + other series-level
configurations from dict-based literal pattern to a frozen dataclass
(`SeriesConfig`) with `__post_init__` validation. The current Option C+
disposition keeps the validator at module level for the only flagged
member (SAHMREALTIME); the dataclass migration would centralise all
type validation including unit/frequency/release_lag enums and
expected_min/max sanity bounds. Touches `config.py`, every loader that
reads `FRED_SERIES_API` (or analogous TV / Yahoo registries), and
existing tests that read the dict.

---

## L7 backlog additions (deferrals from L3.5)

### L7-CI-1 — CI-level env-hygiene check (declared deps == installed)

**Status**: pending (deferred from 3.5E per D27).
**Effort**: 1–2h.
**Triggered by**: D27.
**Priority**: Tier 2 (medium / hardening).
**Description**: Add a CI-level (and/or `make check-env`) assertion that
every dependency declared in `pyproject.toml`'s `[project] dependencies`
is actually installed in the active venv. Forward-prevent gaps like the
filelock case surfaced at 3.5E STEP 0 (`filelock>=3.13` was declared
and resolved in `uv.lock` but never installed in `D:/macro_pipeline/.venv`,
silently leaving validation CLI invocations using the broken AP-6 path).
Implementation sketch: `python -m pip check` or a small script that
parses `pyproject.toml` deps and `pip list --format=json`, exits non-zero
on missing packages. Wire into the existing GitHub Actions CI workflow
introduced at L1.5D so PRs fail closed on declared-but-not-installed
dependency gaps. Out of L3.5E scope (cache-atomicity sweep is the focus);
the surgical filelock install at STEP 0 closes the immediate gap.

---

## Format note

Future deviations should be appended below the last numeric entry.
Each row follows: ID | date (YYYY-MM-DD) | sub-phase | topic |
disposition (ACCEPT / REJECT / CONDITIONAL) | rationale (1–2
sentences) | L5 backlog ref (if any).
