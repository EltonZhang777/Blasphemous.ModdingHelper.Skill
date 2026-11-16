"""Resolve exported Unity scene sets and report serialized scene evidence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .unity_project import (
    EXCLUDED_DIRECTORY_NAMES,
    REFERENCE_UNITY_VERSION,
    SCENE_LAYERS,
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
from .unity_serialized import SerializedError, parse_serialized_file


SceneError = SerializedError


def _new_payload(project: Path, query: Dict[str, object]) -> Dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "scene",
        "status": "invalid_project",
        "project": {"root": str(project)},
        "query": query,
        "results": [],
        "limits": {},
        "truncated": False,
        "warnings": [],
        "error": None,
    }


def _project_data(
    root: Path,
    included_roots: Sequence[Path],
    warnings: List[Dict[str, object]],
) -> Dict[str, object]:
    version, major, compatible, version_warnings = _unity_version(root)
    warnings.extend(version_warnings)
    return {
        "root": str(root),
        "unity_version": version,
        "unity_major": major,
        "reference_unity_version": REFERENCE_UNITY_VERSION,
        "unity_major_compatible": compatible,
        "included_roots": [_relative(path, root) for path in included_roots],
    }


def _layer_and_stem(path: Path) -> Tuple[Optional[str], str]:
    for layer in SCENE_LAYERS:
        if path.stem.endswith(layer) and len(path.stem) > len(layer):
            return layer, path.stem[: -len(layer)]
    return None, path.stem


def _group_key(path: Path, root: Path) -> Tuple[str, str, str]:
    layer, stem = _layer_and_stem(path)
    return (
        _relative(path.parent, root),
        stem,
        "set" if layer else "standalone",
    )


def _discover_groups(files: Sequence[Path], root: Path) -> List[Dict[str, object]]:
    groups: Dict[Tuple[str, str, str], Dict[str, object]] = {}
    for path in files:
        if path.suffix.lower() != ".unity":
            continue
        key = _group_key(path, root)
        group = groups.setdefault(
            key,
            {
                "directory": key[0],
                "logical_name": key[1],
                "members": [],
            },
        )
        layer, _ = _layer_and_stem(path)
        group["members"].append({"layer": layer, "path": path})
    for group in groups.values():
        group["members"].sort(
            key=lambda member: (
                SCENE_LAYERS.index(member["layer"]) if member["layer"] else -1,
                str(member["path"]),
            )
        )
    return sorted(
        groups.values(),
        key=lambda group: (
            str(group["directory"]),
            str(group["logical_name"]),
            str(group["members"][0]["layer"] or ""),
        ),
    )


def _scene_result(
    group: Dict[str, object],
    root: Path,
    evidence: Sequence[Dict[str, object]] = (),
    requested_path: Optional[str] = None,
) -> Dict[str, object]:
    members = [
        {"layer": member["layer"], "path": _relative(member["path"], root)}
        for member in group["members"]
    ]
    present_layers = [
        layer for layer in SCENE_LAYERS if any(member["layer"] == layer for member in members)
    ]
    is_standalone = all(member["layer"] is None for member in members)
    missing_layers = [] if is_standalone else [
        layer for layer in SCENE_LAYERS if layer not in present_layers
    ]
    kind = "standalone" if is_standalone else ("complete" if not missing_layers else "incomplete")
    return {
        "logical_name": group["logical_name"],
        "directory": group["directory"],
        "kind": kind,
        "present_layers": present_layers,
        "missing_layers": missing_layers,
        "members": members,
        "requested_path": requested_path,
        "object_count": sum(int(item["object_count"]) for item in evidence),
        "reference_count": sum(int(item["reference_count"]) for item in evidence),
        "evidence": list(evidence),
    }


def _error_evidence(path: Path, root: Path, error: SceneError) -> Dict[str, object]:
    return {
        "path": _relative(path, root),
        "status": error.status,
        "layer": _layer_and_stem(path)[0],
        "object_count": 0,
        "reference_count": 0,
        "objects": [],
    }


def _direct_membership(
    path: Path,
    root: Path,
    warnings: List[Dict[str, object]],
) -> Dict[str, object]:
    layer, stem = _layer_and_stem(path)
    members: List[Dict[str, object]] = []
    candidates = [(layer, path)] if layer is None else [
        (candidate_layer, path.parent / f"{stem}{candidate_layer}.unity")
        for candidate_layer in SCENE_LAYERS
    ]
    for candidate_layer, candidate_path in candidates:
        try:
            exists = candidate_path.exists()
        except OSError as error:
            warnings.append(
                _warning(
                    "scene_unreadable",
                    f"Scene member could not be inspected: {error}",
                    _relative(candidate_path, root),
                )
            )
            continue
        if not exists:
            continue
        if _is_link_like(candidate_path):
            warnings.append(
                _warning(
                    "symlink_not_followed",
                    "Scene member is a link and was not included.",
                    _relative(candidate_path, root),
                )
            )
            continue
        if not candidate_path.is_file():
            continue
        members.append({"layer": candidate_layer, "path": candidate_path})
    return {
        "directory": _relative(path.parent, root),
        "logical_name": stem,
        "members": members,
    }


def _resolve_direct_path(
    root: Path,
    included_roots: Sequence[Path],
    selector: str,
) -> Path:
    try:
        raw = Path(selector).expanduser()
    except (OSError, RuntimeError) as error:
        raise SceneError(
            "invalid_query",
            "invalid_scene_path",
            f"Scene path could not be expanded: {error}",
            "invalid_scene_path",
        ) from error
    if any(part == ".." for part in raw.parts):
        raise SceneError(
            "invalid_query",
            "path_traversal",
            "Parent-directory traversal is not allowed.",
            "path_traversal",
        )
    candidate = raw if raw.is_absolute() else root / raw
    try:
        candidate = Path(os.path.abspath(os.fspath(candidate)))
        relative = candidate.relative_to(root)
    except (OSError, ValueError) as error:
        raise SceneError(
            "invalid_query",
            "path_outside_project",
            "Scene path is outside the Unity project root.",
            "path_outside_root",
        ) from error
    current = root
    for part in relative.parts:
        current = current / part
        if not _is_link_like(current):
            continue
        inside = _within(current, root)
        raise SceneError(
            "invalid_query",
            "linked_scene_path",
            f"Scene path contains a link and was not read: {relative.as_posix()}",
            "symlink_not_followed" if inside else "symlink_outside_root",
        )
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise SceneError(
            "invalid_query",
            "invalid_scene_path",
            f"Scene path could not be resolved: {relative.as_posix()}: {error}",
        ) from error
    if not _within(resolved, root):
        raise SceneError(
            "invalid_query",
            "path_outside_project",
            "Scene path resolves outside the Unity project root.",
            "symlink_outside_root",
        )
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise SceneError(
            "invalid_query",
            "path_outside_project",
            "Scene path resolves outside the Unity project root.",
            "path_outside_root",
        ) from error
    if not relative.parts:
        raise SceneError("invalid_query", "invalid_scene_path", "Scene path is empty.")
    if any(
        part.casefold() in EXCLUDED_DIRECTORY_NAMES
        for part in relative.parts[:-1]
    ):
        raise SceneError(
            "invalid_query",
            "excluded_path",
            f"Scene path is under an excluded directory: {relative.as_posix()}",
            "excluded_path",
        )
    included_names = {_relative(path, root) for path in included_roots}
    if relative.parts[0] not in included_names:
        raise SceneError(
            "invalid_query",
            "path_outside_project",
            f"Scene path is outside the included Assets or Packages roots: {relative.as_posix()}",
            "path_outside_root",
        )
    if not resolved.exists():
        raise SceneError(
            "not_found",
            "scene_not_found",
            f"Scene file does not exist: {relative.as_posix()}",
            "scene_not_found",
        )
    if not resolved.is_file():
        raise SceneError(
            "invalid_query",
            "invalid_scene_path",
            f"Scene path is not a file: {relative.as_posix()}",
            "invalid_scene_path",
        )
    if resolved.suffix.lower() != ".unity":
        raise SceneError(
            "unsupported_format",
            "unsupported_scene_format",
            f"Scene path is not a .unity file: {relative.as_posix()}",
            "unsupported_format",
        )
    return resolved


def _parse_evidence(
    paths: Sequence[Path],
    root: Path,
    warnings: List[Dict[str, object]],
) -> Tuple[List[Dict[str, object]], Optional[SceneError]]:
    evidence: List[Dict[str, object]] = []
    first_error: Optional[SceneError] = None
    for path in paths:
        try:
            parsed, parse_warnings = parse_serialized_file(path, root)
        except SceneError as error:
            first_error = first_error or error
            warnings.append(
                _warning(
                    error.warning_code or error.code,
                    str(error),
                    _relative(path, root),
                )
            )
            evidence.append(_error_evidence(path, root, error))
            continue
        parsed["layer"] = _layer_and_stem(path)[0]
        evidence.append(parsed)
        warnings.extend(parse_warnings)
    return evidence, first_error


def _name_query(
    name: str,
    root: Path,
    included_roots: Sequence[Path],
    payload: Dict[str, object],
    warnings: List[Dict[str, object]],
) -> None:
    if not name.strip() or "/" in name or "\\" in name:
        raise SceneError(
            "invalid_query",
            "invalid_scene_name",
            "Scene name must be a non-empty filename or stem, not a path.",
            "invalid_scene_name",
        )
    normalized = name.strip()
    if normalized.casefold().endswith(".unity"):
        normalized = normalized[:-6]
    if not normalized:
        raise SceneError(
            "invalid_query",
            "invalid_scene_name",
            "Scene name must include a filename or stem.",
            "invalid_scene_name",
        )
    files, scan_warnings = _walk_files(root, included_roots)
    warnings.extend(scan_warnings)
    groups = _discover_groups(files, root)
    matches = []
    for group in groups:
        aliases = {str(group["logical_name"]).casefold()}
        aliases.update(Path(member["path"]).stem.casefold() for member in group["members"])
        aliases.update(Path(member["path"]).name.casefold() for member in group["members"])
        if normalized.casefold() in aliases:
            matches.append(group)
    if not matches:
        payload["status"] = "not_found"
        warnings.append(
            _warning(
                "scene_not_found",
                f"No scene matches name or stem: {normalized}",
            )
        )
        return
    if len(matches) > 1:
        payload["status"] = "ambiguous"
        payload["results"] = [_scene_result(group, root) for group in matches]
        warnings.append(
            _warning(
                "ambiguous_scene_name",
                f"Scene name or stem is ambiguous: {normalized}",
            )
        )
        return

    group = matches[0]
    paths = [member["path"] for member in group["members"]]
    evidence, error = _parse_evidence(paths, root, warnings)
    payload["status"] = error.status if error else "ok"
    payload["results"] = [_scene_result(group, root, evidence)]
    if error:
        payload["error"] = {"code": error.code, "message": str(error)}
    if payload["results"][0]["kind"] == "incomplete":
        warnings.append(
            _warning(
                "incomplete_scene_set",
                f"Scene set {group['logical_name']} is missing recognized layers.",
                str(group["directory"]),
            )
        )


def _path_query(
    selector: str,
    root: Path,
    included_roots: Sequence[Path],
    payload: Dict[str, object],
    warnings: List[Dict[str, object]],
) -> None:
    path = _resolve_direct_path(root, included_roots, selector)
    group = _direct_membership(path, root, warnings)
    evidence, error = _parse_evidence([path], root, warnings)
    requested_path = _relative(path, root)
    payload["status"] = error.status if error else "ok"
    payload["results"] = [_scene_result(group, root, evidence, requested_path)]
    if error:
        payload["error"] = {"code": error.code, "message": str(error)}
    if payload["results"][0]["kind"] == "incomplete":
        warnings.append(
            _warning(
                "incomplete_scene_set",
                f"Scene set {group['logical_name']} is missing recognized layers.",
                str(group["directory"]),
            )
        )


def scene_query(
    project: Path,
    path_selector: Optional[str] = None,
    name_selector: Optional[str] = None,
    unknown: Sequence[str] = (),
) -> Dict[str, object]:
    """Return the version-1 scene query envelope."""

    if (path_selector is None) == (name_selector is None):
        query: Dict[str, object] = {}
    elif path_selector is not None:
        query = {"selector": "path", "path": path_selector}
    else:
        query = {"selector": "name", "name": name_selector}
    payload = _new_payload(Path(project), query)
    if unknown:
        payload["status"] = "invalid_query"
        payload["error"] = {
            "code": "invalid_scene_selector",
            "message": "Unsupported scene selector: " + " ".join(unknown),
        }
        return payload
    warnings: List[Dict[str, object]] = []
    try:
        if not query:
            raise SceneError(
                "invalid_query",
                "invalid_scene_selector",
                "Scene requires exactly one of --path or --name.",
            )
        root, included_roots = _validated_project(project)
        payload["project"] = _project_data(root, included_roots, warnings)
        if path_selector is not None:
            _path_query(path_selector, root, included_roots, payload, warnings)
        else:
            _name_query(name_selector or "", root, included_roots, payload, warnings)
    except NavigationError as error:
        payload["status"] = "invalid_project"
        payload["error"] = {"code": error.code, "message": str(error)}
    except SceneError as error:
        payload["status"] = error.status
        payload["error"] = {"code": error.code, "message": str(error)}
        if error.warning_code:
            warnings.append(_warning(error.warning_code, str(error)))
    except OSError as error:
        payload["status"] = "invalid_query"
        payload["error"] = {"code": "invalid_query", "message": str(error)}
    payload["warnings"] = _sorted_warnings(warnings)
    return payload
