# Spec: Manual test log snapshots

## Problem Statement

The real-profile Test workflow currently reads the BepInEx and Unity **current
logs** in place. A later game launch can overwrite the BepInEx log before the
agent analyzes the result of an earlier Manual verification. The user can
provide a completed test result, but the evidence for that result is not
reliably preserved as a complete, session-bound artifact.

The workflow must preserve both log sources after the user confirms that the
Test session is complete. It must also handle the case where the user has
finished the Manual verification but has not closed the game. Stopping the
game can itself produce useful log records, so stop authorization and snapshot
capture must remain separate, visible decisions.

## Solution

Add a log-snapshot operation to the existing Python mod-testing CLI and its
`TestSession` lifecycle seam. The operation stores a complete BepInEx copy and
a complete Unity copy in the session data for the associated Test session. It
never moves, truncates, deletes, or changes the original logs.

The agent triggers the operation only after the user explicitly confirms that
the test is complete or supplies a natural-language test result. Process exit,
startup polling, `logs`, `stop`, and `clean` do not trigger a snapshot by
themselves.

If the tracked game process has already exited, the operation copies both
sources immediately. If it is still running, the agent tells the user and
requests permission to stop it. An approved stop is performed through the
existing tracked-process stop seam; after the process tree exits, the
operation copies the logs. If the user explicitly declines stop, or an
approved force stop fails, the operation copies the current log contents
instead and records that the process was still running or that stopping failed.
If the user does not answer the stop request, the snapshot remains pending;
the agent does not infer approval or capture in the same turn.

Each source is copied independently into a dedicated snapshot directory under
the Test session's temporary session data. Source-specific target names prevent
collisions. A repeated capture for the same session replaces that session's
same-source snapshot and updates its metadata. The session manifest records
per-source status, capture conditions, process state, stop decision/result,
source and target paths, byte counts, and digests. A missing or failed source
does not delete a successful source; the overall snapshot is marked incomplete.

When a completed Test session is analyzed, the log-analyzer workflow uses its
Test log snapshot as the evidence source. It does not silently fall back to a
profile current log that may belong to a later launch. Analysis of a current
log remains available only when the user explicitly asks for current evidence.

## User Stories

