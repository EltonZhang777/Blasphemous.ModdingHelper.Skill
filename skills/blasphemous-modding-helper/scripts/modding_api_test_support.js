"use strict";

const childProcess = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const scriptDirectory = __dirname;
const skillDirectory = path.resolve(scriptDirectory, "..");
const repositoryRoot = path.resolve(scriptDirectory, "../../..");
const defaultTimeout = 180000;

function text(value) {
  return value === undefined || value === null ? "" : String(value);
}

function commandOutput(result) {
  return [result.stdout, result.stderr]
    .map(text)
    .filter((value) => value.length > 0)
    .join("");
}

function commandWorks(command, args) {
  const result = childProcess.spawnSync(command, args, {
    encoding: "utf8",
    timeout: 10000,
    windowsHide: true,
  });
  return !result.error && result.status === 0;
}

function findPowerShell() {
  const explicit = process.env.MODDING_API_POWERSHELL;
  const candidates = explicit
    ? [explicit]
    : process.platform === "win32"
      ? ["powershell.exe", "pwsh"]
      : ["pwsh", "powershell"];
  for (const candidate of candidates) {
    if (commandWorks(candidate, ["-NoProfile", "-Command", "exit 0"])) {
      return candidate;
    }
  }
  throw new Error(
    "PowerShell is required for the cross-platform acceptance gate; " +
      "set MODDING_API_POWERSHELL to an executable path if discovery fails",
  );
}

function findBash() {
  const explicit = process.env.MODDING_API_BASH;
  const candidates = explicit
    ? [explicit]
    : process.platform === "win32"
      ? [
          path.join(process.env.ProgramFiles || "C:\\Program Files", "Git", "bin", "bash.exe"),
          "C:\\Program Files\\Git\\bin\\bash.exe",
          "bash",
        ]
      : ["bash"];
  for (const candidate of candidates) {
    if (commandWorks(candidate, ["--version"])) {
      return candidate;
    }
  }
  throw new Error(
    "Bash is required for the cross-platform acceptance gate; " +
      "set MODDING_API_BASH to an executable path if discovery fails",
  );
}

function toBashPath(filePath) {
  const normalized = path.resolve(filePath).replace(/\\/g, "/");
  const drive = normalized.match(/^([A-Za-z]):\/(.*)$/);
  if (drive) {
    return `/${drive[1].toLowerCase()}/${drive[2]}`;
  }
  return normalized;
}

function runCommand(command, args, options = {}) {
  const result = childProcess.spawnSync(command, args, {
    cwd: options.cwd || repositoryRoot,
    env: options.env || process.env,
    encoding: "utf8",
    timeout: options.timeout || defaultTimeout,
    windowsHide: true,
  });
  return {
    status: typeof result.status === "number" ? result.status : 1,
    output: commandOutput(result),
    timedOut: Boolean(result.error && result.error.code === "ETIMEDOUT"),
    error: result.error || null,
  };
}

function invokeBash(bash, script, args, env) {
  const bashArgs = process.platform === "win32" ? ["--login"] : [];
  bashArgs.push(toBashPath(script));
  for (const argument of args || []) {
    bashArgs.push(
      process.platform === "win32" && /^(--target-path|--preferences-file|--metadata-file)$/.test(argument)
        ? argument
        : process.platform === "win32" && /^([A-Za-z]):[\\/]/.test(argument)
          ? toBashPath(argument)
          : argument,
    );
  }
  return runCommand(bash, bashArgs, { env });
}

function invokePowerShell(powerShell, script, args, env) {
  return runCommand(
    powerShell,
    [
      "-NoLogo",
      "-NoProfile",
      "-NonInteractive",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      script,
    ].concat(args || []),
    { env },
  );
}

function parseKeyValues(output) {
  const values = {};
  for (const line of text(output).split(/\r?\n/)) {
    const separator = line.indexOf("=");
    if (separator > 0) {
      values[line.slice(0, separator)] = line.slice(separator + 1);
    }
  }
  return values;
}

function createFixtureDirectory(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

module.exports = {
  commandOutput,
  createFixtureDirectory,
  findBash,
  findPowerShell,
  invokeBash,
  invokePowerShell,
  parseKeyValues,
  repositoryRoot,
  runCommand,
  scriptDirectory,
  skillDirectory,
  text,
  toBashPath,
};
