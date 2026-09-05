import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validator import validate_candidate


SOURCE = r'''---
name: sample
description: Keep this metadata byte-for-byte.
---
# Compression target

Use `codex exec` with https://example.com/docs and [the guide](docs/guide.md).
The implementation lives in ci/compress-docs/compress_docs.py and uses BlasModAPI.
git status --short

    python tool.py --flag

```bash
python tool.py --flag
```

- First item
  - Nested item
- Second item

| Name | Value |
| --- | --- |
| mode | read-only |

The agent MUST preserve C:\game\mod.dll.
'''


class ValidatorTests(unittest.TestCase):
    def assert_invalid(self, source, candidate, message):
        result = validate_candidate(source.encode("utf-8"), candidate.encode("utf-8"))
        self.assertFalse(result.is_valid)
        self.assertTrue(any(message in error for error in result.errors), result.errors)

    def test_allows_prose_compression_and_preserves_frontmatter_bom_and_crlf(self):
        source = "\ufeff" + SOURCE.replace("\n", "\r\n")
        candidate = (
            "\ufeff"
            + r'''---
name: sample
description: Keep this metadata byte-for-byte.
---
# Compression target

Use `codex exec` with https://example.com/docs and [the guide](docs/guide.md).
Short prose. ci/compress-docs/compress_docs.py uses BlasModAPI.
git status --short

    python tool.py --flag

```bash
python tool.py --flag
```

- Short first
  - Short nested
- Short second

| Name | Value |
| --- | --- |
| mode | safe |

The agent MUST preserve C:\game\mod.dll.
'''.replace("\n", "\r\n")
        )
        result = validate_candidate(source.encode("utf-8"), candidate.encode("utf-8"))
        self.assertTrue(result.is_valid, result.errors)

    def test_rejects_frontmatter_change(self):
        candidate = SOURCE.replace("name: sample", "name: changed")
        self.assert_invalid(SOURCE, candidate, "frontmatter")

    def test_accepts_mixed_source_after_majority_newline_normalization(self):
        source = "# Heading\r\n\nUse `codex`.\r\n"
        candidate = "# Heading\r\n\r\nUse `codex`.\r\n"
        result = validate_candidate(source.encode("utf-8"), candidate.encode("utf-8"))
        self.assertTrue(result.is_valid, result.errors)
        self.assertTrue(any("mixed source newlines" in warning for warning in result.warnings))

    def test_rejects_fenced_code_change(self):
        candidate = SOURCE.replace("```bash\npython tool.py --flag", "```bash\npython other.py --flag")
        self.assert_invalid(SOURCE, candidate, "fenced code")

    def test_rejects_indented_code_change(self):
        candidate = SOURCE.replace("    python tool.py --flag", "    python other.py --flag")
        self.assert_invalid(SOURCE, candidate, "indented code")

    def test_rejects_inline_link_url_path_and_identifier_change(self):
        candidate = SOURCE.replace("`codex exec`", "`codex run`")
        self.assert_invalid(SOURCE, candidate, "inline code")
        candidate = SOURCE.replace("https://example.com/docs", "https://example.com/other")
        self.assert_invalid(SOURCE, candidate, "URL")
        candidate = SOURCE.replace("docs/guide.md", "docs/other.md")
        self.assert_invalid(SOURCE, candidate, "Markdown link")
        candidate = SOURCE.replace("ci/compress-docs/compress_docs.py", "ci/other.py")
        self.assert_invalid(SOURCE, candidate, "path")
        candidate = SOURCE.replace("git status --short", "git diff --short")
        self.assert_invalid(SOURCE, candidate, "command")
        candidate = SOURCE.replace("BlasModAPI", "OtherAPI")
        self.assert_invalid(SOURCE, candidate, "technical identifier")

    def test_rejects_reference_link_filename_and_hyphenated_identifier_change(self):
        source = "# Heading\n\n[reference]: docs/reference.md\nRead README.md.\nUse Assembly-CSharp.\n"
        candidate = source.replace("docs/reference.md", "docs/other.md")
        self.assert_invalid(source, candidate, "Markdown link")
        candidate = source.replace("README.md", "OTHER.md")
        self.assert_invalid(source, candidate, "path")
        candidate = source.replace("Assembly-CSharp", "Other-Assembly")
        self.assert_invalid(source, candidate, "technical identifier")

    def test_rejects_heading_or_list_shape_change(self):
        self.assert_invalid(SOURCE, SOURCE.replace("# Compression target", "# Changed"), "heading")
        self.assert_invalid(SOURCE, SOURCE.replace("  - Nested item", "- Nested item"), "list")

    def test_rejects_table_shape_change(self):
        candidate = SOURCE.replace("| Name | Value |", "| Name | Value | Extra |")
        self.assert_invalid(SOURCE, candidate, "table")

    def test_rejects_normative_unit_change(self):
        candidate = SOURCE.replace("The agent MUST preserve C:\\game\\mod.dll.", "The agent MAY preserve C:\\game\\mod.dll.")
        self.assert_invalid(SOURCE, candidate, "normative")

    def test_rejects_ambiguous_unclosed_protected_content(self):
        self.assert_invalid("# Heading\n\n```\nopen\n", "# Heading\n\n```\nopen\n", "unclosed fenced")
        self.assert_invalid("# Heading\n\nUnmatched `code\n", "# Heading\n\nUnmatched `code\n", "unmatched inline")


if __name__ == "__main__":
    unittest.main()
