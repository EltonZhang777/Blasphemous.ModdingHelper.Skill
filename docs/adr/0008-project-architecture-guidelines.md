---
status: accepted
---

# Route new Mod files through soft architecture categories

When a Caller Mod repository has no established architecture, or the user explicitly asks for organization, the Skill uses a separate project-architecture-guidelines route instead of folding directory placement into the detailed C# and Harmony rules. The route classifies new Mod-owned files by primary responsibility, preserves existing project structure, and never performs a migration as part of the guidance.

## Decision

- Use `Components/`, `Configs/`, `Extensions/`, `Patches/`, `Events/`, and `Commands/` for their named responsibilities; keep entrypoints, startup orchestration, and project-level public types at the root.
- Treat `Patches/` as the default name for Harmony code. An existing `HarmonyPatches/` convention may remain, or may distinguish multiple patch mechanisms, but it is not required for new projects.
- Put Harmony bridges that raise events in `Patches/`; put event definitions, handlers, and subscriptions in `Events/`.
- Put extension methods and tightly coupled support types in `Extensions/`; do not use it as a generic utility bucket. The legacy `TraverseUtils` example is not normative.
- Assign each new file to one primary category and mirror the directory in its namespace by default. Split only when responsibilities are independently meaningful.
- Preserve an established directory, namespace, or feature-oriented architecture. Do not move or rename existing files under this guidance.
- Use `Blasphemous.LocalizationPatcher` and `Blasphemous.InventorySorting` only as non-binding examples; their existing exceptions are not migration targets.

## Consequences

- New projects receive a small, predictable default shape without requiring speculative `Utils`, `Helpers`, or `Managers` directories.
- Existing Mods can adopt the route incrementally for new files without a forced refactor.
- Detailed C#, ModdingAPI, and Harmony behavior remains owned by their existing references; this ADR only decides placement and routing boundaries.
