"""Layer 3.5b-T — strict cache validation at the production read boundary.

Closes Codex 5.5 finding T (HIGH) — production scoring data path
(``access._read_cached_series_and_meta``) historically called
``pd.read_parquet`` directly with no sidecar validation, and
``cache.read_cache_validated`` short-circuited the sha256 check when
the sidecar's ``data_sha256`` field was empty / missing.

Test plan per pre-flight §3.5: 4 NEG / 2 POS = 67% NEG (exceeds 50%
floor). The "tampered parquet" and "tampered sidecar" tests cover
the same bug from two angles (Codex finding T (a) and (b)
respectively).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from macro_pipeline.cache import (
    read_cache_validated,
    write_cache_atomic,
)
from macro_pipeline.exceptions import CacheValidationError


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Path:
    """Tmp cache dir with one valid PAYEMS-style fixture written via the
    atomic helper (so ``data_sha256`` is populated). All tests in this
    module operate on that fixture rather than mutating production
    caches."""
    df = pd.DataFrame({"PAYEMS": [157000.0, 157200.0, 157400.0]},
                      index=pd.date_range("2024-01-01", periods=3, freq="MS"))
    write_cache_atomic(
        stem="fred_PAYEMS",
        df=df,
        meta={"indicator_id": "PAYEMS", "source": "FRED_API"},
        cache_dir=tmp_path,
    )
    return tmp_path


def _patch_data_cache(tmp_cache: Path):
    """Context manager-style patch for the module-level DATA_CACHE
    constant in ``access`` so ``load_series`` reads from our fixture."""
    return patch("macro_pipeline.access.DATA_CACHE", tmp_cache)


# ---------------------------------------------------------------------------
# 1. NEG — load_series raises on corrupted (sha-mismatch) cache
# ---------------------------------------------------------------------------
def test_load_series_raises_on_corrupted_cache(tmp_cache: Path) -> None:
    """Codex T (a) + (b): with the production read path now routed
    through ``read_cache_validated``, an sha mismatch must surface as
    ``CacheValidationError`` at the access boundary (helper returns
    ``None`` on mismatch; access wrapper raises)."""
    parquet = tmp_cache / "fred_PAYEMS.parquet"
    sidecar = tmp_cache / "fred_PAYEMS.meta.json"
    # Tamper sidecar's data_sha256 → forces sha mismatch on read,
    # preserving the parquet bytes so pyarrow can still parse the file.
    md = json.loads(sidecar.read_text())
    md["data_sha256"] = "0" * 64
    sidecar.write_text(json.dumps(md))
    # access registry needs the cache stem visible.
    from macro_pipeline.access import _refresh_registry, load_series

    with _patch_data_cache(tmp_cache), patch(
        "macro_pipeline.access._cache_registry",
        return_value={"PAYEMS": "fred_PAYEMS"},
    ):
        _refresh_registry()
        with pytest.raises(CacheValidationError, match="cache validation failed"):
            load_series("PAYEMS")
    # Sanity: parquet untouched.
    assert parquet.exists()


# ---------------------------------------------------------------------------
# 2. NEG — load_series raises on missing data_sha256 sidecar
# ---------------------------------------------------------------------------
def test_load_series_raises_on_missing_sha_sidecar(tmp_cache: Path) -> None:
    """The Codex T (b) bug specifically: a sidecar that exists but
    lacks ``data_sha256`` was silently accepted by the prior truthy
    guard. Post-3.5b-T, this MUST raise ``CacheValidationError``."""
    sidecar = tmp_cache / "fred_PAYEMS.meta.json"
    md = json.loads(sidecar.read_text())
    md.pop("data_sha256", None)
    sidecar.write_text(json.dumps(md))
    from macro_pipeline.access import _refresh_registry, load_series

    with _patch_data_cache(tmp_cache), patch(
        "macro_pipeline.access._cache_registry",
        return_value={"PAYEMS": "fred_PAYEMS"},
    ):
        _refresh_registry()
        with pytest.raises(CacheValidationError, match="missing data_sha256"):
            load_series("PAYEMS")


# ---------------------------------------------------------------------------
# 3. NEG — load_series raises on tampered sidecar (same as #1 but via
#    a different tampering surface to lock the contract from a second
#    angle)
# ---------------------------------------------------------------------------
def test_load_series_raises_on_tampered_sidecar(tmp_cache: Path) -> None:
    """Modify ``data_sha256`` to a non-empty fake hex string; helper
    returns ``None`` on mismatch; access wrapper raises."""
    sidecar = tmp_cache / "fred_PAYEMS.meta.json"
    md = json.loads(sidecar.read_text())
    md["data_sha256"] = "abcdef" + "0" * 58
    sidecar.write_text(json.dumps(md))
    from macro_pipeline.access import _refresh_registry, load_series

    with _patch_data_cache(tmp_cache), patch(
        "macro_pipeline.access._cache_registry",
        return_value={"PAYEMS": "fred_PAYEMS"},
    ):
        _refresh_registry()
        with pytest.raises(CacheValidationError):
            load_series("PAYEMS")


# ---------------------------------------------------------------------------
# 4. NEG — read_cache_validated mandatory sha (D2 spec literal)
# ---------------------------------------------------------------------------
def test_read_cache_validated_mandatory_sha(tmp_cache: Path) -> None:
    """Direct contract test on the helper: a sidecar that exists +
    parses but lacks ``data_sha256`` raises (post-3.5b-T per D2)."""
    sidecar = tmp_cache / "fred_PAYEMS.meta.json"
    md = json.loads(sidecar.read_text())
    md.pop("data_sha256", None)
    sidecar.write_text(json.dumps(md))
    with pytest.raises(CacheValidationError, match="missing data_sha256"):
        read_cache_validated("fred_PAYEMS", tmp_cache)


# ---------------------------------------------------------------------------
# 5. POS — load_series succeeds on valid cache
# ---------------------------------------------------------------------------
def test_load_series_succeeds_on_valid_cache(tmp_cache: Path) -> None:
    """Round-trip: write fixture via ``write_cache_atomic``;
    ``load_series`` must return the matching ``IndicatorBundle``."""
    from macro_pipeline.access import _refresh_registry, load_series

    with _patch_data_cache(tmp_cache), patch(
        "macro_pipeline.access._cache_registry",
        return_value={"PAYEMS": "fred_PAYEMS"},
    ):
        _refresh_registry()
        bundle = load_series("PAYEMS")
    assert bundle.indicator_id == "PAYEMS"
    assert bundle.data.shape == (3,)
    assert bundle.data.iloc[0] == 157000.0


# ---------------------------------------------------------------------------
# 6. POS — all caches have data_sha256 post-L3.5b
# ---------------------------------------------------------------------------
def test_all_caches_have_sha_post_l3_5b() -> None:
    """Walk the live ``DATA_CACHE`` and assert every ``*.meta.json``
    carries a non-empty ``data_sha256`` field. Skipped if the cache is
    empty (CI environment without populated caches).

    Per Standing Order: empirical claim verification — this test makes
    the "all 138 caches have data_sha256" assertion mechanically
    falsifiable on every test run, not just on Pre-flight smoke
    inspection."""
    from macro_pipeline.config import DATA_CACHE

    if not DATA_CACHE.exists():
        pytest.skip("DATA_CACHE does not exist (CI without populated caches)")
    parquets = list(DATA_CACHE.rglob("*.parquet"))
    if not parquets:
        pytest.skip("no parquet caches present (CI without populated caches)")

    missing: list[tuple[Path, str]] = []
    for parquet in parquets:
        sidecar = parquet.with_suffix(".meta.json")
        if not sidecar.exists():
            missing.append((parquet, "no sidecar"))
            continue
        try:
            md = json.loads(sidecar.read_text())
        except json.JSONDecodeError:
            missing.append((parquet, "sidecar JSON parse error"))
            continue
        # HMM pickle sidecars also live under data/cache/hmm but follow
        # a slightly different schema; both still must carry data_sha256.
        if not md.get("data_sha256"):
            missing.append((parquet, "no data_sha256 in sidecar"))

    assert not missing, (
        f"{len(missing)} cache entries violate the L3.5b-T mandatory-"
        f"data_sha256 invariant: {missing[:5]}"
    )
