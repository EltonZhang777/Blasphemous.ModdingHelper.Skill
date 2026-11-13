# Player-performed in-game verification

The agent MUST follow this guide only after [In-game test coordination](blasphemous-modding-test-in-game-coordination.md) selects Player-performed verification and the shared [Real-profile preparation](blasphemous-modding-test-real-profile.md) has produced startup evidence. The Real-profile branch remains authoritative for every command, profile safeguard, session operation, and snapshot.

## Perform and record the planned scenario

1. The agent MUST confirm the exact Test session and the scene or save state used. It MUST follow the operation list and expected result supplied by the coordinator.
2. The player MUST perform the listed game actions and report what was visible. For a no-input observation, the player MAY describe the named target state without taking an action.
3. For each operation, the agent MUST record the expected result, exact player action or observation, and observed result. The agent MUST include visible errors and their approximate time, and MUST mark a result unknown or unobserved when it was not seen. The agent MUST NOT infer it from startup logs or another evidence source.
4. The agent MUST return a clear success, failure, or anomalous result to the coordinator with the same session ID. The Real-profile branch owns any log collection or snapshot that follows.

The coordinator's ordinary-penalty rule and disposable-profile limits apply to this run.

## Completion criterion

The report MUST identify the Test session, scene/save state, exact actions, expected and observed results, visible errors or approximate failure time, status, and next action. Player-performed evidence remains separate from Computer Use, startup, logs, profile-lifecycle operations, and xUnit.
