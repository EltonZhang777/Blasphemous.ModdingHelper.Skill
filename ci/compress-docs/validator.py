"""Conservative, local validation for compression candidates."""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Set, Tuple


UTF8_BOM = b"\xef\xbb\xbf"
MAX_ERRORS = 64
MAX_ERROR_LENGTH = 256
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
LIST_ITEM = re.compile(r"^([ \t]*)([-+*]|\d+[.)])(?:[ \t]+)(?:\[([ xX])\][ \t]+)?")
ATX_HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+.*|[ \t]*)$")
SETEXT_HEADING = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
URL = re.compile(r"(?i)\b(?:https?|ftp)://[^\s<>()\]]+")
PATH = re.compile(
    r"(?<![\w])(?:[A-Za-z]:[\\/]|(?:\.\.?[\\/])|[A-Za-z0-9_.-]+[\\/])"
    r"[^\s<>()\],;:]+"
)
PATH_FILENAME = re.compile(
    r"(?i)(?<![\w./\\-])[A-Za-z0-9_-]+\.(?:md|py|js|ts|json|yml|yaml|toml|dll|exe|cs|sh|ps1|bat|txt|log|zip|sln|xml|css|html)(?![\w])"
)
NORMATIVE = re.compile(
    r"\b(?:MUST(?:[ \t]+NOT)?|SHOULD(?:[ \t]+NOT)?|SHALL(?:[ \t]+NOT)?|"
    r"MAY|REQUIRED|RECOMMENDED|OPTIONAL|PROHIBITED)\b"
)
COMMAND_LINE = re.compile(
    r"^\s*(?:[$>]\s*)?(?:"
    r"git\s+(?:add|apply|branch|checkout|clean|clone|commit|diff|log|pull|push|revert|status|switch|worktree)\b|"
    r"gh\s+\w+\b|codex\s+(?:exec|login|resume|review)\b|"
    r"python(?:\d+(?:\.\d+)*)?\s+\S+|node\s+\S+|"
    r"npm\s+(?:install|run|test|exec|pack|publish)\b|"
    r"(?:pip|pipx|dotnet|pytest|cargo|curl)\s+\S+)"
)
TECHNICAL = (
    re.compile(r"(?<![A-Za-z0-9_])[A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+(?![A-Za-z0-9_])"),
    re.compile(r"(?<![A-Za-z0-9_])[A-Z][A-Z0-9_]{2,}(?![A-Za-z0-9_])"),
    re.compile(r"(?<![A-Za-z0-9_])[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]+(?![A-Za-z0-9_])"),
    re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9]*\d[A-Za-z0-9]*(?![A-Za-z0-9_])"),
    re.compile(r"(?<![A-Za-z0-9_])\d+(?:\.\d+)+[A-Za-z0-9]*(?![A-Za-z0-9_])"),
    re.compile(r"(?<![A-Za-z0-9])--[A-Za-z][A-Za-z0-9-]*(?![A-Za-z0-9])"),
    re.compile(
        r"(?<![A-Za-z0-9_])(?=[A-Za-z0-9-]*[A-Z0-9])"
        r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+(?![A-Za-z0-9_])"
    ),
)
LINK_DEFINITION = re.compile(
    r"(?m)^ {0,3}\[[^\]\n]+\]:[ \t]*(?:<[^>\n]+>|[^ \t\n]+)(?:[ \t]+.*)?$"
)


@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.is_valid = False
        if len(self.errors) < MAX_ERRORS:
            self.errors.append(message[:MAX_ERROR_LENGTH])

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


