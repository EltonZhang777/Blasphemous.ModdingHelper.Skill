---
name: invocation-preflight
description: Shared command context, preferences gate, recovery, and completion contract for blasphemous-modding-helper
---

# Invocation preflight

This reference is the single source of truth for the shared preflight contract of every `blasphemous-modding-helper` invocation. It owns command context, preference scope selection, first-time setup, path-failure recovery, the tracked-session stop exception, and preflight completion. The top-level [Skill](../../SKILL.md) remains the sole cross-branch router. Specialized references MUST link here and MUST add only their own requirements and evidence.

## Command context

Every executable example in this Skill MUST use the following context:

1. The agent MUST set `SKILL_ROOT` in Bash or `$SkillRoot` in PowerShell to the absolute installed directory containing this `SKILL.md` and its `scripts/` directory. The value identifies the installed Skill and MUST NOT be inferred from, or replaced by, a checkout-relative path.
2. The agent MUST keep the caller's Mod repository as the current working directory when invoking Skill scripts. Project-relative paths, `.csproj` discovery, and project-scoped preferences MUST resolve from that caller directory.
3. The agent MUST invoke each script through an explicit Skill-root path and the interpreter named by its reference:
   - Bash entry point: `bash "$SKILL_ROOT/scripts/<script>.sh" [arguments]`.
   - PowerShell entry point: `& (Join-Path $SkillRoot 'scripts\<script>.ps1') [arguments]`.
   - Python entry point: `"$PYTHON3" "$SKILL_ROOT/scripts/<script>.py" [arguments]`, or the equivalent PowerShell invocation, after `PYTHON3` has been resolved.
   - Node.js entry point: `node "$SKILL_ROOT/scripts/<script>.js" [arguments]` when the reference names a Node.js entry point.
4. The agent MUST resolve and set the root variable and any required interpreter before copying or executing a command. The selected branch MUST supply any additional shell compatibility requirement; the command context does not authorize a compatibility shell where a branch requires a native shell.
5. The agent MUST quote paths and arguments whenever the selected shell requires quoting, including paths containing spaces.

The command context is ready when the installed Skill root, caller Mod repository, required interpreter, and selected shell are known before a command is executed.

## Preferences gate

The agent MUST run the preference check from the caller's Mod repository with the explicit Skill-root path:

```bash
bash "$SKILL_ROOT/scripts/check_preferences.sh"
```

```powershell
& (Join-Path $SkillRoot 'scripts\check_preferences.ps1')
```

The check emits `project`, `user`, or no output. Project scope MUST take precedence over user scope:

- Project: `.skills/blasphemous-modding-helper/preferences.md` under the caller's current working directory.
- User: `$HOME/.skills/blasphemous-modding-helper/preferences.md`.

When the check finds a file, the agent MUST read, parse, and apply that selected file. The complete field schema and approved local-reference locations are defined in [preferences-schema.md](preferences-schema.md). A branch MAY require additional fields, but it MUST validate those fields after this shared gate selects the active file.

When the check finds no file, the agent MUST enter [First-Time Setup](first-time-setup.md). The agent MUST NOT infer defaults or enter source analysis, log analysis, modding operations, or test workflow commands before setup reports success or an explicit setup failure.

## First-time setup and recovery

[First-Time Setup](first-time-setup.md) owns the setup questions, validation, scope save, and optional local ModdingAPI checkout. The shared gate above owns when setup is required; this section owns the common blocking and recovery contract:

- Missing preferences MUST block every normal branch until setup succeeds. A setup failure MUST be reported with its error and retry path.
- The only preflight exception is `/blasphemous-modding-test stop SESSION_ID`. It MUST use only the recorded session identity, MUST address only that tracked process tree, and MUST not read or edit preferences when normal context preflight is unavailable.
- A source-code or modding path failure MUST use this exact handoff: "Some operations failed using the saved paths in `preferences.md`. Would you like to re-run the first-time setup to update them?"
- If the user answers Yes, the agent MUST delete the active `preferences.md` and return to [First-Time Setup](first-time-setup.md). If the user answers No, the agent MUST continue with the current paths and report the specific failure.

After this contract completes, the agent MUST return to the top-level Skill's workflow. The top-level document selects the applicable source, log, mod-test, or general-modding branch; each branch then adds only its own path, environment, or evidence requirements.

## Completion criteria

The shared preflight is complete only when all applicable conditions below hold:

1. The command context is ready, including the installed Skill root, caller Mod repository, required interpreter, and selected shell.
2. The preference check has selected and applied a project or user file, or First-Time Setup has reported success.
3. The selected branch has received the active preferences file and can state its additional required fields before mutating files, launching a process, or relying on a source or log path.
4. For the tracked-session stop exception, the recorded process is stopped or confirmed gone and no unrelated process was touched.
5. For a declined path recovery, the specific failure and the next action have been reported. A successful setup instead returns a validated preferences file to the main workflow.
