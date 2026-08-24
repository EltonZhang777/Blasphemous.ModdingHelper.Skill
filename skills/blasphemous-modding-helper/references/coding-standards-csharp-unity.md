# C# and runtime Unity standards

This reference is C# branch selected by [coding standards router](sub-skills/coding-standards.md). Before applying a rule, the agent MUST read [Requirement levels](requirement-levels-definitions.md). rules apply only after router's Mod-owned scope gate passes.

## Scope and direct-copy handling

These standards MUST apply only to C# that Mod author can maintain in root of Caller Mod repository, including its source projects, `src/`, `Patches/`, and Mod-owned tests. They MUST NOT apply to decompiled game source, upstream Mods, dependency or vendor code, linked projects caller cannot change, generated output, build output, package caches, or other derived files.

When task directly copies excluded code, agent MUST preserve that direct copy as-is. Mechanical namespace or path changes MAY be made when they are required for compilation. When code receives substantive new behavior or structural rewrite, new or changed code MUST follow these standards.

## Compatibility and authority

Caller's actual compiler target, project references, and referenced game or ModdingAPI assemblies MUST determine whether syntax, BCL APIs, Unity APIs, and member signatures are legal. Unity `2017.4.40f1` baseline and this reference provide defaults; they MUST NOT override verified project or API constraint.

Agent MUST inspect narrowest authoritative source for compatibility question:

1. Assemblies referenced by caller's Mod, including corresponding source when available.
2. Version-matched upstream source and documentation.
3. This reference for local naming, organization, and runtime Unity conventions.

## C# naming

- Namespaces, classes, structs, supported records, interfaces, enums, methods, properties, events, and enum members MUST use `PascalCase`.
- Interfaces MUST begin with `I`; type parameters SHOULD begin with `T` when type-parameter name is needed.
- Constants MUST use `PascalCase`, for example `ModId` or `DefaultDamage`.
- Parameters and local variables MUST use `camelCase`.
- Private instance fields MUST use `_camelCase`; `m_` convention MUST NOT be introduced.
- Public fields SHOULD NOT substitute for public API; property or method SHOULD represent value that belongs to Mod's surface.
- Names SHOULD avoid unexplained abbreviations and SHOULD remain aligned with established game or ModdingAPI public names when referring to them.

## Files, types, and members

- Ordinary source file MUST use name aligned with its primary top-level type.
- Ordinary source file SHOULD contain one main top-level type.
- Namespaces MUST align with Mod project structure.
- Implementation details SHOULD remain `private` or `internal`; Mod SHOULD expose only API that it or another Mod needs.
- Members SHOULD follow stable order: constants, static state, instance state, properties/events, constructors, lifecycle callbacks, public API, then private helpers.
- Patch aggregation files MAY use deliberate multi-type layout; Harmony-specific organization is owned by [Harmony patching branch](coding-standards-harmony-patching.md).

## Runtime Unity components

When Mod creates or attaches `MonoBehaviour` at runtime, it MUST use Unity callbacks for component lifecycle work and MUST NOT use `MonoBehaviour` constructor for runtime initialization. callback choice SHOULD follow this table:

| Callback | Component responsibility |
| --- | --- |
| `Awake` | Establish the component's own references and local invariants. |
| `OnEnable` | Perform work required whenever the component becomes enabled. |
| `Start` | Initialize behavior that depends on other scene or runtime objects. |
| `Update` | Run per-frame work that is genuinely required and cannot be event-driven. |
| `LateUpdate` | Run per-frame work that MUST follow normal updates. |
| `OnDisable` | Undo per-enable subscriptions or state changes symmetrically. |
| `OnDestroy` | Perform component-local finalization. |

One-time global initialization MUST NOT be placed in `OnEnable`, per-frame polling SHOULD be replaced by event-driven seam when one exists, and expensive work MUST NOT be repeated in `Update` or `LateUpdate` without demonstrated need. Mod startup and game-session logic MUST remain in `BlasMod` lifecycle rather than in unrelated runtime component callback.

## UnityEditor and serialization boundary

This branch MUST NOT introduce UnityEditor, Inspector, Prefab, ScriptableObject, or Unity serialization rules into Mod. Mod has no UnityEditor relationship, so `[SerializeField]`, serialized-field naming, Inspector exposure, and editor asset workflows are outside this standard. Runtime-created components remain covered by runtime callback rules above.

## Positive and negative examples

### Scope routing

Good:

```text
Caller Mod repository/src/DamageTracker.cs
Route: coding-standards router → this C# and runtime Unity reference
```

Bad:

```text
Caller game dump/Assembly-CSharp/Player.cs
Route: excluded decompiled source; the Mod-owned C# standards are not applied
```

Bad route would rewrite code caller cannot maintain and would confuse game-source facts with Mod-owned conventions.

### Naming and organization

Good:

```csharp
internal sealed class DamageTracker
{
    private int _damage;

    internal int Damage => _damage;

    internal void AddDamage(int amount)
    {
        _damage += amount;
    }
}
```

Bad:

```csharp
public class damagetracker
{
    private int m_damage;
    public int damage;
}
```

Bad form hides type's purpose, introduces excluded field convention, and exposes mutable state instead of deliberate Mod surface.

### Runtime callback placement

Good:

```csharp
internal sealed class RuntimeUpdater : MonoBehaviour
{
    private void Awake()
    {
        // Establish component-local references.
    }

    private void Update()
    {
        // Perform only required per-frame work.
    }
}
```

Bad:

```csharp
internal sealed class RuntimeUpdater : MonoBehaviour
{
    private RuntimeUpdater()
    {
        FindObjectOfType<SomeComponent>();
    }

    private void Update()
    {
        FindObjectOfType<SomeComponent>();
    }
}
```

Bad form relies on Unity constructor and repeats scene lookup every frame instead of using appropriate callback and event-driven or cached seam.

## Review checklist

Before finishing Mod-owned C# task, reviewer MUST verify:

- Router's ownership and direct-copy gate was applied.
- Actual caller compiler and referenced API support every syntax, API, and signature used.
- Names, file names, type organization, access levels, and member order follow this branch.
- Runtime `MonoBehaviour` work uses appropriate Unity callback and avoids constructor initialization or unnecessary per-frame work.
- No UnityEditor, Inspector, Prefab, ScriptableObject, or serialization assumption was introduced.
- Positive and negative routing examples remain consistent with scope gate.
- Requirement-level wording follows [Requirement levels](requirement-levels-definitions.md).
