# `/blasphemous-modding-test`

This is authoritative workflow for repeatable local Blasphemous mod tests. Agent MUST use it when task needs to build or select mod package, deploy it to modding profile, launch profile-local game, inspect startup evidence, stop tracked session, clean deployment, or collect player's Manual verification description, including when no new automated run is requested.

Python CLI automates filesystem, build, process, and log operations. It does not control game through MCP and it does not verify visual, input, combat, menu, save, or other in-game behavior. Keep automated evidence and player's **Manual verification** as separate evidence sources.

## Entry conditions

1. Agent MUST complete [Invocation preflight](../config/invocation-preflight.md) before using the workflow. This sub-skill adds one profile-specific requirement: the active `preferences.md` MUST define `modding_profile_path`; the agent MUST use the [preferences schema](../config/preferences-schema.md) and [first-time setup](../config/first-time-setup.md) when that field is missing or invalid.
2. Agent MUST resolve native Python 3 interpreter before invoking CLI. `PYTHON3` below means that resolved executable; it is not arbitrary shell command. On Windows, agent MUST use configured Python installation rather than assuming `python` or `py` is on `PATH`.
3. Agent MUST use native Windows PowerShell, or native Linux/macOS Bash. CLI MUST reject Git Bash, Cygwin, WSL, Proton, Wine, and unsupported operating systems. Paths MUST remain quoted when they contain spaces.
4. Agent MUST confirm that selected profile is disposable or mirror game installation. CLI operates on that profile's `Modding` root and launches its local game executable.

Done when: agent can name active preferences file, project, profile, Python interpreter, and native shell before any profile mutation is attempted.

## CLI entry point

Before executing command in this reference, agent MUST apply command-context contract in [Invocation preflight](../config/invocation-preflight.md). CLI MUST run from caller's Mod repository; caller does not need repository checkout containing `skills/blasphemous-modding-helper`.

CLI entry point is:

```text
$SKILL_ROOT/scripts/blasphemous_modding_test.py
```

PowerShell invocation shape:

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\blasphemous_modding_test.py') <command> [options]
```

Native Bash invocation shape:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/blasphemous_modding_test.py" <command> [options]
```

Argument shapes below abbreviate shell-specific invocation above as `<TEST_CLI>`. Agent MUST expand that placeholder with PowerShell or Bash form; it MUST NOT replace it with checkout-relative script path.

CLI has five commands: `run`, `stop`, `clean`, `logs`, and read-only `status`. session identifier printed by `run` is 32-character lowercase hexadecimal value and is required by `stop`, `clean`, and `logs`.

## Encoding and path output

The CLI emits user-facing stdout and stderr as UTF-8, including profile, project, artifact, and log paths. Keep paths as quoted arguments in native PowerShell and Bash invocations; spaces are part of the path, not argument separators. Text returned by build and process-management subprocesses is decoded as UTF-8 with replacement for undecodable bytes, so a decoding failure remains a readable build, launch, or cleanup error. Existing log files use the same explicit replacement policy only for log content; it does not alter recorded or displayed path values.

### Agent-safe help and canonical flow

Agents SHOULD inspect `<TEST_CLI> --help` first, then `<TEST_CLI> <command> --help` before invoking a command. Each subcommand help lists only that command's accepted options, explains context and per-invocation overrides where applicable, and includes a command-specific example. `stop` is the exception to normal context resolution: it accepts only `SESSION_ID` and optional `--force`.

Canonical flow for a normal build, startup evidence, tracked stop, safe cleanup, and read-only status:

```text
<TEST_CLI> run --project <PROJECT.csproj> --profile <PROFILE> --startup-timeout 60
<TEST_CLI> logs SESSION_ID
<TEST_CLI> stop SESSION_ID
<TEST_CLI> clean SESSION_ID
<TEST_CLI> status
```

If graceful stop does not finish, retry only the same tracked session with `<TEST_CLI> stop SESSION_ID --force`. `stop` does not accept project, profile, launcher, log-directory, artifact, build, or cleanup options.

Common options are accepted by `run`, `clean`, `logs`, and `status`:

