# Coding standards router

## Entry and scope requirements

Before generating, modifying, reviewing, or refactoring Mod-owned C# in Caller Mod repository, agent MUST read this router and [Requirement levels](../requirement-levels-definitions.md). The router selects only branch references required by task.

This router applies only to code that Mod author can maintain in root of Caller Mod repository, including its source projects, `src/`, `Patches/`, and Mod-owned tests. It MUST NOT be applied to:

- Decompiled game source.
- Upstream Mods, dependency repositories, vendor code, or linked projects that caller cannot change.
- Generated output, build output, package caches, or other derived files.

When request directly copies code from excluded source, agent MUST preserve direct copy as-is. Mechanical namespace or path changes MAY be made when they are required for compilation. If copied code receives substantive new behavior or structural rewrite, new or changed code MUST follow selected standards.

## Route map

| Signal / condition | Destination | Boundary / next action |
| --- | --- | --- |
| New Mod-owned file or directory placement when the Caller Mod repository has no established boundaries, or an explicit request to organize or place new files or directories | [Project architecture guidelines](project-architecture-guidelines.md) | Agent MUST activate this guide only when either condition holds; established structure MUST take precedence. Agent MUST NOT move existing files and MUST report the boundary and proposed directory/namespace. |
| Mod-owned C# conventions, compiler compatibility, or runtime Unity callbacks | [C# and runtime Unity standards](../coding-standards/coding-standards-csharp-unity.md) | Agent MUST load this branch for every applicable Mod-owned C# task; caller compiler and referenced assemblies MUST govern compatibility. |
| ModdingAPI APIs, lifecycle, services, persistence, commands, or logging | [ModdingAPI standards](../coding-standards/coding-standards-moddingAPI.md) | Agent MUST route framework documentation/source through Referencing ModdingAPI; caller's referenced assembly MUST govern API facts. |
| Harmony targets, Patch files/classes, injections, or manual patching | [Harmony patching standards](../coding-standards/coding-standards-harmony-patching.md) | Applicable C# tasks MUST also load the C# branch; ModdingAPI remains the single authority for framework discovery, and manual `Harmony.Patch` MUST follow its approval gate. |
| Decompiled, upstream, dependency/vendor, unmodifiable linked, generated, build, cached, derived, or directly copied code | Scope gate | Agent MUST preserve excluded or copied source; namespace/path-only changes MAY be made when needed. Substantive Mod-owned changes MUST follow the applicable branch. |

## Coding specifications

- Mod language is C#.
- Supported game baseline is Unity `2017.4.40f1`.
- Caller's actual compiler, referenced assemblies, and project target MUST take precedence over general language or Unity baseline.
- Agent MAY consult [Unity 2017.4 Script Reference](https://docs.unity3d.com/2017.4/Documentation/ScriptReference/30_search.html) when runtime Unity fact needs verification.
- ModdingAPI-specific behavior MUST be checked against caller's referenced ModdingAPI assembly and corresponding source or documentation. ModdingAPI tasks route to [ModdingAPI standards](../coding-standards/coding-standards-moddingAPI.md); Harmony tasks route to the [Harmony patching standards](../coding-standards/coding-standards-harmony-patching.md).

## C# and runtime Unity scope

C# task includes generating, modifying, reviewing, or refactoring Mod-owned C#; it also includes runtime `MonoBehaviour` work even when request is described as Unity task. For every applicable C# task, agent MUST read [C# and runtime Unity standards](../coding-standards/coding-standards-csharp-unity.md).

C# and runtime Unity reference MUST be loaded for every applicable Mod-owned C# task, including task that also requires later ModdingAPI or Harmony branch. Agent MUST NOT use this route to impose UnityEditor, Inspector, Prefab, ScriptableObject, or serialization rules on Mod that has no UnityEditor relationship.

## Routing examples

Good:

```text
Request: rename a Mod-owned controller and review its Update callback.
Route: this router → coding-standards-csharp-unity.md
```

Excluded:

```text
Request: reformat a decompiled Assembly-CSharp class copied for reference.
Route: scope gate; preserve the external source and do not load the Mod-owned C# branch.
```

Harmony branch MUST preserve this scope gate and requirement-level contract as its target and resolver rules evolve.

## Completion criterion

Agent MUST report the selected coding branch, ownership and scope decision,
standards evidence, status, the blocked reason when applicable, and the next
implementation or verification action. A coding request is complete only when
the selected standards reference has been applied or the exact blocking scope
condition has been reported.

## Route project architecture requests

For a request about placing a new Mod-owned file or directory, the router MUST activate [Project architecture guidelines](project-architecture-guidelines.md) when either condition holds:

- The Caller Mod repository has no established directory, namespace, module, or feature boundaries.
- The user explicitly asks how to organize or place new files or directories.

For an ordinary request in a project with established or feature-oriented structure, the router MUST NOT impose the default role categories. An explicit organization request still activates the guide, but the existing structure takes precedence.

The architecture guide is soft guidance for new files. It MUST NOT move, rename, or restructure existing files, and it MUST NOT replace the detailed C#, ModdingAPI, or Harmony references selected elsewhere in this router. The route result MUST explain whether it activated, which existing-structure boundary applied, and which primary responsibility determined the placement.
