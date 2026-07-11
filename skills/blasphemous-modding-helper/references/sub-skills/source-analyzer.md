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
    - Use the specialized navigation documents for targeted searches:
      - [core.md](../source_code_navigation/core.md) — Core framework: Managers, Attributes, Audio, Dialog, Map, Penitences, DLC, Achievements
      - [player.md](../source_code_navigation/player.md) — Player Penitent: Abilities, Attacks, Movement, Input, Animation
      - [enemy.md](../source_code_navigation/enemy.md) — Enemy system: All enemy types, AI Framework, Entity base classes
      - [bosses.md](../source_code_navigation/bosses.md) — Boss system: All bosses, BossFightManager, Common Attacks
      - [ui.md](../source_code_navigation/ui.md) — UI system: UIController, Widgets, MenuLogic, HUD, Console commands
      - [items.md](../source_code_navigation/items.md) — Item/Equipment: Inventory types, Effects, Achievements
      - [level.md](../source_code_navigation/level.md) — Level/Environment: Actionables, Interactables, Layout
      - [tools.md](../source_code_navigation/tools.md) — Tools: PlayMaker Actions/Conditions/Events, Audio, Data containers, NPC
      - [localization.md](../source_code_navigation/localization.md) — Localization: I2.Loc, Blasphemous LocalizationManager
    - Prioritize searching in the Assembly-CSharp folder, as almost all game logic code is located there.

