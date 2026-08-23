#!/usr/bin/env python3
"""Profile-aware entry point for the Blasphemous mod test workflow.

This workflow validates the invocation environment, resolves preferences and
a project, preflights a modding profile, builds or selects one package,
deploys a validated artifact, tracks the profile-local game process, and
collects current startup evidence from the existing game logs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Dict, Iterator, List, Optional, Sequence, Tuple


EXIT_SUCCESS = 0
EXIT_USAGE = 2
EXIT_PROFILE = 10
EXIT_BUILD = 20
EXIT_PACKAGE = 30
EXIT_DEPLOY = 40
EXIT_LAUNCH = 50
EXIT_LOGS = 60
EXIT_CLEAN = 70
LAUNCH_GRACE_PERIOD_SECONDS = 0.5
PROCESS_POLL_INTERVAL_SECONDS = 0.05
DEFAULT_LOG_LINES = 200
STARTUP_POLL_INTERVAL_SECONDS = 0.25


class CliError(Exception):
    """A user-facing CLI failure with a stable exit-code category."""

    def __init__(self, code: int, category: str, message: str):
        super().__init__(message)
        self.code = code
        self.category = category


@dataclass(frozen=True)
class Preferences:
    scope: str
    path: Path
    values: Dict[str, str]


@dataclass(frozen=True)
class ProfilePreflight:
    profile: Path
    launcher: Path
    modding_root: Path
    bepinex_root: Path
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class InvocationContext:
    environment: str
    preferences: Preferences
    project: Optional[Path]
    profile: ProfilePreflight


@dataclass(frozen=True)
class ArtifactPlan:
    configuration: str
    target_name: str
    solution_root: Path
    publish_directory: Path
    artifact: Path
    artifact_kind: str
    package_root: Path
    relative_files: Tuple[Path, ...]


@dataclass(frozen=True)
class DeploymentOperation:
    relative_path: Path
    source: Path
    destination: Path
    existed: bool


@dataclass(frozen=True)
class DeploymentResult:
    session_id: str
    state_path: Path
    deployed_files: Tuple[Path, ...]


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    start_token: str
    executable: Optional[Path]


@dataclass(frozen=True)
class LaunchResult:
    session_id: str
    state_path: Path
    pid: int


@dataclass(frozen=True)
class StopResult:
    session_id: str
    state: str


@dataclass(frozen=True)
class CleanResult:
    session_id: str
    state: str
    restored_files: Tuple[Path, ...]
    removed_files: Tuple[Path, ...]
    retained_files: Tuple[Path, ...]
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class LogEvidenceSource:
    label: str
    path: Optional[Path]
    exists: bool
    current: bool
    total_lines: int
    output_lines: Tuple[str, ...]
    evidence_lines: Tuple[str, ...]
    warning: Optional[str]


@dataclass(frozen=True)
class EvidenceReport:
    state: str
    ready: bool
    mod_loaded: bool
    timed_out: bool
    sources: Tuple[LogEvidenceSource, ...]
    warnings: Tuple[str, ...]


@dataclass
class DeploymentTransaction:
    session_id: str
    session_directory: Path
    state_path: Path
    profile: Path
    modding_root: Path
    plan: ArtifactPlan
    operations: Tuple[DeploymentOperation, ...]
    planned_directories: Tuple[Path, ...]
    records: List[Dict[str, object]]
    created_directories: List[Path]
    created_at: str


def _preference_paths(cwd: Path, home: Path) -> Tuple[Tuple[str, Path], ...]:
    relative_path = Path(".skills") / "blasphemous-modding-helper" / "preferences.md"
    return (("project", cwd / relative_path), ("user", home / relative_path))


def _parse_preferences(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise CliError(
            EXIT_PROFILE,
            "profile/preferences",
            f"Could not read preferences.md at {path}: {error}",
        ) from error

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            raise CliError(
                EXIT_PROFILE,
                "profile/preferences",
                f"Invalid preferences.md line {line_number}: expected 'key: value'.",
            )
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise CliError(
                EXIT_PROFILE,
                "profile/preferences",
                f"Invalid preferences.md line {line_number}: key and value are required.",
            )
        if key in values:
            raise CliError(
                EXIT_PROFILE,
                "profile/preferences",
                f"Duplicate preference '{key}' on line {line_number}.",
            )
        values[key] = value

    if "modding_profile_path" not in values:
        raise CliError(
            EXIT_PROFILE,
            "profile/preferences",
            f"preferences.md at {path} must define modding_profile_path.",
        )
    return values


def load_preferences(cwd: Optional[Path] = None, home: Optional[Path] = None) -> Preferences:
    """Load project preferences before user preferences without writing either."""

    current_directory = (cwd or Path.cwd()).resolve()
    user_home = (home or Path.home()).resolve()
    candidates = _preference_paths(current_directory, user_home)

    for scope, path in candidates:
        if not path.exists():
            continue
        if not path.is_file():
            raise CliError(
                EXIT_PROFILE,
                "profile/preferences",
                f"Preference path is not a file: {path}",
            )
        return Preferences(scope, path, _parse_preferences(path))

    locations = ", ".join(str(path) for _, path in candidates)
    raise CliError(
        EXIT_PROFILE,
        "profile/preferences",
        f"No preferences.md found. Complete first-time setup before running the test CLI. Checked: {locations}",
    )


def _unity_log_filenames(environment: str) -> Tuple[str, ...]:
    if environment == "Windows":
        return ("output_log.txt",)
    return ("Player.log", "output_log.txt")


def resolve_unity_log_path(
    preferences: Preferences,
    environment: str,
    explicit_directory: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve the configured Unity log file and return a handoff warning."""

    configured = explicit_directory or preferences.values.get("unity_log_dir")
    if not configured:
        return None, (
            "Unity log directory is not configured. Ask the user for the Unity "
            "log directory, then add 'unity_log_dir: PATH' to the active "
            f"preferences.md: {preferences.path}"
        )

    directory = _expand_path(configured, cwd or Path.cwd())
    if directory.exists() and not directory.is_dir():
        return None, (
            f"Configured unity_log_dir is not a directory: {directory}. Ask the "
            "user for the directory containing the Unity log and update "
            f"{preferences.path}."
        )

    filenames = _unity_log_filenames(environment)
    for filename in filenames:
        candidate = directory / filename
        if candidate.is_file():
            return candidate, None

    expected = ", ".join(str(directory / filename) for filename in filenames)
    if not directory.exists():
        reason = f"Configured Unity log directory does not exist: {directory}."
    else:
        reason = f"Unity log was not found under configured directory: {directory}."
    return directory / filenames[0], (
        f"{reason} Expected {expected}. Ask the user for the correct directory, "
        "then add or update 'unity_log_dir: PATH' in the active "
        f"preferences.md: {preferences.path}."
    )


def _log_signature(path: Path) -> Optional[Dict[str, object]]:
    try:
        if not path.is_file():
            return None
        stat_result = path.stat()
    except OSError:
        return None
    return {
        "exists": True,
        "mtime_ns": int(stat_result.st_mtime_ns),
        "size": int(stat_result.st_size),
    }


def _capture_log_baselines(paths: Sequence[Path]) -> Dict[str, Dict[str, object]]:
    baselines: Dict[str, Dict[str, object]] = {}
    for index, path in enumerate(paths):
        key = "bepinex" if index == 0 else "unity" if index == 1 else f"log_{index}"
        normalized = path.resolve(strict=False)
        signature = _log_signature(normalized)
        baselines[key] = signature or {
            "exists": False,
            "mtime_ns": None,
            "size": None,
        }
    return baselines


def _expand_path(value: str, base: Path, *, resolve: bool = True) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value.strip()))
    path = Path(expanded)
    if not path.is_absolute():
        path = base / path
    return path.resolve(strict=False) if resolve else path


def _project_candidates(cwd: Path) -> List[Path]:
    try:
        candidates = [
            path.resolve()
            for path in cwd.iterdir()
            if path.is_file() and path.suffix.lower() == ".csproj"
        ]
    except OSError as error:
        raise CliError(
            EXIT_USAGE,
            "usage/configuration",
            f"Could not inspect the current directory for .csproj projects: {error}",
        ) from error
    return sorted(candidates, key=lambda path: path.name.lower())


def select_project(cwd: Path, explicit_project: Optional[str]) -> Path:
    """Select exactly one project, or reject an ambiguous implicit selection."""

    if explicit_project:
        project = _expand_path(explicit_project, cwd)
        if project.suffix.lower() != ".csproj":
            raise CliError(
                EXIT_USAGE,
                "usage/configuration",
                f"The selected project must end in .csproj: {project}",
            )
        if not project.is_file():
            raise CliError(
                EXIT_USAGE,
                "usage/configuration",
                f"The selected project does not exist: {project}",
            )
        return project

    candidates = _project_candidates(cwd)
    if not candidates:
        raise CliError(
            EXIT_USAGE,
            "usage/configuration",
            "No .csproj project was found in the current directory; pass --project PATH.",
        )
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise CliError(
            EXIT_USAGE,
            "usage/configuration",
            f"Multiple .csproj projects were found ({names}); pass --project PATH.",
        )
    return candidates[0]


def select_optional_project(cwd: Path, explicit_project: Optional[str]) -> Optional[Path]:
    if explicit_project:
        return select_project(cwd, explicit_project)
    candidates = _project_candidates(cwd)
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise CliError(
            EXIT_USAGE,
            "usage/configuration",
            f"Multiple .csproj projects were found ({names}); pass --project PATH.",
        )
    return candidates[0] if candidates else None


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_project_target_name(project: Path, configuration: str) -> str:
    """Read the deterministic package name declared by a project file."""

    try:
        root = ET.parse(project).getroot()
    except (OSError, ET.ParseError, UnicodeError) as error:
        raise CliError(
            EXIT_BUILD,
            "build",
            f"Could not parse project file {project}: {error}",
        ) from error

    fallback: Optional[str] = None
    for property_group in root.iter():
        if _xml_local_name(property_group.tag) != "PropertyGroup":
            continue
        condition = property_group.attrib.get("Condition", "")
        for property_node in property_group:
            if _xml_local_name(property_node.tag) != "TargetName":
                continue
            value = (property_node.text or "").strip()
            if not value:
                continue
            if configuration.lower() in condition.lower():
                fallback = value
                break
            if not condition and fallback is None:
                fallback = value

    if not fallback:
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Project does not declare a TargetName: {project}",
        )
    if (
        fallback in {".", ".."}
        or any(
            character in fallback
            for character in ("/", "\\", ":", "*", "?", '"', "<", ">", "|")
        )
        or fallback.rstrip(" .") != fallback
        or "$(" in fallback
    ):
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Project TargetName is not a safe package name: {fallback}",
        )
    return fallback


def find_solution_root(project: Path) -> Path:
    """Find the nearest solution directory used by the publish convention."""

    for parent in (project.parent, *project.parent.parents):
        try:
            if any(
                entry.is_file() and entry.suffix.lower() == ".sln"
                for entry in parent.iterdir()
            ):
                return parent
        except OSError:
            return project.parent
    return project.parent