| Option | Meaning |
| --- | --- |
| `--project PATH` | Select one `.csproj`; without it, `run` requires exactly one `.csproj` in the current directory. `clean`, `logs`, and `status` use it only to resolve ambiguity. |
| `--profile PATH` | Override `modding_profile_path` for this invocation. The preferences file is still required by commands that load context. |
| `--launcher PATH` | Select a concrete launcher file for this invocation. It is a path, not a shell command. An explicit launcher emits a warning, especially when it is outside the profile. |
| `--unity-log-dir PATH` | Override `unity_log_dir` for this invocation without editing `preferences.md`. |

### `run`: build, deploy, launch, and optionally wait

```text
<TEST_CLI> run [common options]
    [--configuration Debug|Release]
    [--artifact PATH]
    [--dry-run]
    [--startup-timeout SECONDS]
```

`run` uses the selected project and profile context, with explicit common options overriding saved preferences for this invocation. `--artifact` switches to deploy-only selection; `--dry-run` validates and prints the plan without deployment or launch.

Expected behavior, in order:

1. CLI MUST validate native environment, preferences, project selection, and profile.
2. With no `--artifact`, CLI MUST run equivalent of `dotnet build <project.csproj> --configuration <configuration>`. `Debug` is default. Agent MUST use `--configuration Release` only when user explicitly requests release build; Debug may contain test statements and test code blocks.
3. CLI MUST read project's declared `<TargetName>` and validate complete package under `publish/<TargetName>`.
4. CLI MUST refuse conflicting game instance before deployment. CLI MUST copy every safe file below package root to matching relative path below profile's `Modding` root, creating only missing subdirectories.
5. CLI MUST record deployment manifest and print deployment session identifier.
6. CLI MUST launch selected profile-local executable with profile as its working directory and track exact process identity and child tree. CLI MUST NOT use Steam URI.
7. CLI MUST print `launched` immediately when no timeout is requested. With `--startup-timeout SECONDS`, CLI MUST poll current log evidence until target mod is found or timeout expires, then perform one final evidence read at the timeout boundary.

`--dry-run` performs environment, project, profile, build/artifact, and package validation and prints file plan. It does not copy profile files or launch process. When no `--artifact` is provided, build still runs because build output is part of plan; use explicit artifact for no-build inspection.

Completion criterion: successful non-dry run prints session identifier, deployment state, launch state, and process ID; timed-out run prints timeout evidence and leaves process and session available for diagnosis.

### Build and artifact selection

Project selection is deterministic:

- `--project PATH` MUST name existing `.csproj`.
- Without `--project`, `run` accepts exactly one `.csproj` in current directory.
- Zero projects or multiple projects require explicit `--project` and are usage/configuration failures.

Solution selection is deterministic:

- The CLI inspects `.sln` and `.slnx` files in the project directory and its ancestors in stable path order.
- Classic `.sln` project entries are read from their project-path fields. XML `.slnx` project entries are read from `Project` elements' `Path` attributes.
- Exactly one solution that lists the requested project is selected. Multiple matching solutions, or duplicate membership of the requested project within one solution, fail as build errors; the CLI never guesses.
- If no inspected solution contains the project, the project directory is the explicit build-root fallback, even when unrelated solutions exist.
- The artifact plan prints the selected solution (or fallback), solution root, and trailing-separator `SolutionDir`. Normal packages remain rooted at `<selected-root>/publish/<TargetName>`.

Normal build artifact is package directory under `publish` directory selected by project's solution/build layout:

```text
<solution-or-project root>/publish/<TargetName>/
```

E.g. when project declares `TargetName` as `CustomBackgrounds`, every file under `publish/CustomBackgrounds/` is part of deployment: plugin assemblies, data dependencies, localization, images, JSON, and other resources. package-relative directory structure is preserved. CLI does not select one DLL or discard files by extension.

Agent SHOULD use `--artifact PATH` only when exact input is already known:

- Directory is treated as package root and is not rebuilt.
- `.zip` is extracted into temporary state, validated, and then deployed; it never writes directly into profile during extraction.
- Zip input is recovery path for seriously abnormal or unavailable package directory. It is not selected by timestamp and it is not silent fallback.
- Empty packages, unsafe relative paths, absolute paths, parent traversal, symlinks, hard-link destinations, case-colliding paths, and malformed archive entries fail before deployment.

Completion criterion: printed artifact plan names one `TargetName`, one package root, one artifact kind, and all files that will be copied; no ambiguous or guessed artifact is accepted.

### Profile and launcher preflight

Selected `modding_profile_path` MUST be directory containing:

