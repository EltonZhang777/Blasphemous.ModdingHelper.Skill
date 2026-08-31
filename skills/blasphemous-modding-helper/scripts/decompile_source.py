#!/usr/bin/env python3
"""Decompile Blasphemous assemblies and create a source solution."""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path
from typing import Optional, Sequence

from blasphemous_modding_helper.decompiler import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_POLL_TIMEOUT_SECONDS,
    DecompileError,
    DecompileWorkflow,
    PlatformAdapter,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="decompile_source",
        description="Restore and decompile Blasphemous game assemblies.",
        epilog=(
            "External tools run as direct argument arrays. The script never "
            "auto-elevates; fix permissions manually when access is denied."
        ),
    )
    parser.add_argument(
        "-g",
        "--game-path",
        help="Blasphemous installation directory; defaults to the detected Steam path.",
    )
    parser.add_argument(
        "-o",
        "--output-path",
        help="Output directory; defaults to the Skill's source_code directory.",
    )
    parser.add_argument(
        "--poll-interval",
        "--poll-interval-sec",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="DLL restoration polling interval in seconds.",
    )
    parser.add_argument(
        "--poll-timeout",
        "--poll-timeout-sec",
        type=float,
        default=DEFAULT_POLL_TIMEOUT_SECONDS,
        help="DLL restoration timeout in seconds.",
    )
    parser.add_argument(
        "--platform",
        choices=("Windows", "Linux", "macOS"),
        help="Override detected platform for fixture or cross-platform validation.",
    )
    parser.add_argument(
        "--steam-launcher",
        help="Override Steam URI launcher executable for this invocation.",
    )
    parser.add_argument(
        "--dotnet",
        help="Override dotnet executable for this invocation.",
    )
    parser.add_argument(
        "--ilspycmd",
        help="Override ilspycmd executable for this invocation.",
    )
    return parser


def _format_error(error: DecompileError) -> str:
    lines = [f"[FAIL] Error [{error.category}]: {error.message}"]
    lines.extend(f"Detail: {detail}" for detail in error.details)
    lines.append(f"Action: {error.action}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        adapter = PlatformAdapter.detect(args.platform or platform.system())
        workflow = DecompileWorkflow(platform_adapter=adapter)
        workflow.run(
            game_path=args.game_path,
            output_path=args.output_path,
            poll_interval=args.poll_interval,
            poll_timeout=args.poll_timeout,
            steam_launcher=args.steam_launcher,
            dotnet=args.dotnet,
            ilspycmd=args.ilspycmd,
            skill_root=Path(__file__).resolve().parents[1],
        )
    except DecompileError as error:
        print(_format_error(error), file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError) as error:
        print(
            "[FAIL] Error [decompile/runtime]: "
            f"Decompilation failed unexpectedly: {error}\n"
            "Action: Check paths and external tools, then rerun setup.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
