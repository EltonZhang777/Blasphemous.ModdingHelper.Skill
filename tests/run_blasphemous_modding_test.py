#!/usr/bin/env python3
"""Run the deterministic Python contract suite for the ModdingAPI workflow."""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLI = (
    REPOSITORY_ROOT
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
    / "blasphemous_modding_test.py"
)
SCRIPT_TESTS = (
    REPOSITORY_ROOT
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
)
CLI_COMMANDS = ("run", "stop", "clean", "logs", "status")
SCRIPT_TEST_ENTRY_POINTS = (
    SCRIPT_TESTS / "test_modding_api_lifecycle.py",
    SCRIPT_TESTS / "test_referencing_modding_api.py",
)
SCRIPT_TEST_HELP_ENTRY_POINTS = SCRIPT_TEST_ENTRY_POINTS + (
    SCRIPT_TESTS / "test_modding_api_live.py",
)


class RunnerError(RuntimeError):
    """A deterministic runner failure with a user-facing diagnostic."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Python-only deterministic Blasphemous ModdingAPI "
            "contract suite."
        ),
        epilog=(
            "The runner invokes Python entry points directly with shell=False. "
            "It does not deploy a mod, launch a game, or perform live checks."
        ),
    )
    parser.add_argument(
        "--python",
        dest="python_executable",
        default=sys.executable,
        help="Python 3 executable for child entry points (default: current interpreter).",
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Fail after the suite unless the repository worktree is clean.",
    )
    return parser


def run_command(
    label: str,
    command: Sequence[str],
    *,
    cwd: Path = REPOSITORY_ROOT,
) -> subprocess.CompletedProcess[str]:
    print(f"[RUN] {label}")
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
    except OSError as error:
        raise RunnerError(f"{label} could not start: {error}") from error

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RunnerError(
            f"{label} failed with exit code {result.returncode}."
        )
    print(f"[OK] {label}")
    return result


def run_cli_help(python_executable: str) -> None:
    run_command(
        "Python mod-test root help",
        (python_executable, str(CLI), "--help"),
    )
    for command in CLI_COMMANDS:
        run_command(
            f"Python mod-test {command} help",
            (python_executable, str(CLI), command, "--help"),
        )


def run_fixture_suite(python_executable: str) -> None:
    run_command(
        "Python unittest contract suite",
        (
            python_executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ),
    )
    for entry_point in SCRIPT_TEST_ENTRY_POINTS:
        run_command(
            f"Python script-local test {entry_point.name}",
            (python_executable, str(entry_point)),
        )
    for entry_point in SCRIPT_TEST_HELP_ENTRY_POINTS:
        run_command(
            f"Python script-local help {entry_point.name}",
            (python_executable, str(entry_point), "--help"),
        )


def check_clean_worktree() -> None:
    result = run_command(
        "clean worktree check",
        ("git", "status", "--porcelain"),
    )
    if result.stdout.strip():
        raise RunnerError(f"worktree is not clean:\n{result.stdout}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    print("Runner: native Python")
    print(f"Platform: {platform.system()}")
    print(f"Python: {args.python_executable}")

    try:
        run_cli_help(args.python_executable)
        run_fixture_suite(args.python_executable)
        if args.require_clean:
            check_clean_worktree()
    except RunnerError as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
