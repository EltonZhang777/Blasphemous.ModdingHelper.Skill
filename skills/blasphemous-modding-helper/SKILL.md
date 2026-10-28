---
name: blasphemous-modding-helper
description: Blasphemous 1 modding development helper; supports Blasphemous 1 only, and Blasphemous 2 is not supported. Use when the user wants to build, deploy, launch, inspect startup evidence, stop, clean, or collect Player-performed in-game verification for a Blasphemous 1 mod; identify, explain, compare, or translate a Blasphemous 1 term; develop a Blasphemous 1 mod, analyze Blasphemous 1 decompiled source code, or debug Blasphemous 1 mod-related logs (BepInEx / Unity).
---

# Blasphemous modding helper

You are helping with Blasphemous 1 mod development. This Skill supports Blasphemous 1 only; Blasphemous 2 is not supported.

For Blasphemous 2-only requests, the agent MUST briefly state that Blasphemous 2 is out of scope, MUST invite the user to ask about Blasphemous 1, and MUST NOT start a Skill route or Blasphemous 2-specific work.

## Requirement levels

At start of every Skill invocation, agent MUST read [Requirement levels](references/requirement-levels-definitions.md). It defines RFC 2119 vocabulary used by every authored normative instruction in this Skill; external documentation, source code, and illustrative examples retain their original wording as described there.

## Request routing

After reading [Requirement levels](references/requirement-levels-definitions.md), agent MUST classify the request before applying any branch-specific gate. Agent MUST use the route owner's document as the sole authority for that route's branch-specific guidance. After classifying a request, agent MUST read the shared [Read-only evidence delegation](references/subagent-delegation/read-only-evidence-delegation.md) reference before following specialized route-owner guidance for source analysis, log analysis, ModdingAPI lookup, or localization evidence:

| Request | Route owner | Gate and handoff |
| --- | --- | --- |
| natural-language identify, explain, compare, or translate request for a Blasphemous 1 term, name, UI phrase, or textual reference | [Localization lookup](references/sub-skills/localization-lookup.md) | Agent MUST treat this route as read-only and MUST NOT require configuration. Agent MUST report localization evidence and MUST route unresolved code-like terms to the source analyzer. |
| Find or explain decompiled game source, mechanics, classes, or dependencies | [Source analyzer](references/sub-skills/source-analyzer.md) | Agent MUST complete the shared entry gate and the source-path gate. Agent MUST report the selected source tree, verified code evidence, and next analysis action. |
| Diagnose BepInEx or Unity logs, startup evidence, or runtime diagnostics | [Log analyzer](references/sub-skills/log-analyzer.md) | Agent MUST complete the shared entry gate and MUST resolve required log sources. Agent MUST report evidence mode, paths, status, and next recovery or verification action. |
| Test a Mod; build/deploy/launch a profile; inspect startup; stop, clean, or collect Player-performed in-game verification | [Mod-test entry](references/sub-skills/blasphemous-modding-test.md) | Agent MUST classify the request as `Real-profile`, `xUnit`, `both`, or `ambiguous`, then MUST follow the selected branch owner. Agent MUST ensure that Caller-owned xUnit does not wait for the Real-profile configuration gate. For `both`, Agent MUST keep independent phase reports. |
| Generate, modify, review, or refactor Mod-owned C# or project structure | [Coding standards](references/sub-skills/coding-standards.md) | Agent MUST complete the shared entry gate and selected coding branch. Agent MUST report the ownership boundary and next implementation or verification action. |
| Need ModdingAPI documentation, source guidance, or framework conventions | [Referencing ModdingAPI](references/sub-skills/referencing-modding-api.md) | Agent MUST complete the command-context gate and MUST resolve one local or release-aware reference. Agent MUST report the selected reference/topic and next source or code action. |

The localization row is the only configuration-free operational exception. Every other route MUST complete the shared entry gate before its specialized work, with the Automated xUnit branch's documented exception. A completion report MUST name the selected route and its authority, then report `status`, `completion evidence`, `blocked reason` when applicable, and the next document/action.
After classifying an operational Blasphemous 1 modding request and completing any gate required by its selected route, the agent MUST consult the [Modding knowledge](references/modding-knowledge.md) index at task start. The read-only Localization lookup route is excluded and MUST NOT run this lookup script. If a matching blocker arises later during an operational route, the agent MUST repeat the lookup. This lookup is advisory and does not change the selected route or its gate. Blasphemous 2-only requests MUST NOT use these Blasphemous 1 notes.
Before applying a retrieved note, the agent MUST compare its game version, Mod version, route, and task with the user's case. If the note does not cover that version or task, or leaves coverage unknown, the agent MUST tell the user and MUST NOT present the claim as verified for that case. Logs alone MUST NOT be described as proof of gameplay behavior.