def build_project(project: Path, configuration: str, solution_root: Path) -> None:
    command = ["dotnet", "build", str(project), "--configuration", configuration]
    build_environment = os.environ.copy()
    # The reference projects use $(SolutionDir) in their post-build publish
    # target, but direct project builds do not receive that Visual Studio
    # property automatically. Keep the documented command unchanged while
    # supplying the deterministic solution root through MSBuild's environment.
    build_environment["SolutionDir"] = str(solution_root) + os.sep
    try:
        result = subprocess.run(
            command,
            cwd=solution_root,
            env=build_environment,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise CliError(
            EXIT_BUILD,
            "build",
            f"Could not start dotnet build: {error}",
        ) from error

    if result.returncode == 0:
        return
    details = "\n".join(
        output.strip()
        for output in (result.stdout, result.stderr)
        if output and output.strip()
    )
    suffix = f"\n{details}" if details else ""
    raise CliError(
        EXIT_BUILD,
        "build",
        f"Build failed with exit code {result.returncode}: {' '.join(command)}{suffix}",
    )


def _first_symlink_component(path: Path) -> Optional[Path]:
    for component in (path, *path.parents):
        if component.is_symlink():
            return component
    return None


def _reject_symlink_path(path: Path) -> None:
    """Reject a path whose existing components could redirect artifact reads."""

    try:
        link = _first_symlink_component(path)
    except OSError as error:
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Could not inspect package path {path}: {error}",
        ) from error
    if link is not None:
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Package paths cannot contain symlinks: {link}",
        )


def _safe_relative_path(relative_path: Path) -> None:
    if relative_path.is_absolute() or any(
        part in {"", ".", ".."} for part in relative_path.parts
    ):
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Unsafe package-relative path: {relative_path}",
        )


def _validate_unique_relative_files(relative_files: Sequence[Path]) -> Tuple[Path, ...]:
    """Reject package files that collide on case-insensitive file systems."""

    seen: Dict[str, Path] = {}
    for relative_file in relative_files:
        key = relative_file.as_posix().casefold()
        previous = seen.get(key)
        if (
            previous is not None
            and previous.as_posix() != relative_file.as_posix()
        ):
            raise CliError(
                EXIT_PACKAGE,
                "package artifact",
                f"Ambiguous package paths: {previous} and {relative_file}",
            )
        seen[key] = relative_file
    return tuple(
        sorted(relative_files, key=lambda path: path.as_posix().casefold())
    )


def validate_package_directory(package_root: Path) -> Tuple[Path, ...]:
    """Validate a directory package and return every file relative to its root."""

    _reject_symlink_path(package_root)
    if not package_root.exists():
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Package root does not exist: {package_root}",
        )
    if not package_root.is_dir():
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Package root is not a directory: {package_root}",
        )

    files: List[Path] = []
    for current, directories, filenames in os.walk(package_root, followlinks=False):
        current_path = Path(current)
        for name in (*directories, *filenames):
            candidate = current_path / name
            relative_path = candidate.relative_to(package_root)
            _safe_relative_path(relative_path)
            if candidate.is_symlink():
                raise CliError(
                    EXIT_PACKAGE,
                    "package artifact",
                    f"Package links are not allowed: {relative_path}",
                )
        for name in filenames:
            candidate = current_path / name
            if not candidate.is_file():
                raise CliError(
                    EXIT_PACKAGE,
                    "package artifact",
                    f"Package contains a non-file entry: {candidate}",
                )
            files.append(candidate.relative_to(package_root))

    if not files:
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"The package contains no files: {package_root}",
        )
    return _validate_unique_relative_files(files)


def _safe_zip_parts(name: str) -> Tuple[str, ...]:
    normalized = name.replace("\\", "/")
    if (
        not normalized
        or normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Unsafe archive path: {name}",
        )
    parts = normalized.split("/")
    if parts and parts[-1] == "":
        parts.pop()
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Unsafe archive path: {name}",
        )
    return tuple(parts)


def _zip_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return mode == stat.S_IFLNK


def _extract_archive(archive: Path, extraction_root: Path) -> None:
    try:
        with zipfile.ZipFile(archive) as package:
            seen: Dict[str, str] = {}
            for info in package.infolist():
                parts = _safe_zip_parts(info.filename)
                relative_name = PurePosixPath(*parts).as_posix()
                key = relative_name.casefold()
                if key in seen:
                    raise CliError(
                        EXIT_PACKAGE,
                        "package artifact",
                        f"Ambiguous archive paths: {seen[key]} and {info.filename}",
                    )
                seen[key] = relative_name
                if _zip_symlink(info):
                    raise CliError(
                        EXIT_PACKAGE,
                        "package artifact",
                        f"Archive links are not allowed: {info.filename}",
                    )
                target = extraction_root.joinpath(*parts)
                if not _is_within(target.resolve(strict=False), extraction_root.resolve()):
                    raise CliError(
                        EXIT_PACKAGE,
                        "package artifact",
                        f"Archive path escapes its extraction root: {info.filename}",
                    )
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with package.open(info) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
    except CliError:
        raise
    except (OSError, zipfile.BadZipFile) as error:
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Could not read archive {archive}: {error}",
        ) from error


@contextmanager
def prepare_artifact(
    project: Path,
    configuration: str,
    explicit_artifact: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> Iterator[ArtifactPlan]:
    """Build or select one package and validate its complete file plan."""

    target_name = read_project_target_name(project, configuration)
    solution_root = find_solution_root(project)
    publish_directory = solution_root / "publish"
    artifact_value = None
    if explicit_artifact:
        artifact_input = _expand_path(
            explicit_artifact,
            cwd or Path.cwd(),
            resolve=False,
        )
        _reject_symlink_path(artifact_input)
        artifact_value = artifact_input.resolve(strict=False)

    if artifact_value is None:
        package_root = publish_directory / target_name
        _reject_symlink_path(package_root)
        build_project(project, configuration, solution_root)
        relative_files = validate_package_directory(package_root)
        yield ArtifactPlan(
            configuration,
            target_name,
            solution_root,
            publish_directory,
            package_root,
            "directory",
            package_root,
            relative_files,
        )
        return

    if not artifact_value.exists():
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Explicit artifact does not exist: {artifact_value}",
        )
    if artifact_value.is_dir():
        relative_files = validate_package_directory(artifact_value)
        yield ArtifactPlan(
            configuration,
            target_name,
            solution_root,
            publish_directory,
            artifact_value,
            "directory",
            artifact_value,
            relative_files,
        )
        return
    if artifact_value.suffix.lower() != ".zip" or not artifact_value.is_file():
        raise CliError(
            EXIT_PACKAGE,
            "package artifact",
            f"Explicit artifact must be a directory or .zip archive: {artifact_value}",
        )

    with tempfile.TemporaryDirectory(prefix="blasphemous-modding-test-") as temporary:
        extraction_root = Path(temporary)
        _extract_archive(artifact_value, extraction_root)
        relative_files = validate_package_directory(extraction_root)
        yield ArtifactPlan(
            configuration,
            target_name,
            solution_root,
            publish_directory,
            artifact_value,
            "archive",
            extraction_root,
            relative_files,
        )


def _deployment_state_root() -> Path:
    return Path(tempfile.gettempdir()) / "blasphemous-modding-test" / "sessions"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_hard_linked_destination(path: Path) -> None:
    if path.is_symlink():
        raise OSError(f"deployment target is a symlink: {path}")
    try:
        hard_linked = path.exists() and path.is_file() and path.stat().st_nlink > 1
    except OSError as error:
        raise OSError(f"could not inspect deployment target {path}: {error}") from error
    if hard_linked:
        raise OSError(f"deployment target has multiple hard links: {path}")


def _reject_unsafe_deployment_destination(path: Path) -> None:
    try:
        link = _first_symlink_component(path)
    except OSError as error:
        raise OSError(f"could not inspect deployment path {path}: {error}") from error
    if link is not None:
        raise OSError(f"deployment path contains a symlink: {link}")
    _reject_hard_linked_destination(path)


def _plan_deployment_operations(
    profile: ProfilePreflight,
    plan: ArtifactPlan,
) -> Tuple[Tuple[DeploymentOperation, ...], Tuple[Path, ...]]:
    """Validate every destination before creating any profile directory."""

    modding_root = profile.modding_root
    if not modding_root.is_dir():
        raise CliError(
            EXIT_DEPLOY,
            "deployment",
            f"Selected Modding root is not a directory: {modding_root}",
        )
    try:
        root_link = _first_symlink_component(modding_root)
    except OSError as error:
        raise CliError(
            EXIT_DEPLOY,
            "deployment",
            f"Could not inspect Modding root: {error}",
        ) from error
    if root_link is not None:
        raise CliError(
            EXIT_DEPLOY,
            "deployment",
            f"Modding paths cannot contain symlinks: {root_link}",
        )

    try:
        resolved_root = modding_root.resolve()
    except OSError as error:
        raise CliError(
            EXIT_DEPLOY,
            "deployment",
            f"Could not resolve Modding root: {error}",
        ) from error
    operations: List[DeploymentOperation] = []
    missing_directories = set()
    for relative_path in plan.relative_files:
        source = plan.package_root / relative_path
        destination = modding_root / relative_path
        if not source.is_file() or source.is_symlink():
            raise CliError(
                EXIT_DEPLOY,
                "deployment",
                f"Artifact changed after validation; source file is unavailable: {relative_path}",
            )
        try:
            resolved_destination = destination.resolve(strict=False)
        except OSError as error:
            raise CliError(
                EXIT_DEPLOY,
                "deployment",
                f"Could not resolve deployment path {destination}: {error}",
            ) from error
        if not _is_within(resolved_destination, resolved_root):
            raise CliError(
                EXIT_DEPLOY,
                "deployment",
                f"Package path escapes the selected Modding root: {relative_path}",
            )
        try:
            _reject_unsafe_deployment_destination(destination)
        except OSError as error:
            raise CliError(
                EXIT_DEPLOY,
                "deployment",
                str(error),
            ) from error

        parent_relative = destination.parent.relative_to(modding_root)
        current = modding_root
        for part in parent_relative.parts:
            current /= part
            if current.is_symlink():
                raise CliError(
                    EXIT_DEPLOY,
                    "deployment",
                    f"Deployment directory cannot be a symlink: {current}",
                )
            if current.exists() and not current.is_dir():
                raise CliError(
                    EXIT_DEPLOY,
                    "deployment",
                    f"Deployment path is not a directory: {current}",
                )
            if not current.exists():
                missing_directories.add(current)

        if destination.exists():
            if not destination.is_file():
                raise CliError(
                    EXIT_DEPLOY,
                    "deployment",
                    f"Deployment target is not a regular file: {destination}",
                )
            existed = True
        else:
            existed = False
        operations.append(
            DeploymentOperation(relative_path, source, destination, existed)
        )

    return (
        tuple(operations),
        tuple(
            sorted(
                missing_directories,
                key=lambda path: (len(path.parts), path.as_posix().casefold()),
            )
        ),
    )


