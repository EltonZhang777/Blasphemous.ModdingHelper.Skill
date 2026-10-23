# Real-profile testing delegation

This reference owns delegation constraints for the Real-profile phase. The [Real-profile branch](../sub-skills/blasphemous-modding-test-real-profile.md) remains the authority for its gates, commands, lifecycle, and evidence. Apply the shared [General subagent delegation guidelines](subagent-delegation-general-guidelines.md) as well.

## Assignment

The parent MUST classify the request as Real-profile and complete the branch entry conditions before delegating profile operations. It MUST name the disposable or mirror Modding profile, caller project or selected artifact, exact permitted CLI actions, and the expected evidence. Any approval-gated action MUST have explicit user approval included in the assignment; the child MUST NOT make or infer that decision. A pending approval or missing gate MUST be returned to the parent before profile action. An operation on an existing Test session MUST include that exact session ID. If the child is assigned a `run` that creates a session, it MUST return the session ID emitted by the CLI and the process identity recorded for that session.

Each child task MUST stay within exactly one Test session and the assigned profile. It MUST NOT switch profiles or sessions, infer a session ID, touch unrelated processes, or run unassigned stop, snapshot, or clean operations. Missing gates, unclear scope, or a missing profile/session MUST be returned to the parent before any profile action.

The child MUST report only the evidence it collected. Startup states, CLI output, and logs MUST remain distinct from player-operated **Manual verification**; a child MUST NOT perform or infer the player's observation. The parent retains user decisions and any request for clarification.

## Handoff

The child MUST return the exact CLI commands, profile identity, Test session ID, and, for a session with a launched game process, the process ID and tracked process tree identity recorded in that session manifest. It MUST also return per-action status, evidence mode and locations, blocked reason when applicable, and next action. It MUST identify whether a result is startup evidence or player-provided **Manual verification**. Evidence from another profile or session MUST NOT be mixed into the report.

The parent remains responsible for integrating the result with any other phase and reporting the overall request. A Real-profile result MUST NOT be presented as an Automated xUnit result.
