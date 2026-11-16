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
- `m_script_file_id`: decimal string, including negative values and `"0"`; valid values remain within the signed 64-bit range.
- `m_script_guid`: lowercase 32-character hexadecimal GUID when valid.
- `m_script_type`: JSON integer when present and valid.

Asset resolution and object resolution remain separate in the target fields:

- `target_asset_kind`, `target_asset_path`, and `target_asset_candidates`.
- `asset_resolution` and `asset_resolution_reason`.
- `script_object_resolution`.

A uniquely resolved `.cs` target reports `asset_resolution=resolved` and `script_object_resolution=asset_level_only`. This proves only that the GUID maps to a `.cs` asset. It does not prove a class, namespace, dependency, or behavior.

## Reference states

- `structured` retains a valid file ID and GUID and enters target resolution.
- `null` represents an explicit `fileID: 0` reference. It does not mean that the source component or target metadata is missing.
- `malformed` means the direct `m_Script` value is present but required fields are absent or invalid, a field type is invalid, or the inline map is incomplete. The row may include a bounded, sanitized `raw_reference` for diagnosis.

All rows keep the same target fields. Null and malformed rows use `asset_resolution=not_applicable` and `script_object_resolution=not_applicable`.

## Target states

`target_asset_path` is non-null only when one target path resolves uniquely. `target_asset_candidates` contains every sorted candidate when a GUID is duplicated.

| Observation | Target fields |
| --- | --- |
| No `.meta` supplies the referenced GUID | `target_asset_kind=unresolved`, `asset_resolution=missing`, `asset_resolution_reason=missing_meta` |
| `.meta` supplies the GUID but the target file is absent or not a file | `target_asset_kind=unresolved`, `asset_resolution=missing`, `asset_resolution_reason=missing_target` |
| The matching `.meta` is unreadable or malformed | `target_asset_kind=unresolved`, `asset_resolution=missing`, `asset_resolution_reason=unreadable_meta`, with a `metadata_unusable` warning |
| More than one target uses the GUID | `target_asset_kind=unresolved`, `asset_resolution=ambiguous`, `asset_resolution_reason=duplicate_guid`, with every candidate listed |
| One `.cs` target resolves | `target_asset_kind=cs`, `asset_resolution=resolved`, `script_object_resolution=asset_level_only` |
| One DLL target resolves | `target_asset_kind=binary`, `asset_resolution=resolved`, `script_object_resolution=not_verifiable_binary` |
| One other binary target resolves | `target_asset_kind=binary`, `asset_resolution=unsupported_binary`, `asset_resolution_reason=unsupported_format` |
| One non-C# text or other target resolves | `target_asset_kind=other`, `asset_resolution=resolved`, `script_object_resolution=not_applicable` |

DLL results retain the asset GUID, path, and raw reference only. No inferred MonoScript, class, candidate class, namespace, or behavior appears in a DLL result. Other target kinds remain separate from `.cs` evidence.

## Selectors and filters

No selector means project-wide enumeration. Filters narrow that inventory:

- `--path` names one exact project-relative `.unity`, `.prefab`, or `.asset` source file. The option may be repeated.
- `--object-file-id` selects one source object by its signed 64-bit decimal file ID. It requires exactly one `--path`.
- `--script-guid` performs a raw `m_Script.guid` reverse lookup. It may be repeated and includes bindings whose target is unresolved.
- `--reference-shape` accepts `structured`, `null`, or `malformed`.
- `--asset-resolution` accepts `resolved`, `missing`, `ambiguous`, `unsupported_binary`, or `not_applicable`.
- `--script-object-resolution` accepts `asset_level_only`, `not_verifiable_binary`, or `not_applicable`.

Repeated values within one selector or status axis use OR semantics. Different selector and status dimensions use AND semantics. Path and GUID values are normalized, deduplicated, and echoed in the JSON `query` object. A cursor is valid only for the same normalized query and project.

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" bindings --project "<UNITY_PROJECT_ROOT>" --path "Assets/Scenes/Main.unity" --path "Assets/Prefabs/Widget.prefab"
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" bindings --project "<UNITY_PROJECT_ROOT>" --path "Assets/Scenes/Main.unity" --object-file-id 100
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" bindings --project "<UNITY_PROJECT_ROOT>" --script-guid 0123456789abcdef0123456789abcdef --reference-shape structured --asset-resolution missing
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') bindings --project '<UNITY_PROJECT_ROOT>' --path 'Assets/Scenes/Main.unity' --path 'Assets/Prefabs/Widget.prefab'
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') bindings --project '<UNITY_PROJECT_ROOT>' --path 'Assets/Scenes/Main.unity' --object-file-id 100
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') bindings --project '<UNITY_PROJECT_ROOT>' --script-guid 0123456789abcdef0123456789abcdef --reference-shape structured --asset-resolution missing
```

An invalid path, object ID, GUID, status value, or cursor is an `invalid_query` with exit code `3`. An unsupported selector format, such as a non-Unity source path, reports `error.code=unsupported_format` with `status=invalid_query` and exit code `3`. An `--object-file-id` lookup has a uniqueness requirement: no matching object reports `status=not_found`, while more than one row reports `status=ambiguous`; both use exit code `2`. These uniqueness outcomes take precedence over partial coverage, while `scan_coverage` and warnings still report unavailable evidence.

## Pagination

`--limit` controls the page size. The default is `200` and the maximum is `1000`. When another page exists, `next_cursor` is non-null; pass it with `--cursor` to continue:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" bindings --project "<UNITY_PROJECT_ROOT>" --limit 200 --cursor "<NEXT_CURSOR>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') bindings --project '<UNITY_PROJECT_ROOT>' --limit 200 --cursor '<NEXT_CURSOR>'
```

A normal middle page and a normal final page for a complete, non-unique query both report `status=ok`. A final page has `next_cursor=null`. Object-ID not-found or ambiguous outcomes and partial coverage use their documented non-success status.

## Status and limits

- `status=ok` uses exit code `0`.
- `status=partial` uses exit code `4` when source or metadata evidence could not be scanned completely and no object-ID uniqueness outcome takes precedence; `scan_coverage` is then `partial`.
- `status=not_found` or `status=ambiguous` uses exit code `2` when an object-ID query cannot produce one unique row.
- `status=invalid_query` uses exit code `3` for an invalid limit, source path, object ID, GUID, status value, unsupported format, or cursor.
- `status=invalid_project` uses exit code `3` when the project root is unusable.

Each binding row is serialized asset evidence. A `.cs` path in this command is not behavioral proof and is not treated as equivalent to the authoritative source tree. For classes, dependencies, call flow, or behavior, continue with the source analyzer.

## Next action

Report the source asset path, source object file ID, raw script reference, target asset state, and any warning or ambiguity. If a target is a `.cs` asset, report it as asset-level evidence only and select the source analyzer for behavior. The agent MUST NOT infer a class or script behavior from the Unity path.

## Completion criteria

Binding lookup work is complete only when the exact query, project root, status, scan coverage, page boundary, source and target fields, warnings, and source-analyzer handoff are reported.