def _manifest_payload(
    transaction: DeploymentTransaction,
    status: str,
    error: Optional[str] = None,
    rollback_error: Optional[str] = None,
) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "version": 1,
        "session_id": transaction.session_id,
        "status": status,
        "session_state": "active",
        "cleanup_state": "pending",
        "created_at": transaction.created_at,
        "profile": str(transaction.profile),
        "modding_root": str(transaction.modding_root),
        "configuration": transaction.plan.configuration,
        "target_name": transaction.plan.target_name,
        "artifact": str(transaction.plan.artifact),
        "artifact_kind": transaction.plan.artifact_kind,
        "package_root": str(transaction.plan.package_root),
        "planned_files": [
            relative_path.as_posix()
            for relative_path in transaction.plan.relative_files
        ],
        "planned_directories": [
            path.relative_to(transaction.modding_root).as_posix()
            for path in transaction.planned_directories
        ],
        "created_directories": [
            path.relative_to(transaction.modding_root).as_posix()
            for path in transaction.created_directories
        ],
        "files": transaction.records,
    }
    if error is not None:
        payload["error"] = error
    if rollback_error is not None:
        payload["rollback_error"] = rollback_error
    return payload


def _atomic_write_json(path: Path, payload: Dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _write_manifest(
    transaction: DeploymentTransaction,
    status: str,
    error: Optional[str] = None,
    rollback_error: Optional[str] = None,
) -> None:
    _atomic_write_json(
        transaction.state_path,
        _manifest_payload(transaction, status, error, rollback_error),
    )


def _read_session_manifest(state_path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Could not read session state {state_path}: {error}",
        ) from error
    if not isinstance(payload, dict):
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session state is not an object: {state_path}",
        )
    return payload


def _profile_paths_match(first: Path, second: Path) -> bool:
    first_value = first.resolve(strict=False).as_posix().casefold()
    second_value = second.resolve(strict=False).as_posix().casefold()
    return first_value == second_value


def _session_cleanup_state(payload: Dict[str, object]) -> str:
    value = str(payload.get("cleanup_state", "pending"))
    return value if value in {"pending", "cleaned"} else "pending"


def _session_is_cleanable(payload: Dict[str, object]) -> bool:
    return (
        _session_cleanup_state(payload) != "cleaned"
        and str(payload.get("status", ""))
        not in {"rolled_back", "rollback_failed"}
    )


def _session_sort_key(entry: Tuple[Path, Dict[str, object]]) -> Tuple[str, int, str]:
    state_path, payload = entry
    try:
        modified = state_path.stat().st_mtime_ns
    except OSError:
        modified = 0
    return (
        str(payload.get("created_at", "")),
        modified,
        state_path.parent.name,
    )


def _session_entries(
    profile: Optional[Path] = None,
) -> Tuple[Tuple[Path, Dict[str, object]], ...]:
    state_root = _deployment_state_root()
    if not state_root.is_dir():
        return ()
    entries: List[Tuple[Path, Dict[str, object]]] = []
    try:
        state_paths = tuple(state_root.glob("*/manifest.json"))
    except OSError as error:
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Could not list test sessions under {state_root}: {error}",
        ) from error
    for state_path in state_paths:
        payload = _read_session_manifest(state_path)
        if profile is not None:
            recorded_profile = payload.get("profile")
            if not recorded_profile or not _profile_paths_match(
                Path(str(recorded_profile)),
                profile,
            ):
                continue
        entries.append((state_path, payload))
    entries.sort(key=_session_sort_key, reverse=True)
    return tuple(entries)


def _session_role(
    payload: Dict[str, object],
    newest: bool,
) -> str:
    if _session_cleanup_state(payload) == "cleaned":
        return "cleaned"
    role = str(payload.get("session_state", ""))
    if role in {"active", "archived"}:
        return role
    return "active" if newest else "archived"


def _archive_previous_sessions(profile: Path, current_session_id: str) -> Tuple[str, ...]:
    changes: List[Tuple[Path, str, Dict[str, object], str]] = []
    for state_path, payload in _session_entries(profile):
        session_id = str(payload.get("session_id", state_path.parent.name))
        if session_id == current_session_id or not _session_is_cleanable(payload):
            continue

        process_value = payload.get("process")
        if isinstance(process_value, dict) and str(process_value.get("state", "")) == "launched":
            try:
                identity = ProcessIdentity(
                    int(process_value["pid"]),
                    str(process_value["start_token"]),
                    Path(str(process_value["launcher"])),
                )
            except (KeyError, TypeError, ValueError) as error:
                raise CliError(
                    EXIT_LAUNCH,
                    "launch",
                    f"Could not archive session {session_id}; its tracked process state is incomplete: {error}",
                ) from error
            if _tracked_process_is_alive(identity):
                raise CliError(
                    EXIT_LAUNCH,
                    "launch",
                    f"Session {session_id} still tracks a running game process; stop it before starting another run.",
                )
            process_value["state"] = "exited"
            process_value["recorded_at"] = datetime.now(timezone.utc).isoformat()

        payload["session_state"] = "archived"
        payload["archived_at"] = datetime.now(timezone.utc).isoformat()
        try:
            original = state_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise CliError(
                EXIT_DEPLOY,
                "deployment",
                f"Could not prepare archive state for previous session {session_id}: {error}",
            ) from error
        changes.append((state_path, original, payload, session_id))

    try:
        for state_path, _, payload, _ in changes:
            _atomic_write_json(state_path, payload)
    except OSError as error:
        for state_path, original, _, _ in changes:
            try:
                state_path.write_text(original, encoding="utf-8")
            except OSError:
                pass
        session_text = ", ".join(item[3] for item in changes)
        raise CliError(
            EXIT_DEPLOY,
            "deployment",
            f"Could not archive previous session state ({session_text}): {error}",
        ) from error
    return tuple(item[3] for item in changes)


def _log_is_current(
    path: Path,
    process_state: Dict[str, object],
    baseline_key: str,
) -> bool:
    signature = _log_signature(path)
    if signature is None:
        return False

    baseline_value = process_state.get("log_baseline")
    baseline: Optional[Dict[str, object]] = None
    if isinstance(baseline_value, dict):
        raw_baseline = baseline_value.get(baseline_key)
        if raw_baseline is None:
            raw_baseline = baseline_value.get(str(path.resolve(strict=False)))
        if isinstance(raw_baseline, dict):
            baseline = raw_baseline
    if baseline is not None:
        if not bool(baseline.get("exists")):
            return True
        return any(
            signature.get(key) != baseline.get(key)
            for key in ("mtime_ns", "size")
        )

    started_at = process_state.get("started_at_epoch_ns")
    try:
        return int(signature["mtime_ns"]) >= int(started_at)
    except (KeyError, TypeError, ValueError):
        return False


def _read_log_source(
    label: str,
    path: Optional[Path],
    process_state: Dict[str, object],
    full: bool,
    configured_warning: Optional[str] = None,
    baseline_key: str = "log",
) -> LogEvidenceSource:
    if path is None:
        return LogEvidenceSource(
            label,
            None,
            False,
            False,
            0,
            (),
            (),
            configured_warning or f"{label} log path is not configured.",
        )

    normalized = path.resolve(strict=False)
    if not normalized.is_file():
        return LogEvidenceSource(
            label,
            normalized,
            False,
            False,
            0,
            (),
            (),
            configured_warning or f"{label} log was not found: {normalized}",
        )

    try:
        lines = normalized.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except OSError as error:
        return LogEvidenceSource(
            label,
            normalized,
            False,
            False,
            0,
            (),
            (),
            f"Could not read {label} log {normalized}: {error}",
        )

    current = _log_is_current(normalized, process_state, baseline_key)
    warning = configured_warning
    if not current:
        warning = (
            warning
            or f"{label} log is not current for session {process_state.get('session_id', 'unknown')}; "
            "startup evidence from it is ignored."
        )
    selected_lines = tuple(lines if full else lines[-DEFAULT_LOG_LINES:])
    return LogEvidenceSource(
        label,
        normalized,
        True,
        current,
        len(lines),
        selected_lines,
        tuple(lines),
        warning,
    )


def _chainloader_ready(lines: Sequence[str]) -> bool:
    readiness_words = (
        "initialized",
        "initialised",
        "ready",
        "completed",
        "finished",
        "loaded",
    )
    for line in lines:
        lowered = line.casefold()
        if "chainloader" in lowered and any(
            word in lowered for word in readiness_words
        ):
            return True
    return False


def _target_mod_loaded(lines: Sequence[str], target_name: str) -> bool:
    target = target_name.strip().casefold()
    if not target:
        return False
    load_words = (
        "loading",
        "loaded",
        "initialized",
        "initialised",
        "plugin",
        "ready",
    )
    for line in lines:
        lowered = line.casefold()
        if target in lowered and any(word in lowered for word in load_words):
            return True
    return False


def collect_log_evidence(
    state_path: Path,
    profile: ProfilePreflight,
    preferences: Preferences,
    environment: str,
    *,
    full: bool = False,
    explicit_unity_log_dir: Optional[str] = None,
) -> EvidenceReport:
    """Read current logs once without persisting their contents."""

    manifest = _read_session_manifest(state_path)
    process_value = manifest.get("process")
    if not isinstance(process_value, dict):
        raise CliError(
            EXIT_LOGS,
            "logs/readiness",
            f"Session state has no tracked launch process: {state_path}",
        )
    target_name = str(manifest.get("target_name", "")).strip()
    if not target_name:
        raise CliError(
            EXIT_LOGS,
            "logs/readiness",
            f"Session state has no target mod name: {state_path}",
        )

    unity_path, unity_warning = resolve_unity_log_path(
        preferences,
        environment,
        explicit_directory=explicit_unity_log_dir,
    )
    bepinex_path = profile.bepinex_root / "LogOutput.log"
    sources = (
        _read_log_source(
            "BepInEx",
            bepinex_path,
            process_value,
            full,
            baseline_key="bepinex",
        ),
        _read_log_source(
            "Unity",
            unity_path,
            process_value,
            full,
            configured_warning=unity_warning,
            baseline_key="unity",
        ),
    )
    warnings = tuple(
        source.warning for source in sources if source.warning is not None
    )
    bepinex_source = sources[0]
    current_lines = tuple(
        line
        for source in sources
        if source.exists and source.current
        for line in source.evidence_lines
    )
    ready = (
        bepinex_source.exists
        and bepinex_source.current
        and _chainloader_ready(bepinex_source.evidence_lines)
    )
    mod_loaded = ready and _target_mod_loaded(current_lines, target_name)
    state = "mod_loaded" if mod_loaded else "ready" if ready else "launched"
    return EvidenceReport(
        state,
        ready,
        mod_loaded,
        False,
        sources,
        warnings,
    )


def _update_evidence_state(state_path: Path, report: EvidenceReport) -> None:
    payload = _read_session_manifest(state_path)
    payload["evidence"] = {
        "state": report.state,
        "ready": report.ready,
        "mod_loaded": report.mod_loaded,
        "timed_out": report.timed_out,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            source.label: {
                "exists": source.exists,
                "current": source.current,
                "line_count": source.total_lines,
            }
            for source in report.sources
        },
    }
    _atomic_write_json(state_path, payload)


