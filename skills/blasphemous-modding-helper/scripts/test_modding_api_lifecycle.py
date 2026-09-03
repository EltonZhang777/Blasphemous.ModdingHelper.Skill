#!/usr/bin/env python3
"""Exercise ModdingAPI lifecycle behavior through the public Python CLIs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Sequence


SCRIPT_ROOT = Path(__file__).resolve().parent
RESOLVER = SCRIPT_ROOT / "resolve_modding_api.py"
CLONER = SCRIPT_ROOT / "clone_modding_api.py"
MANAGER = SCRIPT_ROOT / "manage_modding_api.py"
GIT = shutil.which("git") or "git"


class PublicLifecycleContractTests(unittest.TestCase):
    """Verify lifecycle behavior without importing implementation modules."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="modding-api-lifecycle-")
        self.root = Path(self.temp_dir.name).resolve()
        self.remote = self.root / "modding-api.git"
        self.seed = self.root / "seed"
        self.metadata = self.root / "latest.json"
        self._git(self.root, "init", "--bare", str(self.remote))
        self._git(self.root, "init", str(self.seed))
        self._git(self.seed, "config", "user.email", "test@example.invalid")
        self._git(self.seed, "config", "user.name", "Python lifecycle test")
        (self.seed / "README.md").write_text("stable\n", encoding="utf-8")
        self._git(self.seed, "add", "README.md")
        self._git(self.seed, "commit", "-m", "initial stable reference")
        self._git(self.seed, "branch", "-M", "main")
        self._git(self.seed, "tag", "-a", "v1.0.0", "-m", "stable release")
        self._git(self.seed, "remote", "add", "origin", str(self.remote))
        self._git(self.seed, "push", "--set-upstream", "origin", "main", "--tags")
        self.release_commit = self._git(
            self.seed,
            "rev-parse",
            "refs/tags/v1.0.0^{commit}",
        )
        self.metadata.write_text(
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
        self.environment = os.environ.copy()
        self.environment.update(
            {
                "MODDING_API_TEST_MODE": "1",
                "MODDING_API_TEST_REPOSITORY": str(self.remote),
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, cwd: Path, *arguments: str) -> str:
        result = subprocess.run(
            [GIT, "-C", str(cwd), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def run_cli(self, script: Path, *arguments: str):
        return subprocess.run(
            [sys.executable, str(script), *arguments],
            cwd=str(self.root),
            env=self.environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )

    def fixture_arguments(self) -> tuple[str, ...]:
        return "--metadata-file", str(self.metadata)

    def test_resolver_public_cli_preserves_selector_and_reference_fields(self):
        result = self.run_cli(
            RESOLVER,
            "--selector",
            "latest",
            *self.fixture_arguments(),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        fields = dict(line.split("=", 1) for line in result.stdout.splitlines())
        self.assertEqual(fields["MODDING_API_SELECTOR"], "latest")
        self.assertEqual(fields["MODDING_API_SELECTOR_KIND"], "release")
        self.assertEqual(fields["MODDING_API_RESOLVED_REF"], "v1.0.0")
        self.assertEqual(fields["MODDING_API_RESOLVED_COMMIT"], self.release_commit)
        self.assertTrue(fields["MODDING_API_DOCS_URL"].endswith("/v1.0.0/docs"))

    def test_clone_and_manager_public_clis_preserve_checkout_and_lock_contract(self):
        target = self.root / "reference"
        clone = self.run_cli(
            CLONER,
            "--target-path",
            str(target),
            "--selector",
            "latest",
            *self.fixture_arguments(),
        )

        self.assertEqual(clone.returncode, 0, clone.stderr)
        clone_fields = dict(line.split("=", 1) for line in clone.stdout.splitlines())
        self.assertEqual(clone_fields["MODDING_API_OPERATION"], "clone")
        self.assertEqual(clone_fields["MODDING_API_RESOLVED_REF"], "v1.0.0")
        self.assertEqual(clone_fields["MODDING_API_RESOLVED_COMMIT"], self.release_commit)
        self.assertEqual(clone_fields["MODDING_API_SHALLOW"], "true")
        self.assertEqual(self._git(target, "rev-parse", "HEAD"), self.release_commit)
        self.assertTrue(Path(f"{target}.lock").is_file())

        check = self.run_cli(
            MANAGER,
            "--operation",
            "check",
            "--target-path",
            str(target),
            "--selector",
            "latest",
            *self.fixture_arguments(),
            "--offline",
        )

        self.assertEqual(check.returncode, 0, check.stderr)
        check_fields = dict(line.split("=", 1) for line in check.stdout.splitlines())
        self.assertEqual(check_fields["MODDING_API_OPERATION"], "check")
        self.assertEqual(check_fields["MODDING_API_NETWORK"], "offline")
        self.assertEqual(check_fields["MODDING_API_LOCK_MATCH"], "true")
        self.assertEqual(check_fields["MODDING_API_CHECKOUT_CHANGED"], "false")

    def test_manager_public_cli_reports_dirty_update_without_mutating_checkout(self):
        target = self.root / "reference"
        clone = self.run_cli(
            CLONER,
            "--target-path",
            str(target),
            "--selector",
            "latest",
            *self.fixture_arguments(),
        )
        self.assertEqual(clone.returncode, 0, clone.stderr)
        (target / "README.md").write_text("changed by user\n", encoding="utf-8")
        before = self._git(target, "rev-parse", "HEAD")

        update = self.run_cli(
            MANAGER,
            "--operation",
            "update",
            "--target-path",
            str(target),
            "--selector",
            "latest",
            *self.fixture_arguments(),
        )

        self.assertEqual(update.returncode, 1)
        self.assertEqual(update.stdout, "")
        self.assertIn("[ERROR REPORT]", update.stderr)
        self.assertIn("operation: update", update.stderr)
        self.assertIn("next_step: ", update.stderr)
        self.assertIn("dirty", update.stderr.lower())
        self.assertEqual(self._git(target, "rev-parse", "HEAD"), before)

    def test_resolver_public_cli_rejects_noncanonical_selector_with_report(self):
        result = self.run_cli(RESOLVER, "--selector", "branch/main")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("[ERROR REPORT]", result.stderr)
        self.assertIn("operation: resolve_modding_api", result.stderr)
        self.assertIn("next_step: ", result.stderr)


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Exercise ModdingAPI resolver, clone, and manager through "
            "public Python subprocess entry points."
        )
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    build_parser().parse_args(argv)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        PublicLifecycleContractTests
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
