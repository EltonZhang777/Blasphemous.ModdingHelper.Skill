---
status: accepted
---

# Preserve user-confirmed Test session log snapshots

The mod-testing workflow reads live BepInEx and Unity current logs, but a later
game launch can overwrite the evidence for an earlier Manual verification. The
user can confirm that a Test session is complete even when the game remains
running, so the workflow needs a stable copy without turning every current-log
read into persistent archival.

## Decision

- Capture a Test log snapshot only after the user explicitly confirms that the
  Test session is complete or provides its natural-language test result.
- Store complete BepInEx and Unity byte copies in that Test session's temporary
  session data. Leave original log locations and files unchanged.
- If the tracked game process is running, request ordinary stop approval. After
  an approved stop succeeds, capture after the tracked process tree exits. If
  the user explicitly declines stop, or an approved force stop fails, capture
  the current contents and record that condition. An unanswered approval stays
  pending.
- Use the existing Python mod-testing CLI and `TestSession` lifecycle seam. Do
  not add a second standalone log-copy implementation.
- For completed Test session analysis, the log-analyzer uses the snapshot. It
  uses a live current log only when the user explicitly asks for current
  evidence, and it does not silently fall back when a requested snapshot is
  missing or incomplete.

## Consequences

- A later game launch cannot overwrite the two-source evidence selected for a
  completed Test session.
- A snapshot taken while the game remains running is valid stable evidence of
  the bytes available at capture time, but its process and stop condition are
  visible and it is not described as post-stop final output.
- Snapshot files remain with archived or cleaned session data and are not added
  to the caller Mod repository or game profile.
- The general no-complete-copy rule remains in force for active/current-log
  analysis; this ADR is a user-confirmed session-data exception only.
