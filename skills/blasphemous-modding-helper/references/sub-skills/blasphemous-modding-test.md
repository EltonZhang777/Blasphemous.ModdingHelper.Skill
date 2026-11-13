# `/blasphemous-modding-test`

The top-level `blasphemous-modding-helper` Skill routes every Mod test request through this shared entry. This document owns request classification, common prerequisites, evidence vocabulary, ambiguity handling, combined-request sequencing, and the boundary between automated evidence and **Player-performed in-game verification** or **Computer Use automated in-game testing**.

The branch documents own their workflows. The shared entry MUST NOT duplicate their operational steps or treat their evidence as interchangeable:

- [Automated xUnit branch](blasphemous-modding-test-automated-xunit.md) is the sole authoritative owner of deterministic non-game tests.
- [Real-profile branch](blasphemous-modding-test-real-profile.md) remains the sole authority for Real-profile commands and lifecycle safeguards.
- [In-game test coordination](blasphemous-modding-test-in-game-coordination.md) owns in-game planning, Computer Use suitability, method choice before setup, and handoff.
- [Player-performed in-game verification](blasphemous-modding-test-player-verification.md) and [Computer Use automated in-game testing](blasphemous-modding-test-computer-use.md) own their evidence procedures. The [manual Rewired keybinding guide](blasphemous-modding-test-rewired-keybindings.md) supports Computer Use planning.

## Test-route and evidence vocabulary

The following terms are distinct and MUST be used consistently in route and completion reports. Player-performed and Computer Use terms name in-game evidence sources; Real-profile names the execution environment and lifecycle. Profile setup, deployment, launch, log collection, process tracking, stop, and cleanup are operational work, not in-game evidence. In-game test coordination is orchestration, not an evidence source.

| Term | Meaning and boundary |
| --- | --- |
| `Current log` | Live configured BepInEx/Unity sources read for diagnosis with explicit `--current`; it is not completed-session evidence. |
| `Test log snapshot` | Complete, session-bound BepInEx/Unity evidence captured for one Test session with explicit `--snapshot`; it never falls back to a live log. |
| `Player-performed in-game verification` | Player-operated observation of in-game behavior, kept separate from Computer Use automated in-game test evidence, CLI, startup, test-runner output, and profile operations. |
| `Computer Use automated in-game test` | Automated in-game evidence produced through Computer Use, kept separate from Player-performed in-game verification, Automated xUnit output, and Real-profile operations. |
| `Automated xUnit test` | Deterministic caller-Mod test run through the standard xUnit/.NET runner without a real profile or game process. |
| `Real-profile test` | Test phase that uses a disposable or mirror Modding profile; it describes the execution environment and lifecycle, not the evidence method. Report startup and in-game evidence separately. |

`launched`, `ready`, and `mod_loaded` are startup states, not gameplay proof. An automated xUnit result is automated evidence, not gameplay proof. A Test session is identified by its exact session ID; evidence from one session MUST NOT be attributed to another.

## Shared entry conditions

1. Agent MUST classify the request through this entry before choosing a test branch. Real-profile and other Skill-owned operations MUST complete the shared [Invocation preflight](../config/invocation-preflight.md); caller-owned Automated xUnit classification and execution do not wait for that gate.
2. Agent MUST identify whether the request needs a real or mirror **Modding profile**, a game process, runtime startup, BepInEx or Unity logs, actual Unity lifecycle or scene state, in-game behavior, player actions, or a specified visible state.
3. Agent MUST preserve the distinction between caller Mod repositories, the Skill repository, Mod-owned code, generated output, and external game artifacts.
4. Agent MUST keep **Player-performed in-game verification**, **Computer Use automated in-game test**, and Automated xUnit output distinct. Startup logs are not in-game evidence.

Classification happens before branch-specific gates. A caller-owned Automated xUnit request does not invoke Skill scripts or require the Skill's configuration or Python runtime; the Real-profile branch owns its own preflight and profile requirements.

## Route decision table

| Signal / condition | Destination | Boundary / next action |
| --- | --- | --- |
| Needs a real or mirror Modding profile, game process, runtime startup/lifecycle, BepInEx or Unity logs, in-game behavior, player actions, or a specified visible state | [In-game test coordination](blasphemous-modding-test-in-game-coordination.md) for in-game behavior or a specified visible state; [Real-profile branch](blasphemous-modding-test-real-profile.md) for lifecycle-only work | Agent MUST route in-game behavior and specified visible-state checks through coordination and lifecycle-only work directly to Real-profile; Real-profile MUST own build/package/deploy/launch/log/stop/cleanup; Agent MUST keep startup evidence separate from **Player-performed in-game verification** and **Computer Use automated in-game test** evidence. |
| Is deterministic and can run without a game process, Modding profile, runtime startup/lifecycle, startup logs, or player action | [Automated xUnit branch](blasphemous-modding-test-automated-xunit.md) | Agent MUST use the standard xUnit/.NET runner; its output MUST remain automated evidence and MUST NOT be reported as gameplay proof. |
| Explicitly requests both kinds of test | Both branch owners | Agent MUST run Automated xUnit first when available, then the Real-profile phase; if it requires in-game behavior or a specified visible state, Agent MUST use coordination before setup and hand off to one selected evidence guide. Agent MUST keep each phase's status and evidence separate. |
| Runtime or evidence conditions are unclear or conflicting | Ambiguous result | Agent MUST ask the user to clarify before routing and MUST run no branch command until clarified. |

