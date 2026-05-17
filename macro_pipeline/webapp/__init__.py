"""L10 web app — one-click UI for forecast pipeline.

Per Strategic L10 single comprehensive pre-flight 2026-05-17.

Public API
----------
``create_app``   Flask application factory.
"""
from macro_pipeline.webapp.app import create_app

__all__ = ["create_app"]
