"use strict";

const path = require("path");
const support = require("./modding_api_test_support");

function fail(message) {
  throw new Error(message);
}

function assert(condition, message) {
  if (!condition) {
    fail(message);
  }
}

function liveValues(output) {
  return support.parseKeyValues(output);
}

function resolveLive(surface, command, script, args, env) {
  const result =
    surface === "bash"
      ? support.invokeBash(command, script, args, env)
      : support.invokePowerShell(command, script, args, env);
  if (result.status !== 0) {
    fail(
      `${surface} live Release resolution failed with exit code ${result.status}${
        result.timedOut ? " (timed out)" : ""
      }:\n${result.output}`,
    );
  }
  return liveValues(result.output);
}

function verifyValues(surface, values) {
  const tag = values.MODDING_API_RESOLVED_TAG;
  const commit = values.MODDING_API_RESOLVED_COMMIT;
  const expectedDocs = `https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/${tag}/docs`;
  const expectedSource = `https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/${tag}`;
  assert(values.MODDING_API_SELECTOR === "latest", `${surface} must resolve latest`);
  assert(values.MODDING_API_SELECTOR_KIND === "release", `${surface} must resolve a Release`);
  assert(tag && tag !== "main", `${surface} must resolve an explicit Release tag`);
  assert(/^[0-9a-fA-F]{40}$/.test(commit || ""), `${surface} must resolve a 40-character commit`);
  assert(values.MODDING_API_RESOLVED_REF === tag, `${surface} must route through the Release tag`);
  assert(values.MODDING_API_DOCS_URL === expectedDocs, `${surface} emitted an incorrect docs URL`);
  assert(values.MODDING_API_SOURCE_URL === expectedSource, `${surface} emitted an incorrect source URL`);
  assert(!values.MODDING_API_DOCS_URL.includes("/tree/main"), `${surface} must not route docs through main`);
  assert(!values.MODDING_API_SOURCE_URL.endsWith("/tree/main"), `${surface} must not route source through main`);
}

function run() {
  const bash = support.findBash();
  const powerShell = support.findPowerShell();
  const env = Object.assign({}, process.env, {
    MODDING_API_POWERSHELL: powerShell,
  });
  const bashValues = resolveLive(
    "bash",
    bash,
    path.join(support.scriptDirectory, "resolve_modding_api.sh"),
    ["--selector", "latest"],
    env,
  );
  const powerShellValues = resolveLive(
    "PowerShell",
    powerShell,
    path.join(support.scriptDirectory, "resolve_modding_api.ps1"),
    ["-Selector", "latest"],
    env,
  );
  verifyValues("Bash", bashValues);
  verifyValues("PowerShell", powerShellValues);
  for (const key of [
    "MODDING_API_RESOLVED_REF",
    "MODDING_API_RESOLVED_TAG",
    "MODDING_API_RESOLVED_COMMIT",
    "MODDING_API_DOCS_URL",
    "MODDING_API_SOURCE_URL",
  ]) {
    assert(
      bashValues[key] === powerShellValues[key],
      `live resolver mismatch for ${key}: Bash=${bashValues[key]} PowerShell=${powerShellValues[key]}`,
    );
  }
  process.stdout.write(`MODDING_API_LIVE_TAG=${bashValues.MODDING_API_RESOLVED_TAG}\n`);
  process.stdout.write(`MODDING_API_LIVE_COMMIT=${bashValues.MODDING_API_RESOLVED_COMMIT}\n`);
  process.stdout.write(`MODDING_API_LIVE_DOCS_URL=${bashValues.MODDING_API_DOCS_URL}/development/main.md\n`);
  process.stdout.write("[OK] ModdingAPI live Release smoke\n");
}

try {
  run();
} catch (error) {
  process.stderr.write(`[FAIL] ${error.message}\n`);
  process.exitCode = 1;
}