@dataclass
class Protected:
    fenced_code: List[str] = field(default_factory=list)
    indented_code: List[str] = field(default_factory=list)
    inline_code: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    markdown_links: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    technical_identifiers: List[str] = field(default_factory=list)
    headings: List[str] = field(default_factory=list)
    lists: List[Tuple[int, str, str]] = field(default_factory=list)
    tables: List[Tuple[int, ...]] = field(default_factory=list)
    normative_units: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def split_frontmatter(raw: bytes) -> Tuple[bytes, bytes, bytes]:
    bom = UTF8_BOM if raw.startswith(UTF8_BOM) else b""
    content = raw[len(bom) :]
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip(b"\r\n") != b"---":
        return bom, b"", content
    offset = len(lines[0])
    for line in lines[1:]:
        offset += len(line)
        if line.rstrip(b"\r\n") in (b"---", b"..."):
            return bom, content[:offset], content[offset:]
    return bom, b"", content


def _canonical_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _newline_counts(raw: bytes) -> Tuple[int, int]:
    return raw.count(b"\r\n"), raw.replace(b"\r\n", b"").count(b"\n")


def _expected_newline(raw: bytes) -> Tuple[str, bool]:
    crlf, lf = _newline_counts(raw)
    if crlf and lf:
        return ("crlf" if crlf >= lf else "lf"), True
    return ("crlf" if crlf else "lf"), False


def _line_starts(lines: Sequence[str]) -> List[int]:
    starts = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line) + 1
    return starts


def _line_indent(line: str) -> int:
    indent = 0
    for char in line:
        if char == " ":
            indent += 1
        elif char == "\t":
            indent += 4
        else:
            break
    return indent


def _mask_ranges(text: str, ranges: Iterable[Tuple[int, int]]) -> str:
    masked = list(text)
    for start, end in ranges:
        for index in range(start, min(end, len(masked))):
            if masked[index] != "\n":
                masked[index] = " "
    return "".join(masked)


def _extract_fenced(text: str) -> Tuple[List[str], Set[int], List[Tuple[int, int]], List[str]]:
    lines = text.split("\n")
    starts = _line_starts(lines)
    blocks = []
    blocked = set()
    ranges = []
    errors = []
    index = 0
    while index < len(lines):
        opening = FENCE.match(lines[index])
        if not opening:
            index += 1
            continue
        char = opening.group(1)[0]
        length = len(opening.group(1))
        start = index
        index += 1
        closed = False
        while index < len(lines):
            closing = FENCE.match(lines[index])
            if (
                closing
                and closing.group(1)[0] == char
                and len(closing.group(1)) >= length
                and not closing.group(2).strip()
            ):
                end = index
                index += 1
                closed = True
                break
            index += 1
        if not closed:
            end = len(lines) - 1
            errors.append("unclosed fenced code block at line " + str(start + 1))
        blocks.append("\n".join(lines[start : end + 1]))
        blocked.update(range(start, end + 1))
        ranges.append((starts[start], starts[end] + len(lines[end])))
        if not closed:
            break
    return blocks, blocked, ranges, errors


def _extract_indented(
    text: str, fenced_lines: Set[int]
) -> Tuple[List[str], Set[int], List[Tuple[int, int]]]:
    lines = text.split("\n")
    starts = _line_starts(lines)
    blocks = []
    blocked = set()
    ranges = []
    index = 0
    while index < len(lines):
        line = lines[index]
        is_code = (
            index not in fenced_lines
            and bool(line.strip())
            and _line_indent(line) >= 4
            and not LIST_ITEM.match(line)
        )
        if not is_code:
            index += 1
            continue
        start = index
        index += 1
        while index < len(lines) and index not in fenced_lines:
            current = lines[index]
            if current.strip():
                if _line_indent(current) < 4 or LIST_ITEM.match(current):
                    break
                index += 1
                continue
            lookahead = index + 1
            while lookahead < len(lines) and not lines[lookahead].strip():
                lookahead += 1
            if (
                lookahead >= len(lines)
                or lookahead in fenced_lines
                or _line_indent(lines[lookahead]) < 4
                or LIST_ITEM.match(lines[lookahead])
            ):
                break
            index = lookahead
        end = index - 1
        blocks.append("\n".join(lines[start : end + 1]))
        blocked.update(range(start, end + 1))
        ranges.append((starts[start], starts[end] + len(lines[end])))
    return blocks, blocked, ranges


