# Blasphemous Log Analyzer

Analyze log files for the game Blasphemous, focusing on debugging mod-related issues and error tracking.

## Core Capabilities
- Analyze log files to identify bugs and errors
- Interpret Unity and mod log information and stack traces
- Prioritize mod code issues when analyzing bugs

## Log File Paths
- Blasphemous Unity log file: `$env:USERPROFILE/AppData/LocalLow/TheGameKitchen/Blasphemous/output_log.txt`
- BepInEx log file: `<modding_profile_path>/BepInEx/LogOutput.log`
  - `<modding_profile_path>` should be acquired from `preferences.md`

## Analysis Approach

1. Analyze user input to extract user's expected pattern, things to look for in log files, and which log file to check (if specified).
2. Check the BepInEx log file first. Almost all error-level and warning-level messages are documented here. All levels of modded log are documented here.
3. If the BepInEx log file cannot provide enough information, or user specifies to check Blasphemous Unity log file, examine the Blasphemous Unity log file for more comprehensive information
4. Provide clear, technical analysis of log contents

