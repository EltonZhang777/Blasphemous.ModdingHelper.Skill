import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
SCRIPT_ROOT = SKILL_ROOT / "scripts"
SCANNER = SCRIPT_ROOT / "unity_project_navigation.py"

HERO_GUID = "a" * 32
ASSET_GUID = "b" * 32
DUPLICATE_GUID = "c" * 32


class UnityScriptNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "UnityProject"
        self.root.mkdir()
        self.write("ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 2017.4.40f1\n")
        self.add_asset(
            "Assets/Scripts/Hero.cs",
            "public class Hero : MonoBehaviour { void Update() {} }\n",
            HERO_GUID,
        )
        self.write("Assets/Scripts/NoMeta.cs", "public class NoMeta {}\n")
        self.write("Assets/Scripts/BrokenMeta.cs", "public class BrokenMeta {}\n")
        self.write("Assets/Scripts/BrokenMeta.cs.meta", "not metadata\n")
        self.add_asset("Assets/Data/Hero.asset", "%YAML 1.1\n", ASSET_GUID)
        self.add_asset(
            "Assets/First/Duplicate.cs",
            "public class Duplicate {}\n",
            DUPLICATE_GUID,
        )
        self.add_asset(
            "Assets/Second/Duplicate.cs",
            "public class Duplicate {}\n",
            DUPLICATE_GUID,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def add_asset(self, relative, content, guid):
        path = self.write(relative, content)
        self.write(relative + ".meta", f"fileFormatVersion: 2\nguid: {guid}\n")
        return path

    def run_scanner(self, *arguments):
        return subprocess.run(
            [sys.executable, str(SCANNER), *arguments],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def query(self, selector, value, exit_code):
        result = self.run_scanner(
            "script",
            "--project",
            str(self.root),
            f"--{selector}",
            value,
        )
        self.assertEqual(result.returncode, exit_code, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return result, json.loads(result.stdout)

    def digest_tree(self):
        digest = hashlib.sha256()
        paths = []
        for path in sorted(self.root.rglob("*")):
            relative = path.relative_to(self.root).as_posix()
            paths.append(relative)
            digest.update(relative.encode("utf-8"))
            if path.is_file():
                stat = path.stat()
                digest.update(str(stat.st_size).encode("ascii"))
                digest.update(str(stat.st_mtime_ns).encode("ascii"))
                digest.update(path.read_bytes())
        return paths, digest.hexdigest()

    def test_path_query_returns_asset_identity_only(self):
        result, payload = self.query("path", "Assets/Scripts/Hero.cs", 0)

        self.assertEqual(payload["command"], "script")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["limits"], {"csharp_parsed": False})
        self.assertEqual(
            payload["results"],
            [
                {
                    "path": "Assets/Scripts/Hero.cs",
                    "type": "cs",
                    "name": "Hero.cs",
                    "guid": HERO_GUID,
                    "metadata": {
                        "path": "Assets/Scripts/Hero.cs.meta",
                        "status": "present",
                        "file_format_version": 2,
                    },
                    "status": "ok",
                }
            ],
        )
        self.assertNotIn("class_name", result.stdout)
        self.assertNotIn("dependencies", payload)
        self.assertEqual(
            result.stdout,
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        )

    def test_path_guid_and_name_selectors_resolve_the_same_script(self):
        for selector, value in (
            ("path", "Assets/Scripts/Hero.cs"),
            ("guid", HERO_GUID.upper()),
            ("name", "Hero"),
        ):
            with self.subTest(selector=selector):
                _, payload = self.query(selector, value, 0)
                self.assertEqual(payload["results"][0]["path"], "Assets/Scripts/Hero.cs")
                self.assertEqual(payload["results"][0]["guid"], HERO_GUID)

    def test_metadata_gaps_remain_actionable(self):
        cases = (
            ("Assets/Scripts/NoMeta.cs", "missing", "metadata_missing"),
            ("Assets/Scripts/BrokenMeta.cs", "unusable", "metadata_unusable"),
        )
        for path, status, warning_code in cases:
            with self.subTest(path=path):
                _, payload = self.query("path", path, 0)
                self.assertEqual(payload["results"][0]["metadata"]["status"], status)
                self.assertIn(
                    warning_code,
                    [warning["code"] for warning in payload["warnings"]],
                )

    def test_duplicate_name_and_guid_are_ambiguous(self):
        self.add_asset(
            "Assets/Other/Hero.cs",
            "public class OtherHero {}\n",
            "d" * 32,
        )

        for selector, value in (
            ("name", "Hero"),
            ("guid", DUPLICATE_GUID),
        ):
            with self.subTest(selector=selector):
                _, payload = self.query(selector, value, 2)
                self.assertEqual(payload["status"], "ambiguous")
                self.assertGreaterEqual(len(payload["results"]), 2)
                self.assertTrue(
                    all(result["status"] == "ambiguous" for result in payload["results"])
                )
                self.assertIn(
                    "ambiguous_script",
                    [warning["code"] for warning in payload["warnings"]],
                )

    def test_duplicate_guid_across_script_and_non_script_is_ambiguous(self):
        self.add_asset("Assets/Data/Hero.asset", "%YAML 1.1\n", HERO_GUID)

        _, payload = self.query("guid", HERO_GUID, 2)

        self.assertEqual(payload["status"], "ambiguous")
        self.assertEqual(
            {result["type"] for result in payload["results"]},
            {"cs", "asset"},
        )
        self.assertTrue(
            all(result["status"] == "ambiguous" for result in payload["results"])
        )
        self.assertTrue(
            all(result["metadata"]["status"] == "duplicate" for result in payload["results"])
        )
        self.assertIn(
            "ambiguous_script_guid",
            [warning["code"] for warning in payload["warnings"]],
        )
        self.assertIn(
            "duplicate_guid",
            [warning["code"] for warning in payload["warnings"]],
        )

    def test_non_script_and_missing_targets_are_structured(self):
        cases = (
            ("path", "Assets/Data/Hero.asset", 3, "invalid_query", "not_cs_script"),
            ("path", "Assets/Scripts/Missing.cs", 2, "not_found", None),
            ("name", "Missing", 2, "not_found", None),
        )
        for selector, value, exit_code, status, error_code in cases:
            with self.subTest(value=value):
                _, payload = self.query(selector, value, exit_code)
                self.assertEqual(payload["status"], status)
                self.assertEqual(
                    payload["error"]["code"] if payload["error"] else None,
                    error_code,
                )

    def test_malformed_guid_is_structured(self):
        result, payload = self.query("guid", "not-a-guid", 3)

        self.assertEqual(payload["status"], "invalid_query")
        self.assertEqual(payload["error"]["code"], "invalid_guid")
        self.assertEqual(result.returncode, 3)

    def test_query_requires_exactly_one_selector(self):
        missing = self.run_scanner("script", "--project", str(self.root))
        both = self.run_scanner(
            "script",
            "--project",
            str(self.root),
            "--path",
            "Assets/Scripts/Hero.cs",
            "--name",
            "Hero",
        )

        for result in (missing, both):
            with self.subTest(arguments=result.args):
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("usage:", result.stderr)

    def test_queries_are_read_only(self):
        before_paths, before_digest = self.digest_tree()

        self.query("path", "Assets/Scripts/Hero.cs", 0)
        self.query("name", "Hero", 0)
        self.query("path", "Assets/Scripts/Missing.cs", 2)

        after_paths, after_digest = self.digest_tree()
        self.assertEqual(after_paths, before_paths)
        self.assertEqual(after_digest, before_digest)

    def test_scripts_topic_routes_behavior_to_source_authority(self):
        main = (SKILL_ROOT / "references/unity-project-navigation/MAIN.md").read_text(
            encoding="utf-8"
        )
        scripts = (
            SKILL_ROOT / "references/unity-project-navigation/scripts.md"
        ).read_text(encoding="utf-8")
        source_analyzer = (
            SKILL_ROOT / "references/sub-skills/source-analyzer.md"
        ).read_text(encoding="utf-8")
        source_navigation = (
            SKILL_ROOT / "references/source-code-navigation/MAIN.md"
        ).read_text(encoding="utf-8")

        self.assertIn("[scripts.md](scripts.md)", main)
        for phrase in (
            "Source analyzer",
            "blocked",
            "MUST NOT fall back",
            "csharp_parsed: false",
            "ambiguous_script_guid",
            "Completion criteria",
        ):
            self.assertIn(phrase, scripts)
        self.assertIsNone(
            re.search(r"[\u4e00-\u9fff]", scripts),
            "Unity navigation topics must remain English-only.",
        )
        self.assertIn("[scripts.md](../unity-project-navigation/scripts.md)", source_analyzer)
        self.assertIn("[scripts.md](../unity-project-navigation/scripts.md)", source_navigation)


if __name__ == "__main__":
    unittest.main()
