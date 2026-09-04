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
 *   --path <dir>    Install directly into an exact skill directory
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
const { execSync } = require("child_process");
const readline = require("readline");

const REPO = "EltonZhang777/Blasphemous.ModdingHelper.Skill";
const REPO_URL = `https://github.com/${REPO}`;
const SKILL_NAME = "blasphemous-modding-helper";
const CLAUDE_MARKETPLACE = "blasphemous-modding-helper-marketplace";
const REPOSITORY_ROOT = path.resolve(__dirname, "..");
const SKILL_SOURCE_DIR = path.join(REPOSITORY_ROOT, "skills", SKILL_NAME);

// ── Provider matrix ─────────────────────────────────────────────────────────
// Single source of truth for all supported AI coding agents.
// Referenced from superpowers-zh (https://github.com/jnMetaCode/superpowers-zh)
// and caveman (https://github.com/JuliusBrussee/caveman).
//
// detect rules are structured objects:
//   { type: "command", value: "<bin>" } — binary on PATH
//   { type: "dir", value: "<path>" }     — config/application directory
//   { type: "file", value: "<path>" }    — config file
//   { type: "vscode-ext", value: "<id>" } — VSCode extension directory
//   { type: "cursor-ext", value: "<id>" } — Cursor extension directory
//
// When a provider has a `profile` its install is delegated to `npx skills add`;
// otherwise the installer uses a native mechanism (e.g. claude plugin, trae dir copy).
const HOME = os.homedir();
const CONFIG_HOME = process.env.XDG_CONFIG_HOME?.trim() || (
  process.platform === "win32"
    ? process.env.APPDATA?.trim() || path.join(HOME, "AppData", "Roaming")
    : path.join(HOME, ".config")
);
const CLAUDE_HOME = process.env.CLAUDE_CONFIG_DIR?.trim() || path.join(HOME, ".claude");
const CODEX_HOME = process.env.CODEX_HOME?.trim() || path.join(HOME, ".codex");
const HERMES_HOME = process.env.HERMES_HOME?.trim() || path.join(HOME, ".hermes");

function commandRule(value) {
  return { type: "command", value };
}

function directoryRule(value) {
  return { type: "dir", value };
}

function fileRule(value) {
  return { type: "file", value };
}

function vscodeExtensionRule(value) {
  return { type: "vscode-ext", value };
}

function cursorExtensionRule(value) {
  return { type: "cursor-ext", value };
}

