# Prefab navigation

The `prefab` query resolves one exported `.prefab` and reports the flattened serialized objects and components that are present. It never opens Unity Editor or changes the export.

## Command

The query accepts exactly one selector:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" prefab --project "<UNITY_PROJECT_ROOT>" --path "<PREFAB_PATH>"
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" prefab --project "<UNITY_PROJECT_ROOT>" --guid "<PREFAB_GUID>"
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" prefab --project "<UNITY_PROJECT_ROOT>" --name "<PREFAB_NAME_OR_STEM>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') prefab --project '<UNITY_PROJECT_ROOT>' --path '<PREFAB_PATH>'
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') prefab --project '<UNITY_PROJECT_ROOT>' --guid '<PREFAB_GUID>'
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') prefab --project '<UNITY_PROJECT_ROOT>' --name '<PREFAB_NAME_OR_STEM>'
```

`--path` is an exact project-relative or in-project absolute `.prefab` path. `--guid` is an exact 32-character hexadecimal GUID. `--name` is a case-insensitive exact basename or extensionless stem and is not a substring search.

## Flattened evidence

The UTinyRipper export provides flattened Prefab documents. Each successful result reports `evidence_kind: "flattened"` and the envelope `limits` report `source_prefab_hierarchy: "not_available"`.

A result contains the resolved `path`, `type`, `guid`, and `metadata`, followed by the observed `object_count`, `reference_count`, and `objects`. Each object contains the serialized `file_id`, `class_id`, top-level `class_name`, observed `m_Name`, `component_file_ids`, `container_file_id`, and serialized `references`.

The flattened evidence is authoritative only for objects that exist in the `.prefab` file. The query MUST NOT reconstruct or infer the original Prefab-instance hierarchy, nested object ownership, variants, or modification records. It MUST NOT treat a flattened object as proof that an object originated from a particular nested Prefab.

## Failures and warnings

- `not_found` and `ambiguous` use exit code `2`.
- `invalid_query`, `invalid_project`, and `unsupported_format` use exit code `3`.
- `prefab_not_found`, `ambiguous_prefab`, `not_prefab`, metadata warnings, and serialized-parse warnings identify actionable conditions with stable codes.

A non-Prefab path, missing target, duplicate name or GUID, malformed serialized target, excluded path, or linked path MUST return structured non-success or warning evidence. A malformed Prefab MUST keep its error visible and MUST NOT expose fabricated objects.

## Evidence limits

Class IDs, observed names, component containers, and references describe serialized export content only. They are not C# behavior, runtime execution, dependency, or gameplay evidence. Behavior questions remain owned by the [Source analyzer](../sub-skills/source-analyzer.md).

## Next action

After a successful query, cite the resolved path and GUID, the flattened limitation, the observed object and reference counts, and the relevant object IDs. For a missing or ambiguous target, present the candidates or verified selector and request one identity. For behavior, route the request to the source analyzer without using Unity `.cs` files as proof.

## Completion criteria

Prefab navigation is complete only when the selector, resolved path, flattened evidence status, observed objects and references, warnings, ambiguity, and next asset or source action are reported. Read-only execution MUST leave the project unchanged.
