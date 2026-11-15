"""Configuration scope discovery and parsing shared by Skill entry points."""

from __future__ import annotations

import math
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - the runtime gate reports this first.
    yaml = None


CONFIG_RELATIVE_PATH = Path(".skills") / "blasphemous-modding-helper" / "config.yml"
# Keep the Python symbol for callers while the active file is config.yml.
PREFERENCES_RELATIVE_PATH = CONFIG_RELATIVE_PATH
SKILL_VERSION_PATH = Path(__file__).resolve().parents[2] / "version.yml"
DEFAULT_CHECK_PERIOD_DAYS = 7
_CHECK_PERIOD_FIELD = "check_period_days"
_LAST_CHECKED_TIME_FIELD = "last_checked_time"
_LAST_CHECKED_VERSION_FIELD = "last_checked_version"
_SEMVER_RE = re.compile(
    r"^(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[0-9A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[0-9A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_TEXT_FIELDS = frozenset(
    {
        "full_source_code_path",
        "lightweight_source_code_path",
        "modding_profile_path",
        "unity_log_dir",
        "modding_api_reference_path",
        "modding_api_reference_selector",
        "unity_project_path",
    }
)


class PreferenceError(Exception):
    """A malformed or unreadable configuration file."""


class LocatedPreferenceError(PreferenceError):
    """A preference failure tied to the selected configuration file."""

    def __init__(
        self,
        message: str,
        location: Optional["PreferenceLocation"] = None,
    ):
        super().__init__(message)
        self.location = location


class PreferenceValidationError(LocatedPreferenceError):
    """A configuration that requires first-time setup recovery."""


class UnityProjectPathError(LocatedPreferenceError):
    """An invalid Unity project path that requires only targeted retry."""


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


@dataclass(frozen=True)
class PreferenceLocation:
    """One selected configuration file and its scope."""

    scope: str
    path: Path


@dataclass(frozen=True)
class Preferences:
    """Parsed configuration with the scope that supplied it."""

    scope: str
    path: Path
    values: Dict[str, object]


@dataclass(frozen=True)
class PreferenceValidationResult:
    """Stable result for the optional freshness validation mode."""

    status: str
    scope: str
    path: Path
    version: str
    trigger: str
    check_period_days: int
    updated_fields: Tuple[str, ...]


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


def update_config_text(text: str, updates: Mapping[str, object]) -> str:
    """Update managed top-level fields without reordering caller content."""

    if not updates:
        return text
    serialized = {key: _format_config_value(value) for key, value in updates.items()}
    flow_mapping = _flow_mapping_node(text)
    if flow_mapping is not None:
        flow_serialized = {
            key: _format_flow_value(value)
            for key, value in updates.items()
        }
        return _update_flow_mapping(text, flow_mapping, flow_serialized)
    _reject_multiline_managed_values(text, serialized)
    output = []
    pending = set(serialized)
    for line in text.splitlines():
        match_key = next(
            (
                key
                for key in serialized
                if re.match(r"^" + _managed_key_pattern(key) + r"\s*:", line)
            ),
            None,
        )
        if match_key is None:
            output.append(line)
            continue
        match = re.match(
            r"^(" + _managed_key_pattern(match_key) + r")\s*:\s*(.*)$",
            line,
        )
        assert match is not None
        output.append(
            f"{match.group(1)}: {serialized[match_key]}"
            f"{_inline_comment(match.group(2))}"
        )
        pending.discard(match_key)
    additions = [
        f"{key}: {serialized[key]}"
        for key in serialized
        if key in pending
    ]
    if additions:
        for index, line in enumerate(output):
            if line.strip() == "...":
                output[index:index] = additions
                break
        else:
            output.extend(additions)
    return "\n".join(output) + "\n"


