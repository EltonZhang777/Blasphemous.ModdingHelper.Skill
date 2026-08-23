---
name: blasphemous-modding-helper
description: Blasphemous modding development helper. Use when the user wants to build, deploy, launch, inspect startup evidence, stop, clean, or perform Manual verification for a Blasphemous mod; develop a mod, analyze Blasphemous decompiled source code, or debug mod-related logs (BepInEx / Unity).
---

# Blasphemous modding helper

You are helping with Blasphemous mod development.

## Requirement levels

At the start of every Skill invocation, you MUST read [Requirement levels](references/requirement-levels-definitions.md). It defines the RFC 2119 vocabulary used by every authored normative instruction in this Skill; external documentation, source code, and illustrative examples retain their original wording as described there.

## Coding standards

Before generating, modifying, reviewing, or refactoring Mod-owned C# in a caller's Mod repository, you MUST read the [coding standards](references/sub-skills/coding-standards.md). It applies the ownership gate, routes C# and runtime Unity work to the [C# and runtime Unity standards](references/coding-standards-csharp-unity.md), ModdingAPI tasks to the [ModdingAPI standards](references/coding-standards-moddingAPI.md), and Harmony or Patch tasks to the [Harmony patching standards](references/coding-standards-harmony-patching.md).

- Game source code language and Mod language: C#.
- Game Unity baseline: Unity `2017.4.40f1`.
  - The agent MAY search the Unity 2017.4.40f1 API documentation at `https://docs.unity3d.com/2017.4/Documentation/ScriptReference/30_search.html?q=<class-name-or-method-name>` for extra information. The agent SHOULD replace `<class-name-or-method-name>` with the actual class or method name.
- ModdingAPI documentation, source guidance, conventions, lifecycle, logging, and examples MUST pass through [Referencing ModdingAPI](references/sub-skills/referencing-modding-api.md) before the agent browses the selected reference.
  - The route selects a configured local checkout or resolves the release-aware remote reference, then loads only the topic needed for the task.
- Mods are developed under the Blasphemous ModdingAPI framework. The agent MUST follow the ModdingAPI conventions and best practices whenever it codes against the selected reference.

## Preferences (`preferences.md`)

The agent MUST check whether `preferences.md` exists.

The agent MUST use the check-preferences scripts to find `preferences.md`:

```bash
# macOS, Linux, WSL, Git Bash
bash scripts/check_preferences.sh
```

```powershell
# PowerShell (Windows)
& .\scripts\check_preferences.ps1
```

Output is one of: `"project"`, `"user"`, or nothing (not found).

`preferences.md` lives at `.skills/blasphemous-modding-helper/preferences.md` (project) or `$HOME/.skills/blasphemous-modding-helper/preferences.md` (user home). Full locations table: [references/config/first-time-setup.md#save-locations](references/config/first-time-setup.md#save-locations).

| Result | Action |
|--------|--------|
| Found | The agent MUST read, parse, and apply the settings. On first use in the session, it SHOULD briefly remind the user: "Using preferences from [path]. You can edit `preferences.md` to customize source code path, etc." |
| Not found | The agent MUST run first-time setup (see below) and MUST NOT silently use defaults or continue to the main workflow. |

**`preferences.md` Contains**: `full_source_code_path`, `lightweight_source_code_path`, `modding_profile_path`, optional `unity_log_dir`, and optional ModdingAPI reference fields — see [references/config/preferences-schema.md](references/config/preferences-schema.md) for the full schema. Use [Referencing ModdingAPI](references/sub-skills/referencing-modding-api.md) for reference selection, remote fallback, lock state, offline checks, and explicit lifecycle operations.

### First-Time Setup (BLOCKING)

**CRITICAL**: When `preferences.md` is not found, you MUST run the first-time setup (a BLOCKING operation) before source analysis, modding operations, or any test command, following [references/config/first-time-setup.md](references/config/first-time-setup.md). The only narrow recovery exception is `/blasphemous-modding-test stop SESSION_ID`: it uses the recorded session identity, does not load or edit preferences, and may stop only that tracked process tree when normal context preflight is unavailable. All other test commands remain blocked until setup completes.

## Workflow

You MUST follow the workflow steps in order, unless otherwise explicitly specified by the user.

### Step 1: Load Preferences

The agent MUST follow the Preferences gate above.

**Done when**: the check-preferences result is `project` or `user` and the selected file has been read, parsed, and applied, or first-time setup has completed. For the tracked-session stop exception, this step is complete when the recorded process is stopped or confirmed gone without loading preferences.

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

If any source code analysis or modding operation fails with file-not-found or path-related errors, the agent MUST ask the user: "Some operations failed using the saved paths in `preferences.md`. Would you like to re-run the first-time setup to update them?"

- **If Yes**: The agent MUST delete `preferences.md` and trigger first-time setup again (see Step 1). This allows the user to correct outdated or incorrect paths.
- **If No**: The agent MUST continue with the current paths and report the specific failure to the user.

**Done when**: either setup has produced a validated preferences file, or the agent has continued with the current paths and reported the specific failure. The tracked-session stop exception is complete when the recorded process is stopped or confirmed gone and no unrelated process was touched.
