---
name: blasphemous-modding-helper
description: Blasphemous modding development helper. Use when the user wants to build, deploy, launch, inspect startup evidence, stop, clean, or perform Manual verification for a Blasphemous mod; develop a mod, analyze Blasphemous decompiled source code, or debug mod-related logs (BepInEx / Unity).
---

# Blasphemous modding helper

You are helping with Blasphemous mod development.

## Requirement levels

At the start of every Skill invocation, you MUST read [Requirement levels](references/requirement-levels-definitions.md). It defines the RFC 2119 vocabulary used by every authored normative instruction in this Skill; external documentation, source code, and illustrative examples retain their original wording as described there.

## Invocation preflight

Before selecting a branch or executing a command, the agent MUST read [Invocation preflight](references/config/invocation-preflight.md). It is the authoritative contract for Skill-root resolution, caller Mod-repository context, interpreter and shell expectations, preference scope and precedence, first-time setup, path recovery, the tracked-session stop exception, and shared completion.

## Coding standards

Before generating, modifying, reviewing, or refactoring Mod-owned C# in a caller's Mod repository, you MUST read the [coding standards](references/sub-skills/coding-standards.md). It applies the ownership gate, routes C# and runtime Unity work to the [C# and runtime Unity standards](references/coding-standards-csharp-unity.md), ModdingAPI tasks to the [ModdingAPI standards](references/coding-standards-moddingAPI.md), and Harmony or Patch tasks to the [Harmony patching standards](references/coding-standards-harmony-patching.md).

- Game source code language and Mod language: C#.
- Game Unity baseline: Unity `2017.4.40f1`.
  - The agent MAY search the Unity 2017.4.40f1 API documentation at `https://docs.unity3d.com/2017.4/Documentation/ScriptReference/30_search.html?q=<class-name-or-method-name>` for extra information. The agent SHOULD replace `<class-name-or-method-name>` with the actual class or method name.
- ModdingAPI documentation, source guidance, conventions, lifecycle, logging, and examples MUST pass through [Referencing ModdingAPI](references/sub-skills/referencing-modding-api.md) before the agent browses the selected reference.
  - The route selects a configured local checkout or resolves the release-aware remote reference, then loads only the topic needed for the task.
- Mods are developed under the Blasphemous ModdingAPI framework. The agent MUST follow the ModdingAPI conventions and best practices whenever it codes against the selected reference.

## Workflow

You MUST follow the workflow steps in order, unless otherwise explicitly specified by the user.

### Step 1: Complete invocation preflight

The agent MUST follow [Invocation preflight](references/config/invocation-preflight.md) before selecting a specialized branch or executing a command.

**Done when**: the completion criteria in Invocation preflight are satisfied and the selected branch has received the active preferences or recovery result.

### Step 2: Analyze User Question

The agent MUST analyze the user question to determine user intent and the task to perform, especially paying attention to the following:

- Whether the user request involves analyzing Blasphemous Source code.
  - If yes, the agent SHOULD create a sub-agent or sub-task to handle the source code analysis using [references/sub-skills/source-analyzer.md](references/sub-skills/source-analyzer.md).
- Whether the user request involves debugging, log tracking, or error tracking.
  - If yes, the agent SHOULD create a sub-agent or sub-task to handle log analysis using [references/sub-skills/log-analyzer.md](references/sub-skills/log-analyzer.md).
- Whether the user request involves a mod test: building or selecting a mod package, deploying it, launching it, reading startup evidence or test logs/status, stopping or cleaning a session, or collecting Manual verification, including when no new automated run is requested.
  - If yes, the agent MUST route to the authoritative [`/blasphemous-modding-test`](references/sub-skills/blasphemous-modding-test.md) sub-skill.

**Done when**: the user question is classified into one or more of the four branches (source code analysis, log analysis, mod testing, or general modding question), and every applicable specialized branch has been routed to its authoritative sub-skill or analysis task.

### Step 3: Use Tools to Gather Information

The agent MUST use tools to gather information required by the task, including:

- source-analyzer and log-analyzer when they are applicable;
- the coding standards and its selected branch references;
- the Unity API and ModdingAPI references routed by the relevant sub-skills.

The tools' `.md` files SHOULD contain all path specifications required for the task. The agent MUST NOT ask the user for a path again unless the needed path information is absent there.

**Done when**: the agent has located every path the task needs (source code, modding profile, and logs) in `preferences.md` or the navigation documents, and has handed any missing or stale path to Step 5.

### Step 4: Solve User Question

The agent MUST use the gathered information to solve the user question.

**Done when**: the answer is complete and the agent has verified every source-code class, file path, and log location cited in the answer against the actual files.

### Step 5: Path Failure Recovery

The agent MUST follow the path-failure recovery contract in [Invocation preflight](references/config/invocation-preflight.md).

**Done when**: the shared recovery contract has produced a validated preferences file, or the agent has continued with the current paths and reported the specific failure and next action.
