#!/usr/bin/env python3
"""Save one explicitly approved Blasphemous 1 experience note locally."""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from blasphemous_modding_helper.note_title import is_canonical_title_scalar


_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_RESERVED_SLUGS = {"con", "prn", "aux", "nul"} | {
    f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)
}
_REQUIRED_SECTIONS = (
    "Finding",
    "Applicable Blasphemous 1 version",
    "Applicable Mod version",
    "Route",
    "Evidence",
    "Reproduction steps",
    "Verification result",
    "Evidence history",
    "Limitations",
)
_EVIDENCE_TYPES = (
    "Static source inspection:",
    "Runtime evidence:",
    "Manual/in-game evidence:",
    "Localization evidence:",
)


class NoteSaveError(ValueError):
    """The approved note cannot be safely saved."""


def _is_link_or_junction(path: Path) -> bool:
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


def _validate_note(content: str) -> None:
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise NoteSaveError("note must start with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise NoteSaveError("note frontmatter is not closed") from error

    metadata = [line.partition(":") for line in lines[1:end]]
    if (
        len(metadata) != 3
        or any(not separator for _, separator, _ in metadata)
        or [key for key, _, _ in metadata] != ["title", "status", "date"]
    ):
        raise NoteSaveError("frontmatter must contain only title, status, and date in that order")
    title_value = metadata[0][2]
    title_scalar = title_value[1:] if title_value.startswith(" ") else ""
    if not is_canonical_title_scalar(title_scalar):
        raise NoteSaveError("frontmatter title must use a canonical plain scalar")
    values = {key: value.strip() for key, _, value in metadata}
    if not values["title"] or values["status"] != "candidate":
        raise NoteSaveError("note must have a title and status: candidate")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", values["date"]) is None:
        raise NoteSaveError("frontmatter date must use YYYY-MM-DD")
    try:
        note_date = date.fromisoformat(values["date"])
    except ValueError as error:
        raise NoteSaveError("frontmatter date must be a real calendar date") from error
    if note_date.isoformat() != values["date"]:
        raise NoteSaveError("frontmatter date must use YYYY-MM-DD")

    body = "\n".join(lines[end + 1 :])
    sections = {}
    for section in _REQUIRED_SECTIONS:
        match = re.search(r"(?m)^## " + re.escape(section) + r"\s*$", body)
        if match is None:
            raise NoteSaveError(f"note is missing the '## {section}' section")
        next_heading = re.search(r"(?m)^## \S", body[match.end() :])
        section_body = body[match.end() : match.end() + next_heading.start() if next_heading else None]
        if not section_body.strip():
            raise NoteSaveError(f"note section '## {section}' must not be empty")
        sections[section] = [line.strip() for line in section_body.splitlines() if line.strip()]

    for section in _REQUIRED_SECTIONS[1:3]:
        version_lines = sections[section]
        if not version_lines[0].startswith("Version:"):
            raise NoteSaveError(f"note section '## {section}' must begin with 'Version:'")
        version = version_lines[0][len("Version:") :].strip()
        if not version or re.search(r"\b(?:tbd|todo|pending)\b", version, re.IGNORECASE):
            raise NoteSaveError(f"note section '## {section}' must name a version or say Unknown/Not applicable")
        if section == _REQUIRED_SECTIONS[1] and re.search(r"\b(?:blasphemous\s*2|b2)\b", version, re.IGNORECASE):
            raise NoteSaveError("Blasphemous 1 experience notes must not name Blasphemous 2")

    if any(
        not any(line.startswith(kind) and line[len(kind) :].strip() for kind in _EVIDENCE_TYPES)
        for line in sections["Evidence"]
    ):
        raise NoteSaveError("each evidence source must have a recognized type label and source detail")

    for entry in sections["Evidence history"]:
        match = re.fullmatch(r"- (\d{4}-\d{2}-\d{2}): (.+)", entry)
        if match is None:
            raise NoteSaveError("evidence history entries must use '- YYYY-MM-DD: correction and evidence' format")
        try:
            history_date = date.fromisoformat(match.group(1))
        except ValueError as error:
            raise NoteSaveError("evidence history dates must be valid YYYY-MM-DD values") from error
        if history_date.isoformat() != match.group(1) or history_date > note_date:
            raise NoteSaveError("evidence history dates must be valid and no later than the note date")


def _write_new_note(path: Path, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    identity = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as note_file:
            note_file.write(content)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            existing = path.lstat()
        except FileNotFoundError:
            pass
        except OSError as cleanup_error:
            raise NoteSaveError(f"incomplete note could not be checked or removed: {path.name}") from cleanup_error
        else:
            if (existing.st_dev, existing.st_ino) == (identity.st_dev, identity.st_ino):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                except OSError as cleanup_error:
                    raise NoteSaveError(f"incomplete note could not be removed: {path.name}") from cleanup_error
        raise


def save_approved_note(
    preferences_file: Path,
    slug: str,
    comparison_outcome: str,
    decision: Optional[str] = None,
    content: str = "",
    *,
    storage: Callable[[Path, str], None] = _write_new_note,
) -> Optional[Path]:
    """Write a new local note only for an explicit yes on a unique candidate."""

    if not isinstance(decision, str) or decision.strip().casefold() != "yes":
        return None
    if comparison_outcome != "unique":
        raise NoteSaveError("only a unique comparison outcome can be saved")
    if not isinstance(slug, str) or _SLUG.fullmatch(slug) is None or slug in _RESERVED_SLUGS:
        raise NoteSaveError("slug must be a safe lowercase topic name without Windows-reserved names")
    if not isinstance(content, str):
        raise NoteSaveError("note content must be text")
    # shortcut: privacy redaction is reviewed before approval; add scanning if unreviewed content can reach this writer.
    _validate_note(content)

    config_path = Path(preferences_file).expanduser()
    if not config_path.is_absolute():
        raise NoteSaveError("preferences-file must be the resolved path selected by invocation preflight")
    if config_path.name != "config.yml" or not config_path.is_file() or config_path.resolve() != config_path:
        raise NoteSaveError("preferences-file must identify the selected config.yml")

    note_directory = config_path.parent / "modding-knowledge"
    target = note_directory / f"{slug}.md"
    if _is_link_or_junction(note_directory):
        raise NoteSaveError("modding-knowledge must not be a symlink or junction")
    if target.exists() or _is_link_or_junction(target):
        raise NoteSaveError(f"local note already exists: {target.name}")
    try:
        note_directory.mkdir(exist_ok=True)
    except OSError as error:
        raise NoteSaveError("could not create the local modding-knowledge directory") from error
    if _is_link_or_junction(note_directory) or not note_directory.is_dir():
        raise NoteSaveError("modding-knowledge is not a safe directory")
    if target.exists() or _is_link_or_junction(target):
        raise NoteSaveError(f"local note already exists: {target.name}")

    try:
        storage(target, content)
    except OSError as error:
        raise NoteSaveError(f"could not save local note: {target.name}") from error
    return target


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preferences-file", type=Path)
    parser.add_argument("--slug", default="")
    parser.add_argument("--comparison-outcome", default="")
    parser.add_argument("--decision", default="")
    args = parser.parse_args(argv)

    if not isinstance(args.decision, str) or args.decision.strip().casefold() != "yes":
        print("No note saved.")
        return 0
    try:
        saved = save_approved_note(
            args.preferences_file or Path(),
            args.slug,
            args.comparison_outcome,
            args.decision,
            sys.stdin.read(),
        )
    except (NoteSaveError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if saved is not None:
        print(f"Saved {saved.name} under modding-knowledge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
