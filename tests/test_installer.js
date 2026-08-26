"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const REPO_ROOT = path.resolve(__dirname, "..");
const INSTALLER = path.join(REPO_ROOT, "bin", "install.js");

function createFailingClaudeCommand(directory) {
  if (process.platform === "win32") {
    const command = path.join(directory, "claude.cmd");
    fs.writeFileSync(command, "@echo off\r\nexit /b 7\r\n");
    return;
  }

  const command = path.join(directory, "claude");
  fs.writeFileSync(command, "#!/bin/sh\nexit 7\n");
  fs.chmodSync(command, 0o755);
}

function prependPath(directory) {
  const separator = process.platform === "win32" ? ";" : ":";
  return `${directory}${separator}${process.env.PATH || ""}`;
}

function runInstallerWithFailingProvider() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-installer-test-"));
  const commandDirectory = path.join(fixtureRoot, "commands");
  fs.mkdirSync(commandDirectory);
  // This intentionally omits --dry-run to exercise failure propagation. The
  // provider is a temporary fixture command, so no real installation occurs.
  createFailingClaudeCommand(commandDirectory);

  try {
    return spawnSync(process.execPath, [INSTALLER, "--only", "claude-code"], {
      cwd: REPO_ROOT,
      encoding: "utf8",
      env: {
        ...process.env,
        PATH: prependPath(commandDirectory),
      },
    });
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

const result = runInstallerWithFailingProvider();
const output = `${result.stdout || ""}\n${result.stderr || ""}`;

assert.notEqual(result.status, 0, `Expected a nonzero exit status.\n${output}`);
assert.match(output, /failed/i, `Expected a failure diagnostic.\n${output}`);
assert.doesNotMatch(output, /Install complete!/i, `Unexpected success message.\n${output}`);

console.log("Installer failure propagation test passed.");
