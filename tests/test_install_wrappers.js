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

function writeFakeCommand(directory, name, script) {
  if (process.platform === "win32") {
    fs.writeFileSync(
      path.join(directory, `${name}.cmd`),
      `@echo off\r\n"%REAL_NODE%" "%FAKE_${name.toUpperCase()}_SCRIPT%" %*\r\nexit /b %ERRORLEVEL%\r\n`,
    );
    // Git Bash does not always resolve a Windows .cmd shim. Keep an
    // extensionless POSIX shim beside it for Bash tests.
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
  const npxCapture = path.join(root, "npx-capture.json");
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
      "fs.writeFileSync(process.env.WRAPPER_NPX_CAPTURE, JSON.stringify(process.argv.slice(2)));",
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
    WRAPPER_NPX_CAPTURE: npxCapture,
    WRAPPER_EXIT: "0",
    CI: "1",
  };
  if (process.platform === "win32") env.Path = env.PATH;

  return { root, commands, decoy, capture, npxCapture, env };
}

function run(command, args, fixture, options = {}) {
  return spawnSync(command, args, {
    cwd: options.cwd || fixture.decoy,
    env: fixture.env,
    encoding: "utf8",
    input: options.input,
    stdio: ["pipe", "pipe", "pipe"],
    timeout: 30000,
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
  fs.rmSync(fixture.npxCapture, { force: true });
}

function assertCloneGuidance(result) {
  const output = `${result.stdout || ""}\n${result.stderr || ""}`;
  assert.notEqual(result.status, 0, `Clone-less invocation succeeded.\n${output}`);
  assert.match(output, /clon/i, `Clone guidance is missing.\n${output}`);
  assert.match(output, /install\.(?:sh|ps1)|local script/i, `Local-script guidance is missing.\n${output}`);
}

function assertNoDelegation(fixture, message) {
  assert.equal(fs.existsSync(fixture.capture), false, message);
  assert.equal(fs.existsSync(fixture.npxCapture), false, "Clone-less invocation invoked npx.");
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
    const directArgs = ["--path", destination, "--dry-run", "--uninstall"];
    const direct = run("bash", [BASH_WRAPPER, ...directArgs], fixture);
    assert.equal(direct.status, 0, direct.stderr);
    assertCapture(fixture, [path.join(REPO_ROOT, "bin", "install.js"), ...directArgs]);

    clearCapture(fixture);
    fixture.env.WRAPPER_EXIT = "7";
    const failed = run("bash", [BASH_WRAPPER, "--path", destination, "--dry-run"], fixture);
    assert.equal(failed.status, 7, `${failed.stdout}\n${failed.stderr}`);

    clearCapture(fixture);
    fixture.env.WRAPPER_EXIT = "0";
    const remoteArgs = ["--path", destination];
    const remote = run("bash", ["-s", "--", ...remoteArgs], fixture, {
      input: fs.readFileSync(BASH_WRAPPER),
    });
    assertCloneGuidance(remote);
    assertNoDelegation(fixture, "Clone-less Bash invoked a delegated command.");

    const caller = path.join(fixture.decoy, "caller.sh");
    fs.writeFileSync(caller, fs.readFileSync(BASH_WRAPPER));
    const evaluated = run("bash", [caller, "--path", destination, "--dry-run"], fixture);
    assertCloneGuidance(evaluated);
    assertNoDelegation(fixture, "Eval caller invoked its adjacent installer.");
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
    const directArgs = ["--path", destination, "--dry-run", "--uninstall"];
    const direct = run(
      powershell,
      ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", POWERSHELL_WRAPPER, ...directArgs],
      fixture,
    );
    assert.equal(direct.status, 0, `${direct.stdout}\n${direct.stderr}`);
    assertCapture(fixture, [path.join(REPO_ROOT, "bin", "install.js"), ...directArgs]);

    clearCapture(fixture);
    const flagNamedDestination = path.join(fixture.root, "legit folder --uninstall");
    const flagNamed = run(
      powershell,
      [
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        POWERSHELL_WRAPPER,
        "--path",
        flagNamedDestination,
        "--dry-run",
      ],
      fixture,
    );
    assert.equal(flagNamed.status, 0, `${flagNamed.stdout}\n${flagNamed.stderr}`);
    assertCapture(fixture, [
      path.join(REPO_ROOT, "bin", "install.js"),
      "--path",
      flagNamedDestination,
      "--dry-run",
    ]);

    const cmdShell = path.join(process.env.SystemRoot || "C:\\Windows", "System32", "cmd.exe");
    const windowsPowerShell = path.join(
      process.env.SystemRoot || "C:\\Windows",
      "System32",
      "WindowsPowerShell",
      "v1.0",
      "powershell.exe",
    );
    if (process.platform === "win32" && fs.existsSync(cmdShell) && fs.existsSync(windowsPowerShell)) {
      clearCapture(fixture);
      const cmdDestination = `${path.join(fixture.root, "cmd legit --uninstall folder")}\\`;
      const realWrapperRoot = path.join(fixture.root, "real-wrapper");
      const realWrapper = path.join(realWrapperRoot, "install.ps1");
      const realCapture = path.join(realWrapperRoot, "capture.json");
      fs.mkdirSync(path.join(realWrapperRoot, "bin"), { recursive: true });
      fs.copyFileSync(POWERSHELL_WRAPPER, realWrapper);
      fs.writeFileSync(
        path.join(realWrapperRoot, "bin", "install.js"),
        "require('node:fs').writeFileSync(process.env.REAL_NODE_CAPTURE, JSON.stringify(process.argv.slice(2)));\n",
      );
      const realEnv = {
        ...fixture.env,
        PATH: `${path.dirname(process.execPath)};${process.env.PATH || ""}`,
        REAL_NODE_CAPTURE: realCapture,
      };
      realEnv.Path = realEnv.PATH;
      const command = [
        `"${windowsPowerShell}"`,
        "-NoProfile -NonInteractive -ExecutionPolicy Bypass",
        `-File "${realWrapper}"`,
        `--path "${cmdDestination}"`,
        "--dry-run",
      ].join(" ");
      const throughCmd = spawnSync(command, {
        cwd: fixture.decoy,
        env: realEnv,
        encoding: "utf8",
        shell: cmdShell,
        timeout: 30000,
      });
      assert.equal(throughCmd.status, 0, `${throughCmd.stdout}\n${throughCmd.stderr}`);
      assert.deepEqual(JSON.parse(fs.readFileSync(realCapture, "utf8")), [
        "--path",
        cmdDestination.slice(0, -1),
        "--dry-run",
      ]);
    }

    clearCapture(fixture);
    fixture.env.WRAPPER_EXIT = "7";
    const failed = run(
      powershell,
      [
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        POWERSHELL_WRAPPER,
        "--path",
        destination,
        "--dry-run",
      ],
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
    assertCloneGuidance(remote);
    assertNoDelegation(fixture, "Clone-less PowerShell invoked a delegated command.");

    const caller = path.join(fixture.decoy, "caller.ps1");
    fs.writeFileSync(caller, fs.readFileSync(POWERSHELL_WRAPPER));
    const evaluated = run(
      powershell,
      ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", caller],
      fixture,
    );
    assertCloneGuidance(evaluated);
    assertNoDelegation(fixture, "Eval caller invoked its adjacent installer.");
  } finally {
    fs.rmSync(fixture.root, { recursive: true, force: true });
  }
  console.log("PowerShell wrapper contract tests passed.");
}

function testDocumentation() {
  const bash = fs.readFileSync(BASH_WRAPPER, "utf8");
  const powershell = fs.readFileSync(POWERSHELL_WRAPPER, "utf8");
  const powershellHelp = powershell.slice(0, powershell.indexOf("#>"));

  assert.match(bash, /bash install\.sh --path <AGENT_SKILLS_DIR>\/blasphemous-modding-helper/);
  assert.match(bash, /bash install\.sh --path <AGENT_SKILLS_DIR>\/blasphemous-modding-helper --dry-run/);
  assert.match(powershellHelp, /\.\\install\.ps1 --path <AGENT_SKILLS_DIR>\\blasphemous-modding-helper/);
  assert.match(powershellHelp, /\.\\install\.ps1 --path <AGENT_SKILLS_DIR>\\blasphemous-modding-helper --dry-run/);
  for (const contents of [bash, powershell]) {
    assert.doesNotMatch(contents, /\bnpx\b|--only|--all|raw\.githubusercontent\.com/i);
  }
  assert.doesNotMatch(powershellHelp, /-InstallerArgs/);
  console.log("Wrapper documentation tests passed.");
}

testDocumentation();
testBash();
testPowerShell();
console.log("Installer wrapper tests completed.");
