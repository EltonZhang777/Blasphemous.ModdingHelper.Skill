"""Read-only structured analysis of explicit Blasphemous 1 save files."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
RUN_ROOT_NAME = "blasphemous-save-analysis"
MAX_SHAPE_MEMBERS = 40
MAX_MODDING_PREVIEW_CHARS = 512
CONVENTIONAL_MODDING_IDENTIFIER = re.compile(
    r"(?:[A-Za-z0-9_-]+\.)+[A-Za-z0-9_-]+|"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


class SaveAnalysisError(Exception):
    """A fatal save-analysis input or output failure."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_identity(path: Path, value: bytes) -> Dict[str, Any]:
    return {
        "path": str(path),
        "name": path.name,
        "bytes": len(value),
        "sha256": _sha256(value),
    }


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _parse_finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite JSON number")
    return number


def _json_loads(value: str):
    return json.loads(
        value,
        parse_constant=_reject_nonstandard_constant,
        parse_float=_parse_finite_float,
    )


def _decode_vanilla(value: bytes) -> Any:
    encoded = value.strip()
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as error:
        raise SaveAnalysisError("unsupported-format", "Input is not a supported save format.") from error
    try:
        text = decoded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SaveAnalysisError("invalid-utf8", "Vanilla save payload is not valid UTF-8.") from error
    try:
        return _json_loads(text)
    except ValueError as error:
        raise SaveAnalysisError("invalid-json", "Vanilla save payload is not valid JSON.") from error


def _parse_json_line(value: str):
    try:
        return _json_loads(value), None
    except ValueError as error:
        return None, str(error)


def _decode_modding(value: bytes):
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SaveAnalysisError(
            "invalid-utf8",
            "ModdingAPI persistence file is not valid UTF-8.",
        ) from error

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    records = []
    counts = {
        "valid_records": 0,
        "invalid_records": 0,
        "incomplete_records": 0,
        "blank_lines": 0,
    }
    index = 0
    while index < len(lines):
        identifier = lines[index]
        if not identifier.strip():
            records.append({"status": "blank", "line": index + 1})
            counts["blank_lines"] += 1
            index += 1
            continue
        if index + 1 >= len(lines):
            records.append(
                {
                    "status": "incomplete",
                    "identifier": identifier,
                    "identifier_line": index + 1,
                    "payload_line": None,
                }
            )
            counts["incomplete_records"] += 1
            index += 1
            continue

        raw_payload = lines[index + 1]
        parsed, error = _parse_json_line(raw_payload)
        if error is None:
            records.append(
                {
                    "status": "valid",
                    "identifier": identifier,
                    "identifier_line": index + 1,
                    "payload_line": index + 2,
                    "payload": parsed,
                }
            )
            counts["valid_records"] += 1
        else:
            records.append(
                {
                    "status": "invalid",
                    "identifier": identifier,
                    "identifier_line": index + 1,
                    "payload_line": index + 2,
                    "raw_payload": raw_payload,
                    "error": error,
                }
            )
            counts["invalid_records"] += 1
        index += 2
    return records, counts


def _format_modding_full(records: Sequence[Dict[str, Any]]) -> str:
    lines = []
    for record in records:
        status = record["status"]
        if status == "blank":
            lines.append("")
            continue
        lines.append(record["identifier"])
        if status == "valid":
            lines.append(
                json.dumps(
                    record["payload"],
                    ensure_ascii=False,
                    allow_nan=False,
                    indent=4,
                )
            )
        elif status == "invalid":
            lines.append(record["raw_payload"])
    return "\n".join(lines) + "\n"


