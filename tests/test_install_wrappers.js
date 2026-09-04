"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const REPO_ROOT = path.resolve(__dirname, "..");
const BASH_WRAPPER = path.join(REPO_ROOT, "install.sh");
const POWERSHELL_WRAPPER = path.join(REPO_ROOT, "install.ps1");
const REAL_NODE = process.execPath;
const REPOSITORY = "EltonZhang777/Blasphemous.ModdingHelper.Skill";

function writeFakeCommand(directory, name, script) {
  if (process.platform === "win32") {
    fs.writeFileSync(
      path.join(directory, `${name}.cmd`),
      `@echo off\r\n"%REAL_NODE%" "%FAKE_${name.toUpperCase()}_SCRIPT%" %*\r\nexit /b %ERRORLEVEL%\r\n`,
    );
    // Git Bash does not always resolve a Windows .cmd shim for a command
    // named npx. Keep an extensionless POSIX shim beside it for Bash tests.
    const bashCommand = path.join(directory, name);
    fs.writeFileSync(
      bashCommand,
      [
        "#!/bin/sh",
        "real_node=\"$REAL_NODE\"",
        "if command -v cygpath >/dev/null 2>&1; then real_node=$(cygpath -u \"$REAL_NODE\"); fi",
        `exec \"$real_node\" \"$FAKE_${name.toUpperCase()}_SCRIPT\" \"$@\"`,
        "",
      ].join("\n"),
    );
    fs.chmodSync(bashCommand, 0o755);
  } else {
    const command = path.join(directory, name);
    fs.writeFileSync(command, `#!/bin/sh\nexec "$REAL_NODE" "$FAKE_${name.toUpperCase()}_SCRIPT" "$@"\n`);
    fs.chmodSync(command, 0o755);
  }
  fs.writeFileSync(script.path, script.contents);
}

function createFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "blasphemous-wrapper-test-"));
  const commands = path.join(root, "commands");
  const decoy = path.join(root, "decoy");
  const capture = path.join(root, "capture.json");
  const fakeNodeScript = {
    path: path.join(root, "fake-node.js"),
    contents: [
      "const fs = require('node:fs');",
      "if (process.argv[2] === '-p') { process.stdout.write('18\\n'); process.exit(0); }",
      "fs.writeFileSync(process.env.WRAPPER_CAPTURE, JSON.stringify(process.argv.slice(2)));",
      "process.exit(Number(process.env.WRAPPER_EXIT || '0'));",
      "",
    ].join("\n"),
  };
  const fakeNpxScript = {
    path: path.join(root, "fake-npx.js"),
    contents: [
      "const fs = require('node:fs');",
      "fs.writeFileSync(process.env.WRAPPER_CAPTURE, JSON.stringify(process.argv.slice(2)));",
      "process.exit(Number(process.env.WRAPPER_EXIT || '0'));",
      "",
    ].join("\n"),
  };

  fs.mkdirSync(commands);
  fs.mkdirSync(path.join(decoy, "bin"), { recursive: true });
  fs.writeFileSync(path.join(decoy, "bin", "install.js"), "decoy installer\n");
  writeFakeCommand(commands, "node", fakeNodeScript);
  writeFakeCommand(commands, "npx", fakeNpxScript);

  const separator = process.platform === "win32" ? ";" : ":";
  const env = {
    ...process.env,
    PATH: `${commands}${separator}${process.env.PATH || ""}`,
    REAL_NODE,
    FAKE_NODE_SCRIPT: fakeNodeScript.path,
    FAKE_NPX_SCRIPT: fakeNpxScript.path,
    WRAPPER_CAPTURE: capture,
    WRAPPER_EXIT: "0",
    CI: "1",
  };
  if (process.platform === "win32") env.Path = env.PATH;

  return { root, commands, decoy, capture, env };
}

function run(command, args, fixture, options = {}) {
  return spawnSync(command, args, {
    cwd: options.cwd || fixture.decoy,
    env: fixture.env,
    encoding: "utf8",
    input: options.input,
    stdio: ["pipe", "pipe", "pipe"],
    timeout: 5000,
  });
}

function readCapture(fixture) {
  assert.equal(fs.existsSync(fixture.capture), true, "wrapper did not invoke the delegated command");
  return JSON.parse(fs.readFileSync(fixture.capture, "utf8"));
}

function assertCapture(fixture, expected) {
  const normalize = (value) => process.platform === "win32" && /^[A-Za-z]:[\\/]/.test(value)
    ? path.win32.normalize(value)
    : value;
  assert.deepEqual(readCapture(fixture).map(normalize), expected.map(normalize));
}

function clearCapture(fixture) {
  fs.rmSync(fixture.capture, { force: true });
}

function shellAvailable(command, args) {
  const result = spawnSync(command, args, { stdio: "ignore", timeout: 5000 });
  return !result.error && result.status === 0;
}

