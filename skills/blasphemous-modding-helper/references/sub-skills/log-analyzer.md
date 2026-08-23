# Blasphemous Log Analyzer

This sub-skill analyzes Blasphemous log files, focusing on debugging Mod-related issues and tracking errors.

## Core Capabilities
- Log-file analysis for bugs and errors
- Unity and Mod log information and stack-trace interpretation
- Mod-code issue prioritization during bug analysis

## Log File Paths
- Blasphemous Unity log file: `$env:USERPROFILE/AppData/LocalLow/TheGameKitchen/Blasphemous/output_log.txt`
- BepInEx log file: `<modding_profile_path>/BepInEx/LogOutput.log`
  - The agent MUST acquire `<modding_profile_path>` from `preferences.md`.

## Analysis Approach

1. The agent MUST analyze the user input to extract the expected pattern, the log details to find, and the log file to check when one is specified.
2. The agent MUST check the BepInEx log file first. Almost all error-level and warning-level messages are documented there, as are all levels of Mod log output.
3. If the BepInEx log file cannot provide enough information, or the user specifies the Blasphemous Unity log file, the agent MUST examine that Unity log for more comprehensive information.
4. The agent MUST provide clear, technical analysis of the log contents.

