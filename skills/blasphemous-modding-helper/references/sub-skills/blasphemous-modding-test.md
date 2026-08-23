# `/blasphemous-modding-test`

This is the authoritative workflow for repeatable local Blasphemous mod tests. Use it when a task needs to build or select a mod package, deploy it to a modding profile, launch the profile-local game, inspect startup evidence, stop a tracked session, clean a deployment, or collect the player's Manual verification description.

The Python CLI automates filesystem, build, process, and log operations. It does not control the game through MCP and it does not verify visual, input, combat, menu, save, or other in-game behavior. Keep the automated evidence and the player's **Manual verification** as separate evidence sources.

## Entry conditions

1. Follow the top-level skill's preferences gate and first-time setup before using the workflow. The active `preferences.md` must define `modding_profile_path`; use the [preferences schema](../config/preferences-schema.md) and [first-time setup](../config/first-time-setup.md) when it is missing or invalid.
2. Resolve a native Python 3 interpreter before invoking the CLI. `PYTHON3` below means that resolved executable; it is not an arbitrary shell command. On Windows, use the configured Python installation rather than assuming `python` or `py` is on `PATH`.
3. Use native Windows PowerShell, or native Linux/macOS Bash. The CLI rejects Git Bash, Cygwin, WSL, Proton, Wine, and unsupported operating systems. Keep paths quoted when they contain spaces.
4. Confirm that the selected profile is a disposable or mirror game installation. The CLI operates on that profile's `Modding` root and launches its local game executable.

Done when: the agent can name the active preferences file, project, profile, Python interpreter, and native shell before any profile mutation is attempted.

## CLI entry point

The repository entry point is:

```text
skills/blasphemous-modding-helper/scripts/blasphemous_modding_test.py
```

PowerShell invocation shape:

```powershell
& $PYTHON3 .\skills\blasphemous-modding-helper\scripts\blasphemous_modding_test.py <command> [options]
```

Native Bash invocation shape:

```bash
"$PYTHON3" skills/blasphemous-modding-helper/scripts/blasphemous_modding_test.py <command> [options]
```

The CLI has five commands: `run`, `stop`, `clean`, `logs`, and read-only `status`. The session identifier printed by `run` is a 32-character lowercase hexadecimal value and is required by `stop`, `clean`, and `logs`.

Common options are accepted by `run`, `clean`, `logs`, and `status`:

| Option | Meaning |
| --- | --- |
| `--project PATH` | Select one `.csproj`; without it, `run` requires exactly one `.csproj` in the current directory. `clean`, `logs`, and `status` use it only to resolve ambiguity. |
| `--profile PATH` | Override `modding_profile_path` for this invocation. The preferences file is still required by commands that load context. |
| `--launcher PATH` | Select a concrete launcher file for this invocation. It is a path, not a shell command. An explicit launcher emits a warning, especially when it is outside the profile. |
| `--unity-log-dir PATH` | Override `unity_log_dir` for this invocation without editing `preferences.md`. |

### `run`: build, deploy, launch, and optionally wait

```text
<python3> .../blasphemous_modding_test.py run [common options]
    [--configuration Debug|Release]
    [--artifact PATH]
    [--dry-run]
    [--startup-timeout SECONDS]
```

Expected behavior, in order:

1. Validate the native environment, preferences, project selection, and profile.
2. With no `--artifact`, run the equivalent of `dotnet build <project.csproj> --configuration <configuration>`. `Debug` is the default. Use `--configuration Release` only when the user explicitly requests a release build; Debug may contain test statements and test code blocks.
3. Read the project's declared `<TargetName>` and validate the complete package under `publish/<TargetName>`.
4. Refuse a conflicting game instance before deployment. Copy every safe file below the package root to the matching relative path below the profile's `Modding` root, creating only missing subdirectories.
5. Record a deployment manifest and print the deployment session identifier.
6. Launch the selected profile-local executable with the profile as its working directory and track the exact process identity and child tree. Do not use a Steam URI.
7. Print `launched` immediately when no timeout is requested. With `--startup-timeout SECONDS`, poll current log evidence until the target mod is found or the timeout expires.

`--dry-run` performs environment, project, profile, build/artifact, and package validation and prints the file plan. It does not copy profile files or launch a process. When no `--artifact` is provided, the build still runs because the build output is part of the plan; use an explicit artifact for a no-build inspection.

