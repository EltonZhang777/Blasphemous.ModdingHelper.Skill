# Assets and GUIDs

The `asset` query resolves one exported file or folder by exact project-relative path, exact GUID, or exact name or extensionless stem. It reads project evidence without opening Unity Editor or changing the export.

## Selectors

Every query MUST provide `--project` and exactly one of `--path`, `--guid`, or `--name`:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" asset --project "<UNITY_PROJECT_ROOT>" --path "Assets/Prefabs/Example.prefab"
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" asset --project "<UNITY_PROJECT_ROOT>" --guid 0123456789abcdef0123456789abcdef
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" asset --project "<UNITY_PROJECT_ROOT>" --name Example
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') asset --project '<UNITY_PROJECT_ROOT>' --path 'Assets/Prefabs/Example.prefab'
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') asset --project '<UNITY_PROJECT_ROOT>' --guid 0123456789abcdef0123456789abcdef
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') asset --project '<UNITY_PROJECT_ROOT>' --name Example
```

- `--path` accepts a project-relative path under `Assets` or a physical `Packages` root. Slash direction, `.` segments, and repeated separators are normalized. An absolute path is accepted only when it resolves inside the project. Parent traversal, excluded directories, links, and paths outside the included roots are rejected rather than guessed.
- `--guid` accepts exactly 32 hexadecimal characters. Matching is case-insensitive, and the result reports the lowercase GUID. Both file and folder metadata are resolved.
- `--name` performs a case-insensitive exact match against a basename or extensionless stem. It is not a substring or fuzzy search, and it MUST NOT contain a path separator.

## Result interpretation

The version-1 envelope contains `schema_version`, `command`, `status`, `project`, `query`, `results`, `limits`, `truncated`, `warnings`, and `error`.

- `ok` means the query resolved uniquely. Exit code `0`.
- `ambiguous` means more than one candidate has the requested identity. Exit code `2`. Every candidate is returned in deterministic project-relative path, type, and GUID order; the agent MUST NOT choose one silently.
- `not_found` means a valid query has no matching path, GUID, or name. Exit code `2`.
- `invalid_query` means the selector is malformed, traverses outside the included roots, names an excluded path, or contains a link that is not followed. Exit code `3`.
- `invalid_project` means the configured root or required `Assets` structure is unusable. Exit code `3`.

Each result reports:

- `path`: normalized project-relative path with forward slashes.
- `type`: the lowercase file extension without a dot, `folder` for a directory, or `file` for an extensionless file.
- `guid`: the lowercase sibling `.meta` GUID, or `null`.
- `metadata`: the expected sibling `.meta` path, metadata status, and parsed `fileFormatVersion` when present.

`metadata.status` is `present`, `missing`, `unusable`, or `duplicate`. A missing or malformed `.meta` does not prevent an exact path lookup from returning the observed file; the result instead carries `metadata_missing` or `metadata_unusable`. Duplicate GUIDs carry `duplicate_guid` and remain ambiguous for a GUID query.

## Evidence limits

Binary assets are reported only by path, GUID, type, and metadata evidence. Their bytes, dimensions, channels, audio samples, meshes, and other content MUST NOT be described as inspected or understood. A `binary_not_inspected` warning makes that limit explicit. Other asset types are also not parsed for content by this query.

The asset query establishes identity and location only. It MUST NOT be used as proof of C# behavior, runtime state, serialized component relationships, or gameplay. Behavior questions remain owned by the [Source analyzer](../sub-skills/source-analyzer.md), even when a Unity `.cs` asset has the same path.

When the requested identity is specifically a `.cs` script asset, use [scripts.md](scripts.md). That query applies the same identity contract without parsing C#.

## Next action

After an `ok` result, cite the project-relative path, type, GUID, and metadata status, then select the narrowest topic needed for the next question. For ambiguity, present the sorted candidates and ask for one identity; the agent MUST NOT infer the intended asset. For a missing identity, verify the selector and project root before trying another query. For binary evidence, continue with metadata or topology only; the agent MUST NOT inspect or reserialize the asset. For behavior, hand the request to the source analyzer.

## Completion criteria

Asset lookup work is complete only when the selected query, project root, status, evidence paths, GUID and metadata status, ambiguity, binary limit, warnings, and next action are reported. A query is not complete when it silently selects among candidates, claims unavailable metadata, or treats asset identity as behavioral proof.
