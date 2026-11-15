"""Read-only structured analysis of explicit Blasphemous 1 save files."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
RUN_ROOT_NAME = "blasphemous-save-analysis"
MAX_SHAPE_MEMBERS = 40


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
        return json.loads(
            text,
            parse_constant=_reject_nonstandard_constant,
            parse_float=_parse_finite_float,
        )
    except ValueError as error:
        raise SaveAnalysisError("invalid-json", "Vanilla save payload is not valid JSON.") from error


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


def _analyze_file(path: Path, input_id: str):
    try:
        value = path.read_bytes()
    except OSError as error:
        raise SaveAnalysisError("input-unreadable", f"Input could not be read: {path}") from error
    parsed = _decode_vanilla(value)
    source = _source_identity(path, value)
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
    return item, parsed


def _paths_overlap(left: Path, right: Path) -> bool:
    try:
        common = os.path.commonpath((str(left), str(right)))
    except ValueError:
        return False
    return common in {str(left), str(right)}


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
    if analysis_root.parent != temp_root:
        raise SaveAnalysisError(
            "unsafe-output-root",
            f"Save-analysis output root escapes the host temporary directory: {analysis_root}",
        )
    if _paths_overlap(input_path, analysis_root):
        raise SaveAnalysisError(
            "input-output-overlap",
            "The temporary save-analysis root overlaps the selected input.",
        )
    return analysis_root


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def _summary(run_id: str, run_root: Path, item: Dict[str, Any], status: str) -> str:
    lines = [
        "Blasphemous 1 save analysis",
        f"Run: {run_id}",
        f"Status: {status}",
        f"Output: {run_root}",
        (
            "Lifetime: output is under the host temporary directory; it may be "
            "deleted early or persist beyond this invocation."
        ),
    ]
    lines.extend(
        [
            "",
            f"Input: {item['source']['path']}",
            f"  Role: {item['role']}",
            f"  Format: {item['format']}",
            f"  Status: {item['parse_status']}",
            f"  Bytes: {item['bytes']}",
            f"  SHA-256: {item['sha256']}",
            f"  Top-level keys: {item['top_level_keys']}",
            f"  Structured chunk: {item['artifacts']['chunk']}",
            f"  Full artifact: {item['artifacts']['full']}",
        ]
    )
    return "\n".join(lines) + "\n"


def analyze(input_path: Path) -> Path:
    resolved_input = input_path.expanduser().resolve(strict=False)
    if not resolved_input.exists():
        raise SaveAnalysisError("input-missing", f"Input path does not exist: {resolved_input}")
    if not resolved_input.is_file():
        raise SaveAnalysisError(
            "unsupported-input",
            f"Input must be one save file: {resolved_input}",
        )

    item, parsed = _analyze_file(resolved_input, "input-1")
    analysis_root = _output_root(resolved_input)
    analysis_root.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    run_root = analysis_root / run_id
    if run_root.exists():
        raise SaveAnalysisError("run-collision", f"Generated run directory already exists: {run_root}")
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=str(analysis_root)))

    chunk = {
        "source": item["source"],
        "role": item["role"],
        "format": item["format"],
        "data_shape": _value_shape(parsed),
    }
    try:
        _write_text(
            staging / item["artifacts"]["chunk"],
            json.dumps(chunk, ensure_ascii=True, indent=2) + "\n",
        )
        _write_text(
            staging / item["artifacts"]["full"],
            json.dumps(parsed, ensure_ascii=False, allow_nan=False, indent=4) + "\n",
        )

        manifest = {
            "schema_version": 1,
            "run_id": run_id,
            "input_mode": "file",
            "status": "success",
            "inputs": [item],
            "artifacts": {
                "manifest": "manifest.json",
                "summary": "summary.txt",
            },
        }
        _write_text(
            staging / "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        _write_text(staging / "summary.txt", _summary(run_id, run_root, item, "success"))
        os.rename(staging, run_root)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return run_root.resolve()


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Run a read-only, configuration-free analysis of one explicit "
            "Blasphemous 1 save file. This command does not modify the input "
            "and does not read a game profile or decompiled source."
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
    parser.add_argument("input", type=Path, help="One explicit save file.")
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
