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
MODDING_API_REPOSITORY = "https://github.com/BrandenEK/Blasphemous.ModdingAPI.git"
CHECKED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
LEGACY_SCRIPT_NAME = re.compile(r"\b[\w.-]+\.(?:js|ps1|sh)\b", re.IGNORECASE)
PYTHON_ENTRY_POINTS = (
    "blasphemous_modding_test.py",
    "check_python_environment.py",
    "check_preferences.py",
    "clone_modding_api.py",
    "decompile_source.py",
    "manage_modding_api.py",
    "resolve_modding_api.py",
    "test_modding_api_acceptance.py",
    "test_modding_api_live.py",
    "test_referencing_modding_api.py",
)


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


def audit_skill_documentation() -> None:
    """Reject documentation that still presents legacy script files as entry points."""

    documents = sorted(SKILL_ROOT.rglob("*.md"))
    contents = {path: read_file(path) for path in documents}
    legacy_references = []
    for path, document in contents.items():
        for match in LEGACY_SCRIPT_NAME.finditer(document):
            legacy_references.append(
                f"{path.relative_to(SKILL_ROOT).as_posix()}: {match.group(0)}"
            )
    if legacy_references:
        raise DocumentationTestFailure(
            "Skill documentation contains legacy script references:\n"
            + "\n".join(legacy_references)
        )

    corpus = "\n".join(contents.values())
    missing = [entry for entry in PYTHON_ENTRY_POINTS if entry not in corpus]
    if missing:
        raise DocumentationTestFailure(
            "Skill documentation does not expose Python entry points: "
            + ", ".join(missing)
        )


def parse_preferences(path: Path) -> Dict[str, str]:
    preferences: Dict[str, str] = {}
    for line in read_file(path).splitlines():
        match = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if match:
            preferences[match.group(1)] = match.group(2).strip()
    return preferences


def selected_version(selector: str) -> str:
    kind, separator, reference = selector.partition(":")
    return reference if separator and kind in ("tag", "branch", "commit") else selector


