"""L10 D9 — Vietnamese user guide page."""
from __future__ import annotations

from flask import Blueprint, render_template

help_bp = Blueprint("help", __name__)


@help_bp.route("/")
def index():
    """Render Vietnamese guide."""
    return render_template("help.html")
