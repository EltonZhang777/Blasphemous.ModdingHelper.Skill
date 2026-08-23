# Blasphemous Source Analyzer

## Description
This sub-skill analyzes the Blasphemous game source code, with a focus on game mechanics, code structure, and dependencies relevant to Mod development.

## Core Capabilities
- Blasphemous game source-code structure analysis
- Key game-logic component identification
- Code-dependency and reference resolution
- Mod-development insight

## Analysis Approach
1. The agent MUST check `preferences.md` for available `full_source_code_path` and `lightweight_source_code_path` values. At least one valid path MUST exist.
2. The agent MUST analyze the user input to extract the expected pattern, the source-code details to find, and the source-code file to check when one is specified.
3. The agent MUST prioritize searching in the lightweight solution first and SHOULD use the full solution only when necessary.
4. The agent SHOULD check for available MCP tools at this step to see whether a tool can quickly navigate and analyze C# code structure (for example, roslyn-code-navigator).
5. The agent SHOULD prioritize using MCP tools when relevant tools are available.
6. If no relevant MCP tool is available, the agent MUST use command-line tools to search for and read relevant class files and code sections. The agent SHOULD use these navigation tips:
    - The agent SHOULD use [../source_code_navigation/MAIN.md](../source_code_navigation/MAIN.md) to navigate major source-code sections; it indexes every specialized navigation document (core, player, enemy, bosses, ui, items, level, tools, localization) with its coverage.
    - The agent SHOULD prioritize searching in the `Assembly-CSharp` folder because almost all game-logic code is located there.

