import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = (
    REPOSITORY_ROOT
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
)


SCANNER = (
    SCRIPT_ROOT / "unity_project_navigation.py"
)


class UnityProjectNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "UnityProject"
        self.root.mkdir()
        self.write("ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 2017.4.40f1\n")
        self.write("Assets/Scenes/SetA_MAIN.unity", "%YAML 1.1\n")
        for layer in ("LOGIC", "LAYOUT", "DECO", "AUDIO"):
            self.write(f"Assets/Scenes/SetA_{layer}.unity", "%YAML 1.1\n")
        self.write("Assets/Scenes/SetB_MAIN.unity", "%YAML 1.1\n")
        for layer in ("LOGIC", "LAYOUT", "DECO", "AUDIO"):
            self.write(f"Assets/Scenes/SetB_{layer}.unity", "%YAML 1.1\n")
        self.write("Assets/Scenes/Partial_MAIN.unity", "%YAML 1.1\n")
        self.write("Assets/Scenes/Partial_DECO.unity", "%YAML 1.1\n")
        self.write("Assets/Scenes/Standalone.unity", "%YAML 1.1\n")
        self.write("Assets/Textures/icon.png", b"not inspected")
        self.write("Assets/Textures/icon.png.meta", b"guid: " + b"a" * 32 + b"\n")
        self.write("Assets/Data/item.asset", b"%YAML 1.1\n")
        self.write("Assets/Data/item.asset.meta", b"guid: " + b"b" * 32 + b"\n")
        self.write("Assets/Scripts/Example.cs", b"class Example {}\n")
        self.write("Packages/com.example/package.json", b"{}\n")
        self.write("Assets/Build/ignored.bin", b"ignored")
        self.write("Assets/Library/ignored.bin", b"ignored")
        self.write("Assets/.vs/ignored.bin", b"ignored")
        self.write("Assets/.vscode/ignored.bin", b"ignored")
        self.write("Library/cache.bin", b"ignored")

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

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

    def project_summary(self):
        result = self.run_scanner("project", "--project", str(self.root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return result, json.loads(result.stdout)

    def digest_tree(self):
        digest = hashlib.sha256()
        paths = []
        for path in sorted(self.root.rglob("*")):
            paths.append(path.relative_to(self.root).as_posix())
            digest.update(path.relative_to(self.root).as_posix().encode("utf-8"))
            if path.is_file():
                stat = path.stat()
                digest.update(str(stat.st_size).encode("ascii"))
                digest.update(str(stat.st_mtime_ns).encode("ascii"))
                digest.update(path.read_bytes())
        return paths, digest.hexdigest()

    @staticmethod
    def remove_tree(path):
        for child in sorted(path.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        path.rmdir()

    def test_project_reports_version_counts_roots_and_scene_sets(self):
        result, payload = self.project_summary()

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["command"], "project")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["project"]["root"], str(self.root.resolve()))
        self.assertEqual(payload["project"]["unity_version"], "2017.4.40f1")
        self.assertEqual(payload["project"]["unity_major"], "2017")
        self.assertTrue(payload["project"]["unity_major_compatible"])
        self.assertEqual(payload["project"]["included_roots"], ["Assets", "Packages"])
        self.assertEqual(payload["query"], {})
        self.assertEqual(payload["limits"], {})
        self.assertFalse(payload["truncated"])
        self.assertEqual(payload["warnings"], [])
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["results"], [{
            "file_counts": {
                "total": 19,
                "unity": 13,
                "prefab": 0,
                "asset": 1,
                "cs": 1,
                "meta": 2,
                "other": 2,
            },
            "scene_counts": {
                "total": 13,
                "complete_sets": 2,
                "incomplete_sets": 1,
                "standalone": 1,
            },
        }])
        self.assertEqual(
            result.stdout,
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        )

    def test_project_output_is_deterministic(self):
        first, first_payload = self.project_summary()
        second, second_payload = self.project_summary()

        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first_payload, second_payload)

    def test_non_2017_major_warns_without_rejection(self):
        self.write("ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 2021.3.10f1\n")

        result, payload = self.project_summary()

        self.assertEqual(result.returncode, 0)
        self.assertFalse(payload["project"]["unity_major_compatible"])
        self.assertEqual(
            [warning["code"] for warning in payload["warnings"]],
            ["unity_major_mismatch"],
        )

    def test_missing_version_warns_unknown(self):
        (self.root / "ProjectSettings/ProjectVersion.txt").unlink()

        result, payload = self.project_summary()

        self.assertEqual(result.returncode, 0)
        self.assertIsNone(payload["project"]["unity_version"])
        self.assertIsNone(payload["project"]["unity_major_compatible"])
        self.assertEqual(
            [warning["code"] for warning in payload["warnings"]],
            ["unity_version_unknown"],
        )

    def test_missing_assets_root_is_invalid_project(self):
        self.remove_tree(self.root / "Assets")

        result = self.run_scanner("project", "--project", str(self.root))

        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "invalid_project")
        self.assertEqual(payload["error"]["code"], "invalid_project")
        self.assertEqual(payload["results"], [])

    def test_excluded_directories_are_not_counted(self):
        self.write("Assets/Temp/ignored.bin", b"ignored")
        self.write("Assets/obj/ignored.bin", b"ignored")
        self.write("Packages/com.example/UserSettings/ignored.bin", b"ignored")

        _, payload = self.project_summary()

        self.assertEqual(payload["results"][0]["file_counts"]["total"], 19)

    def test_project_scan_is_read_only(self):
        before_paths, before_digest = self.digest_tree()
        self.project_summary()
        after_paths, after_digest = self.digest_tree()

        self.assertEqual(after_paths, before_paths)
        self.assertEqual(after_digest, before_digest)

    @unittest.skipIf(os.name == "nt", "POSIX expanduser failure test")
    def test_project_missing_user_expansion_returns_json(self):
        result = self.run_scanner(
            "project",
            "--project",
            "~definitely-missing-codex-user",
        )
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stderr, "")
        self.assertEqual(payload["status"], "invalid_project")
        self.assertEqual(payload["error"]["code"], "invalid_project")

    def test_external_directory_symlink_is_not_traversed(self):
        outside = Path(self.temp_dir.name) / "outside"
        outside.mkdir()
        (outside / "hidden.asset").write_text("%YAML 1.1\n", encoding="utf-8")
        link = self.root / "Assets/External"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlink unavailable: {error}")

        result, payload = self.project_summary()

        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["results"][0]["file_counts"]["total"], 19)
        self.assertIn(
            "symlink_outside_root",
            [warning["code"] for warning in payload["warnings"]],
        )

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_external_directory_junction_is_not_traversed(self):
        outside = Path(self.temp_dir.name) / "junction-outside"
        outside.mkdir()
        (outside / "hidden.asset").write_text("%YAML 1.1\n", encoding="utf-8")
        link = self.root / "Assets" / "ExternalJunction"
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            self.skipTest(f"directory junction unavailable: {result.stderr}")

        _, payload = self.project_summary()

        self.assertEqual(payload["results"][0]["file_counts"]["total"], 19)
        self.assertIn(
            "symlink_outside_root",
            [warning["code"] for warning in payload["warnings"]],
        )

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_internal_directory_junction_is_not_traversed(self):
        link = self.root / "Assets" / "Loop"
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(self.root)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            self.skipTest(f"directory junction unavailable: {result.stderr}")

        _, payload = self.project_summary()

        self.assertEqual(payload["results"][0]["file_counts"]["total"], 19)
        self.assertIn(
            "symlink_not_followed",
            [warning["code"] for warning in payload["warnings"]],
        )

    def test_symlinked_assets_root_outside_project_is_rejected(self):
        outside = Path(self.temp_dir.name) / "outside-assets"
        outside.mkdir()
        assets = self.root / "Assets"
        self.remove_tree(assets)
        try:
            assets.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlink unavailable: {error}")

        result = self.run_scanner("project", "--project", str(self.root))

        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout)["status"], "invalid_project")

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_junction_assets_root_outside_project_is_rejected(self):
        outside = Path(self.temp_dir.name) / "junction-assets"
        outside.mkdir()
        assets = self.root / "Assets"
        self.remove_tree(assets)
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(assets), str(outside)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            self.skipTest(f"directory junction unavailable: {result.stderr}")

        result = self.run_scanner("project", "--project", str(self.root))

        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout)["status"], "invalid_project")


if __name__ == "__main__":
    unittest.main()
