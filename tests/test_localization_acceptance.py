import csv
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
LOCALIZATION_ROOT = SKILL_ROOT / "references" / "localization"
CORE_INDEX = LOCALIZATION_ROOT / "blasphemous1_zh-en-es.tsv"
ALL_INDEX = LOCALIZATION_ROOT / "blasphemous1_all.tsv"
GENERATOR = SKILL_ROOT / "scripts" / "generate_localization_tsv.py"
TEMP_SOURCE = REPOSITORY_ROOT / ".temp" / "localization source"

CORE_HEADER = ["key", "zh", "en", "es"]
ALL_HEADER = ["key", "zh", "en", "es", "fr", "de", "it", "ja", "ko", "pt-BR", "ru"]
SOURCE_NAMES = {
    "Chinese_zh_base.txt",
    "English_en_base.txt",
    "French_fr_base.txt",
    "German_de_base.txt",
    "Italian_it_base.txt",
    "Japanese_ja_base.txt",
    "Korean_ko_base.txt",
    "Portuguese (Brazil)_pt-BR_base.txt",
    "Russian_ru_base.txt",
    "Spanish_es_base.txt",
}


class LocalizationAcceptanceTests(unittest.TestCase):
    def read_table(self, path):
        with path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.reader(stream, delimiter="\t"))
        self.assertEqual(len(rows), 1880)
        return rows[0], rows[1:]

    def test_indexes_are_aligned_wide_utf8_tables(self):
        core_header, core_rows = self.read_table(CORE_INDEX)
        all_header, all_rows = self.read_table(ALL_INDEX)

        self.assertEqual(core_header, CORE_HEADER)
        self.assertEqual(all_header, ALL_HEADER)
        core_keys = [row[0] for row in core_rows]
        all_keys = [row[0] for row in all_rows]
        self.assertEqual(len(set(core_keys)), 1879)
        self.assertEqual(core_keys, all_keys)
        self.assertTrue(all(len(row) == len(ALL_HEADER) for row in all_rows))

    def test_indexes_preserve_localization_tokens(self):
        _, core_rows = self.read_table(CORE_INDEX)
        values = {row[0]: row for row in core_rows}

        fervour = values["PROPS/MSG_FERVOR_TUTORIAL_0"]
        guilt = values["Tutorial/TUT9_TEXT"]
        self.assertIn("@", guilt[1])
        self.assertIn("[ICONTEARS]", guilt[1])
        self.assertIn("Fervour", guilt[2])
        self.assertIn("Fervor", guilt[3])
        self.assertIn("[ACTFlask]", values["Tutorial/TUT10_TEXT"][1])
        self.assertIn("Fervour", fervour[2])

    def test_final_package_contains_no_inputs_or_temporary_generator(self):
        package_names = {path.name for path in SKILL_ROOT.rglob("*") if path.is_file()}

        self.assertFalse(GENERATOR.exists())
        self.assertFalse((REPOSITORY_ROOT / "tests" / "test_localization_tsv_generation.py").exists())
        self.assertFalse(TEMP_SOURCE.exists())
        self.assertTrue(SOURCE_NAMES.isdisjoint(package_names))

    def test_external_seam_documentation_covers_route_and_closed_fallbacks(self):
        main = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").casefold()
        lookup = (
            SKILL_ROOT / "references" / "sub-skills" / "localization-lookup.md"
        ).read_text(encoding="utf-8").casefold()

        self.assertIn("localization-lookup.md", main)
        for phrase in (
            "natural-language",
            "semantic-aliases.md",
            "source-analyzer.md",
            "localization evidence",
            "gameplay evidence",
            "closed failure",
            "unverified guess",
        ):
            self.assertIn(phrase, lookup)


if __name__ == "__main__":
    unittest.main()
