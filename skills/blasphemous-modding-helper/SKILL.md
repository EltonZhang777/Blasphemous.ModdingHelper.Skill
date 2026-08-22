---
name: blasphemous-modding-helper
description: Blasphemous modding development helper. Use when user wants to develop a Blasphemous mod, analyze Blasphemous decompiled source code, or debug mod-related logs (BepInEx / Unity).
---

# Blasphemous modding helper

You are helping with Blasphemous mod development.

## Coding specifications

- Game source code language and modding language: C#
- Game Unity version: Unity 2017.4.40f1
  - You MAY search for Unity 2017.4.40f1 API documentation in the Unity Documentation at `https://docs.unity3d.com/2017.4/Documentation/ScriptReference/30_search.html?q=<class-name-or-method-name>` for extra information. Replace `<class-name-or-method-name>` with the actual class or method name you are searching for.
- Mods are developed under the Blasphemous ModdingAPI framework. You **MUST** follow the ModdingAPI conventions and best practices **WHENEVER YOU CODE** by browsing the links below.
  - ModdingAPI documentation can be found at `https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/main/docs`
  - ModdingAPI source code can be found at `https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/main`
- Before generating or modifying Mod-owned C# in a caller's Mod repository, read [C# and Modding Standards](references/coding-standards.md). It defines the local C# baseline, the complete `BlasMod` lifecycle, Harmony patch ownership, exceptions, and examples. Do not apply it to decompiled, upstream, dependency, generated, or directly copied code that the caller cannot modify.

## Preferences (`preferences.md`)

Check `preferences.md` existence.

Use the check-preferences scripts to find `preferences.md`:

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
| Found | Read, parse, apply settings. On first use in session, briefly remind: "Using preferences from [path]. You can edit `preferences.md` to customize source code path, etc." |
| Not found | **MUST** run first-time setup (see below) — do NOT silently use defaults, do NOT continue to main workflow. |

**`preferences.md` Contains**: `full_source_code_path`, `lightweight_source_code_path`, `modding_profile_path` — see [references/config/preferences-schema.md](references/config/preferences-schema.md) for the full schema.

### First-Time Setup (BLOCKING)

**CRITICAL**: When `preferences.md` is not found, you **MUST** run the first-time setup (a **BLOCKING** operation) before ANY action, following [references/config/first-time-setup.md](references/config/first-time-setup.md).


## Workflow

You **MUST** follow the workflow steps in order, unless otherwise explicitly specified by the user.

### Step 1: Load Preferences

Check `preferences.md` (see Preferences section above)

### Step 2: Analyze User Question

Analyze the user question to determine user intent and the task to perform, especially pay attention to the following:
- Whether the user request involves analyzing Blasphemous Source code. 
  - If yes, you SHOULD create a sub-agent or sub-task to handle the source code analysis using [references/sub-skills/source-analyzer.md](references/sub-skills/source-analyzer.md)
- Whether the user request involves debugging, log tracking, or error tracking.
  - If yes, you SHOULD create a sub-agent or sub-task to handle log analysis using [references/sub-skills/log-analyzer.md](references/sub-skills/log-analyzer.md)

**Done when**: the user question is classified into one of the three branches (source code analysis, log analysis, or general modding question), and a sub-agent task has been created for every branch that applies.

### Step 3: Use Tools to Gather Information

Use tools to gather information required for the task, including:
- source-analyzer and log-analyzer
  - mentioned in `### Step 2: Analyze User Question`
- Unity API documentation and ModdingAPI documentation
  - mentioned in the `## Coding specifications` section above

The tools' `.md` files should contain all the path specifications required for the task; do not ask user for path again unless you don't find the path information you need there.

**Done when**: every path the task needs (source code, modding profile, logs) has been located in `preferences.md` or the navigation documents, and any missing or stale path has been handed to Step 5.

### Step 4: Solve User Question

Use the gathered information to solve the user question.

**Done when**: the answer is complete and every source-code class, file path, and log location cited in the answer has been verified against the actual files.

### Step 5: Path Failure Recovery

If any source code analysis or modding operation fails with file-not-found or path-related errors, the agent MUST ask the user: "Some operations failed using the saved paths in `preferences.md`. Would you like to re-run the first-time setup to update them?"

- **If Yes**: Delete `preferences.md` and trigger first-time setup again (see Step 1). This allows the user to correct outdated or incorrect paths.
- **If No**: Continue with current paths, report the specific failure to the user.
