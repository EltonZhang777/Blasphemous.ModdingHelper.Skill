import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "ci"))

import generate_modding_knowledge_index as indexer
import modding_knowledge_candidates as candidates


REQUIRED_SECTIONS = (
    "Applicable Blasphemous 1 version",
    "Route",
    "Evidence",
    "Verification result",
    "Limitations",
)


def note(title="Synthetic candidate", status="candidate", body_suffix=""):
    sections = "\n\n".join(f"## {heading}\n\nSynthetic evidence-backed text." for heading in REQUIRED_SECTIONS)
    return (
        f"---\ntitle: {title}\nstatus: {status}\ndate: 2026-10-26\n---\n\n"
        f"# {title}\n\n{sections}{body_suffix}\n"
    )


class ModdingKnowledgeCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT)
        self.root = Path(self.temporary.name)
        self.knowledge = self.root / "docs" / "modding-knowledge"
        self.candidate_root = self.knowledge / "candidates"
        self.candidate_root.mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def write_candidate(self, name="synthetic-candidate.md", content=None):
        path = self.candidate_root / name
        path.write_text(content if content is not None else note(), encoding="utf-8")
        return path

    def write_current_indexes(self):
        for name, content in indexer.render_indexes(indexer.build_entries(self.root)).items():
            (self.knowledge / name).write_text(content, encoding="utf-8")

    def run_command(self, argv):
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = candidates.main(argv, repository_root=self.root)
        return code, output.getvalue(), errors.getvalue()

    def test_preflight_and_review_keep_candidates_out_of_indexes_and_preserve_redactions(self):
        path = self.write_candidate(content=note(body_suffix="\n\nPrivacy review: [REDACTED]."))

        code, output, errors = self.run_command(["preflight", str(path)])
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("Preflight passed", output)
        self.assertIn("no content is redacted automatically", output)
        self.assertEqual(indexer.build_entries(self.root), [])

        code, output, errors = self.run_command(["review", str(path)])
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("Privacy review: [REDACTED].", output)
        self.assertIn("INDEX.md", output)
        self.assertIn("index.json", output)
        self.assertEqual(indexer.build_entries(self.root), [])
        self.assertFalse((self.knowledge / "INDEX.md").exists())

    def test_review_scope_contains_only_named_batch_and_its_proposed_indexes(self):
        first = self.write_candidate("first.md", note("First candidate"))
        second = self.write_candidate("second.md", note("Second candidate"))

        code, output, errors = self.run_command(["review", str(first)])

        self.assertEqual((code, errors), (0, ""))
        self.assertIn("First candidate", output)
        self.assertNotIn("Second candidate", output)
        self.assertNotIn("second.md", output)
        self.assertTrue(second.exists())

    def test_promotion_requires_explicit_approval_and_makes_only_approved_note_retrievable(self):
        approved = self.write_candidate("approved.md", note("Approved note"))
        unapproved = self.write_candidate("unapproved.md", note("Unapproved note"))

        code, _output, errors = self.run_command(["promote", str(approved)])
        self.assertNotEqual(code, 0)
        self.assertIn("explicit human approval", errors)
        self.assertTrue(approved.exists())
        self.assertFalse((self.knowledge / "approved.md").exists())
        self.assertEqual(indexer.build_entries(self.root), [])

        self.write_current_indexes()
        code, _output, errors = self.run_command(["promote", "--approve", str(approved)])
        self.assertNotEqual(code, 0)
        self.assertIn("review the exact batch again", errors)

        code, output, errors = self.run_command(["review", str(approved)])
        self.assertEqual((code, errors), (0, ""))
        review_sha256 = output.split("Review SHA-256: ", 1)[1].splitlines()[0]

        code, output, errors = self.run_command(
            ["promote", "--approve", "--review-sha256", review_sha256, str(approved)]
        )
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("Promoted to verified canonical note", output)
        canonical = self.knowledge / "approved.md"
        self.assertIn("status: verified", canonical.read_text(encoding="utf-8"))
        self.assertIn("status: candidate", approved.read_text(encoding="utf-8"))
        self.assertTrue(unapproved.exists())

        entries = indexer.build_entries(self.root)
        self.assertEqual([entry["title"] for entry in entries], ["Approved note"])
        self.assertEqual(entries[0]["status"], "verified")
        self.assertEqual(entries[0]["path"], "docs/modding-knowledge/approved.md")
        self.assertEqual(json.loads((self.knowledge / "index.json").read_text(encoding="utf-8")), entries)
        rendered = indexer.render_indexes(entries)
        for name, content in rendered.items():
            self.assertEqual((self.knowledge / name).read_text(encoding="utf-8"), content)

    def test_promotion_rejects_candidate_changes_after_review(self):
        path = self.write_candidate(content=note("Reviewed note"))
        self.write_current_indexes()

        code, output, errors = self.run_command(["review", str(path)])
        self.assertEqual((code, errors), (0, ""))
        review_sha256 = output.split("Review SHA-256: ", 1)[1].splitlines()[0]
        path.write_text(note("Changed after review"), encoding="utf-8")

        code, _output, errors = self.run_command(
            ["promote", "--approve", "--review-sha256", review_sha256, str(path)]
        )

        self.assertNotEqual(code, 0)
        self.assertIn("review the exact batch again", errors)
        self.assertTrue(path.exists())
        self.assertFalse((self.knowledge / path.name).exists())
        self.assertEqual(indexer.build_entries(self.root), [])

    def test_promotion_rejects_index_changes_after_review(self):
        candidate = self.write_candidate(content=note("Reviewed note"))
        self.write_current_indexes()
        code, output, errors = self.run_command(["review", str(candidate)])
        self.assertEqual((code, errors), (0, ""))
        review_sha256 = output.split("Review SHA-256: ", 1)[1].splitlines()[0]

        (self.knowledge / "another-note.md").write_text(note("Another verified note", "verified"), encoding="utf-8")
        self.write_current_indexes()
        code, _output, errors = self.run_command(
            ["promote", "--approve", "--review-sha256", review_sha256, str(candidate)]
        )

        self.assertNotEqual(code, 0)
        self.assertIn("review the exact batch again", errors)
        self.assertFalse((self.knowledge / candidate.name).exists())
        self.assertEqual([entry["title"] for entry in indexer.build_entries(self.root)], ["Another verified note"])

    def test_batch_preflight_is_all_or_nothing_before_any_promotion(self):
        valid = self.write_candidate("valid.md", note("Valid candidate"))
        invalid = self.write_candidate(
            "invalid.md",
            note("Invalid candidate", body_suffix="\n\nPrivate path: C:\\Users\\alice\\profile\\config.yml"),
        )

        code, _output, errors = self.run_command(["promote", "--approve", str(valid), str(invalid)])

        self.assertNotEqual(code, 0)
        self.assertIn("private or user-specific paths", errors)
        self.assertFalse((self.knowledge / "valid.md").exists())
        self.assertFalse((self.knowledge / "invalid.md").exists())
        self.assertEqual(indexer.build_entries(self.root), [])

    def test_metadata_status_and_authoritative_sections_are_required(self):
        invalid_notes = (
            note().replace("title: Synthetic candidate\n", "", 1),
            note().replace("status: candidate", "status: draft", 1),
            note().replace("date: 2026-10-26", "date: 2026-02-30", 1),
            note().replace("## Route\n\nSynthetic evidence-backed text.", "## Route\n\n", 1),
            note().replace("title: Synthetic candidate\n", "title: Synthetic candidate\n\n", 1),
            note().replace("title: Synthetic candidate", "title: &anchor Synthetic candidate", 1),
            note(body_suffix="\n\n```text\nunclosed"),
            "---\ntitle: Fenced headings\nstatus: candidate\ndate: 2026-10-26\n---\n\n"
            "```markdown\n" + "\n".join(f"## {heading}\nEvidence" for heading in REQUIRED_SECTIONS) + "\n```\n",
        )
        for index, content in enumerate(invalid_notes):
            with self.subTest(index=index):
                path = self.write_candidate(f"invalid-{index}.md", content)
                code, _output, errors = self.run_command(["preflight", str(path)])
                self.assertNotEqual(code, 0)
                self.assertTrue(errors.startswith("knowledge candidate error:"))

    def test_code_block_and_note_size_thresholds(self):
        sixty_one = "\n```text\n" + "\n".join("line" for _ in range(61)) + "\n```"
        path = self.write_candidate(content=note(body_suffix=sixty_one))
        code, output, errors = self.run_command(["preflight", str(path)])
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("code block", output)
        self.assertIn(">60", output)

        one_hundred_fifty_one = "\n```text\n" + "\n".join("line" for _ in range(151)) + "\n```"
        path.write_text(note(body_suffix=one_hundred_fifty_one), encoding="utf-8")
        code, _output, errors = self.run_command(["preflight", str(path)])
        self.assertNotEqual(code, 0)
        self.assertIn("maximum is 150", errors)

        large = self.write_candidate("large.md", note(body_suffix="\n\n" + ("x" * (120 * 1024))))
        code, output, errors = self.run_command(["preflight", str(large)])
        self.assertEqual((code, errors), (0, ""))
        self.assertIn(">120 KiB", output)

    def test_raw_artifacts_credentials_and_private_paths_are_rejected(self):
        raw_log = self.candidate_root / "player.log"
        raw_log.write_text("synthetic log", encoding="utf-8")
        code, _output, errors = self.run_command(["preflight", str(raw_log)])
        self.assertNotEqual(code, 0)
        self.assertIn("Markdown notes", errors)

        for index, suffix in enumerate(("Player.log", "Assembly-CSharp.dll", "dump.cs", "capture.iso", "game.rom", "sprite.png", "decompiled/dump.txt")):
            path = self.write_candidate(f"linked-{index}.md", note(body_suffix=f"\n\n[artifact](evidence/{suffix})"))
            code, _output, errors = self.run_command(["preflight", str(path)])
            self.assertNotEqual(code, 0)
            self.assertIn("raw logs, game files", errors)

        secret = self.write_candidate(
            "secret.md",
            note(body_suffix="\n\nAPI key: abcdefghijklmnop123456"),
        )
        code, _output, errors = self.run_command(["preflight", str(secret)])
        self.assertNotEqual(code, 0)
        self.assertIn("credential-like content", errors)

        raw_logs = "\n\n2026-10-26 10:00:00.001 [Info] first\n2026-10-26 10:00:00.002 [Warning] second\n2026-10-26 10:00:00.003 [Error] third"
        log_note = self.write_candidate("raw-logs.md", note(body_suffix=raw_logs))
        code, _output, errors = self.run_command(["preflight", str(log_note)])
        self.assertNotEqual(code, 0)
        self.assertIn("raw log excerpts", errors)


if __name__ == "__main__":
    unittest.main()
