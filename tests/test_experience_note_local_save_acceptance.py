import sys
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
MAIN_SKILL = SKILL_ROOT / "SKILL.md"
COMPARISON = SKILL_ROOT / "references" / "sub-skills" / "experience-note-comparison.md"
LOCAL_SAVE = SKILL_ROOT / "references" / "sub-skills" / "experience-note-local-save.md"
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))
sys.path.insert(0, str(SCRIPTS_ROOT.parent))

from save_experience_note import NoteSaveError, _is_link_or_junction, _validate_note, save_approved_note
from blasphemous_modding_helper.preferences import load_preferences


NOTE = """---
title: A representative reusable finding
status: candidate
date: 2026-10-26
---

## Finding
The generalized finding.

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
        self.writes[path] = content


class ExperienceNoteLocalSaveAcceptanceTests(unittest.TestCase):
    def test_note_schema_matches_public_candidate_preflight(self):
        invalid_notes = (
            NOTE.replace("Version: Not applicable.", "Version: Pending."),
            NOTE.replace("Static source inspection:", "Source:"),
            NOTE.replace("- 2026-10-26:", "- 2026-10-27:"),
            NOTE.replace("Version: Unknown.", "Version: Blasphemous 2 v1."),
        )
        for content in invalid_notes:
            with self.subTest(content=content):
                with self.assertRaises(NoteSaveError):
                    _validate_note(content)

    def test_windows_reparse_points_are_rejected_as_junctions(self):
        metadata = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        with patch.object(Path, "lstat", return_value=metadata):
            self.assertTrue(_is_link_or_junction(Path("synthetic-junction")))

    def test_skill_and_comparison_route_unique_results_to_local_save(self):
        skill = MAIN_SKILL.read_text(encoding="utf-8")
        comparison = COMPARISON.read_text(encoding="utf-8").casefold()
        reference = LOCAL_SAVE.read_text(encoding="utf-8").casefold()

        self.assertIn("references/sub-skills/experience-note-local-save.md", skill)
        self.assertIn("`unique` candidate", comparison)
        self.assertIn("experience note local save", comparison)
        for phrase in (
            "every unique candidate together in one batch",
            "exact full markdown content",
            "its own explicit yes/no question",
            "unclear response, or silence",
            "status: candidate",
            "windows-reserved device name",
            "reproduction steps",
            "raw logs or configuration",
            "credentials",
            "personal or machine identifiers",
            "absolute paths",
            "selected by invocation preflight",
            "project and user configuration",
            "must not overwrite",
            "does not authorize a pull request",
        ):
            self.assertIn(phrase, reference)

    def test_only_explicit_yes_writes_to_resolved_project_config_with_stub_storage(self):
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
            storage = StubStorage()

            target = save_approved_note(
                config_path,
                "representative-finding",
                "unique",
                "yes",
                NOTE,
                storage=storage.write,
            )
            expected = config_path.parent / "modding-knowledge" / "representative-finding.md"
            self.assertEqual(target, expected)
            self.assertEqual(storage.writes, {expected: NOTE})
            self.assertTrue(expected.parent.is_dir())
            self.assertFalse((user_config.parent / "modding-knowledge").exists())

            for decision in ("no", "unclear", None, ""):
                with self.subTest(decision=decision):
                    result = save_approved_note(
                        config_path,
                        "declined-finding",
                        "unique",
                        decision,
                        NOTE,
                        storage=storage.write,
                    )
                    self.assertIsNone(result)
            self.assertEqual(list(storage.writes), [expected])

            for slug in ("con", "prn", "aux", "nul", "com1", "lpt9"):
                with self.subTest(slug=slug), self.assertRaises(NoteSaveError):
                    save_approved_note(
                        config_path,
                        slug,
                        "unique",
                        "yes",
                        NOTE,
                        storage=storage.write,
                    )
            self.assertEqual(list(storage.writes), [expected])

    def test_non_unique_or_existing_note_cannot_be_written(self):
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temp:
            config_path = Path(temp) / "config.yml"
            config_path.write_text("lightweight_source_code_path: ./source\n", encoding="utf-8")
            storage = StubStorage()

            with self.assertRaises(NoteSaveError):
                save_approved_note(config_path.resolve(), "finding", "deferred", "yes", NOTE, storage=storage.write)
            self.assertFalse(storage.writes)

            existing = config_path.parent / "modding-knowledge" / "existing.md"
            existing.parent.mkdir()
            existing.write_text("keep this note\n", encoding="utf-8")
            with self.assertRaises(NoteSaveError):
                save_approved_note(config_path.resolve(), "existing", "unique", "yes", NOTE, storage=storage.write)
            self.assertFalse(storage.writes)
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep this note\n")

    def test_default_storage_publishes_complete_notes_and_cleans_failed_writes(self):
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as temp:
            config_path = Path(temp) / "config.yml"
            config_path.write_text("lightweight_source_code_path: ./source\n", encoding="utf-8")
            note_directory = config_path.parent / "modding-knowledge"

            saved = save_approved_note(config_path.resolve(), "complete-note", "unique", "yes", NOTE)
            self.assertEqual(saved.read_text(encoding="utf-8"), NOTE)
            self.assertEqual(list(note_directory.iterdir()), [saved])

            with patch("save_experience_note.os.fdopen", side_effect=OSError("synthetic write failure")):
                with self.assertRaises(NoteSaveError):
                    save_approved_note(config_path.resolve(), "failed-note", "unique", "yes", NOTE)

            self.assertFalse((note_directory / "failed-note.md").exists())
            self.assertEqual(list(note_directory.iterdir()), [saved])


if __name__ == "__main__":
    unittest.main()
