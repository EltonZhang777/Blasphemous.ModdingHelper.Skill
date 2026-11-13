import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = REPOSITORY_ROOT / "docs" / "modding-knowledge"
SCRIPT_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "scripts"
INDEX_JSON = KNOWLEDGE_ROOT / "index.json"
NOTE_PATH = "docs/modding-knowledge/fervour-language-variant.md"
NOTE_FILE = REPOSITORY_ROOT / NOTE_PATH
sys.path.insert(0, str(SCRIPT_ROOT))

from modding_knowledge_lookup import main  # noqa: E402


SHA = "a" * 40
INDEX_PATH = "docs/modding-knowledge/index.json"
INDEX_ENTRIES = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
ENTRY = next(entry for entry in INDEX_ENTRIES if entry["path"] == NOTE_PATH)
CONTENT = NOTE_FILE.read_text(encoding="utf-8")
UNRELATED_ENTRY = {
    "title": "Unrelated verified finding",
    "status": "verified",
    "date": "2026-10-28",
    "path": "docs/modding-knowledge/unrelated.md",
}


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
            f"{base}{SHA}/{INDEX_PATH}": json.dumps(INDEX_ENTRIES + [UNRELATED_ENTRY]),
            f"{base}{SHA}/{NOTE_PATH}": CONTENT,
        }
        calls = []

        def fetch(url):
            calls.append(url)
            if url not in responses:
                raise AssertionError(f"unexpected note request: {url}")
            return responses[url]

        status, output, errors = self.run_cli(["resolve"], fetch)
        self.assertEqual(status, 0, errors)
        index = json.loads(output)
        self.assertEqual(index["entries"], INDEX_ENTRIES + [UNRELATED_ENTRY])
        entry = index["entries"][0]
        if entry["path"] != NOTE_PATH:
            entry = next(item for item in index["entries"] if item["path"] == NOTE_PATH)
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
        self.assertNotIn(f"{base}{SHA}/{UNRELATED_ENTRY['path']}", calls)

    def test_resolution_exposes_only_verified_canonical_index_entries(self):
        url = "https://api.github.com/repos/EltonZhang777/Blasphemous.ModdingHelper.Skill/commits/main"
        index_url = f"https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/{SHA}/{INDEX_PATH}"
        unverified = dict(ENTRY, status="candidate", path="docs/modding-knowledge/candidates/draft.md")
        calls = []

        def fetch(requested):
            calls.append(requested)
            return json.dumps({"sha": SHA}) if requested == url else json.dumps(INDEX_ENTRIES + [unverified])

        status, output, errors = self.run_cli(["resolve"], fetch)

        self.assertEqual(status, 0, errors)
        result = json.loads(output)
        self.assertEqual(calls, [url, index_url])
        self.assertEqual(result["entries"], INDEX_ENTRIES)

    def test_failed_index_retrieval_discloses_phase_and_does_not_try_a_note(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if url.endswith("/commits/main"):
                return json.dumps({"sha": SHA})
            raise IncompleteRead(b"partial index")

        status, _, errors = self.run_cli(["resolve"], fetch)
        self.assertEqual(status, 1)
        self.assertIn("failed during index", errors)
        self.assertEqual(len(calls), 2)

    def test_truncated_note_response_is_disclosed_without_fallback(self):
        calls = []

        def truncated(url):
            calls.append(url)
            raise IncompleteRead(b"partial note")

        status, _, errors = self.run_cli(
            ["note", "--commit-sha", SHA, "--path", NOTE_PATH, "--title", ENTRY["title"], "--date", ENTRY["date"]],
            truncated,
        )
        self.assertEqual(status, 1)
        self.assertIn("failed during note", errors)
        self.assertEqual(calls, [f"https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/{SHA}/{NOTE_PATH}"])

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

        mismatched = CONTENT.replace(f"date: {ENTRY['date']}", "date: 2026-10-27")
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
