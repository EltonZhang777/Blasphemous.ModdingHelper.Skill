from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
import shlex
import shutil
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
        reference_version = expected.get(
            "version",
            expected["tag"] or expected["ref"],
        )
        source = expected.get("source", "fixture")
        fixture_version = expected.get(
            "fixture_version",
            reference_version if source == "fixture" else "",
        )
        fixture_status = expected.get(
            "fixture_status",
            "historical" if source == "fixture" else "live",
        )
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
                    f"MODDING_API_REFERENCE_VERSION={reference_version}",
                    f"MODDING_API_RESOLUTION_SOURCE={source}",
                    f"MODDING_API_FIXTURE_VERSION={fixture_version}",
                    f"MODDING_API_FIXTURE_STATUS={fixture_status}",
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
                "source": "direct-selector",
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

    def test_fixture_resolution_reports_historical_source_and_version(self):
        result = self.run_resolver(
            "--selector",
            "latest",
            "--metadata-file",
            self.fixture("latest-release.json"),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MODDING_API_RESOLUTION_SOURCE=fixture", result.stdout)
        self.assertIn("MODDING_API_FIXTURE_VERSION=3.0.1", result.stdout)
        self.assertIn("MODDING_API_FIXTURE_STATUS=historical", result.stdout)
        self.assertIn("MODDING_API_REFERENCE_VERSION=3.0.1", result.stdout)

    def test_fixture_version_mismatch_is_rejected_with_recovery(self):
        with tempfile.TemporaryDirectory() as raw_root:
            metadata = Path(raw_root) / "mismatch.json"
            metadata.write_text(
                '{"tag_name":"v3.0.1","draft":false,"prerelease":false,'
                '"fixture_version":"v1.0.0",'
                '"resolved_ref":"v3.0.1",'
                '"resolved_commit":"0123456789012345678901234567890123456789"}',
                encoding="utf-8",
            )
            result = self.run_resolver(
                "--selector",
                "latest",
                "--metadata-file",
                str(metadata),
            )

        self.assert_report_failure(result, 2, "fixture_version")
        self.assertIn("Repair the fixture", result.stderr)

    def test_fixture_without_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            metadata = Path(raw_root) / "unlabeled.json"
            metadata.write_text(
                '{"tag_name":"v3.0.1","draft":false,"prerelease":false,'
                '"resolved_ref":"v3.0.1",'
                '"resolved_commit":"0123456789012345678901234567890123456789"}',
                encoding="utf-8",
            )
            result = self.run_resolver(
                "--selector",
                "latest",
                "--metadata-file",
                str(metadata),
            )

        self.assert_report_failure(result, 2, "fixture_version")
        self.assertIn("Add fixture_version", result.stderr)

    def test_fixture_without_commit_is_rejected_without_remote_fallback(self):
        with tempfile.TemporaryDirectory() as raw_root:
            metadata = Path(raw_root) / "unresolved.json"
            metadata.write_text(
                '{"tag_name":"v3.0.1","fixture_version":"v3.0.1",'
                '"draft":false,"prerelease":false,"resolved_ref":"v3.0.1"}',
                encoding="utf-8",
            )
            result = self.run_resolver(
                "--selector",
                "latest",
                "--metadata-file",
                str(metadata),
            )

        self.assert_report_failure(result, 2, "resolved_commit")
        self.assertIn("Add the pinned", result.stderr)

    def test_commit_selector_rejects_unused_fixture_input(self):
        result = self.run_resolver(
            "--selector",
            "commit:0123456789012345678901234567890123456789",
            "--metadata-file",
            self.fixture("latest-release.json"),
        )

        self.assert_report_failure(result, 2, "cannot be used")
        self.assertIn("Omit --metadata-file", result.stderr)

    def test_bash_and_powershell_invocation_forms_keep_resolver_parity(self):
        with tempfile.TemporaryDirectory(prefix="modding api fixture ") as raw_root:
            metadata = Path(raw_root) / "latest fixture.json"
            metadata.write_text(
                Path(self.fixture("latest-release.json")).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            bash_form = self.run_resolver(
                "--selector",
                "latest",
                "--metadata-file",
                str(metadata),
            )
            powershell_form = self.run_resolver(
                "-Selector",
                "latest",
                "-MetadataFile",
                str(metadata),
            )

        self.assertEqual(bash_form.returncode, 0, bash_form.stderr)
        self.assertEqual(powershell_form.returncode, 0, powershell_form.stderr)
        self.assertEqual(powershell_form.stdout, bash_form.stdout)
        self.assertEqual(powershell_form.stderr, bash_form.stderr)

    def test_native_shell_invocations_preserve_output_and_errors(self):
        shells = []
        if os.name != "nt" and shutil.which("bash"):
            shells.append(("bash", shutil.which("bash")))
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell:
            shells.append(("powershell", powershell))
        if not shells:
            self.skipTest("no native Bash or PowerShell host is available")

        with tempfile.TemporaryDirectory(prefix="modding api shell ") as raw_root:
            metadata = Path(raw_root) / "latest fixture.json"
            metadata.write_text(
                Path(self.fixture("latest-release.json")).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            expected = self.run_resolver(
                "--selector",
                "latest",
                "--metadata-file",
                str(metadata),
            )
            for name, shell in shells:
                with self.subTest(shell=name):
                    if name == "bash":
                        command = "exec " + " ".join(
                            (
                                shlex.quote(sys.executable),
                                shlex.quote(str(RESOLVER)),
                                "--selector",
                                shlex.quote("latest"),
                                "--metadata-file",
                                shlex.quote(str(metadata)),
                            )
                        )
                        arguments = [shell, "-lc", command]
                    else:
                        def ps_quote(value):
                            return "'" + value.replace("'", "''") + "'"

                        command = "& " + " ".join(
                            (
                                ps_quote(sys.executable),
                                ps_quote(str(RESOLVER)),
                                "-Selector",
                                ps_quote("latest"),
                                "-MetadataFile",
                                ps_quote(str(metadata)),
                            )
                        ) + "; exit $LASTEXITCODE"
                        arguments = [
                            shell,
                            "-NoProfile",
                            "-NonInteractive",
                            "-Command",
                            command,
                        ]
                    result = subprocess.run(
                        arguments,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        shell=False,
                        check=False,
                        env=os.environ.copy(),
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, expected.stdout)
                    self.assertEqual(result.stderr, expected.stderr)

                    if name == "bash":
                        invalid_arguments = [
                            shell,
                            "-lc",
                            "exec "
                            + " ".join(
                                (
                                    shlex.quote(sys.executable),
                                    shlex.quote(str(RESOLVER)),
                                    "--selector",
                                    shlex.quote("main"),
                                )
                            ),
                        ]
                    else:
                        invalid_arguments = [
                            shell,
                            "-NoProfile",
                            "-NonInteractive",
                            "-Command",
                            "& "
                            + " ".join(
                                (
                                    ps_quote(sys.executable),
                                    ps_quote(str(RESOLVER)),
                                    "-Selector",
                                    ps_quote("main"),
                                )
                            )
                            + "; exit $LASTEXITCODE",
                        ]
                    invalid = subprocess.run(
                        invalid_arguments,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        shell=False,
                        check=False,
                        env=os.environ.copy(),
                    )
                    self.assertEqual(invalid.returncode, 2)
                    self.assertEqual(invalid.stdout, "")
                    self.assertIn("[ERROR REPORT]", invalid.stderr)

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
