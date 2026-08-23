# `preferences.md` Schema for blasphemous-modding-helper

## Format

`preferences.md` uses plain `key: value` lines (a YAML subset, no top-level marker):

```yaml
full_source_code_path: Path/to/blasphemous-source-code

lightweight_source_code_path: Path/to/blasphemous-lightweight-source-code

modding_profile_path: Path/to/modding-profile

modding_api_reference_path: /absolute/path/to/references/modding-api

modding_api_reference_selector: latest
```

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `full_source_code_path` | string | N/A | Full source code path (root path storing all source code files; it is preferably a path containing an `.sln` file) |
| `lightweight_source_code_path` | string | N/A | **Minimum field.** Lightweight source code path (root path storing decompiled game DLL source code; it is preferably a path containing an `.sln` file). The decompile scripts (`scripts/decompile_source.ps1` for Windows, `scripts/decompile_source.sh` for macOS/Linux) auto-generate this — their default output maps here. |
| `modding_profile_path` | string | N/A | Blasphemous modding profile root path (SHOULD contain `Blasphemous.exe` and `Modding` folder) |
| `modding_api_reference_path` | string, optional | N/A | Normalized absolute path to a local ModdingAPI reference checkout. When absent, the agent uses the release-aware remote fallback. |
| `modding_api_reference_selector` | string, optional | `latest` when a local path is configured | Selector used for the local checkout: `latest`, `tag:REF`, `branch:REF`, or `commit:SHA`. `main` is not an implicit selector. |

## Approved local reference locations

The local checkout uses the same scope domain as its preferences file:

| Scope | Reference path | Preferences path |
|-------|----------------|------------------|
| User | `$HOME/.skills/blasphemous-modding-helper/references/modding-api` | `$HOME/.skills/blasphemous-modding-helper/preferences.md` |
| Project | `.skills/blasphemous-modding-helper/references/modding-api` | `.skills/blasphemous-modding-helper/preferences.md` |

The stored `modding_api_reference_path` value is absolute after setup. Missing
ModdingAPI fields are valid in legacy preferences and are added only when the
user opts into local reference setup. A skipped local setup leaves both fields
absent so release-aware remote fallback remains available.

## Sibling lock state

The lifecycle commands store reproducibility state beside, not inside, the
checkout. For a reference path ending in `references/modding-api`, the lock
path is `references/modding-api.lock`. The lock is plain `key: value` text:

```yaml
selector: latest
resolved_tag: v1.0.0
resolved_commit: 0123456789abcdef0123456789abcdef01234567
checked_at: 2026-08-22T12:34:56Z
repository: https://github.com/BrandenEK/Blasphemous.ModdingAPI.git
```

`selector`, `resolved_tag`, `resolved_commit`, and `checked_at` are required.
The `repository` value records the supported upstream used by the operation.
The lock file is managed state and is not part of the upstream Git worktree.
