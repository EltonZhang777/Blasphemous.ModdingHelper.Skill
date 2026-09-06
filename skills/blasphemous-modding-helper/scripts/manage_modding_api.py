#!/usr/bin/env python3
"""Check or safely update a selector-pinned ModdingAPI checkout."""

from __future__ import annotations

import datetime as _datetime
import errno
import os
import re
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


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
    r"network|curl|connect|resolve host|timed out|timeout|connection refused|"
    r"connection reset|unable to access|could not resolve|failed to connect|http [45]\d\d",
    re.IGNORECASE,
)
VALID_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
VALID_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")
CHECKED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class ManagerError(Exception):
    """A user-facing lifecycle failure with a stable exit code."""

    def __init__(self, code: int, cause: str, next_step: str) -> None:
        super().__init__(cause)
        self.code = code
        self.cause = cause
        self.next_step = next_step


class HelpRequested(Exception):
    """Internal signal for successful help output."""


@dataclass
class ManagerState:
    operation: str = ""
    scope: str = ""
    target_path: Optional[Path] = None
    preferences_file: Optional[Path] = None
    selector: str = ""
    metadata_file: Optional[Path] = None
    dry_run: bool = False
    offline: bool = False
    selector_explicit: bool = False
    target_explicit: bool = False
    preferences_explicit: bool = False
    test_mode: bool = False
    test_repository: str = ""
    test_home: Optional[Path] = None
    test_network_failure: bool = False
    network_state: str = "unknown"
    current_head: str = "<unavailable>"
    worktree_state: str = "unknown"
    lock_path: Optional[Path] = None
    selector_kind: str = ""
    resolved_ref: str = ""
    resolved_tag: str = ""
    resolved_commit: str = ""
    repository: str = OFFICIAL_REPOSITORY
    resolver_error: str = ""


@dataclass(frozen=True)
class CheckoutInspection:
    ok: bool
    current_head: str
    worktree_state: str
    origin: str = ""
    code: int = EXIT_RUNTIME
    cause: str = ""
    next_step: str = ""


def usage() -> str:
    return """Usage:
  manage_modding_api.py --operation check|update [options]

Options:
  --operation check|update  Explicitly validate or refresh the local checkout.
  --scope project|user      Use the approved project or user reference path.
  --target-path PATH        Override the reference checkout path.
  --preferences-file PATH   Read the selector and path from preferences.md.
  --selector SELECTOR       latest, tag:REF, branch:REF, or commit:SHA.
  --metadata-file PATH      Test-only resolver metadata fixture.
  --offline                 Validate only from the sibling lock state.
  --dry-run                 Plan without fetching, checking out, or writing lock state.
  --help                    Show this help.

The lock state is stored beside the checkout as <target-path>.lock. Update and
check never reset, stash, delete, or replace an existing checkout.
"""


