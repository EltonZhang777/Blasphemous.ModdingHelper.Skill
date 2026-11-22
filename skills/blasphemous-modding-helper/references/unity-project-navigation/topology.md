# Project topology

The `project` query identifies an exported Unity project before narrower asset navigation.

## Command

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" project --project "<UNITY_PROJECT_ROOT>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') project --project '<UNITY_PROJECT_ROOT>'
```

## Result

The version-1 envelope reports:

- `project.root`: the project-relative marker `.`. The caller supplies the actual root; public output does not repeat its absolute location.
- `project.unity_version`: the value from `ProjectSettings/ProjectVersion.txt`, or `null`.
- `project.unity_major_compatible`: whether the detected major version matches the [Unity coding baseline](../sub-skills/coding-standards.md#coding-specifications), or `null` when unknown.
- `project.included_roots`: physical `Assets` and optional `Packages` roots that were scanned.
- `results[0].file_counts`: total files plus `.unity`, `.prefab`, `.asset`, `.cs`, `.meta`, and `other` counts.
- `results[0].scene_counts`: total scenes, complete five-layer sets, incomplete sets, and standalone scenes.

Project-relative paths use forward slashes. A missing or unparseable Unity version produces `unity_version_unknown`. A major version other than the coding baseline's major version produces `unity_major_mismatch` but remains usable. A missing `Assets` root, an existing root that is not a directory, or an included root that resolves outside the project is `invalid_project`.

The five recognized scene layers are `_MAIN`, `_LOGIC`, `_LAYOUT`, `_DECO`, and `_AUDIO`. Only all five members produce a complete set. Partial groups remain incomplete and MUST NOT be completed by guessing absent paths. An unsuffixed `.unity` file is standalone.

The scanner skips `Library`, `Temp`, `Obj`, `obj`, `.vs`, `.vscode`, `.git`, `.idea`, `Logs`, `UserSettings`, `Build`, and `Builds`. It does not follow directory symlinks or junctions. An external link produces `symlink_outside_root`; an internal link produces `symlink_not_followed`. Neither contributes evidence.

The project summary is orientation only. It does not prove scene content, component relationships, C# behavior, or runtime state. The configured source analyzer remains the behavior authority.

## Completion criteria

Topology work is complete only when the command's `status`, Unity version and compatibility, included roots, file counts, scene-set completeness, warnings, and next action are reported.
