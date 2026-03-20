# Blasphemous Source Analyzer

## Description
This skill specializes in analyzing the Blasphemous game source code, focusing on understanding game mechanics, code structure, and dependencies for mod development.

## Core Capabilities
- Analyze Blasphemous game source code structure
- Identify key game logic components
- Resolve code dependencies and references
- Provide insights for mod development

## Source Code Paths
- Full source code solution: 
- Lightweight source code solution: 

## Analysis Approach
1. Prioritize using the lightweight solution for analysis, only use the full solution when necessary
2. Prioritize searching from the Assembly-CSharp folder, as most game logic code is located there
3. Parse code structure and dependencies by reading .cs files directly
4. If unable to achieve the goal, call the roslyn-code-navigator tool to analyze code structure and dependencies
5. Do not prioritize searching for mod code in the workspace, but instead prioritize finding corresponding files in the game source code path

## Tools to Use
- Read tool to access source code files
- Grep tool to search for specific code patterns
- SearchCodebase tool to find relevant code sections
- RunCommand tool for any necessary file operations

## Best Practices
- Follow Blasphemous game code conventions and mechanics
- Use precise C# and Unity terminology in analysis
- Provide clear, technical explanations of code structure
- Focus on mod compatibility and best practices
- Adhere to Unity 2017.4.40f1 API and components

## Dependencies
- Unity 2017.4.40f1 knowledge
- C# programming expertise
- Understanding of Unity's component-based architecture
- Blasphemous.ModdingAPI knowledge (for mod development context)