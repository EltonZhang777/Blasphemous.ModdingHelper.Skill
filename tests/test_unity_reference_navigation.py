import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
SCRIPT_ROOT = SKILL_ROOT / "scripts"
SCANNER = SCRIPT_ROOT / "unity_project_navigation.py"


A_GUID = "a" * 32
B_GUID = "b" * 32
UNRESOLVED_GUID = "c" * 32

A_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  m_Component:
  - component: {fileID: 2}
  m_Name: AObject
--- !u!4 &2
Transform:
  m_GameObject: {fileID: 1}
  m_Father: {fileID: 0}
--- !u!114 &3
MonoBehaviour:
  m_GameObject: {fileID: 2}
  localTarget: {fileID: 1}
  missingLocal: {fileID: 99}
  externalResolved: {fileID: 10, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}
  externalUnresolved: {fileID: 11, guid: cccccccccccccccccccccccccccccccc, type: 2}
"""

B_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &10
GameObject:
  m_Component: [{fileID: 11}]
  m_Name: BObject
--- !u!114 &11
MonoBehaviour:
  m_GameObject: {fileID: 10}
  backToA: {fileID: 1, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, type: 2}
"""

CYCLE_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  m_Name: One
  next: {fileID: 2}
--- !u!1 &2
GameObject:
  m_Name: Two
  next: {fileID: 1}
"""

CHAIN_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  m_Name: One
  next: {fileID: 2}
--- !u!1 &2
GameObject:
  m_Name: Two
  next: {fileID: 3}
--- !u!1 &3
GameObject:
  m_Name: Three
  next: {fileID: 4}
--- !u!1 &4
GameObject:
  m_Name: Four
  next: {fileID: 5}
--- !u!1 &5
GameObject:
  m_Name: Five
"""

BROKEN_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
# guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
"""

TARGET_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  m_Name: Target
"""

INCOMING_CALLER_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &2
GameObject:
  m_Name: Caller
  target: {fileID: 1, guid: 11111111111111111111111111111111, type: 2}
"""

UNUSABLE_METADATA_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &2
GameObject:
  m_Name: UnusableMetadataCaller
  target: {fileID: 1, guid: 22222222222222222222222222222222, type: 2}
"""

SCRIPT_REFERENCE_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!114 &1
MonoBehaviour:
  m_Script: {fileID: 11500000, guid: 99999999999999999999999999999999, type: 3}
"""

DUPLICATE_GUID_REFERENCE_PREFAB = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  target: {fileID: 1, guid: 77777777777777777777777777777777, type: 2}
"""


class UnityReferenceNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "UnityProject"
        self.root.mkdir()
        self.write(
            "ProjectSettings/ProjectVersion.txt",
            "m_EditorVersion: 2017.4.40f1\n",
        )
        self.add_asset("Assets/Prefabs/A.prefab", A_PREFAB, A_GUID)
        self.add_asset("Assets/Prefabs/B.prefab", B_PREFAB, B_GUID)
        self.add_asset("Assets/Cycle/Cycle.prefab", CYCLE_PREFAB, "d" * 32)
        self.add_asset("Assets/Cycle/Chain.prefab", CHAIN_PREFAB, "e" * 32)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def add_asset(self, relative, content, guid):
        path = self.write(relative, content)
        self.write(relative + ".meta", f"fileFormatVersion: 2\nguid: {guid}\n")
        return path

    def run_scanner(self, *arguments, env=None):
        environment = os.environ.copy()
        if env is not None:
            environment.update(env)
        return subprocess.run(
            [sys.executable, str(SCANNER), *arguments],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def sitecustomize(self, source):
        directory = Path(self.temp_dir.name) / "sitecustomize"
        directory.mkdir(exist_ok=True)
        (directory / "sitecustomize.py").write_text(
            textwrap.dedent(source),
            encoding="utf-8",
        )
        current = os.environ.get("PYTHONPATH")
        return {
            "PYTHONPATH": (
                str(directory)
                if not current
                else str(directory) + os.pathsep + current
            )
        }

    def query(self, *arguments, expected=0):
        result = self.run_scanner(
            "references",
            "--project",
            str(self.root),
            *arguments,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return result, json.loads(result.stdout)

    def digest_tree(self):
        digest = hashlib.sha256()
        paths = []
        for path in sorted(self.root.rglob("*")):
            relative = path.relative_to(self.root).as_posix()
            paths.append(relative)
            digest.update(relative.encode("utf-8"))
            if path.is_file():
                stat = path.stat()
                digest.update(str(stat.st_size).encode("ascii"))
                digest.update(str(stat.st_mtime_ns).encode("ascii"))
                digest.update(path.read_bytes())
        return paths, digest.hexdigest()

    @staticmethod
    def edge_scopes(payload):
        return [
            edge["scope"]
            for result in payload["results"]
            for edge in result["edges"]
        ]

    def test_default_outgoing_reports_local_external_and_unresolved_references(self):
        result, payload = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "3",
        )

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["command"], "references")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["query"],
            {
                "selector": "path",
                "value": "Assets/Prefabs/A.prefab",
                "object_file_id": 3,
                "direction": "outgoing",
                "depth": 1,
                "limit": 30,
                "timeout_seconds": 60.0,
            },
        )
        self.assertEqual(payload["limits"]["max_depth"], 4)
        self.assertEqual(payload["limits"]["max_limit"], 100)
        self.assertEqual(payload["limits"]["max_timeout_seconds"], 120.0)
        self.assertTrue(payload["complete"])
        self.assertFalse(payload["truncated"])
        self.assertEqual(len(payload["results"]), 1)

        traversal = payload["results"][0]
        self.assertEqual(traversal["direction"], "outgoing")
        self.assertEqual(traversal["node_count"], 6)
        self.assertEqual(traversal["edge_count"], 5)
        self.assertEqual(
            result.stdout,
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        )
        by_field = {edge["field"]: edge for edge in traversal["edges"]}
        self.assertEqual(by_field["localTarget"]["scope"], "local")
        self.assertIsNone(by_field["localTarget"]["guid"])
        self.assertEqual(by_field["localTarget"]["target"]["file_id"], 1)
        self.assertEqual(by_field["missingLocal"]["target"]["status"], "unresolved")
        self.assertEqual(
            by_field["missingLocal"]["target"]["reason"],
            "object_not_found",
        )
        self.assertEqual(by_field["externalResolved"]["scope"], "external")
        self.assertEqual(
            by_field["externalResolved"]["target"]["path"],
            "Assets/Prefabs/B.prefab",
        )
        self.assertEqual(by_field["externalResolved"]["target"]["file_id"], 10)
        self.assertEqual(by_field["externalResolved"]["target"]["status"], "ok")
        self.assertEqual(
            by_field["externalUnresolved"]["target"]["status"],
            "unresolved",
        )
        self.assertEqual(
            by_field["externalUnresolved"]["target"]["reason"],
            "guid_not_found",
        )
        self.assertIsNone(by_field["externalUnresolved"]["target"]["path"])
        self.assertIn(
            "unresolved_reference",
            [warning["code"] for warning in payload["warnings"]],
        )

    def test_incoming_and_bidirectional_traversal_find_local_and_external_callers(self):
        _, incoming = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "1",
            "--direction",
            "incoming",
        )

        self.assertEqual(incoming["status"], "ok")
        self.assertTrue(incoming["complete"])
        traversal = incoming["results"][0]
        self.assertEqual(traversal["direction"], "incoming")
        self.assertEqual(traversal["edge_count"], 3)
        self.assertIn("local", self.edge_scopes(incoming))
        self.assertIn("external", self.edge_scopes(incoming))
        external = next(
            edge for edge in traversal["edges"] if edge["scope"] == "external"
        )
        self.assertEqual(external["source"]["path"], "Assets/Prefabs/B.prefab")
        self.assertEqual(external["source"]["file_id"], 11)
        self.assertEqual(external["target"]["file_id"], 1)

        _, both = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "1",
            "--direction",
            "both",
        )

        self.assertEqual(both["query"]["direction"], "both")
        self.assertEqual(
            [result["direction"] for result in both["results"]],
            ["outgoing", "incoming"],
        )
        self.assertTrue(all(result["edge_count"] > 0 for result in both["results"]))

    def test_bidirectional_alias_matches_both(self):
        _, alias = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "1",
            "--direction",
            "bidirectional",
        )

        self.assertEqual(alias["query"]["direction"], "both")
        self.assertEqual(
            [result["direction"] for result in alias["results"]],
            ["outgoing", "incoming"],
        )

    def test_object_scope_limits_outgoing_references(self):
        _, scoped = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "2",
            "--direction",
            "outgoing",
        )
        _, whole_asset = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--direction",
            "outgoing",
        )

        scoped_fields = {
            edge["field"] for edge in scoped["results"][0]["edges"]
        }
        whole_fields = {
            edge["field"] for edge in whole_asset["results"][0]["edges"]
        }
        self.assertEqual(scoped_fields, {"m_GameObject"})
        self.assertIn("localTarget", whole_fields)
        self.assertIn("externalResolved", whole_fields)
        self.assertEqual(scoped["results"][0]["nodes"][0]["file_id"], 2)
        self.assertGreater(
            whole_asset["results"][0]["edge_count"],
            scoped["results"][0]["edge_count"],
        )

    def test_cycles_visit_each_object_once_and_depth_bounds_chain(self):
        _, cycle = self.query(
            "--path",
            "Assets/Cycle/Cycle.prefab",
            "--object-file-id",
            "1",
            "--depth",
            "4",
        )

        traversal = cycle["results"][0]
        self.assertEqual(traversal["edge_count"], 2)
        self.assertEqual(traversal["node_count"], 2)
        identities = {
            (node["path"], node["file_id"]) for node in traversal["nodes"]
        }
        self.assertEqual(
            identities,
            {("Assets/Cycle/Cycle.prefab", 1), ("Assets/Cycle/Cycle.prefab", 2)},
        )
        self.assertTrue(traversal["complete"])

        for depth, expected_edges in ((1, 1), (2, 2), (4, 4)):
            with self.subTest(depth=depth):
                _, payload = self.query(
                    "--path",
                    "Assets/Cycle/Chain.prefab",
                    "--object-file-id",
                    "1",
                    "--depth",
                    str(depth),
                )
                self.assertEqual(payload["results"][0]["edge_count"], expected_edges)
                self.assertTrue(payload["complete"])

    def test_caps_truncate_deterministically_and_invalid_values_fail(self):
        _, first = self.query(
            "--path",
            "Assets/Cycle/Chain.prefab",
            "--object-file-id",
            "1",
            "--depth",
            "4",
            "--limit",
            "2",
        )
        _, second = self.query(
            "--path",
            "Assets/Cycle/Chain.prefab",
            "--object-file-id",
            "1",
            "--depth",
            "4",
            "--limit",
            "2",
        )

        self.assertTrue(first["truncated"])
        self.assertFalse(first["complete"])
        self.assertEqual(first["results"][0]["edge_count"], 2)
        self.assertIn("limit", first["results"][0]["incomplete_reasons"])
        self.assertIn(
            "result_limit",
            [warning["code"] for warning in first["warnings"]],
        )
        self.assertEqual(
            first["results"][0]["edges"],
            second["results"][0]["edges"],
        )
        self.assertEqual(first, second)

        _, root_cap = self.query(
            "--path",
            "Assets/Cycle/Chain.prefab",
            "--direction",
            "outgoing",
            "--depth",
            "1",
            "--limit",
            "1",
        )
        self.assertTrue(root_cap["truncated"])
        self.assertEqual(root_cap["results"][0]["node_count"], 2)
        self.assertEqual(root_cap["results"][0]["edge_count"], 1)
        self.assertIn("limit", root_cap["results"][0]["incomplete_reasons"])

        for arguments, code in (
            (("--depth", "5"), "invalid_depth"),
            (("--limit", "101"), "invalid_limit"),
            (("--limit", "0"), "invalid_limit"),
            (("--timeout-seconds", "121"), "invalid_timeout"),
            (("--direction", "sideways"), "invalid_direction"),
        ):
            with self.subTest(arguments=arguments):
                _, payload = self.query(
                    "--path",
                    "Assets/Prefabs/A.prefab",
                    *arguments,
                    expected=3,
                )
                self.assertEqual(payload["status"], "invalid_query")
                self.assertEqual(payload["error"]["code"], code)
                self.assertFalse(payload["complete"])

    def test_timeout_during_external_guid_lookup_returns_timeout(self):
        env = self.sitecustomize(
            """
            import pathlib
            import time

            original = pathlib.Path.open

            def open_path(path, *args, **kwargs):
                if path.name == "B.prefab.meta":
                    time.sleep(15)
                return original(path, *args, **kwargs)

            pathlib.Path.open = open_path
            """
        )
        started = time.monotonic()
        result = self.run_scanner(
            "references",
            "--project",
            str(self.root),
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "3",
            "--timeout-seconds",
            "1",
            env=env,
        )
        elapsed = time.monotonic() - started
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertLess(elapsed, 8.0)
        self.assertEqual(payload["status"], "timeout")
        self.assertFalse(payload["complete"])
        self.assertEqual(payload["error"]["code"], "timeout")
        self.assertIn("timeout", payload["incomplete_reasons"])
        self.assertEqual(payload["root"]["path"], "Assets/Prefabs/A.prefab")
        self.assertIn("timeout", [warning["code"] for warning in payload["warnings"]])

    def test_public_cli_bounds_a_blocked_asset_lookup(self):
        env = self.sitecustomize(
            """
            import pathlib
            import time

            original = pathlib.Path.open

            def open_path(path, *args, **kwargs):
                if path.name == "A.prefab.meta":
                    time.sleep(15)
                return original(path, *args, **kwargs)

            pathlib.Path.open = open_path
            """
        )
        started = time.monotonic()
        result = self.run_scanner(
            "references",
            "--project",
            str(self.root.resolve()),
            "--path",
            str(self.root.resolve() / "Assets" / "Prefabs" / "A.prefab"),
            "--timeout-seconds",
            "1",
            env=env,
        )
        elapsed = time.monotonic() - started
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertLess(elapsed, 8.0)
        self.assertEqual(payload["status"], "timeout")
        self.assertFalse(payload["complete"])
        self.assertIn("timeout", payload["incomplete_reasons"])
        self.assertEqual(payload["root"]["path"], "Assets/Prefabs/A.prefab")

    def test_public_cli_bounds_a_blocked_directory_scan(self):
        env = self.sitecustomize(
            """
            import os
            import time

            original = os.scandir

            def scandir(*args, **kwargs):
                time.sleep(15)
                return original(*args, **kwargs)

            os.scandir = scandir
            """
        )
        started = time.monotonic()
        result = self.run_scanner(
            "references",
            "--project",
            str(self.root),
            "--guid",
            A_GUID,
            "--timeout-seconds",
            "1",
            env=env,
        )
        elapsed = time.monotonic() - started
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertLess(elapsed, 8.0)
        self.assertEqual(payload["status"], "timeout")
        self.assertFalse(payload["complete"])
        self.assertIn("timeout", payload["incomplete_reasons"])

    def test_public_cli_timeout_includes_project_validation(self):
        env = self.sitecustomize(
            """
            import os
            import pathlib
            import time

            blocked = pathlib.Path(os.environ["BLOCKED_PROJECT"])
            original = pathlib.Path.resolve

            def resolve(path, *args, **kwargs):
                if path == blocked:
                    time.sleep(5)
                return original(path, *args, **kwargs)

            pathlib.Path.resolve = resolve
            """
        )
        env["BLOCKED_PROJECT"] = str(self.root)
        started = time.monotonic()
        result = self.run_scanner(
            "references",
            "--project",
            str(self.root),
            "--path",
            "Assets/Prefabs/A.prefab",
            "--timeout-seconds",
            "0.5",
            env=env,
        )
        elapsed = time.monotonic() - started
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertLess(elapsed, 4.0)
        self.assertEqual(payload["status"], "timeout")
        self.assertFalse(payload["complete"])
        self.assertIn("timeout", payload["incomplete_reasons"])

    def test_ambiguous_guid_root_records_incomplete_source_evidence(self):
        self.write("Assets/Bad/Broken.asset", "%YAML 1.1\n")
        (self.root / "Assets/Bad/Broken.asset.meta").write_bytes(
            b"\xff\xfe\x00not-utf8"
        )

        result, payload = self.query("--guid", A_GUID, expected=2)

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(payload["status"], "ambiguous")
        self.assertFalse(payload["complete"])
        self.assertIn(
            "source_evidence_incomplete",
            payload["incomplete_reasons"],
        )
        warning_codes = [warning["code"] for warning in payload["warnings"]]
        self.assertIn("metadata_unusable", warning_codes)
        self.assertIn("source_evidence_incomplete", warning_codes)
        self.assertEqual(
            [candidate["path"] for candidate in payload["asset_candidates"]],
            ["Assets/Prefabs/A.prefab"],
        )

    def test_reference_query_reaches_traversal_with_large_metadata_tree(self):
        for index in range(800):
            self.write(
                f"Assets/Metadata/{index // 100:02d}/{index:04d}.asset",
                "%YAML 1.1\n",
            )
            self.write(
                f"Assets/Metadata/{index // 100:02d}/{index:04d}.asset.meta",
                f"fileFormatVersion: 2\nguid: {index:032x}\n",
            )

        _, payload = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "3",
            "--timeout-seconds",
            "10",
        )

        self.assertTrue(payload["complete"])
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["results"][0]["edge_count"], 5)

    def test_external_target_is_ambiguous_when_metadata_is_incomplete(self):
        self.write("Assets/Prefabs/Unknown.prefab", A_PREFAB)
        self.write("Assets/Prefabs/Unknown.prefab.meta", "not read")
        env = self.sitecustomize(
            """
            import pathlib

            original = pathlib.Path.read_text

            def read_text(path, *args, **kwargs):
                if path.name == "Unknown.prefab.meta":
                    raise PermissionError("metadata denied")
                return original(path, *args, **kwargs)

            pathlib.Path.read_text = read_text
            """
        )

        result = self.run_scanner(
            "references",
            "--project",
            str(self.root),
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "3",
            "--timeout-seconds",
            "10",
            env=env,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        edges = payload["results"][0]["edges"]
        target = next(
            edge["target"]
            for edge in edges
            if edge["target"].get("guid") == B_GUID
        )
        self.assertEqual(target["status"], "ambiguous")
        self.assertEqual(target["reason"], "metadata_unusable")
        self.assertEqual(
            target["candidate_paths"],
            ["Assets/Prefabs/B.prefab"],
        )

    def test_external_target_with_unusable_version_is_not_ok(self):
        self.write(
            "Assets/Prefabs/B.prefab.meta",
            "fileFormatVersion: 1234567890\n"
            f"guid: {B_GUID}\n",
        )

        _, payload = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "3",
            "--timeout-seconds",
            "10",
        )

        edges = payload["results"][0]["edges"]
        target = next(
            edge["target"]
            for edge in edges
            if edge["target"].get("guid") == B_GUID
        )
        self.assertNotEqual(target["status"], "ok")
        self.assertEqual(target["reason"], "metadata_unusable")
        self.assertFalse(payload["complete"])

    def test_external_target_with_duplicate_guid_entries_is_not_ok(self):
        self.write(
            "Assets/Prefabs/B.prefab.meta",
            f"\ufeffguid:{B_GUID}\n"
            f"guid : {'e' * 32} # duplicate\n",
        )

        _, payload = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "3",
            "--timeout-seconds",
            "10",
        )

        target = next(
            edge["target"]
            for edge in payload["results"][0]["edges"]
            if edge["target"].get("guid") == B_GUID
        )
        self.assertNotEqual(target["status"], "ok")
        self.assertEqual(target["reason"], "metadata_unusable")
        self.assertFalse(payload["complete"])

    def test_external_target_with_readable_orphan_metadata_is_not_ok(self):
        self.write(
            "Assets/Orphans/B.prefab.meta",
            f"fileFormatVersion: 2\nguid: {B_GUID}\n",
        )

        _, payload = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "3",
            "--timeout-seconds",
            "10",
        )

        target = next(
            edge["target"]
            for edge in payload["results"][0]["edges"]
            if edge["target"].get("guid") == B_GUID
        )
        self.assertEqual(target["status"], "ambiguous")
        self.assertEqual(target["reason"], "metadata_unusable")
        self.assertFalse(payload["complete"])
        self.assertIn(
            ("metadata_unusable", "Assets/Orphans/B.prefab.meta"),
            [
                (warning["code"], warning.get("path"))
                for warning in payload["warnings"]
            ],
        )

    def test_unrelated_orphan_unsupported_version_does_not_poison_external_guid(self):
        self.write(
            "Assets/Orphans/F.prefab.meta",
            "fileFormatVersion: 1234567890\n"
            f"guid: {'6' * 32}\n",
        )

        _, payload = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "3",
            "--timeout-seconds",
            "10",
        )

        target = next(
            edge["target"]
            for edge in payload["results"][0]["edges"]
            if edge["target"].get("guid") == B_GUID
        )
        self.assertEqual(target["status"], "ok")
        self.assertTrue(payload["complete"])
        self.assertNotIn(
            "metadata_unusable",
            [warning["code"] for warning in payload["warnings"]],
        )

    def test_unrelated_duplicate_guid_metadata_does_not_poison_external_guids(self):
        self.write(
            "Assets/Other/D.prefab.meta",
            "fileFormatVersion: 2\n"
            f"guid: {'4' * 32}\n"
            f"guid: {'5' * 32}\n",
        )

        _, payload = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "3",
            "--timeout-seconds",
            "10",
        )

        targets = {
            edge["target"]["guid"]: edge["target"]
            for edge in payload["results"][0]["edges"]
        }
        self.assertEqual(targets[B_GUID]["status"], "ok")
        self.assertEqual(targets[UNRESOLVED_GUID]["status"], "unresolved")
        self.assertEqual(
            targets[UNRESOLVED_GUID]["reason"],
            "guid_not_found",
        )
        self.assertNotIn(
            "metadata_unusable",
            [warning["code"] for warning in payload["warnings"]],
        )

    def test_orphan_guid_without_a_selectable_path_is_ambiguous(self):
        self.add_asset(
            "Assets/Prefabs/OrphanFirst.prefab",
            """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  orphanFirst: {fileID: 1, guid: 66666666666666666666666666666666, type: 2}
  resolvedAfter: {fileID: 10, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}
""",
            "9" * 32,
        )
        self.write(
            "Assets/Orphans/F.prefab.meta",
            "fileFormatVersion: 2\n"
            f"guid: {'6' * 32}\n",
        )

        _, payload = self.query(
            "--path",
            "Assets/Prefabs/OrphanFirst.prefab",
            "--object-file-id",
            "1",
            "--timeout-seconds",
            "10",
        )

        targets = {
            edge["target"]["guid"]: edge["target"]
            for edge in payload["results"][0]["edges"]
        }
        orphan_target = targets["6" * 32]
        resolved_target = targets[B_GUID]
        self.assertEqual(orphan_target["status"], "ambiguous")
        self.assertEqual(orphan_target["reason"], "metadata_unusable")
        self.assertEqual(resolved_target["status"], "ok")
        self.assertFalse(payload["complete"])

    def test_linked_guid_does_not_poison_a_later_external_guid(self):
        self.add_asset(
            "Assets/Prefabs/LinkedFirst.prefab",
            """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  linkedFirst: {fileID: 1, guid: 77777777777777777777777777777777, type: 2}
  resolvedAfter: {fileID: 10, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}
""",
            "8" * 32,
        )
        actual = self.write("Assets/Links/actual.prefab", TARGET_PREFAB)
        linked = self.root / "Assets/Links/linked.prefab"
        try:
            os.symlink(actual, linked)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"file symlink unavailable: {error}")
        self.write(
            "Assets/Links/linked.prefab.meta",
            "fileFormatVersion: 2\n"
            f"guid: {'7' * 32}\n",
        )

        _, payload = self.query(
            "--path",
            "Assets/Prefabs/LinkedFirst.prefab",
            "--object-file-id",
            "1",
            "--timeout-seconds",
            "10",
        )

        targets = {
            edge["target"]["guid"]: edge["target"]
            for edge in payload["results"][0]["edges"]
        }
        linked_target = targets["7" * 32]
        resolved_target = next(
            edge["target"]
            for edge in payload["results"][0]["edges"]
            if edge["target"].get("guid") == B_GUID
        )
        self.assertEqual(linked_target["status"], "ambiguous")
        self.assertEqual(linked_target["reason"], "metadata_unusable")
        self.assertEqual(resolved_target["status"], "ok")
        self.assertFalse(payload["complete"])
        self.assertIn(
            ("metadata_unusable", "Assets/Links/linked.prefab.meta"),
            [
                (warning["code"], warning.get("path"))
                for warning in payload["warnings"]
            ],
        )

    def test_tiny_timeout_does_not_hide_invalid_arguments(self):
        cases = (
            (
                ("--path", "Assets/Prefabs/A.prefab", "--direction", "sideways"),
                "invalid_direction",
            ),
            (("--guid", "not-a-guid"), "invalid_guid"),
            (("--name", "A/B"), "invalid_name"),
            (("--path", "Assets/../escape.prefab"), "path_traversal"),
        )
        for arguments, error_code in cases:
            with self.subTest(error_code=error_code):
                result = self.run_scanner(
                    "references",
                    "--project",
                    str(self.root),
                    *arguments,
                    "--timeout-seconds",
                    "0.001",
                )
                payload = json.loads(result.stdout)

                self.assertEqual(
                    result.returncode,
                    3,
                    result.stdout + result.stderr,
                )
                self.assertEqual(payload["status"], "invalid_query")
                self.assertEqual(payload["error"]["code"], error_code)

    def test_large_incoming_query_filters_non_candidates_before_parse(self):
        self.add_asset(
            "Assets/Targets/Target.prefab",
            TARGET_PREFAB,
            "1" * 32,
        )
        self.add_asset(
            "Assets/Sources/Caller.prefab",
            INCOMING_CALLER_PREFAB,
            "3" * 32,
        )
        for index in range(800):
            self.write(
                f"Assets/Noise/{index // 80:02d}/Noise{index:04d}.prefab",
                "not a Unity serialized document\n",
            )

        started = time.monotonic()
        _, payload = self.query(
            "--path",
            "Assets/Targets/Target.prefab",
            "--object-file-id",
            "1",
            "--direction",
            "incoming",
        )
        elapsed = time.monotonic() - started

        self.assertTrue(payload["complete"])
        self.assertEqual(payload["incomplete_reasons"], [])
        self.assertEqual(payload["results"][0]["edge_count"], 1)
        self.assertEqual(
            payload["results"][0]["edges"][0]["source"]["path"],
            "Assets/Sources/Caller.prefab",
        )
        self.assertNotIn(
            "malformed_document",
            [warning["code"] for warning in payload["warnings"]],
        )
        self.assertLess(elapsed, 10.0)

    def test_incoming_skipped_source_marks_evidence_incomplete(self):
        outside = Path(self.temp_dir.name) / "Outside"
        outside.mkdir()
        skipped = self.root / "Assets" / "Skipped"
        try:
            os.symlink(outside, skipped, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"directory symlink unavailable: {error}")

        _, payload = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "1",
            "--direction",
            "incoming",
        )

        self.assertFalse(payload["complete"])
        self.assertIn(
            "source_evidence_incomplete",
            payload["results"][0]["incomplete_reasons"],
        )
        self.assertIn(
            "source_evidence_incomplete",
            payload["incomplete_reasons"],
        )

    def test_unreadable_metadata_is_reported_as_unusable_evidence(self):
        self.write("Assets/Bad/Bad.prefab", TARGET_PREFAB)
        self.write(
            "Assets/UnusableMetadataCaller.prefab",
            UNUSABLE_METADATA_PREFAB,
        )
        self.write(
            "Assets/UnusableMetadataCaller.prefab.meta",
            "fileFormatVersion: 2\nguid: 44444444444444444444444444444444\n",
        )
        (self.root / "Assets" / "Bad" / "Bad.prefab.meta").write_bytes(
            b"fileFormatVersion: 2\nguid: 22222222222222222222222222222222\n\xff"
        )

        result, payload = self.query(
            "--path",
            "Assets/UnusableMetadataCaller.prefab",
            "--object-file-id",
            "2",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(payload["complete"])
        self.assertIn(
            "source_evidence_incomplete",
            payload["results"][0]["incomplete_reasons"],
        )
        edge = payload["results"][0]["edges"][0]
        self.assertEqual(edge["target"]["status"], "unresolved")
        self.assertEqual(edge["target"]["reason"], "metadata_unusable")
        warnings = payload["warnings"]
        self.assertIn(
            ("metadata_unusable", "Assets/Bad/Bad.prefab.meta"),
            [(warning["code"], warning.get("path")) for warning in warnings],
        )

        asset_result = self.run_scanner(
            "asset",
            "--project",
            str(self.root),
            "--guid",
            "22222222222222222222222222222222",
        )
        asset_payload = json.loads(asset_result.stdout)
        self.assertEqual(asset_result.returncode, 2, asset_result.stdout)
        self.assertIn(
            ("metadata_unusable", "Assets/Bad/Bad.prefab.meta"),
            [
                (warning["code"], warning.get("path"))
                for warning in asset_payload["warnings"]
            ],
        )

    def test_missing_and_malformed_targets_are_explicit(self):
        self.add_asset("Assets/Broken/Broken.prefab", BROKEN_PREFAB, "f" * 32)
        self.add_asset("Assets/Scripts/Example.cs", "class Example {}\n", "9" * 32)
        self.add_asset(
            "Assets/Prefabs/ScriptReference.prefab",
            SCRIPT_REFERENCE_PREFAB,
            "8" * 32,
        )
        _, missing_object = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "404",
            expected=2,
        )
        self.assertEqual(missing_object["status"], "not_found")
        self.assertEqual(missing_object["error"]["code"], "object_not_found")
        self.assertIn(
            "object_not_found",
            [warning["code"] for warning in missing_object["warnings"]],
        )

        _, malformed = self.query(
            "--path",
            "Assets/Broken/Broken.prefab",
            expected=3,
        )
        self.assertEqual(malformed["status"], "invalid_query")
        self.assertEqual(malformed["error"]["code"], "malformed_serialized")
        self.assertEqual(malformed["results"], [])
        self.assertIn(
            "malformed_document",
            [warning["code"] for warning in malformed["warnings"]],
        )

        _, non_serialized = self.query(
            "--path",
            "Assets/Scripts/Example.cs",
            expected=3,
        )
        self.assertEqual(non_serialized["status"], "unsupported_format")
        self.assertEqual(non_serialized["error"]["code"], "not_serialized_asset")
        self.assertIn(
            "not_serialized_asset",
            [warning["code"] for warning in non_serialized["warnings"]],
        )

        _, script_reference = self.query(
            "--path",
            "Assets/Prefabs/ScriptReference.prefab",
            "--object-file-id",
            "1",
        )
        target = script_reference["results"][0]["edges"][0]["target"]
        self.assertEqual(target["status"], "unsupported")
        self.assertEqual(target["reason"], "not_serialized_asset")
        self.assertEqual(target["path"], "Assets/Scripts/Example.cs")

        _, incoming = self.query(
            "--path",
            "Assets/Prefabs/A.prefab",
            "--object-file-id",
            "1",
            "--direction",
            "incoming",
        )
        self.assertEqual(incoming["status"], "ok")
        self.assertIn(
            "malformed_document",
            [warning["code"] for warning in incoming["warnings"]],
        )
        self.assertFalse(incoming["complete"])

    def test_incoming_without_root_guid_reports_incomplete_external_scope(self):
        path = self.write("Assets/NoMeta/NoMeta.prefab", A_PREFAB)

        result = self.run_scanner(
            "references",
            "--project",
            str(self.root),
            "--path",
            path.relative_to(self.root).as_posix(),
            "--object-file-id",
            "1",
            "--direction",
            "incoming",
        )
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["complete"])
        self.assertIn(
            "external_guid_unavailable",
            payload["results"][0]["incomplete_reasons"],
        )
        self.assertIn(
            "incoming_external_scope_unavailable",
            [warning["code"] for warning in payload["warnings"]],
        )

    def test_duplicate_external_guid_returns_candidates_without_guessing(self):
        duplicate = "7" * 32
        self.add_asset("Assets/Ambiguous/Second.prefab", A_PREFAB, duplicate)
        self.add_asset("Assets/Ambiguous/First.prefab", A_PREFAB, duplicate)
        self.add_asset(
            "Assets/Prefabs/DuplicateReference.prefab",
            DUPLICATE_GUID_REFERENCE_PREFAB,
            "6" * 32,
        )

        _, payload = self.query(
            "--path",
            "Assets/Prefabs/DuplicateReference.prefab",
            "--object-file-id",
            "1",
        )

        target = payload["results"][0]["edges"][0]["target"]
        self.assertEqual(target["status"], "ambiguous")
        self.assertEqual(target["reason"], "ambiguous_guid")
        self.assertIsNone(target["path"])
        self.assertEqual(
            target["candidate_paths"],
            [
                "Assets/Ambiguous/First.prefab",
                "Assets/Ambiguous/Second.prefab",
            ],
        )
        self.assertIn(
            "ambiguous_reference",
            [warning["code"] for warning in payload["warnings"]],
        )

    def test_queries_are_deterministic_and_read_only(self):
        before_paths, before_digest = self.digest_tree()
        first, first_payload = self.query(
            "--guid",
            A_GUID.upper(),
            "--object-file-id",
            "1",
            "--direction",
            "both",
        )
        second, second_payload = self.query(
            "--guid",
            A_GUID.upper(),
            "--object-file-id",
            "1",
            "--direction",
            "both",
        )
        self.query(
            "--path",
            "Assets/Cycle/Cycle.prefab",
            "--direction",
            "incoming",
        )

        after_paths, after_digest = self.digest_tree()
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first_payload, second_payload)
        self.assertEqual(after_paths, before_paths)
        self.assertEqual(after_digest, before_digest)

    def test_component_relations_topic_is_routed_and_documents_the_contract(self):
        navigation = SKILL_ROOT / "references" / "unity-project-navigation"
        main = (navigation / "MAIN.md").read_text(encoding="utf-8")
        topic = (navigation / "component-relations.md").read_text(encoding="utf-8")

        self.assertIn("[component-relations.md](component-relations.md)", main)
        for phrase in (
            "--object-file-id",
            "--direction outgoing|incoming|both",
            "--timeout-seconds",
            "default",
            "unresolved",
            "truncated",
            "timeout",
            "source_evidence_incomplete",
            "metadata_unusable",
            "Source analyzer",
            "Completion criteria",
            "Next action",
        ):
            self.assertIn(phrase, topic)
        self.assertIsNone(
            re.search(r"[\u4e00-\u9fff]", topic),
            "Unity navigation topics must remain English-only.",
        )


if __name__ == "__main__":
    unittest.main()
