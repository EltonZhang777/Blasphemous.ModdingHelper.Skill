from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError
from unittest import mock


SCRIPT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
)
RESOLVER = SCRIPT_ROOT / "resolve_modding_api.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "modding_api"
sys.path.insert(0, str(SCRIPT_ROOT))

import resolve_modding_api  # noqa: E402


class ResolveModdingApiContractTests(unittest.TestCase):
    def run_resolver(self, *arguments, environment=None):
        return subprocess.run(
            [sys.executable, str(RESOLVER), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment or os.environ.copy(),
            check=False,
        )

    def fixture(self, name):
        return str(FIXTURES / name)

    def assert_success_surface(self, result, expected):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "\n".join(
                [
                    "MODDING_API_REPOSITORY=https://github.com/BrandenEK/"
                    "Blasphemous.ModdingAPI.git",
                    f"MODDING_API_SELECTOR={expected['selector']}",
                    f"MODDING_API_SELECTOR_KIND={expected['kind']}",
                    f"MODDING_API_RESOLVED_REF={expected['ref']}",
                    f"MODDING_API_RESOLVED_TAG={expected['tag']}",
                    f"MODDING_API_RESOLVED_COMMIT={expected['commit']}",
                    "MODDING_API_DOCS_URL=https://github.com/BrandenEK/"
                    f"Blasphemous.ModdingAPI/tree/{expected['ref']}/docs",
                    "MODDING_API_SOURCE_URL=https://github.com/BrandenEK/"
                    f"Blasphemous.ModdingAPI/tree/{expected['ref']}",
                    "",
                ]
            ),
        )

    def test_latest_selects_newest_non_draft_non_prerelease_release(self):
        result = self.run_resolver(
            "--selector",
            "latest",
            "--metadata-file",
            self.fixture("latest-releases.json"),
        )

        self.assert_success_surface(
            result,
            {
                "selector": "latest",
                "kind": "release",
                "ref": "v3.0.1",
                "tag": "v3.0.1",
                "commit": "0123456789012345678901234567890123456789",
            },
        )

    def test_legacy_release_fixture_keeps_latest_output_surface(self):
        result = self.run_resolver(
            "--selector",
            "latest",
            "--metadata-file",
            self.fixture("latest-release.json"),
        )

        self.assert_success_surface(
            result,
            {
                "selector": "latest",
                "kind": "release",
                "ref": "3.0.1",
                "tag": "3.0.1",
                "commit": "0123456789012345678901234567890123456789",
            },
        )

    def test_tag_branch_and_commit_selectors_keep_validation_and_fields(self):
        cases = (
            (
                ("tag:2.5.0", "selector-tag.json"),
                {
                    "selector": "tag:2.5.0",
                    "kind": "tag",
                    "ref": "2.5.0",
                    "tag": "2.5.0",
                    "commit": "1111111111111111111111111111111111111111",
                },
            ),
            (
                ("branch:main", "selector-branch.json"),
                {
                    "selector": "branch:main",
                    "kind": "branch",
                    "ref": "main",
                    "tag": "",
                    "commit": "2222222222222222222222222222222222222222",
                },
            ),
        )
        for (selector, metadata), expected in cases:
            with self.subTest(selector=selector):
                result = self.run_resolver(
                    "--selector",
                    selector,
                    "--metadata-file",
                    self.fixture(metadata),
                )
                self.assert_success_surface(result, expected)

        commit = "ABCDEF0123456789ABCDEF0123456789ABCDEF01"
        result = self.run_resolver("--selector", f"commit:{commit}")
        self.assert_success_surface(
            result,
            {
                "selector": f"commit:{commit}",
                "kind": "commit",
                "ref": commit,
                "tag": "",
                "commit": commit,
            },
        )

    def test_fixture_success_does_not_require_shell_or_external_runtime(self):
        environment = os.environ.copy()
        with tempfile.TemporaryDirectory() as empty_path:
            environment["PATH"] = empty_path
            result = self.run_resolver(
                "--selector",
                "latest",
                "--metadata-file",
                self.fixture("latest-release.json"),
                environment=environment,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MODDING_API_RESOLVED_TAG=3.0.1", result.stdout)
        source = RESOLVER.read_text(encoding="utf-8").lower()
        for dependency in ("node", "bash", "powershell"):
            self.assertNotIn(dependency, source)

    def assert_report_failure(self, result, code, cause):
        self.assertEqual(result.returncode, code)
        self.assertEqual(result.stdout, "")
        self.assertIn("[ERROR REPORT]\n", result.stderr)
        self.assertIn("operation: resolve_modding_api\n", result.stderr)
        self.assertIn("next_step: ", result.stderr)
        self.assertIn(cause, result.stderr)

    def test_invalid_selectors_return_usage_code_and_actionable_report(self):
        selectors = (
            "main",
            "tag:",
            "tag:../release",
            "branch:refs//heads/main",
            "commit:abc",
        )
        for selector in selectors:
            with self.subTest(selector=selector):
                result = self.run_resolver("--selector", selector)
                self.assert_report_failure(result, 2, "selector")

    def test_malformed_and_unavailable_metadata_return_configuration_reports(self):
        cases = (
            ("release-malformed.json", "tag_name"),
            ("release-invalid-json.json", "JSON"),
            ("missing.json", "does not exist"),
            ("release-prerelease.json", "prerelease"),
            ("release-draft.json", "draft"),
        )
        for metadata, cause in cases:
            with self.subTest(metadata=metadata):
                result = self.run_resolver(
                    "--selector",
                    "latest",
                    "--metadata-file",
                    self.fixture(metadata),
                )
                self.assert_report_failure(result, 2, cause)

    def test_mismatched_selector_metadata_is_rejected(self):
        result = self.run_resolver(
            "--selector",
            "tag:2.5.0",
            "--metadata-file",
            self.fixture("latest-release.json"),
        )

        self.assert_report_failure(result, 2, "resolved_ref")

    def test_network_failure_returns_runtime_code_and_actionable_report(self):
        stderr = StringIO()
        stdout = StringIO()
        with mock.patch.object(
            resolve_modding_api,
            "urlopen",
            side_effect=URLError("network unavailable"),
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = resolve_modding_api.main(("--selector", "latest"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("could not retrieve", stderr.getvalue())
        self.assertIn("Check network access and retry", stderr.getvalue())

    def test_missing_git_returns_runtime_code_and_actionable_report(self):
        result = resolve_modding_api.CommandResult(
            ("git", "ls-remote"),
            None,
            error="FileNotFoundError: git",
        )
        stderr = StringIO()
        stdout = StringIO()
        with mock.patch.object(resolve_modding_api, "run_command", return_value=result):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = resolve_modding_api.main(
                    ("--selector", "tag:v1.0.0"),
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("git is required", stderr.getvalue())
        self.assertIn("Install Git", stderr.getvalue())

    def test_help_is_stdout_success(self):
        result = self.run_resolver("--help")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("resolve_modding_api.py", result.stdout)
        self.assertIn("tag:REF", result.stdout)


if __name__ == "__main__":
    unittest.main()