function findPowerShell() {
  for (const command of ["pwsh", "powershell"]) {
    if (shellAvailable(command, ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", "exit 0"])) {
      return command;
    }
  }
  return null;
}

function powershellQuote(value) {
  return `'${value.replaceAll("'", "''")}'`;
}

function testBash() {
  if (!shellAvailable("bash", ["-c", "exit 0"])) {
    console.log("Bash wrapper tests skipped: no working Bash host.");
    return;
  }

  const fixture = createFixture();
  try {
    const destination = path.join(fixture.root, "custom destination");
    const directArgs = ["--dry-run", "--only", "trae-cn", "--uninstall"];
    const direct = run("bash", [BASH_WRAPPER, ...directArgs], fixture);
    assert.equal(direct.status, 0, direct.stderr);
    assertCapture(fixture, [path.join(REPO_ROOT, "bin", "install.js"), ...directArgs]);

    clearCapture(fixture);
    fixture.env.WRAPPER_EXIT = "7";
    const failed = run("bash", [BASH_WRAPPER, "--dry-run"], fixture);
    assert.equal(failed.status, 7, `${failed.stdout}\n${failed.stderr}`);

    clearCapture(fixture);
    fixture.env.WRAPPER_EXIT = "0";
    const remoteArgs = ["--path", destination];
    const remote = run("bash", ["-s", "--", ...remoteArgs], fixture, {
      input: fs.readFileSync(BASH_WRAPPER),
    });
    assert.equal(remote.status, 0, `${remote.stdout}\n${remote.stderr}`);
    assertCapture(fixture, ["-y", `github:${REPOSITORY}`, ...remoteArgs]);

    clearCapture(fixture);
    fixture.env.WRAPPER_EXIT = "9";
    const remoteFailed = run("bash", ["-s"], fixture, {
      input: fs.readFileSync(BASH_WRAPPER),
    });
    assert.equal(remoteFailed.status, 9, `${remoteFailed.stdout}\n${remoteFailed.stderr}`);
  } finally {
    fs.rmSync(fixture.root, { recursive: true, force: true });
  }
  console.log("Bash wrapper contract tests passed.");
}

function testPowerShell() {
  const powershell = findPowerShell();
  if (!powershell) {
    console.log("PowerShell wrapper tests skipped: no working PowerShell host.");
    return;
  }

  const fixture = createFixture();
  try {
    const destination = path.join(fixture.root, "custom destination");
    // Synthetic vector: verify raw forwarding without invoking the installer.
    const directArgs = ["--dry-run", "--only", "trae-cn", "--uninstall", "--path", destination];
    const direct = run(
      powershell,
      ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", POWERSHELL_WRAPPER, ...directArgs],
      fixture,
    );
    assert.equal(direct.status, 0, `${direct.stdout}\n${direct.stderr}`);
    assertCapture(fixture, [path.join(REPO_ROOT, "bin", "install.js"), ...directArgs]);

    clearCapture(fixture);
    fixture.env.WRAPPER_EXIT = "7";
    const failed = run(
      powershell,
      ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", POWERSHELL_WRAPPER, "--dry-run"],
      fixture,
    );
    assert.equal(failed.status, 7, `${failed.stdout}\n${failed.stderr}`);

    clearCapture(fixture);
    fixture.env.WRAPPER_EXIT = "0";
    const remoteCommand = [
      `$content = Get-Content -Raw -LiteralPath ${powershellQuote(POWERSHELL_WRAPPER)}`,
      "Invoke-Expression $content",
    ].join("; ");
    const remote = run(
      powershell,
      ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", remoteCommand],
      fixture,
    );
    assert.equal(remote.status, 0, `${remote.stdout}\n${remote.stderr}`);
    assertCapture(fixture, ["-y", `github:${REPOSITORY}`]);

    clearCapture(fixture);
    fixture.env.WRAPPER_EXIT = "9";
    const remoteFailed = run(
      powershell,
      ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", remoteCommand],
      fixture,
    );
    assert.equal(remoteFailed.status, 9, `${remoteFailed.stdout}\n${remoteFailed.stderr}`);
  } finally {
    fs.rmSync(fixture.root, { recursive: true, force: true });
  }
  console.log("PowerShell wrapper contract tests passed.");
}

function testDocumentation() {
  const contents = fs.readFileSync(POWERSHELL_WRAPPER, "utf8");
  const help = contents.slice(0, contents.indexOf("#>"));
  assert.match(help, /\.\\install\.ps1 --dry-run/);
  assert.match(help, /\.\\install\.ps1 --only trae-cn/);
  assert.match(help, /\.\\install\.ps1 --dry-run --path/);
  assert.doesNotMatch(help, /-InstallerArgs/);
  console.log("Wrapper documentation tests passed.");
}

testDocumentation();
testBash();
testPowerShell();
console.log("Installer wrapper tests completed.");
