---
name: first-time-setup
description: First-time setup flow for blasphemous-modding-helper preferences
---

# First-Time Setup

## Overview

When no `preferences.md` is found, this reference describes the preference-setup flow.

**BLOCKING OPERATION**: This setup MUST complete before source analysis, log analysis, modding operations, or test workflow commands. The tracked-session stop exception remains available when normal context preflight is unavailable: `/blasphemous-modding-test stop SESSION_ID` MUST use only the recorded session identity and MUST address only that tracked process tree.

The agent MUST enter the main workflow only after setup completes.

The agent MUST ask only the questions in this setup flow, MUST save `preferences.md`, and MUST continue only after those steps complete.

Setup is complete when the selected-scope `preferences.md` has been written and confirmed, or setup has aborted with the error and retry path reported to the user. The tracked-session stop exception is complete when the recorded process is stopped or confirmed gone without reading or editing preferences.

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
    │   7. The agent MUST ask whether to configure a local ModdingAPI reference (see Q6).
    │      ├─ Yes → the agent MUST use the selected preferences scope, choose a selector, and run the fresh-clone command.
    │      │        ├─ Success → the agent MUST record the normalized path and selector.
    │      │        └─ Failure → the agent MUST show the terminal error report and MUST NOT add the fields.
    │      └─ Skip → the agent MUST leave local reference fields absent; remote fallback remains available.
    │   8. The agent MUST validate all paths (lightweight MUST exist).
    │      ├─ Fail → the agent MUST retry the corresponding single question.
    │      └─ OK → the agent MAY continue.
    │   9. The agent MUST create or update `preferences.md`.
    │   10. The agent MUST continue.
   │
   └─ No (run decompiler) → the agent MUST run the decompile script synchronously
       (Windows: `scripts/decompile_source.ps1` ; macOS/Linux: `scripts/decompile_source.sh`)
       ├─ Success →
       │   lightweight_source_code_path = <skill-root>/source_code/ (auto-set)
       │   5. The agent MUST ask: "Do you also have full source code?" (see Q4).
       │      ├─ Yes → the agent MUST ask for the full source code path (see Q4b)
       │      └─ No  → the agent MUST skip Q4b
       │   6. The agent MUST ask for the modding profile path (see Q5).
       │   7. The agent MUST ask whether to configure a local ModdingAPI reference (see Q6).
       │      ├─ Yes → the agent MUST use the selected preferences scope, choose a selector, and run the fresh-clone command.
       │      └─ Skip → the agent MUST leave local reference fields absent; remote fallback remains available.
       │   8. The agent MUST validate all paths (lightweight MUST exist).
       │   9. The agent MUST create or update `preferences.md`.
       │   10. The agent MUST continue.
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
- If Q2 is "Yes", the agent MUST ask Q1 + Q2 + Q3 + Q4 + Q5 + Q6 in one call; Q4b and selector details are conditional inputs.
- If Q2 is "No", the agent MUST ask Q1 + Q2 + Q4 + Q5 + Q6 in one call; Q3 is auto-filled, and Q4b and selector details are conditional inputs.

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

If the user selects **Yes**, the agent MUST use the same scope selected in Q1.
The agent MUST NOT select an independent reference scope: the agent MUST keep
the local reference and its preferences in the same scope domain. The approved paths are authoritative in
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

For **Exact tag**, the agent MUST collect the tag name and pass `tag:REF`.
For an explicit branch or commit, the agent MUST collect the branch name or
40-character SHA and pass `branch:REF` or `commit:SHA`. `latest` needs no
additional value.

The agent MUST run the matching fresh-clone command from the skill directory:

```bash
bash scripts/clone_modding_api.sh --scope user --selector latest
```

```powershell
& .\scripts\clone_modding_api.ps1 -Scope user -Selector latest
```

The agent MUST use `--scope project` / `-Scope project` when Q1 selected
Project and MUST use User when Q1 selected User. The clone command refuses an existing target, uses shallow history by default, checks out
tags and commits detached, creates a tracking branch for explicit branches,
writes the normalized absolute path plus selector to the selected
`preferences.md`, and writes the sibling lock state described in
[preferences-schema.md#sibling-lock-state](preferences-schema.md#sibling-lock-state).
It does not replace an existing checkout.

## Validate User Input

The agent MUST validate whether the user-input paths exist and are valid using command-line tools.

Validation criteria:
- All branches:
  - `lightweight_source_code_path` **MUST** exist — validate that the root path exists; it SHOULD ideally contain an `.sln` file
  - `full_source_code_path` (if provided) — validate that the root path exists; it SHOULD ideally contain an `.sln` file
  - `modding_profile_path` (if provided) — it SHOULD contain `Blasphemous.exe` and a `Modding` folder
  - When Q6 is enabled, the local ModdingAPI reference parent MUST be writable, and the fresh-clone target MUST NOT already exist.
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

**Local reference failure handling** (Q6 = Yes, clone exit code != 0):
1. The agent MUST display the clone command's terminal error report.
2. The agent MUST NOT write or update `modding_api_reference_path` or `modding_api_reference_selector`.
3. The agent MUST ask the user whether to retry with a corrected selector or path; selecting Skip leaves the release-aware remote fallback enabled.

## Save Locations

The agent MUST use the approved preferences and local-reference paths in
[preferences-schema.md#approved-local-reference-locations](preferences-schema.md#approved-local-reference-locations).

## Setup Workflow After User-questions

1. The agent MUST create the directory if needed.
2. The agent MUST write or update `preferences.md` with the selected values, preserve unknown and legacy fields, and add `modding_api_reference_path` and `modding_api_reference_selector` only when Q6 is enabled and the clone succeeds.
3. If Q6 was skipped, the agent MUST leave both local reference fields absent.
4. The agent MUST confirm: "Preferences saved to [path], you can edit it by yourself at any time."
5. The agent MUST continue the main agent workflow using the saved preferences.

## `preferences.md` Template

The agent MUST read [preferences-schema.md](preferences-schema.md) for detailed template restrictions.

## Modifying Preferences Later

Users can edit `preferences.md` directly or delete it to trigger setup again.