def wait_for_startup_evidence(
    state_path: Path,
    profile: ProfilePreflight,
    preferences: Preferences,
    environment: str,
    timeout: float,
    *,
    explicit_unity_log_dir: Optional[str] = None,
) -> EvidenceReport:
    """Poll current logs until the target mod loads or the session times out."""

    deadline = time.monotonic() + timeout
    while True:
        report = collect_log_evidence(
            state_path,
            profile,
            preferences,
            environment,
            explicit_unity_log_dir=explicit_unity_log_dir,
        )
        if report.mod_loaded:
            _update_evidence_state(state_path, report)
            return report
        if time.monotonic() >= deadline:
            timed_out = EvidenceReport(
                "timeout",
                report.ready,
                report.mod_loaded,
                True,
                report.sources,
                report.warnings,
            )
            _update_evidence_state(state_path, timed_out)
            return timed_out
        time.sleep(min(STARTUP_POLL_INTERVAL_SECONDS, max(0.0, deadline - time.monotonic())))


def _session_manifest_path(
    session_id: str,
    code: int = EXIT_CLEAN,
    category: str = "stop/clean",
    allow_missing: bool = False,
) -> Path:
    if re.fullmatch(r"[0-9a-f]{32}", session_id) is None:
        raise CliError(
            code,
            category,
            "Session ID must be a 32-character hexadecimal identifier.",
        )
    state_path = _deployment_state_root() / session_id / "manifest.json"
    if not state_path.is_file():
        if allow_missing:
            return state_path
        raise CliError(
            code,
            category,
            f"Tracked session state does not exist: {session_id}",
        )
    return state_path


def _normalise_executable(path: Optional[Path]) -> Optional[Path]:
    if path is None:
        return None
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def _same_executable(first: Optional[Path], second: Optional[Path]) -> bool:
    first_value = _normalise_executable(first)
    second_value = _normalise_executable(second)
    if first_value is None or second_value is None:
        return False
    return first_value.as_posix().casefold() == second_value.as_posix().casefold()


def _windows_process_identity(
    pid: int,
    strict: bool = False,
) -> Optional[ProcessIdentity]:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        error_code = ctypes.get_last_error()
        if error_code == 5:
            if strict:
                raise PermissionError(error_code, "OpenProcess access denied")
            return None
        if error_code not in {2, 6, 87, 1168}:
            raise OSError(error_code, "OpenProcess failed")
        return None
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            error_code = ctypes.get_last_error()
            if error_code == 5:
                if strict:
                    raise PermissionError(error_code, "GetProcessTimes access denied")
                return None
            if error_code not in {2, 6, 87, 1168}:
                raise OSError(error_code, "GetProcessTimes failed")
            return None
        start_token = (
            f"{creation.dwHighDateTime:08x}{creation.dwLowDateTime:08x}"
        )
        executable: Optional[Path] = None
        buffer = ctypes.create_unicode_buffer(32768)
        buffer_size = wintypes.DWORD(len(buffer))
        if kernel32.QueryFullProcessImageNameW(
            handle,
            0,
            buffer,
            ctypes.byref(buffer_size),
        ):
            executable = _normalise_executable(Path(buffer.value))
        return ProcessIdentity(pid, start_token, executable)
    finally:
        kernel32.CloseHandle(handle)


def _proc_process_identity(
    pid: int,
    strict: bool = False,
) -> Optional[ProcessIdentity]:
    stat_path = Path("/proc") / str(pid) / "stat"
    try:
        contents = stat_path.read_text(encoding="utf-8")
    except OSError as error:
        if strict and getattr(error, "errno", None) == 13:
            raise
        return None
    except UnicodeError:
        return None
    closing_parenthesis = contents.rfind(")")
    if closing_parenthesis < 0:
        return None
    fields = contents[closing_parenthesis + 2 :].split()
    if len(fields) < 20:
        return None
    try:
        start_token = fields[19]
    except IndexError:
        return None
    executable: Optional[Path] = None
    executable_path = Path("/proc") / str(pid) / "exe"
    try:
        executable = _normalise_executable(executable_path.resolve(strict=True))
    except OSError:
        pass
    return ProcessIdentity(pid, start_token, executable)


def _ps_process_identity(
    pid: int,
    strict: bool = False,
) -> Optional[ProcessIdentity]:
    start_result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=False,
    )
    if start_result.returncode != 0 or not start_result.stdout.strip():
        return None
    command_result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    command = command_result.stdout.strip()
    executable: Optional[Path] = None
    if command:
        first_word = command.split()[0]
        if "/" in first_word:
            executable = _normalise_executable(Path(first_word))
    return ProcessIdentity(pid, start_result.stdout.strip(), executable)


def _process_identity(
    pid: int,
    strict: bool = False,
) -> Optional[ProcessIdentity]:
    if pid <= 0:
        return None
    if os.name == "nt":
        return _windows_process_identity(pid, strict=strict)
    if (Path("/proc")).is_dir():
        return _proc_process_identity(pid, strict=strict)
    return _ps_process_identity(pid, strict=strict)


def _windows_process_entries() -> Tuple[Tuple[int, int, str], ...]:
    import ctypes
    from ctypes import wintypes

    class ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == -1:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    try:
        entry = ProcessEntry32W()
        entry.dwSize = ctypes.sizeof(ProcessEntry32W)
        entries: List[Tuple[int, int, str]] = []
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return ()
        while True:
            entries.append(
                (
                    int(entry.th32ProcessID),
                    int(entry.th32ParentProcessID),
                    str(entry.szExeFile),
                )
            )
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
        return tuple(entries)
    finally:
        kernel32.CloseHandle(snapshot)


def _process_ids() -> Tuple[int, ...]:
    if os.name == "nt":
        return tuple(pid for pid, _, _ in _windows_process_entries())

    proc_root = Path("/proc")
    if proc_root.is_dir():
        process_ids = []
        for candidate in proc_root.iterdir():
            if candidate.name.isdigit():
                process_ids.append(int(candidate.name))
        return tuple(process_ids)

    result = subprocess.run(
        ["ps", "-axo", "pid="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise OSError(result.stderr.strip() or "ps failed")
    process_ids = []
    for line in result.stdout.splitlines():
        try:
            process_ids.append(int(line.strip()))
        except ValueError:
            continue
    return tuple(process_ids)


def _process_image_name(pid: int, known_name: Optional[str] = None) -> Optional[str]:
    if known_name is not None:
        return known_name
    proc_name = Path("/proc") / str(pid) / "comm"
    if proc_name.is_file():
        try:
            return proc_name.read_text(encoding="utf-8").strip().casefold()
        except (OSError, UnicodeError):
            return None
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).name.casefold()


def _find_conflicting_process(launcher: Path) -> Optional[ProcessIdentity]:
    current_pid = os.getpid()
    if os.name == "nt":
        process_entries = _windows_process_entries()
        process_ids = tuple(pid for pid, _, _ in process_entries)
        image_names = {
            pid: image_name.casefold()
            for pid, _, image_name in process_entries
        }
    else:
        process_ids = _process_ids()
        image_names = {}
    for pid in process_ids:
        if pid == current_pid:
            continue
        identity = _process_identity(pid)
        if identity is not None and _same_executable(identity.executable, launcher):
            return identity
        if identity is not None and identity.executable is not None:
            continue
        image_name = _process_image_name(pid, image_names.get(pid))
        if (
            image_name == launcher.name.casefold()
            and (identity is None or identity.executable is None)
        ):
            return identity or ProcessIdentity(pid, "uninspectable", None)
    return None


def _inspect_conflicting_process(profile: ProfilePreflight) -> Optional[ProcessIdentity]:
    try:
        return _find_conflicting_process(profile.launcher)
    except OSError as error:
        raise CliError(
            EXIT_LAUNCH,
            "launch",
            f"Could not inspect running processes before launch: {error}",
        ) from error


def _tracked_process_is_alive(identity: ProcessIdentity) -> bool:
    try:
        current = _process_identity(identity.pid, strict=True)
    except OSError as error:
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Could not inspect tracked process ID {identity.pid}: {error}; refusing to stop it.",
        ) from error
    if current is None:
        return False
    if current.start_token != identity.start_token:
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Tracked process ID {identity.pid} was reused by another process; refusing to stop it.",
        )
    if identity.executable and current.executable and not _same_executable(
        current.executable,
        identity.executable,
    ):
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Tracked process ID {identity.pid} no longer belongs to the selected launcher; refusing to stop it.",
        )
    return True


