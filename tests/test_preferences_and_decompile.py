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
sys.path.insert(0, str(SCRIPT_ROOT))

from blasphemous_modding_helper.preferences import PreferenceError, parse_preferences


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

    def write_config(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("modding_profile_path: profile\n", encoding="utf-8")

    def test_project_preferences_take_precedence_over_user_preferences(self):
        self.write_config(
            self.home / ".skills" / "blasphemous-modding-helper" / "config.yml"
        )
        project_preferences = (
            self.root / ".skills" / "blasphemous-modding-helper" / "config.yml"
        )
        self.write_config(project_preferences)

        result = self.run_preferences("--cwd", str(self.root), "--home", str(self.home))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "project\n")
        self.assertEqual(result.stderr, "")

    def test_user_preferences_are_selected_when_project_file_is_absent(self):
        self.write_config(
            self.home / ".skills" / "blasphemous-modding-helper" / "config.yml"
        )

        result = self.run_preferences("--cwd", str(self.root), "--home", str(self.home))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "user\n")

    def test_old_preferences_filename_is_not_a_fallback(self):
        self.write_config(
            self.root / ".skills" / "blasphemous-modding-helper" / "preferences.md"
        )

        result = self.run_preferences("--cwd", str(self.root), "--home", str(self.home))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_config_parser_preserves_yaml_scalar_types_and_comments(self):
        config = self.root / "config.yml"
        config.write_text(
            '# caller config\n'
            'quoted_path: "C:\\\\Games\\\\Blasphemous #1" # inline\n'
            "retry_count: 3\n"
            "ratio: 1.5\n"
            "unknown_field: future-value\n",
            encoding="utf-8",
        )

        values = parse_preferences(config, required=("quoted_path",))

        self.assertEqual(values["quoted_path"], "C:\\Games\\Blasphemous #1")
        self.assertEqual(values["retry_count"], 3)
        self.assertEqual(values["ratio"], 1.5)
        self.assertEqual(values["unknown_field"], "future-value")

    def test_config_parser_rejects_malformed_yaml_and_duplicate_keys(self):
        config = self.root / "config.yml"
        config.write_text("valid: value\nnot a mapping\n", encoding="utf-8")
        with self.assertRaises(PreferenceError):
            parse_preferences(config)

        config.write_text("duplicate: one\nduplicate: two\n", encoding="utf-8")
        with self.assertRaises(PreferenceError):
            parse_preferences(config)

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
