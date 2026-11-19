"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const REPO_ROOT = path.resolve(__dirname, "..");
const INSTALLER = path.join(REPO_ROOT, "bin", "install.js");
const SKILL_SOURCE = path.join(REPO_ROOT, "skills", "blasphemous-modding-helper");
const REPOSITORY = "EltonZhang777/Blasphemous.ModdingHelper.Skill";

function createCapturingCommand(directory, name) {
  if (process.platform === "win32") {
    fs.writeFileSync(
      path.join(directory, `${name}.cmd`),
      "@echo off\r\necho invoked>\"%INSTALLER_COMMAND_CAPTURE%\"\r\nexit /b 0\r\n",
    );
    return;
  }

  const command = path.join(directory, name);
  fs.writeFileSync(command, '#!/bin/sh\nprintf invoked > "$INSTALLER_COMMAND_CAPTURE"\n');
  fs.chmodSync(command, 0o755);
}

function prependPath(directory) {
  const separator = process.platform === "win32" ? ";" : ":";
  return `${directory}${separator}${process.env.PATH || ""}`;
}

function runInstaller(args, options = {}) {
  return spawnSync(process.execPath, [INSTALLER, ...args], {
    cwd: options.cwd || REPO_ROOT,
    encoding: "utf8",
    env: options.env || process.env,
  });
}

function listFiles(directory, prefix = "") {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const relativePath = path.join(prefix, entry.name);
    if (entry.isDirectory()) {
      files.push(...listFiles(path.join(directory, entry.name), relativePath));
    } else {
      files.push(relativePath);
    }
  }
  return files;
}

function fileContents(directory) {
  return Object.fromEntries(listFiles(directory).sort().map((relativePath) => [
    relativePath,
    fs.readFileSync(path.join(directory, relativePath)),
  ]));
}

