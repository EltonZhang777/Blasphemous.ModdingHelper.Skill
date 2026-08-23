# Harmony patching standards

This reference is the Harmony branch selected by the [coding standards router](sub-skills/coding-standards.md). Before applying a rule, the agent MUST read [Requirement levels](requirement-levels-definitions.md). The branch covers Mod-owned Harmony patch declarations, file and class organization, target resolution, patch methods, lifecycle placement, and approved manual-patch exceptions.

## Scope and authority

These rules MUST apply only to Harmony code the Mod author can maintain in the root of the Caller Mod repository. Decompiled game source, upstream Mods, dependency or vendor code, generated output, and direct copies remain under the router's exclusion and preservation rules.

The caller's actual referenced Harmony assembly and the target type's actual signature MUST determine which attributes, overloads, injection parameters, and resolver APIs are legal. The authority order is:

1. The Harmony assembly and target assemblies actually referenced by the Caller Mod, together with corresponding source when available.
2. Source for those exact referenced versions.
3. The [official Harmony patching documentation](https://harmony.pardeike.net/articles/patching.html), [injection documentation](https://harmony.pardeike.net/articles/patching-injections.html), [HarmonyPatch API reference](https://harmony.pardeike.net/api/HarmonyLib.HarmonyPatch.html), and [AccessTools API reference](https://harmony.pardeike.net/api/HarmonyLib.AccessTools.html).
4. Examples in external documentation.

If a target signature, attribute overload, or resolver result is missing or conflicting, the agent MUST inspect the caller's referenced assembly and matching source. If the fact remains unavailable, the agent MUST stop and ask the user rather than guessing.

The [ModdingAPI standards](coding-standards-moddingAPI.md#services-and-cross-mod-integration) are the single authority for framework-managed Patch discovery, including the prohibition on Mod-owned assembly scanning. A Mod MUST express ordinary patches as Patch classes. This branch defines those declarations and their exception boundaries; it MUST NOT replace or duplicate the ModdingAPI ownership contract.

## Patch files and classes

New Mod-owned Patch files MUST live under the Mod root's `Patches/` directory. The file name MUST use one of these aggregation forms:

| Grouping | File name | Use |
| --- | --- | --- |
| Target type | `<TypeName>Patches.cs` | Patches whose main target is one type, such as `DamageNumberPatches.cs` |
| Coherent functionality | `<Functionality>Patches.cs` | Patches for one feature spanning related target types, such as `CriticalHitPatches.cs` |

A Patch file MAY contain multiple related Patch classes. A file MUST NOT mix unrelated targets or unrelated functionality merely to reduce the file count.

Each Patch class MUST identify its target type and changed behavior in the form `<ClassName>_<FunctionalityDescription>_Patch`. Patch classes SHOULD be `internal static` and each class SHOULD focus on one target method and one coherent behavior. A class MAY contain that target's Prefix, Postfix, Transpiler, and/or Finalizer, but it MUST NOT become a general-purpose utility container.

```csharp
// Patches/DamageNumberPatches.cs
[HarmonyPatch(typeof(DamageNumber), "ApplyScale")]
internal static class DamageNumber_ApplyScale_Patch
{
    [HarmonyPostfix]
    private static void Postfix(ref float __result)
    {
        __result *= 2f;
    }
}

[HarmonyPatch(typeof(DamageNumber), "ShowCriticalHit")]
internal static class DamageNumber_ShowCriticalHit_Patch
{
    [HarmonyPrefix]
    private static void Prefix()
    {
    }
}
```

The file name is the aggregation name, not the Patch class name. One file MAY therefore contain `DamageNumber_ApplyScale_Patch` and `DamageNumber_ShowCriticalHit_Patch` when both belong to the same target-type group.

## Target declarations

The preferred target declaration MUST use a direct string for the method name:

```csharp
[HarmonyPatch(typeof(TargetType), "TargetMethod")]
```

This form MUST be used even when the target is public unless another supported target form is required. A direct string keeps private target methods expressible; `nameof(TargetType.TargetMethod)` can fail to compile when the method is private. `nameof("TargetMethod")` is invalid C# and MUST NOT be used.

An overloaded method MUST specify its parameter types in declaration order:

```csharp
[HarmonyPatch(
    typeof(TargetType),
    "Calculate",
    new[] { typeof(int), typeof(float) }
)]
internal static class TargetType_ClampCalculation_Patch
{
    [HarmonyPrefix]
    private static void Prefix(ref int value)
    {
        value = Math.Max(0, value);
    }
}
```

The parameter-type list MUST match the actual referenced signature, including by-reference, out, pointer, array, optional, or generic argument variations when they affect overload selection. The agent MUST use the caller's actual `HarmonyPatch` and `ArgumentType` API for those variations rather than copying an incompatible example.

Constructor targets MUST use Harmony's constructor form and MUST specify parameters when the constructor is overloaded:

```csharp
[HarmonyPatch(typeof(TargetType), MethodType.Constructor, new[] { typeof(int) })]
internal static class TargetType_Initialize_Patch
{
    [HarmonyPostfix]
    private static void Postfix(TargetType __instance)
    {
        // Apply only the behavior owned by this Mod.
    }
}
```

Static constructors MUST use `MethodType.StaticConstructor`. Property accessors MUST use the getter or setter method type when a property target is intended, for example `[HarmonyPatch(typeof(TargetType), "Value", MethodType.Getter)]`. The actual referenced Harmony version MUST be checked before using less common `MethodType` or attribute overloads.

## Resolver boundaries

Attributes MUST be preferred when they can express the exact target. A `TargetMethod()` or `TargetMethods()` resolver MAY be used only when the target is calculated, version-dependent, inaccessible to a direct type reference, or otherwise cannot be expressed reliably by attributes.

A resolver MUST bind to the known target type, method name, and parameter signature. It MUST return only the exact `MethodBase` or explicitly enumerated set of methods required by the Patch. It MUST NOT search all assemblies or all loaded types, choose the first ambiguous overload, or silently fall back to a different version.

```csharp
[HarmonyPatch]
internal static class TargetType_AdjustVersionedValue_Patch
{
    private static MethodBase TargetMethod()
    {
        return AccessTools.Method(
            typeof(TargetType),
            "Calculate",
            new[] { typeof(int), typeof(float) }
        );
    }

    [HarmonyPostfix]
    private static void Postfix(ref int __result)
    {
        __result = Math.Max(0, __result);
    }
}
```

The resolver is still a Patch declaration; it is not permission to scan or patch an assembly. If a resolver returns no target or an ambiguous target, the agent MUST fail closed, inspect the actual version, and ask the user if the conflict cannot be resolved.

## Patch methods

Patch methods MUST be static. They SHOULD be private unless another documented interoperability need requires a wider access level. Harmony attributes MUST identify the patch kind when the method name is not one of Harmony's recognized names:

| Patch kind | Responsibility | Local rule |
| --- | --- | --- |
| `[HarmonyPrefix]` | Runs before the original method | A Prefix SHOULD return `void`; it MAY return `bool` only when it intentionally controls whether the original runs, and the skip condition MUST be clear. |
| `[HarmonyPostfix]` | Runs after the original method | A Postfix SHOULD return `void`; it MUST use `ref __result` when it changes a return value. |
| `[HarmonyTranspiler]` | Transforms the original method's generated instructions | A Transpiler MUST be used only when a Prefix or Postfix cannot express the required change. |
| `[HarmonyFinalizer]` | Handles exceptions from the original and other patches | A Finalizer MUST be reserved for exception-aware behavior, not ordinary cleanup. |

Patch methods MAY receive only the injected values they use. The common injections are:

- `__instance` for the original instance of a non-static target.
- `__result` for the original return value; a changed result MUST use the correct type and `ref` where required.
- `__state` for deliberate Prefix-to-Postfix state transfer within the same Patch class.
- `___privateField` for a private field, only when no safer public or protected seam exists and the dependency remains narrow.
- `__originalMethod` when a Patch intentionally needs the selected `MethodBase`; it MUST NOT be treated as a way to call the unpatched original.

Normal target arguments SHOULD be injected by their original names or by Harmony's supported indexed form. The agent MUST verify injection names and types against the referenced target signature. Patch methods MUST NOT depend on incidental private fields when an explicit API seam is available.

## Discovery, lifecycle, and manual patching

Framework-managed discovery MUST remain separate from Mod lifecycle callbacks. Patch classes SHOULD remain passive declarations; initialization and cross-Mod work belong in the appropriate `BlasMod` lifecycle branch. The linked ModdingAPI ownership rule controls framework discovery at every lifecycle point.

Manual `Harmony.Patch` is an exception, not a second default. Before writing one, the agent MUST ask the user and wait for confirmation. The exception MAY be approved only when automatic declaration cannot express the required timing, condition, external target, or exact target selection. An approved manual Patch MUST:

- An approved manual Patch MUST use a stable Mod-owned Harmony ID.
- An approved manual Patch MUST resolve and patch only the explicitly selected `MethodBase` or methods.
- An approved manual Patch MUST record why framework-managed declaration cannot express the case.
- An approved manual Patch MUST preserve the framework-managed discovery contract and its assembly-scan prohibition.

If the user does not approve the exception, the agent MUST stop and use the declarative route or report the unresolved limitation.

## Positive and negative examples

### File and class organization

Good:

```text
Patches/DamageNumberPatches.cs
    DamageNumber_ApplyScale_Patch
    DamageNumber_ShowCriticalHit_Patch
```

Bad:

```text
Patches/Patch.cs
    Patch1
    MiscellaneousPatch
```

The bad form hides both the target and the feature, so the Patch inventory cannot be navigated from file or class names.

### Framework discovery

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

The bad form creates a second assembly-scanning lifecycle and can apply the Mod's patches more than once.

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
// Patches are declared in Patches/ and discovered by ModdingAPI.
protected override void OnInitialize()
{
    LoadModState();
}
```

Bad:

```csharp
protected override void OnUpdate()
{
    new Harmony("my.mod").PatchAll(Assembly.GetExecutingAssembly());
}
```

The bad form repeats assembly-wide discovery from a per-frame callback instead of relying on the framework-managed declaration path.

## Review checklist

Before finishing a Harmony-related task, the reviewer MUST verify:

- The router's Mod-owned scope gate and the C# branch were applied.
- The ModdingAPI branch remains the single authority for framework-managed Patch discovery.
- Patch files MUST use `Patches/<TypeName>Patches.cs` or `Patches/<Functionality>Patches.cs` and MAY group only related Patch classes.
- Patch classes MUST use `<ClassName>_<FunctionalityDescription>_Patch`.
- The agent MUST use direct-string targets and MUST disambiguate overloads, constructors, property accessors, and argument variations from the actual referenced API.
- Resolver methods MUST bind to exact targets and MUST NOT scan assemblies or silently choose ambiguous methods.
- Patch methods MUST be static, MUST use appropriate Harmony kinds and injections, and MUST keep advanced operations justified.
- The agent MUST preserve the framework-managed discovery contract and MUST NOT add a manual assembly scan.
- Any manual `Harmony.Patch` operation MUST have explicit user approval and an explicitly selected target.
- Positive and negative examples MUST remain consistent with discovery ownership, naming, target declarations, and lifecycle placement.
- Normative wording MUST follow [Requirement levels](requirement-levels-definitions.md).
