#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const SKILL_NAME = "blasphemous-modding-helper";
const REPOSITORY_ROOT = path.resolve(__dirname, "..");
const SKILL_SOURCE_DIR = path.join(REPOSITORY_ROOT, "skills", SKILL_NAME);

const CYAN = "\x1b[36m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const RED = "\x1b[31m";
const NC = "\x1b[0m";

let DRY_RUN = false;
let UNINSTALL = false;
let DESTINATION = null;

function info(message) {
  console.log(`${CYAN}[*]${NC} ${message}`);
}

function ok(message) {
  console.log(`${GREEN}[✓]${NC} ${message}`);
}

function warn(message) {
  console.log(`${YELLOW}[!]${NC} ${message}`);
}

function err(message) {
  console.log(`${RED}[✗]${NC} ${message}`);
}

function showHelp() {
  console.log(`
  Blasphemous Modding Helper — Installer

  Usage:
    node bin/install.js --path <dir> [--dry-run] [--uninstall]

  Flags:
    --path <dir>      Install into the exact final skill directory
    --dry-run         Preview only, no files written
    --uninstall       Remove Skill-owned files from the exact directory
    --help            Show this help

  --path is required. The installer does not append a directory name.
  Install preserves unrelated entries; uninstall removes only Skill files
  and removes the directory only when it becomes empty.
`);
}

function usageError(message) {
  if (message) err(message);
  showHelp();
  process.exitCode = 2;
}

function parseArgs() {
  const argv = process.argv.slice(2);

  for (let index = 0; index < argv.length; index++) {
    switch (argv[index]) {
      case "--dry-run":
        DRY_RUN = true;
        break;
      case "--uninstall":
        UNINSTALL = true;
        break;
      case "--path": {
        const destination = argv[++index];
        if (!destination || destination.startsWith("--")) {
          usageError("--path requires an argument");
          return false;
        }
        DESTINATION = destination;
        break;
      }
      case "--help":
        showHelp();
        return false;
      default:
        usageError(`Unknown flag: ${argv[index]}`);
        return false;
    }
  }

  if (DESTINATION === null) {
    usageError("--path is required");
    return false;
  }

  return true;
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

  if (!fs.statSync(existingPath).isDirectory()) {
    throw new Error(`${existingPath} is not a directory`);
  }
  return path.resolve(fs.realpathSync(existingPath), ...missingSegments);
}

function isAllowedSystemSymlink(linkPath) {
  if (process.platform !== "darwin") return false;
  const root = path.parse(linkPath).root;
  if (linkPath !== path.join(root, "var")) return false;
  try {
    return fs.realpathSync(linkPath) === path.join(root, "private", "var");
  } catch {
    return false;
  }
}

function findSymbolicLinkAncestor(targetDir) {
  const root = path.parse(targetDir).root;
  const segments = path.relative(root, targetDir).split(path.sep).filter(Boolean);
  let currentPath = root;

  for (const segment of segments) {
    currentPath = path.join(currentPath, segment);
    try {
      if (fs.lstatSync(currentPath).isSymbolicLink() && !isAllowedSystemSymlink(currentPath)) {
        return currentPath;
      }
    } catch (error) {
      if (error.code === "ENOENT" || error.code === "ENOTDIR") break;
      throw error;
    }
  }

  return null;
}

function resolveDestination(rawPath) {
  const targetDir = path.resolve(process.cwd(), normalizeCustomPath(rawPath));
  const symbolicLinkAncestor = findSymbolicLinkAncestor(targetDir);
  if (symbolicLinkAncestor !== null) {
    err(`Custom path rejected: ${symbolicLinkAncestor} is a symbolic link or junction`);
    info("Choose a real dedicated directory to avoid redirecting installation.");
    return null;
  }

  let safetyTarget;
  try {
    safetyTarget = resolveRealPathForSafety(targetDir);
  } catch (error) {
    err(`Custom path rejected: ${targetDir}`);
    info(error.message);
    return null;
  }
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

function copyDirSync(sourceDir, targetDir) {
  fs.mkdirSync(targetDir, { recursive: true });
  for (const entry of fs.readdirSync(sourceDir, { withFileTypes: true })) {
    const sourcePath = path.join(sourceDir, entry.name);
    const targetPath = path.join(targetDir, entry.name);
    if (entry.isDirectory()) {
      copyDirSync(sourcePath, targetPath);
    } else {
      fs.copyFileSync(sourcePath, targetPath);
    }
  }
}

function installToDestination(action, targetDir) {
  const verb = action === "install" ? "Installing" : "Uninstalling";
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
  } catch (error) {
    warn(`Failed to ${action} custom path: ${error.message}`);
    info(action === "install"
      ? "Choose a writable dedicated skill directory and retry."
      : "Select the exact custom path that contains this Skill's SKILL.md.");
    return false;
  }
}

function main() {
  console.log("");
  console.log("  ╔══════════════════════════════════════════╗");
  console.log("  ║   Blasphemous Modding Helper Installer   ║");
  console.log("  ╚══════════════════════════════════════════╝");
  console.log("");

  if (!parseArgs()) return;

  if (DRY_RUN) {
    info("DRY RUN mode — no files will be written.");
    console.log("");
  }
  if (UNINSTALL) {
    info("UNINSTALL MODE.");
    console.log("");
  }

  const targetDir = resolveDestination(DESTINATION);
  if (targetDir === null) {
    process.exitCode = 2;
    return;
  }

  if (!installToDestination(UNINSTALL ? "uninstall" : "install", targetDir)) {
    process.exitCode = 1;
  }
}

try {
  main();
} catch (error) {
  err(`Unexpected error: ${error.message}`);
  process.exitCode = 1;
}
