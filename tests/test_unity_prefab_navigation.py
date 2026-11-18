import hashlib
import json
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
NO_META_GUID = "b" * 32
DUPLICATE_GUID = "c" * 32

HERO_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  m_Component:
  - component: {fileID: 2}
  - component: {fileID: 3}
  m_Name: Hero
--- !u!4 &2
Transform:
  m_GameObject: {fileID: 1}
  m_Father: {fileID: 0}
--- !u!114 &3
MonoBehaviour:
  m_GameObject: {fileID: 1}
  m_Script: {fileID: 11500000, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, type: 3}
  target: {fileID: 2}
"""

BROKEN_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
"""


class UnityPrefabNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "UnityProject"
        self.root.mkdir()
        self.write("ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 2017.4.40f1\n")
        self.add_asset("Assets/Prefabs/Hero.prefab", HERO_PREFAB, HERO_GUID)
        self.add_asset("Assets/Prefabs/Broken.prefab", BROKEN_PREFAB, "d" * 32)
        self.write("Assets/Prefabs/NoMeta.prefab", HERO_PREFAB)
        binary = self.root / "Assets/Prefabs/Binary.prefab"
        binary.write_bytes(b"\x00\x01\x02")
        self.write(
            "Assets/Prefabs/Binary.prefab.meta",
            "fileFormatVersion: 2\nguid: " + "f" * 32 + "\n",
        )
        self.add_asset("Assets/Data/Hero.asset", "%YAML 1.1\n", NO_META_GUID)
        self.add_asset(
            "Assets/First/Duplicate.prefab",
            HERO_PREFAB,
            DUPLICATE_GUID,
        )
        self.add_asset(
            "Assets/Second/Duplicate.prefab",
            HERO_PREFAB,
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
            "prefab",
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

    def test_path_query_returns_flattened_object_evidence(self):
        result, payload = self.query("path", "Assets/Prefabs/Hero.prefab", 0)

        self.assertEqual(payload["command"], "prefab")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["limits"],
            {
                "evidence_kind": "flattened",
                "source_prefab_hierarchy": "not_available",
            },
        )
        prefab = payload["results"][0]
        self.assertEqual(prefab["evidence_kind"], "flattened")
        self.assertEqual(prefab["object_count"], 3)
        self.assertEqual(prefab["reference_count"], 7)
        game_object = prefab["objects"][0]
        self.assertEqual(game_object["file_id"], 1)
        self.assertEqual(game_object["class_name"], "GameObject")
        self.assertEqual(game_object["name"], "Hero")
        self.assertEqual(game_object["component_file_ids"], [2, 3])
        self.assertEqual(
            result.stdout,
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        )

    def test_path_guid_and_name_selectors_resolve_the_same_prefab(self):
        for selector, value in (
            ("path", "Assets/Prefabs/Hero.prefab"),
            ("guid", HERO_GUID.upper()),
            ("name", "Hero"),
        ):
            with self.subTest(selector=selector):
                _, payload = self.query(selector, value, 0)
                self.assertEqual(
                    payload["results"][0]["path"],
                    "Assets/Prefabs/Hero.prefab",
                )
                self.assertEqual(payload["results"][0]["guid"], HERO_GUID)

    def test_missing_metadata_remains_actionable_for_a_path_query(self):
        _, payload = self.query("path", "Assets/Prefabs/NoMeta.prefab", 0)

        self.assertEqual(payload["results"][0]["metadata"]["status"], "missing")
        self.assertIn(
            "metadata_missing",
            [warning["code"] for warning in payload["warnings"]],
        )
        self.assertEqual(payload["results"][0]["object_count"], 3)

    def test_duplicate_name_and_guid_are_ambiguous(self):
        self.add_asset(
            "Assets/Other/Hero.prefab",
            HERO_PREFAB,
            "e" * 32,
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
                    "ambiguous_prefab",
                    [warning["code"] for warning in payload["warnings"]],
                )

    def test_mixed_guid_collision_returns_every_candidate(self):
        duplicate = "6" * 32
        self.add_asset("Assets/Prefabs/Mixed.prefab", HERO_PREFAB, duplicate)
        self.add_asset("Assets/Data/Mixed.asset", "%YAML 1.1\n", duplicate)

        _, payload = self.query("guid", duplicate, 2)

        self.assertEqual(payload["status"], "ambiguous")
        self.assertIsNone(payload["error"])
        self.assertEqual(
            [
                (result["path"], result["type"], result["status"])
                for result in payload["results"]
            ],
            [
                ("Assets/Data/Mixed.asset", "asset", "ambiguous"),
                ("Assets/Prefabs/Mixed.prefab", "prefab", "ambiguous"),
            ],
        )
        self.assertTrue(
            all(result["metadata"]["status"] == "duplicate" for result in payload["results"])
        )
        self.assertTrue(
            all(result["object_count"] == 0 for result in payload["results"])
        )
        warning_codes = [warning["code"] for warning in payload["warnings"]]
        self.assertIn("ambiguous_prefab", warning_codes)
        self.assertEqual(warning_codes.count("duplicate_guid"), 2)

    def test_unreadable_unrelated_metadata_prevents_unique_prefab_guid(self):
        self.write("Assets/Other/Broken.asset", "%YAML 1.1\n")
        broken = self.root / "Assets/Other/Broken.asset.meta"
        broken.write_bytes(b"\xff\xfe\x00not-utf8")

        _, payload = self.query("guid", HERO_GUID, 2)

        self.assertEqual(payload["status"], "ambiguous")
        self.assertEqual(
            [result["path"] for result in payload["results"]],
            ["Assets/Prefabs/Hero.prefab"],
        )
        self.assertEqual(payload["results"][0]["status"], "ambiguous")
        self.assertEqual(payload["results"][0]["object_count"], 0)
        self.assertIn(
            "ambiguous_prefab",
            [warning["code"] for warning in payload["warnings"]],
        )

    def test_ambiguous_non_prefab_guid_keeps_readable_candidates(self):
        guid = "9" * 32
        self.add_asset("Assets/Data/Only.asset", "%YAML 1.1\n", guid)
        self.write("Assets/Other/Broken.asset", "%YAML 1.1\n")
        broken = self.root / "Assets/Other/Broken.asset.meta"
        broken.write_bytes(b"\xff\xfe\x00not-utf8")

        _, payload = self.query("guid", guid, 2)

        self.assertEqual(payload["status"], "ambiguous")
        self.assertEqual(
            [
                (result["path"], result["type"], result["status"])
                for result in payload["results"]
            ],
            [
                (
                    "Assets/Data/Only.asset",
                    "asset",
                    "ambiguous",
                )
            ],
        )

    def test_path_and_name_surface_duplicate_guid_without_filtering_the_prefab(self):
        duplicate = "7" * 32
        self.add_asset("Assets/Prefabs/Exact.prefab", HERO_PREFAB, duplicate)
        self.add_asset("Assets/Data/Collision.asset", "%YAML 1.1\n", duplicate)

        for selector, value in (
            ("path", "Assets/Prefabs/Exact.prefab"),
            ("name", "Exact"),
        ):
            with self.subTest(selector=selector):
                _, payload = self.query(selector, value, 0)

                self.assertEqual(payload["status"], "ok")
                self.assertEqual(len(payload["results"]), 1)
                result = payload["results"][0]
                self.assertEqual(result["path"], "Assets/Prefabs/Exact.prefab")
                self.assertEqual(result["type"], "prefab")
                self.assertEqual(result["metadata"]["status"], "duplicate")
                self.assertEqual(result["object_count"], 3)
                self.assertIn(
                    "duplicate_guid",
                    [warning["code"] for warning in payload["warnings"]],
                )

    def test_non_prefab_missing_and_malformed_targets_are_structured(self):
        cases = (
            ("path", "Assets/Data/Hero.asset", 3, "invalid_query", "not_prefab"),
            (
                "path",
                "Assets/Prefabs/Missing.prefab",
                2,
                "not_found",
                None,
            ),
            (
                "path",
                "Assets/Prefabs/Broken.prefab",
                3,
                "invalid_query",
                "malformed_serialized",
            ),
            (
                "path",
                "Assets/Prefabs/Binary.prefab",
                3,
                "unsupported_format",
                "unsupported_serialized_format",
            ),
        )
        for selector, value, exit_code, status, error_code in cases:
            with self.subTest(value=value):
                _, payload = self.query(selector, value, exit_code)
                self.assertEqual(payload["status"], status)
                self.assertEqual(
                    payload["error"]["code"] if payload["error"] else None,
                    error_code,
                )
                if payload["results"]:
                    self.assertEqual(payload["results"][0]["objects"], [])

    def test_query_requires_exactly_one_selector(self):
        missing = self.run_scanner(
            "prefab",
            "--project",
            str(self.root),
        )
        both = self.run_scanner(
            "prefab",
            "--project",
            str(self.root),
            "--path",
            "Assets/Prefabs/Hero.prefab",
            "--name",
            "Hero",
        )

        for result in (missing, both):
            with self.subTest(arguments=result.args):
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("usage:", result.stderr)

    def test_out_of_range_serialized_ids_are_malformed(self):
        hundred_digit_id = "9" * 100
        huge_id = "9" * 5000
        cases = (
            (
                "Assets/Prefabs/HundredDigit.prefab",
                f"%YAML 1.1\n--- !u!1 &{hundred_digit_id}\nGameObject:\n",
            ),
            (
                "Assets/Prefabs/HugeReference.prefab",
                "%YAML 1.1\n--- !u!114 &1\nMonoBehaviour:\n"
                f"  m_Script: {{fileID: {huge_id}, type: 3}}\n",
            ),
            (
                "Assets/Prefabs/HugeType.prefab",
                "%YAML 1.1\n--- !u!114 &1\nMonoBehaviour:\n"
                f"  m_Script: {{fileID: 1, type: {huge_id}}}\n",
            ),
            (
                "Assets/Prefabs/HugeNegativeType.prefab",
                "%YAML 1.1\n--- !u!114 &1\nMonoBehaviour:\n"
                f"  m_Script: {{fileID: 1, type: -{huge_id}}}\n",
            ),
        )
        for index, (relative, content) in enumerate(cases, start=1):
            self.add_asset(relative, content, f"{index:x}" * 32)

        for relative, _ in cases:
            with self.subTest(path=relative):
                _, payload = self.query("path", relative, 3)
                self.assertEqual(payload["status"], "invalid_query")
                self.assertEqual(payload["error"]["code"], "malformed_serialized")
                self.assertEqual(payload["results"][0]["objects"], [])

        self.add_asset(
            "Assets/Prefabs/PlainText.prefab",
            "%YAML 1.1\n--- !u!1 &1\nGameObject:\n"
            f"  note: text {{fileID: {huge_id}}}\n"
            f"  note_type: text {{fileID: 1, type: {huge_id}}}\n",
            "4" * 32,
        )
        _, payload = self.query("path", "Assets/Prefabs/PlainText.prefab", 0)
        self.assertEqual(payload["results"][0]["object_count"], 1)
        self.assertEqual(payload["results"][0]["reference_count"], 0)

    def test_queries_are_read_only(self):
        before_paths, before_digest = self.digest_tree()

        self.query("path", "Assets/Prefabs/Hero.prefab", 0)
        self.query("name", "Hero", 0)
        self.query("path", "Assets/Prefabs/Broken.prefab", 3)

        after_paths, after_digest = self.digest_tree()
        self.assertEqual(after_paths, before_paths)
        self.assertEqual(after_digest, before_digest)

    def test_prefab_topic_is_routed_and_documents_flattened_limits(self):
        main = (SKILL_ROOT / "references/unity-project-navigation/MAIN.md").read_text(
            encoding="utf-8"
        )
        prefabs = (
            SKILL_ROOT / "references/unity-project-navigation/prefabs.md"
        ).read_text(encoding="utf-8")

        self.assertIn("[prefabs.md](prefabs.md)", main)
        self.assertIn("flattened", prefabs)
        self.assertIn("variant", prefabs)
        self.assertIn("nested object ownership", prefabs)


if __name__ == "__main__":
    unittest.main()
