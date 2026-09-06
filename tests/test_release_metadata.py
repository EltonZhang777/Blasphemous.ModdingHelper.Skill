import json
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_REFERENCES = {
    "blasphemous-modding-helper:source-analyzer": (
        "Source Analyzer",
        "skills/blasphemous-modding-helper/references/sub-skills/source-analyzer.md",
    ),
    "blasphemous-modding-helper:log-analyzer": (
        "Log Analyzer",
        "skills/blasphemous-modding-helper/references/sub-skills/log-analyzer.md",
    ),
    "blasphemous-modding-helper:blasphemous-modding-test": (
        "Mod Test",
        "skills/blasphemous-modding-helper/references/sub-skills/blasphemous-modding-test.md",
    ),
    "blasphemous-modding-helper:localization-lookup": (
        "Localization Lookup",
        "skills/blasphemous-modding-helper/references/sub-skills/localization-lookup.md",
    ),
}


class ReleaseMetadataTests(unittest.TestCase):
    def test_public_manifests_share_the_version_source(self):
        version_text = (
            REPOSITORY_ROOT / "ci" / "update-version" / "version.yml"
        ).read_text(encoding="utf-8")
        version = re.search(r"^version:\s*([^\s#]+)\s*$", version_text, re.MULTILINE)
        self.assertIsNotNone(version)
        expected = version.group(1)

        manifests = (
            REPOSITORY_ROOT / ".claude-plugin" / "plugin.json",
            REPOSITORY_ROOT / "gemini-extension.json",
            REPOSITORY_ROOT / "package.json",
            REPOSITORY_ROOT / "skills-lock.json",
        )
        for manifest_path in manifests:
            with self.subTest(manifest=manifest_path.name):
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["version"], expected)
                if manifest_path.name == "skills-lock.json":
                    self.assertEqual(manifest["skills"]["blasphemous-modding-helper"]["version"], expected)
                    for entry in manifest["references"].values():
                        self.assertEqual(entry["version"], expected)

    def test_lock_and_readme_cover_public_reference_branches(self):
        lock = json.loads(
            (REPOSITORY_ROOT / "skills-lock.json").read_text(encoding="utf-8")
        )
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        marketplace = json.loads(
            (
                REPOSITORY_ROOT
                / ".claude-plugin"
                / "marketplace.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(set(lock["references"]), set(PUBLIC_REFERENCES))
        self.assertIn(
            "localization",
            marketplace["plugins"][0]["description"].casefold(),
        )
        for key, (label, path) in PUBLIC_REFERENCES.items():
            with self.subTest(reference=key):
                entry = lock["references"][key]
                self.assertEqual(entry["path"], path)
                self.assertTrue((REPOSITORY_ROOT / path).is_file())
                self.assertIn(label, readme)


if __name__ == "__main__":
    unittest.main()
