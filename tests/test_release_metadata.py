import json
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERSION_SOURCE = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "version.yml"
ROUTED_REFERENCES = {
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
    def test_public_manifests_and_dependency_inventory_match_sources(self):
        self.assertTrue(VERSION_SOURCE.is_file())
        self.assertFalse(
            (REPOSITORY_ROOT / "ci" / "update-version" / "version.yml").exists()
        )
        requirements = (
            REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "requirements.txt"
        ).read_text(encoding="utf-8")
        preflight = (
            REPOSITORY_ROOT
            / "skills"
            / "blasphemous-modding-helper"
            / "references"
            / "config"
            / "invocation-preflight.md"
        ).read_text(encoding="utf-8")
        dependencies_match = re.search(
            r"(?ms)^## Dependencies\s*\n(.*?)(?=^## |\Z)", preflight
        )
        self.assertIsNotNone(dependencies_match)
        dependencies = dependencies_match.group(1)
        dependency_rows = [
            [cell.strip() for cell in line.strip("|").split("|")]
            for line in dependencies.splitlines()
            if line.startswith("| ")
            and not line.startswith(("| Dependency |", "| --- |"))
        ]
        self.assertEqual(
            {row[0] for row in dependency_rows},
            {"`PyYAML>=6.0`", "`ilspycmd`", "BepInEx", "ModdingAPI", "Git"},
        )
        expected_columns = {
            "`PyYAML>=6.0`": 4,
            "`ilspycmd`": 3,
            "BepInEx": 3,
            "ModdingAPI": 3,
            "Git": 3,
        }
        for row in dependency_rows:
            self.assertEqual(len(row), expected_columns[row[0]], row[0])
            self.assertTrue(all(row[1:]), row[0])
        self.assertNotRegex(dependencies, r"(?m)^\| \x60?(?:Python|Steam|\.NET)\x60?(?:\s|\|)")
        self.assertRegex(requirements, r"(?m)^\s*PyYAML\s*>=\s*6\.0\s*(?:#.*)?$")
        declared_packages = re.findall(r"(?m)^\s*([A-Za-z][A-Za-z0-9_.-]*)", requirements)
        self.assertEqual([name.casefold() for name in declared_packages], ["pyyaml"])
        self.assertIn("`PyYAML>=6.0`", dependencies)
        version_text = VERSION_SOURCE.read_text(encoding="utf-8")
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
                if manifest_path.name == "package.json":
                    self.assertEqual(manifest["engines"]["node"], ">=18")
                    self.assertIn("Node.js `>=18`", dependencies)
                    self.assertIn("installation-time requirement", dependencies.casefold())
                if manifest_path.name == "skills-lock.json":
                    self.assertEqual(manifest["skills"]["blasphemous-modding-helper"]["version"], expected)
                    for entry in manifest["references"].values():
                        self.assertEqual(entry["version"], expected)

    def test_release_matrix_validates_runtime_before_acceptance(self):
        workflow = (
            REPOSITORY_ROOT / ".github" / "workflows" / "build.yml"
        ).read_text(encoding="utf-8")
        preflight = workflow.index("check_python_environment.py")
        acceptance = workflow.index("test_modding_api_acceptance.py")
        self.assertLess(preflight, acceptance)
        self.assertIn(
            "skills/blasphemous-modding-helper/requirements.txt",
            workflow[preflight:acceptance],
        )
        self.assertIn(
            "zip -r publish/${{ env.PROJECT_NAME }}.zip skills/${{ env.PROJECT_NAME }}",
            workflow,
        )

    def test_lock_and_readme_cover_routed_reference_branches(self):
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

        self.assertEqual(set(lock["references"]), set(ROUTED_REFERENCES))
        self.assertIn(
            "Only the top-level `blasphemous-modding-helper` skill is activated.",
            readme,
        )
        self.assertIn(
            "users do not need to invoke these references directly.",
            readme,
        )
        self.assertIn(
            "localization",
            marketplace["plugins"][0]["description"].casefold(),
        )
        for key, (label, path) in ROUTED_REFERENCES.items():
            with self.subTest(reference=key):
                entry = lock["references"][key]
                self.assertEqual(entry["path"], path)
                self.assertTrue((REPOSITORY_ROOT / path).is_file())
                self.assertIn(label, readme)


if __name__ == "__main__":
    unittest.main()
