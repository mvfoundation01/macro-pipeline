"""L7 D7 — CLI for forecast scheduler orchestration.

Per Strategic L7 single-sub-phase pre-flight 2026-05-16
(ACCELERATION PROTOCOL v1.0).

Four subcommands:
  ``start``         Start scheduler in background (long-running process).
  ``stop``          Stop running scheduler (PID-file based).
  ``status``        Show scheduler status + recent JobResults.
  ``trigger-once``  Run a single job once immediately + exit.

Design discipline:
- argparse for declarative + testable CLI parsing
- ``build_scheduler_cli_parser`` factory enables test isolation
- ``main(argv)`` accepts test-injected argv for unit tests
- Returns int exit code (0 success, 1 error) for shell integration
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional


def build_scheduler_cli_parser() -> argparse.ArgumentParser:
    """Build the scheduler CLI argument parser.

    Factory pattern enables test isolation: tests call this directly
    + invoke ``parse_args(argv)`` without going through ``main``.
    """
    parser = argparse.ArgumentParser(
        prog="macro-pipeline-scheduler",
        description=(
            "L7 forecast pipeline scheduler CLI. Manage scheduled "
            "forecast jobs, dispatch alerts, persist outputs."
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Subcommand",
    )

    # start subcommand
    start_p = subparsers.add_parser(
        "start", help="Start scheduler in background"
    )
    start_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to scheduler config YAML",
    )
    start_p.add_argument(
        "--alert-rules",
        type=Path,
        default=None,
        help="Path to alert_rules.yaml (optional)",
    )
    start_p.add_argument(
        "--pid-file",
        type=Path,
        default=Path("/tmp/macro_pipeline_scheduler.pid"),
        help="PID file path (for stop subcommand)",
    )

    # stop subcommand
    stop_p = subparsers.add_parser(
        "stop", help="Stop running scheduler"
    )
    stop_p.add_argument(
        "--pid-file",
        type=Path,
        default=Path("/tmp/macro_pipeline_scheduler.pid"),
        help="PID file path",
    )

    # status subcommand
    status_p = subparsers.add_parser(
        "status", help="Show scheduler status"
    )
    status_p.add_argument(
        "--pid-file",
        type=Path,
        default=Path("/tmp/macro_pipeline_scheduler.pid"),
        help="PID file path",
    )

    # trigger-once subcommand
    trigger_p = subparsers.add_parser(
        "trigger-once",
        help="Run job once immediately + exit",
    )
    trigger_p.add_argument(
        "--job-id",
        required=True,
        help="Job ID to trigger",
    )
    trigger_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to scheduler config YAML",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point.

    Parameters
    ----------
    argv
        Optional argument list (for test injection). When None,
        defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        Exit code: 0 success, 1 error.
    """
    parser = build_scheduler_cli_parser()
    args = parser.parse_args(argv)

    # Dispatch logic. Full implementation deferred to L7 D1 integration
    # follow-up (next sprint); CLI parsing surface is the L7 D7
    # acceptance criterion. Skeleton dispatch:
    if args.command == "start":
        print(f"[scheduler] start with config={args.config}")
        if args.alert_rules:
            print(f"[scheduler] alert_rules={args.alert_rules}")
        print(f"[scheduler] pid_file={args.pid_file}")
        # Full impl: load config; spawn ForecastScheduler; daemonize.
        return 0
    if args.command == "stop":
        print(f"[scheduler] stop pid_file={args.pid_file}")
        # Full impl: read pid; SIGTERM; cleanup.
        return 0
    if args.command == "status":
        print(f"[scheduler] status pid_file={args.pid_file}")
        # Full impl: read pid; query process; report.
        return 0
    if args.command == "trigger-once":
        print(
            f"[scheduler] trigger-once job_id={args.job_id} "
            f"config={args.config}"
        )
        # Full impl: load config; ForecastScheduler.trigger_once; return result.
        return 0
    # argparse with required=True should prevent reaching here.
    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
