#!/usr/bin/env python3
"""Opt-in acceptance runner for one exported real Unity project."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
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
sys.path.insert(0, str(SCANNER.parent))

from blasphemous_modding_helper.unity_project import _is_link_like  # noqa: E402

DEFAULT_MANIFEST = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "unity-real-project-smoke.json"
)
PROJECT_ENV = "BLASPHEMOUS_UNITY_PROJECT_PATH"
SCANNER_TIMEOUT_SECONDS = 600
BINDINGS_LIMIT = 1000
BINDINGS_TIMEOUT_SECONDS = 300
TYPICAL_SCRIPT_FILE_ID = "11500000"


class SmokeFailure(RuntimeError):
    """One real-project acceptance expectation failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _read_json(path: Path) -> Dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SmokeFailure("Could not read local real-project manifest.") from error
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

    def raise_walk_error(error: OSError) -> None:
        raise SmokeFailure(
            f"Project path inventory could not be read: {error}"
        ) from error

    for directory, names, filenames in os.walk(
        str(root),
        topdown=True,
        followlinks=False,
        onerror=raise_walk_error,
    ):
        base = Path(directory)
        kept_names = []
        for name in names:
            child = base / name
            if not _is_link_like(child):
                kept_names.append(name)
                continue
            relative = child.relative_to(root).as_posix()
            paths.add("dir:" + relative)
            directory_count += 1
        names[:] = kept_names
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
    return [_redact_project_root(item, project_root) for item in arguments]


def _redact_project_root(value: object, *project_roots: Path) -> str:
    variants = set()
    for project_root in project_roots:
        if not project_root.is_absolute():
            continue
        variants.update({str(project_root), project_root.as_posix()})
    variants.update(
        variant.replace("\\", "\\\\")
        for variant in tuple(variants)
        if "\\" in variant
    )
    text = str(value)
    flags = re.IGNORECASE if os.name == "nt" else 0
    for variant in sorted(variants, key=len, reverse=True):
        text = re.sub(
            re.escape(variant),
            "<UNITY_PROJECT_ROOT>",
            text,
            flags=flags,
        )
    return text


def _run_scanner_with_size(
    python_executable: str,
    project_root: Path,
    arguments: Sequence[str],
    allow_incomplete: bool = False,
) -> Tuple[Dict[str, object], float, int]:
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
            + " ".join(_scanner_command(command, project_root))
        ) from error
    elapsed = round(time.monotonic() - started, 2)
    if result.returncode != 0 and not (
        allow_incomplete and result.returncode in {3, 4}
    ):
        raise SmokeFailure(
            f"Scanner command failed with exit code {result.returncode}: "
            f"{' '.join(_scanner_command(command, project_root))}\n"
            f"stdout:\n{_redact_project_root(result.stdout, project_root)}\n"
            f"stderr:\n{_redact_project_root(result.stderr, project_root)}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SmokeFailure(
            "Scanner output was not JSON: "
            f"{' '.join(_scanner_command(command, project_root))}: {error}"
        ) from error
    _require(isinstance(payload, dict), "Scanner output envelope is not an object.")
    if result.returncode != 0 and not (
        payload.get("status") in {"partial", "timeout"}
        and payload.get("scan_coverage") == "partial"
    ):
        raise SmokeFailure(
            "Scanner command failed with exit code "
            f"{result.returncode}: "
            f"{' '.join(_scanner_command(command, project_root))}"
        )
    return payload, elapsed, len(result.stdout.encode("utf-8"))


def _run_scanner(
    python_executable: str,
    project_root: Path,
    arguments: Sequence[str],
) -> Tuple[Dict[str, object], float]:
    payload, elapsed, _ = _run_scanner_with_size(
        python_executable,
        project_root,
        arguments,
    )
    return payload, elapsed


def _query_record(
    name: str,
    arguments: Sequence[str],
    project_root: Path,
    payload: Dict[str, object],
    elapsed: float,
    serialized_bytes: Optional[int] = None,
) -> Dict[str, object]:
    record = {
        "query": name,
        "command": _scanner_command(arguments, project_root),
        "status": payload.get("status"),
        "scan_coverage": payload.get("scan_coverage"),
        "elapsed_seconds": elapsed,
    }
    if serialized_bytes is not None:
        record["serialized_bytes"] = serialized_bytes
    return record


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