const PROVIDERS = [
  // ── Native installers ──────────────────────────────────────────────────
  {
    id: "trae-cn",
    label: "Trae IDE (Trae-CN)",
    detect: [directoryRule(path.join(HOME, ".trae-cn", "skills"))],
  },
  {
    id: "claude-code",
    label: "Claude Code",
    detect: [commandRule("claude"), directoryRule(CLAUDE_HOME)],
    profile: "claude-code",
  },
  {
    id: "gemini-cli",
    label: "Gemini CLI",
    detect: [commandRule("gemini"), directoryRule(path.join(HOME, ".gemini"))],
    profile: "gemini-cli",
  },
  // ── CLI agents (npx skills add) ────────────────────────────────────────
  {
    id: "cursor",
    label: "Cursor",
    detect: [commandRule("cursor"), directoryRule(path.join(HOME, ".cursor"))],
    profile: "cursor",
  },
  {
    id: "windsurf",
    label: "Windsurf",
    detect: [commandRule("windsurf"), directoryRule(path.join(HOME, ".codeium", "windsurf"))],
    profile: "windsurf",
  },
  {
    id: "cline",
    label: "Cline",
    detect: [
      commandRule("cline"),
      directoryRule(path.join(HOME, ".cline")),
      vscodeExtensionRule("saoudrizwan.claude-dev"),
    ],
    profile: "cline",
  },
  {
    id: "opencode",
    label: "opencode",
    detect: [commandRule("opencode"), directoryRule(path.join(CONFIG_HOME, "opencode"))],
    profile: "opencode",
  },
  {
    id: "continue",
    label: "Continue",
    detect: [commandRule("continue"), directoryRule(path.join(HOME, ".continue"))],
    profile: "continue",
  },
  {
    id: "codex",
    label: "Codex CLI",
    detect: [commandRule("codex"), directoryRule(CODEX_HOME)],
    profile: "codex",
    aliases: ["codex-cli"],
  },
  {
    id: "kiro",
    label: "Kiro CLI",
    detect: [commandRule("kiro"), directoryRule(path.join(HOME, ".kiro"))],
    profile: "kiro-cli",
  },
  {
    id: "hermes-agent",
    label: "Hermes Agent",
    detect: [commandRule("hermes"), directoryRule(HERMES_HOME)],
    profile: "hermes-agent",
    aliases: ["hermes"],
  },
  {
    id: "aider-desk",
    label: "Aider Desk",
    detect: [commandRule("aider"), directoryRule(path.join(HOME, ".aider-desk"))],
    profile: "aider-desk",
  },
  {
    id: "qwen-code",
    label: "Qwen Code",
    detect: [commandRule("qwen"), directoryRule(path.join(HOME, ".qwen"))],
    profile: "qwen-code",
  },
  {
    id: "openclaw",
    label: "OpenClaw",
    detect: [
      commandRule("openclaw"),
      directoryRule(path.join(HOME, ".openclaw")),
      directoryRule(path.join(HOME, ".clawdbot")),
      directoryRule(path.join(HOME, ".moltbot")),
    ],
    profile: "openclaw",
  },
  {
    id: "warp",
    label: "Warp",
    detect: [commandRule("warp"), directoryRule(path.join(HOME, ".warp"))],
    profile: "warp",
  },
  {
    id: "replit",
    label: "Replit Agent",
    detect: [commandRule("replit"), fileRule(path.join(process.cwd(), ".replit"))],
    profile: "replit",
  },
  {
    id: "claw-code",
    label: "Claw Code",
    detect: [commandRule("claw"), vscodeExtensionRule("claw")],
    profile: "claw-code",
  },
  // ── VSCode / Cursor extension-based agents ─────────────────────────────
  {
    id: "roo",
    label: "Roo Code",
    detect: [
      directoryRule(path.join(HOME, ".roo")),
      vscodeExtensionRule("rooveterinaryinc.roo-cline"),
      cursorExtensionRule("roo"),
    ],
    profile: "roo",
  },
  {
    id: "kilo",
    label: "Kilo Code",
    detect: [directoryRule(path.join(HOME, ".kilocode")), vscodeExtensionRule("kilocode")],
    profile: "kilo",
  },
  {
    id: "augment",
    label: "Augment Code",
    detect: [directoryRule(path.join(HOME, ".augment")), vscodeExtensionRule("augment")],
    profile: "augment",
  },
  {
    id: "copilot",
    label: "GitHub Copilot",
    detect: [
      directoryRule(path.join(HOME, ".copilot")),
      vscodeExtensionRule("github.copilot"),
      vscodeExtensionRule("github.copilot-chat"),
    ],
    profile: "github-copilot",
  },
  // ── Config-directory agents ────────────────────────────────────────────
  {
    id: "qoder",
    label: "Qoder",
    detect: [directoryRule(path.join(HOME, ".qoder"))],
    profile: "qoder",
  },
  {
    id: "antigravity",
    label: "Google Antigravity",
    detect: [directoryRule(path.join(HOME, ".gemini", "antigravity"))],
    profile: "antigravity",
  },
];

// ── Detection helpers ───────────────────────────────────────────────────────

function hasCommand(cmd) {
  const pathValue = process.env.PATH || process.env.Path || "";
  const extensions = process.platform === "win32" && path.extname(cmd) === ""
    ? (process.env.PATHEXT || ".COM;.EXE;.BAT;.CMD").split(";")
    : [""];
  const commandName = path.isAbsolute(cmd) ? null : cmd;
  const directories = pathValue.split(path.delimiter).filter(Boolean);

  for (const directory of directories) {
    for (const extension of extensions) {
      const candidate = commandName === null
        ? cmd
        : path.join(directory, `${cmd}${extension}`);
      try {
        if (!fs.statSync(candidate).isFile()) continue;
        if (process.platform !== "win32") fs.accessSync(candidate, fs.constants.X_OK);
        return true;
      } catch {
        // Continue through PATH entries and PATHEXT variants.
      }
    }
  }
  return false;
}

