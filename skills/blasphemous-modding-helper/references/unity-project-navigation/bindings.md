# Script bindings

The `bindings` query lists direct `MonoBehaviour` script references in exported text `.unity`, `.prefab`, and `.asset` files. It reads `!u!114` objects with a direct `m_Script` field and does not reconstruct nested references or flattened Prefab instance chains.

## Project-wide query

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" bindings --project "<UNITY_PROJECT_ROOT>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') bindings --project '<UNITY_PROJECT_ROOT>'
```

The result is one version-1 JSON object. `results` contains one row per observed binding. Repeated scene or Prefab instances remain separate rows.

## Row fields

Source fields identify the serialized component:

- `source_asset_path`: project-relative POSIX path of the scene, Prefab, or asset.
- `source_asset_kind`: `scene`, `prefab`, or `asset`.
- `source_object_file_id`: decimal string for the source object; the value is local to that asset.
- `source_class_id`: `114` for `MonoBehaviour`.
- `source_class_name`: `MonoBehaviour`.

Reference fields preserve the serialized `m_Script` value:

- `reference_shape`: `structured`, `null`, or `malformed`.
- `m_script_file_id`: decimal string, including negative values and `"0"`.
- `m_script_guid`: lowercase 32-character hexadecimal GUID when valid.
- `m_script_type`: JSON integer when present.

Asset resolution and object resolution remain separate in the target fields:

- `target_asset_kind`, `target_asset_path`, and `target_asset_candidates`.
- `asset_resolution` and `asset_resolution_reason`.
- `script_object_resolution`.

A uniquely resolved `.cs` target reports `asset_resolution=resolved` and `script_object_resolution=asset_level_only`. This proves only that the GUID maps to a `.cs` asset. It does not prove a class, namespace, dependency, or behavior.

## Pagination

`--limit` controls the page size. The default is `200` and the maximum is `1000`. When another page exists, `next_cursor` is non-null; pass it with `--cursor` to continue:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" bindings --project "<UNITY_PROJECT_ROOT>" --limit 200 --cursor "<NEXT_CURSOR>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') bindings --project '<UNITY_PROJECT_ROOT>' --limit 200 --cursor '<NEXT_CURSOR>'
```

A middle page and a final page both report `status=ok`. A final page has `next_cursor=null`.

## Status and limits

- `status=ok` uses exit code `0`.
- `status=invalid_query` uses exit code `3` for an invalid limit or cursor.
- `status=invalid_project` uses exit code `3` when the project root is unusable.

Each binding row is serialized asset evidence. A `.cs` path in this command is not behavioral proof and is not treated as equivalent to the authoritative source tree. For classes, dependencies, call flow, or behavior, continue with the source analyzer.

## Next action

Report the source asset path, source object file ID, raw script reference, target asset state, and any warning or ambiguity. If a target is a `.cs` asset, report it as asset-level evidence only and select the source analyzer for behavior. The agent MUST NOT infer a class or script behavior from the Unity path.

## Completion criteria

Binding lookup work is complete only when the exact query, project root, status, page boundary, source and target fields, warnings, and source-analyzer handoff are reported.
