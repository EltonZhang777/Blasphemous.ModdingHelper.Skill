import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT_ROOT))

from blasphemous_modding_helper.preferences import (  # noqa: E402
    parse_preferences,
    read_skill_version,
    PreferenceValidationError,
    validate_preferences,
)


CHECK_PREFERENCES = SCRIPT_ROOT / "check_preferences.py"


class PreferencesValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.environment = os.environ.copy()
        self.environment["HOME"] = str(self.home)
        self.environment["USERPROFILE"] = str(self.home)
        self.config = self.root / ".skills" / "blasphemous-modding-helper" / "config.yml"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_config(self, text):
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text(text, encoding="utf-8")

    def run_validation(self):
        return subprocess.run(
            [
                sys.executable,
                str(CHECK_PREFERENCES),
                "--cwd",
                str(self.root),
                "--home",
                str(self.home),
                "--validate",
            ],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    @staticmethod
    def fields(result):
        return dict(
            line.split("=", 1)
            for line in result.stdout.splitlines()
            if "=" in line
        )

    @staticmethod
    def checked_at(now):
        return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def valid_config(self, checked_at, version=None, period=7):
        return (
            "# keep header\n"
            "unknown:\n"
            "  nested: [one, two]\n"
            "modding_profile_path: profile # keep profile note\n"
            f"last_checked_version: {version or read_skill_version()}\n"
            f"last_checked_time: '{checked_at}'\n"
            f"check_period_days: {period}\n"
        )

    def test_first_validation_writes_default_metadata_and_preserves_content(self):
        self.write_config(
            "# keep header\n"
            "unknown:\n"
            "  nested: [one, two]\n"
            "modding_profile_path: profile # keep profile note\n"
        )

        result = self.run_validation()

        self.assertEqual(result.returncode, 0, result.stderr)
        fields = self.fields(result)
        self.assertEqual(fields["PREFERENCES_VALIDATION_STATUS"], "normalized")
        self.assertEqual(fields["PREFERENCES_VALIDATION_TRIGGER"], "first-validation")
        self.assertEqual(fields["PREFERENCES_CHECK_PERIOD_DAYS"], "7")
        self.assertEqual(
            fields["PREFERENCES_UPDATED_FIELDS"],
            "last_checked_time,last_checked_version,check_period_days",
        )
        values = parse_preferences(self.config)
        self.assertEqual(values["unknown"], {"nested": ["one", "two"]})
        self.assertEqual(values["check_period_days"], 7)
        self.assertEqual(values["last_checked_version"], read_skill_version())
        self.assertIsInstance(values["last_checked_time"], str)
        text = self.config.read_text(encoding="utf-8")
        self.assertIn("# keep header", text)
        self.assertIn("# keep profile note", text)
        self.assertLess(text.index("unknown:\n"), text.index("modding_profile_path:"))

    def test_current_version_change_triggers_validation(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.write_config(self.valid_config(self.checked_at(now), version="1.0.0"))

        result = self.run_validation()

        self.assertEqual(result.returncode, 0, result.stderr)
        fields = self.fields(result)
        self.assertEqual(fields["PREFERENCES_VALIDATION_STATUS"], "passed")
        self.assertEqual(fields["PREFERENCES_VALIDATION_TRIGGER"], "version-changed")
        self.assertEqual(parse_preferences(self.config)["last_checked_version"], read_skill_version())

    def test_missing_metadata_triggers_validation(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.write_config(
            "modding_profile_path: profile\n"
            f"last_checked_time: '{self.checked_at(now)}'\n"
            "check_period_days: 7\n"
        )

        result = self.run_validation()

        self.assertEqual(result.returncode, 0, result.stderr)
        fields = self.fields(result)
        self.assertEqual(fields["PREFERENCES_VALIDATION_STATUS"], "passed")
        self.assertEqual(fields["PREFERENCES_VALIDATION_TRIGGER"], "metadata-missing")

    def test_missing_period_is_initialized_after_valid_metadata(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.write_config(
            self.valid_config(self.checked_at(now)).replace(
                "check_period_days: 7\n", ""
            )
        )

        result = validate_preferences(cwd=self.root, home=self.home, now=now)

        self.assertEqual(result.status, "normalized")
        self.assertEqual(result.trigger, "period-missing")
        self.assertEqual(parse_preferences(self.config)["check_period_days"], 7)

    def test_current_config_within_period_skips_and_does_not_write(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.write_config(self.valid_config(self.checked_at(now - timedelta(days=1))))
        before = self.config.read_bytes()

        result = self.run_validation()

        self.assertEqual(result.returncode, 0, result.stderr)
        fields = self.fields(result)
        self.assertEqual(fields["PREFERENCES_VALIDATION_STATUS"], "skipped")
        self.assertEqual(fields["PREFERENCES_VALIDATION_TRIGGER"], "within-period")
        self.assertEqual(fields["PREFERENCES_UPDATED_FIELDS"], "")
        self.assertEqual(self.config.read_bytes(), before)

    def test_elapsed_period_uses_strictly_greater_than(self):
        fixed_now = datetime(2030, 1, 8, tzinfo=timezone.utc)
        self.write_config(
            self.valid_config(
                self.checked_at(fixed_now - timedelta(days=7)),
                period=7,
            )
        )

        result = validate_preferences(
            cwd=self.root,
            home=self.home,
            now=fixed_now,
        )

        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.trigger, "within-period")
        self.write_config(
            self.valid_config(
                self.checked_at(fixed_now - timedelta(days=7, seconds=1)),
                period=7,
            )
        )

        result = validate_preferences(cwd=self.root, home=self.home, now=fixed_now)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.trigger, "period-elapsed")

    def test_positive_float_period_is_floored_and_stored(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.write_config(self.valid_config(self.checked_at(now), period="7.9"))

        result = self.run_validation()

        self.assertEqual(result.returncode, 0, result.stderr)
        fields = self.fields(result)
        self.assertEqual(fields["PREFERENCES_VALIDATION_STATUS"], "normalized")
        self.assertEqual(fields["PREFERENCES_VALIDATION_TRIGGER"], "period-normalized")
        self.assertEqual(parse_preferences(self.config)["check_period_days"], 7)

    def test_invalid_periods_fail_without_replacing_the_value(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        invalid_values = ("0.5", "0", "-1", "nan", "inf", "null", "[1, 2]", '"7"')
        for invalid in invalid_values:
            with self.subTest(period=invalid):
                text = self.valid_config(self.checked_at(now), period=invalid)
                self.write_config(text)
                before = self.config.read_bytes()

                result = self.run_validation()

                self.assertEqual(result.returncode, 10, result.stdout)
                self.assertIn("check_period_days", result.stdout)
                self.assertEqual(self.config.read_bytes(), before)

    def test_date_overflow_periods_fail_without_replacing_the_value(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        for invalid in ("1000000000", "100000000000000000000000"):
            with self.subTest(period=invalid):
                self.write_config(self.valid_config(self.checked_at(now), period=invalid))
                before = self.config.read_bytes()

                result = self.run_validation()

                self.assertEqual(result.returncode, 10, result.stdout)
                self.assertIn("check_period_days", result.stdout)
                self.assertEqual(self.config.read_bytes(), before)

    def test_invalid_yaml_and_future_metadata_route_to_setup(self):
        self.write_config("valid: value\nnot a mapping\n")
        before = self.config.read_bytes()

        result = self.run_validation()

        self.assertEqual(result.returncode, 10)
        fields = self.fields(result)
        self.assertEqual(fields["PREFERENCES_VALIDATION_STATUS"], "failed")
        self.assertEqual(fields["PREFERENCES_SETUP"], "required")
        self.assertIn(str(self.config), fields["PREFERENCES_FILE"])
        self.assertIn("Invalid config.yml", fields["PREFERENCES_VALIDATION_REASON"])
        self.assertEqual(self.config.read_bytes(), before)

        future = datetime.now(timezone.utc) + timedelta(days=1)
        self.write_config(self.valid_config(self.checked_at(future)))
        result = self.run_validation()

        self.assertEqual(result.returncode, 0, result.stderr)
        fields = self.fields(result)
        self.assertEqual(fields["PREFERENCES_VALIDATION_STATUS"], "passed")
        self.assertEqual(fields["PREFERENCES_VALIDATION_TRIGGER"], "metadata-invalid")

    def test_missing_config_reports_setup_recovery(self):
        result = self.run_validation()

        self.assertEqual(result.returncode, 10)
        fields = self.fields(result)
        self.assertEqual(fields["PREFERENCES_VALIDATION_STATUS"], "failed")
        self.assertEqual(fields["PREFERENCES_SETUP"], "required")

    def test_invalid_project_config_does_not_fall_back_to_user_scope(self):
        self.write_config("check_period_days: 0\n")
        user_config = self.home / ".skills" / "blasphemous-modding-helper" / "config.yml"
        user_config.parent.mkdir(parents=True, exist_ok=True)
        user_config.write_text(
            "modding_profile_path: user-profile\n",
            encoding="utf-8",
        )

        result = self.run_validation()

        self.assertEqual(result.returncode, 10)
        fields = self.fields(result)
        self.assertEqual(fields["PREFERENCES_SCOPE"], "project")
        self.assertIn(str(self.config), fields["PREFERENCES_FILE"])

    def test_validation_failure_retains_the_selected_scope(self):
        self.write_config("check_period_days: 0\n")
        user_config = self.home / ".skills" / "blasphemous-modding-helper" / "config.yml"
        user_config.parent.mkdir(parents=True, exist_ok=True)
        user_config.write_text("modding_profile_path: user-profile\n", encoding="utf-8")

        with self.assertRaises(PreferenceValidationError) as failure:
            validate_preferences(cwd=self.root, home=self.home)

        self.assertEqual(failure.exception.location.scope, "project")
        self.assertEqual(failure.exception.location.path, self.config.resolve())


if __name__ == "__main__":
    unittest.main()
