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

Patch aggregation files are the deliberate exception to the one-type-per-file preference; see [Harmony patches](#harmony-patches).

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

The current ModdingAPI base class is `BlasMod`. Read the actual referenced `BlasMod` version before overriding methods. The documented lifecycle surface is:

| Method | Timing and intended responsibility |
| --- | --- |
| `OnPreInitialize()` | Pre-manager initialization work that is safe before normal manager startup. Include it only when the referenced API exposes it. |
| `OnInitialize()` | Mod-local initialization and registration after the normal initialization stage. |
| `OnRegisterServices(ModServiceProvider provider)` | Registration of services through the ModdingAPI service provider. Keep ordinary gameplay logic elsewhere. |
| `OnAllInitialized()` | Work that depends on all Mods and managers completing initialization. |
| `OnUpdate()` | Per-frame Mod logic after initialization. Use only for work that cannot be event-driven. |
| `OnLateUpdate()` | Per-frame logic that must run after normal updates. |
| `OnLevelPreloaded(string oldLevel, string newLevel)` | Work immediately before a new level, including the main menu, is loaded. |
| `OnLevelLoaded(string oldLevel, string newLevel)` | Work after a new level, including the main menu, is loaded and its runtime objects can be located. |
| `OnLevelUnloaded(string oldLevel, string newLevel)` | Work when the old level, including the main menu, is unloaded. |
| `OnNewGame()` | Work after data is reset while starting a new game from the main menu. |
| `OnLoadGame()` | Work after data is reset while loading an existing game from the main menu. |
| `OnExitGame()` | Work after quitting the current game and returning to the main menu. |
| `OnDispose()` | Final game-shutdown callback. This standard does not require boilerplate resource or subscription cleanup solely because this callback exists. |

The documented startup order is `OnPreInitialize` (when exposed) → manager initialization → `OnInitialize` → `OnRegisterServices` → all managers initialized → `OnAllInitialized`. Level and save callbacks occur at their corresponding game events, and `OnDispose` occurs during final shutdown.

Do not generate empty overrides for callbacks the Mod does not use. Do not move one-time initialization into `OnUpdate`, access scene objects before the relevant level callback, or use `OnInitialize` for work that requires every other Mod to be ready. Only call `base.X()` when the actual referenced API implementation or documentation requires it; the style standard does not add unconditional base calls.

A full lifecycle outline is useful as a reference, but the `OnPreInitialize` method must be removed from the generated code when the caller's API version does not expose it.

The method accessibility in a generated Mod must match the actual referenced API. The outline uses the common cross-assembly `protected override` form; if the caller's API requires a different legal override declaration, follow that signature.

## Logging

### Pre-approved debug and temporary logging exception

A logging-only exception for debugging logging functionality is pre-approved and MAY be used without a separate per-use user confirmation when every condition below is met:

- A debug-only statement MUST be excluded from Release by `#if DEBUG` or another compile-time condition supported by the caller's project, so the Release build is unaffected; or
- A temporary statement MUST be marked with `[DEBUG]`, `[DIAG]`, or an explicit comment that identifies its temporary use, and MUST be removed after testing.

The qualifying statement MUST be for debugging logging functionality. It MUST still use a severity appropriate to the event and provide useful Mod and operation context. It MAY omit other logging guidance, such as ordinary frequency or user-facing-display rules, only for the qualifying debug or temporary statement. This exception MUST NOT waive non-logging coding, API, lifecycle, or patching rules.

If a logging statement does not satisfy every condition above, the normal exception-handling process applies and the agent MUST ask the user before deviating from a local rule.

## Harmony patches

### Patch ownership and discovery

ModdingAPI owns discovery and application of Harmony patches during the Mod initialization flow. A Mod declares Patch classes; it does not create a second assembly-scanning lifecycle.

**MUST NOT** call any of the following for the Mod's own assembly:

```csharp
new Harmony("my.mod").PatchAll();
new Harmony("my.mod").PatchAll(Assembly.GetExecutingAssembly());
Harmony.CreateAndPatchAll(Assembly.GetExecutingAssembly());
```

Do not add a manual `PatchAll` call to `OnInitialize`, `OnAllInitialized`, `OnRegisterServices`, a Unity callback, or a plugin entry point. A manual `Harmony.Patch` operation is an exception only when automatic discovery cannot express the required timing, condition, external target, or exact selection. Stop and ask the user before writing such an exception; do not silently choose it.

### Patch files and classes

Put new Patch files under the Mod root's `Patches/` directory:

- Group by target type with `<TypeName>Patches.cs`, for example `DamageNumberPatches.cs`.
- Group a coherent cross-type feature with `<Functionality>Patches.cs`, for example `CriticalHitPatches.cs`.
- A file may contain multiple related Patch classes.
- Keep unrelated targets and unrelated features in separate files.

Each Patch class follows:

```csharp
[HarmonyPatch(typeof(TargetType), "TargetMethod")]
internal static class TargetType_DescribeBehavior_Patch
{
    [HarmonyPrefix]
    private static void Prefix() { }
}
```

The class name is based on the target type's simple name and the functionality being changed: `<ClassName>_<FunctionalityDescription>_Patch`. The file name is the aggregation name, not the Patch class name, so a file such as `TargetTypePatches.cs` can contain `TargetType_FirstBehavior_Patch` and `TargetType_SecondBehavior_Patch`.

Keep one Patch class focused on one target method and one coherent behavior. It may contain that target's Prefix, Postfix, Transpiler, and/or Finalizer, but it must not become a general-purpose utility container.

### Target declarations

Use a direct string for the target method name. This is intentional: the target may be `private` and therefore unavailable to `nameof(TargetType.TargetMethod)`.

```csharp
[HarmonyPatch(typeof(TargetType), "TargetMethod")]
```

Do not write `nameof("TargetMethod")`; that is not valid C# syntax. For an overloaded target, provide the argument types explicitly:

```csharp
[HarmonyPatch(typeof(TargetType), "TargetMethod", new[] { typeof(int), typeof(string) })]
```

For constructors, use Harmony's constructor target form and specify argument types when needed. Use a `TargetMethod()` resolver with `AccessTools` only when attributes cannot express the target reliably, such as a calculated, version-dependent, or otherwise complex private target. A resolver is still a Patch declaration, not permission to add a manual assembly scan.

### Patch methods

Use explicit Harmony attributes and static methods:

```csharp
[HarmonyPrefix]
private static void Prefix(TargetType __instance) { }

[HarmonyPostfix]
private static void Postfix(ref ResultType __result) { }
```

- A Prefix normally returns `void`.
- A Prefix may return `bool` only when it intentionally decides whether the original method runs; document the skip condition in the code.
- A Postfix normally returns `void` and changes a result through `ref __result` when necessary.
- Use `__instance` for the original instance, `__result` for the return value, and `__state` only for deliberate Prefix-to-Postfix state transfer.
- Use `___privateField` only when no safer public or protected seam exists, and keep the dependency narrow.
- Transpilers operate on generated instructions and are advanced; use them only when a Prefix or Postfix cannot express the change.
- Finalizers are for exception-aware patch behavior, not ordinary cleanup.
- Do not add priorities, ordering constraints, or a custom Harmony ID unless the interoperability need is real and documented.

If a manual `Harmony.Patch` exception is approved, use a stable Mod-owned Harmony ID and patch only the explicitly selected target. Never use that exception to reintroduce `PatchAll`.

## Positive and negative examples

Examples below are deliberately small. A negative example shows the operational reason for the rule, not merely a preferred formatting choice.

### Patch file and class names

Good:

```text
Patches/DamageNumberPatches.cs
    DamageNumber_ShowCriticalHit_Patch
    DamageNumber_ApplyScale_Patch
```

Bad:

```text
Patches/Patch.cs
    Patch1
    MiscellaneousPatch
```

The bad form hides the target and makes a file-level Patch inventory difficult to navigate.

### Automatic discovery

Good:

```csharp
[HarmonyPatch(typeof(TargetType), "TargetMethod")]
internal static class TargetType_AdjustDamage_Patch
{
    [HarmonyPostfix]
    private static void Postfix(ref int __result) => __result *= 2;
}
```

Bad:

```csharp
protected override void OnInitialize()
{
    new Harmony("my.mod").PatchAll(Assembly.GetExecutingAssembly());
}
```

The bad form duplicates the ModdingAPI-owned discovery step and can apply the Mod's patches more than once.

### Private and overloaded targets

Good:

```csharp
[HarmonyPatch(typeof(TargetType), "Calculate", new[] { typeof(int), typeof(float) })]
internal static class TargetType_ClampCalculation_Patch
{
    [HarmonyPrefix]
    private static void Prefix(ref int value) => value = Math.Max(0, value);
}
```

Bad:

```csharp
[HarmonyPatch(typeof(TargetType), nameof("Calculate"))]
internal static class TargetType_ClampCalculation_Patch { }
```

The bad form is invalid C# and, even if changed to a bare ambiguous string, does not identify the intended overload.

### Lifecycle placement

Good:

```csharp
protected override void OnAllInitialized()
{
    // The Mod can now rely on all Mods and registered services being initialized.
    RegisterWithAnotherModIfPresent();
}
```

Bad:

```csharp
protected override void OnUpdate()
{
    // Repeats one-time cross-Mod setup every frame.
    RegisterWithAnotherModIfPresent();
}
```

The bad form adds per-frame work and performs initialization at the wrong lifecycle stage.

## Review checklist

Before finishing Mod code, verify:

- The file is Mod-owned and not excluded or directly copied code.
- Names and member organization follow the C# baseline.
- Unity callbacks are used only for runtime components; no UnityEditor/serialization assumptions were added.
- The actual referenced `BlasMod` version exposes every override used.
- Patch files use the `Patches/` aggregation naming rule.
- Patch classes use `<TargetType>_<FunctionalityDescription>_Patch`.
- Target attributes use direct method-name strings and disambiguate overloads.
- No Mod-owned `PatchAll` or `CreateAndPatchAll` call was added.
- Any manual `Harmony.Patch` exception was explicitly approved by the user.
- Positive and negative examples remain consistent with these rules.
