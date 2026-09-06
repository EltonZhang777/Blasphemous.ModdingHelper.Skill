#!/usr/bin/env python3
"""Report active preferences scope for the caller's Mod repository."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from blasphemous_modding_helper.preferences import preference_scope


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report whether project or user preferences are active."
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        help="Caller Mod repository; defaults to the current directory.",
    )
    parser.add_argument(
        "--home",
        type=Path,
        help="User home directory; defaults to the host home.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    scope = preference_scope(args.cwd, args.home)
    if scope is not None:
        print(scope)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
