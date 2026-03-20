# Blasphemous Source Analyzer

## Description
Analyze and understand the Blasphemous game source code, focusing on understanding game mechanics, code structure, and dependencies/relevance for mod development.

## Core Capabilities
- Analyze Blasphemous game source code structure
- Identify key game logic components
- Resolve code dependencies and references
- Provide insights for mod development

## Analysis Approach
1. Analyze user input to extract user's expected pattern, things to look for in source code, and which source code file to check (if specified).
2. Prioritize using the lightweight solution for analysis, only use the full solution when necessary.
3. Prioritize searching from the Assembly-CSharp folder, as almost all game logic code is located there
4. You SHOULD check for available MCP tools at this step to see if any tool can help you analyze C# code structure (e.g. roslyn-code-navigator). 
5. Prioritize using MCP tools if available. If no relevant MCP tool is available, use command line tools to search for and read relevant class files and code sections.

