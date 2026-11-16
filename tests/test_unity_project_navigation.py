import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = (
    REPOSITORY_ROOT
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT_ROOT))

from blasphemous_modding_helper import unity_project  # noqa: E402


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

    def assert_public_output_omits_root(self, result, root):
        variants = {str(root), root.as_posix()}
        for variant in variants:
            self.assertNotIn(variant, result.stdout)
            self.assertNotIn(json.dumps(variant)[1:-1], result.stdout)

        payload = json.loads(result.stdout)
        strings = []

        def collect(value):
            if isinstance(value, dict):
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)
            elif isinstance(value, str):
                strings.append(value)

        collect(payload)
        for value in strings:
            for variant in variants:
                self.assertNotIn(variant.casefold(), value.casefold())
        return payload

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
        self.assertEqual(payload["project"]["root"], ".")
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

    def test_public_cli_output_contains_no_absolute_project_root(self):
        self.write(
            "Assets/Prefabs/Widget.prefab",
            "%YAML 1.1\n--- !u!114 &1\nMonoBehaviour:\n  m_Script: {fileID: 11500000}\n",
        )
        commands = (
            ("project",),
            ("asset", "--path", "Assets/Data/item.asset"),
            ("scene", "--path", "Assets/Scenes/Standalone.unity"),
            ("prefab", "--path", "Assets/Prefabs/Widget.prefab"),
            ("script", "--path", "Assets/Scripts/Example.cs"),
            ("bindings",),
            ("references", "--path", "Assets/Data/item.asset"),
        )
        for command in commands:
            with self.subTest(command=command[0]):
                result = self.run_scanner(
                    *command,
                    "--project",
                    str(self.root),
                )
                self.assertEqual(result.stderr, "")
                payload = self.assert_public_output_omits_root(result, self.root)
                self.assertEqual(payload["project"]["root"], ".")

        self.write(
            "ProjectSettings/ProjectVersion.txt",
            "m_EditorVersion: 2021.3.10f1\n",
        )
        warning_result = self.run_scanner("project", "--project", str(self.root))
        warning_payload = self.assert_public_output_omits_root(
            warning_result,
            self.root,
        )
        self.assertTrue(warning_payload["warnings"])

    def test_invalid_project_error_contains_no_absolute_project_root(self):
        missing = self.root.parent / "PrivateMissingProject"

        result = self.run_scanner("project", "--project", str(missing))

        self.assertEqual(result.returncode, 3)
        payload = self.assert_public_output_omits_root(result, missing)
        self.assertEqual(payload["project"]["root"], ".")

    def test_public_cli_os_error_redacts_project_root(self):
        script = f"""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, {str(SCRIPT_ROOT)!r})
from blasphemous_modding_helper import unity_project

root = Path({str(self.root)!r})

def walk(top, topdown=True, onerror=None, followlinks=False):
    if onerror is not None:
        onerror(PermissionError(13, "Access denied", str(root)))
    yield top, [], []

with mock.patch.object(unity_project.os, "walk", walk):
    raise SystemExit(unity_project.main(["project", "--project", str(root)]))
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = self.assert_public_output_omits_root(result, self.root)
        self.assertTrue(payload["warnings"])
        self.assertEqual(payload["project"]["root"], ".")

    def test_invalid_relative_project_does_not_echo_the_supplied_root(self):
        relative = "tests/missing-private-project"
        resolved = (REPOSITORY_ROOT / relative).resolve()

        result = self.run_scanner("project", "--project", relative)

        self.assertEqual(result.returncode, 3)
        payload = self.assert_public_output_omits_root(result, resolved)
        self.assertEqual(payload["project"]["root"], ".")

    def test_expanduser_failure_still_returns_a_public_envelope(self):
        stream = io.StringIO()
        with mock.patch.object(
            Path,
            "expanduser",
            side_effect=RuntimeError("Unknown user"),
        ):
            with redirect_stdout(stream):
                return_code = unity_project.main(
                    ["project", "--project", "~missing_user"]
                )

        payload = json.loads(stream.getvalue())
        self.assertEqual(return_code, 3)
        self.assertEqual(payload["status"], "invalid_project")
        self.assertEqual(payload["project"]["root"], ".")
        self.assertNotIn("~missing_user", stream.getvalue())

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

    def test_directory_resolution_cycle_is_reported_without_traceback(self):
        cycle = self.root / "Assets" / "Loop"
        cycle.mkdir()
        resolve = Path.resolve

        def resolve_with_cycle(path, *args, **kwargs):
            if path == cycle:
                raise RuntimeError("Symlink loop")
            return resolve(path, *args, **kwargs)

        with mock.patch.object(Path, "resolve", resolve_with_cycle):
            payload = unity_project.project_summary(self.root)

        self.assertEqual(payload["status"], "ok")
        self.assertIn(
            "Assets/Loop",
            [warning.get("path") for warning in payload["warnings"]],
        )

    def test_project_root_resolution_cycle_returns_invalid_project(self):
        resolve = Path.resolve

        def resolve_with_cycle(path, *args, **kwargs):
            if path == self.root:
                raise RuntimeError("Symlink loop")
            return resolve(path, *args, **kwargs)

        with mock.patch.object(Path, "resolve", resolve_with_cycle):
            payload = unity_project.project_summary(self.root)

        self.assertEqual(payload["status"], "invalid_project")
        self.assertEqual(payload["error"]["code"], "invalid_project")

    def test_project_expanduser_failure_returns_invalid_project(self):
        with mock.patch.object(
            Path,
            "expanduser",
            side_effect=RuntimeError("Unknown user"),
        ):
            payload = unity_project.project_summary(Path("~missing_user"))

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
