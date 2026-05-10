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
