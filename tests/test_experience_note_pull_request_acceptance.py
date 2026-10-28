import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
CI_ROOT = REPOSITORY_ROOT / "ci"
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "experience-note-comparison"
MAIN_SKILL = SKILL_ROOT / "SKILL.md"
PR_REFERENCE = SKILL_ROOT / "references" / "sub-skills" / "experience-note-pull-requests.md"
sys.path.insert(0, str(SCRIPTS_ROOT))
sys.path.insert(0, str(SCRIPTS_ROOT.parent))
sys.path.insert(0, str(CI_ROOT))

from blasphemous_modding_helper.preferences import load_preferences
from experience_note_pull_requests import (
    ExperienceNotePullRequest,
    build_pull_request_proposals,
    create_approved_pull_requests,
    format_proposals,
)
from generate_modding_knowledge_index import NoteError, parse_note
from modding_knowledge_candidates import preflight_candidates
from save_experience_note import NoteSaveError, save_approved_note


NOTE = """---
title: Reusable finding about {slug}
status: candidate
date: 2026-10-26
---

## Finding
The verified behavior for {slug}.

## Applicable Blasphemous 1 version
Version: Unknown.

## Applicable Mod version
Version: Not applicable.

## Route
The relevant Skill route and how to use this finding.

## Evidence
Static source inspection: an authoritative reference establishes the finding.

## Reproduction steps
1. Follow the documented setup.
2. Repeat the observation.

## Verification result
The stated method reproduced the result.

## Evidence history
- 2026-10-26: Initial verification from the authoritative reference.

## Limitations
The evidence does not establish behavior in other versions.
"""


class StubStorage:
    def __init__(self):
        self.writes = {}

    def write(self, path, content):
        with path.open("w", encoding="utf-8", newline="") as note_file:
            note_file.write(content)
        self.writes[path] = content


class StubPullRequestOperations:
    def __init__(self):
        self.created = []

    def create(self, proposal):
        result = f"https://example.invalid/pull/{len(self.created) + 1}"
        self.created.append(
            {
                "title": proposal.title,
                "body": proposal.body,
                "branch": proposal.branch,
                "path": proposal.candidate_path,
                "content": proposal.content,
                "url": result,
            }
        )
        return result


