#!/usr/bin/env python3
"""Report active configuration scope for the caller's Mod repository."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from blasphemous_modding_helper.preferences import (
    PreferenceError,
    preference_scope,
    set_unity_project_path,
    UnityProjectPathError,
    validate_preferences,
)


EXIT_SETUP_REQUIRED = 10


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report whether project or user configuration is active."
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
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run freshness-gated Python validation for the active config.yml.",
    )
    parser.add_argument(
        "--set-unity-project-path",
        metavar="PATH",
        help="Validate and add only unity_project_path to the active config.yml.",
    )
    return parser


def _safe_field(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ")


def _print_validation_failure(error: PreferenceError) -> int:
    location = getattr(error, "location", None)
    print(f"PREFERENCES_SCOPE={location.scope if location else ''}")
    print(f"PREFERENCES_FILE={location.path if location else ''}")
    print("PREFERENCES_VALIDATION_STATUS=failed")
    print("PREFERENCES_SETUP=required")
    print(f"PREFERENCES_VALIDATION_REASON={_safe_field(error)}")
    return EXIT_SETUP_REQUIRED


def _print_unity_path_failure(error: UnityProjectPathError) -> int:
    location = error.location
    print(f"PREFERENCES_SCOPE={location.scope if location else ''}")
    print(f"PREFERENCES_FILE={location.path if location else ''}")
    print("PREFERENCES_SETUP=not-required")
    print("PREFERENCES_NEXT_ACTION=retry-unity-project-path")
    print(f"PREFERENCES_VALIDATION_REASON={_safe_field(error)}")
    return EXIT_SETUP_REQUIRED


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.validate and args.set_unity_project_path is not None:
        parser.error("--validate and --set-unity-project-path are mutually exclusive")
    if args.set_unity_project_path is not None:
        try:
            location, project = set_unity_project_path(
                args.set_unity_project_path,
                cwd=args.cwd,
                home=args.home,
            )
        except UnityProjectPathError as error:
            return _print_unity_path_failure(error)
        except PreferenceError as error:
            return _print_validation_failure(error)
        print(f"PREFERENCES_SCOPE={location.scope}")
        print(f"PREFERENCES_FILE={location.path}")
        print(f"PREFERENCES_UNITY_PROJECT_PATH={project}")
        return 0
    if args.validate:
        try:
            result = validate_preferences(cwd=args.cwd, home=args.home)
        except PreferenceError as error:
            return _print_validation_failure(error)
        print(f"PREFERENCES_SCOPE={result.scope}")
        print(f"PREFERENCES_FILE={result.path}")
        print(f"PREFERENCES_VALIDATION_STATUS={result.status}")
        print(f"PREFERENCES_VALIDATION_TRIGGER={result.trigger}")
        print(f"PREFERENCES_VERSION={result.version}")
        print(f"PREFERENCES_CHECK_PERIOD_DAYS={result.check_period_days}")
        print(f"PREFERENCES_UPDATED_FIELDS={','.join(result.updated_fields)}")
        return 0
    scope = preference_scope(args.cwd, args.home)
    if scope is not None:
        print(scope)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
