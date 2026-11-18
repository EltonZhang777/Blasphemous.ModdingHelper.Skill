"""Read-only asset identity lookup for an exported Unity project."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .unity_project import (
    EXCLUDED_DIRECTORY_NAMES,
    REFERENCE_UNITY_VERSION,
    SCHEMA_VERSION,
    NavigationError,
    _is_link_like,
    _relative,
    _sorted_warnings,
    _unity_version,
    _validated_project,
    _walk_files,
    _warning,
    _within,
)


GUID_PATTERN = re.compile(r"^[0-9A-Fa-f]{32}$")
META_GUID = re.compile(r"^guid[ \t]*:\s*([0-9A-Fa-f]{32})\s*$", re.MULTILINE)
META_GUID_KEY = re.compile(r"^guid[ \t]*:.*$", re.MULTILINE)
META_VERSION = re.compile(r"^fileFormatVersion:\s*(\d+)\s*$", re.MULTILINE)
META_ANY_GUID = re.compile(r"(?<![0-9A-Fa-f])([0-9A-Fa-f]{32})(?![0-9A-Fa-f])")
MAX_METADATA_VERSION_DIGITS = 9
METADATA_READ_WORKERS = 32
MAX_WARNINGS = 50
ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:|[/\\])")
BINARY_SUFFIXES = frozenset(
    {
        ".7z",
        ".aiff",
        ".assets",
        ".bmp",
        ".bundle",
        ".bytes",
        ".dds",
        ".dll",
        ".exr",
        ".fbx",
        ".flac",
        ".gif",
        ".gz",
        ".hdr",
        ".jpeg",
        ".jpg",
        ".mesh",
        ".mp3",
        ".mp4",
        ".ogg",
        ".otf",
        ".png",
        ".psd",
        ".ress",
        ".so",
        ".tar",
        ".tga",
        ".ttf",
        ".wav",
        ".webm",
        ".zip",
    }
)


def _project_info(
    root: Path, included_roots: Sequence[Path]
) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    version, major, compatible, warnings = _unity_version(root)
    return (
        {
            "root": str(root),
            "unity_version": version,
            "unity_major": major,
            "reference_unity_version": REFERENCE_UNITY_VERSION,
            "unity_major_compatible": compatible,
            "included_roots": [_relative(path, root) for path in included_roots],
        },
        warnings,
    )


def _read_metadata(
    root: Path,
    path: Path,
    stopped: Optional[Callable[[], bool]] = None,
) -> Tuple[Optional[str], Dict[str, object], List[Dict[str, object]]]:
    meta_path = path.with_name(path.name + ".meta")
    meta_relative = _relative(meta_path, root)
    metadata: Dict[str, object] = {
        "path": meta_relative,
        "status": "missing",
        "file_format_version": None,
    }
    if stopped is not None and stopped():
        metadata["status"] = "unusable"
        return None, metadata, [
            _warning("timeout", "Metadata read timed out.", meta_relative)
        ]
    if _is_link_like(meta_path):
        metadata["status"] = "unusable"
        code = (
            "symlink_outside_root"
            if not _within(meta_path, root)
            else "symlink_not_followed"
        )
        return None, metadata, [
            _warning(
                "metadata_unusable",
                "Metadata is a link and was not read.",
                meta_relative,
            ),
            _warning(
                code,
                "Metadata link was not followed.",
                meta_relative,
            ),
        ]
    if not meta_path.exists():
        return None, metadata, [
            _warning(
                "metadata_missing",
                "No sibling .meta file provides a GUID.",
                _relative(path, root),
            )
        ]
    if not meta_path.is_file() or not _within(meta_path, root):
        metadata["status"] = "unusable"
        return None, metadata, [
            _warning(
                "metadata_unusable",
                "The sibling .meta path is not a readable project file.",
                meta_relative,
            )
        ]
    try:
        text = meta_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        metadata["status"] = "unusable"
        return None, metadata, [
            _warning(
                "metadata_unusable",
                f"The sibling .meta file could not be read: {error}",
                meta_relative,
            )
        ]
    if len(META_GUID_KEY.findall(text)) != 1:
        metadata["status"] = "unusable"
        return None, metadata, [
            _warning(
                "metadata_unusable",
                "The sibling .meta file must have exactly one valid GUID.",
                meta_relative,
            )
        ]
    guid_match = META_GUID.search(text)
    if guid_match is None:
        metadata["status"] = "unusable"
        return None, metadata, [
            _warning(
                "metadata_unusable",
                "The sibling .meta file must have exactly one valid GUID.",
                meta_relative,
            )
        ]
    guid = guid_match.group(1).lower()
    metadata["status"] = "present"
    version_match = META_VERSION.search(text)
    raw_version = version_match.group(1) if version_match is not None else None
    if (
        raw_version is not None
        and len(raw_version) > MAX_METADATA_VERSION_DIGITS
    ):
        metadata["status"] = "unusable"
        return guid, metadata, [
            _warning(
                "metadata_unusable",
                "The sibling .meta file has an unsupported fileFormatVersion.",
                meta_relative,
            )
        ]
    try:
        metadata["file_format_version"] = (
            int(raw_version) if raw_version is not None else None
        )
    except ValueError:
        metadata["status"] = "unusable"
        return guid, metadata, [
            _warning(
                "metadata_unusable",
                "The sibling .meta file has an unsupported fileFormatVersion.",
                meta_relative,
            )
        ]
    return guid, metadata, []


def _result(
    root: Path,
    path: Path,
    stopped: Optional[Callable[[], bool]] = None,
) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    is_directory = path.is_dir()
    suffix = path.suffix.lower()
    binary = not is_directory and suffix in BINARY_SUFFIXES
    guid, metadata, warnings = _read_metadata(root, path, stopped)
    result: Dict[str, object] = {
        "path": _relative(path, root),
        "type": "folder" if is_directory else (suffix[1:] or "file"),
        "guid": guid,
        "metadata": metadata,
    }
    if binary:
        warnings.append(
            _warning(
                "binary_not_inspected",
                "Binary asset content was not inspected.",
                result["path"],
            )
        )
    return result, warnings


def _result_key(result: Dict[str, object]) -> Tuple[str, str, str, str]:
    path = str(result["path"])
    return (path.casefold(), path, str(result["type"]), str(result.get("guid") or ""))


def _read_metadata_entry(
    meta_path: Path,
    stopped: Optional[Callable[[], bool]] = None,
) -> Tuple[str, Optional[Path], Optional[str], Tuple[str, ...]]:
    if meta_path.suffix.lower() != ".meta" or _is_link_like(meta_path):
        return "skip", None, None, ()
    target = meta_path.with_suffix("")
    if target.suffix.lower() == ".meta":
        return "skip", None, None, ()
    if stopped is not None and stopped():
        return "timeout", None, None, ()
    try:
        text = meta_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return "unreadable", target, None, ()
    if stopped is not None and stopped():
        return "timeout", None, None, ()
    if len(META_GUID_KEY.findall(text)) != 1:
        candidates = tuple(
            dict.fromkeys(
                match.lower()
                for match in META_ANY_GUID.findall(text)
            )
        )
        return "invalid_guid", target, None, candidates
    guid_match = META_GUID.search(text)
    if guid_match is None:
        candidates = tuple(
            dict.fromkeys(
                match.lower()
                for match in META_ANY_GUID.findall(text)
            )
        )
        return "invalid_guid", target, None, candidates
    guid = guid_match.group(1).lower()
    if _is_link_like(target):
        return "linked_target", target, guid, (guid,)
    if not target.exists():
        return "orphan", target, guid, (guid,)
    version_match = META_VERSION.search(text)
    if version_match is not None:
        raw_version = version_match.group(1)
        if len(raw_version) > MAX_METADATA_VERSION_DIGITS:
            return "invalid_version", target, guid, (guid,)
        try:
            int(raw_version)
        except ValueError:
            return "invalid_version", target, guid, (guid,)
    return "ok", target, guid, (guid,)


def _metadata_entries(
    files: Sequence[Path],
    stopped: Optional[Callable[[], bool]] = None,
) -> Optional[List[Tuple[str, Optional[Path], Optional[str], Tuple[str, ...]]]]:
    if not files:
        return []
    entries: List[Tuple[str, Optional[Path], Optional[str], Tuple[str, ...]]] = []
    with ThreadPoolExecutor(
        max_workers=min(METADATA_READ_WORKERS, len(files))
    ) as executor:
        for start in range(0, len(files), METADATA_READ_WORKERS):
            chunk = files[start:start + METADATA_READ_WORKERS]
            entries.extend(
                executor.map(
                    lambda path: _read_metadata_entry(path, stopped),
                    chunk,
                )
            )
            if stopped is not None and stopped():
                return None
    return entries


def _metadata_targets_for_guids(
    root: Path,
    files: Sequence[Path],
    guids: Sequence[str],
    stopped: Optional[Callable[[], bool]] = None,
    warnings: Optional[List[Dict[str, object]]] = None,
) -> Tuple[Dict[str, List[Path]], bool]:
    wanted = {guid.lower() for guid in guids}
    targets: Dict[str, List[Path]] = defaultdict(list)
    if not wanted:
        return targets, False
    entries = _metadata_entries(files, stopped)
    if entries is None:
        raise NavigationError("timeout", "Asset lookup timed out.")
    incomplete = False
    for meta_path, (status, target, guid, candidates) in zip(files, entries):
        if status == "skip":
            continue
        if status == "timeout":
            raise NavigationError("timeout", "Asset lookup timed out.")
        if status in {"orphan", "linked_target"}:
            if wanted.intersection(candidates):
                incomplete = True
                if warnings is not None:
                    warnings.append(
                        _warning(
                            "metadata_unusable",
                            (
                                "Metadata target is missing, so asset identity is unconfirmed."
                                if status == "orphan"
                                else "Metadata target is a link, so asset identity is unconfirmed."
                            ),
                            _relative(meta_path, root),
                        )
                    )
            continue
        if status in {
            "unreadable",
            "invalid_guid",
            "invalid_version",
        }:
            if status == "unreadable" or wanted.intersection(candidates):
                incomplete = True
            if warnings is not None:
                warnings.append(
                    _warning(
                        "metadata_unusable",
                        "Metadata could not be used while checking asset identity.",
                        _relative(meta_path, root),
                    )
                )
        if status not in {"ok", "invalid_version"} or guid not in wanted:
            continue
        assert target is not None
        if status == "invalid_version":
            incomplete = True
        targets[guid].append(target)
    return targets, incomplete


def _mark_duplicate_guids(
    results: Sequence[Dict[str, object]],
    warnings: List[Dict[str, object]],
    targets_by_guid: Dict[str, List[Path]],
) -> None:
    for result in results:
        guid = result.get("guid")
        if not isinstance(guid, str):
            continue
        targets = targets_by_guid.get(guid, [])
        if len(targets) < 2:
            continue
        metadata = result["metadata"]
        if isinstance(metadata, dict):
            metadata["status"] = "duplicate"
        warnings.append(
            _warning(
                "duplicate_guid",
                f"GUID {guid} identifies {len(targets)} project paths.",
                result["path"],
            )
        )


def _normalize_path(root: Path, included_roots: Sequence[Path], value: str) -> Path:
    if not value or "\x00" in value:
        raise NavigationError("invalid_query", "The path selector is empty or invalid.")
    portable = value.replace("\\", "/")
    if any(part == ".." for part in portable.split("/")):
        raise NavigationError("path_traversal", "Parent-directory traversal is not allowed.")
    if ABSOLUTE_PATH.match(value):
        try:
            absolute = Path(value).expanduser()
        except (OSError, RuntimeError) as error:
            raise NavigationError(
                "invalid_query",
                f"The absolute path selector could not be resolved: {error}",
            ) from error
        raw_absolute = Path(os.path.abspath(os.fspath(absolute)))
        try:
            relative = raw_absolute.relative_to(root)
        except ValueError:
            root_text = os.fspath(root)
            raw_text = os.fspath(raw_absolute)
            if (
                os.name != "nt"
                or not os.path.normcase(raw_text).startswith(
                    os.path.normcase(root_text) + os.sep
                )
            ):
                raise NavigationError(
                    "path_outside_root",
                    "The absolute path selector is outside the Unity project.",
                )
            relative = Path(raw_text[len(root_text) + 1 :])
    else:
        parts = [
            part
            for part in PurePosixPath(portable).parts
            if part not in ("", ".")
        ]
        if not parts:
            raise NavigationError("invalid_query", "The path selector does not name an asset.")
        relative = Path(*parts)
    target = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if _is_link_like(current):
            inside = _within(current, root)
            raise NavigationError(
                "symlink_not_followed" if inside else "symlink_outside_root",
                "The selected path contains a link, which is not followed.",
            )
    try:
        target = target.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise NavigationError(
            "invalid_query",
            f"The selected path could not be resolved: {error}",
        ) from error
    if not _within(target, root):
        raise NavigationError(
            "path_outside_root",
            "The path selector resolves outside the Unity project.",
        )
    try:
        relative = target.relative_to(root)
    except ValueError as error:
        raise NavigationError(
            "path_outside_root",
            "The path selector resolves outside the Unity project.",
        ) from error
    if len(relative.parts) < 2:
        raise NavigationError(
            "invalid_query",
            "The path selector must name an asset below an included root.",
        )
    if relative.parts[0] not in {_relative(path, root) for path in included_roots}:
        raise NavigationError(
            "path_outside_included_roots",
            "The path selector is outside Assets and Packages.",
        )
    excluded_parts = (
        relative.parts[1:] if target.is_dir() else relative.parts[1:-1]
    )
    if EXCLUDED_DIRECTORY_NAMES.intersection(
        part.casefold() for part in excluded_parts
    ):
        raise NavigationError(
            "excluded_path",
            "The path selector names an excluded generated or IDE directory.",
        )
    if os.name == "nt" and any(":" in part for part in relative.parts):
        raise NavigationError(
            "invalid_query",
            "The path selector contains an invalid Windows path segment.",
        )
    if relative.suffix.lower() == ".meta":
        raise NavigationError(
            "metadata_not_asset",
            "A .meta file is metadata evidence, not an asset selector.",
        )
    return target


def asset_query(
    project: Path,
    selector: str,
    value: str,
    stopped: Optional[Callable[[], bool]] = None,
    *,
    duplicate_guid_check: bool = True,
) -> Dict[str, object]:
    """Return the version-1 asset lookup envelope."""

    root = Path(project)
    payload: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "command": "asset",
        "status": "invalid_project",
        "project": {"root": str(root)},
        "query": {"selector": selector, "value": value},
        "results": [],
        "limits": {},
        "truncated": False,
        "warnings": [],
        "error": None,
    }
    warnings: List[Dict[str, object]] = []
    timed_out = False
    try:
        root, included_roots = _validated_project(root)
        project_info, version_warnings = _project_info(root, included_roots)
        payload["project"] = project_info
        payload["status"] = "ok"
        warnings.extend(version_warnings)
        if stopped is not None and stopped():
            timed_out = True
            raise NavigationError("timeout", "Asset lookup timed out.")

        if selector not in {"path", "guid", "name"}:
            raise NavigationError("invalid_query", f"Unknown asset selector: {selector}")
        if not value or "\x00" in value:
            raise NavigationError("invalid_query", "The asset selector value is empty or invalid.")

        if selector == "path":
            target = _normalize_path(root, included_roots, value)
            payload["query"] = {
                "selector": selector,
                "value": _relative(target, root),
            }
            if target.is_file() or target.is_dir():
                result, result_warnings = _result(root, target, stopped)
                results = [result]
                payload["results"] = results
                warnings.extend(result_warnings)
                if duplicate_guid_check and isinstance(result.get("guid"), str):
                    files, scan_warnings = _walk_files(
                        root,
                        included_roots,
                        stopped,
                        (".meta",),
                    )
                    warnings.extend(scan_warnings)
                    targets_by_guid, metadata_incomplete = _metadata_targets_for_guids(
                        root,
                        files,
                        [str(result["guid"])],
                        stopped,
                        warnings,
                    )
                    metadata_incomplete = metadata_incomplete or bool(scan_warnings)
                    if metadata_incomplete:
                        warnings.append(
                            _warning(
                                "metadata_unusable",
                                "Unreadable metadata prevents proving GUID uniqueness.",
                                result["metadata"]["path"],
                            )
                        )
                    _mark_duplicate_guids(
                        results,
                        warnings,
                        targets_by_guid,
                    )
            else:
                payload["status"] = "not_found"
            if stopped is not None and stopped():
                timed_out = True
                raise NavigationError("timeout", "Asset lookup timed out.")
        else:
            if selector == "guid":
                if GUID_PATTERN.fullmatch(value) is None:
                    raise NavigationError(
                        "invalid_guid",
                        "GUID selectors must be exactly 32 hexadecimal characters.",
                    )
                payload["query"] = {"selector": selector, "value": value.lower()}
            else:
                if "/" in value or "\\" in value:
                    raise NavigationError(
                        "invalid_name",
                        "Name selectors must be one basename or extensionless stem.",
                    )
                payload["query"] = {"selector": selector, "value": value}

            files, scan_warnings = _walk_files(
                root,
                included_roots,
                stopped,
                (".meta",) if selector == "guid" else None,
            )
            warnings.extend(scan_warnings)
            targets_by_guid: Dict[str, List[Path]] = {}
            metadata_incomplete = bool(scan_warnings)
            if selector == "guid" and metadata_incomplete:
                warnings.append(
                    _warning(
                        "metadata_unusable",
                        "Unreadable scan areas prevent proving metadata uniqueness.",
                    )
                )
            if stopped is not None and stopped():
                timed_out = True
                raise NavigationError("timeout", "Asset lookup timed out.")
            if selector == "name":
                folded = value.casefold()
                matches = set()
                included = set(included_roots)
                for path in files:
                    if stopped is not None and stopped():
                        timed_out = True
                        raise NavigationError("timeout", "Asset lookup timed out.")
                    if path.suffix.lower() == ".meta":
                        target = path.with_suffix("")
                        if (
                            target.suffix.lower() != ".meta"
                            and target.is_dir()
                            and not _is_link_like(target)
                            and (
                                target.name.casefold() == folded
                                or target.stem.casefold() == folded
                            )
                        ):
                            matches.add(target)
                        continue
                    if path.name.casefold() == folded or path.stem.casefold() == folded:
                        matches.add(path)
                    parent = path.parent
                    while parent not in included:
                        if (
                            parent.name.casefold() == folded
                            or parent.stem.casefold() == folded
                        ):
                            matches.add(parent)
                        parent = parent.parent
            else:
                query_guid = value.lower()
                targets_by_guid, warnings_incomplete = _metadata_targets_for_guids(
                    root,
                    files,
                    [query_guid],
                    stopped,
                    warnings,
                )
                metadata_incomplete = metadata_incomplete or warnings_incomplete
                matches = targets_by_guid.get(query_guid, [])

            results: List[Dict[str, object]] = []
            ordered_matches = sorted(
                matches,
                key=lambda item: (str(item).casefold(), str(item)),
            )
            for target in ordered_matches:
                result, result_warnings = _result(root, target, stopped)
                results.append(result)
                warnings.extend(result_warnings)
            results.sort(key=_result_key)
            if selector == "name" and duplicate_guid_check:
                result_guids = [
                    str(result["guid"])
                    for result in results
                    if isinstance(result.get("guid"), str)
                ]
                targets_by_guid, name_incomplete = _metadata_targets_for_guids(
                    root,
                    [
                        path
                        for path in files
                        if path.suffix.lower() == ".meta"
                    ],
                    result_guids,
                    stopped,
                    warnings,
                )
                metadata_incomplete = (
                    metadata_incomplete or name_incomplete
                )
            if selector == "name" and metadata_incomplete:
                warnings.append(
                    _warning(
                        "metadata_unusable",
                        "Unreadable metadata prevents proving GUID uniqueness.",
                    )
                )
            _mark_duplicate_guids(results, warnings, targets_by_guid)
            payload["results"] = results
            if not results:
                payload["status"] = "not_found"
            elif len(results) > 1:
                payload["status"] = "ambiguous"
            else:
                payload["status"] = "ok"
            if selector == "guid" and metadata_incomplete:
                payload["status"] = "ambiguous"
            if stopped is not None and stopped():
                timed_out = True
                raise NavigationError("timeout", "Asset lookup timed out.")
    except NavigationError as error:
        payload["error"] = {"code": error.code, "message": str(error)}
        if timed_out or error.code == "timeout":
            payload["status"] = "timeout"
        elif payload["status"] != "invalid_project":
            payload["status"] = "invalid_query"
    except OSError as error:
        payload["status"] = "invalid_project"
        payload["error"] = {"code": "invalid_project", "message": str(error)}
    unique_warnings = {
        (
            str(item.get("code", "")),
            str(item.get("path", "")),
            str(item.get("message", "")),
        ): item
        for item in warnings
    }
    ordered_warnings = _sorted_warnings(unique_warnings.values())
    if len(ordered_warnings) > MAX_WARNINGS:
        omitted = len(ordered_warnings) - MAX_WARNINGS
        kept_warnings = ordered_warnings[:MAX_WARNINGS]
        metadata_warning = next(
            (
                warning
                for warning in ordered_warnings
                if warning.get("code") == "metadata_unusable"
            ),
            None,
        )
        if metadata_warning is not None and metadata_warning not in kept_warnings:
            kept_warnings[-1] = metadata_warning
        ordered_warnings = _sorted_warnings(
            [
                *kept_warnings,
                _warning(
                    "warnings_truncated",
                    f"{omitted} warnings were omitted.",
                ),
            ]
        )
    payload["warnings"] = ordered_warnings
    return payload


def asset_exit_code(payload: Dict[str, object]) -> int:
    status = payload.get("status")
    if status == "ok":
        return 0
    if status in {"ambiguous", "not_found"}:
        return 2
    return 3
