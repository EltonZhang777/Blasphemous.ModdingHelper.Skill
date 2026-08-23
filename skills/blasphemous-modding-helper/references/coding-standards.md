# Coding standards compatibility pointer

This file is retained only for links from older Skill installations. It MUST NOT be treated as an authoritative coding-standards document and MUST NOT compete with the routed references.

The single entry point for current Mod-owned C# standards is the [coding standards router](sub-skills/coding-standards.md). Before generating, modifying, reviewing, or refactoring Mod-owned C# in a caller's Mod repository, the agent MUST read that router and [Requirement levels](requirement-levels-definitions.md).

The router selects the applicable branch:

- [C# and runtime Unity standards](coding-standards-csharp-unity.md) — C# naming, file/type/member organization, compiler compatibility, and runtime Unity callbacks.
- [ModdingAPI standards](coding-standards-moddingAPI.md) — ModdingAPI calls, the complete `BlasMod` lifecycle, services, development-document routing, and `ModLog`.
- [Harmony patching standards](coding-standards-harmony-patching.md) — Patch files, Patch classes, target declarations, injection, discovery, and approved manual-patch exceptions.

The [Requirement levels](requirement-levels-definitions.md) document remains the single RFC 2119 vocabulary and exception-handling authority. Older links to lifecycle, logging, or Harmony sections MUST be redirected to the corresponding branch above.
