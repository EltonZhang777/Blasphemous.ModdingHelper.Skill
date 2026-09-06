import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
AUDIT = SKILL_ROOT / "scripts" / "audit_rfc2119.py"
MODDING_API_STANDARDS = (
    SKILL_ROOT
    / "references"
    / "coding-standards"
    / "coding-standards-moddingAPI.md"
)
REFERENCING = (
    SKILL_ROOT / "references" / "sub-skills" / "referencing-modding-api.md"
)


class Rfc2119AuditTests(unittest.TestCase):
    def test_strict_audit_passes_for_packaged_skill_markdown(self):
        result = subprocess.run(
            [sys.executable, str(AUDIT), "--strict"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RFC 2119 candidate audit: PASS", result.stdout)

    def test_modding_api_guidance_uses_resolved_reference_urls(self):
        standards = MODDING_API_STANDARDS.read_text(encoding="utf-8")
        referencing = REFERENCING.read_text(encoding="utf-8")

        self.assertNotIn("ModdingAPI/blob/main/", standards)
        self.assertIn("MODDING_API_DOCS_URL", referencing)
        self.assertIn("MODDING_API_SOURCE_URL", referencing)
        self.assertIn("branch:main", referencing)


if __name__ == "__main__":
    unittest.main()
