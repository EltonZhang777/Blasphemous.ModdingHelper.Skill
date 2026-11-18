# Scene navigation

The `scene` query resolves one logical scene set or one exact `.unity` file and reports serialized evidence from the files that are present. It never opens Unity Editor or changes the project.

## Command

The query accepts exactly one selector:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" scene --project "<UNITY_PROJECT_ROOT>" --name "<SCENE_NAME_OR_STEM>"
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" scene --project "<UNITY_PROJECT_ROOT>" --path "<SCENE_PATH>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') scene --project '<UNITY_PROJECT_ROOT>' --name '<SCENE_NAME_OR_STEM>'
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') scene --project '<UNITY_PROJECT_ROOT>' --path '<SCENE_PATH>'
```

`--name` is case-insensitive exact matching against the logical stem, member stem, or filename. It is not a substring or fuzzy search. `--path` is an exact project-relative or in-project absolute path. The agent MUST use `--path` when the request names a specific scene file.

## Scene-set contract

A scene set consists only of `.unity` files in one directory with one shared logical stem and the exact suffixes `_MAIN`, `_LOGIC`, `_LAYOUT`, `_DECO`, and `_AUDIO`.

- `complete` means all five recognized layers are present.
- `incomplete` means at least one recognized layer is present and at least one is absent.
- `standalone` means the file has no recognized layer suffix.

The result lists `present_layers` and `missing_layers` from actual filenames. The scanner MUST NOT synthesize a missing path. A direct path query returns evidence for that exact file and MAY additionally identify its same-directory set membership.

## Result

The version-1 envelope uses the common `schema_version`, `command`, `status`, `project`, `query`, `results`, `limits`, `truncated`, `warnings`, and `error` fields. Each scene result contains:

- `logical_name`, `directory`, and `kind`.
- `present_layers`, `missing_layers`, and the observed `members`.
- `requested_path` for a direct-path query, otherwise `null`.
- `object_count` and `reference_count` for parsed evidence.
- `evidence` entries for the exact requested file or every present member of a named set.

Each evidence entry contains `path`, `status`, `layer`, object and reference counts, and `objects`. Each object contains the serialized `file_id`, `class_id`, top-level `class_name`, observed `m_Name`, `component_file_ids`, `container_file_id`, and serialized `references`.

Each reference contains:

- `field`, `file_id`, `guid`, `type`, and source `line`.
- `scope`: `local` for a file-local `fileID`, `external` when a GUID is present, or `null` for `fileID: 0`.

Object and local file IDs are scoped to one evidence file. The same numeric ID in two scene layers is not one object. A GUID is observed text only; this query does not resolve it to an asset path, script type, or C# behavior.

## Failures and warnings

- `not_found` and `ambiguous` use exit code `2` and return no fabricated evidence.
- `invalid_query`, `invalid_project`, and `unsupported_format` use exit code `3`.
- `incomplete_scene_set`, `ambiguous_scene_name`, `scene_not_found`, `excluded_path`, `malformed_document`, and link warnings identify actionable conditions with stable codes.

An excluded directory, path outside the project, path traversal, unsupported selector, linked scene path, or malformed direct target MUST return structured non-success. A malformed member of a named set keeps its parse error visible in `evidence`; it MUST NOT be presented as complete object evidence.

## Evidence limits

The exported scene is authoritative only for observed serialized objects and references. Class IDs and top-level class containers are serialization evidence, not proof of C# type behavior, runtime execution, component semantics, or gameplay state. Missing or ambiguous evidence MUST remain missing or ambiguous.

The agent MUST use [topology.md](topology.md) for project-wide counts and [Source analyzer](../sub-skills/source-analyzer.md) for C# behavior, dependencies, and runtime call flow. The agent MUST use the resolved member path as the next asset-navigation step or hand the behavior question to the source authority.

## Completion criteria

Scene navigation is complete only when the selector, exact scene or set, completeness, present and missing layers, observed evidence paths, warnings, and next asset or source action are reported. Read-only execution MUST leave the project unchanged. The next action is to select the required member path, report a missing layer, or hand a behavior question to the source authority.
