# `preferences.md` Schema for blasphemous-modding-helper

## Format

`preferences.md` uses plain `key: value` lines (YAML subset, no top-level marker):

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

## Approved local reference locations

Local checkout uses same scope domain as its preferences file:

| Scope | Reference path | Preferences path |
|-------|----------------|------------------|
| User | `$HOME/.skills/blasphemous-modding-helper/references/modding-api` | `$HOME/.skills/blasphemous-modding-helper/preferences.md` |
| Project | `.skills/blasphemous-modding-helper/references/modding-api` | `.skills/blasphemous-modding-helper/preferences.md` |

Stored `modding_api_reference_path` value is absolute after setup. Missing
ModdingAPI fields are valid in legacy preferences and are added only when the
user opts into local reference setup. skipped local setup leaves both fields
absent so release-aware remote fallback remains available.

## Sibling lock state

Lifecycle commands store reproducibility state beside, not inside, the
checkout. For reference path ending in `references/modding-api`, lock
path is `references/modding-api.lock`. lock is plain `key: value` text:

```yaml
selector: latest
resolved_tag: v1.0.0
resolved_commit: 0123456789abcdef0123456789abcdef01234567
checked_at: 2026-08-22T12:34:56Z
repository: https://github.com/BrandenEK/Blasphemous.ModdingAPI.git
```

`selector`, `resolved_tag`, `resolved_commit`, and `checked_at` are required.
`repository` value records supported upstream used by operation.
Lock file is managed state and is not part of upstream Git worktree.

## Resolver fixture contract

`--metadata-file` is a deterministic test input, not live Release metadata.
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
fixture version, and `MODDING_API_FIXTURE_STATUS=historical` together. A
missing or mismatched `fixture_version` is a deterministic failure; repair the
fixture or use a matching selector. This prevents an old fixture from looking
like the current API.