class ExperienceNotePullRequestAcceptanceTests(unittest.TestCase):
    def test_noncanonical_title_is_rejected_by_pr_preparation_and_promotion_parser(self):
        content = NOTE.format(slug="noncanonical-title").replace(
            "title: Reusable finding about noncanonical-title",
            "title: Finding: A detail",
        )
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temp:
            root = Path(temp)
            config_path = root / "config.yml"
            config_path.write_text("lightweight_source_code_path: ./source\n", encoding="utf-8")
            note_directory = root / "modding-knowledge"
            note_directory.mkdir()
            saved_note = note_directory / "noncanonical-title.md"
            saved_note.write_text(content, encoding="utf-8")

            with self.assertRaises(NoteSaveError):
                build_pull_request_proposals(config_path.resolve(), [saved_note.resolve()])

            candidate = root / "docs" / "modding-knowledge" / "candidates" / saved_note.name
            candidate.parent.mkdir(parents=True)
            candidate.write_text(content, encoding="utf-8")
            with self.assertRaises(NoteError):
                parse_note(candidate, root)

    def test_one_failed_pr_does_not_skip_other_explicit_yes_items(self):
        proposals = [
            ExperienceNotePullRequest("first", "title", "body", "branch", "path.md", "content"),
            ExperienceNotePullRequest("second", "title", "body", "branch", "path.md", "content"),
        ]
        calls = []

        def create(proposal):
            calls.append(proposal.slug)
            if proposal.slug == "first":
                raise RuntimeError("synthetic PR failure")
            return "created"

        outcomes = create_approved_pull_requests(
            proposals,
            {"first": "yes", "second": "yes"},
            create,
        )
        self.assertEqual(calls, ["first", "second"])
        self.assertIsInstance(outcomes[0][1], RuntimeError)
        self.assertEqual(outcomes[1][1], "created")

    def test_saved_note_batch_requires_separate_pr_yes_and_keeps_local_notes(self):
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temp:
            root = Path(temp)
            project = root / "project"
            user_home = root / "user-home"
            project_config = project / ".skills" / "blasphemous-modding-helper" / "config.yml"
            user_config = user_home / ".skills" / "blasphemous-modding-helper" / "config.yml"
            project_config.parent.mkdir(parents=True)
            user_config.parent.mkdir(parents=True)
            project_config.write_text("lightweight_source_code_path: ./source\n", encoding="utf-8")
            user_config.write_text("lightweight_source_code_path: ./other-source\n", encoding="utf-8")
            selected = load_preferences(cwd=project, home=user_home)
            self.assertEqual(selected.scope, "project")
            config_path = selected.path.resolve(strict=True)

            fixture_candidate = (FIXTURE_ROOT / "candidate.md").read_text(encoding="utf-8")
            fixture_local = (FIXTURE_ROOT / "local" / "duplicate.md").read_text(encoding="utf-8")
            fixture_public = (FIXTURE_ROOT / "public" / "fervour-language-variant.md").read_text(encoding="utf-8")
            public_index = json.loads((FIXTURE_ROOT / "public" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(fixture_candidate.split("---", 2)[2], fixture_local.split("---", 2)[2])
            self.assertEqual(fixture_candidate.split("---", 2)[2], fixture_public.split("---", 2)[2])
            self.assertEqual(public_index[0]["status"], "verified")

            storage = StubStorage()
            saved = {}
            for slug in ("approved-one", "declined-pr", "silent-pr"):
                content = NOTE.format(slug=slug)
                self.assertNotEqual(content.split("---", 2)[2], fixture_local.split("---", 2)[2])
                saved[slug] = save_approved_note(
                    config_path,
                    slug,
                    "unique",
                    "yes",
                    content,
                    storage=storage.write,
                )

            self.assertIsNone(
                save_approved_note(
                    config_path,
                    "declined-local",
                    "unique",
                    "no",
                    NOTE.format(slug="declined-local"),
                    storage=storage.write,
                )
            )
            self.assertFalse((config_path.parent / "modding-knowledge" / "declined-local.md").exists())
            self.assertEqual(set(storage.writes), set(saved.values()))

            proposals = build_pull_request_proposals(config_path, list(saved.values()))
            self.assertEqual([proposal.slug for proposal in proposals], list(saved))
            with self.assertRaises(NoteSaveError):
                build_pull_request_proposals(
                    config_path,
                    [user_config.parent / "modding-knowledge" / "approved-one.md"],
                )
            rendered = format_proposals(proposals)
            self.assertNotIn(str(config_path.parent), rendered)
            for proposal in proposals:
                self.assertIn(f"Title: {proposal.title}", rendered)
                self.assertIn(proposal.body, rendered)
                self.assertIn(proposal.content, proposal.body)

            public_repository = root / "public-repository"
            candidate_directory = public_repository / "docs" / "modding-knowledge" / "candidates"
            candidate_directory.mkdir(parents=True)
            candidate = candidate_directory / f"{proposals[0].slug}.md"
            with candidate.open("w", encoding="utf-8", newline="") as candidate_file:
                candidate_file.write(proposals[0].content)
            checked = preflight_candidates(public_repository, [candidate])
            self.assertEqual(checked[0]["text"], proposals[0].content)
            self.assertFalse((public_repository / "docs" / "modding-knowledge" / "index.json").exists())

            operations = StubPullRequestOperations()
            created = create_approved_pull_requests(
                proposals,
                {
                    "approved-one": " yes ",
                    "declined-pr": "no",
                    "silent-pr": None,
                },
                operations.create,
            )
            self.assertEqual(len(created), 1)
            self.assertEqual(len(operations.created), 1)
            self.assertEqual(operations.created[0]["title"], proposals[0].title)
            self.assertEqual(operations.created[0]["body"], proposals[0].body)
            self.assertEqual(operations.created[0]["path"], proposals[0].candidate_path)
            self.assertEqual(operations.created[0]["content"], proposals[0].content)
            self.assertTrue(saved["declined-pr"].is_file())
            self.assertTrue(saved["silent-pr"].is_file())
            self.assertTrue(saved["approved-one"].is_file())

    def test_skill_routes_saved_notes_to_separate_pr_approval(self):
        skill = MAIN_SKILL.read_text(encoding="utf-8")
        reference = PR_REFERENCE.read_text(encoding="utf-8").casefold()
        self.assertIn("experience-note-pull-requests.md", skill)
        for phrase in (
            "only paths returned",
            "current task",
            "exact full title",
            "exact full body",
            "separate yes/no",
            "unclear answer, or silence",
            "declined pr must leave its local note untouched",
            "default branch",
            "update canonical indexes",
            "must not merge",
        ):
            self.assertIn(phrase, reference)


if __name__ == "__main__":
    unittest.main()
