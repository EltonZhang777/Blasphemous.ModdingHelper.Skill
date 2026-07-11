#!/usr/bin/env node
/**
 * Blasphemous Modding Helper — Unified Installer (Node)
 *
 * One Node script replaces install.sh + install.ps1 as the source of truth.
 * Works on Windows (PowerShell), macOS, and Linux.
 *
 * Distribution:
 *   Local clone: node bin/install.js [flags]
 *   curl|bash:   delegated from install.sh → npx -y github:REPO -- [flags]
 *   Windows:     pwsh install.ps1 [flags] → same npx delegation
 *
 * Flags:
 *   --all           Install for ALL detected agents (no prompt)
 *   --only <id>     Install for a specific agent only (repeatable)
 *   --dry-run       Preview what would be installed
 *   --uninstall     Remove skill from all agents
 *   --help          Show usage
 *
 * Pure stdlib, zero npm runtime deps.
 */
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { execSync, spawnSync } = require("child_process");
const readline = require("readline");

const REPO = "EltonZhang777/Blasphemous.ModdingHelper.Skill";
const REPO_URL = `https://github.com/${REPO}`;
const SKILL_NAME = "blasphemous-modding-helper";
const SKILL_SOURCE_DIR = path.join(__dirname, "..", "skills", SKILL_NAME);

// ── Provider matrix ─────────────────────────────────────────────────────────
// Single source of truth for all supported AI coding agents.
// Referenced from superpowers-zh (https://github.com/jnMetaCode/superpowers-zh)
// and caveman (https://github.com/JuliusBrussee/caveman).
//
// detect rules:
//   "command:<bin>"       — binary on PATH (most reliable)
//   "dir:<path>"          — directory existence (for dir-only agents like Trae-CN)
//   "vscode-ext:<id>"     — VSCode extension directory match
//   "cursor-ext:<id>"     — Cursor extension directory match
//
// `soft: true` means the provider is excluded from auto-detect and only
// installs when the user passes `--only <id>`. This prevents false positives
// from stale config dirs.
//
// When a provider has a `profile` its install is delegated to `npx skills add`;
// otherwise the installer uses a native mechanism (e.g. claude plugin, trae dir copy).
const HOME = os.homedir();
const PROVIDERS = [
  // ── Native installers ──────────────────────────────────────────────────
  {
    id: "trae-cn",
    label: "Trae IDE (Trae-CN)",
    detect: `dir:${HOME}\\.trae-cn\\skills`,
  },
  {
    id: "claude-code",
    label: "Claude Code",
    detect: "command:claude",
    profile: "claude-code",
  },
  {
    id: "gemini-cli",
    label: "Gemini CLI",
    detect: "command:gemini",
    profile: "gemini-cli",
  },
  // ── CLI agents (npx skills add) ────────────────────────────────────────
  {
    id: "cursor",
    label: "Cursor",
    detect: "command:cursor",
    profile: "cursor",
  },
  {
    id: "windsurf",
    label: "Windsurf",
    detect: "command:windsurf",
    profile: "windsurf",
  },
  {
    id: "cline",
    label: "Cline",
    detect: "command:cline",
    profile: "cline",
  },
  {
    id: "opencode",
    label: "opencode",
    detect: "command:opencode",
    profile: "opencode",
  },
  {
    id: "continue",
    label: "Continue",
    detect: "command:continue",
    profile: "continue",
  },
  {
    id: "codex-cli",
    label: "Codex CLI",
    detect: "command:codex",
    profile: "codex-cli",
  },
  {
    id: "kiro",
    label: "Kiro CLI",
    detect: "command:kiro",
    profile: "kiro-cli",
  },
  {
    id: "hermes",
    label: "Hermes Agent",
    detect: "command:hermes",
    profile: "hermes",
  },
  {
    id: "aider-desk",
    label: "Aider Desk",
    detect: "command:aider",
    profile: "aider-desk",
  },
  {
    id: "qwen-code",
    label: "Qwen Code",
    detect: "command:qwen",
    profile: "qwen-code",
  },
  {
    id: "openclaw",
    label: "OpenClaw",
    detect: `command:openclaw||dir:${HOME}\\.openclaw`,
    profile: "openclaw",
  },
  {
    id: "warp",
    label: "Warp",
    detect: "command:warp",
    profile: "warp",
  },
  {
    id: "replit",
    label: "Replit Agent",
    detect: "command:replit",
    profile: "replit",
  },
  {
    id: "claw-code",
    label: "Claw Code",
    detect: "command:claw||vscode-ext:claw",
    profile: "claw-code",
  },
  // ── VSCode / Cursor extension-based agents ─────────────────────────────
  {
    id: "roo",
    label: "Roo Code",
    detect: "vscode-ext:roo||vscode-ext:rooveterinaryinc.roo-cline||cursor-ext:roo",
    profile: "roo",
  },
  {
    id: "kilo",
    label: "Kilo Code",
    detect: "vscode-ext:kilocode",
    profile: "kilo",
  },
  {
    id: "augment",
    label: "Augment Code",
    detect: "vscode-ext:augment",
    profile: "augment",
  },
  {
    id: "copilot",
    label: "GitHub Copilot",
    detect: "vscode-ext:github.copilot||vscode-ext:github.copilot-chat",
    profile: "github-copilot",
  },
  // ── Soft agents (opt-in via --only only) ───────────────────────────────
  {
    id: "qoder",
    label: "Qoder",
    detect: `dir:${HOME}\\.qoder`,
    profile: "qoder",
    soft: true,
  },
  {
    id: "antigravity",
    label: "Google Antigravity",
    detect: `dir:${HOME}\\.gemini\\antigravity`,
    profile: "antigravity",
    soft: true,
  },
];

