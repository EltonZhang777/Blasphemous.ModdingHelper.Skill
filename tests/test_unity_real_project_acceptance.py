import importlib.util
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


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "unity_real_project_acceptance_runner",
        RUNNER,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        bindings = manifest["bindings"]["census"]
        self.assertEqual(bindings["rows"], 75147)
        self.assertEqual(bindings["pages"], 76)
        self.assertEqual(bindings["target_category"]["cs"], 68660)
        self.assertEqual(bindings["target_category"]["dll"], 2356)
        self.assertEqual(bindings["target_category"]["unresolved"], 4130)
        self.assertEqual(bindings["target_category"]["null"], 1)
        self.assertEqual(bindings["target_category"]["malformed"], 0)
        self.assertEqual(bindings["distinct_m_script_file_ids"], 50)
        self.assertEqual(bindings["non_typical_file_id_rows"], 6485)
        self.assertEqual(bindings["packages_source_candidates"], 0)

    def test_binding_census_aggregates_states_and_samples(self):
        runner = load_runner()
        census = runner._new_binding_census()
        state = {"file_ids": set(), "previous_last": None}
        rows = [
            self.binding_row("Assets/Scenes/Main.unity", "scene", "1", "cs"),
            self.binding_row("Assets/Prefabs/Dll.prefab", "prefab", "2", "dll"),
            self.binding_row(
                "Assets/Data/Config.asset",
                "asset",
                "3",
                "unresolved",
            ),
            self.binding_row("Assets/Scenes/Null.unity", "scene", "4", "null"),
            self.binding_row(
                "Assets/Prefabs/Malformed.prefab",
                "prefab",
                "5",
                "malformed",
            ),
        ]

        runner._accumulate_binding_page(
            census,
            state,
            {
                "status": "ok",
                "scan_coverage": "complete",
                "warnings": [],
                "error": None,
                "results": rows,
            },
        )

        self.assertEqual(census["rows"], 5)
        self.assertEqual(census["pages"], 1)
        self.assertEqual(
            census["source_asset_kind"],
            {"scene": 2, "prefab": 2, "asset": 1},
        )
        self.assertEqual(
            census["target_category"],
            {
                "cs": 1,
                "dll": 1,
                "unresolved": 1,
                "null": 1,
                "malformed": 1,
                "binary_other": 0,
                "other": 0,
            },
        )
        self.assertEqual(
            set(census["samples"]),
            {
                "cs",
                "dll",
                "unresolved",
                "null",
                "malformed",
                "non_typical_file_id",
                "asset",
            },
        )
        self.assertEqual(len(state["file_ids"]), 4)

    @staticmethod
    def binding_row(source_path, source_kind, file_id, category):
        guid = "a" * 32
        base = {
            "source_asset_path": source_path,
            "source_asset_kind": source_kind,
            "source_object_file_id": file_id,
            "reference_shape": "structured",
            "m_script_file_id": "11500000",
            "m_script_guid": guid,
            "m_script_type": 3,
            "target_asset_kind": "cs",
            "target_asset_path": "Assets/Scripts/Example.cs",
            "target_asset_candidates": [],
            "asset_resolution": "resolved",
            "asset_resolution_reason": None,
            "script_object_resolution": "asset_level_only",
        }
        if category == "cs":
            return base
        if category == "dll":
            return {
                **base,
                "m_script_file_id": "11500001",
                "target_asset_kind": "binary",
                "target_asset_path": "Assets/Plugins/Example.dll",
                "script_object_resolution": "not_verifiable_binary",
            }
        if category == "unresolved":
            return {
                **base,
                "target_asset_kind": "unresolved",
                "target_asset_path": None,
                "asset_resolution": "missing",
                "asset_resolution_reason": "missing_meta",
                "script_object_resolution": "not_applicable",
            }
        if category == "null":
            return {
                **base,
                "reference_shape": "null",
                "m_script_file_id": "0",
                "m_script_guid": None,
                "target_asset_kind": "not_applicable",
                "target_asset_path": None,
                "asset_resolution": "not_applicable",
                "script_object_resolution": "not_applicable",
            }
        return {
            **base,
            "reference_shape": "malformed",
            "m_script_file_id": None,
            "m_script_guid": None,
            "target_asset_kind": "not_applicable",
            "target_asset_path": None,
            "asset_resolution": "not_applicable",
            "script_object_resolution": "not_applicable",
        }

    def test_seven_navigation_topics_are_english_and_reachable(self):
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
