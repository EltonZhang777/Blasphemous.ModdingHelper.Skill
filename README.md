# Blasphemous Modding Helper for AI Agents

[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Plugin](https://img.shields.io/badge/Claude%20Code-plugin-blueviolet)](#-install)

An AI agent skill that provides expert assistance with **Blasphemous mod development**. Helps you work with decompiled C# source code, analyze game mechanics, debug logs, and create custom mods using the [ModdingAPI](https://github.com/BrandenEK/Blasphemous.ModdingAPI) framework.

---

## 🚀 Install

### One command (auto-detects your agents)

```bash
# macOS / Linux / WSL
curl -fsSL https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/main/install.sh | bash

# Windows PowerShell
irm https://raw.githubusercontent.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/main/install.ps1 | iex
```

The installer detects AI coding agents on your machine and installs the skill for each one.

### Per-agent install

| Agent | Command |
|-------|---------|
| **Claude Code** | `/plugin marketplace add EltonZhang777/Blasphemous.ModdingHelper.Skill` then `/plugin install blasphemous-modding-helper@EltonZhang777/Blasphemous.ModdingHelper.Skill` |
| **Gemini CLI** | `gemini extensions install https://github.com/EltonZhang777/Blasphemous.ModdingHelper.Skill` |
| **Codex CLI** | Clone repo → symlink `skills/blasphemous-modding-helper` to `~/.agents/skills/` |
| **Cursor / Windsurf / Cline** | `npx skills add EltonZhang777/Blasphemous.ModdingHelper.Skill -a <agent>` |

### Manual install

1. Download the skill from the [release page](https://github.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/releases).
2. Extract to your AI coding tool's skill folder (e.g., `.claude/skills/`, `~/.agents/skills/`).
3. Restart the tool if the skill doesn't show up.

### Activation

After installation, manually activate the skill:
- **Claude Code**: skill is registered automatically; just ask a modding question
- **Other agents**: use `/command` or mention the skill in context

---

## 📦 What's Included

- **Core Skill** — Top-level configuration with coding specifications, preferences management, and workflow guidelines
- **Source Code Navigation Guides** — 10 AI-friendly docs for navigating decompiled Blasphemous source code (core, player, enemies, bosses, UI, items, levels, tools, localization, and main index)
- **Sub-Skills**:
  - **Source Analyzer** — Read and analyze game source code to understand mechanics, structure, and dependencies
  - **Log Analyzer** — Debug and error tracking for mod development (BepInEx and Unity logs)
- **Configuration Reference** — First-time setup and preferences documentation

---

## 💡 Usage

Prompt the AI in natural language with clear objectives.

**Examples:**
- *"Find and explain the class that handles the map UI in Blasphemous source code"*
- *"Read the logs of modded Blasphemous to find errors, and find what in my mod causes the error"*
- *"Explain the AI of the boss Isidora, start by searching in the namespace `Gameplay.GameControllers.Bosses.Isidora`"*

---

## 📋 Requirements

- Any AI coding tool that supports skills (Claude Code, Gemini CLI, Codex CLI, Cursor, etc.)
- A decompiled C# solution of Blasphemous' source code
- A modded Blasphemous profile with BepInEx and ModdingAPI installed (use the [Mod Installer](https://github.com/BrandenEK/Blasphemous.Modding.Installer) for easy management)

---

## 🔧 Development

```bash
git clone https://github.com/EltonZhang777/Blasphemous.ModdingHelper.Skill.git
cd Blasphemous.ModdingHelper.Skill
```

The repository uses:
- **`.claude-plugin/plugin.json`** — Claude Code plugin manifest
- **`skills/blasphemous-modding-helper/SKILL.md`** — Core skill definition
- **`install.sh` / `install.ps1`** — Cross-platform unified installers
- **`gemini-extension.json`** — Gemini CLI extension descriptor
- **`skills-lock.json`** — Skill version tracking

### Distribution note

- **GitHub Release zip** contains only `skills/blasphemous-modding-helper/` — intended for manual installs.
- **`npx github:EltonZhang777/Blasphemous.ModdingHelper.Skill`** (used by the curl-pipe paths of `install.sh` / `install.ps1`) runs the full repository, which also includes `bin/install.js` and the platform installers.

---

## 📄 License

MIT — see [LICENSE](LICENSE).
