"""L10 D1 — Home page (input form)."""
from __future__ import annotations

from flask import Blueprint, render_template

home_bp = Blueprint("home", __name__)


@home_bp.route("/")
def index():
    """Render the input form (D2)."""
    return render_template("input.html")
