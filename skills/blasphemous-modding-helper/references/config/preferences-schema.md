# `preferences.md` Schema for blasphemous-modding-helper

## Format

`preferences.md` uses plain `key: value` lines (a YAML subset, no top-level marker):

```yaml
full_source_code_path: Path/to/blasphemous-source-code

lightweight_source_code_path: Path/to/blasphemous-lightweight-source-code

modding_profile_path: Path/to/modding-profile
```

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `full_source_code_path` | string | N/A | Full source code path (root path storing all source code files; it is preferably a path containing an `.sln` file) |
| `lightweight_source_code_path` | string | N/A | **Minimum field.** Lightweight source code path (root path storing decompiled game DLL source code; it is preferably a path containing an `.sln` file). The decompile scripts (`scripts/decompile_source.ps1` for Windows, `scripts/decompile_source.sh` for macOS/Linux) auto-generate this — their default output maps here. |
| `modding_profile_path` | string | N/A | Blasphemous modding profile root path (SHOULD contain `Blasphemous.exe` and `Modding` folder) |
