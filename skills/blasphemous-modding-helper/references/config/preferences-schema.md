# `preferences.md` Schema for blasphemous-modding-helper

## Format

`preferences.md` uses plain `key: value` lines (a YAML subset, no top-level marker):

```yaml
full_source_code_path: Path/to/blasphemous-source-code

lightweight_source_code_path: Path/to/blasphemous-lightweight-source-code

modding_profile_path: Path/to/modding-profile

unity_log_dir: Path/to/unity-log-directory
```

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `full_source_code_path` | string | N/A | Full source code path (root path storing all source code files, should better be containing `.sln` file) |
| `lightweight_source_code_path` | string | N/A | **MINIMUM required field.** Lightweight source code path (root path storing decompiled game DLL source code, should better be containing `.sln` file). The decompile scripts (`scripts/decompile_source.ps1` for Windows, `scripts/decompile_source.sh` for macOS/Linux) auto-generate this — their default output maps here. |
| `modding_profile_path` | string | N/A | Blasphemous modding profile root path (SHOULD contain `Blasphemous.exe` and `Modding` folder) |
| `unity_log_dir` | string | Optional | Directory containing the current Unity log. Windows normally contains `output_log.txt`; native Linux/macOS profiles normally contain `Player.log`. The test CLI reports a recovery handoff when this field or its log is missing. |