def _process_parent_map() -> Dict[int, int]:
    if os.name == "nt":
        return {
            pid: parent_pid
            for pid, parent_pid, _ in _windows_process_entries()
        }
    proc_root = Path("/proc")
    if proc_root.is_dir():
        parents: Dict[int, int] = {}
        for candidate in proc_root.iterdir():
            if not candidate.name.isdigit():
                continue
            identity_path = candidate / "stat"
            try:
                contents = identity_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            closing_parenthesis = contents.rfind(")")
            if closing_parenthesis < 0:
                continue
            fields = contents[closing_parenthesis + 2 :].split()
            if len(fields) < 4:
                continue
            try:
                parents[int(candidate.name)] = int(fields[1])
            except ValueError:
                continue
        return parents

    result = subprocess.run(
        ["ps", "-axo", "pid=,ppid="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise OSError(result.stderr.strip() or "ps failed")
    parents = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        try:
            parents[int(fields[0])] = int(fields[1])
        except ValueError:
            continue
    return parents


def _descendant_pids(root_pid: int) -> Tuple[int, ...]:
    children: Dict[int, List[int]] = {}
    for pid, parent_pid in _process_parent_map().items():
        children.setdefault(parent_pid, []).append(pid)
    descendants: List[int] = []
    pending = list(children.get(root_pid, ()))
    while pending:
        pid = pending.pop(0)
        descendants.append(pid)
        pending.extend(children.get(pid, ()))
    return tuple(descendants)


def _wait_for_process_exit(identity: ProcessIdentity, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        current = _process_identity(identity.pid, strict=True)
        if current is None or current.start_token != identity.start_token:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(PROCESS_POLL_INTERVAL_SECONDS)


def _same_process_identity(
    expected: ProcessIdentity,
    current: Optional[ProcessIdentity],
) -> bool:
    if current is None or current.start_token != expected.start_token:
        return False
    if expected.executable and current.executable and not _same_executable(
        current.executable,
        expected.executable,
    ):
        return False
    return True


def _wait_for_process_alive(
    identity: ProcessIdentity,
    timeout: float = LAUNCH_GRACE_PERIOD_SECONDS,
) -> Tuple[bool, Optional[ProcessIdentity]]:
    """Confirm that the launched identity remains alive through startup grace."""

    deadline = time.monotonic() + timeout
    while True:
        current = _process_identity(identity.pid, strict=True)
        if not _same_process_identity(identity, current):
            return False, current
        if time.monotonic() >= deadline:
            return True, current
        time.sleep(PROCESS_POLL_INTERVAL_SECONDS)


def _snapshot_process_tree(identity: ProcessIdentity) -> Tuple[ProcessIdentity, ...]:
    current = _process_identity(identity.pid, strict=True)
    if current is None:
        return ()
    if not _same_process_identity(identity, current):
        raise OSError(
            f"tracked process ID {identity.pid} changed before termination"
        )
    tree = [current]
    for pid in _descendant_pids(identity.pid):
        child = _process_identity(pid, strict=True)
        if child is not None:
            tree.append(child)
    return tuple(tree)


def _terminate_process_tree(identity: ProcessIdentity, force: bool = False) -> None:
    tree = _snapshot_process_tree(identity)
    if not tree:
        return
    if os.name == "nt":
        if not _same_process_identity(
            identity,
            _process_identity(identity.pid, strict=True),
        ):
            raise OSError(
                f"tracked process ID {identity.pid} changed before taskkill"
            )
        command = ["taskkill", "/PID", str(identity.pid), "/T"]
        if force:
            command.append("/F")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 and _same_process_identity(
            identity,
            _process_identity(identity.pid, strict=True),
        ):
            raise OSError(result.stderr.strip() or result.stdout.strip() or "taskkill failed")
        return

    termination_signal = signal.SIGKILL if force else signal.SIGTERM
    for process in reversed(tree):
        current = _process_identity(process.pid, strict=True)
        if current is None:
            continue
        if not _same_process_identity(process, current):
            raise OSError(
                f"process ID {process.pid} changed before termination"
            )
        try:
            os.kill(current.pid, termination_signal)
        except ProcessLookupError:
            continue
        except PermissionError as error:
            raise OSError(
                f"could not stop process {current.pid}: {error}"
            ) from error


def _update_process_state(
    state_path: Path,
    process_state: Dict[str, object],
) -> None:
    payload = _read_session_manifest(state_path)
    payload["process"] = process_state
    _atomic_write_json(state_path, payload)


def _launch_failure_state(
    profile: ProfilePreflight,
    state: str,
    error: str,
    pid: Optional[int] = None,
    exit_code: Optional[int] = None,
) -> Dict[str, object]:
    process_state: Dict[str, object] = {
        "state": state,
        "launcher": str(profile.launcher),
        "working_directory": str(profile.profile),
        "error": error,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    if pid is not None:
        process_state["pid"] = pid
    if exit_code is not None:
        process_state["exit_code"] = exit_code
    return process_state


def launch_session(
    deployment: DeploymentResult,
    profile: ProfilePreflight,
    log_paths: Optional[Sequence[Path]] = None,
) -> LaunchResult:
    """Launch the selected profile and persist identity for a later stop."""

    manifest = _read_session_manifest(deployment.state_path)
    if manifest.get("session_id") != deployment.session_id:
        raise CliError(
            EXIT_LAUNCH,
            "launch",
            f"Deployment state does not match session {deployment.session_id}.",
        )
    conflict = _inspect_conflicting_process(profile)
    if conflict is not None:
        process_state = _launch_failure_state(
            profile,
            "blocked",
            f"A matching launcher is already running with process ID {conflict.pid}.",
        )
        _update_process_state(deployment.state_path, process_state)
        raise CliError(
            EXIT_LAUNCH,
            "launch",
            f"A matching game instance is already running with process ID {conflict.pid}; refusing to attach.",
        )

    tracked_log_paths = tuple(
        log_paths
        or (profile.bepinex_root / "LogOutput.log",)
    )
    started_at_epoch_ns = time.time_ns()
    log_baseline = _capture_log_baselines(tracked_log_paths)
    options: Dict[str, object] = {
        "cwd": str(profile.profile),
        "shell": False,
    }
    if os.name == "nt":
        options["creationflags"] = getattr(
            subprocess,
            "CREATE_NEW_PROCESS_GROUP",
            0,
        )
    else:
        options["start_new_session"] = True

    try:
        process = subprocess.Popen([str(profile.launcher)], **options)
    except OSError as error:
        process_state = _launch_failure_state(profile, "failed", str(error))
        _update_process_state(deployment.state_path, process_state)
        raise CliError(
            EXIT_LAUNCH,
            "launch",
            f"Could not start the selected launcher: {error}",
        ) from error

    exit_code = process.poll()
    if exit_code is not None:
        process_state = _launch_failure_state(
            profile,
            "exited",
            f"The launcher exited before it became a live tracked process (exit code {exit_code}).",
            pid=process.pid,
            exit_code=exit_code,
        )
        _update_process_state(deployment.state_path, process_state)
        raise CliError(
            EXIT_LAUNCH,
            "launch",
            f"The game launcher exited before launch completed (exit code {exit_code}).",
        )

    try:
        identity = _process_identity(process.pid, strict=True)
    except OSError as error:
        identity = None
        identity_error = error
    else:
        identity_error = None
    if identity is None:
        try:
            process.terminate()
        except OSError:
            pass
        reason = str(identity_error or "process identity could not be read")
        process_state = _launch_failure_state(
            profile,
            "failed",
            reason,
            pid=process.pid,
        )
        _update_process_state(deployment.state_path, process_state)
        raise CliError(
            EXIT_LAUNCH,
            "launch",
            f"The launcher started but could not be safely tracked: {reason}",
        )

    try:
        alive, current = _wait_for_process_alive(identity)
    except OSError as error:
        alive = False
        current = None
        identity_error = error
    else:
        identity_error = None
    if not alive:
        if current is None:
            state = "exited"
            reason = "The launcher exited during the startup grace period."
        elif not _same_process_identity(identity, current):
            state = "failed"
            reason = (
                "The launched process identity changed during the startup grace "
                "period; refusing to stop an unrelated process."
            )
        else:
            state = "failed"
            reason = str(
                identity_error
                or "The launched process could not be confirmed during startup grace."
            )
        process_state = _launch_failure_state(
            profile,
            state,
            reason,
            pid=process.pid,
        )
        _update_process_state(deployment.state_path, process_state)
        raise CliError(EXIT_LAUNCH, "launch", reason)

    process_state = {
        "state": "launched",
        "session_id": deployment.session_id,
        "pid": identity.pid,
        "start_token": identity.start_token,
        "launcher": str(profile.launcher),
        "working_directory": str(profile.profile),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_at_epoch_ns": started_at_epoch_ns,
        "log_baseline": log_baseline,
    }
    try:
        _update_process_state(deployment.state_path, process_state)
        _update_evidence_state(
            deployment.state_path,
            EvidenceReport("launched", False, False, False, (), ()),
        )
    except (CliError, OSError) as error:
        try:
            _terminate_process_tree(identity, force=True)
        except OSError:
            pass
        raise CliError(
            EXIT_LAUNCH,
            "launch",
            f"Could not persist tracked process state; the launched process was not retained: {error}",
        ) from error
    return LaunchResult(deployment.session_id, deployment.state_path, identity.pid)


def stop_session(session_id: str, force: bool = False) -> StopResult:
    """Stop only the process identity recorded for one test session."""

    state_path = _session_manifest_path(session_id, allow_missing=True)
    if not state_path.is_file():
        return StopResult(session_id, "gone")
    manifest = _read_session_manifest(state_path)
    process_value = manifest.get("process")
    if not isinstance(process_value, dict):
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} has no tracked game process.",
        )
    process_state = dict(process_value)
    state = str(process_state.get("state", ""))
    if state in {"stopped", "exited"}:
        return StopResult(session_id, state)
    if state != "launched":
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} is not stoppable in state '{state}'.",
        )
    try:
        pid = int(process_state["pid"])
        start_token = str(process_state["start_token"])
        launcher = Path(str(process_state["launcher"]))
    except (KeyError, TypeError, ValueError) as error:
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} has incomplete tracked process state: {error}",
        ) from error
    identity = ProcessIdentity(pid, start_token, launcher)
    if not _tracked_process_is_alive(identity):
        process_state["state"] = "exited"
        process_state["recorded_at"] = datetime.now(timezone.utc).isoformat()
        _update_process_state(state_path, process_state)
        return StopResult(session_id, "exited")

    try:
        tracked_tree = _snapshot_process_tree(identity)
        if not tracked_tree:
            process_state["state"] = "exited"
            process_state["recorded_at"] = datetime.now(timezone.utc).isoformat()
            _update_process_state(state_path, process_state)
            return StopResult(session_id, "exited")
        _terminate_process_tree(identity, force=force)
        if not _wait_for_process_exit(identity):
            raise OSError(
                f"process {pid} is still running after stop; retry with --force"
            )
        for child in tracked_tree[1:]:
            if not _wait_for_process_exit(child):
                raise OSError(
                    f"child process {child.pid} is still running after stop; retry with --force"
                )
    except (OSError, CliError) as error:
        if isinstance(error, CliError):
            raise
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Could not stop tracked process tree for session {session_id}: {error}",
        ) from error

    process_state["state"] = "stopped"
    process_state["force"] = force
    process_state["stopped_at"] = datetime.now(timezone.utc).isoformat()
    _update_process_state(state_path, process_state)
    return StopResult(session_id, "stopped")


def _ensure_session_process_stopped(
    session_id: str,
    manifest: Dict[str, object],
) -> bool:
    process_value = manifest.get("process")
    if not isinstance(process_value, dict):
        return False
    state = str(process_value.get("state", ""))
    if state in {"stopped", "exited", "failed", "blocked"}:
        return False
    if state != "launched":
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} has an unknown tracked process state '{state}'; refusing to clean it.",
        )
    try:
        identity = ProcessIdentity(
            int(process_value["pid"]),
            str(process_value["start_token"]),
            Path(str(process_value["launcher"])),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} has incomplete tracked process state: {error}",
        ) from error
    if _tracked_process_is_alive(identity):
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} tracks a game process that is still running; stop it before cleaning.",
        )
    process_value["state"] = "exited"
    process_value["recorded_at"] = datetime.now(timezone.utc).isoformat()
    return True


def _clean_manifest_path(
    value: object,
    root: Path,
    label: str,
) -> Path:
    if value is None or not str(value).strip():
        raise OSError(f"{label} is missing from session state")
    candidate = Path(str(value))
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved_root = root.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    if not _is_within(resolved_candidate, resolved_root):
        raise OSError(f"{label} escapes the recorded Modding root: {candidate}")
    return candidate


def _clean_backup_path(
    session_directory: Path,
    value: object,
) -> Path:
    if value is None or not str(value).strip():
        raise OSError("overwritten file backup is missing from session state")
    candidate = session_directory / str(value)
    resolved_root = session_directory.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    if not _is_within(resolved_candidate, resolved_root):
        raise OSError(f"backup path escapes the session state directory: {candidate}")
    if _first_symlink_component(candidate) is not None or candidate.is_symlink():
        raise OSError(f"backup path contains a symlink: {candidate}")
    if not candidate.is_file():
        raise OSError(f"backup is missing: {candidate}")
    return candidate


