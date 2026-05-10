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
| D28 | 2026-05-10 | 3.5b-T | Spec D4 transitional migration scaffold (DeprecationWarning + auto-recompute → enforce strictly) deferred; strict-only enforcement implemented (AM-3.5b-T-1=A) | ACCEPT | L3.5b spec §3.3-D4 prescribed a 3-state migration ladder for `data_sha256` mandatory enforcement: (1) emit DeprecationWarning on first read; (2) auto-recompute + write sidecar; (3) enforce strictly. Empirical state at 138/138 caches post-3.5E STEP 0 (CFTC + HLW sidecar fixup) makes scaffold dormant — every cache already carries `data_sha256`. Per V/Strategic-approved 4-rationale case (empirical 138/138 + bug repro; spec-literal-vs-intent precedent 3.5A AM4 / 3.5B AM10 / 3.5D AM21 / 3.5E D27; Codex finding T scope; YAGNI), implementation went straight to strict enforcement. Discrete migration sprint deferred to **L7-MIGRATE-1** if/when legacy cache state surfaces (e.g., future fresh deployment). Codex finding T closure verified empirically: pre-3.5b-T `load_series('PAYEMS')` with tampered sidecar returned a valid bundle (silent pass); post-3.5b-T raises `CacheValidationError`. Both `access.py:142` (direct `pd.read_parquet`) and `cache.py:378` (truthy-guard short-circuit) paths fixed. Grep audit (per new "Empirical claim verification" Standing Order): zero functional `pd.read_parquet` in `access.py` (sole match is docstring describing prior behavior); 5 loader-internal cache-fresh-check paths remain in `loaders/` but are out of Codex T scope (loader rebuild flows, not production scoring). | **L7-MIGRATE-1** (NEW) |
| D29 | 2026-05-10 | 3.5b-U | `release_lag_days` for SAHMREALTIME calibrated 7 → 30 + apply visibility-shift inside Option Z by-construction branch (AM-3.5b-U-2=(b)) | ACCEPT | L3.5b spec §4.3 Path A item 1 prescribed `release_lag_days=30 (or empirically determined value)`. Pre-flight empirical exam: SAHMREALTIME index is observation-month (value-change spacing 29-31 days; changes at first business day of month). Bug reproduction at canonical 2025-06-15 anchor: pre-fix `load_series('SAHMREALTIME', as_of=2025-06-15)` returned June 2025 SAHM (0.17, published ~2025-07-04) — **3-week look-ahead leak**. With prior config `release_lag_days=7` and visibility-shift applied, leak persists (latest visible 2025-06-13). Empirical band 14 ≤ lag ≤ 45 days; calibrated to 30 (spec literal + ~3-day safety margin matching actual SAHM publication on first Friday of M+1, ~30-37 days post observation-month index). Per V/Strategic-approved 5-rationale case (empirical bug repro; Codex finding U scope; empirical calibration; spec support; **Strategic self-correction** — 3.5B AM10 disposition was approved without empirical verification, the new "Empirical claim verification" Standing Order was added precisely because of this gap, and 3.5b-U is the first sub-phase to use the new Standing Order to CORRECT an earlier Strategic Claude approval — a healthy pattern). Implementation: (1) `config.SAHMREALTIME.release_lag_days` 7→30 + rationale extended; (2) `access._load_via_visibility_shift::Branch 1` now applies `to_visibility_index(s, lag)` mirroring Branch 3, with `pit_source = "by_construction_visibility_shift"` distinguishing from prior `"by_construction_latest"`; (3) `lag` now read from **live config first** (with cache-meta fallback), preventing config-vs-cache drift silently using stale sidecar values; (4) `pit_audit` validator extended to flag any Option Z series with `release_lag_days > 0` whose rationale lacks "release_lag" mention. Empirical post-fix at 2025-06-15: latest visible = May 2025 SAHM (0.27, published ~2025-06-06), June 2025 obs correctly excluded. Gate 13 anchors stable; Gate 10/Gate 13/Gate 16 still PASS. | none |
| D30 | 2026-05-10 | 3.5b-V | Comprehensive AP-6 narrowing sweep within Codex-flagged files (21 sites total) + `legitimate_missing_data_exceptions()` shared helper + side-fix to `get_pit_rstar` exception type (AM-3.5b-V-1=Comprehensive) | ACCEPT | L3.5b spec §5 D2 listed 4 sites (one per file). AST-walk audit per new "Empirical claim verification" Standing Order revealed each Codex-flagged file has 4-6 sibling broad-except blocks following the identical pattern: 5 in `cdrs_vulnerability.py` (V1-V5), 5 in `cdrs_trigger.py` (T1-T5), 6 in `kindleberger.py`, 4 in `dalio_cycle.py` — total 20 sibling sites + 1 D27 consolidation = **21 sites in scope**. Codex finding text "broader scoring/regime tree still has AP-6 style broad catches" supports comprehensive intent. Per V/Strategic-approved 6-rationale case (empirical AST-walk; Codex text; architectural consistency; precedent 3.5A AM4 / 3.5B AM10 / 3.5D AM21 / 3.5E D27 / 3.5b-T D28 / 3.5b-U D29; effort within budget; Strategic self-critique that spec D2 "4 sites" was authoring shortcut without AST-walk). All 21 sites use shared helper `legitimate_missing_data_exceptions()` returning `(HmmArtifactMissingError, HmmArtifactCorruptError, HmmMetadataIncompatibleError, PitDataUnavailableError)`. Helper PROPAGATES `PitContractViolationError`, `RegimeClassifierError`, `HmmConcurrencyError`, `CacheValidationError`, `IndicatorLoadError`, `KeyError`, `ValueError`, `FileNotFoundError`. **Side-fix** (regression remediation, in-scope architectural improvement): `loaders/hlw_rstar_vintage.py::get_pit_rstar` raised bare `ValueError("No HLW vintage available...")` for pre-2015Q4 PIT lookups — semantically a "PIT data missing" case but typed as generic ValueError. Changed to raise `PitDataUnavailableError` matching NBER extract's pre-1978 pattern. One existing test updated (`test_official_4d.py::test_pit_pre_2015_raises` ValueError → PitDataUnavailableError). **D27 consolidation contract expansion**: helper adds `PitDataUnavailableError` to D27's original 3-type tuple (informational; empirical impact = zero since `predict_state` doesn't raise this type); D27 empirical case (RegimeClassifierError for filelock-missing) preserved (verified by POS regression test #5). **16 out-of-scope broad-except sites** identified in AST-walk (loaders rebuild flows, validation framework, math fallbacks) tracked for L5-14 hygiene backlog. Gate 16 sub-criterion 4 updated to accept helper pattern OR original inline-tuple form (backward-compatible). | **L5-14** (NEW) |

---

## L5 backlog additions (deferrals from L3.5)

### L5-14 — Comprehensive AP-6 hygiene sweep across out-of-scope categories

**Status**: pending (deferred from 3.5b-V per D30 + V/Strategic
approval).
**Effort**: 3–5h.
**Triggered by**: D30 + 3.5b-V AST-walk audit identifying 16 broad
`except Exception:` blocks in loaders rebuild flows, validation
framework error reporting, and math fallbacks that are out of Codex
finding V scope but follow related anti-patterns.
**Priority**: Tier 3 (low / nice-to-have).

**Description**: 16 sites identified in `LAYER_3_5b_V_PREFLIGHT.md`
§2.1 out-of-scope table:
- math fallbacks (`analysis/newey_west_hac.py:77`, `analysis/r_squared_panel.py:167`) — 2 sites; legitimate numerical edge cases but could be narrowed to specific math types
- tmp-cleanup (`cache.py:50, 65`) — 2 sites; legitimate (rethrows original); narrow to expected I/O types if possible
- loader rebuild flows (`loaders/atlanta_wage.py:52`, `loaders/fred_vintage_panel.py:248`, `loaders/hlw_rstar.py:65`, `loaders/shiller.py:102`, `loaders/yahoo_loader.py:363, 474`) — 6 sites; idiomatic rebuild-on-failure pattern but could be narrowed to specific I/O / parse / network types
- validation gate framework error reporting (`validation.py:1310, 1330, 1518, 1736, 1763, 1853, 2277, 2376, 2450`) — 9 sites; framework-level (gates collect errors into findings); could be narrowed to specific gate-runtime types

Each category has different idioms; sweep would need per-category analysis.
Out of scope for L3.5b which targeted Codex finding V scoring/regime tree.
Right-sized for L4/L5 hygiene window when broader codebase reviews are
on the table.

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

## L7 backlog additions (deferrals from L3.5 + L3.5b)

### L7-MIGRATE-1 — Discrete migration sprint for legacy caches without `data_sha256`

**Status**: pending (deferred from 3.5b-T per D28).
**Effort**: 1–2h.
**Triggered by**: D28 (AM-3.5b-T-1=A — strict-only enforcement; transitional scaffold deferred).
**Priority**: Tier 4 (cold / contingent).
**Description**: If a future fresh deployment of the pipeline (e.g.,
new clone + first-time loader population in a clean environment)
surfaces legacy caches without `data_sha256`, run a discrete migration
sprint: walk `data/cache/`, read each parquet, compute sha256, rewrite
sidecar via `cache.atomic_write_bytes` with `data_sha256` populated.
Same one-shot pattern applied at 3.5E STEP 0 for the 5 stale CFTC + HLW
sidecars. After migration completes, `python -m macro_pipeline.utils.cache_audit`
should report 0 issues. Only triggered when legacy cache state is
empirically observed; not a forward-prevention task.

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
