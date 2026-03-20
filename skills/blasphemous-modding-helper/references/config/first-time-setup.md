---
name: first-time-setup
description: First-time setup flow for blasphemous-modding-helper preferences
---

# First-Time Setup

## Overview

When no `preferences.md` is found, guide user through preference setup.

**BLOCKING OPERATION**: This setup MUST complete before ANY action. Do NOT:
- Analyze user question
- Proceed to any workflow steps

ONLY ask the questions in this setup flow, save `preferences.md`, and then continue.

## Setup Flow

```
No `preferences.md` found
        |
        v
+---------------------+
| AskUserQuestion     |
| (all questions)     |
+---------------------+
        |
        v
+---------------------+
| Validate User Input |
|   Are paths valid?  |
+---------------------+
        |
        |
        |-------- No ----------> AskUserQuestion again until input is checked to be valid
        |
        |  Yes
        |
        v
+--------------------------+
| Create `preferences.md`  |
+--------------------------+
        |
        v
    Continue
```

## AskUserQuestion Questions

**Language**: Use user's input language or language preference of the editor/cli they're using.

Use AskUserQuestion with ALL questions in ONE call:

### Question 1: Full Source Code Path

```yaml
header: "full source code path"
question: "Where is your full source code of decompiled Blasphemous project?"
options: a user-input path
```

Note: You SHOULD prompt user to input the full source code path.

### Question 2: Lightweight Source Code Path

```yaml
header: "lightweight source code path"
question: "Where is your lightweight source code of decompiled Blasphemous project's core files?"
options: a user-input path
```

Note: You SHOULD prompt user to input the lightweight source code path.

### Question 3: Modding Profile Path

```yaml
header: "modding profile path"
question: "Where is your Blasphemous modding profile root path?"
options: a user-input path
```

Note: You SHOULD prompt user to input the modding profile path.

### Question 4: Save Location

```yaml
header: "Save"
question: "Where to save preferences?"
options:
  - label: "User (Recommended)"
    description: "$HOME/.skills/blasphemous-modding-helper/preferences.md in user home"
  - label: "Project"
    description: ".skills/blasphemous-modding-helper/preferences.md in project"
```

## Validate User Input

Validate if the user input paths exist and are valid using command-line tools. 

Validation criteria:
- At least one of `full_source_code_path` or `lightweight_source_code_path` must be valid.
  - `full_source_code_path` is the root path storing all source code files, should better be containing `.sln` file.
  - `lightweight_source_code_path` is the root path storing only key source code files like `Assembly-CSharp.dll`, should better be containing `.sln` file
- `modding_profile_path` is the root path storing all modding profile files, SHOULD contain `Blasphemous.exe` and `Modding` folder

If any check failed, revert to the AskUserQuestion step again (reference process above).

## Save Locations

| Choice | Path | Scope |
|--------|------|-------|
| Project | `.skills/blasphemous-modding-helper/preferences.md` | Project directory |
| User | `$HOME/.skills/blasphemous-modding-helper/preferences.md` | User home |

## Setup Workflow After User-questions

1. Create directory if needed
2. Write preferences.md with selected values
3. Confirm: "Preferences saved to [path], you can edit it by yourself at any time."
4. Continue main agent workflow using saved preferences

## `preferences.md` Template

see [preferences-schema.md](preferences-schema.md) for detailed template restrictions.

## Modifying Preferences Later

Users can edit `preferences.md` directly or delete it to trigger setup again.