def _verify_binding_samples(samples: Dict[str, Dict[str, object]]) -> None:
    cs_sample = samples["cs"]
    _require(cs_sample["reference_shape"] == "structured", "CS sample is not structured.")
    _require(cs_sample["target_asset_kind"] == "cs", "CS sample target kind drifted.")
    _require(cs_sample["asset_resolution"] == "resolved", "CS sample is unresolved.")
    _require(
        cs_sample["script_object_resolution"] == "asset_level_only",
        "CS sample claims more than asset-level resolution.",
    )
    _require(bool(cs_sample["target_asset_path"]), "CS sample has no target path.")

    dll_sample = samples["dll"]
    _require(dll_sample["target_asset_kind"] == "binary", "DLL sample target kind drifted.")
    _require(
        str(dll_sample["target_asset_path"]).casefold().endswith(".dll"),
        "DLL sample target is not a DLL.",
    )
    _require(dll_sample["asset_resolution"] == "resolved", "DLL sample is unresolved.")
    _require(
        dll_sample["script_object_resolution"] == "not_verifiable_binary",
        "DLL sample claims a verifiable script object.",
    )

    unresolved_sample = samples["unresolved"]
    _require(
        unresolved_sample["target_asset_kind"] == "unresolved",
        "Unresolved sample target kind drifted.",
    )
    _require(
        unresolved_sample["asset_resolution"] == "missing",
        "Unresolved sample asset resolution drifted.",
    )
    _require(
        unresolved_sample["asset_resolution_reason"] == "missing_meta",
        "Unresolved sample reason drifted.",
    )
    _require(
        unresolved_sample["script_object_resolution"] == "not_applicable",
        "Unresolved sample object resolution drifted.",
    )

    null_sample = samples["null"]
    _require(null_sample["reference_shape"] == "null", "Null sample shape drifted.")
    _require(
        null_sample["m_script_file_id"] == "0",
        "Null sample file ID is not zero.",
    )
    _require(
        null_sample["asset_resolution"] == "not_applicable",
        "Null sample asset resolution drifted.",
    )
    _require(
        null_sample["script_object_resolution"] == "not_applicable",
        "Null sample object resolution drifted.",
    )

    non_typical = samples["non_typical_file_id"]
    _require(
        non_typical["reference_shape"] == "structured",
        "Non-typical file-ID sample is not structured.",
    )
    _require(
        non_typical["m_script_file_id"] != TYPICAL_SCRIPT_FILE_ID,
        "Non-typical file-ID sample uses the typical value.",
    )
    _require(samples["asset"]["source_asset_kind"] == "asset", "Asset sample drifted.")
    if "malformed" in samples:
        malformed = samples["malformed"]
        _require(
            malformed["reference_shape"] == "malformed",
            "Malformed sample shape drifted.",
        )
        _require(
            malformed["asset_resolution"] == "not_applicable",
            "Malformed sample asset resolution drifted.",
        )
    if "packages" in samples:
        package = samples["packages"]
        paths = (package["source_asset_path"], package["target_asset_path"])
        _require(
            any(str(path or "").startswith("Packages/") for path in paths),
            "Package sample has no Packages path.",
        )


def _verify_binding_sample_chains(
    samples: Dict[str, Dict[str, object]],
    manifest: Dict[str, object],
) -> None:
    expected = manifest["bindings"].get("samples")
    _require(
        isinstance(expected, dict),
        "Binding manifest has no expected sample chains.",
    )
    _require(
        set(samples) == set(expected),
        "Binding census sample categories drifted.",
    )
    for category, sample in samples.items():
        _require(
            sample == expected[category],
            f"Binding {category} sample chain drifted.",
        )


def _verify_binding_census(
    census: Dict[str, object],
    manifest: Dict[str, object],
) -> None:
    expected = manifest["bindings"]["census"]
    _require(census["rows"] == expected["rows"], "Binding census row count drifted.")
    for key in (
        "source_asset_kind",
        "reference_shape",
        "target_category",
        "asset_resolution",
        "script_object_resolution",
    ):
        _require(
            census[key] == expected[key],
            f"Binding census {key} counts drifted.",
        )
    for key in (
        "distinct_m_script_file_ids",
        "non_typical_file_id_rows",
        "candidate_source_files",
    ):
        _require(
            census[key] == expected[key],
            f"Binding census {key} drifted.",
        )
    _require(census["warning_codes"] == {}, "Binding census reported warnings.")


