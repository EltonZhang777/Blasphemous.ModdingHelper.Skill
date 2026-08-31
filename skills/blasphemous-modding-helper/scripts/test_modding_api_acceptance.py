#!/usr/bin/env python3
"""Run the Python-only deterministic acceptance surface for the Skill."""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence
from urllib.parse import unquote


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
REPOSITORY_ROOT = SKILL_ROOT.parents[1]
ROOT_RUNNER = REPOSITORY_ROOT / "tests" / "run_blasphemous_modding_test.py"
INSTALLER = REPOSITORY_ROOT / "bin" / "install.js"
INSTALLER_TEST = REPOSITORY_ROOT / "tests" / "test_installer.js"


class AcceptanceError(RuntimeError):
    """A user-facing acceptance-gate failure."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Python-only deterministic acceptance surface for the "
            "Blasphemous ModdingAPI Skill."
        ),
        epilog=(
            "Migrated Skill behavior runs through Python entry points. "
            "The Node.js installer is tested separately; live GitHub, Steam, "
            "game, and Manual verification remain opt-in."
        ),
    )
    parser.add_argument(
        "--python",
        dest="python_executable",
        default=sys.executable,
        help="Python 3 executable for the deterministic test surface (default: current interpreter).",
    )
    parser.add_argument(
        "--node",
        dest="node_executable",
        default=os.environ.get("MODDING_API_NODE") or shutil.which("node") or "node",
        help="Node.js executable for the separate installer boundary tests.",
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Fail after all checks unless the repository worktree is clean.",
    )
    return parser


def run_command(
    label: str,
    command: Sequence[str],
    *,
    cwd: Path = REPOSITORY_ROOT,
) -> subprocess.CompletedProcess[str]:
    print(f"[RUN] {label}")
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
    except OSError as error:
        raise AcceptanceError(f"{label} could not start: {error}") from error
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise AcceptanceError(
            f"{label} failed with exit code {result.returncode}."
        )
    print(f"[OK] {label}")
    return result


def run_check(label: str, check: Callable[[], None]) -> None:
    print(f"[RUN] {label}")
    try:
        check()
    except (AcceptanceError, OSError, UnicodeError) as error:
        raise AcceptanceError(f"{label} failed: {error}") from error
    print(f"[OK] {label}")


def run_python_surface(python_executable: str) -> None:
    run_command(
        "Python deterministic contract surface",
        (
            python_executable,
            str(ROOT_RUNNER),
            "--python",
            python_executable,
        ),
    )


def run_installer_surface(node_executable: str) -> None:
    run_command(
        "Node installer regression test",
        (node_executable, str(INSTALLER_TEST)),
    )
    for agent in ("trae-cn", "claude-code"):
        run_command(
            f"Node installer dry-run ({agent})",
            (node_executable, str(INSTALLER), "--dry-run", "--only", agent),
        )
    run_command("Node installer help", (node_executable, str(INSTALLER), "--help"))


def _git_markdown_files(arguments: Sequence[str]) -> List[Path]:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=str(REPOSITORY_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
    except OSError as error:
        raise AcceptanceError(f"Git Markdown file discovery could not start: {error}") from error
    if result.returncode != 0:
        raise AcceptanceError(
            "Git Markdown file discovery failed:\n"
            f"{result.stdout}\n{result.stderr}"
        )
    paths = []
    for raw_path in result.stdout.split("\0"):
        if not raw_path or not raw_path.lower().endswith(".md"):
            continue
        path = (REPOSITORY_ROOT / raw_path).resolve()
        if path.is_file():
            paths.append(path)
    return paths


def tracked_markdown_files() -> List[Path]:
    return _git_markdown_files(
        (
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            "*.md",
        )
    )


def ignored_markdown_files() -> List[Path]:
    return _git_markdown_files(
        (
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "-z",
            "--",
            "*.md",
        )
    )


def display_path(path: Path) -> str:
    return path.relative_to(REPOSITORY_ROOT).as_posix()


def markdown_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split()[0] if target.split() else ""
    return target.split("#", 1)[0]


def find_missing_markdown_links(files: Iterable[Path]) -> List[str]:
    missing: List[str] = []
    link_pattern = re.compile(r"!?\[[^\]]*\]\(([^)\r\n]+)\)")
    for path in files:
        contents = path.read_text(encoding="utf-8")
        for match in link_pattern.finditer(contents):
            target = markdown_target(match.group(1))
            if (
                not target
                or target.startswith("#")
                or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
                or target.startswith("//")
            ):
                continue
            resolved = (path.parent / unquote(target)).resolve()
            if not resolved.exists():
                missing.append(f"{display_path(path)} -> {target}")
    return missing


def check_markdown_links() -> None:
    repository_files = tracked_markdown_files()
    ignored_files = ignored_markdown_files()
    missing = find_missing_markdown_links(repository_files)
    ignored_missing = find_missing_markdown_links(ignored_files)
    if ignored_files:
        print(
            "[INFO] ignored Markdown files excluded from repository link "
            f"validation ({len(ignored_files)}):"
        )
        for path in ignored_files:
            print(display_path(path))
    if ignored_missing:
        print("[WARN] ignored local Markdown link findings (not release failures):")
        for item in ignored_missing:
            print(item)
    if missing:
        raise AcceptanceError(
            "missing repository Markdown links:\n" + "\n".join(missing)
        )


def check_git_diff() -> None:
    run_command("git diff --check", ("git", "diff", "--check"))


def check_clean_worktree() -> None:
    result = run_command("clean worktree check", ("git", "status", "--porcelain"))
    if result.stdout.strip():
        raise AcceptanceError(f"worktree is not clean:\n{result.stdout}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    print("Acceptance runner: native Python")
    print(f"Platform: {platform.system()}")
    print(f"Python: {args.python_executable}")
    print(f"Node installer boundary: {args.node_executable}")
    try:
        run_python_surface(args.python_executable)
        run_installer_surface(args.node_executable)
        run_check("Markdown link check", check_markdown_links)
        run_check("git diff --check", check_git_diff)
        if args.require_clean:
            run_check("clean worktree check", check_clean_worktree)
    except AcceptanceError as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
