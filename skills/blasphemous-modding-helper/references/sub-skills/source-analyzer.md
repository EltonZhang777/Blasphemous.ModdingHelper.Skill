# Blasphemous Source Analyzer

## Description
Analyze and understand the Blasphemous game source code, focusing on understanding game mechanics, code structure, and dependencies/relevance for mod development.

## Core Capabilities
- Analyze Blasphemous game source code structure
- Identify key game logic components
- Resolve code dependencies and references
- Provide insights for mod development

## Analysis Approach
1. Check `preferences.md` for available paths of `full_source_code_path` and `lightweight_source_code_path`. There should be at least one valid path.
2. Analyze user input to extract user's expected pattern, things to look for in source code, and which source code file to check (if specified).
3. Prioritize searching in the lightweight solution first, only use the full solution when necessary.
5. You SHOULD check for available MCP tools at this step to see if any tool can help you quickly navigate and analyze C# code structure (e.g. roslyn-code-navigator). 
6. Prioritize using MCP tools if available. 
7. If no relevant MCP tool is available, use command line tools to search for and read relevant class files and code sections. Utilize the following tips to help searching:
    - Use [../source_code_navigation/MAIN.md](../source_code_navigation/MAIN.md) to navigate around major sections of the source code.
    - Prioritize searching in the Assembly-CSharp folder, as almost all game logic code is located there.

