---
name: invocation-preflight
description: Shared command context, configuration gate, recovery, and completion contract for blasphemous-modding-helper
---

# Invocation preflight

This reference is the single source of truth for the shared preflight contract of every operational `blasphemous-modding-helper` invocation. It owns command context, configuration scope selection, when first-time setup is required, path-failure recovery, the tracked-session stop exception, and preflight completion. Detailed setup questions, validation, save operations, and optional local checkout belong to [First-Time Setup](first-time-setup.md). The top-level [Skill](../../SKILL.md) remains the sole cross-branch router. Specialized references MUST link here and MUST add only their own requirements and evidence.

The read-only [localization lookup branch](../sub-skills/localization-lookup.md) is the documented configuration exception. It reads the bundled localization index as text and does not run Skill scripts, inspect a Modding profile, or inspect source code. It confirms the index path and file readability, then follows its own completion criteria.

## Command context

Every executable example in this Skill MUST use this context:

1. Agent MUST set `SKILL_ROOT` in Bash or `$SkillRoot` in PowerShell to the absolute installed directory containing this `SKILL.md` and its `scripts/` directory. The value identifies the installed Skill and MUST NOT be inferred from, or replaced by, a checkout-relative path.
2. Agent MUST keep caller's Mod repository as current working directory when invoking Skill scripts. Project-relative paths, `.csproj` discovery, and project-scoped configuration MUST resolve from that caller directory.
3. Agent MUST invoke Skill runtime and test scripts through their explicit Python entry point:
   - Bash host: `"$PYTHON3" "$SKILL_ROOT/scripts/<script>.py" [arguments]`.
   - PowerShell host: `& $PYTHON3 (Join-Path $SkillRoot 'scripts\<script>.py') [arguments]`.
   The Python interpreter MUST be resolved first. Runtime selection and failure classification are defined in [Python Runtime](python-runtime.md). Legacy JavaScript, PowerShell, and Bash script files are not Skill invocation paths.
4. Agent MUST resolve and set the root variable and Python interpreter before copying or executing a command. The selected branch MUST supply any additional native-OS or compatibility-layer requirement; command context does not authorize a compatibility environment.
5. Agent MUST quote paths and arguments whenever selected shell requires quoting, including paths containing spaces.

Command context is ready when installed Skill root, caller Mod repository, resolved Python interpreter, and supported native host are known before a command is executed.

## Native Python shell template

PowerShell and Bash are host syntaxes for the same native Python entry point;
they are not separate implementations. Every executable example MUST preserve
this parity:

| Context | Canonical invocation |
| --- | --- |
| Bash | `"$PYTHON3" "$SKILL_ROOT/scripts/<script>.py" [arguments]` |
| PowerShell | `& $PYTHON3 (Join-Path $SkillRoot 'scripts\<script>.py') [arguments]` |

Both forms MUST use the resolved `PYTHON3`, an absolute installed Skill root,
the caller's Mod repository as working directory, and the same script and
argument values. Paths remain separate quoted arguments; host-specific slash
syntax is the only permitted textual difference. Examples in branch references
inherit this contract and MUST NOT call a legacy shell/JavaScript entry point,
MUST NOT use a checkout-relative Skill path, and MUST NOT change the working
directory implicitly.

## Python runtime gate

During first-time setup, agent MUST complete [Python Runtime](python-runtime.md) before asking setup questions. The gate resolves an explicit interpreter, `PYTHON3`, or the host interpreter in that order; accepts Python 3.9 or newer; validates the Skill dependency manifest; and never installs packages automatically.

After setup succeeds, agent MUST reuse the validated interpreter context for normal branches. Agent MUST retry this gate only after a classified Python-environment failure. Ordinary Git, network, dotnet, game, profile, log, and Mod failures remain branch-owned runtime or domain failures and MUST NOT trigger Python reconfiguration.

## Configuration gate

Agent MUST run the configuration check from caller's Mod repository with explicit Skill-root path:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/check_preferences.py" --validate
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\check_preferences.py') --validate
```

Validation mode emits structured `PREFERENCES_*` fields with a stable status of
`skipped`, `passed`, `normalized`, or `failed`. A `failed` result includes an
actionable reason, marks `PREFERENCES_SETUP=required`, and MUST enter
[First-Time Setup](first-time-setup.md) before any downstream operational
workflow continues. Downstream branches MUST consume the selected validation result
and `PREFERENCES_SCOPE`/`PREFERENCES_FILE`; they MUST NOT rediscover or
revalidate configuration independently. Project scope MUST take precedence over user scope:

- Project: `.skills/blasphemous-modding-helper/config.yml` under caller's current working directory.
- User: `$HOME/.skills/blasphemous-modding-helper/config.yml`.

When check finds a file, agent MUST read, parse, and apply that selected file. Complete field schema and approved local-reference locations are defined in [the config schema](preferences-schema.md). A branch MAY require additional fields, but it MUST validate those fields after this shared gate selects the active file.

The no-argument `check_preferences.py` mode remains available for callers that
only need the legacy `project`, `user`, or empty scope output; it does not run
freshness validation or write configuration metadata.

When check finds no file, agent MUST enter [First-Time Setup](first-time-setup.md). Agent MUST NOT infer defaults or enter source analysis, log analysis, modding operations, or test workflow commands before setup reports success or explicit setup failure.

## First-time setup and recovery

[First-Time Setup](first-time-setup.md) owns setup questions, validation, scope save, optional local ModdingAPI checkout, and the setup-specific success or incomplete result. The shared gate above owns when setup is required and consumes that result; this section owns the common blocking and recovery contract:

- Missing configuration MUST block every operational branch until setup succeeds. The read-only localization lookup branch does not require configuration and remains available when no configuration file exists. Setup failure MUST be reported with its error and retry path.
- Only preflight exception is `/blasphemous-modding-test stop SESSION_ID`. It MUST use only recorded session identity, MUST address only that tracked process tree, and MUST not read or edit configuration when normal context preflight is unavailable.
- Source-code or modding path failure MUST use this exact handoff: "Some operations failed using the saved paths in `config.yml`. Would you like to re-run the first-time setup to update them?"
- If user answers Yes, agent MUST delete active `config.yml` and return to [First-Time Setup](first-time-setup.md). If user answers No, agent MUST continue with current paths and report specific failure.

After this contract completes, agent MUST return to top-level Skill's workflow. top-level document selects applicable source, log, mod-test, or general-modding branch; each branch then adds only its own path, environment, or evidence requirements.

## Completion criteria

Shared preflight is complete only when all applicable conditions below hold:

1. An operational branch has a ready command context, including installed Skill root, caller Mod repository, resolved Python interpreter, and supported native host; or the localization branch has a confirmed bundled index path and readable file.
2. An operational branch has a selected and applied project or user configuration file, or First-Time Setup has reported success. The localization branch has no configuration requirement.
3. The selected branch has received its required context before mutating files, launching a process, or relying on source or log paths.
4. For the tracked-session stop exception, the recorded process is stopped or confirmed gone and no unrelated process was touched.
5. For declined path recovery, the specific failure and next action have been reported. Successful setup instead returns a validated configuration file to the main workflow.
6. The result report names the selected route or gate status, completion evidence, the blocked reason when applicable, and the next document or action.
