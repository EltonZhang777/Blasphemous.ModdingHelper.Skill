import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "scripts"
SCANNER = SCRIPT_ROOT / "unity_project_navigation.py"
sys.path.insert(0, str(SCRIPT_ROOT))

from blasphemous_modding_helper import unity_assets  # noqa: E402

ICON_GUID = "1" * 32
ITEM_GUID = "2" * 32
FOLDER_GUID = "3" * 32
PACKAGE_GUID = "4" * 32


class UnityAssetNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "UnityProject"
        self.root.mkdir()
        self.write("ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 2017.4.40f1\n")
        self.add_asset("Assets/Textures/Icon.PNG", b"\x89PNG\r\n", ICON_GUID)
        self.add_asset("Assets/Data/item.asset", "%YAML 1.1\n", ITEM_GUID)
        self.add_asset("Assets/Data/hero.asset", "%YAML 1.1\n", "5" * 32)
        self.add_asset(
            "Packages/com.example/Localization/Table.asset",
            "%YAML 1.1\n",
            PACKAGE_GUID,
        )
        self.write("Assets/Data/no-meta.bin", b"\x00\x01")
        self.write("Assets/Data/broken.asset", "%YAML 1.1\n")
        self.write("Assets/Data/broken.asset.meta", "not metadata\n")
        self.write("Assets/Library/Excluded.PNG", b"excluded")
        (self.root / "Assets" / "Images").mkdir()
        self.write_meta("Assets/Images.meta", FOLDER_GUID)

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
            relative,
            f"fileFormatVersion: 2\nguid: {guid}\n",
        )

    def add_asset(self, relative, content, guid):
        path = self.write(relative, content)
        self.write_meta(relative + ".meta", guid)
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

    def query(self, selector, value, expected_returncode):
        result = self.run_scanner(
            "asset",
            "--project",
            str(self.root),
            f"--{selector}",
            value,
        )
        self.assertEqual(
            result.returncode,
            expected_returncode,
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

    def test_path_lookup_normalizes_project_relative_path(self):
        result, payload = self.query("path", "./Assets//Data\\item.asset", 0)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["command"], "asset")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["query"], {
            "selector": "path",
            "value": "Assets/Data/item.asset",
        })
        self.assertEqual(payload["project"]["included_roots"], ["Assets", "Packages"])
        self.assertEqual(payload["results"], [{
            "path": "Assets/Data/item.asset",
            "type": "asset",
            "guid": ITEM_GUID,
            "metadata": {
                "path": "Assets/Data/item.asset.meta",
                "status": "present",
                "file_format_version": 2,
            },
        }])
        self.assertEqual(
            result.stdout,
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        )

    def test_absolute_path_inside_project_is_normalized(self):
        absolute = str((self.root / "Assets/Data/item.asset").resolve())

        _, payload = self.query("path", absolute, 0)

        self.assertEqual(payload["query"]["value"], "Assets/Data/item.asset")

    def test_project_root_path_is_rejected_without_traceback(self):
        result = self.run_scanner(
            "asset",
            "--project",
            str(self.root),
            "--path",
            str(self.root.resolve()),
        )

        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "invalid_query")

    def test_guid_lookup_resolves_file_and_folder_metadata(self):
        _, file_payload = self.query("guid", ITEM_GUID.upper(), 0)
        _, folder_payload = self.query("guid", FOLDER_GUID, 0)

        self.assertEqual(file_payload["results"][0]["path"], "Assets/Data/item.asset")
        self.assertEqual(file_payload["results"][0]["type"], "asset")
        self.assertEqual(folder_payload["results"][0]["path"], "Assets/Images")
        self.assertEqual(folder_payload["results"][0]["type"], "folder")
        self.assertEqual(folder_payload["results"][0]["guid"], FOLDER_GUID)

    def test_name_lookup_is_case_insensitive_and_matches_stem(self):
        _, basename_payload = self.query("name", "icon.png", 0)
        _, stem_payload = self.query("name", "HERO", 0)
        _, package_payload = self.query("name", "table.asset", 0)

        self.assertEqual(basename_payload["results"][0]["path"], "Assets/Textures/Icon.PNG")
        self.assertEqual(stem_payload["results"][0]["path"], "Assets/Data/hero.asset")
        self.assertEqual(
            package_payload["results"][0]["path"],
            "Packages/com.example/Localization/Table.asset",
        )

    def test_name_lookup_resolves_folders(self):
        _, meta_folder = self.query("name", "Images", 0)
        _, file_folder = self.query("name", "Data", 0)

        self.assertEqual(meta_folder["results"][0]["path"], "Assets/Images")
        self.assertEqual(meta_folder["results"][0]["type"], "folder")
        self.assertEqual(file_folder["results"][0]["path"], "Assets/Data")
        self.assertEqual(file_folder["results"][0]["type"], "folder")

    def test_name_lookup_is_not_a_substring_search(self):
        result, payload = self.query("name", "Tab", 2)

        self.assertEqual(payload["status"], "not_found")
        self.assertEqual(payload["results"], [])
        self.assertIsNone(payload["error"])

    def test_duplicate_name_candidates_are_ambiguous_and_deterministic(self):
        self.add_asset("Assets/A/Shared.asset", "%YAML 1.1\n", "6" * 32)
        self.add_asset("Assets/B/shared.ASSET", "%YAML 1.1\n", "7" * 32)

        first, payload = self.query("name", "SHARED", 2)
        second, repeated = self.query("name", "SHARED", 2)

        self.assertEqual(payload["status"], "ambiguous")
        self.assertEqual(
            [result["path"] for result in payload["results"]],
            ["Assets/A/Shared.asset", "Assets/B/shared.ASSET"],
        )
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(payload, repeated)

    def test_duplicate_guid_is_ambiguous_with_all_candidates(self):
        duplicate = "8" * 32
        self.add_asset("Assets/Z/duplicate.asset", "%YAML 1.1\n", duplicate)
        self.add_asset("Assets/A/duplicate.asset", "%YAML 1.1\n", duplicate)

        _, payload = self.query("guid", duplicate, 2)

        self.assertEqual(payload["status"], "ambiguous")
        self.assertEqual(
            [result["path"] for result in payload["results"]],
            ["Assets/A/duplicate.asset", "Assets/Z/duplicate.asset"],
        )
        self.assertEqual(
            [result["metadata"]["status"] for result in payload["results"]],
            ["duplicate", "duplicate"],
        )
        self.assertEqual(
            [warning["code"] for warning in payload["warnings"]],
            ["duplicate_guid", "duplicate_guid"],
        )

    def test_exact_path_and_name_mark_duplicates_outside_the_result_set(self):
        duplicate = "e" * 32
        self.add_asset("Assets/Data/Exact.asset", "%YAML 1.1\n", duplicate)
        self.add_asset("Assets/Other/Collision.asset", "%YAML 1.1\n", duplicate)

        for selector, value in (
            ("path", "Assets/Data/Exact.asset"),
            ("name", "Exact"),
        ):
            with self.subTest(selector=selector):
                first, payload = self.query(selector, value, 0)
                second, repeated = self.query(selector, value, 0)

                self.assertEqual(payload["status"], "ok")
                self.assertEqual(
                    [result["path"] for result in payload["results"]],
                    ["Assets/Data/Exact.asset"],
                )
                self.assertEqual(
                    payload["results"][0]["metadata"]["status"],
                    "duplicate",
                )
                duplicates = [
                    warning
                    for warning in payload["warnings"]
                    if warning["code"] == "duplicate_guid"
                ]
                self.assertEqual(len(duplicates), 1)
                self.assertEqual(
                    duplicates[0]["path"],
                    "Assets/Data/Exact.asset",
                )
                self.assertEqual(
                    duplicates[0]["message"],
                    f"GUID {duplicate} identifies 2 project paths.",
                )
                self.assertEqual(first.stdout, second.stdout)
                self.assertEqual(payload, repeated)

    def test_unique_path_and_name_keep_present_metadata(self):
        for selector, value in (
            ("path", "Assets/Data/item.asset"),
            ("name", "hero"),
        ):
            with self.subTest(selector=selector):
                _, payload = self.query(selector, value, 0)

                self.assertEqual(payload["results"][0]["metadata"]["status"], "present")
                self.assertNotIn(
                    "duplicate_guid",
                    [warning["code"] for warning in payload["warnings"]],
                )

    def test_guid_query_reads_metadata_only_for_matching_targets(self):
        with mock.patch.object(
            unity_assets,
            "_read_metadata",
            wraps=unity_assets._read_metadata,
        ) as reader:
            payload = unity_assets.asset_query(self.root, "guid", ITEM_GUID)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(reader.call_count, 1)

    def test_missing_identities_are_not_guessed(self):
        _, missing_path = self.query("path", "Assets/Absent.asset", 2)
        _, missing_guid = self.query("guid", "9" * 32, 2)
        _, missing_name = self.query("name", "Absent", 2)

        self.assertEqual(missing_path["status"], "not_found")
        self.assertIsNone(missing_path["error"])
        self.assertEqual(missing_guid["status"], "not_found")
        self.assertEqual(missing_name["status"], "not_found")
        self.assertEqual(missing_guid["results"], [])
        self.assertEqual(missing_name["results"], [])

    def test_missing_and_unusable_metadata_stay_discoverable_by_path(self):
        _, missing = self.query("path", "Assets/Data/no-meta.bin", 0)
        _, unusable = self.query("path", "Assets/Data/broken.asset", 0)

        self.assertIsNone(missing["results"][0]["guid"])
        self.assertEqual(missing["results"][0]["metadata"]["status"], "missing")
        self.assertIn("metadata_missing", [warning["code"] for warning in missing["warnings"]])
        self.assertIsNone(unusable["results"][0]["guid"])
        self.assertEqual(unusable["results"][0]["metadata"]["status"], "unusable")
        self.assertIn(
            "metadata_unusable",
            [warning["code"] for warning in unusable["warnings"]],
        )

    def test_oversized_metadata_version_is_unusable_but_path_is_discoverable(self):
        self.write("Assets/Data/huge.asset", "%YAML 1.1\n")
        self.write(
            "Assets/Data/huge.asset.meta",
            "fileFormatVersion: " + "9" * 5000 + "\nguid: " + "b" * 32 + "\n",
        )

        result, payload = self.query("path", "Assets/Data/huge.asset", 0)

        self.assertEqual(result.returncode, 0)
        self.assertIsNone(payload["results"][0]["guid"])
        self.assertEqual(payload["results"][0]["metadata"]["status"], "unusable")
        self.assertIn(
            "metadata_unusable",
            [warning["code"] for warning in payload["warnings"]],
        )
        _, guid_payload = self.query("guid", "b" * 32, 2)
        self.assertEqual(guid_payload["status"], "not_found")

    def test_excluded_name_applies_only_to_directories(self):
        self.write("Assets/Data/Library", "%YAML 1.1\n")
        self.write_meta("Assets/Data/Library.meta", "c" * 32)

        result, payload = self.query("path", "Assets/Data/Library", 0)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["results"][0]["path"], "Assets/Data/Library")
        self.assertEqual(payload["results"][0]["type"], "file")

    def test_binary_asset_reports_identity_metadata_only(self):
        _, payload = self.query("path", "Assets/Textures/Icon.PNG", 0)

        result = payload["results"][0]
        self.assertEqual(
            set(result),
            {"path", "type", "guid", "metadata"},
        )
        self.assertEqual(result["type"], "png")
        self.assertEqual(result["guid"], ICON_GUID)
        self.assertIn(
            "binary_not_inspected",
            [warning["code"] for warning in payload["warnings"]],
        )

    def test_excluded_roots_are_not_discoverable(self):
        _, payload = self.query("name", "Excluded", 2)
        result = self.run_scanner(
            "asset",
            "--project",
            str(self.root),
            "--path",
            "Assets/Library/Excluded.PNG",
        )

        self.assertEqual(payload["status"], "not_found")
        self.assertEqual(result.returncode, 3)
        rejected = json.loads(result.stdout)
        self.assertEqual(rejected["status"], "invalid_query")
        self.assertEqual(rejected["error"]["code"], "excluded_path")

    def test_excluded_directory_name_is_case_insensitive(self):
        self.add_asset("Assets/logs/hidden.asset", "%YAML 1.1\n", "a" * 32)

        _, payload = self.query("name", "hidden", 2)
        result = self.run_scanner(
            "asset",
            "--project",
            str(self.root),
            "--path",
            "Assets/logs/hidden.asset",
        )

        self.assertEqual(payload["status"], "not_found")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout)["error"]["code"], "excluded_path")

    @unittest.skipUnless(os.name == "nt", "Windows path alias test")
    def test_windows_path_aliases_are_rejected_and_canonicalized(self):
        alias = self.run_scanner(
            "asset",
            "--project",
            str(self.root),
            "--path",
            "Assets/Library./Excluded.PNG",
        )
        _, canonical = self.query("path", "assets/data/ITEM.asset", 0)

        self.assertEqual(alias.returncode, 3)
        alias_payload = json.loads(alias.stdout)
        self.assertEqual(alias_payload["status"], "invalid_query")
        self.assertEqual(alias_payload["error"]["code"], "excluded_path")
        self.assertEqual(canonical["query"]["value"], "Assets/Data/item.asset")
        self.assertEqual(canonical["results"][0]["path"], "Assets/Data/item.asset")

    def test_path_traversal_and_outside_absolute_paths_are_rejected(self):
        outside = Path(self.temp_dir.name) / "outside.asset"
        outside.write_text("%YAML 1.1\n", encoding="utf-8")

        for selected in ("../outside.asset", "Assets/../../outside.asset", str(outside)):
            with self.subTest(selected=selected):
                result = self.run_scanner(
                    "asset",
                    "--project",
                    str(self.root),
                    "--path",
                    selected,
                )
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, 3)
                self.assertEqual(payload["status"], "invalid_query")
                self.assertIn(
                    payload["error"]["code"],
                    {"path_traversal", "path_outside_root"},
                )

    def test_internal_link_is_not_followed(self):
        link = self.root / "Assets" / "Data"
        with mock.patch.object(
            unity_assets,
            "_is_link_like",
            side_effect=lambda path: path == link,
        ):
            payload = unity_assets.asset_query(
                self.root,
                "path",
                "Assets/Data/hero.asset",
            )

        self.assertEqual(payload["status"], "invalid_query")
        self.assertEqual(payload["error"]["code"], "symlink_not_followed")
        self.assertEqual(payload["results"], [])

    def test_absolute_internal_link_is_not_followed(self):
        link = self.root / "Assets" / "Data"
        with mock.patch.object(
            unity_assets,
            "_is_link_like",
            side_effect=lambda path: path == link,
        ):
            payload = unity_assets.asset_query(
                self.root,
                "path",
                str(self.root / "Assets" / "Data" / "hero.asset"),
            )

        self.assertEqual(payload["status"], "invalid_query")
        self.assertEqual(payload["error"]["code"], "symlink_not_followed")

    @unittest.skipUnless(os.name == "nt", "Windows alternate data stream test")
    def test_windows_alternate_data_stream_is_rejected(self):
        result = self.run_scanner(
            "asset",
            "--project",
            str(self.root),
            "--path",
            "Assets/Data/item.asset:stream",
        )

        self.assertEqual(result.returncode, 3)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "invalid_query")

    def test_cli_does_not_create_bytecode_cache(self):
        before = {
            path for path in SCRIPT_ROOT.rglob("__pycache__") if path.is_dir()
        }

        self.query("path", "Assets/Data/item.asset", 0)

        after = {
            path for path in SCRIPT_ROOT.rglob("__pycache__") if path.is_dir()
        }
        self.assertEqual(after, before)

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_external_junction_is_rejected(self):
        outside = Path(self.temp_dir.name) / "outside-junction"
        outside.mkdir()
        (outside / "secret.asset").write_text("%YAML 1.1\n", encoding="utf-8")
        link = self.root / "Assets" / "External"
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if created.returncode != 0:
            self.skipTest(f"directory junction unavailable: {created.stderr}")

        result = self.run_scanner(
            "asset",
            "--project",
            str(self.root),
            "--path",
            "Assets/External/secret.asset",
        )
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 3)
        self.assertEqual(payload["status"], "invalid_query")
        self.assertEqual(payload["error"]["code"], "symlink_outside_root")

    def test_each_query_requires_exactly_one_selector(self):
        missing = self.run_scanner("asset", "--project", str(self.root))
        both = self.run_scanner(
            "asset",
            "--project",
            str(self.root),
            "--path",
            "Assets/Data/item.asset",
            "--guid",
            ITEM_GUID,
        )

        self.assertEqual(missing.returncode, 2)
        self.assertEqual(both.returncode, 2)
        self.assertEqual(missing.stdout, "")
        self.assertEqual(both.stdout, "")
        self.assertIn("one of the arguments", missing.stderr)
        self.assertIn("not allowed with argument", both.stderr)

    def test_asset_queries_are_read_only(self):
        before_paths, before_digest = self.digest_tree()

        self.query("path", "Assets/Data/item.asset", 0)
        self.query("guid", ICON_GUID, 0)
        self.query("name", "hero", 0)

        after_paths, after_digest = self.digest_tree()
        self.assertEqual(after_paths, before_paths)
        self.assertEqual(after_digest, before_digest)


class UnityAssetDocumentationTests(unittest.TestCase):
    def test_asset_topic_is_routed_and_documents_evidence_limits(self):
        navigation = (
            SCRIPT_ROOT.parent / "references" / "unity-project-navigation"
        )
        index = (navigation / "MAIN.md").read_text(encoding="utf-8")
        topic = (navigation / "assets-and-guids.md").read_text(encoding="utf-8")

        self.assertIn("[assets-and-guids.md](assets-and-guids.md)", index)
        for phrase in (
            "--path",
            "--guid",
            "--name",
            "ambiguous",
            "not_found",
            "binary",
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
