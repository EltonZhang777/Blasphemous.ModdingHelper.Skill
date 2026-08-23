#!/usr/bin/env python3
"""Audit authored Markdown for likely unmarked RFC 2119 instructions.

The audit is deliberately conservative. It reports likely unmarked imperatives
and lowercase absolute requirement words for manual review; it does not rewrite
documents or decide whether descriptive prose is normative. Fenced source/code
examples, block quotes, and source-navigation facts are treated as non-normative
contexts where the local requirement contract permits original wording.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


UPPERCASE_KEYWORD = re.compile(
    r"\b(?:MUST(?:\s+NOT)?|SHALL(?:\s+NOT)?|SHOULD(?:\s+NOT)?|"
    r"REQUIRED|RECOMMENDED|NOT\s+RECOMMENDED|MAY|OPTIONAL)\b"
)
LOWERCASE_ABSOLUTE = re.compile(
    r"\b(?:must(?:\s+not)?|shall(?:\s+not)?|should(?:\s+not)?)\b"
)
UNMARKED_IMPERATIVE = re.compile(
    r"^(?:do\s+not|don't|use|check|read|follow|keep|make\s+sure|ensure|"
    r"ask|run|analyze|prioritize|inspect|verify|load|route|call|include|"
    r"avoid|return|delete|create|set|select|copy|move|add|remove|apply|"
    r"preserve|prefer|stop|continue|report|provide|display|choose|write|"
    r"save|validate|treat|target|organize|record|override|release|register|"
    r"place|expose|limit|consider)\b",
    re.IGNORECASE,
)
LIST_MARKER = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)")
TABLE_SEPARATOR = re.compile(r"^:?-{3,}:?$")
CODE_LANGUAGES = {
    "bash",
    "c",
    "c#",
    "csharp",
    "cpp",
    "cs",
    "diff",
    "json",
    "powershell",
    "ps1",
    "sh",
    "shell",
    "textile",
    "xml",
    "yaml",
    "yml",
}


def strip_inline_code(value: str) -> str:
    """Remove inline code so examples do not become instruction candidates."""

    return re.sub(r"`[^`]*`", "", value)


def instruction_fragments(line: str) -> list[str]:
    """Return prose/list/table fragments that can contain an instruction."""

    stripped = strip_inline_code(line.strip())
    if not stripped:
        return []
    if stripped.startswith("#"):
        return []
    if stripped.startswith("|"):
        fragments = [cell.strip() for cell in stripped.strip("|").split("|")]
        return [fragment for fragment in fragments if fragment and not TABLE_SEPARATOR.match(fragment)]
    return [LIST_MARKER.sub("", stripped)]


def is_code_fence(line: str) -> tuple[bool, str]:
    stripped = line.strip()
    if stripped.startswith("```"):
        return True, stripped[3:].strip().lower().split()[0] if stripped[3:].strip() else ""
    if stripped.startswith("~~~"):
        return True, stripped[3:].strip().lower().split()[0] if stripped[3:].strip() else ""
    return False, ""


def audit_file(path: Path, skill_root: Path) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    in_fence = False
    fence_language = ""
    in_html_comment = False
    in_frontmatter = False
    first_line = True
    source_navigation = "source_code_navigation" in path.parts

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.rstrip()

        if first_line and line.strip() == "---":
            in_frontmatter = True
            first_line = False
            continue
        first_line = False
        if in_frontmatter:
            if line.strip() == "---":
                in_frontmatter = False
            continue

        fence, language = is_code_fence(line)
        if fence:
            if not in_fence:
                in_fence = True
                fence_language = language
            else:
                in_fence = False
                fence_language = ""
            continue
        if in_fence and fence_language in CODE_LANGUAGES:
            continue
        if in_html_comment:
            if "-->" in line:
                in_html_comment = False
            continue
        if "<!--" in line:
            if "-->" not in line.split("<!--", 1)[1]:
                in_html_comment = True
            continue
        if line.lstrip().startswith(">") or line.startswith("    "):
            continue

        fragments = instruction_fragments(line)
        if not fragments:
            continue

        if any(
            fragment.lower().startswith(("route:", "request:", "action:", "good:", "bad:"))
            for fragment in fragments
        ):
            continue

        has_uppercase_keyword = bool(UPPERCASE_KEYWORD.search(line))
        if not has_uppercase_keyword and LOWERCASE_ABSOLUTE.search(line):
            if not source_navigation:
                findings.append((line_number, "lowercase requirement word", line.strip()))
                continue

        if has_uppercase_keyword:
            continue
        if re.search(r"\b(?:do\s+not|don't)\b", line, re.IGNORECASE):
            findings.append((line_number, "unmarked prohibition", line.strip()))
            continue
        if line.lstrip().startswith("|"):
            # Navigation and responsibility tables often use verb phrases as
            # factual labels. Lowercase absolute words are still audited above;
            # an uppercase keyword makes a normative table cell self-documenting.
            continue
        if source_navigation:
            # These documents are source/API indexes. Their descriptions and
            # action labels are factual references, not agent instructions.
            continue
        if any(UNMARKED_IMPERATIVE.match(fragment) for fragment in fragments):
            findings.append((line_number, "unmarked imperative", line.strip()))

    return findings


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root,
        help="Skill directory to audit (default: this script's parent Skill directory)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with status 1 when any candidate is reported",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    files = sorted(root.rglob("*.md"))
    findings: list[tuple[Path, int, str, str]] = []
    for path in files:
        findings.extend((path, line, kind, text) for line, kind, text in audit_file(path, root))

    if findings:
        for path, line, kind, text in findings:
            print(f"{path.relative_to(root)}:{line}: {kind}: {text}")
        print(f"RFC 2119 candidate audit: {len(findings)} finding(s) in {len(files)} Markdown files.")
        return 1 if args.strict else 0

    print(f"RFC 2119 candidate audit: PASS ({len(files)} Markdown files scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
