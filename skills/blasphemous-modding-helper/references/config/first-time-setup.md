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
   │   7. AskUserQuestion: configure a local ModdingAPI reference (see Q6)
   │      ├─ Yes → use the selected preferences scope, choose a selector, and run the fresh-clone command
   │      │        ├─ Success → record normalized path and selector
   │      │        └─ Failure → show the terminal error report and do not add fields
   │      └─ Skip → leave local reference fields absent; remote fallback remains available
   │   8. Validate all paths (lightweight MUST exist)
   │      ├─ Fail → retry corresponding single question
   │      └─ OK → continue
   │   9. Create or update `preferences.md`
   │   10. Continue
   │
   └─ No (run decompiler) → run decompile script synchronously
       (Windows: `scripts/decompile_source.ps1` ; macOS/Linux: `scripts/decompile_source.sh`)
       ├─ Success →
       │   lightweight_source_code_path = <skill-root>/source_code/ (auto-set)
       │   5. AskUserQuestion: "Do you also have full source code?" (see Q4)
       │      ├─ Yes → AskUserQuestion: full source code path (see Q4b)
       │      └─ No  → skip
       │   6. AskUserQuestion: modding profile path (see Q5)
       │   7. AskUserQuestion: configure a local ModdingAPI reference (see Q6)
       │      ├─ Yes → use the selected preferences scope, choose a selector, and run the fresh-clone command
       │      └─ Skip → leave local reference fields absent
       │   8. Validate all paths (lightweight MUST exist)
       │   9. Create or update `preferences.md`
       │   10. Continue
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
- If user answered "Yes" to Q2: ask Q1 + Q2 + Q3 + Q4 + Q5 + Q6 + save location = 6 questions
- If user answered "No" to Q2: ask Q1 + Q2 + Q4 + Q5 + Q6 + save location = 5 questions (Q3 auto-filled)

### Q1: Save Location

```yaml
header: "Save"
question: "Where to save preferences?"
options:
  - label: "User (Recommended)"
    description: "User scope; see preferences-schema.md#approved-local-reference-locations — available across projects"
  - label: "Project"
    description: "Project scope; see preferences-schema.md#approved-local-reference-locations — scoped to this repository"
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

### Q6: Local ModdingAPI Reference

```yaml
header: "local ModdingAPI reference"
question: "Configure a local ModdingAPI reference checkout?"
options:
  - label: "Yes (Recommended)"
    description: "Clone a shallow, reproducible checkout and save its absolute path and selector in preferences.md"
  - label: "Skip"
    description: "Leave local reference fields absent and use the release-aware remote fallback"
```

If the user selects **Yes**, use the same scope selected in Q1. Do not select
an independent reference scope: the local reference and its preferences must
stay in the same scope domain. The approved paths are authoritative in
[preferences-schema.md#approved-local-reference-locations](preferences-schema.md#approved-local-reference-locations).

```yaml
header: "reference selector"
question: "Which ModdingAPI reference should be cloned?"
options:
  - label: "latest (Recommended)"
    description: "Newest non-draft, non-prerelease GitHub Release"
  - label: "Exact tag"
    description: "Reproduce a named Release tag with tag:REF"
  - label: "Explicit branch or commit"
    description: "Use branch:REF or commit:SHA for deliberate development or source pinning"
```

For **Exact tag**, collect the tag name and pass `tag:REF`. For an explicit
branch or commit, collect the branch name or 40-character SHA and pass
`branch:REF` or `commit:SHA`. `latest` needs no additional value.

Run the matching fresh-clone command from the skill directory:

```bash
bash scripts/clone_modding_api.sh --scope user --selector latest
```

```powershell
& .\scripts\clone_modding_api.ps1 -Scope user -Selector latest
```

Use `--scope project` / `-Scope project` when Q1 selected Project; use User
when Q1 selected User. The clone command refuses an existing target, uses shallow history by default, checks out
tags and commits detached, creates a tracking branch for explicit branches,
and writes the normalized absolute path plus selector to the selected
`preferences.md`. It does not replace an existing checkout.

## Validate User Input

Validate if the user input paths exist and are valid using command-line tools.

Validation criteria:
- All branches:
  - `lightweight_source_code_path` **MUST** exist (required) — validate root path exists, should ideally contain `.sln` file
  - `full_source_code_path` (if provided) — validate root path exists, should ideally contain `.sln` file
  - `modding_profile_path` (if provided) — should contain `Blasphemous.exe` and `Modding` folder
  - local ModdingAPI reference parent — must be writable when Q6 is enabled; the fresh-clone target itself must not already exist
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

**Local reference failure handling** (Q6 = Yes, clone exit code != 0):
1. Display the clone command's terminal error report.
2. Do not write or update `modding_api_reference_path` or `modding_api_reference_selector`.
3. Ask the user whether to retry with a corrected selector or path; selecting Skip leaves the release-aware remote fallback enabled.

## Save Locations

Use the approved preferences and local-reference paths in
[preferences-schema.md#approved-local-reference-locations](preferences-schema.md#approved-local-reference-locations).

## Setup Workflow After User-questions

1. Create directory if needed
2. Write or update `preferences.md` with selected values. Preserve unknown and legacy fields. Add `modding_api_reference_path` and `modding_api_reference_selector` only when Q6 is enabled and the clone succeeds.
3. If Q6 was skipped, leave both local reference fields absent.
4. Confirm: "Preferences saved to [path], you can edit it by yourself at any time."
5. Continue main agent workflow using saved preferences

## `preferences.md` Template

see [preferences-schema.md](preferences-schema.md) for detailed template restrictions.

## Modifying Preferences Later

Users can edit `preferences.md` directly or delete it to trigger setup again.
