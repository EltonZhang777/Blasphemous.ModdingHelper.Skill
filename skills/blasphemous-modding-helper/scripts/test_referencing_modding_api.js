"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const childProcess = require("child_process");

const skillRoot = path.resolve(__dirname, "..");
const topLevelSkill = path.join(skillRoot, "SKILL.md");
const preflightReference = path.join(
  skillRoot,
  "references",
  "config",
  "invocation-preflight.md",
);
const firstTimeSetup = path.join(
  skillRoot,
  "references",
  "config",
  "first-time-setup.md",
);
const referencingSkill = path.join(
  skillRoot,
  "references",
  "sub-skills",
  "referencing-modding-api.md",
);
const sourceAnalyzer = path.join(
  skillRoot,
  "references",
  "sub-skills",
  "source-analyzer.md",
);
const logAnalyzer = path.join(
  skillRoot,
  "references",
  "sub-skills",
  "log-analyzer.md",
);
const moddingTest = path.join(
  skillRoot,
  "references",
  "sub-skills",
  "blasphemous-modding-test.md",
);
const sourceNavigation = path.join(
  skillRoot,
  "references",
  "source_code_navigation",
  "MAIN.md",
);

function fail(message) {
  throw new Error(message);
}

function assertContains(text, needle, label) {
  if (!text.includes(needle)) {
    fail(`${label} must contain: ${needle}`);
  }
}

function assertNotContains(text, needle, label) {
  if (text.includes(needle)) {
    fail(`${label} must not contain: ${needle}`);
  }
}

function readFile(filePath) {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch (error) {
    fail(`could not read ${filePath}: ${error.message}`);
  }
}

function parsePreferences(filePath) {
  const preferences = {};
  for (const line of readFile(filePath).split(/\r?\n/)) {
    const match = line.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (match) {
      preferences[match[1]] = match[2].trim();
    }
  }
  return preferences;
}

function selectRoute(preferences) {
  if (preferences.modding_api_reference_path) {
    const documentationPath = path.join(
      preferences.modding_api_reference_path,
      "docs",
      "development",
      "main.md",
    );
    return {
      kind: "local",
      path: preferences.modding_api_reference_path,
      selector: preferences.modding_api_reference_selector || "latest",
      documentationPath,
    };
  }
  return {
    kind: "remote-release",
    selector: "latest",
  };
}

function writeFixture(filePath, contents) {
  fs.writeFileSync(filePath, contents, "utf8");
}

function resolveReleaseDocumentation(metadataFile) {
  const resolverPath = path.join(__dirname, "resolve_modding_api.py");
  const command =
    process.env.PYTHON3 ||
    process.env.BLASPHEMOUS_PYTHON ||
    (process.platform === "win32" ? "python" : "python3");
  const args = [
    resolverPath,
    "--selector",
    "latest",
    "--metadata-file",
    metadataFile,
  ];
  const result = childProcess.spawnSync(command, args, {
    encoding: "utf8",
    timeout: 10000,
    windowsHide: true,
  });
  if (result.error) {
    fail(`Release resolver could not run: ${result.error.message}`);
  }
  if (result.status !== 0) {
    fail(`Release resolver failed:\n${result.stdout}\n${result.stderr}`);
  }
  const values = {};
  for (const line of `${result.stdout}\n${result.stderr}`.split(/\r?\n/)) {
    const separator = line.indexOf("=");
    if (separator > 0) {
      values[line.slice(0, separator)] = line.slice(separator + 1);
    }
  }
  if (!values.MODDING_API_DOCS_URL) {
    fail("Release resolver did not emit MODDING_API_DOCS_URL");
  }
  return values;
}

