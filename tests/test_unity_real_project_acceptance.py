import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_unity_real_project_acceptance as runner

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
EXPECTED_MANIFEST = {
    "schema_version": 1,
    "unity_version": "2017.4.40f1",
    "baseline": {
        "assets_total_files": 94153,
        "scanner_total_files": 94154,
        "unity_files": 1970,
        "prefab_files": 729,
        "asset_files": 32617,
        "cs_files": 5308,
        "meta_files": 47685,
        "complete_scene_sets": 393,
        "incomplete_scene_sets": 0,
        "standalone_scenes": 5,
    },
    "scene_set": {
        "name": "D01BZ01S01",
        "kind": "complete",
        "present_layers": ["_MAIN", "_LOGIC", "_LAYOUT", "_DECO", "_AUDIO"],
        "members": [
            "Assets/#Design/#CVSTODIA/D01 - Feudal District/D01BZ01 - Mea Culpa/D01BZ01S01 - Arena/D01BZ01S01_MAIN.unity",
            "Assets/#Design/#CVSTODIA/D01 - Feudal District/D01BZ01 - Mea Culpa/D01BZ01S01 - Arena/D01BZ01S01_LOGIC.unity",
            "Assets/#Design/#CVSTODIA/D01 - Feudal District/D01BZ01 - Mea Culpa/D01BZ01S01 - Arena/D01BZ01S01_LAYOUT.unity",
            "Assets/#Design/#CVSTODIA/D01 - Feudal District/D01BZ01 - Mea Culpa/D01BZ01S01 - Arena/D01BZ01S01_DECO.unity",
            "Assets/#Design/#CVSTODIA/D01 - Feudal District/D01BZ01 - Mea Culpa/D01BZ01S01 - Arena/D01BZ01S01_AUDIO.unity",
        ],
        "object_count": 1599,
        "reference_count": 9037,
    },
    "standalone_scene": {
        "path": "Assets/#Design/Scenes/Platform/Preload_Windows.unity",
        "kind": "standalone",
        "members": ["Assets/#Design/Scenes/Platform/Preload_Windows.unity"],
        "object_count": 5,
        "reference_count": 21,
    },
    "prefab": {
        "path": "Assets/Resources/inventory/questitem/QI78.prefab",
        "guid": "01ed6fc6d86656c449f2e9902e9bbb8a",
        "evidence_kind": "flattened",
        "object_count": 4,
        "reference_count": 17,
        "object_file_ids": [
            100100000,
            1810135827502625,
            4693694004387539,
            114940650439655525,
        ],
    },
    "script": {
        "path": "Assets/Plugins/Assembly-CSharp-firstpass/BaseCRTEffect.cs",
        "name": "BaseCRTEffect.cs",
        "guid": "c847fb2e431978e6595b5ef160d260a8",
        "metadata_status": "present",
    },
    "guid_lookup": {
        "guid": "01ed6fc6d86656c449f2e9902e9bbb8a",
        "path": "Assets/Resources/inventory/questitem/QI78.prefab",
        "type": "prefab",
    },
    "references": {
        "path": "Assets/Resources/inventory/questitem/QI78.prefab",
        "object_file_id": 114940650439655525,
        "direction": "outgoing",
        "depth": 2,
        "limit": 30,
        "timeout_seconds": 120,
        "status": "ok",
        "complete": True,
        "node_count": 7,
        "edge_count": 9,
        "edges": [
            {
                "field": "picture",
                "scope": "external",
                "target_path": "Assets/Sprite/qi78.asset",
                "target_file_id": 21300000,
                "target_status": "ok",
                "target_reason": None,
            },
            {
                "field": "texture",
                "scope": "external",
                "target_path": "Assets/Texture2D/items-icons-spritesheet.png",
                "target_file_id": 2800000,
                "target_status": "unsupported",
                "target_reason": "binary_asset_not_inspected",
            },
            {
                "field": "m_Script",
                "scope": "external",
                "target_path": "Assets/Scripts/Assembly-CSharp/Framework/Inventory/QuestItem.cs",
                "target_file_id": 11500000,
                "target_status": "unsupported",
                "target_reason": "not_serialized_asset",
            },
        ],
    },
    "incoming_references": {
        "path": "Assets/Resources/inventory/questitem/QI78.prefab",
        "object_file_id": 114940650439655525,
        "direction": "incoming",
        "depth": 1,
        "limit": 30,
        "timeout_seconds": 120,
        "status": "ok",
        "complete": True,
        "node_count": 2,
        "edge_count": 1,
        "edges": [
            {
                "field": "m_Component.component",
                "scope": "local",
                "target_path": "Assets/Resources/inventory/questitem/QI78.prefab",
                "target_file_id": 114940650439655525,
                "target_status": "ok",
                "target_reason": None,
            }
        ],
    },
    "representative_files": [
        "Assets/#Design/#CVSTODIA/D01 - Feudal District/D01BZ01 - Mea Culpa/D01BZ01S01 - Arena/D01BZ01S01_MAIN.unity",
        "Assets/#Design/#CVSTODIA/D01 - Feudal District/D01BZ01 - Mea Culpa/D01BZ01S01 - Arena/D01BZ01S01_LOGIC.unity",
        "Assets/#Design/#CVSTODIA/D01 - Feudal District/D01BZ01 - Mea Culpa/D01BZ01S01 - Arena/D01BZ01S01_LAYOUT.unity",
        "Assets/#Design/#CVSTODIA/D01 - Feudal District/D01BZ01 - Mea Culpa/D01BZ01S01 - Arena/D01BZ01S01_DECO.unity",
        "Assets/#Design/#CVSTODIA/D01 - Feudal District/D01BZ01 - Mea Culpa/D01BZ01S01 - Arena/D01BZ01S01_AUDIO.unity",
        "Assets/#Design/Scenes/Platform/Preload_Windows.unity",
        "Assets/Resources/inventory/questitem/QI78.prefab",
        "Assets/Resources/inventory/questitem/QI78.prefab.meta",
        "Assets/Plugins/Assembly-CSharp-firstpass/BaseCRTEffect.cs",
        "Assets/Plugins/Assembly-CSharp-firstpass/BaseCRTEffect.cs.meta",
        "Assets/Sprite/qi78.asset",
        "Assets/Sprite/qi78.asset.meta",
        "Assets/Texture2D/items-icons-spritesheet.png",
        "Assets/Texture2D/items-icons-spritesheet.png.meta",
        "ProjectSettings/ProjectVersion.txt",
    ],
}


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


