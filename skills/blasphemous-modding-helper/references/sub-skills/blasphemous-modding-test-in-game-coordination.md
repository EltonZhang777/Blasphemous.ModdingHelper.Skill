# In-game test coordination

The shared [Mod-test entry](blasphemous-modding-test.md) routes requests that need in-game behavior or a specified visible state here. This document owns the plan, Computer Use suitability assessment, user method choice, and handoff. The [Real-profile branch](blasphemous-modding-test-real-profile.md) remains authoritative for configuration, profile requirements, commands, build/package/deployment, launch, startup/log evidence, session tracking, stop, and cleanup.

## Plan and assess before setup

Before any profile setup, build, deployment, or launch, the agent MUST list the required in-game operations in order. For each operation, the agent MUST show its expected result, scene or save state, controls or interface interaction, observation target and evidence, required input/observation precision, available reasoning interval, and per-operation Computer Use rating and rationale. The overall rating MUST reflect the least suitable required operation. When controls matter, the agent MUST read the [manual Rewired keybinding guide](blasphemous-modding-test-rewired-keybindings.md) before planning an input.

The agent MUST assess Computer Use against every required operation and expected observation. The assessment MUST consider input timing and precision, observation cadence and visual precision, and the reasoning time available between interactions. The agent MUST NOT exclude movement, platforming, climbing, jumping, or combat solely because of its category.

- **Suitable:** Computer Use input timing, observation cadence, and available reasoning time can meet the precision required by every planned operation and expected observation.
- **Conditionally suitable:** required input timing, observation cadence, visual precision, or reasoning interval is uncertain for a specific operation. Before asking for the method choice, the agent MUST disclose the representative probe action, its expected control result, and how failure will be handled. If the user chooses Computer Use with the probe, the agent MUST include it in the listed run and apply the same time cap. If it misses the stated control result or precision, the agent MUST stop and report, and MUST NOT switch methods automatically.
- **Unsuitable:** any required operation or observation exceeds the available precision. The agent MUST name the operation and whether input timing, observation cadence, or reasoning time is insufficient. The agent MUST wait for the user to choose Player-performed verification, revise the plan, or cancel, and MUST NOT switch methods automatically.

If the requested outcome or target state is not clear enough to assess, the agent MUST ask for clarification before presenting a method choice. An explicit no-input observation MAY be used when the user names the visible state to inspect; the agent MUST list that state and its expected visible result in the plan.

## Method choice and common preparation

For every in-game run, present the operation list, expected results, suitability assessment, and available methods. When Computer Use is suitable or conditionally suitable, offer Player-performed verification or Computer Use; for a conditional rating, include the disclosed probe. When Computer Use is unsuitable, offer Player-performed verification, plan revision, or cancellation, and MUST NOT present Computer Use as an available method. The agent MUST wait for the user's method choice before any Real-profile preparation, build, deployment, or launch. A Computer Use choice authorizes only the listed operations for this run and its disclosed time cap. A revised plan requires a new assessment and method choice before setup. The agent MUST NOT infer, silently select, or automatically switch methods.

If the user cancels, end the run without Real-profile setup or other profile operations. Only after the user selects Player-performed verification or Computer Use for the current plan may the agent perform the shared Real-profile preflight, build/package/deployment, profile-local launch, and startup-evidence flow once, following the Real-profile branch. If preparation is blocked, the agent MUST report that phase and MUST NOT claim in-game evidence. After startup, the agent MUST hand off to exactly one selected evidence guide: [Player-performed in-game verification](blasphemous-modding-test-player-verification.md) or [Computer Use automated in-game testing](blasphemous-modding-test-computer-use.md). The evidence guide MUST NOT repeat common preparation or introduce alternate lifecycle commands.

Lifecycle-only requests such as build/deploy/launch, startup inspection, logs, stop, or cleanup with no requested in-game result MUST remain on the Real-profile route and MUST NOT require this method choice. Automated xUnit remains separate.

## Disposable-profile limits and reporting

The selected profile MUST be confirmed as disposable or a mirror installation under the Real-profile preflight. Within that profile, the agent MAY perform ordinary in-game saving, resetting, quitting, and progress changes needed by the listed plan. Before deleting local data through the operating-system UI, the agent MUST obtain explicit user confirmation at the time of that action; disposable-profile approval does not cover it.

Ordinary in-game penalties such as death, damage, or resource use MUST NOT by themselves stop or disqualify the selected in-game run. They affect the result only if they fail the planned expectation or prevent completion or interpretation. For Computer Use, the agent MUST stop when the expected result succeeds or fails, the state prevents completion or interpretation, or the announced time cap is reached.

The coordinator is not an evidence source. Reports MUST identify the selected method and Test session, list expected and observed results, and keep Player-performed, Computer Use, startup, Current log, Test log snapshot, profile-lifecycle, and xUnit evidence separate. The agent MUST apply the Real-profile branch's session-identity and snapshot rules to the returned in-game result.

## Completion criterion

The method is chosen before setup, the common Real-profile preparation runs once, and exactly one selected evidence guide receives the in-game phase. The report names each operation's expected and observed result, the selected method, session, status, and next action.
