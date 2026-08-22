#!/usr/bin/env python3
"""Profile-aware entry point for the Blasphemous mod test workflow.

This first slice is intentionally read-only. It validates the invocation
environment, resolves preferences and a project, preflights a modding
profile, builds or selects one package, validates its deployment plan, and
exposes the dry-run and status seams used by later workflow steps.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass
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


def _reject_symlink_path(path: Path) -> None:
    """Reject a path whose existing components could redirect artifact reads."""

    for component in (path, *path.parents):
        try:
            if component.is_symlink():
                raise CliError(
                    EXIT_PACKAGE,
                    "package artifact",
                    f"Package paths cannot contain symlinks: {component}",
                )
        except OSError as error:
            raise CliError(
                EXIT_PACKAGE,
                "package artifact",
                f"Could not inspect package path {component}: {error}",
            ) from error


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
        return launcher, tuple(warnings)

    candidates = _launcher_candidates(profile, environment)
    for candidate in candidates:
        if candidate.is_file() and (
            candidate.stat().st_size > 0
            and (environment == "Windows" or os.access(candidate, os.X_OK))
        ):
            return candidate.resolve(), tuple(warnings)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blasphemous-modding-test",
        description="Validate a Blasphemous modding profile without changing it.",
        epilog="The first workflow slice is read-only: use 'run --dry-run' or 'status'.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Resolve project/preferences/profile and optionally perform a dry run.",
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


def _run_command(args: argparse.Namespace) -> int:
    if not args.dry_run:
        raise CliError(
            EXIT_USAGE,
            "usage/configuration",
            "The run command is read-only in this workflow slice; pass --dry-run. Deployment and launch are added by later tickets.",
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
        print("Dry run: no profile files copied; no process launched.")
    return EXIT_SUCCESS


def _status_command(args: argparse.Namespace) -> int:
    context = _resolve_context(args, require_project=False)
    _print_context(context)
    print("Test session status: not tracked in this workflow slice")
    print("Status is read-only: no files copied; no process launched.")
    return EXIT_SUCCESS


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return _run_command(args)
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
