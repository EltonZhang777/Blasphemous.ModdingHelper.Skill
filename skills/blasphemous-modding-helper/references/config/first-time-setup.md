---
name: first-time-setup
description: First-time setup flow for blasphemous-modding-helper preferences
---

# First-Time Setup

## Overview

When no `preferences.md` is found, this reference describes the preference-setup flow.

**BLOCKING OPERATION**: This setup MUST complete before ANY action. The agent MUST NOT:
- The agent MUST NOT analyze the user's question.
- The agent MUST NOT proceed to any workflow steps.

The agent MUST ask only the questions in this setup flow, MUST save `preferences.md`, and MUST continue only after those steps complete.

## Setup Flow

```text
1. No `preferences.md` found

2. The agent MUST ask the save-location AskUserQuestion (see Q1).
   ─── Asked first to avoid "auto-write" destination conflict ───

3. The agent MUST ask: "Do you have decompiled Blasphemous source code?" (see Q2).
   │
   ├─ Yes → the agent MUST enter the manual path flow:
   │   4. The agent MUST ask for the lightweight source code path (see Q3; REQUIRED).
   │      ├─ Validate fail → the agent MUST retry Q3
   │      └─ OK → the agent MUST continue
   │   5. The agent MUST ask: "Do you also have full source code?" (see Q4).
   │      ├─ Yes → the agent MUST ask for the full source code path (see Q4b)
   │      └─ No  → the agent MAY skip Q4b
   │   6. The agent MUST ask for the modding profile path (see Q5).
   │   7. The agent MUST validate all paths (lightweight MUST exist).
   │      ├─ Fail → the agent MUST retry the corresponding single question
   │      └─ OK → the agent MAY continue
   │   8. The agent MUST create `preferences.md`.
   │   9. The agent MUST continue.
   │
   └─ No (run decompiler) → the agent MUST run the decompile script synchronously
       (Windows: `scripts/decompile_source.ps1` ; macOS/Linux: `scripts/decompile_source.sh`)
       ├─ Success →
       │   lightweight_source_code_path = <skill-root>/source_code/ (auto-set)
       │   5. The agent MUST ask: "Do you also have full source code?" (see Q4).
       │      ├─ Yes → the agent MUST ask for the full source code path (see Q4b)
       │      └─ No  → the agent MUST skip Q4b
       │   6. The agent MUST ask for the modding profile path (see Q5).
       │   8. The agent MUST create `preferences.md`.
       │   9. The agent MUST continue.
       │
       └─ Failed (exit code != 0) →
           The agent MUST report error details to the user.
           The agent MUST ask: "Decompilation failed. Provide source paths manually?"
           ├─ Yes → the agent MUST enter manual path flow at step 4 (Q3).
           └─ No  → the agent MUST abort setup and instruct the user to fix the error and retry.
```

## AskUserQuestion Questions

**Language of AskUserQuestion Questions**: you SHOULD attempt to use the user's input language or language preference of the editor/cli they're using when asking questions.
- This means you SHOULD attempt to translate the questions' header, question, options, etc. However, you SHOULD NEVER translate the user input or any file, path, etc.
- The agent SHOULD default to English only when the user's input language is not available.

The agent MUST use AskUserQuestion with **ALL applicable** questions in **ONE** call:
- If the user answered "Yes" to Q2, the agent MUST ask Q1 + Q2 + Q3 + Q4 + Q5 + save location = 5 questions.
- If the user answered "No" to Q2, the agent MUST ask Q1 + Q2 + Q4 + Q5 + save location = 4 questions (Q3 is auto-filled).

### Q1: Save Location

```yaml
header: "Save"
question: "Where to save preferences?"
options:
  - label: "User (Recommended)"
    description: "$HOME/.skills/blasphemous-modding-helper/preferences.md in user home — available across projects"
  - label: "Project"
    description: ".skills/blasphemous-modding-helper/preferences.md in project — scoped to this repository"
```

Note: The agent MUST ask this first so auto-write for the decompile branch knows the destination.

