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
    def test_dependency_inventory_matches_preflight_and_machine_readable_sources(self):
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
            {"`PyYAML>=6.0`", "`Pillow>=10.0`", "`ilspycmd`", "BepInEx", "ModdingAPI", "Git"},
        )
        expected_columns = {
            "`PyYAML>=6.0`": 4,
            "`Pillow>=10.0`": 3,
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

        package = json.loads((REPOSITORY_ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["engines"]["node"], ">=18")
        self.assertIn("Node.js `>=18`", dependencies)
        self.assertIn("installation-time requirement", dependencies.casefold())

    def test_public_integration_metadata_matches_skill_identity_and_version(self):
        self.assertTrue(VERSION_SOURCE.is_file())
        self.assertFalse(
            (REPOSITORY_ROOT / "ci" / "update-version" / "version.yml").exists()
        )
        requirements = (
            REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "requirements.txt"
        ).read_text(encoding="utf-8")
        self.assertRegex(requirements, r"(?m)^\s*PyYAML\s*>=\s*6\.0\s*(?:#.*)?$")
        version_text = VERSION_SOURCE.read_text(encoding="utf-8")
        version = re.search(r"^version:\s*([^\s#]+)\s*$", version_text, re.MULTILINE)
        self.assertIsNotNone(version)
        expected = version.group(1)

        manifests = (
            REPOSITORY_ROOT / ".claude-plugin" / "plugin.json",
            REPOSITORY_ROOT / ".codex-plugin" / "plugin.json",
            REPOSITORY_ROOT / "gemini-extension.json",
            REPOSITORY_ROOT / "package.json",
            REPOSITORY_ROOT / "skills-lock.json",
        )
        loaded_manifests = {}
        for manifest_path in manifests:
            with self.subTest(manifest=manifest_path.name):
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                loaded_manifests[manifest_path] = manifest
                self.assertEqual(manifest["version"], expected)
                if manifest_path.name == "skills-lock.json":
                    self.assertEqual(manifest["skills"]["blasphemous-modding-helper"]["version"], expected)
                    for entry in manifest["references"].values():
                        self.assertEqual(entry["version"], expected)

        codex = loaded_manifests[REPOSITORY_ROOT / ".codex-plugin" / "plugin.json"]
        claude = loaded_manifests[REPOSITORY_ROOT / ".claude-plugin" / "plugin.json"]
        marketplace = json.loads(
            (REPOSITORY_ROOT / ".claude-plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        codex_marketplace = json.loads(
            (
                REPOSITORY_ROOT
                / ".agents"
                / "plugins"
                / "marketplace.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(codex["name"], "blasphemous-modding-helper")
        self.assertEqual(codex["skills"], "./skills/")
        self.assertTrue((REPOSITORY_ROOT / "skills").is_dir())
        self.assertEqual(claude["name"], codex["name"])
        self.assertNotIn("minCliVersion", claude)
        self.assertNotIn("agents", claude)
        self.assertTrue(marketplace["description"])
        self.assertEqual(marketplace["plugins"][0]["name"], claude["name"])
        codex_entry = codex_marketplace["plugins"][0]
        self.assertEqual(codex_entry["name"], codex["name"])
        self.assertEqual(codex_entry["source"]["path"], "./")
        self.assertEqual(codex_entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(codex_entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(
            codex_entry["interface"]["displayName"],
            "Blasphemous Modding Helper",
        )
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / codex_entry["source"]["path"]
                / ".codex-plugin"
                / "plugin.json"
            ).is_file()
        )
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        repository = codex["repository"].removeprefix("https://github.com/")
        self.assertIn(f"codex plugin marketplace add {repository}", readme)
        self.assertIn(
            f"codex plugin add {codex_entry['name']}@{codex_marketplace['name']}",
            readme,
        )

    def test_release_matrix_validates_runtime_before_acceptance(self):
        workflow = (
            REPOSITORY_ROOT / ".github" / "workflows" / "build.yml"
        ).read_text(encoding="utf-8")
        preflight = workflow.index("check_python_environment.py")
        acceptance = workflow.index("test_modding_api_acceptance.py")
        self.assertIn(
            "run: python tests/test_modding_api_acceptance.py --python python --require-clean",
            workflow,
        )
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
