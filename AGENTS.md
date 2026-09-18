# Repository guide for agents

## Scope and safety

This repository packages `blasphemous-modding-helper`, a cross-agent skill for Blasphemous mod development. It contains Skill instructions and references, a cross-platform decompiler helper, and a Node.js installer. The game source tree, modding profile, logs, and generated preferences belong outside this repository.

Keep generated decompiled source, profiles, logs, preferences, and other caller data out of the Skill package and release archive.

## Source of truth

Use the narrowest authoritative file for each change:

- `skills/blasphemous-modding-helper/SKILL.md` owns installed Skill behavior, workflow routing, frontmatter, and the shared preferences gate.
- `skills/blasphemous-modding-helper/references/config/` and `references/sub-skills/` own detailed setup and branch behavior; read only the references selected by the task.
- `skills/blasphemous-modding-helper/scripts/blasphemous_modding_helper/preferences.py` owns preference scope and parsing; `decompiler.py` owns the cross-platform decompilation workflow.
- `skills/blasphemous-modding-helper/references/source-code-navigation/MAIN.md` is the source-navigation authority; read it before searching source details.
- `bin/install.js` owns installer behavior, agent detection, provider IDs, and CLI flags. `install.sh` and `install.ps1` are entry shims and stay behaviorally aligned with it.
- `skills/blasphemous-modding-helper/version.yml` is the version source; `ci/update-version/UpdateVersionNumber.py` synchronizes public version fields.
- `README.md`, `package.json`, `.claude-plugin/plugin.json`, `gemini-extension.json`, and `skills-lock.json` are public package docs or manifests.
- `.github/workflows/build.yml` is the CI and release-packaging contract.

## Working sequence

1. Check `git status --short`, preserve pre-existing user changes, and classify the task as Skill content, reference navigation, installer, version/manifest, or CI/release work.
2. Read the authority for that branch and only the references it selects. Finish this step when every changed fact has one identified owner.
3. Make the narrowest coherent edit. For cross-platform installer behavior, edit `bin/install.js` first and keep the Bash and PowerShell files as entry shims.
4. Run the relevant branch checks, then inspect `git diff --check`, the final diff, and `git status --short`. Work is complete when the intended behavior is covered and affected references and metadata are consistent.

## Conditional references

- **Skill content:** read `skills/blasphemous-modding-helper/SKILL.md` and the branch references it routes to; preserve frontmatter and relative links.
- **Source navigation:** read `skills/blasphemous-modding-helper/references/source-code-navigation/MAIN.md` before searching class details.
- **Installer or CI:** read `bin/install.js --help`, `tests/test_installer.js`, `tests/test_install_wrappers.js`, and `.github/workflows/build.yml`; use dry-run checks for local provider inspection.
- **Decompiler or first-time setup:** read `skills/blasphemous-modding-helper/references/config/first-time-setup.md` before execution. `decompile_source.py` removes the configured Steam DLLs to trigger validation; confirm the exact game path and required Steam, .NET, and `ilspycmd` tools first.
- **Issue or triage work:** read `docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md`.
- **Domain or ADR work:** read `docs/agents/domain.md` and relevant files under `docs/adr/`.
- **Handoff work:** read `docs/agents/handoff.md` before reading `docs/handoff/`; local handoffs are evidence, not current authority.

## Checks

The repository has no npm test/build script; use the branch checks and CI contract:

- Installer or JavaScript: run syntax, installer regression, wrapper, dry-run, and help checks relevant to the change.
- Python Skill workflows: follow `docs/verification/blasphemous-modding-test.md` with a resolved Python 3.9+ interpreter; compile changed entry points when applicable.
- Version or manifest: run the updater in dry-run mode and compare changed manifests with `skills/blasphemous-modding-helper/version.yml`.
- Skill or Markdown references: validate changed relative links and preserve `MAIN.md` routing.
- Any change: run `git diff --check` and finish with `git status --short`.
