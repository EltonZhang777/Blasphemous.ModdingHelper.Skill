import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY_ROOT / "ci" / "update-version" / "UpdateVersionNumber.py"
MANIFESTS = (
    "package.json",
    ".claude-plugin/plugin.json",
    "gemini-extension.json",
    "skills-lock.json",
)


def version_values(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "version":
                yield nested
            yield from version_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from version_values(nested)


class UpdateVersionNumberTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        update_version_dir = self.root / "ci" / "update-version"
        update_version_dir.mkdir(parents=True)
        shutil.copy2(SCRIPT, update_version_dir / SCRIPT.name)
        (update_version_dir / "version.yml").write_text(
            "version: 2.0.0\n", encoding="utf-8"
        )

        for relative_path in MANIFESTS:
            destination = self.root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPOSITORY_ROOT / relative_path, destination)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_updater(self, *arguments):
        return subprocess.run(
            [
                sys.executable,
                str(self.root / "ci" / "update-version" / SCRIPT.name),
                *arguments,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_updates_all_public_version_fields_when_the_first_lock_field_is_current(self):
        package = json.loads((self.root / "package.json").read_text(encoding="utf-8"))
        package["version"] = "1.2.0"
        (self.root / "package.json").write_text(
            json.dumps(package, indent=2) + "\n", encoding="utf-8"
        )

        lock_path = self.root / "skills-lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["version"] = "2.0.0"
        lock["skills"]["blasphemous-modding-helper"]["version"] = "1.2.0"
        for entry in lock["references"].values():
            entry["version"] = "1.2.0"
        lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

        result = self.run_updater()

        self.assertEqual(result.returncode, 0, result.stderr)
        for relative_path in MANIFESTS:
            manifest = json.loads(
                (self.root / relative_path).read_text(encoding="utf-8")
            )
            values = list(version_values(manifest))
            self.assertTrue(values)
            self.assertTrue(all(value == "2.0.0" for value in values))
        self.assertEqual(
            sum(
                len(
                    list(
                        version_values(
                            json.loads(
                                (self.root / path).read_text(encoding="utf-8")
                            )
                        )
                    )
                )
                for path in MANIFESTS
            ),
            9,
        )

    def test_missing_manifest_fails_before_writing_other_manifests(self):
        package_path = self.root / "package.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        package["version"] = "1.2.0"
        package_path.write_text(
            json.dumps(package, indent=2) + "\n", encoding="utf-8"
        )
        before = package_path.read_bytes()
        (self.root / "gemini-extension.json").unlink()

        result = self.run_updater()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required manifest", result.stderr)
        self.assertEqual(package_path.read_bytes(), before)

    def test_rejects_invalid_semver_source(self):
        (self.root / "ci" / "update-version" / "version.yml").write_text(
            "version: 01.2.3\n", encoding="utf-8"
        )

        result = self.run_updater()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not valid SemVer", result.stderr)

    def test_accepts_semver_prerelease_and_build_metadata(self):
        (self.root / "ci" / "update-version" / "version.yml").write_text(
            "version: 1.0.0-alpha+001\n", encoding="utf-8"
        )

        result = self.run_updater()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_dry_run_does_not_write_manifests(self):
        before = {
            relative_path: (self.root / relative_path).read_bytes()
            for relative_path in MANIFESTS
        }

        result = self.run_updater("--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would be updated", result.stdout)
        for relative_path, contents in before.items():
            self.assertEqual((self.root / relative_path).read_bytes(), contents)


if __name__ == "__main__":
    unittest.main()
