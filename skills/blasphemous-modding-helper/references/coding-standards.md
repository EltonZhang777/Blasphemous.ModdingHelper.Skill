# C# and Modding Standards

This is the local coding standard for Mod-owned C# in a caller's Blasphemous Mod repository. Read it before generating or modifying Mod code. It is a style and workflow contract for the AI assistant; it is not a replacement for the caller's source tree, the referenced assemblies, or upstream API documentation.

## Scope and rule levels

These rules apply only to code that the Mod author can maintain in the root of the caller's Mod repository, including its own source projects, `src/`, `Patches/`, and Mod-owned tests. They do not apply to:

- Decompiled game source.
- Upstream Mods, dependency repositories, vendor code, or linked projects that the caller cannot change.
- Generated output, build output, package caches, or other derived files.

When a request directly copies code from an excluded source, preserve the copied code as-is. Mechanical namespace or path changes needed to compile it still count as a direct copy. If the code receives substantive new behavior or a structural rewrite, the new or changed code follows this standard.

Use [Requirement levels](requirement-levels-definitions.md) as the single source of truth for RFC 2119 keywords and exception handling. Do not reformat unrelated legacy code merely to make it comply; apply the standard when the code is touched.

## Authority and versioning

Use the narrowest authoritative source for the question at hand:

1. The ModdingAPI, Harmony, Unity, and game assemblies actually referenced by the caller's Mod, including their source when available.
2. The corresponding upstream documentation and examples:
   - [Blasphemous ModdingAPI development documentation](https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/main/docs/development/main.md)
   - [`BlasMod` documentation](https://raw.githubusercontent.com/BrandenEK/Blasphemous.ModdingAPI/main/docs/development/mod.md)
   - [ModdingAPI order of execution](https://raw.githubusercontent.com/BrandenEK/Blasphemous.ModdingAPI/main/docs/development/execution.md)
   - [Blasphemous ModdingAPI source](https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/main)
   - [Harmony patching documentation](https://harmony.pardeike.net/articles/patching.html)
   - [Unity 2017.4 Script Reference](https://docs.unity3d.com/2017.4/Documentation/ScriptReference/30_search.html)
3. This document for local naming, organization, and workflow conventions.
4. [`SKILL.md`](../SKILL.md) for the skill workflow and preference gate.

Local style rules may be stricter than upstream style, but they must not contradict an API signature or runtime requirement. If the upstream documentation and the referenced assembly disagree, inspect the actual referenced version before writing code. In particular, the current execution-order document mentions `OnPreInitialize` while the current Mod class page does not list it; treat that callback as version-gated and do not invent an override that the caller's `BlasMod` does not expose.

The current API documentation uses `BlasMod` and `On...` callbacks. Older `Mod`, `PersistentMod`, `Initialize`, or `Dispose` examples are legacy references and are not the default template for new code.

## C# baseline

The baseline follows conventional C# naming, adapted to Blasphemous ModdingAPI code targeting Unity `2017.4.40f1` and the caller's actual compiler target.

### Naming

- Namespaces, classes, structs, records where supported, interfaces, enums, methods, properties, events, and enum members use `PascalCase`.
- Interfaces begin with `I`; type parameters begin with `T` when a type-parameter name is needed.
- Constants use `PascalCase`, for example `ModId` or `DefaultDamage`.
- Parameters and local variables use `camelCase`.
- Private instance fields use `_camelCase`; do not introduce the `m_` convention.
- Public fields are not a substitute for a public API. Prefer a property or method when the value is part of the Mod's surface.
- Avoid unexplained abbreviations. Keep names aligned with the target game's or ModdingAPI's established public names when referring to them.

### Files, types, and members

For ordinary source files:

- Keep the file name aligned with its primary top-level type.
- Prefer one main top-level type per file.
- Keep namespaces aligned with the Mod project structure.
- Keep implementation details private or internal; expose only the API the Mod or another Mod actually needs.
- Organize members in a stable order: constants, static state, instance state, properties/events, constructors, lifecycle callbacks, public API, then private helpers.

Patch aggregation files are the deliberate exception to the one-type-per-file preference; see [Harmony patching standards](coding-standards-harmony-patching.md).

Target the language and framework level supported by the caller's project and Unity `2017.4.40f1`. Do not introduce newer syntax, BCL APIs, or Unity APIs without checking that the actual project references support them.

## Runtime Unity components

This standard does not cover UnityEditor, Inspector workflows, Prefabs, ScriptableObjects, or Unity serialization. The caller's Mod does not have a UnityEditor relationship, so `[SerializeField]` and serialized-field naming are outside this document.

When a Mod creates or attaches a `MonoBehaviour` at runtime, use Unity callbacks for that component only:

| Callback | Use it for | Avoid putting here |
| --- | --- | --- |
| `Awake` | The component's own references and local invariants | Assumptions about unrelated objects already being ready |
| `OnEnable` | Work that must happen whenever the component becomes enabled | One-time global initialization |
| `Start` | Initialization that depends on other scene/runtime objects | Work that must run before other components' `Start` callbacks |
| `Update` | Per-frame work that is genuinely required | Polling that can be event-driven or expensive work every frame |
| `LateUpdate` | Per-frame work that must follow normal updates | General initialization |
| `OnDisable` | Per-enable cleanup and subscription symmetry | Permanent Mod shutdown policy |
| `OnDestroy` | Component-local finalization | Assuming the whole Mod process is shutting down |

Do not use a `MonoBehaviour` constructor for Unity runtime initialization. Keep the Mod's own startup and game-session logic in the `BlasMod` lifecycle below.

## `BlasMod` lifecycle

The authoritative lifecycle table, callback responsibilities, version gating, shutdown behavior, and override rules live in [ModdingAPI standards](coding-standards-moddingAPI.md). ModdingAPI lifecycle tasks MUST read that branch. This legacy heading remains as a compatibility anchor; it MUST NOT be treated as a second lifecycle authority.

## Logging

The authoritative ModdingAPI and ModLog rules now live in [ModdingAPI standards](coding-standards-moddingAPI.md). ModdingAPI-related tasks MUST read that branch; the remaining material in this legacy aggregate is retained only for migration compatibility.

## Harmony patches

The authoritative Harmony rules now live in [Harmony patching standards](coding-standards-harmony-patching.md). Harmony-related tasks MUST read that branch; this legacy heading remains a compatibility anchor and MUST NOT be treated as a second Harmony authority.
