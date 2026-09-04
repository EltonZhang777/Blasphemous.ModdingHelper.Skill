import unittest
from pathlib import Path


SKILL_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
)
MAIN_SKILL = SKILL_ROOT / "SKILL.md"
LOOKUP_SKILL = SKILL_ROOT / "references" / "sub-skills" / "localization-lookup.md"
PREFLIGHT = SKILL_ROOT / "references" / "config" / "invocation-preflight.md"


class LocalizationLookupDocumentationTests(unittest.TestCase):
    def test_main_skill_routes_natural_language_term_requests(self):
        main = MAIN_SKILL.read_text(encoding="utf-8")

        self.assertIn("localization-lookup.md", main)
        self.assertIn("natural-language", main)
        self.assertIn("read-only localization", main)

    def test_lookup_branch_defines_default_text_search_and_evidence_boundary(self):
        lookup = LOOKUP_SKILL.read_text(encoding="utf-8").casefold()

        self.assertIn("blasphemous1_zh-en-es.tsv", lookup)
        self.assertIn("rg", lookup)
        self.assertIn("complete localization key", lookup)
        self.assertIn("localization evidence", lookup)
        self.assertIn("gameplay evidence", lookup)

    def test_lookup_branch_is_independent_of_preferences(self):
        lookup = LOOKUP_SKILL.read_text(encoding="utf-8").casefold()
        preflight = PREFLIGHT.read_text(encoding="utf-8").casefold()

        self.assertIn("does not require", lookup)
        self.assertIn("preferences.md", lookup)
        self.assertIn("localization lookup branch", preflight)
        self.assertIn("read-only", preflight)

    def test_lookup_documents_on_demand_all_language_selection(self):
        lookup = LOOKUP_SKILL.read_text(encoding="utf-8").casefold()

        self.assertIn("blasphemous1_all.tsv", lookup)
        self.assertIn("core index by default", lookup)
        self.assertIn("requested target language", lookup)
        self.assertIn("full comparison", lookup)
        self.assertIn("instruction language", lookup)

    def test_lookup_documents_controlled_source_analysis_fallback(self):
        lookup = LOOKUP_SKILL.read_text(encoding="utf-8").casefold()

        self.assertIn("source-analyzer.md", lookup)
        self.assertIn("code identifier", lookup)
        self.assertIn("gameplay evidence", lookup)
        self.assertIn("inference", lookup)
        self.assertIn("natural-language term", lookup)


if __name__ == "__main__":
    unittest.main()
