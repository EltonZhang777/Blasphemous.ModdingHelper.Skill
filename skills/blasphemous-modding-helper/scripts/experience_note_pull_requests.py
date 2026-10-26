#!/usr/bin/env python3
"""Prepare pull-request proposals for experience notes already saved with approval."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

from save_experience_note import (
    NoteSaveError,
    _RESERVED_SLUGS,
    _SLUG,
    _is_link_or_junction,
    _validate_note,
)


@dataclass(frozen=True)
class ExperienceNotePullRequest:
    slug: str
    title: str
    body: str
    branch: str
    candidate_path: str
    content: str


def build_pull_request_proposals(
    preferences_file: Path,
    saved_note_paths: Sequence[Path],
) -> list[ExperienceNotePullRequest]:
    config_path = Path(preferences_file).expanduser()
    if (
        not config_path.is_absolute()
        or config_path.name != "config.yml"
        or not config_path.is_file()
        or config_path.resolve() != config_path
    ):
        raise NoteSaveError("preferences-file must identify the resolved config.yml selected by invocation preflight")

    note_directory = config_path.parent / "modding-knowledge"
    if saved_note_paths and (_is_link_or_junction(note_directory) or not note_directory.is_dir()):
        raise NoteSaveError("selected modding-knowledge directory is missing or unsafe")

    proposals = []
    seen = set()
    for value in saved_note_paths:
        source = Path(value)
        slug = source.stem
        if (
            not source.is_absolute()
            or source.parent != note_directory
            or source.suffix != ".md"
            or _SLUG.fullmatch(slug) is None
            or slug in _RESERVED_SLUGS
            or _is_link_or_junction(source)
        ):
            raise NoteSaveError("only returned paths for saved topic-slug notes are eligible for PR review")
        if slug in seen:
            raise NoteSaveError(f"saved note was named more than once: {source.name}")
        seen.add(slug)
        try:
            if source.resolve(strict=True) != source or not source.is_file():
                raise NoteSaveError(f"saved note is unavailable or unsafe: {source.name}")
            with source.open("r", encoding="utf-8", newline="") as note_file:
                content = note_file.read()
        except (OSError, UnicodeError) as error:
            raise NoteSaveError(f"saved note cannot be read: {source.name}") from error
        _validate_note(content)

        candidate_path = f"docs/modding-knowledge/candidates/{source.name}"
        title = f"Add experience note candidate: {slug}"
        body = (
            "Add this locally approved experience note for maintainer review.\n\n"
            "The note remains outside canonical indexing and retrieval until maintainer review. "
            "This pull request does not update canonical indexes.\n\n"
            f"Candidate: `{candidate_path}`\n\n"
            "Exact candidate content:\n\n"
            f"{content}"
        )
        proposals.append(
            ExperienceNotePullRequest(
                slug=slug,
                title=title,
                body=body,
                branch=f"experience-note/{slug}",
                candidate_path=candidate_path,
                content=content,
            )
        )
    return proposals


def create_approved_pull_requests(
    proposals: Sequence[ExperienceNotePullRequest],
    decisions: Mapping[str, Optional[str]],
    create_pull_request: Callable[[ExperienceNotePullRequest], object],
) -> list[tuple[ExperienceNotePullRequest, object]]:
    """Attempt each explicit yes independently; return its result or raised exception."""
    outcomes = []
    for proposal in proposals:
        decision = decisions.get(proposal.slug)
        if isinstance(decision, str) and decision.strip().casefold() == "yes":
            try:
                result = create_pull_request(proposal)
            except Exception as error:
                result = error
            outcomes.append((proposal, result))
    return outcomes


def format_proposals(proposals: Sequence[ExperienceNotePullRequest]) -> str:
    if not proposals:
        return "No saved experience notes are eligible for PR review."
    return "\n\n---\n\n".join(
        f"Proposal {index}/{len(proposals)}\n"
        f"Title: {proposal.title}\n"
        f"Body:\n{proposal.body}"
        for index, proposal in enumerate(proposals, start=1)
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preferences-file", required=True, type=Path)
    parser.add_argument("saved_note_paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    try:
        proposals = build_pull_request_proposals(args.preferences_file, args.saved_note_paths)
    except (NoteSaveError, OSError, UnicodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(format_proposals(proposals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