Completion criterion: a successful non-dry run prints a session identifier, deployment state, launch state, and process ID; a timed-out run prints the timeout evidence and leaves the process and session available for diagnosis.

### Build and artifact selection

Project selection is deterministic:

- `--project PATH` must name an existing `.csproj`.
- Without `--project`, `run` accepts exactly one `.csproj` in the current directory.
- Zero projects or multiple projects require an explicit `--project` and are usage/configuration failures.

The normal build artifact is the package directory under the `publish` directory selected by the project's solution/build layout:

```text
<solution-or-project root>/publish/<TargetName>/
```

For example, when the project declares `TargetName` as `CustomBackgrounds`, every file under `publish/CustomBackgrounds/` is part of the deployment: plugin assemblies, data dependencies, localization, images, JSON, and other resources. The package-relative directory structure is preserved. The CLI does not select one DLL or discard files by extension.

Use `--artifact PATH` only when the exact input is already known:

- A directory is treated as the package root and is not rebuilt.
- A `.zip` is extracted into temporary state, validated, and then deployed; it never writes directly into the profile during extraction.
- Zip input is a recovery path for a seriously abnormal or unavailable package directory. It is not selected by timestamp and it is not a silent fallback.
- Empty packages, unsafe relative paths, absolute paths, parent traversal, symlinks, hard-link destinations, case-colliding paths, and malformed archive entries fail before deployment.

Completion criterion: the printed artifact plan names one `TargetName`, one package root, one artifact kind, and all files that will be copied; no ambiguous or guessed artifact is accepted.

### Profile and launcher preflight

The selected `modding_profile_path` must be a directory containing:

```text
<profile>/Modding/
<profile>/BepInEx/core/BepInEx.dll
```

It must also contain a non-empty launcher. Known launchers are selected only inside the profile:

| Host | Default candidates |
| --- | --- |
| Windows | `<profile>/Blasphemous.exe` |
| Linux | `<profile>/Blasphemous.x86_64`, then `<profile>/Blasphemous` |
| macOS | `<profile>/Blasphemous.app/Contents/MacOS/Blasphemous`, then `<profile>/Blasphemous` |

`--launcher PATH` accepts one concrete existing file, checks executability where the host requires it, and passes it directly to the process API. It does not accept arbitrary shell syntax, pipelines, arguments, or a command string. The explicit path may be outside the profile, but the CLI emits a warning; treat that as a user-visible safety exception. The game is started with `shell=False` and the profile as its working directory.

Completion criterion: preflight has identified the exact profile, `Modding` root, BepInEx root, and launcher, and any launcher override warning is visible to the agent and user.

### `stop`: stop one tracked session

```text
<python3> .../blasphemous_modding_test.py stop SESSION_ID [--force]
```

`stop` operates only on the process identity recorded in that session manifest and its captured child tree. It never selects a process by name and never attaches to an unrelated game. Without `--force`, request a normal stop; `--force` is limited to the same tracked tree when graceful termination does not finish.

The command is idempotent:

- `stopped`: this invocation terminated the tracked tree.
- `exited`: the tracked process had already exited.
- `gone`: the valid session manifest is already absent; no process was touched.

Completion criterion: the tracked process is stopped or confirmed gone, and no unrelated process was terminated.

### `logs`: read current startup evidence

```text
<python3> .../blasphemous_modding_test.py logs SESSION_ID [common options] [--full]
```

The CLI reads the existing logs in place and stores only evidence metadata in the temporary session manifest. It does not create a persistent log report or copy log contents. Default output is the last 200 lines per source; `--full` prints the complete current file.

The sources are:

```text
BepInEx: <profile>/BepInEx/LogOutput.log
Unity:   <unity_log_dir>/output_log.txt       (Windows)
Unity:   <unity_log_dir>/Player.log           (native Linux/macOS, then output_log.txt)
```

`unity_log_dir` is optional in the schema but required to locate a Unity log. On Windows, the usual directory is `%USERPROFILE%/AppData/LocalLow/TheGameKitchen/Blasphemous`; configure that directory explicitly when it is not already in `preferences.md`. If the directory or file is missing, print the warning, ask the user for the correct directory, and save `unity_log_dir: PATH` in the active `preferences.md` after the user supplies it. A one-run `--unity-log-dir PATH` override is available while confirming the value.

