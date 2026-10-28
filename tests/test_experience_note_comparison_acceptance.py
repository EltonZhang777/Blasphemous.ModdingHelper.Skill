import json
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
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


if __name__ == "__main__":
    unittest.main()
