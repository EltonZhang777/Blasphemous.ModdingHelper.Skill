# Blasphemous Modding Helper for AI Agents

[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Agent Skill](https://img.shields.io/badge/Agent-Skill-blueviolet)](#-install)

An AI agent skill that provides expert assistance with **Blasphemous mod development**. Helps you work with decompiled C# source code, analyze game mechanics, inspect save evidence read-only, debug logs, and create custom mods using the [ModdingAPI](https://github.com/BrandenEK/Blasphemous.ModdingAPI) framework.

---

## 🚀 Install

Choose one of the two supported installation routes.

### Clone and install

Clone the repository, then run the platform wrapper with the exact final Skill directory:

```bash
git clone https://github.com/EltonZhang777/Blasphemous.ModdingHelper.Skill.git
cd Blasphemous.ModdingHelper.Skill
bash install.sh --path "<AGENT_SKILLS_DIR>/blasphemous-modding-helper"
```

```powershell
git clone https://github.com/EltonZhang777/Blasphemous.ModdingHelper.Skill.git
Set-Location Blasphemous.ModdingHelper.Skill
.\install.ps1 --path "<AGENT_SKILLS_DIR>\blasphemous-modding-helper"
```

`--path` is the exact final Skill directory; the installer does not append another directory name. Add `--dry-run` to preview the operation, or `--uninstall` to remove Skill-owned files from that directory. The destination must be outside this repository and must not pass through a symbolic link or junction. Installation preserves unrelated entries.

The clone-local wrappers require Node.js 18 or newer; they do not download an installer.

### Install from the release archive

1. Download the archive from [GitHub Releases](https://github.com/EltonZhang777/Blasphemous.ModdingHelper.Skill/releases).
2. Copy the bundled `skills/blasphemous-modding-helper/` directory to `<AGENT_SKILLS_DIR>/blasphemous-modding-helper/`.
3. Keep `SKILL.md` at the installed directory root, with its `references/` and `scripts/` directories beside it; do not add another `skills/` level.
4. Restart or reload the Agent Skills host if the skill does not appear.

### Activation

After either installation route, prompt naturally. The top-level skill selects the applicable workflow.

---

## 📦 What's Included

- **Core Skill** — Top-level configuration with coding specifications, configuration management, and workflow guidelines
- **Source Code Navigation Guides** — 10 AI-friendly docs for navigating decompiled Blasphemous source code (core, player, enemies, bosses, UI, items, levels, tools, localization, and main index)
- **Automatically routed workflows**:
  - **Source Analyzer** — Read and analyze game source code to understand mechanics, structure, and dependencies
  - **Log Analyzer** — Debug and error tracking for mod development (BepInEx and Unity logs)
  - **Mod Test** — Build, deploy, launch, inspect startup evidence, stop, clean, and verify in-game behavior with Player or Computer Use
  - **Save Analysis** — Read-only decode and inspect an explicit Blasphemous 1 save file or directory under the host temporary directory
  - **Localization Lookup** — Read-only lookup and translation support for Blasphemous 1 terms and UI text
  - **Unity Project Navigation** — Read-only topology and scene-set summary for an exported Unity project
- **Configuration Reference** — First-time setup and configuration documentation

Only the top-level `blasphemous-modding-helper` skill is activated. The Agent automatically selects the applicable workflow reference; users do not need to invoke these references directly.

---

## 💡 Usage

Prompt the AI in natural language with clear objectives.

**Examples:**
- *"Find and explain the class that handles the map UI in Blasphemous source code"*
- *"Read the logs of modded Blasphemous to find errors, and find what in my mod causes the error"*
- *"Explain the AI of the boss Isidora, start by searching in the namespace `Gameplay.GameControllers.Bosses.Isidora`"*

---

## 📋 Requirements

- An Agent Skills-compatible host
- Python 3.9 or newer for cross-platform Skill scripts
- Node.js 18 or newer for the clone-local installer
- PowerShell 5.1 or newer for the clone-local Windows installer
- See [Dependencies](skills/blasphemous-modding-helper/references/config/invocation-preflight.md#dependencies) for the post-install package and conditional workflow dependencies
- Use the [Mod Installer](https://github.com/BrandenEK/Blasphemous.Modding.Installer) to manage game profiles when needed

---

## 🔧 Development

```bash
git clone https://github.com/EltonZhang777/Blasphemous.ModdingHelper.Skill.git
cd Blasphemous.ModdingHelper.Skill
```

The repository uses:
- **`skills/blasphemous-modding-helper/SKILL.md`** — Core skill definition
- **`bin/install.js`** — Explicit-path installer
- **`install.sh` / `install.ps1`** — Clone-local platform wrappers
- **`skills-lock.json`** — Skill version tracking

### Distribution note

The GitHub Release archive contains only `skills/blasphemous-modding-helper/` for manual installation.

---

## 📄 License

MIT — see [LICENSE](LICENSE).
