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

    def test_redaction_is_case_insensitive_on_windows(self):
        if os.name != "nt":
            self.skipTest("Windows path case folding")
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "UnityProject"
            lower_root = str(root).lower()

            message = runner._redact_project_root(
                f"failed at {lower_root}",
                root,
            )

        self.assertNotIn(lower_root, message)
        self.assertIn("<UNITY_PROJECT_ROOT>", message)

    def test_incomplete_scanner_payload_is_accepted_for_census(self):
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = {
                "status": "timeout",
                "scan_coverage": "partial",
                "warnings": [{"code": "timeout"}],
                "error": {"code": "timeout"},
            }
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=3,
                stdout=json.dumps(payload),
                stderr="",
            )
            with mock.patch.object(
                runner.subprocess,
                "run",
                return_value=completed,
            ):
                actual, _, _ = runner._run_scanner_with_size(
                    sys.executable,
                    root,
                    ["bindings", "--project", str(root)],
                    allow_incomplete=True,
                )

        self.assertEqual(actual, payload)

    def test_snapshot_does_not_follow_directory_links(self):
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "UnityProject"
            outside = base / "Outside"
            root.mkdir()
            outside.mkdir()
            (outside / "secret.txt").write_text("secret", encoding="utf-8")
            link = root / "Linked"
            try:
                os.symlink(outside, link, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory link unavailable: {error}")

            paths, _, _, _ = runner._snapshot_paths(root)

        self.assertIn("dir:Linked", paths)
        self.assertFalse(
            any("Linked/secret.txt" in path for path in paths),
        )

    def test_binding_benchmark_records_both_page_sizes_and_coverage(self):
        runner = self.load_runner()

        def page(start):
            return {
                "status": "ok",
                "scan_coverage": "pending",
                "warnings": [],
                "error": None,
                "limits": {"limit": 2},
                "next_cursor": "next" if start == 0 else "next-two",
                "results": [
                    {
                        "source_asset_path": "Assets/Test.unity",
                        "source_object_file_id": str(index),
                    }
                    for index in range(start, start + 2)
                ],
            }

        with mock.patch.object(
            runner,
            "_run_scanner_with_size",
            side_effect=(
                (page(0), 1.0, 1234),
                (page(2), 2.0, 5678),
            ),
        ):
            benchmark, records = runner._run_binding_benchmark(
                sys.executable,
                REPOSITORY_ROOT,
                2,
            )

        self.assertEqual(benchmark["serialized_bytes"], 1234)
        self.assertEqual(benchmark["scan_coverage"], "pending")
        self.assertEqual(
            benchmark["cursor_transition"]["serialized_bytes"],
            5678,
        )
        self.assertEqual(
            benchmark["cursor_transition"]["scan_coverage"],
            "pending",
        )
        self.assertEqual(records[0]["serialized_bytes"], 1234)
        self.assertEqual(records[1]["serialized_bytes"], 5678)
        self.assertEqual(records[0]["scan_coverage"], "pending")
        self.assertEqual(records[1]["scan_coverage"], "pending")

    def test_binding_benchmark_rejects_a_repeated_page_boundary(self):
        runner = self.load_runner()

        def page(cursor):
            return {
                "status": "ok",
                "scan_coverage": "pending",
                "warnings": [],
                "error": None,
                "limits": {"limit": 2},
                "next_cursor": cursor,
                "results": [
                    {
                        "source_asset_path": "Assets/Test.unity",
                        "source_object_file_id": str(index),
                    }
                    for index in range(2)
                ],
            }

        with mock.patch.object(
            runner,
            "_run_scanner_with_size",
            side_effect=(
                (page("first-cursor"), 1.0, 1234),
                (page("second-cursor"), 2.0, 5678),
            ),
        ):
            with self.assertRaises(runner.SmokeFailure):
                runner._run_binding_benchmark(
                    sys.executable,
                    REPOSITORY_ROOT,
                    2,
                )

    def test_binding_benchmark_accepts_a_final_second_page(self):
        runner = self.load_runner()

        def page(start):
            next_cursor = "next" if start == 0 else None
            return {
                "status": "ok",
                "scan_coverage": "pending" if next_cursor else "complete",
                "warnings": [],
                "error": None,
                "limits": {"limit": 2},
                "next_cursor": next_cursor,
                "results": [
                    {
                        "source_asset_path": "Assets/Test.unity",
                        "source_object_file_id": str(index),
                    }
                    for index in range(start, start + 2)
                ],
            }

        with mock.patch.object(
            runner,
            "_run_scanner_with_size",
            side_effect=(
                (page(0), 1.0, 1234),
                (page(2), 2.0, 5678),
            ),
        ):
            benchmark, _ = runner._run_binding_benchmark(
                sys.executable,
                REPOSITORY_ROOT,
                2,
            )

        self.assertEqual(
            benchmark["cursor_transition"]["scan_coverage"],
            "complete",
        )
        self.assertFalse(
            benchmark["cursor_transition"]["next_cursor_present"],
        )

    def test_binding_sample_chains_must_match_the_manifest(self):
        runner = self.load_runner()
        expected = {
            "source_asset_path": "Assets/Fixture.unity",
            "source_object_file_id": "1",
            "target_asset_path": "Assets/Fixture.cs",
        }
        manifest = {"bindings": {"samples": {"cs": expected}}}

        runner._verify_binding_sample_chains(
            {"cs": dict(expected)},
            manifest,
        )

        drifted = dict(expected)
        drifted["target_asset_path"] = "Assets/Other.cs"
        with self.assertRaises(runner.SmokeFailure):
            runner._verify_binding_sample_chains(
                {"cs": drifted},
                manifest,
            )

    def test_binding_census_allows_a_target_only_packages_sample(self):
        runner = self.load_runner()
        samples = {
            key: {}
            for key in (
                "asset",
                "cs",
                "dll",
                "non_typical_file_id",
                "null",
                "packages",
                "unresolved",
            )
        }
        payload = {
            "status": "ok",
            "scan_coverage": "complete",
            "warnings": [],
            "error": None,
            "results": [],
            "next_cursor": None,
            "census": {
                "candidate_source_files": 0,
                "reference_shape": {},
                "rows": 0,
                "source_asset_kind": {},
                "target_category": {"malformed": 0},
                "warning_codes": {},
                "samples": samples,
            },
        }
        project_payload = {
            "schema_version": 1,
            "project": {
                "included_roots": ["Assets"],
                "unity_version": "2017.4.40f1",
            },
            "results": [
                {
                    "file_counts": {
                        "unity": 0,
                        "prefab": 0,
                        "asset": 0,
                    }
                }
            ]
        }
        manifest = {
            "bindings": {
                "census": {"packages_source_candidates": 0},
            }
        }

        with mock.patch.object(
            runner,
            "_run_scanner_with_size",
            return_value=(payload, 1.0, 100),
        ), mock.patch.object(
            runner,
            "_run_binding_benchmark",
            return_value=({}, []),
        ), mock.patch.object(
            runner,
            "_verify_binding_samples",
        ), mock.patch.object(
            runner,
            "_verify_binding_sample_chains",
        ), mock.patch.object(
            runner,
            "_verify_binding_census",
        ):
            census, _, complete = runner._run_binding_census(
                sys.executable,
                REPOSITORY_ROOT,
                project_payload,
                set(),
                manifest,
            )

        self.assertTrue(complete)
        self.assertIn("packages", census["samples"])

    def test_binding_census_partial_status_is_preserved(self):
        runner = self.load_runner()
        partial = {
            "status": "timeout",
            "scan_coverage": "partial",
            "warnings": [{"code": "timeout"}],
            "error": {"code": "timeout"},
            "census": None,
        }
        project_payload = {
            "project": {"unity_version": "2017.4.40f1"},
            "results": [
                {
                    "file_counts": {
                        "total": 0,
                        "unity": 0,
                        "prefab": 0,
                        "asset": 0,
                        "cs": 0,
                        "meta": 0,
                    },
                    "scene_counts": {
                        "complete_sets": 0,
                        "standalone": 0,
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "UnityProject"
            (root / "Assets").mkdir(parents=True)
            (root / "ProjectSettings").mkdir()
            (root / "ProjectSettings" / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2017.4.40f1\n",
                encoding="utf-8",
            )
            with mock.patch.object(
                runner,
                "_read_json",
                return_value={"schema_version": 1, "representative_files": []},
            ), mock.patch.object(
                runner,
                "_run_scanner",
                return_value=(project_payload, 1.0),
            ), mock.patch.object(
                runner,
                "_verify_project_summary",
            ), mock.patch.object(
                runner,
                "_run_binding_census",
                return_value=(partial, [], False),
            ):
                return_code, report = runner.run(
                    sys.executable,
                    str(root),
                    root / "manifest.json",
                    True,
                )

        self.assertEqual(return_code, 4)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(
            report["completion_evidence"]["bindings_census"],
            partial,
        )
        self.assertIsNotNone(report["read_only"])

    def test_binding_census_accepts_package_sources_without_a_binding_sample(self):
        runner = self.load_runner()
        samples = {
            key: {}
            for key in (
                "asset",
                "cs",
                "dll",
                "non_typical_file_id",
                "null",
                "unresolved",
            )
        }
        payload = {
            "status": "ok",
            "scan_coverage": "complete",
            "warnings": [],
            "error": None,
            "results": [],
            "next_cursor": None,
            "census": {
                "candidate_source_files": 0,
                "reference_shape": {},
                "rows": 0,
                "source_asset_kind": {},
                "target_category": {"malformed": 0},
                "warning_codes": {},
                "samples": samples,
            },
        }
        project_payload = {
            "schema_version": 1,
            "project": {
                "included_roots": ["Assets", "Packages"],
                "unity_version": "2017.4.40f1",
            },
            "results": [
                {
                    "file_counts": {
                        "unity": 0,
                        "prefab": 0,
                        "asset": 0,
                    }
                }
            ]
        }
        manifest = {
            "bindings": {
                "census": {"packages_source_candidates": 1},
            }
        }

        with mock.patch.object(
            runner,
            "_run_scanner_with_size",
            return_value=(payload, 1.0, 100),
        ), mock.patch.object(
            runner,
            "_run_binding_benchmark",
            return_value=({}, []),
        ), mock.patch.object(
            runner,
            "_verify_binding_samples",
        ), mock.patch.object(
            runner,
            "_verify_binding_sample_chains",
        ), mock.patch.object(
            runner,
            "_verify_binding_census",
        ):
            census, _, complete = runner._run_binding_census(
                sys.executable,
                REPOSITORY_ROOT,
                project_payload,
                {"file:Packages/com.example/Empty.asset"},
                manifest,
            )

        self.assertTrue(complete)
        self.assertNotIn("packages", census["samples"])

    def test_inventory_read_failure_redacts_the_project_root(self):
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "UnityProject"
            (root / "Assets").mkdir(parents=True)
            (root / "ProjectSettings").mkdir()
            (root / "ProjectSettings" / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2017.4.40f1\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                runner,
                "_read_json",
                return_value={"schema_version": 1},
            ):
                with mock.patch.object(
                    runner,
                    "_snapshot_paths",
                    side_effect=PermissionError(f"Cannot read {root}"),
                ):
                    return_code, report = runner.run(
                        sys.executable,
                        str(root),
                        root / "manifest.json",
                        True,
                    )

        self.assertEqual(return_code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertNotIn(str(root), report["error"])
        self.assertIn("<UNITY_PROJECT_ROOT>", report["error"])

    def test_external_manifest_failure_does_not_echo_its_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "UnityProject"
            (root / "Assets").mkdir(parents=True)
            (root / "ProjectSettings").mkdir()
            (root / "ProjectSettings" / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2017.4.40f1\n",
                encoding="utf-8",
            )
            manifest = Path(temp) / "private-manifest.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--project",
                    str(root),
                    "--manifest",
                    str(manifest),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        self.assertNotIn(str(manifest), result.stdout)
        self.assertNotIn(str(root), result.stdout)

    def test_manifest_failure_redacts_an_in_project_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "UnityProject"
            (root / "Assets").mkdir(parents=True)
            (root / "ProjectSettings").mkdir()
            (root / "ProjectSettings" / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2017.4.40f1\n",
                encoding="utf-8",
            )
            missing = root / "missing-manifest.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--project",
                    str(root),
                    "--manifest",
                    str(missing),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            relative_result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--project",
                    ".",
                    "--manifest",
                    "missing.manifest.json",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["project"]["root"], ".")
        self.assertNotIn(str(root), result.stdout)
        self.assertNotIn(str(missing), result.stdout)
        self.assertEqual(
            report["error"],
            "Could not read local real-project manifest.",
        )
        relative_report = json.loads(relative_result.stdout)
        self.assertEqual(relative_result.returncode, 1)
        self.assertEqual(relative_report["project"]["root"], ".")
        self.assertNotIn("missing.manifest.json", relative_result.stdout)
        self.assertEqual(
            relative_report["error"],
            "Could not read local real-project manifest.",
        )
        self.assertNotIn(str(root), relative_result.stdout)

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
        self.assertEqual(
            set(manifest["bindings"]["samples"]),
            {
                "asset",
                "cs",
                "dll",
                "non_typical_file_id",
                "null",
                "unresolved",
            },
        )

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
