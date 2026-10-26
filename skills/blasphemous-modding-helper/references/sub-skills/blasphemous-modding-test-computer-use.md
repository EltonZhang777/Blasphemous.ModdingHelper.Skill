# Computer Use automated in-game testing

Agent MUST follow this guide only after [In-game test coordination](blasphemous-modding-test-in-game-coordination.md) selects Computer Use and completes the shared [Real-profile preparation](blasphemous-modding-test-real-profile.md). The Real-profile branch owns commands, profile safeguards, session operations, startup/log evidence, stop, cleanup, and snapshots. Computer Use owns only the selected in-game evidence phase.

## Authorization and window selection

The user's Computer Use choice authorizes one run of the listed operations on the selected disposable profile. It does not authorize another run or a time extension. A conditional-suitability probe is part of that run and its cap.

Agent MUST visually identify the game window from its visible content. If multiple candidates exist or the game window cannot be identified confidently, the agent MUST ask the user which window to use before interacting. Visual selection MUST NOT be described as a guarantee of process or window identity.

## Input, observation, and time cap

The agent MUST announce the agent-estimated hard time cap before the first game-directed input and MUST start the timer with that first input. In an observation-only run, the agent MUST announce the cap before the first test-specific observation and start the timer there. Window identification and initial-state preflight MUST NOT count toward the cap. The agent MUST NOT impose a fixed input-count ceiling.

Passive observation MAY be used in fast scenes, but observations are intermittent. The agent MUST report only states visible at an observation and MUST NOT infer a transient event, action, or transition between screen checks. A no-input run MAY be used when the user has named the visible state to inspect.

The agent MUST stop when the expected result succeeds or fails, an uninterpretable or preventing state occurs, or the cap is reached. A new run or time extension MUST receive fresh user authorization. The agent MAY perform ordinary in-game saving, resetting, quitting, and progress changes on the selected disposable profile when included in the plan. Before deleting local data through the operating-system UI, the agent MUST obtain explicit confirmation at the time of deletion.

## GUI and in-game console

The agent MUST use the game's GUI for the planned interaction. An in-game console command MAY be used only when trusted documentation or user-provided material establishes its exact syntax and relevant effects, and the command serves the stated test goal. The agent MUST include the command and expected visible result in the plan before method selection. If syntax, effects, or relevance are uncertain, the agent MUST NOT issue it. The in-game console MUST NOT be used to run an operating-system shell, arbitrary code, or unrelated commands.

## Evidence and completion

The agent MUST report only observed results. For every planned operation, the agent MUST record the expected result and what was visibly observed, and MUST identify gaps as unknown or unobserved. The agent MUST include visible errors and approximate times when available. The agent MUST NOT treat startup logs, profile operations, or xUnit output as Computer Use evidence. The agent MUST return the result and exact Test session ID to the coordinator, which follows the Real-profile branch's session and snapshot rules.

## Completion criterion

The report identifies the authorized plan, visible game window selection or ambiguity, time cap, Test session, expected and observed results, any unobserved interval, status, and next action. It makes no process/window identity guarantee and keeps Computer Use evidence separate from Player-performed, startup, logs, profile-lifecycle, and xUnit evidence.
