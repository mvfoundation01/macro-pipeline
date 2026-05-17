"""L10 D5 — Results page endpoints.

Strategy:
- L8 ``ForecastUIRenderer.render_full_report(partition)`` produces a
  self-contained dir tree at ``webapp_render_dir/report_<partition>/``
  with index.html + 8 detail pages + relative-path static assets.
- We serve that dir directly via ``send_from_directory`` (preserves the
  L8 page navigation + CSS without rewriting paths).

Routes
------
GET /results/latest                                Redirect to most-recent partition.
GET /results/<partition>                           Serve index.html.
GET /results/<partition>/<path:filename>           Serve any file in the report dir.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    send_from_directory,
    url_for,
)

results_bp = Blueprint("results", __name__)

_PARTITION_RE = re.compile(r"^\d{4}-\d{2}$")


def _validate_partition(partition: str) -> None:
    """Reject anything that isn't ``YYYY-MM``; abort(404) on failure.

    Defends against path traversal (``../``) and arbitrary directory names.
    """
    if not _PARTITION_RE.fullmatch(partition):
        abort(404)


@results_bp.route("/latest")
def latest():
    """Redirect to the most-recent partition (current month if it exists,
    else most-recently-modified ``report_*`` directory, else home with flash).
    """
    render_dir = Path(current_app.config["WEBAPP_RENDER_DIR"])
    current_partition = datetime.now(UTC).strftime("%Y-%m")
    if (render_dir / f"report_{current_partition}").exists():
        return redirect(url_for("results.show", partition=current_partition))
    candidates = sorted(
        render_dir.glob("report_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        from flask import flash

        flash(
            "Chưa có forecast nào được tạo. Hãy điền form và chạy forecast trước.",
            "error",
        )
        return redirect(url_for("home.index"))
    latest_dir = candidates[0]
    partition = latest_dir.name.removeprefix("report_")
    return redirect(url_for("results.show", partition=partition))


@results_bp.route("/<partition>")
@results_bp.route("/<partition>/")
def show(partition: str):
    """Render the L11 results wrapper with provenance + links to L8 pages."""
    _validate_partition(partition)
    render_dir = Path(current_app.config["WEBAPP_RENDER_DIR"]) / f"report_{partition}"
    if not render_dir.exists():
        abort(404)
    provenance: dict | None = None
    prov_path = render_dir / "PROVENANCE.json"
    if prov_path.exists():
        try:
            provenance = json.loads(prov_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            provenance = None
    return render_template(
        "results.html", partition=partition, provenance=provenance
    )


@results_bp.route("/<partition>/<path:filename>")
def asset(partition: str, filename: str):
    """Serve any file inside the report dir (CSS/JS/other HTML pages)."""
    _validate_partition(partition)
    render_dir = Path(current_app.config["WEBAPP_RENDER_DIR"]) / f"report_{partition}"
    if not render_dir.exists():
        abort(404)
    return send_from_directory(str(render_dir), filename)
