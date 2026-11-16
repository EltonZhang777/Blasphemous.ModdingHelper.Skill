"""Read-only flattened Prefab inspection for an exported Unity project."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .unity_assets import asset_query
from .unity_project import _sorted_warnings, _warning
from .unity_serialized import SerializedError, parse_serialized_file


FLATTENED_LIMITS = {
    "evidence_kind": "flattened",
    "source_prefab_hierarchy": "not_available",
}


def _result_base(result: Dict[str, object], status: str) -> Dict[str, object]:
    return {
        "path": result["path"],
        "type": result["type"],
        "guid": result.get("guid"),
        "metadata": result["metadata"],
        "status": status,
        "evidence_kind": "flattened",
        "object_count": 0,
        "reference_count": 0,
        "objects": [],
    }


def prefab_query(project: Path, selector: str, value: str) -> Dict[str, object]:
    """Return the version-1 flattened Prefab evidence envelope."""

    asset_payload = asset_query(project, selector, value)
    payload = dict(asset_payload)
    payload["command"] = "prefab"
    payload["limits"] = dict(FLATTENED_LIMITS)
    warnings: List[Dict[str, object]] = list(payload["warnings"])
    results = payload["results"]

    if payload["status"] not in {"ok", "ambiguous"}:
        return payload

    prefabs = [result for result in results if result["type"] == "prefab"]
    non_prefabs = [result for result in results if result["type"] != "prefab"]
    if selector == "path" and results and not prefabs:
        payload["status"] = "invalid_query"
        payload["results"] = []
        payload["error"] = {
            "code": "not_prefab",
            "message": "The path selector does not name a .prefab asset.",
        }
        payload["warnings"] = _sorted_warnings(warnings)
        return payload
    if not prefabs:
        payload["status"] = "not_found"
        payload["results"] = []
        payload["error"] = None
        warnings.append(
            _warning(
                "prefab_not_found",
                "No Prefab matches the supplied selector.",
            )
        )
        payload["warnings"] = _sorted_warnings(warnings)
        return payload

    if selector == "guid" and payload["status"] == "ambiguous" and prefabs and non_prefabs:
        payload["status"] = "ambiguous"
        payload["results"] = [
            _result_base(result, "ambiguous") for result in results
        ]
        payload["error"] = None
        warnings.append(
            _warning(
                "ambiguous_prefab",
                "The GUID identifies both Prefab and non-Prefab assets; no Prefab was selected.",
            )
        )
        payload["warnings"] = _sorted_warnings(warnings)
        return payload

    prefabs.sort(key=lambda result: str(result["path"]).casefold())
    if len(prefabs) > 1:
        payload["status"] = "ambiguous"
        payload["results"] = [
            _result_base(result, "ambiguous") for result in prefabs
        ]
        payload["error"] = None
        warnings.append(
            _warning(
                "ambiguous_prefab",
                f"The selector identifies {len(prefabs)} Prefab assets.",
            )
        )
        payload["warnings"] = _sorted_warnings(warnings)
        return payload

    root = Path(str(payload["project"]["root"]))
    candidate = prefabs[0]
    path = root / str(candidate["path"])
    try:
        evidence, parse_warnings = parse_serialized_file(path, root)
    except SerializedError as error:
        payload["status"] = error.status
        payload["error"] = {"code": error.code, "message": str(error)}
        result = _result_base(candidate, error.status)
        warnings.append(
            _warning(
                error.warning_code or error.code,
                str(error),
                candidate["path"],
            )
        )
    else:
        payload["status"] = "ok"
        result = _result_base(candidate, "ok")
        result.update(
            {
                "object_count": evidence["object_count"],
                "reference_count": evidence["reference_count"],
                "objects": evidence["objects"],
            }
        )
        warnings.extend(parse_warnings)

    payload["results"] = [result]
    payload["warnings"] = _sorted_warnings(warnings)
    return payload
