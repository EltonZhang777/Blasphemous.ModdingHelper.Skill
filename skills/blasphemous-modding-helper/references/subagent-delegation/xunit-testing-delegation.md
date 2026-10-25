# Automated xUnit testing delegation

This reference owns delegation constraints for the Automated xUnit phase. The [Automated xUnit branch](../sub-skills/blasphemous-modding-test-automated-xunit.md) remains the authority for classifying and executing that route. Apply the shared [General subagent delegation guidelines](subagent-delegation-general-guidelines.md) as well.

## Assignment

The parent MUST classify the request as Automated xUnit before delegating. It MUST give the child the caller Mod repository, selected test project, exact command, and any relevant runner or framework constraint. An unclear project or command MUST be returned to the parent for resolution.

The child MAY run only the assigned deterministic test phase through the standard .NET test runner. The standard `dotnet test` command may compile the selected test project as part of that run. This validation-only assignment grants no permission to edit implementation, test, or project files.

The child MUST NOT use a Modding profile, launch or inspect the game, deploy an artifact, collect startup logs, or claim gameplay evidence. A failing or blocked test result MUST be reported with its actual runner result; it MUST NOT be replaced with a different runner or a real-profile check.

## Handoff

The child MUST report the selected project, exact command, runner result, exit status, concise failure evidence when applicable, and next action. A passing xUnit run is automated evidence and MUST NOT be reported as gameplay proof. Any Real-profile or **Player-performed in-game verification** phase remains separate and is handed back to the parent.

The parent retains ownership of code changes, route changes, interpretation, and any decision to rerun or select another phase.
