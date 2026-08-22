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
| `full_source_code_path` | string | N/A | Full source code path (root path storing all source code files, should better be containing `.sln` file) |
| `lightweight_source_code_path` | string | N/A | **MINIMUM required field.** Lightweight source code path (root path storing decompiled game DLL source code, should better be containing `.sln` file). The decompile scripts (`scripts/decompile_source.ps1` for Windows, `scripts/decompile_source.sh` for macOS/Linux) auto-generate this — their default output maps here. |
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