When the main task identifies an evidence-backed Blasphemous 1 finding that may help beyond the current task, including a future improvement to the current Mod, the agent MUST start the [Experience note comparison](references/sub-skills/experience-note-comparison.md) in an independent child task and continue the main task without waiting for it. The comparison is read-only; it does not request approval, save a note, or create a pull request. At task end, the main task MUST follow [Experience note local save](references/sub-skills/experience-note-local-save.md) for any unique candidates. Only paths returned after an explicit local-save yes may then enter the separately approved [Experience note pull request](references/sub-skills/experience-note-pull-requests.md) workflow.

## Shared entry gate

The [Invocation preflight](references/config/invocation-preflight.md) reference is the sole authority for the shared entry gate: Skill-root resolution, caller Mod-repository context, Python interpreter and host expectations, configuration scope and precedence, when first-time setup is required, path recovery, the tracked-session stop exception, and shared completion. It delegates detailed setup questions, validation, save operations, and optional local checkout to [First-Time Setup](references/config/first-time-setup.md). It routes Python interpreter and dependency validation to [Python Runtime](references/config/python-runtime.md). The read-only localization branch follows its documented configuration exception. The [Dependencies](references/config/invocation-preflight.md#dependencies) section contains the canonical post-install package and conditional workflow dependency inventory.

## Coding standards

Before generating, modifying, reviewing, or refactoring Mod-owned C# in caller's Mod repository, agent MUST read [coding standards](references/sub-skills/coding-standards.md). It applies the ownership gate, routes C# and runtime Unity work to the [C# and runtime Unity standards](references/coding-standards/coding-standards-csharp-unity.md), ModdingAPI tasks to the [ModdingAPI standards](references/coding-standards/coding-standards-moddingAPI.md), and Harmony or Patch tasks to the [Harmony patching standards](references/coding-standards/coding-standards-harmony-patching.md).

- Game source code language and Mod language: C#.
- Game Unity baseline: Unity `2017.4.40f1`.
  - Agent MAY search Unity 2017.4.40f1 API documentation at `https://docs.unity3d.com/2017.4/Documentation/ScriptReference/30_search.html?q=<class-name-or-method-name>` for extra information. Agent SHOULD replace `<class-name-or-method-name>` with actual class or method name.
- ModdingAPI documentation, source guidance, conventions, lifecycle, logging, and examples MUST pass through [Referencing ModdingAPI](references/sub-skills/referencing-modding-api.md) before agent browses selected reference.
  - The route selects configured local checkout or resolves release-aware remote reference, then loads only topic needed for task.
- Mods are developed under Blasphemous ModdingAPI framework. Agent MUST follow ModdingAPI conventions and best practices whenever it codes against selected reference.

## Workflow

Agent MUST follow workflow steps in order, unless otherwise explicitly specified by user.

### Step 1: Complete shared entry gate

Agent MUST complete the shared entry gate before selecting an operational specialized branch or executing command. The localization lookup branch follows its read-only exception.

**Done when**: the shared entry gate's completion criteria are satisfied for an operational branch, or the localization branch has confirmed its index path and read-only context.

### Step 2: Analyze User Question

Agent MUST apply the Request routing rules above and route every applicable branch to its owning reference before gathering evidence.

Where useful to clarify the request, agent SHOULD identify the desired observable outcome and evidence relevant to the selected route, especially for Mod feature requests with a visible or persistent result. Route-specific completion criteria and evidence boundaries remain authoritative.

**Done when**: user question is classified into one or more applicable branches (localization lookup, source code analysis, log analysis, mod testing, or general modding question), and every applicable specialized branch has been routed to its authoritative workflow reference or analysis task.

### Step 3: Use Tools to Gather Information

Agent MUST use tools to gather information required by task, including:

- source-analyzer and log-analyzer when they are applicable;
- coding standards and its selected branch references;
- Unity API and ModdingAPI references routed by relevant sub-skills.

Tools' `.md` files SHOULD contain all path specifications required for task. Agent MUST NOT ask user for path again unless needed path information is absent there.

**Done when**: agent has located every path task needs (source code, modding profile, and logs) in `config.yml` or navigation documents, and has handed any missing or stale path to Step 5.

### Step 4: Solve User Question

Agent MUST use gathered information to solve user question.

If repeating the same approach yields no new evidence, Agent MUST pause, summarize what was checked and learned, identify remaining unknowns, then change approach or request the specific user action or information needed to proceed.

**Done when**: answer is complete and agent has verified every source-code class, file path, and log location cited in answer against actual files.

### Step 5: Path Failure Recovery

Agent MUST follow the path-failure recovery contract in the shared entry gate.

**Done when**: shared recovery contract has produced a validated configuration file, or agent has continued with current paths and reported specific failure and next action.
