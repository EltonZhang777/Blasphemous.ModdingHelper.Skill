---
name: blasphemous-modding-helper
description: Blasphemous modding development helper. Use when user specifies developing a Blasphemous mod.
---

# Blasphemous modding helper

You are helping with Blasphemous mod development.

## Coding specifications

- Game source code language and modding language: C#
- Game Unity version: Unity 2017.4.40f1
  - You MAY search for Unity 2017.4.40f1 API documentation in the Unity Documentation at `https://docs.unity3d.com/2017.4/Documentation/ScriptReference/30_search.html?q=<class-name-or-method-name>` for extra information. Replace `<class-name-or-method-name>` with the actual class or method name you are searching for.
- Mods are developed under the Blasphemous ModdingAPI framework. You MUST follow the ModdingAPI conventions and best practices.
  - ModdingAPI documentation can be found at `https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/main/docs`
  - ModdingAPI source code can be found at `https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/main`

## Preferences (`preferences.md`)

Check `preferences.md` existence (priority order):

```bash
# macOS, Linux, WSL, Git Bash
test -f .skills/blasphemous-modding-helper/preferences.md && echo "project"
```

```powershell
# PowerShell (Windows)
if (Test-Path .skills/blasphemous-modding-helper/preferences.md) { "project" }
$xdg = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { "$HOME/.config" }
if (Test-Path "$xdg/skills/blasphemous-modding-helper/preferences.md") { "xdg" }
if (Test-Path "$HOME/.skills/blasphemous-modding-helper/preferences.md") { "user" }
```

| Path | Location |
|------|----------|
| `.skills/blasphemous-modding-helper/preferences.md` | Project directory |
| `$HOME/.skills/blasphemous-modding-helper/preferences.md` | User home |

| Result | Action |
|--------|--------|
| Found | Read, parse, apply settings. On first use in session, briefly remind: "Using preferences from [path]. You can edit `preferences.md` to customize source code path, etc." |
| Not found | **MUST** run first-time setup (see below) — do NOT silently use defaults |

**`preferences.md` Documents**: 
- full_source_code_path
- lightweight_source_code_path
- modding_profile_path

Schema for `preferences.md`: [references/config/preferences-schema.md](references/config/preferences-schema.md)

### First-Time Setup (BLOCKING)

**CRITICAL**: When `preferences.md` is not found, you **MUST** run the first-time setup before ANY action. This is a **BLOCKING** operation.

You **MUST** reference [references/config/first-time-setup.md](references/config/first-time-setup.md) for first-time setup.


## Workflow

You **MUST** follow the workflow steps in order, unless otherwise explicitly specified by the user.

### Step 1: Load Preferences

Check `preferences.md` (see Preferences section above)

### Step 2: Analyze User Question

Analyze the user question to determine user intent and the task to perform, especially pay attention to the following:
- Whether the user request involves analying Blasphemous Source code. 
  - If yes, you SHOULD create a sub-agent or sub-task to handle the source code analysis using [references/sub-skills/source-analyzer.md](references/sub-skills/source-analyzer.md)
- Whether the user request involves debugging, log tracking, or error tracking.
  - If yes, you SHOULD create a sub-agent or sub-task to handle log analysis using [references/sub-skills/log-analyzer.md](references/sub-skills/log-analyzer.md)

### Step 3: Use Tools to Gather Information

Use tools to gather information required for the task, including:
- source-analyzer and log-analyzer
  - mentioned in `### Step 2: Analyze User Question`
- Unity API documentation and ModdingAPI documentation
  - mentioned in the `## Coding specifications` section above
 
### Step 4: Solve User Question

Use the gathered information to solve the user question.