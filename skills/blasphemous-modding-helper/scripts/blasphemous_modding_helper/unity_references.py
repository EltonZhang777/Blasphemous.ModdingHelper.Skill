"""Read-only serialized-reference traversal for an exported Unity project."""

from __future__ import annotations

import math
import re
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .unity_assets import (
    BINARY_SUFFIXES,
    GUID_PATTERN,
    META_GUID,
    META_VERSION,
    _project_info,
    _read_metadata,
    _result,
    asset_query,
)
from .unity_project import (
    SCHEMA_VERSION,
    NavigationError,
    _is_link_like,
    _relative,
    _sorted_warnings,
    _validated_project,
    _walk_files,
    _warning,
)
from .unity_serialized import SerializedError, parse_serialized_file


DEFAULT_DEPTH = 1
MAX_DEPTH = 4
DEFAULT_LIMIT = 30
MAX_LIMIT = 100
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_TIMEOUT_SECONDS = 120.0
MAX_WARNINGS = 50
READ_WORKERS = 8
READ_CHUNK_SIZE = 256
MIN_UNITY_ID = -(2**63)
MAX_UNITY_ID = 2**63 - 1

# Unity may serialize these asset types as text YAML.
SERIALIZED_SUFFIXES = frozenset(
    {
        ".anim",
        ".asset",
        ".brush",
        ".controller",
        ".cubemap",
        ".flare",
        ".fontsettings",
        ".giparams",
        ".guiskin",
        ".lighting",
        ".lightingdata",
        ".mask",
        ".mat",
        ".mixer",
        ".navmesh",
        ".overridecontroller",
        ".physicmaterial",
        ".physicmaterial2d",
        ".playable",
        ".prefab",
        ".preset",
        ".renderpipelinesettings",
        ".rendertexture",
        ".shadervariants",
        ".signal",
        ".spriteatlas",
        ".terrain",
        ".terrainlayer",
        ".unity",
    }
)
DIRECTIONS = ("outgoing", "incoming")
GUID_REFERENCE = re.compile(rb"guid\s*:\s*([0-9A-Fa-f]{32})")


class ReferenceError(Exception):
    """A structured reference-query failure."""

    def __init__(self, code: str, message: str, status: str = "invalid_query") -> None:
        super().__init__(message)
        self.code = code
        self.status = status


class _WarningLog:
    def __init__(self) -> None:
        self.items: List[Dict[str, object]] = []
        self.seen: Set[Tuple[str, str, str]] = set()
        self.suppressed = False

    def add(self, warning: Dict[str, object]) -> None:
        key = (
            str(warning.get("code", "")),
            str(warning.get("path", "")),
            str(warning.get("message", "")),
        )
        if key in self.seen:
            return
        if len(self.items) >= MAX_WARNINGS:
            self.suppressed = True
            return
        self.seen.add(key)
        self.items.append(dict(warning))

    def add_many(self, warnings: Iterable[Dict[str, object]]) -> None:
        for warning in warnings:
            self.add(warning)

    def code(self, code: str, message: str, path: Optional[str] = None) -> None:
        self.add(_warning(code, message, path))

    def finish(self) -> List[Dict[str, object]]:
        warnings = list(self.items)
        if self.suppressed:
            warnings.append(
                _warning(
                    "warnings_truncated",
                    f"Only the first {MAX_WARNINGS} distinct warnings are reported.",
                )
            )
        return _sorted_warnings(warnings)


def _monotonic() -> float:
    return time.monotonic()


class _Deadline:
    def __init__(self, timeout_seconds: float) -> None:
        self.deadline = _monotonic() + timeout_seconds

    def expired(self) -> bool:
        return _monotonic() >= self.deadline


def _parallel_each(
    paths: Sequence[Path],
    deadline: _Deadline,
    worker: Callable[[Path], object],
    consume: Callable[[Path, object], None],
) -> bool:
    if not paths:
        return False
    with ThreadPoolExecutor(max_workers=min(READ_WORKERS, len(paths))) as pool:
        for start in range(0, len(paths), READ_CHUNK_SIZE):
            if deadline.expired():
                return True
            chunk = paths[start : start + READ_CHUNK_SIZE]
            futures = [pool.submit(worker, path) for path in chunk]
            for path, future in zip(chunk, futures):
                if deadline.expired():
                    for pending in futures:
                        pending.cancel()
                    return True
                consume(path, future.result())
    return False