### Q2: Decompiled Source Branch

```yaml
header: "decompiled source"
question: "Do you have decompiled Blasphemous source code?"
options:
  - label: "No (run decompiler)"
    description: "Automatically decompile game DLLs from Steam installation"
  - label: "Yes"
    description: "I already have decompiled source code, I will provide paths"
```

- When the user selects **No**, the agent MUST run the decompile script synchronously:
  - **Windows**: `scripts/decompile_source.ps1`
  - **macOS/Linux**: `scripts/decompile_source.sh`
  On success, `lightweight_source_code_path` is auto-filled to `<skill-root>/source_code/`. On failure, the agent MUST prompt the user whether to provide paths manually.
- When the user selects **Yes**, the agent MUST enter the manual path flow.

### Q3: Lightweight Source Code Path

```yaml
header: "lightweight source code path"
question: "Where is your lightweight source code of decompiled Blasphemous project's core files?"
options: a user-input path
```

Note:
- This is the **MINIMUM required field**. At least lightweight MUST be set.
- For the decompile branch (Q2 = No), this path is auto-determined — the agent MUST skip this question.

### Q4: Full Source Code (optional)

```yaml
header: "full source needed"
question: "Do you also have full decompiled Blasphemous source code (.sln with all projects)?"
options:
  - label: "Yes"
    description: "Provide full source code path"
  - label: "No"
    description: "Skip full source code, proceed with lightweight source only"
```

Note: The agent MUST ask this only if lightweight source code is already provided (manually or via decompile). This field is purely optional.

### Q4b: Full Source Code Path (conditional)

```yaml
header: "full source code path"
question: "Where is your full source code of decompiled Blasphemous project?"
options: a user-input path
```

Note: The agent MUST ask this only if the user answered "Yes" to Q4.

### Q5: Modding Profile Path

```yaml
header: "modding profile path"
question: "Where is your Blasphemous modding profile root path?"
options: a user-input path
```

Note: This path MUST be entered manually in all branches. The modding profile is typically a full game copy, not part of the original game installation, so it cannot be auto-detected from the game path.

## Validate User Input

The agent MUST validate whether the user-input paths exist and are valid using command-line tools.

Validation criteria:
- All branches:
  - `lightweight_source_code_path` **MUST** exist — validate that the root path exists; it SHOULD ideally contain an `.sln` file
  - `full_source_code_path` (if provided) — validate that the root path exists; it SHOULD ideally contain an `.sln` file
  - `modding_profile_path` (if provided) — it SHOULD contain `Blasphemous.exe` and a `Modding` folder
- If any check fails, the agent MUST return to the **corresponding single question** (not the entire flow):
  - Lightweight fail → retry Q3 only
  - Full fail (if provided) → retry Q4b only
  - Modding profile fail → retry Q5 only
- Decompile branch: script exit code 0 validates lightweight automatically

**Script failure handling** (Q2 = No, script exit code != 0):
1. The agent MUST display the script's error output to the user.
2. The agent MUST ask: "Decompilation failed. Would you like to provide source paths manually instead?"
   - Yes → the agent MUST enter manual path flow at Q3 (lightweight).
   - No → the agent MUST abort setup and instruct the user to resolve the error and retry.

## Save Locations

| Choice | Path | Scope |
|--------|------|-------|
| Project | `.skills/blasphemous-modding-helper/preferences.md` | Project directory |
| User | `$HOME/.skills/blasphemous-modding-helper/preferences.md` | User home |

## Setup Workflow After User-questions

1. The agent MUST create the directory if needed.
2. The agent MUST write `preferences.md` with the selected values.
3. The agent MUST confirm: "Preferences saved to [path], you can edit it by yourself at any time."
4. The agent MUST continue the main agent workflow using the saved preferences.

## `preferences.md` Template

The agent MUST read [preferences-schema.md](preferences-schema.md) for detailed template restrictions.

## Modifying Preferences Later

Users can edit `preferences.md` directly or delete it to trigger setup again.
