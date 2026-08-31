#!/usr/bin/env python3
"""Create a shallow, selector-pinned ModdingAPI reference checkout."""

from __future__ import annotations

import datetime as _datetime
import errno
import os
import re
import shutil
import stat
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from blasphemous_modding_helper.runtime import run_command  # noqa: E402
import resolve_modding_api  # noqa: E402


EXIT_SUCCESS = 0
EXIT_RUNTIME = 1
EXIT_USAGE = 2
GIT_TIMEOUT_SECONDS = 60.0
OFFICIAL_REPOSITORY = resolve_modding_api.MODDING_API_REPOSITORY
NETWORK_FAILURE = re.compile(
    r"network|connect|resolve host|timed out|timeout|connection refused|"
    r"connection reset|unable to access|could not resolve|failed to connect",
    re.IGNORECASE,
)


class CloneError(Exception):
    """A user-facing clone failure with a stable exit code and next step."""

    def __init__(self, code: int, cause: str, next_step: str) -> None:
        super().__init__(cause)
        self.code = code
        self.cause = cause
        self.next_step = next_step


class HelpRequested(Exception):
    """Internal signal for successful help output."""


@dataclass
class CloneState:
    scope: str = ""
    target_path: Optional[Path] = None
    preferences_file: Optional[Path] = None
    selector: str = ""
    metadata_file: Optional[Path] = None
    target_explicit: bool = False
    preferences_explicit: bool = False
    selector_explicit: bool = False
    test_mode: bool = False
    test_repository: str = ""
    test_home: Optional[Path] = None
    lock_path: Optional[Path] = None
    repository: str = ""
    selector_kind: str = ""
    resolved_ref: str = ""
    resolved_tag: str = ""
    resolved_commit: str = ""
    checked_at: str = ""
    network_state: str = "unknown"
    guard_path: Optional[Path] = None
    staging_path: Optional[Path] = None
    lock_staging_path: Optional[Path] = None
    target_identity: Optional[Tuple[int, int, int, int]] = None
    target_reserved: bool = False
    moved_entries: List[Tuple[str, Tuple[int, int, int, int]]] = field(default_factory=list)
    lock_identity: Optional[Tuple[int, int, int, int]] = None
    lock_moved: bool = False
    preferences_existed: bool = False
    preferences_content: str = ""
    preferences_identity: Optional[Tuple[int, int, int, int]] = None
    preferences_changed: bool = False
    preferences_after_identity: Optional[Tuple[int, int, int, int]] = None


def usage() -> str:
    return """Usage:
  clone_modding_api.py --scope project|user [options]

Options:
  --scope project|user      Use the approved project or user reference path.
  --target-path PATH        Override the reference checkout path.
  --preferences-file PATH   Write the selected path and selector to preferences.md.
  --selector SELECTOR       latest, tag:REF, branch:REF, or commit:SHA.
  --metadata-file PATH      Test-only resolver metadata fixture.
  --help                    Show this help.

Existing targets and sibling lock paths are never replaced.
"""


def parse_arguments(arguments: Sequence[str]) -> CloneState:
    state = CloneState()
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        key = argument.lower()
        if key in ("--help", "-help", "-h"):
            raise HelpRequested()

        def value_for(option: str) -> str:
            if index + 1 >= len(arguments):
                raise CloneError(
                    EXIT_USAGE,
                    f"{option} requires a value",
                    "Use --help to see the supported options.",
                )
            return arguments[index + 1]

        if key in ("--scope", "-scope"):
            state.scope = value_for(argument)
            index += 2
            continue
        if key in ("--target-path", "-targetpath"):
            state.target_path = Path(value_for(argument)).expanduser()
            state.target_explicit = True
            index += 2
            continue
        if key in ("--preferences-file", "-preferencesfile"):
            state.preferences_file = Path(value_for(argument)).expanduser()
            state.preferences_explicit = True
            index += 2
            continue
        if key in ("--selector", "-selector"):
            state.selector = value_for(argument)
            state.selector_explicit = True
            index += 2
            continue
        if key in ("--metadata-file", "-metadatafile"):
            state.metadata_file = Path(value_for(argument)).expanduser()
            index += 2
            continue
        if key == "--test-mode":
            state.test_mode = True
            index += 1
            continue
        if key == "--test-repository":
            state.test_repository = value_for(argument)
            index += 2
            continue
        if key == "--test-home":
            state.test_home = Path(value_for(argument)).expanduser()
            index += 2
            continue
        raise CloneError(
            EXIT_USAGE,
            f"unknown option: {argument}",
            "Use --help to see the supported options.",
        )
    return state


