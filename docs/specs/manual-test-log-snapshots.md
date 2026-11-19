# Spec: Preserve user-confirmed Test log snapshots

## Problem Statement

The real-profile Test workflow currently reads the BepInEx and Unity **Current log** sources in place. A later game launch can overwrite the BepInEx log before the agent analyzes the result of an earlier Player-performed in-game verification. The user can provide a completed test result, but the evidence for that result is not reliably preserved as a complete, session-bound artifact.

The workflow must preserve both log sources after the user confirms that the Test session is complete. It must also handle the case where the user has finished the Player-performed in-game verification but has not closed the game. Stopping the game can itself produce useful log records, so stop authorization and snapshot capture must remain separate, visible decisions.

## Rationale

The workflow needs stable evidence for a user-confirmed Test session without turning every Current log read into a persistent archive. The existing dynamic-baseline rule therefore has one narrow, accepted exception for completed Test-session data. The decision, operational behavior, and safety boundary are already established; this repository specification records why the exception exists and what it must achieve, while the installed Real-profile reference owns how to perform it.

## Requirements

- Snapshot capture is available only through the user-confirmed Test-session gate in the installed mod-test contract.
- The evidence is session-bound, preserves both required log sources without changing originals, and makes incomplete or partial capture visible.
- The workflow does not infer completion, stop, or force-stop approval from process state, lifecycle commands, or silence.
- Completed-session analysis uses that session's snapshot and does not silently substitute a Current log; explicit Current log analysis remains separate.
- The implementation continues to use the existing Python mod-testing lifecycle boundary and does not add a parallel log-copy surface.

## Acceptance Outcomes

- A later game launch cannot overwrite the evidence accepted for a user-confirmed Test session.
- Snapshot evidence with a non-final process condition, a missing source, or a failed source is reported as such rather than as complete post-stop evidence.
- Test log snapshot data remains available with its session after archive or safe clean and stays separate from Player-performed, startup, Current log, and profile-lifecycle evidence.
- The installed Real-profile reference remains sufficient for operation without the repository specification; no second operational contract or implementation path is introduced.
- ADR 0009 remains accepted and records the narrow exception to the general no-complete-copy rule.

## References

- [ADR 0009: Preserve user-confirmed Test session log snapshots](../adr/0009-user-confirmed-test-log-snapshots.md)
- [Installed Real-profile snapshot contract](../../skills/blasphemous-modding-helper/references/sub-skills/blasphemous-modding-test-real-profile.md)
- [Historical mod-test verification record](../verification/blasphemous-modding-test.md)
