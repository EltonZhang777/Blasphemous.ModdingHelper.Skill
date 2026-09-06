---
name: blasphemous-modding-helper
description: Blasphemous modding development helper. Use when the user wants to build, deploy, launch, inspect startup evidence, stop, clean, or perform Manual verification for a Blasphemous mod; identify, explain, compare, or translate a Blasphemous 1 term; develop a mod, analyze Blasphemous decompiled source code, or debug mod-related logs (BepInEx / Unity).
---

# Blasphemous modding helper

You are helping with Blasphemous mod development.

## Request routing

After reading Requirement levels, agent MUST classify the request before choosing an operational branch.

- For a natural-language request to identify, explain, compare, or translate a Blasphemous 1 term, name, UI phrase, or textual reference, agent MUST read [Localization lookup](references/sub-skills/localization-lookup.md). Agent MUST treat this as a read-only localization branch and MUST NOT require preferences.
- For source analysis, log analysis, mod testing, or Mod work, agent MUST continue through the shared entry gate and the applicable branch below.

## Requirement levels

At start of every Skill invocation, agent MUST read [Requirement levels](references/requirement-levels-definitions.md). It defines RFC 2119 vocabulary used by every authored normative instruction in this Skill; external documentation, source code, and illustrative examples retain their original wording as described there.

## Shared entry gate

The [Invocation preflight](references/config/invocation-preflight.md) reference is the sole authority for Skill-root resolution, caller Mod-repository context, Python interpreter and host expectations, preference scope and precedence, first-time setup, path recovery, tracked-session stop exception, and shared completion. It routes Python interpreter and dependency validation to [Python Runtime](references/config/python-runtime.md). The read-only localization branch follows its documented preference exception.

## Coding standards

Before generating, modifying, reviewing, or refactoring Mod-owned C# in caller's Mod repository, agent MUST read [coding standards](references/sub-skills/coding-standards.md). It applies the ownership gate, routes C# and runtime Unity work to the [C# and runtime Unity standards](references/coding-standards/coding-standards-csharp-unity.md), ModdingAPI tasks to the [ModdingAPI standards](references/coding-standards/coding-standards-moddingAPI.md), and Harmony or Patch tasks to the [Harmony patching standards](references/coding-standards/coding-standards-harmony-patching.md).

- Game source code language and Mod language: C#.
- Game Unity baseline: Unity `2017.4.40f1`.
  - Agent MAY search Unity 2017.4.40f1 API documentation at `https://docs.unity3d.com/2017.4/Documentation/ScriptReference/30_search.html?q=<class-name-or-method-name>` for extra information. Agent SHOULD replace `<class-name-or-method-name>` with actual class or method name.
- ModdingAPI documentation, source guidance, conventions, lifecycle, logging, and examples MUST pass through [Referencing ModdingAPI](references/sub-skills/referencing-modding-api.md) before agent browses selected reference.
  - Route selects configured local checkout or resolves release-aware remote reference, then loads only topic needed for task.
- Mods are developed under Blasphemous ModdingAPI framework. Agent MUST follow ModdingAPI conventions and best practices whenever it codes against selected reference.

## Workflow

Agent MUST follow workflow steps in order, unless otherwise explicitly specified by user.

### Step 1: Complete shared entry gate

Agent MUST complete the shared entry gate before selecting an operational specialized branch or executing command. The localization lookup branch follows its read-only exception.

**Done when**: the shared entry gate's completion criteria are satisfied for an operational branch, or the localization branch has confirmed its index path and read-only context.

### Step 2: Analyze User Question

Agent MUST apply the Request routing rules above and route every applicable branch to its owning reference before gathering evidence.

**Done when**: user question is classified into one or more applicable branches (localization lookup, source code analysis, log analysis, mod testing, or general modding question), and every applicable specialized branch has been routed to its authoritative sub-skill or analysis task.

### Step 3: Use Tools to Gather Information

Agent MUST use tools to gather information required by task, including:

- source-analyzer and log-analyzer when they are applicable;
- coding standards and its selected branch references;
- Unity API and ModdingAPI references routed by relevant sub-skills.

Tools' `.md` files SHOULD contain all path specifications required for task. Agent MUST NOT ask user for path again unless needed path information is absent there.

**Done when**: agent has located every path task needs (source code, modding profile, and logs) in `preferences.md` or navigation documents, and has handed any missing or stale path to Step 5.

### Step 4: Solve User Question

Agent MUST use gathered information to solve user question.

**Done when**: answer is complete and agent has verified every source-code class, file path, and log location cited in answer against actual files.

### Step 5: Path Failure Recovery

Agent MUST follow the path-failure recovery contract in the shared entry gate.

**Done when**: shared recovery contract has produced validated preferences file, or agent has continued with current paths and reported specific failure and next action.