// ── Detection helpers ───────────────────────────────────────────────────────

function hasCommand(cmd) {
  try {
    if (process.platform === "win32") {
      return spawnSync("where", [cmd], { stdio: "ignore" }).status === 0;
    }
    return spawnSync("sh", ["-c", `command -v ${cmd}`], { stdio: "ignore" }).status === 0;
  } catch {
    return false;
  }
}

function hasDir(dirPath) {
  try {
    return fs.existsSync(dirPath) && fs.statSync(dirPath).isDirectory();
  } catch {
    return false;
  }
}

/**
 * Check if a VSCode extension with the given ID prefix is installed.
 * VSCode extensions are stored in:
 *   Windows: %USERPROFILE%\.vscode\extensions\<publisher>.<name>-<version>
 *   macOS:   ~/.vscode/extensions/<publisher>.<name>-<version>
 *   Linux:   ~/.vscode/extensions/<publisher>.<name>-<version>
 */
function hasVscodeExt(extId) {
  const dirs = [
    path.join(os.homedir(), ".vscode", "extensions"),
    path.join(os.homedir(), ".vscode-insiders", "extensions"),
    // VSCodium
    path.join(os.homedir(), ".vscode-oss", "extensions"),
  ];
  // Also check the program files path on Windows
  if (process.platform === "win32") {
    dirs.push(
      path.join(process.env.LOCALAPPDATA || "", "Programs", "Microsoft VS Code", "resources", "app", "extensions")
    );
  }
  for (const dir of dirs) {
    if (!hasDir(dir)) continue;
    try {
      const entries = fs.readdirSync(dir);
      if (entries.some((e) => e.startsWith(extId))) return true;
    } catch {
      // skip dirs we can't read
    }
  }
  return false;
}

/**
 * Check if a Cursor extension with the given ID prefix is installed.
 * Cursor extensions are stored in:
 *   Windows: %USERPROFILE%\.cursor\extensions\<publisher>.<name>-<version>
 */
function hasCursorExt(extId) {
  const dirs = [
    path.join(os.homedir(), ".cursor", "extensions"),
  ];
  for (const dir of dirs) {
    if (!hasDir(dir)) continue;
    try {
      const entries = fs.readdirSync(dir);
      if (entries.some((e) => e.startsWith(extId))) return true;
    } catch {
      // skip dirs we can't read
    }
  }
  return false;
}

