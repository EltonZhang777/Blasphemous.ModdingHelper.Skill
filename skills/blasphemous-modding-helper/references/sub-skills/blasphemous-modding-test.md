# `/blasphemous-modding-test`

The top-level `blasphemous-modding-helper` Skill routes every Mod test request through this shared entry. This document owns request classification, common prerequisites, evidence vocabulary, ambiguity handling, combined-request sequencing, and the boundary between automated evidence and **Manual verification**.

The branch documents own their workflows. The shared entry MUST NOT duplicate their operational steps or treat their evidence as interchangeable:

- [Automated xUnit branch](blasphemous-modding-test-automated-xunit.md) is the sole authoritative owner of deterministic non-game tests.
- [Real-profile branch](blasphemous-modding-test-real-profile.md) is the sole authoritative owner of real-profile operations and player-operated verification.

## Shared entry conditions

1. Agent MUST classify the request through this entry before choosing a test branch. Real-profile and other Skill-owned operations MUST complete the shared [Invocation preflight](../config/invocation-preflight.md); caller-owned Automated xUnit classification and execution do not wait for that gate.
2. Agent MUST identify whether the request needs a real or mirror **Modding profile**, a game process, runtime startup, BepInEx or Unity logs, actual Unity lifecycle or scene state, or player actions.
3. Agent MUST preserve the distinction between caller Mod repositories, the Skill repository, Mod-owned code, generated output, and external game artifacts.
4. Agent MUST keep automated evidence separate from **Manual verification**. A test runner result or startup log is not a player observation.

Classification happens before branch-specific gates. A caller-owned Automated
xUnit request does not invoke Skill scripts or require the Skill's configuration
or Python runtime; the Real-profile branch owns its own preflight and profile
requirements.

## Route decision table

| Request condition | Route | Evidence boundary |
| --- | --- | --- |
| Needs a real or mirror Modding profile, game process, BepInEx or Unity startup, actual Unity lifecycle or scene state, runtime logs, or player actions | [Real-profile branch](blasphemous-modding-test-real-profile.md) | Build, package, deployment, launch, startup evidence, stop, cleanup, and player **Manual verification** remain separate states. |
| Is deterministic and can run without a game process, Modding profile, runtime lifecycle, startup logs, or player action | [Automated xUnit branch](blasphemous-modding-test-automated-xunit.md) | Standard xUnit runner output is automated test evidence only; it is not gameplay evidence. |
| Explicitly requests both kinds of test | Run two ordered phases: Automated xUnit first when available, then Real-profile | Record each phase and its evidence independently; neither phase promotes the other. |
| Leaves the required runtime conditions unclear | Ask the user to clarify before choosing a route | Agent MUST NOT silently choose a destructive, incomplete, or evidence-incompatible route. |

## Route result contract

The agent MUST return exactly one route result: `Real-profile`, `xUnit`, `both`, or
`ambiguous`. `ambiguous` is a no-execution result: the agent MUST NOT execute a
branch command until the user clarifies the required runtime conditions and
evidence.

## Both-phase and final report contract

For a `both` result, the xUnit phase first runs; the Real-profile phase second
runs. The xUnit phase does not wait for Real-profile configuration; the
Real-profile phase runs its own branch gate independently.

Each phase records independent commands, independent evidence, and independent statuses.
A failure or block in one phase does not fabricate the other phase
result. Both is complete only after all required phases complete.

Conflicting environment or evidence requirements return `ambiguous` or
`unresolved`. Ambiguous requests execute no test or profile command. The final
report MUST include route, per-phase command, evidence, status, blocked reason,
and next action; Automated, startup, and **Manual verification** evidence remain
separate.

Test doubles, mocks, and stubs remain compatible with the Automated xUnit route when the test does not require the real game process, profile, lifecycle, or player. A test that needs those runtime conditions belongs to the Real-profile route even when it references Unity or game-facing types.

## Common evidence and safety rules

- `mod_loaded` and other startup logs show startup evidence only. They MUST NOT be reported as gameplay verification.
- **Manual verification** is player-operated evidence. It records the scene or save state, exact actions, expected result, observed result, and visible errors or approximate failure time.
- A combined request is complete only when each selected phase has its own state and evidence, or a warning names the exact blocked phase.
- Existing caller architecture takes precedence. The route MUST NOT trigger a repository-wide migration, create a concrete current-Mod test, or require a Test Mod for every standalone Mod.
- The Skill repository's Python CLI and fixture tests remain under their existing Python test contract. The caller-Mod xUnit convention does not redirect or replace them.
- A Test Mod is a game-side real-profile artifact; an Automated test project is a standard .NET test project. They MUST NOT be described as interchangeable.

## Manual completion and session identity

The agent MUST treat an explicit statement that testing is complete or a
natural-language success, failure, or anomalous result as a snapshot trigger
only when the result is clear and can be associated with exactly one Test
session. An ambiguous result or an unclear session identity remains unresolved.

When the result or session is ambiguous, the agent MUST NOT invoke `snapshot`,
MUST NOT select the newest session by guess, and MUST NOT infer the session from
process state.
The agent MUST ask the user for the Test session ID and any missing result
detail before capturing evidence. Process exit, startup polling, `logs`,
`stop`, and `clean` MUST NOT resolve a missing completion confirmation or
session identity.

## Completion criterion

The request is classified before execution, the selected branch owns the operational steps, and the final report names automated, startup, and **Manual verification** evidence separately. The `/blasphemous-modding-test stop SESSION_ID` safety path is owned by the [Real-profile branch](blasphemous-modding-test-real-profile.md).
