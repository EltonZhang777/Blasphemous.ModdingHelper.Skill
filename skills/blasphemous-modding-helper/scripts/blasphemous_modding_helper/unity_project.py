"""Read-only navigation of an exported Blasphemous Unity project."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


SCHEMA_VERSION = 1
REFERENCE_UNITY_VERSION = "2017.4.40f1"
SCENE_LAYERS = ("_MAIN", "_LOGIC", "_LAYOUT", "_DECO", "_AUDIO")
EXCLUDED_DIRECTORIES = frozenset(
    {
        "Library",
        "Temp",
        "Obj",
        "obj",
        ".vs",
        ".git",
        ".idea",
        ".vscode",
        "Logs",
        "UserSettings",
        "Build",
        "Builds",
    }
)
EXCLUDED_DIRECTORY_NAMES = frozenset(name.casefold() for name in EXCLUDED_DIRECTORIES)
UNITY_VERSION = re.compile(r"^\d+\.\d+\.\d+[A-Za-z]\d+$")


class NavigationError(Exception):
    """A structured navigation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _warning(code: str, message: str, path: Optional[str] = None) -> Dict[str, object]:
    warning: Dict[str, object] = {"code": code, "message": message}
    if path is not None:
        warning["path"] = path
    return warning


def _sorted_warnings(warnings: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    return sorted(
        warnings,
        key=lambda item: (
            str(item.get("code", "")),
            str(item.get("path", "")),
            str(item.get("message", "")),
        ),
    )


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root)
    except (OSError, RuntimeError):
        return False
    except ValueError:
        return False
    return True


def _is_link_like(path: Path) -> bool:
    try:
        metadata = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(metadata.st_mode):
        return True
    return bool(getattr(metadata, "st_reparse_tag", 0))


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _unity_version(root: Path) -> Tuple[Optional[str], Optional[str], Optional[bool], List[Dict[str, object]]]:
    version_path = root / "ProjectSettings" / "ProjectVersion.txt"
    link_like = _is_link_like(version_path.parent) or _is_link_like(version_path)
    if link_like or not _within(version_path, root):
        code = "symlink_not_followed" if link_like and _within(version_path, root) else "symlink_outside_root"
        return None, None, None, [
            _warning(
                "unity_version_unknown",
                "Unity version could not be read from ProjectSettings/ProjectVersion.txt.",
                "ProjectSettings/ProjectVersion.txt",
            ),
            _warning(
                code,
                "Unity version file or its parent is a link and was not read.",
                "ProjectSettings/ProjectVersion.txt",
            ),
        ]
    try:
        text = version_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None, None, None, [
            _warning(
                "unity_version_unknown",
                "Unity version could not be read from ProjectSettings/ProjectVersion.txt.",
                "ProjectSettings/ProjectVersion.txt",
            )
        ]
    version = None
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "m_EditorVersion" and value.strip():
            version = value.strip()
            break
    if version is None or UNITY_VERSION.fullmatch(version) is None:
        return None, None, None, [
            _warning(
                "unity_version_unknown",
                "Unity version is missing or unparseable.",
                "ProjectSettings/ProjectVersion.txt",
            )
        ]
    major = version.split(".", 1)[0]
    compatible = major == REFERENCE_UNITY_VERSION.split(".", 1)[0]
    warnings = []
    if not compatible:
        warnings.append(
            _warning(
                "unity_major_mismatch",
                f"Unity {version} does not use the {REFERENCE_UNITY_VERSION.split('.', 1)[0]} major version baseline.",
                "ProjectSettings/ProjectVersion.txt",
            )
        )
    return version, major, compatible, warnings


def _included_roots(root: Path) -> List[Path]:
    assets = root / "Assets"
    if not assets.is_dir():
        raise NavigationError("invalid_project", f"Unity project has no Assets directory: {root}")
    if _is_link_like(assets) or not _within(assets, root):
        raise NavigationError(
            "invalid_project",
            f"Assets is a link or resolves outside the Unity project root: {assets}",
        )
    roots = [assets]
    packages = root / "Packages"
    if packages.is_dir():
        if _is_link_like(packages) or not _within(packages, root):
            raise NavigationError(
                "invalid_project",
                f"Packages is a link or resolves outside the Unity project root: {packages}",
            )
        roots.append(packages)
    return roots


def _validated_project(project: Path) -> Tuple[Path, List[Path]]:
    try:
        root = Path(project).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise NavigationError(
            "invalid_project",
            f"Unity project root could not be resolved: {project}: {error}",
        ) from error
    if not root.is_dir():
        raise NavigationError(
            "invalid_project",
            f"Unity project root is not a directory: {root}",
        )
    return root, _included_roots(root)


def validate_project_root(project: Path) -> Path:
    """Validate only the project structure required by navigation."""

    return _validated_project(project)[0]


