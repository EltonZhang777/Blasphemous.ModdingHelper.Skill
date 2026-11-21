"""Read-only inspection of Unity serialized documents."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .unity_project import _relative, _warning


DOCUMENT_HEADER = re.compile(r"^--- !u!(\d+) &(-?\d+)(?: stripped)?\s*$")
TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*$")
NAME_FIELD = re.compile(r"^\s{2}m_Name:\s*(.*?)\s*$")
REFERENCE = re.compile(r"\{([^{}]*\bfileID\s*:\s*-?\d+[^{}]*)\}")
REFERENCE_PAIR = re.compile(r"([A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*([^,}]+)")
FIELD_KEY = re.compile(r"([A-Za-z_][A-Za-z0-9_.-]*)\s*:\s+$")
MAPPING_KEY = re.compile(
    r"^\s*(?:-\s+)?([A-Za-z_][A-Za-z0-9_.-]*):\s*(.*)$"
)
BLOCK_SCALAR_HEADER = re.compile(
    r"^(\s*)(-\s+)?((?:[A-Za-z_][A-Za-z0-9_.-]*):\s+)?[|>][0-9+-]*\s*$"
)
LEADING_FLOW_KEY = re.compile(
    r"^\s*(?:-\s+)?([A-Za-z_][A-Za-z0-9_.-]*):\s+[\[{]"
)
PLAIN_KEY = re.compile(
    r"^(\s*)(-\s+)?([A-Za-z_][A-Za-z0-9_.-]*):(?:\s+(.*))?$"
)
MIN_UNITY_ID = -(2**63)
MAX_UNITY_ID = 2**63 - 1


class SerializedError(Exception):
    """A structured serialized-content parse failure."""

    def __init__(
        self,
        status: str,
        code: str,
        message: str,
        warning_code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.warning_code = warning_code


def _strip_comment(text: str) -> str:
    quote: Optional[str] = None
    index = 0
    while index < len(text):
        character = text[index]
        if quote is not None:
            if quote == '"' and character == "\\":
                index += 2
                continue
            if character == quote:
                if quote == "'" and index + 1 < len(text) and text[index + 1] == "'":
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if character in {"'", '"'}:
            previous = index - 1
            while previous >= 0 and text[previous] == " ":
                previous -= 1
            if previous < 0 or text[previous] in ":-[{,":
                quote = character
            index += 1
            continue
        if character == "#" and (index == 0 or text[index - 1].isspace()):
            return text[:index].rstrip()
        index += 1
    return text.rstrip()


def _scalar(raw: str) -> Optional[str]:
    raw = _strip_comment(raw).strip()
    if not raw or raw in {"~", "null"} or raw in {"|", "|-", "|+", ">", ">-", ">+"}:
        return None
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    if raw.startswith('"') and raw.endswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return raw[1:-1]
        return value if isinstance(value, str) else None
    return raw


def _unity_id(value: str, field: str, relative: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise SerializedError(
            "invalid_query",
            "malformed_serialized",
            f"{field} is not a signed 64-bit integer in {relative}.",
            "malformed_document",
        ) from error
    if not MIN_UNITY_ID <= parsed <= MAX_UNITY_ID:
        raise SerializedError(
            "invalid_query",
            "malformed_serialized",
            f"{field} is outside the signed 64-bit range in {relative}.",
            "malformed_document",
        )
    return parsed


def _structure_only(
    line: str, quote: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """Blank quoted scalars and comments while keeping YAML structure."""

    characters = list(line)
    index = 0
    while index < len(characters):
        character = characters[index]
        if quote is not None:
            characters[index] = " "
            if quote == '"' and character == "\\" and index + 1 < len(characters):
                characters[index + 1] = " "
                index += 2
                continue
            if character == quote:
                if (
                    quote == "'"
                    and index + 1 < len(characters)
                    and characters[index + 1] == "'"
                ):
                    characters[index + 1] = " "
                    index += 2
                    continue
                quote = None
            index += 1
            continue
        if character in {"'", '"'}:
            previous = index - 1
            while previous >= 0 and line[previous] == " ":
                previous -= 1
            if previous < 0 or line[previous] in ":-[{,":
                quote = character
                characters[index] = " "
            index += 1
            continue
        if character == "#" and (index == 0 or line[index - 1].isspace()):
            characters[index:] = " " * (len(characters) - index)
            break
        index += 1
    return "".join(characters), quote


def _structure_lines(lines: Sequence[str]) -> List[str]:
    structures: List[str] = []
    block_indent: Optional[int] = None
    plain_indent: Optional[int] = None
    quote: Optional[str] = None
    for line in lines:
        indentation = len(line) - len(line.lstrip(" "))
        if block_indent is not None:
            if not line.strip() or indentation > block_indent:
                structures.append("")
                continue
            block_indent = None
        if plain_indent is not None:
            if not line.strip() or indentation > plain_indent:
                structures.append("")
                continue
            plain_indent = None
        structure, quote = _structure_only(line, quote)
        header = BLOCK_SCALAR_HEADER.fullmatch(structure)
        if header:
            block_indent = len(header.group(1))
            if header.group(2) and header.group(3):
                block_indent += len(header.group(2))
        else:
            plain = PLAIN_KEY.match(structure)
            if plain and plain.group(4):
                value = plain.group(4).strip()
                if value and value[0] not in "'\"|>{[&*!~" and not value.startswith("- "):
                    plain_indent = len(plain.group(1)) + len(plain.group(2) or "")
        structures.append(structure)
    return structures


def _document_ranges(
    lines: Sequence[str],
    relative: str,
) -> List[Tuple[int, int, int, int, int]]:
    starts: List[Tuple[int, int, int]] = []
    for index, line in enumerate(lines):
        if not line.startswith("---"):
            continue
        matched = DOCUMENT_HEADER.fullmatch(line.rstrip())
        if matched is None:
            raise SerializedError(
                "invalid_query",
                "malformed_serialized",
                f"Unparseable Unity document header at line {index + 1}.",
                "malformed_document",
            )
        starts.append(
            (
                index,
                _unity_id(matched.group(1), "class ID", relative),
                _unity_id(matched.group(2), "file ID", relative),
            )
        )
    if not starts:
        raise SerializedError(
            "invalid_query",
            "malformed_serialized",
            "Serialized content contains no Unity documents.",
            "malformed_document",
        )
    return [
        (
            start[0] + 1,
            starts[index + 1][0] if index + 1 < len(starts) else len(lines),
            start[1],
            start[2],
            start[0],
        )
        for index, start in enumerate(starts)
    ]


def _component_ids(lines: Sequence[str], relative: str) -> List[int]:
    component_ids: List[int] = []
    active = False
    base_indent = 0
    for structure in _structure_lines(lines):
        indentation = len(structure) - len(structure.lstrip(" "))
        stripped = structure.strip()
        if not active:
            if re.match(r"^\s*m_Component:\s*$", structure):
                active = True
                base_indent = indentation
            continue
        if not stripped:
            continue
        if indentation <= base_indent and not stripped.startswith("- "):
            break
        matched = REFERENCE.search(structure)
        if matched:
            prefix = structure[: matched.start()]
            if (
                FIELD_KEY.search(prefix) is None
                and not prefix.lstrip().startswith("-")
                and not prefix.rstrip().endswith(("[", ",", "{"))
            ):
                continue
            file_id = re.search(r"\bfileID\s*:\s*(-?\d+)", matched.group(1))
            if file_id:
                component_ids.append(
                    _unity_id(file_id.group(1), "component file ID", relative)
                )
    return component_ids


def _references(
    lines: Sequence[str],
    start_line: int,
    relative: str,
) -> List[Dict[str, object]]:
    references: List[Dict[str, object]] = []
    parent_key: Optional[str] = None
    for index, structure in enumerate(_structure_lines(lines)):
        mapping = MAPPING_KEY.match(structure)
        mapping_key = mapping.group(1) if mapping else None
        for matched in REFERENCE.finditer(structure):
            pairs = {
                pair.group(1): pair.group(2).strip()
                for pair in REFERENCE_PAIR.finditer(matched.group(1))
            }
            file_value = pairs.get("fileID")
            if file_value is None or not re.fullmatch(r"-?\d+", file_value):
                continue
            guid = pairs.get("guid")
            type_value = pairs.get("type")
            prefix = structure[: matched.start()]
            field = FIELD_KEY.search(prefix)
            field_name = field.group(1) if field else None
            if field_name is None:
                leading = LEADING_FLOW_KEY.match(prefix)
                if leading:
                    field_name = leading.group(1)
            if (
                field_name is None
                and not prefix.lstrip().startswith("-")
                and not prefix.rstrip().endswith(("[", ",", "{"))
            ):
                continue
            file_id = _unity_id(file_value, "reference file ID", relative)
            type_id = (
                _unity_id(type_value, "reference type", relative)
                if type_value and re.fullmatch(r"-?\d+", type_value)
                else None
            )
            if field_name == "component" and parent_key == "m_Component":
                field_name = "m_Component.component"
            if field_name is None:
                field_name = parent_key or "reference"
            references.append(
                {
                    "field": field_name,
                    "file_id": file_id,
                    "guid": guid,
                    "type": type_id,
                    "scope": (
                        "external"
                        if guid
                        else ("null" if file_id == 0 else "local")
                    ),
                    "line": start_line + index + 1,
                }
            )
        if mapping and not mapping.group(2).strip():
            parent_key = mapping_key
    return references


def _container_file_id(lines: Sequence[str], relative: str) -> Optional[int]:
    for structure in _structure_lines(lines):
        matched = re.match(r"^\s{2}m_GameObject:\s*\{([^}]*)\}", structure)
        if matched is None:
            continue
        file_id = re.search(r"\bfileID\s*:\s*(-?\d+)", matched.group(1))
        if file_id:
            return _unity_id(file_id.group(1), "container file ID", relative)
    return None


def parse_serialized_file(
    path: Path, root: Path
) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    """Return observed objects and references from one Unity serialized file."""

    relative = _relative(path, root)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise SerializedError(
            "invalid_query",
            "unreadable_serialized",
            f"File could not be read: {relative}: {error}",
            "serialized_unreadable",
        ) from error
    if b"\x00" in raw:
        raise SerializedError(
            "unsupported_format",
            "unsupported_serialized_format",
            f"File is not UTF-8 text and was not inspected: {relative}",
            "binary_asset_not_inspected",
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise SerializedError(
            "invalid_query",
            "malformed_serialized",
            f"File is not valid UTF-8 text: {relative}",
            "malformed_document",
        ) from error

    lines = text.splitlines()
    warnings: List[Dict[str, object]] = []
    objects: List[Dict[str, object]] = []
    seen_ids = set()
    for body_start, end, class_id, file_id, header_line in _document_ranges(
        lines, relative
    ):
        body = lines[body_start:end]
        top_level = next((line for line in body if line.strip()), "")
        matched = TOP_LEVEL_KEY.fullmatch(top_level.rstrip())
        if matched is None:
            raise SerializedError(
                "invalid_query",
                "malformed_serialized",
                f"Unity document at line {header_line + 1} has no class container: {relative}",
                "malformed_document",
            )
        if file_id in seen_ids:
            warnings.append(
                _warning(
                    "duplicate_object_id",
                    f"Duplicate serialized object ID {file_id} in one file.",
                    relative,
                )
            )
        seen_ids.add(file_id)
        name = None
        for line in body:
            name_match = NAME_FIELD.fullmatch(line)
            if name_match:
                name = _scalar(name_match.group(1))
                break
        references = _references(body, body_start, relative)
        objects.append(
            {
                "file_id": file_id,
                "class_id": class_id,
                "class_name": matched.group(1),
                "name": name,
                "component_file_ids": _component_ids(body, relative),
                "container_file_id": _container_file_id(body, relative),
                "references": references,
            }
        )
    objects.sort(key=lambda item: item["file_id"])
    return {
        "path": relative,
        "status": "ok",
        "object_count": len(objects),
        "reference_count": sum(len(item["references"]) for item in objects),
        "objects": objects,
    }, warnings
