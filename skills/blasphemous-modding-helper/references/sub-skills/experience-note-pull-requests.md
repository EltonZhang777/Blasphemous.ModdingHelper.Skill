# Experience note pull requests

This reference owns the separate publication approval for locally saved Blasphemous 1 experience notes. It follows [Experience note local save](experience-note-local-save.md), but a local-save yes does not authorize a pull request.

## Eligibility and proposal batch

- Only paths returned by `scripts/save_experience_note.py` after an explicit local-save yes in the current task are eligible. The main task MUST NOT scan for or submit older local notes, declined candidates, duplicates, deferred findings, or Blasphemous 2 findings.
- The main task MUST use the `config.yml` path selected by invocation preflight and MUST prepare the full proposal batch before asking for PR decisions:

```bash
"$PYTHON3" "$SKILL_ROOT/scripts/experience_note_pull_requests.py" --preferences-file "$PREFERENCES_FILE" "$SAVED_NOTE_1" "$SAVED_NOTE_2"
```

```powershell
& $PYTHON3 (Join-Path $SkillRoot 'scripts\experience_note_pull_requests.py') --preferences-file $PreferencesFile $SavedNotePaths
```

- The destination MUST be resolved from the installed Skill repository metadata, such as `.codex-plugin/plugin.json` or `package.json`. The main task MUST NOT use the caller Mod repository as the PR destination.
- Before presenting proposals, the main task MUST review every exact note body for the same privacy boundary used at local save. Caller data, raw logs or configuration, credentials, personal or machine identifiers, and absolute paths MUST be removed. If any content changes after local-save approval, the main task MUST show the revised note and obtain local-save approval again before proposing a PR.
- The main task MUST present every proposed PR together and identify the destination repository and default branch. For each, it MUST show the exact full title, exact full body, candidate file path, and exact candidate file content. The proposal script includes the candidate content in the PR body and prints no local configuration path.
- The main task MUST ask a separate yes/no question for each PR. Only a clear yes for that specific proposal authorizes creating it. No, an unclear answer, or silence MUST mean no PR for that item. One approval MUST NOT approve another.

## Create approved proposals

For each explicit yes, the main task MUST create one branch from the destination repository's default branch and add the exact approved content at `docs/modding-knowledge/candidates/<topic-slug>.md`. It MUST create the PR with the exact title and body shown in the batch. It MUST NOT overwrite an existing branch or candidate path; it MUST report the conflict and keep the local note.

The main task MUST create only approved PRs. A declined PR MUST leave its local note untouched. The main task MUST NOT merge any PR or update canonical indexes. Candidate notes MUST remain outside canonical indexing and retrieval until maintainer review. If creation fails, the main task MUST report the failure and keep the local note.

## Completion criteria

Done when every eligible locally saved note was included in one proposal batch, each PR received its own decision, only explicit yes decisions invoked PR operations, and each successful PR contains the exact approved candidate content. The main task MUST report created PR links, declined items, and failures.

Next action: continue the main task; maintainers review candidate PRs before any canonical promotion.
