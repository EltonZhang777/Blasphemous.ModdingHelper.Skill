# Blasphemous Source Analyzer

## Description
This sub-skill analyzes the Blasphemous game source code, with a focus on game mechanics, code structure, and dependencies relevant to Mod development.

## Core Capabilities
- Blasphemous game source-code structure analysis
- Key game-logic component identification
- Code-dependency and reference resolution
- Mod-development insight

## Entry conditions

Before source analysis, the agent MUST complete [Invocation preflight](../config/invocation-preflight.md). This branch adds the source-path requirement: the active `preferences.md` MUST provide at least one valid `full_source_code_path` or `lightweight_source_code_path`.

## Analysis Approach
1. The agent MUST analyze the user input to extract the expected pattern, the source-code details to find, and the source-code file to check when one is specified.
2. The agent MUST prioritize searching in the lightweight solution first and SHOULD use the full solution only when necessary.
3. The agent SHOULD check for available MCP tools at this step to see whether a tool can quickly navigate and analyze C# code structure (for example, roslyn-code-navigator).
4. The agent SHOULD prioritize using MCP tools when relevant tools are available.
5. If no relevant MCP tool is available, the agent MUST use command-line tools to search for and read relevant class files and code sections. The agent SHOULD use these navigation tips:
    - The agent SHOULD use [../source_code_navigation/MAIN.md](../source_code_navigation/MAIN.md) to navigate major source-code sections; it indexes every specialized navigation document (core, player, enemy, bosses, ui, items, level, tools, localization) with its coverage.
    - The agent SHOULD prioritize searching in the `Assembly-CSharp` folder because almost all game-logic code is located there.

## Completion criteria

The agent MUST mark source analysis complete only when the active preferences file and the source path used are recorded, the relevant source evidence has been checked, and every cited class or file path has been verified against the selected source tree. If the required source paths are missing or invalid, the agent MUST report the exact missing path and the next setup or recovery action instead of claiming completion.