def _read_metadata_source(path: Path) -> Tuple[str, Optional[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return "unreadable", str(error)
    guid_match = META_GUID.search(text)
    if guid_match is None:
        return "invalid_guid", None
    version_match = META_VERSION.search(text)
    if version_match is not None:
        try:
            int(version_match.group(1))
        except ValueError:
            return "invalid_version", None
    return "ok", guid_match.group(1).lower()


def _read_guid_sources(path: Path) -> Tuple[str, object]:
    try:
        content = path.read_bytes()
    except OSError as error:
        return "unreadable", str(error)
    return (
        "ok",
        {
            match.group(1).decode("ascii").lower()
            for match in GUID_REFERENCE.finditer(content)
        },
    )


def _new_payload(project: Path, query: Dict[str, object]) -> Dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "references",
        "status": "invalid_project",
        "project": {"root": str(project)},
        "query": query,
        "root": None,
        "asset_candidates": [],
        "results": [],
        "limits": {},
        "truncated": False,
        "complete": False,
        "incomplete_reasons": [],
        "warnings": [],
        "error": None,
    }


def _parse_direction(raw: Optional[str]) -> str:
    value = "outgoing" if raw is None else str(raw).strip().casefold()
    if value == "bidirectional":
        value = "both"
    if value not in {"outgoing", "incoming", "both"}:
        raise ReferenceError(
            "invalid_direction",
            "Direction must be outgoing, incoming, or both.",
        )
    return value


def _parse_bounded_int(
    raw: Optional[str],
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if raw is None:
        return default
    try:
        value = int(raw) if isinstance(raw, int) else int(raw, 10)
    except (TypeError, ValueError) as error:
        raise ReferenceError(
            f"invalid_{name}",
            f"{name} must be an integer.",
        ) from error
    if not minimum <= value <= maximum:
        raise ReferenceError(
            f"invalid_{name}",
            f"{name} must be between {minimum} and {maximum}.",
        )
    return value


def _parse_object_file_id(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    try:
        value = int(raw) if isinstance(raw, int) else int(raw, 10)
    except (TypeError, ValueError) as error:
        raise ReferenceError(
            "invalid_object_file_id",
            "object file ID must be a signed 64-bit integer.",
        ) from error
    if not MIN_UNITY_ID <= value <= MAX_UNITY_ID:
        raise ReferenceError(
            "invalid_object_file_id",
            "object file ID must be a signed 64-bit integer.",
        )
    return value


def _parse_timeout(raw: Optional[str]) -> float:
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise ReferenceError(
            "invalid_timeout",
            "timeout-seconds must be a positive number.",
        ) from error
    if (
        not math.isfinite(value)
        or value <= 0
        or value > MAX_TIMEOUT_SECONDS
    ):
        raise ReferenceError(
            "invalid_timeout",
            f"timeout-seconds must be greater than 0 and at most {MAX_TIMEOUT_SECONDS:g}.",
        )
    return value


def _node(
    path: Optional[str],
    guid: Optional[str],
    file_id: Optional[int],
    depth: int,
    status: str = "ok",
    reason: Optional[str] = None,
    serialized_object: Optional[Dict[str, object]] = None,
    candidate_paths: Sequence[str] = (),
) -> Dict[str, object]:
    return {
        "path": path,
        "guid": guid.lower() if isinstance(guid, str) else None,
        "file_id": file_id,
        "class_id": (
            serialized_object.get("class_id") if serialized_object is not None else None
        ),
        "class_name": (
            serialized_object.get("class_name")
            if serialized_object is not None
            else None
        ),
        "name": (
            serialized_object.get("name") if serialized_object is not None else None
        ),
        "depth": depth,
        "status": status,
        "reason": reason,
        "candidate_paths": list(candidate_paths),
    }


def _node_ref(node: Dict[str, object]) -> Dict[str, object]:
    return {
        key: node[key]
        for key in (
            "path",
            "guid",
            "file_id",
            "class_id",
            "class_name",
            "name",
            "status",
            "reason",
            "candidate_paths",
        )
    }


def _node_identity(node: Dict[str, object]) -> Tuple[str, str, object]:
    path = node.get("path")
    guid = node.get("guid")
    file_id = node.get("file_id")
    if isinstance(path, str):
        return ("path", path, file_id)
    if isinstance(guid, str):
        return ("guid", guid, file_id)
    return ("unknown", "", file_id)


def _node_sort_key(node: Dict[str, object]) -> Tuple[object, ...]:
    path = node.get("path")
    guid = node.get("guid")
    file_id = node.get("file_id")
    return (
        int(node.get("depth") or 0),
        0 if isinstance(path, str) else 1,
        path if isinstance(path, str) else "",
        guid if isinstance(guid, str) else "",
        file_id if isinstance(file_id, int) else -1,
        str(node.get("status", "")),
        str(node.get("reason", "")),
        str(node.get("class_name", "")),
        str(node.get("name", "")),
    )


def _edge_sort_key(edge: Dict[str, object]) -> Tuple[object, ...]:
    source = edge["source"]
    target = edge["target"]
    return (
        int(edge.get("depth") or 0),
        str(source.get("path") or ""),
        str(source.get("guid") or ""),
        int(source.get("file_id") or 0),
        str(target.get("path") or ""),
        str(target.get("guid") or ""),
        int(target.get("file_id") or 0),
        str(edge.get("field") or ""),
        int(edge.get("line") or 0),
        str(edge.get("scope") or ""),
    )


def _make_edge(
    depth: int,
    reference: Dict[str, object],
    source: Dict[str, object],
    target: Dict[str, object],
) -> Dict[str, object]:
    return {
        "depth": depth,
        "scope": reference["scope"],
        "field": reference["field"],
        "line": reference["line"],
        "guid": (
            str(reference.get("guid")).lower()
            if reference.get("guid") is not None
            else None
        ),
        "file_id": reference["file_id"],
        "type": reference.get("type"),
        "source": _node_ref(source),
        "target": _node_ref(target),
    }


def _object_map(evidence: Dict[str, object]) -> Dict[int, List[Dict[str, object]]]:
    objects: Dict[int, List[Dict[str, object]]] = defaultdict(list)
    for item in evidence["objects"]:
        objects[int(item["file_id"])].append(item)
    return objects


def _one_object(
    objects: Dict[int, List[Dict[str, object]]],
    file_id: int,
) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    matches = objects.get(file_id, [])
    if not matches:
        return None, "object_not_found"
    if len(matches) > 1:
        return None, "duplicate_object_id"
    return matches[0], None


class _ReferenceContext:
    def __init__(
        self,
        root: Path,
        included_roots: Sequence[Path],
        warnings: _WarningLog,
        deadline: _Deadline,
    ) -> None:
        self.root = root
        self.included_roots = included_roots
        self.warnings = warnings
        self.deadline = deadline
        self.parsed: Dict[str, Tuple[Optional[Dict[str, object]], Optional[SerializedError]]] = {}
        self.guids: Dict[str, Optional[str]] = {}
        self.external: Dict[str, Dict[str, object]] = {}
        self.metadata_paths: Optional[Dict[str, List[str]]] = None
        self.metadata_timed_out = False
        self.metadata_incomplete = False
        self.incoming_sources: Optional[Dict[str, List[Path]]] = None
        self.incoming_timed_out = False
        self.incoming_incomplete = False
        self.source_incomplete = False

    def parse(
        self,
        path: Path,
    ) -> Tuple[Optional[Dict[str, object]], Optional[SerializedError]]:
        relative = _relative(path, self.root)
        if relative in self.parsed:
            return self.parsed[relative]
        try:
            evidence, parse_warnings = parse_serialized_file(path, self.root)
        except SerializedError as error:
            self.parsed[relative] = (None, error)
            self.source_incomplete = True
            return None, error
        self.parsed[relative] = (evidence, None)
        self.warnings.add_many(parse_warnings)
        return evidence, None

    def asset_guid(self, path: Path) -> Optional[str]:
        relative = _relative(path, self.root)
        if relative not in self.guids:
            guid, metadata, warnings = _read_metadata(self.root, path)
            self.warnings.add_many(warnings)
            if metadata["status"] == "unusable":
                self.source_incomplete = True
            self.guids[relative] = guid
        return self.guids[relative]

    def _external_metadata(self) -> Dict[str, List[str]]:
        if self.metadata_paths is not None:
            return self.metadata_paths
        files, scan_warnings = _walk_files(
            self.root,
            self.included_roots,
            self.deadline.expired,
            (".meta",),
        )
        self.warnings.add_many(scan_warnings)
        if scan_warnings:
            self.source_incomplete = True
            self.metadata_incomplete = True
        index: Dict[str, List[str]] = defaultdict(list)

        def consume_metadata(meta_path: Path, raw_result: object) -> None:
            status, value = raw_result
            relative = _relative(meta_path, self.root)
            if status == "unreadable":
                self.warnings.code(
                    "metadata_unusable",
                    f"Metadata could not be read: {value}",
                    relative,
                )
                self.metadata_incomplete = True
                return
            if status == "invalid_guid":
                self.warnings.code(
                    "metadata_unusable",
                    "Metadata has no valid GUID.",
                    relative,
                )
                self.metadata_incomplete = True
                return
            if status == "invalid_version":
                self.warnings.code(
                    "metadata_unusable",
                    "Metadata has an unsupported fileFormatVersion.",
                    relative,
                )
                self.metadata_incomplete = True
                return
            target = meta_path.with_suffix("")
            if target.suffix.lower() == ".meta":
                return
            index[str(value)].append(_relative(target, self.root))

        if _parallel_each(
            files,
            self.deadline,
            _read_metadata_source,
            consume_metadata,
        ):
            self.metadata_timed_out = True
        self.metadata_paths = index
        if self.deadline.expired():
            self.metadata_timed_out = True
        if self.metadata_incomplete:
            self.source_incomplete = True
        return index

    def _incoming_source_candidates(self) -> Dict[str, List[Path]]:
        if self.incoming_sources is not None:
            return self.incoming_sources
        files, scan_warnings = _walk_files(
            self.root,
            self.included_roots,
            self.deadline.expired,
            tuple(SERIALIZED_SUFFIXES),
        )
        self.warnings.add_many(scan_warnings)
        if scan_warnings:
            self.incoming_incomplete = True
            self.source_incomplete = True
        index: Dict[str, List[Path]] = defaultdict(list)

        def consume_source(path: Path, raw_result: object) -> None:
            status, value = raw_result
            relative = _relative(path, self.root)
            if status == "unreadable":
                self.warnings.code(
                    "scan_unreadable",
                    f"Serialized source could not be read while filtering incoming candidates: {value}",
                    relative,
                )
                self.incoming_incomplete = True
                self.source_incomplete = True
                return
            for guid in value:
                index[str(guid)].append(path)

        if _parallel_each(
            files,
            self.deadline,
            _read_guid_sources,
            consume_source,
        ):
            self.incoming_timed_out = True
        self.incoming_sources = index
        if self.deadline.expired():
            self.incoming_timed_out = True
        return index

    def resolve_external(self, guid: str) -> Dict[str, object]:
        normalized = guid.lower()
        if GUID_PATTERN.fullmatch(normalized) is None:
            result: Dict[str, object] = {
                "status": "unresolved",
                "guid": normalized,
                "reason": "invalid_guid",
            }
            self.external[normalized] = result
            return result
        if self.deadline.expired():
            return {"status": "timeout", "guid": normalized, "reason": "timeout"}
        if normalized in self.external:
            return self.external[normalized]
        index = self._external_metadata()
        if self.metadata_timed_out or self.deadline.expired():
            return {"status": "timeout", "guid": normalized, "reason": "timeout"}
        paths: List[str] = []
        for candidate in index.get(normalized, []):
            target = self.root / candidate
            if _is_link_like(target):
                self.warnings.code(
                    "metadata_unusable",
                    "The metadata target is a link and was not followed.",
                    _relative(target.with_name(target.name + ".meta"), self.root),
                )
                self.metadata_incomplete = True
                self.source_incomplete = True
                continue
            if target.is_file() or target.is_dir():
                paths.append(candidate)
        paths.sort()
        if len(paths) == 1:
            asset, asset_warnings = _result(self.root, self.root / paths[0])
            self.warnings.add_many(asset_warnings)
            if self.deadline.expired():
                return {"status": "timeout", "guid": normalized, "reason": "timeout"}
            result = {
                "status": "ok",
                "guid": normalized,
                "path": asset["path"],
                "type": asset["type"],
                "metadata": asset["metadata"],
            }
        elif len(paths) > 1:
            result = {
                "status": "ambiguous",
                "guid": normalized,
                "reason": "ambiguous_guid",
                "candidate_paths": paths,
            }
        elif self.metadata_incomplete:
            result = {
                "status": "unresolved",
                "guid": normalized,
                "reason": "metadata_unusable",
            }
        else:
            result = {
                "status": "unresolved",
                "guid": normalized,
                "reason": "guid_not_found",
            }
        if self.metadata_incomplete:
            result["source_incomplete"] = True
            self.source_incomplete = True
        self.external[normalized] = result
        return result


def _problem_warning(
    warnings: _WarningLog,
    node: Dict[str, object],
) -> None:
    status = node["status"]
    if status in {"ok", "asset"}:
        return
    code = "ambiguous_reference" if status == "ambiguous" else "unresolved_reference"
    identity = (
        f"GUID {node['guid']}"
        if isinstance(node.get("guid"), str)
        else f"{node['path']}#{node['file_id']}"
    )
    path = node.get("path") if isinstance(node.get("path"), str) else None
    warnings.code(
        code,
        f"Reference target {identity} is {status}: {node.get('reason')}.",
        path,
    )


def _root_nodes(
    path: str,
    guid: Optional[str],
    objects: Sequence[Dict[str, object]],
    limit: int,
    warnings: _WarningLog,
) -> Tuple[List[Dict[str, object]], bool]:
    ordered = sorted(objects, key=lambda item: int(item["file_id"]))
    truncated = len(ordered) > limit
    if truncated:
        ordered = ordered[:limit]
        warnings.code(
            "result_limit",
            f"Root object evidence is limited to {limit} objects.",
            path,
        )
    return [_node(path, guid, int(item["file_id"]), 0, serialized_object=item) for item in ordered], truncated


def _resolve_target(
    context: _ReferenceContext,
    source_path: str,
    depth: int,
    reference: Dict[str, object],
) -> Tuple[Dict[str, object], Optional[Dict[str, object]]]:
    file_id = int(reference["file_id"])
    if reference["scope"] == "local":
        evidence, error = context.parse(context.root / source_path)
        if error is not None:
            return (
                _node(
                    source_path,
                    None,
                    file_id,
                    depth,
                    status="unresolved",
                    reason=error.code,
                ),
                None,
            )
        serialized_object, reason = _one_object(
            _object_map(evidence or {}),
            file_id,
        )
        if serialized_object is None:
            return (
                _node(
                    source_path,
                    None,
                    file_id,
                    depth,
                    status="ambiguous" if reason == "duplicate_object_id" else "unresolved",
                    reason=reason,
                ),
                None,
            )
        return (
            _node(
                source_path,
                context.asset_guid(context.root / source_path),
                file_id,
                depth,
                serialized_object=serialized_object,
            ),
            serialized_object,
        )

    guid = str(reference.get("guid") or "").lower()
    resolved = context.resolve_external(guid)
    if resolved["status"] == "timeout":
        return (
            _node(
                None,
                guid,
                file_id,
                depth,
                status="unresolved",
                reason="timeout",
            ),
            None,
        )
    if resolved["status"] != "ok":
        return (
            _node(
                None,
                guid,
                file_id,
                depth,
                status=str(resolved["status"]),
                reason=str(resolved.get("reason") or resolved["status"]),
                candidate_paths=resolved.get("candidate_paths", []),
            ),
            None,
        )

    target_path = str(resolved["path"])
    if file_id == 0:
        return (
            _node(
                target_path,
                guid,
                file_id,
                depth,
                status="asset",
            ),
            None,
        )
    if str(resolved.get("type")) == "folder":
        return (
            _node(
                target_path,
                guid,
                file_id,
                depth,
                status="unsupported",
                reason="not_serialized_asset",
            ),
            None,
        )
    if Path(target_path).suffix.lower() in BINARY_SUFFIXES:
        return (
            _node(
                target_path,
                guid,
                file_id,
                depth,
                status="unsupported",
                reason="binary_asset_not_inspected",
            ),
            None,
        )
    if Path(target_path).suffix.lower() not in SERIALIZED_SUFFIXES:
        return (
            _node(
                target_path,
                guid,
                file_id,
                depth,
                status="unsupported",
                reason="not_serialized_asset",
            ),
            None,
        )
    if context.deadline.expired():
        return (
            _node(
                target_path,
                guid,
                file_id,
                depth,
                status="unresolved",
                reason="timeout",
            ),
            None,
        )
    evidence, error = context.parse(context.root / target_path)
    if error is not None:
        context.warnings.code(
            error.warning_code or error.code,
            str(error),
            target_path,
        )
        return (
            _node(
                target_path,
                guid,
                file_id,
                depth,
                status="unsupported" if error.status == "unsupported_format" else "unresolved",
                reason=error.code,
            ),
            None,
        )
    serialized_object, reason = _one_object(_object_map(evidence or {}), file_id)
    if serialized_object is None:
        return (
            _node(
                target_path,
                guid,
                file_id,
                depth,
                status="ambiguous" if reason == "duplicate_object_id" else "unresolved",
                reason=reason,
            ),
            None,
        )
    return (
        _node(
            target_path,
            guid,
            file_id,
            depth,
            serialized_object=serialized_object,
        ),
        serialized_object,
    )


def _traverse_outgoing(
    context: _ReferenceContext,
    root_path: str,
    root_guid: Optional[str],
    roots: Sequence[Dict[str, object]],
    depth: int,
    limit: int,
    deadline: _Deadline,
) -> Dict[str, object]:
    nodes, root_truncated = _root_nodes(
        root_path,
        root_guid,
        roots,
        limit,
        context.warnings,
    )
    truncated = root_truncated
    edge_truncated = False
    seen_nodes = {_node_identity(node) for node in nodes}
    root_items = sorted(roots, key=lambda item: int(item["file_id"]))
    visited = {(root_path, int(item["file_id"])) for item in root_items[:limit]}
    queue: Deque[Tuple[int, Dict[str, object], Dict[str, object]]] = deque(
        (0, node, item) for node, item in zip(nodes, root_items)
    )
    edges: List[Dict[str, object]] = []
    timed_out = False
    while queue:
        if deadline.expired():
            timed_out = True
            break
        current_depth, source, serialized_object = queue.popleft()
        if current_depth >= depth:
            continue
        references = sorted(
            serialized_object["references"],
            key=lambda item: (
                str(item.get("scope") or ""),
                str(item.get("guid") or ""),
                int(item.get("file_id") or 0),
                str(item.get("field") or ""),
                int(item.get("line") or 0),
            ),
        )
        for reference in references:
            if reference["scope"] not in {"local", "external"}:
                continue
            if len(edges) >= limit:
                edge_truncated = True
                break
            if deadline.expired():
                timed_out = True
                break
            target, target_object = _resolve_target(
                context,
                str(source["path"]),
                current_depth + 1,
                reference,
            )
            if target["reason"] == "timeout":
                timed_out = True
                break
            edges.append(_make_edge(current_depth + 1, reference, source, target))
            identity = _node_identity(target)
            if identity not in seen_nodes:
                seen_nodes.add(identity)
                nodes.append(target)
            _problem_warning(context.warnings, target)
            if (
                target_object is not None
                and target["status"] == "ok"
                and current_depth + 1 < depth
            ):
                key = (str(target["path"]), int(target["file_id"]))
                if key not in visited:
                    visited.add(key)
                    queue.append((current_depth + 1, target, target_object))
        if edge_truncated or timed_out:
            break

    truncated = root_truncated or edge_truncated
    reasons: List[str] = []
    if truncated:
        reasons.append("limit")
        if edge_truncated:
            context.warnings.code(
                "result_limit",
                f"Reference results are limited to {limit} edges.",
                root_path,
            )
    if timed_out:
        reasons.append("timeout")
        context.warnings.code(
            "timeout",
            "Reference traversal stopped at the configured timeout.",
            root_path,
        )
    if context.source_incomplete and "source_evidence_incomplete" not in reasons:
        reasons.append("source_evidence_incomplete")
    if deadline.expired() and "timeout" not in reasons:
        timed_out = True
        reasons.append("timeout")
    nodes.sort(key=_node_sort_key)
    edges.sort(key=_edge_sort_key)
    return {
        "direction": "outgoing",
        "status": "timeout" if timed_out else "ok",
        "complete": not truncated and not reasons,
        "incomplete_reasons": reasons,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


def _incoming_matches(
    context: _ReferenceContext,
    target_path: str,
    target_file_id: int,
    target_guid: Optional[str],
    reasons: List[str],
) -> Tuple[List[Dict[str, object]], bool]:
    matches: List[Dict[str, object]] = []
    evidence, error = context.parse(context.root / target_path)
    if error is not None:
        context.warnings.add(
            _warning(
                error.warning_code or error.code,
                str(error),
                target_path,
            )
        )
        context.source_incomplete = True
    else:
        for item in (evidence or {}).get("objects", []):
            for reference in item["references"]:
                if (
                    reference["scope"] != "local"
                    or int(reference["file_id"]) != target_file_id
                ):
                    continue
                matches.append(
                    {
                        "source_path": target_path,
                        "source_guid": context.asset_guid(context.root / target_path),
                        "source_file_id": int(item["file_id"]),
                        "source_object": item,
                        "field": reference["field"],
                        "line": reference["line"],
                        "scope": "local",
                        "guid": None,
                        "file_id": int(reference["file_id"]),
                        "type": reference.get("type"),
                    }
                )

    if not isinstance(target_guid, str):
        return matches, False
    resolved = context.resolve_external(target_guid)
    if resolved["status"] == "timeout":
        return matches, True
    if (
        resolved["status"] != "ok"
        or str(resolved.get("path")) != target_path
    ):
        reason = (
            "ambiguous_guid"
            if resolved["status"] == "ambiguous"
            else "external_guid_unresolved"
        )
        if reason not in reasons:
            reasons.append(reason)
            context.warnings.code(
                "incoming_external_scope_unavailable",
                f"External incoming references for GUID {target_guid} are unavailable: {reason}.",
                target_path,
            )
        return matches, False

    sources = context._incoming_source_candidates()
    if context.incoming_timed_out:
        return matches, True
    if context.incoming_incomplete:
        context.source_incomplete = True
    for source_path in sorted(
        sources.get(target_guid, []),
        key=lambda path: (
            _relative(path, context.root).casefold(),
            _relative(path, context.root),
        ),
    ):
        if context.deadline.expired():
            return matches, True
        relative = _relative(source_path, context.root)
        evidence, error = context.parse(source_path)
        if error is not None:
            context.warnings.add(
                _warning(
                    error.warning_code or error.code,
                    str(error),
                    relative,
                )
            )
            context.source_incomplete = True
            continue
        source_guid = context.asset_guid(source_path)
        for item in (evidence or {}).get("objects", []):
            for reference in item["references"]:
                guid = str(reference.get("guid") or "").lower()
                if (
                    reference["scope"] != "external"
                    or guid != target_guid
                    or int(reference["file_id"]) != target_file_id
                ):
                    continue
                matches.append(
                    {
                        "source_path": relative,
                        "source_guid": source_guid,
                        "source_file_id": int(item["file_id"]),
                        "source_object": item,
                        "field": reference["field"],
                        "line": reference["line"],
                        "scope": "external",
                        "guid": guid,
                        "file_id": int(reference["file_id"]),
                        "type": reference.get("type"),
                    }
                )
    return matches, False


def _incoming_edge_sort_key(item: Dict[str, object]) -> Tuple[object, ...]:
    return (
        str(item["source_path"]),
        str(item["source_guid"] or ""),
        int(item["source_file_id"]),
        str(item["field"]),
        int(item["line"]),
        str(item["scope"]),
    )


def _traverse_incoming(
    context: _ReferenceContext,
    root_path: str,
    root_guid: Optional[str],
    roots: Sequence[Dict[str, object]],
    depth: int,
    limit: int,
    deadline: _Deadline,
) -> Dict[str, object]:
    nodes, root_truncated = _root_nodes(
        root_path,
        root_guid,
        roots,
        limit,
        context.warnings,
    )
    truncated = root_truncated
    edge_truncated = False
    seen_nodes = {_node_identity(node) for node in nodes}
    root_items = sorted(roots, key=lambda item: int(item["file_id"]))
    visited = {(root_path, int(item["file_id"])) for item in root_items[:limit]}
    queue: Deque[Tuple[int, Dict[str, object]]] = deque(
        (0, node)
        for node in nodes
    )
    reasons: List[str] = []
    timed_out = False
    if root_guid is None:
        reasons.append("external_guid_unavailable")
        context.warnings.code(
            "incoming_external_scope_unavailable",
            "The root asset has no usable GUID; external incoming references cannot be observed.",
            root_path,
        )

    edges: List[Dict[str, object]] = []
    while queue:
        if deadline.expired():
            timed_out = True
            reasons.append("timeout")
            break
        current_depth, target = queue.popleft()
        if current_depth >= depth:
            continue
        target_guid = target.get("guid")
        if not isinstance(target_guid, str):
            if "external_guid_unavailable" not in reasons:
                reasons.append("external_guid_unavailable")
                context.warnings.code(
                    "incoming_external_scope_unavailable",
                    "An object has no usable asset GUID; external incoming references cannot be observed.",
                    str(target["path"]),
                )
        matches, target_timed_out = _incoming_matches(
            context,
            str(target["path"]),
            int(target["file_id"]),
            target_guid if isinstance(target_guid, str) else None,
            reasons,
        )
        if target_timed_out:
            timed_out = True
            reasons.append("timeout")
            break

        matches.sort(key=_incoming_edge_sort_key)
        for item in matches:
            if len(edges) >= limit:
                edge_truncated = True
                break
            if deadline.expired():
                timed_out = True
                reasons.append("timeout")
                break
            source = _node(
                str(item["source_path"]),
                item.get("source_guid"),
                int(item["source_file_id"]),
                current_depth + 1,
                serialized_object=item["source_object"],
            )
            reference = {
                "scope": item["scope"],
                "field": item["field"],
                "line": item["line"],
                "guid": item["guid"],
                "file_id": item["file_id"],
                "type": item["type"],
            }
            edges.append(
                _make_edge(
                    current_depth + 1,
                    reference,
                    source,
                    target,
                )
            )
            identity = _node_identity(source)
            if identity not in seen_nodes:
                seen_nodes.add(identity)
                nodes.append(source)
            if current_depth + 1 < depth:
                key = (str(source["path"]), int(source["file_id"]))
                if key not in visited:
                    visited.add(key)
                    queue.append((current_depth + 1, source))
        if edge_truncated or timed_out:
            break

    truncated = root_truncated or edge_truncated
    if truncated:
        if "limit" not in reasons:
            reasons.append("limit")
        if edge_truncated:
            context.warnings.code(
                "result_limit",
                f"Incoming reference results are limited to {limit} edges.",
                root_path,
            )
    if timed_out:
        if "timeout" not in reasons:
            reasons.append("timeout")
        context.warnings.code(
            "timeout",
            "Incoming reference traversal stopped at the configured timeout.",
            root_path,
        )
    if context.source_incomplete and "source_evidence_incomplete" not in reasons:
        reasons.append("source_evidence_incomplete")
    if deadline.expired() and "timeout" not in reasons:
        timed_out = True
        reasons.append("timeout")
    nodes.sort(key=_node_sort_key)
    edges.sort(key=_edge_sort_key)
    return {
        "direction": "incoming",
        "status": "timeout" if timed_out else "ok",
        "complete": not truncated and not timed_out and not reasons,
        "incomplete_reasons": sorted(set(reasons)),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


def references_query(
    project: Path,
    selector: str,
    value: str,
    object_file_id: Optional[str] = None,
    direction: Optional[str] = None,
    depth: Optional[str] = None,
    limit: Optional[str] = None,
    timeout_seconds: Optional[str] = None,
) -> Dict[str, object]:
    """Return the version-1 serialized-reference traversal envelope."""

    payload = _new_payload(
        Path(project),
        {
            "selector": selector,
            "value": value,
            "object_file_id": object_file_id,
            "direction": direction,
            "depth": depth,
            "limit": limit,
            "timeout_seconds": timeout_seconds,
        },
    )
    warnings = _WarningLog()
    try:
        direction_value = _parse_direction(direction)
        depth_value = _parse_bounded_int(
            depth,
            "depth",
            DEFAULT_DEPTH,
            1,
            MAX_DEPTH,
        )
        limit_value = _parse_bounded_int(
            limit,
            "limit",
            DEFAULT_LIMIT,
            1,
            MAX_LIMIT,
        )
        timeout_value = _parse_timeout(timeout_seconds)
        object_id = _parse_object_file_id(object_file_id)
        if selector not in {"path", "guid", "name"}:
            raise ReferenceError(
                "invalid_query",
                f"Unsupported asset selector: {selector}",
            )
        if not value or "\x00" in value:
            raise ReferenceError("invalid_query", "The asset selector value is empty or invalid.")

        payload["query"] = {
            "selector": selector,
            "value": value,
            "object_file_id": object_id,
            "direction": direction_value,
            "depth": depth_value,
            "limit": limit_value,
            "timeout_seconds": timeout_value,
        }
        payload["limits"] = {
            "evidence_kind": "serialized_references",
            "direction": direction_value,
            "depth": depth_value,
            "max_depth": MAX_DEPTH,
            "limit": limit_value,
            "max_limit": MAX_LIMIT,
            "timeout_seconds": timeout_value,
            "max_timeout_seconds": MAX_TIMEOUT_SECONDS,
            "external_identity": "unique_sibling_meta_guid",
        }
        deadline = _Deadline(timeout_value)
        root, included_roots = _validated_project(Path(project))
        project_info, version_warnings = _project_info(root, included_roots)
        warnings.add_many(version_warnings)
        payload["project"] = project_info
        payload["status"] = "ok"

        asset_payload = asset_query(root, selector, value, deadline.expired)
        warnings.add_many(asset_payload["warnings"])
        if asset_payload["status"] != "ok":
            payload["status"] = str(asset_payload["status"])
            payload["error"] = asset_payload["error"]
            payload["asset_candidates"] = asset_payload["results"]
            if payload["status"] == "timeout" or deadline.expired():
                payload["status"] = "timeout"
                payload["complete"] = False
                payload["incomplete_reasons"] = ["timeout"]
                warnings.code("timeout", "Reference traversal timed out.", None)
                return payload
            metadata_unusable = any(
                warning.get("code") == "metadata_unusable"
                for warning in asset_payload["warnings"]
            )
            if payload["status"] == "not_found" and metadata_unusable:
                payload["status"] = "source_evidence_incomplete"
                payload["complete"] = False
                payload["incomplete_reasons"] = ["source_evidence_incomplete"]
                warnings.code(
                    "source_evidence_incomplete",
                    "The asset selector could not be resolved because metadata is unusable.",
                    value,
                )
                return payload
            warning_code = (
                "ambiguous_asset"
                if payload["status"] == "ambiguous"
                else (
                    "reference_asset_not_found"
                    if payload["status"] == "not_found"
                    else "reference_asset_invalid"
                )
            )
            warnings.code(
                warning_code,
                "The asset selector did not resolve to exactly one asset.",
            )
            return payload
        if deadline.expired():
            payload["status"] = "timeout"
            payload["error"] = {
                "code": "timeout",
                "message": "Reference traversal timed out during asset lookup.",
            }
            payload["complete"] = False
            payload["incomplete_reasons"] = ["timeout"]
            warnings.code("timeout", "Reference traversal timed out during asset lookup.")
            return payload

        asset = asset_payload["results"][0]
        root_path = str(asset["path"])
        root_guid = asset.get("guid") if isinstance(asset.get("guid"), str) else None
        root_type = str(asset.get("type"))
        payload["query"]["value"] = asset_payload["query"]["value"]
        payload["root"] = {
            "path": root_path,
            "type": root_type,
            "guid": root_guid,
            "metadata": asset["metadata"],
            "object_file_id": object_id,
        }
        if root_type == "folder":
            raise ReferenceError(
                "not_serialized_asset",
                "The selected asset is a folder and has no serialized object references.",
                status="unsupported_format",
            )
        if Path(root_path).suffix.lower() in BINARY_SUFFIXES:
            warnings.code(
                "binary_asset_not_inspected",
                "Binary asset content was not inspected.",
                root_path,
            )
            raise ReferenceError(
                "binary_asset_not_inspected",
                "The selected asset is binary and has no inspected serialized references.",
                status="unsupported_format",
            )
        if Path(root_path).suffix.lower() not in SERIALIZED_SUFFIXES:
            warnings.code(
                "not_serialized_asset",
                "The selected asset is not a Unity serialized text asset.",
                root_path,
            )
            raise ReferenceError(
                "not_serialized_asset",
                "The selected asset is not a Unity serialized text asset.",
                status="unsupported_format",
            )

        context = _ReferenceContext(root, included_roots, warnings, deadline)
        if asset["metadata"]["status"] == "unusable":
            context.source_incomplete = True
        evidence, parse_error = context.parse(root / root_path)
        if parse_error is not None:
            payload["status"] = parse_error.status
            payload["error"] = {
                "code": parse_error.code,
                "message": str(parse_error),
            }
            warnings.add(
                _warning(
                    parse_error.warning_code or parse_error.code,
                    str(parse_error),
                    root_path,
                )
            )
            return payload

        objects = (evidence or {}).get("objects", [])
        if object_id is None:
            roots = objects
        else:
            matches = [
                item for item in objects if int(item["file_id"]) == object_id
            ]
            if not matches:
                payload["status"] = "not_found"
                payload["error"] = {
                    "code": "object_not_found",
                    "message": f"No serialized object has file ID {object_id} in {root_path}.",
                }
                warnings.code(
                    "object_not_found",
                    f"No serialized object has file ID {object_id}.",
                    root_path,
                )
                return payload
            if len(matches) > 1:
                payload["status"] = "ambiguous"
                payload["error"] = {
                    "code": "duplicate_object_id",
                    "message": f"File ID {object_id} is duplicated in {root_path}.",
                }
                warnings.code(
                    "duplicate_object_id",
                    f"File ID {object_id} is duplicated.",
                    root_path,
                )
                return payload
            roots = matches
        payload["root"]["object_count"] = len(objects)
        payload["root"]["matched_object_count"] = len(roots)

        if deadline.expired():
            payload["status"] = "timeout"
            payload["error"] = {
                "code": "timeout",
                "message": "Reference traversal timed out.",
            }
            payload["incomplete_reasons"] = ["timeout"]
            warnings.code("timeout", "Reference traversal timed out.", root_path)
            return payload

        selected_directions = (
            list(DIRECTIONS) if direction_value == "both" else [direction_value]
        )
        results: List[Dict[str, object]] = []
        for selected_direction in selected_directions:
            if selected_direction == "outgoing":
                results.append(
                    _traverse_outgoing(
                        context,
                        root_path,
                        root_guid,
                        roots,
                        depth_value,
                        limit_value,
                        deadline,
                    )
                )
            else:
                results.append(
                    _traverse_incoming(
                        context,
                        root_path,
                        root_guid,
                        roots,
                        depth_value,
                        limit_value,
                        deadline,
                    )
                )
        if deadline.expired():
            for item in results:
                if "timeout" not in item["incomplete_reasons"]:
                    item["incomplete_reasons"].append("timeout")
                item["complete"] = False
                item["status"] = "timeout"
            warnings.code(
                "timeout",
                "Reference traversal timed out before completeness was established.",
                root_path,
            )
        payload["results"] = results
        payload["truncated"] = any(bool(item["incomplete_reasons"]) and "limit" in item["incomplete_reasons"] for item in results)
        reasons: Set[str] = set()
        for item in results:
            reasons.update(str(reason) for reason in item["incomplete_reasons"])
        payload["incomplete_reasons"] = sorted(reasons)
        payload["complete"] = bool(results) and all(
            bool(item["complete"]) for item in results
        ) and not deadline.expired()
        if any(item["status"] == "timeout" for item in results):
            payload["status"] = "timeout"
            payload["error"] = {
                "code": "timeout",
                "message": "Reference traversal timed out; returned evidence is incomplete.",
            }
    except ReferenceError as error:
        payload["status"] = error.status
        payload["error"] = {"code": error.code, "message": str(error)}
        warnings.code(error.code, str(error))
    except NavigationError as error:
        payload["status"] = "invalid_project"
        payload["error"] = {"code": error.code, "message": str(error)}
        warnings.code(error.code, str(error))
    except OSError as error:
        payload["status"] = "invalid_query"
        payload["error"] = {"code": "invalid_query", "message": str(error)}
        warnings.code("invalid_query", str(error))
    finally:
        payload["warnings"] = warnings.finish()
    return payload