## Route result contract

The agent MUST return exactly one route result: `Real-profile`, `xUnit`, `both`, or `ambiguous`. `ambiguous` is a no-execution result: the agent MUST NOT execute a branch command until the user clarifies the required runtime conditions and evidence.

An in-game behavior or specified visible-state request returns Real-profile and MUST pass through In-game test coordination before setup; lifecycle-only Real-profile requests go directly to the Real-profile branch.

## Both-phase and final report contract

For a `both` result, the xUnit phase first runs; the Real-profile phase second runs. The xUnit phase does not wait for Real-profile configuration; the Real-profile phase runs its own branch gate independently.

For any Real-profile phase requiring in-game behavior or a specified visible state, the agent MUST obtain the method choice before preparation, run common preparation once, and hand off to one selected evidence guide. Lifecycle-only Real-profile work stays direct.

Each phase records independent commands, independent evidence, and independent statuses. A failure or block in one phase does not fabricate the other phase result. Both is complete only after all required phases complete.

Conflicting environment or evidence requirements return `ambiguous` or `unresolved`. Ambiguous requests execute no test or profile command. The final report MUST include route, per-phase command, status, completion evidence, blocked reason when applicable, and next action; Automated xUnit, startup, **Player-performed in-game verification**, and **Computer Use automated in-game test** evidence remain separate.

Test doubles, mocks, and stubs remain compatible with the Automated xUnit route when the test does not require the real game process, profile, lifecycle, or player. A test that needs those runtime conditions belongs to the Real-profile route even when it references Unity or game-facing types.

## Common evidence and safety rules

- `mod_loaded` and other startup logs show startup evidence only. They MUST NOT be reported as gameplay verification.
- **Player-performed in-game verification** is player-operated evidence. It records the scene or save state, exact actions, expected result, observed result, and visible errors or approximate failure time.
- **Computer Use automated in-game test** is automated in-game evidence and MUST remain distinct from player-operated evidence and Real-profile setup or lifecycle operations.
- Reports MUST keep Player-performed, Computer Use, startup, Current log, Test log snapshot, profile-lifecycle, and Automated xUnit evidence separate.
- A combined request is complete only when each selected phase has its own state and evidence, or a warning names the exact blocked phase.
- Existing caller architecture takes precedence. The route MUST NOT trigger a repository-wide migration, create a concrete current-Mod test, or require a Test Mod for every standalone Mod.
- The Skill repository's Python CLI and fixture tests remain under their existing Python test contract. The caller-Mod xUnit convention does not redirect or replace them.
- A Test Mod is a game-side real-profile artifact; an Automated test project is a standard .NET test project. They MUST NOT be described as interchangeable.

## Subagent guidance

Any delegated test work MUST follow the shared [General subagent delegation guidelines](../subagent-delegation/subagent-delegation-general-guidelines.md). The selected phase MUST also follow its owner: [Automated xUnit testing delegation](../subagent-delegation/xunit-testing-delegation.md) or [Real-profile testing delegation](../subagent-delegation/real-profile-testing-delegation.md). An ambiguous request remains unresolved and MUST NOT be delegated as an executable test phase. For a `both` result, the parent MUST assign the Automated xUnit phase to one child first, then assign the Real-profile phase to a separate child after the xUnit handoff; each child MUST report only its own phase, keeping status, evidence, blocked reason, and next action independent. If a child for a selected test phase is unavailable, the parent MUST report that phase as blocked with the reason and next action; it MUST NOT run the assigned tests as a fallback.

## Manual completion and session identity

The agent MUST treat an explicit statement that testing is complete or a natural-language success, failure, or anomalous result as a snapshot trigger only when the result is clear and can be associated with exactly one Test session. An ambiguous result or an unclear session identity remains unresolved.

When the result or session is ambiguous, the agent MUST NOT invoke `snapshot`, MUST NOT select the newest session by guess, and MUST NOT infer the session from process state. The agent MUST ask the user for the Test session ID and any missing result detail before capturing evidence. Process exit, startup polling, `logs`, `stop`, and `clean` MUST NOT resolve a missing completion confirmation or session identity.

## Completion criterion

The request is classified before execution, the selected branch owns the operational steps, and the final report names status, completion evidence, blocked reason when applicable, next action, and Automated xUnit, startup, **Player-performed in-game verification**, and **Computer Use automated in-game test** evidence separately. The `/blasphemous-modding-test stop SESSION_ID` safety path is owned by the [Real-profile branch](blasphemous-modding-test-real-profile.md).