function hasDir(dirPath) {
  try {
    return fs.existsSync(dirPath) && fs.statSync(dirPath).isDirectory();
  } catch {
    return false;
  }
}

function hasFile(filePath) {
  try {
    return fs.existsSync(filePath) && fs.statSync(filePath).isFile();
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

  for (const rule of provider.detect) {
    switch (rule.type) {
      case "command":
        if (hasCommand(rule.value)) return true;
        break;
      case "dir":
        if (hasDir(rule.value)) return true;
        break;
      case "file":
        if (hasFile(rule.value)) return true;
        break;
      case "vscode-ext":
        if (hasVscodeExt(rule.value)) return true;
        break;
      case "cursor-ext":
        if (hasCursorExt(rule.value)) return true;
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

function findProvider(id) {
  const normalized = id.toLowerCase();
  return PROVIDERS.find((p) => p.id === normalized || (p.aliases || []).includes(normalized));
}

// ── Installation handlers ───────────────────────────────────────────────────

function installClaudeCode(action) {
  let success = true;
  info("Scope: user-level (plugin marketplace)");
  if (action === "install") {
    info("Installing for Claude Code via plugin marketplace...");
    success = run(`claude plugin marketplace add ${REPO} --scope user`, "Claude Code marketplace add") && success;
    success = run(`claude plugin install "${SKILL_NAME}@${CLAUDE_MARKETPLACE}" --scope user`, "Claude Code plugin install") && success;
  } else {
    info("Uninstalling from Claude Code...");
    success = run(`claude plugin uninstall ${SKILL_NAME} --scope user --yes`, "Claude Code uninstall") && success;
  }
  return success;
}

function installGeminiCli(action) {
  info("Scope: user-level (Gemini extension)");
  if (action === "install") {
    info("Installing for Gemini CLI...");
    return run(`gemini extensions install ${REPO_URL} --consent --skip-settings`, "Gemini CLI install");
  } else {
    info("Uninstalling from Gemini CLI...");
    return run(`gemini extensions uninstall ${SKILL_NAME}`, "Gemini CLI uninstall");
  }
}

function installTraeCn(action) {
  const home = os.homedir();
  const targetDir = path.join(home, ".trae-cn", "skills", SKILL_NAME);

  if (action === "install") {
    info(`Installing for Trae IDE (Trae-CN)...`);
    info(`Target: ${targetDir}`);
    info("Scope: user-level");

    if (DRY_RUN) {
      console.log(`  copy "${SKILL_SOURCE_DIR}" → "${targetDir}"`);
      return true;
    }

    // Create parent dir if needed
    try {
      fs.mkdirSync(path.dirname(targetDir), { recursive: true });
    } catch (e) {
      warn(`Failed to create target directory: ${e.message}`);
      return false;
    }

    // Remove existing if present
    try {
      if (fs.existsSync(targetDir)) {
        fs.rmSync(targetDir, { recursive: true, force: true });
      }
    } catch (e) {
      warn(`Failed to remove existing installation: ${e.message}`);
      return false;
    }

    // Copy skill directory recursively
    try {
      copyDirSync(SKILL_SOURCE_DIR, targetDir);
      ok("Installed for Trae IDE (Trae-CN)");
      return true;
    } catch (e) {
      warn(`Failed to copy skill directory: ${e.message}`);
      warn("Try running as Administrator or copy manually.");
      return false;
    }
  } else {
    info("Uninstalling from Trae IDE (Trae-CN)...");
    info(`Target: ${targetDir}`);
    info("Scope: user-level");
    if (DRY_RUN) {
      console.log(`  remove "${targetDir}"`);
      return true;
    }
    if (!fs.existsSync(targetDir)) {
      return true;
    }
    try {
      fs.rmSync(targetDir, { recursive: true, force: true });
      ok("Uninstalled from Trae IDE (Trae-CN)");
      return true;
    } catch (e) {
      warn(`Failed to uninstall: ${e.message}`);
      return false;
    }
  }
}

function runViaNpx(agent, action) {
  const cmd = action === "install"
    ? `npx -y skills add ${REPO} -a ${agent.profile} -g -y`
    : `npx -y skills remove ${SKILL_NAME} -a ${agent.profile} -g -y`;
  const noun = action === "install" ? "Installing" : "Uninstalling";
  info(`${noun} for ${agent.label} via npx skills...`);
  info("Scope: user-level");
  return run(cmd, `${noun} for ${agent.label}`);
}

function isSameOrWithin(parent, candidate) {
  const relative = path.relative(parent, candidate);
  const parentTraversal = relative === ".." || relative.startsWith(`..${path.sep}`);
  return relative === "" || (!parentTraversal && !path.isAbsolute(relative));
}

function pathsEqual(left, right) {
  return path.relative(left, right) === "" && path.relative(right, left) === "";
}

function normalizeCustomPath(rawPath) {
  return process.platform === "win32" ? rawPath : rawPath.replace(/\\/g, path.sep);
}

function resolveRealPathForSafety(targetDir) {
  let existingPath = targetDir;
  const missingSegments = [];

  while (!fs.existsSync(existingPath)) {
    const parentPath = path.dirname(existingPath);
    if (parentPath === existingPath) break;
    missingSegments.unshift(path.basename(existingPath));
    existingPath = parentPath;
  }

  return path.resolve(fs.realpathSync(existingPath), ...missingSegments);
}

function findSymbolicLinkAncestor(targetDir) {
  const root = path.parse(targetDir).root;
  const segments = path.relative(root, targetDir).split(path.sep).filter(Boolean);
  let currentPath = root;

  for (const segment of segments) {
    currentPath = path.join(currentPath, segment);
    try {
      if (fs.lstatSync(currentPath).isSymbolicLink()) return currentPath;
    } catch (e) {
      if (e.code === "ENOENT" || e.code === "ENOTDIR") break;
      throw e;
    }
  }

  return null;
}

function resolveCustomPath(rawPath) {
  const targetDir = path.resolve(process.cwd(), normalizeCustomPath(rawPath));
  const symbolicLinkAncestor = findSymbolicLinkAncestor(targetDir);
  if (symbolicLinkAncestor !== null) {
    err(`Custom path rejected: ${symbolicLinkAncestor} is a symbolic link or junction`);
    info("Choose a real dedicated directory to avoid redirecting installation.");
    return null;
  }

  const safetyTarget = resolveRealPathForSafety(targetDir);
  const sourceDir = fs.realpathSync(SKILL_SOURCE_DIR);
  const repositoryRoot = fs.realpathSync(REPOSITORY_ROOT);
  const filesystemRoot = path.parse(safetyTarget).root;

  if (
    isSameOrWithin(sourceDir, safetyTarget) ||
    isSameOrWithin(safetyTarget, sourceDir) ||
    isSameOrWithin(repositoryRoot, safetyTarget) ||
    pathsEqual(safetyTarget, repositoryRoot) ||
    pathsEqual(safetyTarget, filesystemRoot)
  ) {
    err(`Custom path rejected: ${targetDir}`);
    info("Choose a dedicated directory outside the Skill source and repository root.");
    return null;
  }

  if (fs.existsSync(targetDir) && fs.lstatSync(targetDir).isSymbolicLink()) {
    err(`Custom path rejected: ${targetDir} is a symbolic link`);
    info("Choose a real dedicated directory to avoid replacing an unrelated target.");
    return null;
  }

  return targetDir;
}

function isSkillDirectory(directory) {
  const manifest = path.join(directory, "SKILL.md");
  try {
    if (!fs.lstatSync(manifest).isFile()) return false;
    const content = fs.readFileSync(manifest, "utf8");
    return new RegExp(`^name:\\s*${SKILL_NAME}\\s*$`, "m").test(content);
  } catch {
    return false;
  }
}

function removeSkillContents(sourceDir, targetDir) {
  for (const entry of fs.readdirSync(sourceDir, { withFileTypes: true })) {
    const targetPath = path.join(targetDir, entry.name);
    let targetStat;
    try {
      targetStat = fs.lstatSync(targetPath);
    } catch {
      continue;
    }

    if (entry.isDirectory() && targetStat.isDirectory() && !targetStat.isSymbolicLink()) {
      removeSkillContents(path.join(sourceDir, entry.name), targetPath);
      if (fs.readdirSync(targetPath).length === 0) {
        fs.rmdirSync(targetPath);
      }
      continue;
    }

    if (!entry.isDirectory() || targetStat.isSymbolicLink()) {
      fs.rmSync(targetPath, { force: true });
    }
  }
}

function validateCopyDestination(sourceDir, targetDir) {
  if (fs.existsSync(targetDir)) {
    const targetStat = fs.lstatSync(targetDir);
    if (targetStat.isSymbolicLink() || !targetStat.isDirectory()) {
      throw new Error("destination must be a real directory");
    }
  }

  for (const entry of fs.readdirSync(sourceDir, { withFileTypes: true })) {
    const targetPath = path.join(targetDir, entry.name);
    let targetStat;
    try {
      targetStat = fs.lstatSync(targetPath);
    } catch {
      continue;
    }

    if (targetStat.isSymbolicLink()) {
      throw new Error(`refusing symbolic-link replacement: ${targetPath}`);
    }
    if (entry.isDirectory()) {
      if (!targetStat.isDirectory()) {
        throw new Error(`destination type conflict: ${targetPath}`);
      }
      validateCopyDestination(path.join(sourceDir, entry.name), targetPath);
    } else if (!targetStat.isFile()) {
      throw new Error(`destination type conflict: ${targetPath}`);
    }
  }
}

function installCustomPath(action, targetDir) {
  const verb = action === "install" ? "Installing" : "Uninstalling";
  const failedVerb = action === "install" ? "install" : "uninstall";
  info(`${verb} to custom path...`);
  info(`Source: ${SKILL_SOURCE_DIR}`);
  info(`Destination: ${targetDir}`);

  try {
    const destinationExists = fs.existsSync(targetDir);
    if (destinationExists) {
      const destinationStat = fs.lstatSync(targetDir);
      if (action === "install") {
        if (!destinationStat.isDirectory()) {
          throw new Error("destination must be a directory");
        }
        const manifest = path.join(targetDir, "SKILL.md");
        if (fs.existsSync(manifest) && !isSkillDirectory(targetDir)) {
          throw new Error("destination contains another Skill's SKILL.md");
        }
      } else if (!destinationStat.isDirectory() || !isSkillDirectory(targetDir)) {
        throw new Error("destination is not an installed Skill directory");
      }
    }

    if (action === "install") {
      validateCopyDestination(SKILL_SOURCE_DIR, targetDir);
    }

    if (DRY_RUN) {
      console.log(`  ${action === "install" ? "copy" : "remove"} "${targetDir}"`);
      return true;
    }

    if (action !== "install") {
      if (!destinationExists) {
        info("Custom path is already absent.");
        return true;
      }
      removeSkillContents(SKILL_SOURCE_DIR, targetDir);
      const retained = fs.readdirSync(targetDir);
      if (retained.length === 0) {
        fs.rmdirSync(targetDir);
      } else {
        info(`Retained existing entries: ${retained.join(", ")}`);
      }
      ok(`Uninstalled Skill files from custom path: ${targetDir}`);
      return true;
    }

    fs.mkdirSync(targetDir, { recursive: true });
    copyDirSync(SKILL_SOURCE_DIR, targetDir);
    if (!fs.existsSync(path.join(targetDir, "SKILL.md"))) {
      throw new Error("SKILL.md was not installed");
    }
    ok(`Installed to custom path: ${targetDir}`);
    return true;
  } catch (e) {
    warn(`Failed to ${failedVerb} custom path: ${e.message}`);
    info(action === "install"
      ? "Choose a writable dedicated skill directory and retry."
      : "Select the exact custom path that contains this Skill's SKILL.md.");
    return false;
  }
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
    return true;
  }
  try {
    // stdio: "pipe" (not "ignore") so child stderr is captured for the
    // failure path below; successful runs stay quiet.
    execSync(cmd, { stdio: "pipe", maxBuffer: 10 * 1024 * 1024 });
    return true;
  } catch (e) {
    const detail =
      (e && e.stderr && e.stderr.toString().trim()) ||
      (e && e.stdout && e.stdout.toString().trim()) ||
      (e && e.message) ||
      "";
    warn(`${desc} failed. Try manually.`);
    const lines = detail.split("\n").slice(0, 10).filter((l) => l.trim());
    if (lines.length > 0) {
      console.log(`    ${lines.join("\n    ")}`);
    }
    return false;
  }
}

// ── Interactive selection ───────────────────────────────────────────────────

async function promptSelectAgent(detected) {
  const sorted = [...detected];
  const allIds = new Set(PROVIDERS.flatMap((p) => [p.id, ...(p.aliases || [])]));

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
          (p) => p.id === token || (p.aliases || []).includes(token)
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
let CUSTOM_PATH = null;

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
      case "--path":
        const destination = argv[++i];
        if (!destination || destination.startsWith("--")) {
          err("--path requires an argument");
          process.exit(2);
        }
        CUSTOM_PATH = destination;
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
    --path <dir>      Install directly into the exact final skill directory
    --dry-run         Preview only, no files written
    --uninstall       Remove the skill
    --help, -h        Show this help

  Custom path:
    --path is the final skill directory; the installer does not append a name.
    It cannot be combined with --all or --only.
    Install preserves unrelated entries; uninstall removes only Skill files
    and removes the directory only when it becomes empty.

Supported agents:
${PROVIDERS.map((p) => {
  const aliases = p.aliases ? ` (aliases: ${p.aliases.join(", ")})` : "";
  return `    ${p.id.padEnd(15)} ${p.label}${aliases}`;
}).join("\n")}
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

  if (CUSTOM_PATH !== null) {
    if (ALL || ONLY_AGENTS.length > 0) {
      err("--path cannot be combined with --all or --only.");
      info("Use --path alone for direct custom-path installation.");
      process.exitCode = 2;
      return;
    }

    const targetDir = resolveCustomPath(CUSTOM_PATH);
    if (targetDir === null) {
      process.exitCode = 2;
      return;
    }

    if (!installCustomPath(action, targetDir)) {
      process.exitCode = 1;
    }
    return;
  }

  // Resolve target agents
  let targets;
  if (ONLY_AGENTS.length > 0) {
    // --only was specified: validate and use those
    targets = [];
    const unknown = [];
    for (const id of ONLY_AGENTS) {
      const provider = findProvider(id);
      if (!provider) {
        unknown.push(id);
      } else if (!targets.includes(provider)) {
        targets.push(provider);
      }
    }
    if (unknown.length > 0) {
      err(`Unknown agent(s): ${unknown.join(", ")}`);
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
  let allSucceeded = true;
  for (const agent of targets) {
    let operationSucceeded = false;
    switch (agent.id) {
      case "claude-code":
        operationSucceeded = installClaudeCode(action);
        break;
      case "gemini-cli":
        operationSucceeded = installGeminiCli(action);
        break;
      case "trae-cn":
        operationSucceeded = installTraeCn(action);
        break;
      default:
        operationSucceeded = runViaNpx(agent, action);
        break;
    }
    allSucceeded = operationSucceeded && allSucceeded;
    console.log("");
  }

  if (!allSucceeded) {
    const operation = action === "install" ? "Installation" : "Uninstallation";
    err(`${operation} failed for one or more targets.`);
    process.exitCode = 1;
    return;
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
