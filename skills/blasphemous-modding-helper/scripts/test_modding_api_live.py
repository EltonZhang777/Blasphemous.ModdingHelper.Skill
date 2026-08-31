#!/usr/bin/env python3
"""Run the opt-in live ModdingAPI release smoke through the Python resolver."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence


SCRIPT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_ROOT.parents[2]
RESOLVER = SCRIPT_ROOT / "resolve_modding_api.py"


class LiveTestFailure(RuntimeError):
    """A user-facing live smoke failure."""


def parse_key_values(output: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def resolve_live() -> Dict[str, str]:
    try:
        result = subprocess.run(
            [sys.executable, str(RESOLVER), "--selector", "latest"],
            cwd=str(REPOSITORY_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
    except OSError as error:
        raise LiveTestFailure(f"live Release resolver could not start: {error}") from error
    if result.returncode != 0:
        raise LiveTestFailure(
            "live Release resolution failed with exit code "
            f"{result.returncode}:\n{result.stdout}\n{result.stderr}"
        )
    return parse_key_values(result.stdout)


def verify_values(values: Dict[str, str]) -> None:
    tag = values.get("MODDING_API_RESOLVED_TAG", "")
    commit = values.get("MODDING_API_RESOLVED_COMMIT", "")
    expected_docs = (
        "https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/"
        f"{tag}/docs"
    )
    expected_source = (
        "https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/{tag}"
    ).format(tag=tag)
    checks = (
        (values.get("MODDING_API_SELECTOR") == "latest", "must resolve latest"),
        (
            values.get("MODDING_API_SELECTOR_KIND") == "release",
            "must resolve a Release",
        ),
        (bool(tag) and tag != "main", "must resolve an explicit Release tag"),
        (
            bool(re.fullmatch(r"[0-9a-fA-F]{40}", commit)),
            "must resolve a 40-character commit",
        ),
        (
            values.get("MODDING_API_RESOLVED_REF") == tag,
            "must route through the Release tag",
        ),
        (
            values.get("MODDING_API_DOCS_URL") == expected_docs,
            "emitted an incorrect docs URL",
        ),
        (
            values.get("MODDING_API_SOURCE_URL") == expected_source,
            "emitted an incorrect source URL",
        ),
        (
            "/tree/main" not in values.get("MODDING_API_DOCS_URL", ""),
            "must not route docs through main",
        ),
        (
            not values.get("MODDING_API_SOURCE_URL", "").endswith("/tree/main"),
            "must not route source through main",
        ),
    )
    for passed, message in checks:
        if not passed:
            raise LiveTestFailure(message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Opt-in live GitHub Release smoke for the Python ModdingAPI resolver."
        ),
        epilog="No network request is made unless --live is explicitly supplied.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Resolve the current stable GitHub Release over the network.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.live:
        print(
            "Live verification is opt-in; re-run with --live when network access "
            "is approved.",
            file=sys.stderr,
        )
        return 2
    try:
        values = resolve_live()
        verify_values(values)
    except LiveTestFailure as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    print(f"MODDING_API_LIVE_TAG={values['MODDING_API_RESOLVED_TAG']}")
    print(f"MODDING_API_LIVE_COMMIT={values['MODDING_API_RESOLVED_COMMIT']}")
    print(
        "MODDING_API_LIVE_DOCS_URL="
        f"{values['MODDING_API_DOCS_URL']}/development/main.md"
    )
    print("[OK] ModdingAPI live Release smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