```text
<profile>/Modding/
<profile>/BepInEx/core/BepInEx.dll
```

Selected profile MUST also contain non-empty launcher. Known launchers are selected only inside profile:

| Host | Default candidates |
| --- | --- |
| Windows | `<profile>/Blasphemous.exe` |
| Linux | `<profile>/Blasphemous.x86_64`, then `<profile>/Blasphemous` |
| macOS | `<profile>/Blasphemous.app/Contents/MacOS/Blasphemous`, then `<profile>/Blasphemous` |

`--launcher PATH` accepts one concrete existing file, checks executability where host requires it, and passes it directly to process API. It does not accept arbitrary shell syntax, pipelines, arguments, or command string. explicit path may be outside profile, but CLI emits warning; treat that as user-visible safety exception. game is started with `shell=False` and profile as its working directory.

Completion criterion: preflight has identified exact profile, `Modding` root, BepInEx root, and launcher, and any launcher override warning is visible to agent and user.

### `stop`: stop one tracked session

```text
<TEST_CLI> stop SESSION_ID [--force]
```

`stop` operates only on process identity recorded in that session manifest and its captured child tree. It never selects process by name and never attaches to unrelated game. Without `--force`, request normal stop; `--force` is limited to same tracked tree when graceful termination does not finish.

Command is idempotent:

- `stopped`: this invocation terminated tracked tree.
- `exited`: tracked process had already exited.
- `gone`: valid session manifest is already absent; no process was touched.

Completion criterion: tracked process is stopped or confirmed gone, and no unrelated process was terminated.

### `logs`: read current startup evidence

```text
<TEST_CLI> logs SESSION_ID [common options] [--full]
```

`logs` uses the selected profile and log-directory context. `--project`, `--profile`, `--launcher`, and `--unity-log-dir` override saved values for this invocation; `--full` is the only logs-specific output override.

CLI reads existing logs in place and stores only bounded evidence metadata in temporary session manifest. It does not create persistent log report or copy log contents. Default output is last 200 lines per source; `--full` prints complete current file. Evidence hits retain source label, concrete path, line number, match reason, kind, bounded text, and available `mod_id`/`mod_name` independently of the output tail, so early startup hits remain reportable without unbounded output.

Sources are:

```text
BepInEx: <profile>/BepInEx/LogOutput.log
Unity:   <unity_log_dir>/output_log.txt       (Windows)
Unity:   <unity_log_dir>/Player.log           (native Linux/macOS, then output_log.txt)
```

`unity_log_dir` is optional in schema but REQUIRED to locate Unity log. On Windows, usual directory is `%USERPROFILE%/AppData/LocalLow/TheGameKitchen/Blasphemous`; agent MUST configure that directory explicitly when it is not already in `preferences.md`. If directory or file is missing, CLI MUST print warning, agent MUST ask user for correct directory, and agent MUST save `unity_log_dir: PATH` in active `preferences.md` after user supplies it. one-run `--unity-log-dir PATH` override is available while confirming value.

`LogOutput.log` contains current BepInEx run and overwrites previous run; there is no BepInEx history or polling log to recover. launcher records a metadata-and-content baseline, so existing log is marked `stale` and ignored for this session unless its content changes after launch. missing or unreadable BepInEx log is hard logs/readiness failure. missing Unity log is warning and requires user handoff above.

Package `TargetName` identifies the publish package, not necessarily the runtime Mod identity. The CLI persists bounded runtime aliases derived from `TargetName`, an explicit project `AssemblyName`, and the project name. Structured ModdingAPI or Mod Loader registration evidence exposes the canonical `mod_id`; standard BepInEx `Loading`/`Loaded` evidence exposes the human-readable `mod_name`. Mod Loader identity is preferred for target matching. A BepInEx display name participates only through an explicit display-name alias or as corroborating context; it is never rewritten as a canonical ID. Positive target evidence requires a current BepInEx chainloader readiness record plus an exact structured target record. Paths, errors, and unstructured mentions do not count. A target error before positive registration prevents promotion; a later target error is retained as diagnostic metadata without demoting an already established load. The session manifest retains bounded source, path, line, reason, kind, text, and available identity metadata for matched evidence; it never copies a log.

Startup states are deliberately narrower than gameplay results:

