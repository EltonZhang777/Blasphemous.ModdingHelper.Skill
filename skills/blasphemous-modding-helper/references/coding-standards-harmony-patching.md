# Harmony patching standards

This reference is Harmony branch selected by [coding standards router](sub-skills/coding-standards.md). Before applying a rule, the agent MUST read [Requirement levels](requirement-levels-definitions.md). branch covers Mod-owned Harmony patch declarations, file and class organization, target resolution, patch methods, lifecycle placement, and approved manual-patch exceptions.

## Scope and authority

These rules MUST apply only to Harmony code Mod author can maintain in root of Caller Mod repository. Decompiled game source, upstream Mods, dependency or vendor code, generated output, and direct copies remain under router's exclusion and preservation rules.

Caller's actual referenced Harmony assembly and target type's actual signature MUST determine which attributes, overloads, injection parameters, and resolver APIs are legal. authority order is:

1. Harmony assembly and target assemblies referenced by Caller Mod, together with corresponding source when available.
2. Source for those exact referenced versions.
3. [official Harmony patching documentation](https://harmony.pardeike.net/articles/patching.html), [injection documentation](https://harmony.pardeike.net/articles/patching-injections.html), [HarmonyPatch API reference](https://harmony.pardeike.net/api/HarmonyLib.HarmonyPatch.html), and [AccessTools API reference](https://harmony.pardeike.net/api/HarmonyLib.AccessTools.html).
4. Examples in external documentation.

If target signature, attribute overload, or resolver result is missing or conflicting, agent MUST inspect caller's referenced assembly and matching source. If fact remains unavailable, agent MUST stop and ask user rather than guessing.

[ModdingAPI standards](coding-standards-moddingAPI.md#services-and-cross-mod-integration) are single authority for framework-managed Patch discovery, including prohibition on Mod-owned assembly scanning. Mod MUST express ordinary patches as Patch classes. This branch defines those declarations and their exception boundaries; it MUST NOT replace or duplicate ModdingAPI ownership contract.

## Patch files and classes

New Mod-owned Patch files MUST live under Mod root's `Patches/` directory. file name MUST use one of these aggregation forms:

| Grouping | File name | Use |
| --- | --- | --- |
| Target type | `<TypeName>Patches.cs` | Patches whose main target is one type, such as `DamageNumberPatches.cs` |
| Coherent functionality | `<Functionality>Patches.cs` | Patches for one feature spanning related target types, such as `CriticalHitPatches.cs` |

Patch file MAY contain multiple related Patch classes. file MUST NOT mix unrelated targets or unrelated functionality merely to reduce file count.

Each Patch class MUST identify its target type and changed behavior in form `<ClassName>_<FunctionalityDescription>_Patch`. Patch classes SHOULD be `internal static` and each class SHOULD focus on one target method and one coherent behavior. class MAY contain that target's Prefix, Postfix, Transpiler, and/or Finalizer, but it MUST NOT become general-purpose utility container.

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

File name is aggregation name, not Patch class name. One file MAY therefore contain `DamageNumber_ApplyScale_Patch` and `DamageNumber_ShowCriticalHit_Patch` when both belong to same target-type group.

## Target declarations

Preferred target declaration MUST use direct string for method name:

```csharp
[HarmonyPatch(typeof(TargetType), "TargetMethod")]
```

This form MUST be used even when target is public unless another supported target form is required. direct string keeps private target methods expressible; `nameof(TargetType.TargetMethod)` can fail to compile when method is private. `nameof("TargetMethod")` is invalid C# and MUST NOT be used.

Overloaded method MUST specify its parameter types in declaration order:

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

Parameter-type list MUST match actual referenced signature, including by-reference, out, pointer, array, optional, or generic argument variations when they affect overload selection. Agent MUST use caller's actual `HarmonyPatch` and `ArgumentType` API for those variations rather than copying incompatible example.

Constructor targets MUST use Harmony's constructor form and MUST specify parameters when constructor is overloaded:

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

Static constructors MUST use `MethodType.StaticConstructor`. Property accessors MUST use getter or setter method type when property target is intended, for example `[HarmonyPatch(typeof(TargetType), "Value", MethodType.Getter)]`. actual referenced Harmony version MUST be checked before using less common `MethodType` or attribute overloads.

## Resolver boundaries

Attributes MUST be preferred when they can express exact target. `TargetMethod()` or `TargetMethods()` resolver MAY be used only when target is calculated, version-dependent, inaccessible to direct type reference, or otherwise cannot be expressed reliably by attributes.

Resolver MUST bind to known target type, method name, and parameter signature. It MUST return only exact `MethodBase` or explicitly enumerated set of methods required by Patch. It MUST NOT search all assemblies or all loaded types, choose first ambiguous overload, or silently fall back to different version.

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

Resolver is still Patch declaration; it is not permission to scan or patch assembly. If resolver returns no target or ambiguous target, agent MUST fail closed, inspect actual version, and ask user if conflict cannot be resolved.

## Patch methods

Patch methods MUST be static. They SHOULD be private unless another documented interoperability need requires wider access level. Harmony attributes MUST identify patch kind when method name is not one of Harmony's recognized names:

| Patch kind | Responsibility | Local rule |
| --- | --- | --- |
| `[HarmonyPrefix]` | Runs before the original method | A Prefix SHOULD return `void`; it MAY return `bool` only when it intentionally controls whether the original runs, and the skip condition MUST be clear. |
| `[HarmonyPostfix]` | Runs after the original method | A Postfix SHOULD return `void`; it MUST use `ref __result` when it changes a return value. |
| `[HarmonyTranspiler]` | Transforms the original method's generated instructions | A Transpiler MUST be used only when a Prefix or Postfix cannot express the required change. |
| `[HarmonyFinalizer]` | Handles exceptions from the original and other patches | A Finalizer MUST be reserved for exception-aware behavior, not ordinary cleanup. |

Patch methods MAY receive only injected values they use. common injections are:

- `__instance` for original instance of non-static target.
- `__result` for original return value; changed result MUST use correct type and `ref` where required.
- `__state` for deliberate Prefix-to-Postfix state transfer within same Patch class.
- `___privateField` for private field, only when no safer public or protected seam exists and dependency remains narrow.
- `__originalMethod` when Patch intentionally needs selected `MethodBase`; it MUST NOT be treated as way to call unpatched original.

Normal target arguments SHOULD be injected by their original names or by Harmony's supported indexed form. Agent MUST verify injection names and types against referenced target signature. Patch methods MUST NOT depend on incidental private fields when explicit API seam is available.

## Discovery, lifecycle, and manual patching

Framework-managed discovery MUST remain separate from Mod lifecycle callbacks. Patch classes SHOULD remain passive declarations; initialization and cross-Mod work belong in appropriate `BlasMod` lifecycle branch. linked ModdingAPI ownership rule controls framework discovery at every lifecycle point.

Manual `Harmony.Patch` is exception, not second default. Before writing one, agent MUST ask user and wait for confirmation. exception MAY be approved only when automatic declaration cannot express required timing, condition, external target, or exact target selection. approved manual Patch MUST:

- Approved manual Patch MUST use stable Mod-owned Harmony ID.
- Approved manual Patch MUST resolve and patch only explicitly selected `MethodBase` or methods.
- Approved manual Patch MUST record why framework-managed declaration cannot express case.
- Approved manual Patch MUST preserve framework-managed discovery contract and its assembly-scan prohibition.

If user does not approve exception, agent MUST stop and use declarative route or report unresolved limitation.

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

Bad form hides both target and feature, so Patch inventory cannot be navigated from file or class names.

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

Bad form creates second assembly-scanning lifecycle and can apply Mod's patches more than once.

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

Bad form is invalid C# and, even if changed to bare ambiguous string, does not identify intended overload.

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

Bad form repeats assembly-wide discovery from per-frame callback instead of relying on framework-managed declaration path.

## Review checklist

Before finishing Harmony-related task, reviewer MUST verify:

- Router's Mod-owned scope gate and C# branch were applied.
- ModdingAPI branch remains single authority for framework-managed Patch discovery.
- Patch files MUST use `Patches/<TypeName>Patches.cs` or `Patches/<Functionality>Patches.cs` and MAY group only related Patch classes.
- Patch classes MUST use `<ClassName>_<FunctionalityDescription>_Patch`.
- Agent MUST use direct-string targets and MUST disambiguate overloads, constructors, property accessors, and argument variations from actual referenced API.
- Resolver methods MUST bind to exact targets and MUST NOT scan assemblies or silently choose ambiguous methods.
- Patch methods MUST be static, MUST use appropriate Harmony kinds and injections, and MUST keep advanced operations justified.
- Agent MUST preserve framework-managed discovery contract and MUST NOT add manual assembly scan.
- Any manual `Harmony.Patch` operation MUST have explicit user approval and explicitly selected target.
- Positive and negative examples MUST remain consistent with discovery ownership, naming, target declarations, and lifecycle placement.
- Normative wording MUST follow [Requirement levels](requirement-levels-definitions.md).