def path_exists(path: Optional[Path]) -> bool:
    if path is None:
        return False
    try:
        os.lstat(path)
        return True
    except FileNotFoundError:
        return False


def remove_tree(path: Path) -> None:
    def on_error(function, name, _error):
        os.chmod(name, stat.S_IWRITE)
        function(name)

    shutil.rmtree(path, onerror=on_error)


def normalize_path(value: Path) -> Path:
    raw = os.path.expanduser(str(value))
    if os.name == "nt":
        match = re.fullmatch(r"/(?:mnt/)?([A-Za-z])(?:/(.*))?", raw)
        if match is None:
            match = re.fullmatch(r"\\(?:mnt\\)?([A-Za-z])(?:\\(.*))?", raw)
        if match:
            suffix = (match.group(2) or "").replace("/", "\\")
            drive_path = f"{match.group(1).upper()}:\\{suffix}"
            raw = drive_path if suffix else f"{match.group(1).upper()}:\\"
        elif os.environ.get("MSYSTEM") and (
            raw in ("/tmp", "\\tmp")
            or raw.startswith("/tmp/")
            or raw.startswith("\\tmp\\")
        ):
            suffix = raw[5:].replace("/", "\\")
            raw = str(Path(tempfile.gettempdir()) / suffix)
    return Path(raw).resolve(strict=False)


def read_key_value(path: Optional[Path], key: str) -> str:
    if path is None or not path_exists(path):
        return ""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise CloneError(
            EXIT_RUNTIME,
            f"could not read preferences file: {path} ({error})",
            "Fix the preferences path or permissions, then retry.",
        ) from error
    pattern = re.compile(r"^[ \t]*" + re.escape(key) + r"[ \t]*:[ \t]*(.*)$")
    for line in content.splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return ""


def select_preference_context(state: CloneState) -> Optional[Path]:
    cwd = Path.cwd()
    home = (
        normalize_path(state.test_home)
        if state.test_mode and state.test_home is not None
        else Path.home()
    )
    project_target = cwd / ".skills" / "blasphemous-modding-helper" / "references" / "modding-api"
    project_preferences = cwd / ".skills" / "blasphemous-modding-helper" / "preferences.md"
    user_target = home / ".skills" / "blasphemous-modding-helper" / "references" / "modding-api"
    user_preferences = home / ".skills" / "blasphemous-modding-helper" / "preferences.md"
    default_target: Optional[Path] = None
    default_preferences: Optional[Path] = None

    if state.scope == "project":
        default_target = project_target
        default_preferences = project_preferences
        if state.preferences_file is None:
            state.preferences_file = default_preferences
    elif state.scope == "user":
        default_target = user_target
        default_preferences = user_preferences
        if state.preferences_file is None:
            state.preferences_file = default_preferences
    elif (
        state.preferences_file is None
        and not state.target_explicit
    ):
        if path_exists(project_preferences):
            default_target = project_target
            default_preferences = project_preferences
            state.preferences_file = project_preferences
        elif path_exists(user_preferences):
            default_target = user_target
            default_preferences = user_preferences
            state.preferences_file = user_preferences

    if state.preferences_file is not None:
        state.preferences_file = normalize_path(state.preferences_file)
        if (
            state.scope
            and state.preferences_explicit
            and default_preferences is not None
            and state.preferences_file != normalize_path(default_preferences)
        ):
            raise CloneError(
                EXIT_USAGE,
                f"preferences file scope does not match --scope {state.scope}",
                "Use the preferences path belonging to the selected scope.",
            )
    return default_target


