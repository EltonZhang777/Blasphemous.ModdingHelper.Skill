---
name: invocation-preflight
description: Shared command context, preferences gate, recovery, and completion contract for blasphemous-modding-helper
---

# Invocation preflight

This reference is the single source of truth for the shared preflight contract of every `blasphemous-modding-helper` invocation. It owns command context, preference scope selection, first-time setup, path-failure recovery, the tracked-session stop exception, and preflight completion. The top-level [Skill](../../SKILL.md) remains the sole cross-branch router. Specialized references MUST link here and MUST add only their own requirements and evidence.

## Command context

Every executable example in this Skill MUST use this context:

1. Agent MUST set `SKILL_ROOT` in Bash or `$SkillRoot` in PowerShell to the absolute installed directory containing this `SKILL.md` and its `scripts/` directory. The value identifies the installed Skill and MUST NOT be inferred from, or replaced by, a checkout-relative path.
2. Agent MUST keep caller's Mod repository as current working directory when invoking Skill scripts. Project-relative paths, `.csproj` discovery, and project-scoped preferences MUST resolve from that caller directory.
3. Agent MUST invoke Skill runtime and test scripts through their explicit Python entry point:
   - Bash host: `"$PYTHON3" "$SKILL_ROOT/scripts/<script>.py" [arguments]`.
   - PowerShell host: `& $PYTHON3 (Join-Path $SkillRoot 'scripts\<script>.py') [arguments]`.
   The Python interpreter MUST be resolved first. Runtime selection and failure classification are defined in [Python Runtime](python-runtime.md). Legacy JavaScript, PowerShell, and Bash script files are not Skill invocation paths.
4. Agent MUST resolve and set the root variable and Python interpreter before copying or executing a command. The selected branch MUST supply any additional native-OS or compatibility-layer requirement; command context does not authorize a compatibility environment.
5. Agent MUST quote paths and arguments whenever selected shell requires quoting, including paths containing spaces.

Command context is ready when installed Skill root, caller Mod repository, resolved Python interpreter, and supported native host are known before a command is executed.

## Python runtime gate

During first-time setup, agent MUST complete [Python Runtime](python-runtime.md) before asking setup questions. The gate resolves an explicit interpreter, `PYTHON3`, or the host interpreter in that order; accepts Python 3.9 or newer; validates the Skill dependency manifest; and never installs packages automatically.

After setup succeeds, agent MUST reuse the validated interpreter context for normal branches. Agent MUST retry this gate only after a classified Python-environment failure. Ordinary Git, network, dotnet, game, profile, log, and Mod failures remain branch-owned runtime or domain failures and MUST NOT trigger Python reconfiguration.

## Preferences gate

Agent MUST run preference check from caller's Mod repository with explicit Skill-root path:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/check_preferences.py"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\check_preferences.py')
```

Check emits `project`, `user`, or no output. Project scope MUST take precedence over user scope:

- Project: `.skills/blasphemous-modding-helper/preferences.md` under caller's current working directory.
- User: `$HOME/.skills/blasphemous-modding-helper/preferences.md`.

When check finds file, agent MUST read, parse, and apply that selected file. complete field schema and approved local-reference locations are defined in [preferences-schema.md](preferences-schema.md). branch MAY require additional fields, but it MUST validate those fields after this shared gate selects active file.

When check finds no file, agent MUST enter [First-Time Setup](first-time-setup.md). Agent MUST NOT infer defaults or enter source analysis, log analysis, modding operations, or test workflow commands before setup reports success or explicit setup failure.

## First-time setup and recovery

[First-Time Setup](first-time-setup.md) owns setup questions, validation, scope save, and optional local ModdingAPI checkout. shared gate above owns when setup is required; this section owns common blocking and recovery contract:

- Missing preferences MUST block every normal branch until setup succeeds. setup failure MUST be reported with its error and retry path.
- Only preflight exception is `/blasphemous-modding-test stop SESSION_ID`. It MUST use only recorded session identity, MUST address only that tracked process tree, and MUST not read or edit preferences when normal context preflight is unavailable.
- Source-code or modding path failure MUST use this exact handoff: "Some operations failed using the saved paths in `preferences.md`. Would you like to re-run the first-time setup to update them?"
- If user answers Yes, agent MUST delete active `preferences.md` and return to [First-Time Setup](first-time-setup.md). If user answers No, agent MUST continue with current paths and report specific failure.

After this contract completes, agent MUST return to top-level Skill's workflow. top-level document selects applicable source, log, mod-test, or general-modding branch; each branch then adds only its own path, environment, or evidence requirements.

## Completion criteria

Shared preflight is complete only when all applicable conditions below hold:

1. Command context is ready, including installed Skill root, caller Mod repository, resolved Python interpreter, and supported native host.
2. Preference check has selected and applied project or user file, or First-Time Setup has reported success.
3. Selected branch has received active preferences file and can state its additional required fields before mutating files, launching process, or relying on source or log path.
4. For tracked-session stop exception, recorded process is stopped or confirmed gone and no unrelated process was touched.
5. For declined path recovery, specific failure and next action have been reported. successful setup instead returns validated preferences file to main workflow.
