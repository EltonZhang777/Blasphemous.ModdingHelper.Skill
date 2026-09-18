# Spec: Mod test routing and execution boundaries

## Problem Statement

From a Blasphemous Mod developer's perspective, the Skill currently presents one testing workflow whose real-profile operations and automated code-test expectations are easy to conflate. An agent may launch a game for a deterministic code test, treat xUnit success as gameplay evidence, or describe a real-profile check without preserving the player's Manual verification boundary.

The ambiguity is sharper across project shapes. A prerequisite library such as `Blasphemous.NewbieEltonLibs` can have a production library, a sibling xUnit project, and a separate external Test Mod for real-game verification. A standalone Mod such as `Blasphemous.LocalizationPatcher` has a game-side production project and no equivalent library-consumer test project. The Skill needs one routing contract that supports both shapes without making a library Test Mod, a test project, and a production Mod interchangeable.

## Solution

Turn the existing mod-test document into a shared entry point. It keeps the information and constraints common to every test request, defines the boundary between Real-profile tests and Automated xUnit tests, and routes the request to one of two independent Markdown branch documents.

The Real-profile branch owns the existing build, package, profile, launch, startup-evidence, stop, cleanup, and Manual verification workflow. The Automated xUnit branch owns deterministic non-game tests and describes a sibling `<ModRepoName>.Tests` project that references the main Mod project and runs through the standard .NET test runner. A prerequisite library may additionally use a separate Test Mod as an external consumer for real-game verification; a standalone Mod may use its production Mod directly. Neither branch is allowed to claim the other branch's evidence.

## User Stories

1. As an AI agent, I want every Mod test request classified before execution, so that I choose the correct evidence and avoid launching unnecessary external processes.
2. As a Mod developer, I want requests requiring a real or mirror Modding profile, game process, BepInEx/Unity logs, or player actions routed to the Real-profile branch, so that real-game work follows the safe profile workflow.
3. As a Mod developer, I want requests that can run without a game process, Modding profile, runtime startup, or player action routed to the Automated xUnit branch, so that deterministic checks remain fast and repeatable.
4. As an AI agent, I want the route to treat test doubles as compatible with Automated xUnit tests, so that code can be tested without pretending that a simulated game is a real-game result.
5. As an AI agent, I want tests requiring actual Unity lifecycle, scene state, BepInEx startup, or player interaction routed to the Real-profile branch, so that xUnit cannot be used to overstate runtime coverage.
6. As a user, I want an ambiguous test request surfaced for clarification, so that the agent does not silently choose a destructive or incomplete route.
7. As a user requesting both test classes, I want them executed as separate phases with separate evidence, so that an xUnit result and a real-profile result remain distinguishable.
8. As a maintainer, I want the shared entry point to state that `mod_loaded` and startup logs do not prove gameplay behavior, so that automated startup evidence is not reported as a gameplay pass.
9. As a maintainer, I want the shared entry point to preserve common preflight, ownership, evidence, and safety constraints, so that the two branch documents do not drift on shared rules.
10. As an AI agent, I want the Real-profile branch to retain the existing build, package validation, deployment, launch, process ownership, log, stop, and newest-first cleanup contract, so that routing does not weaken established safety behavior.
11. As a player, I want Manual verification to remain a distinct player-operated evidence source, so that my observed visual, input, combat, menu, save, or other behavior is not confused with CLI output.
12. As a Mod developer, I want the Automated xUnit branch to explain that tests run through the normal .NET test runner, so that a hand-run program or custom success signal is not treated as the standard automated path.
13. As a Mod developer, I want every non-real-machine test in my Mod repository to use xUnit, so that the repository has one predictable automated test technology.
14. As a Mod developer, I want an Automated test project named `<ModRepoName>.Tests` next to the main Mod project, so that test ownership and project discovery are predictable.
15. As an AI agent, I want the Automated test project to reference the main Mod project, so that tests exercise the Mod's public or intended external behavior rather than copied implementations.
16. As a Mod developer, I want the production Mod target framework and game-side runtime contract left unchanged by adding automated tests, so that test infrastructure does not accidentally change the shipped Mod.
17. As a prerequisite-library maintainer, I want xUnit tests to exercise the library as an external consumer where practical, so that public API compatibility is tested at the consumer boundary.
18. As a prerequisite-library maintainer, I want a separate Test Mod recognized as a real-game verification artifact, so that library behavior requiring Unity, BepInEx, or game state can be exercised without confusing it with the xUnit project.
19. As a standalone-Mod maintainer, I want the production Mod itself to remain the default real-game artifact, so that the Skill does not require a redundant Test Mod for every repository.
20. As an AI agent, I want the route to distinguish a Test Mod from an Automated test project, so that I do not place game-side commands in xUnit or treat test-runner assemblies as deployable plugins.
21. As a Mod developer, I want an existing repository architecture preserved, so that routing guidance does not trigger an unsolicited project migration.
22. As a Mod developer starting without an established test layout, I want the small sibling-project convention offered as soft architecture guidance, so that I can add tests without inventing a new structure.
23. As a maintainer, I want the reference library-plus-Test-Mod architecture and the standalone-Mod architecture used as contrasting examples, so that the route teaches the boundary instead of copying either repository wholesale.
24. As a maintainer, I want this spec to define routing and execution boundaries without writing tests for one current Mod, so that the shared Skill remains reusable.
25. As a maintainer, I want the Skill repository's own Python CLI and fixture tests to remain under their existing contract, so that the caller-Mod xUnit rule does not contradict the Skill package's accepted test architecture.
26. As an AI agent, I want each branch to declare its completion evidence and next action, so that a passing automated test, a blocked profile setup, and a pending Manual verification cannot be reported as the same state.
27. As a documentation maintainer, I want the shared entry point to link to exactly one owner for each branch, so that future changes have an obvious authoritative document.