function detectAgent(provider) {
  // Soft agents are never auto-detected
  if (provider.soft) return false;

  const rules = provider.detect.split("||");
  for (const rule of rules) {
    const [type, ...rest] = rule.split(":");
    const value = rest.join(":");
    switch (type) {
      case "command":
        if (hasCommand(value)) return true;
        break;
      case "dir":
        if (hasDir(value)) return true;
        break;
      case "vscode-ext":
        if (hasVscodeExt(value)) return true;
        break;
      case "cursor-ext":
        if (hasCursorExt(value)) return true;
        break;
    }
  }
  return false;
}

function detectAgents(onlyIds) {
  if (onlyIds && onlyIds.length > 0) {
    return PROVIDERS.filter((p) => onlyIds.includes(p.id));
  }
  return PROVIDERS.filter((p) => detectAgent(p));
}

// ── Installation handlers ───────────────────────────────────────────────────

function installClaudeCode(action) {
  if (action === "install") {
    info("Installing for Claude Code via plugin marketplace...");
    run(`claude plugin marketplace add ${REPO}`, "Claude Code marketplace add");
    run(`claude plugin install "${SKILL_NAME}@${REPO}"`, "Claude Code plugin install");
  } else {
    info("Uninstalling from Claude Code...");
    run(`claude plugin uninstall ${SKILL_NAME}`, "Claude Code uninstall");
  }
}

function installGeminiCli(action) {
  if (action === "install") {
    info("Installing for Gemini CLI...");
    run(`gemini extensions install ${REPO_URL}`, "Gemini CLI install");
  } else {
    info("Uninstalling from Gemini CLI...");
    run(`gemini extensions uninstall ${REPO_URL}`, "Gemini CLI uninstall");
  }
}

function installTraeCn(action) {
  const home = os.homedir();
  const targetDir = path.join(home, ".trae-cn", "skills", SKILL_NAME);

  if (action === "install") {
    info(`Installing for Trae IDE (Trae-CN)...`);
    info(`Target: ${targetDir}`);

    if (DRY_RUN) {
      console.log(`  copy "${SKILL_SOURCE_DIR}" → "${targetDir}"`);
      return;
    }

    // Create parent dir if needed
    try {
      fs.mkdirSync(path.dirname(targetDir), { recursive: true });
    } catch (e) {
      warn(`Failed to create target directory: ${e.message}`);
      return;
    }

    // Remove existing if present
    try {
      if (fs.existsSync(targetDir)) {
        fs.rmSync(targetDir, { recursive: true, force: true });
      }
    } catch (e) {
      warn(`Failed to remove existing installation: ${e.message}`);
      return;
    }

    // Copy skill directory recursively
    try {
      copyDirSync(SKILL_SOURCE_DIR, targetDir);
      ok("Installed for Trae IDE (Trae-CN)");
    } catch (e) {
      warn(`Failed to copy skill directory: ${e.message}`);
      warn("Try running as Administrator or copy manually.");
    }
  } else {
    info("Uninstalling from Trae IDE (Trae-CN)...");
    if (!DRY_RUN && fs.existsSync(targetDir)) {
      try {
        fs.rmSync(targetDir, { recursive: true, force: true });
        ok("Uninstalled from Trae IDE (Trae-CN)");
      } catch (e) {
        warn(`Failed to uninstall: ${e.message}`);
      }
    }
  }
}

function runViaNpx(agent, action) {
  const cmd = action === "install" ? "add" : "remove";
  const noun = action === "install" ? "Installing" : "Uninstalling";
  info(`${noun} for ${agent.label} via npx skills...`);
  run(`npx skills ${cmd} ${REPO} -a ${agent.profile}`, `${noun} for ${agent.label}`);
}

// ── Utility functions ───────────────────────────────────────────────────────

function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

