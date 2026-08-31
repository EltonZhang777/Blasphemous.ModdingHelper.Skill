#!/usr/bin/env python3
"""Resolve a ModdingAPI selector to a stable reference and canonical URLs."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from blasphemous_modding_helper.runtime import CommandResult, run_command  # noqa: E402


EXIT_SUCCESS = 0
EXIT_RUNTIME = 1
EXIT_USAGE = 2

MODDING_API_REPOSITORY = "https://github.com/BrandenEK/Blasphemous.ModdingAPI.git"
MODDING_API_WEB_REPOSITORY = "https://github.com/BrandenEK/Blasphemous.ModdingAPI"
MODDING_API_RELEASE_API = (
    "https://api.github.com/repos/BrandenEK/Blasphemous.ModdingAPI/releases/latest"
)
NETWORK_TIMEOUT_SECONDS = 60.0
GIT_TIMEOUT_SECONDS = 60.0
VALID_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
VALID_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")


class ResolutionError(Exception):
    """A user-facing resolver failure with a stable exit code and next step."""

    def __init__(
        self,
        code: int,
        cause: str,
        next_step: str,
        selector: Optional[str] = None,
    ) -> None:
        super().__init__(cause)
        self.code = code
        self.cause = cause
        self.next_step = next_step
        self.selector = selector


@dataclass(frozen=True)
class Options:
    selector: str = "latest"
    metadata_file: Optional[Path] = None


@dataclass(frozen=True)
class ReleaseMetadata:
    tag: Optional[str]
    draft: Optional[bool]
    prerelease: Optional[bool]
    resolved_ref: Optional[str]
    resolved_commit: Optional[str]
    published_at: Optional[str]


def usage() -> str:
    return """Usage:
  resolve_modding_api.py [--selector SELECTOR] [--metadata-file PATH]

Selectors:
  latest             Resolve the newest stable GitHub Release.
  tag:REF            Resolve an explicit Git tag.
  branch:REF         Resolve an explicit Git branch.
  commit:SHA         Resolve an exact 40-character commit.

Options:
  --metadata-file PATH
      Read Release-shaped JSON from PATH instead of the GitHub Releases API.
      This is intended for deterministic tests and offline fixture use.
  --help
