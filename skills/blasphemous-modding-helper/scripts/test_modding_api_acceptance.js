"use strict";

const fs = require("fs");
const path = require("path");
const support = require("./modding_api_test_support");

const { repositoryRoot, scriptDirectory } = support;

function fail(message) {
  throw new Error(message);
}

function assert(condition, message) {
  if (!condition) {
    fail(message);
  }
}

function runSuite(label, invoke) {
  process.stdout.write(`[RUN] ${label}\n`);
  const result = invoke();
  if (result.status !== 0) {
    fail(
      `${label} failed with exit code ${result.status}${
        result.timedOut ? " (timed out)" : ""
      }:\n${result.output}`,
    );
  }
  process.stdout.write(`[OK] ${label}\n`);
}

function parseArguments(argv) {
  const options = { requireClean: false };
  for (const argument of argv) {
    if (argument === "--require-clean") {
      options.requireClean = true;
    } else if (argument === "--help" || argument === "-h") {
      process.stdout.write(
        "Usage: test_modding_api_acceptance.js [--require-clean]\n" +
          "  --require-clean  Fail unless the repository worktree is clean.\n",
      );
      return null;
    } else {
      fail(`unknown option: ${argument}`);
    }
  }
  return options;
}

function runResolverParity(bash, powerShell, env) {
  const fixtureRoot = support.createFixtureDirectory("modding-api-parity-");
  try {
    const metadataFile = path.join(fixtureRoot, "latest.json");
    fs.writeFileSync(
      metadataFile,
      JSON.stringify({
        tag_name: "v1.0.0",
        draft: false,
        prerelease: false,
        resolved_ref: "v1.0.0",
        resolved_commit: "0123456789012345678901234567890123456789",
      }),
      "utf8",
    );
    const resolverShell = path.join(scriptDirectory, "resolve_modding_api.sh");
    const resolverPowerShell = path.join(scriptDirectory, "resolve_modding_api.ps1");
    const bashResult = support.invokeBash(
      bash,
      resolverShell,
      ["--selector", "latest", "--metadata-file", metadataFile],
      env,
    );
    const powerShellResult = support.invokePowerShell(
      powerShell,
      resolverPowerShell,
      ["-Selector", "latest", "-MetadataFile", metadataFile],
      env,
    );
    assert(
      bashResult.status === 0 && powerShellResult.status === 0,
      `resolver parity fixture failed:\nBash:\n${bashResult.output}\nPowerShell:\n${powerShellResult.output}`,
    );
    const bashValues = support.parseKeyValues(bashResult.output);
    const powerShellValues = support.parseKeyValues(powerShellResult.output);
    for (const key of [
      "MODDING_API_REPOSITORY",
      "MODDING_API_SELECTOR",
      "MODDING_API_SELECTOR_KIND",
      "MODDING_API_RESOLVED_REF",
      "MODDING_API_RESOLVED_TAG",
      "MODDING_API_RESOLVED_COMMIT",
      "MODDING_API_DOCS_URL",
      "MODDING_API_SOURCE_URL",
    ]) {
      assert(
        bashValues[key] === powerShellValues[key],
        `resolver output mismatch for ${key}: Bash=${bashValues[key]} PowerShell=${powerShellValues[key]}`,
      );
    }

    const invalidBash = support.invokeBash(
      bash,
      resolverShell,
      ["--selector", "main"],
      env,
    );
    const invalidPowerShell = support.invokePowerShell(
      powerShell,
      resolverPowerShell,
      ["-Selector", "main"],
      env,
    );
    assert(
      invalidBash.status === 2 && invalidPowerShell.status === 2,
      `invalid selector exit-code mismatch: Bash=${invalidBash.status} PowerShell=${invalidPowerShell.status}`,
    );
    for (const output of [invalidBash.output, invalidPowerShell.output]) {
      assert(output.includes("[ERROR REPORT]"), "invalid selector must print an error report");
      assert(output.includes("next_step:"), "invalid selector report must include next_step");
    }
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

function runGit(workingDirectory, args) {
  const result = support.runCommand("git", ["-C", workingDirectory].concat(args));
  assert(result.status === 0, `Git fixture command failed: ${result.output}`);
  return result.output.trim();
}

function normalizedValue(values, key, replacements) {
  let value = values[key];
  assert(value !== undefined, `missing output field: ${key}`);
  for (const [source, replacement] of replacements) {
    value = value.split(source).join(replacement);
  }
  return value;
}

function compareSurfaceValues(label, bashOutput, powerShellOutput, keys, replacements) {
  const bashValues = support.parseKeyValues(bashOutput);
  const powerShellValues = support.parseKeyValues(powerShellOutput);
  for (const key of keys) {
    const bashValue = normalizedValue(bashValues, key, replacements);
    const powerShellValue = normalizedValue(powerShellValues, key, replacements);
    assert(
      bashValue === powerShellValue,
      `${label} output mismatch for ${key}: Bash=${bashValue} PowerShell=${powerShellValue}`,
    );
  }
}

function parseErrorReport(output) {
  const report = {};
  for (const line of output.split(/\r?\n/)) {
    const match = line.match(/^([a-z_]+):\s*(.*)$/);
    if (match) {
      report[match[1]] = match[2];
    }
  }
  return report;
}

function compareErrorReports(label, bashOutput, powerShellOutput, replacements) {
  const bashReport = parseErrorReport(bashOutput);
  const powerShellReport = parseErrorReport(powerShellOutput);
  for (const key of [
    "operation",
    "target_path",
    "selector",
    "current_head",
    "worktree_state",
    "network_state",
    "cause",
    "next_step",
  ]) {
    const bashValue = normalizedValue(bashReport, key, replacements);
    const powerShellValue = normalizedValue(powerShellReport, key, replacements);
    assert(
      bashValue === powerShellValue,
      `${label} error-report mismatch for ${key}: Bash=${bashValue} PowerShell=${powerShellValue}`,
    );
  }
}

function checkoutState(target) {
  const lockPath = `${target}.lock`;
  return {
    head: runGit(target, ["rev-parse", "HEAD"]),
    branch: runGit(target, ["rev-parse", "--abbrev-ref", "HEAD"]),
    shallow: runGit(target, ["rev-parse", "--is-shallow-repository"]),
    origin: runGit(target, ["config", "--get", "remote.origin.url"]),
    status: runGit(target, ["status", "--porcelain"]),
    lock: fs
      .readFileSync(lockPath, "utf8")
      .replace(/^checked_at:.*$/m, "checked_at: <TIME>"),
  };
}

function compareCheckoutStates(label, bashState, powerShellState) {
  for (const key of ["head", "branch", "shallow", "origin", "status", "lock"]) {
    assert(
      bashState[key] === powerShellState[key],
      `${label} state mismatch for ${key}: Bash=${bashState[key]} PowerShell=${powerShellState[key]}`,
    );
  }
}

function runCloneLifecycleParity(bash, powerShell, env) {
  const fixtureRoot = support.createFixtureDirectory("modding-api-surface-parity-");
  try {
    const remote = path.join(fixtureRoot, "modding-api.git");
    const seed = path.join(fixtureRoot, "seed");
    const metadataFile = path.join(fixtureRoot, "latest.json");
    const bashTarget = path.join(fixtureRoot, "bash-reference");
    const powerShellTarget = path.join(fixtureRoot, "powershell-reference");
    runGit(fixtureRoot, ["init", "--bare", remote]);
    runGit(fixtureRoot, ["init", seed]);
    runGit(seed, ["config", "user.email", "test@example.invalid"]);
    runGit(seed, ["config", "user.name", "ModdingAPI parity test"]);
    fs.writeFileSync(path.join(seed, "README.md"), "stable\n", "utf8");
    runGit(seed, ["add", "README.md"]);
    runGit(seed, ["commit", "-m", "initial stable reference"]);
    runGit(seed, ["branch", "-M", "main"]);
    runGit(seed, ["tag", "-a", "v1.0.0", "-m", "stable release"]);
    runGit(seed, ["remote", "add", "origin", remote]);
    runGit(seed, ["push", "--set-upstream", "origin", "main", "--tags"]);
    const releaseCommit = runGit(seed, ["rev-parse", "refs/tags/v1.0.0^{commit}"]);
    fs.writeFileSync(
      metadataFile,
      JSON.stringify({
        tag_name: "v1.0.0",
        draft: false,
        prerelease: false,
        resolved_ref: "v1.0.0",
        resolved_commit: releaseCommit,
      }),
      "utf8",
    );

    const fixtureEnv = Object.assign({}, env, {
      MODDING_API_TEST_MODE: "1",
      MODDING_API_TEST_REPOSITORY: remote,
    });
    const cloneShell = path.join(scriptDirectory, "clone_modding_api.sh");
    const clonePowerShell = path.join(scriptDirectory, "clone_modding_api.ps1");
    const managerShell = path.join(scriptDirectory, "manage_modding_api.sh");
    const managerPowerShell = path.join(scriptDirectory, "manage_modding_api.ps1");
    const cloneBash = support.invokeBash(
      bash,
      cloneShell,
      ["--target-path", bashTarget, "--selector", "latest", "--metadata-file", metadataFile],
      fixtureEnv,
    );
    const clonePowerShellResult = support.invokePowerShell(
      powerShell,
      clonePowerShell,
      ["-TargetPath", powerShellTarget, "-Selector", "latest", "-MetadataFile", metadataFile],
      fixtureEnv,
    );
    assert(cloneBash.status === 0 && clonePowerShellResult.status === 0, "clone surface parity fixture failed");
    compareSurfaceValues(
      "clone",
      cloneBash.output,
      clonePowerShellResult.output,
      [
        "MODDING_API_OPERATION",
        "MODDING_API_REFERENCE_PATH",
        "MODDING_API_SELECTOR",
        "MODDING_API_SELECTOR_KIND",
        "MODDING_API_RESOLVED_REF",
        "MODDING_API_RESOLVED_TAG",
        "MODDING_API_RESOLVED_COMMIT",
        "MODDING_API_SHALLOW",
        "MODDING_API_LOCK_PATH",
      ],
      [
        [bashTarget, "<TARGET>"],
        [powerShellTarget, "<TARGET>"],
        [`${bashTarget}.lock`, "<TARGET>.lock"],
        [`${powerShellTarget}.lock`, "<TARGET>.lock"],
      ],
    );
    compareCheckoutStates(
      "clone",
      checkoutState(bashTarget),
      checkoutState(powerShellTarget),
    );

    const checkBash = support.invokeBash(
      bash,
      managerShell,
      ["--operation", "check", "--target-path", bashTarget, "--selector", "latest", "--metadata-file", metadataFile, "--offline"],
      fixtureEnv,
    );
    const checkPowerShell = support.invokePowerShell(
      powerShell,
      managerPowerShell,
      ["-Operation", "check", "-TargetPath", powerShellTarget, "-Selector", "latest", "-MetadataFile", metadataFile, "-Offline"],
      fixtureEnv,
    );
    assert(checkBash.status === 0 && checkPowerShell.status === 0, "offline check surface parity fixture failed");
    compareSurfaceValues(
      "offline check",
      checkBash.output,
      checkPowerShell.output,
      [
        "MODDING_API_OPERATION",
        "MODDING_API_REFERENCE_PATH",
        "MODDING_API_SELECTOR",
        "MODDING_API_SELECTOR_KIND",
        "MODDING_API_RESOLVED_REF",
        "MODDING_API_RESOLVED_TAG",
        "MODDING_API_RESOLVED_COMMIT",
        "MODDING_API_NETWORK",
        "MODDING_API_DRY_RUN",
        "MODDING_API_LOCK_MATCH",
        "MODDING_API_CHECKOUT_CHANGED",
        "MODDING_API_LOCK_UPDATED",
      ],
      [
        [bashTarget, "<TARGET>"],
        [powerShellTarget, "<TARGET>"],
      ],
    );
    compareCheckoutStates(
      "offline check",
      checkoutState(bashTarget),
      checkoutState(powerShellTarget),
    );

    fs.writeFileSync(path.join(bashTarget, "README.md"), "dirty\n", "utf8");
    fs.writeFileSync(path.join(powerShellTarget, "README.md"), "dirty\n", "utf8");
    const updateBash = support.invokeBash(
      bash,
      managerShell,
      ["--operation", "update", "--target-path", bashTarget, "--selector", "latest", "--metadata-file", metadataFile],
      fixtureEnv,
    );
    const updatePowerShell = support.invokePowerShell(
      powerShell,
      managerPowerShell,
      ["-Operation", "update", "-TargetPath", powerShellTarget, "-Selector", "latest", "-MetadataFile", metadataFile],
      fixtureEnv,
    );
    assert(updateBash.status === 1 && updatePowerShell.status === 1, "dirty update exit-code parity failed");
    compareErrorReports("dirty update", updateBash.output, updatePowerShell.output, [
      [bashTarget, "<TARGET>"],
      [powerShellTarget, "<TARGET>"],
    ]);
    compareCheckoutStates(
      "dirty update",
      checkoutState(bashTarget),
      checkoutState(powerShellTarget),
    );
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

function runInstallerSmoke(env) {
  const installer = path.join(repositoryRoot, "bin", "install.js");
  for (const agent of ["trae-cn", "claude-code"]) {
    const result = support.runCommand(
      process.execPath,
      [installer, "--dry-run", "--only", agent],
      { env },
    );
    if (result.status !== 0) {
      fail(`installer dry-run for ${agent} failed:\n${result.output}`);
    }
  }
  const helpResult = support.runCommand(process.execPath, [installer, "--help"], { env });
  if (helpResult.status !== 0) {
    fail(`installer help failed:\n${helpResult.output}`);
  }
}

function gitMarkdownFiles(args) {
  const result = support.runCommand("git", args);
  assert(result.status === 0, `Git Markdown file discovery failed:\n${result.output}`);
  return result.output
    .split("\0")
    .filter((relativePath) => relativePath.length > 0)
    .filter((relativePath) => relativePath.toLowerCase().endsWith(".md"))
    .map((relativePath) => path.resolve(repositoryRoot, relativePath))
    .filter((file) => fs.existsSync(file) && fs.statSync(file).isFile());
}

function trackedMarkdownFiles() {
  return gitMarkdownFiles([
    "ls-files",
    "--cached",
    "--others",
    "--exclude-standard",
    "-z",
    "--",
    "*.md",
  ]);
}

function ignoredMarkdownFiles() {
  return gitMarkdownFiles([
    "ls-files",
    "--others",
    "--ignored",
    "--exclude-standard",
    "-z",
    "--",
    "*.md",
  ]);
}

function displayPath(file) {
  return path.relative(repositoryRoot, file).replace(/\\/g, "/");
}

function markdownTarget(rawTarget) {
  let target = rawTarget.trim();
  if (target.startsWith("<") && target.includes(">")) {
    target = target.slice(1, target.indexOf(">"));
  } else {
    target = target.split(/\s+/)[0];
  }
  return target.split("#", 1)[0];
}

function findMissingMarkdownLinks(files) {
  const missing = [];
  for (const file of files) {
    const contents = fs.readFileSync(file, "utf8");
    const linkPattern = /!?\[[^\]]*\]\(([^)\r\n]+)\)/g;
    let match;
    while ((match = linkPattern.exec(contents)) !== null) {
      const target = markdownTarget(match[1]);
      if (
        !target ||
        target.startsWith("#") ||
        /^[A-Za-z][A-Za-z0-9+.-]*:/.test(target) ||
        target.startsWith("//")
      ) {
        continue;
      }
      const resolved = path.resolve(path.dirname(file), decodeURIComponent(target));
      if (!fs.existsSync(resolved)) {
        missing.push(`${displayPath(file)} -> ${target}`);
      }
    }
  }
  return missing;
}

function checkMarkdownLinks() {
  const repositoryFiles = trackedMarkdownFiles();
  const ignoredFiles = ignoredMarkdownFiles();
  const missing = findMissingMarkdownLinks(repositoryFiles);
  const ignoredMissing = findMissingMarkdownLinks(ignoredFiles);

  if (ignoredFiles.length > 0) {
    process.stdout.write(
      `[INFO] ignored Markdown files excluded from repository link validation (${ignoredFiles.length}):\n` +
        `${ignoredFiles.map(displayPath).join("\n")}\n`,
    );
  }
  if (ignoredMissing.length > 0) {
    process.stdout.write(
      `[WARN] ignored local Markdown link findings (not release failures):\n` +
        `${ignoredMissing.join("\n")}\n`,
    );
  }
  assert(missing.length === 0, `missing repository Markdown links:\n${missing.join("\n")}`);
}

function checkGitDiff() {
  const result = support.runCommand("git", ["diff", "--check"]);
  assert(result.status === 0, `git diff --check failed:\n${result.output}`);
}

function checkCleanWorktree() {
  const result = support.runCommand("git", ["status", "--porcelain"]);
  assert(result.status === 0, `git status failed:\n${result.output}`);
  assert(!result.output.trim(), `worktree is not clean:\n${result.output}`);
}

function run() {
  const options = parseArguments(process.argv.slice(2));
  if (options === null) {
    return;
  }
  const bash = support.findBash();
  const powerShell = support.findPowerShell();
  const env = Object.assign({}, process.env, {
    MODDING_API_POWERSHELL: powerShell,
  });
  runResolverParity(bash, powerShell, env);
  runSuite("clone/lifecycle surface parity", () => {
    runCloneLifecycleParity(bash, powerShell, env);
    return { status: 0, output: "" };
  });

  const suites = [
    ["resolver Bash", "bash", "test_resolve_modding_api.sh"],
    ["resolver PowerShell", "powershell", "test_resolve_modding_api.ps1"],
    ["clone Bash", "bash", "test_clone_modding_api.sh"],
    ["clone PowerShell", "powershell", "test_clone_modding_api.ps1"],
    ["lifecycle Bash", "bash", "test_manage_modding_api.sh"],
    ["lifecycle PowerShell", "powershell", "test_manage_modding_api.ps1"],
    ["documentation Bash", "bash", "test_referencing_modding_api.sh"],
    ["documentation PowerShell", "powershell", "test_referencing_modding_api.ps1"],
  ];
  for (const [label, surface, fileName] of suites) {
    const script = path.join(scriptDirectory, fileName);
    runSuite(label, () =>
      surface === "bash"
        ? support.invokeBash(bash, script, [], env)
        : support.invokePowerShell(powerShell, script, [], env),
    );
  }

  runSuite("installer dry-run smoke", () => {
    runInstallerSmoke(env);
    return { status: 0, output: "" };
  });
  runSuite("Markdown link check", () => {
    checkMarkdownLinks();
    return { status: 0, output: "" };
  });
  runSuite("git diff --check", () => {
    checkGitDiff();
    return { status: 0, output: "" };
  });
  if (options.requireClean) {
    runSuite("clean worktree check", () => {
      checkCleanWorktree();
      return { status: 0, output: "" };
    });
  }
  process.stdout.write("[OK] ModdingAPI cross-platform acceptance gate\n");
}

try {
  run();
} catch (error) {
  process.stderr.write(`[FAIL] ${error.message}\n`);
  process.exitCode = 1;
}
