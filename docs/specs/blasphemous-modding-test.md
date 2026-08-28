# Spec: Blasphemous mod test workflow

## Problem Statement

From the mod developer's perspective, the skill can help write and inspect a Blasphemous mod but does not define a repeatable way to build a mod, deploy the build package to a safe modding profile, start the modded game, inspect startup evidence, and return the profile to a known state.

The missing workflow creates several risks. A developer may copy the wrong build output, place resource files in the wrong Modding subdirectory, launch the original Steam installation instead of a mirror profile, overwrite another mod's files, lose a pre-test version during cleanup, or mistake a running game process for a successfully loaded mod. The game has no available MCP for gameplay control, so the workflow must also state clearly which checks remain manual and player-operated.

## Solution

Provide a cross-platform `argparse` CLI and a dedicated mod-testing sub-skill. The CLI owns deterministic build selection, package validation, safe deployment, profile-local game launch, process tracking, log inspection, session rollback, and stable exit codes. The sub-skill owns the user-facing workflow, preferences integration, manual gameplay boundary, acceptance criteria, and troubleshooting guidance.

The default workflow builds the selected project in Debug configuration, resolves the package directory named by the project, validates every package-relative file, deploys it to the selected modding profile, launches the profile-local game, and reports separate `launched`, `ready`, and `mod_loaded` states. Release configuration is explicit. A release archive is an explicit fallback only; it is never selected by timestamp or silently substituted for a build package.

The workflow stores only temporary session state for process ownership, deployment manifests, file hashes, and backups. It does not create persistent log copies. The player performs game actions and reports the observed behavior; the agent combines that description with the BepInEx and Unity logs.

## User Stories