def select_target(state: CloneState, default_target: Optional[Path]) -> None:
    target = state.target_path
    if not state.target_explicit and state.preferences_file is not None:
        configured = read_key_value(state.preferences_file, "modding_api_reference_path")
        if configured:
            target = Path(configured).expanduser()
    if target is None or not str(target):
        if default_target is not None:
            target = default_target
        else:
            raise CloneError(
                EXIT_USAGE,
                "no local reference path was provided",
                "Use --target-path, --scope, or configure "
                "modding_api_reference_path in preferences.md.",
            )
    state.target_path = normalize_path(target)
    state.lock_path = Path(str(state.target_path) + ".lock")


def select_selector(state: CloneState) -> None:
    if not state.selector_explicit:
        configured = read_key_value(
            state.preferences_file,
            "modding_api_reference_selector",
        )
        state.selector = configured or "latest"
    if not state.selector:
        raise CloneError(
            EXIT_USAGE,
            "no selector was configured",
            "Use --selector or add modding_api_reference_selector to preferences.md.",
        )


def validate_test_overrides(state: CloneState) -> None:
    state.test_mode = state.test_mode or os.environ.get("MODDING_API_TEST_MODE") == "1"
    if not state.test_repository:
        state.test_repository = os.environ.get("MODDING_API_TEST_REPOSITORY", "")
    if state.test_home is None and os.environ.get("MODDING_API_TEST_HOME"):
        state.test_home = Path(os.environ["MODDING_API_TEST_HOME"]).expanduser()
    if (state.metadata_file is not None or state.test_repository) and not state.test_mode:
        raise CloneError(
            EXIT_USAGE,
            "resolver fixtures and repository overrides require test mode",
            "Use the official resolver without fixtures, or run repository-owned tests "
            "with MODDING_API_TEST_MODE=1.",
        )
    if state.metadata_file is not None:
        state.metadata_file = normalize_path(state.metadata_file)


def network_failure(value: str) -> bool:
    return NETWORK_FAILURE.search(value or "") is not None


def result_detail(result: object) -> str:
    stderr = str(getattr(result, "stderr", "") or "").strip()
    stdout = str(getattr(result, "stdout", "") or "").strip()
    error = str(getattr(result, "error", "") or "").strip()
    return stderr or stdout or error or f"exit code {getattr(result, 'returncode', 1)}"


