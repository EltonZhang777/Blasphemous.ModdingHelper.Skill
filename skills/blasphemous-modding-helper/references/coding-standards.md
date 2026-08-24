# Coding standards compatibility pointer

This file is retained only for links from older Skill installations. It MUST NOT be treated as authoritative coding-standards document and MUST NOT compete with routed references.

Single entry point for current Mod-owned C# standards is [coding standards router](sub-skills/coding-standards.md). Before generating, modifying, reviewing, or refactoring Mod-owned C# in a caller's Mod repository, the agent MUST read that router and [Requirement levels](requirement-levels-definitions.md).

Router selects applicable branch:

- [C# and runtime Unity standards](coding-standards-csharp-unity.md) — C# naming, file/type/member organization, compiler compatibility, and runtime Unity callbacks.
- [ModdingAPI standards](coding-standards-moddingAPI.md) — ModdingAPI calls, complete `BlasMod` lifecycle, services, development-document routing, and `ModLog`.
- [Harmony patching standards](coding-standards-harmony-patching.md) — Patch files, Patch classes, target declarations, injection, discovery, and approved manual-patch exceptions.

[Requirement levels](requirement-levels-definitions.md) document remains single RFC 2119 vocabulary and exception-handling authority. Older links to lifecycle, logging, or Harmony sections MUST be redirected to corresponding branch above.
