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
MANAGER = SCRIPT_ROOT / "manage_modding_api.py"
GIT = shutil.which("git") or "git"


class ManageModdingApiContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="modding-api-manager-python-")).resolve()
        self.remote = self.root / "modding-api.git"
        self.seed = self.root / "seed"
        self.metadata = self.root / "latest.json"
        self.target = self.root / "reference"
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
        (self.seed / "README.md").write_text("development one\n", encoding="utf-8")
        self._git(self.seed, "commit", "-am", "first development reference")
        self._git(self.seed, "push", "--set-upstream", "origin", "dev")
        self.dev_commit = self._git(self.seed, "rev-parse", "HEAD")
        self._git(self.seed, "checkout", "main")
        self.metadata.write_text(
            json.dumps(
                {
                    "tag_name": "v1.0.0",
                    "fixture_version": "v1.0.0",
                    "draft": False,
                    "prerelease": False,
                    "resolved_ref": "v1.0.0",
                    "resolved_commit": self.release_commit,
                }
            ),
            encoding="utf-8",
        )
        self.branch_metadata = self.root / "branch.json"
        self.branch_metadata.write_text(
            json.dumps(
                {
                    "fixture_version": "dev",
                    "resolved_ref": "dev",
                    "resolved_commit": self.dev_commit,
                }
            ),
            encoding="utf-8",
        )
        clone = self.run_cloner(
            "--target-path",
            str(self.target),
            "--selector",
            "latest",
            "--metadata-file",
            str(self.metadata),
        )
        self.assertEqual(clone.returncode, 0, clone.stderr)
        self._configure_git_identity(self.target)

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

    def _git_result(self, cwd, *arguments):
        return subprocess.run(
            [GIT, "-C", str(cwd), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def _configure_git_identity(self, repository):
        self._git(repository, "config", "user.email", "test@example.invalid")
        self._git(repository, "config", "user.name", "ModdingAPI test")

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

    def run_cloner(self, *arguments, environment=None):
        return subprocess.run(
            [sys.executable, str(CLONER), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment or self._environment(),
            check=False,
        )

    def run_manager(self, *arguments, environment=None):
        return subprocess.run(
            [sys.executable, str(MANAGER), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment or self._environment(),
            check=False,
        )

    def clone_reference(self, target, selector, metadata=None):
        arguments = ["--target-path", str(target), "--selector", selector]
        if metadata is not None:
            arguments.extend(("--metadata-file", str(metadata)))
        result = self.run_cloner(*arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        self._configure_git_identity(target)
        return target

    def advance_dev(self, message, contents):
        self._git(self.seed, "checkout", "dev")
        (self.seed / "README.md").write_text(contents + "\n", encoding="utf-8")
        self._git(self.seed, "commit", "-am", message)
        self._git(self.seed, "push", "origin", "dev")
        commit = self._git(self.seed, "rev-parse", "HEAD")
        self._git(self.seed, "checkout", "main")
        self.branch_metadata.write_text(
            json.dumps(
                {
                    "fixture_version": "dev",
                    "resolved_ref": "dev",
                    "resolved_commit": commit,
                }
            ),
            encoding="utf-8",
        )
        return commit

    def fields(self, result):
        return dict(line.split("=", 1) for line in result.stdout.splitlines())

    def assert_error(self, result, code, cause):
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertEqual(result.stdout, "")
        for field in (
            "operation",
            "target_path",
            "selector",
            "current_head",
            "worktree_state",
            "network_state",
            "cause",
            "next_step",
        ):
            self.assertIn(f"{field}: ", result.stderr)
        self.assertIn("[ERROR REPORT]\n", result.stderr)
        self.assertIn(cause, result.stderr)

    def test_offline_check_accepts_matching_lock(self):
        result = self.run_manager(
            "--operation",
            "check",
            "--target-path",
            str(self.target),
            "--selector",
            "latest",
            "--offline",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("MODDING_API_OPERATION=check", result.stdout)
        self.assertIn("MODDING_API_NETWORK=offline", result.stdout)
        self.assertIn("MODDING_API_LOCK_MATCH=true", result.stdout)

    def test_help_is_stdout_success(self):
        result = self.run_manager("--help")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("manage_modding_api.py", result.stdout)
        self.assertIn("check|update", result.stdout)

    def test_online_check_rebuilds_incomplete_lock(self):
        lock = Path(str(self.target) + ".lock")
        original = lock.read_text(encoding="utf-8")
        incomplete = "\n".join(
            "checked_at:" if line.startswith("checked_at:") else line
            for line in original.splitlines()
        )
        lock.write_text(incomplete + "\n", encoding="utf-8")

        result = self.run_manager(
            "--operation",
            "check",
            "--target-path",
            str(self.target),
            "--selector",
            "latest",
            "--metadata-file",
            str(self.metadata),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        values = self.fields(result)
        self.assertEqual(values["MODDING_API_NETWORK"], "online")
        self.assertEqual(values["MODDING_API_LOCK_MATCH"], "true")
        self.assertEqual(values["MODDING_API_LOCK_UPDATED"], "true")
        self.assertIn("checked_at: ", lock.read_text(encoding="utf-8"))

    def test_fixed_update_dry_run_then_update_preserves_shape_and_lock(self):
        old_head = self._git(self.target, "rev-parse", "HEAD")
        old_lock = Path(str(self.target) + ".lock").read_text(encoding="utf-8")
        (self.seed / "README.md").write_text("stable two\n", encoding="utf-8")
        self._git(self.seed, "commit", "-am", "second stable reference")
        self._git(self.seed, "tag", "-a", "v1.1.0", "-m", "new stable release")
        self._git(self.seed, "push", "origin", "main", "--tags")
        new_commit = self._git(self.seed, "rev-parse", "refs/tags/v1.1.0^{commit}")
        new_metadata = self.root / "new-latest.json"
        new_metadata.write_text(
            json.dumps(
                {
                    "tag_name": "v1.1.0",
                    "fixture_version": "v1.1.0",
                    "draft": False,
                    "prerelease": False,
                    "resolved_ref": "v1.1.0",
                    "resolved_commit": new_commit,
                }
            ),
            encoding="utf-8",
        )

        dry_run = self.run_manager(
            "--operation",
            "update",
            "--target-path",
            str(self.target),
            "--selector",
            "latest",
            "--metadata-file",
            str(new_metadata),
            "--dry-run",
        )
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        dry_values = self.fields(dry_run)
        self.assertEqual(dry_values["MODDING_API_CHECKOUT_CHANGED"], "true")
        self.assertEqual(self._git(self.target, "rev-parse", "HEAD"), old_head)
        self.assertEqual(Path(str(self.target) + ".lock").read_text(encoding="utf-8"), old_lock)

        update = self.run_manager(
            "--operation",
            "update",
            "--target-path",
            str(self.target),
            "--selector",
            "latest",
            "--metadata-file",
            str(new_metadata),
        )
        self.assertEqual(update.returncode, 0, update.stderr)
        values = self.fields(update)
        self.assertEqual(values["MODDING_API_CHECKOUT_CHANGED"], "true")
        self.assertEqual(self._git(self.target, "rev-parse", "HEAD"), new_commit)
        detached = self._git_result(self.target, "symbolic-ref", "--quiet", "--short", "HEAD")
        self.assertNotEqual(detached.returncode, 0)

    def test_branch_dry_run_plans_fetch_and_update_fast_forwards(self):
        target = self.clone_reference(
            self.root / "branch-reference",
            "branch:dev",
            self.branch_metadata,
        )
        lock = Path(str(target) + ".lock")
        old_lock = lock.read_text(encoding="utf-8")
        self._git(target, "update-ref", "-d", "refs/remotes/origin/dev")

        dry_run = self.run_manager(
            "--operation",
            "update",
            "--target-path",
            str(target),
            "--selector",
            "branch:dev",
            "--metadata-file",
            str(self.branch_metadata),
            "--dry-run",
        )
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        dry_values = self.fields(dry_run)
        self.assertEqual(dry_values["MODDING_API_PLAN_REQUIRES_FETCH"], "true")
        self.assertEqual(self._git(target, "rev-parse", "HEAD"), self.dev_commit)
        self.assertEqual(lock.read_text(encoding="utf-8"), old_lock)
        self._git(target, "update-ref", "refs/remotes/origin/dev", self.dev_commit)

        new_commit = self.advance_dev("second development reference", "development two")
        update = self.run_manager(
            "--operation",
            "update",
            "--target-path",
            str(target),
            "--selector",
            "branch:dev",
            "--metadata-file",
            str(self.branch_metadata),
        )
        self.assertEqual(update.returncode, 0, update.stderr)
        values = self.fields(update)
        self.assertEqual(values["MODDING_API_SELECTOR_KIND"], "branch")
        self.assertEqual(self._git(target, "rev-parse", "HEAD"), new_commit)
        self.assertEqual(self._git(target, "branch", "--show-current"), "dev")
        self.assertEqual(
            self._git(target, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
            "origin/dev",
        )
        self.assertIn(f"resolved_commit: {new_commit}", lock.read_text(encoding="utf-8"))

    def test_divergent_branch_update_preserves_head_and_lock(self):
        target = self.clone_reference(
            self.root / "divergent-reference",
            "branch:dev",
            self.branch_metadata,
        )
        local_contents = "local divergent"
        (target / "README.md").write_text(local_contents + "\n", encoding="utf-8")
        self._git(target, "commit", "-am", "local divergent reference")
        local_head = self._git(target, "rev-parse", "HEAD")
        lock = Path(str(target) + ".lock")
        old_lock = lock.read_text(encoding="utf-8")
        remote_commit = self.advance_dev("third development reference", "development three")

        result = self.run_manager(
            "--operation",
            "update",
            "--target-path",
            str(target),
            "--selector",
            "branch:dev",
            "--metadata-file",
            str(self.branch_metadata),
        )

        self.assert_error(result, 1, "divergent")
        self.assertEqual(self._git(target, "rev-parse", "HEAD"), local_head)
        self.assertEqual(lock.read_text(encoding="utf-8"), old_lock)
        self.assertNotEqual(local_head, remote_commit)

    def test_dirty_wrong_origin_and_invalid_checkout_stop_without_recovery(self):
        target_head = self._git(self.target, "rev-parse", "HEAD")
        lock = Path(str(self.target) + ".lock")
        lock_before = lock.read_text(encoding="utf-8")
        (self.target / "README.md").write_text("local edit\n", encoding="utf-8")
        dirty = self.run_manager(
            "--operation",
            "update",
            "--target-path",
            str(self.target),
            "--selector",
            "latest",
            "--metadata-file",
            str(self.metadata),
        )
        self.assert_error(dirty, 1, "local changes")
        self.assertIn("worktree_state: dirty", dirty.stderr)
        self._git(self.target, "checkout", "--", "README.md")
        self.assertEqual(self._git(self.target, "rev-parse", "HEAD"), target_head)
        self.assertEqual(lock.read_text(encoding="utf-8"), lock_before)

        wrong_origin = self.root / "wrong-origin.git"
        self._git(self.root, "init", "--bare", str(wrong_origin))
        self._git(self.target, "remote", "set-url", "origin", str(wrong_origin))
        wrong = self.run_manager(
            "--operation",
            "check",
            "--target-path",
            str(self.target),
            "--selector",
            "latest",
            "--offline",
        )
        self.assert_error(wrong, 1, "does not match")
        self._git(self.target, "remote", "set-url", "origin", str(self.remote))

        invalid = self.root / "not-a-checkout"
        invalid.mkdir()
        (invalid / "README.md").write_text("not git\n", encoding="utf-8")
        invalid_result = self.run_manager(
            "--operation",
            "check",
            "--target-path",
            str(invalid),
            "--selector",
            "latest",
            "--offline",
        )
        self.assert_error(invalid_result, 1, "not a Git worktree")

    def test_offline_mismatch_network_fallback_and_missing_reference_are_reported(self):
        lock = Path(str(self.target) + ".lock")
        original = lock.read_text(encoding="utf-8")
        bad = original.replace(
            f"resolved_commit: {self.release_commit}",
            "resolved_commit: " + "0" * 40,
        )
        lock.write_text(bad, encoding="utf-8")
        mismatch = self.run_manager(
            "--operation",
            "check",
            "--target-path",
            str(self.target),
            "--selector",
            "latest",
            "--offline",
        )
        self.assert_error(mismatch, 1, "does not match locked commit")
        lock.write_text(original, encoding="utf-8")

        fallback = self.run_manager(
            "--operation",
            "check",
            "--target-path",
            str(self.target),
            "--selector",
            "latest",
            environment=self._environment(MODDING_API_TEST_NETWORK_FAILURE="1"),
        )
        self.assertEqual(fallback.returncode, 0, fallback.stderr)
        fallback_values = self.fields(fallback)
        self.assertEqual(fallback_values["MODDING_API_NETWORK"], "offline")
        self.assertEqual(fallback_values["MODDING_API_LOCK_MATCH"], "true")

        missing = self.run_manager(
            "--operation",
            "update",
            "--target-path",
            str(self.target),
            "--selector",
            "commit:" + "0" * 40,
        )
        self.assert_error(missing, 1, "Git operation failed")
        self.assertEqual(self._git(self.target, "rev-parse", "HEAD"), self.release_commit)
        self.assertEqual(lock.read_text(encoding="utf-8"), original)

    def test_python_entry_point_has_no_legacy_runtime_dependency(self):
        source = MANAGER.read_text(encoding="utf-8").lower()
        for dependency in ("node", "bash", "powershell", "shell"):
            self.assertNotIn(dependency, source)


if __name__ == "__main__":
    unittest.main()
