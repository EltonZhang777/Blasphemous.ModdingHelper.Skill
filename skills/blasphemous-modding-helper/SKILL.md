---
name: blasphemous-modding-helper
description: Blasphemous modding development helper. Use when user wants to develop a Blasphemous mod, analyze Blasphemous decompiled source code, or debug mod-related logs (BepInEx / Unity).
---

# Blasphemous modding helper

You are helping with Blasphemous mod development.

## Requirement levels

At the start of every Skill invocation, you MUST read [Requirement levels](references/requirement-levels-definitions.md). It defines the RFC 2119 vocabulary used by every authored normative instruction in this Skill; external documentation, source code, and illustrative examples retain their original wording as described there.

## Coding standards

Before generating, modifying, reviewing, or refactoring Mod-owned C# in a caller's Mod repository, you MUST read the [coding standards](references/sub-skills/coding-standards.md). It applies the ownership gate, routes C# and runtime Unity work to the [C# and runtime Unity standards](references/coding-standards-csharp-unity.md), ModdingAPI tasks to the [ModdingAPI standards](references/coding-standards-moddingAPI.md), and Harmony or Patch tasks to the [Harmony patching standards](references/coding-standards-harmony-patching.md).

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

**`preferences.md` Contains**: `full_source_code_path`, `lightweight_source_code_path`, `modding_profile_path` — see [references/config/preferences-schema.md](references/config/preferences-schema.md) for the full schema.

### First-Time Setup (BLOCKING)

**CRITICAL**: When `preferences.md` is not found, you **MUST** run the first-time setup (a **BLOCKING** operation) before ANY action, following [references/config/first-time-setup.md](references/config/first-time-setup.md).


## Workflow

You **MUST** follow the workflow steps in order, unless otherwise explicitly specified by the user.

### Step 1: Load Preferences

The agent MUST check `preferences.md` (see Preferences section above).

### Step 2: Analyze User Question

The agent MUST analyze the user question to determine user intent and the task to perform, especially paying attention to the following:
- Whether the user request involves analyzing Blasphemous Source code. 
  - If yes, the agent SHOULD create a sub-agent or sub-task to handle the source code analysis using [references/sub-skills/source-analyzer.md](references/sub-skills/source-analyzer.md).
- Whether the user request involves debugging, log tracking, or error tracking.
  - If yes, the agent SHOULD create a sub-agent or sub-task to handle log analysis using [references/sub-skills/log-analyzer.md](references/sub-skills/log-analyzer.md).

**Done when**: the agent has classified the user question into one of the three branches (source code analysis, log analysis, or general modding question) and has created a sub-agent task for every branch that applies.

### Step 3: Use Tools to Gather Information

The agent MUST use tools to gather information required for the task, including:
- source-analyzer and log-analyzer
  - mentioned in `### Step 2: Analyze User Question`
- The coding standards and its selected branch references
  - mentioned in the `## Coding standards` section above

The tools' `.md` files SHOULD contain all path specifications required for the task. The agent MUST NOT ask the user for a path again unless the needed path information is absent there.

**Done when**: the agent has located every path the task needs (source code, modding profile, and logs) in `preferences.md` or the navigation documents, and has handed any missing or stale path to Step 5.

### Step 4: Solve User Question

The agent MUST use the gathered information to solve the user question.

**Done when**: the answer is complete and the agent has verified every source-code class, file path, and log location cited in the answer against the actual files.

### Step 5: Path Failure Recovery

If any source code analysis or modding operation fails with file-not-found or path-related errors, the agent MUST ask the user: "Some operations failed using the saved paths in `preferences.md`. Would you like to re-run the first-time setup to update them?"

- **If Yes**: The agent MUST delete `preferences.md` and trigger first-time setup again (see Step 1). This allows the user to correct outdated or incorrect paths.
- **If No**: The agent MUST continue with the current paths and report the specific failure to the user.
