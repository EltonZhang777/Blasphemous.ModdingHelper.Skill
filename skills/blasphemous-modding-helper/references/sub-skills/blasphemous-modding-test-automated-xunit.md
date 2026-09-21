# Automated xUnit branch

The shared [Mod-test entry](blasphemous-modding-test.md) routes here for deterministic tests that run without a real or mirror Modding profile, game process, runtime startup, Unity lifecycle or scene state, startup logs, or player actions. This document is the sole authoritative owner of the Automated xUnit route.

## Boundary

Automated xUnit tests:

- MUST use xUnit and the normal .NET test runner.
- MUST run without building, deploying to, or launching a game profile.
- MAY use mocks, stubs, and other test doubles; a simulated dependency does not become real-game evidence.
- MUST NOT claim that a passing test, startup log, `mod_loaded`, or any other automated result proves gameplay behavior.

Automated xUnit does not require `config.yml`, the Skill Python runtime,
`modding_profile_path`, a launcher, Unity logs, BepInEx, a game process, or any
Real-profile gate. Missing profile-only fields do not block this route.

If a test needs actual Unity lifecycle, scene state, BepInEx startup, a game process, a Modding profile, runtime logs, or player interaction, route it to the [Real-profile branch](blasphemous-modding-test-real-profile.md).

## Project convention

When a caller Mod repository adds automated tests, the soft convention is a sibling `<ModRepoName>.Tests` project next to the main Mod project. The test project:

1. References the main Mod project so tests exercise the intended public or external-consumer boundary rather than a copied implementation.
2. Uses a target framework compatible with the repository's supported .NET tooling.
3. Leaves the production Mod target framework and game-side runtime contract unchanged.
4. Runs through the standard `dotnet test` path; a hand-run program or custom success signal is not the standard automated route.
5. Remains a test-runner project and is not a deployable game plugin or **Test Mod**.

The sibling-project and naming convention is guidance for a repository adding this capability. Existing project architecture takes precedence; this route MUST NOT trigger an unsolicited migration.

## Architecture shapes

### Prerequisite library

A prerequisite library MAY use a production library, a sibling `<ModRepoName>.Tests` xUnit project, and an optional external Test Mod. The xUnit project tests deterministic library behavior as an external consumer where practical. The Test Mod is a separate Real-profile artifact for behavior that needs Unity, BepInEx, game state, or player interaction.

### Standalone Mod

A standalone Mod MAY keep its production Mod project as the default Real-profile artifact and have no sibling xUnit project. The absence of an xUnit project does not route real-game checks into xUnit, and a Test Mod is not mandatory.

These shapes are contrasting prior art, not templates for repository-wide restructuring.

## Execution and evidence

The standard command is `dotnet test <ModRepoName>.Tests`; it may compile the
test project as part of the standard test runner. A wrapper is valid only when
it delegates to the standard xUnit runner. `dotnet run`, a hand-written runner,
the Real-profile CLI, and a Test Mod MUST NOT silently replace xUnit.

Framework or command conflicts return `blocked` or `ambiguous`; the agent MUST
NOT silently switch runners. Evidence records the selected project, runner
output, test result, and exit status. The report status is exactly `passed`,
`failed`, or `blocked`, and states that xUnit is not gameplay proof.

Agent MUST NOT build, deploy, launch, inspect startup logs, stop a game process,
clean a profile, or collect player **Manual verification** in this branch.

For an explicit two-branch request, complete this branch first when it is available, then hand off to the [Real-profile branch](blasphemous-modding-test-real-profile.md). Keep the two phase results and their next actions separate.

## Completion criterion

The selected xUnit project runs through the standard test runner, references the main Mod project, and produces deterministic automated evidence without a real profile or game process. The report states that this evidence does not prove gameplay and names any separately required Real-profile or **Manual verification** phase.
