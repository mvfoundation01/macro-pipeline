"""L11 D2 — Build the bundled data snapshot.

Copies a curated manifest of panels from V's local ``data/cache/`` into
``macro_pipeline/data_snapshot/`` so the L11 ProducerAdapter can derive
ForecastInputs from real historical data inside the PyInstaller bundle
(no FRED API key, no internet required at forecast time).

Each panel is a parquet file with a sibling ``.meta.json``. The script
copies both, computes a SHA-256 of each parquet, and writes
``MANIFEST.json`` recording the snapshot date, panel list, file
checksums, and panel-count totals.

Rerun whenever V's local cache refreshes; commit the resulting changes.

Usage
-----
    python scripts/build_data_snapshot.py            # build snapshot
    python scripts/build_data_snapshot.py --list     # show manifest only
    python scripts/build_data_snapshot.py --check    # verify checksums of existing snapshot
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_CACHE = REPO_ROOT / "data" / "cache"
SNAPSHOT_DIR = REPO_ROOT / "macro_pipeline" / "data_snapshot"
MANIFEST_PATH = SNAPSHOT_DIR / "MANIFEST.json"

# Manifest is grouped by tier. Each entry is the parquet stem (no extension);
# the .meta.json sibling is copied automatically. Subdirectory entries use
# forward slashes.
MANIFEST: dict[str, list[str]] = {
    "tier1_shiller": [
        "official_SHILLER_TR_PRICE",
        "official_SHILLER_PRICE",
        "official_SHILLER_REAL_PRICE",
        "official_SHILLER_CAPE",
        "official_SHILLER_TR_CAPE",
        "official_SHILLER_EARNINGS",
        "official_SHILLER_DIVIDEND",
        "official_SHILLER_GS10",
        "official_SHILLER_CPI",
    ],
    "tier1_market_modern": [
        "yahoo_SPX_PRICE",
        "yahoo_SPX_TR",
        "yahoo_VIX_YAHOO",
        "yahoo_VIX3M",
    ],
    "tier1_recession_anchors": [
        "fred_USREC",
        "fred_T10Y2Y",
        "fred_T10Y3M",
    ],
    "tier1_analysis_artifacts": [
        "analysis/r_squared_panel",
    ],
    "tier2_form_overlay_anchors": [
        "fred_PAYEMS",
        "fred_PCEPILFE",
        "fred_CORESTICKM159SFRBATL",
        "fred_MEDCPIM158SFRBCLE",
        "fred_NFCI",
        "fred_ANFCI",
        "fred_KCFSI",
        "fred_INDPRO",
        "fred_SAHMREALTIME",
    ],
    "tier2_financial_stress": [
        "fed_EBP",
        "fed_NTFS_DAILY_DASHBOARD",
        "fed_NTFS_OFFICIAL_REPL",
    ],
    "tier3_vintage_panels": [
        "vintage_panels/PAYEMS_vintage",
        "vintage_panels/PCEPILFE_vintage",
        "vintage_panels/INDPRO_vintage",
        "vintage_panels/CFNAIMA3_vintage",
        "vintage_panels/RSAFS_vintage",
        "vintage_panels/RRSFS_vintage",
    ],
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _flat_panel_list() -> list[str]:
    return [p for entries in MANIFEST.values() for p in entries]


def _copy_panel(stem: str) -> tuple[bool, dict]:
    """Copy a single panel (parquet + .meta.json) into the snapshot.

    Returns (ok, record). ``record`` is the per-panel entry for MANIFEST.json
    (sha256 of parquet, byte size, copy timestamp), or contains ``"error"``.
    """
    src_parquet = SOURCE_CACHE / f"{stem}.parquet"
    src_meta = SOURCE_CACHE / f"{stem}.meta.json"
    if not src_parquet.exists():
        return False, {"stem": stem, "error": f"source missing: {src_parquet}"}
    dst_parquet = SNAPSHOT_DIR / f"{stem}.parquet"
    dst_parquet.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_parquet, dst_parquet)
    record: dict = {
        "stem": stem,
        "sha256": _sha256_file(dst_parquet),
        "bytes": dst_parquet.stat().st_size,
    }
    if src_meta.exists():
        shutil.copy2(src_meta, SNAPSHOT_DIR / f"{stem}.meta.json")
        record["meta_present"] = True
    else:
        record["meta_present"] = False
    return True, record


def build_snapshot() -> int:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(UTC).isoformat()
    records: list[dict] = []
    errors: list[dict] = []
    for stem in _flat_panel_list():
        ok, record = _copy_panel(stem)
        if ok:
            records.append(record)
            print(f"[OK]   {stem}  ({record['bytes']:>10,} bytes)")
        else:
            errors.append(record)
            print(f"[MISS] {stem}  ({record.get('error', 'unknown')})")
    total_bytes = sum(r["bytes"] for r in records)
    manifest = {
        "schema_version": "1.0",
        "build_timestamp_utc": now_iso,
        "source_cache": str(SOURCE_CACHE),
        "snapshot_dir": str(SNAPSHOT_DIR),
        "tiers": MANIFEST,
        "panels_copied": len(records),
        "panels_missing": len(errors),
        "total_bytes": total_bytes,
        "records": records,
        "errors": errors,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print()
    print(f"[INFO] {len(records)} panels copied, {len(errors)} missing")
    print(f"[INFO] Total bytes: {total_bytes:,} ({total_bytes / (1024 * 1024):.1f} MB)")
    print(f"[INFO] MANIFEST: {MANIFEST_PATH}")
    return 0 if not errors else 2


def check_snapshot() -> int:
    if not MANIFEST_PATH.exists():
        print(f"[ERROR] No MANIFEST.json at {MANIFEST_PATH}; run build first.")
        return 1
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    bad = 0
    for record in manifest.get("records", []):
        path = SNAPSHOT_DIR / f"{record['stem']}.parquet"
        if not path.exists():
            print(f"[MISSING]  {record['stem']}")
            bad += 1
            continue
        actual_sha = _sha256_file(path)
        if actual_sha != record["sha256"]:
            print(f"[CHECKSUM] {record['stem']}: expected {record['sha256'][:12]}, got {actual_sha[:12]}")
            bad += 1
        else:
            print(f"[OK]       {record['stem']}")
    print()
    if bad == 0:
        print(f"[INFO] All {len(manifest.get('records', []))} panels verified.")
        return 0
    print(f"[ERROR] {bad} panels failed verification.")
    return 1


def list_manifest() -> int:
    print(f"[INFO] Snapshot manifest ({len(_flat_panel_list())} panels):")
    for tier, entries in MANIFEST.items():
        print(f"  {tier}:")
        for stem in entries:
            src = SOURCE_CACHE / f"{stem}.parquet"
            status = "✓" if src.exists() else "✗ MISSING in cache"
            size = (
                f" ({src.stat().st_size:,} bytes)"
                if src.exists() else ""
            )
            print(f"    {status}  {stem}{size}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build / verify L11 data snapshot")
    parser.add_argument("--list", action="store_true", help="show manifest + source-cache availability")
    parser.add_argument("--check", action="store_true", help="verify checksums of existing snapshot")
    args = parser.parse_args(argv)
    if args.list:
        return list_manifest()
    if args.check:
        return check_snapshot()
    return build_snapshot()


if __name__ == "__main__":
    sys.exit(main())