def run_git(reference_path: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=str(reference_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            check=False,
        )
    except OSError as error:
        raise DocumentationTestFailure(
            f"local checkout version could not be read: {error}. "
            "Next step: install Git or run the local reference manager."
        ) from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Git failed"
        raise DocumentationTestFailure(
            f"local checkout version could not be read: {detail}. "
            "Next step: run the local reference manager check/update."
        )
    return result.stdout.strip()


def local_checkout_version(reference_path: str) -> str:
    path = Path(reference_path)
    lock_values = parse_preferences(Path(reference_path + ".lock"))
    expected_commit = lock_values.get("resolved_commit", "")
    if (
        not expected_commit
        or not CHECKED_AT.fullmatch(lock_values.get("checked_at", ""))
        or lock_values.get("repository") != MODDING_API_REPOSITORY
    ):
        raise DocumentationTestFailure(
            f"local checkout lock is incomplete or unsupported: {path}.lock. "
            "Next step: run the local reference manager check/update."
        )
    actual_commit = run_git(path, "rev-parse", "HEAD")
    if actual_commit.lower() != expected_commit.lower():
        raise DocumentationTestFailure(
            "local checkout version mismatch: lock commit "
            f"{expected_commit} != checkout {actual_commit}. "
            "Next step: run the local reference manager update or repair its lock state."
        )
    expected_tag = lock_values.get("resolved_tag", "")
    if expected_tag:
        actual_tag = run_git(path, "describe", "--tags", "--exact-match", "HEAD")
        if actual_tag != expected_tag:
            raise DocumentationTestFailure(
                "local checkout version mismatch: lock tag "
                f"{expected_tag} != checkout tag {actual_tag}. "
                "Next step: run the local reference manager update or repair its lock state."
            )
        return actual_tag
    return actual_commit


def select_route(preferences: Dict[str, str]) -> Dict[str, str]:
    local_path = preferences.get("modding_api_reference_path")
    if local_path:
        selector = preferences.get("modding_api_reference_selector", "latest")
        documentation_path = (
            Path(local_path) / "docs" / "development" / "main.md"
        )
        return {
            "kind": "local",
            "path": local_path,
            "selector": selector,
            "checkout_selector": parse_preferences(
                Path(local_path + ".lock")
            ).get("selector", ""),
            "checkout_version": local_checkout_version(local_path),
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
    required = (
        "MODDING_API_REFERENCE_VERSION",
        "MODDING_API_RESOLUTION_SOURCE",
        "MODDING_API_FIXTURE_VERSION",
        "MODDING_API_FIXTURE_STATUS",
    )
    missing = [key for key in required if key not in values or not values[key]]
    if missing:
        raise DocumentationTestFailure(
            "release resolver did not report fixture/version context: "
            + ", ".join(missing)
        )
    return values


def assert_version_relationship(
    fixture_version: str,
    preference_selector: str,
    checkout_selector: str,
    local_checkout: str,
    remote_selector: str,
    remote_resolution: str,
    remote_commit: str,
) -> None:
    if not all(
        (
            fixture_version,
            preference_selector,
            checkout_selector,
            local_checkout,
            remote_selector,
            remote_resolution,
            remote_commit,
        )
    ):
        raise DocumentationTestFailure(
            "ModdingAPI version relationship is incomplete; report fixture version, "
            "selected preference, local checkout version, and remote resolution version."
        )
    if fixture_version != remote_resolution:
        raise DocumentationTestFailure(
            "ModdingAPI version mismatch: fixture "
            f"{fixture_version} != remote resolution {remote_resolution}. "
            "Next step: repair the fixture_version or select the matching Release."
        )
    if checkout_selector != preference_selector:
        raise DocumentationTestFailure(
            "ModdingAPI version mismatch: preference "
            f"{preference_selector} != local checkout selector {checkout_selector}. "
            "Next step: run the local reference manager update or repair its lock state."
        )
    if remote_selector == "latest":
        expected_remote = remote_resolution
    else:
        expected_remote = selected_version(remote_selector)
    if expected_remote != remote_resolution:
        raise DocumentationTestFailure(
            "ModdingAPI version mismatch: remote preference "
            f"{remote_selector} != remote resolution {remote_resolution}. "
            "Next step: repair the selector or resolve the matching Release."
        )
    if preference_selector == "latest":
        expected_local = remote_resolution
    elif preference_selector.startswith("branch:"):
        expected_local = remote_commit
    else:
        expected_local = selected_version(preference_selector)
    if expected_local != local_checkout:
        raise DocumentationTestFailure(
            "ModdingAPI version mismatch: preference "
            f"{preference_selector} != local checkout {local_checkout}. "
            "Next step: run the local reference manager update or repair its lock state."
        )


def run_documentation_smoke() -> None:
    audit_skill_documentation()
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
        local_version = "v3.0.1"
        run_git(local_path, "init", "-q")
        run_git(local_path, "config", "user.email", "reference-smoke@example.invalid")
        run_git(local_path, "config", "user.name", "Reference smoke")
        run_git(local_path, "add", "docs/development/main.md")
        run_git(local_path, "commit", "-qm", "fixture ModdingAPI reference")
        local_commit = run_git(local_path, "rev-parse", "HEAD")
        run_git(local_path, "tag", "-a", local_version, "-m", "fixture release")
        local_lock = Path(str(local_path) + ".lock")
        local_lock.write_text(
            "\n".join(
                (
                    f"selector: tag:{local_version}",
                    f"resolved_tag: {local_version}",
                    f"resolved_commit: {local_commit}",
                    "checked_at: 2026-09-04T00:00:00Z",
                    f"repository: {MODDING_API_REPOSITORY}",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        matching_metadata = fixture_root / "matching-release.json"
        matching_metadata.write_text(
            json.dumps(
                {
                    "tag_name": local_version,
                    "fixture_version": local_version,
                    "draft": False,
                    "prerelease": False,
                    "resolved_ref": local_version,
                    "resolved_commit": local_commit,
                }
            ),
            encoding="utf-8",
        )
        historical_metadata = fixture_root / "historical-release.json"
        historical_metadata.write_text(
            json.dumps(
                {
                    "tag_name": "v1.0.0",
                    "fixture_version": "v1.0.0",
                    "draft": False,
                    "prerelease": False,
                    "resolved_ref": "v1.0.0",
                    "resolved_commit": "1111111111111111111111111111111111111111",
                }
            ),
            encoding="utf-8",
        )
        mismatch_metadata = fixture_root / "mismatch-release.json"
        mismatch_metadata.write_text(
            json.dumps(
                {
                    "tag_name": local_version,
                    "fixture_version": "v1.0.0",
                    "draft": False,
                    "prerelease": False,
                    "resolved_ref": local_version,
                    "resolved_commit": local_commit,
                }
            ),
            encoding="utf-8",
        )
        local_preferences.write_text(
            "\n".join(
                (
                    "lightweight_source_code_path: /fixture/source",
                    f"modding_api_reference_path: {local_path}",
                    f"modding_api_reference_selector: tag:{local_version}",
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
            or local_route.get("checkout_version") != local_version
        ):
            raise DocumentationTestFailure(
                "configured local preferences must select the local reference route and version"
            )
        if not Path(local_route["documentation_path"]).is_file():
            raise DocumentationTestFailure("local route must point at docs/development/main.md")
        if local_route.get("selector") != f"tag:{local_version}":
            raise DocumentationTestFailure(
                "local preferences must preserve the configured selector"
            )

        remote_route = select_route(parse_preferences(skipped_preferences))
        if remote_route != {"kind": "remote-release", "selector": "latest"}:
            raise DocumentationTestFailure(
                "skipped local setup must select the latest release-aware remote route"
            )
        resolved_release = resolve_release_documentation(matching_metadata)
        assert_version_relationship(
            resolved_release["MODDING_API_FIXTURE_VERSION"],
            local_route["selector"],
            local_route["checkout_selector"],
            local_route["checkout_version"],
            remote_route["selector"],
            resolved_release["MODDING_API_REFERENCE_VERSION"],
            resolved_release["MODDING_API_RESOLVED_COMMIT"],
        )
        historical_release = resolve_release_documentation(historical_metadata)
        if (
            historical_release["MODDING_API_FIXTURE_STATUS"] != "historical"
            or historical_release["MODDING_API_FIXTURE_VERSION"] != "v1.0.0"
        ):
            raise DocumentationTestFailure(
                "historical fixture output must be explicitly labeled with its version"
            )
        remote_documentation = (
            f"{resolved_release['MODDING_API_DOCS_URL']}/development/main.md"
        )
        expected = (
            "https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/"
            "v3.0.1/docs/development/main.md"
        )
        if remote_documentation != expected or "/tree/main/" in remote_documentation:
            raise DocumentationTestFailure(
                "remote route must retain an explicit release reference"
            )
        historical_documentation = (
            f"{historical_release['MODDING_API_DOCS_URL']}/development/main.md"
        )
        historical_expected = (
            "https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/"
            "v1.0.0/docs/development/main.md"
        )
        if historical_documentation != historical_expected:
            raise DocumentationTestFailure(
                "historical fixture route must retain its explicit release reference"
            )
        try:
            resolve_release_documentation(mismatch_metadata)
        except DocumentationTestFailure as error:
            if "fixture_version" not in str(error) or "Repair" not in str(error):
                raise DocumentationTestFailure(
                    "version mismatch must include fixture and recovery guidance"
                ) from error
        else:
            raise DocumentationTestFailure(
                "mismatched fixture version must fail deterministically"
            )

    print("MODDING_API_DOC_ROUTE=local")
    print("MODDING_API_DOC_ROUTE=remote-release")
    print(f"MODDING_API_DOC_PATH={remote_documentation}")
    print(f"MODDING_API_PREFERENCE_SELECTOR={local_route['selector']}")
    print(f"MODDING_API_LOCAL_CHECKOUT_SELECTOR={local_route['checkout_selector']}")
    print(f"MODDING_API_LOCAL_CHECKOUT_VERSION={local_route['checkout_version']}")
    print(f"MODDING_API_REMOTE_PREFERENCE_SELECTOR={remote_route['selector']}")
    print(
        "MODDING_API_REMOTE_RESOLUTION_VERSION="
        f"{resolved_release['MODDING_API_REFERENCE_VERSION']}"
    )
    print(f"MODDING_API_FIXTURE_VERSION={resolved_release['MODDING_API_FIXTURE_VERSION']}")
    print(
        "MODDING_API_HISTORICAL_FIXTURE_VERSION="
        f"{historical_release['MODDING_API_FIXTURE_VERSION']}"
    )
    print("MODDING_API_HISTORICAL_FIXTURE_STATUS=historical")
    print(f"MODDING_API_HISTORICAL_FIXTURE_DOC_PATH={historical_documentation}")
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
