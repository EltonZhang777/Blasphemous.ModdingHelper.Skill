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
BINDING_FIELDS = {
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
}


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
        self.assertEqual(set(row), BINDING_FIELDS)
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

    def test_null_and_malformed_references_keep_the_target_schema(self):
        oversized = "x" * 600
        self.add_source(
            "Assets/Scenes/Invalid.unity",
            [
                (1, "{fileID: 0}"),
                (2, [("fileID", "0")]),
                (3, "{fileID: 11500000}"),
                (
                    4,
                    "{fileID: 11500000, guid: not-a-guid, type: 3}",
                ),
                (
                    5,
                    "{fileID: nope, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
                (
                    6,
                    "{fileID: 9223372036854775808, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
                (
                    7,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3",
                ),
                (8, oversized),
                (9, "{fileID: 0, type: invalid}"),
                (
                    10,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3, junk: value}",
                ),
                (
                    11,
                    "{wrapper: {fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}}",
                ),
                (
                    12,
                    "{fileID: 1_0, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
            ],
        )

        _, payload = self.query()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            [row["reference_shape"] for row in payload["results"]],
            [
                "null",
                "null",
                "malformed",
                "malformed",
                "malformed",
                "malformed",
                "malformed",
                "malformed",
                "malformed",
                "malformed",
                "malformed",
                "malformed",
            ],
        )
        for row in payload["results"]:
            expected_fields = set(BINDING_FIELDS)
            if row["reference_shape"] == "malformed":
                expected_fields.add("raw_reference")
            self.assertEqual(set(row), expected_fields)
            self.assertEqual(row["target_asset_kind"], "not_applicable")
            self.assertIsNone(row["target_asset_path"])
            self.assertEqual(row["target_asset_candidates"], [])
            self.assertEqual(row["asset_resolution"], "not_applicable")
            self.assertIsNone(row["asset_resolution_reason"])
            self.assertEqual(row["script_object_resolution"], "not_applicable")
            if row["reference_shape"] == "malformed":
                self.assertIn("raw_reference", row)
                self.assertLessEqual(len(row["raw_reference"]), 512)
            else:
                self.assertNotIn("raw_reference", row)
        self.assertEqual(payload["results"][0]["m_script_file_id"], "0")
        self.assertEqual(payload["results"][1]["m_script_file_id"], "0")
        self.assertIsNone(payload["results"][5]["m_script_file_id"])
        self.assertTrue(payload["results"][6]["raw_reference"].endswith(", type: 3"))

    def test_target_resolution_states_remain_separate(self):
        missing_meta = "d" * 32
        missing_target = "e" * 32
        duplicate = "f" * 32
        dll_target = "1" * 32
        unsupported_target = "2" * 32
        other_target = "3" * 32
        self.write_meta("Assets/Scripts/MissingTarget.cs", missing_target)
        self.add_script("Assets/Scripts/CopyA.cs", duplicate)
        self.add_script("Assets/Scripts/CopyB.cs", duplicate)
        self.write("Assets/Plugins/Example.dll", b"MZ")
        self.write_meta("Assets/Plugins/Example.dll", dll_target)
        self.write("Assets/Textures/Example.png", b"\x89PNG")
        self.write_meta("Assets/Textures/Example.png", unsupported_target)
        self.write("Assets/Data/Example.txt", "data\n")
        self.write_meta("Assets/Data/Example.txt", other_target)
        self.add_source(
            "Assets/Scenes/Targets.unity",
            [
                (
                    1,
                    "{fileID: -7, guid: "
                    + missing_meta
                    + ", type: 3}",
                ),
                (
                    2,
                    "{fileID: 9007199254740993, guid: "
                    + missing_target
                    + ", type: 3}",
                ),
                (
                    3,
                    "{fileID: 11500000, guid: "
                    + duplicate
                    + ", type: 3}",
                ),
                (
                    4,
                    "{fileID: 11500000, guid: "
                    + dll_target
                    + ", type: 3}",
                ),
                (
                    5,
                    "{fileID: 11500000, guid: "
                    + unsupported_target
                    + ", type: 3}",
                ),
                (
                    6,
                    "{fileID: 11500000, guid: "
                    + other_target
                    + ", type: 3}",
                ),
            ],
        )

        _, payload = self.query()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(len(payload["results"]), 6)
        (
            missing_meta_row,
            missing_target_row,
            duplicate_row,
            dll_row,
            unsupported_row,
            other_row,
        ) = payload["results"]

        self.assertEqual(missing_meta_row["m_script_file_id"], "-7")
        self.assertEqual(missing_meta_row["target_asset_kind"], "unresolved")
        self.assertEqual(missing_meta_row["asset_resolution"], "missing")
        self.assertEqual(
            missing_meta_row["asset_resolution_reason"],
            "missing_meta",
        )
        self.assertEqual(
            missing_target_row["m_script_file_id"],
            "9007199254740993",
        )
        self.assertEqual(missing_target_row["asset_resolution"], "missing")
        self.assertEqual(
            missing_target_row["asset_resolution_reason"],
            "missing_target",
        )
        self.assertEqual(duplicate_row["asset_resolution"], "ambiguous")
        self.assertEqual(
            duplicate_row["asset_resolution_reason"],
            "duplicate_guid",
        )
        self.assertIsNone(duplicate_row["target_asset_path"])
        self.assertEqual(
            duplicate_row["target_asset_candidates"],
            [
                {"kind": "cs", "path": "Assets/Scripts/CopyA.cs"},
                {"kind": "cs", "path": "Assets/Scripts/CopyB.cs"},
            ],
        )
        self.assertEqual(dll_row["target_asset_kind"], "binary")
        self.assertEqual(
            dll_row["target_asset_path"],
            "Assets/Plugins/Example.dll",
        )
        self.assertEqual(dll_row["asset_resolution"], "resolved")
        self.assertIsNone(dll_row["asset_resolution_reason"])
        self.assertEqual(
            dll_row["script_object_resolution"],
            "not_verifiable_binary",
        )
        self.assertEqual(unsupported_row["target_asset_kind"], "binary")
        self.assertEqual(
            unsupported_row["target_asset_path"],
            "Assets/Textures/Example.png",
        )
        self.assertEqual(
            unsupported_row["asset_resolution"],
            "unsupported_binary",
        )
        self.assertEqual(
            unsupported_row["asset_resolution_reason"],
            "unsupported_format",
        )
        self.assertEqual(other_row["target_asset_kind"], "other")
        self.assertEqual(other_row["asset_resolution"], "resolved")
        self.assertEqual(
            other_row["script_object_resolution"],
            "not_applicable",
        )
        for row in (
            missing_meta_row,
            missing_target_row,
            duplicate_row,
        ):
            self.assertEqual(
                row["script_object_resolution"],
                "not_applicable",
            )
        for row in payload["results"]:
            self.assertEqual(set(row), BINDING_FIELDS)
            for field in (
                "target_asset_kind",
                "target_asset_path",
                "target_asset_candidates",
                "asset_resolution",
                "asset_resolution_reason",
                "script_object_resolution",
            ):
                self.assertIn(field, row)

    def test_unreadable_metadata_is_not_reported_as_complete(self):
        broken_guid = "4" * 32
        self.write("Assets/Scripts/Broken.cs", "class Broken {}\n")
        self.write(
            "Assets/Scripts/Broken.cs.meta",
            (
                "fileFormatVersion: 2\n"
                f"guid: {broken_guid}\n"
            ).encode("utf-8")
            + b"\xff",
        )
        self.add_source(
            "Assets/Scenes/BrokenMeta.unity",
            [
                (
                    1,
                    "{fileID: 11500000, guid: "
                    + broken_guid
                    + ", type: 3}",
                )
            ],
        )

        _, payload = self.query(expected=4)

        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["scan_coverage"], "partial")
        self.assertEqual(
            payload["warnings"],
            [
                {
                    "code": "metadata_unusable",
                    "message": (
                        "Metadata is not valid UTF-8 and was only partially read."
                    ),
                    "path": "Assets/Scripts/Broken.cs.meta",
                }
            ],
        )
        row = payload["results"][0]
        self.assertEqual(set(row), BINDING_FIELDS)
        self.assertEqual(row["target_asset_kind"], "unresolved")
        self.assertIsNone(row["target_asset_path"])
        self.assertEqual(row["asset_resolution"], "missing")
        self.assertEqual(row["asset_resolution_reason"], "unreadable_meta")
        self.assertEqual(row["script_object_resolution"], "not_applicable")

    def test_path_filters_use_or_semantics_and_bind_the_cursor(self):
        self.add_source(
            "Assets/Scenes/FilterA.unity",
            [
                (
                    1,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                )
            ],
        )
        self.add_source(
            "Assets/Scenes/FilterB.prefab",
            [
                (
                    2,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                )
            ],
        )
        arguments = (
            "--path",
            "Assets/Scenes/FilterB.prefab",
            "--path",
            "Assets/Scenes/FilterA.unity",
        )

        _, payload = self.query(*arguments)

        self.assertEqual(
            payload["query"],
            {
                "source_asset_paths": [
                    "Assets/Scenes/FilterA.unity",
                    "Assets/Scenes/FilterB.prefab",
                ]
            },
        )
        self.assertEqual(
            [
                row["source_asset_path"]
                for row in payload["results"]
            ],
            [
                "Assets/Scenes/FilterA.unity",
                "Assets/Scenes/FilterB.prefab",
            ],
        )

        _, first = self.query(*arguments, "--limit", "1")
        _, second = self.query(
            *arguments,
            "--limit",
            "1",
            "--cursor",
            first["next_cursor"],
        )
        _, invalid = self.query(
            "--path",
            "Assets/Scenes/FilterA.unity",
            "--limit",
            "1",
            "--cursor",
            first["next_cursor"],
            expected=3,
        )

        self.assertEqual(
            first["results"][0]["source_asset_path"],
            "Assets/Scenes/FilterA.unity",
        )
        self.assertEqual(
            second["results"][0]["source_asset_path"],
            "Assets/Scenes/FilterB.prefab",
        )
        self.assertEqual(invalid["status"], "invalid_query")

    def test_object_file_id_requires_one_path_and_a_unique_match(self):
        source_path = "Assets/Scenes/Objects.unity"
        self.add_source(
            source_path,
            [
                (
                    10,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
                (
                    20,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
                (
                    30,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
                (
                    30,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
            ],
        )
        self.add_source("Assets/Scenes/Other.unity", [])

        _, payload = self.query(
            "--path",
            source_path,
            "--object-file-id",
            "+0020",
        )

        self.assertEqual(
            payload["query"],
            {
                "source_asset_paths": [source_path],
                "source_object_file_id": "20",
            },
        )
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(
            payload["results"][0]["source_object_file_id"],
            "20",
        )

        for arguments in (
            ("--object-file-id", "20"),
            (
                "--path",
                source_path,
                "--path",
                "Assets/Scenes/Other.unity",
                "--object-file-id",
                "20",
            ),
            (
                "--path",
                source_path,
                "--path",
                source_path,
                "--object-file-id",
                "20",
            ),
            (
                "--path",
                source_path,
                "--object-file-id",
                "1_0",
            ),
            (
                "--path",
                source_path,
                "--object-file-id",
                "9223372036854775808",
            ),
        ):
            with self.subTest(arguments=arguments):
                _, invalid = self.query(*arguments, expected=3)
                self.assertEqual(invalid["status"], "invalid_query")
                self.assertEqual(invalid["results"], [])

        _, not_found = self.query(
            "--path",
            source_path,
            "--object-file-id",
            "99",
            expected=2,
        )
        self.assertEqual(not_found["status"], "not_found")
        self.assertEqual(not_found["results"], [])

        _, ambiguous = self.query(
            "--path",
            source_path,
            "--object-file-id",
            "30",
            expected=2,
        )
        self.assertEqual(ambiguous["status"], "ambiguous")
        self.assertEqual(len(ambiguous["results"]), 2)

    def test_identical_bindings_do_not_disappear_between_pages(self):
        self.add_source(
            "Assets/Scenes/Identical.unity",
            [
                (
                    40,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
                (
                    40,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
            ],
        )
        arguments = ("--script-guid", SCRIPT_GUID, "--limit", "1")

        _, first = self.query(*arguments)
        _, second = self.query(
            *arguments,
            "--cursor",
            first["next_cursor"],
        )

        self.assertEqual(len(first["results"]), 1)
        self.assertIsNotNone(first["next_cursor"])
        self.assertEqual(len(second["results"]), 1)
        self.assertIsNone(second["next_cursor"])
        self.assertEqual(
            first["results"][0]["source_object_file_id"],
            second["results"][0]["source_object_file_id"],
        )

    def test_script_guid_reverse_lookup_keeps_unresolved_instances(self):
        unresolved_guid = "b" * 32
        self.add_source(
            "Assets/Scenes/Reverse.unity",
            [
                (
                    1,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
                (
                    2,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
                (
                    3,
                    "{fileID: 11500000, guid: "
                    + unresolved_guid.upper()
                    + ", type: 3}",
                ),
            ],
        )

        _, payload = self.query(
            "--script-guid",
            unresolved_guid.upper(),
            "--script-guid",
            SCRIPT_GUID.upper(),
        )

        self.assertEqual(
            payload["query"],
            {
                "script_guids": [
                    SCRIPT_GUID,
                    unresolved_guid,
                ]
            },
        )
        self.assertEqual(len(payload["results"]), 3)
        self.assertEqual(
            [
                row["source_object_file_id"]
                for row in payload["results"]
                if row["m_script_guid"] == SCRIPT_GUID
            ],
            ["1", "2"],
        )
        unresolved_row = next(
            row
            for row in payload["results"]
            if row["m_script_guid"] == unresolved_guid
        )
        self.assertEqual(unresolved_row["asset_resolution"], "missing")
        self.assertEqual(
            unresolved_row["asset_resolution_reason"],
            "missing_meta",
        )

    def test_status_filters_use_or_within_axes_and_and_across_axes(self):
        missing_guid = "5" * 32
        dll_guid = "6" * 32
        unsupported_guid = "7" * 32
        self.write("Assets/Plugins/Filter.dll", b"MZ")
        self.write_meta("Assets/Plugins/Filter.dll", dll_guid)
        self.write("Assets/Textures/Filter.png", b"\x89PNG")
        self.write_meta("Assets/Textures/Filter.png", unsupported_guid)
        self.add_source(
            "Assets/Scenes/Statuses.unity",
            [
                (
                    1,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                ),
                (2, "{fileID: 0}"),
                (3, "{fileID: 11500000}"),
                (
                    4,
                    "{fileID: 11500000, guid: "
                    + missing_guid
                    + ", type: 3}",
                ),
                (
                    5,
                    "{fileID: 11500000, guid: "
                    + dll_guid
                    + ", type: 3}",
                ),
                (
                    6,
                    "{fileID: 11500000, guid: "
                    + unsupported_guid
                    + ", type: 3}",
                ),
            ],
        )

        _, shapes = self.query(
            "--reference-shape",
            "structured",
            "--reference-shape",
            "null",
        )
        self.assertEqual(shapes["status"], "ok")
        self.assertEqual(
            set(row["reference_shape"] for row in shapes["results"]),
            {"structured", "null"},
        )
        _, malformed = self.query("--reference-shape", "malformed")
        self.assertEqual(
            [row["source_object_file_id"] for row in malformed["results"]],
            ["3"],
        )

        _, assets = self.query(
            "--asset-resolution",
            "resolved",
            "--asset-resolution",
            "missing",
        )
        self.assertEqual(
            [row["source_object_file_id"] for row in assets["results"]],
            ["1", "4", "5"],
        )
        _, unsupported = self.query(
            "--asset-resolution",
            "unsupported_binary",
            "--asset-resolution",
            "not_applicable",
        )
        self.assertEqual(
            [row["source_object_file_id"] for row in unsupported["results"]],
            ["2", "3", "6"],
        )

        _, objects = self.query(
            "--script-object-resolution",
            "asset_level_only",
            "--script-object-resolution",
            "not_verifiable_binary",
        )
        self.assertEqual(
            [row["source_object_file_id"] for row in objects["results"]],
            ["1", "5"],
        )
        _, not_applicable = self.query(
            "--script-object-resolution",
            "not_applicable",
        )
        self.assertEqual(
            [
                row["source_object_file_id"]
                for row in not_applicable["results"]
            ],
            ["2", "3", "4", "6"],
        )

        _, crossed = self.query(
            "--reference-shape",
            "structured",
            "--asset-resolution",
            "resolved",
            "--script-object-resolution",
            "not_verifiable_binary",
        )
        self.assertEqual(
            [row["source_object_file_id"] for row in crossed["results"]],
            ["5"],
        )
        _, selector_and_status = self.query(
            "--path",
            "Assets/Scenes/Statuses.unity",
            "--script-guid",
            dll_guid,
            "--asset-resolution",
            "resolved",
        )
        self.assertEqual(
            [
                row["source_object_file_id"]
                for row in selector_and_status["results"]
            ],
            ["5"],
        )

        _, empty = self.query(
            "--reference-shape",
            "null",
            "--asset-resolution",
            "resolved",
        )
        self.assertEqual(empty["status"], "ok")
        self.assertEqual(empty["results"], [])

    def test_invalid_path_and_filter_queries_return_json_errors(self):
        self.add_script("Assets/Scripts/UsesPath.cs", "8" * 32)
        outside = Path(self.temp_dir.name) / "outside.unity"
        for arguments in (
            ("--path", "Assets/Scenes/Missing.unity"),
            ("--path", "Assets/Scripts/UsesPath.cs"),
            ("--path", "../outside.unity"),
            ("--path", str(outside)),
            ("--path", "ProjectSettings/ProjectVersion.txt"),
            ("--path", "Assets/Library/Hidden.unity"),
            ("--script-guid", "not-a-guid"),
            ("--reference-shape", "unknown"),
            ("--asset-resolution", "unknown"),
            ("--script-object-resolution", "unknown"),
        ):
            with self.subTest(arguments=arguments):
                _, payload = self.query(*arguments, expected=3)
                self.assertEqual(payload["status"], "invalid_query")
                self.assertEqual(payload["results"], [])
                self.assertIsNotNone(payload["error"])

        _, unsupported = self.query(
            "--path",
            "Assets/Scripts/UsesPath.cs",
            expected=3,
        )
        self.assertEqual(
            unsupported["error"]["code"],
            "unsupported_format",
        )

        directory = self.root / "Assets/Scenes/Folder.unity"
        directory.mkdir(parents=True)
        _, invalid_directory = self.query(
            "--path",
            "Assets/Scenes/Folder.unity",
            expected=3,
        )
        self.assertEqual(invalid_directory["status"], "invalid_query")

    def test_external_symlink_source_path_is_rejected(self):
        outside = Path(self.temp_dir.name) / "outside.unity"
        outside.write_text("%YAML 1.1\n", encoding="utf-8")
        link = self.root / "Assets/Scenes/External.unity"
        try:
            link.symlink_to(outside)
        except OSError as error:
            self.skipTest(f"file symlink unavailable: {error}")

        _, payload = self.query(
            "--path",
            "Assets/Scenes/External.unity",
            expected=3,
        )

        self.assertEqual(payload["status"], "invalid_query")
        self.assertEqual(
            payload["error"]["code"],
            "symlink_outside_root",
        )

    def test_not_found_precedes_partial_coverage_for_unique_queries(self):
        broken_guid = "9" * 32
        source_path = "Assets/Scenes/PartialUnique.unity"
        self.write("Assets/Scripts/Broken.cs", "class Broken {}\n")
        self.write(
            "Assets/Scripts/Broken.cs.meta",
            (
                "fileFormatVersion: 2\n"
                f"guid: {broken_guid}\n"
            ).encode("utf-8")
            + b"\xff",
        )
        self.add_source(
            source_path,
            [
                (
                    1,
                    "{fileID: 11500000, guid: "
                    + SCRIPT_GUID
                    + ", type: 3}",
                )
            ],
        )

        _, payload = self.query(
            "--path",
            source_path,
            "--object-file-id",
            "99",
            expected=2,
        )

        self.assertEqual(payload["status"], "not_found")
        self.assertEqual(payload["scan_coverage"], "partial")
        self.assertEqual(payload["results"], [])

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
