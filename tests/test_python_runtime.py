import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
)
CHECK_SCRIPT = SCRIPT_ROOT / "check_python_environment.py"
sys.path.insert(0, str(SCRIPT_ROOT))

from blasphemous_modding_helper import runtime  # noqa: E402


class PythonRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.requirements = self.root / "requirements.txt"
        self.requirements.write_text(
            "# Standard-library-only foundation\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_check(self, *arguments, environment=None):
        return subprocess.run(
            [sys.executable, str(CHECK_SCRIPT), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment or os.environ.copy(),
            check=False,
        )

    def test_public_entry_point_reports_valid_host_runtime(self):
        result = self.run_check(
            "--python",
            sys.executable,
            "--requirements",
            str(self.requirements),
        )

        self.assertEqual(result.returncode, runtime.EXIT_SUCCESS)
        self.assertIn("PYTHON_RUNTIME_STATUS=ok", result.stdout)
        self.assertIn("PYTHON_VERSION=", result.stdout)
        self.assertIn("PYTHON_DEPENDENCY_COUNT=0", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_python3_environment_is_used_when_no_explicit_interpreter_exists(self):
        environment = os.environ.copy()
        environment["PYTHON3"] = sys.executable

        result = self.run_check("--requirements", str(self.requirements), environment=environment)

        self.assertEqual(result.returncode, runtime.EXIT_SUCCESS)
        self.assertIn("PYTHON_RUNTIME_SOURCE=PYTHON3", result.stdout)

    def test_missing_dependency_has_stable_configuration_diagnostic(self):
        self.requirements.write_text(
            "package-that-does-not-exist-for-blasphemous-helper>=1\n",
            encoding="utf-8",
        )

        result = self.run_check(
            "--python",
            sys.executable,
            "--requirements",
            str(self.requirements),
        )

        self.assertEqual(result.returncode, runtime.EXIT_CONFIGURATION)
        self.assertIn("Error [configuration/python-runtime]", result.stderr)
        self.assertIn("Reason: dependency-validation-failed", result.stderr)
        self.assertIn("automatic installation is disabled", result.stderr)
        self.assertIn("Packages installed: none", result.stderr)
        self.assertIn("PYTHON_RUNTIME_STATUS=error", result.stderr)

    def test_missing_manifest_is_a_configuration_failure(self):
        result = self.run_check(
            "--python",
            sys.executable,
            "--requirements",
            str(self.root / "missing.txt"),
        )

        self.assertEqual(result.returncode, runtime.EXIT_CONFIGURATION)
        self.assertIn("Reason: missing-requirements-manifest", result.stderr)

    def test_old_interpreter_is_rejected(self):
        with mock.patch.object(runtime, "_probe_interpreter", return_value=(3, 8, 10)):
            with self.assertRaises(runtime.PythonEnvironmentError) as failure:
                runtime.resolve_interpreter(sys.executable)

        self.assertEqual(failure.exception.kind, "incompatible-interpreter")
        self.assertEqual(failure.exception.code, runtime.EXIT_CONFIGURATION)

    def test_malformed_requirements_are_rejected(self):
        self.requirements.write_text("-e git+https://example.test/repo.git\n", encoding="utf-8")

        with self.assertRaises(runtime.PythonEnvironmentError) as failure:
            runtime.parse_requirements(self.requirements)

        self.assertEqual(failure.exception.kind, "invalid-requirements-manifest")

    def test_nonzero_external_command_is_not_python_environment_failure(self):
        result = runtime.run_command(
            (sys.executable, "-c", "import sys; sys.exit(7)"),
        )

        self.assertEqual(result.returncode, 7)
        self.assertFalse(result.succeeded)
        with self.assertRaises(runtime.CommandExecutionError):
            runtime.require_success(result, "fixture command")
        self.assertFalse(runtime.is_python_environment_failure(runtime.CommandExecutionError("x", result)))

    def test_external_command_uses_argument_array_and_shell_false(self):
        completed = subprocess.CompletedProcess(
            args=["fixture"],
            returncode=0,
            stdout="ok",
            stderr="",
        )
        with mock.patch.object(runtime.subprocess, "run", return_value=completed) as runner:
            result = runtime.run_command(("fixture", "value with spaces"))

        self.assertTrue(result.succeeded)
        arguments = runner.call_args.args[0]
        keywords = runner.call_args.kwargs
        self.assertEqual(arguments, ["fixture", "value with spaces"])
        self.assertFalse(keywords["shell"])

    def test_external_command_accepts_standard_env_keyword(self):
        completed = subprocess.CompletedProcess(
            args=["fixture"],
            returncode=0,
            stdout="ok",
            stderr="",
        )
        with mock.patch.object(runtime.subprocess, "run", return_value=completed) as runner:
            runtime.run_command(("fixture",), env={"ONLY_FOR_FIXTURE": "1"})

        self.assertEqual(runner.call_args.kwargs["env"], {"ONLY_FOR_FIXTURE": "1"})

    def test_process_start_uses_argument_array_and_shell_false(self):
        with mock.patch.object(runtime.subprocess, "Popen", return_value=mock.Mock()) as starter:
            runtime.start_process(
                ("fixture", "value with spaces"),
                cwd=self.root,
                start_new_session=True,
            )

        self.assertEqual(
            starter.call_args.args[0],
            ["fixture", "value with spaces"],
        )
        self.assertEqual(starter.call_args.kwargs["cwd"], str(self.root))
        self.assertTrue(starter.call_args.kwargs["start_new_session"])
        self.assertFalse(starter.call_args.kwargs["shell"])

    def test_compatible_release_constraint_uses_the_next_significant_component(self):
        self.assertTrue(runtime._satisfies_version("1.4.9", "~=", "1.4"))
        self.assertFalse(runtime._satisfies_version("2.0.0", "~=", "1.4"))
        self.assertTrue(runtime._satisfies_version("1.4.6", "~=", "1.4.5"))
        self.assertFalse(runtime._satisfies_version("1.5.0", "~=", "1.4.5"))

    def test_classified_runtime_errors_are_the_only_setup_retry_signal(self):
        runtime_error = runtime.PythonEnvironmentError("probe", "message", "hint")
        command_result = runtime.CommandResult(("git",), 1, stderr="network failure")

        self.assertTrue(runtime.is_python_environment_failure(runtime_error))
        self.assertFalse(
            runtime.is_python_environment_failure(runtime.CommandExecutionError("git", command_result))
        )

    def test_known_import_failure_is_classified_for_setup_retry(self):
        error = ModuleNotFoundError("missing dependency", name="missing_dependency")

        classified = runtime.classify_import_failure(error)

        self.assertEqual(classified.kind, "dependency-import-failed")
        self.assertTrue(runtime.is_python_environment_failure(classified))


if __name__ == "__main__":
    unittest.main()