def clean_session(
    session_id: str,
    remove_new_files: bool = False,
    expected_profile: Optional[Path] = None,
) -> CleanResult:
    """Safely roll back one stopped deployment session.

    The manifest remains in temporary state after cleaning so status and
    repeated recovery commands stay idempotent. Overwritten files are only
    restored when their current hash still matches this session's deployed
    hash. New files are retained unless the caller explicitly opts in to
    removing them.
    """

    state_path = _session_manifest_path(session_id, allow_missing=True)
    if not state_path.is_file():
        return CleanResult(
            session_id,
            "already-gone",
            (),
            (),
            (),
            ("Session state is already gone; no profile files were changed.",),
        )
    manifest = _read_session_manifest(state_path)
    recorded_profile = manifest.get("profile")
    if not recorded_profile:
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} has no recorded modding profile.",
        )
    profile = Path(str(recorded_profile)).resolve(strict=False)
    if expected_profile is not None and not _profile_paths_match(
        profile,
        expected_profile,
    ):
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} belongs to profile {profile}, but the selected profile is {expected_profile.resolve(strict=False)}.",
        )

    process_changed = _ensure_session_process_stopped(session_id, manifest)
    cleanup_state = _session_cleanup_state(manifest)
    if cleanup_state == "cleaned" and not remove_new_files:
        if process_changed:
            _atomic_write_json(state_path, manifest)
        return CleanResult(session_id, "already-cleaned", (), (), (), ())

    entries = _session_entries(profile)
    current_entry: Optional[Tuple[Path, Dict[str, object]]] = None
    for entry in entries:
        if entry[0] == state_path:
            current_entry = entry
            break
    if current_entry is None:
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} is not present in the session listing.",
        )
    current_key = _session_sort_key(current_entry)
    newer_sessions = [
        str(payload.get("session_id", path.parent.name))
        for path, payload in entries
        if path != state_path
        and _session_is_cleanable(payload)
        and _session_sort_key((path, payload)) > current_key
    ]
    if newer_sessions:
        newer_text = ", ".join(newer_sessions)
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Cannot clean older session {session_id} while newer session(s) remain active: {newer_text}. Clean newest-first.",
        )

    root_value = manifest.get("modding_root")
    if not root_value:
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} has no recorded Modding root.",
        )
    modding_root = Path(str(root_value)).resolve(strict=False)
    files_value = manifest.get("files")
    if not isinstance(files_value, list):
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Session {session_id} has no valid deployment file records.",
        )

    operations: List[Tuple[str, Dict[str, object], Path, Optional[Path]]] = []
    retained_files: List[Path] = []
    warnings: List[str] = []
    conflicts: List[str] = []
    for index, value in enumerate(files_value):
        if not isinstance(value, dict):
            conflicts.append(f"file record {index} is not an object")
            continue
        if not bool(value.get("completed", True)):
            continue
        try:
            destination = _clean_manifest_path(
                value.get("destination"),
                modding_root,
                f"file record {index} destination",
            )
        except OSError as error:
            conflicts.append(str(error))
            continue

        existed = bool(value.get("existed", False))
        if existed:
            if bool(value.get("restored", False)):
                continue
            try:
                backup = _clean_backup_path(
                    state_path.parent,
                    value.get("backup_path"),
                )
                if not destination.is_file() or destination.is_symlink():
                    raise OSError(f"overwritten deployment target is unavailable: {destination}")
                _reject_unsafe_deployment_destination(destination)
                deployed_hash = str(value.get("deployed_sha256", ""))
                if not deployed_hash or _sha256(destination) != deployed_hash:
                    raise OSError(
                        f"overwritten deployment target changed during testing; protected from restoration: {destination}"
                    )
                original_hash = str(value.get("original_sha256", ""))
                if not original_hash or _sha256(backup) != original_hash:
                    raise OSError(f"recorded backup hash is invalid: {backup}")
                operations.append(("restore", value, destination, backup))
            except (OSError, ValueError) as error:
                conflicts.append(str(error))
            continue

        if bool(value.get("removed", False)):
            continue
        if not remove_new_files:
            if destination.exists() or destination.is_symlink():
                retained_files.append(destination)
                if destination.is_symlink() or not destination.is_file():
                    warnings.append(
                        f"Retaining new deployment path without inspection: {destination}"
                    )
                else:
                    deployed_hash = str(value.get("deployed_sha256", ""))
                    if deployed_hash and _sha256(destination) != deployed_hash:
                        warnings.append(
                            f"Retaining new file changed during testing: {destination}"
                        )
            continue

        if not destination.exists() and not destination.is_symlink():
            value["removed"] = True
            continue
        try:
            if destination.is_symlink() or not destination.is_file():
                raise OSError(f"new deployment target is not a regular file: {destination}")
            _reject_unsafe_deployment_destination(destination)
            deployed_hash = str(value.get("deployed_sha256", ""))
            if not deployed_hash or _sha256(destination) != deployed_hash:
                raise OSError(
                    f"new deployment target changed during testing; protected from removal: {destination}"
                )
            operations.append(("remove", value, destination, None))
        except (OSError, ValueError) as error:
            conflicts.append(str(error))

    if conflicts:
        if process_changed:
            _atomic_write_json(state_path, manifest)
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            "Safe clean refused; protected files were not changed: "
            + "; ".join(conflicts),
        )

    restored_files: List[Path] = []
    removed_files: List[Path] = []
    try:
        for operation, record, destination, backup in operations:
            _reject_unsafe_deployment_destination(destination)
            if operation == "restore":
                if backup is None or not destination.is_file():
                    raise OSError(f"restoration target is unavailable: {destination}")
                expected = str(record.get("deployed_sha256", ""))
                if not expected or _sha256(destination) != expected:
                    raise OSError(
                        f"overwritten deployment target changed during testing; protected from restoration: {destination}"
                    )
                shutil.copy2(backup, destination)
                original_hash = str(record.get("original_sha256", ""))
                if not original_hash or _sha256(destination) != original_hash:
                    raise OSError(f"restored file hash mismatch: {destination}")
                record["restored"] = True
                restored_files.append(destination)
            else:
                expected = str(record.get("deployed_sha256", ""))
                if not destination.is_file() or not expected or _sha256(destination) != expected:
                    raise OSError(
                        f"new deployment target changed during testing; protected from removal: {destination}"
                    )
                destination.unlink()
                record["removed"] = True
                removed_files.append(destination)
            _atomic_write_json(state_path, manifest)
    except (OSError, ValueError) as error:
        try:
            _atomic_write_json(state_path, manifest)
        except OSError:
            pass
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Safe clean stopped without completing all records: {error}",
        ) from error

    directory_values = manifest.get("created_directories", [])
    if isinstance(directory_values, list):
        directories: List[Path] = []
        for value in directory_values:
            try:
                directories.append(
                    _clean_manifest_path(
                        value,
                        modding_root,
                        "created deployment directory",
                    )
                )
            except OSError as error:
                warnings.append(str(error))
        for directory in sorted(
            directories,
            key=lambda path: (len(path.parts), path.as_posix().casefold()),
            reverse=True,
        ):
            if directory.is_symlink():
                warnings.append(f"Left deployment directory symlink untouched: {directory}")
                continue
            if not directory.exists():
                continue
            try:
                directory.rmdir()
            except OSError:
                warnings.append(f"Left non-empty deployment directory untouched: {directory}")

    manifest["cleanup_state"] = "cleaned"
    manifest["cleaned_at"] = datetime.now(timezone.utc).isoformat()
    manifest["cleaned_with_remove_new_files"] = remove_new_files
    manifest["restored_files"] = [path.as_posix() for path in restored_files]
    manifest["removed_files"] = [path.as_posix() for path in removed_files]
    manifest["retained_files"] = [path.as_posix() for path in retained_files]
    try:
        _atomic_write_json(state_path, manifest)
    except OSError as error:
        raise CliError(
            EXIT_CLEAN,
            "stop/clean",
            f"Safe clean changed files but could not persist session state: {error}",
        ) from error
    return CleanResult(
        session_id,
        "cleaned",
        tuple(restored_files),
        tuple(removed_files),
        tuple(retained_files),
        tuple(warnings),
    )


def _create_deployment_transaction(
    profile: ProfilePreflight,
    plan: ArtifactPlan,
    operations: Tuple[DeploymentOperation, ...],
    planned_directories: Tuple[Path, ...],
) -> DeploymentTransaction:
    state_root = _deployment_state_root()
    session_directory: Optional[Path] = None
    try:
        state_root.mkdir(parents=True, exist_ok=True)
        for _ in range(5):
            session_id = uuid.uuid4().hex
            candidate = state_root / session_id
            try:
                candidate.mkdir()
            except FileExistsError:
                continue
            session_directory = candidate
            break
        if session_directory is None:
            raise OSError("could not allocate a unique deployment session directory")

        records: List[Dict[str, object]] = []
        for operation in operations:
            backup_path = session_directory / "backups" / operation.relative_path
            records.append(
                {
                    "relative_path": operation.relative_path.as_posix(),
                    "destination": str(operation.destination),
                    "existed": operation.existed,
                    "backup_path": (
                        backup_path.relative_to(session_directory).as_posix()
                        if operation.existed
                        else None
                    ),
                    "backup_created": False,
                    "original_sha256": None,
                    "deployed_sha256": None,
                    "started": False,
                    "completed": False,
                }
            )
        transaction = DeploymentTransaction(
            session_id,
            session_directory,
            session_directory / "manifest.json",
            profile.profile,
            profile.modding_root,
            plan,
            operations,
            planned_directories,
            records,
            [],
            datetime.now(timezone.utc).isoformat(),
        )
        _write_manifest(transaction, "planned")
        return transaction
    except (OSError, TypeError, ValueError) as error:
        if session_directory is not None:
            shutil.rmtree(session_directory, ignore_errors=True)
        raise CliError(
            EXIT_DEPLOY,
            "deployment",
            f"Could not create deployment transaction state: {error}",
        ) from error


def _rollback_deployment(transaction: DeploymentTransaction) -> Tuple[str, ...]:
    """Undo an incomplete deployment so no partial package remains.

    This failure-path compensation is distinct from the later safe-clean
    operation, which preserves new files from a successful test by default.
    """

    errors: List[str] = []
    for record in reversed(transaction.records):
        if not record["started"]:
            continue
        destination = Path(str(record["destination"]))
        try:
            if record["existed"]:
                backup_value = record["backup_path"]
                if not record["backup_created"] or not backup_value:
                    continue
                backup = transaction.session_directory / str(backup_value)
                if not backup.is_file():
                    raise OSError(f"backup is missing: {backup}")
                if destination.exists() and not destination.is_file():
                    raise OSError(f"deployment target is no longer a regular file: {destination}")
                _reject_unsafe_deployment_destination(destination)
                if not destination.parent.is_dir():
                    raise OSError(f"deployment target parent is unavailable: {destination.parent}")
                if record["completed"] and record["deployed_sha256"]:
                    if _sha256(destination) != str(record["deployed_sha256"]):
                        raise OSError(f"deployed file changed before rollback: {destination}")
                shutil.copy2(backup, destination)
                expected = record["original_sha256"]
                if expected and _sha256(destination) != expected:
                    raise OSError(f"restored file hash mismatch: {destination}")
            else:
                if destination.exists():
                    if not destination.is_file():
                        raise OSError(f"new deployment target is not a regular file: {destination}")
                    _reject_unsafe_deployment_destination(destination)
                    expected = record["deployed_sha256"]
                    if not expected or _sha256(destination) != str(expected):
                        raise OSError(f"new deployment target changed before rollback: {destination}")
                    destination.unlink()
        except (OSError, ValueError) as error:
            errors.append(str(error))

    for directory in reversed(transaction.created_directories):
        try:
            if directory.is_symlink():
                raise OSError(f"created deployment directory became a symlink: {directory}")
            if directory.exists():
                directory.rmdir()
        except OSError as error:
            errors.append(str(error))
    return tuple(errors)


