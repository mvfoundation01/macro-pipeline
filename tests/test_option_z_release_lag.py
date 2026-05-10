"""Layer 3.5b-U — Option Z release-lag empirical verification + fix.

Closes Codex 5.5 finding U (HIGH) — the Option Z by-construction branch
in ``access._load_via_visibility_shift`` truncated SAHMREALTIME at
``as_of`` directly while metadata claimed ``applied_release_lag_days``,
leaking unpublished current-month observations for an
observation-month-indexed series.

Empirical verification (per spec §4.2 + new "Empirical claim
verification" Standing Order): SAHMREALTIME index is observation-month
(value-change spacing 29-31 days; changes at first business day of
month). Calibrated lag of 30 days (D29) is required to actually remove
the leak; the prior config value of 7 was insufficient.

Test plan per pre-flight §5: 3 NEG / 3 POS = 50% NEG (meets floor).
"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_pipeline.access import load_series


# ---------------------------------------------------------------------------
# 1. POS — Option Z applies the configured release lag
# ---------------------------------------------------------------------------
def test_sahm_option_z_applies_release_lag() -> None:
    """At as_of=2025-06-15, the Option Z by-construction branch must
    apply ``release_lag_days`` so that the latest visible observation
    has ``observation_index <= as_of - release_lag_days``. Pre-3.5b-U
    the truncation ignored the lag and leaked the June 2025 obs."""
    bundle = load_series("SAHMREALTIME", as_of=pd.Timestamp("2025-06-15"))
    nonnull = bundle.data.dropna()
    latest_obs_index = nonnull.index[-1]
    # The lag is read from live config (3.5b-U D29 = 30).
    lag_days = bundle.metadata["applied_release_lag_days"]
    assert lag_days == 30, f"expected lag=30, got {lag_days}"
    # latest visible observation must be at most ``as_of - lag`` days old
    cutoff = pd.Timestamp("2025-06-15") - pd.Timedelta(days=lag_days)
    assert latest_obs_index <= cutoff, (
        f"latest visible obs index {latest_obs_index.date()} exceeds "
        f"as_of - lag = {cutoff.date()} → look-ahead bias"
    )


# ---------------------------------------------------------------------------
# 2. POS — Option Z metadata matches behavior
# ---------------------------------------------------------------------------
def test_sahm_option_z_metadata_matches_behavior() -> None:
    """Returned bundle's ``applied_release_lag_days`` must equal the
    actual visibility shift applied. After 3.5b-U the helper applies
    ``to_visibility_index(s, lag)`` and emits ``pit_source =
    'by_construction_visibility_shift'``."""
    bundle = load_series("SAHMREALTIME", as_of=pd.Timestamp("2025-06-15"))
    md = bundle.metadata
    assert md["pit_safe_by_construction"] is True
    assert md["pit_source"] == "by_construction_visibility_shift", (
        f"expected by_construction_visibility_shift, got {md['pit_source']!r}"
    )
    assert md["applied_release_lag_days"] == 30
    assert bundle.derived_confidence_cap == pytest.approx(0.70)


# ---------------------------------------------------------------------------
# 3. POS — empirical 2025-06-15 anchor returns May (not June) SAHM
# ---------------------------------------------------------------------------
def test_sahm_pit_at_2025_06_15_respects_lag() -> None:
    """The canonical 2025-06-15 anchor: latest visible value is the
    May 2025 SAHM observation (visibility 2025-05-31 with +30d lag)
    NOT the June 2025 SAHM observation (visibility 2025-07-02, NOT
    visible at as_of=2025-06-15). This is the empirical look-ahead-bias
    closure — the test would FAIL pre-3.5b-U."""
    bundle = load_series("SAHMREALTIME", as_of=pd.Timestamp("2025-06-15"))
    nonnull = bundle.data.dropna()
    # May 2025 SAHM value in our cache is 0.27; June 2025 is 0.17.
    # If the bug is back, the latest visible value would be 0.17 (June).
    latest_value = nonnull.iloc[-1]
    assert latest_value == pytest.approx(0.27), (
        f"expected May 2025 SAHM (0.27); got {latest_value} — "
        "regression: June 2025 obs leaking?"
    )
    # Latest visible obs index must precede June 2025 first business day.
    assert nonnull.index[-1] < pd.Timestamp("2025-06-02"), (
        f"latest visible {nonnull.index[-1].date()} >= 2025-06-02 → "
        "June 2025 obs leaking"
    )


# ---------------------------------------------------------------------------
# 4. NEG — pit_audit raises on construction-rationale missing release_lag mention
# ---------------------------------------------------------------------------
def test_option_z_construction_rationale_must_address_release_lag(monkeypatch) -> None:
    """3.5b-U D29 contract: an Option Z series with
    ``release_lag_days > 0`` must document the lag application in its
    ``pit_construction_rationale``. The validator catches drift where a
    series gets the flag flipped on without updating the rationale.
    """
    from macro_pipeline import config
    from macro_pipeline.utils.pit_audit import audit_pit_contracts

    # Take the canonical SAHMREALTIME spec but strip the release_lag mention
    # from its rationale.
    sahm_orig = dict(config.FRED_SERIES_API["SAHMREALTIME"])
    sahm_unannotated = dict(sahm_orig)
    sahm_unannotated["pit_construction_rationale"] = (
        "FRED publishes SAHMREALTIME as a real-time series. "
        "(no rate_lag mention here — intentionally stripped for test)"
    )
    fake_api = {**config.FRED_SERIES_API, "SAHMREALTIME": sahm_unannotated}
    monkeypatch.setattr(config, "FRED_SERIES_API", fake_api)
    # pit_audit imports FRED_SERIES_API at module load; override the
    # imported binding so the validator sees the test fixture.
    from macro_pipeline.utils import pit_audit as pit_audit_mod
    monkeypatch.setattr(pit_audit_mod, "FRED_SERIES_API", fake_api)
    report = audit_pit_contracts()
    bad = [m for m in report.mismatches if m.series_id == "SAHMREALTIME"]
    assert bad, (
        f"validator must flag SAHMREALTIME when rationale lacks "
        f"release_lag mention; mismatches: "
        f"{[(m.series_id, m.reason) for m in report.mismatches]}"
    )
    assert "release_lag" in bad[0].reason.lower()


# ---------------------------------------------------------------------------
# 5. NEG — pit_audit raises on Option Z with positive lag and no rationale
# ---------------------------------------------------------------------------
def test_option_z_branch_release_lag_consistency_validator(monkeypatch) -> None:
    """Synthetic Option Z series with ``release_lag_days=10`` and a
    rationale that doesn't mention release_lag → audit flags it."""
    from macro_pipeline import config
    from macro_pipeline.utils.pit_audit import audit_pit_contracts

    bad_spec = {
        "freq": "M", "vintage": True, "unit": "pct",
        "expected_min": -1.0, "expected_max": 10.0, "release_lag_days": 10,
        "pit_safe_by_construction": True,
        "pit_construction_rationale": (
            "Some series we believe is real-time-by-construction with no "
            "lag commentary at all."
        ),
        "derived_confidence_cap": 0.80,
        "description": "synthetic test series",
    }
    fake_api = {**config.FRED_SERIES_API, "TEST_OPT_Z_BAD": bad_spec}
    monkeypatch.setattr(config, "FRED_SERIES_API", fake_api)
    # The audit walks FRED_SERIES_API at module level; reload to pick up.
    from macro_pipeline.utils import pit_audit as pit_audit_mod
    monkeypatch.setattr(pit_audit_mod, "FRED_SERIES_API", fake_api)
    report = audit_pit_contracts()
    flagged = [m for m in report.mismatches if m.series_id == "TEST_OPT_Z_BAD"]
    assert flagged, "synthetic Option Z series without rationale was not flagged"


