import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLI = (
    REPOSITORY_ROOT
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
    / "analyze_save.py"
)


class SaveAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.temp_root = self.root / "os temp"
        self.temp_root.mkdir()
        self.work = self.root / "caller repo"
        self.work.mkdir()
        self.config = (
            self.work / ".skills" / "blasphemous-modding-helper" / "config.yml"
        )
        self.config.parent.mkdir(parents=True)
        self.config.write_bytes(b"not: [valid yaml")
        self.config_hash = hashlib.sha256(self.config.read_bytes()).hexdigest()
        self.config_mtime = self.config.stat().st_mtime_ns

    def tearDown(self):
        self.temp_dir.cleanup()

    def cli_environment(self, extra_env=None):
        environment = os.environ.copy()
        environment["TEMP"] = str(self.temp_root)
        environment["TMP"] = str(self.temp_root)
        environment["TMPDIR"] = str(self.temp_root)
        environment["HOME"] = str(self.work)
        environment["USERPROFILE"] = str(self.work)
        environment["PYTHONIOENCODING"] = "utf-8"
        if extra_env:
            environment.update(extra_env)
        return environment

    def run_cli(self, *arguments, extra_env=None, cwd=None):
        return subprocess.run(
            [sys.executable, str(CLI), *arguments],
            cwd=str(cwd or self.work),
            env=self.cli_environment(extra_env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )

    def vanilla_bytes(self, value):
        decoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
        return base64.b64encode(decoded)

    def modding_bytes(self, *payloads):
        lines = []
        for identifier, payload in payloads:
            lines.extend((identifier, json.dumps(payload, ensure_ascii=False)))
        return ("\n".join(lines) + "\n").encode("utf-8")

    def shadow_sitecustomize(self):
        directory = self.root / "shadow python"
        directory.mkdir()
        (directory / "sitecustomize.py").write_text(
            "\n".join(
                [
                    "import os",
                    "import tempfile",
                    "import uuid",
                    "",
                    "_original_mkdtemp = tempfile.mkdtemp",
                    "",
                    "def _mkdtemp(*args, **kwargs):",
                    "    fixed = os.environ.get('SAVE_ANALYSIS_TEST_STAGING')",
                    "    if fixed and kwargs.get('prefix') == '.staging-':",
                    "        return fixed",
                    "    return _original_mkdtemp(*args, **kwargs)",
                    "",
                    "tempfile.mkdtemp = _mkdtemp",
                    "fixed_uuid = os.environ.get('SAVE_ANALYSIS_TEST_UUID')",
                    "if fixed_uuid:",
                    "    uuid.uuid4 = lambda: uuid.UUID(fixed_uuid)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return directory

    def test_vanilla_save_is_analyzed_without_configuration(self):
        source = self.root / "Unicode 存档.bin"
        payload = {
            "$type": "Demo.Save, Assembly-CSharp",
            "unknown": {"nested": [1, {"kept": "值"}]},
        }
        source.write_bytes(self.vanilla_bytes(payload))
        before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        before_mtime = source.stat().st_mtime_ns

        result = self.run_cli(str(source))

        self.assertEqual(result.returncode, 0, result.stderr)
        run_root = Path(result.stdout.strip())
        self.assertTrue(run_root.is_absolute())
        self.assertTrue(run_root.is_dir())
        self.assertEqual(run_root.parent, self.temp_root / "blasphemous-save-analysis")

        manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "success")
        self.assertEqual(manifest["inputs"][0]["format"], "vanilla-base64-json")
        self.assertEqual(manifest["inputs"][0]["parse_status"], "ok")
        self.assertEqual(manifest["inputs"][0]["bytes"], len(source.read_bytes()))
        self.assertEqual(manifest["inputs"][0]["sha256"], before_hash)

        chunk = json.loads(
            (run_root / manifest["inputs"][0]["artifacts"]["chunk"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(chunk["source"]["path"], str(source.resolve()))
        self.assertEqual(chunk["data_shape"]["type"], "object")
        member_types = {
            member["name"]: member["value_type"]
            for member in chunk["data_shape"]["members"]
        }
        self.assertEqual(member_types["$type"], "string")
        self.assertEqual(member_types["unknown"], "object")
        self.assertNotIn("值", json.dumps(chunk, ensure_ascii=False))

        full_text = (run_root / manifest["inputs"][0]["artifacts"]["full"]).read_text(
            encoding="utf-8"
        )
        self.assertTrue(full_text.endswith("\n"))
        self.assertIn('\n    "$type"', full_text)
        self.assertEqual(json.loads(full_text), payload)
        summary = (run_root / "summary.txt").read_text(encoding="utf-8")
        self.assertIn("Status: success", summary)
        self.assertIn("Format: vanilla-base64-json", summary)
        self.assertIn("Top-level keys: 2", summary)

        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before_hash)
        self.assertEqual(source.stat().st_mtime_ns, before_mtime)
        self.assertEqual(hashlib.sha256(self.config.read_bytes()).hexdigest(), self.config_hash)
        self.assertEqual(self.config.stat().st_mtime_ns, self.config_mtime)
        self.assertEqual(list(self.work.iterdir()), [self.work / ".skills"])

    def test_cli_contract_separates_misuse_from_fatal_decode_failure(self):
        help_result = self.run_cli("--help")
        self.assertEqual(help_result.returncode, 0)
        help_text = help_result.stdout.casefold()
        for phrase in ("read-only", "configuration", "manifest", "full artifact"):
            self.assertIn(phrase, help_text)

        for arguments in (
            (),
            ("one", "two"),
            ("--include-full", "input"),
            ("--no-full", "input"),
        ):
            with self.subTest(arguments=arguments):
                misuse = self.run_cli(*arguments)
                self.assertEqual(misuse.returncode, 2)
                self.assertTrue(misuse.stderr)

        invalid = self.root / "invalid.save"
        invalid.write_bytes(b"not base64!")
        fatal = self.run_cli(str(invalid))
        self.assertEqual(fatal.returncode, 1)
        self.assertIn("Reason: unsupported-format", fatal.stderr)

    def test_nonstandard_json_and_unwritable_full_text_fail_without_staging(self):
        nonstandard = self.root / "nonstandard.save"
        nonstandard.write_bytes(base64.b64encode(b'{"value": NaN}'))
        result = self.run_cli(str(nonstandard))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Reason: invalid-json", result.stderr)

        overflow = self.root / "overflow.save"
        overflow.write_bytes(base64.b64encode(b'{"value": 1e999}'))
        result = self.run_cli(str(overflow))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Reason: invalid-json", result.stderr)

        surrogate = self.root / "surrogate.save"
        surrogate.write_bytes(base64.b64encode(b'{"value":"\\ud800"}'))
        result = self.run_cli(str(surrogate))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        analysis_root = self.temp_root / "blasphemous-save-analysis"
        staging = list(analysis_root.glob(".staging-*")) if analysis_root.exists() else []
        self.assertEqual(staging, [])

    def test_repeated_runs_publish_unique_complete_directories(self):
        source = self.root / "save.bin"
        source.write_bytes(self.vanilla_bytes({"value": 1}))

        first = self.run_cli(str(source))
        second = self.run_cli(str(source))

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(first.stdout, second.stdout)
        for output in (first.stdout, second.stdout):
            run_root = Path(output.strip())
            self.assertTrue((run_root / "manifest.json").is_file())
            self.assertTrue((run_root / "summary.txt").is_file())
            self.assertTrue((run_root / "full" / "input-1.json").is_file())

    def test_concurrent_runs_publish_distinct_complete_directories(self):
        source = self.root / "concurrent save.bin"
        source.write_bytes(self.vanilla_bytes({"value": 1}))
        command = [sys.executable, str(CLI), str(source)]
        environment = self.cli_environment()
        processes = [
            subprocess.Popen(
                command,
                cwd=str(self.work),
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
            )
            for _ in range(2)
        ]
        results = [process.communicate(timeout=60) for process in processes]

        for process, (stdout, stderr) in zip(processes, results):
            self.assertEqual(process.returncode, 0, stderr)
            self.assertTrue((Path(stdout.strip()) / "manifest.json").is_file())
        self.assertNotEqual(results[0][0].strip(), results[1][0].strip())
        analysis_root = self.temp_root / "blasphemous-save-analysis"
        self.assertEqual(list(analysis_root.glob(".staging-*")), [])

    def test_unsafe_output_root_file_is_rejected(self):
        source = self.root / "save.bin"
        source.write_bytes(self.vanilla_bytes({"value": 1}))
        analysis_root = self.temp_root / "blasphemous-save-analysis"
        analysis_root.write_bytes(b"sentinel")

        unsafe_root = self.run_cli(str(source))

        self.assertEqual(unsafe_root.returncode, 1)
        self.assertIn("Reason: unsafe-output-root", unsafe_root.stderr)
        self.assertEqual(analysis_root.read_bytes(), b"sentinel")

    def test_input_output_overlap_is_rejected(self):
        analysis_root = self.temp_root / "blasphemous-save-analysis"
        analysis_root.mkdir()
        overlapping_source = analysis_root / "input.save"
        overlapping_source.write_bytes(self.vanilla_bytes({"value": 2}))
        overlap = self.run_cli(str(overlapping_source))

        self.assertEqual(overlap.returncode, 1)
        self.assertIn("Reason: input-output-overlap", overlap.stderr)
        self.assertEqual(
            [path.name for path in analysis_root.iterdir()],
            ["input.save"],
        )
        self.assertEqual(list(analysis_root.glob(".staging-*")), [])

    def test_output_root_symlink_does_not_redirect_artifacts(self):
        source = self.root / "save.bin"
        source.write_bytes(self.vanilla_bytes({"value": 1}))
        outside = self.root / "outside output"
        outside.mkdir()
        analysis_root = self.temp_root / "blasphemous-save-analysis"
        try:
            os.symlink(outside, analysis_root, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlinks unavailable: {error}")

        result = self.run_cli(str(source))

        self.assertEqual(result.returncode, 1)
        self.assertIn("Reason: unsafe-output-root", result.stderr)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(source.read_bytes(), self.vanilla_bytes({"value": 1}))

    def test_staging_hard_link_cannot_redirect_an_artifact_write(self):
        source = self.root / "save.bin"
        source.write_bytes(self.vanilla_bytes({"value": 1}))
        analysis_root = self.temp_root / "blasphemous-save-analysis"
        analysis_root.mkdir()
        staging = analysis_root / ".staging-fixed"
        staging.mkdir()
        external = self.root / "external sentinel"
        external.write_bytes(b"do not overwrite")
        try:
            os.link(external, staging / "manifest.json")
        except OSError as error:
            self.skipTest(f"hard links unavailable: {error}")
        shadow = self.shadow_sitecustomize()

        result = self.run_cli(
            str(source),
            extra_env={
                "PYTHONPATH": str(shadow),
                "SAVE_ANALYSIS_TEST_STAGING": str(staging),
            },
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Reason: unsafe-output-path", result.stderr)
        self.assertEqual(external.read_bytes(), b"do not overwrite")
        self.assertFalse(staging.exists())
        self.assertEqual(list(analysis_root.iterdir()), [])

    def test_run_collision_preserves_published_output(self):
        source = self.root / "save.bin"
        source.write_bytes(self.vanilla_bytes({"value": 1}))
        fixed_uuid = "00000000-0000-4000-8000-000000000001"
        shadow = self.shadow_sitecustomize()
        environment = {
            "PYTHONPATH": str(shadow),
            "SAVE_ANALYSIS_TEST_UUID": fixed_uuid,
        }

        first = self.run_cli(str(source), extra_env=environment)
        self.assertEqual(first.returncode, 0, first.stderr)
        run_root = Path(first.stdout.strip())
        before = {
            path.relative_to(run_root).as_posix(): path.read_bytes()
            for path in run_root.rglob("*")
            if path.is_file()
        }
        source.write_bytes(self.vanilla_bytes({"value": 2}))

        second = self.run_cli(str(source), extra_env=environment)

        self.assertEqual(second.returncode, 1)
        self.assertIn("Reason: run-collision", second.stderr)
        after = {
            path.relative_to(run_root).as_posix(): path.read_bytes()
            for path in run_root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)
        analysis_root = self.temp_root / "blasphemous-save-analysis"
        self.assertEqual(list(analysis_root.glob(".staging-*")), [])

    def test_missing_configuration_and_external_sentinels_remain_untouched(self):
        source_directory = self.root / "input sentinels"
        source_directory.mkdir()
        source = source_directory / "Unicode 存档.bin"
        source.write_bytes(self.vanilla_bytes({"value": 1}))
        source_files = {path.name for path in source_directory.iterdir()}
        fresh_home = self.root / "fresh caller"
        fresh_home.mkdir()
        profile = self.root / "profile sentinel"
        profile.mkdir()
        (profile / "keep.txt").write_text("profile", encoding="utf-8")
        game = self.root / "game sentinel"
        game.mkdir()
        (game / "keep.txt").write_text("game", encoding="utf-8")

        result = self.run_cli(
            str(source),
            extra_env={
                "HOME": str(fresh_home),
                "USERPROFILE": str(fresh_home),
            },
            cwd=fresh_home,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(fresh_home.iterdir()), [])
        self.assertEqual({path.name for path in source_directory.iterdir()}, source_files)
        self.assertEqual((profile / "keep.txt").read_text(encoding="utf-8"), "profile")
        self.assertEqual((game / "keep.txt").read_text(encoding="utf-8"), "game")
        self.assertFalse((profile / "blasphemous-save-analysis").exists())
        self.assertFalse((game / "blasphemous-save-analysis").exists())

    def test_moddingapi_records_preserve_duplicate_identifiers_and_order(self):
        source = self.root / "renamed-no-extension.bin"
        source.write_bytes(
            self.modding_bytes(
                (
                    "demo.mod1",
                    {
                        "coins": 1,
                        "name": "值",
                        "separator": "值\u2028行",
                        "note": "x" * 2000,
                    },
                ),
                ("demo.mod2", {"coins": 2}),
                ("demo.mod1", {"coins": 3, "$type": "Demo.State"}),
            )
        )
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        before_mtime = source.stat().st_mtime_ns

        result = self.run_cli(str(source))

        self.assertEqual(result.returncode, 0, result.stderr)
        run_root = Path(result.stdout.strip())
        manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
        item = manifest["inputs"][0]
        self.assertEqual(item["format"], "moddingapi-records")
        self.assertEqual(item["role"], "moddingapi")
        self.assertEqual(item["counts"]["valid_records"], 3)
        self.assertEqual(item["artifacts"]["full"], "full/input-1.txt")

        chunk = json.loads(
            (run_root / item["artifacts"]["chunk"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            [record["identifier"] for record in chunk["records"]],
            ["demo.mod1", "demo.mod2", "demo.mod1"],
        )
        self.assertEqual(
            [record["identifier_line"] for record in chunk["records"]],
            [1, 3, 5],
        )
        self.assertEqual(
            [record["payload_line"] for record in chunk["records"]],
            [2, 4, 6],
        )
        member_types = {
            member["name"]: member["value_type"]
            for member in chunk["records"][0]["payload_shape"]["members"]
        }
        self.assertEqual(member_types["name"], "string")
        self.assertEqual(member_types["note"], "string")
        self.assertNotIn("值", json.dumps(chunk, ensure_ascii=False))
        self.assertNotIn("x" * 100, json.dumps(chunk, ensure_ascii=False))
        self.assertIn(
            "$type",
            [
                member["name"]
                for member in chunk["records"][2]["payload_shape"]["members"]
            ],
        )

        full_text = (run_root / item["artifacts"]["full"]).read_text(encoding="utf-8")
        self.assertTrue(full_text.startswith("demo.mod1\n{\n"))
        self.assertIn('\n    "name": "值"', full_text)
        self.assertIn('\n    "separator": "值\u2028行"', full_text)
        self.assertIn('\n    "$type": "Demo.State"\n}', full_text)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(full_text)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        self.assertEqual(source.stat().st_mtime_ns, before_mtime)

    def test_moddingapi_malformed_and_incomplete_records_remain_visible(self):
        source = self.root / "mixed-records.bin"
        oversized_payload = "not-json-" + "x" * 600
        source.write_bytes(
            ("bad.mod\n" + oversized_payload + "\n\ngood.mod\n").encode("utf-8")
            + json.dumps({"ok": True}).encode("utf-8")
            + b"\nincomplete.mod\n"
        )

        result = self.run_cli(str(source))

        self.assertEqual(result.returncode, 0, result.stderr)
        run_root = Path(result.stdout.strip())
        manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
        item = manifest["inputs"][0]
        self.assertEqual(item["parse_status"], "ok")
        self.assertEqual(
            item["counts"],
            {
                "valid_records": 1,
                "invalid_records": 1,
                "incomplete_records": 1,
                "blank_lines": 1,
            },
        )
        chunk = json.loads(
            (run_root / item["artifacts"]["chunk"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            [record["status"] for record in chunk["records"]],
            ["invalid", "blank", "valid", "incomplete"],
        )
        self.assertEqual(
            chunk["records"][0]["raw_payload_preview"],
            oversized_payload[:512],
        )
        self.assertEqual(chunk["records"][0]["raw_payload_chars"], 609)
        self.assertTrue(chunk["records"][0]["raw_payload_truncated"])
        self.assertEqual(chunk["records"][0]["payload_line"], 2)
        self.assertEqual(chunk["records"][1]["line"], 3)
        self.assertEqual(chunk["records"][2]["payload_line"], 5)
        self.assertEqual(chunk["records"][3]["identifier"], "incomplete.mod")
        self.assertIsNone(chunk["records"][3]["payload_line"])

        full_text = (run_root / item["artifacts"]["full"]).read_text(encoding="utf-8")
        self.assertIn("bad.mod\n" + oversized_payload + "\n\ngood.mod\n", full_text)
        self.assertTrue(full_text.endswith("incomplete.mod\n"))
        summary = (run_root / "summary.txt").read_text(encoding="utf-8")
        self.assertIn("Status: ok", summary)
        self.assertIn("Valid records: 1", summary)
        self.assertIn("Invalid records: 1", summary)
        self.assertIn("Incomplete records: 1", summary)

    def test_moddingapi_format_is_recognized_when_every_payload_is_malformed(self):
        source = self.root / "damaged-records.bin"
        source.write_bytes(b"first.mod\n{\"open\": true\nsecond.mod\nnot-json\n")

        result = self.run_cli(str(source))

        self.assertEqual(result.returncode, 0, result.stderr)
        run_root = Path(result.stdout.strip())
        manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
        item = manifest["inputs"][0]
        self.assertEqual(item["format"], "moddingapi-records")
        self.assertEqual(item["counts"]["valid_records"], 0)
        self.assertEqual(item["counts"]["invalid_records"], 2)
        self.assertEqual(
            item["warnings"],
            ["2 invalid payload record(s)"],
        )
        chunk = json.loads(
            (run_root / item["artifacts"]["chunk"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            [record["raw_payload_preview"] for record in chunk["records"]],
            ['{"open": true', "not-json"],
        )

    def test_directory_analyzes_every_supported_role_without_recursing(self):
        source = self.root / "save directory"
        source.mkdir()
        vanilla = self.vanilla_bytes({"value": "值"})
        modding = self.modding_bytes(("demo.mod", {"ok": True}))
        expected_roles = {
            "app_settings": ("vanilla-global-settings", "vanilla-base64-json"),
            "app_settings_backup": (
                "vanilla-global-settings-backup",
                "vanilla-base64-json",
            ),
            "app_settings_modded": (
                "moddingapi-global-settings",
                "moddingapi-records",
            ),
            "app_settings_modded_backup": (
                "moddingapi-global-settings-backup",
                "moddingapi-records",
            ),
            "savegame_0.save": ("vanilla-player-save", "vanilla-base64-json"),
            "savegame_0.save_backup": (
                "vanilla-player-save-backup",
                "vanilla-base64-json",
            ),
            "savegame_0_modded.save": (
                "moddingapi-slot-companion",
                "moddingapi-records",
            ),
            "savegame_0_modded.save_backup": (
                "moddingapi-slot-companion-backup",
                "moddingapi-records",
            ),
        }
        for name, (_, detected_format) in expected_roles.items():
            content = vanilla if detected_format == "vanilla-base64-json" else modding
            (source / name).write_bytes(content)
        before = {
            name: hashlib.sha256((source / name).read_bytes()).hexdigest()
            for name in expected_roles
        }

        for name in ("notes.txt", "savegame_0.save.bak", "app_settings_copy"):
            (source / name).write_bytes(vanilla)
        nested = source / "nested"
        nested.mkdir()
        (nested / "savegame_1.save").write_bytes(vanilla)
        source_files = {path.name for path in source.iterdir()}

        result = self.run_cli(str(source))

        self.assertEqual(result.returncode, 0, result.stderr)
        run_root = Path(result.stdout.strip())
        manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["input_mode"], "directory")
        by_name = {
            item["source"]["name"]: item for item in manifest["inputs"]
        }
        self.assertEqual(set(by_name), set(expected_roles))
        for name, (role, detected_format) in expected_roles.items():
            item = by_name[name]
            self.assertEqual(item["role"], role)
            self.assertEqual(item["format"], detected_format)
            self.assertTrue(item["role_match"])
            self.assertTrue((run_root / item["artifacts"]["chunk"]).is_file())
            self.assertTrue((run_root / item["artifacts"]["full"]).is_file())
        self.assertEqual(
            before,
            {
                name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                for name in expected_roles
            },
        )
        self.assertEqual({path.name for path in source.iterdir()}, source_files)

        summary = (run_root / "summary.txt").read_text(encoding="utf-8")
        for name in expected_roles:
            self.assertIn(str(source / name).casefold(), summary.casefold())
        self.assertNotIn("notes.txt", summary)
        self.assertNotIn("savegame_1.save", summary)

    def test_directory_reports_filename_and_content_mismatches(self):
        source = self.root / "mismatched directory"
        source.mkdir()
        (source / "savegame_0.save").write_bytes(
            self.modding_bytes(("demo.mod", {"ok": True}))
        )
        (source / "app_settings_modded").write_bytes(
            self.vanilla_bytes({"value": 1})
        )

        result = self.run_cli(str(source))

        self.assertEqual(result.returncode, 0, result.stderr)
        run_root = Path(result.stdout.strip())
        manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
        by_name = {item["source"]["name"]: item for item in manifest["inputs"]}
        slot = by_name["savegame_0.save"]
        global_settings = by_name["app_settings_modded"]
        self.assertEqual(slot["role"], "vanilla-player-save")
        self.assertEqual(slot["expected_format"], "vanilla-base64-json")
        self.assertEqual(slot["format"], "moddingapi-records")
        self.assertFalse(slot["role_match"])
        self.assertIn("Role mismatch", slot["warnings"][0])
        self.assertEqual(global_settings["role"], "moddingapi-global-settings")
        self.assertEqual(global_settings["expected_format"], "moddingapi-records")
        self.assertEqual(global_settings["format"], "vanilla-base64-json")
        self.assertFalse(global_settings["role_match"])

        summary = (run_root / "summary.txt").read_text(encoding="utf-8")
        self.assertEqual(summary.count("Role match: no"), 2)

    def test_directory_preserves_valid_siblings_when_supported_file_is_corrupt(self):
        source = self.root / "partly corrupt directory"
        source.mkdir()
        valid = source / "app_settings"
        valid.write_bytes(self.vanilla_bytes({"value": 1}))
        corrupt = source / "savegame_0.save"
        corrupt.write_bytes(b"not a save")

        result = self.run_cli(str(source))

        self.assertEqual(result.returncode, 0, result.stderr)
        run_root = Path(result.stdout.strip())
        manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
        by_name = {item["source"]["name"]: item for item in manifest["inputs"]}
        self.assertEqual(set(by_name), {"app_settings", "savegame_0.save"})
        self.assertEqual(by_name["app_settings"]["parse_status"], "ok")
        failed = by_name["savegame_0.save"]
        self.assertEqual(failed["role"], "vanilla-player-save")
        self.assertEqual(failed["expected_format"], "vanilla-base64-json")
        self.assertEqual(failed["format"], "unknown")
        self.assertEqual(failed["parse_status"], "failed")
        self.assertEqual(failed["error"]["reason"], "unsupported-format")
        self.assertIsNone(failed["artifacts"]["full"])
        self.assertEqual(failed["full_artifact_status"], "unavailable")
        chunk = json.loads(
            (run_root / failed["artifacts"]["chunk"]).read_text(encoding="utf-8")
        )
        self.assertEqual(chunk["parse_status"], "failed")
        self.assertEqual(chunk["error"]["reason"], "unsupported-format")

        summary = (run_root / "summary.txt").read_text(encoding="utf-8")
        self.assertIn("Status: ok", summary)
        self.assertIn("Status: failed", summary)
        self.assertIn("Error: unsupported-format", summary)
        self.assertIn("Full artifact: unavailable", summary)

    def test_directory_does_not_follow_supported_name_symlink(self):
        source = self.root / "linked directory"
        source.mkdir()
        (source / "app_settings").write_bytes(self.vanilla_bytes({"value": 1}))
        external = self.root / "external save"
        external.write_bytes(self.vanilla_bytes({"external": True}))
        link = source / "savegame_1.save"
        try:
            os.symlink(external, link)
        except OSError as error:
            self.skipTest(f"file symlinks unavailable: {error}")

        result = self.run_cli(str(source))

        self.assertEqual(result.returncode, 0, result.stderr)
        run_root = Path(result.stdout.strip())
        manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [item["source"]["name"] for item in manifest["inputs"]],
            ["app_settings"],
        )
        summary = (run_root / "summary.txt").read_text(encoding="utf-8")
        self.assertNotIn("savegame_1.save", summary)

    def test_directory_with_no_supported_files_fails_clearly(self):
        source = self.root / "unsupported directory"
        source.mkdir()
        (source / "notes.txt").write_text("not a save", encoding="utf-8")
        nested = source / "nested"
        nested.mkdir()
        (nested / "savegame_1.save").write_bytes(self.vanilla_bytes({"value": 1}))

        result = self.run_cli(str(source))

        self.assertEqual(result.returncode, 1)
        self.assertIn("Reason: no-supported-files", result.stderr)
        analysis_root = self.temp_root / "blasphemous-save-analysis"
        self.assertFalse(analysis_root.exists())


if __name__ == "__main__":
    unittest.main()