def _scanner_version() -> str:
    version_path = (
        REPOSITORY_ROOT
        / "skills"
        / "blasphemous-modding-helper"
        / "version.yml"
    )
    try:
        for line in version_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() == "version" and value.strip():
                return value.strip()
    except (OSError, UnicodeError) as error:
        raise SmokeFailure(f"Could not read the Skill scanner version: {error}") from error
    raise SmokeFailure("The Skill scanner version is missing.")


def _utc_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _package_source_candidates(paths: Iterable[str]) -> int:
    suffixes = {".unity", ".prefab", ".asset"}
    return sum(
        1
        for path in paths
        if path.startswith("file:Packages/")
        and Path(path).suffix.casefold() in suffixes
    )


def _binding_arguments(
    project_root: Path,
    limit: int,
    cursor: Optional[str] = None,
) -> List[str]:
    arguments = [
        "bindings",
        "--project",
        str(project_root),
        "--limit",
        str(limit),
        "--timeout-seconds",
        str(BINDINGS_TIMEOUT_SECONDS),
    ]
    if cursor is not None:
        arguments.extend(["--cursor", cursor])
    return arguments


def _binding_census_arguments(project_root: Path) -> List[str]:
    return [
        "bindings",
        "--project",
        str(project_root),
        "--census-summary",
        "--timeout-seconds",
        str(BINDINGS_TIMEOUT_SECONDS),
    ]


def _redacted_cursor_arguments(arguments: Sequence[str]) -> List[str]:
    redacted = list(arguments)
    for index, value in enumerate(redacted):
        if value == "--cursor" and index + 1 < len(redacted):
            redacted[index + 1] = "<OPAQUE_CURSOR>"
    return redacted


def _verify_binding_page(
    payload: Dict[str, object],
    limit: int,
    expected_rows: Optional[int] = None,
    expected_coverage: str = "complete",
) -> None:
    _require(payload.get("status") == "ok", "Binding page status is not ok.")
    _require(
        payload.get("scan_coverage") == expected_coverage,
        f"Binding page scan coverage is not {expected_coverage}.",
    )
    _require(
        payload.get("warnings") == [] and payload.get("error") is None,
        "Binding page reported warnings or an error.",
    )
    _require(
        payload.get("limits", {}).get("limit") == limit,
        "Binding page limit drifted.",
    )
    results = payload.get("results")
    _require(isinstance(results, list), "Binding page results are not an array.")
    if expected_rows is not None:
        _require(
            len(results) == expected_rows,
            f"Binding page returned {len(results)} rows; expected {expected_rows}.",
        )


def _run_binding_benchmark(
    python_executable: str,
    project_root: Path,
    limit: int,
) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    first_args = _binding_arguments(project_root, limit)
    first, first_elapsed, first_bytes = _run_scanner_with_size(
        python_executable,
        project_root,
        first_args,
    )
    _verify_binding_page(first, limit, limit, "pending")
    cursor = first.get("next_cursor")
    _require(isinstance(cursor, str) and cursor, "First page has no next cursor.")

    second_args = _binding_arguments(project_root, limit, cursor)
    second, second_elapsed, second_bytes = _run_scanner_with_size(
        python_executable,
        project_root,
        second_args,
    )
    next_cursor = second.get("next_cursor")
    second_coverage = "complete" if next_cursor is None else "pending"
    if next_cursor is not None:
        _require(
            isinstance(next_cursor, str) and next_cursor,
            "Second binding page has an invalid next cursor.",
        )
        _require(
            next_cursor != cursor,
            "Binding cursor did not advance to the second page.",
        )
    _verify_binding_page(second, limit, limit, second_coverage)
    first_rows = first["results"]
    second_rows = second["results"]

    def binding_identity(row: Dict[str, object]) -> Tuple[object, ...]:
        return (
            row.get("source_asset_path"),
            row.get("source_object_file_id"),
            row.get("reference_shape"),
            row.get("m_script_file_id"),
            row.get("m_script_guid"),
        )

    first_identities = {binding_identity(row) for row in first_rows}
    second_identities = {binding_identity(row) for row in second_rows}
    transitioned = first_identities.isdisjoint(second_identities)
    _require(
        transitioned,
        "Binding cursor repeated the first page boundary.",
    )
    benchmark = {
        "limit": limit,
        "page_row_count": len(first_rows),
        "serialized_bytes": first_bytes,
        "scan_coverage": first.get("scan_coverage"),
        "first_page_elapsed_seconds": first_elapsed,
        "next_cursor_present": True,
        "cursor_transition": {
            "page_row_count": len(second_rows),
            "serialized_bytes": second_bytes,
            "scan_coverage": second.get("scan_coverage"),
            "second_page_elapsed_seconds": second_elapsed,
            "boundary_identity_changed": transitioned,
            "next_cursor_present": second.get("next_cursor") is not None,
        },
    }
    records = [
        _query_record(
            f"bindings_benchmark_{limit}",
            first_args,
            project_root,
            first,
            first_elapsed,
            first_bytes,
        ),
        _query_record(
            f"bindings_benchmark_{limit}_cursor",
            _redacted_cursor_arguments(second_args),
            project_root,
            second,
            second_elapsed,
            second_bytes,
        ),
    ]
    return benchmark, records


