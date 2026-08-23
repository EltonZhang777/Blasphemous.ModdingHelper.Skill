# Blasphemous Log Analyzer

This sub-skill analyzes Blasphemous log files, focusing on debugging Mod-related issues and tracking errors.

## Core Capabilities
- Log-file analysis for bugs and errors
- Unity and Mod log information and stack-trace interpretation
- Mod-code issue prioritization during bug analysis

## Log File Paths
- Blasphemous Unity log file: resolve `unity_log_dir` from `preferences.md`; Windows normally uses `$env:USERPROFILE/AppData/LocalLow/TheGameKitchen/Blasphemous/output_log.txt`, while native Linux/macOS profiles normally use `Player.log` under the configured directory
- BepInEx log file: `<modding_profile_path>/BepInEx/LogOutput.log`
  - The agent MUST acquire `<modding_profile_path>` from `preferences.md`.

## Analysis Approach

1. The agent MUST analyze the user input to extract the expected pattern, the log details to find, and the log file to check when one is specified.
2. The agent MUST check the BepInEx log file first. Almost all error-level and warning-level messages are documented there, as are all levels of Mod log output.
3. If the BepInEx log file cannot provide enough information, or the user specifies the Blasphemous Unity log file, the agent MUST examine that Unity log for more comprehensive information.
4. The agent MUST provide clear, technical analysis of the log contents.

## Startup evidence handoff

When the mod-test CLI reports a missing Unity log directory or log:

1. The agent MUST ask the user for the directory that contains the current Unity log.
2. The agent MUST add `unity_log_dir: PATH` to the active `preferences.md`, or pass `--unity-log-dir PATH` for a one-run override. Project preferences MUST take precedence over user preferences.
3. The agent MUST re-run `logs SESSION_ID` or the explicit startup-evidence wait.

This step is complete only when the CLI resolves the Unity log or the warning remains visible with the exact missing path and preference file to update. The CLI reads the existing BepInEx and Unity logs in place; it does not create persistent log copies.

`launched`, `ready`, and `mod_loaded` are startup states. They MUST NOT be used to verify visual, input, combat, menu, save, or other gameplay behavior. After startup evidence is collected, the agent MUST ask the player to operate the game and report the observed behavior in natural language; the agent MUST treat that report as the manual gameplay evidence.

## Completion criteria

The agent MUST mark log analysis complete only when the report contains all of the following:

1. The active preferences file and every log source inspected, or the exact missing path and the required preference-update handoff.
2. The expected pattern, relevant log evidence, and a conclusion tied to that evidence. If the BepInEx log is sufficient, the agent MUST state that a Unity-log read was not required; otherwise, the Unity-log result MUST be included.
3. A concrete next action: a code/configuration change, another evidence request, a tracked-session operation, or player Manual verification.

Missing or unreadable evidence is not a successful analysis. The analysis is complete in that case only when the warning names the missing source, the active preferences file, and the next action needed to recover.

