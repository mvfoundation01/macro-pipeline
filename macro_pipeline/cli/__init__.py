"""L7 CLI module — command-line entry points for scheduler + tooling.

Per Strategic L7 single-sub-phase pre-flight 2026-05-16
(ACCELERATION PROTOCOL v1.0) D7.

Public API
----------
``build_scheduler_cli_parser``    argparse.ArgumentParser factory.
``main``                          CLI entry point (used by setup.py / pyproject).
"""
from __future__ import annotations

from .scheduler_cli import build_scheduler_cli_parser, main

__all__ = ["build_scheduler_cli_parser", "main"]
