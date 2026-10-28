import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))
sys.path.insert(0, str(SCRIPTS_ROOT.parent))

from experience_note_pull_requests import (  # noqa: E402
    build_pull_request_proposals,
    create_approved_pull_requests,
    format_proposals,
)
from save_experience_note import NoteSaveError, save_approved_note  # noqa: E402


MAIN_SKILL = SKILL_ROOT / "SKILL.md"
COMPARISON = SKILL_ROOT / "references" / "sub-skills" / "experience-note-comparison.md"
LOCAL_SAVE = SKILL_ROOT / "references" / "sub-skills" / "experience-note-local-save.md"
PULL_REQUESTS = SKILL_ROOT / "references" / "sub-skills" / "experience-note-pull-requests.md"
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "experience-note-comparison"


def split_note(raw):
    lines = raw.splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError("fixture note is missing YAML frontmatter")
    end = lines.index("---", 1)
    fields = [line.partition(":")[0] for line in lines[1:end]]
    return fields, "\n".join(lines[end + 1 :])


class ExperienceNoteComparisonAcceptanceTests(unittest.TestCase):
    def test_b1_skill_routes_evidence_backed_reusable_findings_to_comparison(self):
        skill = MAIN_SKILL.read_text(encoding="utf-8")
        self.assertIn("references/sub-skills/experience-note-comparison.md", skill)
        self.assertIn("evidence-backed", skill)
        self.assertIn("independent child task", skill)
        self.assertIn("continue the main task without waiting", skill)

    def test_comparison_handoff_is_read_only_and_covers_all_outcomes(self):
        reference = COMPARISON.read_text(encoding="utf-8").casefold()
        for phrase in (
            "child task",
            "continue the main task",
            "local note corpus",
            "public canonical notes",
            "exact duplicate",
            "uncertain",
            "comparison failure",
            "stale",
            "conflict",
            "version context",
            "supporting evidence",
            "must not prompt the user",
            "save a note",
            "create a pull request",
            "must not edit",
            "blasphemous 2",
        ):
            self.assertIn(phrase, reference)

        self.assertRegex(reference, r"(?is)resolve.{0,120}main.{0,120}exactly once")
        self.assertRegex(reference, r"(?is)same (?:full )?sha")
        self.assertIn("completion criteria", reference)
        self.assertRegex(reference, r"next (?:action|step)")

    def test_differently_titled_possible_public_match_is_deferred(self):
        candidate = (FIXTURE_ROOT / "candidate.md").read_text(encoding="utf-8")
        candidate_title = next(
            line.partition(": ")[2] for line in candidate.splitlines() if line.startswith("title: ")
        )
        possible_entry = json.loads(
            (FIXTURE_ROOT / "public" / "differently-titled-possible-match-index.json").read_text(encoding="utf-8")
        )[0]
        reference = COMPARISON.read_text(encoding="utf-8").casefold()
        local_save = LOCAL_SAVE.read_text(encoding="utf-8").casefold()
        pull_requests = PULL_REQUESTS.read_text(encoding="utf-8").casefold()

        self.assertNotEqual(possible_entry["title"], candidate_title)
        self.assertEqual(possible_entry["status"], "verified")
        self.assertIn("review every verified index entry", reference)
        self.assertIn("a title mismatch must not establish that an entry is distinct", reference)
        self.assertIn("could describe the same reusable finding under another title", reference)
        self.assertIn("must return `deferred`", reference)
        self.assertIn("must not fetch that ambiguous note", reference)
        self.assertIn("must not infer `unique` solely because no public title clearly matches", reference)
        self.assertIn("must not pass the candidate to local-save or pr approval", reference)
        self.assertIn("deferred candidates", local_save)
        self.assertIn("must not be offered for saving", local_save)
        self.assertIn("deferred findings", pull_requests)
        self.assertIn("must not scan for or submit", pull_requests)
        self.assertIn("at most one clearly matching", reference)
        self.assertIn("or use cached or previously fetched content", reference)
        self.assertIn("must not use fallback content", reference)

    def test_controlled_corpora_follow_the_canonical_note_contract(self):
        candidate = (FIXTURE_ROOT / "candidate.md").read_text(encoding="utf-8")
        local = (FIXTURE_ROOT / "local" / "duplicate.md").read_text(encoding="utf-8")
        public_index = json.loads((FIXTURE_ROOT / "public" / "index.json").read_text(encoding="utf-8"))
        public_note = (FIXTURE_ROOT / "public" / "fervour-language-variant.md").read_text(encoding="utf-8")

        candidate_fields, candidate_body = split_note(candidate)
        local_fields, local_body = split_note(local)
        public_fields, public_body = split_note(public_note)
        self.assertEqual(candidate_fields, ["title", "status", "date"])
        self.assertEqual(local_fields, ["title", "status", "date"])
        self.assertEqual(public_fields, ["title", "status", "date"])
        self.assertEqual(candidate_body, local_body)
        self.assertEqual(candidate_body, public_body)
        self.assertEqual(public_index[0]["status"], "verified")
        self.assertEqual(public_index[0]["path"], "docs/modding-knowledge/fervour-language-variant.md")

        for body in (candidate_body, local_body, public_body):
            for heading in (
                "## Applicable Blasphemous 1 version",
                "## Route",
                "## Evidence",
                "## Verification result",
                "## Limitations",
            ):
                self.assertIn(heading, body)

    def test_reported_non_unique_outcomes_block_save_and_pr_side_effects(self):
        candidate = (FIXTURE_ROOT / "candidate.md").read_text(encoding="utf-8")
        local_duplicate = (FIXTURE_ROOT / "local" / "duplicate.md").read_text(encoding="utf-8")
        public_index = json.loads((FIXTURE_ROOT / "public" / "index.json").read_text(encoding="utf-8"))
        public_note = (FIXTURE_ROOT / "public" / "fervour-language-variant.md").read_text(encoding="utf-8")
        possible_match = json.loads(
            (FIXTURE_ROOT / "public" / "differently-titled-possible-match-index.json").read_text(encoding="utf-8")
        )[0]
        stale_note = (FIXTURE_ROOT / "local" / "stale.md").read_text(encoding="utf-8")
        conflicting_note = (FIXTURE_ROOT / "local" / "conflicting.md").read_text(encoding="utf-8")
        malformed_note = (FIXTURE_ROOT / "local" / "malformed.md").read_text(encoding="utf-8")
        candidate_title = next(
            line.partition(": ")[2]
            for line in candidate.splitlines()
            if line.startswith("title: ")
        )
        self.assertEqual(split_note(candidate)[1], split_note(local_duplicate)[1])
        self.assertEqual(split_note(candidate)[1], split_note(public_note)[1])
        self.assertNotEqual(possible_match["title"], candidate_title)
        self.assertEqual(public_index[0]["status"], "verified")
        self.assertEqual(split_note(stale_note)[0], ["title", "status", "date"])
        self.assertIn("status: superseded", stale_note)
        self.assertNotEqual(split_note(conflicting_note)[1], split_note(candidate)[1])
        self.assertEqual(split_note(malformed_note)[0], ["title", "status"])

        corpus_files = tuple(path for path in FIXTURE_ROOT.rglob("*") if path.is_file())
        before = {path: path.read_bytes() for path in corpus_files}
        # The comparison is an agent task; exercise its reported outcomes at the write boundaries.
        outcomes = (
            ("exact-duplicate", "exact-duplicate"),
            ("uncertain-match", "deferred"),
            ("incomplete-corpus", "deferred"),
            ("retrieval-failure", "deferred"),
            ("stale-note", "stale"),
            ("conflicting-note", "conflict"),
        )
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temporary:
            config = Path(temporary) / "config.yml"
            config.write_text("lightweight_source_code_path: ./source\n", encoding="utf-8")
            writes = []
            for scenario, outcome in outcomes:
                with self.subTest(scenario=scenario), self.assertRaises(NoteSaveError):
                    save_approved_note(
                        config.resolve(),
                        scenario,
                        outcome,
                        "yes",
                        "controlled candidate content",
                        storage=lambda path, content: writes.append((path, content)),
                    )

            proposals = build_pull_request_proposals(config.resolve(), [])
            created = []
            self.assertEqual(format_proposals(proposals), "No saved experience notes are eligible for PR review.")
            self.assertEqual(create_approved_pull_requests(proposals, {}, created.append), [])
            self.assertEqual(writes, [])
            self.assertEqual(created, [])
            self.assertFalse((config.parent / "modding-knowledge").exists())

        self.assertEqual(before, {path: path.read_bytes() for path in corpus_files})


if __name__ == "__main__":
    unittest.main()
