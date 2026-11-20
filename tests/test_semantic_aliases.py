import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ALIASES = (
    REPOSITORY_ROOT
    / "skills"
    / "blasphemous-modding-helper"
    / "references"
    / "localization"
    / "semantic-aliases.md"
)
GLOSSARY = REPOSITORY_ROOT / "GLOSSARY.md"
CANONICAL_EVIDENCE_TERM = "Player-performed in-game verification"
LEGACY_EVIDENCE_TERM = "Manual verification"

REQUIRED_FIELDS = {
    "concept_id",
    "alias",
    "language",
    "alias_type",
    "positive_context",
    "negative_context",
    "evidence_keys",
    "confidence",
    "note",
}
ALIAS_TYPES = {"community_slang", "translation_variant", "code_identifier"}
CONFIDENCES = {"high", "medium", "low"}


class SemanticAliasDocumentTests(unittest.TestCase):
    def test_alias_records_have_the_review_contract(self):
        text = ALIASES.read_text(encoding="utf-8")
        records = re.split(r"^## (?=ALIAS-)", text, flags=re.MULTILINE)[1:]

        self.assertTrue(records)
        for record in records:
            fields = dict(
                re.findall(r"^- `([^`]+)`: ?(.*)$", record, flags=re.MULTILINE)
            )
            self.assertEqual(REQUIRED_FIELDS, set(fields))
            self.assertIn(fields["alias_type"].strip("`"), ALIAS_TYPES)
            self.assertIn(fields["confidence"].strip("`"), CONFIDENCES)
            self.assertTrue(fields["evidence_keys"] or "human confirmation" in fields["note"].casefold())

    def test_alias_document_declares_context_and_review_rules(self):
        text = ALIASES.read_text(encoding="utf-8").casefold()

        self.assertIn("one alias may map to multiple candidates", text)
        self.assertIn("light normalization", text)
        self.assertIn("user confirmation", text)
        self.assertIn("not an encyclopedia", text)


class EvidenceTerminologyTests(unittest.TestCase):
    def test_glossary_keeps_the_canonical_term_with_one_bounded_alias(self):
        glossary = GLOSSARY.read_text(encoding="utf-8")
        self.assertIn(f"**{CANONICAL_EVIDENCE_TERM}**:", glossary)
        self.assertEqual(
            re.findall(LEGACY_EVIDENCE_TERM, glossary, flags=re.IGNORECASE),
            [LEGACY_EVIDENCE_TERM],
        )


if __name__ == "__main__":
    unittest.main()