const CYAN = "\x1b[36m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const RED = "\x1b[31m";
const NC = "\x1b[0m";

function info(msg) {
  console.log(`${CYAN}[*]${NC} ${msg}`);
}
function ok(msg) {
  console.log(`${GREEN}[✓]${NC} ${msg}`);
}
function warn(msg) {
  console.log(`${YELLOW}[!]${NC} ${msg}`);
}
function err(msg) {
  console.log(`${RED}[✗]${NC} ${msg}`);
}

function run(cmd, desc) {
  if (DRY_RUN) {
    console.log(`  ${cmd}`);
    return;
  }
  try {
    execSync(cmd, { stdio: "ignore" });
  } catch {
    warn(`${desc} failed. Try manually.`);
  }
}

// ── Interactive selection ───────────────────────────────────────────────────

async function promptSelectAgent(detected) {
  const sorted = [...detected];
  const allIds = new Set(PROVIDERS.map((p) => p.id));

  // Show the available options
  function showMenu() {
    console.log("");
    console.log("  Detected AI coding agents on this machine:");
    console.log("");
    sorted.forEach((p, i) => {
      console.log(`    [${i + 1}] ${p.label}`);
    });
    console.log("");
    console.log("  Commands:");
    console.log("    all               Install for ALL detected agents");
    console.log("    exit / cancel     Cancel and exit");
    console.log("    <id> / <number>   Select specific agent(s)");
    console.log('                      (comma-sep: "1,3" or "cursor,claude")');
    console.log("");
  }

  return new Promise((resolve) => {
    showMenu();

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    rl.question("  Your choice (default: all): ", (answer) => {
      rl.close();

      const trimmed = answer.trim().toLowerCase();

      // Empty → all
      if (!trimmed) {
        console.log("");
        info("Installing for ALL detected agents.");
        resolve(sorted);
        return;
      }

      // Exit commands
      if (["exit", "quit", "cancel", "q", "0"].includes(trimmed)) {
        resolve([]);
        return;
      }

      // "all" → all
      if (trimmed === "all") {
        console.log("");
        info("Installing for ALL detected agents.");
        resolve(sorted);
        return;
      }

      // Comma/semi-colon/space separated list
      const tokens = trimmed
        .split(/[,; ]+/)
        .map((t) => t.trim())
        .filter(Boolean);

      const selected = [];
      const unknown = [];

      for (const token of tokens) {
        // Try number match first
        const num = parseInt(token, 10);
        if (!isNaN(num) && num >= 1 && num <= sorted.length) {
          selected.push(sorted[num - 1]);
          continue;
        }
        // Try ID match (case-insensitive)
        const match = sorted.find(
          (p) => p.id.toLowerCase() === token
        );
        if (match) {
          selected.push(match);
          continue;
        }
        // Check if it's a valid provider ID but not detected
        if (allIds.has(token)) {
          unknown.push(`${token} (not detected on this machine)`);
        } else {
          unknown.push(token);
        }
      }

      if (selected.length > 0) {
        const unique = [];
        const seen = new Set();
        for (const p of selected) {
          if (!seen.has(p.id)) {
            seen.add(p.id);
            unique.push(p);
          }
        }
        if (unknown.length > 0) {
          warn(`Unknown / unavailable: ${unknown.join(", ")}`);
        }
        console.log("");
        info(`Selected agents: ${unique.map((p) => p.label).join(", ")}`);
        resolve(unique);
      } else {
        // Nothing valid selected — re-prompt
        err(`No valid agent selected: "${trimmed}"`);
        info("Use agent IDs or numbers from the list above.");
        info('Type "all" for all detected agents, or "exit" to cancel.');
        console.log("");
        rl.close();
        // Recurse into a new prompt
        promptSelectAgent(detected).then(resolve);
      }
    });
  });
}

// ── Main ────────────────────────────────────────────────────────────────────

let DRY_RUN = false;
let UNINSTALL = false;
let ALL = false;
let ONLY_AGENTS = [];

function parseArgs() {
  const argv = process.argv.slice(2);

  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case "--dry-run":
        DRY_RUN = true;
        break;
      case "--uninstall":
        UNINSTALL = true;
        break;
      case "--all":
        ALL = true;
        break;
      case "--only":
        const v = argv[++i];
        if (!v) {
          err("--only requires an argument");
          process.exit(2);
        }
        ONLY_AGENTS.push(...v.split(",").map((s) => s.trim()));
        break;
      case "--help":
      case "-h":
        showHelp();
        process.exit(0);
      default:
        err(`Unknown flag: ${argv[i]}`);
        showHelp();
        process.exit(2);
    }
  }
}

