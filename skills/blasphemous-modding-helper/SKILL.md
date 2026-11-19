---
name: blasphemous-modding-helper
description: Blasphemous 1 mod development helper for Mod testing, BepInEx/Unity diagnostics, decompiled source and save analysis, exported Unity project navigation, ModdingAPI guidance, and game-term localization.
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
| natural-language identify, explain, compare, or translate request for a Blasphemous 1 term, name, UI phrase, or textual reference | [Localization lookup](references/sub-skills/localization-lookup.md) | Agent MUST follow the Localization lookup owner's documented configuration exception. Agent MUST report localization evidence and MUST route unresolved code-like terms to the source analyzer. |
| Find or explain decompiled game source, mechanics, classes, or dependencies | [Source analyzer](references/sub-skills/source-analyzer.md) | Agent MUST complete the shared entry gate and the source-path gate. Agent MUST report the selected source tree, verified code evidence, and next analysis action. |
| Inspect exported Unity project topology, assets, GUIDs, script assets, flattened Prefabs, Unity version, or scene-set summary | [Unity project navigation](references/sub-skills/unity-project-navigation.md) | Agent MUST complete the shared entry gate and require a valid `unity_project_path` only for this route. Agent MUST keep exported asset evidence separate from C# behavior evidence, MUST NOT parse or infer behavior from Unity script files, and MUST route behavior questions to the source analyzer. |
| Diagnose BepInEx or Unity logs, startup evidence, or runtime diagnostics | [Log analyzer](references/sub-skills/log-analyzer.md) | Agent MUST complete the shared entry gate and MUST resolve required log sources. Agent MUST report evidence mode, paths, status, and next recovery or verification action. |
| Test a Mod; build/deploy/launch a profile; inspect startup; stop, clean, or verify in-game behavior through Player-performed actions or Computer Use | [Mod-test entry](references/sub-skills/blasphemous-modding-test.md) | Agent MUST classify the request as `Real-profile`, `xUnit`, `both`, or `ambiguous`, then MUST follow the selected branch owner. Agent MUST follow the Mod-test entry's documented Automated xUnit configuration exception. For `both`, Agent MUST keep independent phase reports. |
| Generate, modify, review, or refactor Mod-owned C# or project structure | [Coding standards](references/sub-skills/coding-standards.md) | Agent MUST complete the shared entry gate and selected coding branch. Agent MUST report the ownership boundary and next implementation or verification action. |
| Need ModdingAPI documentation, source guidance, or framework conventions | [Referencing ModdingAPI](references/sub-skills/referencing-modding-api.md) | Agent MUST complete the command-context gate and MUST resolve one local or release-aware reference. Agent MUST report the selected reference/topic and next source or code action. |
| Analyze one explicit Blasphemous 1 save file or directory read-only | [Save analysis](references/sub-skills/save-analysis.md) | Agent MUST follow the Save analysis owner's documented configuration-free input and read-only boundary. |

The shared [Invocation preflight](references/config/invocation-preflight.md) owns the shared entry gate, common completion-report contract, and its own documented configuration exceptions; the [Mod-test entry](references/sub-skills/blasphemous-modding-test.md) owns the Automated xUnit configuration exception. After classifying an operational Blasphemous 1 modding request and completing any gate required by its selected route, the agent MUST consult the [Modding knowledge](references/modding-knowledge.md) index at task start. The read-only localization lookup and Save analysis routes are excluded and MUST NOT run this lookup script. If a matching blocker arises later during an operational route, the agent MUST repeat the lookup. This lookup is advisory and does not change the selected route or its gate. Before applying a retrieved note, the agent MUST compare its game version, Mod version, route, and task with the user's case. If the note does not cover that version or task, or leaves coverage unknown, the agent MUST tell the user and MUST NOT present the claim as verified for that case. Logs alone MUST NOT be described as proof of gameplay behavior.

