# Blasphemous Log Analyzer

This sub-skill analyzes Blasphemous log files, focusing on debugging Mod-related issues and tracking errors.

## Core Capabilities
- Log-file analysis for bugs and errors
- Unity and Mod log information and stack-trace interpretation
- Mod-code issue prioritization during bug analysis

## Entry conditions

Before log analysis, agent MUST complete [Invocation preflight](../config/invocation-preflight.md). This branch adds log-source requirements: active `preferences.md` MUST provide `modding_profile_path`, and `unity_log_dir` MUST be resolved when Unity evidence is needed.

## Log File Paths
- Blasphemous Unity log file: resolve `unity_log_dir` from `preferences.md`; Windows normally uses `$env:USERPROFILE/AppData/LocalLow/TheGameKitchen/Blasphemous/output_log.txt`, while native Linux/macOS profiles normally use `Player.log` under configured directory
- BepInEx log file: `<modding_profile_path>/BepInEx/LogOutput.log`
  - Agent MUST acquire `<modding_profile_path>` from `preferences.md`.

## Analysis Approach

1. Agent MUST analyze user input to extract expected pattern, log details to find, and log file to check when one is specified.
2. Agent MUST check BepInEx log file first. Almost all error-level and warning-level messages are documented there, as are all levels of Mod log output.
3. If BepInEx log file cannot provide enough information, or user specifies Blasphemous Unity log file, agent MUST examine that Unity log for more comprehensive information.
4. Agent MUST provide clear, technical analysis of log contents.

## Startup evidence handoff

When mod-test CLI reports missing Unity log directory or log:

1. Agent MUST ask user for directory that contains current Unity log.
2. Agent MUST add `unity_log_dir: PATH` to active `preferences.md`, or pass `--unity-log-dir PATH` for one-run override. active file is scope selected by [Invocation preflight](../config/invocation-preflight.md).
3. Agent MUST re-run `logs SESSION_ID` or explicit startup-evidence wait.

This step is complete only when CLI resolves Unity log or warning remains visible with exact missing path and preference file to update. CLI reads existing BepInEx and Unity logs in place; it does not create persistent log copies.

`launched`, `ready`, and `mod_loaded` are startup states. They MUST NOT be used to verify visual, input, combat, menu, save, or other gameplay behavior. After startup evidence is collected, agent MUST ask player to operate game and report observed behavior in natural language; agent MUST treat that report as manual gameplay evidence.

## Startup diagnostic ownership

The `logs` operation keeps structured warning and error records as bounded evidence
hits with an ownership group:

| Group | Meaning |
| --- | --- |
| `target` | The record contains a derived target runtime alias and is relevant to the target Mod. |
| `framework` | The record belongs to a recognized BepInEx, ModdingAPI, Unity, or related framework source and is not target-owned. |
| `baseline` | The record is a structured warning/error within the exact pre-session byte prefix retained by the current log. This is provenance, not a harmlessness claim. |
| `unknown` | The record is not target-owned, is not from a recognized framework source, and has no proven session baseline; it remains visible without an ownership claim. |

The launcher captures only pre-session file metadata (including size, digest, and
line count). A current source receives `baseline` labels only when its retained
prefix still matches that digest and ends at a complete line boundary; a
rewritten, truncated, missing, or otherwise unproven prefix receives no
baseline labels. Baseline labels do not suppress or delete log lines. Newly
observed warnings and errors remain visible as `framework` or `unknown`
evidence, and target-owned errors remain beside the startup result. The report
stays bounded and does not persist a complete log copy.

## Completion criteria

Agent MUST mark log analysis complete only when report contains all of these:

1. Active preferences file and every log source inspected, or exact missing path and required preference-update handoff.
2. Expected pattern, relevant log evidence, and conclusion tied to that evidence. If BepInEx log is sufficient, agent MUST state that Unity-log read was not required; otherwise, Unity-log result MUST be included.
3. Concrete next action: code/configuration change, another evidence request, tracked-session operation, or player Manual verification.

Missing or unreadable evidence is not successful analysis. analysis is complete in that case only when warning names missing source, active preferences file, and next action needed to recover.

