# Repository guide for agents

## Repository role

This repository packages `blasphemous-modding-helper`, a cross-agent skill for Blasphemous mod development. It contains skill instructions and references, a cross-platform decompiler helper, and a Node.js installer. The game source tree, modding profile, logs, and generated preferences belong outside this repository.

## Source of truth

Use the narrowest authoritative file for each change:

- `skills/blasphemous-modding-helper/SKILL.md` defines the installed skill's behavior, workflow, frontmatter, and required preferences gate.
- `skills/blasphemous-modding-helper/references/config/` defines preference setup and schema; `references/sub-skills/` defines source and log analysis branches.
- `skills/blasphemous-modding-helper/scripts/blasphemous_modding_helper/preferences.py` owns Python preference scope and parsing; `decompiler.py` owns the cross-platform decompilation workflow.
- `skills/blasphemous-modding-helper/references/source_code_navigation/MAIN.md` is the navigation index. Route to one topical document (`core`, `player`, `enemy`, `bosses`, `ui`, `items`, `level`, `tools`, or `localization`) before searching its details.
- `bin/install.js` owns installer behavior, agent detection, provider IDs, and CLI flags. `install.sh` and `install.ps1` are thin entry shims and should remain behaviorally aligned with it.
- `ci/version.yml` is the version source. `ci/UpdateVersionNumber.py` synchronizes the version fields in `package.json`, `.claude-plugin/plugin.json`, `gemini-extension.json`, and `skills-lock.json`.
- `README.md`, `.claude-plugin/plugin.json`, `gemini-extension.json`, and `skills-lock.json` are public distribution metadata; update them when user-visible installation or package metadata changes.
- `.github/workflows/build.yml` is the CI and release-packaging contract. The release archive contains the skill directory plus the two installer shims.

## Working sequence

1. Check `git status --short` and preserve pre-existing user changes. Classify the task as skill content, reference navigation, installer, version metadata, or CI/release work.
2. Read the authoritative file and every linked reference that the change can affect. Keep relative links valid and keep each fact in one authoritative location; use a short pointer instead of duplicating a navigation list.
3. Make the smallest coherent change. For cross-platform behavior, update the shared Node implementation first and keep the Bash and PowerShell entry points as wrappers.
4. Verify the changed branch, then inspect `git diff --check`, the final diff, and `git status --short`. A task is complete when the intended behavior is covered, affected references and metadata are consistent, and the relevant checks pass.

## Skill behavior to preserve

- The installed skill is a Blasphemous modding assistant, not a replacement for the user's game source or mod project. Keep the frontmatter `name`, `description`, and relative reference links valid.
- Preferences are a blocking first step for operational Skill branches. The read-only localization lookup branch is an explicit exception: it reads only the bundled localization indexes and does not require preferences, a Modding profile, source code, or logs. The check scripts look for project scope at `.skills/blasphemous-modding-helper/preferences.md` and user scope under `$HOME/.skills/blasphemous-modding-helper/preferences.md`. When no file exists, first-time setup must finish before source analysis, log analysis, or modding work.
- Source analysis starts with the lightweight source path, uses the full source only when needed, and routes through `references/source_code_navigation/MAIN.md`. Navigation paths are relative to `Assembly-CSharp/`.
- Log analysis checks the BepInEx log first and then the Unity log when needed. The modding profile path comes from `preferences.md`.
- Mod code targets C# on Unity `2017.4.40f1` under the Blasphemous ModdingAPI conventions. Keep links to the ModdingAPI documentation and source when changing coding guidance.

## Installer and script safety

- The installer requires Node.js 18 or newer and has no runtime npm dependencies. Use `node bin/install.js --help` as the CLI reference.
- Local installer checks should use dry-run mode, for example:

  ```text
  node bin/install.js --dry-run --only trae-cn
  node bin/install.js --dry-run --only claude-code
  node bin/install.js --help
  ```

  Dry-run keeps checks from writing to the user's home directory or invoking an installation. `--uninstall` and real installation runs are user-authorized operations.
- `decompile_source.py` is a setup operation with side effects: it removes `Assembly-CSharp.dll` and `Assembly-CSharp-firstpass.dll` from the configured Steam installation to trigger file validation, then decompiles them. Resolve and confirm paths before invoking it; it checks actual access, does not auto-elevate, and requires Steam, a .NET SDK, and `ilspycmd`.
- Failure propagation regression: run `node tests/test_installer.js`. This test intentionally executes a temporary fake provider without `--dry-run` to exercise command failure handling; it does not access real agent directories or install anything.
- Keep the Windows and Unix decompiler flows conceptually equivalent: validate the game, restore the DLLs through Steam, decompile both assemblies, create `BlasphemousSourceCode.sln` when projects are found, and report the output path for `preferences.md`.

## Verification matrix

Run only the checks relevant to the changed area:

- Installer or JavaScript: `node --check bin/install.js`, both installer dry-runs above, and `node bin/install.js --help`.
- Python Skill workflows: use a resolved Python 3.9+ interpreter for `tests/run_blasphemous_modding_test.py` or `skills/blasphemous-modding-helper/scripts/test_modding_api_acceptance.py`; use `-m py_compile` on changed entry points.
- Version or manifest: run `python ci/UpdateVersionNumber.py --dry-run`, parse every changed JSON manifest, and confirm all version fields agree with `ci/version.yml`. Use the available Python 3 interpreter on the host.
- Skill or Markdown references: inspect every changed relative link and confirm paths/case match the repository. For source navigation, check `MAIN.md` routing and keep class-to-document mappings in one topical file.
- Any change: `git diff --check` and a final `git status --short`.

There is no package test suite or build script; the Python acceptance surface, CI installer smoke tests, and release packaging are the repository's executable checks.

## Local material

Ignore local planning material labelled in `.gitignore`. Generated decompiled source, modding profiles, logs, and preference files are user data; keep them out of the skill package and release archive.

## Agent skills

### Issue tracker

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

This repo uses a single-context domain glossary at root and ADRs under `docs/adr/`. See `docs/agents/domain.md`.