1. As a Blasphemous mod developer, I want one named testing sub-skill, so that I can start the complete local test workflow consistently.
2. As an AI agent, I want a documented CLI contract, so that I can use the same operations on every supported platform.
3. As a Windows user, I want the workflow to run from PowerShell, so that I can test a mod without installing a second automation stack.
4. As a Linux or macOS user, I want the workflow to run from Bash, so that I can use the native game profile and launcher behavior.
5. As a user on an unsupported shell or compatibility layer, I want an explicit unsupported-environment result, so that the workflow does not pretend to provide safe automation.
6. As a mod developer, I want the CLI to use the only project file in the current directory by default, so that common projects need no repeated path input.
7. As a mod developer, I want multiple project files to require an explicit project selection, so that the CLI never builds an arbitrary project.
8. As a mod developer, I want to override the project selection explicitly, so that monorepos and non-standard working directories remain usable.
9. As a mod developer, I want Debug to be the default build configuration, so that test statements and test code blocks remain available during development.
10. As a mod developer, I want Release to require an explicit request, so that a release build is never selected accidentally during debugging.
11. As a mod developer, I want a failed build to stop deployment and launch, so that an old or partial package is not mistaken for the new build.
12. As a mod developer, I want a successful build to resolve its package by the project's declared target name, so that package selection is deterministic.
13. As a mod developer, I want a missing or empty package to fail before deployment, so that the profile is not changed by an invalid build.
14. As a mod developer, I want to use an existing package without rebuilding it, so that I can repeat deployment-only or launch-only checks.
15. As a mod developer, I want to select an exact package directory explicitly, so that I can test a known artifact.
16. As a mod developer, I want to select a release archive explicitly, so that I have a recovery path when the package directory is seriously abnormal.
17. As a mod developer, I want archives to be extracted into temporary state first, so that an archive never writes directly into the game profile.
18. As a mod developer, I want the CLI to reject unsafe archive entries, so that absolute paths, parent traversal, and link escapes cannot write outside the Modding root.
19. As a mod developer, I want every safe file under the package root to be deployed, so that DLLs, data, localization, images, JSON, and other mod resources remain available.
20. As a mod developer, I want package-relative paths preserved, so that a data dependency remains in the data directory and a plugin remains in the plugin directory.
21. As a mod developer, I want the CLI to reject ambiguous package layouts, so that a malformed package is not partially deployed.
22. As a mod developer, I want the modding profile to come from the existing preferences model, so that source paths and runtime paths remain separate concerns.
23. As a mod developer, I want explicit profile arguments to override preferences for one invocation, so that temporary profile testing does not rewrite saved configuration.
24. As a mod developer, I want a profile preflight to verify the profile, game launcher, Modding root, and BepInEx installation, so that a vanilla or unrelated directory is not modified.
25. As a mod developer, I want the CLI to create only missing Modding subdirectories, so that a valid profile can receive a package without allowing the CLI to invent a profile root.
26. As a mod developer, I want non-Steam mirror profiles supported, so that testing does not depend on the original Steam installation.
27. As a mod developer, I want Steam URI launch excluded from the default workflow, so that the selected profile remains the source of truth.
28. As a mod developer, I want a known platform launcher selected by default, so that the working directory and executable match the profile.
29. As a mod developer, I want an explicit launcher override, so that a special profile can use a custom launcher when the path is clearly provided.
30. As a security-conscious user, I want arbitrary shell command strings rejected, so that a launcher override cannot become an unbounded command execution surface.
31. As a mod developer, I want the game process started in the profile working directory, so that relative game and BepInEx paths resolve correctly.
32. As a mod developer, I want the CLI to refuse a conflicting already-running game instance, so that it never attaches to or stops an unrelated process.
33. As a mod developer, I want each launch to produce a session identifier, so that later stop, log, and cleanup operations address the correct test.
34. As a mod developer, I want the CLI to track the process it started, so that stop never kills a process selected only by name.
35. As a mod developer, I want stop to be safe when the process already exited, so that recovery commands are idempotent.
36. As a mod developer, I want a force option limited to the tracked process tree, so that an unresponsive game can be stopped without broad process termination.
37. As a mod developer, I want to run a second test before cleaning the first, so that iteration is not blocked by cleanup timing.
38. As a mod developer, I want an archived session warning when a new run supersedes an older session, so that the rollback history is visible to both agent and user.
39. As a mod developer, I want archived sessions retained in newest-first order, so that repeated rollback restores the immediately previous profile state.
40. As a mod developer, I want an older session cleanup rejected while a newer session is active, so that rollback cannot overwrite newer deployment files.
41. As a mod developer, I want a read-only status view of sessions, so that I can discover active and archived identifiers before cleanup.
42. As a mod developer, I want safe clean to restore overwritten files, so that the profile returns toward its pre-test state.
43. As a mod developer, I want safe clean to leave new deployment files by default, so that the CLI does not remove files the user may be inspecting.
44. As a mod developer, I want removal of new deployment files to require explicit user approval, so that cleanup cannot silently destroy test resources.
45. As a mod developer, I want a file changed during testing protected from silent restoration or deletion, so that the user's new work is not lost.
46. As a mod developer, I want deployment state and file backups kept in temporary storage, so that rollback works across separate CLI invocations without adding files to the mod repository.
47. As a mod developer, I want logs excluded from session persistence, so that the workflow reads existing system logs without creating sensitive or bulky copies.
48. As an AI agent, I want a launched state, so that I can distinguish process creation from successful mod initialization.
49. As an AI agent, I want a ready state tied to current BepInEx startup evidence, so that an old process or stale assumption cannot represent the current launch.
50. As an AI agent, I want a mod-loaded state tied to the target mod's load evidence, so that BepInEx startup alone is not reported as target-mod success.
51. As a mod developer, I want startup timeout to leave the process and session available for diagnosis, so that a timeout does not erase useful failure evidence.
52. As an AI agent, I want the BepInEx log read from the selected profile, so that startup errors are analyzed from the same profile that was launched.
53. As an AI agent, I want the Unity log directory configured by preferences, so that platform-specific locations do not require hardcoded assumptions.
54. As a user, I want a missing Unity log to produce a clear question, so that I can provide the correct directory instead of watching an opaque failure.
55. As a user, I want a supplied Unity log directory saved in the active preferences scope, so that later test runs can reuse it.
56. As an AI agent, I want bounded log output by default, so that normal analysis remains readable.
57. As an AI agent, I want an explicit full-log option, so that deeper diagnosis remains possible without changing the default output.
58. As a mod developer, I want the agent to collect my natural-language gameplay description, so that manual behavior remains part of the test evidence.
59. As a mod developer, I want the workflow to state that game actions are manual, so that no one mistakes startup evidence for gameplay verification.
60. As a maintainer, I want dry-run behavior, so that artifact and profile checks can be inspected without copying files or launching a game.
61. As a maintainer, I want stable exit-code categories, so that agents can route build, artifact, deployment, launch, log, and cleanup failures correctly.
62. As a maintainer, I want fixture tests for package mapping and rollback, so that destructive behavior can be tested without a real game installation.
63. As a maintainer, I want fixture tests for repeated sessions, so that archived rollback behavior remains safe.
64. As a maintainer, I want fixture tests for unsafe package paths, so that archive and directory validation protects the deployment boundary.
65. As a maintainer, I want manual smoke coverage for a real modding profile, so that process launch and BepInEx readiness are not assumed from fixtures.
66. As a maintainer, I want one authoritative sub-skill document, so that CLI behavior, manual boundaries, and troubleshooting do not drift across duplicated pages.
67. As a maintainer, I want the top-level skill to link the testing sub-skill once, so that detailed guidance is loaded progressively.
68. As a user, I want common errors mapped to recovery steps, so that missing profile, build, package, launcher, log, and rollback problems are actionable.

## Implementation Decisions

