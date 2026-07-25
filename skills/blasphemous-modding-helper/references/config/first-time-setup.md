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

```text
1. No `preferences.md` found

2. AskUserQuestion: save location (see Q1)
   ─── Asked first to avoid "auto-write" destination conflict ───

3. AskUserQuestion: "Do you have decompiled Blasphemous source code?" (see Q2)
   │
   ├─ Yes → enter manual path flow:
   │   4. AskUserQuestion: lightweight source code path (see Q3; REQUIRED)
   │      ├─ Validate fail → retry Q3
   │      └─ OK → continue
   │   5. AskUserQuestion: "Do you also have full source code?" (see Q4)
   │      ├─ Yes → AskUserQuestion: full source code path (see Q4b)
   │      └─ No  → skip
   │   6. AskUserQuestion: modding profile path (see Q5)
   │   7. Validate all paths (lightweight MUST exist)
   │      ├─ Fail → retry corresponding single question
   │      └─ OK → continue
   │   8. Create `preferences.md`
   │   9. Continue
   │
   └─ No (run decompiler) → run decompile script synchronously
       (Windows: `scripts/decompile_source.ps1` ; macOS/Linux: `scripts/decompile_source.sh`)
       ├─ Success →
       │   lightweight_source_code_path = <skill-root>/source_code/ (auto-set)
       │   5. AskUserQuestion: "Do you also have full source code?" (see Q4)
       │      ├─ Yes → AskUserQuestion: full source code path (see Q4b)
       │      └─ No  → skip
       │   6. AskUserQuestion: modding profile path (see Q5)
       │   8. Create `preferences.md`
       │   9. Continue
       │
       └─ Failed (exit code != 0) →
           Report error details to user
           AskUser: "Decompilation failed. Provide source paths manually?"
           ├─ Yes → enter manual path flow at step 4 (Q3)
           └─ No  → abort setup, instruct user to fix error and retry
```

## AskUserQuestion Questions

**Language of AskUserQuestion Questions**: you SHOULD attempt to use the user's input language or language preference of the editor/cli they're using when asking questions.
- This means you SHOULD attempt to translate the questions' header, question, options, etc. However, you SHOULD NEVER translate the user input or any file, path, etc.
- Default to English only when user's input language is not available.

Use AskUserQuestion with **ALL applicable** questions in **ONE** call:
- If user answered "Yes" to Q2: ask Q1 + Q2 + Q3 + Q4 + Q5 + save location = 5 questions
- If user answered "No" to Q2: ask Q1 + Q2 + Q4 + Q5 + save location = 4 questions (Q3 auto-filled)

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

Note: Asked first so auto-write for decompile branch knows destination.

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

- User selects **No**: Agent runs the decompile script synchronously:
  - **Windows**: `scripts/decompile_source.ps1`
  - **macOS/Linux**: `scripts/decompile_source.sh`
  On success, `lightweight_source_code_path` is auto-filled to `<skill-root>/source_code/`. On failure, prompt user whether to provide paths manually.
- User selects **Yes**: Enter manual path flow.

### Q3: Lightweight Source Code Path

```yaml
header: "lightweight source code path"
question: "Where is your lightweight source code of decompiled Blasphemous project's core files?"
options: a user-input path
```

Note:
- This is the **MINIMUM required field**. At least lightweight MUST be set.
- For the decompile branch (Q2 = No), this path is auto-determined — skip this question.

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

Note: Only ask this if lightweight source code is already provided (manually or via decompile). This field is purely optional.

### Q4b: Full Source Code Path (conditional)

```yaml
header: "full source code path"
question: "Where is your full source code of decompiled Blasphemous project?"
options: a user-input path
```

Note: Only ask if user answered "Yes" to Q4.

### Q5: Modding Profile Path

```yaml
header: "modding profile path"
question: "Where is your Blasphemous modding profile root path?"
options: a user-input path
```

Note: This path must be entered manually in all branches. The modding profile is typically a full game copy, not part of the original game installation, so it cannot be auto-detected from the game path.

## Validate User Input

Validate if the user input paths exist and are valid using command-line tools.

Validation criteria:
- All branches:
  - `lightweight_source_code_path` **MUST** exist (required) — validate root path exists, should ideally contain `.sln` file
  - `full_source_code_path` (if provided) — validate root path exists, should ideally contain `.sln` file
  - `modding_profile_path` (if provided) — should contain `Blasphemous.exe` and `Modding` folder
- If any check fails, revert to the **corresponding single question** (not the entire flow):
  - Lightweight fail → retry Q3 only
  - Full fail (if provided) → retry Q4b only
  - Modding profile fail → retry Q5 only
- Decompile branch: script exit code 0 validates lightweight automatically

**Script failure handling** (Q2 = No, script exit code != 0):
1. Display the script's error output to the user
2. Ask: "Decompilation failed. Would you like to provide source paths manually instead?"
   - Yes → enter manual path flow at Q3 (lightweight)
   - No → abort setup, instruct user to resolve error and retry

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
