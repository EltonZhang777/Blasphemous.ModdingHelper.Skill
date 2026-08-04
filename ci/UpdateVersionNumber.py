#!/usr/bin/env python3
"""Update the package version everywhere from ci/version.yml.

ci/version.yml is the single source of truth:

    version: 1.2.0

Every "version" field in the JSON manifests below is rewritten to match it:

    package.json
    .claude-plugin/plugin.json
    gemini-extension.json
    skills-lock.json            (main entry + sub-skill entries)

Usage:
    python ci/UpdateVersionNumber.py            # read ci/version.yml and update
    python ci/UpdateVersionNumber.py --dry-run  # report changes without writing

Exit code 0 on success, 1 on failure (missing/invalid version source,
non-SemVer value, or no manifest updated).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "ci" / "version.yml"

# Files whose "version" fields are kept in sync with ci/version.yml.
MANIFESTS = [
    "package.json",
    ".claude-plugin/plugin.json",
    "gemini-extension.json",
    "skills-lock.json",
]

# SemVer core: MAJOR.MINOR.PATCH, optionally with -prerelease / +build metadata
# (https://semver.org/#semantic-versioning-specification-semver)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
# Matches `"version": "..."` while preserving surrounding bytes exactly.
VERSION_KEY_RE = re.compile(r'("version"\s*:\s*")[^"]*(")')


def read_version() -> str:
    """Parse `version: X.Y.Z` from ci/version.yml, tolerating comments."""
    if not VERSION_FILE.is_file():
        sys.exit(f"error: version source not found: {VERSION_FILE}")
    for raw in open(VERSION_FILE, encoding="utf-8", newline="").read().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^version\s*:\s*([^\s#]+)\s*$", line)
        if match:
            version = match.group(1).strip("\"'")
            if not SEMVER_RE.match(version):
                sys.exit(
                    f"error: '{version}' in {VERSION_FILE} is not valid SemVer "
                    "(expected MAJOR.MINOR.PATCH, optionally with -pre or +build)"
                )
            return version
    sys.exit(f"error: no 'version:' key found in {VERSION_FILE}")


def rewrite_manifest(rel_path: str, new_version: str):
    """Return (n_replacements, first_old_version, new_text) or None if missing."""
    path = REPO_ROOT / rel_path
    if not path.is_file():
        return None
    text = open(path, encoding="utf-8", newline="").read()
    old_versions = re.findall(r'"version"\s*:\s*"([^"]*)"', text)
    new_text, n = VERSION_KEY_RE.subn(
        lambda m: m.group(1) + new_version + m.group(2), text
    )
    json.loads(new_text)  # fail fast if the rewrite broke the manifest
    first_old = old_versions[0] if old_versions else ""
    return n, first_old, new_text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync package version from ci/version.yml into all manifests."
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
    for rel in MANIFESTS:
        result = rewrite_manifest(rel, version)
        if result is None:
            print(f"  - {rel}: MISSING (skipped)")
            continue
        n, old, new_text = result
        if n == 0:
            print(f"  - {rel}: no 'version' field found (skipped)")
            continue
        total += n
        if old == version:
            print(f"  - {rel}: {n} field(s), already {version}")
        else:
            print(f"  - {rel}: {n} field(s), {old} -> {version}")
            if not args.dry_run:
                open(REPO_ROOT / rel, "w", encoding="utf-8", newline="").write(new_text)

    if total == 0:
        print("error: no manifest was updated")
        return 1
    action = "would be" if args.dry_run else ""
    print(f"done: {total} version field(s) {action} synced to {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
