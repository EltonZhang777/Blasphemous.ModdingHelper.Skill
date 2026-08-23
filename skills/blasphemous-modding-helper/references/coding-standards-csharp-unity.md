# C# and runtime Unity standards

This reference is the C# branch selected by the [coding standards router](sub-skills/coding-standards.md). Before applying a rule, the agent MUST read [Requirement levels](requirement-levels-definitions.md). The rules apply only after the router's Mod-owned scope gate passes.

## Scope and direct-copy handling

These standards MUST apply only to C# that the Mod author can maintain in the root of the Caller Mod repository, including its source projects, `src/`, `Patches/`, and Mod-owned tests. They MUST NOT apply to decompiled game source, upstream Mods, dependency or vendor code, linked projects the caller cannot change, generated output, build output, package caches, or other derived files.

When a task directly copies excluded code, the agent MUST preserve that direct copy as-is. Mechanical namespace or path changes MAY be made when they are required for compilation. When the code receives substantive new behavior or a structural rewrite, the new or changed code MUST follow these standards.

## Compatibility and authority

The caller's actual compiler target, project references, and referenced game or ModdingAPI assemblies MUST determine whether syntax, BCL APIs, Unity APIs, and member signatures are legal. The Unity `2017.4.40f1` baseline and this reference provide defaults; they MUST NOT override a verified project or API constraint.

The agent MUST inspect the narrowest authoritative source for a compatibility question:

1. The assemblies actually referenced by the caller's Mod, including corresponding source when available.
2. Version-matched upstream source and documentation.
3. This reference for local naming, organization, and runtime Unity conventions.

## C# naming

- Namespaces, classes, structs, supported records, interfaces, enums, methods, properties, events, and enum members MUST use `PascalCase`.
- Interfaces MUST begin with `I`; type parameters SHOULD begin with `T` when a type-parameter name is needed.
- Constants MUST use `PascalCase`, for example `ModId` or `DefaultDamage`.
- Parameters and local variables MUST use `camelCase`.
- Private instance fields MUST use `_camelCase`; the `m_` convention MUST NOT be introduced.
- Public fields SHOULD NOT substitute for a public API; a property or method SHOULD represent a value that belongs to the Mod's surface.
- Names SHOULD avoid unexplained abbreviations and SHOULD remain aligned with established game or ModdingAPI public names when referring to them.

## Files, types, and members

- An ordinary source file MUST use a name aligned with its primary top-level type.
- An ordinary source file SHOULD contain one main top-level type.
- Namespaces MUST align with the Mod project structure.
- Implementation details SHOULD remain `private` or `internal`; a Mod SHOULD expose only the API that it or another Mod actually needs.
- Members SHOULD follow a stable order: constants, static state, instance state, properties/events, constructors, lifecycle callbacks, public API, then private helpers.
- Patch aggregation files MAY use a deliberate multi-type layout; Harmony-specific organization is owned by the [Harmony patching branch](coding-standards-harmony-patching.md).

## Runtime Unity components

When a Mod creates or attaches a `MonoBehaviour` at runtime, it MUST use Unity callbacks for component lifecycle work and MUST NOT use a `MonoBehaviour` constructor for runtime initialization. The callback choice SHOULD follow this table:

| Callback | Component responsibility |
| --- | --- |
| `Awake` | Establish the component's own references and local invariants. |
| `OnEnable` | Perform work required whenever the component becomes enabled. |
| `Start` | Initialize behavior that depends on other scene or runtime objects. |
| `Update` | Run per-frame work that is genuinely required and cannot be event-driven. |
| `LateUpdate` | Run per-frame work that MUST follow normal updates. |
| `OnDisable` | Undo per-enable subscriptions or state changes symmetrically. |
| `OnDestroy` | Perform component-local finalization. |

One-time global initialization MUST NOT be placed in `OnEnable`, per-frame polling SHOULD be replaced by an event-driven seam when one exists, and expensive work MUST NOT be repeated in `Update` or `LateUpdate` without a demonstrated need. Mod startup and game-session logic MUST remain in the `BlasMod` lifecycle rather than in an unrelated runtime component callback.

## UnityEditor and serialization boundary

This branch MUST NOT introduce UnityEditor, Inspector, Prefab, ScriptableObject, or Unity serialization rules into a Mod. The Mod has no UnityEditor relationship, so `[SerializeField]`, serialized-field naming, Inspector exposure, and editor asset workflows are outside this standard. Runtime-created components remain covered by the runtime callback rules above.

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

The bad route would rewrite code the caller cannot maintain and would confuse game-source facts with Mod-owned conventions.

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

The bad form hides the type's purpose, introduces the excluded field convention, and exposes mutable state instead of a deliberate Mod surface.

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

The bad form relies on a Unity constructor and repeats a scene lookup every frame instead of using the appropriate callback and an event-driven or cached seam.

## Review checklist

Before finishing a Mod-owned C# task, the reviewer MUST verify:

- The router's ownership and direct-copy gate was applied.
- The actual caller compiler and referenced API support every syntax, API, and signature used.
- Names, file names, type organization, access levels, and member order follow this branch.
- Runtime `MonoBehaviour` work uses the appropriate Unity callback and avoids constructor initialization or unnecessary per-frame work.
- No UnityEditor, Inspector, Prefab, ScriptableObject, or serialization assumption was introduced.
- Positive and negative routing examples remain consistent with the scope gate.
- Requirement-level wording follows [Requirement levels](requirement-levels-definitions.md).
