"""L7 D7 tests — CLI parsing."""
from __future__ import annotations

from pathlib import Path

import pytest

from macro_pipeline.cli import build_scheduler_cli_parser, main


def test_cli_parser_start_subcommand() -> None:
    """POS: start subcommand parses."""
    parser = build_scheduler_cli_parser()
    args = parser.parse_args(["start", "--config", "/tmp/config.yaml"])
    assert args.command == "start"
    assert args.config == Path("/tmp/config.yaml")


def test_cli_parser_start_with_alert_rules() -> None:
    """POS: start with --alert-rules flag."""
    parser = build_scheduler_cli_parser()
    args = parser.parse_args([
        "start", "--config", "/tmp/c.yaml",
        "--alert-rules", "/tmp/rules.yaml",
    ])
    assert args.alert_rules == Path("/tmp/rules.yaml")


def test_cli_parser_stop_subcommand() -> None:
    """POS: stop subcommand parses."""
    parser = build_scheduler_cli_parser()
    args = parser.parse_args(["stop"])
    assert args.command == "stop"


def test_cli_parser_status_subcommand() -> None:
    """POS: status subcommand parses."""
    parser = build_scheduler_cli_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_cli_parser_trigger_once_subcommand() -> None:
    """POS: trigger-once subcommand parses."""
    parser = build_scheduler_cli_parser()
    args = parser.parse_args([
        "trigger-once", "--job-id", "daily", "--config", "/tmp/c.yaml",
    ])
    assert args.command == "trigger-once"
    assert args.job_id == "daily"


def test_cli_parser_start_missing_config_raises() -> None:
    """NEG: start without --config exits via argparse."""
    parser = build_scheduler_cli_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["start"])


def test_cli_parser_trigger_once_missing_job_id_raises() -> None:
    """NEG: trigger-once without --job-id exits."""
    parser = build_scheduler_cli_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["trigger-once", "--config", "/tmp/c.yaml"])


def test_cli_parser_no_subcommand_raises() -> None:
    """NEG: missing required subcommand exits."""
    parser = build_scheduler_cli_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_cli_main_start_exit_zero(capsys) -> None:
    """POS-inv: main('start ...') returns 0."""
    rc = main(["start", "--config", "/tmp/c.yaml"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "[scheduler] start" in captured.out


def test_cli_main_trigger_once_exit_zero(capsys) -> None:
    """POS-inv: main('trigger-once ...') returns 0."""
    rc = main([
        "trigger-once", "--job-id", "daily", "--config", "/tmp/c.yaml"
    ])
    assert rc == 0
