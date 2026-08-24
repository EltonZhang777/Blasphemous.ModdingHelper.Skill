# Blasphemous Source Analyzer

## Description
This sub-skill analyzes Blasphemous game source code, with focus on game mechanics, code structure, and dependencies relevant to Mod development.

## Core Capabilities
- Blasphemous game source-code structure analysis
- Key game-logic component identification
- Code-dependency and reference resolution
- Mod-development insight

## Entry conditions

Before source analysis, agent MUST complete [Invocation preflight](../config/invocation-preflight.md). This branch adds source-path requirement: active `preferences.md` MUST provide at least one valid `full_source_code_path` or `lightweight_source_code_path`.

## Analysis Approach
1. Agent MUST analyze user input to extract expected pattern, source-code details to find, and source-code file to check when one is specified.
2. Agent MUST prioritize searching in lightweight solution first and SHOULD use full solution only when necessary.
3. Agent SHOULD check for available MCP tools at this step to see whether tool can quickly navigate and analyze C# code structure (e.g. roslyn-code-navigator).
4. Agent SHOULD prioritize using MCP tools when relevant tools are available.
5. If no relevant MCP tool is available, agent MUST use command-line tools to search for and read relevant class files and code sections. Agent SHOULD use these navigation tips:
    - The agent SHOULD use [../source_code_navigation/MAIN.md](../source_code_navigation/MAIN.md) to navigate major source-code sections; it indexes every specialized navigation document (core, player, enemy, bosses, ui, items, level, tools, localization) with its coverage.
    - The agent SHOULD prioritize searching in the `Assembly-CSharp` folder because almost all game-logic code is located there.

## Completion criteria

Agent MUST mark source analysis complete only when active preferences file and source path used are recorded, relevant source evidence has been checked, and every cited class or file path has been verified against selected source tree. If required source paths are missing or invalid, agent MUST report exact missing path and next setup or recovery action instead of claiming completion.

