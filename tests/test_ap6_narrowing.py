"""Layer 3.5b-V — broader AP-6 narrowing sweep tests.

Closes Codex 5.5 finding V (MED) — the scoring/regime metric tree had
20 sibling broad-except blocks across 4 files (V1-V5 vulnerability,
T1-T5 trigger, kindleberger metrics, dalio metrics) plus the D27 site
in regime_context.py:295. All 21 sites now use the shared helper
``macro_pipeline.exceptions.legitimate_missing_data_exceptions``.

Test plan per pre-flight §5: 4 NEG (one per Codex-flagged file) + 1
POS regression for D27 site = 80% NEG (well above 50% floor).

Each NEG test induces a non-helper exception (PitContractViolationError,
RegimeClassifierError, CacheValidationError) at one site and verifies
it propagates rather than being silently converted to a "component
missing" note. The POS regression test verifies that the D27 empirical
case (RegimeClassifierError for filelock-missing) still propagates
post-consolidation.
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from macro_pipeline.access import PitDataContext
from macro_pipeline.exceptions import (
    CacheValidationError,
    PitContractViolationError,
)
from macro_pipeline.regime.exceptions import RegimeClassifierError

_ANCHOR = pd.Timestamp("2008-09-15")


# ---------------------------------------------------------------------------
# 1. NEG — cdrs_vulnerability propagates PitContractViolationError
# ---------------------------------------------------------------------------
def test_cdrs_vulnerability_propagates_pit_violation() -> None:
    """A ``PitContractViolationError`` raised inside V1 (or any V*
    component) must propagate. Pre-3.5b-V the broad ``except Exception``
    converted it to ``V1 CAPE load error: PitContractViolationError:
    ...`` and the component returned ``None`` — Codex finding V."""
    from macro_pipeline.scoring import cdrs_vulnerability

    with patch.object(
        cdrs_vulnerability,
        "_pit_series",
        side_effect=PitContractViolationError(
            indicator_id="SHILLER_CAPE",
            reason="synthetic Codex-V test fixture",
        ),
    ), pytest.raises(PitContractViolationError):
        cdrs_vulnerability.v1_cape_percentile(PitDataContext(as_of=_ANCHOR))


# ---------------------------------------------------------------------------
# 2. NEG — cdrs_trigger propagates PitContractViolationError
# ---------------------------------------------------------------------------
def test_cdrs_trigger_propagates_pit_violation() -> None:
    """Same contract for T1 (representative of T1-T5)."""
    from macro_pipeline.scoring import cdrs_trigger

    with patch.object(
        cdrs_trigger,
        "_pit_series",
        side_effect=PitContractViolationError(
            indicator_id="BAMLH0A0HYM2",
            reason="synthetic Codex-V test fixture",
        ),
    ), pytest.raises(PitContractViolationError):
        cdrs_trigger.t1_hy_oas_30d_roc(PitDataContext(as_of=_ANCHOR))


# ---------------------------------------------------------------------------
# 3. NEG — kindleberger propagates RegimeClassifierError
# ---------------------------------------------------------------------------
def test_kindleberger_propagates_config_error() -> None:
    """A ``RegimeClassifierError`` raised inside any kindleberger
    metric (env / config issue, e.g. filelock-missing-style) must
    propagate. Pre-3.5b-V the broad ``except Exception`` converted it
    to a "component missing" note."""
    from macro_pipeline.regime import kindleberger

    with patch.object(
        kindleberger,
        "_pit_series",
        side_effect=RegimeClassifierError(
            component="kindleberger-test",
            reason="synthetic Codex-V test fixture",
        ),
    ), pytest.raises(RegimeClassifierError):
        kindleberger.classify_kindleberger(PitDataContext(as_of=_ANCHOR))


# ---------------------------------------------------------------------------
# 4. NEG — dalio_cycle propagates CacheValidationError
# ---------------------------------------------------------------------------
def test_dalio_cycle_propagates_cache_validation_error() -> None:
    """A ``CacheValidationError`` raised inside any dalio metric (cache
    integrity issue, e.g. tampered sidecar surfaced by 3.5b-T strict
    validation) must propagate."""
    from macro_pipeline.regime import dalio_cycle

    with patch.object(
        dalio_cycle,
        "_pit_series",
        side_effect=CacheValidationError(
            path="data/cache/fred_GFDEGDQ188S.parquet",
            reason="synthetic Codex-V test fixture",
        ),
    ), pytest.raises(CacheValidationError):
        dalio_cycle.classify_dalio(PitDataContext(as_of=_ANCHOR))


# ---------------------------------------------------------------------------
# 5. POS regression — D27 site still propagates RegimeClassifierError
# ---------------------------------------------------------------------------
def test_d27_site_still_propagates_regime_classifier_error_post_consolidation() -> None:
    """The 3.5E D27 empirical case (filelock-missing manifesting as
    ``RegimeClassifierError`` at ``regime_context.py:295``) must still
    propagate post-consolidation — verifies that swapping the inline
    narrow tuple for ``legitimate_missing_data_exceptions`` doesn't
    regress the contract Strategic Claude approved at 3.5E."""
    from macro_pipeline.regime import regime_context

    with patch.object(
        regime_context,
        "predict_state",
        side_effect=RegimeClassifierError(
            component="hmm",
            reason="synthetic D27-regression test fixture (filelock-missing analogue)",
        ),
    ), pytest.raises(RegimeClassifierError):
        regime_context.build_regime_context(PitDataContext(as_of=_ANCHOR))
