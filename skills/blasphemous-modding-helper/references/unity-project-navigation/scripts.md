# Script asset navigation

The `script` query resolves one exported `.cs` script asset by exact path, GUID, or exact name. It reports asset identity and metadata only. It does not parse C# or establish behavior, dependencies, or class semantics. It never opens Unity Editor or changes the export.

## Command

Every query MUST provide `--project` and exactly one selector:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" script --project "<UNITY_PROJECT_ROOT>" --path "<SCRIPT_PATH>"
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" script --project "<UNITY_PROJECT_ROOT>" --guid "<SCRIPT_GUID>"
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" script --project "<UNITY_PROJECT_ROOT>" --name "<SCRIPT_NAME_OR_STEM>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') script --project '<UNITY_PROJECT_ROOT>' --path '<SCRIPT_PATH>'
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') script --project '<UNITY_PROJECT_ROOT>' --guid '<SCRIPT_GUID>'
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') script --project '<UNITY_PROJECT_ROOT>' --name '<SCRIPT_NAME_OR_STEM>'
```

`--path` is an exact project-relative or in-project absolute `.cs` path. `--guid` is an exact 32-character hexadecimal GUID. `--name` is a case-insensitive exact basename or extensionless stem; it is not a substring search and MUST NOT contain a path separator.

## Result

The version-1 envelope uses the common `schema_version`, `command`, `status`, `project`, `query`, `results`, `limits`, `truncated`, `warnings`, and `error` fields. The `limits` object reports `csharp_parsed: false`.

Each result contains only:

- `path`: the normalized project-relative script path.
- `type`: the lowercase file type, normally `cs`.
- `name`: the filename observed at that path.
- `guid`: the lowercase sibling `.meta` GUID, or `null`.
- `metadata`: the expected `.meta` path, metadata status, and parsed `fileFormatVersion`.
- `status`: the identity result status.

The query MUST NOT add class names, members, dependencies, call sites, decompiled code, or inferred runtime meaning.

## Failures and warnings

- `ok` means the selector resolved one script asset. Exit code `0`.
- `ambiguous` means more than one script identity matches, or a GUID also identifies a non-script asset. Exit code `2`. Every candidate is returned; the agent MUST NOT select one silently.
- `not_found` means a valid selector has no matching script asset. Exit code `2`.
- `invalid_query` means a selector is malformed, names a non-script path, traverses outside the included roots, or contains a link that is not followed. Exit code `3`.
- `invalid_project` means the configured root or required `Assets` structure is unusable. Exit code `3`.

`metadata_missing` and `metadata_unusable` make an incomplete `.meta` explicit without fabricating a GUID. `duplicate_guid` identifies shared GUID metadata. `ambiguous_script`, `ambiguous_script_guid`, `not_cs_script`, and `script_not_found` identify candidate, selector, and target failures with stable codes. For a duplicated GUID that crosses script and non-script assets, the result keeps all observed identities ambiguous so the agent MUST NOT silently treat the GUID as a unique script reference.

## Evidence boundary

A Unity `.cs` result proves only that the exported project contains that script path and its observed metadata. It is not proof of C# behavior, dependencies, class semantics, runtime execution, or gameplay.

Behavior, dependency, and class-semantic requests MUST be routed to the [Source analyzer](../sub-skills/source-analyzer.md), which resolves the configured authoritative source tree through [Blasphemous Source Code Navigation](../source-code-navigation/MAIN.md). If that authoritative source cannot support the request, the agent MUST report the source gap as `blocked` and MUST NOT fall back to the Unity `.cs` file. When a task spans script identity and behavior, report the two evidence sets separately.

## Next action

After an `ok` result, cite the resolved path, name, GUID, metadata status, and the `csharp_parsed: false` limit. For ambiguity, present every sorted candidate and request one script identity. For a missing or malformed target, verify the selector and project root or report the malformed metadata. For behavior, hand the request to the source analyzer, or report `blocked` when authoritative source coverage is unavailable.

## Completion criteria

Script navigation is complete only when the selector, project root, resolved script identity, GUID and metadata status, ambiguity or warnings, evidence limit, and next asset or source action are reported. Read-only execution MUST leave the project unchanged. A query is not complete when it silently selects among candidates, claims C# behavior from asset evidence, or hides an unavailable authoritative source behind a Unity fallback.
