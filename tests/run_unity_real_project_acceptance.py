#!/usr/bin/env python3
"""Opt-in acceptance runner for one exported real Unity project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCANNER = (
    REPOSITORY_ROOT
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
    / "unity_project_navigation.py"
)
DEFAULT_MANIFEST = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "unity-real-project-smoke.json"
)
PROJECT_ENV = "BLASPHEMOUS_UNITY_PROJECT_PATH"
SCANNER_TIMEOUT_SECONDS = 240


class SmokeFailure(RuntimeError):
    """One real-project acceptance expectation failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _read_json(path: Path) -> Dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SmokeFailure(f"Could not read JSON evidence at {path}: {error}") from error
    if not isinstance(value, dict):
        raise SmokeFailure(f"JSON evidence at {path} is not an object.")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_paths(root: Path) -> Tuple[Set[str], int, int, int]:
    paths: Set[str] = set()
    assets_files = 0
    file_count = 0
    directory_count = 0
    for directory, names, filenames in os.walk(
        str(root),
        topdown=True,
        followlinks=False,
    ):
        base = Path(directory)
        for name in names:
            relative = (base / name).relative_to(root).as_posix()
            paths.add("dir:" + relative)
            directory_count += 1
        for name in filenames:
            relative = (base / name).relative_to(root).as_posix()
            paths.add("file:" + relative)
            file_count += 1
            if relative.casefold().startswith("assets/"):
                assets_files += 1
    return paths, assets_files, file_count, directory_count


def _hashes(root: Path, relative_paths: Iterable[str]) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for relative in relative_paths:
        path = root / relative
        _require(path.is_file(), f"Representative file is missing: {relative}")
        hashes[relative] = _sha256(path)
    return hashes


def _scanner_command(
    arguments: Sequence[str],
    project_root: Path,
) -> List[str]:
    return [
        item.replace(str(project_root), "<UNITY_PROJECT_ROOT>")
        for item in arguments
    ]


