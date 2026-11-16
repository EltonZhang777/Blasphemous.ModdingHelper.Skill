import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
RUNNER = REPOSITORY_ROOT / "tests" / "run_unity_real_project_acceptance.py"
MANIFEST = REPOSITORY_ROOT / "tests" / "fixtures" / "unity-real-project-smoke.json"
EXAMPLE_MANIFEST = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "unity-real-project-smoke.example.json"
)
IGNORE_FILE = REPOSITORY_ROOT / ".gitignore"
PROJECT_ENV = "BLASPHEMOUS_UNITY_PROJECT_PATH"
NAVIGATION = SKILL_ROOT / "references" / "unity-project-navigation"
TOPICS = (
    "topology.md",
    "assets-and-guids.md",
    "scripts.md",
    "scenes.md",
    "prefabs.md",
    "component-relations.md",
    "bindings.md",
)


def run_runner(project=None):
    environment = os.environ.copy()
    environment.pop(PROJECT_ENV, None)
    if project is not None:
        environment[PROJECT_ENV] = str(project)
    return subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


class UnityRealProjectAcceptanceTests(unittest.TestCase):
    @staticmethod
    def load_runner():
        spec = importlib.util.spec_from_file_location(
            "unity_real_project_acceptance",
            RUNNER,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_missing_real_project_is_blocked_not_substituted(self):
        result = run_runner()

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["evidence_mode"], "real_project")
        self.assertIn("not substituted", report["synthetic_evidence"])
        self.assertTrue(report["blocked_reason"])
        self.assertIn("--project", report["next_action"])
        self.assertEqual(report["commands"], [])
        self.assertIsNone(report["project"]["root"])

    def test_missing_supplied_project_does_not_echo_absolute_path(self):
        missing = REPOSITORY_ROOT / "tests" / "missing-private-project"

        result = run_runner(str(missing))

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["project"]["root"], ".")
        self.assertNotIn(str(missing), result.stdout)
        self.assertNotIn(missing.as_posix(), result.stdout)

    def test_scanner_failure_redacts_the_project_root(self):
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout=f"failed at {root}",
                stderr=f"failed at {root}",
            )
            with mock.patch.object(
                runner.subprocess,
                "run",
                return_value=completed,
            ):
                with self.assertRaises(runner.SmokeFailure) as raised:
                    runner._run_scanner_with_size(
                        sys.executable,
                        root,
                        ["project", "--project", str(root)],
                    )

        message = str(raised.exception)
        self.assertNotIn(str(root), message)
        self.assertIn("<UNITY_PROJECT_ROOT>", message)

    def test_real_project_smoke_when_configured(self):
        project = os.environ.get(PROJECT_ENV)
        if not project:
            self.skipTest(
                f"REAL_PROJECT_SMOKE=blocked: {PROJECT_ENV} is not set"
            )

        result = run_runner(project)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["evidence_mode"], "real_project")
        self.assertEqual(report["project"]["root"], ".")
        self.assertEqual(report["blocked_reason"], None)
        self.assertTrue(report["read_only"]["representative_files"])
        self.assertEqual(report["read_only"]["added_paths"], [])
        self.assertEqual(report["read_only"]["removed_paths"], [])
        self.assertTrue(
            all(
                item["unchanged"]
                for item in report["read_only"]["representative_files"]
            )
        )
        self.assertIn("references", [item["query"] for item in report["commands"]])

    def test_manifest_locks_the_real_smoke_identities(self):
        if not MANIFEST.is_file():
            self.skipTest("operator-local real-project manifest is not present")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["unity_version"], "2017.4.40f1")
        self.assertEqual(manifest["baseline"]["assets_total_files"], 94153)
        self.assertEqual(manifest["scene_set"]["kind"], "complete")
        self.assertEqual(len(manifest["scene_set"]["members"]), 5)
        self.assertEqual(manifest["standalone_scene"]["kind"], "standalone")
        self.assertEqual(manifest["prefab"]["evidence_kind"], "flattened")
        self.assertEqual(manifest["script"]["metadata_status"], "present")
        self.assertEqual(manifest["guid_lookup"]["type"], "prefab")
        self.assertTrue(manifest["references"]["complete"])
        self.assertIn(
            "binary_asset_not_inspected",
            [edge["target_reason"] for edge in manifest["references"]["edges"]],
        )
        bindings = manifest["bindings"]["census"]
        self.assertEqual(bindings["rows"], 75147)
        self.assertEqual(bindings["candidate_source_files"], 35316)
        self.assertNotIn("pages", bindings)
        self.assertEqual(bindings["target_category"]["cs"], 68660)
        self.assertEqual(bindings["target_category"]["dll"], 2356)
        self.assertEqual(bindings["target_category"]["unresolved"], 4130)
        self.assertEqual(bindings["target_category"]["null"], 1)
        self.assertEqual(bindings["target_category"]["malformed"], 0)
        self.assertEqual(bindings["distinct_m_script_file_ids"], 50)
        self.assertEqual(bindings["non_typical_file_id_rows"], 6484)
        self.assertEqual(bindings["packages_source_candidates"], 0)

    def test_example_manifest_is_path_free_and_local_manifest_is_ignored(self):
        manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8"))
        strings = []
        allowed = {
            "2017.4.40f1",
            "_AUDIO",
            "_DECO",
            "_LAYOUT",
            "_LOGIC",
            "_MAIN",
            "binary_asset_not_inspected",
            "complete",
            "external",
            "flattened",
            "ok",
            "outgoing",
            "prefab",
            "present",
            "standalone",
            "unsupported",
        }

        def collect(value):
            if isinstance(value, dict):
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)
            elif isinstance(value, str):
                strings.append(value)

        collect(manifest)
        for index, value in enumerate(strings):
            with self.subTest(index=index):
                self.assertTrue(
                    value in allowed
                    or re.fullmatch(r"<LOCAL_[A-Z0-9_]+>", value),
                    "Example manifest strings must be enum values or placeholders.",
                )
        ignore_text = IGNORE_FILE.read_text(encoding="utf-8")
        self.assertIn(
            "tests/fixtures/unity-real-project-smoke.json",
            ignore_text.splitlines(),
        )
        self.assertEqual(manifest["prefab"]["object_file_ids"], [0])
        self.assertEqual(manifest["references"]["object_file_id"], 0)
        self.assertEqual(manifest["references"]["edges"][0]["target_file_id"], 0)

        verification = (
            REPOSITORY_ROOT
            / "docs"
            / "verification"
            / "unity-project-navigation.md"
        ).read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"(?:Assets|Packages)/", verification))
        self.assertIsNone(re.search(r"\b[0-9A-Fa-f]{32}\b", verification))

    def test_seven_navigation_topics_are_english_and_reachable(self):
        index = (NAVIGATION / "MAIN.md").read_text(encoding="utf-8")
        topic_texts = {}
        for topic in TOPICS:
            with self.subTest(topic=topic):
                self.assertIn(f"[{topic}]({topic})", index)
                topic_text = (NAVIGATION / topic).read_text(encoding="utf-8")
                topic_texts[topic] = topic_text
                self.assertIsNone(
                    re.search(r"[\u4e00-\u9fff]", topic_text),
                    "Unity navigation topics must remain English-only.",
                )

        for topic in ("scripts.md", "component-relations.md"):
            text = topic_texts[topic]
            for phrase in (
                "bindings",
                "`m_script_guid`",
                "`asset_resolution_reason`",
                "DLL",
                "Source analyzer",
                "class semantics",
            ):
                with self.subTest(topic=topic, phrase=phrase):
                    self.assertIn(phrase, text)

        verification = (
            REPOSITORY_ROOT / "docs" / "verification" / "unity-project-navigation.md"
        ).read_text(encoding="utf-8")
        for phrase in (
            "Synthetic gate",
            "Real-project gate",
            "blocked",
            "separate",
            "94,153",
            "seven",
            "bindings",
            "census",
            "Completion criteria",
            "Next action",
        ):
            self.assertIn(phrase, verification)

        main = (NAVIGATION / "MAIN.md").read_text(encoding="utf-8")
        self.assertIn("Source analyzer", main)
        self.assertIn("MUST NOT use Unity `.cs` files as behavioral proof", main)


if __name__ == "__main__":
    unittest.main()
