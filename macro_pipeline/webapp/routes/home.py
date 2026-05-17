"""L10 D1 / L12 D7 — Home page (input form + detected local files)."""
from __future__ import annotations

import logging

from flask import Blueprint, render_template

from macro_pipeline.webapp.local_data_manager import LocalDataManager

log = logging.getLogger(__name__)
home_bp = Blueprint("home", __name__)


@home_bp.route("/")
def index():
    """Render the input form.

    L12 D7: also scan ``data/raw/official`` + ``data/raw/tradingview`` for V's
    institutional CSV exports and inject the classified result into the
    template context so V sees what's auto-detected before deciding whether
    to upload anything manually.
    """
    detected: dict = {}
    scan_error: str | None = None
    try:
        mgr = LocalDataManager()
        detected = mgr.scan()
    except Exception as exc:
        log.exception("LocalDataManager.scan() failed")
        scan_error = f"{type(exc).__name__}: {exc}"

    # Categories with usable files — drives the "we have local data for X"
    # callout next to the manual upload widgets.
    local_categories: set[str] = {
        cat
        for cat in ("yield_curve", "credit_spreads", "sentiment")
        if detected.get(cat)
    }

    return render_template(
        "input.html",
        detected_files=detected,
        local_categories=local_categories,
        scan_error=scan_error,
    )