1. As a mod developer, I want the agent to preserve logs after I confirm that a Test session is complete, so that later launches cannot erase the evidence for my result.
2. As a mod developer, I want a successful Manual verification result to trigger preservation, so that a positive gameplay observation has bounded session evidence.
3. As a mod developer, I want a failed or anomalous Manual verification result to trigger preservation, so that failure analysis retains the same evidence as success analysis.
4. As a mod developer, I want the agent to recognize an explicit statement that testing is complete, so that I do not need to know an internal CLI command to preserve evidence.
5. As a mod developer, I want a process exit alone not to trigger preservation, so that the agent does not infer that a test was complete when the game crashed or was closed for another reason.
6. As a mod developer, I want startup polling alone not to trigger preservation, so that launch evidence is not mistaken for a completed Manual verification.
7. As a mod developer, I want `logs`, `stop`, and `clean` alone not to trigger preservation, so that lifecycle commands do not silently perform an evidence decision for me.
8. As an AI agent, I want a snapshot request associated with one Test session, so that logs from another profile or run cannot be attached by guesswork.
9. As an AI agent, I want ambiguous natural-language results to remain unresolved, so that I can ask for the session identity instead of saving evidence under the wrong session.
10. As a mod developer, I want an already-exited game process to allow immediate capture after my completion confirmation, so that the normal workflow stays short.
11. As a mod developer, I want to be told when the game is still running after I report the result, so that I understand why the agent is requesting another decision.
12. As a mod developer, I want to approve a normal stop before the agent closes the game, so that saving evidence does not silently change my running game state.
13. As a mod developer, I want the snapshot taken after an approved stop completes, so that shutdown-generated log records are included when the stop succeeds.
14. As a mod developer, I want a failed normal stop to require a separate force-stop approval, so that a stronger process action is never inferred from the first approval.
15. As a mod developer, I want the current logs preserved if I explicitly decline normal stop, so that choosing to keep the game open does not discard evidence for a completed test.
16. As a mod developer, I want the current logs preserved if I explicitly decline force stop, so that a failed graceful stop still leaves usable evidence.
17. As a mod developer, I want the current logs preserved if an approved force stop fails, so that an operational stop failure does not erase the completed test result.
18. As an AI agent, I want no snapshot action while a stop-approval request is unanswered, so that silence is never treated as authorization.
19. As a mod developer, I want both BepInEx and Unity logs retained, so that analysis can use the framework and engine evidence together.
20. As a mod developer, I want the copies to contain the complete bytes available at capture time, so that bounded output limits do not destroy diagnostic context.
21. As a mod developer, I want the original BepInEx and Unity log locations left unchanged, so that the game and existing tools continue using their normal paths.
22. As a mod developer, I want original logs never deleted or moved by snapshot capture, so that the snapshot operation cannot cause data loss.
23. As an AI agent, I want snapshot sources resolved using the selected profile and existing Unity-log preference rules, so that the copy corresponds to the Test session that was actually run.
24. As a mod developer, I want snapshots stored in the session data for the associated Test session, so that evidence is isolated from the caller repository and game profile.
25. As a mod developer, I want archived and cleaned session state to retain its snapshot, so that later analysis can inspect evidence after rollback.
26. As an AI agent, I want source-specific target names, so that BepInEx and Unity files cannot overwrite each other when they have similar source names.
27. As a mod developer, I want repeated capture for one Test session to replace the same-source copy deterministically, so that the session has one discoverable current snapshot rather than an unbounded file set.
28. As a mod developer, I want a failed replacement not to destroy an older successful copy, so that a transient read or destination error preserves the last usable evidence.
29. As an AI agent, I want each source to report `copied`, `missing`, or `failed`, so that partial evidence is visible instead of being reported as complete.
30. As a mod developer, I want one successful source retained when the other source is unavailable, so that a Unity-log problem does not discard useful BepInEx evidence, and vice versa.
31. As an AI agent, I want the overall snapshot marked incomplete when either required source is missing or fails, so that downstream analysis does not claim that both logs were preserved.
32. As an AI agent, I want the manifest to record the capture condition and stop outcome, so that analysis can distinguish a post-stop snapshot from a current snapshot taken while the game remained running.
33. As an AI agent, I want a snapshot captured while the process is running to remain valid evidence of the confirmed Test session, so that a user's deliberate choice not to close the game is respected.
34. As an AI agent, I want a later capture after the user closes the game to update the same session snapshot, so that the session can converge on more complete shutdown evidence without creating duplicate artifacts.
35. As an AI agent, I want analysis of a completed Test session to read its Test log snapshot, so that a later game launch cannot silently change the evidence under analysis.
36. As an AI agent, I want analysis of a missing or incomplete snapshot to report that condition, so that the workflow does not silently substitute a different run's current log.
37. As a mod developer, I want an explicit current-log request to remain supported, so that live diagnosis is not confused with post-test evidence analysis.
38. As a maintainer, I want snapshot capture to reuse the existing Python mod-testing lifecycle seam, so that process identity, profile selection, and session ordering are not reimplemented.
39. As a maintainer, I want no second standalone log-copy script, so that there is one implementation boundary for Test session log operations.
40. As a maintainer, I want fixture coverage for exited, running, declined-stop, stop-failure, missing-source, copy-failure, repeated-capture, and profile-isolation cases, so that the evidence contract is regression-tested without a real game.

## Implementation Decisions

