"""Cache integrity audit (Layer 3.5E).

CLI: ``python -m macro_pipeline.utils.cache_audit``

Walks ``data/cache/`` and reports per-file pass / fail / missing-sidecar
counts for both parquet caches and the HMM pickle artifact. Each cache
is validated against its sidecar's ``data_sha256`` (recomputed, not
length-checked). Exits 0 in clean state, 1 on any issue.

Codex review C/N/Q + ChatGPT Dim 12 (atomicity portion).

Cache shapes covered
--------------------
- ``data/cache/<stem>.parquet`` + ``<stem>.meta.json`` (top-level
  parquet caches written via ``cache.write_cache_atomic``).
- ``data/cache/<subdir>/<filename>.parquet`` + ``<filename>.meta.json``
  (subdir caches written via ``cache.write_cache_atomic_subdir``,
  e.g. the R^2 panel).
- ``data/cache/hmm/regime_3state_v1.pkl`` + ``regime_3state_v1.meta.json``
  (3.5A frozen contract — sha-verified pickle artifact).

Usage
-----
::

    python -m macro_pipeline.utils.cache_audit
    python -m macro_pipeline.utils.cache_audit --root /custom/cache/dir
    python -m macro_pipeline.utils.cache_audit --quiet
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from macro_pipeline.config import DATA_CACHE


@dataclass(frozen=True)
class CacheAuditIssue:
    """Single cache validation failure."""

    path: Path
    kind: str          # one of {"missing_sidecar", "sha_mismatch",
                       #         "schema_mismatch", "row_count_mismatch",
                       #         "sidecar_parse_error", "missing_data_sha256"}
    detail: str

    def render(self) -> str:
        return f"  [{self.kind}] {self.path}: {self.detail}"


@dataclass
class CacheAuditReport:
    """Aggregate audit result."""

    files_checked: int
    files_ok: int
    issues: list[CacheAuditIssue]
    skipped: list[Path]   # files we recognised but couldn't pair (orphan
                          # parquet without sidecar — counted as issue;
                          # orphan sidecar without parquet — flagged
                          # separately)

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _audit_one(
    data_path: Path, sidecar_path: Path,
) -> list[CacheAuditIssue]:
    """Validate one ``(data_file, sidecar)`` pair. Empty list = OK."""
    issues: list[CacheAuditIssue] = []
    if not sidecar_path.exists():
        issues.append(CacheAuditIssue(
            path=data_path,
            kind="missing_sidecar",
            detail=f"sidecar not found at {sidecar_path}",
        ))
        return issues
    try:
        meta = json.loads(sidecar_path.read_bytes())
    except json.JSONDecodeError as exc:
        issues.append(CacheAuditIssue(
            path=data_path,
            kind="sidecar_parse_error",
            detail=f"sidecar JSON parse error: {exc}",
        ))
        return issues

    expected_sha = meta.get("data_sha256")
    if not expected_sha:
        issues.append(CacheAuditIssue(
            path=data_path,
            kind="missing_data_sha256",
            detail="sidecar lacks data_sha256 field",
        ))
        return issues

    actual_sha = _sha256_file(data_path)
    if actual_sha != expected_sha:
        issues.append(CacheAuditIssue(
            path=data_path,
            kind="sha_mismatch",
            detail=(
                f"sidecar sha256[:16]={expected_sha[:16]}..., "
                f"recomputed={actual_sha[:16]}... — file modified post-cache"
            ),
        ))
        return issues

    # Optional row_count check (only meaningful for parquet caches).
    if data_path.suffix == ".parquet":
        rc = meta.get("row_count")
        if rc is not None:
            import pandas as pd
            df = pd.read_parquet(data_path)
            if len(df) != int(rc):
                issues.append(CacheAuditIssue(
                    path=data_path,
                    kind="row_count_mismatch",
                    detail=f"sidecar={rc}, actual={len(df)}",
                ))
    return issues


def validate_cache_integrity(
    cache_root: Path | None = None,
) -> CacheAuditReport:
    """Walk the cache root and validate every parquet + pickle pair.

    Returns a ``CacheAuditReport`` with per-file issue list.
    """
    root = Path(cache_root) if cache_root is not None else DATA_CACHE
    issues: list[CacheAuditIssue] = []
    skipped: list[Path] = []
    files_checked = 0
    files_ok = 0

    # Walk every parquet + pickle under root.
    targets: list[Path] = []
    if root.is_dir():
        for ext in ("*.parquet", "*.pkl"):
            targets.extend(sorted(root.rglob(ext)))

    for data_path in targets:
        files_checked += 1
        sidecar_path = data_path.with_suffix(".meta.json")
        file_issues = _audit_one(data_path, sidecar_path)
        if not file_issues:
            files_ok += 1
        else:
            issues.extend(file_issues)

    return CacheAuditReport(
        files_checked=files_checked,
        files_ok=files_ok,
        issues=issues,
        skipped=skipped,
    )


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m macro_pipeline.utils.cache_audit",
        description=(
            "Validate cache integrity (parquet + pickle sha256 vs sidecar)."
        ),
    )
    parser.add_argument(
        "--root", default=None,
        help="Cache root (default: macro_pipeline.config.DATA_CACHE).",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Print only the summary line + issue list (skip per-file OK).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else DATA_CACHE
    report = validate_cache_integrity(cache_root=root)

    if not args.quiet:
        print(f"Cache audit: root={root}")
        print(f"  files_checked = {report.files_checked}")
        print(f"  files_ok      = {report.files_ok}")
        print(f"  issues        = {len(report.issues)}")
    if report.has_issues:
        print("FAIL — cache integrity issues:")
        for issue in report.issues:
            print(issue.render())
        return 1
    print(
        f"OK — {report.files_ok}/{report.files_checked} cache entries valid"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(_main(sys.argv[1:]))


__all__ = [
    "CacheAuditIssue",
    "CacheAuditReport",
    "validate_cache_integrity",
]