| State | Automated evidence |
| --- | --- |
| `launched` | The selected profile-local launcher produced a safely tracked process, but current BepInEx readiness is not established. |
| `ready` | The current BepInEx log contains chainloader readiness evidence, including `Chainloader startup complete`. |
| `mod_loaded` | `ready` plus current structured ModdingAPI or Mod Loader registration, or standard BepInEx loading evidence, matching a derived runtime alias exactly. |
| `timeout` | `--startup-timeout` expired before `mod_loaded`; the session and process remain for diagnosis. |

Completion criterion: agent reports state, current/stale/missing status of both sources, relevant warnings, and bounded or full log output requested by user.

### `status`: read-only session view

```text
<TEST_CLI> status [common options]
```

`status` resolves context only to select the profile and display sessions. Its output is read-only; context options override saved values for this invocation, and no build, deployment, launch, log read, or cleanup option is accepted.

`status` prints selected context and sessions newest first. Each entry reports its role (`active`, `archived`, or `cleaned`), deployment history, cleanup completion, a read-only process observation, and evidence state. The deployment label is marked `current` only for the active session; archived or cleaned deployments are marked `history`. Cleanup is marked `complete` only when the manifest records `cleanup_state: cleaned`. A tracked process that has already exited may therefore appear as `process=exited (observation)` while its manifest remains unchanged; status never rewrites process state.

Completion criterion: agent can discover newest session and all older rollback sessions without changing profile.

### `clean`: newest-first safe rollback

```text
<TEST_CLI> clean SESSION_ID [common options]
    [--remove-new-files]
```

`clean` resolves the session's profile context before rollback. `--project`, `--profile`, `--launcher`, and `--unity-log-dir` override saved values for this invocation; `--remove-new-files` is the only cleanup-specific mutation approval.

Agent MUST stop session first, then clean it. CLI also refuses to clean while tracked game process is still running. Cleanup uses newest-first session stack:

1. Clean newest cleanable session before any older session.
2. Older session with newer active or archived rollback point is rejected; agent MUST NOT bypass this order.
3. Overwritten files are restored only when their current hash still equals hash deployed by this session. file changed during testing is protected and causes safe clean to report conflict without silently overwriting it.
4. Files first created by this session are retained by default, even after process stops. `--remove-new-files` explicitly approves removal only when file is still unchanged; changed, linked, or non-regular paths remain protected.
5. Session manifests remain in temporary state after cleanup, so repeated cleanup is idempotent and `status` can show result.
6. `clean` prints one `Cleanup files:` entry for every completed package file using `action package-relative/path: reason`. Actions are `restored`, `removed`, or `retained`; protection conflicts use `protected package-relative/path: reason`. The same outcomes are persisted as `cleanup_outcomes` in the session manifest.

Default policy therefore restores old files but does not delete new files. If older session is blocked, inspect `status`, stop/clean newer session, then retry older one. If file was changed by user, preserve it and ask whether user wants separate manual resolution.

Completion criterion: requested session is `cleaned` or `already-cleaned`, every restored/removed/retained file is reported with its package-relative path and reason, protected files are reported with their protection reason and remain unchanged, and an already-exited tracked process is safely recorded as exited before cleanup.

## Preferences and CLI overrides

Shared [Invocation preflight](../config/invocation-preflight.md) owns preference scope selection, project-over-user precedence, first-time setup, path recovery, and tracked-session stop exception. After it selects active file, this CLI requires `modding_profile_path`.

Explicit CLI options override selected preference for that invocation: `--profile`, `--project`, `--launcher`, and `--unity-log-dir`. CLI does not rewrite preferences; after missing-log handoff, agent writes user-supplied Unity log directory into active file.

`stop SESSION_ID` is this workflow's implementation of tracked-session recovery exception and uses only recorded session state plus host process check. `run`, `clean`, `logs`, and `status` require normal Invocation preflight and profile gate.

## Automated evidence versus Manual verification

Automated boundary ends at profile launch, startup log evidence, process stop, and safe cleanup. Agent MUST NOT claim that `mod_loaded` proves game behavior.

After startup evidence is available, ask player to perform requested in-game scenario. Collect **Manual verification** in natural language:

- scene or save state used;
- exact player actions;
- expected result;
- observed result, including visual, input, combat, menu, save, or other behavior;
- any visible error or approximate time at which it occurred.

Combine that Manual verification record with CLI state and two current logs when diagnosing test. No gameplay transcript, log copy, or generated test report is required by this workflow. Use existing [log analyzer](log-analyzer.md) for interpretation after test evidence is collected.