def parse_arguments(arguments: Sequence[str]) -> ManagerState:
    state = ManagerState()
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        key = argument.lower()
        if key in ("--help", "-help", "-h"):
            raise HelpRequested()

        if key in (
            "--operation",
            "-operation",
            "--scope",
            "-scope",
            "--target-path",
            "-targetpath",
            "--preferences-file",
            "-preferencesfile",
            "--selector",
            "-selector",
            "--metadata-file",
            "-metadatafile",
            "--test-repository",
            "--test-home",
        ):
            if index + 1 >= len(arguments):
                raise ManagerError(
                    EXIT_USAGE,
                    f"{argument} requires a value",
                    "Use --help to see the supported options.",
                )
            value = arguments[index + 1]
            index += 2
            if key in ("--operation", "-operation"):
                state.operation = value
            elif key in ("--scope", "-scope"):
                state.scope = value
            elif key in ("--target-path", "-targetpath"):
                state.target_path = Path(value).expanduser()
                state.target_explicit = True
            elif key in ("--preferences-file", "-preferencesfile"):
                state.preferences_file = Path(value).expanduser()
                state.preferences_explicit = True
            elif key in ("--selector", "-selector"):
                state.selector = value
                state.selector_explicit = True
            elif key in ("--metadata-file", "-metadatafile"):
                state.metadata_file = Path(value).expanduser()
            elif key == "--test-repository":
                state.test_repository = value
            else:
                state.test_home = Path(value).expanduser()
            continue

        if key in ("--offline", "-offline"):
            state.offline = True
            index += 1
            continue
        if key in ("--dry-run", "-dryrun"):
            state.dry_run = True
            index += 1
            continue
        if key == "--test-mode":
            state.test_mode = True
            index += 1
            continue
        if key == "--test-network-failure":
            state.test_network_failure = True
            index += 1
            continue
        raise ManagerError(
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
        raise ManagerError(
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


def has_key(path: Optional[Path], key: str) -> bool:
    if path is None or not path_exists(path):
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ManagerError(
            EXIT_RUNTIME,
            f"could not read lock state: {path} ({error})",
            "Fix the lock path or permissions, then retry.",
        ) from error
    pattern = re.compile(r"^[ \t]*" + re.escape(key) + r"[ \t]*:")
    return any(pattern.match(line) for line in content.splitlines())


def select_preference_context(state: ManagerState) -> Optional[Path]:
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
    elif state.preferences_file is None and not state.target_explicit:
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
            raise ManagerError(
                EXIT_USAGE,
                f"preferences file scope does not match --scope {state.scope}",
                "Use the preferences path belonging to the selected scope.",
            )
    return default_target


def select_target(state: ManagerState, default_target: Optional[Path]) -> None:
    target = state.target_path
    if not state.target_explicit and state.preferences_file is not None:
        configured = read_key_value(state.preferences_file, "modding_api_reference_path")
        if configured:
            target = Path(configured).expanduser()
    if target is None or not str(target):
        if default_target is not None:
            target = default_target
        else:
            raise ManagerError(
                EXIT_USAGE,
                "no local reference path was provided",
                "Use --target-path, --scope, or configure "
                "modding_api_reference_path in preferences.md.",
            )
    state.target_path = normalize_path(target)
    state.lock_path = Path(str(state.target_path) + ".lock")


def is_valid_ref(value: str) -> bool:
    return bool(
        value
        and VALID_REF.fullmatch(value)
        and ".." not in value
        and not value.endswith("/")
        and "//" not in value
        and "@{" not in value
    )


def select_selector(state: ManagerState) -> None:
    if not state.selector_explicit:
        configured = read_key_value(
            state.preferences_file,
            "modding_api_reference_selector",
        )
        state.selector = configured or "latest"
    if state.selector == "latest":
        state.selector_kind = "release"
        state.resolved_ref = ""
        return
    match = re.fullmatch(r"tag:(.+)", state.selector)
    if match and is_valid_ref(match.group(1)):
        state.selector_kind = "tag"
        state.resolved_ref = match.group(1)
        return
    match = re.fullmatch(r"branch:(.+)", state.selector)
    if match and is_valid_ref(match.group(1)):
        state.selector_kind = "branch"
        state.resolved_ref = match.group(1)
        return
    match = re.fullmatch(r"commit:(.+)", state.selector)
    if match and VALID_COMMIT.fullmatch(match.group(1)):
        state.selector_kind = "commit"
        state.resolved_ref = match.group(1)
        return
    if match:
        raise ManagerError(
            EXIT_USAGE,
            "commit selector must contain a 40-character SHA",
            "Use commit:SHA with an exact 40-character commit.",
        )
    raise ManagerError(
        EXIT_USAGE,
        f"invalid selector: {state.selector}",
        "Use latest, tag:REF, branch:REF, or commit:SHA.",
    )


def validate_test_overrides(state: ManagerState) -> None:
    state.test_mode = state.test_mode or os.environ.get("MODDING_API_TEST_MODE") == "1"
    if not state.test_repository:
        state.test_repository = os.environ.get("MODDING_API_TEST_REPOSITORY", "")
    if state.test_home is None and os.environ.get("MODDING_API_TEST_HOME"):
        state.test_home = Path(os.environ["MODDING_API_TEST_HOME"]).expanduser()
    if (state.metadata_file is not None or state.test_repository) and not state.test_mode:
        raise ManagerError(
            EXIT_USAGE,
            "test-only resolver or repository override requires test mode",
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


def run_git(state: ManagerState, cwd: Path, arguments: Sequence[str]):
    return run_command(
        ("git", *arguments),
        cwd=cwd,
        timeout=GIT_TIMEOUT_SECONDS,
    )


def run_git_or_fail(state: ManagerState, arguments: Sequence[str]):
    assert state.target_path is not None
    result = run_git(state, state.target_path, arguments)
    if not result.succeeded:
        detail = result_detail(result)
        state.network_state = "offline" if network_failure(detail) else "unavailable"
        raise ManagerError(
            EXIT_RUNTIME,
            f"Git operation failed: {detail}",
            "Check network access and the selector; retry without changing the checkout manually.",
        )
    return result


def inspect_checkout(state: ManagerState) -> CheckoutInspection:
    target = state.target_path
    if target is None or not path_exists(target) or not target.is_dir():
        return CheckoutInspection(
            False,
            "<unavailable>",
            "missing",
            code=EXIT_USAGE,
            cause=f"reference path does not exist: {target or '<unset>'}",
            next_step="Run the fresh clone command or provide the configured checkout path.",
        )
    inside = run_git(state, target, ("rev-parse", "--is-inside-work-tree"))
    if not inside.succeeded or inside.stdout.strip() != "true":
        return CheckoutInspection(
            False,
            "<unavailable>",
            "invalid",
            code=EXIT_RUNTIME,
            cause=f"reference path is not a Git worktree: {target}",
            next_step=(
                "Use a valid ModdingAPI checkout or clone a fresh reference into a missing path."
            ),
        )
    head_result = run_git(state, target, ("rev-parse", "HEAD"))
    lines = head_result.stdout.strip().splitlines()
    current_head = lines[0] if head_result.succeeded and lines else "<unavailable>"
    if current_head == "<unavailable>":
        return CheckoutInspection(
            False,
            current_head,
            "invalid",
            code=EXIT_RUNTIME,
            cause="reference worktree has no readable HEAD",
            next_step="Repair the checkout manually or create a fresh reference in another path.",
        )
    status = run_git(state, target, ("status", "--porcelain", "--untracked-files=all"))
    if not status.succeeded:
        return CheckoutInspection(
            False,
            current_head,
            "invalid",
            code=EXIT_RUNTIME,
            cause="could not inspect reference worktree state",
            next_step="Inspect the checkout manually and retry.",
        )
    if status.stdout.strip():
        return CheckoutInspection(
            False,
            current_head,
            "dirty",
            code=EXIT_RUNTIME,
            cause="reference worktree contains local changes",
            next_step=(
                "Commit or remove changes manually, then retry; the manager will not stash, "
                "reset, or delete them."
            ),
        )
    origin = run_git(state, target, ("config", "--get", "remote.origin.url"))
    origin_value = origin.stdout.strip() if origin.succeeded else ""
    if not origin_value:
        return CheckoutInspection(
            False,
            current_head,
            "clean",
            code=EXIT_RUNTIME,
            cause="reference checkout has no origin remote",
            next_step="Add the official ModdingAPI origin manually or create a fresh reference.",
        )
    if canonical_repository(origin_value) != canonical_repository(state.repository):
        return CheckoutInspection(
            False,
            current_head,
            "clean",
            origin=origin_value,
            code=EXIT_RUNTIME,
            cause=(
                "reference origin does not match the official ModdingAPI repository: "
                + origin_value
            ),
            next_step=(
                "Do not use this checkout; configure the official upstream or create a fresh "
                "reference."
            ),
        )
    return CheckoutInspection(True, current_head, "clean", origin=origin_value)


def load_checkout_state(state: ManagerState) -> None:
    inspection = inspect_checkout(state)
    state.current_head = inspection.current_head
    state.worktree_state = inspection.worktree_state
    if not inspection.ok:
        raise ManagerError(inspection.code, inspection.cause, inspection.next_step)


def validate_checkout_shape(state: ManagerState) -> None:
    assert state.target_path is not None
    if state.selector_kind == "branch":
        branch = run_git(state, state.target_path, ("symbolic-ref", "--quiet", "--short", "HEAD"))
        branch_name = branch.stdout.strip() if branch.succeeded else ""
        if branch_name != state.resolved_ref:
            raise ManagerError(
                EXIT_RUNTIME,
                f"current branch is {branch_name}, but selector requires "
                f"branch {state.resolved_ref}",
                "Check out the requested branch manually or use a fresh reference; the manager "
                "will not replace the current branch.",
            )
        upstream = run_git(
            state,
            state.target_path,
            ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
        )
        upstream_name = upstream.stdout.strip() if upstream.succeeded else ""
        if not upstream_name:
            configured_remote = run_git(
                state,
                state.target_path,
                ("config", "--get", f"branch.{state.resolved_ref}.remote"),
            )
            configured_merge = run_git(
                state,
                state.target_path,
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
            raise ManagerError(
                EXIT_RUNTIME,
                f"current branch does not track origin/{state.resolved_ref}",
                "Repair the tracking configuration manually or create a fresh reference; "
                "the manager will not rewrite it.",
            )
        return
    if state.selector_kind in ("release", "tag", "commit"):
        head_reference = run_git(
            state,
            state.target_path,
            ("symbolic-ref", "--quiet", "--short", "HEAD"),
        )
        if head_reference.succeeded:
            raise ManagerError(
                EXIT_RUNTIME,
                "fixed selector requires detached HEAD",
                "Detach HEAD manually at the intended reference or create a fresh fixed-reference "
                "checkout.",
            )
        return
    raise ManagerError(
        EXIT_RUNTIME,
        f"unsupported selector kind: {state.selector_kind}",
        "Use latest, tag:REF, branch:REF, or commit:SHA.",
    )


def canonical_repository(value: str) -> str:
    result = (value or "").strip().rstrip("/")
    match = re.fullmatch(r"/(?:mnt/)?([A-Za-z])/(.*)", result)
    if match:
        result = f"{match.group(1).upper()}:/{match.group(2)}"
    result = result.replace("\\", "/")
    ssh_repository = re.fullmatch(r"git@([^:]+):(.+)", result, re.IGNORECASE)
    if ssh_repository:
        result = f"https://{ssh_repository.group(1)}/{ssh_repository.group(2)}"
    ssh_url = re.fullmatch(r"ssh://git@([^/]+)/(.+)", result, re.IGNORECASE)
    if ssh_url:
        result = f"https://{ssh_url.group(1)}/{ssh_url.group(2)}"
    result = re.sub(r"^https?://(?:www\.)?github\.com/", "https://github.com/", result, flags=re.I)
    if result.lower().endswith(".git"):
        result = result[:-4]
    return result.lower()


def valid_checked_at(value: str) -> bool:
    if not CHECKED_AT.fullmatch(value or ""):
        return False
    try:
        _datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def read_lock(path: Optional[Path]) -> Dict[str, str]:
    return {
        "selector": read_key_value(path, "selector"),
        "resolved_tag": read_key_value(path, "resolved_tag"),
        "resolved_commit": read_key_value(path, "resolved_commit"),
        "checked_at": read_key_value(path, "checked_at"),
        "repository": read_key_value(path, "repository"),
        "has_resolved_tag": "true" if has_key(path, "resolved_tag") else "false",
    }


def lock_matches(state: ManagerState) -> bool:
    lock = read_lock(state.lock_path)
    return bool(
        state.lock_path is not None
        and path_exists(state.lock_path)
        and lock["selector"] == state.selector
        and lock["has_resolved_tag"] == "true"
        and lock["resolved_tag"] == state.resolved_tag
        and lock["resolved_commit"] == state.resolved_commit
        and (
            state.selector_kind != "commit"
            or lock["resolved_commit"].lower() == state.resolved_ref.lower()
        )
        and valid_checked_at(lock["checked_at"])
        and canonical_repository(lock["repository"]) == canonical_repository(state.repository)
    )


def validate_lock(state: ManagerState) -> Dict[str, str]:
    assert state.lock_path is not None
    lock = read_lock(state.lock_path)
    if not path_exists(state.lock_path):
        raise ManagerError(
            EXIT_RUNTIME,
            f"offline validation requires the sibling lock state: {state.lock_path}",
            "Run an online check or update once, then retry offline.",
        )
    if (
        not lock["selector"]
        or lock["has_resolved_tag"] != "true"
        or not lock["resolved_commit"]
        or not lock["checked_at"]
    ):
        raise ManagerError(
            EXIT_RUNTIME,
            f"lock state is incomplete: {state.lock_path}",
            "Run an online check to rebuild the lock state after inspecting the checkout.",
        )
    if not valid_checked_at(lock["checked_at"]):
        raise ManagerError(
            EXIT_RUNTIME,
            "lock state contains an invalid checked_at value",
            "Run an online check to rebuild the lock state.",
        )
    if lock["selector"] != state.selector:
        raise ManagerError(
            EXIT_RUNTIME,
            f"lock selector {lock['selector']} does not match requested selector {state.selector}",
            "Use the locked selector, run an online update for the requested selector, or inspect "
            "the lock manually.",
        )
    if not VALID_COMMIT.fullmatch(lock["resolved_commit"]):
        raise ManagerError(
            EXIT_RUNTIME,
            "lock state contains an invalid resolved commit",
            "Run an online check to rebuild the lock state.",
        )
    if (
        state.selector_kind == "commit"
        and lock["resolved_commit"].lower() != state.resolved_ref.lower()
    ):
        raise ManagerError(
            EXIT_RUNTIME,
            f"lock commit does not match the commit selector {state.selector}",
            "Run an online check for the requested commit or inspect the lock manually.",
        )
    if lock["repository"] and canonical_repository(lock["repository"]) != canonical_repository(
        state.repository
    ):
        raise ManagerError(
            EXIT_RUNTIME,
            "lock state repository does not match the official ModdingAPI repository",
            "Run an online check after correcting the lock state or create a fresh reference.",
        )
    if state.selector == "latest" and not lock["resolved_tag"]:
        raise ManagerError(
            EXIT_RUNTIME,
            "latest lock state has no resolved tag",
            "Run an online check to rebuild the lock state.",
        )
    if state.selector.startswith("tag:") and lock["resolved_tag"] != state.selector[4:]:
        raise ManagerError(
            EXIT_RUNTIME,
            f"lock tag {lock['resolved_tag']} does not match requested selector {state.selector}",
            "Run an online update for the requested tag or inspect the lock manually.",
        )
    state.resolved_tag = lock["resolved_tag"]
    state.resolved_commit = lock["resolved_commit"]
    return lock


def resolve_online(state: ManagerState) -> bool:
    simulated_failure = state.test_network_failure or os.environ.get(
        "MODDING_API_TEST_NETWORK_FAILURE"
    ) == "1"
    if state.test_mode and simulated_failure:
        state.network_state = "offline"
        state.resolver_error = "simulated network failure for repository-owned tests"
        return False
    try:
        resolved = resolve_modding_api.resolve(
            resolve_modding_api.Options(
                selector=state.selector,
                metadata_file=state.metadata_file,
            )
        )
    except resolve_modding_api.ResolutionError as error:
        state.resolver_error = error.cause
        state.network_state = "offline" if network_failure(error.cause) else "unavailable"
        return False
    state.selector_kind, state.resolved_ref, state.resolved_tag, state.resolved_commit = resolved
    if state.test_repository:
        state.repository = state.test_repository
    if not (state.repository and state.selector_kind and state.resolved_commit):
        state.network_state = "unavailable"
        state.resolver_error = "resolver returned incomplete reference metadata"
        return False
    state.network_state = "online"
    return True


def atomic_write(path: Path, content: str) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise OSError(f"write parent does not exist: {parent}")
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


def utc_now() -> str:
    return (
        _datetime.datetime.now(_datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def write_lock_state(state: ManagerState, checked_at: str) -> None:
    assert state.lock_path is not None
    content = (
        f"selector: {state.selector}\n"
        f"resolved_tag: {state.resolved_tag}\n"
        f"resolved_commit: {state.resolved_commit}\n"
        f"checked_at: {checked_at}\n"
        f"repository: {state.repository}\n"
    )
    atomic_write(state.lock_path, content)


def output_values(
    state: ManagerState,
    lock_match: bool,
    checkout_changed: bool,
    lock_updated: bool,
    checked_at: str,
) -> str:
    assert state.target_path is not None
    assert state.lock_path is not None
    return "\n".join(
        (
            f"MODDING_API_OPERATION={state.operation}",
            f"MODDING_API_REFERENCE_PATH={state.target_path}",
            f"MODDING_API_LOCK_PATH={state.lock_path}",
            f"MODDING_API_SELECTOR={state.selector}",
            f"MODDING_API_SELECTOR_KIND={state.selector_kind}",
            f"MODDING_API_RESOLVED_REF={state.resolved_ref}",
            f"MODDING_API_RESOLVED_TAG={state.resolved_tag}",
            f"MODDING_API_RESOLVED_COMMIT={state.resolved_commit}",
            f"MODDING_API_NETWORK={state.network_state}",
            f"MODDING_API_DRY_RUN={'true' if state.dry_run else 'false'}",
            f"MODDING_API_LOCK_MATCH={'true' if lock_match else 'false'}",
            f"MODDING_API_CHECKOUT_CHANGED={'true' if checkout_changed else 'false'}",
            f"MODDING_API_LOCK_UPDATED={'true' if lock_updated else 'false'}",
            f"MODDING_API_CHECKED_AT={checked_at}",
            "",
        )
    )


def run_check(state: ManagerState) -> str:
    if state.current_head != state.resolved_commit:
        raise ManagerError(
            EXIT_RUNTIME,
            f"current HEAD {state.current_head} does not match resolved commit "
            f"{state.resolved_commit}",
            "Run the explicit update operation; check never changes the checkout.",
        )
    matches = lock_matches(state) if path_exists(state.lock_path) else False
    lock_updated = False
    lock = read_lock(state.lock_path)
    checked_at = lock["checked_at"]
    if not matches:
        if state.dry_run:
            checked_at = "<not-written>"
        else:
            checked_at = utc_now()
            try:
                write_lock_state(state, checked_at)
            except OSError as error:
                raise ManagerError(
                    EXIT_RUNTIME,
                    f"could not write lock state: {state.lock_path}",
                    "Ensure the references directory is writable, then rerun check.",
                ) from error
            lock_updated = True
    return output_values(
        state,
        matches if state.dry_run else True,
        False,
        lock_updated,
        checked_at,
    )


def run_update_dry(state: ManagerState) -> str:
    assert state.target_path is not None
    plan_requires_fetch = False
    if state.selector_kind == "branch":
        remote_ref = f"refs/remotes/origin/{state.resolved_ref}"
        remote = run_git(state, state.target_path, ("rev-parse", "--verify", remote_ref))
        if remote.succeeded and remote.stdout.strip():
            if state.current_head != remote.stdout.strip():
                ancestor = run_git(
                    state,
                    state.target_path,
                    ("merge-base", "--is-ancestor", "HEAD", remote_ref),
                )
                if not ancestor.succeeded:
                    raise ManagerError(
                        EXIT_RUNTIME,
                        f"local branch history is divergent from origin/{state.resolved_ref}",
                        "Reconcile the branch manually; the manager will not reset, stash, or "
                        "delete local history.",
                    )
        else:
            plan_requires_fetch = True
    checkout_changed = state.current_head != state.resolved_commit
    result = output_values(state, False, checkout_changed, False, "<not-written>")
    plan = "true" if plan_requires_fetch else "false"
    return result + f"MODDING_API_PLAN_REQUIRES_FETCH={plan}\n"


def run_update(state: ManagerState) -> str:
    assert state.target_path is not None
    checkout_changed = False
    if state.selector_kind == "branch":
        shallow = run_git(state, state.target_path, ("rev-parse", "--is-shallow-repository"))
        refspec = f"+refs/heads/{state.resolved_ref}:refs/remotes/origin/{state.resolved_ref}"
        if shallow.succeeded and shallow.stdout.strip() == "true":
            run_git_or_fail(state, ("fetch", "--unshallow", "origin", refspec))
        else:
            run_git_or_fail(state, ("fetch", "origin", refspec))
        remote_ref = f"refs/remotes/origin/{state.resolved_ref}"
        remote = run_git(state, state.target_path, ("rev-parse", "--verify", remote_ref))
        remote_commit = remote.stdout.strip() if remote.succeeded else ""
        if not remote_commit:
            raise ManagerError(
                EXIT_RUNTIME,
                f"requested branch ref is missing after fetch: {state.resolved_ref}",
                "Verify the branch name and retry; no checkout or lock change was performed.",
            )
        if remote_commit != state.resolved_commit:
            raise ManagerError(
                EXIT_RUNTIME,
                "resolved branch commit changed during update",
                "Retry the update so the selector can be resolved and fetched consistently.",
            )
        if state.current_head != remote_commit:
            ancestor = run_git(
                state,
                state.target_path,
                ("merge-base", "--is-ancestor", "HEAD", remote_ref),
            )
            if not ancestor.succeeded:
                raise ManagerError(
                    EXIT_RUNTIME,
                    f"local branch history is divergent from origin/{state.resolved_ref}",
                    "Reconcile the branch manually; the manager will not reset, stash, or delete "
                    "local history.",
                )
            run_git_or_fail(state, ("merge", "--ff-only", remote_ref))
            checkout_changed = True
    elif state.current_head != state.resolved_commit:
        run_git_or_fail(state, ("fetch", "--depth", "1", "origin", state.resolved_commit))
        run_git_or_fail(state, ("checkout", "--detach", state.resolved_commit))
        checkout_changed = True

    inspection = inspect_checkout(state)
    state.current_head = inspection.current_head
    state.worktree_state = inspection.worktree_state
    if not inspection.ok:
        raise ManagerError(inspection.code, inspection.cause, inspection.next_step)
    if state.current_head != state.resolved_commit:
        raise ManagerError(
            EXIT_RUNTIME,
            f"update ended at {state.current_head} instead of resolved commit "
            f"{state.resolved_commit}",
            "Inspect the checkout manually; no destructive recovery was attempted.",
        )
    validate_checkout_shape(state)
    checked_at = utc_now()
    try:
        write_lock_state(state, checked_at)
    except OSError as error:
        raise ManagerError(
            EXIT_RUNTIME,
            f"checkout updated but lock state could not be written: {state.lock_path}",
            "Write the resolved selector and commit to the sibling lock file, then run check.",
        ) from error
    return output_values(state, True, checkout_changed, True, checked_at)


def report_checkout(state: ManagerState) -> Tuple[str, str]:
    try:
        inspection = inspect_checkout(state)
        return inspection.current_head or "<unavailable>", inspection.worktree_state or "unknown"
    except (OSError, ManagerError, ValueError, TypeError):
        return "<unavailable>", "unknown"


def error_report(state: ManagerState, error: ManagerError) -> str:
    current_head, worktree_state = report_checkout(state)
    target = str(state.target_path) if state.target_path is not None else "<unset>"
    selector = state.selector or "<unset>"
    return "\n".join(
        (
            "[ERROR REPORT]",
            "operation: " + (state.operation or "<unset>"),
            f"target_path: {target}",
            f"selector: {selector}",
            f"current_head: {current_head}",
            f"worktree_state: {worktree_state}",
            f"network_state: {state.network_state or 'unknown'}",
            f"cause: {error.cause}",
            f"next_step: {error.next_step}",
            "",
        )
    )


def execute(state: ManagerState) -> str:
    if not state.operation:
        raise ManagerError(
            EXIT_USAGE,
            "an explicit operation is required",
            "Use --operation check or --operation update.",
        )
    if state.operation not in ("check", "update"):
        raise ManagerError(
            EXIT_USAGE,
            f"invalid operation: {state.operation}",
            "Use --operation check or --operation update.",
        )
    if state.scope and state.scope not in ("project", "user"):
        raise ManagerError(
            EXIT_USAGE,
            f"invalid scope: {state.scope}",
            "Use --scope project or --scope user.",
        )
    validate_test_overrides(state)
    defaults = select_preference_context(state)
    select_target(state, defaults)
    select_selector(state)
    state.repository = state.test_repository or OFFICIAL_REPOSITORY
    load_checkout_state(state)

    offline_validation = False
    if state.offline:
        state.network_state = "offline"
        offline_validation = True
    elif not resolve_online(state):
        if state.operation == "check" and state.network_state == "offline":
            if state.resolver_error:
                sys.stderr.write(state.resolver_error + "\n")
            offline_validation = True
        else:
            if state.resolver_error:
                sys.stderr.write(state.resolver_error + "\n")
            raise ManagerError(
                EXIT_RUNTIME,
                "selector resolution failed",
                "Restore network access or provide a matching local lock state for an offline "
                "check.",
            )

    if offline_validation:
        if state.operation != "check":
            raise ManagerError(
                EXIT_RUNTIME,
                "update cannot refresh a reference while offline",
                "Run check --offline to validate the locked checkout, then retry update online.",
            )
        lock = validate_lock(state)
        validate_checkout_shape(state)
        if state.current_head != state.resolved_commit:
            raise ManagerError(
                EXIT_RUNTIME,
                f"current HEAD {state.current_head} does not match locked commit "
                f"{state.resolved_commit}",
                "Run an online update or inspect the checkout and lock state manually.",
            )
        return output_values(state, True, False, False, lock["checked_at"])

    validate_checkout_shape(state)
    if state.operation == "check":
        return run_check(state)
    if state.dry_run:
        return run_update_dry(state)
    return run_update(state)


def main(arguments: Optional[Sequence[str]] = None) -> int:
    state = ManagerState()
    try:
        state = parse_arguments(arguments if arguments is not None else sys.argv[1:])
        sys.stdout.write(execute(state))
        return EXIT_SUCCESS
    except HelpRequested:
        sys.stdout.write(usage())
        return EXIT_SUCCESS
    except ManagerError as error:
        sys.stderr.write(error_report(state, error))
        return error.code
    except (OSError, ValueError, TypeError) as error:
        unexpected = ManagerError(
            EXIT_RUNTIME,
            f"lifecycle operation failed unexpectedly: {error}",
            "Inspect the error and retry without changing the checkout.",
        )
        sys.stderr.write(error_report(state, unexpected))
        return unexpected.code


if __name__ == "__main__":
    raise SystemExit(main())
