"""Read-only asset identity lookup for an exported Unity project."""

from __future__ import annotations

import os
import re
from collections import defaultdict
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
META_GUID = re.compile(r"^guid:\s*([0-9A-Fa-f]{32})\s*$", re.MULTILINE)
META_VERSION = re.compile(r"^fileFormatVersion:\s*(\d+)\s*$", re.MULTILINE)
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
    root: Path, path: Path
) -> Tuple[Optional[str], Dict[str, object], List[Dict[str, object]]]:
    meta_path = path.with_name(path.name + ".meta")
    meta_relative = _relative(meta_path, root)
    metadata: Dict[str, object] = {
        "path": meta_relative,
        "status": "missing",
        "file_format_version": None,
    }
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
        text = meta_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        metadata["status"] = "unusable"
        return None, metadata, [
            _warning(
                "metadata_unusable",
                f"The sibling .meta file could not be read: {error}",
                meta_relative,
            )
        ]
    guid_match = META_GUID.search(text)
    if guid_match is None:
        metadata["status"] = "unusable"
        return None, metadata, [
            _warning(
                "metadata_unusable",
                "The sibling .meta file has no valid GUID.",
                meta_relative,
            )
        ]
    version_match = META_VERSION.search(text)
    metadata["status"] = "present"
    try:
        metadata["file_format_version"] = (
            int(version_match.group(1)) if version_match is not None else None
        )
    except ValueError:
        metadata["status"] = "unusable"
        return None, metadata, [
            _warning(
                "metadata_unusable",
                "The sibling .meta file has an unsupported fileFormatVersion.",
                meta_relative,
            )
        ]
    return guid_match.group(1).lower(), metadata, []


def _result(
    root: Path, path: Path
) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    is_directory = path.is_dir()
    suffix = path.suffix.lower()
    binary = not is_directory and suffix in BINARY_SUFFIXES
    guid, metadata, warnings = _read_metadata(root, path)
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


def _metadata_targets_for_guids(
    root: Path,
    files: Sequence[Path],
    guids: Sequence[str],
    stopped: Optional[Callable[[], bool]] = None,
    unusable: Optional[List[str]] = None,
) -> Dict[str, List[Path]]:
    wanted = {guid.lower() for guid in guids}
    targets: Dict[str, List[Path]] = defaultdict(list)
    if not wanted:
        return targets
    for meta_path in files:
        if stopped is not None and stopped():
            break
        if meta_path.suffix.lower() != ".meta" or _is_link_like(meta_path):
            continue
        target = meta_path.with_suffix("")
        if target.suffix.lower() == ".meta" or not target.exists():
            continue
        if _is_link_like(target):
            continue
        try:
            text = meta_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            if unusable is not None:
                unusable.append(_relative(meta_path, root))
            continue
        guid_match = META_GUID.search(text)
        if guid_match is None:
            if unusable is not None:
                unusable.append(_relative(meta_path, root))
            continue
        guid = guid_match.group(1).lower()
        if guid not in wanted:
            continue
        version_match = META_VERSION.search(text)
        if version_match is not None:
            try:
                int(version_match.group(1))
            except ValueError:
                if unusable is not None:
                    unusable.append(_relative(meta_path, root))
                continue
        targets[guid].append(target)
    return targets


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
                result, result_warnings = _result(root, target)
                results = [result]
                payload["results"] = results
                warnings.extend(result_warnings)
                if isinstance(result.get("guid"), str):
                    files, scan_warnings = _walk_files(root, included_roots, stopped)
                    warnings.extend(scan_warnings)
                    _mark_duplicate_guids(
                        results,
                        warnings,
                        _metadata_targets_for_guids(
                            root,
                            files,
                            [str(result["guid"])],
                            stopped,
                        ),
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

            files, scan_warnings = _walk_files(root, included_roots, stopped)
            warnings.extend(scan_warnings)
            targets_by_guid: Dict[str, List[Path]] = {}
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
                unusable_metadata_paths: List[str] = []
                targets_by_guid = _metadata_targets_for_guids(
                    root,
                    files,
                    [query_guid],
                    stopped,
                    unusable_metadata_paths,
                )
                matches = targets_by_guid.get(query_guid, [])
                if not matches:
                    for relative in sorted(set(unusable_metadata_paths)):
                        warnings.append(
                            _warning(
                                "metadata_unusable",
                                "Metadata could not be used while resolving the GUID.",
                                relative,
                            )
                        )

            results: List[Dict[str, object]] = []
            ordered_matches = sorted(
                matches,
                key=lambda item: (str(item).casefold(), str(item)),
            )
            for target in ordered_matches:
                result, result_warnings = _result(root, target)
                results.append(result)
                warnings.extend(result_warnings)
            results.sort(key=_result_key)
            if selector == "name":
                result_guids = [
                    str(result["guid"])
                    for result in results
                    if isinstance(result.get("guid"), str)
                ]
                targets_by_guid = _metadata_targets_for_guids(
                    root,
                    files,
                    result_guids,
                    stopped,
                )
            _mark_duplicate_guids(results, warnings, targets_by_guid)
            payload["results"] = results
            if not results:
                payload["status"] = "not_found"
            elif len(results) > 1:
                payload["status"] = "ambiguous"
            else:
                payload["status"] = "ok"
            if stopped is not None and stopped():
                timed_out = True
                raise NavigationError("timeout", "Asset lookup timed out.")
    except NavigationError as error:
        payload["error"] = {"code": error.code, "message": str(error)}
        if timed_out:
            payload["status"] = "timeout"
        elif payload["status"] != "invalid_project":
            payload["status"] = "invalid_query"
    except OSError as error:
        payload["status"] = "invalid_project"
        payload["error"] = {"code": "invalid_project", "message": str(error)}
    payload["warnings"] = _sorted_warnings(warnings)
    return payload


def asset_exit_code(payload: Dict[str, object]) -> int:
    status = payload.get("status")
    if status == "ok":
        return 0
    if status in {"ambiguous", "not_found"}:
        return 2
    return 3
