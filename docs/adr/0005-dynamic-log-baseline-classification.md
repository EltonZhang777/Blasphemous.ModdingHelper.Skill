---
status: accepted
---

# Derive log baselines from the Test session

Concrete warning fingerprints are not reliable diagnostic ownership evidence because a Modding profile and its Debug configuration can change. `baseline` therefore means structured log evidence that existed before the current Test session; the core Skill must not use built-in concrete warning fingerprints, and records without a session baseline remain visible as `target`, `framework`, or `unknown` evidence.

## Consequences

- Missing or stale pre-session evidence cannot produce a `baseline` label; the record remains `unknown`.
- A pre-session prefix without a complete line boundary cannot produce a `baseline` label; the record remains dynamically classified.
- Generic structured source and dynamic target alias checks remain valid; concrete warning text does not become a universal profile rule.
- The core Skill must keep bounded evidence and must not persist a complete log copy.
