import argparse
import json
import re
import stat
import sys
from datetime import date
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "scripts"))

from blasphemous_modding_helper.note_title import is_canonical_title_scalar


KNOWLEDGE_ROOT = REPOSITORY_ROOT / "docs" / "modding-knowledge"
FIELDS = ("title", "status", "date")
STATUSES = {"candidate", "verified", "superseded", "withdrawn"}
NOTE_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\.md\Z")
REQUIRED_SECTIONS = (
    "Applicable Blasphemous 1 version",
    "Applicable Mod version",
    "Route",
    "Evidence",
    "Verification result",
    "Evidence history",
    "Limitations",
)
EVIDENCE_TYPES = (
    "Static source inspection:",
    "Runtime evidence:",
    "Manual/in-game evidence:",
    "Localization evidence:",
)


class NoteError(ValueError):
    pass


def _is_link_or_junction(path):
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def parse_note(path, repository_root=None):
    repository_root = Path(repository_root or REPOSITORY_ROOT)
    label = path.relative_to(repository_root)
    if _is_link_or_junction(path):
        raise NoteError(f"{label} must not be a symlink or junction")
    if not NOTE_NAME.fullmatch(path.name):
        raise NoteError(f"{label} must use a lowercase topic-slug filename")

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise NoteError(f"{label} is missing YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise NoteError(f"{label} has unterminated YAML frontmatter") from error

    metadata = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        scalar = value[1:] if separator and value.startswith(" ") else ""
        invalid_title = key == "title" and not is_canonical_title_scalar(scalar)
        if (
            not separator
            or key not in FIELDS
            or key in metadata
            or not scalar
            or scalar != scalar.strip()
            or "\t" in scalar
            or invalid_title
        ):
            raise NoteError(f"{label} has invalid frontmatter: {line}")
        metadata[key] = scalar
    if tuple(metadata) != FIELDS:
        raise NoteError(f"{label} frontmatter must contain title, status, and date in that order")
    if metadata["status"] not in STATUSES:
        raise NoteError(f"{label} has unsupported status: {metadata['status']}")
    try:
        parsed_date = date.fromisoformat(metadata["date"])
    except ValueError as error:
        raise NoteError(f"{label} date must use YYYY-MM-DD") from error
    if parsed_date.isoformat() != metadata["date"]:
        raise NoteError(f"{label} date must use YYYY-MM-DD")

    body = lines[end + 1 :]
    sections = {}
    current = None
    active_fence = None
    for line in body:
        if active_fence is not None:
            marker, minimum = active_fence
            if re.fullmatch(r" {0,3}" + re.escape(marker) + r"{" + str(minimum) + r",}\s*", line):
                active_fence = None
            continue
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            active_fence = (fence.group(1)[0], len(fence.group(1)))
            continue
        if line.startswith("## "):
            current = line[3:]
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    if active_fence is not None:
        raise NoteError(f"{label} has an unclosed fenced code block")
    for heading in REQUIRED_SECTIONS:
        if not "\n".join(sections.get(heading, ())).strip():
            raise NoteError(f"{label} needs a non-empty '## {heading}' section")

    for heading in REQUIRED_SECTIONS[:2]:
        version_lines = [line.strip() for line in sections[heading] if line.strip()]
        if not version_lines or not version_lines[0].startswith("Version:"):
            raise NoteError(f"{label} {heading} must begin with 'Version:' and name its scope")
        version = version_lines[0][len("Version:") :].strip()
        if not version or re.search(r"\b(?:tbd|todo|pending)\b", version, re.IGNORECASE):
            raise NoteError(f"{label} {heading} must name a version or explicitly say Unknown/Not applicable")
        if heading == REQUIRED_SECTIONS[0] and re.search(r"\b(?:blasphemous\s*2|b2)\b", version, re.IGNORECASE):
            raise NoteError(f"{label} is a Blasphemous 1 note and must not name Blasphemous 2")

    evidence_lines = [line.strip() for line in sections["Evidence"] if line.strip()]
    if not evidence_lines or any(
        not any(line.startswith(kind) and line[len(kind) :].strip() for kind in EVIDENCE_TYPES)
        for line in evidence_lines
    ):
        raise NoteError(f"{label} each Evidence source must have a recognized type label")

    history = [line.strip() for line in sections["Evidence history"] if line.strip()]
    if not history:
        raise NoteError(f"{label} Evidence history needs a dated entry")
    for entry in history:
        match = re.fullmatch(r"- (\d{4}-\d{2}-\d{2}): (.+)", entry)
        if not match:
            raise NoteError(f"{label} Evidence history entries must use '- YYYY-MM-DD: correction and evidence' format")
        try:
            history_date = date.fromisoformat(match.group(1))
        except ValueError as error:
            raise NoteError(f"{label} Evidence history dates must use YYYY-MM-DD") from error
        if history_date.isoformat() != match.group(1) or history_date > parsed_date:
            raise NoteError(f"{label} Evidence history dates must be valid and no later than the note date")

    return metadata


def build_entries(repository_root=None):
    repository_root = Path(repository_root or REPOSITORY_ROOT)
    if _is_link_or_junction(repository_root / "docs"):
        raise NoteError("docs/modding-knowledge must not contain symlinked directories")
    knowledge_root = repository_root / "docs" / "modding-knowledge"
    if _is_link_or_junction(knowledge_root):
        raise NoteError("docs/modding-knowledge must not contain symlinked directories")
    entries = []
    for path in sorted(knowledge_root.glob("*.md"), key=lambda item: item.name.casefold()):
        if path.name.casefold() == "index.md":
            continue
        metadata = parse_note(path, repository_root)
        if metadata["status"] == "verified":
            entries.append(
                {
                    "title": metadata["title"],
                    "status": metadata["status"],
                    "date": metadata["date"],
                    "path": path.relative_to(repository_root).as_posix(),
                }
            )

    titles = [entry["title"].casefold() for entry in entries]
    if len(titles) != len(set(titles)):
        raise NoteError("verified note titles must be unique, ignoring case")
    return sorted(entries, key=lambda entry: (entry["title"].casefold(), entry["path"]))


def render_indexes(entries):
    rows = [
        "# Blasphemous 1 Modding Knowledge Index",
        "",
        "Generated from verified canonical note frontmatter. Do not edit by hand.",
        "",
        "| Title | Date | Status | Note |",
        "| --- | --- | --- | --- |",
    ]
    for entry in entries:
        title = entry["title"].replace("|", "\\|")
        note_name = Path(entry["path"]).name
        rows.append(
            f"| {title} | {entry['date']} | {entry['status']} | [{entry['path']}]({note_name}) |"
        )
    markdown = "\n".join(rows) + "\n"
    machine = json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    return {"INDEX.md": markdown, "index.json": machine}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate or check the Blasphemous 1 modding knowledge indexes.")
    parser.add_argument("--check", action="store_true", help="fail if either generated index is missing or stale")
    args = parser.parse_args(argv)

    try:
        expected = render_indexes(build_entries())
        symlinked = [name for name in expected if _is_link_or_junction(KNOWLEDGE_ROOT / name)]
        if symlinked:
            raise NoteError(f"generated output must not be a symlink or junction: {', '.join(symlinked)}")
        if args.check:
            stale = []
            for name, content in expected.items():
                path = KNOWLEDGE_ROOT / name
                if not path.is_file() or path.read_text(encoding="utf-8") != content:
                    stale.append(name)
            if stale:
                for name in stale:
                    print(f"{name} is stale; run python ci/generate_modding_knowledge_index.py", file=sys.stderr)
                return 1
            print("Modding knowledge indexes are consistent.")
            return 0

        KNOWLEDGE_ROOT.mkdir(parents=True, exist_ok=True)
        for name, content in expected.items():
            (KNOWLEDGE_ROOT / name).write_text(content, encoding="utf-8")
        print("Generated INDEX.md and index.json from verified canonical notes.")
        return 0
    except (OSError, UnicodeError, NoteError) as error:
        print(f"modding knowledge index error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
