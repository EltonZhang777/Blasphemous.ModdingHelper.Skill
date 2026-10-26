import csv
import io
import json
import re
import runpy
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
MAIN_SKILL = SKILL_ROOT / "SKILL.md"
KNOWLEDGE_REFERENCE = SKILL_ROOT / "references" / "modding-knowledge.md"
KNOWLEDGE_ROOT = REPOSITORY_ROOT / "docs" / "modding-knowledge"
INDEX_MARKDOWN = KNOWLEDGE_ROOT / "INDEX.md"
INDEX_JSON = KNOWLEDGE_ROOT / "index.json"
CHECKER = REPOSITORY_ROOT / "ci" / "generate_modding_knowledge_index.py"
LOCALIZATION_INDEX = SKILL_ROOT / "references" / "localization" / "blasphemous1_zh-en-es.tsv"
NOTE_PATH = "docs/modding-knowledge/fervour-language-variant.md"
NOTE_FILE = REPOSITORY_ROOT / NOTE_PATH
NOTE_TITLE = "The Fervour tutorial label has language variants"
NOTE_KEY = "PROPS/MSG_FERVOR_TUTORIAL_0"


class ModdingKnowledgeAcceptanceTests(unittest.TestCase):
    def run_index_check(self):
        return subprocess.run(
            [sys.executable, str(CHECKER), "--check"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_generated_indexes_expose_the_verified_note(self):
        result = self.run_index_check()
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

        entries = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
        self.assertEqual(
            entries,
            [
                {
                    "title": NOTE_TITLE,
                    "status": "verified",
                    "date": "2026-10-26",
                    "path": NOTE_PATH,
                }
            ],
        )
        self.assertIn(NOTE_TITLE, INDEX_MARKDOWN.read_text(encoding="utf-8"))
        self.assertTrue(NOTE_FILE.is_file())

    def test_check_reports_stale_output_without_rewriting_it(self):
        for path, name in ((INDEX_MARKDOWN, "INDEX.md"), (INDEX_JSON, "index.json")):
            with self.subTest(output=name):
                original = path.read_bytes()
                stale = b"stale\n"
                try:
                    path.write_bytes(stale)
                    result = self.run_index_check()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(f"{name} is stale", result.stderr + result.stdout)
                    self.assertEqual(path.read_bytes(), stale)
                finally:
                    path.write_bytes(original)

    def test_generator_rejects_collection_titles(self):
        original_note = NOTE_FILE.read_bytes()
        for invalid_title in ("[Draft]", "{Draft}"):
            with self.subTest(title=invalid_title):
                NOTE_FILE.write_bytes(
                    original_note.replace(
                        f"title: {NOTE_TITLE}".encode(),
                        f"title: {invalid_title}".encode(),
                        1,
                    )
                )
                try:
                    result = self.run_index_check()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("invalid frontmatter", result.stderr)
                finally:
                    NOTE_FILE.write_bytes(original_note)

    def test_generator_refuses_symlinked_index_outputs(self):
        for linked_name in ("INDEX.md", "index.json"):
            with self.subTest(output=linked_name), tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
                root = Path(directory)
                knowledge = root / "docs" / "modding-knowledge"
                knowledge.mkdir(parents=True)
                (knowledge / NOTE_FILE.name).write_bytes(NOTE_FILE.read_bytes())
                linked_output = knowledge / linked_name
                linked_output.write_bytes(b"keep linked output\n")
                other_name = "index.json" if linked_name == "INDEX.md" else "INDEX.md"
                other_output = knowledge / other_name
                other_output.write_bytes(b"keep the other output\n")
                generator = runpy.run_path(str(CHECKER))
                namespace = generator["main"].__globals__
                namespace["REPOSITORY_ROOT"] = root
                namespace["KNOWLEDGE_ROOT"] = knowledge
                path_type = type(linked_output)
                real_is_symlink = path_type.is_symlink
                with mock.patch.object(
                    path_type,
                    "is_symlink",
                    lambda path: path == linked_output or real_is_symlink(path),
                ):
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        result = generator["main"]([])

                self.assertNotEqual(result, 0)
                self.assertEqual(linked_output.read_bytes(), b"keep linked output\n")
                self.assertEqual(other_output.read_bytes(), b"keep the other output\n")

    def test_non_verified_canonical_notes_stay_out_of_indexes(self):
        original_note = NOTE_FILE.read_bytes()
        original_markdown = INDEX_MARKDOWN.read_bytes()
        original_json = INDEX_JSON.read_bytes()
        candidate_note = original_note.replace(b"status: verified", b"status: candidate", 1)
        try:
            NOTE_FILE.write_bytes(candidate_note)
            result = subprocess.run(
                [sys.executable, str(CHECKER)],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertEqual(json.loads(INDEX_JSON.read_text(encoding="utf-8")), [])
            self.assertNotIn(NOTE_TITLE, INDEX_MARKDOWN.read_text(encoding="utf-8"))
        finally:
            NOTE_FILE.write_bytes(original_note)
            INDEX_MARKDOWN.write_bytes(original_markdown)
            INDEX_JSON.write_bytes(original_json)

    def test_note_contract_has_only_the_three_metadata_fields(self):
        lines = NOTE_FILE.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "---")
        end = lines.index("---", 1)
        fields = [line.partition(":")[0] for line in lines[1:end]]
        self.assertEqual(fields, ["title", "status", "date"])

        body = "\n".join(lines[end + 1 :])
        for heading in (
            "## Applicable Blasphemous 1 version",
            "## Route",
            "## Evidence",
            "## Verification result",
            "## Limitations",
        ):
            self.assertIn(heading, body)

    def test_canonical_note_claim_matches_bundled_localization_row(self):
        with LOCALIZATION_INDEX.open(encoding="utf-8", newline="") as stream:
            row = next(
                item
                for item in csv.DictReader(stream, delimiter="\t")
                if item["key"] == NOTE_KEY
            )
        self.assertIn("Fervour", row["en"])
        self.assertIn("Fervor", row["es"])
        note = NOTE_FILE.read_text(encoding="utf-8")
        self.assertIn(NOTE_KEY, note)
        self.assertIn("Localization evidence", note)
        self.assertIn(row["en"], note)
        self.assertIn(row["es"], note)
        for target in re.findall(r"\]\(([^)]+)\)", note):
            if not target.startswith(("http://", "https://", "mailto:")):
                self.assertTrue((NOTE_FILE.parent / target).resolve().is_file(), target)

    def test_skill_routes_b1_tasks_to_the_same_commit_single_note_lookup(self):
        main = MAIN_SKILL.read_text(encoding="utf-8")
        reference = KNOWLEDGE_REFERENCE.read_text(encoding="utf-8").casefold()
        lookup = reference.split("## read-only lookup", 1)[1].split("## completion", 1)[0]
        failure = reference.split("if commit resolution", 1)[1].split("## completion", 1)[0]
        markers = list(re.finditer(r"(?m)^(\d+)\. ", lookup))
        steps = {
            marker.group(1): lookup[marker.end() : markers[index + 1].start() if index + 1 < len(markers) else len(lookup)]
            for index, marker in enumerate(markers)
        }

        self.assertIn("references/modding-knowledge.md", main)
        self.assertIn("task start", main.casefold())
        self.assertIn("matching blocker", main.casefold())
        self.assertEqual(list(steps), ["1", "2", "3", "4", "5"])
        self.assertIn("api.github.com/repos/eltonzhang777/blasphemous.moddinghelper.skill/commits/main", steps["1"])
        self.assertIn("current `main` exactly once", steps["1"])
        self.assertIn("must not resolve `main` again", steps["1"])
        self.assertIn("docs/modding-knowledge/index.json", steps["2"])
        self.assertIn("<sha>/docs/modding-knowledge/index.json", steps["2"])
        self.assertIn("at most one clearly matching entry", steps["3"])
        self.assertIn("must not fetch a note", steps["3"])
        self.assertIn("same raw url with the same sha", steps["4"])
        self.assertIn("must not read other note bodies", steps["4"])
        self.assertIn("full commit sha and repository-relative note path", steps["5"])
        self.assertIn("blasphemous 2", reference)
        self.assertIn("advisory", reference)
        self.assertIn("must not fall back to local, cached, or previously fetched note content", failure)
        self.assertIn("dependent work must pause", failure)
        self.assertIn("sufficient independent evidence", failure)


if __name__ == "__main__":
    unittest.main()
