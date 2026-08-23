# Keep Mod code standards local and let ModdingAPI own Patch discovery

This repository applies its detailed C# and Harmony standards only to Mod-owned code in the caller's Mod repository, while the actual referenced ModdingAPI, Harmony, Unity, and game assemblies remain authoritative for runtime behavior. The rules live in a dedicated reference and preserve directly copied external code; ModdingAPI's `BlasMod` startup owns Harmony discovery, so Mod code declares Patch classes but does not invoke `PatchAll`, with manual `Harmony.Patch` reserved for user-approved exceptions.

## Consequences

- The skill can give consistent local guidance without rewriting upstream or decompiled code.
- `SKILL.md` remains a workflow entry point and links to the detailed reference.
- Patch files can aggregate related Patch classes without giving each file the name of one class.
- A future API-version change must be checked against the caller's actual referenced assembly before applying lifecycle overrides.
