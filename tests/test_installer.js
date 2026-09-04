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

function createSuccessfulCommand(directory, name) {
  if (process.platform === "win32") {
    fs.writeFileSync(path.join(directory, `${name}.cmd`), "@echo off\r\nexit /b 0\r\n");
    return;
  }

  const command = path.join(directory, name);
  fs.writeFileSync(command, "#!/bin/sh\nexit 0\n");
  fs.chmodSync(command, 0o755);
}

function isolatedInstallerEnv(home, commandDirectory) {
  const separator = process.platform === "win32" ? ";" : ":";
  const systemPath = process.platform === "win32"
    ? path.join(process.env.SystemRoot || "C:\\Windows", "System32")
    : "/usr/bin:/bin";
  const pathValue = `${commandDirectory}${separator}${systemPath}`;
  const env = {
    ...process.env,
    HOME: home,
    USERPROFILE: home,
    APPDATA: path.join(home, "AppData", "Roaming"),
    LOCALAPPDATA: path.join(home, "AppData", "Local"),
    XDG_CONFIG_HOME: path.join(home, ".config"),
    CLAUDE_CONFIG_DIR: path.join(home, ".claude"),
    CODEX_HOME: path.join(home, ".codex"),
    HERMES_HOME: path.join(home, ".hermes"),
    PATH: pathValue,
  };
  if (process.platform === "win32") env.Path = pathValue;
  return env;
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

function testCustomPathRejectsAmbiguousOptions() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-custom-conflict-test-"));
  const destination = path.join(fixtureRoot, "harness", "blasphemous-modding-helper");

  try {
    for (const extraArgs of [["--only", "trae-cn"], ["--all"]]) {
      const result = runInstaller(["--path", destination, ...extraArgs]);
      const output = `${result.stdout || ""}\n${result.stderr || ""}`;

      assert.equal(result.status, 2, `Expected conflicting options to fail.\n${output}`);
      assert.match(output, /cannot be combined/i, `Missing conflict diagnostic.\n${output}`);
      assert.equal(fs.existsSync(destination), false);
    }
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testCustomPathRejectsAmbiguousOptions();
console.log("Custom-path conflict tests passed.");

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
  assert.match(output, /--path <dir>/);
  assert.match(output, /exact final skill directory/i);
  assert.match(output, /cannot be combined/i);
}

testCustomPathHelp();
console.log("Custom-path help test passed.");

function testCanonicalProviderCommands() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-provider-contract-test-"));
  const home = path.join(fixtureRoot, "home");
  const commandDirectory = path.join(fixtureRoot, "commands");
  fs.mkdirSync(home, { recursive: true });
  fs.mkdirSync(commandDirectory);
  const env = isolatedInstallerEnv(home, commandDirectory);

  try {
    for (const [canonical, alias, label] of [
      ["codex", "codex-cli", "Codex CLI"],
      ["hermes-agent", "hermes", "Hermes Agent"],
    ]) {
      for (const id of [canonical, alias]) {
        const result = runInstaller(["--only", id, "--dry-run"], { env });
        const output = `${result.stdout || ""}\n${result.stderr || ""}`;

        assert.equal(result.status, 0, `Provider selection failed for ${id}.\n${output}`);
        assert.match(output, new RegExp(label));
        assert.match(output, new RegExp(`npx -y skills add ${REPOSITORY.replace(/[.*+?^${}()|[\\]\\]/g, "\\\\$&")} -a ${canonical} -g -y`));
        assert.match(output, /Scope: user-level/i);
        assert.doesNotMatch(output, new RegExp(`-a ${alias}(?:\\s|$)`));
      }
    }

    const uninstall = runInstaller(["--only", "codex", "--uninstall", "--dry-run"], { env });
    const uninstallOutput = `${uninstall.stdout || ""}\n${uninstall.stderr || ""}`;
    assert.equal(uninstall.status, 0, `Canonical uninstall failed.\n${uninstallOutput}`);
    assert.match(uninstallOutput, /skills remove blasphemous-modding-helper -a codex -g -y/);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testCanonicalProviderCommands();
console.log("Canonical provider command tests passed.");

function runDetectionFixture(name, setup, expected) {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), `blasphemous-detection-${name}-`));
  const home = path.join(fixtureRoot, "home");
  const commandDirectory = path.join(fixtureRoot, "commands");
  fs.mkdirSync(home, { recursive: true });
  fs.mkdirSync(commandDirectory);
  const env = isolatedInstallerEnv(home, commandDirectory);

  try {
    setup(home, commandDirectory);
    const result = runInstaller(["--dry-run"], { env });
    const output = `${result.stdout || ""}\n${result.stderr || ""}`;

    assert.equal(result.status, 0, `${name} detection failed.\n${output}`);
    assert.match(output, expected, `${name} was not detected as expected.\n${output}`);
    assert.doesNotMatch(output, /Your choice \(default: all\)/i);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

function testPlatformNativeDetection() {
  runDetectionFixture(
    "trae-cn",
    (home) => fs.mkdirSync(path.join(home, ".trae-cn", "skills"), { recursive: true }),
    /Detected agents: Trae IDE \(Trae-CN\)[\s\S]*Target:[\s\S]*Scope: user-level/i
  );

  runDetectionFixture(
    "cursor-config",
    (home) => fs.mkdirSync(path.join(home, ".cursor")),
    /Detected agents: Cursor[\s\S]*-a cursor -g -y/i
  );

  runDetectionFixture(
    "windsurf-config",
    (home) => fs.mkdirSync(path.join(home, ".codeium", "windsurf"), { recursive: true }),
    /Detected agents: Windsurf[\s\S]*-a windsurf -g -y/i
  );

  runDetectionFixture(
    "cline-extension",
    (home) => fs.mkdirSync(path.join(home, ".vscode", "extensions", "saoudrizwan.claude-dev-3.0.0"), { recursive: true }),
    /Detected agents: Cline[\s\S]*-a cline -g -y/i
  );

  runDetectionFixture(
    "opencode-config",
    (home) => fs.mkdirSync(path.join(home, ".config", "opencode"), { recursive: true }),
    /Detected agents: opencode[\s\S]*-a opencode -g -y/i
  );

  runDetectionFixture(
    "codex-config",
    (home) => fs.mkdirSync(path.join(home, ".codex")),
    /Detected agents: Codex CLI[\s\S]*-a codex -g -y/i
  );

  runDetectionFixture(
    "hermes-config",
    (home) => fs.mkdirSync(path.join(home, ".hermes")),
    /Detected agents: Hermes Agent[\s\S]*-a hermes-agent -g -y/i
  );

  runDetectionFixture(
    "cursor-command",
    (_home, commandDirectory) => createSuccessfulCommand(commandDirectory, "cursor"),
    /Detected agents: Cursor[\s\S]*-a cursor -g -y/i
  );
}

testPlatformNativeDetection();
console.log("Platform-native detection tests passed.");

function testTraeRequiresSkillDirectory() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-trae-signal-test-"));
  const home = path.join(fixtureRoot, "home");
  const commandDirectory = path.join(fixtureRoot, "commands");
  fs.mkdirSync(path.join(home, ".trae-cn"), { recursive: true });
  fs.mkdirSync(commandDirectory);

  try {
    const result = runInstaller(["--dry-run"], {
      env: isolatedInstallerEnv(home, commandDirectory),
    });
    const output = `${result.stdout || ""}\n${result.stderr || ""}`;

    assert.equal(result.status, 1, `Empty Trae-CN config was treated as installed.\n${output}`);
    assert.match(output, /No supported AI coding agents detected/i);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testTraeRequiresSkillDirectory();
console.log("Trae-CN signal tests passed.");

function testUnixCommandRequiresExecutableBit() {
  if (process.platform === "win32") {
    console.log("Unix executable-bit test skipped on Windows.");
    return;
  }

  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-executable-test-"));
  const home = path.join(fixtureRoot, "home");
  const commandDirectory = path.join(fixtureRoot, "commands");
  fs.mkdirSync(home, { recursive: true });
  fs.mkdirSync(commandDirectory);

  try {
    fs.writeFileSync(path.join(commandDirectory, "cursor"), "#!/bin/sh\nexit 0\n");
    const result = runInstaller(["--dry-run"], {
      env: isolatedInstallerEnv(home, commandDirectory),
    });
    const output = `${result.stdout || ""}\n${result.stderr || ""}`;

    assert.equal(result.status, 1, `Non-executable command was detected.\n${output}`);
    assert.match(output, /No supported AI coding agents detected/i);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testUnixCommandRequiresExecutableBit();
console.log("Command executable-bit tests passed.");

function testNativeProviderDryRuns() {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-native-provider-test-"));
  const home = path.join(fixtureRoot, "home");
  const commandDirectory = path.join(fixtureRoot, "commands");
  fs.mkdirSync(home, { recursive: true });
  fs.mkdirSync(commandDirectory);
  const env = isolatedInstallerEnv(home, commandDirectory);

  try {
    for (const [id, expected, extra] of [
      [
        "claude-code",
        /plugin marketplace add EltonZhang777\/Blasphemous\.ModdingHelper\.Skill --scope user/,
        /plugin install "?blasphemous-modding-helper@blasphemous-modding-helper-marketplace"? --scope user/,
      ],
      ["gemini-cli", /extensions install https:\/\/github\.com\/EltonZhang777\/Blasphemous\.ModdingHelper\.Skill --consent --skip-settings/],
      ["trae-cn", /Target:/],
    ]) {
      const result = runInstaller(["--only", id, "--dry-run"], { env });
      const output = `${result.stdout || ""}\n${result.stderr || ""}`;

      assert.equal(result.status, 0, `${id} dry-run failed.\n${output}`);
      assert.match(output, expected);
      if (extra) assert.match(output, extra);
      assert.match(output, /Scope: user-level/i);
    }

    const claudeUninstall = runInstaller(["--only", "claude-code", "--uninstall", "--dry-run"], { env });
    const claudeUninstallOutput = `${claudeUninstall.stdout || ""}\n${claudeUninstall.stderr || ""}`;
    assert.match(claudeUninstallOutput, /plugin uninstall blasphemous-modding-helper --scope user --yes/);

    const geminiUninstall = runInstaller(["--only", "gemini-cli", "--uninstall", "--dry-run"], { env });
    const geminiUninstallOutput = `${geminiUninstall.stdout || ""}\n${geminiUninstall.stderr || ""}`;
    assert.match(geminiUninstallOutput, /extensions uninstall blasphemous-modding-helper/);

    const traeUninstall = runInstaller(["--only", "trae-cn", "--uninstall", "--dry-run"], { env });
    const traeUninstallOutput = `${traeUninstall.stdout || ""}\n${traeUninstall.stderr || ""}`;
    assert.match(traeUninstallOutput, /Target:[\s\S]*Scope: user-level[\s\S]*remove/i);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

testNativeProviderDryRuns();
console.log("Native provider dry-run tests passed.");

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
