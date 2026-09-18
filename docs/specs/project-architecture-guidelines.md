# Spec: Project architecture guidelines for new Mod files

## Problem Statement

From a Blasphemous Mod author's perspective, the Skill explains C#, ModdingAPI, and Harmony behavior but does not give one consistent way to place newly authored Mod-owned files when a project has no established architecture. This makes entrypoints, runtime components, configuration data, extension methods, events, commands, and Harmony patches drift into the root or into generic `Utils`/`Helpers` folders.

The absence of a soft placement guide also makes examples harder to apply. Existing reference projects use useful categories but contain historical exceptions, so copying their layout literally would either overfit one project or force unwanted migrations in an established Mod repository.

## Solution

Provide an independent `project-architecture-guidelines` route behind the existing Coding Standards router. The route activates only when the Caller Mod repository lacks an established architecture or the user explicitly asks for file and directory organization. It assigns each new file to one primary responsibility, gives a small default set of semantic categories, mirrors directories in new namespaces by default, and preserves existing project and feature-oriented structures.

The guide covers `Components`, `Configs`, `Extensions`, `Patches`, `Events`, and `Commands`, plus the limited role of the project root. It keeps detailed C#, ModdingAPI, and Harmony behavior in their existing authoritative references. The guide uses the two named Mod repositories as non-binding examples and explicitly excludes the stale `TraverseUtils` placement from normative guidance.

## User Stories

1. As a Mod author starting a project without an established architecture, I want the Skill to offer a small default directory shape, so that new files have an obvious home.
2. As a Mod author with an established directory and namespace structure, I want the Skill to preserve it, so that guidance does not trigger an unwanted refactor.
3. As a Mod author who explicitly asks how to organize a new file, I want the architecture route to activate even when my project already has conventions, so that I can request a deliberate placement decision.
4. As an AI agent, I want the architecture route separated from detailed C# and Harmony behavior rules, so that each rule is loaded only when its responsibility is relevant.
5. As a Mod author, I want `Components` to identify reusable runtime or domain objects, state, registries, and management components, so that these types do not accumulate in the root.
6. As a Mod author, I want `Components` not to become a fallback for unknown files, so that every placement still has a concrete responsibility.
7. As a Mod author, I want `Configs` to contain user configuration, serialized settings, and persistence data models, so that configuration shape is separated from live runtime behavior.
8. As a Mod author, I want `Extensions` to contain extension methods and their tightly coupled support types, so that cross-type convenience APIs are easy to find.
9. As a Mod author, I want generic utility code excluded from `Extensions`, so that the directory does not become a second catch-all bucket.
10. As a Mod author, I want `Patches` to be the default category for Harmony Patch files and classes, so that patch code has one predictable home.
11. As a Mod author, I want existing `HarmonyPatches` naming preserved when a project already uses it, so that the guide does not demand a rename.
12. As a Mod author, I want `HarmonyPatches` available when multiple patch mechanisms genuinely need separation, so that the default name does not prevent a clear distinction.
13. As a Mod author, I want a Harmony patch that raises an event classified as a Patch, so that placement follows the primary mechanism rather than a secondary effect.
14. As a Mod author, I want event definitions, handlers, and subscription orchestration classified as `Events`, so that event consumers are separate from the patch bridge that emits them.
15. As a Mod author, I want console command classes classified as `Commands`, so that command-specific behavior is not mixed with general services.
16. As a Mod author, I want the root limited to entrypoints, startup orchestration, and project-level public types, so that the root remains navigable.
17. As a Mod author, I want configuration and persistence models in their semantic category for new projects, so that historical root-level exceptions are not copied into new work.
18. As a Mod author, I want a file assigned by its primary responsibility, so that containing an extension method does not automatically move a registry into `Extensions`.
19. As a Mod author, I want independently meaningful responsibilities split into separate files, so that one file does not become a cross-category dumping ground.
20. As a Mod author, I want files with one coherent responsibility kept together, so that the guide does not cause needless fragmentation.
21. As a Mod author, I want new namespaces to mirror their directories by default, so that the namespace communicates the same boundary as the folder.
22. As a Mod author joining a feature-oriented project, I want the guide to respect the existing feature structure, so that role-based defaults do not erase a working architecture.
23. As a Mod author, I want no pre-made `Utils`, `Helpers`, or `Managers` category recommended without a stable responsibility, so that speculative folders do not collect unrelated code.
24. As an AI agent, I want the guide to explain when a new semantic category is justified, so that unusual responsibilities are handled deliberately rather than hidden in a generic folder.
25. As a maintainer, I want the guide to keep Mod-owned scope distinct from decompiled, dependency, upstream, generated, and build output code, so that placement rules do not cross ownership boundaries.
26. As a Mod author, I want the reference Mod projects used as illustrative mappings rather than templates, so that examples teach responsibility without requiring structural copying.
27. As a Mod author, I want legacy example exceptions called out explicitly, so that an old helper placement is not mistaken for a new rule.
28. As a maintainer, I want detailed C#, ModdingAPI, and Harmony standards to remain authoritative for behavior, so that the architecture guide does not duplicate or contradict them.
29. As a maintainer, I want the route to be verifiable through documentation and link checks, so that a broken reference cannot silently disable the guidance.
30. As an AI agent, I want the route to explain why it did or did not activate, so that users can understand whether existing architecture or an explicit request determined the result.

