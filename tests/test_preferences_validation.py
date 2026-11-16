import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


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
    set_unity_project_path,
    UnityProjectPathError,
    update_config_text,
    validate_preferences,
)
from blasphemous_modding_helper import preferences as preference_module  # noqa: E402
from check_preferences import main as check_preferences_main  # noqa: E402


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

    def run_set_unity_path(self, value):
        return subprocess.run(
            [
                sys.executable,
                str(CHECK_PREFERENCES),
                "--cwd",
                str(self.root),
                "--home",
                str(self.home),
                "--set-unity-project-path",
                str(value),
            ],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def run_set_unity_path_in_process(self, value):
        output = io.StringIO()
        with redirect_stdout(output):
            returncode = check_preferences_main(
                [
                    "--cwd",
                    str(self.root),
                    "--home",
                    str(self.home),
                    "--set-unity-project-path",
                    str(value),
                ]
            )
        return returncode, output.getvalue()

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
        self.assertTrue(Path(fields["PREFERENCES_FILE"]).samefile(self.config))
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

    def test_valid_config_may_omit_unity_project_path(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.write_config(self.valid_config(self.checked_at(now)))

        result = self.run_validation()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("unity_project_path", parse_preferences(self.config))

    def test_targeted_unity_path_update_preserves_unrelated_config(self):
        unity = self.root / "Unity Project"
        (unity / "Assets").mkdir(parents=True)
        self.write_config(
            "# keep header\n"
            "unknown:\n"
            "  nested: [one, two]\n"
            "modding_profile_path: 'profile' # keep profile note\n"
        )

        result = self.run_set_unity_path(unity)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"PREFERENCES_UNITY_PROJECT_PATH={unity.resolve()}", result.stdout)
        values = parse_preferences(self.config)
        self.assertEqual(values["unity_project_path"], str(unity.resolve()))
        self.assertEqual(values["unknown"], {"nested": ["one", "two"]})
        self.assertEqual(values["modding_profile_path"], "profile")
        text = self.config.read_text(encoding="utf-8")
        self.assertIn("# keep header", text)
        self.assertIn("# keep profile note", text)
        self.assertLess(text.index("unknown:\n"), text.index("modding_profile_path:"))

    def test_targeted_unity_path_update_preserves_flow_style_yaml(self):
        unity = self.root / "Unity Flow"
        (unity / "Assets").mkdir(parents=True)
        self.write_config(
            "{modding_profile_path: profile, unknown: [one, two]} # keep inline\n"
        )

        location, project = set_unity_project_path(
            str(unity),
            cwd=self.root,
            home=self.home,
        )

        self.assertEqual(location.scope, "project")
        self.assertEqual(project, unity.resolve())
        values = parse_preferences(self.config)
        self.assertEqual(values["modding_profile_path"], "profile")
        self.assertEqual(values["unknown"], ["one", "two"])
        self.assertEqual(values["unity_project_path"], str(unity.resolve()))
        self.assertIn("# keep inline", self.config.read_text(encoding="utf-8"))

    def test_targeted_unity_path_update_replaces_multiline_flow_value(self):
        unity = self.root / "Unity Flow Multiline"
        (unity / "Assets").mkdir(parents=True)
        self.write_config(
            "{unity_project_path: '/previous\n"
            "  path', modding_profile_path: profile} # keep inline\n"
        )

        result = self.run_set_unity_path(unity)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        values = parse_preferences(self.config)
        self.assertEqual(values["unity_project_path"], str(unity.resolve()))
        self.assertEqual(values["modding_profile_path"], "profile")
        self.assertIn("# keep inline", self.config.read_text(encoding="utf-8"))

    def test_targeted_unity_path_update_accepts_flow_style_trailing_comma(self):
        unity = self.root / "Unity Flow Comma"
        (unity / "Assets").mkdir(parents=True)
        configs = (
            "{modding_profile_path: profile,} # keep inline\n",
            "{\n  modding_profile_path: profile, # keep multiline\n}\n",
        )
        for text in configs:
            with self.subTest(text=text):
                self.write_config(text)

                result = self.run_set_unity_path(unity)

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                values = parse_preferences(self.config)
                self.assertEqual(values["modding_profile_path"], "profile")
                self.assertEqual(values["unity_project_path"], str(unity.resolve()))
                self.assertIn("# keep", self.config.read_text(encoding="utf-8"))

    def test_targeted_unity_path_update_replaces_quoted_block_key(self):
        unity = self.root / "Unity Quoted"
        (unity / "Assets").mkdir(parents=True)
        for key in ("'unity_project_path'", '"unity_project_path"'):
            with self.subTest(key=key):
                self.write_config(
                    f"{key}: '/previous'\n"
                    "modding_profile_path: profile\n"
                )

                result = self.run_set_unity_path(unity)

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                values = parse_preferences(self.config)
                self.assertEqual(values["unity_project_path"], str(unity.resolve()))
                self.assertEqual(values["modding_profile_path"], "profile")
                self.assertEqual(
                    self.config.read_text(encoding="utf-8").count("unity_project_path"),
                    1,
                )

    def test_targeted_unity_path_update_replaces_alias_not_its_anchor(self):
        unity = self.root / "Unity Aliased"
        (unity / "Assets").mkdir(parents=True)
        self.write_config(
            "base_path: &base /previous\n"
            "unity_project_path: *base # keep alias note\n"
            "modding_profile_path: profile\n"
        )

        result = self.run_set_unity_path(unity)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        values = parse_preferences(self.config)
        self.assertEqual(values["base_path"], "/previous")
        self.assertEqual(values["unity_project_path"], str(unity.resolve()))
        text = self.config.read_text(encoding="utf-8")
        self.assertIn("base_path: &base /previous", text)
        self.assertIn("# keep alias note", text)

    def test_targeted_unity_path_update_preserves_uniform_top_level_indent(self):
        unity = self.root / "Unity Indented"
        (unity / "Assets").mkdir(parents=True)
        self.write_config(
            "# keep header\n"
            "    'unknown': {nested: [one, two]}\n"
            "    modding_profile_path: \"profile\" # keep profile note\n"
            "    future: {quoted: 'value'}\n"
        )

        result = self.run_set_unity_path(unity)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        values = parse_preferences(self.config)
        self.assertEqual(values["unity_project_path"], str(unity.resolve()))
        self.assertEqual(values["unknown"], {"nested": ["one", "two"]})
        self.assertEqual(values["modding_profile_path"], "profile")
        self.assertEqual(values["future"], {"quoted": "value"})
        text = self.config.read_text(encoding="utf-8")
        self.assertIn("# keep header", text)
        self.assertIn("# keep profile note", text)
        self.assertIn("\n    unity_project_path:", text)
        self.assertNotIn("\nunity_project_path:", text)
        self.assertLess(text.index("'unknown':"), text.index("modding_profile_path:"))

    def test_targeted_unity_path_update_replaces_block_scalar_values(self):
        unity = self.root / "Unity Block"
        (unity / "Assets").mkdir(parents=True)
        for style in ("|", "|-", "|+", ">", ">-", ">+", "|2", ">2"):
            with self.subTest(style=style):
                self.write_config(
                    "# keep header\n"
                    f"unity_project_path: {style} # keep managed note\n"
                    "  /previous\n"
                    "  path\n"
                    "modding_profile_path: profile # keep profile note\n"
                )

                result = self.run_set_unity_path(unity)

                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                values = parse_preferences(self.config)
                self.assertEqual(values["unity_project_path"], str(unity.resolve()))
                self.assertEqual(values["modding_profile_path"], "profile")
                text = self.config.read_text(encoding="utf-8")
                self.assertIn("# keep header", text)
                self.assertIn("# keep managed note", text)
                self.assertIn("# keep profile note", text)
                self.assertNotIn("/previous", text)
                self.assertEqual(text.count("unity_project_path"), 1)

    def test_targeted_unity_path_invalid_yaml_requires_setup_without_writing(self):
        unity = self.root / "Unity Invalid Config"
        (unity / "Assets").mkdir(parents=True)
        self.write_config("valid: value\nnot a mapping\n")
        before = self.config.read_bytes()

        result = self.run_set_unity_path(unity)

        self.assertEqual(result.returncode, 10)
        fields = self.fields(result)
        self.assertEqual(fields["PREFERENCES_SETUP"], "required")
        self.assertNotIn("PREFERENCES_NEXT_ACTION", fields)
        self.assertIn("Invalid config.yml", fields["PREFERENCES_VALIDATION_REASON"])
        self.assertEqual(self.config.read_bytes(), before)

    def test_targeted_unity_path_parse_failure_preserves_original_configuration(self):
        unity = self.root / "Unity Parse Failure"
        (unity / "Assets").mkdir(parents=True)
        self.write_config("modding_profile_path: profile\n")
        before = self.config.read_bytes()
        original_parse = preference_module._parse_config

        def parse_candidate(text):
            if "unity_project_path" in text:
                raise preference_module.PreferenceError("candidate parse failed")
            return original_parse(text)

        with mock.patch.object(
            preference_module,
            "_parse_config",
            side_effect=parse_candidate,
        ):
            returncode, output = self.run_set_unity_path_in_process(unity)

        self.assertEqual(returncode, 10)
        self.assertIn("PREFERENCES_SETUP=not-required", output)
        self.assertIn("PREFERENCES_NEXT_ACTION=retry-unity-project-path", output)
        self.assertIn("Automated config update", output)
        self.assertEqual(self.config.read_bytes(), before)

    def test_targeted_unity_path_atomic_write_failure_preserves_original(self):
        unity = self.root / "Unity Atomic Failure"
        (unity / "Assets").mkdir(parents=True)
        self.write_config("modding_profile_path: profile\n")
        before = self.config.read_bytes()

        with mock.patch.object(
            preference_module.os,
            "replace",
            side_effect=OSError("atomic replace failed"),
        ):
            returncode, output = self.run_set_unity_path_in_process(unity)

        self.assertEqual(returncode, 10)
        self.assertIn("PREFERENCES_SETUP=not-required", output)
        self.assertIn("PREFERENCES_NEXT_ACTION=retry-unity-project-path", output)
        self.assertIn("atomic replace failed", output)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(list(self.config.parent.glob(".config.yml.*.tmp")), [])

    def test_targeted_unity_path_resolution_cycle_stays_retryable(self):
        unity = self.root / "Unity Cycle"
        unity.mkdir()
        self.write_config("modding_profile_path: profile\n")
        resolve = Path.resolve

        def resolve_with_cycle(path, *args, **kwargs):
            if path == unity:
                raise RuntimeError("Symlink loop")
            return resolve(path, *args, **kwargs)

        with mock.patch.object(Path, "resolve", resolve_with_cycle):
            with self.assertRaises(UnityProjectPathError):
                set_unity_project_path(
                    str(unity),
                    cwd=self.root,
                    home=self.home,
                )

    def test_flow_style_config_update_replaces_existing_and_appends_missing_fields(self):
        self.write_config(
            "{modding_profile_path: 'profile', check_period_days: 7} # keep inline\n"
        )

        updated = update_config_text(
            self.config.read_text(encoding="utf-8"),
            {
                "check_period_days": 14,
                "last_checked_version": read_skill_version(),
            },
        )
        self.config.write_text(updated, encoding="utf-8")

        values = parse_preferences(self.config)
        self.assertEqual(values["check_period_days"], 14)
        self.assertEqual(values["last_checked_version"], read_skill_version())
        self.assertIn("# keep inline", updated)

    def test_config_update_initializes_an_empty_configuration(self):
        updated = update_config_text("", {"check_period_days": 7})
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text(updated, encoding="utf-8")

        self.assertEqual(parse_preferences(self.config), {"check_period_days": 7})

    def test_targeted_unity_path_update_rejects_invalid_path_without_writing(self):
        self.write_config(
            "# keep header\n"
            "modding_profile_path: profile\n"
        )
        before = self.config.read_bytes()
        missing = self.root / "missing-unity"

        result = self.run_set_unity_path(missing)

        self.assertEqual(result.returncode, 10)
        self.assertIn("unity_project_path", result.stdout)
        self.assertNotIn("PREFERENCES_VALIDATION_STATUS", result.stdout)
        self.assertIn("PREFERENCES_SETUP=not-required", result.stdout)
        self.assertIn(
            "PREFERENCES_NEXT_ACTION=retry-unity-project-path",
            result.stdout,
        )
        self.assertEqual(self.config.read_bytes(), before)

    def test_targeted_unity_path_update_requires_existing_config(self):
        unity = self.root / "Unity"
        (unity / "Assets").mkdir(parents=True)

        with self.assertRaises(PreferenceValidationError):
            set_unity_project_path(unity, cwd=self.root, home=self.home)

    def test_targeted_unity_path_rejects_blank_values(self):
        self.write_config("modding_profile_path: profile\n")
        before = self.config.read_bytes()
        for value in ("", "   "):
            with self.subTest(value=value):
                result = self.run_set_unity_path(value)

                self.assertEqual(result.returncode, 10)
                self.assertIn("PREFERENCES_SETUP=not-required", result.stdout)
                self.assertEqual(self.config.read_bytes(), before)

    def test_targeted_unity_path_rejects_symlinked_assets_outside(self):
        outside = self.root / "outside-assets"
        outside.mkdir()
        unity = self.root / "Unity"
        unity.mkdir()
        try:
            (unity / "Assets").symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlink unavailable: {error}")
        self.write_config("modding_profile_path: profile\n")
        before = self.config.read_bytes()

        result = self.run_set_unity_path(unity)

        self.assertEqual(result.returncode, 10)
        self.assertIn("PREFERENCES_SETUP=not-required", result.stdout)
        self.assertEqual(self.config.read_bytes(), before)

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
        self.assertTrue(Path(fields["PREFERENCES_FILE"]).samefile(self.config))

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