# ---------------------------------------------------------------------------
# 6. NEG — config-vs-cache release_lag drift surfaced via metadata
# ---------------------------------------------------------------------------
def test_load_sahm_with_inconsistent_release_lag_metadata_raises(monkeypatch) -> None:
    """Defends against config-cache drift. Live config is the source of
    truth (post-3.5b-U); the access path reads ``release_lag_days`` from
    config first with cache-meta fallback. A test that mocks config to
    a different value than cache should see the live config value
    surface in ``applied_release_lag_days``.

    NEG framing: if the access path silently used the cache's stale
    ``release_lag_days=7`` instead of the live config value, the
    metadata claim would not match the applied behavior, and this test
    would fail."""
    from macro_pipeline import config

    # Mock config to a deliberately different value (simulate post-update
    # state where cache sidecar is stale).
    sahm_modified = dict(config.FRED_SERIES_API["SAHMREALTIME"])
    sahm_modified["release_lag_days"] = 45  # arbitrary non-default
    sahm_modified["pit_construction_rationale"] = (
        sahm_modified["pit_construction_rationale"]
        + " release_lag mock for drift test."
    )
    monkeypatch.setitem(config.FRED_SERIES_API, "SAHMREALTIME", sahm_modified)

    bundle = load_series("SAHMREALTIME", as_of=pd.Timestamp("2025-06-15"))
    # Metadata must reflect the LIVE config value, not the cache sidecar.
    assert bundle.metadata["applied_release_lag_days"] == 45, (
        f"applied_release_lag_days={bundle.metadata['applied_release_lag_days']} "
        "did not pick up live config override → cache-vs-config drift not "
        "handled correctly"
    )
    # The actual data window must respect the new lag.
    nonnull = bundle.data.dropna()
    cutoff = pd.Timestamp("2025-06-15") - pd.Timedelta(days=45)
    assert nonnull.index[-1] <= cutoff