def _extract_inline(text: str) -> Tuple[List[str], List[Tuple[int, int]], List[str]]:
    values = []
    ranges = []
    errors = []
    index = 0
    while index < len(text):
        if text[index] != "`":
            index += 1
            continue
        end = index
        while end < len(text) and text[end] == "`":
            end += 1
        delimiter = "`" * (end - index)
        search = end
        while True:
            closing = text.find(delimiter, search)
            if closing < 0:
                errors.append("unmatched inline code delimiter at byte " + str(index))
                ranges.append((index, len(text)))
                index = len(text)
                break
            longer_left = closing > 0 and text[closing - 1] == "`"
            longer_right = closing + len(delimiter) < len(text) and text[closing + len(delimiter)] == "`"
            if longer_left or longer_right:
                search = closing + 1
                continue
            finish = closing + len(delimiter)
            values.append(text[index:finish])
            ranges.append((index, finish))
            index = finish
            break
    return values, ranges, errors


def _balanced(text: str, start: int, opening: str, closing: str) -> int:
    depth = 1
    index = start + 1
    escaped = False
    while index < len(text):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _extract_links(text: str) -> Tuple[List[str], List[Tuple[int, int]], List[str]]:
    links = []
    ranges = []
    errors = []
    index = 0
    while index < len(text):
        image = text[index] == "!" and index + 1 < len(text) and text[index + 1] == "["
        if text[index] != "[" and not image:
            index += 1
            continue
        start = index
        bracket = index + 1 if image else index
        label_end = _balanced(text, bracket, "[", "]")
        if label_end < 0:
            index += 1
            continue
        next_char = label_end + 1
        if next_char >= len(text) or text[next_char] not in "([":
            index = next_char
            continue
        if text[next_char] == "(":
            end = _balanced(text, next_char, "(", ")")
        else:
            end = _balanced(text, next_char, "[", "]")
        if end < 0:
            errors.append("unclosed Markdown link at byte " + str(start))
            index = next_char + 1
            continue
        finish = end + 1
        links.append(text[start:finish])
        ranges.append((start, finish))
        index = finish
    return links, ranges, errors


def _trim_token(value: str) -> str:
    return value.rstrip(".,;:!?")


def _extract_link_definitions(text: str) -> Tuple[List[str], List[Tuple[int, int]]]:
    matches = list(LINK_DEFINITION.finditer(text))
    return [match.group(0) for match in matches], [match.span() for match in matches]


def _extract_technical(text: str) -> List[str]:
    found = []
    for pattern in TECHNICAL:
        found.extend(match.group(0) for match in pattern.finditer(text))
    return found