def successful_scanner_payloads(manifest):
    baseline = manifest["baseline"]
    scene_set = manifest["scene_set"]
    standalone = manifest["standalone_scene"]
    prefab = manifest["prefab"]
    script = manifest["script"]
    guid = manifest["guid_lookup"]
    references = manifest["references"]
    project_payload = {
        "status": "ok",
        "project": {"unity_version": manifest["unity_version"]},
        "results": [
            {
                "file_counts": {
                    "total": baseline["scanner_total_files"],
                    "unity": baseline["unity_files"],
                    "prefab": baseline["prefab_files"],
                    "asset": baseline["asset_files"],
                    "cs": baseline["cs_files"],
                    "meta": baseline["meta_files"],
                },
                "scene_counts": {
                    "complete_sets": baseline["complete_scene_sets"],
                    "incomplete_sets": baseline["incomplete_scene_sets"],
                    "standalone": baseline["standalone_scenes"],
                },
            }
        ],
        "warnings": [],
    }
    scene_set_payload = {
        "status": "ok",
        "results": [
            {
                "logical_name": scene_set["name"],
                "directory": str(Path(scene_set["members"][0]).parent).replace("\\", "/"),
                "kind": scene_set["kind"],
                "present_layers": scene_set["present_layers"],
                "missing_layers": [],
                "members": [{"path": path} for path in scene_set["members"]],
                "object_count": scene_set["object_count"],
                "reference_count": scene_set["reference_count"],
            }
        ],
        "warnings": [],
    }
    standalone_payload = {
        "status": "ok",
        "results": [
            {
                "logical_name": Path(standalone["path"]).stem,
                "directory": str(Path(standalone["path"]).parent).replace("\\", "/"),
                "kind": standalone["kind"],
                "members": [{"path": path} for path in standalone["members"]],
                "requested_path": standalone["path"],
                "object_count": standalone["object_count"],
                "reference_count": standalone["reference_count"],
            }
        ],
        "warnings": [],
    }
    prefab_payload = {
        "status": "ok",
        "results": [
            {
                "path": prefab["path"],
                "guid": prefab["guid"],
                "evidence_kind": prefab["evidence_kind"],
                "object_count": prefab["object_count"],
                "reference_count": prefab["reference_count"],
                "objects": [
                    {"file_id": file_id} for file_id in prefab["object_file_ids"]
                ],
            }
        ],
        "limits": {"source_prefab_hierarchy": "not_available"},
        "warnings": [],
    }
    script_payload = {
        "status": "ok",
        "results": [
            {
                "path": script["path"],
                "name": script["name"],
                "guid": script["guid"],
                "type": "cs",
                "metadata": {"status": script["metadata_status"]},
            }
        ],
        "limits": {"csharp_parsed": False},
        "warnings": [],
    }
    guid_payload = {
        "status": "ok",
        "results": [
            {
                "path": guid["path"],
                "type": guid["type"],
                "guid": guid["guid"],
            }
        ],
        "warnings": [],
    }
    def reference_payload_for(expected):
        reference_edges = [
            {
                "field": edge["field"],
                "scope": edge["scope"],
                "target": {
                    "path": edge["target_path"],
                    "file_id": edge["target_file_id"],
                    "status": edge["target_status"],
                    "reason": edge["target_reason"],
                },
            }
            for edge in expected["edges"]
        ]
        return {
            "status": expected["status"],
            "complete": expected["complete"],
            "truncated": False,
            "incomplete_reasons": [],
            "root": {
                "path": expected["path"],
                "object_file_id": expected["object_file_id"],
            },
            "results": [
                {
                    "direction": expected["direction"],
                    "node_count": expected["node_count"],
                    "edge_count": expected["edge_count"],
                    "edges": reference_edges,
                }
            ],
            "warnings": [],
        }

    return [
        project_payload,
        scene_set_payload,
        standalone_payload,
        prefab_payload,
        script_payload,
        guid_payload,
        reference_payload_for(references),
        reference_payload_for(manifest["incoming_references"]),
    ]


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
        command_names = [item["query"] for item in report["commands"]]
        self.assertIn("references", command_names)
        self.assertIn("incoming_references", command_names)

    def test_manifest_locks_the_complete_real_smoke_contract(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(manifest, EXPECTED_MANIFEST)

    def test_runner_has_no_manifest_override(self):
        result = subprocess.run(
            [sys.executable, str(RUNNER), "--manifest", str(MANIFEST)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments", result.stderr)

    def test_unreadable_export_returns_one_blocked_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Assets").mkdir()
            project_settings = root / "ProjectSettings"
            project_settings.mkdir()
            (project_settings / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2017.4.40f1\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                runner,
                "_snapshot_paths",
                side_effect=OSError("access denied"),
            ):
                code, report = runner.run(sys.executable, str(root))

        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["commands"], [])
        self.assertIn("access denied", report["blocked_reason"])
        self.assertIn("readable UTinyRipper export", report["next_action"])

    def test_failed_scanner_retains_the_attempted_command(self):
        payloads = successful_scanner_payloads(EXPECTED_MANIFEST)
        calls = 0
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Assets").mkdir()
            project_settings = root / "ProjectSettings"
            project_settings.mkdir()
            (project_settings / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2017.4.40f1\n",
                encoding="utf-8",
            )

            def fail_scanner(python_executable, project_root, arguments, record):
                nonlocal calls
                if calls == 0:
                    calls += 1
                    record["status"] = "ok"
                    record["elapsed_seconds"] = 0.01
                    return payloads.pop(0), 0.01
                record["status"] = "failed"
                record["elapsed_seconds"] = 0.01
                raise runner.SmokeFailure("scanner failed")

            with mock.patch.object(
                runner,
                "_snapshot_paths",
                return_value=(set(), 94153, 94154, 0),
            ), mock.patch.object(
                runner,
                "_hashes",
                return_value={
                    path: "0" * 64 for path in EXPECTED_MANIFEST["representative_files"]
                },
            ), mock.patch.object(runner, "_run_scanner", side_effect=fail_scanner):
                code, report = runner.run(sys.executable, str(root))

        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(len(report["commands"]), 2)
        self.assertEqual(report["commands"][0]["status"], "ok")
        command = report["commands"][1]
        self.assertEqual(command["status"], "failed")
        self.assertEqual(command["command"][0], sys.executable)
        self.assertEqual(command["command"][1], str(runner.SCANNER))
        self.assertIn("scanner failed", report["error"])

    def test_success_report_contains_all_attempted_commands(self):
        payloads = successful_scanner_payloads(EXPECTED_MANIFEST)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Assets").mkdir()
            project_settings = root / "ProjectSettings"
            project_settings.mkdir()
            (project_settings / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2017.4.40f1\n",
                encoding="utf-8",
            )

            def successful_scanner(python_executable, project_root, arguments, record):
                record["status"] = "ok"
                record["elapsed_seconds"] = 0.01
                return payloads.pop(0), 0.01

            with mock.patch.object(
                runner,
                "_snapshot_paths",
                return_value=(set(), 94153, 94154, 0),
            ), mock.patch.object(
                runner,
                "_hashes",
                return_value={
                    path: "0" * 64 for path in EXPECTED_MANIFEST["representative_files"]
                },
            ), mock.patch.object(runner, "_run_scanner", side_effect=successful_scanner):
                code, report = runner.run(sys.executable, str(root))

        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(
            [item["query"] for item in report["commands"]],
            [
                "project",
                "scene_set",
                "standalone_scene",
                "prefab",
                "script",
                "guid_lookup",
                "references",
                "incoming_references",
            ],
        )
        self.assertTrue(
            all(
                item["command"][0] == sys.executable
                and item["command"][1] == str(runner.SCANNER)
                for item in report["commands"]
            )
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
