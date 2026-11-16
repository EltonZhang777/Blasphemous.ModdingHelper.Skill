import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "scripts"
SCANNER = SCRIPT_ROOT / "unity_project_navigation.py"

SCRIPT_GUID = "a" * 32


class UnityBindingNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "UnityProject"
        self.root.mkdir()
        self.write(
            "ProjectSettings/ProjectVersion.txt",
            "m_EditorVersion: 2017.4.40f1\n",
        )
        self.add_script("Assets/Scripts/Example.cs", SCRIPT_GUID)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def write_meta(self, relative, guid):
        self.write(
            relative + ".meta",
            f"fileFormatVersion: 2\nguid: {guid}\n",
        )

    def add_script(self, relative, guid):
        path = self.write(relative, "class Example {}\n")
        self.write_meta(relative, guid)
        return path

    def source_text(self, entries):
        lines = ["%YAML 1.1", "%TAG !u! tag:unity3d.com,2011:"]
        for file_id, m_script in entries:
            lines.extend(
                [
                    f"--- !u!114 &{file_id}",
                    "MonoBehaviour:",
                    "  m_GameObject: {fileID: 1}",
                ]
            )
            if isinstance(m_script, str):
                lines.append(f"  m_Script: {m_script}")
            else:
                lines.append("  m_Script:")
                lines.extend(f"    {key}: {value}" for key, value in m_script)
            lines.append("  m_Name: ")
        return "\n".join(lines) + "\n"

    def add_source(self, relative, entries):
        return self.write(relative, self.source_text(entries))

    def run_bindings(self, *arguments):
        return subprocess.run(
            [
                sys.executable,
                str(SCANNER),
                "bindings",
                "--project",
                str(self.root),
                *arguments,
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def query(self, *arguments, expected=0):
        result = self.run_bindings(*arguments)
        self.assertEqual(
            result.returncode,
            expected,
            result.stdout + result.stderr,
        )
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

    def assert_cs_row(self, row, path, source_kind, object_id):
        self.assertEqual(
            set(row),
            {
                "source_asset_path",
                "source_asset_kind",
                "source_object_file_id",
                "source_class_id",
                "source_class_name",
                "reference_shape",
                "m_script_file_id",
                "m_script_guid",
                "m_script_type",
                "target_asset_kind",
                "target_asset_path",
                "target_asset_candidates",
                "asset_resolution",
                "asset_resolution_reason",
                "script_object_resolution",
            },
        )
        self.assertEqual(row["source_asset_path"], path)
        self.assertEqual(row["source_asset_kind"], source_kind)
        self.assertEqual(row["source_object_file_id"], object_id)
        self.assertEqual(row["source_class_id"], 114)
        self.assertEqual(row["source_class_name"], "MonoBehaviour")
        self.assertEqual(row["reference_shape"], "structured")
        self.assertEqual(row["m_script_file_id"], "11500000")
        self.assertEqual(row["m_script_guid"], SCRIPT_GUID)
        self.assertEqual(row["m_script_type"], 3)
        self.assertEqual(row["target_asset_kind"], "cs")
        self.assertEqual(row["target_asset_path"], "Assets/Scripts/Example.cs")
        self.assertEqual(row["target_asset_candidates"], [])
        self.assertEqual(row["asset_resolution"], "resolved")
        self.assertIsNone(row["asset_resolution_reason"])
        self.assertEqual(row["script_object_resolution"], "asset_level_only")

    def test_project_wide_enumeration_reports_direct_cs_bindings(self):
        self.add_source(
            "Assets/Scenes/Main.unity",
            [
                (
                    100,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                )
            ],
        )
        self.add_source(
            "Assets/Prefabs/Widget.prefab",
            [
                (
                    200,
                    [
                        ("fileID", "11500000"),
                        ("guid", SCRIPT_GUID.upper()),
                        ("type", "3"),
                    ],
                )
            ],
        )
        self.add_source(
            "Assets/Data/Config.asset",
            [
                (
                    300,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                )
            ],
        )

        result, payload = self.query()

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["command"], "bindings")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["scan_coverage"], "complete")
        self.assertEqual(
            payload["limits"],
            {"limit": 200, "default_limit": 200, "max_limit": 1000},
        )
        self.assertFalse(payload["truncated"])
        self.assertEqual(payload["warnings"], [])
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["query"], {})
        self.assertEqual(len(payload["results"]), 3)
        self.assert_cs_row(
            payload["results"][0],
            "Assets/Data/Config.asset",
            "asset",
            "300",
        )
        self.assert_cs_row(
            payload["results"][1],
            "Assets/Prefabs/Widget.prefab",
            "prefab",
            "200",
        )
        self.assert_cs_row(
            payload["results"][2],
            "Assets/Scenes/Main.unity",
            "scene",
            "100",
        )
        self.assertEqual(
            result.stdout,
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        )

    def test_repeated_instances_remain_separate(self):
        self.add_source(
            "Assets/Scenes/Repeated.unity",
            [
                (
                    10,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
                (
                    2,
                    [
                        ("fileID", "11500000"),
                        ("guid", SCRIPT_GUID),
                        ("type", "3"),
                    ],
                ),
            ],
        )

        _, payload = self.query()

        self.assertEqual(
            [row["source_object_file_id"] for row in payload["results"]],
            ["2", "10"],
        )
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["results"][0]["m_script_guid"], SCRIPT_GUID)
        self.assertEqual(payload["results"][1]["m_script_guid"], SCRIPT_GUID)

    def test_physical_packages_root_is_included(self):
        package_guid = "b" * 32
        self.add_script("Packages/com.example/Scripts/PackageScript.cs", package_guid)
        self.add_source(
            "Packages/com.example/Prefabs/PackageWidget.prefab",
            [
                (
                    42,
                    "{fileID: 11500000, guid: "
                    + package_guid
                    + ", type: 3}",
                )
            ],
        )

        _, payload = self.query("--limit", "1000")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["results"]), 1)
        row = payload["results"][0]
        self.assertEqual(
            row["source_asset_path"],
            "Packages/com.example/Prefabs/PackageWidget.prefab",
        )
        self.assertEqual(
            row["target_asset_path"],
            "Packages/com.example/Scripts/PackageScript.cs",
        )
        self.assertEqual(row["asset_resolution"], "resolved")
        self.assertEqual(row["script_object_resolution"], "asset_level_only")

    def test_numeric_ordering_and_cursor_pages_are_deterministic(self):
        self.add_source(
            "Assets/Scenes/Ordered.unity",
            [
                (
                    file_id,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                )
                for file_id in (300, -2, 9007199254740993, 10, 1)
            ],
        )

        first, first_payload = self.query("--limit", "2")
        repeated, repeated_payload = self.query("--limit", "2")
        second, second_payload = self.query(
            "--limit",
            "2",
            "--cursor",
            first_payload["next_cursor"],
        )
        third, third_payload = self.query(
            "--limit",
            "2",
            "--cursor",
            second_payload["next_cursor"],
        )

        self.assertEqual(
            [row["source_object_file_id"] for row in first_payload["results"]],
            ["-2", "1"],
        )
        self.assertEqual(
            [row["source_object_file_id"] for row in second_payload["results"]],
            ["10", "300"],
        )
        self.assertEqual(
            [row["source_object_file_id"] for row in third_payload["results"]],
            ["9007199254740993"],
        )
        self.assertIsNotNone(first_payload["next_cursor"])
        self.assertIsNotNone(second_payload["next_cursor"])
        self.assertIsNone(third_payload["next_cursor"])
        self.assertEqual(first.stdout, repeated.stdout)
        self.assertEqual(first_payload, repeated_payload)
        self.assertNotIn("/", first_payload["next_cursor"])
        for page in (first_payload, second_payload, third_payload):
            self.assertEqual(page["status"], "ok")
            self.assertEqual(page["scan_coverage"], "complete")

    def test_default_and_maximum_page_limits(self):
        self.add_source(
            "Assets/Scenes/Large.unity",
            [
                (
                    file_id,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                )
                for file_id in range(1, 1002)
            ],
        )

        _, default_page = self.query()
        _, maximum_page = self.query("--limit", "1000")
        _, final_page = self.query(
            "--limit",
            "1000",
            "--cursor",
            maximum_page["next_cursor"],
        )

        self.assertEqual(len(default_page["results"]), 200)
        self.assertEqual(default_page["status"], "ok")
        self.assertIsNotNone(default_page["next_cursor"])
        self.assertEqual(len(maximum_page["results"]), 1000)
        self.assertEqual(maximum_page["status"], "ok")
        self.assertIsNotNone(maximum_page["next_cursor"])
        self.assertEqual(len(final_page["results"]), 1)
        self.assertEqual(final_page["status"], "ok")
        self.assertIsNone(final_page["next_cursor"])

    def test_directory_with_cs_suffix_is_not_a_resolved_script(self):
        directory_guid = "c" * 32
        directory = self.root / "Assets/Scripts/NotAFile.cs"
        directory.mkdir(parents=True)
        self.write_meta("Assets/Scripts/NotAFile.cs", directory_guid)
        self.add_source(
            "Assets/Scenes/DirectoryTarget.unity",
            [
                (
                    1,
                    "{fileID: 11500000, guid: "
                    + directory_guid
                    + ", type: 3}",
                )
            ],
        )

        _, payload = self.query()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["results"]), 1)
        row = payload["results"][0]
        self.assertEqual(row["target_asset_kind"], "unresolved")
        self.assertIsNone(row["target_asset_path"])
        self.assertEqual(row["asset_resolution"], "missing")
        self.assertEqual(row["asset_resolution_reason"], "missing_target")
        self.assertEqual(row["script_object_resolution"], "not_applicable")

    def test_invalid_limit_and_cursor_return_json_errors(self):
        self.add_source(
            "Assets/Scenes/Main.unity",
            [
                (
                    1,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                )
            ],
        )

        for arguments in (
            ("--limit", "0"),
            ("--limit", "1001"),
            ("--limit", "not-a-number"),
            ("--cursor", "not-a-cursor"),
        ):
            with self.subTest(arguments=arguments):
                result, payload = self.query(*arguments, expected=3)
                self.assertEqual(payload["status"], "invalid_query")
                self.assertEqual(payload["results"], [])
                self.assertEqual(payload["error"]["code"], "invalid_query")
                self.assertEqual(
                    result.stdout,
                    json.dumps(
                        payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n",
                )

    def test_invalid_project_returns_json_errors(self):
        missing = Path(self.temp_dir.name) / "MissingProject"
        result = subprocess.run(
            [
                sys.executable,
                str(SCANNER),
                "bindings",
                "--project",
                str(missing),
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "invalid_project")
        self.assertEqual(payload["error"]["code"], "invalid_project")

    def test_non_monobehaviour_and_missing_m_script_are_skipped(self):
        self.write(
            "Assets/Scenes/Filtered.unity",
            "\n".join(
                [
                    "%YAML 1.1",
                    "%TAG !u! tag:unity3d.com,2011:",
                    "--- !u!1 &1",
                    "GameObject:",
                    "  m_Name: Root",
                    "--- !u!114 &2",
                    "MonoBehaviour:",
                    "  m_GameObject: {fileID: 1}",
                    "--- !u!114 &3",
                    "MonoBehaviour:",
                    "  m_GameObject: {fileID: 1}",
                    "  m_Script: {fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                    "",
                ]
            ),
        )

        _, payload = self.query()

        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(
            payload["results"][0]["source_object_file_id"],
            "3",
        )

    def test_bindings_query_is_read_only_and_does_not_write_bytecode(self):
        self.add_source(
            "Assets/Scenes/Main.unity",
            [
                (
                    1,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                )
            ],
        )
        before_paths, before_digest = self.digest_tree()
        before_cache = {
            path for path in SCRIPT_ROOT.rglob("__pycache__") if path.is_dir()
        }

        self.query()

        after_paths, after_digest = self.digest_tree()
        after_cache = {
            path for path in SCRIPT_ROOT.rglob("__pycache__") if path.is_dir()
        }
        self.assertEqual(after_paths, before_paths)
        self.assertEqual(after_digest, before_digest)
        self.assertEqual(after_cache, before_cache)

    def test_documentation_routes_bindings_topic(self):
        navigation = (
            SCRIPT_ROOT.parent / "references" / "unity-project-navigation"
        )
        index = (navigation / "MAIN.md").read_text(encoding="utf-8")
        topic = (navigation / "bindings.md").read_text(encoding="utf-8")

        self.assertIn("[bindings.md](bindings.md)", index)
        for phrase in (
            "bindings",
            "m_Script",
            "--limit",
            "--cursor",
            "asset_level_only",
            "source analyzer",
            "Completion criteria",
            "Next action",
        ):
            self.assertIn(phrase, topic)
        self.assertIsNone(
            re.search(r"[\u4e00-\u9fff]", topic),
            "Unity navigation topics must remain English-only.",
        )


if __name__ == "__main__":
    unittest.main()
