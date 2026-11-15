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

    def run_cli(self, *arguments):
        environment = os.environ.copy()
        environment["TEMP"] = str(self.temp_root)
        environment["TMP"] = str(self.temp_root)
        environment["TMPDIR"] = str(self.temp_root)
        environment["HOME"] = str(self.work)
        environment["USERPROFILE"] = str(self.work)
        environment["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [sys.executable, str(CLI), *arguments],
            cwd=str(self.work),
            env=environment,
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


if __name__ == "__main__":
    unittest.main()