def _walk_files(root: Path, included_roots: Sequence[Path]):
    warnings: List[Dict[str, object]] = []
    files: List[Path] = []
    for included_root in included_roots:
        def on_error(error: OSError) -> None:
            relative = None
            if error.filename:
                try:
                    relative = Path(error.filename).relative_to(root).as_posix()
                except ValueError:
                    relative = str(error.filename)
            warnings.append(
                _warning(
                    "scan_unreadable",
                    f"Directory could not be read: {error}",
                    relative,
                )
            )

        for directory, names, filenames in os.walk(
            str(included_root),
            topdown=True,
            onerror=on_error,
            followlinks=False,
        ):
            base = Path(directory)
            kept_names = []
            for name in sorted(names):
                child = base / name
                if name.casefold() in EXCLUDED_DIRECTORY_NAMES:
                    continue
                if not _within(child, root):
                    warnings.append(
                        _warning(
                            "symlink_outside_root",
                            "Directory resolves outside the Unity project and was not traversed.",
                            _relative(child, root),
                        )
                    )
                    continue
                if _is_link_like(child):
                    warnings.append(
                        _warning(
                            "symlink_not_followed",
                            "Directory link was not traversed.",
                            _relative(child, root),
                        )
                    )
                    continue
                kept_names.append(name)
            names[:] = kept_names
            for name in sorted(filenames):
                child = base / name
                if _is_link_like(child):
                    if not _within(child, root):
                        warnings.append(
                            _warning(
                                "symlink_outside_root",
                                "File symlink resolves outside the Unity project and was not read.",
                                _relative(child, root),
                            )
                        )
                    else:
                        warnings.append(
                            _warning(
                                "symlink_not_followed",
                                "File link was not read.",
                                _relative(child, root),
                            )
                        )
                    continue
                files.append(child)
    return files, warnings


def _scene_counts(files: Sequence[Path], root: Path) -> Dict[str, int]:
    groups: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    standalone = 0
    total = 0
    for path in files:
        if path.suffix.lower() != ".unity":
            continue
        total += 1
        stem = path.stem
        layer = next((item for item in SCENE_LAYERS if stem.endswith(item)), None)
        if layer is None or len(stem) == len(layer):
            standalone += 1
            continue
        groups[(_relative(path.parent, root), stem[: -len(layer)])].add(layer)
    complete = sum(len(layers) == len(SCENE_LAYERS) for layers in groups.values())
    incomplete = sum(len(layers) < len(SCENE_LAYERS) for layers in groups.values())
    return {
        "total": total,
        "complete_sets": complete,
        "incomplete_sets": incomplete,
        "standalone": standalone,
    }


def project_summary(project: Path) -> Dict[str, object]:
    """Return the version-1 project summary envelope."""

    root = Path(project)
    base = {
        "schema_version": SCHEMA_VERSION,
        "command": "project",
        "status": "invalid_project",
        "project": {"root": str(root)},
        "query": {},
        "results": [],
        "limits": {},
        "truncated": False,
        "warnings": [],
        "error": None,
    }
    try:
        root = root.expanduser()
        base["project"] = {"root": str(root)}
        root, included_roots = _validated_project(root)
        version, major, compatible, warnings = _unity_version(root)
        files, scan_warnings = _walk_files(root, included_roots)
        counts = Counter(path.suffix.lower() for path in files)
        named = {
            "unity": counts[".unity"],
            "prefab": counts[".prefab"],
            "asset": counts[".asset"],
            "cs": counts[".cs"],
            "meta": counts[".meta"],
        }
        base.update(
            {
                "status": "ok",
                "project": {
                    "root": str(root),
                    "unity_version": version,
                    "unity_major": major,
                    "reference_unity_version": REFERENCE_UNITY_VERSION,
                    "unity_major_compatible": compatible,
                    "included_roots": [
                        _relative(path, root) for path in included_roots
                    ],
                },
                "results": [
                    {
                        "file_counts": {
                            "total": len(files),
                            **named,
                            "other": len(files) - sum(named.values()),
                        },
                        "scene_counts": _scene_counts(files, root),
                    }
                ],
                "warnings": _sorted_warnings([*warnings, *scan_warnings]),
            }
        )
    except NavigationError as error:
        base["error"] = {"code": error.code, "message": str(error)}
    except (OSError, RuntimeError) as error:
        base["status"] = "invalid_project"
        base["error"] = {"code": "invalid_project", "message": str(error)}
    return base


