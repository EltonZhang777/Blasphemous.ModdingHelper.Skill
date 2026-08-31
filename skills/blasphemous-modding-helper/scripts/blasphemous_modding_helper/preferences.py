"""Preference scope discovery and parsing shared by Skill entry points."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple


PREFERENCES_RELATIVE_PATH = Path(".skills") / "blasphemous-modding-helper" / "preferences.md"


class PreferenceError(Exception):
    """A malformed or unreadable preferences file."""


@dataclass(frozen=True)
class PreferenceLocation:
    """One selected preference file and its scope."""

    scope: str
    path: Path


@dataclass(frozen=True)
class Preferences:
    """Parsed preferences with the scope that supplied them."""

    scope: str
    path: Path
    values: Dict[str, str]


def preference_paths(
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Tuple[PreferenceLocation, PreferenceLocation]:
    """Return project then user locations, preserving precedence order."""

    current_directory = (cwd or Path.cwd()).expanduser().resolve(strict=False)
    user_home = (home or Path.home()).expanduser().resolve(strict=False)
    return (
        PreferenceLocation("project", current_directory / PREFERENCES_RELATIVE_PATH),
        PreferenceLocation("user", user_home / PREFERENCES_RELATIVE_PATH),
    )


def find_preferences(
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Optional[PreferenceLocation]:
    """Select first regular preferences file: project, then user."""

    for location in preference_paths(cwd, home):
        if location.path.is_file():
            return location
    return None


def preference_scope(
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Optional[str]:
    """Return selected scope or ``None`` when no preferences file exists."""

    location = find_preferences(cwd, home)
    return location.scope if location is not None else None


def parse_preferences(
    path: Path,
    *,
    required: Iterable[str] = (),
) -> Dict[str, str]:
    """Parse plain ``key: value`` preferences without changing the file."""

    preferences_path = Path(path).expanduser().resolve(strict=False)
    try:
        lines = preferences_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise PreferenceError(
            f"Could not read preferences.md at {preferences_path}: {error}"
        ) from error

    values: Dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            raise PreferenceError(
                f"Invalid preferences.md line {line_number}: expected 'key: value'."
            )
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise PreferenceError(
                f"Invalid preferences.md line {line_number}: key and value are required."
            )
        if key in values:
            raise PreferenceError(f"Duplicate preference '{key}' on line {line_number}.")
        values[key] = value

    missing = [key for key in required if key not in values]
    if missing:
        missing_text = ", ".join(missing)
        raise PreferenceError(
            f"preferences.md at {preferences_path} must define {missing_text}."
        )
    return values


def load_preferences(
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
    *,
    required: Iterable[str] = (),
) -> Preferences:
    """Select and parse project/user preferences without writing either file."""

    locations = preference_paths(cwd, home)
    for location in locations:
        if not location.path.exists():
            continue
        if not location.path.is_file():
            raise PreferenceError(f"Preference path is not a file: {location.path}")
        return Preferences(
            location.scope,
            location.path,
            parse_preferences(location.path, required=required),
        )
    checked = ", ".join(str(item.path) for item in locations)
    raise PreferenceError(f"No preferences.md found. Checked: {checked}")


def resolve_preference_path(value: str, base: Path) -> Path:
    """Expand a configured path relative to caller-owned working directory."""

    expanded = os.path.expandvars(os.path.expanduser(value.strip()))
    path = Path(expanded)
    if not path.is_absolute():
        path = base / path
    return path.resolve(strict=False)


def validate_source_paths(
    values: Mapping[str, str],
    base: Path,
    *,
    require_lightweight: bool = False,
) -> Dict[str, Path]:
    """Validate configured full/lightweight source roots without writing files."""

    result: Dict[str, Path] = {}
    lightweight = values.get("lightweight_source_code_path", "").strip()
    if require_lightweight and not lightweight:
        raise PreferenceError(
            "preferences.md must define lightweight_source_code_path."
        )
    for field in ("lightweight_source_code_path", "full_source_code_path"):
        configured = values.get(field, "").strip()
        if not configured:
            continue
        path = resolve_preference_path(configured, base)
        if not path.exists():
            raise PreferenceError(f"Configured {field} does not exist: {path}")
        if not path.is_dir():
            raise PreferenceError(f"Configured {field} is not a directory: {path}")
        if not os.access(path, os.R_OK | os.X_OK):
            raise PreferenceError(f"Configured {field} is not readable: {path}")
        result[field] = path
    return result