function showHelp() {
  console.log(`
  Blasphemous Modding Helper — Installer

  Usage:
    node bin/install.js [flags]

  Flags:
    --all             Install for all detected agents (no prompt)
    --only <id>       Install for a specific agent (repeatable / comma-sep)
    --dry-run         Preview only, no files written
    --uninstall       Remove the skill
    --help, -h        Show this help

  Supported agents:
${PROVIDERS.map((p) => `    ${p.id.padEnd(15)} ${p.label}`).join("\n")}
`);
}

async function main() {
  // ── ASCII banner ──────────────────────────────────────────────────────────
  console.log("");
  console.log("  ╔══════════════════════════════════════════╗");
  console.log("  ║   Blasphemous Modding Helper Installer   ║");
  console.log("  ╚══════════════════════════════════════════╝");
  console.log(`  ${REPO_URL}`);
  console.log("");

  parseArgs();

  if (DRY_RUN) {
    info("DRY RUN mode — no files will be written.");
    console.log("");
  }

  if (UNINSTALL) {
    info("UNINSTALL mode.");
    console.log("");
  }

  const action = UNINSTALL ? "uninstall" : "install";

  // Resolve target agents
  let targets;
  if (ONLY_AGENTS.length > 0) {
    // --only was specified: validate and use those
    targets = PROVIDERS.filter((p) => ONLY_AGENTS.includes(p.id));
    if (targets.length === 0) {
      err(`Unknown agent(s): ${ONLY_AGENTS.join(", ")}`);
      info(`Use --help to see supported agents.`);
      process.exit(1);
    }
    info(`Using explicitly specified agents: ${targets.map((p) => p.label).join(", ")}`);
  } else {
    // Auto-detect
    const detected = detectAgents();
    if (detected.length === 0) {
      err("No supported AI coding agents detected on this machine.");
      console.log("");
      info("Supported agents:");
      for (const p of PROVIDERS) {
        console.log(`  - ${p.label}`);
      }
      console.log("");
      info(`To install for a specific agent, use:`);
      console.log(`  node bin/install.js --only <agent-id>`);
      console.log(`  (e.g., node bin/install.js --only trae-cn)`);
      console.log("");
      info(`Or install manually: ${REPO_URL}#readme`);
      process.exit(1);
    }

    if (ALL || !process.stdin.isTTY) {
      // --all or non-interactive: install for all detected
      targets = detected;
      info(`Detected agents: ${detected.map((p) => p.label).join(", ")}`);
    } else {
      // Interactive: show selection menu (even for 1 agent so user can exit)
      targets = await promptSelectAgent(detected);
      if (targets.length === 0) {
        info("Installation cancelled.");
        console.log("");
        process.exit(0);
      }
    }
  }

  console.log("");

  // Execute install/uninstall for each target
  for (const agent of targets) {
    switch (agent.id) {
      case "claude-code":
        installClaudeCode(action);
        break;
      case "gemini-cli":
        installGeminiCli(action);
        break;
      case "trae-cn":
        installTraeCn(action);
        break;
      default:
        runViaNpx(agent, action);
        break;
    }
    console.log("");
  }

  // ── Next steps ────────────────────────────────────────────────────────────
  if (action === "install" && !DRY_RUN && targets.length > 0) {
    ok("Install complete!");
    console.log("");
    console.log("  Next steps:");
    console.log("  ──────────────────────────────────────");
    console.log("  1. Open your AI coding tool");
    console.log("  2. Start a session and ask a modding question");
    console.log('     e.g. "Find and explain the class that handles the map UI"');
    console.log("");
    console.log("  Manual activation: some agents need a /command or context trigger.");
    console.log(`  See ${REPO_URL}#readme for details.`);
    console.log("");
  }

  if (action === "uninstall" && !DRY_RUN) {
    ok("Uninstall complete!");
    console.log("");
  }
}

main().catch((e) => {
  err(`Unexpected error: ${e.message}`);
  process.exit(1);
});