## Implementation Decisions

- The highest seam is the existing Coding Standards router. The main Skill entrypoint remains the shared workflow entry, while the new architecture guide is an optional branch selected by the router.
- The route activates when the Caller Mod repository lacks stable directory, namespace, or module boundaries, or when the user explicitly asks for organization. It does not activate to impose a preferred layout on a project with established conventions.
- The guide is soft guidance for new files and directories. It never moves, renames, or restructures existing files as part of this feature.
- `Components` owns reusable Mod-owned runtime or domain objects, state, registries, and management components.
- `Configs` owns user configuration, serialized settings, and persistence data models. New projects use this category even when a reference project keeps an older configuration or persistence type at the root.
- `Extensions` owns extension methods and support types tightly coupled to those extensions. Generic helpers are not placed there, and the legacy `TraverseUtils` example is not normative.
- `Patches` is the canonical default category for Harmony Patch files and classes. Existing `HarmonyPatches` naming is preserved, and that name may distinguish multiple patch mechanisms when the distinction is real.
- `Events` owns event definitions, handlers, and subscription orchestration. A Harmony bridge that raises an event remains in `Patches` by primary mechanism.
- `Commands` owns Mod console command classes and command-specific behavior.
- The project root is reserved for entrypoints, startup orchestration, and project-level public types. The guide does not migrate existing root-level exceptions.
- Each new file has one primary category. A file is split only when its responsibilities are independently meaningful; otherwise its main responsibility determines placement.
- New namespaces mirror their directories by default. Existing namespace exceptions remain untouched.
- Feature-oriented or otherwise established project structures take precedence over the default role categories.
- New categories are introduced only for stable, semantically named responsibilities. The guide does not predefine generic `Utils`, `Helpers`, or `Managers` buckets.
- The reference projects `Blasphemous.LocalizationPatcher` and `Blasphemous.InventorySorting` provide non-binding examples for category responsibilities. Their existing exceptions are evidence for discussion, not migration targets.
- The architecture guide does not own C# naming, compiler compatibility, ModdingAPI lifecycle behavior, Harmony target resolution, patch discovery, or manual patch approval; those remain in existing detailed references.

## Testing Decisions

- Tests verify externally observable routing behavior and documentation quality, not the internal wording or implementation structure of the guide.
- The highest useful test seam is the Coding Standards router: a request with no established architecture or an explicit organization request reaches the architecture guide, while an ordinary Mod task with an established structure does not receive an unsolicited layout rewrite.
- Documentation checks cover the trigger conditions, ownership boundary, primary-responsibility rule, all six semantic categories, root policy, namespace default, existing-structure precedence, and non-migration boundary.
- Example checks cover configuration/persistence models, component registries, extension APIs, command classes, event handlers, Harmony patches, and Harmony-to-event bridges.
- A negative example verifies that generic utility buckets and the legacy `TraverseUtils` placement are not presented as normative defaults.
- Existing Markdown relative-link validation, `git diff --check`, and final worktree inspection remain the required repository checks. No new runtime test suite is needed.

## Out of Scope

- Migrating, renaming, or restructuring files in an existing Mod repository.
- Enforcing the default categories in projects with an established or feature-oriented architecture.
- Implementing code, runtime behavior, project templates, or automatic directory generation.
- Adding generic utility, helper, manager, service, or model categories without a separately justified responsibility.
- Rewriting the detailed C#, ModdingAPI, or Harmony standards.
- Treating decompiled game code, dependency code, upstream code, generated output, or build output as Mod-owned code to be reorganized.
- Copying source code or requiring the reference Mod projects to adopt the new rules.
- Using the stale `TraverseUtils` example as an architectural authority.

## Further Notes

- The architecture guide is intentionally additive: a Mod can use it for the next file without first cleaning up older files.
- `Patches` describes the primary mechanism, while `Events` describes event ownership and consumption; this distinction prevents a patch bridge from being mistaken for an event handler.
- The category list is deliberately small. A future category should be added only when repeated work demonstrates a stable responsibility that cannot be expressed clearly by the existing categories.