def _run_scanner(
    python_executable: str,
    project_root: Path,
    arguments: Sequence[str],
) -> Tuple[Dict[str, object], float]:
    command = [python_executable, str(SCANNER), *arguments]
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=str(REPOSITORY_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
            timeout=SCANNER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise SmokeFailure(
            "Scanner command exceeded the outer acceptance timeout: "
            + " ".join(command)
        ) from error
    elapsed = round(time.monotonic() - started, 2)
    if result.returncode != 0:
        raise SmokeFailure(
            f"Scanner command failed with exit code {result.returncode}: "
            f"{' '.join(command)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SmokeFailure(
            f"Scanner output was not JSON: {' '.join(command)}: {error}"
        ) from error
    _require(isinstance(payload, dict), "Scanner output envelope is not an object.")
    return payload, elapsed


def _query_record(
    name: str,
    arguments: Sequence[str],
    project_root: Path,
    payload: Dict[str, object],
    elapsed: float,
) -> Dict[str, object]:
    return {
        "query": name,
        "command": _scanner_command(arguments, project_root),
        "status": payload.get("status"),
        "elapsed_seconds": elapsed,
    }


def _verify_project_summary(
    payload: Dict[str, object],
    assets_total_files: int,
    manifest: Dict[str, object],
) -> None:
    baseline = manifest["baseline"]
    results = payload.get("results")
    _require(payload.get("status") == "ok", "Project summary status is not ok.")
    _require(
        payload["project"]["unity_version"] == manifest["unity_version"],
        "Unity version does not match the locked real-project baseline.",
    )
    _require(
        isinstance(results, list) and len(results) == 1,
        "Project summary must return one result.",
    )
    counts = results[0]["file_counts"]
    for key in ("unity", "prefab", "asset", "cs", "meta"):
        expected = baseline[f"{key}_files"]
        _require(
            counts[key] == expected,
            f"Project summary {key} count {counts[key]} != {expected}.",
        )
    _require(
        counts["total"] == baseline["scanner_total_files"],
        "Project summary total file count drifted.",
    )
    _require(
        assets_total_files == baseline["assets_total_files"],
        "The independent Assets file inventory drifted.",
    )
    scenes = results[0]["scene_counts"]
    for key in (
        "complete_sets",
        "incomplete_sets",
        "standalone",
    ):
        manifest_key = {
            "complete_sets": "complete_scene_sets",
            "incomplete_sets": "incomplete_scene_sets",
            "standalone": "standalone_scenes",
        }[key]
        _require(
            scenes[key] == baseline[manifest_key],
            f"Project summary {key} count drifted.",
        )
    _require(payload.get("warnings") == [], "Project summary reported warnings.")


def _verify_scene_set(payload: Dict[str, object], manifest: Dict[str, object]) -> None:
    expected = manifest["scene_set"]
    _require(payload.get("status") == "ok", "Scene-set query status is not ok.")
    results = payload.get("results")
    _require(
        isinstance(results, list) and len(results) == 1,
        "Scene-set query must return one result.",
    )
    result = results[0]
    _require(result["kind"] == expected["kind"], "Scene-set kind drifted.")
    _require(
        list(result["present_layers"]) == list(expected["present_layers"]),
        "Scene-set present layers drifted.",
    )
    _require(result["missing_layers"] == [], "Complete scene set reports missing layers.")
    _require(
        [member["path"] for member in result["members"]]
        == list(expected["members"]),
        "Scene-set member paths drifted.",
    )
    _require(
        result["object_count"] == expected["object_count"],
        "Scene-set object count drifted.",
    )
    _require(
        result["reference_count"] == expected["reference_count"],
        "Scene-set reference count drifted.",
    )
    _require(payload.get("warnings") == [], "Scene-set query reported warnings.")


def _verify_standalone_scene(
    payload: Dict[str, object],
    manifest: Dict[str, object],
) -> None:
    expected = manifest["standalone_scene"]
    _require(payload.get("status") == "ok", "Standalone scene status is not ok.")
    result = payload["results"][0]
    _require(result["kind"] == expected["kind"], "Standalone scene kind drifted.")
    _require(
        result["requested_path"] == expected["path"],
        "Standalone scene requested path drifted.",
    )
    _require(
        [member["path"] for member in result["members"]] == list(expected["members"]),
        "Standalone scene membership drifted.",
    )
    _require(
        result["object_count"] == expected["object_count"],
        "Standalone scene object count drifted.",
    )
    _require(
        result["reference_count"] == expected["reference_count"],
        "Standalone scene reference count drifted.",
    )
    _require(payload.get("warnings") == [], "Standalone scene reported warnings.")


def _verify_prefab(payload: Dict[str, object], manifest: Dict[str, object]) -> None:
    expected = manifest["prefab"]
    _require(payload.get("status") == "ok", "Prefab query status is not ok.")
    result = payload["results"][0]
    _require(result["path"] == expected["path"], "Prefab path drifted.")
    _require(result["guid"] == expected["guid"], "Prefab GUID drifted.")
    _require(
        result["evidence_kind"] == expected["evidence_kind"],
        "Prefab evidence kind drifted.",
    )
    _require(
        result["object_count"] == expected["object_count"],
        "Prefab object count drifted.",
    )
    _require(
        result["reference_count"] == expected["reference_count"],
        "Prefab reference count drifted.",
    )
    _require(
        [item["file_id"] for item in result["objects"]]
        == list(expected["object_file_ids"]),
        "Prefab object file IDs drifted.",
    )
    _require(
        payload["limits"]["source_prefab_hierarchy"] == "not_available",
        "Prefab hierarchy limit is not explicit.",
    )
    _require(payload.get("warnings") == [], "Prefab query reported warnings.")


def _verify_script(payload: Dict[str, object], manifest: Dict[str, object]) -> None:
    expected = manifest["script"]
    _require(payload.get("status") == "ok", "Script query status is not ok.")
    result = payload["results"][0]
    for key in ("path", "name", "guid"):
        _require(result[key] == expected[key], f"Script {key} drifted.")
    _require(result["type"] == "cs", "Script result type is not cs.")
    _require(
        result["metadata"]["status"] == expected["metadata_status"],
        "Script metadata status drifted.",
    )
    _require(
        payload["limits"] == {"csharp_parsed": False},
        "Script query did not state the no-C#-parsing limit.",
    )
    _require(payload.get("warnings") == [], "Script query reported warnings.")


def _verify_guid_lookup(
    payload: Dict[str, object],
    manifest: Dict[str, object],
) -> None:
    expected = manifest["guid_lookup"]
    _require(payload.get("status") == "ok", "GUID lookup status is not ok.")
    result = payload["results"][0]
    _require(result["path"] == expected["path"], "GUID lookup path drifted.")
    _require(result["type"] == expected["type"], "GUID lookup type drifted.")
    _require(result["guid"] == expected["guid"], "GUID lookup GUID drifted.")
    _require(payload.get("warnings") == [], "GUID lookup reported warnings.")


def _verify_references(
    payload: Dict[str, object],
    manifest: Dict[str, object],
) -> None:
    expected = manifest["references"]
    _require(payload.get("status") == expected["status"], "Reference status drifted.")
    _require(payload.get("complete") is expected["complete"], "Reference completeness drifted.")
    _require(payload.get("truncated") is False, "Reference query is truncated.")
    _require(payload.get("incomplete_reasons") == [], "Reference query is incomplete.")
    _require(payload["root"]["path"] == expected["path"], "Reference root path drifted.")
    _require(
        payload["root"]["object_file_id"] == expected["object_file_id"],
        "Reference root object ID drifted.",
    )
    results = payload.get("results")
    _require(
        isinstance(results, list) and len(results) == 1,
        "Reference query must return one traversal.",
    )
    traversal = results[0]
    for key in ("direction", "node_count", "edge_count"):
        _require(traversal[key] == expected[key], f"Reference {key} drifted.")
    actual_edges = {
        (
            edge["field"],
            edge["scope"],
            edge["target"]["path"],
            edge["target"]["file_id"],
            edge["target"]["status"],
            edge["target"]["reason"],
        )
        for edge in traversal["edges"]
    }
    for edge in expected["edges"]:
        identity = (
            edge["field"],
            edge["scope"],
            edge["target_path"],
            edge["target_file_id"],
            edge["target_status"],
            edge["target_reason"],
        )
        _require(identity in actual_edges, f"Expected reference edge is missing: {identity}")
    warning_codes = [warning["code"] for warning in payload.get("warnings", [])]
    _require("timeout" not in warning_codes, "Reference query timed out.")
    _require("result_limit" not in warning_codes, "Reference query hit its result limit.")


def _blocked_report(project: Optional[str], reason: str) -> Dict[str, object]:
    return {
        "schema_version": 1,
        "report": "unity-project-navigation-real-project",
        "evidence_mode": "real_project",
        "synthetic_evidence": (
            "separate: tests/test_modding_api_acceptance.py; "
            "synthetic success is not substituted for this report"
        ),
        "status": "blocked",
        "project": {"root": project},
        "commands": [],
        "completion_evidence": {},
        "read_only": None,
        "blocked_reason": reason,
        "error": None,
        "next_action": (
            f"Provide a readable UTinyRipper export with an Assets directory through "
            f"--project or {PROJECT_ENV}, then rerun this runner."
        ),
    }


def run(
    python_executable: str,
    project: Optional[str],
    manifest_path: Path,
) -> Tuple[int, Dict[str, object]]:
    if not project:
        return 2, _blocked_report(
            project,
            f"No real Unity project path was supplied through --project or {PROJECT_ENV}.",
        )
    project_root = Path(project).expanduser()
    if not project_root.is_dir():
        return 2, _blocked_report(
            str(project_root),
            "The supplied real Unity project root is not a readable directory.",
        )
    project_root = project_root.resolve()
    if not (project_root / "Assets").is_dir():
        return 2, _blocked_report(
            str(project_root),
            "The supplied real Unity project root has no Assets directory.",
        )
    if not (project_root / "ProjectSettings" / "ProjectVersion.txt").is_file():
        return 2, _blocked_report(
            str(project_root),
            "The supplied real Unity project root has no ProjectVersion.txt evidence.",
        )

    report: Dict[str, object] = {
        "schema_version": 1,
        "report": "unity-project-navigation-real-project",
        "evidence_mode": "real_project",
        "synthetic_evidence": (
            "separate: tests/test_modding_api_acceptance.py; "
            "synthetic success is not substituted for this report"
        ),
        "status": "failed",
        "project": {"root": str(project_root)},
        "commands": [],
        "completion_evidence": {},
        "read_only": None,
        "blocked_reason": None,
        "error": None,
        "next_action": "Fix the failed real-project evidence and rerun the runner.",
    }
    try:
        manifest = _read_json(manifest_path)
        _require(
            manifest.get("schema_version") == 1,
            "Real-project smoke manifest schema is unsupported.",
        )
        before_paths, before_assets, before_files, before_dirs = _snapshot_paths(
            project_root
        )
        representative_files = manifest["representative_files"]
        before_hashes = _hashes(project_root, representative_files)

        commands: List[Dict[str, object]] = []
        project_args = ["project", "--project", str(project_root)]
        project_payload, elapsed = _run_scanner(
            python_executable,
            project_root,
            project_args,
        )
        commands.append(
            _query_record(
                "project",
                project_args,
                project_root,
                project_payload,
                elapsed,
            )
        )
        _verify_project_summary(
            project_payload,
            before_assets,
            manifest,
        )

        scene_args = [
            "scene",
            "--project",
            str(project_root),
            "--name",
            str(manifest["scene_set"]["name"]),
        ]
        scene_payload, elapsed = _run_scanner(
            python_executable,
            project_root,
            scene_args,
        )
        commands.append(
            _query_record(
                "scene_set",
                scene_args,
                project_root,
                scene_payload,
                elapsed,
            )
        )
        _verify_scene_set(scene_payload, manifest)

        standalone_args = [
            "scene",
            "--project",
            str(project_root),
            "--path",
            str(manifest["standalone_scene"]["path"]),
        ]
        standalone_payload, elapsed = _run_scanner(
            python_executable,
            project_root,
            standalone_args,
        )
        commands.append(
            _query_record(
                "standalone_scene",
                standalone_args,
                project_root,
                standalone_payload,
                elapsed,
            )
        )
        _verify_standalone_scene(standalone_payload, manifest)

        prefab_args = [
            "prefab",
            "--project",
            str(project_root),
            "--path",
            str(manifest["prefab"]["path"]),
        ]
        prefab_payload, elapsed = _run_scanner(
            python_executable,
            project_root,
            prefab_args,
        )
        commands.append(
            _query_record(
                "prefab",
                prefab_args,
                project_root,
                prefab_payload,
                elapsed,
            )
        )
        _verify_prefab(prefab_payload, manifest)

        script_args = [
            "script",
            "--project",
            str(project_root),
            "--path",
            str(manifest["script"]["path"]),
        ]
        script_payload, elapsed = _run_scanner(
            python_executable,
            project_root,
            script_args,
        )
        commands.append(
            _query_record(
                "script",
                script_args,
                project_root,
                script_payload,
                elapsed,
            )
        )
        _verify_script(script_payload, manifest)

        guid_args = [
            "asset",
            "--project",
            str(project_root),
            "--guid",
            str(manifest["guid_lookup"]["guid"]),
        ]
        guid_payload, elapsed = _run_scanner(
            python_executable,
            project_root,
            guid_args,
        )
        commands.append(
            _query_record(
                "guid_lookup",
                guid_args,
                project_root,
                guid_payload,
                elapsed,
            )
        )
        _verify_guid_lookup(guid_payload, manifest)

        reference_expected = manifest["references"]
        reference_args = [
            "references",
            "--project",
            str(project_root),
            "--path",
            str(reference_expected["path"]),
            "--object-file-id",
            str(reference_expected["object_file_id"]),
            "--direction",
            str(reference_expected["direction"]),
            "--depth",
            str(reference_expected["depth"]),
            "--limit",
            str(reference_expected["limit"]),
            "--timeout-seconds",
            str(reference_expected["timeout_seconds"]),
        ]
        reference_payload, elapsed = _run_scanner(
            python_executable,
            project_root,
            reference_args,
        )
        commands.append(
            _query_record(
                "references",
                reference_args,
                project_root,
                reference_payload,
                elapsed,
            )
        )
        _verify_references(reference_payload, manifest)

        after_paths, after_assets, after_files, after_dirs = _snapshot_paths(
            project_root
        )
        after_hashes = _hashes(project_root, representative_files)
        added_paths = sorted(after_paths - before_paths)
        removed_paths = sorted(before_paths - after_paths)
        _require(not added_paths, f"Real-project path inventory gained entries: {added_paths}")
        _require(not removed_paths, f"Real-project path inventory lost entries: {removed_paths}")
        _require(
            before_hashes == after_hashes,
            "One or more representative files changed during the smoke.",
        )
        _require(
            (before_assets, before_files, before_dirs)
            == (after_assets, after_files, after_dirs),
            "Real-project file or directory counts changed during the smoke.",
        )

        report["status"] = "ok"
        report["commands"] = commands
        scene_result = scene_payload["results"][0]
        standalone_result = standalone_payload["results"][0]
        report["completion_evidence"] = {
            "unity_version": project_payload["project"]["unity_version"],
            "baseline": {
                "assets_total_files": before_assets,
                "scanner_total_files": project_payload["results"][0]["file_counts"]["total"],
                "unity_files": project_payload["results"][0]["file_counts"]["unity"],
                "prefab_files": project_payload["results"][0]["file_counts"]["prefab"],
                "asset_files": project_payload["results"][0]["file_counts"]["asset"],
                "cs_files": project_payload["results"][0]["file_counts"]["cs"],
                "meta_files": project_payload["results"][0]["file_counts"]["meta"],
                "complete_scene_sets": project_payload["results"][0]["scene_counts"]["complete_sets"],
                "standalone_scenes": project_payload["results"][0]["scene_counts"]["standalone"],
            },
            "scene_set": {
                key: scene_result[key]
                for key in (
                    "logical_name",
                    "directory",
                    "kind",
                    "present_layers",
                    "missing_layers",
                    "members",
                    "object_count",
                    "reference_count",
                )
            },
            "standalone_scene": {
                key: standalone_result[key]
                for key in (
                    "logical_name",
                    "directory",
                    "kind",
                    "members",
                    "requested_path",
                    "object_count",
                    "reference_count",
                )
            },
            "prefab": prefab_payload["results"][0],
            "script": script_payload["results"][0],
            "guid_lookup": guid_payload["results"][0],
            "references": reference_payload["results"][0],
        }
        report["read_only"] = {
            "path_inventory_entries_before": len(before_paths),
            "path_inventory_entries_after": len(after_paths),
            "file_count_before": before_files,
            "file_count_after": after_files,
            "directory_count_before": before_dirs,
            "directory_count_after": after_dirs,
            "added_paths": added_paths,
            "removed_paths": removed_paths,
            "representative_files": [
                {
                    "path": relative,
                    "sha256": before_hashes[relative],
                    "unchanged": before_hashes[relative] == after_hashes[relative],
                }
                for relative in representative_files
            ],
        }
        report["next_action"] = (
            "Record this real-project report separately from synthetic results, "
            "then close the acceptance ticket."
        )
        return 0, report
    except (SmokeFailure, KeyError, IndexError, TypeError) as error:
        report["error"] = str(error)
        report["next_action"] = (
            "Fix the real-project evidence or manifest drift and rerun; do not "
            "substitute the synthetic suite for this report."
        )
        return 1, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the opt-in real exported Unity project navigation smoke."
    )
    parser.add_argument(
        "--project",
        default=os.environ.get(PROJECT_ENV),
        help=f"Real Unity project root; defaults to {PROJECT_ENV}.",
    )
    parser.add_argument(
        "--python",
        dest="python_executable",
        default=sys.executable,
        help="Python executable for scanner child processes.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Fixed real-project smoke manifest.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    return_code, report = run(
        args.python_executable,
        args.project,
        args.manifest,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
