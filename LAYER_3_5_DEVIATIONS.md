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

## Format note

Future deviations should be appended below the last numeric entry.
Each row follows: ID | date (YYYY-MM-DD) | sub-phase | topic |
disposition (ACCEPT / REJECT / CONDITIONAL) | rationale (1–2
sentences) | L5 backlog ref (if any).