When the main task identifies an evidence-backed Blasphemous 1 finding that may help beyond the current task, including a future improvement to the current Mod, the agent MUST start the [Experience note comparison](references/sub-skills/experience-note-comparison.md) in an independent child task and continue the main task without waiting for it. The comparison is read-only; it does not request approval, save a note, or create a pull request. At task end, the main task MUST follow [Experience note local save](references/sub-skills/experience-note-local-save.md) for any unique candidates. Only paths returned after an explicit local-save yes may then enter the separately approved [Experience note pull request](references/sub-skills/experience-note-pull-requests.md) workflow.

## Shared entry gate

The [Invocation preflight](references/config/invocation-preflight.md) reference is the sole authority for the shared entry gate, its documented route exceptions, and the common completion-report contract. It delegates detailed setup questions, validation, save operations, and optional local checkout to [First-Time Setup](references/config/first-time-setup.md). It routes Python interpreter and dependency validation to [Python Runtime](references/config/python-runtime.md). The [Dependencies](references/config/invocation-preflight.md#dependencies) section contains the canonical post-install package and conditional workflow dependency inventory.

## Coding standards

The [Coding-standards sub-skill](references/sub-skills/coding-standards.md) is the sole entry point for Mod-owned C# and selects the applicable branch references. Agent MUST follow it for every applicable coding task in caller's Mod repository.

## Workflow

Agent MUST follow workflow steps in order, unless otherwise explicitly specified by user.

### Step 1: Complete shared entry gate

Agent MUST complete the shared entry gate before selecting an operational specialized branch or executing command. When a selected route documents a configuration exception, Agent MUST follow that route owner's exception.

**Done when**: the shared entry gate's completion criteria are satisfied, or the selected route owner has confirmed its documented exception and required entry context.

### Step 2: Analyze User Question

Agent MUST apply the Request routing rules above and route every applicable branch to its owning reference before gathering evidence.

Where useful to clarify the request, agent SHOULD identify the desired observable outcome and evidence relevant to the selected route, especially for Mod feature requests with a visible or persistent result. Route-specific completion criteria and evidence boundaries remain authoritative.

**Done when**: user question is classified into one or more applicable branches (localization lookup, save analysis, source code analysis, Unity project navigation, log analysis, mod testing, or general modding question), and every applicable specialized branch has been routed to its authoritative workflow reference or analysis task.

### Step 3: Use Tools to Gather Information

For an operational branch, Agent MUST use tools to gather information required by task, including:

- source-analyzer and log-analyzer when they are applicable;
- coding standards and its selected branch references;
- Unity API and ModdingAPI references routed by relevant sub-skills.

Tools' `.md` files SHOULD contain all path specifications required for task. Agent MUST NOT ask user for path again unless needed path information is absent there. When the selected route documents a configuration exception, Agent MUST follow only that route owner's exception boundary and MUST NOT enter the shared configuration path.

**Done when**: for an operational branch, agent has located every path task needs (source code, modding profile, and logs) in `config.yml` or navigation documents, and has handed any missing or stale path to Step 5; or, for a route with a documented exception, the route owner's required input and context are confirmed.

### Step 4: Solve User Question

Agent MUST use gathered information to solve user question.

If repeating the same approach yields no new evidence, Agent MUST pause, summarize what was checked and learned, identify remaining unknowns, then change approach or request the specific user action or information needed to proceed.

**Done when**: every selected route's owner-defined completion criteria have been satisfied, or the Agent has reported the route owner's truthful incomplete status and next action without claiming completion, and the Agent has verified every cited path, artifact, and evidence value against its actual file or run output.

### Step 5: Path Failure Recovery

For an operational branch, Agent MUST follow the path-failure recovery contract in the shared entry gate. A route with a documented configuration exception MUST follow its route owner's failure handling and MUST NOT enter configuration recovery.

**Done when**: the operational branch recovery contract has produced a validated configuration file, or agent has continued with current paths and reported specific failure and next action; or a route with a documented configuration exception has reported its route owner's specific failure and next action.