function testPathIsRequired() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-required-path-test-"));

  try {
    for (const args of [[], ["--dry-run"], ["--uninstall"], ["--path"]]) {
      const result = runInstaller(args, { cwd: fixtureRoot });
      const output = `${result.stdout || ""}\n${result.stderr || ""}`;

      assert.equal(result.status, 2, `Expected missing --path to fail.\n${output}`);
      assert.match(output, /usage:/i, `Missing usage guidance.\n${output}`);
      assert.match(output, /--path <dir>/, `Missing --path guidance.\n${output}`);
      assert.deepEqual(listFiles(fixtureRoot), [], `Installer wrote files.\n${output}`);
    }
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testPathIsRequired();
console.log("Explicit-path requirement tests passed.");

function testRemovedProviderFlagsAreRejected() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-removed-flags-test-"));
  const commandDirectory = path.join(fixtureRoot, "commands");
  const capture = path.join(fixtureRoot, "command-capture");
  fs.mkdirSync(commandDirectory);
  for (const command of ["npx", "claude", "gemini"]) {
    createCapturingCommand(commandDirectory, command);
  }
  const env = {
    ...process.env,
    PATH: prependPath(commandDirectory),
    INSTALLER_COMMAND_CAPTURE: capture,
  };
  if (process.platform === "win32") env.Path = env.PATH;

  try {
    for (const args of [["--all"], ["--only", "claude-code"], ["--only", "codex"]]) {
      const result = runInstaller(args, { cwd: fixtureRoot, env });
      const output = `${result.stdout || ""}\n${result.stderr || ""}`;

      assert.equal(result.status, 2, `Removed flag was accepted.\n${output}`);
      assert.match(output, /unknown flag/i, `Missing unknown-flag diagnostic.\n${output}`);
      assert.match(output, /usage:/i, `Missing usage guidance.\n${output}`);
      assert.equal(fs.existsSync(capture), false, "A provider command was invoked.");
    }
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testRemovedProviderFlagsAreRejected();
console.log("Removed provider-flag tests passed.");

// These tests intentionally perform real filesystem operations only inside
// isolated OS temp directories; they never touch user-level agent paths.
function testCustomPathInstall() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-custom-path-test-"));
  const destination = path.join(fixtureRoot, "custom harness", "blasphemous-modding-helper");

  try {
    const install = runInstaller(["--path", destination]);
    const installOutput = `${install.stdout || ""}\n${install.stderr || ""}`;

    assert.equal(install.status, 0, `Custom-path install failed.\n${installOutput}`);
    assert.match(installOutput, /custom path/i, `Missing custom-path output.\n${installOutput}`);
    assert.match(installOutput, new RegExp(destination.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    assert.equal(fs.existsSync(path.join(destination, "SKILL.md")), true);
    assert.deepEqual(fileContents(destination), fileContents(SKILL_SOURCE));
    assert.doesNotMatch(installOutput, /via npx skills|Detected agents/i);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testCustomPathInstall();
console.log("Custom-path install test passed.");

function testCustomPathUninstallPreservesUnrelatedFiles() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-custom-uninstall-test-"));
  const destination = path.join(fixtureRoot, "harness", "blasphemous-modding-helper");
  const sibling = path.join(fixtureRoot, "sibling.txt");

  try {
    const install = runInstaller(["--path", destination]);
    assert.equal(install.status, 0, `${install.stdout || ""}\n${install.stderr || ""}`);
    fs.writeFileSync(path.join(destination, "keep.txt"), "keep this file");
    fs.writeFileSync(sibling, "keep sibling");

    const uninstall = runInstaller(["--path", destination, "--uninstall"]);
    const uninstallOutput = `${uninstall.stdout || ""}\n${uninstall.stderr || ""}`;

    assert.equal(uninstall.status, 0, `Custom-path uninstall failed.\n${uninstallOutput}`);
    assert.equal(fs.existsSync(path.join(destination, "SKILL.md")), false);
    assert.equal(fs.readFileSync(path.join(destination, "keep.txt"), "utf8"), "keep this file");
    assert.equal(fs.readFileSync(sibling, "utf8"), "keep sibling");
    assert.match(uninstallOutput, /retained|preserved/i);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testCustomPathUninstallPreservesUnrelatedFiles();
console.log("Custom-path uninstall preservation test passed.");

function testCustomPathDryRunAndNativePathForms() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-custom-forms-test-"));
  const forms = [
    {
      argument: path.win32.join("windows-form", "blasphemous-modding-helper"),
      destination: path.join(fixtureRoot, "windows-form", "blasphemous-modding-helper"),
    },
    {
      argument: path.posix.join("unix-form", "blasphemous-modding-helper"),
      destination: path.join(fixtureRoot, "unix-form", "blasphemous-modding-helper"),
    },
  ];

  try {
    forms.forEach((form, index) => {
      const args = ["--path", form.argument];
      if (index === 0) args.push("--dry-run");
      const result = runInstaller(args, { cwd: fixtureRoot });
      const output = `${result.stdout || ""}\n${result.stderr || ""}`;

      assert.equal(result.status, 0, `Custom-path form failed.\n${output}`);
      assert.match(output, new RegExp(form.destination.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
      if (index === 0) {
        assert.equal(fs.existsSync(form.destination), false);
      } else {
        assert.equal(fs.existsSync(path.join(form.destination, "SKILL.md")), true);
      }
    });
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testCustomPathDryRunAndNativePathForms();
console.log("Custom-path dry-run and path-form tests passed.");

function testCustomPathRejectsUnsafeDestinations() {
  const destinations = [
    path.join(REPO_ROOT, "skills", "blasphemous-modding-helper"),
    path.join(REPO_ROOT, "skills"),
    path.join(REPO_ROOT, "bin", "custom-destination"),
    REPO_ROOT,
  ];

  for (const destination of destinations) {
    const result = runInstaller(["--path", destination, "--dry-run"]);
    const output = `${result.stdout || ""}\n${result.stderr || ""}`;

    assert.equal(result.status, 2, `Unsafe destination was accepted.\n${output}`);
    assert.match(output, /custom path rejected|source|repository root/i);
  }
}

testCustomPathRejectsUnsafeDestinations();
console.log("Custom-path safety boundary tests passed.");

function testCustomPathRejectsFileAncestor() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-file-ancestor-test-"));
  const blocker = path.join(fixtureRoot, "blocker");
  const destination = path.join(blocker, "blasphemous-modding-helper");

  try {
    fs.writeFileSync(blocker, "not a directory");
    const result = runInstaller(["--path", destination, "--dry-run"]);
    const output = `${result.stdout || ""}\n${result.stderr || ""}`;

    assert.equal(result.status, 2, `File ancestor was accepted.\n${output}`);
    assert.match(output, /custom path rejected/i);
    assert.match(output, /not a directory/i);
    assert.equal(fs.readFileSync(blocker, "utf8"), "not a directory");
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testCustomPathRejectsFileAncestor();
console.log("Custom-path file-ancestor safety test passed.");

function testCustomPathRejectsAncestorLinks() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-custom-link-test-"));
  const link = path.join(fixtureRoot, "source-alias");
  const redirectedRoot = path.join(fixtureRoot, "redirected");
  const destination = path.join(link, "child");

  try {
    fs.mkdirSync(redirectedRoot);
    try {
      fs.symlinkSync(redirectedRoot, link, process.platform === "win32" ? "junction" : "dir");
    } catch (error) {
      if (process.platform === "win32" && ["EACCES", "EPERM"].includes(error.code)) {
        console.log("Custom-path ancestor-link test skipped: directory-link permission unavailable.");
        return;
      }
      throw error;
    }

    const result = runInstaller(["--path", destination]);
    const output = `${result.stdout || ""}\n${result.stderr || ""}`;

    assert.equal(result.status, 2, `Ancestor link destination was accepted.\n${output}`);
    assert.match(output, /custom path rejected|symbolic link|junction/i);
    assert.equal(fs.existsSync(path.join(redirectedRoot, "child", "SKILL.md")), false);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testCustomPathRejectsAncestorLinks();
console.log("Custom-path ancestor-link safety test passed.");

function testCustomPathDoesNotReplaceAnotherSkill() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-custom-replacement-test-"));
  const destination = path.join(fixtureRoot, "other-skill");
  const manifest = path.join(destination, "SKILL.md");
  const original = "---\nname: another-skill\n---\n";

  try {
    fs.mkdirSync(destination, { recursive: true });
    fs.writeFileSync(manifest, original);

    const result = runInstaller(["--path", destination]);
    const output = `${result.stdout || ""}\n${result.stderr || ""}`;

    assert.notEqual(result.status, 0, `Unsafe replacement was accepted.\n${output}`);
    assert.match(output, /refus|another|Skill directory/i);
    assert.equal(fs.readFileSync(manifest, "utf8"), original);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testCustomPathDoesNotReplaceAnotherSkill();
console.log("Custom-path replacement safety test passed.");

function testCustomPathHelp() {
  const result = runInstaller(["--help"]);
  const output = `${result.stdout || ""}\n${result.stderr || ""}`;

  assert.equal(result.status, 0, `Installer help failed.\n${output}`);
  assert.match(output, /--path <dir> \[--dry-run\] \[--uninstall\]/);
  assert.match(output, /--path <dir>/);
  assert.match(output, /exact final skill directory/i);
  assert.match(output, /--dry-run/);
  assert.match(output, /--uninstall/);
  assert.match(output, /--help/);
  assert.doesNotMatch(output, /--all|--only|provider|auto-detect|marketplace|extension|npx/i);
}

testCustomPathHelp();
console.log("Custom-path help test passed.");

function testClaudeMarketplaceManifest() {
  const manifestPath = path.join(REPO_ROOT, ".claude-plugin", "marketplace.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

  assert.equal(manifest.name, "blasphemous-modding-helper-marketplace");
  assert.equal(manifest.plugins.length, 1);
  assert.equal(manifest.plugins[0].name, "blasphemous-modding-helper");
  assert.deepEqual(manifest.plugins[0].source, {
    source: "github",
    repo: REPOSITORY,
  });
}

testClaudeMarketplaceManifest();
console.log("Claude marketplace manifest test passed.");