def exit_code(payload: Dict[str, object]) -> int:
    status = payload.get("status")
    if status == "ok":
        return 0
    return 2 if status in {"not_found", "ambiguous"} else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read an exported Blasphemous Unity project without modifying it.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    project = commands.add_parser("project", help="Summarize an exported Unity project.")
    project.add_argument("--project", required=True, help="Exported Unity project root.")
    asset = commands.add_parser("asset", help="Resolve one exported asset identity.")
    asset.add_argument("--project", required=True, help="Exported Unity project root.")
    selectors = asset.add_mutually_exclusive_group(required=True)
    selectors.add_argument("--path", help="Exact project-relative asset path.")
    selectors.add_argument("--guid", help="Exact 32-character hexadecimal GUID.")
    selectors.add_argument("--name", help="Case-insensitive exact basename or stem.")
    prefab = commands.add_parser("prefab", help="Inspect flattened Prefab evidence.")
    prefab.add_argument("--project", required=True, help="Exported Unity project root.")
    prefab_selectors = prefab.add_mutually_exclusive_group(required=True)
    prefab_selectors.add_argument("--path", help="Exact project-relative Prefab path.")
    prefab_selectors.add_argument("--guid", help="Exact 32-character hexadecimal GUID.")
    prefab_selectors.add_argument("--name", help="Case-insensitive exact basename or stem.")
    script = commands.add_parser("script", help="Locate a Unity C# script asset.")
    script.add_argument("--project", required=True, help="Exported Unity project root.")
    script_selectors = script.add_mutually_exclusive_group(required=True)
    script_selectors.add_argument("--path", help="Exact project-relative script path.")
    script_selectors.add_argument("--guid", help="Exact 32-character hexadecimal GUID.")
    script_selectors.add_argument("--name", help="Case-insensitive exact basename or stem.")
    scene = commands.add_parser("scene", help="Resolve a scene set or scene file.")
    scene.add_argument("--project", required=True, help="Exported Unity project root.")
    scene.add_argument("--path", help="Project path to one exact .unity file.")
    scene.add_argument("--name", help="Exact logical scene name or stem.")
    references = commands.add_parser(
        "references",
        help="Trace serialized references from an exported asset or object.",
    )
    references.add_argument("--project", required=True, help="Exported Unity project root.")
    reference_selectors = references.add_mutually_exclusive_group(required=True)
    reference_selectors.add_argument("--path", help="Exact project-relative asset path.")
    reference_selectors.add_argument("--guid", help="Exact 32-character hexadecimal GUID.")
    reference_selectors.add_argument("--name", help="Case-insensitive exact basename or stem.")
    references.add_argument(
        "--object-file-id",
        help="Optional signed 64-bit serialized object file ID.",
    )
    references.add_argument(
        "--direction",
        default="outgoing",
        help="Traversal direction: outgoing, incoming, or both.",
    )
    references.add_argument("--depth", default="1", help="Traversal depth from 1 to 4.")
    references.add_argument("--limit", default="30", help="Result edge limit from 1 to 100.")
    references.add_argument(
        "--timeout-seconds",
        default="60",
        help="Traversal timeout in seconds, up to 120.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args, unknown = parser.parse_known_args(argv)
    if unknown and args.command != "scene":
        parser.error("unrecognized arguments: " + " ".join(unknown))
    if args.command == "project":
        payload = project_summary(Path(args.project))
        return_code = exit_code(payload)
    elif args.command == "asset":
        from .unity_assets import asset_exit_code, asset_query

        if args.path is not None:
            selector, value = "path", args.path
        elif args.guid is not None:
            selector, value = "guid", args.guid
        else:
            selector, value = "name", args.name
        payload = asset_query(Path(args.project), selector, value)
        return_code = asset_exit_code(payload)
    elif args.command == "prefab":
        from .unity_assets import asset_exit_code
        from .unity_prefab import prefab_query

        if args.path is not None:
            selector, value = "path", args.path
        elif args.guid is not None:
            selector, value = "guid", args.guid
        else:
            selector, value = "name", args.name
        payload = prefab_query(Path(args.project), selector, value)
        return_code = asset_exit_code(payload)
    elif args.command == "script":
        from .unity_assets import asset_exit_code
        from .unity_script import script_query

        if args.path is not None:
            selector, value = "path", args.path
        elif args.guid is not None:
            selector, value = "guid", args.guid
        else:
            selector, value = "name", args.name
        payload = script_query(Path(args.project), selector, value)
        return_code = asset_exit_code(payload)
    elif args.command == "scene":
        from .unity_scene import scene_query

        payload = scene_query(Path(args.project), args.path, args.name, unknown)
        return_code = exit_code(payload)
    elif args.command == "references":
        from .unity_references import references_query

        if args.path is not None:
            selector, value = "path", args.path
        elif args.guid is not None:
            selector, value = "guid", args.guid
        else:
            selector, value = "name", args.name
        payload = references_query(
            Path(args.project),
            selector,
            value,
            args.object_file_id,
            args.direction,
            args.depth,
            args.limit,
            args.timeout_seconds,
        )
        return_code = exit_code(payload)
    else:  # pragma: no cover - argparse rejects unknown commands.
        raise AssertionError(args.command)
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
