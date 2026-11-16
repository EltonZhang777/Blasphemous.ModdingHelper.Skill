import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
RUNNER = REPOSITORY_ROOT / "tests" / "run_unity_real_project_acceptance.py"
MANIFEST = REPOSITORY_ROOT / "tests" / "fixtures" / "unity-real-project-smoke.json"
PROJECT_ENV = "BLASPHEMOUS_UNITY_PROJECT_PATH"
NAVIGATION = SKILL_ROOT / "references" / "unity-project-navigation"
TOPICS = (
    "topology.md",
    "assets-and-guids.md",
    "scripts.md",
    "scenes.md",
    "prefabs.md",
    "component-relations.md",
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

    def test_six_navigation_topics_are_english_and_reachable(self):
        index = (NAVIGATION / "MAIN.md").read_text(encoding="utf-8")
        for topic in TOPICS:
            with self.subTest(topic=topic):
                self.assertIn(f"[{topic}]({topic})", index)
                topic_text = (NAVIGATION / topic).read_text(encoding="utf-8")
                self.assertIsNone(
                    re.search(r"[\u4e00-\u9fff]", topic_text),
                    "Unity navigation topics must remain English-only.",
                )

        verification = (
            REPOSITORY_ROOT / "docs" / "verification" / "unity-project-navigation.md"
        ).read_text(encoding="utf-8")
        for phrase in (
            "Synthetic gate",
            "Real-project gate",
            "blocked",
            "separate",
            "94,153",
            "six",
            "Completion criteria",
            "Next action",
        ):
            self.assertIn(phrase, verification)

        main = (NAVIGATION / "MAIN.md").read_text(encoding="utf-8")
        self.assertIn("Source analyzer", main)
        self.assertIn("MUST NOT use Unity `.cs` files as behavioral proof", main)


if __name__ == "__main__":
    unittest.main()
