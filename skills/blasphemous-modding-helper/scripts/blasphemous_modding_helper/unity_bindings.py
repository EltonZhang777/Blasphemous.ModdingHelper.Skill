"""Read-only component-script binding inventory for an exported Unity project."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .unity_assets import (
    BINARY_SUFFIXES,
    GUID_PATTERN,
    META_GUID,
    META_VERSION,
    _project_info,
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
    _within,
)


DEFAULT_LIMIT = 200
MAX_LIMIT = 1000
SORT_VERSION = 1
CURSOR_VERSION = 1
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1
SOURCE_KINDS = {
    ".unity": "scene",
    ".prefab": "prefab",
    ".asset": "asset",
}
DOCUMENT_HEADER = re.compile(
    r"^--- !u!(?P<class_id>\d+) &(?P<file_id>-?\d+)(?:\s+stripped)?\s*$"
)
INLINE_MAP = re.compile(r"^\{\s*(?P<body>[^{}]*?)\s*\}$")
INLINE_ENTRY = re.compile(
    r"^\s*(?P<key>fileID|guid|type)\s*:\s*(?P<value>[^,{}]+?)\s*$"
)
DECIMAL_INTEGER = re.compile(r"^[+-]?\d+$")


def _parse_limit(value: Optional[str]) -> int:
    if value is None:
        return DEFAULT_LIMIT
    try:
        limit = int(value)
    except (TypeError, ValueError) as error:
        raise NavigationError(
            "invalid_query",
            "The limit must be an integer.",
        ) from error
    if limit < 1 or limit > MAX_LIMIT:
        raise NavigationError(
            "invalid_query",
            f"The limit must be between 1 and {MAX_LIMIT}.",
        )
    return limit


def _project_identity(root: Path) -> str:
    return hashlib.sha256(
        os.path.normcase(str(root)).encode("utf-8")
    ).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _query_signature(root: Path, query: Dict[str, object]) -> str:
    material = {
        "command": "bindings",
        "project": _project_identity(root),
        "query": query,
        "schema_version": SCHEMA_VERSION,
        "sort_version": SORT_VERSION,
    }
    return hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()


def _encode_cursor(
    root: Path,
    query: Dict[str, object],
    key: Tuple[str, int, str, str, str, str],
) -> str:
    payload = {
        "p": [key[0], str(key[1]), key[2], key[3], key[4], key[5]],
        "q": _query_signature(root, query),
        "s": SORT_VERSION,
        "v": CURSOR_VERSION,
    }
    encoded = base64.urlsafe_b64encode(
        _canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return encoded.rstrip("=")


def _decode_cursor(
    root: Path,
    query: Dict[str, object],
    value: str,
) -> Tuple[str, int, str, str, str, str]:
    if not value:
        raise NavigationError("invalid_query", "The cursor is empty.")
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.b64decode(
            padded.encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, UnicodeError, ValueError) as error:
        raise NavigationError(
            "invalid_query",
            "The cursor is invalid.",
        ) from error
    if not isinstance(payload, dict):
        raise NavigationError("invalid_query", "The cursor is invalid.")
    if (
        payload.get("v") != CURSOR_VERSION
        or payload.get("s") != SORT_VERSION
        or payload.get("q") != _query_signature(root, query)
    ):
        raise NavigationError(
            "invalid_query",
            "The cursor does not belong to this query or project.",
        )
    position = payload.get("p")
    if (
        not isinstance(position, list)
        or len(position) != 6
        or not all(isinstance(item, str) for item in position)
    ):
        raise NavigationError("invalid_query", "The cursor position is invalid.")
    try:
        object_id = int(position[1])
    except ValueError as error:
        raise NavigationError(
            "invalid_query",
            "The cursor position is invalid.",
        ) from error
    return (
        position[0],
        object_id,
        position[2],
        position[3],
        position[4],
        position[5],
    )


def _iter_documents(
    text: str,
) -> Iterable[Tuple[Tuple[int, int], List[str]]]:
    header: Optional[Tuple[int, int]] = None
    lines: List[str] = []
    for line in text.splitlines():
        if line.startswith("---"):
            if header is not None:
                yield header, lines
            match = DOCUMENT_HEADER.match(line)
            header = (
                (int(match.group("class_id")), int(match.group("file_id")))
                if match is not None
                else None
            )
            lines = []
        elif header is not None:
            lines.append(line)
    if header is not None:
        yield header, lines


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _direct_script_field(
    lines: Sequence[str],
) -> Optional[Tuple[int, int, str]]:
    type_index = None
    type_indent = 0
    for index, line in enumerate(lines):
        if line.strip() == "MonoBehaviour:":
            type_index = index
            type_indent = _indent(line)
            break
    if type_index is None:
        return None
    field_indent = type_indent + 2
    for index in range(type_index + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        indent = _indent(line)
        if indent <= type_indent:
            break
        if (
            indent == field_indent
            and line.strip().startswith("m_Script:")
        ):
            value = line.strip()[len("m_Script:") :].strip()
            return index, field_indent, value
    return None


def _inline_fields(raw: str) -> Optional[Dict[str, str]]:
    map_match = INLINE_MAP.fullmatch(raw)
    if map_match is None:
        return None
    fields: Dict[str, str] = {}
    body = map_match.group("body")
    if not body:
        return fields
    for entry in body.split(","):
        match = INLINE_ENTRY.fullmatch(entry)
        if match is None or match.group("key") in fields:
            return None
        fields[match.group("key")] = match.group("value").strip().strip("'\"")
    return fields


def _decimal_integer(raw: Optional[str], minimum: int, maximum: int) -> Optional[int]:
    if raw is None or DECIMAL_INTEGER.fullmatch(raw) is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if minimum <= value <= maximum else None


def _block_fields(
    lines: Sequence[str],
    field_index: int,
    field_indent: int,
) -> Tuple[Dict[str, str], str]:
    fields: Dict[str, str] = {}
    raw_lines: List[str] = []
    for line in lines[field_index + 1 :]:
        if not line.strip():
            raw_lines.append(line)
            continue
        if _indent(line) <= field_indent:
            break
        raw_lines.append(line)
        if _indent(line) != field_indent + 2:
            continue
        key, separator, value = line.strip().partition(":")
        if separator and key.strip() in {"fileID", "guid", "type"}:
            fields[key.strip()] = value.strip().strip("'\"")
    return fields, "\n".join(raw_lines).strip()


def _bounded_raw_reference(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        character
        if character >= " " or character in "\t\n"
        else " "
        for character in text
    )
    if len(text) > 512:
        return text[:509] + "..."
    return text


def _parse_script_reference(
    lines: Sequence[str],
    field_index: int,
    field_indent: int,
    value: str,
) -> Dict[str, object]:
    raw = value
    if value.startswith("{") and value.endswith("}"):
        fields = _inline_fields(value) or {}
    elif value == "" or value in {"null", "~"}:
        fields, raw = _block_fields(lines, field_index, field_indent)
    elif value == "0":
        fields = {"fileID": "0"}
    else:
        fields = {}

    file_id_raw = fields.get("fileID")
    guid_raw = fields.get("guid")
    type_raw = fields.get("type")
    file_id = _decimal_integer(file_id_raw, INT64_MIN, INT64_MAX)
    script_type = _decimal_integer(
        type_raw,
        -(1 << 31),
        (1 << 31) - 1,
    )
    guid = (
        guid_raw.lower()
        if guid_raw is not None and GUID_PATTERN.fullmatch(guid_raw)
        else None
    )
    malformed = any(
        (
            file_id_raw is not None and file_id is None,
            guid_raw is not None and guid is None,
            type_raw is not None and script_type is None,
        )
    )

    if file_id == 0 and not malformed:
        return {
            "reference_shape": "null",
            "m_script_file_id": "0",
            "m_script_guid": guid,
            "m_script_type": script_type,
        }
    if file_id is not None and guid is not None and not malformed:
        return {
            "reference_shape": "structured",
            "m_script_file_id": str(file_id),
            "m_script_guid": guid,
            "m_script_type": script_type,
        }
    return {
        "reference_shape": "malformed",
        "m_script_file_id": str(file_id) if file_id is not None else None,
        "m_script_guid": guid,
        "m_script_type": script_type,
        "raw_reference": _bounded_raw_reference(raw),
    }


def _parse_source(
    path: Path,
    root: Path,
    text: str,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    kind = SOURCE_KINDS[path.suffix.lower()]
    source_path = _relative(path, root)
    for (class_id, object_file_id), lines in _iter_documents(text):
        if class_id != 114:
            continue
        field = _direct_script_field(lines)
        if field is None:
            continue
        field_index, field_indent, value = field
        row: Dict[str, object] = {
            "source_asset_path": source_path,
            "source_asset_kind": kind,
            "source_object_file_id": str(object_file_id),
            "source_class_id": 114,
            "source_class_name": "MonoBehaviour",
        }
        row.update(
            _parse_script_reference(
                lines,
                field_index,
                field_indent,
                value,
            )
        )
        rows.append(row)
    return rows


def _asset_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".cs":
        return "cs"
    if suffix == ".dll" or suffix in BINARY_SUFFIXES:
        return "binary"
    return "other"


def _build_guid_index(
    root: Path,
    files: Sequence[Path],
) -> Tuple[Dict[str, List[Dict[str, object]]], List[Dict[str, object]]]:
    index: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    warnings: List[Dict[str, object]] = []
    for meta_path in files:
        if meta_path.suffix.lower() != ".meta":
            continue
        target = meta_path.with_suffix("")
        if target.suffix.lower() == ".meta":
            continue
        relative = _relative(meta_path, root)
        try:
            data = meta_path.read_bytes()
        except OSError as error:
            warnings.append(
                _warning(
                    "metadata_unusable",
                    f"Metadata could not be read: {error}",
                    relative,
                )
            )
            continue
        unreadable = False
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("utf-8-sig", errors="replace")
            unreadable = True
            warnings.append(
                _warning(
                    "metadata_unusable",
                    "Metadata is not valid UTF-8 and was only partially read.",
                    relative,
                )
            )
        guid_match = META_GUID.search(text)
        if guid_match is None:
            warnings.append(
                _warning(
                    "metadata_unusable",
                    "Metadata has no valid GUID.",
                    relative,
                )
            )
            continue
        version_match = META_VERSION.search(text)
        if version_match is not None:
            try:
                int(version_match.group(1))
            except ValueError:
                warnings.append(
                    _warning(
                        "metadata_unusable",
                        "Metadata has an unusable fileFormatVersion.",
                        relative,
                    )
                )
                continue
        guid = guid_match.group(1).lower()
        try:
            exists = (
                target.is_file()
                and not _is_link_like(target)
                and _within(target, root)
            )
        except OSError:
            exists = False
        index[guid].append(
            {
                "exists": exists,
                "kind": _asset_kind(target),
                "metadata_unreadable": unreadable,
                "path": _relative(target, root),
            }
        )
    for candidates in index.values():
        candidates.sort(
            key=lambda item: (
                str(item["path"]).casefold(),
                str(item["path"]),
                str(item["kind"]),
            )
        )
    return index, warnings


def _target_fields(
    reference_shape: object,
    script_guid: object,
    index: Dict[str, List[Dict[str, object]]],
) -> Dict[str, object]:
    fields: Dict[str, object] = {
        "target_asset_kind": "not_applicable",
        "target_asset_path": None,
        "target_asset_candidates": [],
        "asset_resolution": "not_applicable",
        "asset_resolution_reason": None,
        "script_object_resolution": "not_applicable",
    }
    if reference_shape != "structured" or not isinstance(script_guid, str):
        return fields
    candidates = index.get(script_guid, [])
    if not candidates:
        fields.update(
            target_asset_kind="unresolved",
            asset_resolution="missing",
            asset_resolution_reason="missing_meta",
        )
        return fields
    if len(candidates) > 1:
        fields.update(
            target_asset_kind="unresolved",
            target_asset_candidates=[
                {
                    "kind": candidate["kind"],
                    "path": candidate["path"],
                }
                for candidate in candidates
            ],
            asset_resolution="ambiguous",
            asset_resolution_reason="duplicate_guid",
        )
        return fields
    candidate = candidates[0]
    if candidate.get("metadata_unreadable"):
        fields.update(
            target_asset_kind="unresolved",
            asset_resolution="missing",
            asset_resolution_reason="unreadable_meta",
        )
        return fields
    if not candidate["exists"]:
        fields.update(
            target_asset_kind="unresolved",
            asset_resolution="missing",
            asset_resolution_reason="missing_target",
        )
        return fields
    kind = str(candidate["kind"])
    path = str(candidate["path"])
    fields.update(
        target_asset_kind=kind,
        target_asset_path=path,
        asset_resolution="resolved",
    )
    if kind == "cs":
        fields["script_object_resolution"] = "asset_level_only"
    elif kind == "binary" and path.lower().endswith(".dll"):
        fields["script_object_resolution"] = "not_verifiable_binary"
    elif kind == "binary":
        fields.update(
            asset_resolution="unsupported_binary",
            asset_resolution_reason="unsupported_format",
        )
    return fields


def _row_key(
    row: Dict[str, object],
) -> Tuple[str, int, str, str, str, str]:
    return (
        str(row["source_asset_path"]),
        int(row["source_object_file_id"]),
        str(row.get("m_script_guid") or ""),
        str(row.get("m_script_file_id") or ""),
        str(row["reference_shape"]),
        str(row.get("raw_reference") or ""),
    )


def _read_source(
    path: Path,
    root: Path,
) -> Tuple[Optional[str], Optional[Dict[str, object]]]:
    relative = _relative(path, root)
    try:
        data = path.read_bytes()
    except OSError as error:
        return None, _warning(
            "source_unreadable",
            f"Candidate source asset could not be read: {error}",
            relative,
        )
    if b"\x00" in data:
        return None, _warning(
            "source_binary",
            "Candidate source asset is binary and was not inspected.",
            relative,
        )
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, _warning(
            "source_binary",
            "Candidate source asset is not UTF-8 text and was not inspected.",
            relative,
        )
    if not text.lstrip().startswith("%YAML") and "--- !u!" not in text:
        return None, _warning(
            "source_unrecognized",
            "Candidate source asset is not recognized as Unity text serialization.",
            relative,
        )
    return text, None


def bindings_query(
    project: Optional[Path],
    limit: Optional[str],
    cursor: Optional[str],
) -> Dict[str, object]:
    """Return a version-1 component-script binding envelope."""

    payload: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "command": "bindings",
        "status": "invalid_project",
        "project": {"root": str(project) if project is not None else ""},
        "query": {},
        "results": [],
        "limits": {},
        "truncated": False,
        "warnings": [],
        "error": None,
        "scan_coverage": "pending",
        "next_cursor": None,
    }
    warnings: List[Dict[str, object]] = []
    project_valid = False
    try:
        if project is None:
            raise NavigationError(
                "invalid_project",
                "The bindings command requires a Unity project root.",
            )
        root, included_roots = _validated_project(Path(project))
        project_valid = True
        project_info, version_warnings = _project_info(root, included_roots)
        payload["project"] = project_info
        warnings.extend(version_warnings)

        page_limit = _parse_limit(limit)
        query: Dict[str, object] = {}
        cursor_key = (
            _decode_cursor(root, query, cursor)
            if cursor is not None
            else None
        )
        payload["limits"] = {
            "limit": page_limit,
            "default_limit": DEFAULT_LIMIT,
            "max_limit": MAX_LIMIT,
        }

        files, scan_warnings = _walk_files(root, included_roots)
        warnings.extend(scan_warnings)
        guid_index, metadata_warnings = _build_guid_index(root, files)
        warnings.extend(metadata_warnings)
        rows: List[Dict[str, object]] = []
        source_warnings: List[Dict[str, object]] = []
        for path in files:
            if path.suffix.lower() not in SOURCE_KINDS:
                continue
            text, warning = _read_source(path, root)
            if warning is not None:
                source_warnings.append(warning)
                continue
            for row in _parse_source(path, root, str(text)):
                row.update(
                    _target_fields(
                        row["reference_shape"],
                        row.get("m_script_guid"),
                        guid_index,
                    )
                )
                rows.append(row)
        warnings.extend(source_warnings)

        coverage = (
            "partial"
            if scan_warnings or source_warnings or metadata_warnings
            else "complete"
        )
        rows.sort(key=_row_key)
        if cursor_key is not None:
            rows = [row for row in rows if _row_key(row) > cursor_key]
        page = rows[:page_limit]
        has_more = len(rows) > page_limit
        payload["results"] = page
        payload["next_cursor"] = (
            _encode_cursor(root, query, _row_key(page[-1]))
            if has_more and page
            else None
        )
        payload["scan_coverage"] = coverage
        payload["status"] = "partial" if coverage == "partial" else "ok"
    except NavigationError as error:
        payload["error"] = {"code": error.code, "message": str(error)}
        payload["status"] = (
            "invalid_query" if project_valid else "invalid_project"
        )
    except OSError as error:
        payload["status"] = "invalid_project"
        payload["error"] = {"code": "invalid_project", "message": str(error)}
    payload["warnings"] = _sorted_warnings(warnings)
    return payload


def bindings_exit_code(payload: Dict[str, object]) -> int:
    status = payload.get("status")
    if status == "ok":
        return 0
    if status == "partial":
        return 4
    return 3