- The existing Python mod-testing CLI and its public `TestSession` lifecycle seam are the only implementation boundary. The log-copy operation is added to the existing Python script under the Skill's scripts directory; no standalone second script is introduced.
- The operation is exposed as a session-addressed snapshot command. The normal mode copies only after the tracked process tree is confirmed exited. An explicit current-capture mode is used only after the agent has recorded an explicit stop refusal or a stop failure; it permits copying while the process remains running and records that condition.
- The agent owns natural-language completion detection, session disambiguation, stop approval, and force-stop approval. The Python operation does not infer user approval from process state, command order, or silence.
- A user completion confirmation is the only trigger. The implementation does not automatically capture during launch, startup polling, `logs`, `stop`, `clean`, or a same-turn agent loop that has not received the user's completion/result response.
- When the process is running, the agent first asks for ordinary stop approval. On approval it reuses the existing tracked-process stop behavior. If ordinary stop fails, the agent asks separately for force-stop approval. An explicit refusal at either approval point or a failed approved force stop selects current-capture mode. An unanswered approval request remains pending.
- A successful ordinary or force stop is followed by snapshot capture only after the tracked process tree is confirmed exited. A process that was already exited is captured without a stop request.
- BepInEx and Unity are required snapshot sources. Their existing profile-relative and configured-directory resolution remains authoritative; the snapshot operation does not change log generation or source discovery rules.
- Each source is copied as a complete byte-preserving file into a source-specific target in the Test session's session data. Stable source names are used for the two targets, while the manifest retains the original source paths and filenames.
- Repeated capture for one session replaces the corresponding target atomically after a successful source read. A failed replacement leaves the prior successful target intact and records the new failure attempt.
- Source capture is independent. A successful source is retained when the other source is missing, unreadable, or fails to copy. The overall snapshot status is complete only when both required sources are copied successfully; otherwise it is incomplete.
- Snapshot metadata records capture time, source and target paths, byte count, digest, per-source status, process state, capture condition, and stop decision/result. The manifest stores metadata only, not a second copy of log contents.
- Snapshot files remain in the session data with the session manifest after archive or safe clean. They are not written into the caller Mod repository, the selected game profile, or the live log directories.
- The log-analyzer responsibility is split by evidence intent: a completed Test session requires its Test log snapshot; a current-log request uses the live source locations. Missing or incomplete snapshots are reported and are not silently replaced by current logs.
- The focused spec supersedes the earlier no-copy rule only for user-confirmed completed Test session snapshots. Dynamic baseline classification, bounded current-log output, startup states, and original-log ownership rules remain unchanged.
- The implementation contract is documented and tested through external behavior. It does not add a new dependency or change the Python standard-library runtime boundary.

## Testing Decisions

- Tests verify externally observable behavior: trigger mode, process-state guard, copy bytes, target names, source isolation, replacement behavior, manifest metadata, partial failure status, and downstream source selection. They do not assert private helper structure.
- The highest test seam is the existing `TestSession` lifecycle seam with its injectable process, file, and session-state adapters. It can exercise the full snapshot contract without starting a game or using a real profile.
- Existing Python `unittest` fixture tests for the mod-testing CLI and log diagnostics are the prior art. New tests extend those fixtures rather than introducing a new test framework or a second fake lifecycle.
- Fixture coverage includes: process already exited; normal stop approved and completed; ordinary stop failure followed by force approval; explicit ordinary-stop refusal; explicit force-stop refusal; force-stop failure; unanswered approval represented as pending; exact two-source byte copies; running-process current capture; source-specific naming; repeated capture replacement; failed replacement preserving the previous copy; missing and unreadable sources; one-source success with overall incomplete status; session/profile mismatch; and manifest metadata without embedded log content.
- Contract tests verify that current-log analysis remains current-log analysis, while completed-session analysis requires the session snapshot and reports missing/incomplete evidence without fallback.
- Documentation checks verify that the user-confirmation gate, stop/force approval distinction, current-capture fallback, snapshot location, retention, and log-analyzer source rule remain consistent with the glossary and the broader mod-testing spec.
- Required repository checks remain the existing Python syntax/fixture checks, Markdown link validation, `git diff --check`, and final worktree inspection. No real-game test is required to validate the file-copy seam; real-profile Manual verification remains a separate acceptance activity.

## Out of Scope

- Changing where Blasphemous or BepInEx writes its original logs.
- Deleting, moving, truncating, or rotating original logs.
- Automatically triggering a snapshot from launch, startup polling, process exit, `logs`, `stop`, `clean`, or an agent loop without the user's completion/result response.
- Automatically stopping or force-stopping the game without the required user approval.
- Treating `ready` or `mod_loaded` as proof of gameplay behavior.
- Replacing the existing log parser, diagnostic ownership rules, startup-state model, bounded current-log output, or Unity-log preference resolution.
- Creating a persistent repository report, a second log-copy script, or a new runtime dependency.
- Silently analyzing a later current log when the requested completed Test session snapshot is missing or incomplete.
- Controlling gameplay or generating a gameplay transcript.
- Implementing the feature, changing the installed Skill references, changing a game profile, or publishing a release artifact as part of this requirements task.

## Further Notes

- The snapshot is evidence for a user-confirmed Test session, not proof that the game behavior was correct. The Manual verification record and automated startup evidence remain separate evidence sources.
- A snapshot captured while the process remains running is valid as a stable copy of the bytes available at that moment, but its metadata must make the non-final process condition visible.
- The existing dynamic-baseline ADR prohibits complete log persistence as a general current-log behavior. This feature is a narrow, user-confirmed session-data exception and should be recorded in a focused ADR before implementation.
