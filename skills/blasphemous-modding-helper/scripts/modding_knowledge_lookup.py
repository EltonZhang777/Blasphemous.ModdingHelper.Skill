#!/usr/bin/env python3
"""Read one verified Blasphemous 1 knowledge note from a pinned commit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from http.client import HTTPException
from typing import Callable, Dict, List, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from blasphemous_modding_helper.note_title import is_canonical_title_scalar


_REPOSITORY = "EltonZhang777/Blasphemous.ModdingHelper.Skill"
_COMMIT_URL = f"https://api.github.com/repos/{_REPOSITORY}/commits/main"
_RAW_BASE = f"https://raw.githubusercontent.com/{_REPOSITORY}/"
_INDEX_PATH = "docs/modding-knowledge/index.json"
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_NOTE_PATH = re.compile(r"docs/modding-knowledge/[a-z0-9]+(?:-[a-z0-9]+)*\.md\Z")


class KnowledgeLookupError(ValueError):
    """A retrieval or validation failure, labelled with its workflow phase."""

    def __init__(self, phase: str, message: str):
        super().__init__(message)
        self.phase = phase


def _http_get_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "blasphemous-modding-helper",
        },
    )
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def _fetch_json(fetch_text: Callable[[str], str], url: str, phase: str):
    try:
        return json.loads(fetch_text(url))
    except (HTTPException, HTTPError, URLError, TimeoutError, OSError, UnicodeError, ValueError) as error:
        raise KnowledgeLookupError(phase, f"could not retrieve or parse response: {error}") from error


def _valid_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _verified_entries(value: object) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        raise KnowledgeLookupError("index", "index root must be a JSON array")

    entries = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"title", "status", "date", "path"}:
            raise KnowledgeLookupError("index", "index entry has an invalid shape")
        if item["status"] != "verified":
            continue
        if (
            not isinstance(item["title"], str)
            or not is_canonical_title_scalar(item["title"])
            or not _valid_date(item["date"])
            or not isinstance(item["path"], str)
            or not _NOTE_PATH.fullmatch(item["path"])
        ):
            raise KnowledgeLookupError("index", "verified index entry has invalid metadata or path")
        entries.append({key: item[key] for key in ("title", "status", "date", "path")})
    return entries


def resolve_index(fetch_text: Callable[[str], str] = _http_get_text) -> Dict[str, object]:
    """Resolve main once, then return verified index metadata pinned to that SHA."""
    commit = _fetch_json(fetch_text, _COMMIT_URL, "commit")
    sha = commit.get("sha") if isinstance(commit, dict) else None
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise KnowledgeLookupError("commit", "response did not contain a full commit SHA")

    index_url = f"{_RAW_BASE}{sha}/{_INDEX_PATH}"
    index = _fetch_json(fetch_text, index_url, "index")
    return {"commit_sha": sha, "entries": _verified_entries(index)}


def _note_metadata(content: str) -> Dict[str, str]:
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise KnowledgeLookupError("note", "note is missing YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise KnowledgeLookupError("note", "note frontmatter is unterminated") from error

    metadata = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        scalar = value[1:] if separator and value.startswith(" ") else ""
        if (
            not separator
            or key not in {"title", "status", "date"}
            or key in metadata
            or not scalar
            or scalar != scalar.strip()
            or (key == "title" and not is_canonical_title_scalar(scalar))
        ):
            raise KnowledgeLookupError("note", "note frontmatter is invalid")
        metadata[key] = scalar
    if tuple(metadata) != ("title", "status", "date") or not _valid_date(metadata.get("date")):
        raise KnowledgeLookupError("note", "note frontmatter fields or date are invalid")
    return metadata


def fetch_note(
    fetch_text: Callable[[str], str], commit_sha: str, entry: Mapping[str, str]
) -> Dict[str, str]:
    """Fetch exactly the selected verified note and return its provenance."""
    if not isinstance(commit_sha, str) or not _SHA.fullmatch(commit_sha):
        raise KnowledgeLookupError("note", "commit SHA is not a full lowercase Git SHA")
    if (
        entry.get("status") != "verified"
        or not isinstance(entry.get("title"), str)
        or not is_canonical_title_scalar(entry["title"])
        or not _valid_date(entry.get("date"))
        or not isinstance(entry.get("path"), str)
        or not _NOTE_PATH.fullmatch(entry["path"])
    ):
        raise KnowledgeLookupError("note", "selected index entry is invalid")

    url = f"{_RAW_BASE}{commit_sha}/{entry['path']}"
    try:
        content = fetch_text(url)
    except (HTTPException, HTTPError, URLError, TimeoutError, OSError, UnicodeError, ValueError) as error:
        raise KnowledgeLookupError("note", f"could not retrieve selected note: {error}") from error
    metadata = _note_metadata(content)
    if any(metadata.get(key) != entry[key] for key in ("title", "status", "date")):
        raise KnowledgeLookupError("note", "note metadata does not match its index entry")
    return {
        "title": metadata["title"],
        "date": metadata["date"],
        "commit_sha": commit_sha,
        "path": entry["path"],
        "content": content,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("resolve", help="resolve main once and read its verified note index")
    note = commands.add_parser("note", help="read one selected note from the resolved commit")
    note.add_argument("--commit-sha", required=True)
    note.add_argument("--path", required=True)
    note.add_argument("--title", required=True)
    note.add_argument("--date", required=True)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "resolve":
            result = resolve_index(_http_get_text)
        else:
            result = fetch_note(
                _http_get_text,
                args.commit_sha,
                {"title": args.title, "status": "verified", "date": args.date, "path": args.path},
            )
    except KnowledgeLookupError as error:
        print(f"Modding knowledge lookup failed during {error.phase}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
