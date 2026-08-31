import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
)
CLONER = SCRIPT_ROOT / "clone_modding_api.py"
GIT = shutil.which("git") or "git"


class CloneModdingApiContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modding-api-clone-python-"))
        self.remote = self.root / "modding-api.git"
        self.seed = self.root / "seed"
        self.project = self.root / "project"
        self.latest_metadata = self.root / "latest.json"
        self.branch_metadata = self.root / "branch.json"
        self._git(self.root, "init", "--bare", str(self.remote))
        self._git(self.root, "init", str(self.seed))
        self._git(self.seed, "config", "user.email", "test@example.invalid")
        self._git(self.seed, "config", "user.name", "ModdingAPI test")
        (self.seed / "README.md").write_text("stable\n", encoding="utf-8")
        self._git(self.seed, "add", "README.md")
        self._git(self.seed, "commit", "-m", "initial stable reference")
        self._git(self.seed, "branch", "-M", "main")
        self._git(self.seed, "tag", "-a", "v1.0.0", "-m", "stable release")
        self._git(self.seed, "remote", "add", "origin", str(self.remote))
        self._git(self.seed, "push", "--set-upstream", "origin", "main", "--tags")
        self.release_commit = self._git(
            self.seed, "rev-parse", "refs/tags/v1.0.0^{commit}"
        )
        self._git(self.seed, "checkout", "-b", "dev")
        (self.seed / "README.md").write_text("development\n", encoding="utf-8")
        self._git(self.seed, "commit", "-am", "development reference")
        self._git(self.seed, "push", "--set-upstream", "origin", "dev")
        self.dev_commit = self._git(self.seed, "rev-parse", "HEAD")
        self._git(self.seed, "checkout", "main")
        self.latest_metadata.write_text(
            json.dumps(
                {
                    "tag_name": "v1.0.0",
                    "draft": False,
                    "prerelease": False,
                    "resolved_ref": "v1.0.0",
                    "resolved_commit": self.release_commit,
                }
            ),
            encoding="utf-8",
        )
        self.branch_metadata.write_text(
            json.dumps(
                {
                    "resolved_ref": "dev",
                    "resolved_commit": self.dev_commit,
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _git(self, cwd, *arguments):
        result = subprocess.run(
            [GIT, "-C", str(cwd), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def _environment(self, **updates):
        environment = os.environ.copy()
        environment.update(
            {
                "MODDING_API_TEST_MODE": "1",
                "MODDING_API_TEST_REPOSITORY": str(self.remote),
            }
        )
        environment.update(updates)
        return environment

    def run_cloner(self, *arguments, cwd=None, environment=None):
        return subprocess.run(
            [sys.executable, str(CLONER), *arguments],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment or self._environment(),
            check=False,
        )

    def fixture_arguments(self, path):
        return "--metadata-file", str(path)

    def assert_success(self, result, selector, kind, reference, tag, commit):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        fields = dict(line.split("=", 1) for line in result.stdout.splitlines())
        self.assertEqual(fields["MODDING_API_OPERATION"], "clone")
        self.assertEqual(fields["MODDING_API_REPOSITORY"], str(self.remote))
        self.assertEqual(fields["MODDING_API_SELECTOR"], selector)
        self.assertEqual(fields["MODDING_API_SELECTOR_KIND"], kind)
        self.assertEqual(fields["MODDING_API_RESOLVED_REF"], reference)
        self.assertEqual(fields["MODDING_API_RESOLVED_TAG"], tag)
        self.assertEqual(fields["MODDING_API_RESOLVED_COMMIT"], commit)
        self.assertEqual(fields["MODDING_API_SHALLOW"], "true")
        self.assertTrue(fields["MODDING_API_REFERENCE_PATH"])
        self.assertTrue(fields["MODDING_API_LOCK_PATH"])

    def assert_failure(self, result, code, cause):
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("[ERROR REPORT]\n", result.stderr)
        self.assertIn("operation: clone_modding_api\n", result.stderr)
        self.assertIn("current_head: ", result.stderr)
        self.assertIn("worktree_state: ", result.stderr)
        self.assertIn("network_state: ", result.stderr)
        self.assertIn("cause: ", result.stderr)
        self.assertIn("next_step: ", result.stderr)
        self.assertIn(cause, result.stderr)

    def test_latest_clone_is_shallow_and_records_preferences_and_lock(self):
        self.project.joinpath(".skills", "blasphemous-modding-helper").mkdir(
            parents=True
        )
        preferences = self.project / ".skills" / "blasphemous-modding-helper" / "preferences.md"
        preferences.write_text(
            "lightweight_source_code_path: legacy-source\n"
            "modding_profile_path: legacy-profile\n",
            encoding="utf-8",
        )
        result = self.run_cloner(
            "--scope",
            "project",
            "--selector",
            "latest",
            *self.fixture_arguments(self.latest_metadata),
            cwd=self.project,
        )
        target = (
            self.project
            / ".skills"
            / "blasphemous-modding-helper"
            / "references"
            / "modding-api"
        )
        lock = Path(str(target) + ".lock")
        self.assert_success(result, "latest", "release", "v1.0.0", "v1.0.0", self.release_commit)
        self.assertEqual(self._git(target, "rev-parse", "HEAD"), self.release_commit)
        self.assertTrue((target / ".git" / "shallow").is_file())
        self.assertNotEqual(
            subprocess.run(
                [GIT, "-C", str(target), "symbolic-ref", "--quiet", "--short", "HEAD"],
                capture_output=True,
                check=False,
            ).returncode,
            0,
        )
        preference_text = preferences.read_text(encoding="utf-8")
        self.assertIn(f"modding_api_reference_path: {target.resolve()}", preference_text)
        self.assertIn("modding_api_reference_selector: latest", preference_text)
        lock_text = lock.read_text(encoding="utf-8")
        self.assertIn("selector: latest", lock_text)
        self.assertIn("resolved_tag: v1.0.0", lock_text)
        self.assertIn(f"resolved_commit: {self.release_commit}", lock_text)
        self.assertIn(f"repository: {self.remote}", lock_text)

    def test_tag_branch_and_commit_selectors_create_expected_shapes(self):
        tag_target = self.root / "tag-reference"
        tag_result = self.run_cloner(
            "--target-path",
            str(tag_target),
            "--selector",
            "tag:v1.0.0",
            *self.fixture_arguments(self.latest_metadata),
        )
        self.assert_success(
            tag_result,
            "tag:v1.0.0",
            "tag",
            "v1.0.0",
            "v1.0.0",
            self.release_commit,
        )
        self.assertEqual(self._git(tag_target, "rev-parse", "HEAD"), self.release_commit)

        branch_target = self.root / "branch-reference"
        branch_result = self.run_cloner(
            "--target-path",
            str(branch_target),
            "--selector",
            "branch:dev",
            *self.fixture_arguments(self.branch_metadata),
        )
        self.assert_success(branch_result, "branch:dev", "branch", "dev", "", self.dev_commit)
        self.assertEqual(self._git(branch_target, "branch", "--show-current"), "dev")
        self.assertEqual(
            self._git(
                branch_target,
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{upstream}",
            ),
            "origin/dev",
        )

        commit_target = self.root / "commit-reference"
        commit_selector = f"commit:{self.dev_commit}"
        commit_result = self.run_cloner(
            "--target-path",
            str(commit_target),
            "--selector",
            commit_selector,
        )
        self.assert_success(
            commit_result,
            commit_selector,
            "commit",
            self.dev_commit,
            "",
            self.dev_commit,
        )
        self.assertEqual(self._git(commit_target, "rev-parse", "HEAD"), self.dev_commit)

    def test_preferences_drive_target_and_selector(self):
        target = self.root / "configured-reference"
        preferences = self.root / "configured-preferences.md"
        preferences.write_text(
            f"modding_api_reference_path: {target}\n"
            "modding_api_reference_selector: tag:v1.0.0\n",
            encoding="utf-8",
        )
        result = self.run_cloner(
            "--preferences-file",
            str(preferences),
            *self.fixture_arguments(self.latest_metadata),
        )
        self.assert_success(result, "tag:v1.0.0", "tag", "v1.0.0", "v1.0.0", self.release_commit)
        self.assertEqual(self._git(target, "rev-parse", "HEAD"), self.release_commit)

    def test_existing_target_and_lock_are_never_replaced(self):
        target = self.root / "existing-reference"
        target.mkdir()
        (target / "sentinel.txt").write_text("keep", encoding="utf-8")
        result = self.run_cloner(
            "--target-path",
            str(target),
            "--selector",
            "latest",
            *self.fixture_arguments(self.latest_metadata),
        )
        self.assert_failure(result, 2, "target path already exists")
        self.assertEqual((target / "sentinel.txt").read_text(encoding="utf-8"), "keep")

        lock_target = self.root / "lock-only-reference"
        lock = Path(str(lock_target) + ".lock")
        lock.write_text("sentinel lock", encoding="utf-8")
        result = self.run_cloner(
            "--target-path",
            str(lock_target),
            "--selector",
            "latest",
            *self.fixture_arguments(self.latest_metadata),
        )
        self.assert_failure(result, 2, "lock path already exists")
        self.assertEqual(lock.read_text(encoding="utf-8"), "sentinel lock")
        self.assertFalse(lock_target.exists())

    def test_invalid_usage_and_fixture_gate_return_actionable_reports(self):
        invalid_scope = self.run_cloner(
            "--scope",
            "invalid",
            "--target-path",
            str(self.root / "invalid-scope"),
            "--selector",
            "latest",
        )
        self.assert_failure(invalid_scope, 2, "invalid scope")
        unknown = self.run_cloner("--bogus")
        self.assert_failure(unknown, 2, "unknown option")
        gated = self.run_cloner(
            "--target-path",
            str(self.root / "fixture-gate"),
            "--selector",
            "latest",
            *self.fixture_arguments(self.latest_metadata),
            environment=dict(self._environment(MODDING_API_TEST_MODE="0")),
        )
        self.assert_failure(gated, 2, "require test mode")

    def test_preferences_failure_rolls_back_checkout(self):
        blocked_parent = self.root / "blocked-preferences"
        blocked_parent.write_text("not a directory", encoding="utf-8")
        target = self.root / "rollback-reference"
        result = self.run_cloner(
            "--target-path",
            str(target),
            "--preferences-file",
            str(blocked_parent / "preferences.md"),
            "--selector",
            "latest",
            *self.fixture_arguments(self.latest_metadata),
        )
        self.assert_failure(result, 1, "preferences")
        self.assertFalse(target.exists(), result.stderr)
        self.assertFalse(Path(str(target) + ".lock").exists(), result.stderr)

    def test_missing_git_is_reported_without_creating_target(self):
        target = self.root / "missing-git"
        environment = self._environment(PATH=tempfile.mkdtemp(dir=self.root))
        result = self.run_cloner(
            "--target-path",
            str(target),
            "--selector",
            "latest",
            *self.fixture_arguments(self.latest_metadata),
            environment=environment,
        )
        self.assert_failure(result, 1, "Git")
        self.assertFalse(target.exists())

    def test_python_entry_point_has_no_shell_runtime_dependency(self):
        source = CLONER.read_text(encoding="utf-8").lower()
        for dependency in ("node", "bash", "powershell"):
            self.assertNotIn(dependency, source)


if __name__ == "__main__":
    unittest.main()