`LogOutput.log` contains the current BepInEx run and overwrites the previous run; there is no BepInEx history or polling log to recover. The launcher records a file baseline, so an existing log is marked `stale` and ignored for this session unless its signature changes after launch. A missing or unreadable BepInEx log is a hard logs/readiness failure. A missing Unity log is a warning and requires the user handoff above.

Startup states are deliberately narrower than gameplay results:

| State | Automated evidence |
| --- | --- |
| `launched` | The selected profile-local launcher produced a safely tracked process, but current BepInEx readiness is not established. |
| `ready` | The current BepInEx log contains chainloader readiness evidence. |
| `mod_loaded` | `ready` plus current log evidence mentioning the target `TargetName` with a loading/loaded/initialized/plugin/ready indication. |
| `timeout` | `--startup-timeout` expired before `mod_loaded`; the session and process remain for diagnosis. |

Completion criterion: the agent reports the state, current/stale/missing status of both sources, relevant warnings, and the bounded or full log output requested by the user.

### `status`: read-only session view

```text
<python3> .../blasphemous_modding_test.py status [common options]
```

`status` prints the selected context and sessions newest first. Each entry reports its role (`active`, `archived`, or `cleaned`), deployment state, cleanup state, tracked process state, and evidence state. It copies no files, launches no process, and does not inspect gameplay.

Completion criterion: the agent can discover the newest session and all older rollback sessions without changing the profile.

### `clean`: newest-first safe rollback

```text
<python3> .../blasphemous_modding_test.py clean SESSION_ID [common options]
    [--remove-new-files]
```

Stop the session first, then clean it. The CLI also refuses to clean while the tracked game process is still running. Cleanup uses a newest-first session stack:

1. Clean the newest cleanable session before any older session.
2. An older session with a newer active or archived rollback point is rejected; do not bypass this order.
3. Overwritten files are restored only when their current hash still equals the hash deployed by this session. A file changed during testing is protected and causes safe clean to report a conflict without silently overwriting it.
4. Files first created by this session are retained by default, even after the process stops. `--remove-new-files` explicitly approves removal only when the file is still unchanged; changed, linked, or non-regular paths remain protected.
5. Session manifests remain in temporary state after cleanup, so repeated cleanup is idempotent and `status` can show the result.

The default policy therefore restores the old files but does not delete new files. If an older session is blocked, inspect `status`, stop/clean the newer session, then retry the older one. If a file was changed by the user, preserve it and ask whether the user wants a separate manual resolution.

Completion criterion: the requested session is `cleaned` or `already-cleaned`, every restored/removed/retained file is reported, and protected files are unchanged.

## Preferences and precedence

For context-loading commands, the CLI checks these locations in order:

1. Project scope: `<current working directory>/.skills/blasphemous-modding-helper/preferences.md`.
2. User scope: `$HOME/.skills/blasphemous-modding-helper/preferences.md`.

The first existing file wins. Its `modding_profile_path` is required. Explicit CLI options override the selected preference for that invocation: `--profile`, `--project`, `--launcher`, and `--unity-log-dir`. The CLI does not rewrite preferences; the agent writes a user-supplied Unity log directory into the active file after the missing-log handoff.

`stop SESSION_ID` uses only the recorded session state and host check, so it is the narrow recovery exception when normal context preflight is unavailable. The top-level skill permits this exception because `stop` neither reads nor edits preferences and only addresses the exact tracked process tree. `run`, `clean`, `logs`, and `status` still require the normal preferences/profile gate.

## Automated evidence versus Manual verification

The automated boundary ends at profile launch, startup log evidence, process stop, and safe cleanup. The agent must not claim that `mod_loaded` proves game behavior.

After startup evidence is available, ask the player to perform the requested in-game scenario. Collect the **Manual verification** in natural language:

- the scene or save state used;
- the exact player actions;
- the expected result;
- the observed result, including visual, input, combat, menu, save, or other behavior;
- any visible error or approximate time at which it occurred.

Combine that Manual verification record with the CLI state and the two current logs when diagnosing the test. No gameplay transcript, log copy, or generated test report is required by this workflow. Use the existing [log analyzer](log-analyzer.md) for interpretation after the test evidence is collected.

## Stable failures and recovery

