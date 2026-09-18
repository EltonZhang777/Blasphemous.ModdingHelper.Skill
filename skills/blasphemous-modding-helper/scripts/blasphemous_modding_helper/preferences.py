"""Preference scope discovery and parsing shared by Skill entry points."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - the runtime gate reports this first.
    yaml = None


CONFIG_RELATIVE_PATH = Path(".skills") / "blasphemous-modding-helper" / "config.yml"
# Keep the Python symbol for callers while the active file is config.yml.
PREFERENCES_RELATIVE_PATH = CONFIG_RELATIVE_PATH
_TEXT_FIELDS = frozenset(
    {
        "full_source_code_path",
        "lightweight_source_code_path",
        "modding_profile_path",
        "unity_log_dir",
        "modding_api_reference_path",
        "modding_api_reference_selector",
    }
)


if yaml is not None:
    class _UniqueKeyLoader(yaml.SafeLoader):
        pass


    def _construct_unique_mapping(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise PreferenceError("config.yml mapping keys must be strings.")
            if key in mapping:
                raise PreferenceError(f"Duplicate config key '{key}'.")
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping


    _UniqueKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _construct_unique_mapping,
    )


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
    values: Dict[str, object]


def _parse_config(text: str) -> Dict[str, object]:
    if yaml is None:
        raise PreferenceError(
            "PyYAML is required to parse config.yml; validate the Skill runtime dependencies and retry."
        )
    try:
        values = yaml.load(text, Loader=_UniqueKeyLoader)
    except PreferenceError:
        raise
    except yaml.YAMLError as error:
        raise PreferenceError(f"Invalid config.yml: {error}") from error
    if not isinstance(values, dict) or not values:
        raise PreferenceError("config.yml must contain a non-empty top-level mapping.")
    for key in _TEXT_FIELDS:
        if key in values and not isinstance(values[key], str):
            raise PreferenceError(f"config.yml field '{key}' must be a string.")
    return values


def format_yaml_string(value: str) -> str:
    """Serialize one managed string without reformatting the whole config."""

    if yaml is None:
        raise PreferenceError(
            "PyYAML is required to write config.yml; validate the Skill runtime dependencies and retry."
        )
    serialized = yaml.safe_dump(
        value,
        default_flow_style=True,
        allow_unicode=True,
        width=4096,
    ).strip()
    if serialized.endswith("\n..."):
        serialized = serialized[:-4]
    return serialized


def preference_paths(
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Tuple[PreferenceLocation, PreferenceLocation]:
    """Return project then user locations, preserving precedence order."""

    current_directory = (cwd or Path.cwd()).expanduser().resolve(strict=False)
    user_home = (home or Path.home()).expanduser().resolve(strict=False)
    return (
        PreferenceLocation("project", current_directory / CONFIG_RELATIVE_PATH),
        PreferenceLocation("user", user_home / CONFIG_RELATIVE_PATH),
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
) -> Dict[str, object]:
    """Parse the supported top-level YAML mapping without changing the file."""

    preferences_path = Path(path).expanduser().resolve(strict=False)
    try:
        text = preferences_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PreferenceError(f"Could not read config.yml at {preferences_path}: {error}") from error

    values = _parse_config(text)

    missing = [key for key in required if key not in values]
    if missing:
        missing_text = ", ".join(missing)
        raise PreferenceError(f"config.yml at {preferences_path} must define {missing_text}.")
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
    raise PreferenceError(f"No config.yml found. Checked: {checked}")


def resolve_preference_path(value: str, base: Path) -> Path:
    """Expand a configured path relative to caller-owned working directory."""

    expanded = os.path.expandvars(os.path.expanduser(value.strip()))
    path = Path(expanded)
    if not path.is_absolute():
        path = base / path
    return path.resolve(strict=False)


def validate_source_paths(
    values: Mapping[str, object],
    base: Path,
    *,
    require_lightweight: bool = False,
) -> Dict[str, Path]:
    """Validate configured full/lightweight source roots without writing files."""

    result: Dict[str, Path] = {}
    lightweight = _text_value(values, "lightweight_source_code_path")
    if require_lightweight and not lightweight:
        raise PreferenceError(
            "config.yml must define lightweight_source_code_path."
        )
    for field in ("lightweight_source_code_path", "full_source_code_path"):
        configured = _text_value(values, field)
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


def _text_value(values: Mapping[str, object], key: str) -> str:
    value = values.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise PreferenceError(f"config.yml field '{key}' must be a string.")
    return value.strip()