## Implementation Decisions

- The highest seam is the existing shared Mod-test entry point. The outer Skill routing remains stable; the entry point adds a test-kind decision table and links to the two branch owners.
- The shared entry point owns only rules common to both branches: request classification, ownership boundaries, common prerequisites, evidence vocabulary, ambiguity handling, combined-request sequencing, and the distinction between automated evidence and Manual verification.
- The Real-profile branch owns the existing real-game workflow. Its content moves out of the shared entry point without changing the established profile safety, process ownership, log, startup-state, stop, or cleanup contract.
- The Automated xUnit branch owns all non-real-machine test guidance. It uses xUnit and the standard .NET test runner; it does not start the game, mutate a Modding profile, depend on player actions, or claim gameplay evidence.
- The boundary is operational, not based only on referenced assemblies: a test may reference Unity or game-facing types and remain an Automated xUnit test if it runs without the real game process, profile, lifecycle, or player. A test that needs those runtime conditions is a Real-profile test.
- A request that explicitly needs both branches is represented as two ordered phases. Automated xUnit runs first when it is available; Real-profile verification remains a separate phase with separate evidence. An ambiguous request is clarified before choosing a branch.
- Every caller Mod repository that adopts automated tests uses a sibling `<ModRepoName>.Tests` project for xUnit tests and keeps the main Mod project as the production reference. The exact test target framework must be compatible with the repository's supported .NET tooling and does not change the production Mod target by implication.
- The test project is not a deployable game artifact. It may use mocks, stubs, or ordinary .NET-compatible test seams, but it must not be described as a Test Mod.
- A Test Mod is an optional real-game consumer artifact. It is appropriate for a prerequisite library or another project whose behavior must be exercised from an external game-side consumer; it is not a mandatory project for every standalone Mod.
- The library-plus-Test-Mod architecture and the standalone-Mod architecture are prior art for routing decisions, not templates that trigger repository-wide restructuring.
- Existing project architecture takes precedence. The sibling naming and placement rule is soft guidance for a caller repository adding this capability, not a migration requirement for unrelated existing projects.
- The Skill repository's own Python CLI and fixture tests remain governed by their existing Python standard-library decisions. The xUnit rule applies to caller Mod repositories, not to this Skill package's internal test suite.
- The route documents describe behavior and evidence only. This spec does not create a concrete `<ModRepoName>.Tests` project, add concrete test cases, create a Test Mod, change the CLI, or run a real profile.

## Testing Decisions

- The primary test seam is the shared entry-point route. Documentation checks should prove that a request requiring a game/profile/player reaches the Real-profile branch and a deterministic non-game request reaches the Automated xUnit branch.
- Tests verify observable routing, branch links, boundary wording, and evidence separation rather than the internal organization or exact prose of the documents.
- Automated-branch checks should verify the xUnit requirement, standard test-runner execution, sibling test-project convention, main-project reference, no-game boundary, and distinction from a Test Mod.
- Real-profile checks should verify that the existing build/deploy/launch/log/stop/clean workflow remains the sole owner of real-game operations and that Manual verification stays player-operated.
- Combined-request checks should verify separate phase/evidence handling and rejection of implicit route guesses for ambiguous requests.
- Architecture checks should cover both prior-art shapes: a prerequisite library with a sibling xUnit project and optional external Test Mod, and a standalone Mod whose production project is the real-game artifact.
- Repository documentation-link checks, `git diff --check`, and final worktree inspection remain required. No real-game run is part of implementing or verifying this routing spec.
- The spec does not require concrete tests for the current Skill repository or any one caller Mod; those belong to later implementation tickets in the affected repository.

## Out of Scope

- Writing xUnit tests for a particular current Mod or library feature.
- Creating or modifying a caller Mod's production project, `<ModRepoName>.Tests` project, or Test Mod.
- Mandating a Test Mod for every standalone Mod repository.
- Replacing xUnit with another automated test framework, or changing the Skill repository's Python test framework.
- Changing the existing Python `blasphemous-modding-test` CLI, profile safety behavior, log analyzer, process control, or cleanup policy.
- Automating gameplay or treating startup evidence as gameplay verification.
- Building, deploying, launching, or cleaning a real game profile during this requirements/specification work.
- Migrating established caller-repository directory or project architecture.
- Adding a new dependency to the installed Skill solely to support routing documentation.
- Publishing a concrete test matrix for one Mod; the route only defines how later requests are classified.

## Further Notes

- `Blasphemous.NewbieEltonLibs` demonstrates the library shape: production library, sibling xUnit project, and a separate game-side Test Mod. Its xUnit tests run as ordinary .NET tests, while its Test Mod is packaged for real-game verification.
- `Blasphemous.LocalizationPatcher` demonstrates the standalone-Mod shape: the production project is the natural real-game artifact, and the absence of a sibling xUnit project is an architecture fact, not evidence that real-game checks belong in xUnit.
- The route should preserve the existing `Manual verification`, `Test session`, `Modding profile`, `Automated xUnit test`, `Automated test project`, and `Test Mod` glossary terms.
- A future implementation may add a concrete xUnit project or branch-specific documentation tests in a caller repository; that work must keep the two evidence surfaces independent.
