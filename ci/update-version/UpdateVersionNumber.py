#!/usr/bin/env python3
"""Update the package version everywhere from ci/update-version/version.yml.

ci/update-version/version.yml is the single source of truth:

    version: <current-version>

Every "version" field in the JSON manifests below is rewritten to match it:

    package.json
    .claude-plugin/plugin.json
    gemini-extension.json
    skills-lock.json            (main entry + sub-skill entries)

Usage:
    python ci/update-version/UpdateVersionNumber.py            # read version.yml and update
    python ci/update-version/UpdateVersionNumber.py --dry-run  # report changes without writing

Exit code 0 on success, 1 on failure (missing/invalid version source,
non-SemVer value, or no manifest updated).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = REPO_ROOT / "ci" / "update-version" / "version.yml"

# Files whose "version" fields are kept in sync with version.yml.
MANIFESTS = [
    "package.json",
    ".claude-plugin/plugin.json",
    "gemini-extension.json",
    "skills-lock.json",
]

# Python variant from https://semver.org/#is-there-a-suggested-regular-expression-regex
# `re.ASCII` keeps Python's \d aligned with SemVer's ASCII digit grammar.
SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>"
    r"(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*"
    r"))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+"
    r"(?:\.[0-9a-zA-Z-]+)*))?$",
    re.ASCII,
)
# Matches `"version": "..."` while preserving surrounding bytes exactly.
VERSION_KEY_RE = re.compile(r'("version"\s*:\s*")[^"]*(")')


def read_version() -> str:
    """Parse `version: X.Y.Z` from version.yml, tolerating comments."""
    if not VERSION_FILE.is_file():
        sys.exit(f"error: version source not found: {VERSION_FILE}")
    with open(VERSION_FILE, encoding="utf-8", newline="") as stream:
        lines = stream.read().splitlines()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^version\s*:\s*([^\s#]+)\s*$", line)
        if match:
            version = match.group(1).strip("\"'")
            if not SEMVER_RE.fullmatch(version):
                sys.exit(
                    f"error: '{version}' in {VERSION_FILE} is not valid SemVer "
                    "(expected MAJOR.MINOR.PATCH, optionally with -pre or +build)"
                )
            return version
    sys.exit(f"error: no 'version:' key found in {VERSION_FILE}")


def rewrite_manifest(rel_path: str, new_version: str):
    """Return (n_replacements, old_versions, new_text) or None if missing."""
    path = REPO_ROOT / rel_path
    if not path.is_file():
        return None
    with open(path, encoding="utf-8", newline="") as stream:
        text = stream.read()
    old_versions = re.findall(r'"version"\s*:\s*"([^"]*)"', text)
    new_text, n = VERSION_KEY_RE.subn(
        lambda m: m.group(1) + new_version + m.group(2), text
    )
    json.loads(new_text)  # fail fast if the rewrite broke the manifest
    return n, old_versions, new_text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync package version from version.yml into all manifests."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the changes without writing any file",
    )
    args = parser.parse_args()

    version = read_version()
    print(f"version source: {VERSION_FILE.relative_to(REPO_ROOT)} -> {version}")

    total = 0
    changed = 0
    pending_writes = []
    for rel in MANIFESTS:
        result = rewrite_manifest(rel, version)
        if result is None:
            print(f"error: required manifest not found: {rel}", file=sys.stderr)
            return 1
        n, old_versions, new_text = result
        if n == 0:
            print(
                f"error: required manifest has no 'version' field: {rel}",
                file=sys.stderr,
            )
            return 1
        total += n
        manifest_changed = sum(old != version for old in old_versions)
        changed += manifest_changed
        if manifest_changed == 0:
            print(f"  - {rel}: {n} field(s), already {version}")
        else:
            print(f"  - {rel}: {manifest_changed}/{n} field(s) -> {version}")
            pending_writes.append((rel, new_text))

    if total == 0:
        print("error: no manifest was updated")
        return 1
    if not args.dry_run:
        for rel, new_text in pending_writes:
            with open(REPO_ROOT / rel, "w", encoding="utf-8", newline="") as stream:
                stream.write(new_text)
    action = "would be updated" if args.dry_run else "updated"
    print(f"done: {changed} version field(s) {action}; {total} verified against {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
