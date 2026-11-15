# Unity Project Navigation Guide

This guide provides read-only navigation for an exported Blasphemous Unity project and applies only after completing [Unity project navigation](../sub-skills/unity-project-navigation.md).

## Navigation Routes

| Request signal | Route destination | Evidence boundary / next action |
| --- | --- | --- |
| Project topology, Unity version, included roots, file counts, or scene-set summary | [topology.md](topology.md) | Agent MUST inspect the exported project summary and report any version, completeness, or unreadable-path warning before a narrower lookup. |

## Evidence boundary

The Unity export is authoritative for exported asset topology and serialized evidence only. The configured source tree remains authoritative for C# behavior, dependencies, and class semantics through [Source analyzer](../sub-skills/source-analyzer.md) and [Blasphemous Source Code Navigation](../source-code-navigation/MAIN.md).

Agent MUST NOT use Unity `.cs` files as behavioral proof. Asset evidence and source evidence MUST be reported separately when one request spans both.

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
