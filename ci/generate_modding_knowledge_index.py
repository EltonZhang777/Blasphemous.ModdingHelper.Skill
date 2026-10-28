import argparse
import json
import re
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
    "Route",
    "Evidence",
    "Verification result",
    "Limitations",
)


class NoteError(ValueError):
    pass


def parse_note(path, repository_root=None):
    repository_root = Path(repository_root or REPOSITORY_ROOT)
    label = path.relative_to(repository_root)
    if path.is_symlink():
        raise NoteError(f"{label} must not be a symlink")
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

    return metadata


def build_entries(repository_root=None):
    repository_root = Path(repository_root or REPOSITORY_ROOT)
    knowledge_root = repository_root / "docs" / "modding-knowledge"
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
        if (REPOSITORY_ROOT / "docs").is_symlink() or KNOWLEDGE_ROOT.is_symlink():
            raise NoteError("docs/modding-knowledge must not be a symlink")
        expected = render_indexes(build_entries())
        symlinked = [name for name in expected if (KNOWLEDGE_ROOT / name).is_symlink()]
        if symlinked:
            raise NoteError(f"generated output must not be a symlink: {', '.join(symlinked)}")
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
