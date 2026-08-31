#!/usr/bin/env python3
"""Smoke-test ModdingAPI documentation routing through Python entry points."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional, Sequence
from urllib.parse import unquote


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
REPOSITORY_ROOT = SKILL_ROOT.parents[1]
RESOLVER = SCRIPT_ROOT / "resolve_modding_api.py"


class DocumentationTestFailure(RuntimeError):
    """A user-facing documentation smoke-test failure."""


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise DocumentationTestFailure(f"could not read {path}: {error}") from error


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise DocumentationTestFailure(f"{label} must contain: {needle}")


def assert_not_contains(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise DocumentationTestFailure(f"{label} must not contain: {needle}")


def parse_preferences(path: Path) -> Dict[str, str]:
    preferences: Dict[str, str] = {}
    for line in read_file(path).splitlines():
        match = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if match:
            preferences[match.group(1)] = match.group(2).strip()
    return preferences


def select_route(preferences: Dict[str, str]) -> Dict[str, str]:
    local_path = preferences.get("modding_api_reference_path")
    if local_path:
        documentation_path = (
            Path(local_path) / "docs" / "development" / "main.md"
        )
        return {
            "kind": "local",
            "path": local_path,
            "selector": preferences.get("modding_api_reference_selector", "latest"),
            "documentation_path": str(documentation_path),
        }
    return {"kind": "remote-release", "selector": "latest"}


def resolve_release_documentation(metadata_file: Path) -> Dict[str, str]:
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(RESOLVER),
                "--selector",
                "latest",
                "--metadata-file",
                str(metadata_file),
            ],
            cwd=str(REPOSITORY_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
    except OSError as error:
        raise DocumentationTestFailure(
            f"release resolver could not run: {error}"
        ) from error
    if result.returncode != 0:
        raise DocumentationTestFailure(
            "release resolver failed:\n"
            f"{result.stdout}\n{result.stderr}"
        )
    values: Dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    if not values.get("MODDING_API_DOCS_URL"):
        raise DocumentationTestFailure(
            "release resolver did not emit MODDING_API_DOCS_URL"
        )
    return values


def run_documentation_smoke() -> None:
    documents = {
        "top-level Skill": read_file(SKILL_ROOT / "SKILL.md"),
        "Invocation preflight reference": read_file(
            SKILL_ROOT / "references" / "config" / "invocation-preflight.md"
        ),
        "First-Time Setup reference": read_file(
            SKILL_ROOT / "references" / "config" / "first-time-setup.md"
        ),
        "ModdingAPI route": read_file(
            SKILL_ROOT / "references" / "sub-skills" / "referencing-modding-api.md"
        ),
        "source route": read_file(
            SKILL_ROOT / "references" / "sub-skills" / "source-analyzer.md"
        ),
        "log route": read_file(
            SKILL_ROOT / "references" / "sub-skills" / "log-analyzer.md"
        ),
        "mod-test route": read_file(
            SKILL_ROOT / "references" / "sub-skills" / "blasphemous-modding-test.md"
        ),
        "source navigation": read_file(
            SKILL_ROOT / "references" / "source_code_navigation" / "MAIN.md"
        ),
    }
    top_level = documents["top-level Skill"]
    preflight = documents["Invocation preflight reference"]
    setup = documents["First-Time Setup reference"]
    referencing = documents["ModdingAPI route"]
    source = documents["source route"]
    logs = documents["log route"]
    mod_test = documents["mod-test route"]
    source_navigation = documents["source navigation"]

    assert_contains(
        top_level,
        "references/sub-skills/referencing-modding-api.md",
        "top-level Skill",
    )
    assert_contains(
        top_level,
        "references/config/invocation-preflight.md",
        "top-level Skill",
    )
    assert_not_contains(top_level, "## Skill command context", "top-level Skill")
    assert_not_contains(
        top_level,
        "## Preferences gate (see Invocation preflight)",
        "top-level Skill",
    )
    assert_not_contains(top_level, "main branch", "top-level Skill")
    assert_not_contains(top_level, "/tree/main", "top-level Skill")

    for heading in (
        "# Invocation preflight",
        "## Command context",
        "## Preferences gate",
        "## First-time setup and recovery",
        "## Completion criteria",
    ):
        assert_contains(preflight, heading, "Invocation preflight reference")
    for contract_text in (
        "absolute installed directory",
        "current working directory",
        "Project scope MUST take precedence over user scope",
        "check_preferences.py",
        "/blasphemous-modding-test stop SESSION_ID",
    ):
        assert_contains(
            preflight,
            contract_text,
            "Invocation preflight reference",
        )
    assert_contains(
        setup,
        "[Invocation preflight](invocation-preflight.md)",
        "First-Time Setup reference",
    )
    assert_contains(setup, "decompile_source.py", "First-Time Setup reference")

    for label, document in (
        ("source route", source),
        ("log route", logs),
        ("mod-test route", mod_test),
        ("ModdingAPI route", referencing),
    ):
        assert_contains(document, "../config/invocation-preflight.md", label)
        assert_not_contains(
            document,
            "../../SKILL.md#skill-command-context",
            label,
        )
    assert_contains(source, "## Completion criteria", "source route")
    assert_contains(logs, "## Completion criteria", "log route")
    assert_contains(mod_test, "Completion criterion", "mod-test route")

    for heading in (
        "## Routing contract",
        "## Stable API topic routing",
        "## Advanced and archived topics",
        "## Game-source separation",
        "## Documentation smoke check",
    ):
        assert_contains(referencing, heading, "ModdingAPI reference sub-skill")
    for page in (
        "docs/development/main.md",
        "docs/development/setup.md",
        "docs/development/mod.md",
        "docs/development/execution.md",
        "docs/development/persistence.md",
        "docs/development/logging.md",
        "docs/development/config.md",
        "docs/development/files.md",
        "docs/development/input.md",
        "docs/development/localization.md",
        "docs/development/console.md",
        "docs/development/items.md",
        "docs/development/levels.md",
        "docs/development/penitence.md",
    ):
        assert_contains(referencing, f"`{page}`", "ModdingAPI reference sub-skill")
    assert_contains(
        referencing,
        "../source_code_navigation/MAIN.md",
        "ModdingAPI reference sub-skill",
    )
    assert_contains(
        source_navigation,
        "# Blasphemous Source Code Navigation Guide",
        "source navigation",
    )

    with tempfile.TemporaryDirectory(prefix="modding-api-reference-doc-smoke-") as raw_root:
        fixture_root = Path(raw_root)
        local_preferences = fixture_root / "local-preferences.md"
        skipped_preferences = fixture_root / "skipped-preferences.md"
        local_path = fixture_root / "references" / "modding-api"
        local_documentation = local_path / "docs" / "development" / "main.md"
        local_documentation.parent.mkdir(parents=True)
        local_documentation.write_text(
            "# fixture ModdingAPI documentation index\n",
            encoding="utf-8",
        )
        release_metadata = fixture_root / "latest-release.json"
        release_metadata.write_text(
            json.dumps(
                {
                    "tag_name": "v1.0.0",
                    "draft": False,
                    "prerelease": False,
                    "resolved_ref": "v1.0.0",
                    "resolved_commit": "0123456789012345678901234567890123456789",
                }
            ),
            encoding="utf-8",
        )
        local_preferences.write_text(
            "\n".join(
                (
                    "lightweight_source_code_path: /fixture/source",
                    f"modding_api_reference_path: {local_path}",
                    "modding_api_reference_selector: tag:v1.0.0",
                )
            ),
            encoding="utf-8",
        )
        skipped_preferences.write_text(
            "lightweight_source_code_path: /fixture/source\n",
            encoding="utf-8",
        )

        local_route = select_route(parse_preferences(local_preferences))
        if (
            local_route.get("kind") != "local"
            or local_route.get("path") != str(local_path)
            or local_route.get("documentation_path") != str(local_documentation)
        ):
            raise DocumentationTestFailure(
                "configured local preferences must select the local reference route"
            )
        if not Path(local_route["documentation_path"]).is_file():
            raise DocumentationTestFailure("local route must point at docs/development/main.md")
        if local_route.get("selector") != "tag:v1.0.0":
            raise DocumentationTestFailure(
                "local preferences must preserve the configured selector"
            )

        remote_route = select_route(parse_preferences(skipped_preferences))
        if remote_route != {"kind": "remote-release", "selector": "latest"}:
            raise DocumentationTestFailure(
                "skipped local setup must select the latest release-aware remote route"
            )
        resolved_release = resolve_release_documentation(release_metadata)
        remote_documentation = (
            f"{resolved_release['MODDING_API_DOCS_URL']}/development/main.md"
        )
        expected = (
            "https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/"
            "v1.0.0/docs/development/main.md"
        )
        if remote_documentation != expected or "/tree/main/" in remote_documentation:
            raise DocumentationTestFailure(
                "remote route must retain an explicit release reference"
            )

    print("MODDING_API_DOC_ROUTE=local")
    print("MODDING_API_DOC_ROUTE=remote-release")
    print(f"MODDING_API_DOC_PATH={remote_documentation}")
    print("[OK] referencing_modding_api documentation smoke")


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Run the ModdingAPI documentation routing smoke test."
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    build_parser().parse_args(argv)
    try:
        run_documentation_smoke()
    except DocumentationTestFailure as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
