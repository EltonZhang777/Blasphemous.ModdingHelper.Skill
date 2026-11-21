# Unity Project Navigation Guide

This guide provides read-only navigation for an exported Blasphemous Unity project and applies only after completing [Unity project navigation](../sub-skills/unity-project-navigation.md).

## Navigation Routes

| Request signal | Route destination | Evidence boundary / next action |
| --- | --- | --- |
| Project topology, Unity version, included roots, file counts, or scene-set summary | [topology.md](topology.md) | Agent MUST inspect the exported project summary and report any version, completeness, or unreadable-path warning before a narrower lookup. |
| Exact asset path, GUID, name, or extensionless stem | [assets-and-guids.md](assets-and-guids.md) | Agent MUST report the resolved project-relative evidence, metadata status, ambiguity, and the binary-content limit before selecting a next action. |
| Script asset path, GUID, or exact name | [scripts.md](scripts.md) | Agent MUST return script asset identity and metadata only. Agent MUST NOT parse C#, infer behavior, dependencies, or class semantics, and MUST report a source gap as `blocked` when authoritative source is unavailable. |
| Scene-set membership or serialized scene-object evidence | [scenes.md](scenes.md) | Agent MUST report completeness, missing layers, observed evidence limits, and any malformed, ambiguous, or excluded target. |
| Flattened Prefab objects or components | [prefabs.md](prefabs.md) | Agent MUST identify the evidence as flattened and MUST NOT infer source instance hierarchy, nesting, variant, or modification structure. |
| Serialized component relations, GUID edges, cycles, or incoming references | [component-relations.md](component-relations.md) | Agent MUST report traversal direction, object scope, unresolved targets, cycles, truncation, and timeout before selecting a next action. |
| Direct MonoBehaviour `m_Script` bindings | [bindings.md](bindings.md) | Agent MUST report source and target evidence separately and hand behavior questions to the source analyzer. |

## Evidence boundary

The Unity export is authoritative for exported asset topology and serialized evidence only. The configured source tree remains authoritative for C# behavior, dependencies, and class semantics through [Source analyzer](../sub-skills/source-analyzer.md) and [Blasphemous Source Code Navigation](../source-code-navigation/MAIN.md).

Script identity from [scripts.md](scripts.md) is asset placement evidence only. Agent MUST NOT use Unity `.cs` files as behavioral proof. Asset evidence and source evidence MUST be reported separately when one request spans both.

## Version-1 document envelope

Every Unity project-navigation query returns one JSON object. The public `schema_version` value is `1`.

The common top-level fields, in order, are `schema_version`, `command`, `status`, `project`, `query`, `results`, `limits`, `truncated`, `warnings`, and `error`. This roster defines common field ownership and ordering only; it does not add type, requiredness, or nullability rules. A query may add command-specific top-level fields around this common envelope.

The roster order is documentation order only; it does not describe the serialized JSON key order.

## First query

The first query is the read-only project summary:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/unity_project_navigation.py" project --project "<UNITY_PROJECT_ROOT>"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\unity_project_navigation.py') project --project '<UNITY_PROJECT_ROOT>'
```

The JSON envelope uses the project-relative paths, warnings, and incompleteness fields described by the selected topic. The scanner does not read `config.yml`; the agent MUST resolve and pass the configured root explicitly.

## Completion criteria

Navigation-index work is complete only when the narrowest topic is selected, the exact query and project root are reported, and the next action identifies the required topic, source behavior owner, or recovery step.
