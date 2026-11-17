"""Read-only Unity script asset lookup without C# inspection."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Dict, List

from .unity_assets import asset_query
from .unity_project import _sorted_warnings, _warning


def _result_base(
    result: Dict[str, object], status: str, result_type: str = "cs"
) -> Dict[str, object]:
    return {
        "path": result["path"],
        "type": result_type,
        "name": PurePosixPath(str(result["path"])).name,
        "guid": result.get("guid"),
        "metadata": result["metadata"],
        "status": status,
    }


def script_query(project: Path, selector: str, value: str) -> Dict[str, object]:
    """Return the version-1 script asset lookup envelope."""

    asset_payload = asset_query(project, selector, value)
    payload = dict(asset_payload)
    payload["command"] = "script"
    payload["limits"] = {"csharp_parsed": False}
    warnings: List[Dict[str, object]] = list(payload["warnings"])
    results = payload["results"]
    source_ambiguous = payload["status"] == "ambiguous"

    if payload["status"] not in {"ok", "ambiguous"}:
        return payload

    scripts = [result for result in results if result["type"] == "cs"]
    non_scripts = [result for result in results if result["type"] != "cs"]
    if selector == "guid" and source_ambiguous and scripts and non_scripts:
        payload["status"] = "ambiguous"
        payload["results"] = [
            _result_base(result, "ambiguous", str(result["type"]))
            for result in results
        ]
        payload["error"] = None
        warnings.append(
            _warning(
                "ambiguous_script_guid",
                "The GUID identifies both script and non-script assets; "
                "no script was selected.",
            )
        )
        payload["warnings"] = _sorted_warnings(warnings)
        return payload
    if selector == "path" and results and not scripts:
        payload["status"] = "invalid_query"
        payload["results"] = []
        payload["error"] = {
            "code": "not_cs_script",
            "message": "The path selector does not name a .cs script asset.",
        }
        payload["warnings"] = _sorted_warnings(warnings)
        return payload
    if not scripts and selector == "guid" and source_ambiguous:
        payload["status"] = "ambiguous"
        payload["results"] = [
            _result_base(result, "ambiguous", str(result["type"]))
            for result in results
        ]
        payload["error"] = None
        warnings.append(
            _warning(
                "ambiguous_script_guid",
                "The GUID does not resolve to one script asset; "
                "readable non-script candidates are retained.",
            )
        )
        payload["warnings"] = _sorted_warnings(warnings)
        return payload
    if not scripts:
        payload["status"] = "not_found"
        payload["results"] = []
        payload["error"] = None
        warnings.append(
            _warning(
                "script_not_found",
                "No C# script asset matches the supplied selector.",
            )
        )
        payload["warnings"] = _sorted_warnings(warnings)
        return payload

    scripts.sort(key=lambda result: str(result["path"]).casefold())
    if len(scripts) > 1 or (selector == "guid" and source_ambiguous):
        payload["status"] = "ambiguous"
        payload["results"] = [
            _result_base(result, "ambiguous") for result in scripts
        ]
        payload["error"] = None
        warnings.append(
            _warning(
                "ambiguous_script",
                (
                    f"The selector identifies {len(scripts)} C# script assets."
                    if len(scripts) > 1
                    else "Unreadable metadata prevents proving a unique script GUID."
                ),
            )
        )
    else:
        payload["status"] = "ok"
        payload["results"] = [_result_base(scripts[0], "ok")]

    payload["warnings"] = _sorted_warnings(warnings)
    return payload
