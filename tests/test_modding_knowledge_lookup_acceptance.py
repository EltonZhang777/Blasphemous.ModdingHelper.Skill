import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

from modding_knowledge_lookup import main  # noqa: E402


SHA = "a" * 40
INDEX_PATH = "docs/modding-knowledge/index.json"
NOTE_PATH = "docs/modding-knowledge/fervour-language-variant.md"
ENTRY = {
    "title": "The Fervour tutorial label has language variants",
    "status": "verified",
    "date": "2026-10-10",
    "path": NOTE_PATH,
}
CONTENT = "\n".join(
    (
        "---",
        f"title: {ENTRY['title']}",
        "status: verified",
        f"date: {ENTRY['date']}",
        "---",
        "## Finding",
        "The displayed label varies by language.",
    )
)


class ModdingKnowledgeLookupAcceptanceTests(unittest.TestCase):
    def run_cli(self, arguments, fetch):
        output = io.StringIO()
        errors = io.StringIO()
        with patch("modding_knowledge_lookup._http_get_text", side_effect=fetch):
            with redirect_stdout(output), redirect_stderr(errors):
                result = main(arguments)
        return result, output.getvalue(), errors.getvalue()

    def test_resolves_one_commit_and_reads_only_its_index_and_selected_note(self):
        base = "https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/"
        responses = {
            "https://api.github.com/repos/EltonZhang777/Blasphemous.ModdingHelper.Skill/commits/main": json.dumps({"sha": SHA}),
            f"{base}{SHA}/{INDEX_PATH}": json.dumps([ENTRY]),
            f"{base}{SHA}/{NOTE_PATH}": CONTENT,
        }
        calls = []

        def fetch(url):
            calls.append(url)
            return responses[url]

        status, output, errors = self.run_cli(["resolve"], fetch)
        self.assertEqual(status, 0, errors)
        index = json.loads(output)
        entry = index["entries"][0]
        status, output, errors = self.run_cli(
            [
                "note",
                "--commit-sha", index["commit_sha"],
                "--path", entry["path"],
                "--title", entry["title"],
                "--date", entry["date"],
            ],
            fetch,
        )
        self.assertEqual(status, 0, errors)
        note = json.loads(output)

        self.assertEqual(calls, list(responses))
        self.assertEqual(index["commit_sha"], SHA)
        self.assertEqual(note["commit_sha"], SHA)
        self.assertEqual(note["path"], NOTE_PATH)
        self.assertEqual(note["content"], CONTENT)

    def test_resolution_exposes_only_verified_canonical_index_entries(self):
        url = "https://api.github.com/repos/EltonZhang777/Blasphemous.ModdingHelper.Skill/commits/main"
        index_url = f"https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/{SHA}/{INDEX_PATH}"
        unverified = dict(ENTRY, status="candidate", path="docs/modding-knowledge/candidates/draft.md")
        calls = []

        def fetch(requested):
            calls.append(requested)
            return json.dumps({"sha": SHA}) if requested == url else json.dumps([ENTRY, unverified])

        status, output, errors = self.run_cli(["resolve"], fetch)

        self.assertEqual(status, 0, errors)
        result = json.loads(output)
        self.assertEqual(calls, [url, index_url])
        self.assertEqual(result["entries"], [ENTRY])

    def test_failed_index_retrieval_discloses_phase_and_does_not_try_a_note(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if url.endswith("/commits/main"):
                return json.dumps({"sha": SHA})
            raise OSError("offline")

        status, _, errors = self.run_cli(["resolve"], fetch)
        self.assertEqual(status, 1)
        self.assertIn("failed during index", errors)
        self.assertEqual(len(calls), 2)

    def test_failed_or_mismatched_note_is_not_replaced_with_other_content(self):
        calls = []

        def fail(url):
            calls.append(url)
            raise OSError("offline")

        status, _, errors = self.run_cli(
            ["note", "--commit-sha", SHA, "--path", NOTE_PATH, "--title", ENTRY["title"], "--date", ENTRY["date"]],
            fail,
        )
        self.assertEqual(status, 1)
        self.assertIn("failed during note", errors)
        self.assertEqual(calls, [f"https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/{SHA}/{NOTE_PATH}"])

        mismatched = CONTENT.replace("date: 2026-10-10", "date: 2026-10-11")
        status, _, errors = self.run_cli(
            ["note", "--commit-sha", SHA, "--path", NOTE_PATH, "--title", ENTRY["title"], "--date", ENTRY["date"]],
            lambda _: mismatched,
        )
        self.assertEqual(status, 1)
        self.assertIn("does not match", errors)

    def test_cli_discloses_the_failed_lookup_phase(self):
        def offline(_):
            raise OSError("offline")

        status, _, errors = self.run_cli(["resolve"], offline)
        self.assertEqual(status, 1)
        self.assertIn("failed during commit", errors)

    def test_invalid_or_nested_note_paths_are_rejected_before_fetch(self):
        calls = []
        for path in ("../private.md", "docs/modding-knowledge/nested/note.md"):
            with self.subTest(path=path):
                status, _, errors = self.run_cli(
                    ["note", "--commit-sha", SHA, "--path", path, "--title", ENTRY["title"], "--date", ENTRY["date"]],
                    lambda url: calls.append(url),
                )
                self.assertEqual(status, 1)
                self.assertIn("failed during note", errors)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
