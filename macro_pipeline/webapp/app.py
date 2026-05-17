"""L10 D1 — Flask application factory.

Per Strategic L10 single comprehensive pre-flight 2026-05-17.

Builds the one-click web app: input page + Excel upload + numerical form
+ POST /forecast/run orchestration + results page (reuses L8 renderer)
+ Vietnamese help page.

Design discipline:
- Application factory pattern (testability + PyInstaller bootstrap)
- Strong secret-key generation (secrets.token_hex(32))
- 50 MiB upload cap (MAX_CONTENT_LENGTH); upload + forecast dirs created at startup
- Config overrides via ``create_app(config={...})`` for tests + standalone
- All four blueprints registered with URL prefixes
"""
from __future__ import annotations

import secrets
from pathlib import Path

from flask import Flask


def create_app(config: dict | None = None) -> Flask:
    """Application factory.

    Parameters
    ----------
    config
        Optional override mapping merged into ``app.config`` after defaults.
        Use this in tests + standalone bootstrap to relocate the upload /
        forecast directories outside the repo tree.

    Returns
    -------
    Flask
        Fully configured Flask app with all four L10 blueprints registered.
    """
    webapp_dir = Path(__file__).parent
    repo_root = webapp_dir.parent.parent

    app = Flask(
        __name__,
        template_folder=str(webapp_dir / "templates"),
        static_folder=str(webapp_dir / "static"),
    )
    app.config["SECRET_KEY"] = secrets.token_hex(32)
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MiB
    app.config["UPLOAD_DIR"] = repo_root / "data" / "uploads"
    app.config["FORECAST_STORE_DIR"] = repo_root / "data" / "forecasts"
    app.config["WEBAPP_RENDER_DIR"] = (
        repo_root / "data" / "forecasts" / "webapp_renders"
    )

    if config:
        app.config.update(config)

    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["FORECAST_STORE_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["WEBAPP_RENDER_DIR"]).mkdir(parents=True, exist_ok=True)

    from macro_pipeline.webapp.routes.forecast import forecast_bp
    from macro_pipeline.webapp.routes.help import help_bp
    from macro_pipeline.webapp.routes.home import home_bp
    from macro_pipeline.webapp.routes.results import results_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(forecast_bp, url_prefix="/forecast")
    app.register_blueprint(results_bp, url_prefix="/results")
    app.register_blueprint(help_bp, url_prefix="/help")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=8000, debug=False)