def run_git(state: CloneState, cwd: Path, arguments: Sequence[str]):
    result = run_command(
        ("git", *arguments),
        cwd=cwd,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    detail = result_detail(result)
    if network_failure(detail):
        state.network_state = "failed"
    return result


def run_git_checked(state: CloneState, cwd: Path, arguments: Sequence[str]):
    result = run_git(state, cwd, arguments)
    if not result.succeeded:
        raise CloneError(
            EXIT_RUNTIME,
            f"Git operation failed: {result_detail(result)}",
            "Check Git installation, network access, the selector, and the target path.",
        )
    return result


def clone_current_head(state: CloneState) -> str:
    if state.target_path is None or not path_exists(state.target_path):
        return "<unavailable>"
    try:
        result = run_git(state, state.target_path, ("rev-parse", "HEAD"))
    except OSError:
        return "<unavailable>"
    if not result.succeeded:
        return "<unavailable>"
    lines = result.stdout.strip().splitlines()
    return lines[0] if lines else "<unavailable>"


def clone_worktree_state(state: CloneState) -> str:
    if state.target_path is None or not path_exists(state.target_path):
        return "missing"
    try:
        inside = run_git(state, state.target_path, ("rev-parse", "--is-inside-work-tree"))
        if not inside.succeeded or inside.stdout.strip() != "true":
            return "not-a-git-worktree"
        status = run_git(
            state,
            state.target_path,
            ("status", "--porcelain", "--untracked-files=all"),
        )
        if not status.succeeded:
            return "unknown"
        return "dirty" if status.stdout.strip() else "clean"
    except OSError:
        return "unknown"


def error_report(state: CloneState, error: CloneError) -> str:
    target = str(state.target_path) if state.target_path is not None else "<unset>"
    selector = state.selector or "<unset>"
    return "\n".join(
        (
            "[ERROR REPORT]",
            "operation: clone_modding_api",
            f"target_path: {target}",
            f"selector: {selector}",
            f"current_head: {clone_current_head(state)}",
            f"worktree_state: {clone_worktree_state(state)}",
            f"network_state: {state.network_state}",
            f"cause: {error.cause}",
            f"next_step: {error.next_step}",
            "",
        )
    )


def local_repository_path(repository: str) -> str:
    if re.match(r"^(?:[A-Za-z]:[\\/]|/)", repository):
        return str(normalize_path(Path(repository)))
    return repository


def resolve_reference(state: CloneState) -> None:
    options = resolve_modding_api.Options(
        selector=state.selector,
        metadata_file=state.metadata_file,
    )
    try:
        resolved = resolve_modding_api.resolve(options)
    except resolve_modding_api.ResolutionError as error:
        if network_failure(error.cause):
            state.network_state = "failed"
        raise CloneError(
            error.code,
            f"selector resolution failed: {error.cause}",
            error.next_step,
        ) from error
    state.selector_kind, state.resolved_ref, state.resolved_tag, state.resolved_commit = resolved
    state.repository = state.test_repository or OFFICIAL_REPOSITORY
    if not (
        state.repository
        and state.selector_kind
        and state.resolved_ref
        and state.resolved_commit
    ):
        raise CloneError(
            EXIT_RUNTIME,
            "resolver returned incomplete reference metadata",
            "Retry selector resolution and inspect its error report.",
        )


def path_identity(path: Path) -> Tuple[int, int, int, int]:
    stat = os.lstat(path)
    return (stat.st_dev, stat.st_ino, stat.st_ctime_ns, stat.st_mode)


def same_path_identity(path: Path, identity: Tuple[int, int, int, int]) -> bool:
    try:
        return path_identity(path) == identity
    except OSError:
        return False


def acquire_commit_guard(state: CloneState, parent: Path) -> None:
    guard = parent / f".{state.target_path.name}.clone-lock"
    try:
        guard.mkdir()
    except FileExistsError as error:
        raise CloneError(
            EXIT_RUNTIME,
            "another clone operation is already using the target path",
            "Wait for the other operation to finish or remove the stale clone lock "
            "after confirming no clone is running.",
        ) from error
    state.guard_path = guard


def remove_path(path: Path) -> None:
    mode = os.lstat(path).st_mode
    if os.path.isdir(path) and not os.path.islink(path):
        remove_tree(path)
    elif mode:
        path.unlink()


def cleanup_paths(state: CloneState) -> List[str]:
    errors: List[str] = []
    if state.staging_path is not None and path_exists(state.staging_path):
        try:
            remove_tree(state.staging_path)
        except OSError as error:
            errors.append(f"staging checkout cleanup: {error}")
    if state.lock_staging_path is not None and path_exists(state.lock_staging_path):
        try:
            state.lock_staging_path.unlink()
        except OSError as error:
            errors.append(f"staging lock cleanup: {error}")
    if state.guard_path is not None and path_exists(state.guard_path):
        try:
            state.guard_path.rmdir()
        except OSError as error:
            errors.append(f"clone lock cleanup: {error}")
    return errors


def reserve_target(state: CloneState) -> None:
    assert state.target_path is not None
    if path_exists(state.target_path):
        raise CloneError(
            EXIT_RUNTIME,
            f"target checkout path appeared during clone: {state.target_path}",
            "Another process created the path; choose a different target or retry "
            "after inspecting it.",
        )
    try:
        state.target_path.mkdir()
    except (FileExistsError, NotADirectoryError) as error:
        raise CloneError(
            EXIT_RUNTIME,
            f"target checkout path appeared during clone: {state.target_path}",
            "Another process created the path; choose a different target or retry "
            "after inspecting it.",
        ) from error
    state.target_identity = path_identity(state.target_path)
    state.target_reserved = True


def move_checkout_contents(state: CloneState) -> None:
    assert state.staging_path is not None
    assert state.target_path is not None
    assert state.target_identity is not None
    for entry in list(state.staging_path.iterdir()):
        if not same_path_identity(state.target_path, state.target_identity):
            raise CloneError(
                EXIT_RUNTIME,
                f"reserved target was replaced during clone: {state.target_path}",
                "Inspect the replacement path and retry with a fresh target.",
            )
        destination = state.target_path / entry.name
        if path_exists(destination):
            raise CloneError(
                EXIT_RUNTIME,
                f"target checkout entry appeared during clone: {destination}",
                "Another process wrote into the reserved target; inspect it and retry "
                "with a fresh target.",
            )
        try:
            os.rename(entry, destination)
        except FileExistsError as error:
            raise CloneError(
                EXIT_RUNTIME,
                f"target checkout entry appeared during clone: {destination}",
                "Another process wrote into the reserved target; inspect it and retry "
                "with a fresh target.",
            ) from error
        state.moved_entries.append((entry.name, path_identity(destination)))
        if not same_path_identity(state.target_path, state.target_identity):
            raise CloneError(
                EXIT_RUNTIME,
                f"reserved target was replaced during clone: {state.target_path}",
                "Inspect the replacement path and retry with a fresh target.",
            )


def atomic_write(path: Path, content: str) -> Tuple[int, int, int, int]:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if path_exists(temporary):
            temporary.unlink()
    return path_identity(path)


def write_preferences(state: CloneState) -> Tuple[int, int, int, int]:
    assert state.preferences_file is not None
    existing = state.preferences_content if state.preferences_existed else ""
    lines = existing.splitlines()
    output: List[str] = []
    path_seen = False
    selector_seen = False
    reference_path = str(state.target_path)
    for line in lines:
        if re.match(r"^\s*modding_api_reference_path\s*:", line):
            output.append(f"modding_api_reference_path: {reference_path}")
            path_seen = True
        elif re.match(r"^\s*modding_api_reference_selector\s*:", line):
            output.append(f"modding_api_reference_selector: {state.selector}")
            selector_seen = True
        else:
            output.append(line)
    if not path_seen:
        output.append(f"modding_api_reference_path: {reference_path}")
    if not selector_seen:
        output.append(f"modding_api_reference_selector: {state.selector}")
    return atomic_write(state.preferences_file, "\n".join(output) + "\n")


def write_lock_state(state: CloneState) -> None:
    assert state.lock_staging_path is not None
    content = (
        f"selector: {state.selector}\n"
        f"resolved_tag: {state.resolved_tag}\n"
        f"resolved_commit: {state.resolved_commit}\n"
        f"checked_at: {state.checked_at}\n"
        f"repository: {state.repository}\n"
    )
    atomic_write(state.lock_staging_path, content)


def link_no_replace(state: CloneState) -> None:
    assert state.lock_staging_path is not None
    assert state.lock_path is not None
    source = state.lock_staging_path
    destination = state.lock_path
    try:
        os.link(source, destination)
    except FileExistsError as error:
        raise CloneError(
            EXIT_RUNTIME,
            f"lock state path appeared during clone: {destination}",
            "Another process created the sibling lock; inspect it and retry with "
            "a fresh target.",
        ) from error
    except OSError as error:
        if error.errno not in (errno.EPERM, errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV):
            raise
        try:
            with source.open("rb") as source_handle:
                content = source_handle.read()
            descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            try:
                with os.fdopen(descriptor, "wb") as destination_handle:
                    descriptor = -1
                    destination_handle.write(content)
                    destination_handle.flush()
                    os.fsync(destination_handle.fileno())
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        except FileExistsError as link_error:
            raise CloneError(
                EXIT_RUNTIME,
                f"lock state path appeared during clone: {destination}",
                "Another process created the sibling lock; inspect it and retry with "
                "a fresh target.",
            ) from link_error
    state.lock_identity = path_identity(destination)
    state.lock_moved = True


def capture_preferences(state: CloneState) -> None:
    if state.preferences_file is None:
        return
    state.preferences_existed = path_exists(state.preferences_file)
    if state.preferences_existed:
        try:
            state.preferences_content = state.preferences_file.read_text(encoding="utf-8")
            state.preferences_identity = path_identity(state.preferences_file)
        except (OSError, UnicodeError) as error:
            raise CloneError(
                EXIT_RUNTIME,
                f"could not read preferences file: {state.preferences_file} ({error})",
                "Fix the preferences path or permissions, then retry.",
            ) from error


def rollback(state: CloneState) -> List[str]:
    errors: List[str] = []
    if state.lock_moved and state.lock_path is not None:
        try:
            if (
                state.lock_identity is not None
                and same_path_identity(state.lock_path, state.lock_identity)
            ):
                state.lock_path.unlink()
            elif path_exists(state.lock_path):
                errors.append(f"lock cleanup: path was replaced: {state.lock_path}")
        except OSError as error:
            errors.append(f"lock cleanup: {error}")
    if state.target_reserved and state.target_path is not None:
        try:
            if not same_path_identity(state.target_path, state.target_identity):
                raise OSError(f"reserved target was replaced: {state.target_path}")
            for name, identity in reversed(state.moved_entries):
                entry = state.target_path / name
                if path_exists(entry):
                    if not same_path_identity(entry, identity):
                        raise OSError(f"checkout entry was replaced: {entry}")
                    remove_path(entry)
            remaining = list(state.target_path.iterdir())
            if remaining:
                raise OSError(
                    "checkout cleanup left concurrent entries: "
                    + ", ".join(item.name for item in remaining)
                )
            state.target_path.rmdir()
        except OSError as error:
            errors.append(f"checkout cleanup: {error}")
    if state.preferences_changed and state.preferences_file is not None:
        try:
            if state.preferences_after_identity is not None and not same_path_identity(
                state.preferences_file,
                state.preferences_after_identity,
            ):
                raise OSError(f"preferences file was replaced: {state.preferences_file}")
            if state.preferences_existed:
                atomic_write(state.preferences_file, state.preferences_content)
            elif path_exists(state.preferences_file):
                state.preferences_file.unlink()
        except OSError as error:
            errors.append(f"preferences restore: {error}")
    return errors


def validate_checkout_shape(state: CloneState, checkout: Path) -> None:
    if state.selector_kind == "branch":
        branch = run_git(state, checkout, ("symbolic-ref", "--quiet", "--short", "HEAD"))
        branch_name = branch.stdout.strip() if branch.succeeded else ""
        if branch_name != state.resolved_ref:
            raise CloneError(
                EXIT_RUNTIME,
                f"current branch is {branch_name}, but selector requires "
                f"branch {state.resolved_ref}",
                "Check out the requested branch manually or use a fresh reference; "
                "the manager will not replace the current branch.",
            )
        upstream = run_git(
            state,
            checkout,
            ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
        )
        upstream_name = upstream.stdout.strip() if upstream.succeeded else ""
        if not upstream_name:
            configured_remote = run_git(
                state,
                checkout,
                ("config", "--get", f"branch.{state.resolved_ref}.remote"),
            )
            configured_merge = run_git(
                state,
                checkout,
                ("config", "--get", f"branch.{state.resolved_ref}.merge"),
            )
            if (
                configured_remote.succeeded
                and configured_remote.stdout.strip() == "origin"
                and configured_merge.succeeded
                and configured_merge.stdout.strip() == f"refs/heads/{state.resolved_ref}"
            ):
                upstream_name = f"origin/{state.resolved_ref}"
        if upstream_name != f"origin/{state.resolved_ref}":
            raise CloneError(
                EXIT_RUNTIME,
                f"branch does not track origin/{state.resolved_ref}",
                "Retry the fresh clone with the requested branch selector.",
            )
        return
    if state.selector_kind in ("release", "tag", "commit"):
        head_reference = run_git(
            state,
            checkout,
            ("symbolic-ref", "--quiet", "--short", "HEAD"),
        )
        if head_reference.succeeded:
            raise CloneError(
                EXIT_RUNTIME,
                "fixed reference is not detached",
                "Retry the fresh clone with the requested tag or commit selector.",
            )
        return
    raise CloneError(
        EXIT_RUNTIME,
        f"resolver returned unsupported selector kind: {state.selector_kind}",
        "Use latest, tag:REF, branch:REF, or commit:SHA.",
    )


def utc_now() -> str:
    return (
        _datetime.datetime.now(_datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def output_values(state: CloneState) -> str:
    preferences = str(state.preferences_file) if state.preferences_file is not None else ""
    assert state.target_path is not None
    assert state.lock_path is not None
    return "\n".join(
        (
            "MODDING_API_OPERATION=clone",
            f"MODDING_API_REPOSITORY={state.repository}",
            f"MODDING_API_REFERENCE_PATH={state.target_path}",
            f"MODDING_API_PREFERENCES_FILE={preferences}",
            f"MODDING_API_SELECTOR={state.selector}",
            f"MODDING_API_SELECTOR_KIND={state.selector_kind}",
            f"MODDING_API_RESOLVED_REF={state.resolved_ref}",
            f"MODDING_API_RESOLVED_TAG={state.resolved_tag}",
            f"MODDING_API_RESOLVED_COMMIT={state.resolved_commit}",
            "MODDING_API_SHALLOW=true",
            f"MODDING_API_LOCK_PATH={state.lock_path}",
            f"MODDING_API_CHECKED_AT={state.checked_at}",
            "",
        )
    )


def execute(state: CloneState) -> str:
    assert state.target_path is not None
    assert state.lock_path is not None
    parent = state.target_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    acquire_commit_guard(state, parent)
    try:
        if path_exists(state.target_path):
            raise CloneError(
                EXIT_USAGE,
                f"target path already exists: {state.target_path}",
                "Choose a missing directory or use the later update/check workflow.",
            )
        if path_exists(state.lock_path):
            raise CloneError(
                EXIT_USAGE,
                f"lock path already exists: {state.lock_path}",
                "Inspect or remove the stale lock manually, then retry with a fresh target.",
            )
        capture_preferences(state)
        resolve_reference(state)
        state.staging_path = Path(
            tempfile.mkdtemp(
                prefix=f".{state.target_path.name}.staging-",
                dir=str(parent),
            )
        )
        state.lock_staging_path = parent / (
            f".{state.lock_path.name}.staging-{uuid.uuid4().hex}"
        )
        repository = local_repository_path(state.repository)
        run_git_checked(state, state.staging_path, ("init", "-q"))
        run_git_checked(state, state.staging_path, ("remote", "add", "origin", repository))
        if state.selector_kind in ("release", "tag"):
            run_git_checked(
                state,
                state.staging_path,
                (
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    f"refs/tags/{state.resolved_ref}:refs/tags/{state.resolved_ref}",
                ),
            )
            run_git_checked(
                state,
                state.staging_path,
                ("checkout", "--detach", f"refs/tags/{state.resolved_ref}"),
            )
        elif state.selector_kind == "branch":
            run_git_checked(
                state,
                state.staging_path,
                (
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    f"refs/heads/{state.resolved_ref}:refs/remotes/origin/{state.resolved_ref}",
                ),
            )
            run_git_checked(
                state,
                state.staging_path,
                (
                    "checkout",
                    "-q",
                    "-b",
                    state.resolved_ref,
                    "--track",
                    f"refs/remotes/origin/{state.resolved_ref}",
                ),
            )
        elif state.selector_kind == "commit":
            run_git_checked(
                state,
                state.staging_path,
                ("fetch", "--depth", "1", "origin", state.resolved_commit),
            )
            run_git_checked(
                state,
                state.staging_path,
                ("checkout", "--detach", state.resolved_commit),
            )
        else:
            raise CloneError(
                EXIT_RUNTIME,
                f"resolver returned unsupported selector kind: {state.selector_kind}",
                "Use latest, tag:REF, branch:REF, or commit:SHA.",
            )
        actual_commit = run_git_checked(
            state,
            state.staging_path,
            ("rev-parse", "HEAD"),
        ).stdout.strip()
        if actual_commit.lower() != state.resolved_commit.lower():
            raise CloneError(
                EXIT_RUNTIME,
                f"checkout resolved to {actual_commit} instead of {state.resolved_commit}",
                "Retry the clone and inspect the selected Git reference.",
            )
        shallow_path = state.staging_path / ".git" / "shallow"
        if not path_exists(shallow_path):
            raise CloneError(
                EXIT_RUNTIME,
                "clone is not shallow",
                "Retry with a Git installation that supports shallow fetches.",
            )
        validate_checkout_shape(state, state.staging_path)
        state.checked_at = utc_now()
        write_lock_state(state)
        reserve_target(state)
        move_checkout_contents(state)
        state.staging_path.rmdir()
        state.staging_path = None
        if state.preferences_file is not None:
            state.preferences_changed = True
            state.preferences_after_identity = write_preferences(state)
        link_no_replace(state)
    except CloneError as error:
        rollback_errors = rollback(state)
        cleanup_errors = cleanup_paths(state)
        details = rollback_errors + cleanup_errors
        if details:
            error.next_step += " Rollback also failed: " + "; ".join(details)
        raise
    except (OSError, ValueError, TypeError) as error:
        rollback_errors = rollback(state)
        cleanup_errors = cleanup_paths(state)
        details = rollback_errors + cleanup_errors
        next_step = "Inspect the target path and retry."
        if details:
            next_step = "Rollback failed: " + "; ".join(details)
        raise CloneError(
            EXIT_RUNTIME,
            f"clone operation failed: {error}",
            next_step,
        ) from error
    finalization_errors = cleanup_paths(state)
    if finalization_errors:
        raise CloneError(
            EXIT_RUNTIME,
            "clone completed but cleanup failed",
            "Inspect the checkout and lock state, then remove only confirmed staging "
            "or clone-lock artifacts. Details: "
            + "; ".join(finalization_errors),
        )
    return output_values(state)


def main(arguments: Optional[Sequence[str]] = None) -> int:
    state = CloneState()
    try:
        parsed = parse_arguments(arguments if arguments is not None else sys.argv[1:])
        state = parsed
        if state.scope not in ("", "project", "user"):
            raise CloneError(
                EXIT_USAGE,
                f"invalid scope: {state.scope}",
                "Use --scope project or --scope user.",
            )
        validate_test_overrides(state)
        default_target = select_preference_context(state)
        select_target(state, default_target)
        select_selector(state)
        sys.stdout.write(execute(state))
        return EXIT_SUCCESS
    except HelpRequested:
        sys.stdout.write(usage())
        return EXIT_SUCCESS
    except CloneError as error:
        sys.stderr.write(error_report(state, error))
        return error.code
    except (OSError, ValueError, TypeError) as error:
        unexpected = CloneError(
            EXIT_RUNTIME,
            f"clone operation failed unexpectedly: {error}",
            "Inspect the error and retry.",
        )
        sys.stderr.write(error_report(state, unexpected))
        return unexpected.code


if __name__ == "__main__":
    raise SystemExit(main())
