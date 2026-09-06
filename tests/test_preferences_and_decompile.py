import os
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
CHECK_PREFERENCES = SCRIPT_ROOT / "check_preferences.py"
DECOMPILE_SOURCE = SCRIPT_ROOT / "decompile_source.py"


class PreferencesAndDecompilerCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.environment = os.environ.copy()
        self.environment["HOME"] = str(self.home)
        self.environment["USERPROFILE"] = str(self.home)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_preferences(self, *arguments):
        return subprocess.run(
            [sys.executable, str(CHECK_PREFERENCES), *arguments],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def run_decompiler(self, *arguments, environment=None):
        return subprocess.run(
            [sys.executable, str(DECOMPILE_SOURCE), *arguments],
            cwd=self.root,
            env=environment or self.environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def write_preferences(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("modding_profile_path: profile\n", encoding="utf-8")

    def test_project_preferences_take_precedence_over_user_preferences(self):
        self.write_preferences(
            self.home / ".skills" / "blasphemous-modding-helper" / "preferences.md"
        )
        project_preferences = (
            self.root / ".skills" / "blasphemous-modding-helper" / "preferences.md"
        )
        self.write_preferences(project_preferences)

        result = self.run_preferences("--cwd", str(self.root), "--home", str(self.home))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "project\n")
        self.assertEqual(result.stderr, "")

    def test_user_preferences_are_selected_when_project_file_is_absent(self):
        self.write_preferences(
            self.home / ".skills" / "blasphemous-modding-helper" / "preferences.md"
        )

        result = self.run_preferences("--cwd", str(self.root), "--home", str(self.home))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "user\n")

    def test_missing_preferences_keeps_empty_success_output(self):
        result = self.run_preferences("--cwd", str(self.root), "--home", str(self.home))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_missing_game_path_fails_before_output_creation(self):
        output = self.root / "source-output"

        result = self.run_decompiler(
            "--platform",
            "Linux",
            "--game-path",
            str(self.root / "missing-game"),
            "--output-path",
            str(output),
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Error [decompile/game-path]", result.stderr)
        self.assertIn("not found", result.stderr)
        self.assertFalse(output.exists())

    def test_missing_steam_launcher_is_reported_without_shell_fallback(self):
        game = self.root / "game"
        (game / "Blasphemous_Data" / "Managed").mkdir(parents=True)
        output = self.root / "source-output"
        environment = self.environment.copy()
        environment["PATH"] = str(self.root / "empty-bin")

        result = self.run_decompiler(
            "--platform",
            "Linux",
            "--game-path",
            str(game),
            "--output-path",
            str(output),
            "--poll-timeout",
            "0.05",
            "--poll-interval",
            "0.01",
            environment=environment,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("steam", result.stderr.lower())
        self.assertIn("manually", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