def deploy_artifact(
    plan: ArtifactPlan,
    profile: ProfilePreflight,
) -> DeploymentResult:
    """Deploy one validated artifact with a recoverable transaction manifest."""

    try:
        operations, missing_directories = _plan_deployment_operations(profile, plan)
    except CliError as error:
        raise CliError(
            EXIT_DEPLOY,
            "deployment",
            f"Deployment preflight failed before profile mutation; rollback not required: {error}",
        ) from error
    transaction = _create_deployment_transaction(
        profile,
        plan,
        operations,
        missing_directories,
    )
    try:
        _write_manifest(transaction, "deploying")
        for directory in missing_directories:
            if directory.is_symlink():
                raise OSError(f"deployment directory became a symlink: {directory}")
            if directory.exists():
                if not directory.is_dir():
                    raise OSError(f"deployment path is not a directory: {directory}")
                continue
            directory.mkdir()
            if directory.is_symlink() or not directory.is_dir():
                raise OSError(f"created deployment path is not a directory: {directory}")
            transaction.created_directories.append(directory)
            _write_manifest(transaction, "deploying")

        for index, operation in enumerate(operations):
            record = transaction.records[index]
            record["started"] = True
            _write_manifest(transaction, "deploying")
            _reject_unsafe_deployment_destination(operation.destination)
            if operation.existed:
                backup_value = record["backup_path"]
                if not backup_value:
                    raise OSError(f"backup path is missing: {operation.destination}")
                backup = transaction.session_directory / str(backup_value)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(operation.destination, backup)
                record["backup_created"] = True
                record["original_sha256"] = _sha256(backup)
                _write_manifest(transaction, "deploying")

            source_hash = _sha256(operation.source)
            record["deployed_sha256"] = source_hash
            _reject_unsafe_deployment_destination(operation.destination)
            shutil.copy2(operation.source, operation.destination)
            if (
                not operation.destination.is_file()
                or _sha256(operation.destination) != source_hash
            ):
                raise OSError(f"deployed file hash mismatch: {operation.destination}")
            record["completed"] = True
            _write_manifest(transaction, "deploying")

        _write_manifest(transaction, "deployed")
        return DeploymentResult(
            transaction.session_id,
            transaction.state_path,
            tuple(operation.relative_path for operation in operations),
        )
    except Exception as error:
        rollback_errors = _rollback_deployment(transaction)
        if rollback_errors:
            rollback_message = "; ".join(rollback_errors)
            try:
                _write_manifest(
                    transaction,
                    "rollback_failed",
                    str(error),
                    rollback_message,
                )
            except OSError:
                pass
            raise CliError(
                EXIT_DEPLOY,
                "deployment",
                f"Deployment failed: {error}; rollback failed: {rollback_message}. Session: {transaction.session_id}",
            ) from error
        try:
            _write_manifest(transaction, "rolled_back", str(error))
        except OSError:
            pass
        raise CliError(
            EXIT_DEPLOY,
            "deployment",
            f"Deployment failed: {error}; rollback succeeded. Session: {transaction.session_id}",
        ) from error


def detect_supported_environment() -> str:
    """Return the supported host family and reject compatibility shells."""

    if os.environ.get("MSYSTEM") or os.environ.get("CYGWIN"):
        raise CliError(
            EXIT_USAGE,
            "usage/configuration",
            "Unsupported environment: use native Windows PowerShell or native Bash, not Git Bash/Cygwin.",
        )

    if any(
        os.environ.get(variable)
        for variable in (
            "STEAM_COMPAT_DATA_PATH",
            "STEAM_COMPAT_CLIENT_INSTALL_PATH",
            "PROTON",
            "WINEPREFIX",
            "WINEDLLOVERRIDES",
        )
    ):
        raise CliError(
            EXIT_USAGE,
            "usage/configuration",
            "Unsupported environment: do not run the CLI through Proton or Wine; use a native profile.",
        )

    system = platform.system()
    if system == "Windows":
        return "Windows"
    if system == "Darwin":
        return "macOS"
    if system == "Linux":
        release = platform.release().lower()
        if (
            os.environ.get("WSL_DISTRO_NAME")
            or os.environ.get("WSL_INTEROP")
            or "microsoft" in release
        ):
            raise CliError(
                EXIT_USAGE,
                "usage/configuration",
                "Unsupported environment: use native Linux Bash instead of WSL.",
            )
        return "Linux"
    raise CliError(
        EXIT_USAGE,
        "usage/configuration",
        f"Unsupported operating system: {system or 'unknown'}.",
    )


def _require_directory(path: Path, label: str) -> None:
    if not path.exists():
        raise CliError(
            EXIT_PROFILE,
            "profile/preferences",
            f"{label} does not exist: {path}",
        )
    if not path.is_dir():
        raise CliError(
            EXIT_PROFILE,
            "profile/preferences",
            f"{label} is not a directory: {path}",
        )


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise CliError(
            EXIT_PROFILE,
            "profile/preferences",
            f"{label} does not exist: {path}",
        )
    if not path.is_file():
        raise CliError(
            EXIT_PROFILE,
            "profile/preferences",
            f"{label} is not a file: {path}",
        )
    if path.stat().st_size == 0:
        raise CliError(
            EXIT_PROFILE,
            "profile/preferences",
            f"{label} is empty: {path}",
        )


def _launcher_candidates(profile: Path, environment: str) -> Tuple[Path, ...]:
    if environment == "Windows":
        return (profile / "Blasphemous.exe",)
    if environment == "Linux":
        return (profile / "Blasphemous.x86_64", profile / "Blasphemous")
    return (
        profile / "Blasphemous.app" / "Contents" / "MacOS" / "Blasphemous",
        profile / "Blasphemous",
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_launcher(
    profile: Path,
    environment: str,
    explicit_launcher: Optional[str],
) -> Tuple[Path, Tuple[str, ...]]:
    warnings: List[str] = []
    if explicit_launcher:
        launcher_value = Path(
            os.path.expandvars(os.path.expanduser(explicit_launcher.strip()))
        )
        if not launcher_value.is_absolute():
            launcher_value = profile / launcher_value
        launcher = launcher_value.resolve(strict=False)
        if not launcher.is_file():
            raise CliError(
                EXIT_PROFILE,
                "profile/preferences",
                f"The selected game launcher does not exist: {launcher}",
            )
        if launcher.stat().st_size == 0:
            raise CliError(
                EXIT_PROFILE,
                "profile/preferences",
                f"The selected game launcher is empty: {launcher}",
            )
        if environment != "Windows" and not os.access(launcher, os.X_OK):
            raise CliError(
                EXIT_PROFILE,
                "profile/preferences",
                f"The selected game launcher is not executable: {launcher}",
            )
        if not _is_within(launcher, profile):
            warnings.append(
                f"The explicit launcher is outside the modding profile: {launcher}"
            )
        else:
            warnings.append(f"Using explicit launcher override: {launcher}")
        return launcher, tuple(warnings)

    candidates = _launcher_candidates(profile, environment)
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            resolved_candidate = candidate.resolve(strict=True)
        except OSError:
            continue
        if not _is_within(resolved_candidate, profile):
            continue
        if resolved_candidate.stat().st_size > 0 and (
            environment == "Windows" or os.access(resolved_candidate, os.X_OK)
        ):
            return resolved_candidate, tuple(warnings)
    candidate_text = ", ".join(str(candidate) for candidate in candidates)
    raise CliError(
        EXIT_PROFILE,
        "profile/preferences",
        f"No known game launcher was found in the modding profile. Checked: {candidate_text}. Pass --launcher PATH for a custom launcher.",
    )


def preflight_profile(
    profile_path: Path,
    environment: str,
    explicit_launcher: Optional[str] = None,
) -> ProfilePreflight:
    profile = profile_path.resolve(strict=False)
    _require_directory(profile, "Modding profile")
    modding_root = profile / "Modding"
    bepinex_root = profile / "BepInEx"
    _require_directory(modding_root, "Modding root")
    _require_directory(bepinex_root, "BepInEx installation")
    _require_file(
        bepinex_root / "core" / "BepInEx.dll",
        "BepInEx core assembly",
    )
    launcher, warnings = _resolve_launcher(profile, environment, explicit_launcher)
    return ProfilePreflight(profile, launcher, modding_root, bepinex_root, warnings)


def _resolve_context(args: argparse.Namespace, require_project: bool) -> InvocationContext:
    environment = detect_supported_environment()
    cwd = Path.cwd().resolve()
    preferences = load_preferences(cwd=cwd)
    configured_profile = preferences.values["modding_profile_path"]
    profile_value = args.profile if args.profile else configured_profile
    profile_path = _expand_path(profile_value, cwd)
    project = (
        select_project(cwd, args.project)
        if require_project
        else select_optional_project(cwd, args.project)
    )
    profile = preflight_profile(profile_path, environment, args.launcher)
    return InvocationContext(environment, preferences, project, profile)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        metavar="PATH",
        help="Select a .csproj; otherwise infer the only project in the current directory.",
    )
    parser.add_argument(
        "--profile",
        metavar="PATH",
        help="Override modding_profile_path for this invocation.",
    )
    parser.add_argument(
        "--launcher",
        metavar="PATH",
        help="Use an explicit game launcher path for this invocation.",
    )
    parser.add_argument(
        "--unity-log-dir",
        metavar="PATH",
        help="Override unity_log_dir for this invocation without editing preferences.md.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blasphemous-modding-test",
        description="Build, validate, and deploy a Blasphemous mod artifact.",
        epilog="Use 'run --dry-run' to inspect the plan without deployment or launch, 'logs SESSION_ID' to inspect current startup evidence, 'stop SESSION_ID' to stop one tracked process tree, 'clean SESSION_ID' for newest-first safe cleanup, or 'status' for a read-only profile view.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Build or select an artifact and deploy it, or print a dry-run plan.",
    )
    _add_common_options(run_parser)
    run_parser.add_argument(
        "--configuration",
        choices=("Debug", "Release"),
        default="Debug",
        help="Build configuration; Debug is the default and Release is explicit.",
    )
    run_parser.add_argument(
        "--artifact",
        metavar="PATH",
        help="Use one exact package directory or explicit .zip archive without building.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the plan without copying files or launching a process.",
    )
    run_parser.add_argument(
        "--startup-timeout",
        metavar="SECONDS",
        type=float,
        help="Wait for current BepInEx and target-mod evidence; omitted means report launched only.",
    )

    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop one tracked test-session process tree.",
    )
    stop_parser.add_argument(
        "session_id",
        metavar="SESSION_ID",
        help="The session identifier printed by a successful run.",
    )
    stop_parser.add_argument(
        "--force",
        action="store_true",
        help="Force-stop only the tracked process tree when graceful stop fails.",
    )

    clean_parser = subparsers.add_parser(
        "clean",
        help="Safely clean one stopped session in newest-first order.",
    )
    clean_parser.add_argument(
        "session_id",
        metavar="SESSION_ID",
        help="The session identifier printed by a successful run.",
    )
    _add_common_options(clean_parser)
    clean_parser.add_argument(
        "--remove-new-files",
        action="store_true",
        help="Explicitly approve removal of unchanged files first created by this session; changed files remain protected.",
    )

    logs_parser = subparsers.add_parser(
        "logs",
        help="Read current BepInEx and Unity startup logs for one session.",
    )
    logs_parser.add_argument(
        "session_id",
        metavar="SESSION_ID",
        help="The session identifier printed by run.",
    )
    _add_common_options(logs_parser)
    logs_parser.add_argument(
        "--full",
        action="store_true",
        help="Print complete log contents instead of the bounded tail.",
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Show the current read-only profile and session status.",
    )
    _add_common_options(status_parser)
    return parser