"""


def error_report(selector: str, error: ResolutionError) -> str:
    return "\n".join(
        (
            "[ERROR REPORT]",
            "operation: resolve_modding_api",
            f"selector: {selector}",
            f"cause: {error.cause}",
            f"next_step: {error.next_step}",
        )
    )


def parse_arguments(arguments: Sequence[str]) -> Options:
    selector = "latest"
    metadata_file: Optional[Path] = None
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in ("--help", "-h", "-Help"):
            print(usage(), end="")
            raise SystemExit(EXIT_SUCCESS)
        if argument in ("--selector", "-Selector", "-selector"):
            if index + 1 >= len(arguments):
                raise ResolutionError(
                    EXIT_USAGE,
                    "--selector requires a value",
                    "Use latest, tag:REF, branch:REF, or commit:SHA.",
                    selector,
                )
            selector = arguments[index + 1]
            index += 2
            continue
        if argument in ("--metadata-file", "-MetadataFile", "-metadatafile"):
            if index + 1 >= len(arguments):
                raise ResolutionError(
                    EXIT_USAGE,
                    "--metadata-file requires a path",
                    "Provide a readable JSON fixture path.",
                    selector,
                )
            metadata_file = Path(arguments[index + 1]).expanduser()
            index += 2
            continue
        raise ResolutionError(
            EXIT_USAGE,
            f"unknown option: {argument}",
            "Use --help to see the supported options.",
            selector,
        )
    return Options(selector=selector, metadata_file=metadata_file)


def is_valid_ref(value: Any) -> bool:
    if not isinstance(value, str) or not value or not VALID_REF.fullmatch(value):
        return False
    return (
        ".." not in value
        and not value.endswith("/")
        and "//" not in value
        and "@{" not in value
    )


def is_valid_commit(value: Any) -> bool:
    return isinstance(value, str) and VALID_COMMIT.fullmatch(value) is not None


def require_ref(value: str, description: str) -> None:
    if not is_valid_ref(value):
        raise ResolutionError(
            EXIT_USAGE,
            f"invalid {description}: {value}",
            "Use a valid non-empty Git reference.",
        )


def require_commit(value: str, description: str, code: int = EXIT_USAGE) -> None:
    if not is_valid_commit(value):
        raise ResolutionError(
            code,
            f"invalid {description}: {value}",
            "Use exactly 40 hexadecimal characters.",
        )


def read_json_file(path: Path) -> Any:
    if not path.is_file():
        raise ResolutionError(
            EXIT_USAGE,
            f"metadata file does not exist: {path}",
            "Provide a readable Release metadata file or omit --metadata-file.",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        raise ResolutionError(
            EXIT_USAGE,
            f"could not read metadata file: {path} ({error})",
            "Check the path and file permissions.",
        ) from error
    except json.JSONDecodeError as error:
        raise ResolutionError(
            EXIT_USAGE,
            f"metadata file is not valid JSON: {path} (parse error: {error.msg})",
            "Repair the JSON fixture and retry.",
        ) from error


def fetch_latest_json() -> Any:
    request = Request(
        MODDING_API_RELEASE_API,
        headers={"User-Agent": "blasphemous-modding-helper"},
    )
    try:
        with urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError) as error:
        raise ResolutionError(
            EXIT_RUNTIME,
            "could not retrieve the official GitHub latest Release metadata",
            "Check network access and retry, or provide an explicit selector.",
        ) from error
    try:
        return json.loads(payload)
    except json.JSONDecodeError as error:
        raise ResolutionError(
            EXIT_RUNTIME,
            "the official GitHub Release response is not valid JSON",
            "Retry the request or use an explicit selector.",
        ) from error


def load_metadata(metadata_file: Optional[Path]) -> Any:
    return read_json_file(metadata_file) if metadata_file is not None else fetch_latest_json()


def optional_string(record: dict, key: str) -> Optional[str]:
    value = record.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ResolutionError(
            EXIT_USAGE,
            f"Release metadata field {key} must be a string",
            "Use the official Releases response or repair the fixture.",
        )
    return value


def parse_release(record: Any, require_release_fields: bool = False) -> ReleaseMetadata:
    if not isinstance(record, dict):
        raise ResolutionError(
            EXIT_USAGE,
            "Release metadata entry is not an object",
            "Use the official Releases response or repair the fixture.",
        )

    tag = optional_string(record, "tag_name")
    if require_release_fields and tag is None:
        raise ResolutionError(
            EXIT_USAGE,
            "Release metadata is missing tag_name",
            "Use the official Releases response or repair the fixture.",
        )
    if tag is not None:
        require_ref(tag, "Release tag")
    draft = record.get("draft")
    prerelease = record.get("prerelease")
    for key, label in (("draft", "draft"), ("prerelease", "prerelease")):
        if (require_release_fields or key in record) and not isinstance(record.get(key), bool):
            raise ResolutionError(
                EXIT_USAGE,
                f"Release metadata is missing a boolean {label} field",
                "Use the official Releases response or repair the fixture.",
            )
    resolved_ref = optional_string(record, "resolved_ref")
    if resolved_ref is not None:
        require_ref(resolved_ref, "resolved_ref")
    resolved_commit = optional_string(record, "resolved_commit")
    if resolved_commit is not None:
        require_commit(resolved_commit, "resolved_commit", EXIT_USAGE)
    published_at = optional_string(record, "published_at")
    return ReleaseMetadata(
        tag=tag,
        draft=draft,
        prerelease=prerelease,
        resolved_ref=resolved_ref,
        resolved_commit=resolved_commit,
        published_at=published_at,
    )


def release_entries(document: Any, require_release_fields: bool = False) -> List[ReleaseMetadata]:
    if isinstance(document, list):
        return [parse_release(entry, require_release_fields) for entry in document]
    return [parse_release(document, require_release_fields)]


def select_latest(document: Any) -> ReleaseMetadata:
    entries = release_entries(document, require_release_fields=True)
    if not entries:
        raise ResolutionError(
            EXIT_USAGE,
            "Release metadata did not contain any releases",
            "Use the official Releases response or repair the fixture.",
        )
    stable = [
        entry
        for entry in entries
        if entry.tag is not None and entry.draft is False and entry.prerelease is False
    ]
    if stable:
        dated = [entry for entry in stable if entry.published_at is not None]
        if dated:
            return max(dated, key=lambda entry: entry.published_at or "")
        return stable[0]
    selected = entries[0]
    if selected.draft is True:
        raise ResolutionError(
            EXIT_USAGE,
            "the selected latest Release is a draft",
            "Publish a stable Release or choose an explicit selector.",
        )
    if selected.prerelease is True:
        raise ResolutionError(
            EXIT_USAGE,
            "the selected latest Release is a prerelease",
            "Publish a stable Release or choose an explicit selector.",
        )
    raise ResolutionError(
        EXIT_USAGE,
        "no non-draft, non-prerelease Release was available",
        "Publish a stable Release or choose an explicit selector.",
    )


def read_optional_metadata_commit(metadata_file: Path, expected_ref: str) -> Optional[str]:
    document = load_metadata(metadata_file)
    entries = release_entries(document)
    if len(entries) != 1:
        raise ResolutionError(
            EXIT_USAGE,
            "explicit selector metadata must contain one object",
            "Repair the fixture or omit --metadata-file.",
        )
    metadata = entries[0]
    if metadata.resolved_commit is not None and metadata.resolved_ref != expected_ref:
        raise ResolutionError(
            EXIT_USAGE,
            f"metadata resolved_ref does not match the requested reference: {expected_ref}",
            "Repair the fixture or omit --metadata-file.",
        )
    return metadata.resolved_commit


def resolve_remote_commit(kind: str, reference: str) -> str:
    if kind == "tag":
        plain_ref = f"refs/tags/{reference}"
        peeled_ref = f"{plain_ref}^{{}}"
        arguments = (
            "git",
            "ls-remote",
            "--tags",
            MODDING_API_REPOSITORY,
            plain_ref,
            peeled_ref,
        )
    else:
        plain_ref = f"refs/heads/{reference}"
        peeled_ref = None
        arguments = (
            "git",
            "ls-remote",
            "--heads",
            MODDING_API_REPOSITORY,
            plain_ref,
        )
    result = run_command(arguments, timeout=GIT_TIMEOUT_SECONDS)
    missing_tool = result.returncode is None and result.error and re.search(
        r"FileNotFoundError|command not found|not found|WinError 2|No such file",
        result.error,
        re.IGNORECASE,
    )
    if missing_tool:
        raise ResolutionError(
            EXIT_RUNTIME,
            f"git is required to resolve the explicit {kind} selector",
            "Install Git or use an exact commit selector.",
        )
    if not result.succeeded:
        raise ResolutionError(
            EXIT_RUNTIME,
            f"could not query the ModdingAPI Git repository for {kind} {reference}",
            "Check network access and the reference name.",
        )

    plain_commit: Optional[str] = None
    peeled_commit: Optional[str] = None
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        commit, ref = parts
        if peeled_ref is not None and ref == peeled_ref:
            peeled_commit = commit
            break
        if ref == plain_ref:
            plain_commit = commit
    commit = peeled_commit or plain_commit
    if commit is None:
        raise ResolutionError(
            EXIT_RUNTIME,
            f"the ModdingAPI {kind} {reference} was not found or did not resolve to a commit",
            "Check the selector spelling or choose a known reference.",
        )
    require_commit(commit, f"remote {kind} resolution", EXIT_RUNTIME)
    return commit


def resolve(options: Options) -> Tuple[str, str, str, str]:
    selector = options.selector
    if selector == "latest":
        metadata = select_latest(load_metadata(options.metadata_file))
        if metadata.tag is None:
            raise ResolutionError(
                EXIT_USAGE,
                "Release metadata is missing tag_name",
                "Use the official Releases response or repair the fixture.",
            )
        resolved_ref = metadata.tag
        resolved_tag = metadata.tag
        resolved_commit = metadata.resolved_commit or resolve_remote_commit("tag", resolved_tag)
        return "release", resolved_ref, resolved_tag, resolved_commit

    if selector.startswith("tag:"):
        resolved_tag = selector[4:]
        require_ref(resolved_tag, "tag selector")
        resolved_commit = None
        if options.metadata_file is not None:
            resolved_commit = read_optional_metadata_commit(options.metadata_file, resolved_tag)
        resolved_commit = resolved_commit or resolve_remote_commit("tag", resolved_tag)
        return "tag", resolved_tag, resolved_tag, resolved_commit

    if selector.startswith("branch:"):
        resolved_ref = selector[7:]
        require_ref(resolved_ref, "branch selector")
        resolved_commit = None
        if options.metadata_file is not None:
            resolved_commit = read_optional_metadata_commit(options.metadata_file, resolved_ref)
        resolved_commit = resolved_commit or resolve_remote_commit("branch", resolved_ref)
        return "branch", resolved_ref, "", resolved_commit

    if selector.startswith("commit:"):
        resolved_commit = selector[7:]
        require_commit(resolved_commit, "commit selector")
        return "commit", resolved_commit, "", resolved_commit

    raise ResolutionError(
        EXIT_USAGE,
        f"invalid selector: {selector}",
        "Use latest, tag:REF, branch:REF, or commit:SHA; main is not an implicit selector.",
    )


def output_values(selector: str, resolved: Tuple[str, str, str, str]) -> str:
    selector_kind, resolved_ref, resolved_tag, resolved_commit = resolved
    return "\n".join(
        (
            f"MODDING_API_REPOSITORY={MODDING_API_REPOSITORY}",
            f"MODDING_API_SELECTOR={selector}",
            f"MODDING_API_SELECTOR_KIND={selector_kind}",
            f"MODDING_API_RESOLVED_REF={resolved_ref}",
            f"MODDING_API_RESOLVED_TAG={resolved_tag}",
            f"MODDING_API_RESOLVED_COMMIT={resolved_commit}",
            f"MODDING_API_DOCS_URL={MODDING_API_WEB_REPOSITORY}/tree/{resolved_ref}/docs",
            f"MODDING_API_SOURCE_URL={MODDING_API_WEB_REPOSITORY}/tree/{resolved_ref}",
        )
    )


def main(arguments: Optional[Sequence[str]] = None) -> int:
    selector = "latest"
    try:
        options = parse_arguments(arguments if arguments is not None else sys.argv[1:])
        selector = options.selector
        resolved = resolve(options)
        print(output_values(options.selector, resolved))
        return EXIT_SUCCESS
    except SystemExit as exit_signal:
        return int(exit_signal.code)
    except ResolutionError as error:
        print(error_report(error.selector or selector, error), file=sys.stderr)
        return error.code
    except (OSError, ValueError, TypeError) as error:
        unexpected = ResolutionError(
            EXIT_RUNTIME,
            f"resolver failed unexpectedly: {error}",
            "Check the Python runtime and retry with a valid selector or fixture.",
        )
        print(error_report(selector, unexpected), file=sys.stderr)
        return unexpected.code


if __name__ == "__main__":
    raise SystemExit(main())