## Stable failures and recovery

CLI prints `Error [category]` and returns stable categories. Route recovery by exit code:

| Code | Category | Typical cause | Recovery |
| ---: | --- | --- | --- |
| `0` | success | Operation completed. | Continue to the next workflow step. |
| `2` | usage/configuration | Invalid arguments, ambiguous project, unsupported shell/OS, or compatibility layer. | Correct the invocation and use native PowerShell or native Bash. |
| `10` | profile/preferences | Missing/invalid preferences, missing profile directories, missing BepInEx core, or missing/invalid launcher preflight. | Complete first-time setup, verify `modding_profile_path`, `Modding`, `BepInEx/core/BepInEx.dll`, and launcher; use explicit path overrides only for the intended invocation. |
| `20` | build | `dotnet build` could not start, parse the project, or returned a failure. | Read the build output, fix the project/dependencies, and rerun. No old package is silently substituted. |
| `30` | package artifact | Missing/empty package, unsafe directory/archive entry, missing `<TargetName>`, or explicit artifact is not a directory/zip. | Inspect `publish/<TargetName>`, pass the exact package directory with `--artifact`, or explicitly use a validated recovery zip. |
| `40` | deployment | Destination preflight, copy, hash verification, or transaction rollback failed. | The agent MUST NOT manually delete profile files. If rollback succeeded, retry after fixing the cause. If rollback failed, retain the printed session ID, inspect the manifest/status, and resolve protected files with the user before any further deployment. |
| `50` | launch | A matching game is already running, launcher start failed, or process identity could not be safely tracked. | Stop only the known session if applicable, verify the profile-local launcher, then rerun. Never attach to or kill an untracked process. |
| `60` | logs/readiness | Current BepInEx log missing/unreadable or startup timeout. | Keep the session alive; run `logs SESSION_ID`, configure `unity_log_dir`, inspect current BepInEx output, ask for the Manual verification description, then stop and clean when diagnosis is complete. |
| `70` | stop/clean | Unknown session/process state, running tracked process, newer session, changed file, or invalid rollback manifest. | Use `status`, stop the tracked process, clean newest-first, and preserve changed files. Retry only after the reported guard is resolved. |

Deployment failures are transactional: partial copy is rolled back automatically when possible. failed rollback is hard stop with session identifier; it is not permission to remove whole `Modding` root. failure to archive previous sessions also attempts to roll back new deployment and reports whether that recovery succeeded.

## Acceptance criteria

Agent MUST use this checklist for complete implementation or Manual verification:

- [ ] Agent can invoke `run`, `stop`, `clean`, `logs`, and `status` with documented argument contract on native Windows PowerShell and native Linux/macOS Bash.
- [ ] Project selection is explicit when ambiguous; default builds use Debug; Release requires explicit option.
- [ ] build package resolves to `publish/<TargetName>` and every file below that package root is planned and deployed with its relative path preserved.
- [ ] explicit directory artifact works without build; explicit zip is temporary, path-validated, and never selected implicitly.
- [ ] Profile preflight rejects incomplete profile, uses profile-local known launcher by default, and warns on explicit launcher override.
- [ ] CLI never uses Steam URI, arbitrary shell command, process-name kill, or broad profile deletion.
- [ ] successful run records session and process identity; repeated runs archive older sessions and print warning.
- [ ] `stop` is limited to tracked process tree and is idempotent for exited or missing session state.
- [ ] `clean` is newest-first, restores only hash-compatible overwritten files, retains new files by default, and requires `--remove-new-files` for unchanged new-file removal.
- [ ] Current BepInEx and configured Unity logs produce bounded output by default and full output only with `--full`; missing Unity configuration produces visible handoff warning.
- [ ] Automated startup evidence is reported as `launched`, `ready`, `mod_loaded`, or `timeout`; Manual verification is collected from player in natural language.
- [ ] Missing profile, build, artifact, launcher, log, timeout, deployment, and rollback conditions map to stable failure categories and recovery steps above.

Design decisions behind this contract are recorded in [Blasphemous mod test spec](../../../../docs/specs/blasphemous-modding-test.md), [stack-safe rollback ADR](../../../../docs/adr/0001-stack-safe-mod-test-rollback.md), and [Python CLI ADR](../../../../docs/adr/0002-python-stdlib-test-cli.md).
