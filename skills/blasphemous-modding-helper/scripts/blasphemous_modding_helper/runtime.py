"""Shared runtime, diagnostics, and subprocess foundation for Skill scripts.

This module deliberately contains no ModdingAPI or game-domain behavior. It
only answers whether a Python runtime is usable and provides a safe external
command boundary for later entry points.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple, Union


EXIT_SUCCESS = 0
EXIT_CONFIGURATION = 78
RUNTIME_ERROR_CATEGORY = "configuration/python-runtime"
MIN_PYTHON_VERSION = (3, 9)
DEFAULT_PROBE_TIMEOUT_SECONDS = 10.0
CommandPart = Union[str, Path]


class PythonEnvironmentError(Exception):
    """A classified Python-environment failure that warrants setup retry."""

    def __init__(
        self,
        kind: str,
        message: str,
        hint: str,
        details: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.hint = hint
        self.details = tuple(details)
        self.category = RUNTIME_ERROR_CATEGORY
        self.code = EXIT_CONFIGURATION

    def render(self) -> str:
        lines = [
            f"Error [{self.category}]: {self.message}",
            f"Reason: {self.kind}",
        ]
        lines.extend(f"Detail: {detail}" for detail in self.details)
        if self.kind == "dependency-validation-failed":
            lines.append("Packages installed: none (automatic installation is disabled).")
        lines.append(f"Action: {self.hint}")
        return "\n".join(lines)


class CommandExecutionError(Exception):
    """A non-Python failure from an explicitly requested external command."""

    def __init__(self, operation: str, result: "CommandResult") -> None:
        self.operation = operation
        self.result = result
        detail = result.stderr.strip() or result.stdout.strip() or result.error
        detail = detail or f"exit code {result.returncode}"
        super().__init__(f"{operation} failed: {detail}")


@dataclass(frozen=True)
class Requirement:
    """One intentionally simple requirements.txt entry."""

    name: str
    operator: Optional[str]
    version: Optional[str]
    raw: str
    line_number: int


@dataclass(frozen=True)
class RuntimeInterpreter:
    """A validated Python executable and the version it reported."""

    executable: Path
    version: Tuple[int, int, int]
    source: str

    @property
    def version_text(self) -> str:
        return ".".join(str(part) for part in self.version)


@dataclass(frozen=True)
class DependencyStatus:
    requirement: Requirement
    installed: bool
    installed_version: Optional[str]
    detail: str


@dataclass(frozen=True)
class RuntimeReport:
    """Successful runtime validation result exposed to future entry points."""

    interpreter: RuntimeInterpreter
    requirements_path: Path
    dependencies: Tuple[DependencyStatus, ...]


@dataclass(frozen=True)
class CommandResult:
    """Captured result of one direct, shell-free external command."""

    command: Tuple[str, ...]
    returncode: Optional[int]
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: Optional[str] = None
    duration_seconds: float = 0.0

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.error is None


_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"\s*(?:(?P<operator>==|!=|~=|>=|<=|>|<)\s*(?P<version>[^\s]+))?$"
)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _default_requirements_path() -> Path:
    return Path(__file__).resolve().parents[2] / "requirements.txt"


def _requirements_path(value: Optional[CommandPart]) -> Path:
    return Path(value).expanduser().resolve(strict=False) if value else _default_requirements_path()


def parse_requirements(path: CommandPart) -> Tuple[Requirement, ...]:
    """Parse the small requirements subset supported by the standard library.

    Blank lines and comments are ignored. Each remaining line is a package
    name with an optional ``==``, ``!=``, ``~=`` or comparison constraint.
    Unsupported pip features fail setup explicitly instead of being silently
    ignored.
    """

    requirements_path = Path(path).expanduser().resolve(strict=False)
    if not requirements_path.is_file():
        raise PythonEnvironmentError(
            "missing-requirements-manifest",
            f"Python dependency manifest was not found: {requirements_path}",
            "Restore requirements.txt or pass --requirements PATH, then rerun setup.",
        )

    requirements = []
    try:
        lines = requirements_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise PythonEnvironmentError(
            "unreadable-requirements-manifest",
            f"Python dependency manifest could not be read: {requirements_path}",
            "Fix the manifest encoding or permissions, then rerun setup.",
            (str(error),),
        ) from error

    for line_number, original in enumerate(lines, start=1):
        value = original.split("#", 1)[0].strip()
        if not value:
            continue
        match = _REQUIREMENT.fullmatch(value)
        if not match:
            raise PythonEnvironmentError(
                "invalid-requirements-manifest",
                f"Unsupported dependency declaration on line {line_number} of {requirements_path}",
                "Use a package name with an optional version constraint, then rerun setup.",
                (value,),
            )
        requirements.append(
            Requirement(
                name=match.group("name"),
                operator=match.group("operator"),
                version=match.group("version"),
                raw=value,
                line_number=line_number,
            )
        )
    return tuple(requirements)


def _resolve_candidate(
    explicit: Optional[CommandPart],
    environment: Mapping[str, str],
    host_python: Optional[CommandPart],
) -> Tuple[Path, str]:
    if explicit is not None and str(explicit).strip():
        raw = str(explicit).strip()
        source = "explicit"
    elif environment.get("PYTHON3", "").strip():
        raw = environment["PYTHON3"].strip()
        source = "PYTHON3"
    else:
        raw = str(host_python or sys.executable).strip()
        source = "host"

    if not raw:
        raise PythonEnvironmentError(
            "missing-interpreter",
            "No Python interpreter was selected.",
            "Provide --python PATH or set PYTHON3 to a Python 3.9+ executable, then rerun setup.",
        )

    candidate = Path(raw).expanduser()
    if candidate.is_file():
        return candidate.resolve(strict=False), source

    located = shutil.which(raw)
    if located:
        return Path(located).resolve(strict=False), source

    raise PythonEnvironmentError(
        "missing-interpreter",
        f"Python interpreter was not found: {raw}",
        "Provide --python PATH or set PYTHON3 to a Python 3.9+ executable, then rerun setup.",
    )


_PROBE_CODE = (
    "import json, sys; "
    "print(json.dumps({'version': list(sys.version_info[:3]), "
    "'executable': sys.executable}))"
)


def run_command(
    command: Sequence[CommandPart],
    *,
    cwd: Optional[CommandPart] = None,
    env: Optional[Mapping[str, str]] = None,
    environment: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
    input_text: Optional[str] = None,
) -> CommandResult:
    """Run one external command without a shell and capture text output.

    Nonzero exit codes, missing tools, and timeouts are returned as command
    results. Callers decide whether those outcomes are domain failures. This
    keeps Git, network, dotnet, game, profile, log, and Mod errors separate
    from Python-environment failures.
    """

    if isinstance(command, (str, bytes)) or not command:
        raise TypeError("command must be a non-empty argument sequence")
    if env is not None and environment is not None:
        raise TypeError("pass only one of env or environment")
    argv = tuple(str(part) for part in command)
    execution_environment = env if env is not None else environment
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd) if cwd is not None else None,
            env=dict(execution_environment) if execution_environment is not None else None,
            input=input_text,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return CommandResult(
            command=argv,
            returncode=None,
            stdout=_text(error.stdout),
            stderr=_text(error.stderr),
            timed_out=True,
            error="command timed out",
            duration_seconds=time.monotonic() - started,
        )
    except OSError as error:
        return CommandResult(
            command=argv,
            returncode=None,
            error=f"{type(error).__name__}: {error}",
            duration_seconds=time.monotonic() - started,
        )
    return CommandResult(
        command=argv,
        returncode=completed.returncode,
        stdout=_text(completed.stdout),
        stderr=_text(completed.stderr),
        duration_seconds=time.monotonic() - started,
    )


def start_process(
    command: Sequence[CommandPart],
    *,
    cwd: Optional[CommandPart] = None,
    env: Optional[Mapping[str, str]] = None,
    environment: Optional[Mapping[str, str]] = None,
    creationflags: int = 0,
    start_new_session: bool = False,
) -> subprocess.Popen:
    """Start one direct, shell-free process with an argument sequence.

    Platform adapters choose the small set of process-group options they need;
    this function keeps argument validation and shell handling in one place.
    """

    if isinstance(command, (str, bytes)) or not command:
        raise TypeError("command must be a non-empty argument sequence")
    if env is not None and environment is not None:
        raise TypeError("pass only one of env or environment")
    argv = [str(part) for part in command]
    options = {
        "cwd": str(cwd) if cwd is not None else None,
        "env": dict(env if env is not None else environment)
        if env is not None or environment is not None
        else None,
        "shell": False,
        "start_new_session": start_new_session,
    }
    if creationflags:
        options["creationflags"] = creationflags
    return subprocess.Popen(argv, **options)


def require_success(result: CommandResult, operation: str = "External command") -> CommandResult:
    """Raise a domain command error when a caller explicitly requires success."""

    if not result.succeeded:
        raise CommandExecutionError(operation, result)
    return result


def _merged_environment(environment: Optional[Mapping[str, str]]) -> Optional[Mapping[str, str]]:
    if environment is None:
        return None
    merged = os.environ.copy()
    merged.update(environment)
    return merged


def _probe_interpreter(
    executable: Path,
    timeout: float,
    environment: Optional[Mapping[str, str]] = None,
) -> Tuple[int, int, int]:
    result = run_command(
        (executable, "-c", _PROBE_CODE),
        env=_merged_environment(environment),
        timeout=timeout,
    )
    if not result.succeeded:
        detail = result.stderr.strip() or result.error or result.stdout.strip()
        raise PythonEnvironmentError(
            "interpreter-probe-failed",
            f"Python interpreter could not be inspected: {executable}",
            "Select a working Python 3.9+ executable, then rerun setup.",
            (detail,) if detail else (),
        )
    try:
        payload = json.loads(result.stdout.strip())
        version = tuple(int(part) for part in payload["version"][:3])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise PythonEnvironmentError(
            "interpreter-probe-invalid",
            f"Python interpreter returned an unreadable version response: {executable}",
            "Select a standard Python 3.9+ executable, then rerun setup.",
            (str(error),),
        ) from error
    if len(version) != 3:
        raise PythonEnvironmentError(
            "interpreter-probe-invalid",
            f"Python interpreter returned an incomplete version response: {executable}",
            "Select a standard Python 3.9+ executable, then rerun setup.",
        )
    return version  # type: ignore[return-value]


def resolve_interpreter(
    explicit: Optional[CommandPart] = None,
    *,
    environment: Optional[Mapping[str, str]] = None,
    host_python: Optional[CommandPart] = None,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
) -> RuntimeInterpreter:
    """Resolve and validate explicit Python, PYTHON3, or the host interpreter."""

    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    selected, source = _resolve_candidate(explicit, environment or os.environ, host_python)
    version = _probe_interpreter(selected, timeout, environment)
    if version < MIN_PYTHON_VERSION:
        minimum = ".".join(str(part) for part in MIN_PYTHON_VERSION)
        actual = ".".join(str(part) for part in version)
        raise PythonEnvironmentError(
            "incompatible-interpreter",
            f"Python 3.9 or newer is required; selected interpreter is {actual}: {selected}",
            f"Select or install Python {minimum}+, then rerun setup.",
        )
    return RuntimeInterpreter(selected, version, source)


_DEPENDENCY_PROBE_CODE = r'''
import importlib.metadata
import importlib.util
import json
import sys

items = json.loads(sys.argv[1])
results = []
for item in items:
    name = item["name"]
    distribution_name = name.replace("_", "-")
    try:
        version = importlib.metadata.version(distribution_name)
        results.append({"name": name, "installed": True, "version": version})
        continue
    except importlib.metadata.PackageNotFoundError:
        pass
    module_name = name.replace("-", "_")
    try:
        available = importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        available = False
    results.append({"name": name, "installed": available, "version": None})
print(json.dumps(results))
'''


def _version_key(value: str) -> Tuple[Tuple[int, Union[int, str]], ...]:
    tokens = []
    for token in re.findall(r"[0-9]+|[A-Za-z]+", value.lower()):
        if token.isdigit():
            tokens.append((0, int(token)))
        else:
            tokens.append((1, token))
    while tokens and tokens[-1] == (0, 0):
        tokens.pop()
    return tuple(tokens)


def _numeric_version(value: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value))


def _satisfies_version(installed: str, operator: Optional[str], required: Optional[str]) -> bool:
    if not operator or not required:
        return True
    actual_key = _version_key(installed)
    required_key = _version_key(required)
    if operator == "==":
        return actual_key == required_key
    if operator == "!=":
        return actual_key != required_key
    if operator == ">=":
        return actual_key >= required_key
    if operator == "<=":
        return actual_key <= required_key
    if operator == ">":
        return actual_key > required_key
    if operator == "<":
        return actual_key < required_key
    if operator == "~=":
        required_numbers = _numeric_version(required)
        installed_numbers = _numeric_version(installed)
        if not required_numbers or not installed_numbers:
            return False
        width = max(len(required_numbers), len(installed_numbers), 2)
        lower = required_numbers + (0,) * (width - len(required_numbers))
        actual = installed_numbers + (0,) * (width - len(installed_numbers))
        upper = list(lower)
        upper_index = max(0, len(required_numbers) - 2)
        upper[upper_index] += 1
        for index in range(upper_index + 1, width):
            upper[index] = 0
        return tuple(actual) >= tuple(lower) and tuple(actual) < tuple(upper)
    return False


def validate_dependencies(
    interpreter: RuntimeInterpreter,
    requirements: Sequence[Requirement],
    *,
    environment: Optional[Mapping[str, str]] = None,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
) -> Tuple[DependencyStatus, ...]:
    """Validate manifest entries inside the selected interpreter environment."""

    if not requirements:
        return ()
    payload = [
        {"name": item.name, "operator": item.operator, "version": item.version}
        for item in requirements
    ]
    result = run_command(
        (interpreter.executable, "-c", _DEPENDENCY_PROBE_CODE, json.dumps(payload)),
        env=_merged_environment(environment),
        timeout=timeout,
    )
    if not result.succeeded:
        detail = result.stderr.strip() or result.error or result.stdout.strip()
        raise PythonEnvironmentError(
            "dependency-probe-failed",
            f"Python dependencies could not be inspected with {interpreter.executable}",
            "Repair the selected Python installation, then rerun setup.",
            (detail,) if detail else (),
        )
    try:
        raw_statuses = json.loads(result.stdout.strip())
        by_name = {str(item["name"]): item for item in raw_statuses}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise PythonEnvironmentError(
            "dependency-probe-invalid",
            "Python dependency validation returned an unreadable response.",
            "Repair the selected Python installation, then rerun setup.",
            (str(error),),
        ) from error

    statuses = []
    missing = []
    incompatible = []
    for requirement in requirements:
        item = by_name.get(requirement.name)
        installed = bool(item and item.get("installed"))
        installed_version = item.get("version") if item else None
        detail = "installed"
        if not installed:
            detail = "missing"
            missing.append(requirement.raw)
        elif requirement.operator and not installed_version:
            detail = "version unavailable"
            incompatible.append(requirement.raw)
        elif not _satisfies_version(installed_version or "", requirement.operator, requirement.version):
            detail = f"installed version {installed_version} does not satisfy {requirement.raw}"
            incompatible.append(f"{requirement.raw} ({detail})")
        statuses.append(DependencyStatus(requirement, installed, installed_version, detail))

    if missing or incompatible:
        details = []
        if missing:
            details.append("Missing: " + ", ".join(missing))
        if incompatible:
            details.append("Incompatible: " + ", ".join(incompatible))
        raise PythonEnvironmentError(
            "dependency-validation-failed",
            "Python dependency validation failed.",
            "Install or repair the listed dependencies manually, then rerun setup; automatic installation is disabled.",
            details,
        )
    return tuple(statuses)


def check_environment(
    explicit_python: Optional[CommandPart] = None,
    *,
    requirements_path: Optional[CommandPart] = None,
    environment: Optional[Mapping[str, str]] = None,
    host_python: Optional[CommandPart] = None,
    timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
) -> RuntimeReport:
    """Resolve Python, validate requirements, and return a reusable report."""

    interpreter = resolve_interpreter(
        explicit_python,
        environment=environment,
        host_python=host_python,
        timeout=timeout,
    )
    manifest = _requirements_path(requirements_path)
    requirements = parse_requirements(manifest)
    dependencies = validate_dependencies(
        interpreter,
        requirements,
        environment=environment,
        timeout=timeout,
    )
    return RuntimeReport(interpreter, manifest, dependencies)


def is_python_environment_failure(error: BaseException) -> bool:
    """Return whether setup/runtime configuration should be retried."""

    return isinstance(error, PythonEnvironmentError)


def classify_import_failure(
    error: ImportError,
    dependency: Optional[str] = None,
) -> PythonEnvironmentError:
    """Classify a known Skill-dependency import failure for setup retry."""

    if not isinstance(error, ImportError):
        raise TypeError("error must be an ImportError")
    missing_name = dependency or getattr(error, "name", None) or "an unnamed dependency"
    return PythonEnvironmentError(
        "dependency-import-failed",
        f"Python dependency could not be imported: {missing_name}",
        "Repair the selected Python installation or dependency, then rerun setup.",
        (str(error),),
    )


def format_report(report: RuntimeReport) -> str:
    lines = [
        "PYTHON_RUNTIME_STATUS=ok",
        f"PYTHON3={report.interpreter.executable}",
        f"PYTHON_VERSION={report.interpreter.version_text}",
        f"PYTHON_RUNTIME_SOURCE={report.interpreter.source}",
        f"PYTHON_REQUIREMENTS={report.requirements_path}",
        f"PYTHON_DEPENDENCY_COUNT={len(report.dependencies)}",
    ]
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the Python runtime and Skill dependency manifest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--python",
        dest="explicit_python",
        help="Python executable path or command name to validate.",
    )
    parser.add_argument(
        "--requirements",
        dest="requirements_path",
        help="Dependency manifest; defaults to the Skill's requirements.txt.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_PROBE_TIMEOUT_SECONDS,
        help="Per-probe timeout in seconds (default: %(default)s).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for first-time setup and classified runtime retries."""

    args = _build_parser().parse_args(argv)
    try:
        report = check_environment(
            args.explicit_python,
            requirements_path=args.requirements_path,
            timeout=args.timeout,
        )
    except PythonEnvironmentError as error:
        print(error.render(), file=sys.stderr)
        print("PYTHON_RUNTIME_STATUS=error", file=sys.stderr)
        return error.code
    except (OSError, ValueError) as error:
        diagnostic = PythonEnvironmentError(
            "runtime-validation-failed",
            "Python runtime validation failed unexpectedly.",
            "Repair the selected Python installation or manifest, then rerun setup.",
            (str(error),),
        )
        print(diagnostic.render(), file=sys.stderr)
        print("PYTHON_RUNTIME_STATUS=error", file=sys.stderr)
        return diagnostic.code

    print(format_report(report))
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
