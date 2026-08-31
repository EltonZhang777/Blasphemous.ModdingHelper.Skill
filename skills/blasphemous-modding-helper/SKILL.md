---
name: blasphemous-modding-helper
description: Blasphemous modding development helper. Use when the user wants to build, deploy, launch, inspect startup evidence, stop, clean, or perform Manual verification for a Blasphemous mod; develop a mod, analyze Blasphemous decompiled source code, or debug mod-related logs (BepInEx / Unity).
---

# Blasphemous modding helper

You are helping with Blasphemous mod development.

## Requirement levels

At start of every Skill invocation, agent MUST read [Requirement levels](references/requirement-levels-definitions.md). It defines RFC 2119 vocabulary used by every authored normative instruction in this Skill; external documentation, source code, and illustrative examples retain their original wording as described there.

## Invocation preflight

Before selecting branch or executing command, agent MUST read [Invocation preflight](references/config/invocation-preflight.md). It is authoritative contract for Skill-root resolution, caller Mod-repository context, interpreter and shell expectations, preference scope and precedence, first-time setup, path recovery, tracked-session stop exception, and shared completion. It routes Python interpreter and dependency validation to [Python Runtime](references/config/python-runtime.md).

## Coding standards

Before generating, modifying, reviewing, or refactoring Mod-owned C# in caller's Mod repository, agent MUST read [coding standards](references/sub-skills/coding-standards.md). It applies the ownership gate, routes C# and runtime Unity work to the [C# and runtime Unity standards](references/coding-standards-csharp-unity.md), ModdingAPI tasks to the [ModdingAPI standards](references/coding-standards-moddingAPI.md), and Harmony or Patch tasks to the [Harmony patching standards](references/coding-standards-harmony-patching.md).

- Game source code language and Mod language: C#.
- Game Unity baseline: Unity `2017.4.40f1`.
  - Agent MAY search Unity 2017.4.40f1 API documentation at `https://docs.unity3d.com/2017.4/Documentation/ScriptReference/30_search.html?q=<class-name-or-method-name>` for extra information. Agent SHOULD replace `<class-name-or-method-name>` with actual class or method name.
- ModdingAPI documentation, source guidance, conventions, lifecycle, logging, and examples MUST pass through [Referencing ModdingAPI](references/sub-skills/referencing-modding-api.md) before agent browses selected reference.
  - Route selects configured local checkout or resolves release-aware remote reference, then loads only topic needed for task.
- Mods are developed under Blasphemous ModdingAPI framework. Agent MUST follow ModdingAPI conventions and best practices whenever it codes against selected reference.

## Workflow

Agent MUST follow workflow steps in order, unless otherwise explicitly specified by user.

### Step 1: Complete invocation preflight

Agent MUST follow [Invocation preflight](references/config/invocation-preflight.md) before selecting specialized branch or executing command.

**Done when**: completion criteria in Invocation preflight are satisfied and selected branch has received active preferences or recovery result.

### Step 2: Analyze User Question

Agent MUST analyze user question to determine user intent and task to perform, especially paying attention to these:

- Whether user request involves analyzing Blasphemous Source code.
  - If yes, agent SHOULD create sub-agent or sub-task to handle source code analysis using [references/sub-skills/source-analyzer.md](references/sub-skills/source-analyzer.md).
- Whether user request involves debugging, log tracking, or error tracking.
  - If yes, agent SHOULD create sub-agent or sub-task to handle log analysis using [references/sub-skills/log-analyzer.md](references/sub-skills/log-analyzer.md).
- Whether user request involves mod test: building or selecting mod package, deploying it, launching it, reading startup evidence or test logs/status, stopping or cleaning session, or collecting Manual verification, including when no new automated run is requested.
  - If yes, agent MUST route to authoritative [`/blasphemous-modding-test`](references/sub-skills/blasphemous-modding-test.md) sub-skill.

**Done when**: user question is classified into one or more of four branches (source code analysis, log analysis, mod testing, or general modding question), and every applicable specialized branch has been routed to its authoritative sub-skill or analysis task.

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

Agent MUST follow path-failure recovery contract in [Invocation preflight](references/config/invocation-preflight.md).

**Done when**: shared recovery contract has produced validated preferences file, or agent has continued with current paths and reported specific failure and next action.
