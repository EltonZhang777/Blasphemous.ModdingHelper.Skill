# `config.yml` Schema for blasphemous-modding-helper

## Format

`config.yml` is a top-level YAML mapping. The supported configuration shape uses
scalar values for known fields and preserves unknown scalar, list, and mapping
fields when they are not changed by a workflow:

```yaml
full_source_code_path: Path/to/blasphemous-source-code

lightweight_source_code_path: Path/to/blasphemous-lightweight-source-code

modding_profile_path: Path/to/modding-profile

unity_log_dir: Path/to/unity-log-directory

modding_api_reference_path: /absolute/path/to/references/modding-api

modding_api_reference_selector: latest
```

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `full_source_code_path` | string | N/A | Full source code path (root path storing all source code files; it is preferably a path containing an `.sln` file) |
| `lightweight_source_code_path` | string | N/A | **Minimum field.** Lightweight source code path (root path storing decompiled game DLL source code; it is preferably a path containing an `.sln` file). The Skill-root Python decompiler ([decompile_source.py](../../scripts/decompile_source.py)) auto-generates this — its default output maps here. |
| `modding_profile_path` | string | N/A | Blasphemous modding profile root path (SHOULD contain `Blasphemous.exe` and `Modding` folder) |
| `unity_log_dir` | string | Optional | Directory containing the current Unity log. Windows normally contains `output_log.txt`; native Linux/macOS profiles normally contain `Player.log`. The test CLI reports a recovery handoff when this field or its log is missing. |
| `modding_api_reference_path` | string, optional | N/A | Normalized absolute path to a local ModdingAPI reference checkout. When absent, the agent uses the release-aware remote fallback. |
| `modding_api_reference_selector` | string, optional | `latest` when a local path is configured | Selector used for the local checkout: `latest`, `tag:REF`, `branch:REF`, or `commit:SHA`. `main` is not an implicit selector. |
| `check_period_days` | positive number, optional | `7` | Freshness period for shared configuration validation. Positive floating-point values are rounded down and stored as positive integers; invalid values enter first-time setup. |

## Freshness validation metadata

The shared `check_preferences.py --validate` configuration gate manages only these fields:

```yaml
last_checked_time: '2026-09-18T12:34:56Z'
last_checked_version: 2.0.0
check_period_days: 7
```

`last_checked_time` is UTC ISO 8601 metadata and `last_checked_version` is the
exact version from the installed Skill's `version.yml`. Missing, malformed, or
future metadata triggers validation. A current configuration within its period
returns `skipped` without writing. Successful validation returns `passed` or
`normalized`, writes the managed metadata, and preserves unrelated fields,
comments, and order. Invalid YAML or invalid `check_period_days` returns
`failed`, leaves the file unchanged, and routes to first-time setup.

## Approved local reference locations

Local checkout uses the same scope as its configuration file:

| Scope | Reference path | Config path |
|-------|----------------|------------------|
| User | `$HOME/.skills/blasphemous-modding-helper/references/modding-api` | `$HOME/.skills/blasphemous-modding-helper/config.yml` |
| Project | `.skills/blasphemous-modding-helper/references/modding-api` | `.skills/blasphemous-modding-helper/config.yml` |

`modding_api_reference_path` is absolute after setup. Missing
ModdingAPI fields remain valid in legacy configuration and are added only when the
user opts into local reference setup. Skipping local setup leaves both fields
absent, preserving release-aware remote fallback.

## Sibling lock state

Lifecycle commands store reproducibility state beside, not inside, the
checkout. For a reference path ending in `references/modding-api`, lock
path is `references/modding-api.lock`. lock is plain `key: value` text:

```yaml
selector: latest
resolved_tag: v1.0.0
resolved_commit: 0123456789abcdef0123456789abcdef01234567
checked_at: 2026-08-22T12:34:56Z
repository: https://github.com/BrandenEK/Blasphemous.ModdingAPI.git
```

`selector`, `resolved_tag`, `resolved_commit`, and `checked_at` are required.
`repository` records the supported upstream used by the operation.
Lock file is managed state, not part of the upstream Git worktree.

## Resolver fixture contract

`--metadata-file` is deterministic test input, not live Release metadata.
Every fixture record MUST declare `fixture_version` equal to its `tag_name` or
`resolved_ref`:

```json
{
  "tag_name": "v3.0.1",
  "fixture_version": "v3.0.1",
  "draft": false,
  "prerelease": false,
  "resolved_ref": "v3.0.1",
  "resolved_commit": "0123456789abcdef0123456789abcdef01234567"
}
```

Resolver output reports `MODDING_API_REFERENCE_VERSION`, fixture source,
fixture version, and `MODDING_API_FIXTURE_STATUS=historical` together. Missing
or mismatched `fixture_version` fails deterministically. Agent MUST repair the
fixture or use a matching selector. This prevents old fixtures from resembling
the current API.
