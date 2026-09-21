# Project architecture guidelines

This guide gives a small default shape for new Mod-owned files. It is a placement decision, not a project template or a migration plan.

## Route decision

The Coding Standards router activates this guide when the Caller Mod repository lacks stable directory, namespace, module, or feature boundaries, or when the user explicitly asks how to organize new files or directories.

When a project already has stable or feature-oriented structure and the user has not asked for organization, the ordinary Mod task keeps its existing route and receives no unsolicited layout rewrite. When the user explicitly asks for organization, this guide activates for the decision, but the established structure still takes precedence.

The agent MUST report every architecture placement decision with this route-result contract:

| Field | Required result |
| --- | --- |
| Activation status | State `activated` for an unstructured repository or an explicit organization request; state `inactive` for ordinary work in an established architecture. |
| Activation reason | Explain the request signal that activated the guide, or why the established architecture kept the guide inactive. |
| Preserved boundary | Name the existing directory, namespace, module, or feature boundary that remains authoritative, or state that none was identified. |
| Primary responsibility | Name the one responsibility that determines placement; for an inactive route, state that the architecture guide did not assign it. |
| Suggested directory | Give the new directory or state that the established path is preserved. |
| Suggested namespace | Mirror the suggested directory by default, or name the established namespace exception. |

## Scope and precedence

This guide applies only to new files and directories in Mod-owned code. Decompiled game code, dependency code, upstream code, generated output, and build output remain outside the Caller Mod architecture boundary.

Existing directory, namespace, module, and feature boundaries take precedence. The guide MUST NOT move, rename, or restructure existing files. A new file MAY follow a role category only when doing so fits the existing structure.

Assign each new file by its primary responsibility. A file MAY contain tightly coupled supporting types, but independently meaningful responsibilities MUST be split into separate files. A file with one coherent responsibility SHOULD stay together.

New namespaces SHOULD mirror their directories by default. Existing namespace exceptions remain unchanged.

## Default shape

For a new project without established boundaries, the default role categories are:

    <ModRoot>/
        <entrypoint>.cs
        Components/
        Configs/
        Extensions/
        Patches/
        Events/
        Commands/

The project root is limited to entrypoints, startup orchestration, and project-level public types. The list is deliberately small; it is not a requirement to create every directory.

| Category | Primary responsibility | Placement boundary |
| --- | --- | --- |
| Components | Reusable Mod-owned runtime or domain objects, state, registries, and management components | A concrete component responsibility is required; Components is not a fallback for an unknown file. |
| Configs | User configuration, serialized settings, and persistence data models | New projects keep configuration and persistence models here even when an older reference project keeps one at the root. |
| Extensions | Extension methods and support types tightly coupled to those extensions | Generic utilities MUST NOT be placed here. |
| Patches | Harmony Patch files and Patch classes | Patches is the default Harmony category; a Harmony bridge that raises an event remains here because its primary mechanism is a patch. |
| Events | Event definitions, handlers, and subscription orchestration | Event consumers and event ownership belong here; the Patch bridge that emits an event remains in Patches. |
| Commands | Mod console command classes and command-specific behavior | Command concerns stay separate from general components and services. |

The guide MUST NOT prescribe generic Utils, Helpers, or Managers buckets. A new semantic category is justified only when a stable responsibility does not fit the existing categories; the proposal MUST name that responsibility and explain why the existing categories are insufficient.

## Existing naming and structure

Projects that already use HarmonyPatches MAY keep that name. A new project SHOULD use Patches by default. HarmonyPatches is justified for a project that genuinely separates multiple patch mechanisms; it is not a required rename target.

An established feature-oriented structure takes precedence over the role categories. The guide is additive: it helps place the next file and does not require cleanup of older exceptions.

## Non-binding examples

The following public repositories illustrate responsibility mappings only. They are not templates, and their source code MUST NOT be copied as an architecture requirement:

- [Blasphemous.LocalizationPatcher](https://github.com/EltonZhang777/Blasphemous.LocalizationPatcher) groups language patch objects under Components, console commands under Commands, event-side code under Events, and Harmony patch files under Patches. Its root Config.cs and L10NGlobalPersistenceData.cs are existing exceptions, not a reason to place new configuration or persistence models in the root.
- [Blasphemous.InventorySorting](https://github.com/EltonZhang777/Blasphemous.InventorySorting) illustrates Components, Configs, Events, Extensions, and an existing HarmonyPatches directory. Its Extensions/TraverseUtils.cs is a legacy example explicitly excluded from normative guidance; it does not make Extensions a generic utility bucket.

Agents MAY use these repositories to explain responsibility, but MUST NOT demand structural copying or migration. A project MAY preserve a different established layout.

## Placement procedure

For each new file:

1. Confirm that the file is Mod-owned and new.
2. Agent MUST record whether the project has stable or feature-oriented boundaries.
3. Agent MUST preserve those boundaries when they exist.
4. Identify one primary responsibility.
5. Agent MUST select the matching existing category or the smallest justified new semantic category.
6. Mirror the directory in the namespace unless the project already uses an exception.
7. Split only independently meaningful responsibilities.
8. Agent MUST report the route reason, preserved structure, responsibility, directory, and namespace.

Detailed C#, ModdingAPI, and Harmony behavior remains owned by the routed references in the Coding Standards router. This guide decides placement; it does not redefine naming, compiler compatibility, lifecycle behavior, patch target resolution, or patch discovery.
