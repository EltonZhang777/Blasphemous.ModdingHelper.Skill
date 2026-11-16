import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = (
    REPOSITORY_ROOT
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT_ROOT))

from blasphemous_modding_helper import unity_serialized  # noqa: E402


SCANNER = (
    SCRIPT_ROOT / "unity_project_navigation.py"
)

MAIN_SCENE = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  m_Component:
  - component: {fileID: 4}
  - component: {fileID: 9}
  m_Name: 'Player "Hub"'
--- !u!4 &4
Transform:
  m_GameObject: {fileID: 1}
  m_Father: {fileID: 0}
--- !u!114 &9
MonoBehaviour:
  m_GameObject: {fileID: 1}
  m_Script: {fileID: 11500000, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, type: 3}
  serializedTarget: {fileID: 123, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, type: 2}
  targetObject: {fileID: 1}
"""

SIMPLE_SCENE = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  m_Component:
  - component: {fileID: 2}
  m_Name: __NAME__
--- !u!4 &2
Transform:
  m_GameObject: {fileID: 1}
  m_Father: {fileID: 0}
"""

BROKEN_SCENE = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!invalid &not-an-id
GameObject:
"""

QUOTED_SCENE = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1
GameObject:
  m_Component: # component list {fileID: 98}
  - component: {fileID: 2}
  m_Name: "Player #1" # unrelated {fileID: 96}
  note: |
    literal {fileID: 77}
  plain_note: first line
    second {fileID: 55} line
    nested:{fileID: 77} line
  same_line_plain: nested:{fileID: 76}
  quoted_note: 'first line
    nested: {fileID: 66}
    - {fileID: 55}
    last line'
  block_sequence:
  - note: |
      literal {fileID: 74}
    target: {fileID: 7}
  flow_children: [{fileID: 5}, {fileID: 6}]
  grouped: # unrelated {fileID: 99}
    child: {fileID: 8}
  # {fileID: 88}
  real: {fileID: 3, guid: cccccccccccccccccccccccccccccccc, type: 2}
--- !u!4 &2
Transform:
  m_GameObject: {fileID: 1}
"""


class UnitySceneNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "UnityProject"
        self.root.mkdir()
        self.write("ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 2017.4.40f1\n")
        self.write("Assets/Scenes/SetA_MAIN.unity", MAIN_SCENE)
        for index, layer in enumerate(("LOGIC", "LAYOUT", "DECO", "AUDIO"), start=1):
            self.write(
                f"Assets/Scenes/SetA_{layer}.unity",
                SIMPLE_SCENE.replace("__NAME__", f"{layer}Root"),
            )
        self.write("Assets/Other/Duplicate_MAIN.unity", SIMPLE_SCENE.replace("__NAME__", "DuplicateRoot"))
        self.write("Assets/Scenes/Duplicate_MAIN.unity", SIMPLE_SCENE.replace("__NAME__", "DuplicateRoot"))
        self.write("Assets/Scenes/Partial_MAIN.unity", SIMPLE_SCENE.replace("__NAME__", "PartialRoot"))
        self.write("Assets/Scenes/Partial_DECO.unity", SIMPLE_SCENE.replace("__NAME__", "PartialDeco"))
        self.write("Assets/Scenes/Standalone.unity", SIMPLE_SCENE.replace("__NAME__", "StandaloneRoot"))
        self.write("Assets/Scenes/Broken.unity", BROKEN_SCENE)
        self.write("Assets/Build/Ignored.unity", SIMPLE_SCENE.replace("__NAME__", "IgnoredBuild"))
        self.write("Assets/Textures/icon.png", b"not inspected")

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def run_scanner(self, *arguments):
        return subprocess.run(
            [sys.executable, str(SCANNER), *arguments],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def query(self, selector, value):
        return self.run_scanner(
            "scene",
            "--project",
            str(self.root),
            selector,
            value,
        )

    def query_ok(self, selector, value):
        result = self.query(selector, value)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
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
                metadata = path.stat()
                digest.update(str(metadata.st_size).encode("ascii"))
                digest.update(str(metadata.st_mtime_ns).encode("ascii"))
                digest.update(path.read_bytes())
        return paths, digest.hexdigest()

    def test_complete_scene_set_returns_all_layers_and_files(self):
        result, payload = self.query_ok("--name", "seta")

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["command"], "scene")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["query"], {"selector": "name", "name": "seta"})
        self.assertEqual(payload["project"]["unity_version"], "2017.4.40f1")
        self.assertEqual(payload["limits"], {})
        self.assertFalse(payload["truncated"])
        self.assertEqual(payload["warnings"], [])
        self.assertIsNone(payload["error"])
        self.assertEqual(
            result.stdout,
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        )

        scene = payload["results"][0]
        self.assertEqual(scene["logical_name"], "SetA")
        self.assertEqual(scene["kind"], "complete")
        self.assertEqual(
            scene["present_layers"],
            ["_MAIN", "_LOGIC", "_LAYOUT", "_DECO", "_AUDIO"],
        )
        self.assertEqual(scene["missing_layers"], [])
        self.assertEqual(len(scene["members"]), 5)
        self.assertEqual(len(scene["evidence"]), 5)
        self.assertEqual(
            [item["path"] for item in scene["evidence"]],
            [member["path"] for member in scene["members"]],
        )

        _, member_stem_payload = self.query_ok("--name", "SetA_MAIN.unity")
        self.assertEqual(member_stem_payload["results"][0]["kind"], "complete")
        self.assertEqual(member_stem_payload["results"][0]["logical_name"], "SetA")

    def test_incomplete_scene_set_reports_present_and_missing_layers_without_fabrication(self):
        _, payload = self.query_ok("--name", "Partial")

        scene = payload["results"][0]
        self.assertEqual(scene["kind"], "incomplete")
        self.assertEqual(scene["present_layers"], ["_MAIN", "_DECO"])
        self.assertEqual(scene["missing_layers"], ["_LOGIC", "_LAYOUT", "_AUDIO"])
        self.assertEqual(
            [member["path"] for member in scene["members"]],
            ["Assets/Scenes/Partial_MAIN.unity", "Assets/Scenes/Partial_DECO.unity"],
        )
        self.assertEqual(
            [warning["code"] for warning in payload["warnings"]],
            ["incomplete_scene_set"],
        )

    def test_standalone_scene_is_queryable_by_name(self):
        _, payload = self.query_ok("--name", "Standalone")

        scene = payload["results"][0]
        self.assertEqual(scene["kind"], "standalone")
        self.assertEqual(scene["present_layers"], [])
        self.assertEqual(scene["missing_layers"], [])
        self.assertEqual(
            scene["members"],
            [{"layer": None, "path": "Assets/Scenes/Standalone.unity"}],
        )
        self.assertEqual(scene["evidence"][0]["objects"][0]["name"], "StandaloneRoot")

        _, direct_payload = self.query_ok("--path", "Assets/Scenes/Standalone.unity")
        self.assertEqual(direct_payload["results"][0]["kind"], "standalone")

    def test_direct_path_returns_exact_file_and_set_membership(self):
        relative = "Assets/Scenes/SetA_DECO.unity"
        _, payload = self.query_ok("--path", relative)

        scene = payload["results"][0]
        self.assertEqual(scene["kind"], "complete")
        self.assertEqual(scene["requested_path"], relative)
        self.assertEqual(len(scene["members"]), 5)
        self.assertEqual(len(scene["evidence"]), 1)
        self.assertEqual(scene["evidence"][0]["path"], relative)
        self.assertEqual(scene["evidence"][0]["objects"][0]["name"], "DECORoot")

        _, absolute_payload = self.query_ok("--path", str(self.root / relative))
        self.assertEqual(
            absolute_payload["results"][0]["evidence"][0]["path"],
            relative,
        )

    def test_direct_path_to_incomplete_member_reports_group_state(self):
        _, payload = self.query_ok("--path", "Assets/Scenes/Partial_DECO.unity")

        scene = payload["results"][0]
        self.assertEqual(scene["kind"], "incomplete")
        self.assertEqual(scene["missing_layers"], ["_LOGIC", "_LAYOUT", "_AUDIO"])
        self.assertEqual(scene["requested_path"], "Assets/Scenes/Partial_DECO.unity")

    def test_duplicate_logical_name_is_ambiguous(self):
        result = self.query("--name", "Duplicate")
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        self.assertEqual(payload["status"], "ambiguous")
        self.assertEqual(
            [scene["directory"] for scene in payload["results"]],
            ["Assets/Other", "Assets/Scenes"],
        )
        self.assertTrue(all(not scene["evidence"] for scene in payload["results"]))
        self.assertEqual(
            [warning["code"] for warning in payload["warnings"]],
            ["ambiguous_scene_name"],
        )

    def test_missing_name_and_missing_direct_path_are_not_found(self):
        for selector, value in (
            ("--name", "DoesNotExist"),
            ("--path", "Assets/Scenes/DoesNotExist.unity"),
        ):
            with self.subTest(selector=selector):
                result = self.query(selector, value)
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stderr, "")
                self.assertEqual(payload["status"], "not_found")
                self.assertEqual(payload["results"], [])
                self.assertEqual(payload["warnings"][0]["code"], "scene_not_found")

    def test_parent_traversal_is_rejected(self):
        result = self.query("--path", "Assets/Scenes/../Scenes/Standalone.unity")
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 3)
        self.assertEqual(payload["status"], "invalid_query")
        self.assertEqual(payload["error"]["code"], "path_traversal")
        self.assertEqual(payload["warnings"][0]["code"], "path_traversal")

    def test_scene_requires_exactly_one_selector(self):
        missing = self.run_scanner("scene", "--project", str(self.root))
        both = self.run_scanner(
            "scene",
            "--project",
            str(self.root),
            "--path",
            "Assets/Scenes/Standalone.unity",
            "--name",
            "Standalone",
        )

        for result in (missing, both):
            with self.subTest(arguments=result.args):
                self.assertEqual(result.returncode, 3)
                self.assertEqual(result.stderr, "")
                payload = json.loads(result.stdout)
                self.assertEqual(payload["status"], "invalid_query")
                self.assertEqual(payload["error"]["code"], "invalid_scene_selector")

    def test_unknown_scene_selector_returns_json(self):
        result = self.run_scanner(
            "scene",
            "--project",
            str(self.root),
            "--guid",
            "abc",
        )

        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "invalid_query")
        self.assertEqual(payload["error"]["code"], "invalid_scene_selector")

    @unittest.skipUnless(os.name != "nt", "POSIX expanduser failure test")
    def test_missing_user_expansion_returns_json(self):
        result = self.run_scanner(
            "scene",
            "--project",
            "~codex_no_such_user_12345",
            "--name",
            "Standalone",
        )

        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "invalid_project")

    def test_malformed_direct_target_returns_structured_failure(self):
        result = self.query("--path", "Assets/Scenes/Broken.unity")
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stderr, "")
        self.assertEqual(payload["status"], "invalid_query")
        self.assertEqual(payload["error"]["code"], "malformed_serialized")
        self.assertEqual(payload["warnings"][0]["code"], "malformed_document")
        self.assertEqual(payload["results"][0]["evidence"][0]["status"], "invalid_query")
        self.assertEqual(payload["results"][0]["evidence"][0]["objects"], [])

    def test_excluded_path_is_rejected_and_excluded_name_is_not_discovered(self):
        ignored_path = "Assets/Build/Ignored.unity"
        result = self.query("--path", ignored_path)
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 3)
        self.assertEqual(payload["status"], "invalid_query")
        self.assertEqual(payload["error"]["code"], "excluded_path")
        self.assertEqual(payload["warnings"][0]["code"], "excluded_path")
        self.assertEqual(payload["results"], [])

        ignored_name = self.query("--name", "Ignored")
        self.assertEqual(ignored_name.returncode, 2)
        self.assertEqual(json.loads(ignored_name.stdout)["status"], "not_found")

    def test_excluded_path_is_rejected_regardless_of_case(self):
        if os.name != "nt":
            self.write(
                "Assets/build/IgnoredLower.unity",
                SIMPLE_SCENE.replace("__NAME__", "IgnoredLower"),
            )

        result = self.query("--path", "Assets/build/Ignored.unity")
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 3)
        self.assertEqual(payload["status"], "invalid_query")
        self.assertEqual(payload["error"]["code"], "excluded_path")

    @unittest.skipUnless(os.name == "nt", "Windows path alias test")
    def test_windows_path_aliases_are_rejected_and_canonicalized(self):
        alias = self.query("--path", "Assets/Build./Ignored.unity")
        _, canonical = self.query_ok("--path", "assets/scenes/standalone.unity")

        self.assertEqual(alias.returncode, 3)
        alias_payload = json.loads(alias.stdout)
        self.assertEqual(alias_payload["status"], "invalid_query")
        self.assertEqual(alias_payload["error"]["code"], "excluded_path")
        self.assertEqual(
            canonical["results"][0]["requested_path"],
            "Assets/Scenes/Standalone.unity",
        )
        self.assertEqual(
            canonical["results"][0]["evidence"][0]["path"],
            "Assets/Scenes/Standalone.unity",
        )

    def test_unity_directory_is_not_a_scene_set_member(self):
        self.write("Assets/Scenes/DirSet_LOGIC.unity", SIMPLE_SCENE.replace("__NAME__", "DirLogic"))
        for layer in ("MAIN", "LAYOUT", "DECO", "AUDIO"):
            (self.root / "Assets" / "Scenes" / f"DirSet_{layer}.unity").mkdir()

        _, payload = self.query_ok("--path", "Assets/Scenes/DirSet_LOGIC.unity")

        scene = payload["results"][0]
        self.assertEqual(scene["kind"], "incomplete")
        self.assertEqual(scene["present_layers"], ["_LOGIC"])
        self.assertEqual(
            [member["path"] for member in scene["members"]],
            ["Assets/Scenes/DirSet_LOGIC.unity"],
        )

    def test_serialized_evidence_is_observed_and_file_scoped(self):
        _, payload = self.query_ok("--name", "SetA")

        main = next(
            item
            for item in payload["results"][0]["evidence"]
            if item["path"] == "Assets/Scenes/SetA_MAIN.unity"
        )
        logic = next(
            item
            for item in payload["results"][0]["evidence"]
            if item["path"] == "Assets/Scenes/SetA_LOGIC.unity"
        )
        game_object = next(item for item in main["objects"] if item["class_id"] == 1)
        transform = next(item for item in main["objects"] if item["class_id"] == 4)
        behaviour = next(item for item in main["objects"] if item["class_id"] == 114)

        self.assertEqual(game_object["name"], 'Player "Hub"')
        self.assertEqual(game_object["component_file_ids"], [4, 9])
        self.assertEqual(transform["container_file_id"], 1)
        self.assertEqual(behaviour["container_file_id"], 1)
        self.assertEqual(behaviour["class_name"], "MonoBehaviour")
        references = {reference["field"]: reference for reference in behaviour["references"]}
        self.assertEqual(references["m_Script"]["scope"], "external")
        self.assertEqual(
            references["m_Script"]["guid"],
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        self.assertEqual(references["targetObject"]["scope"], "local")
        self.assertIsInstance(references["m_Script"]["line"], int)
        self.assertNotIn("resolved_path", references["m_Script"])
        self.assertNotIn("script_name", behaviour)
        self.assertNotIn("behavior", behaviour)

        self.assertEqual(logic["objects"][0]["file_id"], game_object["file_id"])
        self.assertEqual(logic["objects"][0]["name"], "LOGICRoot")

    def test_quoted_and_commented_file_ids_are_not_references(self):
        self.write("Assets/Scenes/Quoted.unity", QUOTED_SCENE)

        _, payload = self.query_ok("--path", "Assets/Scenes/Quoted.unity")

        evidence = payload["results"][0]["evidence"][0]
        game_object = next(item for item in evidence["objects"] if item["class_id"] == 1)
        file_ids = [reference["file_id"] for reference in game_object["references"]]
        self.assertEqual(sorted(file_ids), [2, 3, 5, 6, 7, 8])
        self.assertEqual(game_object["name"], "Player #1")
        self.assertEqual(
            {
                reference["file_id"]: reference["field"]
                for reference in game_object["references"]
            },
            {
                2: "m_Component.component",
                3: "real",
                5: "flow_children",
                6: "flow_children",
                7: "target",
                8: "child",
            },
        )
        self.assertEqual(game_object["component_file_ids"], [2])
        self.assertEqual(evidence["reference_count"], 7)

    def test_bare_sequence_block_scalars_do_not_expose_references(self):
        bare = unity_serialized._structure_lines(
            ["- |", "  literal {fileID: 72}", "real: {fileID: 9}"]
        )
        nested_bare = unity_serialized._structure_lines(
            ["  - |", "    literal {fileID: 73}", "  real: {fileID: 9}"]
        )
        spaced_block = unity_serialized._structure_lines(
            [
                "  -   note: |",
                "        literal {fileID: 74}",
                "      target: {fileID: 11}",
            ]
        )
        spaced_plain = unity_serialized._structure_lines(
            [
                "-   key: value",
                "    sibling: {fileID: 10}",
            ]
        )

        self.assertNotIn("fileID: 72", "".join(bare))
        self.assertIn("fileID: 9", bare[-1])
        self.assertNotIn("fileID: 73", "".join(nested_bare))
        self.assertIn("fileID: 9", nested_bare[-1])
        self.assertNotIn("fileID: 74", "".join(spaced_block))
        self.assertIn("fileID: 11", spaced_block[-1])
        self.assertIn("fileID: 10", spaced_plain[-1])

    def test_scene_queries_are_read_only(self):
        before_paths, before_digest = self.digest_tree()

        self.query("--name", "SetA")
        self.query("--path", "Assets/Scenes/Partial_MAIN.unity")
        self.query("--path", "Assets/Scenes/Broken.unity")
        self.query("--path", "Assets/Build/Ignored.unity")

        after_paths, after_digest = self.digest_tree()
        self.assertEqual(after_paths, before_paths)
        self.assertEqual(after_digest, before_digest)


if __name__ == "__main__":
    unittest.main()
