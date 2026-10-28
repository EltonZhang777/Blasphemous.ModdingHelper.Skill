import contextlib
import base64
import io
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "ci"))

import generate_modding_knowledge_index as indexer
import modding_knowledge_candidates as candidates


REQUIRED_SECTIONS = (
    "Applicable Blasphemous 1 version",
    "Applicable Mod version",
    "Route",
    "Evidence",
    "Verification result",
    "Evidence history",
    "Limitations",
)


def note(title="Synthetic candidate", status="candidate", body_suffix=""):
    sections = "\n\n".join(
        f"## {heading}\n\n"
        + (
            "Version: Blasphemous 1 1.0.0 (synthetic build)."
            if heading == "Applicable Blasphemous 1 version"
            else "Version: SyntheticMod 1.0.0."
            if heading == "Applicable Mod version"
            else "Static source inspection: synthetic source location."
            if heading == "Evidence"
            else "- 2026-10-26: Initial verification; synthetic evidence recorded."
            if heading == "Evidence history"
            else "Synthetic evidence-backed text."
        )
        for heading in REQUIRED_SECTIONS
    )
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

    def test_promotion_write_failure_restores_indexes_and_removes_created_notes(self):
        candidate = self.write_candidate("atomic.md", note("Atomic candidate"))
        existing = self.knowledge / "existing.md"
        existing.write_text(note("Existing note", "verified"), encoding="utf-8")
        self.write_current_indexes()
        original_note = existing.read_bytes()
        original_indexes = {
            name: (self.knowledge / name).read_bytes()
            for name in indexer.render_indexes(indexer.build_entries(self.root))
        }
        code, output, errors = self.run_command(["review", str(candidate)])
        self.assertEqual((code, errors), (0, ""))
        review_sha256 = output.split("Review SHA-256: ", 1)[1].splitlines()[0]
        atomic_write = candidates._atomic_write
        writes = 0

        def fail_second_index_write(path, content):
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError("simulated mid-batch index write failure")
            atomic_write(path, content)

        with patch.object(candidates, "_atomic_write", side_effect=fail_second_index_write):
            code, _output, errors = self.run_command(
                ["promote", "--approve", "--review-sha256", review_sha256, str(candidate)]
            )

        self.assertNotEqual(code, 0)
        self.assertIn("simulated mid-batch index write failure", errors)
        self.assertFalse((self.knowledge / candidate.name).exists())
        self.assertEqual(existing.read_bytes(), original_note)
        for name, content in original_indexes.items():
            self.assertEqual((self.knowledge / name).read_bytes(), content)
        self.assertEqual(list(self.knowledge.glob(".knowledge-promotion-*")), [])

    def test_metadata_status_and_authoritative_sections_are_required(self):
        invalid_notes = (
            note().replace("title: Synthetic candidate\n", "", 1),
            note().replace("status: candidate", "status: draft", 1),
            note().replace("date: 2026-10-26", "date: 2026-02-30", 1),
            note().replace("Version: Blasphemous 1 1.0.0", "No version identified", 1),
            note().replace("Version: Blasphemous 1 1.0.0", "Version: TBD", 1),
            note().replace("Version: Blasphemous 1 1.0.0", "Version: Blasphemous 2 1.0.0", 1),
            note().replace("Version: SyntheticMod 1.0.0", "Version: TODO", 1),
            note().replace("## Route\n\nSynthetic evidence-backed text.", "## Route\n\n", 1),
            note().replace("## Evidence history\n\n- 2026-10-26: Initial verification; synthetic evidence recorded.", "## Evidence history\n\nNo dated record.", 1),
            note().replace("- 2026-10-26: Initial verification", "- 2026-10-27: Future verification", 1),
            note().replace("Static source inspection:", "Unlabeled source:", 1),
            note().replace("Static source inspection: synthetic source location.", "Static source inspection:", 1),
            note().replace(
                "Static source inspection: synthetic source location.",
                "Static source inspection: synthetic source location.\nAn unlabelled additional claim.",
                1,
            ),
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

    def test_screenshot_size_is_strict_and_images_must_be_relative(self):
        screenshot_root = self.knowledge / "screenshots" / "synthetic"
        screenshot_root.mkdir(parents=True)
        screenshot = screenshot_root / "gameplay.png"
        linked_note = "\n\n![Gameplay](../screenshots/synthetic/gameplay.png)"

        valid_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
        )
        screenshot.write_bytes(valid_png)
        path = self.write_candidate("small-image.md", note("Small image", body_suffix=linked_note))
        code, output, errors = self.run_command(["preflight", str(path)])
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("Screenshot:", output)
        self.assertIn("minimal cropping", output)

        screenshot.write_bytes(b"x" * candidates.MAX_SCREENSHOT_BYTES)
        code, _output, errors = self.run_command(["preflight", str(path)])
        self.assertNotEqual(code, 0)
        self.assertIn("strictly below 1.5 MiB", errors)

        screenshot.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 32)
        code, _output, errors = self.run_command(["preflight", str(path)])
        self.assertNotEqual(code, 0)
        self.assertIn("complete, valid image", errors)

        path.write_text(note("Remote image", body_suffix="\n\n![Gameplay](https://example.com/gameplay.png)"), encoding="utf-8")
        code, _output, errors = self.run_command(["preflight", str(path)])
        self.assertNotEqual(code, 0)
        self.assertIn("relative local path", errors)

        path.write_text(
            note("Reference image", body_suffix="\n\n![Gameplay]\n\n[Gameplay]: https://example.com/gameplay.png"),
            encoding="utf-8",
        )
        code, _output, errors = self.run_command(["preflight", str(path)])
        self.assertNotEqual(code, 0)
        self.assertIn("relative Markdown image links", errors)

    def test_supported_screenshot_formats_are_decoded_and_match_their_extensions(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is optional outside screenshot candidate validation")

        def make_image(image_format):
            buffer = io.BytesIO()
            Image.new("RGB", (2, 2), "red").save(buffer, format=image_format)
            return buffer.getvalue()

        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
        )
        fixtures = {
            ".png": png,
            ".jpg": make_image("JPEG"),
            ".jpeg": make_image("JPEG"),
            ".webp": make_image("WEBP"),
        }
        screenshot_root = self.knowledge / "screenshots" / "synthetic"
        screenshot_root.mkdir(parents=True)
        for index, (suffix, payload) in enumerate(fixtures.items()):
            with self.subTest(suffix=suffix):
                filename = f"capture{suffix}"
                (screenshot_root / filename).write_bytes(payload)
                path = self.write_candidate(
                    f"format-{index}.md",
                    note(body_suffix=f"\n\n![Gameplay](../screenshots/synthetic/{filename})"),
                )
                code, _output, errors = self.run_command(["preflight", str(path)])
                self.assertEqual((code, errors), (0, ""))

        (screenshot_root / "mismatch.jpg").write_bytes(png)
        path = self.write_candidate(
            "mismatch.md",
            note(body_suffix="\n\n![Gameplay](../screenshots/synthetic/mismatch.jpg)"),
        )
        code, _output, errors = self.run_command(["preflight", str(path)])
        self.assertNotEqual(code, 0)
        self.assertIn("do not match the image extension", errors)

    def test_screenshot_review_fingerprint_covers_image_and_promotion_keeps_relative_link(self):
        screenshot_root = self.knowledge / "screenshots" / "synthetic"
        screenshot_root.mkdir(parents=True)
        screenshot = screenshot_root / "gameplay.png"
        original_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
        )
        changed_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYPgPAAEDAQAIicLsAAAAAElFTkSuQmCC"
        )
        screenshot.write_bytes(original_png)
        content = note("Screenshot note", body_suffix="\n\n![Gameplay](../screenshots/synthetic/gameplay.png)")
        content = content.replace(
            "- 2026-10-26: Initial verification; synthetic evidence recorded.",
            "- 2026-10-25: Initial verification; synthetic evidence recorded.\n"
            "- 2026-10-26: Correction verified against the screenshot; earlier evidence retained.",
        )
        path = self.write_candidate(
            "screenshot-note.md",
            content,
        )
        self.write_current_indexes()

        code, output, errors = self.run_command(["review", str(path)])
        self.assertEqual((code, errors), (0, ""))
        review_sha256 = output.split("Review SHA-256: ", 1)[1].splitlines()[0]
        self.assertIn("canonical link: screenshots/synthetic/gameplay.png", output)

        screenshot.write_bytes(changed_png)
        code, _output, errors = self.run_command(
            ["promote", "--approve", "--review-sha256", review_sha256, str(path)]
        )
        self.assertNotEqual(code, 0)
        self.assertIn("review the exact batch again", errors)
        self.assertFalse((self.knowledge / path.name).exists())

        code, output, errors = self.run_command(["review", str(path)])
        self.assertEqual((code, errors), (0, ""))
        review_sha256 = output.split("Review SHA-256: ", 1)[1].splitlines()[0]
        code, _output, errors = self.run_command(
            ["promote", "--approve", "--review-sha256", review_sha256, str(path)]
        )
        self.assertEqual((code, errors), (0, ""))
        canonical = (self.knowledge / path.name).read_text(encoding="utf-8")
        self.assertIn("![Gameplay](screenshots/synthetic/gameplay.png)", canonical)
        self.assertIn("- 2026-10-25: Initial verification", canonical)
        self.assertIn("- 2026-10-26: Correction verified", canonical)
        self.assertTrue(screenshot.is_file())

    def test_reparse_points_are_treated_as_junctions(self):
        metadata = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        with patch.object(Path, "lstat", return_value=metadata):
            self.assertTrue(indexer._is_link_or_junction(Path("synthetic-junction")))

    def test_index_generation_and_promotion_reject_junctioned_knowledge_root(self):
        candidate = self.write_candidate()
        self.write_current_indexes()
        original_indexes = {
            name: (self.knowledge / name).read_bytes()
            for name in indexer.render_indexes(indexer.build_entries(self.root))
        }

        with patch.object(indexer, "_is_link_or_junction", side_effect=lambda path: path == self.knowledge):
            with self.assertRaises(indexer.NoteError):
                indexer.build_entries(self.root)
            code, _output, errors = self.run_command(["promote", "--approve", str(candidate)])

        self.assertNotEqual(code, 0)
        self.assertIn("symlinked directories", errors)
        self.assertFalse((self.knowledge / candidate.name).exists())
        for name, content in original_indexes.items():
            self.assertEqual((self.knowledge / name).read_bytes(), content)

    def test_index_generation_and_promotion_reject_junctioned_outputs(self):
        candidate = self.write_candidate()
        self.write_current_indexes()
        original_indexes = {
            name: (self.knowledge / name).read_bytes()
            for name in indexer.render_indexes(indexer.build_entries(self.root))
        }
        output_paths = {self.knowledge / name for name in original_indexes}

        with patch.object(indexer, "REPOSITORY_ROOT", self.root), patch.object(indexer, "KNOWLEDGE_ROOT", self.knowledge):
            with patch.object(indexer, "_is_link_or_junction", side_effect=lambda path: path in output_paths):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertNotEqual(indexer.main([]), 0)
                code, _output, errors = self.run_command(["promote", "--approve", str(candidate)])

        self.assertNotEqual(code, 0)
        self.assertIn("stale", errors)
        self.assertFalse((self.knowledge / candidate.name).exists())
        for name, content in original_indexes.items():
            self.assertEqual((self.knowledge / name).read_bytes(), content)

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

    def test_raw_artifacts_credentials_private_paths_and_logs_are_rejected(self):
        raw_log = self.candidate_root / "player.log"
        raw_log.write_text("synthetic log", encoding="utf-8")
        code, _output, errors = self.run_command(["preflight", str(raw_log)])
        self.assertNotEqual(code, 0)
        self.assertIn("Markdown notes", errors)

        for index, target in enumerate((
            "evidence/Player.log",
            "evidence/Assembly-CSharp.dll",
            "evidence/dump.cs",
            "evidence/capture.iso",
            "evidence/game.rom",
            "evidence/sprite.png",
            "evidence/decompiled/dump.txt",
            "evidence/player.txt",
            "ftp://example.com/Player.log",
        )):
            path = self.write_candidate(
                f"linked-{index}.md",
                note(body_suffix=f"\n\n[artifact]({target})"),
            )
            code, _output, errors = self.run_command(["preflight", str(path)])
            self.assertNotEqual(code, 0)
            self.assertIn("raw logs, game files", errors)

        for index, private_path in enumerate((
            r"C:\Users\alice\profile\config.yml",
            "C:/Users/alice/profile/config.yml",
        )):
            path = self.write_candidate(
                f"private-path-{index}.md",
                note(body_suffix=f"\n\nPrivate path: {private_path}"),
            )
            code, _output, errors = self.run_command(["preflight", str(path)])
            self.assertNotEqual(code, 0)
            self.assertIn("private or user-specific paths", errors)

        secret = self.write_candidate(
            "secret.md",
            note(body_suffix="\n\nAPI key: abcdefghijklmnop123456"),
        )
        code, _output, errors = self.run_command(["preflight", str(secret)])
        self.assertNotEqual(code, 0)
        self.assertIn("credential-like content", errors)

        log_lines = (
            "2026-10-26 10:00:00.001 [Info] first",
            "2026-10-26 10:00:00.002 [Warning] second",
            "2026-10-26 10:00:00.003 [Error] third",
        )
        log_samples = (
            "\n\n" + log_lines[0],
            "\n\n" + "\n".join(log_lines[:2]),
            "\n\n" + "\n".join(log_lines),
            "\n\n" + "\n".join(f"> {line}" for line in log_lines),
            "\n\n" + "\n".join(f"- {line}" for line in log_lines),
            "\n\n[Info : ExampleMod] startup complete",
        )
        for index, raw_logs in enumerate(log_samples):
            log_note = self.write_candidate(f"raw-logs-{index}.md", note(body_suffix=raw_logs))
            code, _output, errors = self.run_command(["preflight", str(log_note)])
            self.assertNotEqual(code, 0)
            self.assertIn("raw log excerpts", errors)

        manual_note = self.write_candidate(
            "manual-observation.md",
            note(body_suffix="\n\n2026-10-26 10:00:00 [Manual] observed the route in game"),
        )
        code, errors_output, errors = self.run_command(["preflight", str(manual_note)])
        self.assertEqual((code, errors), (0, ""), errors_output)


if __name__ == "__main__":
    unittest.main()
