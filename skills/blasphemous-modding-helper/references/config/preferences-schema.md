# `preferences.md` Schema for blasphemous-modding-helper

## Format

`preferences.md` uses YAML format:

```yaml
full_source_code_path: Path/to/blasphemous-source-code

lightweight_source_code_path: Path/to/blasphemous-lightweight-source-code

modding_profile_path: Path/to/modding-profile
```

## Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `full_source_code_path` | string | N/A | Full source code path (root path storing all source code files, should better be containing `.sln` file) |
| `lightweight_source_code_path` | string | N/A | Lightweight source code path (root path storing only key source code files like `Assembly-CSharp.dll`, should better be containing `.sln` file) |
| `modding_profile_path` | string | N/A | Blasphemous modding profile root path (SHOULD contain `Blasphemous.exe` and `Modding` folder) |
