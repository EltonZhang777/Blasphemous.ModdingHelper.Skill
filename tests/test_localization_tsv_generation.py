import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
    / "generate_localization_tsv.py"
)

LANGUAGE_FILES = (
    ("Chinese_zh_base.txt", "zh"),
    ("English_en_base.txt", "en"),
    ("Spanish_es_base.txt", "es"),
    ("French_fr_base.txt", "fr"),
    ("German_de_base.txt", "de"),
    ("Italian_it_base.txt", "it"),
    ("Japanese_ja_base.txt", "ja"),
    ("Korean_ko_base.txt", "ko"),
    ("Portuguese (Brazil)_pt-BR_base.txt", "pt-BR"),
    ("Russian_ru_base.txt", "ru"),
)


class LocalizationTsvGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_dir = self.root / "localization source"
        self.input_dir.mkdir()
        self.core_output = self.root / "core.tsv"
        self.all_output = self.root / "all.tsv"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_sources(self, rows=None):
        rows = rows or {
            "UI/TERM_A": {
                "zh": "@@[ICON:A]中文 {0}",
                "en": "@@[ICON:A]English {0}",
                "es": "@@[ICON:A]Español {0}",
                "fr": "Français",
                "de": "Deutsch",
                "it": "Italiano",
                "ja": "日本語",
                "ko": "한국어",
                "pt-BR": "Português",
                "ru": "Русский",
            },
            "UI/TERM_B": {
                "zh": "第二项",
                "en": "Second term",
                "es": "Segundo término",
                "fr": "Deuxième terme",
                "de": "Zweiter Begriff",
                "it": "Secondo termine",
                "ja": "2番目の用語",
                "ko": "두 번째 용어",
                "pt-BR": "Segundo termo",
                "ru": "Второй термин",
            },
        }
        for filename, language in LANGUAGE_FILES:
            lines = [
                f"{key} -> Replace : {values[language]}"
                for key, values in rows.items()
            ]
            (self.input_dir / filename).write_text(
                "\n".join(lines) + "\n",
                encoding="utf-8",
            )

    def run_generator(self):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--input-dir",
                str(self.input_dir),
                "--core-output",
                str(self.core_output),
                "--all-output",
                str(self.all_output),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def read_tsv(self, path):
        with path.open("r", encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream, delimiter="\t"))

    def test_generates_aligned_core_and_all_language_indexes(self):
        self.write_sources()

        result = self.run_generator()

        self.assertEqual(result.returncode, 0, result.stderr)
        core_rows = self.read_tsv(self.core_output)
        all_rows = self.read_tsv(self.all_output)
        self.assertEqual(
            list(core_rows[0]),
            ["key", "zh", "en", "es"],
        )
        self.assertEqual(
            list(all_rows[0]),
            ["key", "zh", "en", "es", "fr", "de", "it", "ja", "ko", "pt-BR", "ru"],
        )
        self.assertEqual([row["key"] for row in core_rows], ["UI/TERM_A", "UI/TERM_B"])
        self.assertEqual(core_rows[0]["zh"], "@@[ICON:A]中文 {0}")
        self.assertEqual(core_rows[0]["en"], "@@[ICON:A]English {0}")
        self.assertEqual(core_rows[0]["es"], "@@[ICON:A]Español {0}")
        self.assertEqual(all_rows[1]["ru"], "Второй термин")

    def test_rejects_malformed_record(self):
        self.write_sources()
        source = self.input_dir / "English_en_base.txt"
        source.write_text("UI/TERM_A malformed\n", encoding="utf-8")

        result = self.run_generator()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed", result.stderr.lower())
        self.assertFalse(self.core_output.exists())
        self.assertFalse(self.all_output.exists())

    def test_rejects_duplicate_key(self):
        self.write_sources()
        source = self.input_dir / "English_en_base.txt"
        with source.open("a", encoding="utf-8") as stream:
            stream.write("UI/TERM_A -> Replace : duplicate\n")

        result = self.run_generator()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate", result.stderr.lower())

    def test_rejects_key_set_mismatch(self):
        self.write_sources()
        source = self.input_dir / "Spanish_es_base.txt"
        source.write_text("UI/TERM_A -> Replace : only one\n", encoding="utf-8")

        result = self.run_generator()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("key set mismatch", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
