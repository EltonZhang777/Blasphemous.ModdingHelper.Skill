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

from blasphemous_modding_helper import logs  # noqa: E402


class BlasphemousModdingLogsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.bepinex = self.root / "BepInEx" / "LogOutput.log"
        self.unity = self.root / "Unity" / "Player.log"
        self.bepinex.parent.mkdir(parents=True)
        self.unity.parent.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def current_process_state(self):
        return {
            "session_id": "fixture-session",
            "log_baseline": logs.capture_log_baselines(
                (self.bepinex, self.unity)
            ),
        }

    def test_collects_bounded_or_full_output_and_identity_metadata(self):
        prefix = "".join(f"noise-{index}\n" for index in range(250))
        self.bepinex.write_text(
            prefix
            + "[Message: ModdingAPI] Registered Mod: RuntimeProject\n"
            + "[Info : BepInEx] Chainloader startup complete\n"
            + "[Info : BepInEx] Loading [RuntimeProject 1.2.3]\n",
            encoding="utf-8",
        )
        self.unity.write_text("Unity startup\n", encoding="utf-8")
        process_state = self.current_process_state()

        # Baseline must represent the pre-launch files; rewrite as the launch
        # would, while keeping the same paths and process metadata.
        self.bepinex.write_text(
            prefix
            + "[Message: ModdingAPI] Registered Mod: RuntimeProject\n"
            + "[Info : BepInEx] Chainloader startup complete\n"
            + "[Info : BepInEx] Loading [RuntimeProject 1.2.3]\n"
            + "current\n",
            encoding="utf-8",
        )
        bounded = logs.collect_log_evidence(
            self.bepinex,
            self.unity,
            process_state,
            "RuntimeProject",
            ("RuntimeProject", "Runtime.Project"),
        )
        full = logs.collect_log_evidence(
            self.bepinex,
            self.unity,
            process_state,
            "RuntimeProject",
            ("RuntimeProject", "Runtime.Project"),
            full=True,
        )

        self.assertTrue(bounded.mod_loaded)
        self.assertEqual(len(bounded.sources[0].output_lines), 200)
        self.assertEqual(len(full.sources[0].output_lines), full.sources[0].total_lines)
        self.assertTrue(any(hit.mod_id == "RuntimeProject" for hit in bounded.hits))
        self.assertTrue(any(hit.mod_name == "RuntimeProject" for hit in bounded.hits))

    def test_stale_source_is_ignored_and_errors_remain_diagnostic(self):
        self.bepinex.write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : Mod Loader] Registered Mod = RuntimeProject\n",
            encoding="utf-8",
        )
        self.unity.write_text("Unity startup\n", encoding="utf-8")
        stale_state = self.current_process_state()
        stale = logs.collect_log_evidence(
            self.bepinex,
            self.unity,
            stale_state,
            "RuntimeProject",
            ("RuntimeProject",),
        )

        self.bepinex.write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : Mod Loader] Registered Mod = RuntimeProject\n"
            "[Info : BepInEx] Loaded [RuntimeProject 1.0.0]\n"
            "[Error : BepInEx] RuntimeProject failed after registration\n",
            encoding="utf-8",
        )
        current = logs.collect_log_evidence(
            self.bepinex,
            self.unity,
            stale_state,
            "RuntimeProject",
            ("RuntimeProject",),
        )

        self.assertFalse(stale.sources[0].current)
        self.assertFalse(stale.ready)
        self.assertFalse(stale.mod_loaded)
        self.assertTrue(current.ready)
        self.assertTrue(current.mod_loaded)
        self.assertTrue(any(hit.kind == "error" for hit in current.hits))
        self.assertTrue(any(hit.mod_id == "RuntimeProject" for hit in current.hits))
        self.assertTrue(any(hit.mod_name == "RuntimeProject" for hit in current.hits))

    def test_missing_and_unconfigured_sources_keep_recovery_warning(self):
        source = logs.read_log_source(
            "Unity",
            None,
            {},
            full=False,
            configured_warning="Set unity_log_dir in preferences.md.",
        )

        self.assertFalse(source.exists)
        self.assertFalse(source.current)
        self.assertEqual(source.warning, "Set unity_log_dir in preferences.md.")

    def test_resolves_windows_and_unix_unity_log_names(self):
        for filename in ("output_log.txt", "Player.log"):
            directory = self.root / filename.replace(".", "-")
            directory.mkdir()
            expected = directory / filename
            expected.write_text("Unity startup\n", encoding="utf-8")

            resolved, warning = logs.resolve_unity_log_path(
                str(directory),
                preference_path=self.root / "preferences.md",
                log_filenames=(filename,),
                cwd=self.root,
            )

            self.assertEqual(resolved, expected)
            self.assertIsNone(warning)


if __name__ == "__main__":
    unittest.main()