def _print_context(context: InvocationContext) -> None:
    print(f"Environment: {context.environment}")
    print(
        f"Preferences: {context.preferences.scope} ({context.preferences.path})"
    )
    if context.project:
        print(f"Project: {context.project}")
    else:
        print("Project: not selected (run requires --project when no single .csproj is present)")
    print(f"Modding profile: {context.profile.profile}")
    print(f"Launcher: {context.profile.launcher}")
    print(f"Modding root: {context.profile.modding_root}")
    print(f"BepInEx: {context.profile.bepinex_root}")
    for warning in context.profile.warnings:
        print(f"Warning: {warning}", file=sys.stderr)


def _print_artifact_plan(plan: ArtifactPlan) -> None:
    print(f"Configuration: {plan.configuration}")
    print(f"Target name: {plan.target_name}")
    print(f"Publish directory: {plan.publish_directory}")
    print(f"Artifact: {plan.artifact}")
    print(f"Artifact kind: {plan.artifact_kind}")
    print(f"Package root: {plan.package_root}")
    print(f"Planned files: {len(plan.relative_files)}")
    for relative_file in plan.relative_files:
        print(f"  - {relative_file.as_posix()}")


def _print_evidence_report(
    report: EvidenceReport,
    include_logs: bool = False,
    full_logs: bool = False,
) -> None:
    print(f"Startup state: {report.state}")
    print(f"Ready state: {'ready' if report.ready else 'not-ready'}")
    print(f"Mod-loaded state: {'loaded' if report.mod_loaded else 'not-loaded'}")
    for source in report.sources:
        path = str(source.path) if source.path is not None else "not configured"
        if not source.exists:
            status = "missing"
        elif source.current:
            status = "current"
        else:
            status = "stale"
        print(f"{source.label} log: {path}")
        print(f"{source.label} log status: {status}; lines: {source.total_lines}")
        if include_logs and source.output_lines:
            output_kind = "full" if full_logs else f"last {DEFAULT_LOG_LINES}"
            print(f"{source.label} log output ({output_kind} lines):")
            for line in source.output_lines:
                print(line)
    for warning in report.warnings:
        print(f"Warning: {warning}", file=sys.stderr)


def _run_command(args: argparse.Namespace) -> int:
    if args.startup_timeout is not None and (
        not math.isfinite(args.startup_timeout) or args.startup_timeout < 0
    ):
        raise CliError(
            EXIT_USAGE,
            "usage/configuration",
            "--startup-timeout must be zero or greater.",
        )
    context = _resolve_context(args, require_project=True)
    with prepare_artifact(
        context.project,
        args.configuration,
        explicit_artifact=args.artifact,
        cwd=Path.cwd(),
    ) as plan:
        _print_context(context)
        _print_artifact_plan(plan)
        if args.dry_run:
            print("Dry run: no profile files copied; no process launched.")
        else:
            conflict = _inspect_conflicting_process(context.profile)
            if conflict is not None:
                raise CliError(
                    EXIT_LAUNCH,
                    "launch",
                    f"A matching game instance is already running with process ID {conflict.pid}; refusing to deploy or attach.",
                )
            result = deploy_artifact(plan, context.profile)
            try:
                archived_sessions = _archive_previous_sessions(
                    context.profile.profile,
                    result.session_id,
                )
            except CliError as archive_error:
                try:
                    clean_session(
                        result.session_id,
                        remove_new_files=True,
                        expected_profile=context.profile.profile,
                    )
                except (CliError, OSError, UnicodeError) as rollback_error:
                    raise CliError(
                        EXIT_DEPLOY,
                        "deployment",
                        f"Could not archive previous sessions: {archive_error}; automatic rollback of the new deployment also failed: {rollback_error}. Session: {result.session_id}",
                    ) from rollback_error
                raise CliError(
                    archive_error.code,
                    archive_error.category,
                    f"{archive_error}; the new deployment was rolled back safely. Session: {result.session_id}",
                ) from archive_error
            for archived_session in archived_sessions:
                print(
                    f"Warning: archived previous session {archived_session}; clean sessions newest-first.",
                    file=sys.stderr,
                )
            print(f"Deployment session: {result.session_id}")
            print(f"Deployment state: deployed")
            print(f"Deployed files: {len(result.deployed_files)}")
            unity_log_path, _ = resolve_unity_log_path(
                context.preferences,
                context.environment,
                explicit_directory=args.unity_log_dir,
            )
            log_paths = [context.profile.bepinex_root / "LogOutput.log"]
            if unity_log_path is not None:
                log_paths.append(unity_log_path)
            launch = launch_session(result, context.profile, log_paths=log_paths)
            print(f"Launch session: {launch.session_id}")
            print("Launch state: launched")
            print(f"Process ID: {launch.pid}")
            if args.startup_timeout is not None:
                report = wait_for_startup_evidence(
                    result.state_path,
                    context.profile,
                    context.preferences,
                    context.environment,
                    args.startup_timeout,
                    explicit_unity_log_dir=args.unity_log_dir,
                )
                _print_evidence_report(report)
                if report.timed_out:
                    raise CliError(
                        EXIT_LOGS,
                        "logs/readiness",
                        "Startup evidence timed out; the launched process and session "
                        f"remain available for diagnosis: {result.session_id}",
                    )
            else:
                print("Startup state: launched")
    return EXIT_SUCCESS


def _status_command(args: argparse.Namespace) -> int:
    context = _resolve_context(args, require_project=False)
    _print_context(context)
    entries = _session_entries(context.profile.profile)
    print("Test sessions (newest first):")
    if not entries:
        print("  none")
    else:
        for index, (state_path, payload) in enumerate(entries):
            session_id = str(payload.get("session_id", state_path.parent.name))
            role = _session_role(payload, newest=index == 0)
            deployment_state = str(payload.get("status", "unknown"))
            cleanup_state = _session_cleanup_state(payload)
            process_value = payload.get("process")
            process_state = (
                str(process_value.get("state", "unknown"))
                if isinstance(process_value, dict)
                else "not-launched"
            )
            evidence_value = payload.get("evidence")
            evidence_state = (
                str(evidence_value.get("state", "unknown"))
                if isinstance(evidence_value, dict)
                else "unknown"
            )
            print(
                f"  {session_id}: {role} (deployment={deployment_state}, "
                f"cleanup={cleanup_state}, process={process_state}, evidence={evidence_state})"
            )
    print("Status is read-only: no files copied; no process launched.")
    return EXIT_SUCCESS


def _logs_command(args: argparse.Namespace) -> int:
    context = _resolve_context(args, require_project=False)
    state_path = _session_manifest_path(
        args.session_id,
        code=EXIT_LOGS,
        category="logs/readiness",
    )
    manifest = _read_session_manifest(state_path)
    recorded_profile = manifest.get("profile")
    if recorded_profile:
        recorded_path = Path(str(recorded_profile)).resolve(strict=False)
        if recorded_path != context.profile.profile:
            raise CliError(
                EXIT_LOGS,
                "logs/readiness",
                f"Session {args.session_id} belongs to profile {recorded_path}, "
                f"but the selected profile is {context.profile.profile}. Pass --profile for the session profile.",
            )
    report = collect_log_evidence(
        state_path,
        context.profile,
        context.preferences,
        context.environment,
        full=args.full,
        explicit_unity_log_dir=args.unity_log_dir,
    )
    _print_evidence_report(report, include_logs=True, full_logs=args.full)
    if not report.sources[0].exists:
        raise CliError(
            EXIT_LOGS,
            "logs/readiness",
            "The current BepInEx log is unavailable; readiness cannot be confirmed.",
        )
    _update_evidence_state(state_path, report)
    return EXIT_SUCCESS


def _stop_command(args: argparse.Namespace) -> int:
    detect_supported_environment()
    result = stop_session(args.session_id, force=args.force)
    print(f"Stop session: {result.session_id}")
    print(f"Stop state: {result.state}")
    if result.state == "gone":
        print("Tracked session state already gone; no process was terminated.")
    elif result.state == "exited":
        print("Tracked process already exited; no process was terminated.")
    elif args.force:
        print("Stopped tracked process tree with force.")
    else:
        print("Stopped tracked process tree.")
    return EXIT_SUCCESS


def _clean_command(args: argparse.Namespace) -> int:
    context = _resolve_context(args, require_project=False)
    result = clean_session(
        args.session_id,
        remove_new_files=args.remove_new_files,
        expected_profile=context.profile.profile,
    )
    print(f"Clean session: {result.session_id}")
    print(f"Clean state: {result.state}")
    print(f"Restored files: {len(result.restored_files)}")
    print(f"Removed new files: {len(result.removed_files)}")
    print(f"Retained new files: {len(result.retained_files)}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    return EXIT_SUCCESS


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return _run_command(args)
        if args.command == "logs":
            return _logs_command(args)
        if args.command == "stop":
            return _stop_command(args)
        if args.command == "clean":
            return _clean_command(args)
        if args.command == "status":
            return _status_command(args)
        raise CliError(EXIT_USAGE, "usage/configuration", f"Unknown command: {args.command}")
    except CliError as error:
        print(f"Error [{error.category}]: {error}", file=sys.stderr)
        return error.code
    except (OSError, UnicodeError) as error:
        print(
            f"Error [profile/preferences]: Could not read or inspect the configured paths: {error}",
            file=sys.stderr,
        )
        return EXIT_PROFILE


if __name__ == "__main__":
    raise SystemExit(main())
