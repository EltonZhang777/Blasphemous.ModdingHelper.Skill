# Serialized component relations

The `references` query traces serialized object references from one exported asset or one object file ID. It reports only references present in Unity YAML documents. It never opens Unity Editor, changes the export, builds a C# call graph, or maps a script ID to a behavior type.

## Command

The query accepts exactly one asset selector and the common `--project` argument:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" references --project "<UNITY_PROJECT_ROOT>" --path "<ASSET_PATH>"
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" references --project "<UNITY_PROJECT_ROOT>" --guid "<ASSET_GUID>"
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" references --project "<UNITY_PROJECT_ROOT>" --name "<ASSET_NAME_OR_STEM>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') references --project '<UNITY_PROJECT_ROOT>' --path '<ASSET_PATH>'
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') references --project '<UNITY_PROJECT_ROOT>' --guid '<ASSET_GUID>'
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') references --project '<UNITY_PROJECT_ROOT>' --name '<ASSET_NAME_OR_STEM>'
```

Optional traversal controls:

- `--object-file-id`: restrict the root to one signed 64-bit serialized object ID.
- `--direction outgoing|incoming|both`: choose the traversal direction. The aliases `bidirectional` and `both` select both directions.
- `--depth`: traversal depth from 1 to 4. The default is 1.
- `--limit`: maximum edge results per traversal from 1 to 100. The default is 30.
- `--timeout-seconds`: total query timeout from greater than 0 to 120 seconds. The default is 60.

Without `--object-file-id`, objects in the selected asset are depth-0 roots. The limit also bounds those roots; omitted roots set `truncated` and make the result incomplete. With `--object-file-id`, only the matching object is a root. Local object IDs are scoped to one serialized file.

## Direct bindings versus reference traversal

The agent MUST select `bindings` when the question is specifically which script asset a direct MonoBehaviour `m_Script` field references. The binding result keeps `source_asset_path`, `source_object_file_id`, `reference_shape`, `m_script_file_id`, `m_script_guid`, `target_asset_kind`, `target_asset_path`, `asset_resolution`, `asset_resolution_reason`, and `script_object_resolution` together.

The agent MUST select `references` when the question spans arbitrary serialized fields, incoming edges, nested traversal, cycles, or multiple target kinds. The two commands have different evidence scopes; the agent MUST NOT infer one from the other.

A binding that resolves to a `.cs` asset is asset-level evidence only. A binding that resolves to a DLL retains the asset identity but does not reveal a class or MonoScript object inside the binary. See [bindings.md](bindings.md) for the full binding contract.

## Result interpretation

The version-1 envelope contains `schema_version`, `command`, `status`, `project`, `query`, `root`, `asset_candidates`, `results`, `limits`, `truncated`, `complete`, `incomplete_reasons`, `warnings`, and `error`.

`results` contains one traversal for `outgoing` or `incoming`, and contains outgoing followed by incoming for `both`. Each traversal reports:

- `direction`, `status`, `complete`, `incomplete_reasons`, `node_count`, and `edge_count`.
- `nodes`: root and discovered object identities with `path`, `guid`, `file_id`, `class_id`, `class_name`, `name`, `depth`, `status`, `reason`, and `candidate_paths`.
- `edges`: the observed serialized reference with `depth`, `scope`, `field`, `line`, `guid`, `file_id`, `type`, and nested `source` and `target` identities.

`scope: "local"` means the reference uses a file-local object ID. `scope: "external"` means the reference includes a GUID. An external GUID is resolved only through one unique sibling `.meta` identity. A missing GUID, duplicate GUID, missing object, binary target, non-serialized target, or unreadable target remains explicitly unresolved or ambiguous; the query never substitutes a guessed asset. Duplicate GUID identities return their sorted `candidate_paths`.

Nodes and edges are sorted deterministically by depth, project-relative path, object file ID, GUID, field, and source line as applicable. Each object is visited at most once per traversal, so cyclic graphs terminate without repeating nodes.

## Limits and incomplete evidence

- `status: "ok"` with `truncated: true` means the edge limit was reached. `complete` is false and `incomplete_reasons` contains `limit`.
- `status: "timeout"` means the query stopped at the timeout. Any returned traversal evidence is partial, `complete` is false, and `incomplete_reasons` contains `timeout`.
- An incoming query requires a usable root GUID for external incoming references. A missing or ambiguous GUID leaves external incoming scope unavailable and makes the traversal incomplete.
- An unreadable or malformed non-target serialized file is skipped with a bounded warning and makes incoming coverage incomplete. A malformed direct target returns structured non-success.
- Binary assets are not parsed. Their content, dimensions, meshes, audio, and other opaque data are not evidence.

## Evidence limits

The export is authoritative only for observed serialized objects and references. Class IDs, component containers, and reference fields are serialization evidence, not proof of C# behavior, runtime execution, dependency direction, MonoBehaviour semantics, script-ID types, or gameplay state. A direct binding to a script asset is not behavioral proof, and a DLL target never supplies class identity.

Prefab evidence remains flattened. Reference traversal MUST NOT reconstruct Prefab nesting, variants, or modification chains. Scene object IDs are scoped to one scene layer file.

## Completion criteria

Reference navigation is complete only when the selector, object scope, direction, depth, limit, timeout, root identity, traversal status, node and edge counts, unresolved targets, truncation, timeout, and warnings are reported. Returned paths MUST be project-relative with forward slashes.

## Next action

For a direct script binding, select [bindings.md](bindings.md). For a resolved reference target, cite its project-relative path, GUID, and object ID, then select [assets-and-guids.md](assets-and-guids.md), [scenes.md](scenes.md), or [prefabs.md](prefabs.md) for narrower asset evidence. For an unresolved or ambiguous target, report the observed identifiers and recovery selector without choosing a replacement. For C# behavior, dependencies, class semantics, MonoBehaviour meaning, or script-type semantics, hand the question to [Source analyzer](../sub-skills/source-analyzer.md).
