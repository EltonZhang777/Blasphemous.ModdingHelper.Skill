import importlib.util
import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ROOT_RUNNER = REPOSITORY_ROOT / "tests" / "run_blasphemous_modding_test.py"
ACCEPTANCE_RUNNER = REPOSITORY_ROOT / "tests" / "test_modding_api_acceptance.py"
ROOT_TESTS = REPOSITORY_ROOT / "tests"
SCRIPT_TESTS = (
    REPOSITORY_ROOT
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
)


class PythonAcceptanceEntryPointTests(unittest.TestCase):
    def run_entry_point(self, entry_point, *arguments):
        return subprocess.run(
            [sys.executable, str(entry_point), *arguments],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_root_runner_help_describes_python_and_clean_contract(self):
        result = self.run_entry_point(ROOT_RUNNER, "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Python", result.stdout)
        self.assertIn("--require-clean", result.stdout)
        self.assertIn("--python", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_acceptance_runner_help_describes_installer_and_clean_contract(self):
        result = self.run_entry_point(ACCEPTANCE_RUNNER, "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("installer", result.stdout.lower())
        self.assertIn("--require-clean", result.stdout)
        self.assertIn("--python", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_python_behavior_test_entry_points_have_help_contract(self):
        entry_points = (
            ROOT_TESTS / "test_modding_api_lifecycle.py",
            SCRIPT_TESTS / "test_referencing_modding_api.py",
            ROOT_TESTS / "test_modding_api_live.py",
        )
        for entry_point in entry_points:
            with self.subTest(name=entry_point.name):
                result = self.run_entry_point(entry_point, "--help")

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
                self.assertEqual(result.stderr, "")

    def test_live_smoke_requires_explicit_opt_in(self):
        result = self.run_entry_point(
            ROOT_TESTS / "test_modding_api_live.py"
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("opt-in", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_workflow_tests_are_scheduled_once_through_unittest_discovery(self):
        spec = importlib.util.spec_from_file_location("acceptance_runner", ACCEPTANCE_RUNNER)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        invocations = []

        def capture(label, command, **kwargs):
            invocations.append((label, list(command)))
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch.object(runner, "run_command", side_effect=capture), \
                patch.object(runner, "run_installer_surface"), \
                patch.object(runner, "run_check"), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(["--python", sys.executable]), 0)

        root_runs = [
            command
            for label, command in invocations
            if label == "Python deterministic contract surface"
        ]
        self.assertEqual(len(root_runs), 1)
        self.assertIn(str(ROOT_RUNNER), root_runs[0])
        self.assertEqual(len(invocations), 1)

    def test_repository_only_tools_are_outside_the_packaged_skill(self):
        for name in (
            "test_modding_api_acceptance.py",
            "test_modding_api_lifecycle.py",
            "test_modding_api_live.py",
        ):
            with self.subTest(name=name):
                self.assertTrue((ROOT_TESTS / name).is_file())
                self.assertFalse((SCRIPT_TESTS / name).exists())

        self.assertTrue((REPOSITORY_ROOT / "ci" / "audit_rfc2119.py").is_file())
        self.assertFalse((SCRIPT_TESTS / "audit_rfc2119.py").exists())
        self.assertTrue((SCRIPT_TESTS / "test_referencing_modding_api.py").is_file())

    def test_legacy_skill_scripts_and_test_runners_are_absent(self):
        legacy_scripts = sorted(
            path.relative_to(SCRIPT_TESTS).as_posix()
            for path in SCRIPT_TESTS.rglob("*")
            if path.is_file() and path.suffix.lower() in {".js", ".ps1", ".sh"}
        )
        self.assertEqual(legacy_scripts, [])
        for suffix in (".ps1", ".sh"):
            self.assertFalse(
                (REPOSITORY_ROOT / "tests" / f"run_blasphemous_modding_test{suffix}").exists()
            )


if __name__ == "__main__":
    unittest.main()