The CLI prints `Error [category]` and returns stable categories. Route recovery by exit code:

| Code | Category | Typical cause | Recovery |
| ---: | --- | --- | --- |
| `0` | success | Operation completed. | Continue to the next workflow step. |
| `2` | usage/configuration | Invalid arguments, ambiguous project, unsupported shell/OS, or compatibility layer. | Correct the invocation and use native PowerShell or native Bash. |
| `10` | profile/preferences | Missing/invalid preferences, missing profile directories, missing BepInEx core, or missing/invalid launcher preflight. | Complete first-time setup, verify `modding_profile_path`, `Modding`, `BepInEx/core/BepInEx.dll`, and launcher; use explicit path overrides only for the intended invocation. |
| `20` | build | `dotnet build` could not start, parse the project, or returned a failure. | Read the build output, fix the project/dependencies, and rerun. No old package is silently substituted. |
| `30` | package artifact | Missing/empty package, unsafe directory/archive entry, missing `<TargetName>`, or explicit artifact is not a directory/zip. | Inspect `publish/<TargetName>`, pass the exact package directory with `--artifact`, or explicitly use a validated recovery zip. |
| `40` | deployment | Destination preflight, copy, hash verification, or transaction rollback failed. | Do not manually delete profile files. If rollback succeeded, retry after fixing the cause. If rollback failed, retain the printed session ID, inspect the manifest/status, and resolve protected files with the user before any further deployment. |
| `50` | launch | A matching game is already running, launcher start failed, or process identity could not be safely tracked. | Stop only the known session if applicable, verify the profile-local launcher, then rerun. Never attach to or kill an untracked process. |
| `60` | logs/readiness | Current BepInEx log missing/unreadable or startup timeout. | Keep the session alive; run `logs SESSION_ID`, configure `unity_log_dir`, inspect current BepInEx output, ask for the Manual verification description, then stop and clean when diagnosis is complete. |
| `70` | stop/clean | Unknown session/process state, running tracked process, newer session, changed file, or invalid rollback manifest. | Use `status`, stop the tracked process, clean newest-first, and preserve changed files. Retry only after the reported guard is resolved. |

Deployment failures are transactional: a partial copy is rolled back automatically when possible. A failed rollback is a hard stop with a session identifier; it is not permission to remove the whole `Modding` root. A failure to archive previous sessions also attempts to roll back the new deployment and reports whether that recovery succeeded.

## Acceptance criteria

Use this checklist for a complete implementation or Manual verification:

- [ ] The agent can invoke `run`, `stop`, `clean`, `logs`, and `status` with the documented argument contract on native Windows PowerShell and native Linux/macOS Bash.
- [ ] Project selection is explicit when ambiguous; default builds use Debug; Release requires an explicit option.
- [ ] The build package resolves to `publish/<TargetName>` and every file below that package root is planned and deployed with its relative path preserved.
- [ ] An explicit directory artifact works without a build; an explicit zip is temporary, path-validated, and never selected implicitly.
- [ ] Profile preflight rejects an incomplete profile, uses a profile-local known launcher by default, and warns on an explicit launcher override.
- [ ] The CLI never uses a Steam URI, arbitrary shell command, process-name kill, or broad profile deletion.
- [ ] A successful run records a session and process identity; repeated runs archive older sessions and print a warning.
- [ ] `stop` is limited to the tracked process tree and is idempotent for exited or missing session state.
- [ ] `clean` is newest-first, restores only hash-compatible overwritten files, retains new files by default, and requires `--remove-new-files` for unchanged new-file removal.
- [ ] Current BepInEx and configured Unity logs produce bounded output by default and full output only with `--full`; missing Unity configuration produces a visible handoff warning.
- [ ] Automated startup evidence is reported as `launched`, `ready`, `mod_loaded`, or `timeout`; Manual verification is collected from the player in natural language.
- [ ] Missing profile, build, artifact, launcher, log, timeout, deployment, and rollback conditions map to the stable failure categories and recovery steps above.

The design decisions behind this contract are recorded in the [Blasphemous mod test spec](../../../../docs/specs/blasphemous-modding-test.md), [stack-safe rollback ADR](../../../../docs/adr/0001-stack-safe-mod-test-rollback.md), and [Python CLI ADR](../../../../docs/adr/0002-python-stdlib-test-cli.md).
