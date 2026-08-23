# Blasphemous Log Analyzer

Analyze log files for the game Blasphemous, focusing on debugging mod-related issues and error tracking.

## Core Capabilities
- Analyze log files to identify bugs and errors
- Interpret Unity and mod log information and stack traces
- Prioritize mod code issues when analyzing bugs

## Log File Paths
- Blasphemous Unity log file: resolve `unity_log_dir` from `preferences.md`; Windows normally uses `$env:USERPROFILE/AppData/LocalLow/TheGameKitchen/Blasphemous/output_log.txt`, while native Linux/macOS profiles normally use `Player.log` under the configured directory
- BepInEx log file: `<modding_profile_path>/BepInEx/LogOutput.log`
  - `<modding_profile_path>` should be acquired from `preferences.md`

## Analysis Approach

1. Analyze user input to extract user's expected pattern, things to look for in log files, and which log file to check (if specified).
2. Check the BepInEx log file first. Almost all error-level and warning-level messages are documented here. All levels of modded log are documented here.
3. If the BepInEx log file cannot provide enough information, or user specifies to check Blasphemous Unity log file, examine the Blasphemous Unity log file for more comprehensive information
4. Provide clear, technical analysis of log contents

## Startup evidence handoff

When the mod-test CLI reports a missing Unity log directory or log:

1. Ask the user for the directory that contains the current Unity log.
2. Add `unity_log_dir: PATH` to the active `preferences.md`, or pass `--unity-log-dir PATH` for a one-run override. Project preferences take precedence over user preferences.
3. Re-run `logs SESSION_ID` or the explicit startup-evidence wait.

This step is complete only when the CLI resolves the Unity log or the warning remains visible with the exact missing path and preference file to update. The CLI reads the existing BepInEx and Unity logs in place; it does not create persistent log copies.

`launched`, `ready`, and `mod_loaded` are startup states. They do not verify visual, input, combat, menu, save, or other gameplay behavior. After startup evidence is collected, ask the player to operate the game and report the observed behavior in natural language; treat that report as the manual gameplay evidence.