- The feature is a Python standard-library CLI using `argparse`, with equivalent behavior on Windows PowerShell and native Linux/macOS Bash.
- The CLI exposes `run`, `stop`, `clean`, `logs`, and read-only `status` operations. It uses project preferences before user preferences, and explicit arguments override saved values.
- The default build configuration is Debug. Release is explicit. A project is inferred only when the current directory contains exactly one project file; ambiguity requires explicit selection.
- A normal run builds the project, resolves the declared target name, and uses the corresponding package directory in the build output container. An explicit artifact selects deploy-only behavior. A dry run does not deploy or launch.
- A package root is the deployment boundary. All safe relative files below it are copied to the matching relative location under the Modding root. File type is not used to discard resources.
- Release archives are a recovery input only when explicitly selected. They are extracted to temporary state and validated before deployment. Directory and archive selection never uses timestamps or silent fallback.
- The profile is validated as a modding profile before deployment. The game launcher, Modding root, and BepInEx installation are hard prerequisites; missing log files are handled by the log recovery flow.
- Launch uses a profile-local known launcher by default and does not use Steam URI resolution. An explicit launcher path is allowed with a warning, but arbitrary shell command strings are not accepted.
- Deployment uses a transaction-like manifest with target hashes and backups. Session state is temporary and contains no copied log content.
- Repeated runs are allowed. Session state forms a newest-first stack. A newer session must be cleaned before an older session can be cleaned. An archived session is retained until its rollback position is safely removed.
- Safe clean restores overwritten files and preserves new deployment files by default. Removing new files and handling files changed during testing require explicit user approval.
- Stop and clean refuse to operate while the tracked game process is running. Stop is idempotent when the tracked process has already exited.
- The evidence state is split into launched, ready, and mod loaded. Ready uses current BepInEx chainloader completion evidence; mod loaded uses target-mod loading evidence. A timeout preserves the process and session for diagnosis.
- The BepInEx log is profile-relative. The Unity log directory is an optional preferences field. When it is missing, the agent asks the user and writes the answer to the active preferences scope; the CLI itself does not conduct the conversational update.
- Logs are read from their existing system locations. Default output is bounded; full output is explicit. No persistent log report is created.
- User-facing CLI output is UTF-8, and subprocess text is decoded explicitly with safe replacement for undecodable bytes. Unicode and space-containing path values remain intact across the lifecycle; replacement applies only to undecodable subprocess or log text.
- The CLI returns stable categories: success, usage/configuration, profile/preference, build, package, deployment/rollback, launch, log/readiness, and stop/clean.
- The sub-skill is the authority for the user-facing flow, manual gameplay boundary, acceptance criteria, and troubleshooting. The top-level skill links to it once.
- This specification defines behavior only. It does not implement the CLI, modify a game profile, build a mod, or automate gameplay.

## Testing Decisions

- Tests verify external behavior: command results, file mapping, preserved bytes, session state transitions, process ownership, log evidence, output, and exit codes. They do not assert private helper structure.
- The highest useful seam is the CLI orchestration contract, with filesystem, process, and log behavior represented by temporary fixtures and controlled doubles where a real game is not available.
- Fixture tests cover Debug-build selection, explicit Release selection, project ambiguity, package-directory selection, explicit archive selection, safe relative paths, rejected traversal, missing profile requirements, and dry-run non-mutation.
- Fixture tests cover overwriting an existing file, restoring the previous file, retaining new files, protecting files modified during testing, explicit new-file removal, and rollback failure reporting.
- Fixture tests cover repeated sessions, archived-session warnings, newest-first cleanup, status output, idempotent stop, and refusal to clean while a newer session is active.
- Fixture tests cover launched, ready, mod-loaded, timeout, missing BepInEx log, missing Unity log, and preferences update handoff behavior.
- Fixture tests cover Unicode and space-containing paths through dry-run, build errors, run, logs, status, stop, and clean, including undecodable log bytes.
- The same user-visible contract is checked on PowerShell and native Bash environments. Platform-specific launcher resolution is tested with profile fixtures rather than Steam.
- Manual smoke testing uses a real non-Steam or mirror modding profile and verifies build, deployment, process launch, BepInEx readiness, target-mod loading, player actions, log analysis, stop, and safe clean.
- Existing repository Markdown-link checks, `git diff --check`, and final worktree checks remain required. No general package test suite is assumed.

## Out of Scope

- MCP-based or scripted gameplay control.
- Automated verification of visual, input, combat, menu, save, or other in-game behavior.
- Automatic Steam URI launch or automatic discovery of Steam installations.
- Automatic support for WSL, Git Bash, Proton, or other compatibility layers outside the native Windows and Bash contract.
- Persistent log copies, generated test reports, or log archival in the mod repository.
- Deleting or resetting the entire Modding root.
- Removing newly deployed files without explicit user approval.
- Installing BepInEx, ModdingAPI, or other runtime dependencies.
- Changing the existing source decompiler, source-navigation documents, or general log-analysis strategy.
- Changing the external mod projects or game profiles used as reference examples.
- Implementing the CLI or any runtime behavior in this specification step.

## Further Notes

- The reference mod projects use a package directory named by the project target and may also produce archives. The directory is the normal build-test source; the archive is a recovery input.
- Package resources are first-class deployment files. A dependency DLL in a data directory, localization text, image, or JSON file must keep its package-relative location.
- The test workflow reports startup evidence only. A user statement about actual gameplay behavior remains required for a complete manual test record.
- The stack-safe rollback choice is recorded separately because allowing repeated runs while preserving older backups is non-obvious and affects future cleanup behavior.