def _split_table_row(line: str) -> List[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    cells = []
    current = []
    backticks = 0
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            current.append(char)
            escaped = True
        elif char == "`":
            run = 1
            while index + run < len(text) and text[index + run] == "`":
                run += 1
            current.extend("`" * run)
            backticks = 0 if backticks == run else run
            index += run - 1
        elif char == "|" and not backticks:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


def _is_table_separator(line: str) -> bool:
    if "|" not in line:
        return False
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", cell.replace(" ", "")) for cell in cells)


def _extract_tables(text: str, blocked: Set[int]) -> Tuple[List[Tuple[int, ...]], List[str]]:
    lines = text.split("\n")
    tables = []
    errors = []
    index = 0
    while index < len(lines):
        if index in blocked or not _is_table_separator(lines[index]):
            index += 1
            continue
        start = index - 1
        if start < 0 or start in blocked or "|" not in lines[start]:
            errors.append("table separator has no header row at line " + str(index + 1))
            index += 1
            continue
        while start > 0 and start - 1 not in blocked and lines[start - 1].strip() and "|" in lines[start - 1]:
            start -= 1
        end = index + 1
        while end < len(lines) and end not in blocked and lines[end].strip() and "|" in lines[end]:
            end += 1
        rows = [_split_table_row(lines[row]) for row in range(start, end)]
        width = len(rows[index - start])
        if width < 1 or any(len(row) != width for row in rows):
            errors.append("table column count is inconsistent at line " + str(index + 1))
        tables.append(tuple(len(row) for row in rows))
        index = end
    return tables, errors


def _extract(text: str) -> Protected:
    text = _canonical_newlines(text)
    lines = text.split("\n")
    protected = Protected()
    (
        protected.fenced_code,
        fenced_lines,
        fenced_ranges,
        protected.errors,
    ) = _extract_fenced(text)
    (
        protected.indented_code,
        indented_lines,
        indented_ranges,
    ) = _extract_indented(text, fenced_lines)
    blocked_lines = fenced_lines | indented_lines
    block_ranges = fenced_ranges + indented_ranges
    masked_blocks = _mask_ranges(text, block_ranges)
    protected.inline_code, inline_ranges, inline_errors = _extract_inline(masked_blocks)
    protected.errors.extend(inline_errors)
    masked_inline = _mask_ranges(masked_blocks, inline_ranges)
    protected.markdown_links, link_ranges, link_errors = _extract_links(masked_inline)
    protected.errors.extend(link_errors)
    definitions, definition_ranges = _extract_link_definitions(masked_inline)
    protected.markdown_links.extend(definitions)
    masked_links = _mask_ranges(masked_inline, link_ranges + definition_ranges)
    protected.urls = [_trim_token(match.group(0)) for match in URL.finditer(masked_links)]
    masked_urls = _mask_ranges(masked_links, [match.span() for match in URL.finditer(masked_links)])
    path_matches = list(PATH.finditer(masked_urls)) + list(PATH_FILENAME.finditer(masked_urls))
    path_matches.sort(key=lambda match: match.start())
    protected.paths = [_trim_token(match.group(0)) for match in path_matches if _trim_token(match.group(0))]
    masked_paths = _mask_ranges(masked_urls, [match.span() for match in path_matches])
    protected.technical_identifiers = _extract_technical(masked_paths)
    protected.commands = [
        line.rstrip()
        for index, line in enumerate(lines)
        if index not in blocked_lines and COMMAND_LINE.match(line)
    ]

    for index, line in enumerate(lines):
        if index in blocked_lines:
            continue
        if ATX_HEADING.match(line):
            protected.headings.append(line.rstrip())
        elif index + 1 < len(lines) and index + 1 not in blocked_lines and SETEXT_HEADING.match(lines[index + 1]):
            protected.headings.append((line.rstrip() + "\n" + lines[index + 1].rstrip()))
        list_item = LIST_ITEM.match(line)
        if list_item:
            protected.lists.append(
                (
                    _line_indent(list_item.group(1)),
                    list_item.group(2),
                    list_item.group(3) or "",
                )
            )
    protected.tables, table_errors = _extract_tables(text, blocked_lines)
    protected.errors.extend(table_errors)
    masked_semantics = masked_paths
    for index, line in enumerate(masked_semantics.split("\n")):
        if index not in blocked_lines and NORMATIVE.search(line):
            protected.normative_units.append(lines[index].rstrip())
    return protected


def _compare_sequence(result: ValidationResult, label: str, source: Sequence[object], candidate: Sequence[object]) -> None:
    if list(source) != list(candidate):
        result.add_error(label + " changed (source=" + str(len(source)) + ", candidate=" + str(len(candidate)) + ")")


def _compare_counter(result: ValidationResult, label: str, source: Sequence[str], candidate: Sequence[str]) -> None:
    source_counts = Counter(source)
    candidate_counts = Counter(candidate)
    if source_counts != candidate_counts:
        lost = sum((source_counts - candidate_counts).values())
        added = sum((candidate_counts - source_counts).values())
        result.add_error(label + " changed (lost=" + str(lost) + ", added=" + str(added) + ")")


def validate_candidate(source_raw: bytes, candidate_raw: bytes) -> ValidationResult:
    result = ValidationResult()
    try:
        source_raw.decode("utf-8")
    except UnicodeDecodeError:
        result.add_error("source document is not valid UTF-8")
        return result
    try:
        candidate_raw.decode("utf-8")
    except UnicodeDecodeError:
        result.add_error("candidate document is not valid UTF-8")
        return result
    source_bom, source_frontmatter, source_body = split_frontmatter(source_raw)
    candidate_bom, candidate_frontmatter, candidate_body = split_frontmatter(candidate_raw)
    if source_bom != candidate_bom:
        result.add_error("BOM state changed")
    if source_frontmatter != candidate_frontmatter:
        result.add_error("frontmatter changed byte-for-byte")
    if not source_body.strip():
        result.add_error("source body is empty")
        return result
    if not candidate_body.strip():
        result.add_error("candidate body is empty")
        return result

    source_style, source_mixed = _expected_newline(source_body)
    candidate_style, candidate_mixed = _expected_newline(candidate_body)
    source_has_newline = b"\n" in source_body or b"\r" in source_body
    candidate_has_newline = b"\n" in candidate_body or b"\r" in candidate_body
    if source_has_newline != candidate_has_newline or (candidate_has_newline and (candidate_mixed or candidate_style != source_style)):
        result.add_error("newline style changed")
    if source_mixed:
        result.add_warning("mixed source newlines normalized to " + source_style)

    source_text = _canonical_newlines(source_body.decode("utf-8"))
    candidate_text = _canonical_newlines(candidate_body.decode("utf-8"))
    source_protected = _extract(source_text)
    candidate_protected = _extract(candidate_text)
    for error in source_protected.errors:
        result.add_error("source is ambiguous: " + error)
    for error in candidate_protected.errors:
        result.add_error("candidate is ambiguous: " + error)

    _compare_sequence(result, "fenced code", source_protected.fenced_code, candidate_protected.fenced_code)
    _compare_sequence(result, "indented code", source_protected.indented_code, candidate_protected.indented_code)
    _compare_counter(result, "inline code", source_protected.inline_code, candidate_protected.inline_code)
    _compare_sequence(result, "command", source_protected.commands, candidate_protected.commands)
    _compare_counter(result, "Markdown link", source_protected.markdown_links, candidate_protected.markdown_links)
    _compare_counter(result, "URL", source_protected.urls, candidate_protected.urls)
    _compare_counter(result, "path", source_protected.paths, candidate_protected.paths)
    _compare_counter(
        result,
        "technical identifier",
        source_protected.technical_identifiers,
        candidate_protected.technical_identifiers,
    )
    _compare_sequence(result, "heading", source_protected.headings, candidate_protected.headings)
    _compare_sequence(result, "list", source_protected.lists, candidate_protected.lists)
    _compare_sequence(result, "table", source_protected.tables, candidate_protected.tables)
    _compare_sequence(result, "normative unit", source_protected.normative_units, candidate_protected.normative_units)
    return result


def build_protected_reference(body: str) -> str:
    protected = _extract(body)
    lines = ["Protected reference; copy these values exactly when required:"]
    groups = (
        ("fenced code", protected.fenced_code),
        ("indented code", protected.indented_code),
        ("inline code", protected.inline_code),
        ("commands", protected.commands),
        ("Markdown links", protected.markdown_links),
        ("URLs", protected.urls),
        ("paths", protected.paths),
        ("technical identifiers", protected.technical_identifiers),
        ("headings", protected.headings),
        ("lists", protected.lists),
        ("tables", protected.tables),
        ("normative units", protected.normative_units),
    )
    for name, values in groups:
        if values:
            lines.append("[" + name + "]")
            lines.extend(str(value) for value in values)
    return "\n".join(lines)