function run() {
  const topLevel = readFile(topLevelSkill);
  const preflight = readFile(preflightReference);
  const setup = readFile(firstTimeSetup);
  const referencing = readFile(referencingSkill);
  const source = readFile(sourceAnalyzer);
  const logs = readFile(logAnalyzer);
  const modTest = readFile(moddingTest);
  const sourceNavigationText = readFile(sourceNavigation);

  assertContains(
    topLevel,
    "references/sub-skills/referencing-modding-api.md",
    "top-level Skill",
  );
  assertContains(
    topLevel,
    "references/config/invocation-preflight.md",
    "top-level Skill",
  );
  assertNotContains(topLevel, "## Skill command context", "top-level Skill");
  assertNotContains(
    topLevel,
    "## Preferences gate (see Invocation preflight)",
    "top-level Skill",
  );
  assertNotContains(topLevel, "main branch", "top-level Skill");
  assertNotContains(topLevel, "/tree/main", "top-level Skill");

  for (const heading of [
    "# Invocation preflight",
    "## Command context",
    "## Preferences gate",
    "## First-time setup and recovery",
    "## Completion criteria",
  ]) {
    assertContains(preflight, heading, "Invocation preflight reference");
  }
  for (const contractText of [
    "absolute installed directory",
    "current working directory",
    "Project scope MUST take precedence over user scope",
    "check_preferences.sh",
    "check_preferences.ps1",
    "/blasphemous-modding-test stop SESSION_ID",
  ]) {
    assertContains(
      preflight,
      contractText,
      "Invocation preflight reference",
    );
  }
  assertContains(
    setup,
    "[Invocation preflight](invocation-preflight.md)",
    "First-Time Setup reference",
  );

  for (const [label, document] of [
    ["source route", source],
    ["log route", logs],
    ["mod-test route", modTest],
    ["ModdingAPI route", referencing],
  ]) {
    assertContains(document, "../config/invocation-preflight.md", label);
    assertNotContains(
      document,
      "../../SKILL.md#skill-command-context",
      label,
    );
  }
  assertContains(source, "## Completion criteria", "source route");
  assertContains(logs, "## Completion criteria", "log route");
  assertContains(modTest, "Completion criterion", "mod-test route");

  for (const heading of [
    "## Routing contract",
    "## Stable API topic routing",
    "## Advanced and archived topics",
    "## Game-source separation",
    "## Documentation smoke check",
  ]) {
    assertContains(referencing, heading, "ModdingAPI reference sub-skill");
  }

  for (const page of [
    "docs/development/main.md",
    "docs/development/setup.md",
    "docs/development/mod.md",
    "docs/development/execution.md",
    "docs/development/persistence.md",
    "docs/development/logging.md",
    "docs/development/config.md",
    "docs/development/files.md",
    "docs/development/input.md",
    "docs/development/localization.md",
    "docs/development/console.md",
    "docs/development/items.md",
    "docs/development/levels.md",
    "docs/development/penitence.md",
  ]) {
    assertContains(referencing, `\`${page}\``, "ModdingAPI reference sub-skill");
  }

  assertContains(
    referencing,
    "../source_code_navigation/MAIN.md",
    "ModdingAPI reference sub-skill",
  );
  assertContains(
    sourceNavigationText,
    "# Blasphemous Source Code Navigation Guide",
    "source navigation",
  );

  const fixtureRoot = fs.mkdtempSync(
    path.join(os.tmpdir(), "modding-api-reference-doc-smoke-"),
  );
  try {
    const localPreferences = path.join(fixtureRoot, "local-preferences.md");
    const skippedPreferences = path.join(fixtureRoot, "skipped-preferences.md");
    const localPath = path.join(fixtureRoot, "references", "modding-api");
    const localDocumentationPath = path.join(
      localPath,
      "docs",
      "development",
      "main.md",
    );

    fs.mkdirSync(path.dirname(localDocumentationPath), { recursive: true });
    writeFixture(localDocumentationPath, "# fixture ModdingAPI documentation index\n");
    const releaseMetadata = path.join(fixtureRoot, "latest-release.json");
    writeFixture(
      releaseMetadata,
      JSON.stringify({
        tag_name: "v1.0.0",
        draft: false,
        prerelease: false,
        resolved_ref: "v1.0.0",
        resolved_commit: "0123456789012345678901234567890123456789",
      }),
    );

    writeFixture(
      localPreferences,
      [
        "lightweight_source_code_path: /fixture/source",
        `modding_api_reference_path: ${localPath}`,
        "modding_api_reference_selector: tag:v1.0.0",
      ].join("\n"),
    );
    writeFixture(
      skippedPreferences,
      ["lightweight_source_code_path: /fixture/source"].join("\n"),
    );

    const localRoute = selectRoute(parsePreferences(localPreferences));
    if (
      localRoute.kind !== "local" ||
      localRoute.path !== localPath ||
      localRoute.documentationPath !== localDocumentationPath
    ) {
      fail("configured local preferences must select the local reference route");
    }
    if (!fs.existsSync(localRoute.documentationPath)) {
      fail("local route must point at docs/development/main.md");
    }
    if (localRoute.selector !== "tag:v1.0.0") {
      fail("local preferences must preserve the configured selector");
    }

    const remoteRoute = selectRoute(parsePreferences(skippedPreferences));
    if (
      remoteRoute.kind !== "remote-release" ||
      remoteRoute.selector !== "latest"
    ) {
      fail("skipped local setup must select the latest release-aware remote route");
    }
    const resolvedRelease = resolveReleaseDocumentation(releaseMetadata);
    const remoteDocumentationPath = `${resolvedRelease.MODDING_API_DOCS_URL}/development/main.md`;
    if (
      remoteDocumentationPath !==
        "https://github.com/BrandenEK/Blasphemous.ModdingAPI/tree/v1.0.0/docs/development/main.md" ||
      remoteDocumentationPath.includes("/tree/main/")
    ) {
      fail("remote route must retain an explicit release reference");
    }

    console.log("MODDING_API_DOC_ROUTE=local");
    console.log("MODDING_API_DOC_ROUTE=remote-release");
    console.log(`MODDING_API_DOC_PATH=${remoteDocumentationPath}`);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }

  console.log("[OK] referencing_modding_api documentation smoke");
}

try {
  run();
} catch (error) {
  console.error(`[FAIL] ${error.message}`);
  process.exitCode = 1;
}
