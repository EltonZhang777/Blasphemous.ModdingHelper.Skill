# Blasphemous Modding Skill for AI agent

A AI agent skill that provides expert assistance with Blasphemous mod development. It helps you work with the decompiled C# source code, analyze game mechanics, debug logs, and create custom mods for the game _Blasphemous_ based on the [ModdingAPI](https://github.com/BrandenEK/Blasphemous.ModdingAPI)'s framework and conventions.

## What's Included

- **SKILL.md** : Top-level skill configuration with coding specifications, preferences management, and workflow guidelines
- **Source Code Navigation Guides** : Brief AI-friendly documentation for navigating the decompiled Blasphemous source code.
- **Sub-Skills** : Specialized analysis tools:
  - **Source Analyzer** : Instructions on how to read and analyze game source code to understand game mechanics, code structure, and dependencies
  - **Log Analyzer** : Debug and error tracking for mod development, can read both BepInEx and Unity logs
- **Configuration Reference** : Documentation for preferences/config management and first-time setup

## Installation

Currently only supports manual installation.

### As a Skill (manual)

1. Download the skill from the [release page](https://github.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/releases).
2. Extract the skill to the skill folder of your AI coding tool (Claude Code, OpenCode, TRAE, etc).
3. Restart the AI coding tool to load the skill if the skill doesn't show up.

## Requirements

- Any AI coding tool that supports skills.
- A decompiled C# solution of Blasphemous' source code.
- A modded Blasphemous profile with BepInEx and ModdingAPI installed. It should better be managed by the [Mod Installer](https://github.com/BrandenEK/Blasphemous.Modding.Installer).
