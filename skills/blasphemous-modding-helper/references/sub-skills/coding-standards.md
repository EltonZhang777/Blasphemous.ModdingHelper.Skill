# Coding standards router

## Coding specifications

Before generating, modifying, reviewing, or refactoring Mod-owned C# in the Caller Mod repository, the agent MUST read this router and [Requirement levels](../requirement-levels-definitions.md). The router selects only the branch references required by the task.

- The Mod language is C#.
- The supported game baseline is Unity `2017.4.40f1`.
- The caller's actual compiler, referenced assemblies, and project target MUST take precedence over a general language or Unity baseline.
- The agent MAY consult the [Unity 2017.4 Script Reference](https://docs.unity3d.com/2017.4/Documentation/ScriptReference/30_search.html) when a runtime Unity fact needs verification.
- ModdingAPI-specific behavior MUST be checked against the caller's referenced ModdingAPI assembly and corresponding source or documentation. ModdingAPI tasks route to the [ModdingAPI standards](../coding-standards-moddingAPI.md); Harmony tasks route to the [Harmony patching standards](../coding-standards-harmony-patching.md).

## Scope gate

This router applies only to code that the Mod author can maintain in the root of the Caller Mod repository, including its source projects, `src/`, `Patches/`, and Mod-owned tests. It MUST NOT be applied to:

- Decompiled game source.
- Upstream Mods, dependency repositories, vendor code, or linked projects that the caller cannot change.
- Generated output, build output, package caches, or other derived files.

When a request directly copies code from an excluded source, the agent MUST preserve the direct copy as-is. Mechanical namespace or path changes MAY be made when they are required for compilation. If the copied code receives substantive new behavior or a structural rewrite, the new or changed code MUST follow the selected standards.

## Route C# and runtime Unity tasks

A C# task includes generating, modifying, reviewing, or refactoring Mod-owned C#; it also includes runtime `MonoBehaviour` work even when the request is described as a Unity task. For every applicable C# task, the agent MUST read [C# and runtime Unity standards](../coding-standards-csharp-unity.md).

| Task signal | Required reference |
| --- | --- |
| Mod-owned C# naming, file/type/member organization, compiler compatibility, or runtime Unity callbacks | [C# and runtime Unity standards](../coding-standards-csharp-unity.md) |
| ModdingAPI API or setup, `BlasMod`, `ModLog`, `ModServiceProvider`, ConfigHandler, FileHandler, InputHandler, LocalizationHandler, persistence, console/commands, items, levels, penitences, or other service-integration behavior | [ModdingAPI standards](../coding-standards-moddingAPI.md) |
| Harmony or Patch behavior, including target declarations, Patch files, Patch classes, or manual patching | [Harmony patching standards](../coding-standards-harmony-patching.md) |
| Decompiled, upstream, dependency, generated, or directly copied code in the excluded scope | No Mod-owned C# branch; preserve the excluded or copied code under the scope gate |

The C# and runtime Unity reference MUST be loaded for every applicable Mod-owned C# task, including a task that also requires a later ModdingAPI or Harmony branch. The agent MUST NOT use this route to impose UnityEditor, Inspector, Prefab, ScriptableObject, or serialization rules on a Mod that has no UnityEditor relationship.

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

The Harmony branch MUST preserve this scope gate and requirement-level contract as its target and resolver rules evolve.