def _flow_mapping_node(text: str):
    if yaml is None:
        return None
    try:
        node = yaml.compose(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError:
        return None
    if not isinstance(node, yaml.MappingNode) or not node.flow_style:
        return None
    return node


def _reject_multiline_managed_values(text: str, managed: Mapping[str, str]) -> None:
    if yaml is None:
        return
    try:
        node = yaml.compose(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError:
        return
    if not isinstance(node, yaml.MappingNode):
        return
    for key_node, value_node in node.value:
        if not isinstance(key_node, yaml.ScalarNode) or key_node.value not in managed:
            continue
        if (
            not isinstance(value_node, yaml.ScalarNode)
            or value_node.start_mark.line != value_node.end_mark.line
        ):
            raise PreferenceError(
                f"Cannot safely update multi-line config value '{key_node.value}'; "
                "edit config.yml or rerun first-time setup."
            )


def _update_flow_mapping(text: str, node, serialized: Mapping[str, str]) -> str:
    replacements = []
    present = set()
    for key_node, value_node in node.value:
        if not isinstance(key_node, yaml.ScalarNode) or key_node.value not in serialized:
            continue
        present.add(key_node.value)
        replacements.append(
            (
                value_node.start_mark.index,
                value_node.end_mark.index,
                serialized[key_node.value],
            )
        )
    for start, end, value in sorted(replacements, reverse=True):
        text = text[:start] + value + text[end:]
    additions = [
        f"{key}: {value}"
        for key, value in serialized.items()
        if key not in present
    ]
    if additions:
        node = _flow_mapping_node(text)
        if node is None:
            raise PreferenceError("Could not update flow-style config.yml.")
        closing = text.rfind("}", 0, node.end_mark.index)
        if closing < 0:
            raise PreferenceError("Could not update flow-style config.yml.")
        addition_text = ", ".join(additions)
        if node.value:
            value_end = node.value[-1][1].end_mark.index
            comma = _flow_separator(text[value_end:closing])
            if comma is None:
                text = text[:value_end] + ", " + addition_text + text[value_end:]
            else:
                insertion = value_end + comma + 1
                spacer = "" if text[insertion:insertion + 1].isspace() else " "
                text = text[:insertion] + spacer + addition_text + text[insertion:]
        else:
            text = text[:closing] + addition_text + text[closing:]
    try:
        _parse_config(text)
    except PreferenceError as error:
        raise PreferenceError(f"Automated config update would make config.yml invalid: {error}") from error
    return text


def _format_config_value(value: object) -> str:
    if isinstance(value, str):
        return format_yaml_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    raise PreferenceError(f"Unsupported managed config value type: {type(value).__name__}.")


def _managed_key_pattern(key: str) -> str:
    escaped = re.escape(key)
    return rf"(?:{escaped}|'{escaped}'|\"{escaped}\")"


def _flow_separator(tail: str) -> Optional[int]:
    in_comment = False
    for index, character in enumerate(tail):
        if character == "\n":
            in_comment = False
        elif in_comment:
            continue
        elif character == "#" and (index == 0 or tail[index - 1].isspace()):
            in_comment = True
        elif character == ",":
            return index
    return None


def _format_flow_value(value: object) -> str:
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return _format_config_value(value)


def _inline_comment(value: str) -> str:
    quote = None
    escaped = False
    for index, character in enumerate(value):
        if quote == '"' and escaped:
            escaped = False
            continue
        if quote == '"' and character == "\\":
            escaped = True
            continue
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in ("'", '"'):
            quote = character
        elif character == "#" and index > 0 and value[index - 1].isspace():
            return value[index - 1 :]
    return ""


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
    """Select the first existing configuration location: project, then user."""

    for location in preference_paths(cwd, home):
        if location.path.exists():
            return location
    return None


def preference_scope(
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Optional[str]:
    """Return selected scope or ``None`` when no configuration file exists."""

    location = find_preferences(cwd, home)
    return location.scope if location is not None else None


def parse_preferences(
    path: Path,
    *,
    required: Iterable[str] = (),
) -> Dict[str, object]:
    """Parse the supported top-level YAML mapping without changing the file."""

    preferences_path, _, values = _read_config(path)
    missing = [key for key in required if key not in values]
    if missing:
        missing_text = ", ".join(missing)
        raise PreferenceError(f"config.yml at {preferences_path} must define {missing_text}.")
    return values


def _read_config(path: Path) -> Tuple[Path, str, Dict[str, object]]:
    preferences_path = Path(path).expanduser().resolve(strict=False)
    try:
        text = preferences_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PreferenceError(f"Could not read config.yml at {preferences_path}: {error}") from error

    return preferences_path, text, _parse_config(text)


def read_skill_version(version_path: Optional[Path] = None) -> str:
    """Read and validate the installed Skill's exact version."""

    source = Path(version_path or SKILL_VERSION_PATH).expanduser().resolve(strict=False)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PreferenceValidationError(
            f"Skill version source is unavailable at {source}: {error}"
        ) from error
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(
            r"^version\s*:\s*['\"]?([^'\"#\s]+)['\"]?(?:\s+#.*)?$",
            line,
        )
        if match is None:
            continue
        version = match.group(1)
        if not _SEMVER_RE.fullmatch(version):
            raise PreferenceValidationError(
                f"Skill version source contains invalid SemVer '{version}'."
            )
        return version
    raise PreferenceValidationError(f"Skill version source has no version key: {source}")


def _normalize_check_period(values: Mapping[str, object]) -> Tuple[int, bool]:
    if _CHECK_PERIOD_FIELD not in values:
        return DEFAULT_CHECK_PERIOD_DAYS, True
    raw = values[_CHECK_PERIOD_FIELD]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise PreferenceValidationError(
            "check_period_days must be a positive finite number."
        )
    if isinstance(raw, float):
        if not math.isfinite(raw):
            raise PreferenceValidationError(
                "check_period_days must be a positive finite number."
            )
        normalized = math.floor(raw)
        needs_write = True
    else:
        normalized = raw
        needs_write = False
    if normalized <= 0:
        raise PreferenceValidationError(
            "check_period_days must remain positive after normalization."
        )
    try:
        timedelta(days=normalized)
    except OverflowError as error:
        raise PreferenceValidationError(
            "check_period_days exceeds the supported date range."
        ) from error
    return int(normalized), needs_write


def _parse_checked_time(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        return value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _utc_now(value: Optional[datetime]) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _format_checked_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _validation_trigger(
    values: Mapping[str, object],
    current_version: str,
    period_days: int,
    period_missing: bool,
    period_needs_write: bool,
    now: datetime,
) -> Optional[str]:
    version_present = _LAST_CHECKED_VERSION_FIELD in values
    time_present = _LAST_CHECKED_TIME_FIELD in values
    if not version_present and not time_present:
        return "first-validation"
    if not version_present or not time_present:
        return "metadata-missing"
    last_version = values[_LAST_CHECKED_VERSION_FIELD]
    if not isinstance(last_version, str) or not last_version.strip():
        return "metadata-invalid"
    if last_version != current_version:
        return "version-changed"
    checked_at = _parse_checked_time(values[_LAST_CHECKED_TIME_FIELD])
    if checked_at is None or checked_at > now:
        return "metadata-invalid"
    if now - checked_at > timedelta(days=period_days):
        return "period-elapsed"
    if period_missing:
        return "period-missing"
    if period_needs_write:
        return "period-normalized"
    return None


def _atomic_write_config(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_preferences(
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
    *,
    now: Optional[datetime] = None,
    version_path: Optional[Path] = None,
) -> PreferenceValidationResult:
    """Run freshness-gated validation and preserve unrelated config content."""

    location = find_preferences(cwd, home)
    if location is None:
        raise PreferenceValidationError(
            "No config.yml found. Complete first-time setup before continuing."
        )
    if not location.path.is_file():
        raise PreferenceValidationError(
            f"Configuration path is not a file: {location.path}",
            location,
        )
    try:
        _, text, values = _read_config(location.path)
        current_version = read_skill_version(version_path)
        period_days, period_needs_write = _normalize_check_period(values)
    except PreferenceValidationError as error:
        if error.location is not None:
            raise
        raise PreferenceValidationError(str(error), location) from error
    except PreferenceError as error:
        raise PreferenceValidationError(str(error), location) from error
    period_missing = _CHECK_PERIOD_FIELD not in values
    current_time = _utc_now(now)
    trigger = _validation_trigger(
        values,
        current_version,
        period_days,
        period_missing,
        period_needs_write,
        current_time,
    )
    if trigger is None:
        return PreferenceValidationResult(
            "skipped",
            location.scope,
            location.path,
            current_version,
            "within-period",
            period_days,
            (),
        )

    updates: Dict[str, object] = {
        _LAST_CHECKED_TIME_FIELD: _format_checked_time(current_time),
        _LAST_CHECKED_VERSION_FIELD: current_version,
    }
    if period_needs_write:
        updates[_CHECK_PERIOD_FIELD] = period_days
    updated_text = update_config_text(text, updates)
    try:
        _atomic_write_config(location.path, updated_text)
    except OSError as error:
        raise PreferenceValidationError(
            f"Could not write validated config.yml at {location.path}: {error}"
        ) from error
    return PreferenceValidationResult(
        "normalized" if period_needs_write else "passed",
        location.scope,
        location.path,
        current_version,
        trigger,
        period_days,
        tuple(updates),
    )


def load_preferences(
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
    *,
    required: Iterable[str] = (),
) -> Preferences:
    """Select and parse project/user configuration without writing either file."""

    locations = preference_paths(cwd, home)
    for location in locations:
        if not location.path.exists():
            continue
        if not location.path.is_file():
            raise PreferenceError(f"Configuration path is not a file: {location.path}")
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
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise PreferenceError(f"Configured path could not be resolved: {path}: {error}") from error


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


def validate_unity_project_path(path: Path) -> Path:
    """Validate an exported Unity project root without reading its assets."""

    from .unity_project import NavigationError, validate_project_root

    try:
        return validate_project_root(Path(path))
    except NavigationError as error:
        raise PreferenceError(str(error)) from error


def set_unity_project_path(
    value: str,
    *,
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Tuple[PreferenceLocation, Path]:
    """Validate and add only unity_project_path to the active configuration."""

    location = find_preferences(cwd, home)
    if location is None:
        raise PreferenceValidationError(
            "No config.yml found. Complete first-time setup before configuring the Unity project."
        )
    try:
        _, text, _ = _read_config(location.path)
    except PreferenceError as error:
        raise PreferenceValidationError(str(error), location) from error
    try:
        try:
            if not value.strip():
                raise PreferenceError("path is empty")
            resolved = resolve_preference_path(value, cwd or Path.cwd())
            project = validate_unity_project_path(resolved)
        except PreferenceError as error:
            raise UnityProjectPathError(
                f"Invalid unity_project_path: {error}",
                location,
            ) from error
        updated_text = update_config_text(
            text,
            {"unity_project_path": str(project)},
        )
        _atomic_write_config(location.path, updated_text)
    except UnityProjectPathError:
        raise
    except (OSError, PreferenceError) as error:
        raise PreferenceValidationError(str(error), location) from error
    return location, project


def _text_value(values: Mapping[str, object], key: str) -> str:
    value = values.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise PreferenceError(f"config.yml field '{key}' must be a string.")
    return value.strip()