def _modding_chunk_records(
    records: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    chunk_records = []
    for record in records:
        chunk_record = {
            key: value
            for key, value in record.items()
            if key not in {"payload", "raw_payload"}
        }
        if record["status"] == "valid":
            chunk_record["payload_shape"] = _value_shape(record["payload"])
        elif record["status"] == "invalid":
            raw_payload = record["raw_payload"]
            chunk_record["raw_payload_preview"] = raw_payload[
                :MAX_MODDING_PREVIEW_CHARS
            ]
            chunk_record["raw_payload_chars"] = len(raw_payload)
            chunk_record["raw_payload_truncated"] = (
                len(raw_payload) > MAX_MODDING_PREVIEW_CHARS
            )
        chunk_records.append(chunk_record)
    return chunk_records


def _has_modding_content(
    records: Sequence[Dict[str, Any]], counts: Dict[str, int]
) -> bool:
    if counts["valid_records"]:
        return True
    return any(
        record["status"] in {"valid", "invalid"}
        and CONVENTIONAL_MODDING_IDENTIFIER.fullmatch(record["identifier"])
        for record in records
    )


def _top_level_count(value: Any) -> int:
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, list):
        return len(value)
    return 0


def _json_type(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return "number"
    return "unknown"


def _value_shape(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        names = list(value)[:MAX_SHAPE_MEMBERS]
        return {
            "type": "object",
            "member_count": len(value),
            "members": [
                {"name": name, "value_type": _json_type(value[name])}
                for name in names
            ],
            "members_omitted": max(0, len(value) - len(names)),
        }
    if isinstance(value, list):
        item_types = sorted({_json_type(item) for item in value})
        return {
            "type": "array",
            "length": len(value),
            "item_types": item_types,
        }
    return {"type": _json_type(value)}


def _modding_warnings(counts: Dict[str, int]) -> list:
    warnings = []
    if counts["invalid_records"]:
        warnings.append(f"{counts['invalid_records']} invalid payload record(s)")
    if counts["incomplete_records"]:
        warnings.append(f"{counts['incomplete_records']} incomplete record(s)")
    return warnings


def _directory_role(name: str) -> Optional[tuple]:
    roles = {
        "app_settings": ("vanilla-global-settings", "vanilla-base64-json"),
        "app_settings_backup": (
            "vanilla-global-settings-backup",
            "vanilla-base64-json",
        ),
        "app_settings_modded": (
            "moddingapi-global-settings",
            "moddingapi-records",
        ),
        "app_settings_modded_backup": (
            "moddingapi-global-settings-backup",
            "moddingapi-records",
        ),
    }
    if name in roles:
        return roles[name]

    match = re.fullmatch(r"savegame_\d+(_modded)?\.save(_backup)?", name)
    if match is None:
        return None
    moddingapi = match.group(1) is not None
    backup = match.group(2) is not None
    if moddingapi:
        role = (
            "moddingapi-slot-companion-backup"
            if backup
            else "moddingapi-slot-companion"
        )
        return role, "moddingapi-records"
    role = "vanilla-player-save-backup" if backup else "vanilla-player-save"
    return role, "vanilla-base64-json"


def _apply_role(
    item: Dict[str, Any],
    chunk: Dict[str, Any],
    role_hint: tuple,
) -> None:
    role, expected_format = role_hint
    role_match = item["format"] == expected_format
    item["role"] = role
    item["expected_format"] = expected_format
    item["role_match"] = role_match
    chunk["role"] = role
    chunk["expected_format"] = expected_format
    chunk["role_match"] = role_match
    if not role_match:
        item["warnings"].append(
            f"Role mismatch: expected {expected_format} for {role}; "
            f"detected {item['format']}."
        )


def _failed_analysis(
    source: Dict[str, Any],
    input_id: str,
    role_hint: tuple,
    error: SaveAnalysisError,
):
    role, expected_format = role_hint
    detail = {"reason": error.reason, "message": error.message}
    item = {
        "id": input_id,
        "source": source,
        "role": role,
        "format": "unknown",
        "expected_format": expected_format,
        "parse_status": "failed",
        "warnings": [],
        "bytes": source["bytes"],
        "sha256": source["sha256"],
        "error": detail,
        "artifacts": {
            "chunk": f"structured/{input_id}.json",
            "full": None,
        },
        "full_artifact_status": "unavailable",
    }
    chunk = {
        "source": source,
        "role": role,
        "format": "unknown",
        "expected_format": expected_format,
        "parse_status": "failed",
        "error": detail,
    }
    return item, chunk, None


def _analyze_file(
    path: Path,
    input_id: str,
    role_hint: Optional[tuple] = None,
):
    try:
        value = path.read_bytes()
    except OSError as error:
        raise SaveAnalysisError("input-unreadable", f"Input could not be read: {path}") from error
    source = _source_identity(path, value)
    vanilla_error = None
    try:
        parsed = _decode_vanilla(value)
    except SaveAnalysisError as error:
        vanilla_error = error
        parsed = None

    records, counts = _decode_modding(value)
    has_modding_content = _has_modding_content(records, counts)
    if parsed is not None and has_modding_content:
        raise SaveAnalysisError(
            "ambiguous-content",
            "Input matches more than one supported save format.",
        )
    if has_modding_content:
        item = {
            "id": input_id,
            "source": source,
            "role": "moddingapi",
            "format": "moddingapi-records",
            "parse_status": "ok",
            "warnings": _modding_warnings(counts),
            "bytes": source["bytes"],
            "sha256": source["sha256"],
            "counts": counts,
            "artifacts": {
                "chunk": f"structured/{input_id}.json",
                "full": f"full/{input_id}.txt",
            },
            "full_artifact_status": "complete",
        }
        chunk = {
            "source": source,
            "role": "moddingapi",
            "format": "moddingapi-records",
            "counts": counts,
            "records": _modding_chunk_records(records),
        }
        if role_hint is not None:
            _apply_role(item, chunk, role_hint)
        return item, chunk, _format_modding_full(records)
    if vanilla_error is not None:
        raise vanilla_error

    item = {
        "id": input_id,
        "source": source,
        "role": "vanilla",
        "format": "vanilla-base64-json",
        "parse_status": "ok",
        "warnings": [],
        "bytes": source["bytes"],
        "sha256": source["sha256"],
        "top_level_keys": _top_level_count(parsed),
        "artifacts": {
            "chunk": f"structured/{input_id}.json",
            "full": f"full/{input_id}.json",
        },
        "full_artifact_status": "complete",
    }
    chunk = {
        "source": source,
        "role": "vanilla",
        "format": "vanilla-base64-json",
        "data_shape": _value_shape(parsed),
    }
    if role_hint is not None:
        _apply_role(item, chunk, role_hint)
    return (
        item,
        chunk,
        json.dumps(parsed, ensure_ascii=False, allow_nan=False, indent=4) + "\n",
    )


def _paths_overlap(left: Path, right: Path) -> bool:
    try:
        common = os.path.commonpath((str(left), str(right)))
    except ValueError:
        return False
    return common in {str(left), str(right)}


def _path_within(path: Path, root: Path) -> bool:
    try:
        common = os.path.commonpath((str(path), str(root)))
    except ValueError:
        return False
    return common == str(root)


def _output_root(input_path: Path) -> Path:
    temp_root = Path(tempfile.gettempdir()).resolve()
    candidate = temp_root / RUN_ROOT_NAME
    if candidate.is_symlink():
        raise SaveAnalysisError(
            "unsafe-output-root",
            f"Save-analysis output root must not be a symbolic link: {candidate}",
        )
    if candidate.exists() and not candidate.is_dir():
        raise SaveAnalysisError(
            "unsafe-output-root",
            f"Save-analysis output root is not a directory: {candidate}",
        )
    analysis_root = candidate.resolve()
    if analysis_root != candidate or analysis_root.parent != temp_root:
        raise SaveAnalysisError(
            "unsafe-output-root",
            (
                "Save-analysis output root must not redirect outside its "
                f"dedicated temporary directory: {candidate}"
            ),
        )
    if _paths_overlap(input_path, analysis_root):
        raise SaveAnalysisError(
            "input-output-overlap",
            "The temporary save-analysis root overlaps the selected input.",
        )
    return analysis_root


def _write_text(root: Path, relative: str, value: str) -> None:
    target = root / relative
    resolved_root = root.resolve(strict=True)
    resolved_target = target.resolve(strict=False)
    if (
        root.is_symlink()
        or resolved_root != root
        or target.is_symlink()
        or resolved_target != target
        or not _path_within(resolved_target, resolved_root)
    ):
        raise SaveAnalysisError(
            "unsafe-output-path",
            f"Save-analysis output path redirects through a link: {target}",
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = target.parent.resolve(strict=True)
    if (
        target.parent.is_symlink()
        or resolved_parent != target.parent
        or not _path_within(resolved_parent, resolved_root)
    ):
        raise SaveAnalysisError(
            "unsafe-output-path",
            f"Save-analysis output parent redirects through a link: {target.parent}",
        )

    try:
        stream = target.open("x", encoding="utf-8", newline="\n")
    except FileExistsError as error:
        raise SaveAnalysisError(
            "unsafe-output-path",
            f"Save-analysis output already exists or is linked: {target}",
        ) from error

    with stream:
        if os.fstat(stream.fileno()).st_nlink != 1:
            raise SaveAnalysisError(
                "unsafe-output-path",
                f"Save-analysis output must not be hard-linked: {target}",
            )
        stream.write(value)


def _publish(staging: Path, run_root: Path) -> None:
    try:
        run_root.mkdir(mode=0o700)
    except FileExistsError as error:
        raise SaveAnalysisError(
            "run-collision",
            f"Generated run directory already exists: {run_root}",
        ) from error

    moved = []
    try:
        for child in sorted(staging.iterdir(), key=lambda entry: entry.name.casefold()):
            destination = run_root / child.name
            os.rename(child, destination)
            moved.append((destination, child))
        staging.rmdir()
    except Exception:
        for destination, source in reversed(moved):
            if destination.exists() or destination.is_symlink():
                os.rename(destination, source)
        try:
            run_root.rmdir()
        except OSError:
            pass
        raise


def _summary(
    run_id: str,
    run_root: Path,
    items: Sequence[Dict[str, Any]],
    status: str,
) -> str:
    lines = [
        "Blasphemous 1 save analysis",
        f"Run: {run_id}",
        f"Status: {status}",
        f"Inputs: {len(items)}",
        f"Output: {run_root}",
        (
            "Lifetime: output is under the host temporary directory; it may be "
            "deleted early or persist beyond this invocation."
        ),
    ]
    for item in items:
        lines.extend(
            [
                "",
                f"Input: {item['source']['path']}",
                f"  Role: {item['role']}",
                f"  Format: {item['format']}",
                f"  Status: {item['parse_status']}",
                f"  Bytes: {item['bytes']}",
                f"  SHA-256: {item['sha256']}",
                f"  Structured chunk: {item['artifacts']['chunk']}",
                f"  Full artifact: {item['artifacts']['full'] or 'unavailable'}",
            ]
        )
        if "expected_format" in item:
            lines.append(f"  Expected format: {item['expected_format']}")
        if "role_match" in item:
            lines.append(f"  Role match: {'yes' if item['role_match'] else 'no'}")
        if "error" in item:
            error = item["error"]
            lines.append(f"  Error: {error['reason']}: {error['message']}")
        if "top_level_keys" in item:
            lines.append(f"  Top-level keys: {item['top_level_keys']}")
        counts = item.get("counts")
        if counts:
            lines.extend(
                f"  {name.replace('_', ' ').capitalize()}: {value}"
                for name, value in counts.items()
            )
        for warning in item["warnings"]:
            lines.append(f"  Warning: {warning}")
    return "\n".join(lines) + "\n"


def _directory_inputs(path: Path) -> List[tuple]:
    inputs = []
    for child in sorted(path.iterdir(), key=lambda entry: entry.name.casefold()):
        role_hint = _directory_role(child.name)
        if role_hint is not None and not child.is_symlink() and child.is_file():
            inputs.append((child, role_hint))
    if not inputs:
        raise SaveAnalysisError(
            "no-supported-files",
            f"Directory contains no supported save files: {path}",
        )
    return inputs


def analyze(input_path: Path) -> Path:
    resolved_input = input_path.expanduser().resolve(strict=False)
    if not resolved_input.exists():
        raise SaveAnalysisError("input-missing", f"Input path does not exist: {resolved_input}")
    if resolved_input.is_file():
        inputs = [(resolved_input, None)]
        input_mode = "file"
    elif resolved_input.is_dir():
        inputs = _directory_inputs(resolved_input)
        input_mode = "directory"
    else:
        raise SaveAnalysisError(
            "unsupported-input",
            f"Input must be one save file or directory: {resolved_input}",
        )

    analyses = []
    for index, (path, role_hint) in enumerate(inputs, start=1):
        input_id = f"input-{index}"
        try:
            analysis = _analyze_file(path, input_id, role_hint)
        except SaveAnalysisError as error:
            if input_mode != "directory":
                raise
            source = _source_identity(path, path.read_bytes())
            analysis = _failed_analysis(source, input_id, role_hint, error)
        analyses.append(analysis)

    analysis_root = _output_root(resolved_input)
    analysis_root.mkdir(parents=True, exist_ok=True)
    if analysis_root.is_symlink() or analysis_root.resolve(strict=True) != analysis_root:
        raise SaveAnalysisError(
            "unsafe-output-root",
            f"Save-analysis output root was redirected: {analysis_root}",
        )
    run_id = uuid.uuid4().hex
    run_root = analysis_root / run_id
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=str(analysis_root)))

    try:
        for item, chunk, full_text in analyses:
            _write_text(
                staging,
                item["artifacts"]["chunk"],
                json.dumps(chunk, ensure_ascii=True, indent=2) + "\n",
            )
            if full_text is not None:
                _write_text(
                    staging,
                    item["artifacts"]["full"],
                    full_text,
                )

        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "input_mode": input_mode,
            "status": "success",
            "inputs": [item for item, _, _ in analyses],
            "artifacts": {
                "manifest": "manifest.json",
                "summary": "summary.txt",
            },
        }
        _write_text(
            staging,
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        _write_text(
            staging,
            "summary.txt",
            _summary(
                run_id,
                run_root,
                [item for item, _, _ in analyses],
                "success",
            ),
        )
        if analysis_root.is_symlink() or analysis_root.resolve(strict=True) != analysis_root:
            raise SaveAnalysisError(
                "unsafe-output-root",
                f"Save-analysis output root was redirected: {analysis_root}",
            )
        _publish(staging, run_root)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return run_root


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Run a read-only, configuration-free analysis of one explicit "
            "Blasphemous 1 save file or save directory. This command does not "
            "modify the input and does not read a game profile or decompiled "
            "source."
        ),
        epilog=(
            "Every run creates a unique directory under the host temporary "
            "area and always writes manifest.json, summary.txt, structured "
            "chunks, and a normalized full artifact. Read the manifest and "
            "chunks before the full artifact."
        ),
    )


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    _configure_stdio()
    parser = build_parser()
    parser.add_argument(
        "input",
        type=Path,
        help="One explicit save file or save directory.",
    )
    args = parser.parse_args(argv)
    try:
        run_root = analyze(args.input)
    except SaveAnalysisError as error:
        print(f"Error [save-analysis]: {error.message}", file=sys.stderr)
        print(f"Reason: {error.reason}", file=sys.stderr)
        return EXIT_FAILURE
    except OSError as error:
        print(f"Error [save-analysis]: analysis could not complete: {error}", file=sys.stderr)
        print("Reason: io-failure", file=sys.stderr)
        return EXIT_FAILURE
    except UnicodeError as error:
        print(f"Error [save-analysis]: analysis contains unencodable text: {error}", file=sys.stderr)
        print("Reason: invalid-unicode", file=sys.stderr)
        return EXIT_FAILURE
    print(run_root)
    return EXIT_SUCCESS