def _run_binding_census(
    python_executable: str,
    project_root: Path,
    project_payload: Dict[str, object],
    before_paths: Set[str],
    manifest: Dict[str, object],
) -> Tuple[Dict[str, object], List[Dict[str, object]], bool]:
    expected = manifest["bindings"]["census"]
    package_sources = _package_source_candidates(before_paths)
    _require(
        package_sources == expected["packages_source_candidates"],
        "Packages source candidate count drifted.",
    )
    arguments = _binding_census_arguments(project_root)
    started_at = _utc_now()
    payload, elapsed, _ = _run_scanner_with_size(
        python_executable,
        project_root,
        arguments,
        allow_incomplete=True,
    )
    scanner_status = payload.get("status")
    scan_coverage = payload.get("scan_coverage")
    if scanner_status in {"partial", "timeout"} or scan_coverage == "partial":
        return (
            {
                "status": scanner_status,
                "scan_coverage": scan_coverage,
                "warnings": payload.get("warnings"),
                "error": payload.get("error"),
                "census": payload.get("census"),
            },
            [
                _query_record(
                    "bindings_census_summary",
                    arguments,
                    project_root,
                    payload,
                    elapsed,
                )
            ],
            False,
        )
    _require(payload.get("status") == "ok", "Binding census status is not ok.")
    _require(
        payload.get("scan_coverage") == "complete",
        "Binding census scan coverage is not complete.",
    )
    _require(
        payload.get("warnings") == [] and payload.get("error") is None,
        "Binding census reported warnings or an error.",
    )
    _require(
        payload.get("results") == [],
        "Binding census summary returned paginated rows.",
    )
    _require(payload.get("next_cursor") is None, "Binding census has a cursor.")
    payload_census = payload.get("census")
    _require(
        isinstance(payload_census, dict),
        "Binding census summary has no census object.",
    )
    census = dict(payload_census)
    file_counts = project_payload["results"][0]["file_counts"]
    _require(
        census["candidate_source_files"]
        == sum(file_counts[key] for key in ("unity", "prefab", "asset")),
        "Binding census source candidate count drifted.",
    )
    samples = census.get("samples")
    _require(isinstance(samples, dict), "Binding census samples are not an object.")
    required_samples = (
        "cs",
        "dll",
        "unresolved",
        "null",
        "non_typical_file_id",
        "asset",
    )
    for key in required_samples:
        _require(
            isinstance(samples.get(key), dict),
            f"Binding census has no {key} sample.",
        )
    if census["target_category"]["malformed"]:
        _require(
            isinstance(samples.get("malformed"), dict),
            "Binding census has malformed rows but no malformed sample.",
        )
    else:
        _require(
            "malformed" not in samples,
            "Binding census reported a malformed sample without malformed rows.",
        )
    _verify_binding_samples(samples)
    _verify_binding_sample_chains(samples, manifest)
    _verify_binding_census(census, manifest)

    default_benchmark, default_records = _run_binding_benchmark(
        python_executable,
        project_root,
        200,
    )
    maximum_benchmark, maximum_records = _run_binding_benchmark(
        python_executable,
        project_root,
        BINDINGS_LIMIT,
    )
    finished_at = _utc_now()

    census["default_page_benchmark"] = default_benchmark
    census["maximum_page_benchmark"] = maximum_benchmark
    census["scan_timestamps"] = {
        "started_at": started_at,
        "finished_at": finished_at,
        "summary_elapsed_seconds": elapsed,
    }
    census["invocation"] = {
        "command": _scanner_command(arguments, project_root),
        "selectors": {},
        "mode": "census_summary",
    }
    census["scanner_version"] = _scanner_version()
    census["schema_version"] = project_payload["schema_version"]
    census["unity_version"] = project_payload["project"]["unity_version"]
    census["packages_root_included"] = (
        "Packages" in project_payload["project"]["included_roots"]
    )
    census["packages_source_candidates"] = package_sources
    census["file_counts"] = file_counts
    census["scan_coverage"] = "complete"
    census["error_counts"] = dict(census["warning_codes"])
    snapshot_material = {
        key: census[key]
        for key in (
            "unity_version",
            "scanner_version",
            "schema_version",
            "file_counts",
            "rows",
            "source_asset_kind",
            "reference_shape",
            "target_category",
        )
    }
    census["snapshot_id"] = hashlib.sha256(
        json.dumps(
            snapshot_material,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    records = [
        _query_record(
            "bindings_census_summary",
            arguments,
            project_root,
            payload,
            elapsed,
        ),
        {
            "query": "bindings_census",
            "status": "ok",
            "elapsed_seconds": elapsed,
            "rows": census["rows"],
            "samples": len(census["samples"]),
        },
        *default_records,
        *maximum_records,
    ]
    return census, records, True


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
        "project": {"root": "." if project else None},
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
    bindings_census: bool = False,
) -> Tuple[int, Dict[str, object]]:
    if not project:
        return 2, _blocked_report(
            project,
            f"No real Unity project path was supplied through --project or {PROJECT_ENV}.",
        )
    try:
        project_input = Path(project).expanduser()
    except (OSError, RuntimeError):
        return 2, _blocked_report(
            project,
            "The supplied real Unity project root could not be resolved.",
        )
    project_root = project_input
    try:
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
    except (OSError, RuntimeError):
        return 2, _blocked_report(
            str(project_input),
            "The supplied real Unity export could not be read.",
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
        "project": {"root": "."},
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

        if bindings_census:
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
            _verify_project_summary(project_payload, before_assets, manifest)
            (
                binding_census_result,
                census_records,
                census_complete,
            ) = _run_binding_census(
                python_executable,
                project_root,
                project_payload,
                before_paths,
                manifest,
            )
            commands.extend(census_records)

            after_paths, after_assets, after_files, after_dirs = _snapshot_paths(
                project_root
            )
            after_hashes = _hashes(project_root, representative_files)
            added_paths = sorted(after_paths - before_paths)
            removed_paths = sorted(before_paths - after_paths)
            _require(
                not added_paths,
                f"Real-project path inventory gained entries: {added_paths}",
            )
            _require(
                not removed_paths,
                f"Real-project path inventory lost entries: {removed_paths}",
            )
            _require(
                before_hashes == after_hashes,
                "One or more representative files changed during the census.",
            )
            _require(
                (before_assets, before_files, before_dirs)
                == (after_assets, after_files, after_dirs),
                "Real-project file or directory counts changed during the census.",
            )
            baseline_evidence = {
                "assets_total_files": before_assets,
                "scanner_total_files": project_payload["results"][0]["file_counts"]["total"],
                "unity_files": project_payload["results"][0]["file_counts"]["unity"],
                "prefab_files": project_payload["results"][0]["file_counts"]["prefab"],
                "asset_files": project_payload["results"][0]["file_counts"]["asset"],
                "cs_files": project_payload["results"][0]["file_counts"]["cs"],
                "meta_files": project_payload["results"][0]["file_counts"]["meta"],
                "complete_scene_sets": project_payload["results"][0]["scene_counts"]["complete_sets"],
                "standalone_scenes": project_payload["results"][0]["scene_counts"]["standalone"],
            }
            report["commands"] = commands
            report["completion_evidence"] = {
                "unity_version": project_payload["project"]["unity_version"],
                "baseline": baseline_evidence,
                "bindings_census": binding_census_result,
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
            if not census_complete:
                report["status"] = "partial"
                report["next_action"] = (
                    "Census evidence is incomplete. Restore the unreadable source "
                    "or metadata, raise the timeout only within its documented "
                    "limit, and rerun the same acceptance command."
                )
                return 4, report
            report["status"] = "ok"
            report["next_action"] = (
                "Record aggregate-only binding evidence separately from synthetic "
                "results, then close the acceptance ticket."
            )
            return 0, report

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
            "The smoke passed. Run again with --bindings-census for component "
            "binding acceptance."
        )
        return 0, report
    except (OSError, SmokeFailure, KeyError, IndexError, TypeError) as error:
        report["error"] = _redact_project_root(
            str(error),
            project_root,
            project_input,
        )
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
    parser.add_argument(
        "--bindings-census",
        action="store_true",
        help="Run the full real-project binding census and page benchmarks.",
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
        args.bindings_census,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
